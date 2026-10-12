"""``X-API-Key`` check (constant-time) for every router but /health."""

from __future__ import annotations

import hmac
import logging
from typing import Optional

from fastapi import Header, HTTPException, Request

from api.settings import get_settings

log = logging.getLogger("bebop.api")
_warned = False

_LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost", "testclient")


async def require_api_key(request: Request,
                          x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    global _warned
    s = get_settings()
    if s.api_key:
        if x_api_key and hmac.compare_digest(x_api_key.encode(), s.api_key.encode()):
            return
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
    host = request.client.host if request.client else ""
    if s.dev and host in _LOCAL_HOSTS:
        if not _warned:
            log.warning("BEBOP_DEV=1 and no BEBOP_API_KEY: accepting unauthenticated "
                        "requests from localhost")
            _warned = True
        return
    raise HTTPException(status_code=503, detail="BEBOP_API_KEY is not configured on the API")
