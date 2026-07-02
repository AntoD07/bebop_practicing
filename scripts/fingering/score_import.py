"""Score import: MusicXML (exact) and PDF/image via OMR (best-effort).

Turns a written score into the pitch ``line`` the fingering optimizer consumes:
``{"pitch": midi, "start": onset_in_beats, "phrase_start": bool, "degree": ...}``
plus the chord context. Pitches from a score are ABSOLUTE — no octave choice,
no transposition; the optimizer only decides where on the neck to play them.

Parsing uses music21 when available (handles .xml/.musicxml/.mxl robustly) with
a small stdlib fallback for plain monophonic MusicXML. OMR runs through
``oemer`` (if installed) on a rendered PNG; its output is MusicXML, which flows
through the same parser — and the same human review table, because OMR is
never 100%.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from typing import List, Optional, Tuple
from xml.etree import ElementTree as ET

from scripts.fingering.chords import parse_chord

# Interval (from chord root) -> jazz degree name, for the tab's label lane.
_INTERVAL_DEGREE = {
    0: "1", 1: "b9", 2: "9", 3: "b3", 4: "3", 5: "11",
    6: "#11", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7",
}

_STEP_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# MusicXML harmony <kind> -> chord-symbol suffix.
_KIND_SUFFIX = {
    "major": "", "minor": "m", "dominant": "7", "major-seventh": "maj7",
    "minor-seventh": "m7", "half-diminished": "m7b5", "diminished": "dim",
    "diminished-seventh": "dim7", "augmented": "aug", "minor-sixth": "m6",
    "major-sixth": "6", "dominant-ninth": "9", "minor-ninth": "m9",
    "suspended-fourth": "7sus4",
}


# --------------------------------------------------------------------------- #
# MusicXML parsing
# --------------------------------------------------------------------------- #
def _read_musicxml_bytes(data: bytes) -> bytes:
    """Return raw XML bytes, unwrapping .mxl (zip) containers."""
    if data[:2] == b"PK":  # zip => .mxl
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as z:
            names = [n for n in z.namelist()
                     if n.endswith((".xml", ".musicxml")) and not n.startswith("META-INF")]
            if not names:
                raise ValueError("no MusicXML found inside .mxl container")
            return z.read(names[0])
    return data


def parse_musicxml(data: bytes) -> dict:
    """Parse (monophonic) MusicXML into notes, chords, and meter.

    Returns ``{"notes": [{"midi","start","duration","phrase_start","bar"}],
    "chords": [{"start_beat","symbol"}], "beats_per_bar": int}``.
    Ties are merged; rests mark the next note as a phrase start; extra chord
    tones (<chord/> elements) and grace notes are skipped — melody line only.
    """
    root = ET.fromstring(_read_musicxml_bytes(data))
    part = root.find("part")
    if part is None:
        raise ValueError("no <part> in MusicXML")

    notes: List[dict] = []
    chords: List[dict] = []
    divisions = 1
    beats_per_bar = 4
    onset = 0.0          # absolute, in quarter-note beats
    after_rest = True    # line start counts as a phrase start
    tie_open = False

    for m_i, measure in enumerate(part.findall("measure")):
        attrs = measure.find("attributes")
        if attrs is not None:
            d = attrs.find("divisions")
            if d is not None and d.text:
                divisions = int(d.text)
            t = attrs.find("time/beats")
            if t is not None and t.text:
                beats_per_bar = int(t.text)
        for el in measure:
            if el.tag == "harmony":
                step = el.findtext("root/root-step")
                alter = el.findtext("root/root-alter")
                kind_el = el.find("kind")
                if step:
                    sym = step + ({"1": "#", "-1": "b"}.get(alter, "") if alter else "")
                    kind_text = (kind_el.get("text") if kind_el is not None else None)
                    kind = (kind_el.text if kind_el is not None else "") or ""
                    sym += kind_text if kind_text else _KIND_SUFFIX.get(kind, "")
                    chords.append({"start_beat": onset, "symbol": sym})
            elif el.tag in ("backup", "forward"):
                dur = el.findtext("duration")
                delta = (float(dur) / divisions) if dur else 0.0
                onset += -delta if el.tag == "backup" else delta
            elif el.tag == "note":
                if el.find("grace") is not None:
                    continue
                if el.find("chord") is not None:
                    continue  # keep the melody note only
                dur_el = el.findtext("duration")
                dur = (float(dur_el) / divisions) if dur_el else 0.0
                if el.find("rest") is not None:
                    onset += dur
                    after_rest = True
                    continue
                pitch_el = el.find("pitch")
                if pitch_el is None:
                    onset += dur
                    continue
                step = pitch_el.findtext("step")
                alter = int(pitch_el.findtext("alter") or 0)
                octave = int(pitch_el.findtext("octave"))
                midi = (octave + 1) * 12 + _STEP_PC[step] + alter
                tie_types = {t.get("type") for t in el.findall("tie")}
                if tie_open and notes and notes[-1]["midi"] == midi:
                    # continuation of a tie: extend, don't re-strike
                    notes[-1]["duration"] += dur
                else:
                    notes.append({
                        "midi": midi, "start": onset, "duration": dur,
                        "phrase_start": after_rest, "bar": m_i + 1,
                    })
                    after_rest = False
                tie_open = "start" in tie_types and "stop" not in tie_types \
                    or ("start" in tie_types and "stop" in tie_types and tie_open)
                onset += dur
    if not notes:
        raise ValueError("no notes found in the score")
    return {"notes": notes, "chords": chords, "beats_per_bar": beats_per_bar}


def parse_with_music21(data: bytes) -> dict:
    """music21-backed parse (more tolerant); same output shape."""
    import music21
    with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as f:
        f.write(_read_musicxml_bytes(data))
        path = f.name
    try:
        score = music21.converter.parse(path)
    finally:
        os.unlink(path)
    part = score.parts[0] if score.parts else score
    flat = part.flatten()
    ts = flat.getElementsByClass(music21.meter.TimeSignature)
    beats_per_bar = int(ts[0].numerator) if ts else 4
    notes, chords = [], []
    prev_end = None
    for el in flat.stripTies().notesAndRests:
        onset = float(el.offset)
        if isinstance(el, music21.harmony.ChordSymbol):
            continue  # chord symbols are context, not sounding melody notes
        if isinstance(el, music21.note.Rest):
            prev_end = None
            continue
        pitch = el.pitches[0] if el.pitches else None  # top of any chord
        if pitch is None:
            continue
        notes.append({
            "midi": int(pitch.midi), "start": onset,
            "duration": float(el.quarterLength),
            "phrase_start": prev_end is None or onset > prev_end + 1e-6,
            "bar": int(el.measureNumber or 0),
        })
        prev_end = onset + float(el.quarterLength)
    for h in flat.getElementsByClass(music21.harmony.ChordSymbol):
        chords.append({"start_beat": float(h.offset), "symbol": h.figure})
    if not notes:
        raise ValueError("no notes found in the score")
    return {"notes": notes, "chords": chords, "beats_per_bar": beats_per_bar}


def parse_score(data: bytes) -> dict:
    """Best-effort parse: music21 if importable, stdlib fallback otherwise."""
    try:
        return parse_with_music21(data)
    except ImportError:
        return parse_musicxml(data)


# --------------------------------------------------------------------------- #
# Degrees / line building
# --------------------------------------------------------------------------- #
def chord_at(chords: List[dict], onset: float) -> Optional[str]:
    active, start = None, -1.0
    for c in chords:
        if c["start_beat"] <= onset + 1e-6 and c["start_beat"] >= start:
            active, start = c["symbol"], c["start_beat"]
    return active


def degree_for(midi: int, symbol: Optional[str]) -> Optional[str]:
    if not symbol:
        return None
    parsed = parse_chord(symbol)
    if parsed is None:
        return None
    root, _ = parsed
    return _INTERVAL_DEGREE[(midi - root) % 12]


def line_from_score(parsed: dict) -> Tuple[List[dict], dict]:
    """Build the optimizer ``line`` + ``context`` from a parsed score.

    Every note gets its jazz degree w.r.t. the active chord symbol — that is
    what labels chord tones on top of the tab.
    """
    chords = parsed["chords"]
    line = []
    for n in parsed["notes"]:
        sym = chord_at(chords, n["start"])
        line.append({
            "pitch": n["midi"],
            "start": n["start"],
            "phrase_start": n["phrase_start"],
            "degree": degree_for(n["midi"], sym),
            "cell": f"bar {n['bar']}" if n.get("bar") else None,
        })
    # Density: eighth feel if the typical inter-onset gap is < 1 beat.
    gaps = [b["start"] - a["start"] for a, b in zip(parsed["notes"], parsed["notes"][1:])]
    density = "eighth" if gaps and sorted(gaps)[len(gaps) // 2] < 0.99 else "quarter"
    context = {
        "chords": chords,
        "beats_per_bar": parsed["beats_per_bar"],
        "density": density,
    }
    return line, context


# --------------------------------------------------------------------------- #
# PDF / image -> MusicXML via OMR
# --------------------------------------------------------------------------- #
def pdf_to_png(pdf_path: str, out_dir: str, size: int = 4000) -> str:
    """Render page 1 of a PDF to PNG. Uses macOS qlmanage (no extra deps)."""
    subprocess.run(
        ["qlmanage", "-t", "-s", str(size), "-o", out_dir, pdf_path],
        capture_output=True, timeout=120,
    )
    png = os.path.join(out_dir, os.path.basename(pdf_path) + ".png")
    if not os.path.exists(png):
        raise RuntimeError("PDF rendering failed (qlmanage produced no PNG)")
    return png


# Preferred: an isolated venv with oemer's supported deps (numpy<2, opencv 4.x)
# — the main env's opencv-5/numpy-2 stack breaks oemer 0.1.x internally.
_OEMER_VENV_PYTHON = os.path.expanduser("~/.venvs/oemer-omr/bin/python")


def _omr_python() -> Optional[str]:
    if os.path.exists(_OEMER_VENV_PYTHON):
        return _OEMER_VENV_PYTHON
    if shutil.which("oemer") is not None:
        return "python"  # fall back to the current env (may be less compatible)
    return None


def omr_available() -> bool:
    return _omr_python() is not None


# oemer 0.1.x still uses NumPy<1.24 aliases (np.int / np.float / np.bool),
# which NumPy 2 removed. Rather than patching site-packages, run oemer through
# a shim that restores the aliases at runtime — self-contained and reversible.
_OEMER_SHIM = (
    "import sys, numpy as np\n"
    "for _a, _t in (('int', int), ('float', float), ('bool', bool)):\n"
    "    if not hasattr(np, _a):\n"
    "        setattr(np, _a, _t)\n"
    "from oemer.ete import main\n"
    "sys.argv = ['oemer'] + sys.argv[1:]\n"
    "main()\n"
)


def run_omr(png_path: str, out_dir: str, timeout: int = 900) -> bytes:
    """Run oemer on a score image; return the resulting MusicXML bytes.

    Slow (deep-learning inference on CPU, minutes on first run while models
    download). Output must ALWAYS pass through the human review table.
    """
    os.makedirs(out_dir, exist_ok=True)
    py = _omr_python()
    if py is None:
        raise RuntimeError("oemer is not installed (main env or ~/.venvs/oemer-omr)")
    proc = subprocess.run(
        [py, "-c", _OEMER_SHIM, png_path, "-o", out_dir, "--without-deskew"],
        capture_output=True, text=True, timeout=timeout,
    )
    produced = [os.path.join(out_dir, f) for f in os.listdir(out_dir)
                if f.endswith(".musicxml") or f.endswith(".xml")]
    if not produced:
        raise RuntimeError(
            f"oemer produced no MusicXML. stderr tail: {proc.stderr[-400:]}")
    newest = max(produced, key=os.path.getmtime)
    with open(newest, "rb") as f:
        return f.read()
