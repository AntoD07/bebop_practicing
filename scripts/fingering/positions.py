"""The five named guitar positions used in the Cell Quiz.

Each position constrains the fingering search to a region of the neck anchored
on the chord root, so the same cell can be practised in every shape:

  1. CAGED E string root  — root on string 6, a compact box (E-shape).
  2. CAGED A string root  — root on string 5, a compact box (A-shape).
  3. Diagonal E string root — root on string 6, box opened upward (2npS climb).
  4. Diagonal A string root — root on string 5, box opened upward.
  5. More Horizontal, D string root — root on string 4, few strings, wide fret
     window so the line runs laterally along one/two strings.

A position sets (a) the register the cell is voiced in — the root's actual
location on the neck — and (b) a fret window + string set. The DP then finds the
layout. If a cell doesn't fit the strict box the window is widened once and
flagged; if it still can't be placed we say so rather than fake it.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from scripts.fingering.config import FingeringConfig, STANDARD_TUNING_MIDI
from scripts.fingering.optimizer import optimize_fingering, FingeringResult, cost_of
from scripts.fingering.cell_bridge import build_pitch_line, root_pc
from scripts.fingering.pitch import midi_to_name

POSITIONS: List[str] = [
    "CAGED E string root",
    "CAGED A string root",
    "Diagonal E string root",
    "Diagonal A string root",
    "More Horizontal, D string root",
]

POSITION_DESC = {
    "CAGED E string root": "Root on the low-E (6th) string; compact CAGED box.",
    "CAGED A string root": "Root on the A (5th) string; compact CAGED box.",
    "Diagonal E string root": "From the 6th-string root, climbing diagonally up the neck.",
    "Diagonal A string root": "From the 5th-string root, climbing diagonally up the neck.",
    "More Horizontal, D string root": "Root on the D (4th) string; lateral, few strings.",
}

# string, frets below/above the root fret, allowed strings, root strings
# (the CAGED root pattern the shape's key-roots must sit on), extra overrides.
_SPECS = {
    "CAGED E string root":       dict(string=6, below=1, above=4,
                                      strings=(1, 2, 3, 4, 5, 6), roots=(6, 4, 1)),
    "CAGED A string root":       dict(string=5, below=1, above=4,
                                      strings=(1, 2, 3, 4, 5, 6), roots=(5, 3)),
    "Diagonal E string root":    dict(string=6, below=1, above=7,
                                      strings=(1, 2, 3, 4, 5, 6), roots=(6, 4, 1)),
    "Diagonal A string root":    dict(string=5, below=1, above=7,
                                      strings=(1, 2, 3, 4, 5, 6), roots=(5, 3)),
    "More Horizontal, D string root": dict(
        string=4, below=3, above=9, strings=(2, 3, 4, 5), roots=(4, 2),
        overrides=dict(break_cost=0.5, reach_cost=0.2)),
}


def _root_fret(root_pc: int, string: int) -> int:
    """Lowest fret (0..11) where ``root_pc`` sits on ``string``.

    We take the natural low position for the key; the octave search then also
    offers the register an octave up, each with its own cost.
    """
    return (root_pc - STANDARD_TUNING_MIDI[string]) % 12


def _position(name: str, root_pc_val: int, base: FingeringConfig):
    """Return (config, root_midi) for a position.

    The config carries BOTH the key-anchored fret window and the root pin: key
    roots may only sit on the shape's root strings, so an "E string root"
    position can never render with its root on the A string.
    """
    spec = _SPECS[name]
    rf = _root_fret(root_pc_val, spec["string"])
    lo, hi = max(0, rf - spec["below"]), rf + spec["above"]
    root_midi = STANDARD_TUNING_MIDI[spec["string"]] + rf
    cfg = base.with_overrides(fret_window=(lo, hi), string_range=spec["strings"],
                              root_pin=(root_pc_val, spec["roots"]),
                              **spec.get("overrides", {}))
    return cfg, root_midi


_STRING_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


def _register_label(result: FingeringResult, root_pc_val: Optional[int] = None) -> str:
    """A short 'where on the neck' label: pitch span, fret span, root string."""
    placed = result.best.placed
    los = min(p.note.midi for p in placed)
    his = max(p.note.midi for p in placed)
    frets = [p.fret for p in placed if p.fret > 0]
    span = f"frets {min(frets)}–{max(frets)}" if frets else "open"
    label = f"{midi_to_name(los)}–{midi_to_name(his)} · {span}"
    if root_pc_val is not None:
        root_strings = sorted({p.string for p in placed
                               if p.note.midi % 12 == root_pc_val})
        if root_strings:
            label += " · root on " + "/".join(
                _STRING_ORDINAL[s] for s in root_strings) + " str"
    return label


def _feasible_octaves(cell: dict, context: dict, cfg: FingeringConfig,
                      root_midi: int) -> List[Tuple[FingeringResult, Optional[str]]]:
    """Every distinct octave in which ``cell`` fits this key-anchored box.

    The box (fret window + strings) is fixed by the KEY root, independent of the
    cell's starting note. We voice the cell at several octaves around the box and
    keep each that fits, deduped by placement — so the player can see (and pick)
    the low-E-string octave vs. a higher one, each with its own cost.
    """
    seen = set()
    out: List[Tuple[FingeringResult, Optional[str]]] = []
    for off in (-12, 0, 12, 24):
        line = build_pitch_line([cell], base_midi=root_midi + off,
                                first_note_target=root_midi + off)
        try:
            r = optimize_fingering(line, context, cfg)
        except ValueError:
            continue
        sig = tuple((p.string, p.fret, p.stroke) for p in r.best.placed)
        if sig in seen:
            continue
        seen.add(sig)
        out.append((r, None))
    if not out:
        # Nothing fit the strict box — widen once (still key-anchored) and retry.
        lo, hi = cfg.fret_window or (0, cfg.max_fret)
        wide = cfg.with_overrides(fret_window=(max(0, lo - 4), hi + 4))
        for off in (-12, 0, 12):
            line = build_pitch_line([cell], base_midi=root_midi + off,
                                    first_note_target=root_midi + off)
            try:
                r = optimize_fingering(line, context, wide)
            except ValueError:
                continue
            sig = tuple((p.string, p.fret, p.stroke) for p in r.best.placed)
            if sig in seen:
                continue
            seen.add(sig)
            out.append((r, "box widened to fit the cell"))
    return out


def position_config_for_key(name: str, key, base: Optional[FingeringConfig] = None):
    """Public: (config, root_midi) that pins a named position for a KEY.

    The config carries the key-anchored fret window, the shape's string set and
    the root pin; ``root_midi`` is the register anchor (the key root's location
    on the shape's root string) to voice lines around.
    """
    base = base or FingeringConfig()
    return _position(name, root_pc(key), base)


def classify_position(placed, key) -> str:
    """Name the position a free fingering falls in, w.r.t. the KEY.

    Checks each named position's key-anchored box (both octaves of the root
    fret) and its root-string pattern; returns the first matching position name
    plus the fret span, or just the span when no shape matches.
    """
    rpc = root_pc(key)
    frets = [p.fret for p in placed if p.fret > 0]
    if not frets:
        return "open strings"
    lo, hi = min(frets), max(frets)
    span = f"frets {lo}–{hi}"
    for name in POSITIONS:
        spec = _SPECS[name]
        if not all(p.string in spec["strings"] for p in placed):
            continue
        rf0 = _root_fret(rpc, spec["string"])
        for rf in (rf0, rf0 + 12):
            wlo, whi = max(0, rf - spec["below"]), rf + spec["above"]
            if lo >= wlo and hi <= whi and all(
                p.string in spec["roots"] for p in placed
                if p.note.midi % 12 == rpc
            ):
                return f"{name} · {span}"
    return span


def optimize_all_positions(cell: dict, context: dict,
                           base: Optional[FingeringConfig] = None) -> List[dict]:
    """Finger ``cell`` in each of the five positions, ranked by cost (decreasing).

    ``cell`` is a bridge dict ``{"name","root","degrees","mode","movement"}`` —
    ``root`` is the KEY (positions are defined relative to the key, not the cell's
    starting note). Returns, per position:

        {"name", "best_cost", "octaves": [{"result","cost","register","note"}, ...]}

    where ``octaves`` lists every register the cell fits in that box, cheapest
    first, and ``cost`` is scored under the shared ``base`` weights so positions
    (some solved with relaxed configs) stay comparable. Positions are sorted by
    ``best_cost`` descending; unplayable ones sink to the bottom.
    """
    base = base or FingeringConfig()
    rpc = root_pc(cell["root"])
    density = context.get("density", "quarter")
    out: List[dict] = []
    for name in POSITIONS:
        cfg, root_midi = _position(name, rpc, base)
        octaves = []
        for r, note in _feasible_octaves(cell, context, cfg, root_midi):
            octaves.append({
                "result": r,
                "cost": cost_of(r.best.placed, base, density),
                "register": _register_label(r, rpc),
                "note": note,
            })
        octaves.sort(key=lambda o: o["cost"])
        out.append({
            "name": name,
            "best_cost": octaves[0]["cost"] if octaves else None,
            "octaves": octaves,
        })
    out.sort(key=lambda p: (p["best_cost"] is None,
                            -(p["best_cost"] if p["best_cost"] is not None else 0.0)))
    return out
