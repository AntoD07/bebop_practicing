"""Page 2: line sampling, exhaustive pairs and line fingerings."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.budget import make_budget
from api.cache import respond
from api.schemas import LineFingeringRequest, LinePairsRequest, SampleRequest
from api.serialize import config_diff, fingering_json, sampled_line_json
from scripts.domain.catalog import load_catalog
from scripts.domain.lines import line_cells, line_fingerings
from scripts.domain.notes import harmony_caption
from scripts.domain.sampling import (
    LINE_TYPES, MYXO_TO_DORIAN_LINE_TYPE, all_pairs, connecting_note_lists,
    line_structure_mapping, sample_line_checked, sample_many,
)
from scripts.domain.notes import combo_chord_tones_info, combo_mapping_info
from scripts.fingering.config import FingeringConfig
from scripts.fingering.positions import POSITIONS

router = APIRouter()


def _check_type(line_type: str) -> None:
    if line_type not in LINE_TYPES:
        raise HTTPException(422, f"unknown line type {line_type!r}; types: {LINE_TYPES}")


@router.post("/lines/sample")
def sample(request: Request, body: SampleRequest):
    _check_type(body.line_type)
    payload = body.model_dump(mode="json")
    # An unseeded sample must not be cached (every click is a new draw).
    if body.seed is None:
        import random
        payload["_nonce"] = random.random()

    def compute():
        structure = line_structure_mapping(body.line_type, length=body.length,
                                           n_dorian=body.n_dorian, n_myxo=body.n_myxo)
        cn = connecting_note_lists(body.line_type, structure, body.connecting_notes, body.chord_tones)
        kwargs = dict(line_type=body.line_type, bonus=body.bonus, dom_to_minor=body.dom_to_minor,
                      sus4=body.sus4, length=body.length, movement=body.movement,
                      starting_note=body.starting_note, ending_note=body.ending_note,
                      connecting_notes=cn, n_dorian=body.n_dorian, n_myxo=body.n_myxo)
        if body.n == 1:
            import random as _r
            one = sample_line_checked(rng=_r.Random(body.seed), **kwargs)
            lines = [one] if one is not None else []
        else:
            lines = sample_many(body.n, seed=body.seed, **kwargs)
        is_combo = body.line_type == MYXO_TO_DORIAN_LINE_TYPE
        return {
            "line_type": body.line_type,
            "structure_preview": structure,
            "connecting_notes": cn,
            "lines": [sampled_line_json(sl, body.key) for sl in lines],
            "message": (None if lines else
                        "No line satisfying the connecting-note constraints was found — try relaxing them."),
            "harmony_caption": harmony_caption(body.key, structure) if body.key else None,
            "mapping_info": combo_mapping_info() if is_combo else None,
            "chord_tones_info": combo_chord_tones_info() if (is_combo and body.chord_tones) else None,
        }

    return respond(request, "lines/sample", payload, compute)


@router.post("/lines/pairs")
def pairs(request: Request, body: LinePairsRequest):
    _check_type(body.line_type)
    payload = body.model_dump(mode="json")

    def compute():
        structure = line_structure_mapping(body.line_type, length=2, n_dorian=body.n_dorian,
                                           n_myxo=body.n_myxo)
        if len(structure) != 2:
            raise HTTPException(422, "exhaustive pairs need a 2-cell line type")
        cn = connecting_note_lists(body.line_type, structure, body.connecting_notes, body.chord_tones)
        lines = all_pairs(body.line_type, bonus=body.bonus, movement=body.movement,
                          starting_note=body.starting_note, ending_note=body.ending_note,
                          connecting_notes=cn, n_dorian=body.n_dorian, n_myxo=body.n_myxo)
        return {"line_type": body.line_type, "structure": structure, "connecting_notes": cn,
                "lines": [sampled_line_json(sl, body.key) for sl in lines]}

    return respond(request, "lines/pairs", payload, compute)


@router.post("/fingering/line")
def line(request: Request, body: LineFingeringRequest):
    payload = body.model_dump(mode="json")
    if body.position is not None and body.position not in POSITIONS and body.position != "Free (best on the neck)":
        raise HTTPException(422, f"unknown position {body.position!r}")

    def compute():
        cat = load_catalog()
        names, degrees, movements = [], [], []
        for ref in body.cells:
            if ref.id:
                c = cat.get(ref.id)
                names.append(c.name)
                degrees.append(list(ref.degrees) if ref.degrees else list(c.degrees))
                movements.append(ref.movement or c.movement)
            else:
                names.append(ref.name)
                degrees.append(list(ref.degrees or []))
                movements.append(ref.movement)
        mv_modes = body.movement_modes or body.reading_modes
        cells = line_cells(body.key, names, degrees, body.reading_modes, mv_modes, movements)
        cfg = body.config.apply() if body.config else FingeringConfig()
        position = body.position if body.position in POSITIONS else None
        budget = make_budget(body.max_layouts)
        pk = body.pos_key or body.key
        res = line_fingerings(body.key, cells, body.reading_modes, mv_modes, position=position,
                              pos_key=pk, config=cfg, budget=budget)
        fings = [fingering_json(r, pk, mode, body.with_reports) for r, mode in res["fingerings"]]
        n_total = len(fings)
        if body.max_cost is not None:
            fings = [f for f in fings if f["cost"] <= body.max_cost]
        return {
            "key": body.key, "pos_key": pk, "position": position or "Free (best on the neck)",
            "cells": [{"name": n, "degrees": d, "movement": m, "reading_mode": rm, "movement_mode": mm}
                      for n, d, m, rm, mm in zip(names, degrees, movements, body.reading_modes, mv_modes)],
            "pivot_indices": res["pivots"],
            "fingerings": fings, "n_total": n_total, "best": 0 if fings else None,
            "truncated": res["truncated"], "chunks": res["chunks"], "error": res["error"],
            "harmony_caption": harmony_caption(body.key, mv_modes),
            "budget": {"max_layouts": budget.max_layouts, "used": budget.used,
                       "elapsed_ms": round(budget.elapsed_ms(), 1)},
            "config": config_diff(cfg),
        }

    return respond(request, "fingering/line", payload, compute)
