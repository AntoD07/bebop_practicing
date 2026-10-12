"""Rank the fingerings of a pentatonic line across neck positions + run styles.

Mirrors ``rank_line_fingerings`` in the Melodic Lines page: solve the line under
"Free" (best anywhere), the user's preferred "3+2 per string" fingering, and each
named CAGED/diagonal position, then rank by a common cost. The whole run is first
octave-shifted into the guitar's playable range so long (2-3 octave) runs don't
fall off the top of the neck.
"""

from typing import List, Optional

from scripts.fingering.config import FingeringConfig, STANDARD_TUNING_MIDI
from scripts.fingering.optimizer import optimize_fingering, cost_of, enumerate_fingerings
from scripts.fingering.picking import ConventionError
from scripts.fingering.pitch import parse_pitch, candidate_placements
from scripts.fingering.positions import (
    POSITIONS,
    position_config_for_key,
    position_boxes,
    classify_position,
    classify_positions,
)
from scripts.pentatonics.pentatonics import PENTATONICS


def _fitting_slice(line, cfg):
    """Longest contiguous [start, end) of the line whose notes all fit ``cfg``'s box."""
    feas = [len(candidate_placements(parse_pitch(d["pitch"]), cfg)) > 0 for d in line]
    best_i, best_len, j, n = 0, 0, 0, len(feas)
    while j < n:
        if not feas[j]:
            j += 1
            continue
        k = j
        while k < n and feas[k]:
            k += 1
        if k - j > best_len:
            best_len, best_i = k - j, j
        j = k
    return best_i, best_i + best_len

def _fitting_prefix(line, cfg) -> int:
    """Length of the longest PREFIX of the line whose notes all fit ``cfg``'s box.

    Unlike :func:`_fitting_slice` (longest slice anywhere), a prefix always
    starts on the run's first note — the starting note the user picked. A
    key-root note counts as fitting only on the shape's root strings: the
    enumeration pins roots there (hard), so a prefix that ran up to a root
    with no such placement (Eb minor, CAGED A: the high Eb only on e/11)
    would be rejected wholesale instead of stopping one note earlier.
    """
    pin = cfg.root_pin
    n = 0
    for d in line:
        midi = parse_pitch(d["pitch"])
        pls = candidate_placements(midi, cfg)
        if pin is not None and midi % 12 == pin[0]:
            pls = [pl for pl in pls if pl.string in pin[1]]
        if not pls:
            break
        n += 1
    return n


_LOW_OPEN = STANDARD_TUNING_MIDI[6]  # 40, low-E open


def _hi_playable(max_fret):
    return STANDARD_TUNING_MIDI[1] + max_fret  # highest note = high-E at max fret


def sliding_pins(line: List[dict], max_fret: int = 18, per_string: int = 3):
    """Rolling 3-per-string 'sliding' run — the long horizontal traversal.

    Consecutive notes are taken 3 to a string, walking string 1->6 when the run
    descends (6->1 ascending); the hand shifts along the neck at each string
    change. Unlike the boxed CAGED shapes or the fixed 3+2 groups (max ~6 string
    groups), this covers up to 18 notes (~3 octaves) in one continuous motion.
    Returns ``(line, pins, covered)``.
    """
    n = len(line)
    if n < 2:
        return line, {}, 0
    best = (line, {}, 0)
    for oct_shift in (0, 12, 24, -12, -24):
        tl = _transpose(line, oct_shift)
        midis = [parse_pitch(d["pitch"]) for d in tl]
        descending = midis[-1] < midis[0]
        for start_off in (0, 1, 2):  # the walk may start a string or two in
            pins, covered = {}, 0
            for i, m in enumerate(midis):
                g = i // per_string + start_off
                s = (1 + g) if descending else (6 - g)
                s = min(6, max(1, s))  # extra groups pile on the last string
                f = m - STANDARD_TUNING_MIDI[s]
                if not (0 <= f <= max_fret):
                    break
                pins[m] = (s, f)
                covered = i + 1
            if covered > best[2]:
                best = (tl, pins, covered)
    return best


def _transpose(line: List[dict], semitones: int) -> List[dict]:
    """Shift every pitch by ``semitones`` (same run, different register)."""
    out = []
    for d in line:
        e = dict(d)
        e["pitch"] = parse_pitch(d["pitch"]) + semitones
        out.append(e)
    return out


def _fit_register(line: List[dict], max_fret: int = 15) -> List[dict]:
    """Octave-shift the whole run so it best fits [low-E open, high-E@max_fret]."""
    midis = [parse_pitch(d["pitch"]) for d in line]
    if not midis:
        return line
    lo, hi = min(midis), max(midis)
    target_lo, target_hi = _LOW_OPEN, _hi_playable(max_fret)
    best_k, best_pen = 0, None
    for k in range(-4, 5):
        nlo, nhi = lo + 12 * k, hi + 12 * k
        pen = max(0, target_lo - nlo) + max(0, nhi - target_hi)
        if best_pen is None or pen < best_pen:
            best_pen, best_k = pen, k
    return _transpose(line, best_k * 12) if best_k else line


def _h32_group_fn(root, penta: str):
    """Return midi -> global 3+2 group number for the pentatonic's canonical
    string groups (minor: b3-4-5 / b7-root; major-type: 1-2-3 / 5-6). Chromatic
    passing tones join the group of the scale tone ABOVE them (their resolution).
    """
    from scripts.fingering.cell_bridge import root_pc

    intervals = PENTATONICS[penta]["intervals"]
    groups = PENTATONICS[penta]["h32_groups"]
    rpc = root_pc(root)

    def global_group(midi: int) -> int:
        o, rel = divmod(midi - rpc, 12)
        if rel in intervals:
            idx = intervals.index(rel)
        else:
            ups = [iv for iv in intervals if iv > rel]
            if ups:
                idx = intervals.index(min(ups))
            else:
                idx, o = 0, o + 1
        gid, off = groups[idx]
        return 2 * (o + off) + gid

    return global_group


def preferred_pins(line: List[dict], root, penta: str, max_fret: int = 15):
    """Return ``(line, pins, covered)`` for the horizontal 3+2 per-string fingering.

    The layout is DEGREE-based (the user's system): each canonical string group
    takes one string, whatever note the run starts on — a run starting mid-group
    simply plays the remainder of that group's string. Fingers (1-2-4 / 1-3)
    then emerge from the pair-span physics. Searches octave registers and keeps
    the one covering the most of the run.
    """
    n = len(line)
    if n == 0:
        return line, {}, 0
    global_group = _h32_group_fn(root, penta)

    best_line, best_pins, best_cov = line, {}, 0
    for oct_shift in (0, 12, 24, -12, -24):
        tl = _transpose(line, oct_shift)
        midis = [parse_pitch(d["pitch"]) for d in tl]
        gs = [global_group(m) for m in midis]
        gmin = min(gs)
        pins, covered = {}, 0
        for m, g in zip(midis, gs):
            s = max(1, 6 - (g - gmin))  # groups walk 6->1; extras pile on string 1
            f = m - STANDARD_TUNING_MIDI[s]
            if 0 <= f <= max_fret:
                pins[m] = (s, f)
                covered += 1
            else:
                break  # run climbs off the neck here; partial is fine
        if covered > best_cov:
            best_line, best_pins, best_cov = tl, pins, covered
    return best_line, best_pins, best_cov


def _safe_opt(line, context, cfg, pinned=None):
    try:
        return optimize_fingering(line, context, cfg, pinned=pinned)
    except (ValueError, KeyError, ConventionError):
        return None


def _align_slice(i: int, e: int, group: Optional[int]):
    """Snap a slice to grouping boundaries so a pattern's identity survives.

    Formulas/patterns are cycles of ``group`` notes; a slice cut mid-grouping
    shows a PHASE-ROTATED pattern — visually a different (or another formula's!)
    contour. Align the start up and the end down to multiples of ``group``.
    """
    if not group:
        return i, e
    i2 = ((i + group - 1) // group) * group
    e2 = i2 + ((e - i2) // group) * group
    return i2, max(i2, e2)


def _align_prefix(covered: int, group: Optional[int]) -> int:
    """Trim a prefix length down to a whole number of groupings."""
    if not group:
        return covered
    return (covered // group) * group


def _row(label, cand, covered, n_total, base, key):
    """Build a row; annotate 'where' with N/M when only part of the run fits.

    Rows also carry ``cpn`` (cost per played note): candidates cover DIFFERENT
    amounts of the run, so raw total cost is not comparable — a cheap 8-note
    fragment is not "easier" than a 20-note fingering.
    """
    if cand is None or covered < 2:
        return {"position": label, "cost": None, "cpn": None,
                "covered": 0, "where": "does not fit", "result": None}
    where = classify_position(cand.best.placed, key)
    if covered < n_total:
        where += f" · {covered}/{n_total} notes"
    n_played = max(1, len(cand.best.placed))
    cost = cost_of(cand.best.placed, base)
    return {
        "position": label,
        "cost": cost,
        "cpn": cost / n_played,
        "covered": n_played,
        "where": where,
        "result": cand,
    }


def _free_style_row(label, line, context, cfg, base, key, n_total, group=None):
    """A free-placement candidate that renders the largest slice that fits."""
    res = _safe_opt(line, context, cfg)
    covered = n_total
    if res is None:
        i, e = _fitting_slice(line, cfg)
        i, e = _align_slice(i, e, group)
        res = _safe_opt(line[i:e], context, cfg) if e - i >= 2 else None
        covered = (e - i) if res else 0
    return _row(label, res, covered, n_total, base, key)


# Open-string pitches, highest first: (midi, string).
_OPEN_PITCHES = [(64, 1), (59, 2), (55, 3), (50, 4), (45, 5), (40, 6)]


def open_pivot_pins(line: List[dict], root, penta: str, max_fret: int = 18):
    """The 3+2 system with a single open-string repositioning pivot mid-run.

    Same degree-based string groups as :func:`preferred_pins`, but when the run
    reaches a pentatonic note that IS an open string (e.g. open high-E for A
    minor), that note is played OPEN — the hand shifts up the neck while it
    rings — and the 3+2 grouping CONTINUES from the new position, mapped so the
    remaining groups finish on string 1. Returns ``(line, pins, covered)``.
    """
    n = len(line)
    if n == 0:
        return line, {}, 0
    global_group = _h32_group_fn(root, penta)

    best = (line, {}, 0)
    for oct_shift in (0, 12, 24, -12, -24):
        tl = _transpose(line, oct_shift)
        midis = [parse_pitch(d["pitch"]) for d in tl]
        gs = [global_group(m) for m in midis]
        gmin = min(gs)
        for ppitch, pstring in _OPEN_PITCHES:  # highest open string first
            if ppitch not in midis:
                continue
            pidx = midis.index(ppitch)
            if not (2 <= pidx <= n - 2):  # must be a real mid-run pivot
                continue
            pins, covered, fits = {}, 0, True
            # Before the pivot: the plain 3+2 walk from string 6.
            for i in range(pidx):
                s = max(1, 6 - (gs[i] - gmin))
                f = midis[i] - STANDARD_TUNING_MIDI[s]
                if not (0 <= f <= max_fret):
                    fits = False
                    break
                pins[midis[i]] = (s, f)
                covered = i + 1
            if not fits:
                continue
            # The pivot: played open; the hand shifts while it rings.
            pins[ppitch] = (pstring, 0)
            covered = pidx + 1
            # After the pivot: the SAME 3+2 grouping, re-anchored up the neck so
            # the remaining groups land on the top strings and end on string 1.
            rest = list(range(pidx + 1, n))
            if rest:
                gmax = max(gs[i] for i in rest)
                for i in rest:
                    s = min(6, max(1, 1 + (gmax - gs[i])))
                    f = midis[i] - STANDARD_TUNING_MIDI[s]
                    if not (0 <= f <= max_fret):
                        break
                    pins[midis[i]] = (s, f)
                    covered = i + 1
            if covered > best[2]:
                best = (tl, pins, covered)
    return best


def rank_pentatonic_fingerings(
    line: List[dict], key: str, base_cfg: Optional[FingeringConfig] = None,
    root=None, penta: str = "minor", group: Optional[int] = None,
) -> List[dict]:
    """Return candidate fingering rows sorted by cost (unplayable ones sink).

    ``root``/``penta`` identify the pentatonic (for the degree-based 3+2 layout);
    ``root`` defaults to ``key``. Every candidate renders the largest slice of
    the run that fits — a run may climb off the top of the neck, and it's fine
    not to finish the scale. ``group`` (e.g. 4 for Bergonzi formulas) aligns all
    partial slices to grouping boundaries, so a truncated pattern never shows a
    phase-rotated (wrong) contour.
    """
    base = base_cfg or FingeringConfig()
    # Pentatonic runs are the ONE context where open strings are welcome (the
    # engine-wide default is now fretted-only): the open-string-pivot system
    # PINS a fret-0 placement, and pins are filtered through
    # candidate_placements — without this override the pivot dies.
    base = base.with_overrides(allow_open_strings=True)
    context = {"key": key}
    root = root if root is not None else key
    orig_line = line
    line = _fit_register(line, base.max_fret)  # bring the run onto the neck
    n_total = len(line)
    min_cov = max(2, group or 0)
    rows: List[dict] = []

    # Free — cheapest anywhere (the natural "diagonal" lie); partial if it runs off.
    rows.append(_free_style_row("Free (best on the neck)", line, context, base,
                                base, key, n_total, group))

    # The user's preferred 3+2 per-string fingering, pinned exactly (engine still
    # derives picking + the 1-2-4 / 1-3 fingers). Longest prefix that fits.
    pline, pins, covered = preferred_pins(line, root, penta, base.max_fret)
    covered = _align_prefix(covered, group)
    res = _safe_opt(pline[:covered], context, base, pinned=pins) if covered >= min_cov else None
    rows.append(_row("3+2 per string (your fingering)", res, covered, n_total, base, key))

    # 3+2 with an open-string pivot — the same degree-based layout, but one
    # pentatonic note that coincides with an open string is played OPEN mid-run,
    # letting the hand shift up so the 3+2 grouping finishes up the neck (needs
    # the upper frets a real neck has).
    op_cfg = base.with_overrides(max_fret=18)
    op_line, op_pins, op_cov = open_pivot_pins(orig_line, root, penta, 18)
    op_cov = _align_prefix(op_cov, group)
    op_res = _safe_opt(op_line[:op_cov], context, op_cfg, pinned=op_pins) if op_cov >= min_cov else None
    rows.append(_row("3+2 with open-string pivot", op_res, op_cov, n_total, base, key))

    # Sliding 3-per-string — the long horizontal traversal (2-3 octaves in one
    # continuous shifting motion; the go-to when the boxed systems run out).
    sl_line, sl_pins, sl_cov = sliding_pins(orig_line, 18)
    sl_cov = _align_prefix(sl_cov, group)
    sl_res = _safe_opt(sl_line[:sl_cov], context, op_cfg, pinned=sl_pins) if sl_cov >= min_cov else None
    rows.append(_row("3 per string (sliding run)", sl_res, sl_cov, n_total, base, key))

    # Named positions — the largest slice that fits each key-anchored box.
    rows.extend(_position_rows(line, key, base, context, n_total, group, min_cov))
    _sort_rows(rows)
    return rows


def _sort_rows(rows: List[dict]) -> None:
    """Rank by cost PER NOTE (coverage-fair), fullest coverage breaking ties;
    unplayable rows sink."""
    rows.sort(key=lambda r: (r["cpn"] is None,
                             r["cpn"] if r["cpn"] is not None else 0.0,
                             -r["covered"]))


def _position_rows(line, key, base, context, n_total, group, min_cov) -> List[dict]:
    """One row per named position: transpose the run by octaves to sit in each
    key-anchored box and keep the largest (grouping-aligned) slice that fits.
    (Position configs are fretted-only: movable shapes never use open strings
    — enforced in positions.py.)"""
    rows: List[dict] = []
    for pos in POSITIONS:
        cfg, _root_midi = position_config_for_key(pos, key, base)
        best = None  # ((-covered, cost), cand, covered)
        for off in (-24, -12, 0, 12, 24):
            tl = _transpose(line, off)
            i, e = _fitting_slice(tl, cfg)
            i, e = _align_slice(i, e, group)
            if e - i < min_cov:
                continue
            cand = _safe_opt(tl[i:e], context, cfg)
            if cand is None:
                continue
            cov = e - i
            metric = (-cov, cost_of(cand.best.placed, base))
            if best is None or metric < best[0]:
                best = (metric, cand, cov)
        if best is None:
            rows.append({"position": pos, "cost": None, "cpn": None, "covered": 0,
                         "where": "does not fit", "result": None})
        else:
            _, cand, cov = best
            rows.append(_row(pos, cand, cov, n_total, base, key))
    return rows


def rank_line_fingerings(
    line: List[dict], key: str, base_cfg: Optional[FingeringConfig] = None,
    group: Optional[int] = None,
) -> List[dict]:
    """The GENERIC ranker for any run (triad pairs, hexatonics…): "Free" plus
    the five named positions, cheapest per note first — no pentatonic-specific
    systems (3+2, open-string pivot, sliding) and NO open strings (the engine-
    wide rule; only pentatonic runs get the open-string exception). Rows are
    the same dicts as :func:`rank_pentatonic_fingerings`.
    """
    base = base_cfg or FingeringConfig()
    context = {"key": key}
    line = _fit_register(line, base.max_fret)
    n_total = len(line)
    min_cov = max(2, group or 0)
    rows: List[dict] = [
        _free_style_row("Free (best on the neck)", line, context, base, base, key, n_total, group)
    ]
    rows.extend(_position_rows(line, key, base, context, n_total, group, min_cov))
    # A box that fits only a scrap of a long run (one grouping of a 50-note
    # alternating-triads line, often at a NEGATIVE sweep-bonus cost) is not a
    # fingering of the run: demote anything under a third of it to the bottom.
    for r in rows:
        if r["result"] is not None and 0 < r["covered"] < n_total / 3:
            r.update(cost=None, cpn=None,
                     where=f"fits only {r['covered']}/{n_total} notes")
    _sort_rows(rows)
    return rows


def rank_line_across_starts(
    lines_by_start: dict, key: str, base_cfg: Optional[FingeringConfig] = None,
    group: Optional[int] = None,
) -> List[dict]:
    """:func:`rank_line_fingerings` for several starting notes, one combined
    list (each row tagged with ``start``) cheapest per note first."""
    combined = []
    for start_label, line in lines_by_start.items():
        for r in rank_line_fingerings(line, key, base_cfg, group=group):
            r = dict(r)
            r["start"] = start_label
            combined.append(r)
    _sort_rows(combined)
    return combined


def rank_across_starts(
    lines_by_start: dict, key: str, base_cfg: Optional[FingeringConfig] = None,
    root=None, penta: str = "minor", group: Optional[int] = None,
) -> List[dict]:
    """Rank fingerings for several starting notes at once.

    ``lines_by_start`` maps a starting-note label to its exercise line. Returns one
    combined list (each row tagged with ``start``) sorted by cost, so you can see
    which starting note + fingering lies easiest.
    """
    combined = []
    for start_label, line in lines_by_start.items():
        for r in rank_pentatonic_fingerings(line, key, base_cfg, root=root,
                                            penta=penta, group=group):
            r = dict(r)
            r["start"] = start_label
            combined.append(r)
    _sort_rows(combined)
    return combined


# "Enforce the position" on the pentatonic page: the box tolerates this many
# frets (the user's ±1 for runs; cell connections use a hard box).
PENTA_POSITION_SLACK = 1


def enumerate_position_fingerings(
    line: List[dict], key: str, position: str,
    base_cfg: Optional[FingeringConfig] = None, group: Optional[int] = None,
    slack: int = PENTA_POSITION_SLACK, max_layouts: int = 4000,
) -> List[dict]:
    """EVERY fingering of a run inside one named position (±``slack`` frets),
    cheapest per note first — the Cell Connexions logic applied to a run.

    Both octaves of the box and every octave transposition of the run are
    tried; each renders the longest PREFIX of the run that fits the (tolerant)
    box — the fingering always starts on the run's first note, i.e. the
    starting note the user picked, never on a cheaper slice from the middle
    (which would start on another degree and drag the hand onto a low
    string). All distinct string/fret layouts of that prefix are enumerated,
    and only those labelled with the position (same tolerance) are kept. When
    a prefix admits more than ``max_layouts`` layouts the single optimum is
    listed instead. Rows are the same dicts as
    :func:`rank_pentatonic_fingerings` plus ``layout``.
    """
    base = base_cfg or FingeringConfig()
    context = {"key": key}
    line = _fit_register(line, base.max_fret)
    n_total = len(line)
    min_cov = max(2, group or 0)
    rows: List[dict] = []
    seen = set()
    for cfg, _root_midi in position_boxes(position, key, base):
        cfg = cfg.with_overrides(window_overflow_frets=slack)
        for off in (-24, -12, 0, 12, 24):
            tl = _transpose(line, off)
            i, e = 0, _align_prefix(_fitting_prefix(tl, cfg), group)
            if e - i < min_cov:
                continue
            seg = tl[i:e]
            try:
                cands = enumerate_fingerings(seg, context, cfg, max_layouts=max_layouts)
            except ValueError:
                one = _safe_opt(seg, context, cfg)
                cands = [one] if one is not None else []
            except ConventionError:
                continue
            for cand in cands:
                layout = " ".join(f"{p.string}/{p.fret}" for p in cand.best.placed)
                if layout in seen:
                    continue
                names = classify_positions(cand.best.placed, key, slack=slack)
                if position not in names:
                    continue
                seen.add(layout)
                row = _row(position, cand, e - i, n_total, base, key)
                # Label with the SAME tolerance the filter used (the strict
                # label would read "frets a-b" for a fingering one fret out).
                pl = cand.best.placed
                row["where"] = (f"{position} · frets {min(p.fret for p in pl)}–"
                                f"{max(p.fret for p in pl)}"
                                + (f" · {e - i}/{n_total} notes" if e - i < n_total else ""))
                row["layout"] = layout
                rows.append(row)
    # Other octaves of the run often fit only a short fragment of it; a cheap
    # 3-note fragment is not a fingering of the run. Keep the fullest coverage.
    if rows:
        best_cov = max(r["covered"] for r in rows)
        rows = [r for r in rows if r["covered"] == best_cov]
    rows.sort(key=lambda r: (r["cpn"], -r["covered"]))
    return rows


def enumerate_across_starts(
    lines_by_start: dict, key: str, position: str,
    base_cfg: Optional[FingeringConfig] = None, group: Optional[int] = None,
) -> List[dict]:
    """:func:`enumerate_position_fingerings` for several starting notes."""
    combined = []
    for start_label, line in lines_by_start.items():
        for r in enumerate_position_fingerings(line, key, position, base_cfg, group):
            r = dict(r)
            r["start"] = start_label
            combined.append(r)
    combined.sort(key=lambda r: (r["cpn"], -r["covered"]))
    return combined
