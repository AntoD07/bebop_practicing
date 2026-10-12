"""Layout-count and wall-clock planning for the fingering enumerations.

A position enumeration lists EVERY string/fret layout of a line inside a box;
the layout space is the product of the per-pitch candidate counts, and one
(box, register) chunk of a "More Horizontal" pair can reach ~7800 layouts
(≈11 s). The planner enumerates chunks in ascending size while the cumulative
layout count fits ``max_layouts`` and the deadline holds, and solves the rest
with the single optimum (``mode == "optimum"``), reporting ``truncated``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import (
    FingeringResult, count_layouts, enumerate_fingerings, optimize_fingering,
)
from scripts.fingering.picking import ConventionError


@dataclass
class LayoutBudget:
    max_layouts: Optional[int] = None       # None = unlimited
    time_budget_ms: Optional[float] = None  # None = no deadline
    used: int = 0
    started: float = field(default_factory=time.monotonic)

    def expired(self) -> bool:
        if self.time_budget_ms is None:
            return False
        return (time.monotonic() - self.started) * 1000.0 >= self.time_budget_ms

    def allows(self, n_layouts: int) -> bool:
        if self.expired():
            return False
        if self.max_layouts is None:
            return True
        return self.used + n_layouts <= self.max_layouts

    def consume(self, n_layouts: int) -> None:
        self.used += n_layouts

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self.started) * 1000.0


@dataclass
class Chunk:
    """One (box, register) enumeration unit."""
    box: int
    offset: int
    line: List[dict]
    context: dict
    config: FingeringConfig
    n_layouts: int
    extra: Dict[str, Any] = field(default_factory=dict)


def plan_chunk(box: int, offset: int, line: List[dict], context: dict,
               config: FingeringConfig, **extra) -> Chunk:
    return Chunk(box=box, offset=offset, line=line, context=context, config=config,
                 n_layouts=count_layouts(line, context, config), extra=dict(extra))


def enumerate_chunks(chunks: List[Chunk], budget: Optional[LayoutBudget] = None
                     ) -> Tuple[List[Tuple[FingeringResult, Chunk]], bool, List[dict]]:
    """Enumerate ``chunks`` smallest first within ``budget``; the rest get the
    single optimum. Returns ``(results, truncated, reports)`` where each report
    is ``{box, offset, layouts, mode}`` with mode in enumerated / optimum /
    infeasible / empty."""
    budget = budget or LayoutBudget()
    order = sorted(range(len(chunks)), key=lambda i: (chunks[i].n_layouts, chunks[i].box, chunks[i].offset))
    results: List[Tuple[FingeringResult, Chunk]] = []
    reports: List[Optional[dict]] = [None] * len(chunks)
    truncated = False
    for i in order:
        ch = chunks[i]
        rep = {"box": ch.box, "offset": ch.offset, "layouts": ch.n_layouts, "mode": "empty"}
        reports[i] = rep
        if ch.n_layouts <= 0:
            continue
        if budget.allows(ch.n_layouts):
            try:
                cands = enumerate_fingerings(ch.line, ch.context, ch.config,
                                             max_layouts=max(1, ch.n_layouts))
            except ConventionError:
                raise
            except ValueError:
                cands = []
            budget.consume(ch.n_layouts)
            rep["mode"] = "enumerated" if cands else "infeasible"
            results.extend((c, ch) for c in cands)
        else:
            truncated = True
            try:
                one = optimize_fingering(ch.line, ch.context, ch.config)
            except ValueError:
                rep["mode"] = "infeasible"
                continue
            rep["mode"] = "optimum"
            results.append((one, ch))
    return results, truncated, [r for r in reports if r is not None]


def layout_sig(result: FingeringResult) -> str:
    """A fingering's string/fret layout, e.g. '3/14 3/12 4/14' (stable id)."""
    return " ".join(f"{p.string}/{p.fret}" for p in result.best.placed)


def dedupe_sorted(results: List[Tuple[FingeringResult, Chunk]]
                  ) -> List[Tuple[FingeringResult, Chunk]]:
    """Distinct layouts, cheapest first; ties broken by the layout string so the
    order never depends on chunk iteration order."""
    seen = set()
    out = []
    for r, ch in results:
        sig = layout_sig(r)
        if sig in seen:
            continue
        seen.add(sig)
        out.append((r, ch))
    out.sort(key=lambda rc: (rc[0].best.total_cost, layout_sig(rc[0])))
    return out
