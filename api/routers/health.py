"""``GET /health`` (no auth): catalog stats, engine version, data warnings."""

from __future__ import annotations

import platform

from fastapi import APIRouter

from api.cache import cache_stats, plain
from api.settings import get_settings
from api.version import ENGINE_VERSION
from scripts.domain.catalog import load_catalog

router = APIRouter()


@router.get("/health")
def health():
    s = get_settings()
    cat = load_catalog()
    return plain({
        "ok": True,
        "engine_version": ENGINE_VERSION,
        "python": platform.python_version(),
        "auth": s.auth_mode,
        "limits": {"max_layouts": s.max_layouts, "max_layouts_ceiling": s.max_layouts_ceiling,
                   "time_budget_ms": s.time_budget_ms},
        "catalog": cat.stats(),
        "warnings": list(cat.warnings),
        "cache": cache_stats(),
        "vision": bool(s.anthropic_api_key),
    })
