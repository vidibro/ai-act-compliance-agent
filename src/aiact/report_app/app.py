"""The report app: one document in, one compliance report out.

Run with `make app`. Separate from the internal backend UI (`aiact.backend`), which exposes the
whole ruleset and its review state; this app shows a reader their own report and nothing else.

The model keys come from the environment, as in `scripts/review.py`.

TWO MODES. The normal mode is the review: `POST /api/review`, every model seam live. The DEMO
mode is the same pipeline with the three model seams replaced by deterministic stand-ins
(`aiact.report_app.demo`): `POST /api/demo/review`, no model call, no key needed, and a response
flagged `demo: true` so nothing downstream can mistake it for a review. Demo mode is always
available unless `AIACT_DEMO_MODE=off`; it is the ONLY mode when a live review cannot run — no
model (`AIACT_LLM_MODEL` empty), no key for it, or `AIACT_DEMO_MODE=only` — which `GET /api/mode`
tells the page. Sample documents for either mode come from `GET /api/samples`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

from aiact.brain import Brain
from aiact.config import get_settings
from aiact.document import DocumentTooLarge, check_size
from aiact.gap.judge import Judge
from aiact.pipeline import review
from aiact.policy_loader import load_policy_spec
from aiact.providers import vendor_behind
from aiact.report_app import explanations
from aiact.report_app.citations import segment_citations
from aiact.report_app.demo import DEMO_NOTE, DemoBrain, DemoJudge, DemoSummariser
from aiact.report_app.law import ProvisionText, paragraph_text, provision
from aiact.report_app.roles import RoleDefinition, role_definitions
from aiact.report_app.samples import Sample, SampleDocument, list_samples, load_sample
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


# The key each vendor reads, for the one question the page asks before offering a live review: can
# one run at all? A proxy holds its own key, and a vendor not listed here is given the benefit of
# the doubt — its credentials may come from anywhere (AWS, Vertex), and locking such a deployment
# into demo mode would be the worse mistake.
_VENDOR_KEYS: dict[str, tuple[str, ...]] = {
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "mistral": ("MISTRAL_API_KEY",),
}


def live_unavailable_because() -> str | None:
    """Why a live review cannot run, as far as configuration shows — or None where it can.

    Three things are checked, in the order a reader would fix them: `AIACT_DEMO_MODE=only`, an
    empty `AIACT_LLM_MODEL`, and a missing key for the model's vendor (unless a proxy is set, which
    holds its own). Whether the key WORKS shows on the first call, as it always did."""
    settings = get_settings()
    if settings.demo_mode == "only":
        return "Live reviews are switched off on this server (AIACT_DEMO_MODE=only)."
    model = settings.llm_model.strip()
    if not model:
        return "No model is configured: AIACT_LLM_MODEL is empty."
    if settings.llm_api_base:
        return None
    keys = _VENDOR_KEYS.get(vendor_behind(model)[0])
    if keys is None or any(os.environ.get(key) for key in keys):
        return None
    # Provider-agnostic on purpose: which variable holds the key is the provider's business and
    # .env.example's — the page says only what is true for every provider.
    return (
        f"No provider key is set for the configured model ({model}), so a live review cannot "
        "run. Add your provider's key to .env (see .env.example)."
    )


def _require_model() -> None:
    reason = live_unavailable_because()
    if reason is not None:
        hint = (
            " Use demo mode to see the report without a model."
            if get_settings().demo_mode != "off"
            else " Set a model and its key in .env."
        )
        raise HTTPException(status_code=503, detail=reason + hint)


def _require_demo() -> None:
    if get_settings().demo_mode == "off":
        raise HTTPException(
            status_code=403,
            detail="Demo mode is switched off on this server (AIACT_DEMO_MODE=off).",
        )


def get_brain() -> Brain:
    from aiact.classify.llm_brain import LLMBrain  # lazy: importing needs no API stack

    _require_model()
    return LLMBrain()


def get_judge() -> Judge | None:
    """None lets the gap layer build its default judge."""
    return None


def get_summariser() -> Summariser:
    _require_model()
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
    role_definitions()
    # Warm what the first response would otherwise load: a demo review should be instant on
    # the first request too.
    explanations.load(str(get_spec().act_version_date))
    paragraph_text("")
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


@app.get("/api/roles")
def roles() -> dict[str, RoleDefinition]:
    """What each role means, by role id: the Act's Article 3 definition where it has one."""
    return role_definitions()


@app.get("/api/provision/{key}")
def get_provision(key: str) -> ProvisionText:
    """An article ("75b") or annex ("IV") of the pinned Act, for a reference the reader opens."""
    found = provision(key)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No article or annex {key!r} in this Act.")
    return found


@app.get("/api/limits")
def limits() -> dict[str, int]:
    """What the page shows beside the input. 0 means no limit."""
    return {"max_document_chars": get_settings().max_document_chars}


class ModeInfo(BaseModel):
    """Which modes the page can offer, and why."""

    demo_mode: Literal["available", "only", "off"]
    """The server's `AIACT_DEMO_MODE` setting."""
    live_available: bool
    """False where a live review cannot run: demo mode is then the only mode the page offers."""
    live_unavailable_because: str | None
    """The reason, in the words the page shows; None where a live review can run."""
    llm_model: str | None
    """The configured model string, for the page to show; None when there is none."""
    demo_note: str
    """What a demo report is and is not, for the page to say before one is run."""


@app.get("/api/mode")
def mode() -> ModeInfo:
    settings = get_settings()
    reason = live_unavailable_because()
    return ModeInfo(
        demo_mode=settings.demo_mode,
        live_available=reason is None,
        live_unavailable_because=reason,
        llm_model=settings.llm_model.strip() or None,
        demo_note=DEMO_NOTE,
    )


@app.get("/api/samples")
def samples() -> list[Sample]:
    """Documents the page can load to try the review on: the golden set's reference files, the
    guide's worked-example card and the smoke check's vendor pages."""
    return list_samples()


@app.get("/api/samples/{sample_id}")
def get_sample(sample_id: str) -> SampleDocument:
    found = load_sample(sample_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No sample document {sample_id!r}.")
    return found


def _review(
    request: ReviewRequest,
    spec: PolicyRuleset,
    brain: Brain,
    judge: Judge | None,
    summariser: Summariser,
    demo_note: str | None = None,
) -> ReviewResponse:
    try:
        check_size(request.document)
    except DocumentTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(summariser.summarise, request.document)
        report = review(request.document, spec, brain, judge=judge, system_id=request.system_id)
        summary = _summary(pending)
    return build_response(report, spec, summary, demo_note=demo_note)


@app.post("/api/review")
def post_review(
    request: ReviewRequest,
    spec: Annotated[PolicyRuleset, Depends(get_spec)],
    brain: Annotated[Brain, Depends(get_brain)],
    judge: Annotated[Judge | None, Depends(get_judge)],
    summariser: Annotated[Summariser, Depends(get_summariser)],
) -> ReviewResponse:
    """Classify the document, check it against the obligations that applies, and resolve every
    rule and norm the report names. A short summary of the system is written alongside. Takes as
    long as the model calls do. 503 when a live review cannot run here (no model, no key, or
    demo-only), 502 when the model call fails — demo mode works either way."""
    try:
        return _review(request, spec, brain, judge, summariser)
    except HTTPException:
        raise
    except Exception as exc:
        # A failed model call — a missing key, a vendor outage, a proxy that refused — is the one
        # failure a reader can act on, and a bare 500 does not let them. The traceback stays in
        # the log.
        log.exception("The review failed")
        first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        raise HTTPException(
            status_code=502,
            detail=(
                f"The review could not be completed: {first_line[:300].rstrip('.')}. Check "
                "AIACT_LLM_MODEL and the provider key in .env."
            ),
        ) from exc


@app.post("/api/demo/review")
def post_demo_review(
    request: ReviewRequest, spec: Annotated[PolicyRuleset, Depends(get_spec)]
) -> ReviewResponse:
    """The same review with no model behind it: the classification answers, the verdicts and the
    summary come from the keyword heuristics in `aiact.report_app.demo`, and the response says so
    in `demo` and `demo_note`. Needs no key and takes well under a second. Illustrative only.
    403 where the server has switched demo mode off."""
    _require_demo()
    return _review(request, spec, DemoBrain(), DemoJudge(), DemoSummariser(), demo_note=DEMO_NOTE)
