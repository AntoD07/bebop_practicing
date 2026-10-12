"""Pydantic request models (responses are documented in ``api/serialize.py``)."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

from scripts.fingering.config import FingeringConfig

Anchor = Literal["key", "chord1", "chord2"]


class CellRef(BaseModel):
    """A catalog cell by ``id``, or an explicit cell (``name``/``mode``/
    ``degrees``/``movement``)."""
    id: Optional[str] = None
    name: Optional[str] = None
    mode: Optional[str] = None
    degrees: Optional[List[str]] = None
    movement: Optional[str] = None

    @model_validator(mode="after")
    def _one_of(self):
        if not self.id and not (self.name and self.degrees):
            raise ValueError("a cell needs an id, or a name + degrees")
        return self


class ConfigOverrides(BaseModel):
    """The whitelisted fingering knobs (the Pentatonics page's sliders)."""
    max_stretch: Optional[int] = Field(None, ge=3, le=6)
    u_cost: Optional[float] = Field(None, ge=0, le=20)
    drop_cost: Optional[float] = Field(None, ge=0, le=50)
    shift_cost: Optional[float] = Field(None, ge=0, le=10)
    break_cost: Optional[float] = Field(None, ge=0, le=20)
    sweep_bonus: Optional[float] = Field(None, ge=0, le=10)
    max_fret: Optional[int] = Field(None, ge=12, le=22)

    def apply(self, base: Optional[FingeringConfig] = None) -> FingeringConfig:
        base = base or FingeringConfig()
        over = {k: v for k, v in self.model_dump().items() if v is not None}
        return base.with_overrides(**over) if over else base


class TranslateRequest(BaseModel):
    tokens: List[str]
    mapping: str
    mode: Optional[str] = None     # target mode for the sus4 shift


class PairsRequest(BaseModel):
    chord1: str
    chord2: str
    bonus: bool = False
    dom_to_minor1: bool = False
    dom_to_minor2: bool = False
    movement: Optional[str] = None
    pivot: Optional[str] = None
    key: Optional[str] = None


class ConnectionRequest(BaseModel):
    key: str
    chord1: str
    chord2: str
    cell1: CellRef
    cell2: CellRef
    bonus: bool = False
    dom_to_minor1: bool = False
    dom_to_minor2: bool = False
    position: Optional[str] = None
    anchor: Anchor = "key"
    box: Optional[int] = Field(None, ge=0, le=1)
    max_layouts: Optional[int] = Field(None, ge=1)
    max_cost: Optional[float] = None
    config: Optional[ConfigOverrides] = None
    with_reports: bool = True


class LineFingeringRequest(BaseModel):
    key: str
    cells: List[CellRef]
    reading_modes: List[str]
    movement_modes: Optional[List[str]] = None
    position: Optional[str] = None
    pos_key: Optional[str] = None
    max_layouts: Optional[int] = Field(None, ge=1)
    max_cost: Optional[float] = None
    config: Optional[ConfigOverrides] = None
    with_reports: bool = True

    @model_validator(mode="after")
    def _lengths(self):
        if len(self.cells) != len(self.reading_modes):
            raise ValueError("cells and reading_modes must have the same length")
        if self.movement_modes is not None and len(self.movement_modes) != len(self.cells):
            raise ValueError("movement_modes must match cells")
        if not self.cells:
            raise ValueError("a line needs at least one cell")
        return self


class SampleRequest(BaseModel):
    line_type: str
    length: int = Field(4, ge=1, le=12)
    n_dorian: int = Field(1, ge=1, le=6)
    n_myxo: int = Field(1, ge=1, le=6)
    bonus: bool = False
    dom_to_minor: bool = False
    sus4: bool = False
    movement: Optional[str] = None
    starting_note: Optional[str] = None
    ending_note: Optional[str] = None
    connecting_notes: Optional[List[str]] = None     # the picker's selection (None = page default)
    chord_tones: bool = False
    n: int = Field(1, ge=1, le=100)
    seed: Optional[int] = None
    key: Optional[str] = None


class LinePairsRequest(BaseModel):
    line_type: str
    bonus: bool = False
    movement: Optional[str] = None
    starting_note: Optional[str] = None
    ending_note: Optional[str] = None
    connecting_notes: Optional[List[str]] = None
    chord_tones: bool = False
    n_dorian: int = Field(1, ge=1, le=6)
    n_myxo: int = Field(1, ge=1, le=6)
    key: Optional[str] = None


class PositionsFingeringRequest(BaseModel):
    key: str
    mode: str
    cell: CellRef
    dom_to_minor: bool = False
    config: Optional[ConfigOverrides] = None
    with_reports: bool = True


class NoteIn(BaseModel):
    pitch: Union[int, str]
    start: Optional[float] = None
    phrase_start: bool = False
    degree: Optional[str] = None
    cell: Optional[str] = None
    role: Optional[str] = None


class ChordIn(BaseModel):
    start_beat: float
    symbol: str


class RankAbsoluteRequest(BaseModel):
    key: str
    line: List[NoteIn] = Field(..., min_length=1, max_length=64)
    chords: List[ChordIn] = Field(default_factory=list)
    beats_per_bar: int = Field(4, ge=1, le=12)
    density: Optional[Literal["quarter", "eighth"]] = None
    config: Optional[ConfigOverrides] = None
    with_reports: bool = True


class ParseMusicXmlRequest(BaseModel):
    filename: str = "score.musicxml"
    data_b64: str


class VisionRequest(BaseModel):
    images: List[str] = Field(..., min_length=1, max_length=8)   # PNG, base64


class PentaGenerateRequest(BaseModel):
    key: str
    penta: str = "minor"
    exercise: Literal["scale", "pattern", "chromatic", "bergonzi", "shifting"] = "scale"
    direction: str = "ascending"
    n_octaves: int = Field(3, ge=1, le=3)
    low_octave: int = Field(1, ge=1, le=4)
    start_degs: Optional[List[int]] = None     # None = every degree
    x: int = Field(4, ge=2, le=8)
    add_b6: bool = False
    formula: Optional[str] = None
    shift_choice: Optional[str] = None         # Bergonzi side-slip (None = sweep)
    groups_per_shift: int = Field(2, ge=1, le=6)
    n_shifts: int = Field(3, ge=1, le=8)
    interval_name: Optional[str] = None        # Shifting exercise


class RankRequest(BaseModel):
    key: str
    line: List[NoteIn] = Field(..., min_length=2, max_length=200)
    position: Optional[str] = None
    root: Optional[str] = None
    penta: str = "minor"
    group: Optional[int] = Field(None, ge=1)
    generic: bool = False                     # triads/hexatonics: no 3+2 / open systems
    start_label: Optional[str] = None
    config: Optional[ConfigOverrides] = None
    max_layouts: Optional[int] = Field(None, ge=1)
    with_reports: bool = True


class TriadGenerateRequest(BaseModel):
    root1: str
    quality1: str = "major"
    root2: str
    quality2: str = "major"
    exercise: Literal["scale", "pattern", "alternating"] = "scale"
    direction: str = "ascending"
    n_octaves: int = Field(2, ge=1, le=3)
    low_octave: int = Field(2, ge=1, le=4)
    x: int = Field(4, ge=2, le=8)
    start_degs: Optional[List[int]] = None
