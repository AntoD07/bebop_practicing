"""Triad pairs & hexatonics (page 6): the pair, its neck markers, position
boxes and the exercise generators. Ranking goes through
``POST /pentatonics/rank`` with ``generic: true``."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.cache import respond
from api.schemas import TriadGenerateRequest
from scripts.fingering.config import FingeringConfig
from scripts.fingering.positions import POSITIONS
from scripts.pentatonics.fingering_rank import PENTA_POSITION_SLACK
from scripts.triad_pairs.neck_map import TRIAD_COLOURS, neck_markers, position_map_boxes
from scripts.triad_pairs.triads import (
    ALTERNATING_DIRECTIONS, DEFAULT_PAIR_INTERVAL, QUALITY_NAMES, ROOTS, SCALE_DIRECTIONS,
    Triad, TriadPair, alternating_triads_run, hexatonic_pattern_run, hexatonic_scale_run,
)

router = APIRouter()


def _pair(root1, quality1, root2, quality2) -> TriadPair:
    for r in (root1, root2):
        if r not in ROOTS:
            raise HTTPException(422, f"root must be one of {ROOTS}")
    for q in (quality1, quality2):
        if q not in QUALITY_NAMES:
            raise HTTPException(422, f"quality must be one of {QUALITY_NAMES}")
    return TriadPair(Triad(root1, quality1), Triad(root2, quality2))


def _triad_json(t: Triad) -> dict:
    return {"root": t.root, "quality": t.quality, "symbol": t.symbol,
            "names": list(t.names), "degrees": list(t.degrees), "pcs": list(t.pcs)}


@router.get("/triads/pair")
def pair(request: Request, root1: str = "C", quality1: str = "major", root2: str = "D",
         quality2: str = "major", key: str = "C", max_fret: int = 15):
    payload = {"root1": root1, "quality1": quality1, "root2": root2, "quality2": quality2,
               "key": key, "max_fret": max_fret}

    def compute():
        p = _pair(root1, quality1, root2, quality2)
        hexa = p.hexatonic
        boxes = {}
        for name in POSITIONS:
            boxes[name] = [{"fret_lo": lo, "fret_hi": hi, "strings": list(strings)}
                           for lo, hi, strings in position_map_boxes(name, key, FingeringConfig())]
        return {
            "title": p.title, "interval_name": p.interval_name,
            "triads": [_triad_json(t) for t in p.triads],
            "hexatonic": [{**t, "triads": list(t["triads"])} for t in hexa],
            "hexatonic_names": p.hexatonic_names,
            "common": [p.name_for(pc) for pc in p.common_pcs],
            "identical": p.first == p.second,
            "markers": [{**m, "triads": list(m["triads"]), "roots": list(m["roots"])}
                        for m in neck_markers(p, max_fret)],
            "boxes": boxes, "colours": list(TRIAD_COLOURS), "slack": PENTA_POSITION_SLACK,
            "constants": {"roots": ROOTS, "qualities": QUALITY_NAMES,
                          "default_interval": DEFAULT_PAIR_INTERVAL,
                          "scale_directions": SCALE_DIRECTIONS,
                          "alternating_directions": ALTERNATING_DIRECTIONS},
        }

    return respond(request, "triads/pair", payload, compute)


@router.post("/triads/generate")
def generate(request: Request, body: TriadGenerateRequest):
    payload = body.model_dump(mode="json")

    def compute():
        p = _pair(body.root1, body.quality1, body.root2, body.quality2)
        hexa = p.hexatonic
        if body.start_degs:
            bad = [i for i in body.start_degs if not 0 <= i < len(hexa)]
            if bad:
                raise HTTPException(422, f"start_degs out of range: {bad}")
            starts = [(hexa[i]["name"], i) for i in body.start_degs]
        else:
            starts = [(t["name"], i) for i, t in enumerate(hexa)]
        note = "" if body.start_degs else " · all starts"
        lo, n, d, x = body.low_octave, body.n_octaves, body.direction, body.x
        if body.exercise == "scale":
            lbs = {lbl: hexatonic_scale_run(p, lo, n, d, start_deg=sd) for lbl, sd in starts}
            title, group = f"{p.title} hexatonic — {d} ({n} oct){note}", None
        elif body.exercise == "pattern":
            lbs = {lbl: hexatonic_pattern_run(p, lo, n, x, d, start_deg=sd) for lbl, sd in starts}
            title, group = f"{p.title} — {x}-notes grouping, {d} ({n} oct){note}", x
        else:
            if d not in ALTERNATING_DIRECTIONS:
                raise HTTPException(422, f"direction must be one of {ALTERNATING_DIRECTIONS}")
            lbs = {lbl: alternating_triads_run(p, lo, n, x, d, start_deg=sd) for lbl, sd in starts}
            title, group = f"{p.title} — alternating triads, {x} notes, {d} ({n} oct){note}", x
        lbs = {k: v for k, v in lbs.items() if v}
        return {"title": title, "group": group, "exercise": body.exercise,
                "start_labels": list(lbs), "lines_by_start": lbs,
                "message": None if lbs else "Nothing to play — the grouping is longer than the run."}

    return respond(request, "triads/generate", payload, compute)
