"""Vision-based score reading via the Claude API (tier C of score import).

Sends the score image(s) to Claude with an explicit, complete statement of the
LOGIC for parsing staff notation — staff geometry, key signature and accidental
scope, beam/flag rhythm math, ties vs slurs, chord-symbol placement — plus a
per-measure self-check (durations must sum to the time signature). Output is
constrained to a JSON schema (``output_config.format``), so the response parses
deterministically into the same shape as :func:`score_import.parse_musicxml`.

Like every OMR tier, the result feeds the human review table — vision models
read jazz fonts far better than classical OMR, but a wrong accidental is still
possible, so nothing is trusted blindly.
"""

from __future__ import annotations

import base64
import json
import os
from typing import List, Optional

MODEL = "claude-opus-4-8"

# --------------------------------------------------------------------------- #
# The score-reading logic, stated explicitly for the model.
# --------------------------------------------------------------------------- #
SCORE_READING_LOGIC = """\
You are reading a single-staff, monophonic jazz lead sheet / exercise in
standard Western notation. Extract every note exactly. Apply this logic:

## 1. Staff geometry (treble clef)
The five staff lines, bottom to top, are E4 G4 B4 D5 F5.
The four spaces, bottom to top, are F4 A4 C5 E5.
Notes above the staff continue upward: G5 (space above the top line), A5 (1st
ledger line), B5, C6 (2nd ledger line), ...
Notes below the staff continue downward: D4 (space below the bottom line),
C4 (1st ledger line below, "middle C"), B3, A3 (2nd ledger line below), ...
Judge each notehead's line/space carefully relative to the five staff lines;
ledger lines must be counted one by one.

## 2. Key signature and accidentals
- Read the key signature right after the clef (sharps/flats on specific
  lines). It applies to every note of that letter name in EVERY octave.
- An accidental (♭, ♯, ♮) printed before a notehead applies to that letter
  AND octave from that point until the END OF THE MEASURE, then resets at
  the barline. A natural (♮) cancels the key signature or an earlier
  accidental for the rest of the measure.
- If there is no key signature, every accidental is explicit.

## 3. Rhythm (durations in quarter-note beats)
- Filled notehead + stem, no beam/flag = quarter note (1.0 beat).
- Filled notehead + beam or single flag = eighth note (0.5).
- Double beam/flag = sixteenth (0.25). Count the beams connecting each note.
- Hollow notehead + stem = half note (2.0); hollow without stem = whole (4.0).
- A dot after a notehead multiplies its duration by 1.5.
- Rests: thick block hanging under a line = half rest ONLY if on the middle
  line region; squiggle = quarter rest (1.0); flagged squiggle = eighth rest
  (0.5); hanging block = half (2.0); floating block = whole/full-measure.
- A TIE is a curved line connecting two noteheads of the SAME pitch —
  the second note is not re-struck: mark the first with tied_to_next=true.
  A curved line spanning DIFFERENT pitches is a slur — ignore slurs.
- Triplets are marked with a small 3; each triplet eighth = 1/3 beat.

## 4. Measures and the self-check (important)
Bar lines divide measures. Read the time signature (e.g. 4/4).
For EVERY measure: the durations of its notes and rests MUST sum exactly to
the time signature (4.0 beats in 4/4, except a possible pickup measure or the
final measure). If your reading of a measure does not sum correctly, RE-EXAMINE
that measure — you probably misread a beam count, missed a rest, or split a
beamed group wrongly — and fix it before answering.

## 5. Chord symbols
Chord symbols (e.g. C-6/9, G7, Fmaj7) are printed ABOVE the staff. Assign each
one to the measure and beat it sits over, judged by its horizontal position
relative to the noteheads beneath it. "C-" means C minor; "6/9" is a chord
quality suffix (write the symbol exactly as printed, e.g. "C-6/9").

## 6. Reading order
Systems (staff rows) are read top to bottom; within a system, left to right.
Measure numbers may be printed at the start of each system — use them to keep
your measure count aligned. The full-page image gives you overall context;
the strip images (if provided) are the same systems enlarged for accuracy —
prefer the strips for pitch/accidental detail.

Extract EVERY note. Do not invent notes that are not printed. If a symbol is
genuinely illegible, choose the most plausible reading and add it to the
"uncertain" list with the measure number and reason.
"""

# JSON schema for the structured response (structured outputs: no numerical
# constraints allowed — validation happens in our converter).
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "time_signature_beats": {"type": "integer"},
        "chords": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "measure": {"type": "integer"},
                    "beat": {"type": "number"},
                    "symbol": {"type": "string"},
                },
                "required": ["measure", "beat", "symbol"],
                "additionalProperties": False,
            },
        },
        "measures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["note", "rest"]},
                                "pitch": {"type": ["string", "null"]},
                                "duration_beats": {"type": "number"},
                                "tied_to_next": {"type": "boolean"},
                            },
                            "required": ["type", "pitch", "duration_beats",
                                         "tied_to_next"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["number", "events"],
                "additionalProperties": False,
            },
        },
        "uncertain": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "measure": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["measure", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["time_signature_beats", "chords", "measures", "uncertain"],
    "additionalProperties": False,
}


# --------------------------------------------------------------------------- #
# Image prep: slice the page into system strips for better effective resolution
# --------------------------------------------------------------------------- #
def slice_systems(png_path: str, out_dir: str) -> List[str]:
    """Split a score page into one PNG strip per staff system.

    Uses a horizontal ink-density projection (pure PIL/numpy) to find the staff
    bands and cuts generous margins around each. Falls back to the whole page
    if detection looks wrong.
    """
    from PIL import Image
    import numpy as np

    img = Image.open(png_path).convert("L")
    a = np.asarray(img)
    ink = (a < 128).mean(axis=1)          # fraction of dark pixels per row
    dense = ink > 0.08                    # staff lines are long horizontal runs

    bands = []
    start = None
    for y, d in enumerate(dense):
        if d and start is None:
            start = y
        elif not d and start is not None:
            if y - start > 10:            # a staff is at least ~10px of dense rows
                bands.append((start, y))
            start = None
    if start is not None:
        bands.append((start, len(dense)))

    # Merge bands closer than half a staff height (beams split the projection).
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] < 60:
            merged[-1] = (merged[-1][0], b[1])
        else:
            merged.append(list(b))

    if not 1 <= len(merged) <= 12:
        return [png_path]                 # detection failed — send whole page

    paths = []
    h = a.shape[0]
    for i, (y0, y1) in enumerate(merged):
        top = max(0, y0 - 130)            # room for chord symbols above
        bot = min(h, y1 + 60)
        strip = img.crop((0, top, img.width, bot))
        p = os.path.join(out_dir, f"system_{i+1}.png")
        strip.save(p)
        paths.append(p)
    return paths


def _image_block(path: str) -> dict:
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": data}}


# --------------------------------------------------------------------------- #
# The API call
# --------------------------------------------------------------------------- #
def read_score_with_claude(png_path: str, work_dir: str,
                           api_key: Optional[str] = None) -> dict:
    """Read a score image with Claude vision; return the score_import dict shape.

    Returns ``{"notes": [...], "chords": [...], "beats_per_bar": int,
    "uncertain": [...]}`` — directly compatible with the review table.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    strips = slice_systems(png_path, work_dir)
    content = [{"type": "text", "text": SCORE_READING_LOGIC},
               {"type": "text", "text": "Full page (context):"},
               _image_block(png_path)]
    if strips != [png_path]:
        content.append({"type": "text",
                        "text": "The same systems, enlarged top-to-bottom — "
                                "use these for pitch/accidental detail:"})
        for p in strips:
            content.append(_image_block(p))

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": SCORE_SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    raw = json.loads(text)
    return _convert(raw)


def _convert(raw: dict) -> dict:
    """Model JSON -> the parse_musicxml() dict shape (onsets, ties, rests)."""
    bpb = int(raw.get("time_signature_beats") or 4)
    notes, chords = [], []
    onset = 0.0
    after_rest = True
    pending_tie = False

    for m in sorted(raw["measures"], key=lambda x: x["number"]):
        for ev in m["events"]:
            dur = float(ev["duration_beats"])
            if ev["type"] == "rest" or not ev["pitch"]:
                onset += dur
                after_rest = True
                pending_tie = False
                continue
            from scripts.fingering.pitch import parse_pitch
            midi = parse_pitch(str(ev["pitch"]).strip())
            if pending_tie and notes and notes[-1]["midi"] == midi:
                notes[-1]["duration"] += dur
            else:
                notes.append({"midi": midi, "start": onset, "duration": dur,
                              "phrase_start": after_rest, "bar": m["number"]})
                after_rest = False
            pending_tie = bool(ev.get("tied_to_next"))
            onset += dur

    for c in raw.get("chords", []):
        chords.append({
            "start_beat": (int(c["measure"]) - 1) * bpb + (float(c["beat"]) - 1.0),
            "symbol": str(c["symbol"]),
        })
    if not notes:
        raise ValueError("vision model returned no notes")
    return {"notes": notes, "chords": chords, "beats_per_bar": bpb,
            "uncertain": raw.get("uncertain", [])}


def vision_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True
