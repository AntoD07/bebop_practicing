"""The per-transition cost model, shared by the DP and the reporting pass.

Keeping the cost in one place guarantees the number the solver optimises is the
same number we later print and break down by contributor — no drift between
"what was searched" and "what was reported".

CONVENTIONS (the crux — verified at runtime by
:func:`scripts.fingering.picking.verify_conventions` before any search):

  * Strings 1..6; string 1 = high E (thinnest / highest), string 6 = low E.
  * A downstroke (D) is a REST STROKE: the pick travels toward string 1 and
    comes to rest on the next-thinner string.
  * "Ascending in pitch across strings" = moving to a LOWER-numbered string
    (str3 -> str2 -> str1). Consecutive rest-stroke downstrokes across such a
    crossing are the free "economy sweep": D-D-D, zero cost.
  * A "descending crossing" = moving to a HIGHER-numbered string (str1 -> str2).
    Arriving there D->D is the penalised "drop"; arriving U->D (the pick already
    travelling up, so it falls naturally onto the thicker string) is clean.

CONSEQUENCE (where upstrokes live): every string ENTRY is a rest-stroke D —
that is inviolable. Within a string, up-down alternation (D-U) is the natural
motion at this pacing (``same_string_dd_penalty`` > ``u_cost``), EXCEPT before
an ascending crossing where staying on D earns the economy-sweep bonus. A U
therefore appears in exactly two roles: (a) the parity fix that turns a
would-be D->D descending drop into a clean U->D, and (b) same-string
alternation. A U never starts a string and never lands on beat 1 — the one
exception is an off-beat pickup opening a phrase, which may be a U so the
alternation brings the following downbeat back to D.

DOWNBEATS (beats 1 and 3) want a D. Beat 1 is hard (a U there is illegal);
beat 3 is soft (``beat3_penalty``). When alternation would put a U on a
downbeat, repeating the downstroke (same-string D-D) is the accepted fix,
priced slightly above a plain D-D (``downbeat_dd_penalty``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from scripts.fingering.config import FingeringConfig
from scripts.fingering.pitch import Note

DOWN = "D"
UP = "U"
PULL = "po"   # pull-off (phase 2 only)
HAMMER = "h"  # hammer-on (phase 2 only)

DOWNBEATS = (1, 3)  # beats that want a downstroke (beat 1 hard, beat 3 soft)

# Max comfortable fret gap between consecutive notes per finger pair
# (unordered, index..pinky = 1..4). Same finger reused = 0 (any move is a jump);
# anatomically bound 3-4 barely spans 1 fret; independent 1-4 spans 4.
_PAIR_SPAN = {
    (1, 1): 0, (2, 2): 0, (3, 3): 0, (4, 4): 0,
    (1, 2): 2, (1, 3): 3, (1, 4): 4,
    (2, 3): 2, (2, 4): 3,
    (3, 4): 1,
}

# RELAXED fret gap per pair — the spacing a hand produces with no effort.
# Used only to rank finger choices within a string run (deviation is a mild
# preference, span violations above are the hard physics).
_PAIR_IDEAL = {
    (1, 1): 0, (2, 2): 0, (3, 3): 0, (4, 4): 0,
    (1, 2): 1, (1, 3): 2, (1, 4): 3,
    (2, 3): 1, (2, 4): 2,
    (3, 4): 1,
}


@dataclass
class PlacedNote:
    """A note committed to a string/fret with a derived stroke and hand anchor."""

    note: Note
    string: int
    fret: int
    anchor: Optional[int]     # index-finger fret of the hand position
    finger: int               # 0 = open, 1..4 = index..pinky, 5 = stretch
    is_stretch: bool
    stroke: str               # "D" / "U" (phase 1); "po"/"h" only in phase-2 output
    run_len: int              # 1..3 (capped): consecutive notes on this string
    is_rest_stroke: bool      # a D that comes to rest on the next-thinner string

    @property
    def beat(self) -> int:
        return self.note.beat


def classify_transition(prev: PlacedNote, cur: PlacedNote) -> dict:
    """Describe the string move from ``prev`` to ``cur``."""
    return {
        "same_string": cur.string == prev.string,
        "ascending_cross": cur.string < prev.string,   # up in pitch, toward str 1
        "descending_cross": cur.string > prev.string,  # down in pitch, toward str 6
    }


def _sweep_bonus_applies(cur: PlacedNote, config: FingeringConfig) -> bool:
    if config.sweep_bonus_beats is None:
        # "accent on the beat": any note landing on an integer beat. On the
        # pure quarter grid that is every note; on an eighth grid, the on-beats.
        return cur.note.onset % 1 == 0
    return cur.beat in config.sweep_bonus_beats


def _overflow(pn: PlacedNote, config: FingeringConfig) -> int:
    """Frets by which a placement pokes outside the (soft) position window
    of its string (slanted shapes have one window per string)."""
    win = config.fret_window_for(pn.string)
    if not win or pn.fret == 0:
        return 0
    lo, hi = win
    return max(0, lo - pn.fret, pn.fret - hi)


def _root_pin_charge(pn: PlacedNote, config: FingeringConfig) -> float:
    """Soft root pin: a key-root note off the shape's root strings is charged."""
    if config.root_pin is None:
        return 0.0
    pin_pc, pin_strings = config.root_pin
    if pn.note.midi % 12 == pin_pc and pn.string not in pin_strings:
        return config.root_pin_cost
    return 0.0


def initial_cost(first: PlacedNote, config: FingeringConfig) -> Tuple[float, List[Tuple[str, float]]]:
    contribs: List[Tuple[str, float]] = []
    cost = 0.0
    if first.stroke == UP:  # an off-beat pickup opening on a U
        cost += config.u_cost
        contribs.append(("u_cost", config.u_cost))
    if first.is_stretch:
        cost += config.stretch_cost
        contribs.append(("stretch", config.stretch_cost))
    if first.fret == 0:
        cost += config.open_string_cost
        contribs.append(("open_string", config.open_string_cost))
    over = _overflow(first, config)
    if over:
        cost += config.window_overflow_cost * over
        contribs.append(("box_overflow", config.window_overflow_cost * over))
    pin = _root_pin_charge(first, config)
    if pin:
        cost += pin
        contribs.append(("root_pin", pin))
    return cost, contribs


def edge_cost(prev: PlacedNote, cur: PlacedNote, config: FingeringConfig,
              density: str = "quarter") -> Tuple[float, List[Tuple[str, float]]]:
    """Cost of playing ``cur`` immediately after ``prev``.

    Returns ``(cost, contributions)`` where contributions is a list of
    ``(tag, amount)`` for the flags/top-contributor report.
    """
    rel = classify_transition(prev, cur)
    contribs: List[Tuple[str, float]] = []
    cost = 0.0

    # --- Phrase break (note after a rest): the hand repositions for free and
    # the pick re-enters fresh — no shift/reach/crossing/alternation charges.
    if cur.note.phrase_start:
        if cur.stroke == UP:  # an off-beat pickup re-entering on a U
            cost += config.u_cost
            contribs.append(("u_cost", config.u_cost))
        if cur.is_stretch:
            cost += config.stretch_cost
            contribs.append(("stretch", config.stretch_cost))
        if cur.fret == 0:
            cost += config.open_string_cost
            contribs.append(("open_string", config.open_string_cost))
        return cost, contribs

    # --- Hand shift: lateral routing isn't free, just cheaper than a hot drop.
    # Beyond the per-fret distance, each anchor CHANGE is a hand relocation —
    # a flat event cost keeps phrases in one position when possible.
    if prev.anchor is not None and cur.anchor is not None:
        d = abs(cur.anchor - prev.anchor)
        if d:
            amt = d * config.shift_cost + config.shift_event_cost
            cost += amt
            contribs.append(("shift", amt))

    # --- Finger-pair span: consecutive fretted notes are played by two fingers
    # of ONE hand; each pair has a maximum comfortable fret gap. Every fret
    # beyond it is charged — this is the general inter-finger penalty.
    if prev.fret > 0 and cur.fret > 0 and prev.finger and cur.finger:
        # The 5th "finger" is a pinky stretch — pair-wise it behaves as the pinky.
        f1 = min(4, prev.finger)
        f2 = min(4, cur.finger)
        span = _PAIR_SPAN[(min(f1, f2), max(f1, f2))]
        gap = abs(cur.fret - prev.fret)
        if gap > span:
            amt = config.finger_span_cost * (gap - span)
            cost += amt
            contribs.append(("finger_span", amt))

    # --- Physical reach between the two note positions (Euclidean on the neck).
    # Only fretted-to-fretted counts a horizontal span (open strings need no
    # fretting hand). We charge only the distance BEYOND a free hand-span, so
    # normal boxes/sweeps are free and only wide leaps (e.g. 8 frets on one
    # string) are penalised.
    dfret = abs(cur.fret - prev.fret) if (prev.fret > 0 and cur.fret > 0) else 0
    dstr = abs(cur.string - prev.string)
    dist = (dfret ** 2 + (config.string_distance * dstr) ** 2) ** 0.5
    over = dist - config.free_reach
    if over > 0:
        amt = config.reach_cost * over
        cost += amt
        contribs.append(("reach", amt))

    # --- Crossing costs.
    if rel["descending_cross"]:
        if cur.stroke == DOWN:
            if prev.stroke == DOWN:
                amt = config.drop_cost * config.density_scale(density)
                # Per-cell exception (config.cell_drop_scale): both notes in the
                # cell, or leaving the shared pivot (the cell's own first note).
                if cur.note.cell is not None and (
                        prev.note.cell == cur.note.cell or prev.note.role == "pivot"):
                    amt *= config.drop_scale_for(cur.note.cell)
                cost += amt
                contribs.append(("drop", amt))       # a managed drop at quarter pacing
            # prev.stroke == UP -> clean U->D parity arrival, no drop cost.
        elif cur.stroke == UP:
            # Only reachable when allow_up_arrival is True.
            amt = config.up_arrival_penalty
            cost += amt
            contribs.append(("up_arrival", amt))
    elif rel["ascending_cross"]:
        # Economy sweep: only a continuing DOWN motion within ONE hand position
        # sweeps — a crossing that relocates the anchor is not a sweep and
        # earns nothing. Reward the accent when it lands on a beat.
        anchor_stable = (prev.anchor is None or cur.anchor is None
                         or cur.anchor == prev.anchor)
        if prev.stroke == DOWN and anchor_stable and _sweep_bonus_applies(cur, config):
            cost -= config.sweep_bonus
            contribs.append(("sweep_bonus", -config.sweep_bonus))
    elif rel["same_string"]:
        # Same-string D->D is stiffer than natural up-down alternation at this
        # pacing; the solver alternates D-U unless a sweep (or beat 1) says not to.
        # A D-D that lands a downbeat on D is the parity fix, priced a bit higher.
        if prev.stroke == DOWN and cur.stroke == DOWN:
            if cur.beat in DOWNBEATS:
                cost += config.downbeat_dd_penalty
                contribs.append(("downbeat_dd", config.downbeat_dd_penalty))
            else:
                cost += config.same_string_dd_penalty
                contribs.append(("same_str_dd", config.same_string_dd_penalty))

    # --- Upstroke bookkeeping.
    if cur.stroke == UP:
        cost += config.u_cost
        contribs.append(("u_cost", config.u_cost))
        if cur.beat == 3:
            cost += config.beat3_penalty
            contribs.append(("beat3", config.beat3_penalty))

    # --- Open strings: mid-line they break the hand position; keep them rare.
    if cur.fret == 0:
        cost += config.open_string_cost
        contribs.append(("open_string", config.open_string_cost))

    # --- Soft position window: poking outside the box is playable but charged.
    over = _overflow(cur, config)
    if over:
        cost += config.window_overflow_cost * over
        contribs.append(("box_overflow", config.window_overflow_cost * over))

    # --- Soft root pin: key roots prefer the shape's root strings.
    pin = _root_pin_charge(cur, config)
    if pin:
        cost += pin
        contribs.append(("root_pin", pin))

    # --- Stretch (5-fret extension), always flagged.
    if cur.is_stretch:
        cost += config.stretch_cost
        contribs.append(("stretch", config.stretch_cost))

    # --- 2npS break: charged once, when a string run first exceeds two notes.
    if rel["same_string"] and prev.run_len == config.expected_notes_per_string:
        cost += config.break_cost
        contribs.append(("break_2nps", config.break_cost))

    return cost, contribs


def relabel_fingers(placed: List[PlacedNote], config: FingeringConfig) -> None:
    """Reassign left-hand fingers from finger-PAIR physics (post-search pass).

    The DP's rigid ``finger = fret - anchor + 1`` box model cannot express
    standard fingerings like 1-2-4 over a whole-step + whole-step 3-notes-per-
    string group (frets X, X+2, X+4) — it derives 1-3-stretch instead. Here the
    fingers for the FIXED placements are re-derived by a tiny DP minimising, in
    order: pair-span excess (the hard physics, ``_PAIR_SPAN``), same-string
    deviation from each pair's relaxed gap (``_PAIR_IDEAL``), distance from the
    anchor-box prior (keeps in-position fingerings stable), and lower fingers.
    Fingers may not cross on one string. Stretch flags are recomputed as "this
    note participates in a pair beyond its span". Mutates ``placed`` in place.
    """
    n = len(placed)
    if n == 0:
        return
    choices = [[0] if p.fret == 0 else [1, 2, 3, 4] for p in placed]

    # A note that ENTERS a multi-note same-string run frames the hand for that
    # run: entered index-first when the run ascends in fret, pinky-first when it
    # descends (standard hand-framing; single-note strings are exempt).
    run_entry_pref = [0] * n  # 0 = none, +1 = prefer low fingers, -1 = prefer high
    for i, p in enumerate(placed):
        if p.fret == 0:
            continue
        starts_run = i == 0 or placed[i - 1].string != p.string
        if starts_run and i + 1 < n and placed[i + 1].string == p.string \
                and placed[i + 1].fret > 0 and placed[i + 1].fret != p.fret:
            run_entry_pref[i] = 1 if placed[i + 1].fret > p.fret else -1

    def unary(i: int, f: int) -> float:
        p = placed[i]
        c = 0.001 * f  # all else equal, lower fingers (index-first re-anchoring)
        if run_entry_pref[i] == 1:
            c += 0.05 * (f - 1)
        elif run_entry_pref[i] == -1:
            c += 0.05 * (4 - f)
        # The anchor-box prior keeps in-position fingerings stable — but ONLY
        # while the hand stays put. At an anchor change (or the line start) the
        # hand re-anchors freely, index leading.
        if (p.fret > 0 and p.anchor is not None and i > 0
                and placed[i - 1].anchor == p.anchor):
            prior = min(4, max(1, p.fret - p.anchor + 1))
            c += 0.01 * abs(f - prior)
        return c

    def pair(i: int, f1: int, f2: int) -> Optional[float]:
        prev, cur = placed[i - 1], placed[i]
        c = unary(i, f2)
        if (cur.note.phrase_start or prev.fret == 0 or cur.fret == 0
                or not f1 or not f2):
            return c  # no fretting-hand pair across opens / phrase breaks
        gap = abs(cur.fret - prev.fret)
        same = cur.string == prev.string
        if same and cur.fret != prev.fret:
            # Fingers may not cross on a string; same finger = a slide (charged).
            if (cur.fret > prev.fret and f2 < f1) or (cur.fret < prev.fret and f2 > f1):
                return None
            if f1 == f2:
                c += 1.0 * gap
        key = (min(f1, f2), max(f1, f2))
        if gap > _PAIR_SPAN[key]:
            c += 1000.0 * (gap - _PAIR_SPAN[key])  # hard physics dominates
        if same:
            c += 1.0 * abs(gap - _PAIR_IDEAL[key])  # relaxed-spacing preference
        return c

    dp = [{f: (unary(0, f), 0) for f in choices[0]}]
    for i in range(1, n):
        row = {}
        for f2 in choices[i]:
            best = None
            for f1, (c1, _) in dp[i - 1].items():
                pc = pair(i, f1, f2)
                if pc is None:
                    continue
                if best is None or c1 + pc < best[0]:
                    best = (c1 + pc, f1)
            if best is not None:
                row[f2] = best
        if not row:  # no consistent assignment (shouldn't happen) — bail out
            return
        dp.append(row)

    f = min(dp[-1], key=lambda k: dp[-1][k][0])
    fingers = [f]
    for i in range(n - 1, 0, -1):
        f = dp[i][f][1]
        fingers.append(f)
    fingers.reverse()

    for p, fg in zip(placed, fingers):
        p.finger = fg
    for i, p in enumerate(placed):
        if p.fret == 0:
            p.is_stretch = False
            continue
        stretch = False
        for j in (i - 1, i + 1):
            if 0 <= j < n and placed[j].fret > 0 and placed[j].finger:
                if placed[max(i, j)].note.phrase_start:
                    continue
                key = (min(p.finger, placed[j].finger), max(p.finger, placed[j].finger))
                if abs(p.fret - placed[j].fret) > _PAIR_SPAN[key]:
                    stretch = True
        p.is_stretch = stretch
