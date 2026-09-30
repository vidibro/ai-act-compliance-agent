"""Internal read-only UI over the Act and guidance coverage artifacts.

Run with `make ui`. The payloads are built once at startup; restart to pick up data changes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aiact.norm_loader import load_normative_coverage
from aiact.policy_loader import load_policy_spec
from aiact.ui.coverage_map import build_coverage_map
from aiact.ui.norm_cards import build_norm_cards

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    bundle = load_normative_coverage()
    spec = load_policy_spec()
    app.state.coverage = build_coverage_map(bundle, spec)
    app.state.norms = build_norm_cards(bundle, spec)
    yield


app = FastAPI(title="AI Act coverage", lifespan=_lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def _revalidate(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Edited page files show on the next reload; unchanged ones still come back as 304.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/coverage")
def coverage() -> dict[str, Any]:
    payload: dict[str, Any] = app.state.coverage
    return payload


@app.get("/api/norms")
def norms() -> dict[str, Any]:
    payload: dict[str, Any] = app.state.norms
    return payload
