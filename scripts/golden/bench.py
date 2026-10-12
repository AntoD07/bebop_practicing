"""Latency bench: random pivot pairs × (Free + the 5 positions) under the
default budget. Every call must finish under 3.5 s.

    python -m scripts.golden.bench [--pairs 400] [--seed 0]
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.budget import make_budget  # noqa: E402
from scripts.domain.connections import pairs_for_pivot, score_connection_pair  # noqa: E402
from scripts.domain.notes import CHORD_MODES, PRACTICE_KEYS  # noqa: E402
from scripts.fingering.positions import POSITIONS  # noqa: E402

LIMIT_S = 3.5


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    rng = random.Random(args.seed)
    times = []
    worst = []
    n_calls = 0
    t_start = time.time()
    while n_calls < args.pairs * (len(POSITIONS) + 1):
        c1, c2 = rng.choice(CHORD_MODES), rng.choice(CHORD_MODES)
        dtm1 = rng.random() < 0.2 and c1 in ("MinorResolutions", "MajorResolutions", "Locrian", "Myxolidian")
        dtm2 = rng.random() < 0.2 and c2 in ("MinorResolutions", "MajorResolutions", "Locrian", "Myxolidian")
        try:
            pp = pairs_for_pivot(c1, c2, bonus=rng.random() < 0.3, dom_to_minor1=dtm1,
                                 dom_to_minor2=dtm2, key="C")
        except Exception as e:  # noqa: BLE001
            print("pairs failed:", c1, c2, e)
            continue
        if not pp["pairs"]:
            continue
        e, s = rng.choice(pp["pairs"])
        key = rng.choice(PRACTICE_KEYS)
        anchor = rng.choice(["key", "chord1", "chord2"])
        c1d = {"name": e.name, "degrees": list(e.degrees), "movement": e.movement}
        c2d = {"name": s.name, "degrees": list(s.degrees), "movement": s.movement}
        for pos in [None] + POSITIONS:
            t0 = time.perf_counter()
            res = score_connection_pair(key, pp["read1"], pp["read2"], c1d, c2d, position=pos,
                                        anchor=anchor, myxo_to_dorian=pp["myxo_to_dorian"],
                                        single_chord=pp["single_chord"], budget=make_budget())
            dt = time.perf_counter() - t0
            times.append(dt)
            n_calls += 1
            worst.append((dt, key, c1, c2, e.name, s.name, pos, len(res["fingerings"]), res["truncated"]))
    worst.sort(reverse=True)
    times.sort()
    p = lambda q: times[min(len(times) - 1, int(q * len(times)))]
    print(f"{len(times)} calls in {time.time() - t_start:.1f}s — p50 {p(0.5)*1000:.0f} ms, "
          f"p95 {p(0.95)*1000:.0f} ms, p99 {p(0.99)*1000:.0f} ms, max {times[-1]*1000:.0f} ms, "
          f"mean {statistics.mean(times)*1000:.0f} ms")
    print("slowest:")
    for w in worst[:8]:
        print(f"  {w[0]*1000:7.0f} ms  key {w[1]:2s} {w[2]}->{w[3]} {w[6]}  "
              f"({w[7]} fingerings, truncated={w[8]})  {w[4]} -> {w[5]}")
    over = [w for w in worst if w[0] > LIMIT_S]
    if over:
        print(f"FAIL: {len(over)} call(s) over {LIMIT_S}s")
        return 1
    print(f"OK: every call under {LIMIT_S}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
