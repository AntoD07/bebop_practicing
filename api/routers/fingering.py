"""Home-page per-position tabs and the score page's absolute ranking."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.cache import respond
from api.schemas import PositionsFingeringRequest, RankAbsoluteRequest
from api.serialize import config_diff, fingering_json
from scripts.domain.catalog import load_catalog
from scripts.domain.cells import connection_steps, view
from scripts.fingering.config import FingeringConfig
from scripts.fingering.pitch import parse_pitch
from scripts.fingering.positions import POSITIONS, optimize_all_positions, rank_absolute_fingerings

router = APIRouter()

SHIFT_TEXT = {0: "as written", -12: "1 octave down", 12: "1 octave up",
              -24: "2 octaves down", 24: "2 octaves up"}


@router.post("/fingering/positions")
def positions(request: Request, body: PositionsFingeringRequest):
    payload = body.model_dump(mode="json")

    def compute():
        ref = body.cell
        if ref.id:
            cell = load_catalog().get(ref.id)
            v = view(cell, connection_steps(body.mode, dom_to_minor=body.dom_to_minor))
            name, degrees, movement = cell.name, list(ref.degrees or v.degrees), ref.movement or cell.movement
        else:
            name, degrees, movement = ref.name, list(ref.degrees or []), ref.movement
        cfg = body.config.apply() if body.config else FingeringConfig()
        c = {"name": name, "root": body.key, "degrees": degrees, "mode": body.mode,
             "movement": movement}
        ctx = {"key": body.key,
               "chords": [{"start_beat": 0, "symbol": f"{body.key} {body.mode}"}]}
        try:
            ranked = optimize_all_positions(c, ctx, cfg)
        except (ValueError, KeyError) as e:
            raise HTTPException(400, f"could not compute fingering: {e}")
        out = []
        for p in ranked:
            out.append({
                "name": p["name"], "index": POSITIONS.index(p["name"]) + 1,
                "best_cost": p["best_cost"],
                "octaves": [{
                    "cost": o["cost"], "register": o["register"], "note": o["note"],
                    "fingering": fingering_json(o["result"], body.key, "optimum", body.with_reports),
                } for o in p["octaves"]],
            })
        return {"key": body.key, "mode": body.mode, "cell": {"name": name, "degrees": degrees,
                                                                "movement": movement},
                "positions": out, "config": config_diff(cfg)}

    return respond(request, "fingering/positions", payload, compute)


@router.post("/fingering/rank-absolute")
def rank_absolute(request: Request, body: RankAbsoluteRequest):
    payload = body.model_dump(mode="json")

    def compute():
        line = []
        for i, n in enumerate(body.line):
            try:
                midi = parse_pitch(n.pitch)
            except ValueError as e:
                raise HTTPException(422, f"note {i}: {e}")
            line.append({"pitch": midi, "start": float(n.start if n.start is not None else i),
                         "phrase_start": bool(n.phrase_start), "degree": n.degree,
                         "cell": n.cell, "role": n.role})
        line.sort(key=lambda d: d["start"])
        line[0]["phrase_start"] = True
        if body.density:
            density = body.density
        else:
            gaps = [b["start"] - a["start"] for a, b in zip(line, line[1:])]
            density = "eighth" if gaps and sorted(gaps)[len(gaps) // 2] < 0.99 else "quarter"
        chords = [c.model_dump() for c in body.chords]
        ctx = {"key": body.key, "chords": chords, "beats_per_bar": body.beats_per_bar,
               "density": density}
        base = (body.config.apply() if body.config else FingeringConfig()).with_overrides(
            beats_per_bar=body.beats_per_bar)
        rows = rank_absolute_fingerings(line, ctx, body.key, base=base)
        out = []
        for r in rows:
            out.append({
                "label": r["label"], "cost": r["cost"], "where": r["where"], "n_up": r["n_up"],
                "also": list(r["also"]), "shift": r["shift"],
                "shift_text": SHIFT_TEXT.get(r["shift"], "—") if r["shift"] is not None else "—",
                "fingering": (fingering_json(r["result"], body.key, "ranked", body.with_reports)
                              if r["result"] is not None else None),
            })
        feasible = [r for r in out if r["fingering"] is not None]
        return {"key": body.key, "density": density, "beats_per_bar": body.beats_per_bar,
                "rows": out, "n_feasible": len(feasible),
                "all_shifted": bool(feasible) and all(r["shift"] for r in feasible),
                "config": config_diff(base)}

    return respond(request, "fingering/rank-absolute", payload, compute)
