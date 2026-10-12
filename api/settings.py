"""Environment configuration (every ``BEBOP_*`` variable in one place).

BEBOP_API_KEY           shared secret checked on every router but /health
BEBOP_ALLOWED_ORIGINS   comma-separated CORS origins (default: localhost:3000)
BEBOP_MAX_LAYOUTS       layout budget per request (2000 ≈ 3 s; container: 10000)
BEBOP_MAX_LAYOUTS_CEILING  the most a client may ask for via ``max_layouts``
BEBOP_TIME_BUDGET_MS    wall-clock budget per enumeration request
BEBOP_DEV               "1" lets localhost in without an API key (warning)
BEBOP_CACHE_SIZE        in-process LRU response cache entries
BEBOP_VISION_MODEL      overrides the Claude model of the score reader
ANTHROPIC_API_KEY       the score reader's key (Python only)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

DEFAULT_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def _bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None or not v.strip():
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    try:
        return int(v) if v not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    api_key: Optional[str]
    allowed_origins: Tuple[str, ...]
    max_layouts: int
    max_layouts_ceiling: int
    time_budget_ms: int
    dev: bool
    anthropic_api_key: Optional[str]
    vision_model: Optional[str]
    cache_size: int

    @property
    def auth_mode(self) -> str:
        return "api_key" if self.api_key else ("dev" if self.dev else "unconfigured")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = tuple(o.strip() for o in os.environ.get("BEBOP_ALLOWED_ORIGINS", "").split(",")
                    if o.strip()) or DEFAULT_ORIGINS
    max_layouts = max(1, _int("BEBOP_MAX_LAYOUTS", 2000))
    return Settings(
        api_key=(os.environ.get("BEBOP_API_KEY") or "").strip() or None,
        allowed_origins=origins,
        max_layouts=max_layouts,
        max_layouts_ceiling=max(max_layouts, _int("BEBOP_MAX_LAYOUTS_CEILING", 5 * max_layouts)),
        time_budget_ms=max(100, _int("BEBOP_TIME_BUDGET_MS", 6000)),
        dev=_bool("BEBOP_DEV", False),
        anthropic_api_key=(os.environ.get("ANTHROPIC_API_KEY") or "").strip() or None,
        vision_model=(os.environ.get("BEBOP_VISION_MODEL") or "").strip() or None,
        cache_size=max(0, _int("BEBOP_CACHE_SIZE", 512)),
    )
