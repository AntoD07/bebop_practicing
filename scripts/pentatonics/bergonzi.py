"""Bergonzi pentatonic 'shapes' — load the pattern library and generate lines.

Patterns live in ``data/pentatonics/bergonzi_patterns.json`` (hand-editable source
of truth). Each pattern is a 4-note melodic cell described by scale-INDEX offsets
(step = +/-1, skip = +/-2); ``stride`` advances the start index per repetition,
sweeping the shape through the pentatonic.
"""

import json
from typing import List

from scripts.paths import BERGONZI_PATTERNS
from scripts.pentatonics.pentatonics import PENTATONICS, root_midi, _line


def load_patterns() -> List[dict]:
    """Return the list of Bergonzi shape dicts from the data file."""
    with open(BERGONZI_PATTERNS) as f:
        data = json.load(f)
    return data["patterns"]


def _index_to_note(base_midi: int, penta: str, idx: int):
    """Map a pentatonic scale index (0.. ; 5 = root one octave up) to (midi, degree)."""
    intervals = PENTATONICS[penta]["intervals"]
    degrees = PENTATONICS[penta]["degrees"]
    n = len(intervals)
    octave, deg = divmod(idx, n)
    return base_midi + 12 * octave + intervals[deg], degrees[deg]


def apply_pattern(
    root,
    penta: str,
    pattern: dict,
    low_octave: int = 3,
    n_octaves: int = 2,
) -> List[dict]:
    """Sweep a Bergonzi formula through the pentatonic, starting ON THE ROOT.

    Grouping starts follow the book exactly: ascending formulas (stride +2)
    start at the root and climb by skip (C-F-Bb-Eb-G over C minor); descending
    formulas (stride -2) start at the TOP root and walk down by skip
    (C-G-Eb-Bb-F). A grouping's offsets may dip below the low root or peak
    above the top one — the register auto-fit downstream keeps it on the neck.
    Five groupings complete a cycle over two octaves.
    """
    base = root_midi(root, low_octave)
    offsets = pattern["offsets"]
    stride = int(pattern.get("stride", 1)) or 1
    n = len(PENTATONICS[penta]["intervals"])
    top = n * n_octaves  # the top-octave root's scale index

    if stride > 0:  # ascending: root, +skip, ... (top = the cycle repeat point)
        starts = list(range(0, top, stride))
    else:  # descending: top root, -skip, ...
        starts = list(range(top, 0, stride))

    line = []
    for j, s in enumerate(starts):
        for off in offsets:
            m, d = _index_to_note(base, penta, s + off)
            # "cell" tags each 4-note grouping -> the tab draws brackets, so the
            # formula's phase is visible and a truncation is obvious.
            line.append({"pitch": m, "role": d, "degree": d, "cell": f"G{j + 1}"})
    return line


_PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _closest_tone_index(midi: int, base: int, penta: str, direction: int) -> int:
    """Scale index (relative to ``base``) of the key's pentatonic tone closest
    to ``midi``. Ties break in the line's direction (+1 ascending / -1 desc)."""
    intervals = PENTATONICS[penta]["intervals"]
    n = len(intervals)
    cands = []
    for off in range(-11, 12):
        m2 = midi + off
        rel = (m2 - base) % 12
        if rel in intervals:
            cands.append((abs(off), -(off * direction), m2))
    cands.sort()
    m2 = cands[0][2]
    o, rel = divmod(m2 - base, 12)
    return o * n + intervals.index(rel)


def shift_pattern(
    root,
    penta: str,
    pattern: dict,
    block_offsets: List[int],
    low_octave: int = 3,
    groups_per_shift: int = 2,
) -> List[dict]:
    """Side-slip a Bergonzi formula BY KEY with voice-leading continuity.

    Sweep the formula through the home key for ``groups_per_shift`` groupings
    (advancing by the formula's stride, exactly like the plain sweep), then
    move to the next key block and CONTINUE the pattern from the new key's
    pentatonic tone CLOSEST to the last played note (ties resolve in the line's
    direction) — not a restart of the same cell. ``block_offsets`` are semitone
    offsets from the home key per block (constant-interval walk or a repeating
    cycle like home/+1/+7/home). Each block is bracketed with its key name.
    """
    offsets = pattern["offsets"]
    stride = int(pattern.get("stride", 1)) or 1
    n = len(PENTATONICS[penta]["intervals"])
    gps = max(1, int(groups_per_shift))
    direction = 1 if stride > 0 else -1

    line: List[dict] = []
    last_midi = None
    for k, block_off in enumerate(block_offsets if block_offsets else [0]):
        base_k = root_midi(root, low_octave) + block_off
        key_name = _PC_NAMES[base_k % 12]
        if last_midi is None:
            # Home block anchors like the plain sweep: ascending formulas start
            # on the root, descending ones two octaves up (room to walk down).
            start = 0 if direction > 0 else n * 2
        else:
            start = _closest_tone_index(last_midi, base_k, penta, direction)
        for g in range(gps):
            s = start + g * stride
            for off in offsets:
                m, d = _index_to_note(base_k, penta, s + off)
                line.append({"pitch": m, "role": d, "degree": d,
                             "cell": f"{key_name}·{g + 1}"})
                last_midi = m
    return line
