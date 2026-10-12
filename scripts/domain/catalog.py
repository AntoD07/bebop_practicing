"""The cell library (``data/sampling/*_sampling.csv``) as frozen dataclasses.

The CSVs stay the hand-edited source of truth; this module is the ONE place
that reads them (``csv.DictReader`` + ``ast.literal_eval`` on ``Notes``). Every
token is stripped, a missing ``Type`` column means Essential (7sus4) and a
missing ``Movement`` column means None.

Cell ids are stable across row edits: ``"<mode>:<sha1(mode|name|degrees)[:8]>"``
(identical duplicates get ``-2``, ``-3``…). ``legacy_key`` (``(mode, name)``)
is what ``connection_picks.json`` was keyed on.

Data oddities are SURFACED, not silently fixed: rows whose Start/End Note
differ from ``Notes[0]``/``Notes[-1]`` (``nominal_mismatch``) and duplicate
names land in ``Catalog.warnings`` (served by ``/health`` and ``/cells``).
"""

from __future__ import annotations

import ast
import csv
import hashlib
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from scripts.domain.notes import MODES
from scripts.paths import sampling_file

# Cell names may HINT the true sounding degree of their first note, e.g.
# "Bill Evans enclosure (from #9)" whose Start Note is the nominal "3" (used
# for pivot MATCHING) while the note actually played is the #9 — the pivot is
# re-pitched a semitone. "(from ...)" and "(start ...)" both work; ordinal
# suffixes and b13/13 spellings are normalised. Tokens with a chord prefix
# (e.g. "(from V-7th)") are ignored — they name another chord's degree.
_PIVOT_HINT_RE = re.compile(r"\((?:from|start)\s*([#b]?)\s*(\d{1,2}|maj7)"
                            r"(?:st|nd|rd|th)?\s*\)", re.I)
_HINT_NORMALISE = {"b13": "b6", "13": "6", "#12": "#11"}


def pivot_hint(name: Optional[str]) -> Optional[str]:
    """The hinted first-note degree from a cell name, or None."""
    m = _PIVOT_HINT_RE.search(name or "")
    if not m:
        return None
    token = (m.group(1) or "") + m.group(2)
    return _HINT_NORMALISE.get(token, token)


def _clean(value) -> str:
    return "" if value is None else str(value).strip()


def parse_notes(raw) -> Tuple[str, ...]:
    """``"['1', '3', '5 ']" -> ('1', '3', '5')``."""
    if isinstance(raw, (list, tuple)):
        return tuple(_clean(t) for t in raw)
    parsed = ast.literal_eval(_clean(raw))
    if isinstance(parsed, str):
        parsed = [parsed]
    return tuple(_clean(t) for t in parsed)


@dataclass(frozen=True)
class Cell:
    id: str
    mode: str
    index: int                       # 0-based row position in the CSV
    name: str
    degrees: Tuple[str, ...]
    start: str
    end: str
    movement: Optional[str]          # "A" / "D" / "N" / None
    type: str                        # "Essential" / "Bonus"
    nominal_mismatch: bool           # Start/End != Notes[0]/[-1]
    pivot_hint: Optional[str]
    modes: Optional[Tuple[str, ...]] = None   # the (latent) "Modes" column

    @property
    def legacy_key(self) -> Tuple[str, str]:
        return (self.mode, self.name)

    @property
    def essential(self) -> bool:
        return self.type == "Essential"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "mode": self.mode, "index": self.index, "name": self.name,
            "degrees": list(self.degrees), "start": self.start, "end": self.end,
            "movement": self.movement, "type": self.type,
            "nominal_mismatch": self.nominal_mismatch, "pivot_hint": self.pivot_hint,
        }


@dataclass
class Catalog:
    cells_by_mode: Dict[str, List[Cell]] = field(default_factory=dict)
    by_id: Dict[str, Cell] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    files: Dict[str, str] = field(default_factory=dict)

    def cells(self, mode: str, bonus: bool = False) -> List[Cell]:
        """A mode's cells; Essential only unless ``bonus`` (CSV order)."""
        if mode not in self.cells_by_mode:
            raise KeyError(f"unknown mode {mode!r}")
        rows = self.cells_by_mode[mode]
        return list(rows) if bonus else [c for c in rows if c.essential]

    def get(self, cell_id: str) -> Cell:
        try:
            return self.by_id[cell_id]
        except KeyError:
            raise KeyError(f"unknown cell id {cell_id!r}") from None

    def find(self, mode: str, name: str) -> Optional[Cell]:
        """First cell named ``name`` in ``mode`` (any type), or None."""
        for c in self.cells_by_mode.get(mode, []):
            if c.name == name:
                return c
        return None

    def stats(self) -> Dict[str, dict]:
        return {m: {"total": len(rows), "essential": sum(1 for c in rows if c.essential)}
                for m, rows in self.cells_by_mode.items()}


def _read_mode(mode: str, path: str) -> Tuple[List[Cell], List[str]]:
    cells: List[Cell] = []
    warnings: List[str] = []
    if not os.path.exists(path):
        return cells, [f"{mode}: sampling file missing ({os.path.basename(path)})"]
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        has_type = "Type" in (reader.fieldnames or [])
        has_mv = "Movement" in (reader.fieldnames or [])
        has_modes = "Modes" in (reader.fieldnames or [])
        if not has_type:
            warnings.append(f"{mode}: no Type column — every cell read as Essential")
        if not has_mv:
            warnings.append(f"{mode}: no Movement column — movements read as None")
        seen_ids: Dict[str, int] = {}
        name_counts: Dict[str, int] = {}
        for index, row in enumerate(reader):
            name = _clean(row.get("Cell Name"))
            if not name:
                warnings.append(f"{mode}: row {index + 2} has no Cell Name — skipped")
                continue
            try:
                degrees = parse_notes(row.get("Notes"))
            except (ValueError, SyntaxError) as e:
                warnings.append(f"{mode}: {name!r} has unparsable Notes ({e}) — skipped")
                continue
            if not degrees:
                warnings.append(f"{mode}: {name!r} has no notes — skipped")
                continue
            start, end = _clean(row.get("Start Note")), _clean(row.get("End Note"))
            mv = _clean(row.get("Movement")) if has_mv else ""
            movement = mv if mv in ("A", "D", "N") else None
            if has_mv and movement is None:
                warnings.append(f"{mode}: {name!r} has Movement {mv!r} (expected A/D/N)")
            typ = (_clean(row.get("Type")) if has_type else "") or "Essential"
            modes_col = None
            if has_modes:
                try:
                    modes_col = tuple(_clean(m) for m in ast.literal_eval(_clean(row.get("Modes"))))
                except (ValueError, SyntaxError):
                    modes_col = None
            mismatch = (start != degrees[0]) or (end != degrees[-1])
            if mismatch:
                warnings.append(
                    f"{mode}: {name!r} Start/End ({start}/{end}) differ from "
                    f"Notes[0]/[-1] ({degrees[0]}/{degrees[-1]})")
            fingerprint = "|".join([mode, name, ",".join(degrees)])
            base = f"{mode}:{hashlib.sha1(fingerprint.encode()).hexdigest()[:8]}"
            n = seen_ids.get(base, 0) + 1
            seen_ids[base] = n
            cid = base if n == 1 else f"{base}-{n}"
            if n > 1:
                warnings.append(f"{mode}: identical duplicate row {name!r} (id {cid})")
            name_counts[name] = name_counts.get(name, 0) + 1
            cells.append(Cell(
                id=cid, mode=mode, index=index, name=name, degrees=degrees,
                start=start, end=end, movement=movement, type=typ,
                nominal_mismatch=mismatch, pivot_hint=pivot_hint(name), modes=modes_col,
            ))
        for name, n in name_counts.items():
            if n > 1:
                warnings.append(f"{mode}: duplicate cell name {name!r} ({n} rows)")
    return cells, warnings


def build_catalog(modes=None) -> Catalog:
    cat = Catalog()
    for mode in (modes or MODES):
        path = sampling_file(mode)
        cells, warnings = _read_mode(mode, path)
        cat.cells_by_mode[mode] = cells
        cat.files[mode] = path
        cat.warnings.extend(warnings)
        for c in cells:
            cat.by_id[c.id] = c
    return cat


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    """The catalog, read once per process (≈5 ms)."""
    return build_catalog()


def reload_catalog() -> Catalog:
    load_catalog.cache_clear()
    return load_catalog()


def cells(mode: str, bonus: bool = False) -> List[Cell]:
    return load_catalog().cells(mode, bonus)


def cell_by_id(cell_id: str) -> Cell:
    return load_catalog().get(cell_id)


def find_cell(mode: str, name: str) -> Optional[Cell]:
    return load_catalog().find(mode, name)
