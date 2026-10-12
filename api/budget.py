"""Settings-driven layout/time budgets for the enumerating endpoints."""

from __future__ import annotations

from typing import Optional

from api.settings import get_settings
from scripts.domain.budget import LayoutBudget


def make_budget(max_layouts: Optional[int] = None,
                time_budget_ms: Optional[int] = None) -> LayoutBudget:
    """A fresh budget: the client may lower ``max_layouts`` or raise it up to
    the configured ceiling (the "load every layout" button); the wall-clock
    budget is the server's."""
    s = get_settings()
    ml = s.max_layouts if max_layouts is None else max(1, min(int(max_layouts), s.max_layouts_ceiling))
    tb = s.time_budget_ms if time_budget_ms is None else max(100, min(int(time_budget_ms), 10 * s.time_budget_ms))
    return LayoutBudget(max_layouts=ml, time_budget_ms=tb)
