"""Engine objects -> JSON dicts (the ONE place the wire shapes are defined).

FingeringJSON
    layout        "3/14 3/12 4/14"      (= the picks' layout signature)
    encoding      "3/14D 3/12U 4/14D"   (= the legacy log's Tab column)
    cost, n_up, n_flags, fret_lo, fret_hi
    positions[]   every named position the layout fits (w.r.t. ``key``)
    where         "<position> · frets a–b" (or just the span)
    placed[]      PlacedJSON per note (pitch, timing, string/fret/finger/stroke…)
    chords[]      the context's chord lane, beats_per_bar, density
    contributions, flags, drop_sites, warnings, report (format_report text)
    mode          "enumerated" | "optimum" | "free"
    alternate     a second voicing (Free only) or null
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence

from scripts.domain.budget import layout_sig
from scripts.domain.cells import CellView
from scripts.fingering.config import FingeringConfig
from scripts.fingering.costs import PlacedNote
from scripts.fingering.optimizer import FingeringResult, Voicing
from scripts.fingering.positions import classify_position, classify_positions
from scripts.fingering.render import format_report


def placed_json(i: int, p: PlacedNote) -> Dict[str, Any]:
    n = p.note
    return {
        "i": i, "midi": n.midi, "name": n.name, "onset": n.onset, "beat": n.beat,
        "string": p.string, "fret": p.fret, "finger": p.finger, "stretch": bool(p.is_stretch),
        "stroke": p.stroke, "run_len": p.run_len, "rest": bool(p.is_rest_stroke),
        "role": n.role, "degree": n.degree, "cell": n.cell,
        "phrase_start": bool(n.phrase_start), "grace": bool(n.is_grace),
    }


def encoding_of(placed: Sequence[PlacedNote]) -> str:
    return " ".join(f"{p.string}/{p.fret}{p.stroke}" for p in placed)


def voicing_json(v: Voicing, key=None) -> Dict[str, Any]:
    placed = v.placed
    frets = [p.fret for p in placed if p.fret > 0]
    return {
        "layout": " ".join(f"{p.string}/{p.fret}" for p in placed),
        "encoding": encoding_of(placed),
        "cost": v.total_cost,
        "n_up": sum(1 for p in placed if p.stroke == "U"),
        "n_flags": len(v.flags),
        "fret_lo": min(frets) if frets else 0,
        "fret_hi": max(frets) if frets else 0,
        "positions": classify_positions(placed, key) if key is not None else [],
        "where": (classify_position(placed, key) if key is not None
                  else (f"frets {min(frets)}–{max(frets)}" if frets else "open strings")),
        "placed": [placed_json(i, p) for i, p in enumerate(placed)],
        "contributions": [[tag, round(amt, 4)] for tag, amt in v.contributions],
        "flags": list(v.flags),
        "drop_sites": [asdict(d) for d in v.drop_sites],
    }


def fingering_json(result: FingeringResult, key=None, mode: str = "enumerated",
                   with_report: bool = True) -> Dict[str, Any]:
    out = voicing_json(result.best, key)
    out.update({
        "mode": mode,
        "warnings": list(result.warnings),
        "beats_per_bar": result.context.get("beats_per_bar", result.config.beats_per_bar),
        "density": result.context.get("density", "quarter"),
        "chords": list(result.context.get("chords") or []),
        "key": result.context.get("key"),
        "report": format_report(result) if with_report else None,
        "alternate": voicing_json(result.alternate, key) if result.alternate is not None else None,
    })
    return out


def config_diff(cfg: FingeringConfig) -> Dict[str, Any]:
    """The config fields that differ from the engine defaults."""
    base = FingeringConfig()
    out = {}
    for k, v in asdict(cfg).items():
        if getattr(base, k) != v:
            out[k] = v
    return out


def cell_view_json(v: CellView) -> Dict[str, Any]:
    return v.to_dict()


def sampled_line_json(sl, key=None) -> Dict[str, Any]:
    from scripts.domain.notes import harmony_caption

    return {
        "cells": [cell_view_json(c) for c in sl.cells],
        "structure": list(sl.structure),
        "reading_modes": list(sl.reading_modes),
        "movement_modes": list(sl.movement_modes),
        "line_type": sl.line_type,
        "signature": list(sl.signature),
        "harmony_caption": harmony_caption(key, sl.structure) if key is not None else None,
    }


def rows_json(rows: List[dict], key=None) -> List[Dict[str, Any]]:
    """Pentatonic/triad ranking rows (``fingering_rank`` dicts) to JSON."""
    out = []
    for r in rows:
        res = r.get("result")
        out.append({
            "position": r.get("position"), "cost": r.get("cost"), "cpn": r.get("cpn"),
            "covered": r.get("covered"), "where": r.get("where"),
            "layout": r.get("layout"), "start": r.get("start"),
            "fingering": fingering_json(res, key, "ranked") if res is not None else None,
        })
    return out
