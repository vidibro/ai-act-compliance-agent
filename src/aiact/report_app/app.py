"""The report app: one document in, one compliance report out.

Run with `make app`. Separate from the internal coverage UI (`aiact.ui`), which exposes the whole
ruleset and its review state; this app shows a reader their own report and nothing else.

The model keys come from the environment, as in `scripts/review.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aiact.brain import Brain
from aiact.document import DocumentTooLarge
from aiact.gap.judge import LLMJudge
from aiact.pipeline import review
from aiact.policy_loader import load_policy_spec
from aiact.report_app.views import ReviewResponse, build_response
from aiact.schemas.policy import PolicyRuleset

STATIC = Path(__file__).parent / "static"


class ReviewRequest(BaseModel):
    document: str = Field(min_length=1)
    """The system card or technical documentation, as plain text or Markdown."""
    system_id: str = Field(default="system", min_length=1, max_length=100)


@lru_cache(maxsize=1)
def get_spec() -> PolicyRuleset:
    return load_policy_spec()


def get_brain() -> Brain:
    from aiact.classify.llm_brain import LLMBrain  # lazy: importing needs no API stack

    return LLMBrain()


def get_judge() -> LLMJudge | None:
    """None lets the gap layer build its default judge."""
    return None


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()  # the app boundary owns .env; the library stays free of it
    get_spec()  # fail at start, not on the first request, if the data does not load
    yield


app = FastAPI(title="AI Act Compliance Review", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.post("/api/review")
def post_review(
    request: ReviewRequest,
    spec: Annotated[PolicyRuleset, Depends(get_spec)],
    brain: Annotated[Brain, Depends(get_brain)],
    judge: Annotated[LLMJudge | None, Depends(get_judge)],
) -> ReviewResponse:
    """Classify the document, check it against the obligations that applies, and resolve every
    rule and norm the report names. Takes as long as the model calls do."""
    try:
        report = review(request.document, spec, brain, judge=judge, system_id=request.system_id)
    except DocumentTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return build_response(report, spec)
