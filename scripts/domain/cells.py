"""Translated cell views and the ``(cells, pivots, mapping)`` triple.

A :class:`CellView` is a catalog :class:`Cell` read in some harmonic
representation: its degrees / start / end after the translation steps a page
applies (see the ``*_steps`` helpers, which mirror the legacy
``create_cell_frames`` / ``change_note_representation`` wiring exactly):

* pivots (``pivot_steps``): what the pivot pickers compare
* connections (``connection_steps``): what page 1 / the home page finger
* the sampler (``sampler_steps``): what page 2's sampler chains

The old pandas code built the pivot->raw ``mapping`` with a misaligned
``zip(unique, unique)``; here it is built row-wise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scripts.domain.catalog import Cell, cells as catalog_cells
from scripts.domain.transposition import TranslationError, translate_step


@dataclass(frozen=True)
class CellView:
    cell: Cell
    degrees: Tuple[str, ...]
    start: str
    end: str
    steps: Tuple[str, ...] = ()
    error: Optional[str] = None

    # Convenience pass-throughs ------------------------------------------
    @property
    def id(self) -> str:
        return self.cell.id

    @property
    def name(self) -> str:
        return self.cell.name

    @property
    def mode(self) -> str:
        return self.cell.mode

    @property
    def movement(self) -> Optional[str]:
        return self.cell.movement

    @property
    def type(self) -> str:
        return self.cell.type

    @property
    def translated(self) -> bool:
        return bool(self.steps)

    def to_dict(self) -> dict:
        d = self.cell.to_dict()
        d.update({
            "degrees": list(self.degrees), "start": self.start, "end": self.end,
            "raw_degrees": list(self.cell.degrees), "raw_start": self.cell.start,
            "raw_end": self.cell.end, "steps": list(self.steps), "error": self.error,
        })
        return d

    def bridge_dict(self, root, reading_mode: Optional[str] = None) -> dict:
        """The ``{"name","root","degrees","mode","movement"}`` dict the
        fingering bridge consumes."""
        return {"name": self.name, "root": root, "degrees": list(self.degrees),
                "mode": reading_mode or self.mode, "movement": self.movement}


# --------------------------------------------------------------------------- #
# Which translation steps apply where (legacy wiring, verbatim)
# --------------------------------------------------------------------------- #
def pivot_steps(chord: str, dom_to_minor: bool = False, sus4: bool = False) -> List[str]:
    """``create_cell_frames``' pivot representation."""
    steps: List[str] = []
    if chord in ("Minor", "Dorian", "Locrian") and sus4:
        steps.append("sus4")
    if chord in ("Locrian", "MinorResolutions") and dom_to_minor:
        steps.append("dom_to_minor")
    elif chord in ("MajorResolutions", "Myxolidian") and dom_to_minor:
        steps.append("dom_to_major")
    return steps


def connection_steps(chord: str, dom_to_minor: bool = False,
                     myxo_to_dorian: bool = False) -> List[str]:
    """Page 1 / home: the degrees a connection is fingered with."""
    steps: List[str] = []
    if chord in ("MinorResolutions", "Locrian") and dom_to_minor:
        steps.append("dom_to_minor")
    elif chord in ("Myxolidian", "MajorResolutions") and dom_to_minor:
        steps.append("dom_to_major")
    if chord == "Myxolidian" and myxo_to_dorian:
        steps.append("dom_to_dorian")
    return steps


def sampler_steps(mode: str, dom_to_minor: bool = False, sus4: bool = False,
                  loc_to_dom: bool = False, myxo_to_dorian: bool = False) -> List[str]:
    """``change_note_representation`` (page 2's sampler)."""
    steps: List[str] = []
    if mode in ("Minor", "Dorian", "Locrian") and sus4:
        steps.append("sus4")
    if mode == "Locrian" and loc_to_dom:
        steps.append("loc_to_dom")
    if mode in ("Locrian", "MinorResolutions") and dom_to_minor:
        steps.append("dom_to_minor")
    if mode == "MajorResolutions" and dom_to_minor:
        steps.append("dom_to_major")
    if mode == "Myxolidian" and myxo_to_dorian:
        steps.append("dom_to_dorian")
    return steps


def apply_steps(tokens: Iterable[str], steps: Sequence[str], mode: str) -> List[str]:
    out = [str(t) for t in tokens]
    for step in steps:
        out = translate_step(out, step, mode)
    return out


def view(cell: Cell, steps: Sequence[str] = (), strict: bool = True) -> CellView:
    """``cell`` read through ``steps``. With ``strict`` a gap raises
    :class:`TranslationError`; otherwise the view keeps the raw tokens and
    carries the error text."""
    if not steps:
        return CellView(cell=cell, degrees=cell.degrees, start=cell.start, end=cell.end)
    try:
        degrees = tuple(apply_steps(cell.degrees, steps, cell.mode))
        start = apply_steps([cell.start], steps, cell.mode)[0]
        end = apply_steps([cell.end], steps, cell.mode)[0]
    except TranslationError as e:
        if strict:
            raise
        return CellView(cell=cell, degrees=cell.degrees, start=cell.start, end=cell.end,
                        steps=tuple(steps), error=str(e))
    return CellView(cell=cell, degrees=degrees, start=start, end=end, steps=tuple(steps))


def views(cells: Iterable[Cell], steps: Sequence[str] = (), strict: bool = True) -> List[CellView]:
    return [view(c, steps, strict) for c in cells]


def mode_views(mode: str, bonus: bool = False, steps: Sequence[str] = (),
               strict: bool = True) -> List[CellView]:
    return views(catalog_cells(mode, bonus), steps, strict)


# --------------------------------------------------------------------------- #
# The legacy (df_cells, mapped_notes, mapping) triple
# --------------------------------------------------------------------------- #
def cell_frames(chord: str, bonus: bool = False, field: str = "Start Note",
                dom_to_minor: bool = False, sus4: bool = False,
                loc_to_dominant: bool = False,
                ) -> Tuple[List[Cell], List[str], Dict[str, str]]:
    """``(cells, pivots, mapping)``: the raw cells of ``chord``, the unique
    values of ``field`` in the pivot representation (first-appearance order)
    and the row-wise ``{mapped: raw}`` map. ``loc_to_dominant`` is accepted
    for signature parity but — as in the legacy code — never applied here."""
    raw = catalog_cells(chord, bonus)
    steps = pivot_steps(chord, dom_to_minor=dom_to_minor, sus4=sus4)
    vs = views(raw, steps)
    pick = (lambda v: v.start) if field == "Start Note" else (lambda v: v.end)
    pick_raw = (lambda c: c.start) if field == "Start Note" else (lambda c: c.end)
    pivots = list(dict.fromkeys(pick(v) for v in vs))
    mapping: Dict[str, str] = {}
    for v in vs:
        mapping.setdefault(pick(v), pick_raw(v.cell))
    return raw, pivots, mapping
