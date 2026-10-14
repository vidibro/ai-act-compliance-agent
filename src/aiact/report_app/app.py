"""The report app: one document in, one compliance report out.

Run with `make app`. Separate from the internal backend UI (`aiact.ui`), which exposes the whole
ruleset and its review state; this app shows a reader their own report and nothing else.

The model keys come from the environment, as in `scripts/review.py`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

from aiact.brain import Brain
from aiact.config import get_settings
from aiact.document import DocumentTooLarge, check_size
from aiact.gap.judge import LLMJudge
from aiact.pipeline import review
from aiact.policy_loader import load_policy_spec
from aiact.report_app.citations import segment_citations
from aiact.report_app.views import (
    NormView,
    ReviewResponse,
    RuleView,
    build_response,
    resolve_norms,
    resolve_rules,
)
from aiact.schemas.classification import UseCaseClassification
from aiact.schemas.policy import PolicyRuleset
from aiact.summary import LLMSummariser, Summariser, SystemSummary

STATIC = Path(__file__).parent / "static"
GUIDE = Path("docs/system-card-guide.md")  # relative to the working directory, like the data paths
log = logging.getLogger(__name__)


class ReviewRequest(BaseModel):
    document: str = Field(min_length=1)
    """The system card or technical documentation, as plain text or Markdown."""
    system_id: str = Field(default="system", min_length=1, max_length=100)
    """An id for traces. The name shown to the reader is read from the document."""


@lru_cache(maxsize=1)
def get_spec() -> PolicyRuleset:
    return load_policy_spec()


def get_brain() -> Brain:
    from aiact.classify.llm_brain import LLMBrain  # lazy: importing needs no API stack

    return LLMBrain()


def get_judge() -> LLMJudge | None:
    """None lets the gap layer build its default judge."""
    return None


def get_summariser() -> Summariser:
    return LLMSummariser()


def _summary(pending: Future[SystemSummary | None]) -> SystemSummary | None:
    """The name and summary, or None if writing them failed. The report stands without them."""
    try:
        return pending.result()
    except Exception:
        log.warning("The system summary could not be written", exc_info=True)
        return None


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()  # the app boundary owns .env; the library stays free of it
    get_spec()  # fail at start, not on the first request, if the data does not load
    segment_citations()
    yield


app = FastAPI(title="AI Act Compliance Review", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def _revalidate(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # The browser asks before reusing a cached page file, so an edit shows on the next reload;
    # an unchanged file still comes back as 304.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/guide", include_in_schema=False)
def guide() -> HTMLResponse:
    """The system-card guide, rendered from its Markdown on each request, so an edit shows on
    reload."""
    markdown = MarkdownIt("commonmark", {"html": False}).enable("table")
    body = markdown.render(GUIDE.read_text(encoding="utf-8"))
    page = (STATIC / "guide.html").read_text(encoding="utf-8")
    return HTMLResponse(page.replace("<!-- guide -->", body))


@app.get("/guide.md", include_in_schema=False)
def guide_markdown() -> PlainTextResponse:
    """The guide as written, for the page's copy button."""
    return PlainTextResponse(GUIDE.read_text(encoding="utf-8"), media_type="text/markdown")


class RefreshRequest(BaseModel):
    """What a saved report names. The saved report itself is not sent back: its classification
    answers come out of JSON as text, and an answer refuses raw text by design."""

    use_cases: list[UseCaseClassification]
    rule_ids: list[str]
    norm_ids: list[str]


class RefreshResponse(BaseModel):
    rules: dict[str, RuleView]
    norms: dict[str, NormView]


@app.post("/api/refresh")
def post_refresh(
    request: RefreshRequest, spec: Annotated[PolicyRuleset, Depends(get_spec)]
) -> RefreshResponse:
    """The rules and norms a saved report names, rebuilt from the current spec, so a report saved
    before a rules change reads like a new one. Nothing is re-judged and no model is called."""
    return RefreshResponse(
        rules=resolve_rules(request.rule_ids, request.use_cases, spec),
        norms=resolve_norms(request.norm_ids, spec, request.use_cases),
    )


@app.get("/api/limits")
def limits() -> dict[str, int]:
    """What the page shows beside the input. 0 means no limit."""
    return {"max_document_chars": get_settings().max_document_chars}


@app.post("/api/review")
def post_review(
    request: ReviewRequest,
    spec: Annotated[PolicyRuleset, Depends(get_spec)],
    brain: Annotated[Brain, Depends(get_brain)],
    judge: Annotated[LLMJudge | None, Depends(get_judge)],
    summariser: Annotated[Summariser, Depends(get_summariser)],
) -> ReviewResponse:
    """Classify the document, check it against the obligations that applies, and resolve every
    rule and norm the report names. A short summary of the system is written alongside. Takes as
    long as the model calls do."""
    try:
        check_size(request.document)
    except DocumentTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(summariser.summarise, request.document)
        report = review(request.document, spec, brain, judge=judge, system_id=request.system_id)
        summary = _summary(pending)
    return build_response(report, spec, summary)
