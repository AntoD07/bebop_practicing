"""Pentatonic scale definitions and line generators.

Each public generator returns an engine ``line`` (list of pitch dicts) built from
absolute MIDI pitches, ready for ``scripts.fingering.optimize_fingering``. Pitches
are labelled with their scale degree so the rendered tab shows degree annotations.
"""

from typing import List, Optional

from scripts.fingering.cell_bridge import root_pc

# --------------------------------------------------------------------------- #
# Scale definitions — semitone intervals from the root + degree labels.
# (Confirmed with the user.)
#
# "h32_groups" encodes the canonical horizontal (3+2 per string) layout: which
# degrees share a string. Maps scale index -> (group id, octave offset); the
# groups split at the scale's minor-third gaps. Minor is the user's stated
# layout: b3-4-5 on one string, b7-1(next octave's root) on the next — so the
# root belongs to the PREVIOUS octave's second group (octave offset -1).
# --------------------------------------------------------------------------- #
PENTATONICS = {
    "minor": {
        "intervals": [0, 3, 5, 7, 10], "degrees": ["1", "b3", "4", "5", "b7"],
        "h32_groups": {0: (1, -1), 1: (0, 0), 2: (0, 0), 3: (0, 0), 4: (1, 0)},
    },
    "major": {
        "intervals": [0, 2, 4, 7, 9], "degrees": ["1", "2", "3", "5", "6"],
        "h32_groups": {0: (0, 0), 1: (0, 0), 2: (0, 0), 3: (1, 0), 4: (1, 0)},
    },
    "minor6": {
        "intervals": [0, 2, 3, 7, 9], "degrees": ["1", "2", "b3", "5", "6"],
        "h32_groups": {0: (0, 0), 1: (0, 0), 2: (0, 0), 3: (1, 0), 4: (1, 0)},
    },
    "dominant": {
        "intervals": [0, 2, 4, 7, 10], "degrees": ["1", "2", "3", "5", "b7"],
        "h32_groups": {0: (0, 0), 1: (0, 0), 2: (0, 0), 3: (1, 0), 4: (1, 0)},
    },
}
PENTATONIC_NAMES = ["minor", "major", "minor6", "dominant"]

# Ascending chromatic spelling for inserted passing tones (labels for the tab).
_CHROM_LABEL = {
    0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4",
    6: "#4", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7",
}

DIRECTIONS = ["ascending", "descending", "both"]
SHIFT_INTERVALS = {"Semitone": 1, "Tone": 2, "Minor third": 3, "Major third": 4}

# Named shift CYCLES: per-block semitone offsets FROM THE HOME KEY, repeating.
# "Semitone + tritone" = home -> +1 (semitone up) -> +7 (a tritone above that)
# -> home again (a fourth up), e.g. Eb -> E -> Bb -> Eb.
SHIFT_CYCLES = {
    "Semitone+tritone cycle (Eb·E·Bb·Eb)": [0, 1, 7],
}
SHIFT_CHOICES = list(SHIFT_INTERVALS) + list(SHIFT_CYCLES)


def shift_offsets(choice: str, n_blocks: int) -> List[int]:
    """Per-block semitone offsets from the home key for a shift selection.

    A plain interval walks away from home (0, i, 2i, ...); a named cycle repeats
    its offsets (0, +1, +7, 0, +1, ...), returning home each round.
    """
    if choice in SHIFT_INTERVALS:
        iv = SHIFT_INTERVALS[choice]
        return [k * iv for k in range(n_blocks)]
    cyc = SHIFT_CYCLES[choice]
    return [cyc[k % len(cyc)] for k in range(n_blocks)]


def root_midi(root, octave: int = 3) -> int:
    """MIDI note of ``root`` in a given octave (C3 = 48, C4 = 60)."""
    return (octave + 1) * 12 + root_pc(root)


def _line(midis: List[int], degrees: List[str]) -> List[dict]:
    return [
        {"pitch": m, "role": d, "degree": d} for m, d in zip(midis, degrees)
    ]


def _apply_direction(midis, degrees, direction):
    if direction == "descending":
        return midis[::-1], degrees[::-1]
    if direction == "both":
        # up then down, without repeating the turnaround note
        return (midis + midis[-2::-1], degrees + degrees[-2::-1])
    return midis, degrees  # ascending


# --------------------------------------------------------------------------- #
# Plain scale run
# --------------------------------------------------------------------------- #
def _scale_midis(base_midi: int, penta: str, n_octaves: int, start_deg: int = 0):
    """Ascending pentatonic tones over ``n_octaves`` beginning on scale-degree
    index ``start_deg`` (0 = root). ``base_midi`` is the root's pitch."""
    intervals = PENTATONICS[penta]["intervals"]
    labels = PENTATONICS[penta]["degrees"]
    n = len(intervals)
    midis, degs = [], []
    for j in range(n * n_octaves + 1):  # +1 completes the top octave on the start note
        octave, deg = divmod(start_deg + j, n)
        midis.append(base_midi + 12 * octave + intervals[deg])
        degs.append(labels[deg])
    return midis, degs


def scale_run(
    root,
    penta: str = "minor",
    low_octave: int = 3,
    n_octaves: int = 2,
    direction: str = "ascending",
    start_deg: int = 0,
) -> List[dict]:
    """Pentatonic scale run over ``n_octaves``, beginning on ``start_deg``."""
    base = root_midi(root, low_octave)
    midis, degs = _scale_midis(base, penta, n_octaves, start_deg)
    midis, degs = _apply_direction(midis, degs, direction)
    return _line(midis, degs)


# --------------------------------------------------------------------------- #
# x-notes pattern — the classic sequence: x consecutive scale notes, then the
# same from the next scale note (1-2-3-4, 2-3-4-5, 3-4-5-6 ... over the run).
# --------------------------------------------------------------------------- #
def notes_pattern_run(
    root,
    penta: str = "minor",
    low_octave: int = 3,
    n_octaves: int = 2,
    x: int = 4,
    direction: str = "ascending",
    start_deg: int = 0,
) -> List[dict]:
    """``x``-note groups stepping through the pentatonic over ``n_octaves``.

    Ascending: each group climbs x scale notes and the next group starts one
    scale note higher; descending: groups fall from the top and start one
    note lower each time; "both" = ascending then descending. Groups are
    tagged ``cell`` G1, G2 ... so the tab brackets them and partial slices
    align to whole groups (pass ``group=x`` to the ranker).
    """
    intervals = PENTATONICS[penta]["intervals"]
    labels = PENTATONICS[penta]["degrees"]
    n = len(intervals)
    base = root_midi(root, low_octave)
    lo, top = start_deg, start_deg + n * n_octaves  # scale-index span of the run

    def note(idx):
        octv, deg = divmod(idx, n)
        return base + 12 * octv + intervals[deg], labels[deg]

    asc = [[s + k for k in range(x)] for s in range(lo, top - x + 2)]
    desc = [[t - k for k in range(x)] for t in range(top, lo + x - 2, -1)]
    groups = {"ascending": asc, "descending": desc, "both": asc + desc}[direction]
    line = []
    for j, g in enumerate(groups):
        for idx in g:
            m, d = note(idx)
            line.append({"pitch": m, "role": d, "degree": d, "cell": f"G{j + 1}"})
    return line


# --------------------------------------------------------------------------- #
# Chromaticised run — one passing tone in every whole-step gap.
# Minor pentatonic ascending -> 1 b3 (3) 4 (#4) 5 b7 (7).  add_b6 adds b6 in the
# 5->b7 gap (semitone 8 wherever it lands inside a minor-third gap).
# --------------------------------------------------------------------------- #
def _chromatic_midis(base_midi, penta, n_octaves, add_b6, start_deg=0):
    intervals = PENTATONICS[penta]["intervals"]
    labels = PENTATONICS[penta]["degrees"]
    n = len(intervals)
    midis, degs = [], []
    for j in range(n * n_octaves):
        octv, deg = divmod(start_deg + j, n)
        lo = 12 * octv + intervals[deg]
        noctv, ndeg = divmod(start_deg + j + 1, n)
        hi = 12 * noctv + intervals[ndeg]
        midis.append(base_midi + lo)
        degs.append(labels[deg])
        gap = hi - lo
        if gap == 2:  # whole step -> single passing tone
            midis.append(base_midi + lo + 1)
            degs.append(_CHROM_LABEL[(lo + 1) % 12])
        elif gap == 3 and add_b6 and (lo + 1) % 12 == 8:  # add the b6 colour only
            midis.append(base_midi + lo + 1)
            degs.append(_CHROM_LABEL[8])
    foctv, fdeg = divmod(start_deg + n * n_octaves, n)
    midis.append(base_midi + 12 * foctv + intervals[fdeg])
    degs.append(labels[fdeg])
    return midis, degs


def chromatic_run(
    root,
    penta: str = "minor",
    low_octave: int = 3,
    n_octaves: int = 2,
    direction: str = "ascending",
    add_b6: bool = False,
    start_deg: int = 0,
) -> List[dict]:
    """Pentatonic run with chromatic passing tones filling the whole-step gaps."""
    base = root_midi(root, low_octave)
    midis, degs = _chromatic_midis(base, penta, n_octaves, add_b6, start_deg)
    midis, degs = _apply_direction(midis, degs, direction)
    return _line(midis, degs)


# --------------------------------------------------------------------------- #
# Shifting / side-slipping — repeat the shape transposed by an interval.
# --------------------------------------------------------------------------- #
def shift_run(
    root,
    penta: str = "minor",
    block_offsets: Optional[List[int]] = None,
    direction: str = "ascending",
    low_octave: int = 3,
    octaves_per_block: int = 1,
    start_deg: int = 0,
) -> List[dict]:
    """Play the pentatonic once per block, each transposed by its offset.

    ``block_offsets`` are semitone offsets from the home key (see
    :func:`shift_offsets` — a constant interval walk, or a repeating cycle like
    home/+1/+7/home). Degree labels reset each block, so every block reads as
    the same shape in its key.
    """
    base = root_midi(root, low_octave)
    offsets = block_offsets if block_offsets else [0]
    midis: List[int] = []
    degs: List[str] = []
    for off in offsets:
        bm, bd = _scale_midis(base + off, penta, octaves_per_block, start_deg)
        bm, bd = _apply_direction(bm, bd, direction)
        midis.extend(bm)
        degs.extend(bd)
    return _line(midis, degs)
