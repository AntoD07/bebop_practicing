"""Definition-of-done tests for the fingering optimizer.

Run from the repo root:

    python -m scripts.fingering.tests

Each test prints the full per-note table (via the report) and then asserts the
musical properties the spec requires. The convention sanity check runs first;
the U-invariant is asserted on every test's output.
"""

from __future__ import annotations

from typing import List

from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering, FingeringResult
from scripts.fingering.picking import verify_conventions, find_invariant_violations
from scripts.fingering.costs import UP
from scripts.fingering.render import format_report
from scripts.fingering import cell_bridge


class TestFailure(AssertionError):
    pass


def _check(cond: bool, msg: str):
    if not cond:
        raise TestFailure(msg)


def _n_up(result: FingeringResult) -> int:
    return sum(1 for p in result.best.placed if p.stroke == UP)


def _n_desc_cross(result: FingeringResult) -> int:
    p = result.best.placed
    return sum(1 for i in range(len(p) - 1) if p[i + 1].string > p[i].string)


def _has_flag(result: FingeringResult, needle: str) -> bool:
    return any(needle in f for f in result.best.flags)


def _invariant_ok(result: FingeringResult) -> List[int]:
    return find_invariant_violations(result.best.placed)


def _banner(name: str, blurb: str):
    print("\n" + "#" * 74)
    print(f"# {name}: {blurb}")
    print("#" * 74)


# --------------------------------------------------------------------------- #
def test_T1():
    _banner("T1", "Ascending Dm arpeggio, one note per string -> D-D-D sweep")
    # D3, A3, D4, F4 — ascending Dm arpeggio.
    line = [
        {"pitch": "D3", "role": "root", "degree": "1", "cell": "Dm arp"},
        {"pitch": "A3", "role": "5", "degree": "5", "cell": "Dm arp"},
        {"pitch": "D4", "role": "root", "degree": "1", "cell": "Dm arp"},
        {"pitch": "F4", "role": "b3", "degree": "b3", "cell": "Dm arp"},
    ]
    ctx = {"key": "Dm", "chords": [{"start_beat": 0, "symbol": "Dm"}]}
    r = optimize_fingering(line, ctx)
    print(format_report(r))
    _check(_n_up(r) == 0, f"T1 expected zero upstrokes, got {_n_up(r)}")
    _check(not _has_flag(r, "drop"), "T1 must have no drops")
    _check(not _has_flag(r, "2npS BREAK"), "T1 must have no breaks")
    _check(_invariant_ok(r) == [], "T1 invariant violated")
    print(">>> T1 PASS")


def test_T2():
    _banner("T2", "Descending 2-octave D melodic-minor run -> parity-U / routing")
    # D melodic minor (asc form) descending across two octaves.
    dmm = [74, 73, 71, 69, 67, 65, 64, 62, 61, 59, 57, 55, 53, 52, 50]
    line = [{"pitch": m, "role": "scale"} for m in dmm]
    ctx = {"key": "Dm", "chords": [{"start_beat": 0, "symbol": "Dm"}]}
    r = optimize_fingering(line, ctx)
    print(format_report(r))
    nu, nd = _n_up(r), _n_desc_cross(r)
    _check(_invariant_ok(r) == [], "T2 invariant violated")
    # v2 picking: Us serve parity fixes AND in-string alternation, so the cap is
    # descending crossings + same-string continuations (never string entries).
    n_same = sum(1 for i in range(len(r.best.placed) - 1)
                 if r.best.placed[i + 1].string == r.best.placed[i].string)
    _check(nu <= nd + n_same, f"T2 U count {nu} exceeds legal sites {nd + n_same}")
    routing = _has_flag(r, "ROUTING")
    _check(_has_flag(r, "PARITY") or routing,
           "T2 expected a parity-U fix and/or lateral routing")
    print(f">>> T2 PASS (U={nu}, desc-crossings={nd}, routing={routing})")


def test_T3():
    _banner("T3", "ii-V-i in A minor (Bm7b5-E7 resolving to Am) from the cell DB")
    ii = cell_bridge.first_cell("Locrian")
    V = cell_bridge.first_cell("Myxolidian")
    i = cell_bridge.first_cell("MinorResolutions")
    # Resolution cells are DOMINANT-based: degrees spell from the resolving V7
    # (E7 -> Am), so the resolution cell's root is E, not the tonic A.
    ii["root"], V["root"], i["root"] = "B", "E", "E"
    i["is_resolution"] = True
    cells = [ii, V, i]
    line = cell_bridge.build_pitch_line(cells)
    cell_len = len(ii["degrees"])
    # One "bar" per cell so each chord's beat 1 is exact.
    ctx = {
        "key": "Am",
        "beats_per_bar": cell_len,
        "chords": [
            {"start_beat": 0, "symbol": "Bm7b5"},
            {"start_beat": cell_len, "symbol": "E7"},
            {"start_beat": 2 * cell_len, "symbol": "E7"},  # dominant-based resolution bar
        ],
    }
    cfg = FingeringConfig(beats_per_bar=cell_len)
    r = optimize_fingering(line, ctx, cfg)
    print(format_report(r))
    _check(_invariant_ok(r) == [], "T3 invariant violated")
    # Beat 1 of each chord (first note of each cell) must be a downstroke.
    for start in (0, cell_len, 2 * cell_len):
        p = r.best.placed[start]
        _check(p.stroke == "D", f"T3 chord start note {start} not a downstroke")
    print(">>> T3 PASS (each chord's beat 1 is a downstroke; breaks flagged if any)")


def test_T5():
    _banner("T5", "Ascending arpeggio cascade (Am6 -> B°7 climb, 2npS) -> all sweeps")
    # Am6 (A C E F#) then continuing the climb; pure ascending cascade.
    climb = [45, 48, 52, 54, 57, 60, 64, 66]  # A2 C3 E3 F#3 A3 C4 E4 F#4
    line = [{"pitch": m, "role": "arp"} for m in climb]
    ctx = {"key": "Am", "chords": [{"start_beat": 0, "symbol": "Am6"}]}
    r = optimize_fingering(line, ctx)
    print(format_report(r))
    _check(_n_up(r) == 0, f"T5 any upstroke = fail (got {_n_up(r)})")
    _check(not _has_flag(r, "drop"), "T5 must have no drops")
    _check(_invariant_ok(r) == [], "T5 invariant violated")
    has_sweep = any(t == "sweep_bonus" for t, _ in r.best.contributions)
    _check(has_sweep, "T5 expected sweep bonuses on the ascending crossings")
    print(">>> T5 PASS (zero U, sweep bonuses present)")


def test_T4():
    _banner("T4", "Phase-2 APPLY: upper-neighbor turn (pick-hammer-pull, 8h10p8)")
    # E4 is the final resolution (a chord tone): the turn fires there — the
    # target keeps its pick, then upper neighbour hammered + pulled back,
    # all inside the target's beat on ONE string (no crossing touched).
    line = [
        {"pitch": "C5", "degree": "b3", "cell": "desc run"},
        {"pitch": "B4", "degree": "9", "cell": "desc run"},
        {"pitch": "A4", "degree": "1", "cell": "desc run"},
        {"pitch": "E4", "degree": "5", "role": "resolution", "cell": "desc run"},
    ]
    ctx = {"key": "Am", "chords": [{"start_beat": 0, "symbol": "Am"}]}
    pinned = {72: (1, 8), 71: (1, 7), 69: (1, 5), 64: (2, 5)}
    cfg = FingeringConfig(ornament_engine_enabled=True)
    r = optimize_fingering(line, ctx, cfg, pinned=pinned)
    print(format_report(r))
    _check(_invariant_ok(r) == [], "T4 invariant violated (phase-1 solution)")
    o = r.ornamented
    _check(o is not None, "T4 expected an ornamented voicing")
    _check(len(o.events) == 1 and o.events[0]["family"] == "turn",
           f"T4 expected one turn, got {[e['family'] for e in o.events]}")
    _check(len(o.placed) == len(r.best.placed) + 2,
           "T4 turn must insert exactly two grace notes")
    tail = o.placed[-3:]
    _check([p.stroke for p in tail][1:] == ["h", "po"],
           f"T4 turn must be pick-hammer-pull, got {[p.stroke for p in tail]}")
    _check(tail[0].stroke in ("D", "U"), "T4 target must keep its pick attack")
    _check(tail[0].string == tail[1].string == tail[2].string,
           "T4 turn must stay on one string")
    _check(tail[1].fret == tail[0].fret + cfg.turn_fret_interval
           and tail[2].fret == tail[0].fret,
           f"T4 expected {tail[0].fret}h{tail[0].fret+2}p{tail[0].fret}, got "
           f"{tail[0].fret}h{tail[1].fret}p{tail[2].fret}")
    _check(tail[1].note.is_grace and tail[2].note.is_grace,
           "T4 inserted notes must be graces")
    _check(len(r.best.placed) == 4 and r.best.placed[-1].stroke == "D",
           "T4 phase-1 (all-picked) must stay untouched")
    _check(o.picks_after == o.picks_before,
           "T4 the turn is mechanically idle — pick count unchanged")
    _check(any("strip them above" in f for f in o.flags),
           "T4 expected the tempo honesty flag")
    _check(not [f for f in o.flags if f.startswith("MECHANICS")],
           f"T4 ornament mechanics violated: {o.flags}")
    print(">>> T4 PASS (turn applied on the resolution; phase-1 untouched)")


def _strokes(r: FingeringResult) -> List[str]:
    return [p.stroke for p in r.best.placed]


def test_T6():
    _banner("T6", "Off-beat pickup (&4) into beat 1 on the same string -> U-D")
    # G4 on the "&" of 4, then A4 on beat 1, both on the B string.
    pinned = {67: (2, 8), 69: (2, 10), 71: (1, 7), 72: (1, 8)}
    pitches = [67, 69, 71, 72]
    ctx = {"key": "G", "density": "eighth", "chords": []}
    line = [{"pitch": m, "start": 3.5 + 0.5 * i} for i, m in enumerate(pitches)]
    r = optimize_fingering(line, ctx, pinned=pinned)
    print(format_report(r))
    _check(_strokes(r)[:2] == ["U", "D"],
           f"T6 off-beat pickup should be U into a D downbeat, got {_strokes(r)}")
    _check(_invariant_ok(r) == [], "T6 invariant violated")
    # The same line starting ON beat 4: an on-beat phrase start stays D.
    line = [{"pitch": m, "start": 3.0 + 0.5 * i} for i, m in enumerate(pitches)]
    r2 = optimize_fingering(line, ctx, pinned=pinned)
    _check(_strokes(r2)[0] == "D", "T6 an on-beat phrase start must be D")
    print(">>> T6 PASS (pickup U on the '&', downbeat D; on-beat start stays D)")


def test_T7():
    _banner("T7", "Downbeat D-D is priced above a plain D-D -> moved off the downbeat")
    cfg = FingeringConfig()
    ctx = {"key": "G", "density": "eighth", "chords": []}
    # String change on "&4" then beat 1 on the same string: the only way to a
    # D downbeat is D-D onto beat 1 — charged downbeat_dd, not same_str_dd.
    pinned = {69: (2, 10), 71: (1, 7), 72: (1, 8), 74: (1, 10)}
    line = [{"pitch": m, "start": 3.0 + 0.5 * i} for i, m in enumerate([69, 71, 72, 74])]
    r = optimize_fingering(line, ctx, cfg, pinned=pinned)
    print(format_report(r))
    _check(r.best.placed[2].stroke == "D", "T7 beat 1 must be a downstroke")
    tags = dict(r.best.contributions)
    _check(tags.get("downbeat_dd") == cfg.downbeat_dd_penalty,
           f"T7 expected one downbeat_dd charge, got {r.best.contributions}")
    # Entering the e string on "&3" with three notes before beat 1: the repeated
    # downstroke goes on beat 4 (plain D-D) so beat 1 arrives by alternation.
    pinned = {67: (2, 8), 71: (1, 7), 72: (1, 8), 74: (1, 10), 76: (1, 12)}
    line = [{"pitch": m, "start": 2.0 + 0.5 * i}
            for i, m in enumerate([67, 71, 72, 74, 76])]
    r2 = optimize_fingering(line, ctx, cfg, pinned=pinned)
    print(format_report(r2))
    _check(_strokes(r2) == ["D", "D", "D", "U", "D"],
           f"T7 expected D D D U D (D-D on beat 4), got {_strokes(r2)}")
    _check(_invariant_ok(r) == [] and _invariant_ok(r2) == [], "T7 invariant violated")
    print(">>> T7 PASS (downbeat D-D charged; hiccup moved to the weak beat)")


def test_T8():
    _banner("T8", "Cell connection on the eighth-note grid -> pivot on beat 3, D")
    c1 = {"name": "Desc bebop from root", "root": "G", "mode": "Myxolidian",
          "degrees": ["1", "maj7", "7", "6", "5"], "movement": "D"}
    c2 = {"name": "Asc II-m7 arp", "root": 0, "mode": "Myxolidian",
          "degrees": ["5", "7", "9", "4", "3"], "movement": "A"}
    line, pivot, _ = cell_bridge.build_connection_line(c1, c2)
    ctx = cell_bridge.cell_context(
        {"key": "G", "chords": [{"start_beat": 0, "symbol": "G7"},
                                {"start_beat": cell_bridge.cell_beat(pivot),
                                 "symbol": "G7"}]})
    r = optimize_fingering(cell_bridge.timed_cell_line(line), ctx)
    print(format_report(r))
    pv = r.best.placed[pivot]
    _check(pv.beat == 3, f"T8 pivot should land on beat 3, got beat {pv.beat}")
    for p in r.best.placed:
        if p.beat == 1:
            _check(p.stroke == "D", f"T8 beat-1 note {p.note.index} not a downstroke")
    _check(_invariant_ok(r) == [], "T8 invariant violated")
    print(f">>> T8 PASS (pivot on beat 3, stroke {pv.stroke})")


def test_T9():
    _banner("T9", "Reported cost == re-scored cost (no path aliasing), 300 random lines")
    import random as _random
    from scripts.fingering.optimizer import cost_of
    rng = _random.Random(20261012)
    bad = []
    for k in range(300):
        n = rng.randint(4, 9)
        line = [{"pitch": rng.randint(45, 79)} for _ in range(n)]
        density = rng.choice(["quarter", "eighth"])
        ctx = {"key": "C", "density": density, "chords": []}
        if density == "eighth":
            line = [dict(d, start=0.5 * i) for i, d in enumerate(line)]
        r = optimize_fingering(line, ctx)
        if abs(r.best.total_cost - cost_of(r.best.placed, r.config, density)) > 1e-6:
            bad.append((k, "best", r.best.total_cost, cost_of(r.best.placed, r.config, density)))
        if r.alternate is not None and abs(
                r.alternate.total_cost - cost_of(r.alternate.placed, r.config, density)) > 1e-6:
            bad.append((k, "alternate", r.alternate.total_cost,
                        cost_of(r.alternate.placed, r.config, density)))
    _check(not bad, f"T9 {len(bad)} aliased result(s): {bad[:5]}")
    print(">>> T9 PASS (300 lines, best and alternate costs stable)")


def main():
    print("Convention sanity check ...", end=" ")
    verify_conventions()
    print("OK")

    tests = [test_T1, test_T2, test_T3, test_T5, test_T4, test_T6, test_T7, test_T8,
             test_T9]
    passed, failed = 0, 0
    results = []
    for t in tests:
        try:
            t()
            passed += 1
            results.append((t.__name__, "PASS", ""))
        except Exception as e:  # noqa: BLE001 — report, don't abort the suite
            failed += 1
            results.append((t.__name__, "FAIL", str(e)))
            print(f">>> {t.__name__} FAIL: {e}")

    print("\n" + "=" * 74)
    print("SUMMARY")
    print("=" * 74)
    for name, status, msg in results:
        print(f"  {name}: {status}  {msg}")
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
