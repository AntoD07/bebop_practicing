"""Line structures and the backward cell sampler (page 2).

``sample_line`` builds a line BACKWARD from the ending cell to keep note
continuity: each earlier cell must END on the note the (already sampled) next
cell STARTS on — the pivot. ``connecting_notes[k]`` constrains cell k's start
note (the pivot it enters); the line's first note (k == 0) is only constrained
when the page asks for chord tones. The last cell is drawn with weights
1/(row+1), favouring the cells listed first in the CSV; earlier cells are
drawn uniformly. This is a faithful port of the legacy pandas sampler.

"Major x Dominant" rolls its structure at random — the sampled line carries
the structure it was built with (``SampledLine.structure``), so a consumer
never re-rolls it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from scripts.domain.catalog import cells as catalog_cells
from scripts.domain.cells import CellView, sampler_steps, views

MYXO_TO_DORIAN_LINE_TYPE = "Dorian x Myxolidian"

line_structure_dic: Dict[str, List[str]] = {
    "Maj7": ["Maj7", "Maj7", "Maj7", "Maj7"],
    "7sus4 Infinity Loop": ["Myxolidian", "Myxolidian", "Myxolidian", "Myxolidian"],
    "Minor": ["Minor", "Minor", "Minor", "Minor"],
    "Dorian": ["Dorian", "Dorian", "Dorian", "Dorian"],
    "Myxolidian": ["Myxolidian", "Myxolidian", "Myxolidian", "Myxolidian"],
    "Short Maj 2-5-1": ["Myxolidian", "MajorResolutions"],
    "Long Maj 2-5-1": ["Myxolidian", "Myxolidian", "Myxolidian", "MajorResolutions"],
    "Long Maj 2-5-1 with Maj7 ending": [
        "7sus4", "7sus4", "7sus4", "MajorResolutions", "Maj7", "Maj7",
    ],
    "Short Minor 2-5-1": ["Locrian", "MinorResolutions"],
    "Long Minor 2-5-1": ["Locrian", "Locrian", "Locrian", "MinorResolutions"],
    "Long Minor with double resolution": [
        "Locrian", "Locrian", "MinorResolutions", "MinorResolutions",
    ],
    "Long Minor 2-5-1 with Minor ending": [
        "Locrian", "Locrian", "Locrian", "MinorResolutions", "Minor", "Minor",
    ],
    "Double resolution": ["Locrian", "Locrian", "MinorResolutions", "MinorResolutions"],
    "Minor and Dominant 2-cells alternated": [
        "Minor", "Minor", "Locrian", "MinorResolutions",
        "Minor", "Minor", "Locrian", "MinorResolutions",
        "Minor", "Minor", "Locrian", "MinorResolutions",
    ],
    "Minor x Dominant": [
        "Minor", "Minor", "MinorResolutions", "MinorResolutions",
        "Minor", "Minor", "MinorResolutions", "MinorResolutions",
        "Minor", "Minor", "MinorResolutions", "MinorResolutions",
    ],
}

# Line types whose structure is "length" cells of one mode.
_FIXED_LENGTH_TYPES = ("Minor", "Dorian", "Maj7", "Myxolidian", "Locrian")

# The page's selector, in order.
LINE_TYPES = [
    "Maj7", "Minor", "Dorian", "Myxolidian", "Locrian",
    "Short Maj 2-5-1", "Long Maj 2-5-1", "Short Minor 2-5-1", "Long Minor 2-5-1",
    "Long Minor with double resolution", "Double resolution",
    "Minor and Dominant 2-cells alternated", "Minor x Dominant", "Major x Dominant",
    MYXO_TO_DORIAN_LINE_TYPE,
]
DEFAULT_LINE_TYPE = "Long Maj 2-5-1"

# Line types whose first/end-note pickers are hidden on the page.
NO_FIRST_LAST_NOTE_TYPES = (
    "Long Minor 2-5-1 with Minor ending", "Long Maj 2-5-1 with Maj7 ending",
    "Minor and Dominant 2-cells alternated",
)
# Line types whose connecting-note default is "everything" (else chord tones).
ALL_NOTES_DEFAULT_TYPES = ("Long Minor 2-5-1", "Short Minor 2-5-1", "Double resolution")


def line_structure_mapping(line_type: str, length: Optional[int] = None,
                           n_dorian: int = 1, n_myxo: int = 1,
                           rng: Optional[random.Random] = None) -> List[str]:
    """The cell-mode sequence of a line type ("Major x Dominant" is random:
    pass ``rng`` for reproducibility)."""
    if line_type == MYXO_TO_DORIAN_LINE_TYPE:
        return ["Dorian"] * int(n_dorian) + ["Myxolidian"] * int(n_myxo)
    if line_type in _FIXED_LENGTH_TYPES:
        return [line_type] * int(length or 4)
    if line_type == "Major x Dominant":
        r = rng or random
        return [r.choice(["Maj7", "MajorResolutions"]) for _ in range(int(length or 4))]
    if line_type not in line_structure_dic:
        raise KeyError(f"unknown line type {line_type!r}")
    return list(line_structure_dic[line_type])


def allowed_starts(connecting_notes, k: int) -> Optional[set]:
    """Allowed start notes of cell ``k``, or None for no constraint.

    ``k == 0`` is the line's FIRST note: pages fill ``connecting_notes[0]``
    only when it should be constrained (chord tones), else leave it empty.
    """
    if not connecting_notes or k < 0 or k >= len(connecting_notes):
        return None
    allowed = {str(a) for a in (connecting_notes[k] or []) if a is not None}
    return allowed or None


def bridge_modes(modes: Sequence[str], line_type: str, dom_to_minor: bool = False) -> List[str]:
    """Mode names for the fingering bridge. Resolution cells are DOMINANT-based
    (degrees spelled from the resolving V7); but when the translate checkbox
    has rewritten their degrees to the Minor/Major-I representation, they
    must be read with the tonic modes instead. In the Dorian x Myxolidian
    combo the Myxolidian degrees are ALWAYS re-spelled ii-relative, so they
    read as Dorian."""
    out = list(modes)
    if line_type == MYXO_TO_DORIAN_LINE_TYPE:
        out = ["Dorian" if m == "Myxolidian" else m for m in out]
    if dom_to_minor:
        out = [{"MajorResolutions": "MajorTonic",
                "MinorResolutions": "MinorTonic"}.get(m, m) for m in out]
    return out


@dataclass
class SampledLine:
    cells: List[CellView]          # in playing order, degrees in the sampler's representation
    structure: List[str]           # the ORIGINAL CSV mode per cell
    line_type: str
    dom_to_minor: bool = False

    @property
    def names(self) -> List[str]:
        return [c.name for c in self.cells]

    @property
    def degrees(self) -> List[List[str]]:
        return [list(c.degrees) for c in self.cells]

    @property
    def reading_modes(self) -> List[str]:
        return bridge_modes(self.structure, self.line_type, self.dom_to_minor)

    @property
    def movement_modes(self) -> List[str]:
        return list(self.structure)

    @property
    def signature(self) -> tuple:
        return tuple(c.id for c in self.cells)


def _sampler_views(mode: str, bonus: bool, dom_to_minor: bool, sus4: bool,
                   loc_to_dom: bool, myxo_to_dorian: bool) -> List[CellView]:
    steps = sampler_steps(mode, dom_to_minor=dom_to_minor, sus4=sus4,
                          loc_to_dom=loc_to_dom, myxo_to_dorian=myxo_to_dorian)
    return views(catalog_cells(mode, bonus), steps)


def _movement_ok(view: CellView, movement) -> bool:
    if movement is None or movement == "None":
        return True
    if movement in ("A and N", "D and N"):
        return str(view.movement) in ("N", movement[0])
    return str(view.movement) == str(movement)


def sample_line(line_type: str, bonus: bool = False, dom_to_minor: bool = False,
                sus4: bool = False, loc_to_dom: bool = False, length: int = 4,
                movement=None, starting_note=None, ending_note=None,
                connecting_notes=None, n_dorian: int = 1, n_myxo: int = 1,
                rng: Optional[random.Random] = None, max_tries: int = 2000,
                ) -> Optional[SampledLine]:
    """Sample one pivot-connected line (see the module docstring), or None
    when the constraints cannot be met."""
    r = rng or random.Random()
    myxo_to_dorian = line_type == MYXO_TO_DORIAN_LINE_TYPE
    cache: Dict[str, List[CellView]] = {}

    def pool(mode: str) -> List[CellView]:
        if mode not in cache:
            cache[mode] = _sampler_views(mode, bonus, dom_to_minor, sus4, loc_to_dom,
                                         myxo_to_dorian)
        return cache[mode]

    for _ in range(max_tries):
        mode_list = line_structure_mapping(line_type, length=length, n_dorian=n_dorian,
                                           n_myxo=n_myxo, rng=r)
        last_pool = pool(mode_list[-1])
        indexed = list(enumerate(last_pool))          # row position -> weight 1/(row+1)
        if movement is not None and movement != "None":
            indexed = [(i, v) for i, v in indexed if _movement_ok(v, movement)]
            if not indexed:
                return None
        if ending_note not in ("None", None, ""):
            indexed = [(i, v) for i, v in indexed if v.end == str(ending_note)]
        if not indexed:
            return None
        allowed = allowed_starts(connecting_notes, len(mode_list) - 1)
        if allowed:
            indexed = [(i, v) for i, v in indexed if v.start in allowed]
            if not indexed:
                return None
        final = r.choices([v for _, v in indexed], weights=[1.0 / (i + 1) for i, _ in indexed])[0]
        line = [final]
        ok = True
        for i, mode in enumerate(mode_list[:-1][::-1]):
            cands = pool(mode)
            if movement is not None and movement != "None":
                cands = [v for v in cands if _movement_ok(v, movement)]
            next_first = line[-1].degrees[0]
            cands = [v for v in cands if v.end == next_first]
            allowed = allowed_starts(connecting_notes, len(mode_list) - 2 - i)
            if allowed:
                cands = [v for v in cands if v.start in allowed]
            if i == len(mode_list) - 2:
                if starting_note not in ("None", None, ""):
                    cands = [v for v in cands if v.start == str(starting_note)]
                else:
                    allowed0 = allowed_starts(connecting_notes, 0)
                    if allowed0:
                        cands = [v for v in cands if v.start in allowed0]
            if not cands:
                ok = False
                break
            line.append(r.choice(cands))
        if ok:
            return SampledLine(cells=line[::-1], structure=list(mode_list),
                               line_type=line_type, dom_to_minor=dom_to_minor)
    return None


def pivots_respected(degrees: Sequence[Sequence[str]], connecting_notes) -> bool:
    """Check every boundary pivot against the entering cell's allowed set: the
    note a cell STARTS on (== previous cell's end, the pivot) must be in that
    cell's connecting-notes list. Empty/None sets mean 'no constraint'."""
    if not connecting_notes:
        return True
    starts = [str(d[0]).strip() for d in degrees]
    for k in range(1, len(starts)):
        allowed = connecting_notes[k] if k < len(connecting_notes) else None
        if not allowed:
            continue
        allowed_set = {str(a) for a in allowed if a is not None}
        if allowed_set and starts[k] not in allowed_set:
            return False
    return True


def sample_line_checked(max_tries: int = 60, **kwargs) -> Optional[SampledLine]:
    """Sample a line and reject any whose pivots violate connecting_notes."""
    cn = kwargs.get("connecting_notes")
    for _ in range(max_tries):
        out = sample_line(**kwargs)
        if out is None:
            return None
        if pivots_respected(out.degrees, cn):
            return out
    return None


def sample_many(n: int, seed: Optional[int] = None, max_attempts_factor: int = 10,
                **kwargs) -> List[SampledLine]:
    """Up to ``n`` DISTINCT pivot-respecting lines (page 2's batch loop)."""
    rng = random.Random(seed)
    kwargs = dict(kwargs, rng=rng)
    cn = kwargs.get("connecting_notes")
    out: List[SampledLine] = []
    seen = set()
    attempts = 0
    while len(out) < n and attempts < n * max_attempts_factor:
        attempts += 1
        s = sample_line(**kwargs)
        if s is None:
            continue
        if not pivots_respected(s.degrees, cn):
            continue
        if s.signature in seen:
            continue
        seen.add(s.signature)
        out.append(s)
    return out


def all_pairs(line_type: str, bonus: bool = False, movement=None, starting_note=None,
              ending_note=None, connecting_notes=None, n_dorian: int = 1,
              n_myxo: int = 1) -> List[SampledLine]:
    """Every pivot-valid pair for a 2-cell line type (page 2's exhaustive
    enumeration; raw CSV degrees, Myxolidian re-spelled ii-relative in the
    Dorian x Myxolidian combo)."""
    structure = line_structure_mapping(line_type, length=2, n_dorian=n_dorian, n_myxo=n_myxo)
    if len(structure) != 2:
        raise ValueError("exhaustive pairs need a 2-cell line type")
    myxo_to_dorian = line_type == MYXO_TO_DORIAN_LINE_TYPE
    d1 = _sampler_views(structure[0], bonus, False, False, False, myxo_to_dorian)
    d2 = _sampler_views(structure[1], bonus, False, False, False, myxo_to_dorian)
    if movement not in (None, "None"):
        d1 = [v for v in d1 if _movement_ok(v, movement)]
        d2 = [v for v in d2 if _movement_ok(v, movement)]
    if starting_note not in (None, "None", ""):
        d1 = [v for v in d1 if v.start == str(starting_note)]
    elif connecting_notes and connecting_notes[0]:
        first = {str(a) for a in connecting_notes[0] if a is not None}
        d1 = [v for v in d1 if v.start in first]
    if ending_note not in (None, "None", ""):
        d2 = [v for v in d2 if v.end == str(ending_note)]
    out = []
    for a in d1:
        for b in d2:
            if a.end == b.start and pivots_respected([a.degrees, b.degrees], connecting_notes):
                out.append(SampledLine(cells=[a, b], structure=list(structure),
                                       line_type=line_type))
    return out
