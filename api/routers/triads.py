"""Triad pairs & hexatonics (page 6): the pair, its neck markers, position
boxes and the exercise generators. Ranking goes through
``POST /pentatonics/rank`` with ``generic: true`` (+ ``run_weights: true``).

Favourite fingerings are stateless here: ``/triads/favorites/make`` turns a
ranked fingering into the record the app stores, ``/triads/favorites/render``
replays a stored record as saved or mimicked in another key."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.cache import respond
from api.schemas import FavoriteMakeRequest, FavoriteRenderRequest, TriadGenerateRequest, TriadPairIn
from api.serialize import fingering_json
from scripts.fingering.config import FingeringConfig
from scripts.fingering.positions import POSITIONS
from scripts.fingering.cell_bridge import root_pc
from scripts.pentatonics.fingering_rank import PENTA_POSITION_SLACK
from scripts.triad_pairs.favorites import (
    favorite_line, make_favorite, render_favorite, run_config, transpose_favorite,
)
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


def _pair_in(p: TriadPairIn) -> TriadPair:
    return _pair(p.roots[0], p.qualities[0], p.roots[1], p.qualities[1])


def _check_key(key: str) -> None:
    try:
        root_pc(key)
    except (KeyError, ValueError, IndexError):
        raise HTTPException(422, f"unknown key {key!r}")


def _check_position(position) -> None:
    if position is not None and position not in POSITIONS:
        raise HTTPException(422, f"unknown position {position!r}")


@router.post("/triads/favorites/make")
def favorite_make(request: Request, body: FavoriteMakeRequest):
    payload = body.model_dump(mode="json")

    def compute():
        _check_key(body.key)
        _check_position(body.position)
        fav = make_favorite([p.model_dump() for p in body.placed], _pair_in(body.pair), body.key,
                            body.position, body.exercise, body.params, body.start, body.title,
                            body.cost)
        return {"favorite": fav}

    return respond(request, "triads/favorites/make", payload, compute)


@router.post("/triads/favorites/render")
def favorite_render(request: Request, body: FavoriteRenderRequest):
    payload = body.model_dump(mode="json")

    def compute():
        fav = body.favorite.model_dump()
        _check_key(body.key)
        _check_key(fav["key"])
        _check_position(fav["position"])
        _pair_in(body.favorite.pair)
        cfg = run_config(body.config.apply() if body.config else FingeringConfig())
        as_saved = body.key == fav["key"]
        out = {"key": body.key, "as_saved": as_saved, "position": fav["position"],
               "fret_delta": 0, "in_box": None, "fingering": None, "message": None}
        if as_saved:
            p, line, pins = favorite_line(fav)
        else:
            t = transpose_favorite(fav, body.key, cfg.max_fret, PENTA_POSITION_SLACK, cfg)
            if t is None:
                out["pair_title"] = None
                out["message"] = f"No octave of this layout stays on the neck in {body.key}."
                return out
            p, line, pins = t["pair"], t["line"], t["pins"]
            out["fret_delta"] = t["fret_delta"]
            out["in_box"] = t["in_box"] if fav["position"] else None
        out["pair_title"] = p.title
        res = render_favorite(line, pins, body.key, cfg)
        if res is None:
            out["message"] = "The engine could not re-finger this layout here."
        else:
            out["fingering"] = fingering_json(res, body.key, "favorite", body.with_reports)
        return out

    return respond(request, "triads/favorites/render", payload, compute)
