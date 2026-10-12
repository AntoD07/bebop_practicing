"""Score import: MusicXML (exact) -> the pitch ``line`` the optimizer consumes.

``{"pitch": midi, "start": onset_in_beats, "phrase_start": bool, "degree": ...}``
plus the chord context. Pitches from a score are ABSOLUTE — no octave choice,
no transposition; the optimizer only decides where on the neck to play them.

Parsing uses music21 when importable (handles .xml/.musicxml/.mxl robustly)
with a stdlib fallback for plain monophonic MusicXML — the deployed API ships
only the stdlib path. Images/PDFs go through the Claude-vision reader
(``vision_omr.py``); the classical oemer OMR tier was retired (unusable on
jazz fonts). Every reading flows through the app's human review table.
"""

from __future__ import annotations

import os
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
    Multi-staff (piano) parts: melody notes come from the FIRST staff and its
    first voice only (the right hand); other staves/voices still advance the
    time cursor (``<backup>`` rewinds it). Chord symbols are kept from every
    staff.
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
    melody_staff: Optional[str] = None   # first staff seen = the top/right hand
    melody_voice: Optional[str] = None   # first voice on that staff

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
                    sym += (kind_text.strip() if kind_text
                            else _KIND_SUFFIX.get(kind, ""))
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
                staff = el.findtext("staff")
                voice = el.findtext("voice")
                if melody_staff is None:
                    melody_staff = staff  # may be None (single-staff part)
                is_melody = (staff == melody_staff)
                if el.find("rest") is not None:
                    onset += dur
                    if is_melody:
                        after_rest = True
                    continue
                if not is_melody:
                    onset += dur   # other staff: time passes, note dropped
                    continue
                if melody_voice is None:
                    melody_voice = voice
                if voice != melody_voice:
                    onset += dur   # second voice on the staff: dropped too
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


def _melody_part(score):
    """The part carrying the melody: highest median pitch wins.

    Piano scores arrive as two PartStaffs (right hand + left hand); the
    guitar line is the RIGHT hand only — the top staff. A single-part lead
    sheet passes through unchanged.
    """
    parts = list(score.parts)
    if len(parts) <= 1:
        return parts[0] if parts else score

    def _median_midi(p):
        ms = sorted(n.pitches[0].midi for n in p.flatten().notes if n.pitches)
        return ms[len(ms) // 2] if ms else -1

    return max(parts, key=_median_midi)


def _figure_symbol(h) -> str:
    """music21 ChordSymbol.figure with flats normalized: ``E-m7`` → ``Ebm7``."""
    fig = h.figure or ""
    root = h.root()
    if root is not None and fig.startswith(root.name):
        fig = root.name.replace("-", "b") + fig[len(root.name):]
    return fig


def parse_with_music21(data: bytes) -> dict:
    """music21-backed parse (more tolerant); same output shape.

    Multi-staff (piano) scores: melody notes come from the top staff only;
    chord symbols are gathered from EVERY staff (they may be written on
    either hand).
    """
    import music21
    with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as f:
        f.write(_read_musicxml_bytes(data))
        path = f.name
    try:
        score = music21.converter.parse(path)
    finally:
        os.unlink(path)
    part = _melody_part(score)
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
        pitch = max(el.pitches, key=lambda p: p.midi) if el.pitches else None
        if pitch is None:
            continue
        notes.append({
            "midi": int(pitch.midi), "start": onset,
            "duration": float(el.quarterLength),
            "phrase_start": prev_end is None or onset > prev_end + 1e-6,
            "bar": int(el.measureNumber or 0),
        })
        prev_end = onset + float(el.quarterLength)
    seen_chords = set()
    for h in score.flatten().getElementsByClass(music21.harmony.ChordSymbol):
        key = (float(h.offset), _figure_symbol(h))
        if key in seen_chords:
            continue
        seen_chords.add(key)
        chords.append({"start_beat": key[0], "symbol": key[1]})
    chords.sort(key=lambda c: c["start_beat"])
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
