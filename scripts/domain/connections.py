"""Pivot connections (page 1): pair two chords' cells on a pivot note and
finger each pair as ONE merged line.

The pivot note is SHARED — the last note of the first cell IS the first note
of the second (len1 + len2 - 1 notes) — and the whole line goes through a
single DP, so the cost is the cost of the entire connection. Cell 2's root is
derived from the pivot pitch, so the join is seamless.

"Enforce the position" makes a named position a HARD box anchored on today's
key (the I of the ii-V-I, or the chord itself for a single-chord pair) or on
chord 1 / chord 2; EVERY fingering of the connection inside the shape is
listed — both octaves of the box, every register, every string/fret layout
(roots pinned to the shape's root strings) — cheapest first.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from scripts.domain.budget import (
    Chunk, LayoutBudget, dedupe_sorted, enumerate_chunks, layout_sig, plan_chunk,
)
from scripts.domain.cells import CellView, connection_steps, mode_views, pivot_steps, views
from scripts.domain.catalog import cells as catalog_cells
from scripts.domain.notes import DEFAULT_PIVOT, allowed_movements, sort_degrees
from scripts.fingering.cell_bridge import (
    build_connection_line, cell_beat, cell_context, chord_symbol_for_mode,
    chord_symbol_for_root_pc, is_single_chord, root_offset, root_pc, timed_cell_line,
)
from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import FingeringResult, optimize_fingering
from scripts.fingering.positions import POSITIONS, POSITION_SLACK, position_boxes

FREE = "Free (best on the neck)"
REGISTER_OFFSETS = (-24, -12, 0, 12, 24)
ANCHORS = ("key", "chord1", "chord2")

_TONIC_READING = {"MajorResolutions": "MajorTonic", "MinorResolutions": "MinorTonic",
                  "Myxolidian": "MajorTonic"}


def reading_mode(chord: str, translated: bool) -> str:
    """Mode the fingering bridge reads a cell's degrees with.

    The "Translate Dominant to Minor/Major-I" checkboxes rewrite resolution /
    Myxolidian degrees to the I-chord representation; those must be read with
    the tonic modes, else the derived root (and the chord label) are wrong.
    """
    if not translated:
        return chord
    return _TONIC_READING.get(chord, chord)


def is_myxo_to_dorian(chord1: str, chord2: str) -> bool:
    """Dorian/Minor -> Myxolidian: re-spell the Myxolidian cells from the ii
    root so both sides share one representation and the pivots line up."""
    return chord1 in ("Dorian", "Minor") and chord2 == "Myxolidian"


def pair_key(end_name: str, start_name: str) -> str:
    return f"{end_name} → {start_name}"


def pick_key(chord1: str, chord2: str, raw_pivot: str, myxo_to_dorian: bool,
             position: Optional[str], anchor: str, single_chord: bool) -> str:
    """The ``connection_picks.json`` key, byte-for-byte as page 1 built it:
    ``chord1|chord2|[ii:]rawPivot|position[|anchor:key|anchor:2nd]``."""
    pos = position if position in POSITIONS else FREE
    parts = [chord1, chord2, ("ii:" if myxo_to_dorian else "") + str(raw_pivot), pos]
    if anchor == "key" and not single_chord:
        parts.append("anchor:key")
    elif anchor == "chord2":
        parts.append("anchor:2nd")
    return "|".join(parts)


# --------------------------------------------------------------------------- #
# Pairing
# --------------------------------------------------------------------------- #
def side_views(chord: str, bonus: bool, dom_to_minor: bool, myxo_to_dorian: bool
               ) -> Tuple[List[CellView], List[CellView]]:
    """``(pivot_views, fingering_views)`` of one side: the pivot
    representation the pickers compare, and the degrees the pair is fingered
    with (page 1 translated the raw frames AFTER filtering on the raw pivot)."""
    raw = catalog_cells(chord, bonus)
    pv = views(raw, pivot_steps(chord, dom_to_minor=dom_to_minor))
    fv = views(raw, connection_steps(chord, dom_to_minor=dom_to_minor,
                                     myxo_to_dorian=myxo_to_dorian))
    if myxo_to_dorian and chord == "Myxolidian":
        # Page 1: the ii-spelled Start Notes ARE the pivot names (identity map).
        pv = fv
    return pv, fv


def pivot_options(chord1: str, chord2: str, bonus: bool = False,
                  dom_to_minor1: bool = False, dom_to_minor2: bool = False) -> dict:
    """Pivot notes common to both sides, in degree order, with the raw
    spelling each side filters on (``raw2`` is what the pick key uses)."""
    m2d = is_myxo_to_dorian(chord1, chord2)
    pv1, _ = side_views(chord1, bonus, dom_to_minor1, False)
    pv2, _ = side_views(chord2, bonus, dom_to_minor2 and not m2d, m2d)
    ends = {}
    for v in pv1:
        ends.setdefault(v.end, v.cell.end)
    starts = {}
    for v in pv2:
        starts.setdefault(v.start, v.start if m2d else v.cell.start)
    common = sort_degrees(set(ends) & set(starts))
    pivots = [{"value": p, "raw1": ends[p], "raw2": starts[p]} for p in common]
    default = DEFAULT_PIVOT if DEFAULT_PIVOT in common else (common[0] if common else None)
    return {"pivots": pivots, "default": default, "myxo_to_dorian": m2d}


def pairs_for_pivot(chord1: str, chord2: str, pivot: Optional[str] = None,
                    bonus: bool = False, dom_to_minor1: bool = False,
                    dom_to_minor2: bool = False, movement: Optional[str] = None,
                    key: Optional[str] = None) -> dict:
    """Everything page 1 derives before fingering: the pivot list, the ending
    cells of chord 1 and starting cells of chord 2 on the pivot (movement-
    filtered, in the FINGERING representation), the pairs, the reading modes
    and the harmony labels."""
    m2d = is_myxo_to_dorian(chord1, chord2)
    dtm2 = dom_to_minor2 and not m2d
    opts = pivot_options(chord1, chord2, bonus, dom_to_minor1, dtm2)
    pivot = pivot if pivot is not None else opts["default"]
    mv = allowed_movements(movement)
    pv1, fv1 = side_views(chord1, bonus, dom_to_minor1, False)
    pv2, fv2 = side_views(chord2, bonus, dtm2, m2d)
    ending = [f for p, f in zip(pv1, fv1)
              if p.end == pivot and (str(p.movement) in mv)]
    starting = [f for p, f in zip(pv2, fv2)
                if p.start == pivot and (str(p.movement) in mv)]
    read1 = reading_mode(chord1, dom_to_minor1)
    read2 = "Dorian" if m2d else reading_mode(chord2, dtm2)
    single = is_single_chord([chord1, chord2])
    raw2 = next((p["raw2"] for p in opts["pivots"] if p["value"] == pivot), pivot)
    out = {
        "chord1": chord1, "chord2": chord2, "pivot": pivot, "raw_pivot": raw2,
        "pivots": opts["pivots"], "myxo_to_dorian": m2d, "single_chord": single,
        "read1": read1, "read2": read2, "dom_to_minor2_effective": dtm2,
        "ending": ending, "starting": starting,
        "pairs": [(e, s) for e in ending for s in starting],
    }
    if key is not None:
        out["sym1"] = chord_symbol_for_mode(key, read1, single)
    return out


# --------------------------------------------------------------------------- #
# Fingering ONE pair
# --------------------------------------------------------------------------- #
def _anchor(anchor: str, key, root1: int, chord2_root: int, sym1: str, sym2: str):
    if anchor == "chord2":
        return chord2_root, sym2
    if anchor == "chord1":
        return root1, sym1
    return root_pc(key), f"{key} (today's key)"


def score_connection_pair(key, read1: str, read2: str, cell1: dict, cell2: dict,
                          position: Optional[str] = None, anchor: str = "key",
                          myxo_to_dorian: bool = False, single_chord: bool = False,
                          config: Optional[FingeringConfig] = None,
                          budget: Optional[LayoutBudget] = None,
                          box: Optional[int] = None) -> dict:
    """Finger one ending -> starting pair (the body of page 1's
    ``score_connections`` for a single pair).

    ``cell1``/``cell2``: ``{"name", "degrees", "movement"}`` with the degrees
    in the representation the pair is fingered with. ``read1``/``read2``: the
    modes those degrees are READ with. ``position``: a named position (every
    in-box fingering, cheapest first) or None/Free (the single cheapest
    fingering anywhere). ``anchor``: "key" / "chord1" / "chord2". ``box``
    restricts the enumeration to one octave of the shape (0 = root fret,
    1 = twelve frets up) so a client can split a heavy pair in two.

    Returns a dict with ``fingerings`` (list of ``(FingeringResult, mode)``
    where mode is "enumerated" / "optimum" / "free"), ``truncated``,
    ``chunks`` (the planner's report), the pivot/anchor/chord labels, or
    ``error`` when the pair cannot be voiced.
    """
    cfg = config or FingeringConfig()
    d1, d2 = list(cell1["degrees"]), list(cell2["degrees"])
    sym1 = chord_symbol_for_mode(key, read1, single_chord)
    root1 = (root_pc(key) + root_offset(read1, single_chord)) % 12
    c1 = {"name": cell1["name"], "root": root1, "degrees": d1, "mode": read1,
          "movement": cell1.get("movement")}
    c2 = {"name": cell2["name"], "root": 0, "degrees": d2, "mode": read2,
          "movement": cell2.get("movement")}
    pivot_index = len(d1) - 1
    out = {
        "end": cell1["name"], "start": cell2["name"], "pivot_index": pivot_index,
        "pivot_label": f"{d1[-1]}={d2[0]}", "sym1": sym1, "root1": root1,
        "fingerings": [], "truncated": False, "chunks": [], "error": None,
        "position": position if position in POSITIONS else None, "anchor": anchor,
    }
    try:
        _, _, root2_pc = build_connection_line(c1, c2)
    except (ValueError, KeyError) as e:
        out["error"] = str(e)
        return out
    chord2_root = (root2_pc + 5) % 12 if myxo_to_dorian else root2_pc
    sym2 = (chord_symbol_for_root_pc(chord2_root, "Myxolidian") if myxo_to_dorian
            else chord_symbol_for_root_pc(root2_pc, read2))
    anchor_pc, anchor_sym = _anchor(anchor, key, root1, chord2_root, sym1, sym2)
    out.update(sym2=sym2, root2=root2_pc, chord2_root=chord2_root,
               anchor_pc=anchor_pc, anchor_sym=anchor_sym)

    def ctx_for(pidx: int) -> dict:
        return cell_context({"key": key, "chords": [
            {"start_beat": 0, "symbol": sym1},
            {"start_beat": cell_beat(pidx), "symbol": sym2}]})

    if position in POSITIONS:
        chunks: List[Chunk] = []
        for bi, (box_cfg, box_root_midi) in enumerate(position_boxes(position, anchor_pc, cfg)):
            if box is not None and bi != box:
                continue
            # The box is a HARD filter (POSITION_SLACK = 0 — validated).
            box_cfg = box_cfg.with_overrides(window_overflow_frets=POSITION_SLACK)
            seen_lines = set()
            for off in REGISTER_OFFSETS:
                try:
                    line, pidx, _ = build_connection_line(c1, c2, base_midi=box_root_midi + off)
                except (ValueError, KeyError):
                    continue
                pitches = tuple(n["pitch"] for n in line)
                if pitches in seen_lines:
                    continue
                seen_lines.add(pitches)
                chunks.append(plan_chunk(bi, off, timed_cell_line(line), ctx_for(pidx),
                                         box_cfg, pivot_index=pidx))
        results, truncated, reports = enumerate_chunks(chunks, budget)
        results = dedupe_sorted(results)
        modes = {id(ch): rep["mode"] for ch, rep in zip(chunks, reports)}
        out["fingerings"] = [(r, modes.get(id(ch), "enumerated")) for r, ch in results]
        out["truncated"] = truncated
        out["chunks"] = reports
        if not results:
            out["error"] = "does not fit this position"
        return out

    try:
        line, pidx, _ = build_connection_line(c1, c2)
        result = optimize_fingering(timed_cell_line(line), ctx_for(pidx), cfg)
    except (ValueError, KeyError) as e:
        out["error"] = str(e)
        return out
    out["fingerings"] = [(result, "free")]
    out["chunks"] = [{"box": None, "offset": 0, "layouts": 1, "mode": "free"}]
    return out
