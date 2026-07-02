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
    _banner("T3", "ii-V-i in A minor (Bm7b5-E7-Am6) from the cell DB")
    ii = cell_bridge.first_cell("Locrian")
    V = cell_bridge.first_cell("Myxolidian")
    i = cell_bridge.first_cell("MinorResolutions")
    ii["root"], V["root"], i["root"] = "B", "E", "A"
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
            {"start_beat": 2 * cell_len, "symbol": "Am6"},
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
    _banner("T4", "Phase-2 smoke test (engine forced ON): one ornament at a forced drop")
    # A4 on beat 1 (forced D, so no parity-U is available) leaping down to D3.
    # D3 (MIDI 50) is below the open pitch of every string A4 can sit on
    # (strings 1-3), so it cannot share a string with A4 -> lateral routing is
    # impossible and the descending crossing is a FORCED managed drop onto D3,
    # the root of D7 (a chord tone).
    line = [
        {"pitch": "A4", "role": "9", "degree": "9", "cell": "wide leap"},
        {"pitch": "D3", "role": "root", "degree": "1", "cell": "wide leap"},
    ]
    ctx = {"key": "G", "chords": [{"start_beat": 0, "symbol": "D7"}]}
    cfg = FingeringConfig(ornament_engine_enabled=True)
    r = optimize_fingering(line, ctx, cfg)
    print(format_report(r))
    _check(len(r.best.drop_sites) >= 1, "T4 expected a forced managed drop")
    _check(len(r.ornaments) == 1, f"T4 expected exactly one ornament, got {len(r.ornaments)}")
    orn = r.ornaments[0]
    _check("=>" in orn["parity_after"] or "->" in orn["parity_after"],
           "T4 ornament must show parity math")
    _check(_invariant_ok(r) == [], "T4 invariant violated (phase-1 solution)")
    print(f">>> T4 PASS (ornament: {orn['ornament']}; parity {orn['parity_before']} => {orn['parity_after']})")


def main():
    print("Convention sanity check ...", end=" ")
    verify_conventions()
    print("OK")

    tests = [test_T1, test_T2, test_T3, test_T5, test_T4]
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
