"""The compute API: ``app`` is the Vercel Python function (``/api/index``, with
``/api/py/(.*)`` rewritten to it) and the uvicorn/container entry point.

Routes (all under ``/api/py``): health, cells, translate, positions, constants,
connections/pairs, fingering/connection, fingering/line, lines/sample,
lines/pairs, fingering/positions, fingering/rank-absolute, pentatonics/*,
triads/*, score/*. Every router but health requires ``X-API-Key``.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from api.auth import require_api_key  # noqa: E402
from api.routers import (  # noqa: E402
    cells, connections, fingering, health, lines, pentatonics, score, triads,
)
from api.settings import get_settings  # noqa: E402
from api.version import ENGINE_VERSION  # noqa: E402
from scripts.domain.catalog import load_catalog  # noqa: E402
from scripts.domain.transposition import TranslationError  # noqa: E402
from scripts.fingering.picking import ConventionError, verify_conventions  # noqa: E402

PREFIX = "/api/py"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_catalog()            # ≈5 ms; warms the lru_cache
    verify_conventions()      # halts on a cost-model inversion
    yield


app = FastAPI(title="Bebop compute API", version=ENGINE_VERSION[:12], lifespan=lifespan,
              docs_url=f"{PREFIX}/docs", openapi_url=f"{PREFIX}/openapi.json", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)


@app.exception_handler(TranslationError)
async def _translation_error(_request: Request, exc: TranslationError):
    return JSONResponse(status_code=422, content={
        "detail": str(exc), "token": exc.token, "mapping": exc.mapping})


@app.exception_handler(KeyError)
async def _key_error(_request: Request, exc: KeyError):
    return JSONResponse(status_code=404, content={"detail": str(exc.args[0] if exc.args else exc)})


@app.exception_handler(ConventionError)
async def _convention_error(_request: Request, exc: ConventionError):
    return JSONResponse(status_code=500, content={"detail": f"engine convention error: {exc}"})


app.include_router(health.router, prefix=PREFIX, tags=["health"])
_auth = [Depends(require_api_key)]
app.include_router(cells.router, prefix=PREFIX, tags=["cells"], dependencies=_auth)
app.include_router(connections.router, prefix=PREFIX, tags=["connections"], dependencies=_auth)
app.include_router(lines.router, prefix=PREFIX, tags=["lines"], dependencies=_auth)
app.include_router(fingering.router, prefix=PREFIX, tags=["fingering"], dependencies=_auth)
app.include_router(pentatonics.router, prefix=PREFIX, tags=["pentatonics"], dependencies=_auth)
app.include_router(triads.router, prefix=PREFIX, tags=["triads"], dependencies=_auth)
app.include_router(score.router, prefix=PREFIX, tags=["score"], dependencies=_auth)


@app.get("/api/index")
@app.get(PREFIX)
def root():
    return {"ok": True, "service": "bebop compute API", "engine_version": ENGINE_VERSION,
            "docs": f"{PREFIX}/docs"}
