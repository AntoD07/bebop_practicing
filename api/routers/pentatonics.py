"""Pentatonic exercises: pattern library, line generators and the rankers.

"Rank ALL formulas" is not an endpoint: the frontend generates each formula's
line and ranks it with one ``/rank`` call per line.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.budget import make_budget
from api.cache import respond
from api.schemas import PentaGenerateRequest, RankRequest
from api.serialize import config_diff, rows_json
from scripts.fingering.config import FingeringConfig
from scripts.fingering.pitch import parse_pitch
from scripts.fingering.positions import POSITIONS
from scripts.pentatonics.bergonzi import apply_pattern, load_patterns, shift_pattern
from scripts.pentatonics.fingering_rank import (
    PENTA_POSITION_SLACK, enumerate_position_fingerings, rank_line_fingerings,
    rank_pentatonic_fingerings,
)
from scripts.pentatonics.pentatonics import (
    DIRECTIONS, PENTATONIC_NAMES, PENTATONICS, SHIFT_CHOICES, chromatic_run,
    notes_pattern_run, scale_run, shift_offsets, shift_run,
)

router = APIRouter()

EXERCISES = [
    {"id": "scale", "label": "Scale run"},
    {"id": "pattern", "label": "x-notes pattern"},
    {"id": "chromatic", "label": "Chromatic passing tones"},
    {"id": "bergonzi", "label": "Bergonzi patterns"},
    {"id": "shifting", "label": "Shifting"},
]


@router.get("/pentatonics/patterns")
def patterns(request: Request):
    def compute():
        return {
            "patterns": load_patterns(),
            "pentatonics": {k: {"intervals": v["intervals"], "degrees": v["degrees"]}
                            for k, v in PENTATONICS.items()},
            "names": PENTATONIC_NAMES,
            "directions": DIRECTIONS,
            "shift_choices": SHIFT_CHOICES,
            "exercises": EXERCISES,
            "position_slack": PENTA_POSITION_SLACK,
        }
    return respond(request, "pentatonics/patterns", {}, compute)


def _lines_by_start(body: PentaGenerateRequest):
    if body.penta not in PENTATONICS:
        raise HTTPException(422, f"unknown pentatonic {body.penta!r}")
    degrees = PENTATONICS[body.penta]["degrees"]
    if body.start_degs:
        bad = [i for i in body.start_degs if not 0 <= i < len(degrees)]
        if bad:
            raise HTTPException(422, f"start_degs out of range: {bad}")
        starts = [(degrees[i], i) for i in body.start_degs]
    else:
        starts = [(lbl, i) for i, lbl in enumerate(degrees)]
    key, penta, lo, n_oct, d = body.key, body.penta, body.low_octave, body.n_octaves, body.direction
    starts_note = "" if body.start_degs else " · all starts"
    if body.exercise == "scale":
        lbs = {lbl: scale_run(key, penta, lo, n_oct, d, start_deg=sd) for lbl, sd in starts}
        return lbs, f"{key} {penta} pentatonic — {d} ({n_oct} oct){starts_note}", None
    if body.exercise == "pattern":
        lbs = {lbl: notes_pattern_run(key, penta, lo, n_oct, body.x, d, start_deg=sd)
               for lbl, sd in starts}
        return lbs, f"{key} {penta} — {body.x}-notes pattern, {d} ({n_oct} oct){starts_note}", body.x
    if body.exercise == "chromatic":
        lbs = {lbl: chromatic_run(key, penta, lo, n_oct, d, body.add_b6, start_deg=sd)
               for lbl, sd in starts}
        return lbs, (f"{key} {penta} + chromatics — {d}" + (" +b6" if body.add_b6 else "")
                     + starts_note), None
    if body.exercise == "shifting":
        name = body.interval_name or SHIFT_CHOICES[2]
        if name not in SHIFT_CHOICES:
            raise HTTPException(422, f"unknown shift {name!r}")
        offs = shift_offsets(name, int(body.n_shifts) + 1)
        lbs = {lbl: shift_run(key, penta, offs, d, lo, octaves_per_block=1, start_deg=sd)
               for lbl, sd in starts}
        return lbs, f"{key} {penta} — {name.lower()} ×{int(body.n_shifts)}{starts_note}", None
    # bergonzi
    pats = load_patterns()
    names = [p["name"] for p in pats]
    if body.formula not in names:
        raise HTTPException(422, f"unknown formula {body.formula!r}")
    pat = pats[names.index(body.formula)]
    use_shift = bool(body.shift_choice) and body.shift_choice != "none"
    if use_shift:
        if body.shift_choice not in SHIFT_CHOICES:
            raise HTTPException(422, f"unknown shift {body.shift_choice!r}")
        offs = shift_offsets(body.shift_choice, int(body.n_shifts) + 1)
        ln = shift_pattern(key, penta, pat, offs, lo, groups_per_shift=int(body.groups_per_shift))
        note = (f", {int(body.groups_per_shift)} grp/key, shift by {body.shift_choice.lower()} "
                f"×{int(body.n_shifts)}")
    else:
        ln = apply_pattern(key, penta, pat, lo, n_oct)
        note = ""
    return {body.formula: ln}, f"{key} {penta} — {body.formula}{note}", len(pat["offsets"])


@router.post("/pentatonics/generate")
def generate(request: Request, body: PentaGenerateRequest):
    payload = body.model_dump(mode="json")

    def compute():
        lbs, title, group = _lines_by_start(body)
        return {"title": title, "group": group, "exercise": body.exercise,
                "start_labels": list(lbs), "lines_by_start": lbs}

    return respond(request, "pentatonics/generate", payload, compute)


def _line(body: RankRequest):
    out = []
    for i, n in enumerate(body.line):
        try:
            midi = parse_pitch(n.pitch)
        except ValueError as e:
            raise HTTPException(422, f"note {i}: {e}")
        d = {"pitch": midi, "role": n.role or n.degree, "degree": n.degree}
        if n.cell is not None:
            d["cell"] = n.cell
        out.append(d)
    return out


@router.post("/pentatonics/rank")
def rank(request: Request, body: RankRequest):
    payload = body.model_dump(mode="json")
    if body.position is not None and body.position not in POSITIONS:
        raise HTTPException(422, f"unknown position {body.position!r}")

    def compute():
        line = _line(body)
        cfg = body.config.apply() if body.config else FingeringConfig()
        budget = make_budget(body.max_layouts)
        if body.position:
            rows = enumerate_position_fingerings(line, body.key, body.position, cfg,
                                                 group=body.group, max_layouts=budget.max_layouts)
        elif body.generic:
            rows = rank_line_fingerings(line, body.key, cfg, group=body.group)
        else:
            rows = rank_pentatonic_fingerings(line, body.key, cfg, root=body.root or body.key,
                                              penta=body.penta, group=body.group)
        for r in rows:
            r["start"] = body.start_label
        return {"key": body.key, "position": body.position, "generic": body.generic,
                "n_total": len(line), "rows": rows_json(rows, body.key), "config": config_diff(cfg)}

    return respond(request, "pentatonics/rank", payload, compute)
