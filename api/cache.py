"""In-process LRU response cache + ETags.

Key = (endpoint, canonical JSON of the validated request, ENGINE_VERSION).
``respond()`` wraps a compute function: it answers ``If-None-Match`` with 304,
adds ``meta: {engine_version, elapsed_ms, cached, request_hash}`` to the body
and an ``ETag`` header. Bodies are plain dicts of JSON primitives.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from api.settings import get_settings
from api.version import ENGINE_VERSION


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str,
                      ensure_ascii=False)


def request_hash(endpoint: str, payload: Any) -> str:
    h = hashlib.sha1()
    h.update(ENGINE_VERSION.encode())
    h.update(b"|")
    h.update(endpoint.encode())
    h.update(b"|")
    h.update(canonical(payload).encode())
    return h.hexdigest()[:20]


def make_etag(endpoint: str, payload: Any) -> str:
    return f'"{ENGINE_VERSION[:12]}-{request_hash(endpoint, payload)}"'


class _LRU:
    def __init__(self, size: int):
        self.size = size
        self._d: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            v = self._d.get(key)
            if v is not None:
                self._d.move_to_end(key)
            return v

    def put(self, key: str, value: Dict[str, Any]) -> None:
        if self.size <= 0:
            return
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self.size:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()

    def __len__(self) -> int:
        return len(self._d)


_cache = _LRU(get_settings().cache_size)


def cache_stats() -> dict:
    return {"entries": len(_cache), "size": _cache.size}


def compute_cached(endpoint: str, payload: Any, compute: Callable[[], Dict[str, Any]]
                   ) -> Tuple[Dict[str, Any], bool, float]:
    key = request_hash(endpoint, payload)
    hit = _cache.get(key)
    if hit is not None:
        return hit, True, 0.0
    t0 = time.perf_counter()
    body = compute()
    elapsed = (time.perf_counter() - t0) * 1000.0
    _cache.put(key, body)
    return body, False, elapsed


def respond(request: Request, endpoint: str, payload: Any,
            compute: Callable[[], Dict[str, Any]]) -> Response:
    etag = make_etag(endpoint, payload)
    inm = request.headers.get("if-none-match")
    if inm and etag in [t.strip() for t in inm.split(",")]:
        return Response(status_code=304, headers={"ETag": etag})
    body, cached, elapsed = compute_cached(endpoint, payload, compute)
    out = dict(body)
    out["meta"] = {
        "engine_version": ENGINE_VERSION, "elapsed_ms": round(elapsed, 1),
        "cached": cached, "request_hash": request_hash(endpoint, payload),
    }
    return JSONResponse(out, headers={"ETag": etag,
                                      "Cache-Control": "private, max-age=0, must-revalidate"})


def plain(body: Dict[str, Any], elapsed_ms: float = 0.0) -> Dict[str, Any]:
    """A non-cached body with the same ``meta`` shape."""
    out = dict(body)
    out["meta"] = {"engine_version": ENGINE_VERSION, "elapsed_ms": round(elapsed_ms, 1),
                   "cached": False, "request_hash": None}
    return out
