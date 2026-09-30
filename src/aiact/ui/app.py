"""Internal read-only UI over the Act and guidance coverage artifacts.

Run with `make ui`. The payload is built once at startup; restart to pick up data changes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from aiact.ui.coverage_map import build_coverage_map

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.coverage = build_coverage_map()
    yield


app = FastAPI(title="AI Act coverage", lifespan=_lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/", include_in_schema=False)
def coverage_page() -> FileResponse:
    return FileResponse(STATIC / "coverage.html")


@app.get("/api/coverage")
def coverage() -> dict[str, Any]:
    payload: dict[str, Any] = app.state.coverage
    return payload
