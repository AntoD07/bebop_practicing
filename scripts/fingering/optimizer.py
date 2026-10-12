"""The shortest-path (Viterbi/DP) fingering + picking search.

This is NOT a greedy per-note chooser. We build a trellis over notes; a state is
``(string, fret, hand_anchor, outgoing_stroke, string_run_length)`` and the
transition cost is the playability + picking + shift + break model in
:mod:`scripts.fingering.costs`. The minimum-cost path through the trellis is the
recommended fingering; the picking falls out of it.

Where a descending crossing could be handled three ways the DP simply *expands
all three* and lets cost decide:

  a) PARITY  — end the upper string on a U so the crossing arrives U->D
               (one same-string U state; costs ``u_cost``).
  b) ROUTING — don't cross at all: take the next (lower) pitch on the SAME string
               at a lower fret (a same-string transition; costs a hand shift and,
               for long single-string runs, a flagged 2npS break).
  c) MANAGED DROP — accept the D->D crossing, cheap at quarter pacing
               (``drop_cost * quarter_density_scale``); flagged as a managed drop.

We keep the k-best paths per state so a runner-up within ``alt_margin`` can be
returned as an alternate voicing.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from scripts.fingering.config import FingeringConfig, default_config
from scripts.fingering.pitch import (
    Note, build_notes, candidate_placements, anchors_for, finger_for,
)
from scripts.fingering.costs import (
    DOWN, UP, PlacedNote, classify_transition, edge_cost, initial_cost,
    relabel_fingers,
)
from scripts.fingering.picking import (
    verify_conventions, entry_strokes, same_string_strokes,
    phrase_start_strokes, find_invariant_violations,
)

# A DP state key. anchor may be None (open string carries the position).
StateKey = Tuple[int, int, Optional[int], str, int]
# A k-best entry: cumulative cost and a backpointer (prev_state, prev_entry_idx).
Back = Optional[Tuple[StateKey, int]]


def _make_placed(note: Note, string: int, fret: int, anchor: Optional[int],
                 stroke: str, run_len: int, config: FingeringConfig) -> PlacedNote:
    finger, is_stretch = finger_for(fret, anchor, config)
    is_rest = (stroke == DOWN and string > 1)  # a D on the thinnest string can't rest
    return PlacedNote(
        note=note, string=string, fret=fret, anchor=anchor, finger=finger,
        is_stretch=is_stretch, stroke=stroke, run_len=run_len, is_rest_stroke=is_rest,
    )


@dataclass
class DropSite:
    """A flagged descending crossing that arrived D->D (a managed drop)."""

    target_index: int      # note index we dropped ONTO (the ornament target)
    prev_index: int
    from_string: int
    to_string: int
    beat: int
    fix: str = "managed_drop"


@dataclass
class Voicing:
    """A concrete fingering solution (the best, or an alternate)."""

    placed: List[PlacedNote]
    total_cost: float
    contributions: List[Tuple[str, float]]   # aggregated by tag, desc by amount
    flags: List[str]
    drop_sites: List[DropSite]

    def stroke_string(self) -> str:
        return " ".join(p.stroke for p in self.placed)


@dataclass
class FingeringResult:
    notes: List[Note]
    best: Voicing
    alternate: Optional[Voicing]
    context: dict
    config: FingeringConfig
    feasible: bool = True
    warnings: List[str] = field(default_factory=list)
    # Phase-2 applied-ornament events (populated only when the engine is enabled).
    ornaments: List[dict] = field(default_factory=list)
    # The slurred version of the line (an ornaments.OrnamentedVoicing), built
    # from a COPY of ``best`` — phase 1 stays the all-picked technique version.
    ornamented: Optional[object] = None

    @property
    def placed(self) -> List[PlacedNote]:
        return self.best.placed


# --------------------------------------------------------------------------- #
# The DP
# --------------------------------------------------------------------------- #
def _finalize(layer: Dict[StateKey, List[Tuple[float, Back]]], k: int) -> None:
    for key, entries in layer.items():
        entries.sort(key=lambda e: e[0])
        del entries[k:]


def _run_dp(notes: List[Note], config: FingeringConfig, density: str,
            pinned: Optional[Dict[int, Tuple[int, int]]] = None):
    """Return (layers, nodes) trellis, or raise ValueError if a pitch won't fit.

    ``pinned`` optionally maps a MIDI pitch to one (string, fret): every
    occurrence of that pitch must use that placement (the consistency pass).
    """
    n = len(notes)
    k = max(2, config.kbest)

    placements = []
    for nt in notes:
        pls = candidate_placements(nt.midi, config)
        if pinned and nt.midi in pinned:
            pls = [p for p in pls if (p.string, p.fret) == pinned[nt.midi]]
        placements.append(pls)
    for i, pls in enumerate(placements):
        if not pls:
            raise ValueError(
                f"note {i} ({notes[i].name}, midi {notes[i].midi}) has no playable "
                f"position within string_range={config.string_range} and "
                f"max_fret={config.max_fret}."
            )

    layers: List[Dict[StateKey, List[Tuple[float, Back]]]] = [dict() for _ in range(n)]
    nodes: List[Dict[StateKey, PlacedNote]] = [dict() for _ in range(n)]

    # --- init: note 0 opens the phrase => D, or U on an off-beat pickup (H4).
    for p in placements[0]:
        for a in anchors_for(p.fret, config):
            for stroke in phrase_start_strokes(notes[0]):
                pn = _make_placed(notes[0], p.string, p.fret, a, stroke, 1, config)
                c0, _ = initial_cost(pn, config)
                key: StateKey = (p.string, p.fret, a, stroke, 1)
                nodes[0][key] = pn
                layers[0].setdefault(key, []).append((c0, None))
    _finalize(layers[0], k)

    # --- transitions
    for i in range(n - 1):
        prev_layer = layers[i]
        nxt = i + 1
        for prev_key, prev_entries in prev_layer.items():
            pn_prev = nodes[i][prev_key]
            for p in placements[nxt]:
                rel_same = (p.string == pn_prev.string)
                rel_asc = (p.string < pn_prev.string)
                rel_desc = (p.string > pn_prev.string)

                # Legal strokes for the arriving note. After a U, a same-string
                # note goes back to D (alternation, never U-U); crossings always
                # enter on D (H1); a phrase start (after a rest) re-enters on D,
                # or on U when it is an off-beat pickup (H4).
                if notes[nxt].phrase_start:
                    strokes = phrase_start_strokes(notes[nxt])
                elif rel_same:
                    if pn_prev.stroke == UP:
                        strokes = [DOWN]
                    else:
                        strokes = same_string_strokes(notes[nxt].beat)
                elif rel_asc:
                    strokes = [DOWN]                        # entry (sweep if prev D)
                else:  # descending crossing
                    strokes = entry_strokes(True, config)   # [D] or [D,U] if allowed

                # Hand anchor options.
                if p.fret == 0:
                    anchor_opts: List[Optional[int]] = [pn_prev.anchor]  # open carries
                else:
                    anchor_opts = anchors_for(p.fret, config)

                run_len = (1 if notes[nxt].phrase_start
                           else min(pn_prev.run_len + 1, 3) if rel_same else 1)

                for a in anchor_opts:
                    for stroke in strokes:
                        cur = _make_placed(notes[nxt], p.string, p.fret, a,
                                           stroke, run_len, config)
                        e, _ = edge_cost(pn_prev, cur, config, density)
                        cur_key: StateKey = (p.string, p.fret, a, stroke, run_len)
                        nodes[nxt].setdefault(cur_key, cur)
                        bucket = layers[nxt].setdefault(cur_key, [])
                        for idx, (cp, _back) in enumerate(prev_entries):
                            bucket.append((cp + e, (prev_key, idx)))
        _finalize(layers[nxt], k)

    return layers, nodes


def _backtrack(layers, nodes, term_key: StateKey, entry_idx: int,
               n: int) -> List[PlacedNote]:
    path: List[PlacedNote] = []
    key: Optional[StateKey] = term_key
    idx = entry_idx
    for i in range(n - 1, -1, -1):
        # A COPY: trellis nodes are shared by every path through them, and
        # relabel_fingers() mutates finger/stretch in place — returning the
        # shared object let the alternate's relabelling silently rewrite the
        # best path after it had been analysed (27/392 Free results had
        # best.total_cost != cost_of(best.placed)).
        pn = copy.copy(nodes[i][key])
        path.append(pn)
        _cost, back = layers[i][key][idx]
        if back is None:
            break
        key, idx = back
    path.reverse()
    return path


def _signature(placed: List[PlacedNote]):
    return tuple((p.string, p.fret, p.stroke) for p in placed)


# --------------------------------------------------------------------------- #
# Path analysis: total cost, contributions, and every flag the spec asks for.
# --------------------------------------------------------------------------- #
def _analyze(placed: List[PlacedNote], config: FingeringConfig,
             density: str) -> Voicing:
    total = 0.0
    agg: Dict[str, float] = {}

    def add(tag: str, amt: float):
        agg[tag] = agg.get(tag, 0.0) + amt

    c0, contribs0 = initial_cost(placed[0], config)
    total += c0
    for tag, amt in contribs0:
        add(tag, amt)

    flags: List[str] = []
    drop_sites: List[DropSite] = []

    for i in range(len(placed) - 1):
        prev, cur = placed[i], placed[i + 1]
        e, contribs = edge_cost(prev, cur, config, density)
        total += e
        for tag, amt in contribs:
            add(tag, amt)

        rel = classify_transition(prev, cur)
        # Which drop-resolution fix (a/b/c) at each descending pitch move.
        # A phrase break is not a crossing — the rest absorbs the motion.
        if cur.note.phrase_start:
            pass
        elif rel["descending_cross"]:
            if prev.stroke == UP:
                flags.append(
                    f"note {i+1} (beat {cur.beat}): descending crossing "
                    f"str{prev.string}->str{cur.string} resolved by PARITY (fix a) "
                    f"— U->D."
                )
            else:
                flags.append(
                    f"note {i+1} (beat {cur.beat}): descending crossing "
                    f"str{prev.string}->str{cur.string} is a MANAGED DROP (fix c) "
                    f"— D->D, cost "
                    f"{config.drop_cost * config.density_scale(density) * (config.drop_scale_for(cur.note.cell) if cur.note.cell is not None and (prev.note.cell == cur.note.cell or prev.note.role == 'pivot') else 1.0):.2f}."
                )
                drop_sites.append(DropSite(
                    target_index=i + 1, prev_index=i,
                    from_string=prev.string, to_string=cur.string, beat=cur.beat,
                ))
        elif rel["same_string"] and cur.note.midi < prev.note.midi:
            # A descending pitch handled without crossing = lateral ROUTING (fix b).
            if cur.anchor is not None and prev.anchor is not None and cur.anchor != prev.anchor:
                flags.append(
                    f"note {i+1} (beat {cur.beat}): descending run kept ON str{cur.string} "
                    f"by ROUTING (fix b) — lateral shift {prev.anchor}->{cur.anchor}."
                )

        # Every U and the purpose it serves (parity fix vs. in-string alternation).
        if cur.stroke == UP:
            if i + 2 < len(placed) and placed[i + 2].string > cur.string:
                nxt = placed[i + 2]
                flags.append(
                    f"note {i+1} (beat {cur.beat}): U sets parity for the descending "
                    f"crossing note {i+1}->{i+2} (str{cur.string}->str{nxt.string})."
                )
            # alternation U: normal up-down within the string, no flag needed.

        # A downbeat (beat 1) not on a downstroke is illegal — safety flag.
        if cur.beat == 1 and cur.stroke != DOWN:
            flags.append(f"WARNING note {i+1}: beat 1 not on a downstroke ({cur.stroke}).")

    if placed and placed[0].beat == 1 and placed[0].stroke != DOWN:
        flags.append("WARNING note 0: beat 1 not on a downstroke.")

    # 2npS breaks: runs whose length != the expected 2. Length-1 runs are the
    # normal arpeggio idiom (one note per string) and are NOT flagged; runs of
    # 3+ are crammed/lateral breaks and always flagged.
    for start, length, string in _string_runs(placed):
        if length >= 3:
            frets = [placed[j].fret for j in range(start, start + length)]
            flags.append(
                f"2npS BREAK: {length} notes on str{string} "
                f"(notes {start}..{start+length-1}, frets {frets})."
            )

    contributions = sorted(agg.items(), key=lambda kv: -kv[1])
    return Voicing(placed=placed, total_cost=round(total, 4),
                   contributions=contributions, flags=flags, drop_sites=drop_sites)


def cost_of(placed: List[PlacedNote], config: FingeringConfig,
            density: str = "quarter") -> float:
    """Total cost of an *existing* placement under a given config.

    Used to compare fingerings on equal footing — e.g. ranking positions with a
    common weight set even though each position was solved with its own config.
    """
    return _analyze(placed, config, density).total_cost


def _string_runs(placed: List[PlacedNote]):
    """Yield (start_index, length, string) for each maximal same-string run."""
    if not placed:
        return
    start = 0
    for i in range(1, len(placed)):
        if placed[i].string != placed[start].string:
            yield start, i - start, placed[start].string
            start = i
    yield start, len(placed) - start, placed[start].string


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def optimize_fingering(line: List[dict], context: Optional[dict] = None,
                       config: Optional[FingeringConfig] = None,
                       pinned: Optional[Dict[int, Tuple[int, int]]] = None) -> FingeringResult:
    """Find the best Gypsy-jazz fingering + picking for a fixed melodic line.

    ``line``    : ordered list of ``{"pitch": <midi|scientific>, "role": <opt>,
                  "cell": <opt>, "degree": <opt>}``.
    ``context`` : ``{"key":..., "chords":[...], "beats_per_bar":4, "density":"quarter"}``.
    ``config``  : a :class:`FingeringConfig` (defaults if omitted).
    ``pinned``  : optional ``{midi: (string, fret)}`` forcing chosen placements
                  (e.g. a specific hand-fingering); picking/fingers are still derived.

    Returns a :class:`FingeringResult`. Phase-2 ornaments are attached only when
    ``config.ornament_engine_enabled`` is True.
    """
    config = config or default_config()
    context = context or {}

    # GUARDRAIL: the convention sanity check runs before anything else. On
    # failure it raises ConventionError and we halt — we do not proceed.
    verify_conventions(config)

    if not line:
        raise ValueError("empty line")

    density = context.get("density", "quarter")
    notes = build_notes(line, config, context)

    layers, nodes = _run_dp(notes, config, density, pinned=pinned)
    n = len(notes)

    # Terminal states: any stroke may end the line (a trailing U is legal
    # in-string alternation — the natural D-U on a final same-string pair).
    terminals: List[Tuple[float, StateKey, int]] = []
    for key, entries in layers[n - 1].items():
        for idx, (cost, _back) in enumerate(entries):
            terminals.append((cost, key, idx))
    if not terminals:
        raise ValueError("no feasible fingering")
    terminals.sort(key=lambda t: t[0])

    best_path = _backtrack(layers, nodes, terminals[0][1], terminals[0][2], n)
    # Post-search: fingers re-derived from finger-pair physics (1-2-4 groups etc.)
    # for the fixed placements, then the reported cost is computed from them.
    relabel_fingers(best_path, config)
    best = _analyze(best_path, config, density)

    # --- Consistency pass: the SAME pitch should keep the SAME (string,fret).
    # If the best path refingers a repeated pitch, re-solve with each pitch
    # pinned to one of its used placements and keep the consistent solution
    # unless it's worse by more than consistency_cost per refingered pitch.
    if config.consistency_cost > 0 and n > 1:
        groups: Dict[int, List[Tuple[int, Tuple[int, int]]]] = {}
        for i, p in enumerate(best_path):
            groups.setdefault(p.note.midi, []).append((i, (p.string, p.fret)))
        incon = {m: pl for m, pl in groups.items()
                 if len({loc for _, loc in pl}) > 1}
        if incon:
            budget = best.total_cost + config.consistency_cost * len(incon)
            for which in (0, -1):  # pin to first- or last-occurrence placement
                pin = {m: pl[which][1] for m, pl in incon.items()}
                try:
                    layers2, nodes2 = _run_dp(notes, config, density, pinned=pin)
                except ValueError:
                    continue
                terms2 = sorted(
                    (cost, key, idx)
                    for key, entries in layers2[n - 1].items()
                    for idx, (cost, _b) in enumerate(entries)
                )
                if not terms2:
                    continue
                path2 = _backtrack(layers2, nodes2, terms2[0][1], terms2[0][2], n)
                relabel_fingers(path2, config)
                cand = _analyze(path2, config, density)
                if cand.total_cost <= budget:
                    cand.flags.append(
                        f"consistency: {len(incon)} repeated pitch(es) refingered "
                        f"to a single placement (was {best.total_cost}, "
                        f"now {cand.total_cost}).")
                    best_path, best = path2, cand
                    budget = cand.total_cost

    # Alternate voicing: first runner-up that differs and is within alt_margin.
    alternate: Optional[Voicing] = None
    best_sig = _signature(best_path)
    margin = best.total_cost + config.alt_margin * max(1.0, abs(best.total_cost))
    for cost, key, idx in terminals[1:]:
        path = _backtrack(layers, nodes, key, idx, n)
        if _signature(path) == best_sig:
            continue
        relabel_fingers(path, config)
        cand = _analyze(path, config, density)
        if cand.total_cost <= margin:
            alternate = cand
        break

    result = FingeringResult(
        notes=notes, best=best, alternate=alternate,
        context=context, config=config,
    )

    # GUARDRAIL: the invariant must hold on the returned solution.
    violations = find_invariant_violations(best_path)
    if violations:
        result.warnings.append(
            f"INVARIANT VIOLATION at notes {violations} — every U must be "
            f"immediately followed by a descending string change. This is a bug."
        )

    # "Won't fit cleanly": surface the least-bad option honestly rather than
    # presenting a drop/break-riddled solution as optimal.
    n_drops = len(best.drop_sites)
    n_breaks = sum(1 for f in best.flags if f.startswith("2npS BREAK"))
    if n_drops + n_breaks >= max(2, n // 3):
        result.warnings.append(
            f"This line does not fit Gypsy mechanics cleanly "
            f"({n_drops} managed drop(s), {n_breaks} 2npS break(s)). "
            f"Showing the least-bad option with its flags."
        )

    # Phase 2 (disabled by default): APPLY the enabled ornament families to a
    # copy of the solution — the slurred version lives in result.ornamented,
    # the all-picked phase-1 line above stays untouched.
    if config.ornament_engine_enabled:
        from scripts.fingering.ornaments import apply_ornaments
        result.ornamented = apply_ornaments(result, context, config)
        result.ornaments = result.ornamented.events

    return result


def _layout_candidates(notes: List[Note], config: FingeringConfig,
                       hard_root_pin: bool = True):
    """Per distinct pitch (ascending), the (string, fret) placements a config
    admits — the root pin applied as a hard FILTER when requested."""
    pitches = sorted({nt.midi for nt in notes})
    cands = []
    for m in pitches:
        pls = [(p.string, p.fret) for p in candidate_placements(m, config)]
        if hard_root_pin and config.root_pin is not None:
            pin_pc, pin_strings = config.root_pin
            if m % 12 == pin_pc:
                pls = [pl for pl in pls if pl[0] in pin_strings]
        cands.append(pls)
    return pitches, cands


def count_layouts(line: List[dict], context: Optional[dict] = None,
                  config: Optional[FingeringConfig] = None,
                  hard_root_pin: bool = True) -> int:
    """How many distinct layouts :func:`enumerate_fingerings` would visit for
    this line/config — the product of the per-pitch candidate counts, with no
    DP run. 0 when some pitch has no admissible placement (the enumeration
    would return nothing). Lets a caller plan a time budget before searching.
    """
    config = config or default_config()
    context = context or {}
    if not line:
        return 0
    notes = build_notes(line, config, context)
    _pitches, cands = _layout_candidates(notes, config, hard_root_pin)
    n_layouts = 1
    for pls in cands:
        n_layouts *= len(pls)
    return n_layouts


def enumerate_fingerings(line: List[dict], context: Optional[dict] = None,
                         config: Optional[FingeringConfig] = None,
                         hard_root_pin: bool = True,
                         max_layouts: int = 20000) -> List[FingeringResult]:
    """EVERY distinct string/fret layout of a fixed line, best-cost first.

    Where :func:`optimize_fingering` returns the single optimum, this lists all
    layouts the config admits (fret window, string set, open-string rule): for
    each assignment of one (string, fret) per distinct pitch — repeated pitches
    keep one placement, the consistency convention — the DP still derives the
    optimal picking/anchors, so each layout is reported at its own best cost.

    ``hard_root_pin``: a configured ``root_pin`` becomes a FILTER (root-pitch-
    class notes only on the shape's root strings) instead of a soft charge, so
    every listed layout really belongs to the position.

    Raises ``ValueError`` when the layout space exceeds ``max_layouts`` (a
    window too wide to enumerate — use :func:`optimize_fingering` there).
    """
    import itertools

    config = config or default_config()
    context = context or {}
    verify_conventions(config)
    if not line:
        raise ValueError("empty line")
    density = context.get("density", "quarter")
    notes = build_notes(line, config, context)
    n = len(notes)

    pitches, cands = _layout_candidates(notes, config, hard_root_pin)
    if any(not pls for pls in cands):
        return []
    n_layouts = 1
    for pls in cands:
        n_layouts *= len(pls)
    if n_layouts > max_layouts:
        raise ValueError(f"{n_layouts} layouts — too many to enumerate")

    out: List[FingeringResult] = []
    for combo in itertools.product(*cands):
        try:
            layers, nodes = _run_dp(notes, config, density, pinned=dict(zip(pitches, combo)))
        except ValueError:
            continue
        terms = [(cost, key, idx) for key, entries in layers[n - 1].items()
                 for idx, (cost, _b) in enumerate(entries)]
        if not terms:
            continue
        _c, key, idx = min(terms, key=lambda t: t[0])
        path = _backtrack(layers, nodes, key, idx, n)
        relabel_fingers(path, config)
        out.append(FingeringResult(notes=notes, best=_analyze(path, config, density),
                                   alternate=None, context=context, config=config))
    out.sort(key=lambda r: r.best.total_cost)
    return out
