"""The catalog, degree translation and the shared constants / positions."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from api.cache import respond
from api.schemas import TranslateRequest
from api.serialize import cell_view_json
from scripts.domain.catalog import load_catalog
from scripts.domain.cells import views
from scripts.domain.notes import (
    CHORD_MODES, CHORD_TONES, DEGREE_ORDER, LINE_MOVEMENT_OPTIONS, MODES, MOVEMENTS,
    NOTE_OPTIONS, PRACTICE_KEYS,
)
from scripts.domain.sampling import (
    ALL_NOTES_DEFAULT_TYPES, DEFAULT_LINE_TYPE, LINE_TYPES, MYXO_TO_DORIAN_LINE_TYPE,
    NO_FIRST_LAST_NOTE_TYPES, line_structure_dic,
)
from scripts.domain.transposition import MAPPING_NAMES, translate_step
from scripts.fingering.cell_bridge import root_pc
from scripts.fingering.config import FingeringConfig
from scripts.fingering.positions import POSITIONS, POSITION_DESC, POSITION_SLACK, position_boxes
from scripts.pentatonics.fingering_rank import PENTA_POSITION_SLACK

router = APIRouter()

TRANSLATIONS = ["none"] + MAPPING_NAMES


@router.get("/cells")
def cells(request: Request, mode: str = Query(...), bonus: bool = False,
          translate: str = "none", translate_mode: Optional[str] = None):
    if translate not in TRANSLATIONS:
        raise HTTPException(422, f"translate must be one of {TRANSLATIONS}")
    payload = {"mode": mode, "bonus": bonus, "translate": translate, "translate_mode": translate_mode}

    def compute():
        cat = load_catalog()
        try:
            raw = cat.cells(mode, bonus)
        except KeyError:
            raise HTTPException(404, f"unknown mode {mode!r}; modes: {MODES}")
        steps = [] if translate == "none" else [translate]
        if translate == "sus4":
            # the sus4 shift needs its target mode; the catalog cell's own
            # mode is the 7sus4 vocabulary, so take it from the query
            out = []
            for c in raw:
                v = views([c], [], strict=False)[0]
                try:
                    degs = translate_step(c.degrees, "sus4", translate_mode or "Dorian")
                    start = translate_step([c.start], "sus4", translate_mode or "Dorian")[0]
                    end = translate_step([c.end], "sus4", translate_mode or "Dorian")[0]
                    d = v.to_dict()
                    d.update(degrees=degs, start=start, end=end, steps=["sus4"])
                except Exception as e:  # noqa: BLE001
                    d = v.to_dict()
                    d["error"] = str(e)
                out.append(d)
        else:
            out = [cell_view_json(v) for v in views(raw, steps, strict=False)]
        return {"mode": mode, "bonus": bonus, "translate": translate, "cells": out,
                "warnings": [w for w in cat.warnings if w.startswith(f"{mode}:")]}

    return respond(request, "cells", payload, compute)


@router.post("/translate")
def translate(body: TranslateRequest):
    if body.mapping not in MAPPING_NAMES:
        raise HTTPException(422, f"mapping must be one of {MAPPING_NAMES}")
    # TranslationError -> 422 via the app-level handler
    return {"tokens": translate_step(body.tokens, body.mapping, body.mode),
            "mapping": body.mapping}


def constants() -> dict:
    return {
        "keys": PRACTICE_KEYS,
        "modes": MODES,
        "chord_modes": CHORD_MODES,
        "degree_order": DEGREE_ORDER,
        "chord_tones": CHORD_TONES,
        "note_options": NOTE_OPTIONS,
        "movements": MOVEMENTS,
        "line_movement_options": LINE_MOVEMENT_OPTIONS,
        "positions": POSITIONS,
        "position_desc": POSITION_DESC,
        "position_slack": POSITION_SLACK,
        "penta_position_slack": PENTA_POSITION_SLACK,
        "line_types": LINE_TYPES,
        "default_line_type": DEFAULT_LINE_TYPE,
        "line_structures": line_structure_dic,
        "combo_line_type": MYXO_TO_DORIAN_LINE_TYPE,
        "no_first_last_note_types": list(NO_FIRST_LAST_NOTE_TYPES),
        "all_notes_default_types": list(ALL_NOTES_DEFAULT_TYPES),
        "translations": TRANSLATIONS,
    }


@router.get("/positions")
def positions(request: Request, key: str = "C"):
    payload = {"key": key}

    def compute():
        try:
            root_pc(key)
        except (KeyError, IndexError):
            raise HTTPException(422, f"bad key {key!r}")
        out = []
        for i, name in enumerate(POSITIONS, start=1):
            boxes = []
            for cfg, root_midi in position_boxes(name, key, FingeringConfig()):
                lo, hi = cfg.fret_window
                boxes.append({"fret_lo": lo, "fret_hi": hi, "strings": list(cfg.string_range),
                              "root_strings": list(cfg.root_pin[1]) if cfg.root_pin else [],
                              "root_midi": root_midi})
            out.append({"index": i, "name": name, "desc": POSITION_DESC.get(name, ""),
                        "boxes": boxes})
        return {"key": key, "positions": out, "constants": constants()}

    return respond(request, "positions", payload, compute)


@router.get("/constants")
def get_constants():
    return {"constants": constants()}
