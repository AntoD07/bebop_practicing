"""Pivot-chained lines -> fingerings (page 2).

Every fingering of a line inside a named position (cheapest first), or the
single cheapest fingering anywhere when the position is Free. Same logic as
the connections: the position is a HARD box anchored on ``pos_key`` (today's
key, or its V); both octaves of the box and every register of the line are
enumerated, layouts deduped, and only fingerings labelled with the position
are kept.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from scripts.domain.budget import (
    Chunk, LayoutBudget, dedupe_sorted, enumerate_chunks, layout_sig, plan_chunk,
)
from scripts.domain.catalog import find_cell
from scripts.fingering.cell_bridge import (
    build_chain_line, cell_beat, cell_context, chord_symbol_for_mode,
    chord_symbol_for_root_pc, is_single_chord, root_offset, root_pc, timed_cell_line,
)
from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import FingeringResult, optimize_fingering
from scripts.fingering.positions import (
    POSITIONS, POSITION_SLACK, classify_positions, position_boxes,
)

FREE_OFFSETS = (0, 12, -12, 24)
BOX_OFFSETS = (-24, -12, 0, 12, 24)


def cell_movement(mode: str, name: str) -> Optional[str]:
    """Movement (A/D/N) of a named cell, from the catalog (first match)."""
    c = find_cell(mode, name)
    return c.movement if c is not None else None


def line_cells(key, names: Sequence[str], degrees: Sequence[Sequence[str]],
               reading_modes: Sequence[str], movement_modes: Optional[Sequence[str]] = None,
               movements: Optional[Sequence[Optional[str]]] = None) -> List[dict]:
    """Bridge cell dicts for a chained line: the first cell's root comes from
    today's key (``cell_bridge.root_offset``), later roots are derived from
    the pivots inside the chain. ``movement_modes`` are the ORIGINAL CSV mode
    names when ``reading_modes`` carries translated reading modes (names
    collide across CSVs with different Movement)."""
    mv_modes = list(movement_modes) if movement_modes else list(reading_modes)
    single = is_single_chord(mv_modes)
    kpc = root_pc(key)
    out = []
    for i, (name, degs, mode) in enumerate(zip(names, degrees, reading_modes)):
        mv = movements[i] if movements and i < len(movements) and movements[i] is not None \
            else cell_movement(mv_modes[i], name)
        out.append({
            "name": name, "root": (kpc + root_offset(mode, single)) % 12,
            "degrees": [str(d).strip() for d in degs], "mode": mode, "movement": mv,
        })
    return out


def line_context(key, reading_modes: Sequence[str], movement_modes: Sequence[str],
                 roots: Sequence[int], pivots: Sequence[int]) -> dict:
    """Cell notes are eighths; each chord starts on its cell's pivot."""
    single = is_single_chord(list(movement_modes))
    chords = []
    for k in range(len(reading_modes)):
        if movement_modes[k] == "Myxolidian" and reading_modes[k] == "Dorian":
            # Translated Myxolidian cell: the derived root is the ii root;
            # the sounding chord is the dominant a 4th above it.
            sym = chord_symbol_for_root_pc((roots[k] + 5) % 12, "Myxolidian")
        elif k == 0:
            sym = chord_symbol_for_mode(key, reading_modes[0], single)
        else:
            sym = chord_symbol_for_root_pc(roots[k], reading_modes[k])
        start = 0 if k == 0 else cell_beat(pivots[k - 1])
        chords.append({"start_beat": start, "symbol": sym})
    return cell_context({"key": key, "chords": chords})


def line_fingerings(key, cells: List[dict], reading_modes: Sequence[str],
                    movement_modes: Optional[Sequence[str]] = None,
                    position: Optional[str] = None, pos_key=None,
                    config: Optional[FingeringConfig] = None,
                    budget: Optional[LayoutBudget] = None) -> dict:
    """``{"fingerings": [(FingeringResult, mode)], "truncated", "chunks",
    "pivots", "error"}`` — every fingering of the chained line inside
    ``position`` (cheapest first), or the single cheapest anywhere."""
    cfg = config or FingeringConfig()
    pk = pos_key if pos_key is not None else key
    mv_modes = list(movement_modes) if movement_modes else list(reading_modes)
    out = {"fingerings": [], "truncated": False, "chunks": [], "pivots": [], "error": None}

    if position not in POSITIONS:
        best = None
        for off in FREE_OFFSETS:
            try:
                line, pivots, roots = build_chain_line(cells, base_midi=60 + off)
                ctx = line_context(key, reading_modes, mv_modes, roots, pivots)
                cand = optimize_fingering(timed_cell_line(line), ctx, cfg)
            except (ValueError, KeyError):
                continue
            if best is None or cand.best.total_cost < best[0].best.total_cost:
                best = (cand, pivots)
        if best is None:
            out["error"] = "No playable fingering for this line."
            return out
        out["fingerings"] = [(best[0], "free")]
        out["pivots"] = list(best[1])
        out["chunks"] = [{"box": None, "offset": 0, "layouts": 1, "mode": "free"}]
        return out

    chunks: List[Chunk] = []
    for bi, (box_cfg, box_root_midi) in enumerate(position_boxes(position, pk, cfg)):
        box_cfg = box_cfg.with_overrides(window_overflow_frets=POSITION_SLACK)
        seen_lines = set()
        for off in BOX_OFFSETS:
            try:
                line, pivots, roots = build_chain_line(cells, base_midi=box_root_midi + off)
            except (ValueError, KeyError):
                continue
            pitches = tuple(n["pitch"] for n in line)
            if pitches in seen_lines:
                continue
            seen_lines.add(pitches)
            ctx = line_context(key, reading_modes, mv_modes, roots, pivots)
            chunks.append(plan_chunk(bi, off, timed_cell_line(line), ctx, box_cfg,
                                     pivots=list(pivots)))
    results, truncated, reports = enumerate_chunks(chunks, budget)
    results = [(r, ch) for r, ch in results
               if position in classify_positions(r.best.placed, pk)]
    results = dedupe_sorted(results)
    modes = {id(ch): rep["mode"] for ch, rep in zip(chunks, reports)}
    out["fingerings"] = [(r, modes.get(id(ch), "enumerated")) for r, ch in results]
    out["truncated"] = truncated
    out["chunks"] = reports
    out["pivots"] = list(results[0][1].extra.get("pivots", [])) if results else []
    if not results:
        out["error"] = "This line does not fit the position."
    return out
