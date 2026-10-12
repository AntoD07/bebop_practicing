"""Shared constants and user-facing strings (no pandas, no streamlit)."""

from __future__ import annotations

import ast
from typing import Iterable, List, Sequence

# The 12 practice keys the daily rotation draws from (and the override list).
PRACTICE_KEYS = ["C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db"]

# Every sampling CSV (mode) in the cell library.
MODES = ["Maj7", "Minor", "Dorian", "Myxolidian", "Locrian",
         "MajorResolutions", "MinorResolutions", "7sus4"]
# The chords the UI lets you pick (7sus4 has no Movement/Type columns and was
# never exposed).
CHORD_MODES = ["Maj7", "Minor", "Dorian", "Myxolidian", "Locrian",
               "MajorResolutions", "MinorResolutions"]

# Pivot notes in degree order; "3" is the default pivot whenever both sides
# offer it (the most practised connection note).
DEGREE_ORDER = ["1", "b9", "9", "#9", "3", "maj3", "4", "11", "#11", "5", "#5",
                "b6", "6", "b7", "7", "#7", "maj7"]
DEFAULT_PIVOT = "3"

CHORD_TONES = ["1", "3", "5", "7"]

# The first/last-note and connecting-note pickers of the Melodic Lines page.
NOTE_OPTIONS = ["1", "9", "3", "4", "11", "#11", "5", "6", "7", "b7", "b6",
                "b9", "#9", "#7"]

MOVEMENTS = ["A", "D", "N"]
LINE_MOVEMENT_OPTIONS = ["A and N", "D and N", "A", "D"]


def parse_degrees(value) -> List[str]:
    """Degree tokens from a list, a tuple, or the CSV's ``"['1', '3']"`` repr."""
    if isinstance(value, (list, tuple)):
        return [str(t).strip() for t in value]
    s = str(value).strip()
    try:
        parsed = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return [s]
    if isinstance(parsed, (list, tuple)):
        return [str(t).strip() for t in parsed]
    return [str(parsed).strip()]


def join_notes(cell) -> str:
    """``"1-3-5-7"`` from a degree list or its string repr."""
    return "-".join(parse_degrees(cell))


def degree_sort_key(token: str):
    t = str(token)
    return (DEGREE_ORDER.index(t) if t in DEGREE_ORDER else 99, t)


def sort_degrees(tokens: Iterable[str]) -> List[str]:
    return sorted(dict.fromkeys(str(t) for t in tokens), key=degree_sort_key)


def allowed_movements(movement) -> set:
    """Movement values a selection admits (page 1: None/A/D; page 2 adds
    'A and N' / 'D and N')."""
    if movement in (None, "", "None"):
        return {"N", "A", "D"}
    if movement in ("A and N", "D and N"):
        return {"N", movement[0]}
    return {"N", str(movement)}


def harmony_caption(key, modes: Sequence[str]) -> str:
    """How today's key maps onto the line's chords (shared by pages 1-2).
    Pass the ORIGINAL CSV mode names."""
    from scripts.fingering.cell_bridge import chord_symbol_for_mode, is_single_chord

    modes = list(modes)
    single = is_single_chord(modes)
    first = chord_symbol_for_mode(key, modes[0], single)
    if single:
        return f"Harmony: one chord, **{first}** — today's key ({key}) is its root."
    return (f"Harmony: today's key **{key}** is read as the I of a ii-V-I — the "
            f"line starts on **{first}**; later chords follow from the pivots.")


def combo_chord_tone_connecting_notes(mode_list: Sequence[str]) -> List[List[str]]:
    """Allowed pivot notes per cell for the Dorian x Myxolidian combo.

    A pivot is the first note of the cell it enters, so it must be a chord
    tone of THAT cell's chord. Myxolidian cells are spelled ii-relative in the
    combo, so the V7 chord tones 1-3-5-7 appear as 4-6-1-3.
    """
    from scripts.domain.transposition import dom_to_dorian_mapping

    myxo = [dom_to_dorian_mapping[d] for d in CHORD_TONES]
    return [list(myxo) if m == "Myxolidian" else list(CHORD_TONES) for m in mode_list]


def combo_mapping_info() -> str:
    """User-facing note explaining the Myxolidian -> Dorian (ii) re-spelling."""
    from scripts.domain.transposition import dom_to_dorian_mapping

    pairs = ", ".join(f"{d}→{dom_to_dorian_mapping[d]}"
                      for d in ["1", "9", "3", "4", "5", "6", "7", "#11", "b9"])
    return (
        "**Mapping applied:** Myxolidian cells are re-spelled from the ii "
        "(Dorian) root, so both chords share one note representation and the "
        f"pivots line up. V7 degree → ii degree: {pairs}. "
        "Myxolidian notes shown below (and the start/end/connecting-note "
        "pickers) use this ii spelling."
    )


def combo_chord_tones_info() -> str:
    from scripts.domain.transposition import dom_to_dorian_mapping

    myxo = ", ".join(dom_to_dorian_mapping[d] for d in CHORD_TONES)
    return (
        "**Chord-tone pivots:** a pivot is the first note of the cell it enters, "
        "so it must be a chord tone of THAT cell's chord. Entering a Dorian cell: "
        f"{', '.join(CHORD_TONES)} (ii-7 chord tones). Entering a Myxolidian cell: "
        f"{myxo} (the V7's 1-3-5-7, in ii spelling)."
    )
