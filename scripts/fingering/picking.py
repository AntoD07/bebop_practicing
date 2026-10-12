"""Picking derivation rules, the convention sanity check, and the U-invariant.

Picking is DERIVED from the fingering, never chosen freely:

  H1. Every string-change (entry) note is a rest-stroke downstroke D.
  H2. Within one string, strokes after the entry D may mix D/U, but: no U on
      beat 1 (beat 3 = soft penalty), U never *starts* a string, and after a U
      the next same-string note goes back to D (up-down alternation, never U-U).
  H3. Phase 1 is 100% picked — no legato, no inserted/deleted/tied pitches.
  H4. A phrase opens on D — except an OFF-BEAT pickup (e.g. the "&" of 4),
      which may be a U so the alternation lands the next downbeat on D.

INVARIANT (v2 — same-string up-down alternation is idiomatic, per the player):
  * a U never arrives on a string change (H1) — an off-beat pickup opening a
    phrase is not a string change (H4),
  * a U never lands on beat 1,
  * two Us never follow each other on the same string.
A U therefore serves one of two purposes: the parity fix before a descending
crossing (U->D), or natural alternation within a string. String entries being
forced to D still guards the degenerate all-sweep/U-spray solutions.
"""

from __future__ import annotations

from typing import List, Optional

from scripts.fingering.config import FingeringConfig, default_config
from scripts.fingering.pitch import Note
from scripts.fingering.costs import (
    DOWN, UP, PlacedNote, classify_transition, edge_cost,
)


class ConventionError(RuntimeError):
    """Raised when the string/stroke conventions in the cost model are inverted."""


def _pn(string: int, fret: int, stroke: str, beat: int = 2, run_len: int = 1) -> PlacedNote:
    """Tiny PlacedNote factory for the sanity check.

    All fixtures share ONE hand anchor (fret 5) — the sweep convention is a
    picking-hand property and must be tested inside a stable position, without
    incurring shift/relocation costs.
    """
    note = Note(index=0, midi=60, beat=beat)
    return PlacedNote(
        note=note, string=string, fret=fret, anchor=5, finger=max(1, fret - 4),
        is_stretch=False, stroke=stroke, run_len=run_len,
        is_rest_stroke=(stroke == DOWN),
    )


def verify_conventions(config: Optional[FingeringConfig] = None) -> None:
    """Halt before any search if the convention/cost model is inverted.

    Checks, against the *actual* cost function:
      1. An ascending one-note-per-string sweep (str3->str2->str1), all D, must
         be free (no "drop", total cost <= 0).
      2. A descending crossing (str2->str3) arriving D->D must be penalised
         (a "drop" contribution appears).
      3. The same descending crossing arriving U->D must NOT be penalised.

    The check verifies the PICKING convention, so placement-context costs are
    neutralised: the fixtures live at frets 7-8, which a position's fret window
    or root pin would otherwise charge (overflow/pin), falsely tripping the
    "sweep must be free" probe.
    """
    cfg = (config or default_config()).with_overrides(fret_window=None,
                                                      string_fret_windows=None,
                                                      root_pin=None)

    # 1) ascending sweep: str3 -> str2 -> str1, all downstrokes.
    a = _pn(3, 7, DOWN)
    b = _pn(2, 8, DOWN)
    c = _pn(1, 8, DOWN)
    total = 0.0
    for prev, cur in ((a, b), (b, c)):
        cost, contribs = edge_cost(prev, cur, cfg)
        if any(tag == "drop" for tag, _ in contribs):
            raise ConventionError(
                "Ascending sweep (lower-numbered string) was penalised as a drop "
                "— the string-direction convention is INVERTED. Halting."
            )
        total += cost
    if total > 0:
        raise ConventionError(
            f"Ascending economy sweep is not free (total={total}). Halting."
        )

    # 2) descending crossing str2 -> str3 arriving D->D must be a drop.
    d_prev = _pn(2, 8, DOWN)
    d_cur = _pn(3, 7, DOWN)
    _, contribs = edge_cost(d_prev, d_cur, cfg)
    if not any(tag == "drop" for tag, _ in contribs):
        raise ConventionError(
            "Descending crossing arriving D->D was NOT penalised — convention "
            "inverted or drop_cost misconfigured. Halting."
        )

    # 3) same crossing arriving U->D (parity fix) must be clean.
    u_prev = _pn(2, 8, UP)
    u_cur = _pn(3, 7, DOWN)
    _, contribs = edge_cost(u_prev, u_cur, cfg)
    if any(tag == "drop" for tag, _ in contribs):
        raise ConventionError(
            "U->D descending arrival still penalised as a drop — the parity fix "
            "is not being credited. Halting."
        )


def entry_strokes(descending: bool, config: FingeringConfig) -> List[str]:
    """Legal strokes for a string-CHANGE (entry) note.

    H1: always a rest-stroke D. If allow_up_arrival is set (non-default) a U
    arrival on a descending crossing is also legal (penalised in the cost).
    """
    if descending and config.allow_up_arrival:
        return [DOWN, UP]
    return [DOWN]


def phrase_start_strokes(note: Note) -> List[str]:
    """Legal strokes for the first note of a phrase (line start / after a rest).

    H4: D, plus U when the note is an off-beat pickup — playing the "&" up lets
    the alternation bring the downbeat that follows back to D.
    """
    if note.onset % 1 != 0:
        return [DOWN, UP]
    return [DOWN]


def same_string_strokes(beat: int) -> List[str]:
    """Legal strokes for a same-string continuation note.

    Default D; U allowed except on beat 1 (H2). Whether a U is *actually* legal
    also depends on the invariant (must be immediately followed by a descending
    crossing) — that is enforced structurally in the DP transition step.
    """
    if beat == 1:
        return [DOWN]
    return [DOWN, UP]


def find_invariant_violations(placed: List[PlacedNote]) -> List[int]:
    """Return indices of upstrokes violating INVARIANT v2.

    Violations: a U arriving on a string change, a U on beat 1, a U opening a
    phrase on the beat, or a U immediately followed by another U on the same
    string. An empty list means the invariant holds (a U is a parity fix,
    in-string alternation, or an off-beat pickup).
    """
    bad: List[int] = []
    for i, pn in enumerate(placed):
        if pn.stroke != UP:
            continue
        if pn.beat == 1:
            bad.append(i)
            continue
        if i == 0 or pn.note.phrase_start:
            if UP not in phrase_start_strokes(pn.note):  # on-beat phrase start
                bad.append(i)
                continue
        elif placed[i - 1].string != pn.string:  # U on a string entry
            bad.append(i)
            continue
        if (i + 1 < len(placed) and placed[i + 1].string == pn.string
                and placed[i + 1].stroke == UP):
            bad.append(i)
    return bad
