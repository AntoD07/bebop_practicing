"""Page 1: pivot pairs and the per-pair fingering search."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.budget import make_budget
from api.cache import respond
from api.schemas import CellRef, ConnectionRequest, PairsRequest
from api.serialize import cell_view_json, config_diff, fingering_json
from scripts.domain.catalog import load_catalog
from scripts.domain.cells import connection_steps, view
from scripts.domain.connections import (
    FREE, is_myxo_to_dorian, pair_key, pairs_for_pivot, reading_mode, score_connection_pair,
)
from scripts.domain.notes import combo_mapping_info
from scripts.fingering.cell_bridge import chord_symbol_for_mode, is_single_chord
from scripts.fingering.config import FingeringConfig
from scripts.fingering.positions import POSITIONS

router = APIRouter()


def resolve_cell(ref: CellRef, chord: str, dom_to_minor: bool, myxo_to_dorian: bool) -> dict:
    """``{"id","name","degrees","movement"}`` in the fingering representation."""
    if ref.id:
        cell = load_catalog().get(ref.id)       # KeyError -> 404 (app handler)
        v = view(cell, connection_steps(chord, dom_to_minor=dom_to_minor,
                                        myxo_to_dorian=myxo_to_dorian))
        if ref.degrees:
            # an explicit override wins (the client already holds the view)
            return {"id": cell.id, "name": cell.name, "degrees": list(ref.degrees),
                    "movement": ref.movement or cell.movement}
        return {"id": cell.id, "name": cell.name, "degrees": list(v.degrees),
                "movement": cell.movement}
    return {"id": None, "name": ref.name, "degrees": list(ref.degrees or []),
            "movement": ref.movement}


@router.post("/connections/pairs")
def pairs(request: Request, body: PairsRequest):
    payload = body.model_dump(mode="json")

    def compute():
        try:
            pp = pairs_for_pivot(body.chord1, body.chord2, pivot=body.pivot, bonus=body.bonus,
                                 dom_to_minor1=body.dom_to_minor1, dom_to_minor2=body.dom_to_minor2,
                                 movement=body.movement, key=body.key)
        except KeyError as e:
            raise HTTPException(404, str(e))
        key = body.key
        single = pp["single_chord"]
        anchors = None
        harmony = None
        if key is not None:
            sym1 = pp["sym1"]
            if single:
                harmony = (f"One chord: {sym1}. {body.chord1} → {body.chord2} stays on a single "
                           f"chord, so today's key ({key}) is its root — and the position sits on it.")
                anchors = {"key": f"Today's key — {key}"}
            else:
                harmony = (f"Today's key {key} is read as the I of a ii-V-I: {body.chord1} starts on "
                           f"{sym1}; the 2nd chord follows from the pivot (shown on each tab).")
                anchors = {"key": f"Today's key — {key}", "chord1": f"1st chord — {sym1}",
                           "chord2": f"2nd chord — {body.chord2}"}
        return {
            "chord1": pp["chord1"], "chord2": pp["chord2"], "pivot": pp["pivot"],
            "raw_pivot": pp["raw_pivot"], "pivots": pp["pivots"],
            "myxo_to_dorian": pp["myxo_to_dorian"], "single_chord": single,
            "read1": pp["read1"], "read2": pp["read2"],
            "dom_to_minor2_effective": pp["dom_to_minor2_effective"],
            "sym1": pp.get("sym1"), "harmony_info": harmony, "anchors": anchors,
            "mapping_info": combo_mapping_info() if pp["myxo_to_dorian"] else None,
            "ending": [cell_view_json(v) for v in pp["ending"]],
            "starting": [cell_view_json(v) for v in pp["starting"]],
            "pairs": [{"end_id": e.id, "start_id": s.id, "pair_key": pair_key(e.name, s.name)}
                      for e, s in pp["pairs"]],
            "positions": POSITIONS, "free_label": FREE,
        }

    return respond(request, "connections/pairs", payload, compute)


@router.post("/fingering/connection")
def connection(request: Request, body: ConnectionRequest):
    payload = body.model_dump(mode="json")
    if body.position is not None and body.position not in POSITIONS and body.position != FREE:
        raise HTTPException(422, f"unknown position {body.position!r}")

    def compute():
        m2d = is_myxo_to_dorian(body.chord1, body.chord2)
        dtm2 = body.dom_to_minor2 and not m2d
        read1 = reading_mode(body.chord1, body.dom_to_minor1)
        read2 = "Dorian" if m2d else reading_mode(body.chord2, dtm2)
        single = is_single_chord([body.chord1, body.chord2])
        c1 = resolve_cell(body.cell1, body.chord1, body.dom_to_minor1, False)
        c2 = resolve_cell(body.cell2, body.chord2, dtm2, m2d)
        cfg = body.config.apply() if body.config else FingeringConfig()
        position = body.position if body.position in POSITIONS else None
        budget = make_budget(body.max_layouts)
        res = score_connection_pair(body.key, read1, read2, c1, c2, position=position,
                                    anchor=body.anchor, myxo_to_dorian=m2d, single_chord=single,
                                    config=cfg, budget=budget, box=body.box)
        anchor_pc = res.get("anchor_pc")
        fings = [fingering_json(r, anchor_pc, mode, body.with_reports)
                 for r, mode in res["fingerings"]]
        n_total = len(fings)
        if body.max_cost is not None:
            fings = [f for f in fings if f["cost"] <= body.max_cost]
        return {
            "end": c1["name"], "start": c2["name"], "end_id": c1["id"], "start_id": c2["id"],
            "pair_key": pair_key(c1["name"], c2["name"]),
            "pivot": {"index": res["pivot_index"], "label": res["pivot_label"],
                      "name": (fings[0]["placed"][res["pivot_index"]]["name"] if fings else None)},
            "pivot_indices": [res["pivot_index"]],
            "sym1": res["sym1"], "sym2": res.get("sym2"),
            "anchor": {"name": body.anchor, "pc": anchor_pc, "sym": res.get("anchor_sym")},
            "read1": read1, "read2": read2, "myxo_to_dorian": m2d, "single_chord": single,
            "position": position or FREE,
            "fingerings": fings, "n_total": n_total, "best": 0 if fings else None,
            "truncated": res["truncated"], "chunks": res["chunks"], "error": res["error"],
            "budget": {"max_layouts": budget.max_layouts, "used": budget.used,
                       "elapsed_ms": round(budget.elapsed_ms(), 1)},
            "config": config_diff(cfg),
        }

    return respond(request, "fingering/connection", payload, compute)
