"""The backend: an internal read-only UI over the Act and guidance coverage artifacts.

Run with `make backend`. The data files are watched: a request after an edit rebuilds the payloads,
and the page polls `/api/version` to pick the change up. Python edits restart the server
(`--reload`).
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aiact.backend.coverage_map import build_coverage_map
from aiact.backend.norm_cards import build_norm_cards
from aiact.norm_loader import load_normative_coverage
from aiact.policy_loader import load_policy_spec

STATIC = Path(__file__).parent / "static"
DATA_DIRS = (Path("data/policy"), Path("data/golden_set"))
DATA_SUFFIXES = {".yaml", ".yml", ".json", ".md"}


def _fingerprint(roots: tuple[Path, ...], suffixes: set[str] | None = None) -> str:
    """Changes whenever a watched file is added, removed or saved."""
    digest = hashlib.sha1()
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and (suffixes is None or path.suffix in suffixes):
                stat = path.stat()
                digest.update(f"{path}:{stat.st_mtime_ns}:{stat.st_size};".encode())
    return digest.hexdigest()[:16]


class Payloads:
    """The two payloads, rebuilt when the data changes. A failed rebuild keeps the last good
    payloads and reports the error, so a half-finished edit does not take the page down."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.fingerprint = ""
        self.coverage: dict[str, Any] | None = None
        self.norms: dict[str, Any] | None = None
        self.error: str | None = None

    def refresh(self) -> None:
        current = _fingerprint(DATA_DIRS, DATA_SUFFIXES)
        if current == self.fingerprint:
            return
        with self._lock:
            if current == self.fingerprint:
                return
            try:
                bundle = load_normative_coverage()
                spec = load_policy_spec()
                self.coverage = build_coverage_map(bundle, spec)
                self.norms = build_norm_cards(bundle, spec)
                self.error = None
            except Exception as exc:  # any invalid data file, reported rather than raised
                self.error = f"{type(exc).__name__}: {exc}"
            self.fingerprint = current

    def get(self, name: str) -> dict[str, Any]:
        self.refresh()
        payload: dict[str, Any] | None = getattr(self, name)
        if payload is None:
            raise HTTPException(status_code=503, detail=self.error or "data not loaded")
        return payload


PAYLOADS = Payloads()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    PAYLOADS.refresh()
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


@app.get("/api/version")
def version() -> dict[str, str | None]:
    """What the page polls: a new `data` refetches the payloads, a new `page` reloads the page."""
    PAYLOADS.refresh()
    return {
        "data": PAYLOADS.fingerprint,
        "page": _fingerprint((STATIC,)),
        "error": PAYLOADS.error,
    }


@app.get("/api/coverage")
def coverage() -> dict[str, Any]:
    return PAYLOADS.get("coverage")


@app.get("/api/norms")
def norms() -> dict[str, Any]:
    return PAYLOADS.get("norms")
