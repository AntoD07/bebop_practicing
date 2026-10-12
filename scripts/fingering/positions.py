"""The five named guitar positions used in the Cell Quiz.

Each position constrains the fingering search to a region of the neck anchored
on the chord root, so the same cell can be practised in every shape:

  1. CAGED E string root  — root on string 6, a compact box (E-shape).
  2. CAGED A string root  — root on string 5, a compact box (A-shape).
  3. Diagonal E string root — root on string 6 under the PINKY: the box runs
     from three frets below the root fret up to it (Eb: 8-11).
  4. Diagonal A string root — root on string 5 under the pinky (Eb: 3-6).
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
from scripts.fingering.cell_bridge import (
    build_pitch_line, cell_context, root_pc, timed_cell_line,
)
from scripts.fingering.pitch import midi_to_name, parse_pitch

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
    # Diagonals: the hand box with the ROOT UNDER THE PINKY — three frets
    # below the root fret up to it (Eb: E-diag 8-11, A-diag 3-6). A CAGED box
    # has the root under the index (rf-1..rf+4). Roots are unpinned here: a
    # hand at 3-6 plays the Eb on B/4 as naturally as on A/6.
    "Diagonal E string root":    dict(string=6, below=3, above=0,
                                      strings=(1, 2, 3, 4, 5, 6), roots=(1, 2, 3, 4, 5, 6)),
    "Diagonal A string root":    dict(string=5, below=3, above=0,
                                      strings=(1, 2, 3, 4, 5, 6), roots=(1, 2, 3, 4, 5, 6)),
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


def _string_windows(spec: dict, rf: int):
    """Per-string ``(string, lo, hi)`` boxes of a slanted shape at root fret
    ``rf``, or None for a plain rectangular box."""
    offs = spec.get("pair_offsets")
    if not offs:
        return None
    return tuple((s, max(0, rf + o), rf + o + spec["span"]) for s, o in offs.items())


def _window_at(spec: dict, rf: int):
    """(global envelope, per-string windows) of a shape at root fret ``rf``."""
    sw = _string_windows(spec, rf)
    if sw:
        return (min(lo for _, lo, _ in sw), max(hi for _, _, hi in sw)), sw
    return (max(0, rf - spec["below"]), rf + spec["above"]), None


def _position(name: str, root_pc_val: int, base: FingeringConfig):
    """Return (config, root_midi) for a position.

    The config carries BOTH the key-anchored fret window(s) and the root pin:
    key roots may only sit on the shape's root strings, so an "E string root"
    position can never render with its root on the A string.
    """
    spec = _SPECS[name]
    rf = _root_fret(root_pc_val, spec["string"])
    (lo, hi), sw = _window_at(spec, rf)
    root_midi = STANDARD_TUNING_MIDI[spec["string"]] + rf
    # Positions are MOVABLE shapes — fully fretted by definition. Open strings
    # only sneak in when a box sits at the nut, and never belong to the shape.
    cfg = base.with_overrides(fret_window=(lo, hi), string_fret_windows=sw,
                              string_range=spec["strings"],
                              root_pin=(root_pc_val, spec["roots"]),
                              allow_open_strings=False,
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
        line = timed_cell_line(build_pitch_line([cell], base_midi=root_midi + off,
                                                first_note_target=root_midi + off))
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
        wide = cfg.with_overrides(
            fret_window=(max(0, lo - 4), hi + 4),
            string_fret_windows=tuple((s, max(0, l - 4), h + 4)
                                      for s, l, h in cfg.string_fret_windows or ()) or None)
        for off in (-12, 0, 12):
            line = timed_cell_line(build_pitch_line([cell], base_midi=root_midi + off,
                                                    first_note_target=root_midi + off))
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


def position_signature(name: str):
    """Hashable description of a shape — pass it to ``st.cache_data`` functions
    so a change to ``_SPECS`` invalidates their cache (Streamlit only keys on
    the cached function's own source, not on this module)."""
    spec = _SPECS.get(name)
    if spec is None:
        return name
    return (name, "slack", POSITION_SLACK) + tuple(sorted((k, tuple(sorted(v.items())) if isinstance(v, dict)
                                   else v) for k, v in spec.items()))


def position_config_for_key(name: str, key, base: Optional[FingeringConfig] = None):
    """Public: (config, root_midi) that pins a named position for a KEY.

    The config carries the key-anchored fret window, the shape's string set and
    the root pin; ``root_midi`` is the register anchor (the key root's location
    on the shape's root string) to voice lines around.
    """
    base = base or FingeringConfig()
    return _position(name, root_pc(key), base)


def position_boxes(name: str, key, base: Optional[FingeringConfig] = None):
    """Every ``(config, root_midi)`` of a named position on the neck.

    The same movable shape exists at its root fret AND 12 frets higher;
    :func:`position_config_for_key` only returns the low one. The high copy is
    included whenever its root fret is still on the fingerboard.
    """
    base = base or FingeringConfig()
    cfg, root_midi = _position(name, root_pc(key), base)
    spec = _SPECS[name]
    rf_hi = _root_fret(root_pc(key), spec["string"]) + 12
    out = [(cfg, root_midi)]
    if rf_hi <= base.max_fret:
        (lo, hi), sw = _window_at(spec, rf_hi)
        out.append((cfg.with_overrides(fret_window=(lo, hi), string_fret_windows=sw),
                    root_midi + 12))
    return out


# Tolerance outside a position's box, in frets — used BOTH by page 1's
# enumeration and by the labelling below, so "listed in the position" and
# "labelled with the position" always agree. 0 = hard boundary (validated by
# the user; 2 was tried on 2026-10-11 and reverted — boxes overlapped too much).
POSITION_SLACK = 0


def classify_positions(placed, key, slack: int = None) -> List[str]:
    """Every named position a fingering belongs to (w.r.t. the KEY root): the
    shapes whose key-anchored box — at either octave of the root fret —
    contains all its frets, on the shape's strings, with the key roots on the
    shape's root strings. Empty when nothing matches.
    """
    slack = POSITION_SLACK if slack is None else slack
    rpc = root_pc(key)
    frets = [p.fret for p in placed if p.fret > 0]
    if not frets:
        return []
    lo, hi = min(frets), max(frets)
    out = []
    for name in POSITIONS:
        spec = _SPECS[name]
        if not all(p.string in spec["strings"] for p in placed):
            continue
        if not all(p.string in spec["roots"] for p in placed if p.note.midi % 12 == rpc):
            continue
        rf0 = _root_fret(rpc, spec["string"])
        for rf in (rf0, rf0 + 12):
            if max(0, rf - spec["below"] - slack) <= lo and hi <= rf + spec["above"] + slack:
                out.append(name)
                break
    return out


def classify_position(placed, key) -> str:
    """Name the (most specific) position a fingering falls in, w.r.t. the KEY,
    plus its fret span — or just the span when no shape matches."""
    frets = [p.fret for p in placed if p.fret > 0]
    if not frets:
        return "open strings"
    span = f"frets {min(frets)}–{max(frets)}"
    names = classify_positions(placed, key)
    return f"{names[0]} · {span}" if names else span


def rank_absolute_fingerings(line: List[dict], context: dict, key,
                             base: Optional[FingeringConfig] = None) -> List[dict]:
    """Rank candidate fingerings for a FIXED absolute-pitch line (e.g. a score).

    Unlike :func:`optimize_all_positions` (cells, re-voiced per box), the
    pitches here are written and absolute — a position either covers the
    register or honestly reports that it doesn't. Candidates:

      * Free — the global best on the neck, plus its in-margin alternate;
      * the five named positions, anchored on ``key``;
      * three plain neck bands (low/mid/high fret windows) as extra proposals.

    A candidate whose register does not fit AS WRITTEN (e.g. a piano line
    reaching above the neck) is retried with the whole line transposed
    ±1–2 octaves — the written octave is always preferred, and the shift used
    is reported in ``shift`` (semitones: 0, ±12, ±24; None = nothing fit).
    As-written rows always rank above transposed ones: the written octave is
    the score's ground truth, a shift is a compromise — never a cheap win.

    Identical placements are merged (extra labels collect in ``also``); every
    candidate is scored with :func:`cost_of` under the shared ``base`` weights
    so relaxed position configs stay comparable. Rows are sorted cheapest
    (most feasible) first; unplayable candidates sink to the bottom with the
    reason in ``where``. Each row:

        {"label", "cost", "where", "n_up", "also", "shift", "result"}

    ``result`` is a render-ready :class:`FingeringResult` whose ``best`` is
    THIS candidate (the Free alternate is re-wrapped so it renders), or None.
    """
    base = base or FingeringConfig()
    if "beats_per_bar" in context:
        base = base.with_overrides(beats_per_bar=context["beats_per_bar"])
    density = context.get("density", "quarter")
    line = [{**n, "pitch": parse_pitch(n["pitch"])} for n in line]
    rows: List[dict] = []
    by_sig: dict = {}

    def _keep(label, res, voicing, shift):
        sig = tuple((p.string, p.fret) for p in voicing.placed)
        if sig in by_sig:
            by_sig[sig]["also"].append(label)
            return
        shown = FingeringResult(notes=res.notes, best=voicing, alternate=None,
                                context=res.context, config=res.config,
                                warnings=list(res.warnings))
        row = {"label": label,
               "cost": cost_of(voicing.placed, base, density),
               "where": classify_position(voicing.placed, key),
               "n_up": sum(1 for p in voicing.placed if p.stroke == "U"),
               "also": [], "shift": shift, "result": shown}
        by_sig[sig] = row
        rows.append(row)

    def _solve(label, cfg, with_alternate=False):
        written_err = None
        # The written octave first; transposed fallbacks only if it can't fit.
        for shift in (0, -12, 12, -24, 24):
            shifted = (line if shift == 0 else
                       [{**n, "pitch": n["pitch"] + shift} for n in line])
            try:
                res = optimize_fingering(shifted, context, cfg)
            except ValueError as e:
                if shift == 0:
                    written_err = e
                continue
            _keep(label, res, res.best, shift)
            if with_alternate and res.alternate is not None:
                _keep(f"{label} · alternate", res, res.alternate, shift)
            return
        rows.append({"label": label, "cost": None,
                     "where": f"does not fit (any octave): {written_err}",
                     "n_up": None, "also": [], "shift": None, "result": None})

    _solve("Free (best on the neck)", base, with_alternate=True)
    for name in POSITIONS:
        cfg, _ = _position(name, root_pc(key), base)
        _solve(name, cfg)
    for label, win in (("Low neck (frets 0–7)", (0, 7)),
                       ("Mid neck (frets 4–11)", (4, 11)),
                       ("High neck (frets 8–15)", (8, min(15, base.max_fret)))):
        _solve(label, base.with_overrides(fret_window=win))

    rows.sort(key=lambda r: (r["cost"] is None,
                             abs(r["shift"] or 0),
                             r["cost"] if r["cost"] is not None else 0.0))
    return rows


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
    context = cell_context(context)  # cell notes are eighths
    density = context["density"]
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
