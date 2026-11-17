"""Favourite fingerings — keep a chosen layout for later study, in any key.

A favourite is a fingering the player picked from a ranking: the exact
string/fret layout of one exercise line, with the context that produced it
(pair, key, position, exercise, parameters, starting note). This module is
PURE: it builds the record and replays it. Persistence is the app's business
(the ``fingering_favorites`` table, written by the Next.js route handlers).

Mimicking in another key
------------------------
A named position is a MOVABLE hand box anchored on the key root, so the same
fingering exists in every key: the whole layout slides along the neck by the
difference between the two keys' root frets (plus or minus an octave when that
keeps it on the fingerboard), and the pair's triads move with the key. The
line keeps its shape — pitches shift by exactly the fret delta — only the
labels change (``Eb:3`` becomes ``C:3``). :func:`transpose_favorite` picks the
octave whose frets fall inside the position's box for the new key when one
does, and otherwise the nearest one that stays on the neck. The picking is
re-derived by the engine from the pinned layout, so the mimicked tab shows a
real fingering at its real cost.

Run-oriented weights
--------------------
:func:`run_config` is the triad-pairs page's reading of the cost model: the
downbeat D-D surcharge is a cell (eighth-note) rule that, at run pacing (every
note a beat), only punished 3-notes-per-string shapes whose string entries
fall off the downbeats — it is set equal to the plain same-string D-D penalty.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from scripts.fingering.cell_bridge import root_pc
from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering
from scripts.fingering.positions import position_boxes
from scripts.triad_pairs.triads import ROOTS, Triad, TriadPair

PAGE_TRIAD_PAIRS = "triad_pairs"


def run_config(cfg: Optional[FingeringConfig] = None) -> FingeringConfig:
    """``cfg`` with the downbeat D-D surcharge neutralised (run pacing)."""
    cfg = cfg or FingeringConfig()
    return cfg.with_overrides(downbeat_dd_penalty=cfg.same_string_dd_penalty)


def layout_signature(layout: Sequence[Sequence[int]]) -> str:
    return " ".join(f"{s}/{f}" for s, f in layout)


def pair_dict(pair: TriadPair) -> dict:
    return {"roots": [t.root for t in pair.triads],
            "qualities": [t.quality for t in pair.triads]}


def pair_from_dict(d: dict) -> TriadPair:
    return TriadPair(Triad(d["roots"][0], d["qualities"][0]),
                     Triad(d["roots"][1], d["qualities"][1]))


def make_favorite(placed: Sequence[dict], pair: TriadPair, key: str, position: Optional[str],
                  exercise: str, params: dict, start: str, title: str,
                  cost: Optional[float], page: str = PAGE_TRIAD_PAIRS) -> dict:
    """Build the record for a rendered fingering.

    ``placed`` is the fingering's notes in order, each ``{"midi", "string",
    "fret", "degree", "cell"}`` (the wire ``placed[]``). Each note keeps its
    pitch, its owning triad index and chord degree (so the label can be rebuilt
    in another key) and its grouping tag; triad-group tags (``C↑``) are stored
    as the arrow alone and rebuilt from the symbol. The caller adds the id and
    the timestamp.
    """
    layout = [[int(p["string"]), int(p["fret"])] for p in placed]
    syms = [t.symbol for t in pair.triads]
    line = []
    for p in placed:
        label = p.get("degree") or ""
        k, deg = None, label
        if ":" in label:
            sym, deg = label.rsplit(":", 1)
            k = syms.index(sym) if sym in syms else None
        cell = p.get("cell")
        arrow = None
        if cell and cell[-1] in "↑↓" and cell[:-1] in syms:
            arrow, k_cell = cell[-1], syms.index(cell[:-1])
            k = k_cell if k is None else k
        line.append({"pitch": int(p["midi"]), "k": k, "deg": deg,
                     "cell": None if arrow else cell, "arrow": arrow})
    return {
        "page": page, "title": title, "exercise": exercise, "params": params,
        "key": key, "position": position, "pair": pair_dict(pair),
        "start": start, "layout": layout, "line": line,
        "cost": None if cost is None else round(float(cost), 3),
    }


# --------------------------------------------------------------------------- #
# Rebuilding lines and mimicking in another key
# --------------------------------------------------------------------------- #
def _relabel(line: List[dict], pair: TriadPair, semitones: int = 0) -> List[dict]:
    """Engine line for a stored ``line``, shifted by ``semitones`` and labelled
    with ``pair``'s symbols."""
    out = []
    for n in line:
        k = n.get("k")
        if k is not None:
            sym = pair.triads[k].symbol
            label = f"{sym}:{n['deg']}"
            cell = f"{sym}{n['arrow']}" if n.get("arrow") else n.get("cell")
        else:
            label, cell = n.get("deg", ""), n.get("cell")
        d = {"pitch": n["pitch"] + semitones, "role": label, "degree": label}
        if cell:
            d["cell"] = cell
        out.append(d)
    return out


def transpose_pair(pair: TriadPair, semitones: int) -> TriadPair:
    return TriadPair(*(Triad(ROOTS[(t.root_pc + semitones) % 12], t.quality)
                       for t in pair.triads))


def _frets_in_boxes(layout, boxes, slack: int) -> bool:
    return all(any(lo - slack <= f <= hi + slack and s in strings
                   for lo, hi, strings in boxes) for s, f in layout)


def transpose_favorite(fav: dict, new_key: str, max_fret: int = 15, slack: int = 1,
                       base_cfg: Optional[FingeringConfig] = None) -> Optional[dict]:
    """Mimic a favourite in ``new_key``: the same layout slid by the keys' fret
    difference (±12 when needed), the pair's triads moved with the key.

    Returns ``{"pair", "line", "pins", "fret_delta", "in_box", "semitones"}``
    or None when no octave of the shift keeps every fret on the neck. When the
    favourite has a position, the octave whose frets sit inside that position's
    box for the new key (±``slack``) wins; otherwise the smallest shift wins.
    """
    pair = pair_from_dict(fav["pair"])
    delta = (root_pc(new_key) - root_pc(fav["key"])) % 12
    layout = [tuple(x) for x in fav["layout"]]
    boxes = []
    if fav.get("position"):
        for cfg, _r in position_boxes(fav["position"], new_key, base_cfg):
            lo, hi = cfg.fret_window
            boxes.append((lo, hi, tuple(cfg.string_range)))
    cands = []
    for d in (delta, delta - 12, delta + 12):
        if d == 0 and fav["key"] != new_key and delta != 0:
            continue
        shifted = [(s, f + d) for s, f in layout]
        if not all(1 <= f <= max_fret for _s, f in shifted):
            continue
        in_box = bool(boxes) and _frets_in_boxes(shifted, boxes, slack)
        cands.append((0 if in_box else 1, abs(d), d, shifted, in_box))
    if not cands:
        return None
    cands.sort()
    _, _, d, shifted, in_box = cands[0]
    new_pair = transpose_pair(pair, d)
    line = _relabel(fav["line"], new_pair, d)
    pins = {n["pitch"]: pl for n, pl in zip(line, shifted)}
    return {"pair": new_pair, "line": line, "pins": pins, "fret_delta": d,
            "in_box": in_box, "semitones": d}


def favorite_line(fav: dict) -> Tuple[TriadPair, List[dict], Dict[int, Tuple[int, int]]]:
    """The favourite as saved: ``(pair, engine line, pins)``."""
    pair = pair_from_dict(fav["pair"])
    line = _relabel(fav["line"], pair, 0)
    pins = {n["pitch"]: tuple(pl) for n, pl in zip(line, fav["layout"])}
    return pair, line, pins


def render_favorite(line: List[dict], pins: Dict[int, Tuple[int, int]], key: str,
                    base_cfg: Optional[FingeringConfig] = None):
    """Re-derive picking and fingers for a pinned layout (a render-ready
    ``FingeringResult``), or None when the engine rejects the pins."""
    cfg = (base_cfg or FingeringConfig()).with_overrides(
        fret_window=None, string_fret_windows=None, root_pin=None,
        string_range=(1, 2, 3, 4, 5, 6))
    try:
        return optimize_fingering(line, {"key": key}, cfg, pinned=pins)
    except (ValueError, KeyError):
        return None
