"""The report app: one document in, one compliance report out.

Run with `make app`. Separate from the internal backend UI (`aiact.backend`), which exposes the
whole ruleset and its review state; this app shows a reader their own report and nothing else.

The model and its key come from the environment, as in `scripts/review.py` — or from the REQUEST:
a caller may bring their own key (BYOK) in the `X-LLM-API-Key` header and name the model in the
body, and the review runs on those, for that request alone. The key is never stored, logged,
traced or indexed; `AIACT_BYOK_MODE` says whether the server accepts one, requires one, or refuses
it. See `LLMAccess`.

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
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
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
from aiact.providers import profile_for, vendor_behind
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
from aiact.scrubbing import scrub
from aiact.summary import LLMSummariser, Summariser, SystemSummary
from aiact.usage import PRICES

STATIC = Path(__file__).parent / "static"
GUIDE = Path("docs/system-card-guide.md")  # relative to the working directory, like the data paths
log = logging.getLogger(__name__)


# The LiteLLM model strings we will route: `vendor/name`, a gateway prefix in front, a Bedrock
# `:0` revision, a Vertex `@001` version. Anything else is refused before it reaches a provider.
_MODEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,199}$"

# The caller's key travels in this header — not in the body, where it would sit beside the
# document in every request log, saved request and browser cache that keeps bodies; and not in
# `Authorization`, which names the caller to THIS service and is what a later auth layer will
# read. A header of its own keeps "who are you" and "whose provider account pays" apart.
BYOK_HEADER = "X-LLM-API-Key"
_KEY_MAX_LENGTH = 2048


class ReviewRequest(BaseModel):
    document: str = Field(min_length=1)
    """The system card or technical documentation, as plain text or Markdown."""
    system_id: str = Field(default="system", min_length=1, max_length=100)
    """An id for traces. The name shown to the reader is read from the document."""
    model: str | None = Field(default=None, pattern=_MODEL_PATTERN)
    """The LiteLLM model string to review with (`anthropic/claude-haiku-4-5`), in place of the
    server's `AIACT_LLM_MODEL`. Its provider key comes from the `X-LLM-API-Key` header, or from the
    server where it holds one for that vendor. Ignored by the demo review, which calls no model."""


@dataclass(frozen=True)
class LLMAccess:
    """What one request brings for its model calls: the model, and whose key pays for them.

    Built per request from the body and the header, handed to the three seams, and gone when the
    response is. The key is excluded from the repr so that no log line, traceback local or
    assertion message formats it. Nothing else keeps a reference: the seams hold it privately for
    their calls, the trace metadata is an allow-list that never carried a key, and the document
    index holds the document alone."""

    model: str
    """The model this review runs on: the request's, else the server's. Empty when neither."""
    api_key: str | None = field(default=None, repr=False)
    """The caller's own key, or None to run on the server's credentials."""

    @property
    def byok(self) -> bool:
        return self.api_key is not None


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


def _server_has_key_for(model: str) -> bool:
    """Whether the server's own configuration can pay for calls to `model`, as far as it shows.

    A proxy holds its own key; a vendor not in `_VENDOR_KEYS` is given the benefit of the doubt.
    Whether the key WORKS shows on the first call, as it always did."""
    settings = get_settings()
    if settings.llm_api_base:
        return True
    keys = _VENDOR_KEYS.get(vendor_behind(model)[0])
    return keys is None or any(os.environ.get(key) for key in keys)


def live_unavailable_because(access: LLMAccess | None = None) -> str | None:
    """Why a live review cannot run — or None where it can.

    With no `access`, this is the server's own standing, for `GET /api/mode`: the configured model
    on the server's keys. With one, it is the answer for that request — the model it names and
    the key it brings, where the server accepts one.

    Checked in the order a reader would fix them: `AIACT_DEMO_MODE=only`, no model at all, and no
    key for the model's vendor — the caller's first, then the server's, unless `AIACT_BYOK_MODE`
    is `required`, in which case the server's keys are never spent on a review."""
    settings = get_settings()
    if settings.demo_mode == "only":
        return "Live reviews are switched off on this server (AIACT_DEMO_MODE=only)."
    byok = settings.byok_mode != "off"
    model = access.model if access else settings.llm_model.strip()
    if not model:
        return "No model is configured: AIACT_LLM_MODEL is empty." + (
            " Name one in the request (`model`) to run a live review." if byok else ""
        )
    if access is not None and access.byok:
        return None
    if settings.byok_mode == "required":
        return (
            f"This server runs bring-your-own-key: send your provider's key for the model "
            f"({model}) in the {BYOK_HEADER} header to run a live review."
        )
    if _server_has_key_for(model):
        return None
    # Provider-agnostic on purpose: which variable holds the key is the provider's business and
    # .env.example's — the page says only what is true for every provider.
    return (
        f"No provider key is set on this server for the model ({model}), so a live review cannot "
        "run on it. "
        + (
            f"Send your own in the {BYOK_HEADER} header, or add the provider's key to .env "
            "(see .env.example)."
            if byok
            else "Add your provider's key to .env (see .env.example)."
        )
    )


def _require_live(access: LLMAccess) -> None:
    reason = live_unavailable_because(access)
    if reason is not None:
        hint = (
            " Use demo mode to see the report without a model."
            if get_settings().demo_mode != "off"
            else " Set a model and its key in .env."
        )
        raise HTTPException(status_code=503, detail=reason + hint)


def _caller_key(header: str | None) -> str | None:
    """The key from the header, checked for SHAPE only — never echoed back. A FastAPI validation
    error on the header would put the rejected value in the 422 body, so the checks are here."""
    if header is None:
        return None
    key = header.strip()
    if not key:
        return None
    if get_settings().byok_mode == "off":
        raise HTTPException(
            status_code=400,
            detail=(
                f"This server does not accept a caller's provider key ({BYOK_HEADER}): reviews "
                "run on the model and key the server is configured with (AIACT_BYOK_MODE=off)."
            ),
        )
    if len(key) > _KEY_MAX_LENGTH or not all(0x21 <= ord(char) <= 0x7E for char in key):
        raise HTTPException(
            status_code=400,
            detail=f"The {BYOK_HEADER} header is not a usable key: one token of printable ASCII.",
        )
    return key


def get_llm_access(
    request: ReviewRequest,
    x_llm_api_key: Annotated[
        str | None,
        Header(
            alias=BYOK_HEADER,
            description=(
                "Your own provider key for the model the review runs on, used for this request "
                "only and never stored. Optional where the server holds a key; required where it "
                "runs bring-your-own-key (see GET /api/mode)."
            ),
        ),
    ] = None,
) -> LLMAccess:
    """The model and key for this request. Shape is checked here; whether the review can run on
    them is checked where a seam is built, so a test that stubs every seam needs no key."""
    model = (request.model or get_settings().llm_model).strip()
    return LLMAccess(model=model, api_key=_caller_key(x_llm_api_key))


def _require_demo() -> None:
    if get_settings().demo_mode == "off":
        raise HTTPException(
            status_code=403,
            detail="Demo mode is switched off on this server (AIACT_DEMO_MODE=off).",
        )


def get_brain(access: Annotated[LLMAccess, Depends(get_llm_access)]) -> Brain:
    from aiact.classify.llm_brain import LLMBrain  # lazy: importing needs no API stack

    _require_live(access)
    return LLMBrain(model=access.model, api_key=access.api_key)


def get_judge(access: Annotated[LLMAccess, Depends(get_llm_access)]) -> Judge | None:
    """Built here rather than left to the gap layer's default, which would read the environment:
    the judge must run on the model and key the REQUEST brought, like the other two seams."""
    from aiact.gap.judge import LLMJudge  # lazy: importing needs no API stack

    _require_live(access)
    return LLMJudge(model=access.model, api_key=access.api_key)


def get_summariser(access: Annotated[LLMAccess, Depends(get_llm_access)]) -> Summariser:
    _require_live(access)
    return LLMSummariser(model=access.model, api_key=access.api_key)


def _summary(
    pending: Future[SystemSummary | None], api_key: str | None = None
) -> SystemSummary | None:
    """The name and summary, or None if writing them failed. The report stands without them.

    The failure is logged scrubbed of `api_key`: this is the one model call whose exception is
    written out rather than raised, so it gets the same net as the 502 path."""
    try:
        return pending.result()
    except Exception:
        log.warning(
            "The system summary could not be written\n%s",
            scrub(traceback.format_exc(), extra=api_key),
        )
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


class ByokInfo(BaseModel):
    """Whether a reader can — or must — bring their own provider key and choose the model."""

    mode: Literal["available", "required", "off"]
    """The server's `AIACT_BYOK_MODE` setting."""
    header: str
    """The request header that carries the key."""
    key_required: bool
    """True where a live review runs only with a caller's key: the server requires one, or holds
    none for its model. False where the server's own key serves (a caller's still wins if sent)."""
    model_required: bool
    """True where the server names no model, so a live review must name one in the request."""
    model_pattern: str
    """The regular expression a `model` must match, so the page can say so before sending."""


class ModelInfo(BaseModel):
    """A model the page can offer to choose from. Any LiteLLM model string is accepted in the
    request; these are the ones this project has priced and shaped a request for."""

    model: str
    """The LiteLLM model string to send as `model`."""
    vendor: str
    verified: bool
    """Whether the request shape for this model has been checked against the vendor's
    documentation (see `aiact.providers`)."""


class ModeInfo(BaseModel):
    """Which modes the page can offer, and why."""

    demo_mode: Literal["available", "only", "off"]
    """The server's `AIACT_DEMO_MODE` setting."""
    live_available: bool
    """False where a live review cannot run on the server's own configuration. Unless `byok.mode`
    is `off`, a caller's key (and model) can still make one run — `byok` says what is needed."""
    live_unavailable_because: str | None
    """The reason, in the words the page shows; None where a live review can run."""
    llm_model: str | None
    """The server's configured model string, for the page to show; None when there is none."""
    byok: ByokInfo
    demo_note: str
    """What a demo report is and is not, for the page to say before one is run."""


def byok_info() -> ByokInfo:
    settings = get_settings()
    model = settings.llm_model.strip()
    return ByokInfo(
        mode=settings.byok_mode,
        header=BYOK_HEADER,
        key_required=settings.byok_mode == "required"
        or (settings.byok_mode == "available" and bool(model) and not _server_has_key_for(model)),
        model_required=settings.byok_mode != "off" and not model,
        model_pattern=_MODEL_PATTERN,
    )


@app.get("/api/mode")
def mode() -> ModeInfo:
    settings = get_settings()
    reason = live_unavailable_because()
    return ModeInfo(
        demo_mode=settings.demo_mode,
        live_available=reason is None,
        live_unavailable_because=reason,
        llm_model=settings.llm_model.strip() or None,
        byok=byok_info(),
        demo_note=DEMO_NOTE,
    )


@lru_cache(maxsize=1)
def known_models() -> list[ModelInfo]:
    """The models this project prices (`aiact.usage`), as LiteLLM strings, for the page's list.

    The price table keys on the bare name; the vendor is read off it the way the provider seam
    reads it through a gateway, and becomes the LiteLLM prefix. A priced model of a vendor the
    page cannot check a key for is left out: the list is what the page can offer with a straight
    face, not the whole table."""
    found: list[ModelInfo] = []
    for name in PRICES:
        vendor = vendor_behind(f"litellm_proxy/{name}")[0]
        if vendor not in _VENDOR_KEYS:
            continue
        model = f"{vendor}/{name}"
        found.append(ModelInfo(model=model, vendor=vendor, verified=profile_for(model).verified))
    return sorted(found, key=lambda m: (m.vendor, m.model))


@app.get("/api/models")
def models() -> list[ModelInfo]:
    """Models the page can offer a reader to choose from. Not a restriction: `model` on the review
    request takes any LiteLLM model string, and an unlisted one gets the conservative request
    shape."""
    return known_models()


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
    access: LLMAccess | None = None,
) -> ReviewResponse:
    """`access` is the model and key the seams were built from; None for a demo, which has
    neither."""
    try:
        check_size(request.document)
    except DocumentTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(summariser.summarise, request.document)
        report = review(request.document, spec, brain, judge=judge, system_id=request.system_id)
        summary = _summary(pending, access.api_key if access else None)
    return build_response(
        report, spec, summary, demo_note=demo_note, model=access.model if access else None
    )


@app.post("/api/review")
def post_review(
    request: ReviewRequest,
    spec: Annotated[PolicyRuleset, Depends(get_spec)],
    access: Annotated[LLMAccess, Depends(get_llm_access)],
    brain: Annotated[Brain, Depends(get_brain)],
    judge: Annotated[Judge | None, Depends(get_judge)],
    summariser: Annotated[Summariser, Depends(get_summariser)],
) -> ReviewResponse:
    """Classify the document, check it against the obligations that applies, and resolve every
    rule and norm the report names. A short summary of the system is written alongside. Takes as
    long as the model calls do.

    Runs on the model named in `model` (else the server's) and the key in the `X-LLM-API-Key`
    header (else the server's, where it holds one and `AIACT_BYOK_MODE` is not `required`).
    503 when a live review cannot run here (no model, no key, or demo-only), 400 when a key is sent
    to a server that refuses them, 502 when the model call fails — demo mode works either way."""
    try:
        return _review(request, spec, brain, judge, summariser, access=access)
    except HTTPException:
        raise
    except Exception as exc:
        # A failed model call — a missing key, a vendor outage, a proxy that refused — is the one
        # failure a reader can act on, and a bare 500 does not let them. The traceback stays in
        # the log, and the caller's key in neither: LiteLLM's errors have been probed and carry no
        # key (SECURITY.md), and this is the net behind that, not a fix for a known leak.
        log.error("The review failed\n%s", scrub(traceback.format_exc(), extra=access.api_key))
        text = scrub(str(exc), extra=access.api_key).strip()
        first_line = text.splitlines()[0] if text else type(exc).__name__
        hint = (
            f"Check the model named in the request ({access.model}) and the key sent with it."
            if access.byok
            else "Check AIACT_LLM_MODEL and the provider key in .env."
        )
        raise HTTPException(
            status_code=502,
            detail=f"The review could not be completed: {first_line[:300].rstrip('.')}. {hint}",
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
