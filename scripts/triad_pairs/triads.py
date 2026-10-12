"""Triad pairs, hexatonic scales and the exercise line generators.

Vocabulary
----------
* A :class:`Triad` is a root + quality (major, minor, diminished, augmented,
  sus4, sus2). Its tones are spelled by LETTER (a third is two letters up, a
  fifth four — D major is D F# A, never D Gb A), with the few unreadable
  spellings (Cb, E#, double accidentals) folded to their common enharmonic.
* A :class:`TriadPair` is two triads; its ``hexatonic`` is the union of their
  pitch classes, ordered ascending from the FIRST triad's root (six tones when
  the triads share none — the classic pairs: C + D, Bb + C, F + G…). A tone
  shared by both triads is *owned* by the first triad for labelling.

Lines
-----
Every generator returns an engine ``line``: ``{"pitch": <midi int>, "role",
"degree", "cell"}`` dicts. ``degree`` is the tab's label lane — here
``"<triad symbol>:<chord degree>"`` (``C:3``, ``Dm:b3``), so the player always
sees WHICH triad a note belongs to. ``cell`` tags the groupings so the tab
brackets them and partial slices align to whole groups (``group=x``).

* :func:`hexatonic_scale_run` / :func:`hexatonic_pattern_run` — the scale
  played as a scale (plain run, and the x-notes 1-2-3-4 / 2-3-4-5 pattern),
  exactly like the pentatonic exercises but over the six-note union.
* :func:`alternating_triads_run` — the triad-pair exercise proper: groups of
  ``x`` consecutive ARPEGGIO tones, alternating between the two triads, each
  group starting on the next tone of its triad (the inversions walk up/down).
  Four directions: every group ascending (C E G · D F# A · E G C · …), every
  group descending, or zig-zag — one up, the other down — with an overall
  climb or fall (``alternating ↑↓ (climbing)``: C E G · A F# D · E G C · …).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from scripts.fingering.cell_bridge import root_pc

# Roots offered in the UI — flat jazz spelling, like the app's practice keys.
ROOTS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# quality -> semitone intervals, chord-degree labels, chord-symbol suffix and
# the LETTER step of each tone above the root (for correct spelling).
TRIAD_QUALITIES: Dict[str, dict] = {
    "major":      dict(intervals=(0, 4, 7), degrees=("1", "3", "5"),   symbol="",     letters=(0, 2, 4)),
    "minor":      dict(intervals=(0, 3, 7), degrees=("1", "b3", "5"),  symbol="m",    letters=(0, 2, 4)),
    "diminished": dict(intervals=(0, 3, 6), degrees=("1", "b3", "b5"), symbol="°",    letters=(0, 2, 4)),
    "augmented":  dict(intervals=(0, 4, 8), degrees=("1", "3", "#5"),  symbol="+",    letters=(0, 2, 4)),
    "sus4":       dict(intervals=(0, 5, 7), degrees=("1", "4", "5"),   symbol="sus4", letters=(0, 3, 4)),
    "sus2":       dict(intervals=(0, 2, 7), degrees=("1", "2", "5"),   symbol="sus2", letters=(0, 1, 4)),
}
QUALITY_NAMES = list(TRIAD_QUALITIES)

# Default pairing: the second triad a WHOLE TONE above the first (C + D).
DEFAULT_PAIR_INTERVAL = 2

_LETTERS = "CDEFGAB"
_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACC = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}
_FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_UNREADABLE = {"Cb": "B", "Fb": "E", "B#": "C", "E#": "F"}

_INTERVAL_NAMES = {
    0: "the same root", 1: "a semitone apart", 2: "a whole tone apart",
    3: "a minor third apart", 4: "a major third apart", 5: "a fourth apart",
    6: "a tritone apart", 7: "a fifth apart", 8: "a minor sixth apart",
    9: "a major sixth apart", 10: "a minor seventh apart", 11: "a major seventh apart",
}


def _spell(pc: int, letter: str, prefer_sharps: bool = False) -> str:
    """Spell pitch class ``pc`` on ``letter`` (``6, "F"`` -> ``F#``); fold the
    unreadable results (``Cb``, ``E#``, doubles) to a plain enharmonic."""
    diff = (pc - _LETTER_PC[letter] + 6) % 12 - 6
    if diff in (-1, 0, 1):
        name = letter + _ACC[diff]
        return _UNREADABLE.get(name, name)
    return (_SHARP_NAMES if prefer_sharps else _FLAT_NAMES)[pc % 12]


@dataclass(frozen=True)
class Triad:
    root: str
    quality: str = "major"

    @property
    def spec(self) -> dict:
        return TRIAD_QUALITIES[self.quality]

    @property
    def root_pc(self) -> int:
        return root_pc(self.root)

    @property
    def symbol(self) -> str:
        """Chord symbol: ``C``, ``Dm``, ``B°``, ``Eb+``, ``Gsus4``."""
        return f"{self.root}{self.spec['symbol']}"

    @property
    def pcs(self) -> Tuple[int, ...]:
        return tuple((self.root_pc + iv) % 12 for iv in self.spec["intervals"])

    @property
    def degrees(self) -> Tuple[str, ...]:
        return tuple(self.spec["degrees"])

    @property
    def names(self) -> Tuple[str, ...]:
        """Letter-correct note names of the tones (root, third/fourth, fifth)."""
        li = _LETTERS.index(self.root[0].upper())
        sharps = "#" in self.root
        return tuple(_spell(pc, _LETTERS[(li + step) % 7], sharps)
                     for pc, step in zip(self.pcs, self.spec["letters"]))

    def degree_of(self, pc: int) -> Optional[str]:
        pc %= 12
        return self.degrees[self.pcs.index(pc)] if pc in self.pcs else None

    def name_of(self, pc: int) -> Optional[str]:
        pc %= 12
        return self.names[self.pcs.index(pc)] if pc in self.pcs else None

    def contains(self, midi: int) -> bool:
        return midi % 12 in self.pcs

    def next_above(self, midi: int, strict: bool = True) -> int:
        """Lowest triad tone above ``midi`` (strictly, or ``midi`` itself)."""
        m = midi + 1 if strict else midi
        while not self.contains(m):
            m += 1
        return m

    def next_below(self, midi: int, strict: bool = True) -> int:
        m = midi - 1 if strict else midi
        while not self.contains(m):
            m -= 1
        return m

    def arpeggio(self, start: int, x: int, direction: int = 1) -> List[int]:
        """``x`` consecutive triad tones from ``start`` (a triad tone) going
        up (``direction=1``) or down (``-1``): the inversion that begins there."""
        if not self.contains(start):
            raise ValueError(f"{start} is not a tone of {self.symbol}")
        out = [start]
        while len(out) < x:
            out.append(self.next_above(out[-1]) if direction > 0 else self.next_below(out[-1]))
        return out


@dataclass(frozen=True)
class TriadPair:
    first: Triad
    second: Triad

    @property
    def triads(self) -> Tuple[Triad, Triad]:
        return (self.first, self.second)

    @property
    def title(self) -> str:
        return f"{self.first.symbol} + {self.second.symbol}"

    @property
    def interval_name(self) -> str:
        return _INTERVAL_NAMES[(self.second.root_pc - self.first.root_pc) % 12]

    @property
    def common_pcs(self) -> Tuple[int, ...]:
        return tuple(pc for pc in self.first.pcs if pc in self.second.pcs)

    def owner(self, pc: int, prefer: int = 0) -> Optional[int]:
        """Index (0/1) of the triad a pitch class belongs to; a shared tone goes
        to ``prefer``. None when the tone is in neither triad."""
        pc %= 12
        members = [i for i, t in enumerate(self.triads) if pc in t.pcs]
        if not members:
            return None
        return prefer if prefer in members else members[0]

    def label_for(self, pc: int, triad_index: Optional[int] = None) -> str:
        """The tab's label for a tone: ``<symbol>:<degree>`` of its (owning) triad."""
        k = self.owner(pc, 0 if triad_index is None else triad_index)
        if k is None:
            return ""
        t = self.triads[k]
        return f"{t.symbol}:{t.degree_of(pc)}"

    def name_for(self, pc: int) -> str:
        k = self.owner(pc)
        return self.triads[k].name_of(pc) if k is not None else _FLAT_NAMES[pc % 12]

    @property
    def hexatonic(self) -> List[dict]:
        """The union of both triads, ascending from the first triad's root.

        Each tone: ``{"pc", "offset" (semitones above the first root), "name",
        "label", "triads": (indices of the triads containing it)}``.
        """
        base = self.first.root_pc
        out = []
        for off in range(12):
            pc = (base + off) % 12
            members = tuple(i for i, t in enumerate(self.triads) if pc in t.pcs)
            if not members:
                continue
            out.append({"pc": pc, "offset": off, "name": self.name_for(pc),
                        "label": self.label_for(pc), "triads": members,
                        "labels": [self.label_for(pc, i) for i in members]})
        return out

    @property
    def hexatonic_names(self) -> List[str]:
        return [t["name"] for t in self.hexatonic]


def default_pair(key: str, interval: int = DEFAULT_PAIR_INTERVAL) -> TriadPair:
    """The key's major triad + the major triad ``interval`` semitones up."""
    second = ROOTS[(root_pc(key) + interval) % 12]
    return TriadPair(Triad(key, "major"), Triad(second, "major"))


# --------------------------------------------------------------------------- #
# Line generators
# --------------------------------------------------------------------------- #
SCALE_DIRECTIONS = ["ascending", "descending", "both"]
ALT_ASC, ALT_DESC = "ascending", "descending"
ALT_CLIMB, ALT_FALL = "alternating ↑↓ (climbing)", "alternating ↓↑ (falling)"
ALTERNATING_DIRECTIONS = [ALT_ASC, ALT_DESC, ALT_CLIMB, ALT_FALL]


def root_midi(root: str, octave: int = 3) -> int:
    """MIDI note of ``root`` in a given octave (C3 = 48, C4 = 60)."""
    return (octave + 1) * 12 + root_pc(root)


def _hex_note(pair: TriadPair, base: int, idx: int) -> Tuple[int, dict]:
    """Scale index (0.. ; ``n`` = the first root an octave up) -> (midi, tone)."""
    tones = pair.hexatonic
    n = len(tones)
    octave, deg = divmod(idx, n)
    t = tones[deg]
    return base + 12 * octave + t["offset"], t


def _note(midi: int, label: str, cell: Optional[str] = None) -> dict:
    d = {"pitch": midi, "role": label, "degree": label}
    if cell is not None:
        d["cell"] = cell
    return d


def _apply_direction(line: List[dict], direction: str) -> List[dict]:
    if direction == "descending":
        return line[::-1]
    if direction == "both":  # up then down, without repeating the turnaround note
        return line + line[-2::-1]
    return line


def hexatonic_scale_run(pair: TriadPair, low_octave: int = 2, n_octaves: int = 2,
                        direction: str = "ascending", start_deg: int = 0) -> List[dict]:
    """The hexatonic scale over ``n_octaves``, beginning on scale index ``start_deg``."""
    base = root_midi(pair.first.root, low_octave)
    n = len(pair.hexatonic)
    line = []
    for j in range(n * n_octaves + 1):  # +1 completes the top octave on the start note
        m, t = _hex_note(pair, base, start_deg + j)
        line.append(_note(m, t["label"]))
    return _apply_direction(line, direction)


def hexatonic_pattern_run(pair: TriadPair, low_octave: int = 2, n_octaves: int = 2,
                          x: int = 4, direction: str = "ascending",
                          start_deg: int = 0) -> List[dict]:
    """``x``-note groups stepping through the hexatonic scale (1-2-3-4, 2-3-4-5…).

    Same rules as the pentatonic pattern: ascending groups climb ``x`` scale
    notes and the next starts one scale note higher; descending groups fall
    from the top; "both" = ascending then descending. Groups are tagged
    ``G1, G2…`` so the tab brackets them (pass ``group=x`` to the ranker).
    """
    base = root_midi(pair.first.root, low_octave)
    n = len(pair.hexatonic)
    lo, top = start_deg, start_deg + n * n_octaves
    asc = [[s + k for k in range(x)] for s in range(lo, top - x + 2)]
    desc = [[t - k for k in range(x)] for t in range(top, lo + x - 2, -1)]
    groups = {"ascending": asc, "descending": desc, "both": asc + desc}[direction]
    line = []
    for j, g in enumerate(groups):
        for idx in g:
            m, t = _hex_note(pair, base, idx)
            line.append(_note(m, t["label"], f"G{j + 1}"))
    return line


def alternating_triads_run(pair: TriadPair, low_octave: int = 2, n_octaves: int = 2,
                           x: int = 3, direction: str = ALT_ASC,
                           start_deg: int = 0) -> List[dict]:
    """Groups of ``x`` arpeggio tones alternating between the two triads.

    The run spans ``n_octaves`` above the starting tone (scale index
    ``start_deg`` of the hexatonic). The first group plays the triad that OWNS
    the starting tone (the first triad when both contain it); groups then
    alternate triads.

    * ``ascending`` — every group ascends; each next group starts on the next
      tone of ITS triad above the previous group's start, so the inversions
      walk up: C E G · D F# A · E G C · F# A D · … (one cycle per octave,
      closing on the top-octave start tone).
    * ``descending`` — the mirror, from the top down.
    * ``alternating ↑↓ (climbing)`` — one triad up, the other down: a group
      starts on the next tone of its triad ABOVE the previous group's last
      note, so the pairs drift upward (C E G · A F# D · E G C · D A F# · …).
    * ``alternating ↓↑ (falling)`` — the mirror: down, then up, drifting down.

    Groups are tagged with their triad symbol and arrow (``C↑``, ``D↓``) for
    the tab brackets; pass ``group=x`` to the ranker.
    """
    base = root_midi(pair.first.root, low_octave)
    start, tone = _hex_note(pair, base, start_deg)
    lo, hi = start, start + 12 * n_octaves
    tri = pair.triads
    k = pair.owner(tone["pc"])
    groups: List[Tuple[int, int, int]] = []  # (triad index, start midi, ±1)

    if direction == ALT_ASC:
        s = lo
        while s <= hi:
            groups.append((k, s, +1))
            k ^= 1
            s = tri[k].next_above(s)
    elif direction == ALT_DESC:
        s = hi
        while s >= lo:
            groups.append((k, s, -1))
            k ^= 1
            s = tri[k].next_below(s)
    elif direction in (ALT_CLIMB, ALT_FALL):
        climb = direction == ALT_CLIMB
        s, d = (lo, +1) if climb else (hi, -1)
        while (s <= hi) if climb else (s >= lo):
            # The leading group (up when climbing, down when falling) …
            groups.append((k, s, d))
            last = tri[k].arpeggio(s, x, d)[-1]
            # … and its partner on the other triad, in the other direction,
            # entered from the tone just past the leading group's last note.
            k ^= 1
            s = tri[k].next_above(last) if climb else tri[k].next_below(last)
            groups.append((k, s, -d))
            last = tri[k].arpeggio(s, x, -d)[-1]
            k ^= 1
            s = tri[k].next_above(last) if climb else tri[k].next_below(last)
    else:
        raise ValueError(f"unknown direction {direction!r}")

    line: List[dict] = []
    for k, s, d in groups:
        t = tri[k]
        tag = f"{t.symbol}{'↑' if d > 0 else '↓'}"
        for m in t.arpeggio(s, x, d):
            line.append(_note(m, pair.label_for(m % 12, k), tag))
    return line
