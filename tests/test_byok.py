"""Bring-your-own-key on the report app: the caller's key and model run the review, and the key
goes nowhere else.

The key arrives in the `X-LLM-API-Key` header and the model in the body. Three things are pinned:
that every model call of a review — the brain's, the judge's, the summariser's — is made with that
key and that model; that the server's three switches (`AIACT_BYOK_MODE`) do what they say; and the
promise SECURITY.md makes: the key is in no response, no log line, no trace metadata and no vector
store, and is not echoed when it is refused.
"""

from __future__ import annotations

import logging
import re
import sys
import types
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from aiact import tracing
from aiact.classify.llm_brain import LLMBrain
from aiact.classify.scripted_brain import ScriptedBrain
from aiact.gap.judge import LLMJudge
from aiact.report_app.app import (
    BYOK_HEADER,
    LLMAccess,
    app,
    get_brain,
    live_unavailable_because,
)
from aiact.retrieval.store import DocumentIndex
from aiact.schemas.enums import AnnexIIIArea
from aiact.summary import LLMSummariser
from conftest import StubEmbedding
from test_providers import a_question

KEY = "sk-byok-NOTAREALKEY-0123456789abcdef"
MODEL = "openai/gpt-4.1"
DOCUMENT = (
    "# System card\n\n## Human oversight\n\nA panel reviews every recommendation.\n\n"
    "## Accuracy\n\nAccuracy is measured on a held-out set.\n"
)
HIGH_RISK = {
    "is_ai": True,
    "prohibited": None,
    "annex_iii": AnnexIIIArea.EMPLOYMENT,
    "profiling": True,
}

# One reply every seam can read: a verdict for the judge, a name and summary for the summariser,
# and a value for the brain where a test lets it run.
REPLY = (
    '{"verdict": "gap", "reasoning": "Nothing about this obligation.", "confidence": "high", '
    '"name": "TalentRank", "summary": "Scores job applicants.", "value": true}'
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def server(monkeypatch) -> None:
    """A server with a model configured and NO key of its own, talking to the vendor direct."""
    monkeypatch.setenv("AIACT_LLM_MODEL", "anthropic/claude-haiku-4-5")
    for name in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "OPENAI_API_KEY",
        "LITELLM_PROXY_URL",
        "AIACT_LLM_API_BASE",
        "LITELLM_PROXY_API_KEY",
        "AIACT_BYOK_MODE",
        "AIACT_DEMO_MODE",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def completion(monkeypatch) -> list[dict]:
    """A fake `litellm.completion` that records every call's kwargs and answers `REPLY`."""
    calls: list[dict] = []

    def fake(**kwargs):  # noqa: ANN001
        calls.append(kwargs)
        message = types.SimpleNamespace(content=REPLY)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=None)

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=fake))
    return calls


@pytest.fixture
def live_judge(monkeypatch) -> list[DocumentIndex]:
    """The real judge with the offline embedder, keeping every index it builds for inspection.

    Swapped in beneath the judge's own `index_for`, whose lock stays: the graph judges
    concurrently, and Chroma's ephemeral client is not safe to create from several threads."""
    built: list[DocumentIndex] = []

    class OfflineIndex(DocumentIndex):
        @classmethod
        def build(cls, text: str, **kwargs: object) -> DocumentIndex:
            index = super().build(text, embedding_function=StubEmbedding(), **kwargs)  # type: ignore[arg-type]
            built.append(index)
            return index

    monkeypatch.setattr("aiact.gap.judge.DocumentIndex", OfflineIndex)
    return built


def scripted_brain() -> None:
    app.dependency_overrides[get_brain] = lambda: ScriptedBrain(HIGH_RISK)


# ---- the key and the model reach every call ------------------------------------------------------


def test_the_caller_s_key_and_model_are_used_on_every_model_call(
    client, server, completion, live_judge
):
    """The judge and the summariser are the real ones here; the brain is scripted so the review
    reaches the obligation check, which is where most of the calls are."""
    scripted_brain()
    response = client.post(
        "/api/review",
        json={"document": DOCUMENT, "model": MODEL},
        headers={BYOK_HEADER: KEY},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == MODEL and body["demo"] is False
    assert body["report"]["findings"] and body["system_name"] == "TalentRank"
    assert len(completion) > 1  # the judge's calls and the summariser's
    assert all(call["api_key"] == KEY for call in completion)
    assert all(call["model"] == MODEL for call in completion)


@pytest.mark.parametrize(
    "seam",
    [
        lambda: LLMBrain(model=MODEL, api_key=KEY).decide(a_question(), "a system"),
        lambda: LLMSummariser(model=MODEL, api_key=KEY).summarise("a document"),
    ],
)
def test_each_seam_passes_the_key_it_was_built_with(completion, seam, server):
    seam()
    [call] = completion
    assert call["api_key"] == KEY and call["model"] == MODEL


def test_the_caller_s_key_wins_over_the_server_s(
    client, server, completion, live_judge, monkeypatch
):
    """Their key, their bill — even where the server holds one for the same vendor."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-the-operators-own-key-000000")
    scripted_brain()
    client.post(
        "/api/review", json={"document": DOCUMENT, "model": MODEL}, headers={BYOK_HEADER: KEY}
    )
    assert completion and all(call["api_key"] == KEY for call in completion)


def test_the_caller_s_key_replaces_the_proxy_s(completion, server, monkeypatch):
    """With a proxy configured, the caller's key is the credential the proxy sees."""
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://proxy.example/")
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "sk-proxy-key-000000000")
    LLMSummariser(model="litellm_proxy/gemini-2.5-flash", api_key=KEY).summarise("a document")
    [call] = completion
    assert call["api_key"] == KEY and call["api_base"] == "http://proxy.example"


def test_without_a_caller_key_the_call_is_made_as_before(completion, server, monkeypatch):
    """No key on the request: nothing is passed and LiteLLM reads the vendor's own variable."""
    LLMSummariser(model=MODEL).summarise("a document")
    assert "api_key" not in completion[-1]
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://proxy.example")
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "sk-proxy-key-000000000")
    LLMSummariser(model=MODEL).summarise("a document")
    assert completion[-1]["api_key"] == "sk-proxy-key-000000000"


def test_a_model_alone_runs_on_the_server_s_key_for_that_vendor(
    client, server, completion, live_judge, monkeypatch
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-the-operators-own-key-000000")
    scripted_brain()
    body = client.post("/api/review", json={"document": DOCUMENT, "model": MODEL}).json()
    assert body["model"] == MODEL
    assert completion and all(call["model"] == MODEL for call in completion)
    assert all("api_key" not in call for call in completion)  # LiteLLM reads the environment


def test_a_model_the_server_holds_no_key_for_needs_one_from_the_caller(client, server):
    scripted_brain()
    response = client.post("/api/review", json={"document": DOCUMENT, "model": MODEL})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert MODEL in detail and BYOK_HEADER in detail
    assert "OPENAI" not in detail and "API_KEY" not in detail  # provider-agnostic, as ever


@pytest.mark.parametrize("model", ["", "../x", "a model", "anthropic/claude?x", "x" * 201])
def test_a_model_string_that_is_not_a_model_string_is_refused(client, server, model):
    response = client.post("/api/review", json={"document": DOCUMENT, "model": model})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "model",
    [
        "anthropic/claude-haiku-4-5",
        "litellm_proxy/gemini-2.5-flash",
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "vertex_ai/gemini-1.5-pro@001",
        "openrouter/anthropic/claude-3.5-sonnet",
    ],
)
def test_the_model_strings_litellm_routes_are_accepted(model):
    from aiact.report_app.app import ReviewRequest

    assert ReviewRequest(document="x", model=model).model == model


# ---- the server's switch -----------------------------------------------------------------------


def test_a_server_without_a_key_tells_the_page_a_reader_can_bring_one(client, server):
    info = client.get("/api/mode").json()
    assert info["live_available"] is False  # not on the server's own configuration
    assert BYOK_HEADER in info["live_unavailable_because"]
    assert info["byok"] == {
        "mode": "available",
        "header": BYOK_HEADER,
        "key_required": True,
        "model_required": False,
        "model_pattern": info["byok"]["model_pattern"],
    }
    assert re.match(info["byok"]["model_pattern"], MODEL)
    assert not re.match(info["byok"]["model_pattern"], "a model")


def test_a_server_with_its_own_key_tells_the_page_a_key_is_optional(client, server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-the-operators-own-key-000000")
    info = client.get("/api/mode").json()
    assert info["live_available"] is True
    assert info["byok"]["key_required"] is False and info["byok"]["model_required"] is False


def test_a_server_without_a_model_tells_the_page_to_name_one(client, server, monkeypatch):
    monkeypatch.setenv("AIACT_LLM_MODEL", "")
    info = client.get("/api/mode").json()
    assert info["live_available"] is False
    assert "AIACT_LLM_MODEL is empty" in info["live_unavailable_because"]
    assert info["byok"]["model_required"] is True
    # And a request that names one, with a key, runs.
    assert live_unavailable_because(LLMAccess(model=MODEL, api_key=KEY)) is None
    assert live_unavailable_because(LLMAccess(model="", api_key=KEY)) is not None


def test_required_means_the_server_s_keys_are_never_spent(
    client, server, completion, live_judge, monkeypatch
):
    monkeypatch.setenv("AIACT_BYOK_MODE", "required")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-the-operators-own-key-000000")
    scripted_brain()

    info = client.get("/api/mode").json()
    assert info["live_available"] is False and info["byok"]["key_required"] is True
    assert "bring-your-own-key" in info["live_unavailable_because"]

    refused = client.post("/api/review", json={"document": DOCUMENT})
    assert refused.status_code == 503
    assert BYOK_HEADER in refused.json()["detail"] and "demo mode" in refused.json()["detail"]
    assert completion == []

    ran = client.post("/api/review", json={"document": DOCUMENT}, headers={BYOK_HEADER: KEY})
    assert ran.status_code == 200
    assert ran.json()["model"] == "anthropic/claude-haiku-4-5"  # the server's model, their key
    assert completion and all(call["api_key"] == KEY for call in completion)


def test_off_refuses_a_caller_s_key_and_says_so(client, server, completion, monkeypatch):
    monkeypatch.setenv("AIACT_BYOK_MODE", "off")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-the-operators-own-key-000000")
    scripted_brain()

    assert client.get("/api/mode").json()["byok"]["mode"] == "off"
    response = client.post("/api/review", json={"document": DOCUMENT}, headers={BYOK_HEADER: KEY})
    assert response.status_code == 400
    assert "AIACT_BYOK_MODE=off" in response.json()["detail"]
    assert completion == []
    # Without the header, the server's own configuration serves as before.
    assert live_unavailable_because(LLMAccess(model="anthropic/claude-haiku-4-5")) is None
    # And where that configuration is short of a key, the reason offers no header to try.
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    info = client.get("/api/mode").json()
    assert info["byok"]["key_required"] is False  # there is no key a reader could bring
    assert BYOK_HEADER not in info["live_unavailable_because"]


def test_the_demo_review_ignores_the_key_and_calls_no_model(client, server, completion):
    response = client.post(
        "/api/demo/review", json={"document": DOCUMENT, "model": MODEL}, headers={BYOK_HEADER: KEY}
    )
    assert response.status_code == 200
    assert response.json()["demo"] is True and response.json()["model"] is None
    assert completion == []


def test_an_empty_header_is_no_key(client, server):
    scripted_brain()
    response = client.post("/api/review", json={"document": DOCUMENT}, headers={BYOK_HEADER: "  "})
    assert response.status_code == 503  # as if no header: the server has no key of its own


def test_the_page_is_offered_the_priced_models(client):
    listed = client.get("/api/models").json()
    models = {m["model"] for m in listed}
    assert "anthropic/claude-haiku-4-5" in models and "gemini/gemini-2.5-flash" in models
    assert all(m["vendor"] == m["model"].split("/")[0] for m in listed)
    assert all(m["verified"] for m in listed), "every listed model has a checked request shape"
    assert listed == sorted(listed, key=lambda m: (m["vendor"], m["model"]))


# ---- the key goes nowhere else -----------------------------------------------------------------


def _is_the_summariser(kwargs: dict) -> bool:
    return kwargs["messages"][-1]["content"].startswith("Summarise this documentation")


@pytest.mark.parametrize(
    ("fails", "status", "logged"),
    [
        (lambda kwargs: True, 502, "The review failed"),
        (_is_the_summariser, 200, "The system summary could not be written"),
    ],
    ids=["every call fails: the 502", "the summary fails: logged and swallowed"],
)
def test_the_key_is_in_no_response_log_trace_or_index(
    client, server, completion, live_judge, caplog, monkeypatch, fails, status, logged
):
    """The whole promise, end to end, on a review whose model calls FAIL with the key in the
    error — the paths that format exceptions and tracebacks into text are where a secret would
    be pasted. (LiteLLM's own errors carry no key, as far as probed; the net is for the day that
    changes.) Two such paths: the judge's failure becomes the 502, and the summariser's, raised
    in its own thread beside a review that succeeds, is logged and swallowed."""

    def failing(**kwargs):  # noqa: ANN001
        if fails(kwargs):
            raise RuntimeError(f"AuthenticationError: invalid key {kwargs['api_key']}")
        message = types.SimpleNamespace(content=REPLY)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=None)

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=failing))
    scripted_brain()

    with caplog.at_level(logging.DEBUG):
        response = client.post(
            "/api/review",
            json={"document": DOCUMENT, "model": MODEL},
            headers={BYOK_HEADER: KEY},
        )

    assert response.status_code == status
    if status == 502:
        assert "invalid key" in response.json()["detail"]
    else:
        assert response.json()["system_summary"] is None and response.json()["report"]["findings"]
    assert KEY not in response.text
    assert logged in caplog.text and "invalid key" in caplog.text
    assert KEY not in caplog.text
    assert live_judge, "the judge built an index"
    for index in live_judge:
        assert KEY not in repr(index.chunks)
        held = index._collection.get(include=["documents", "metadatas"])
        assert KEY not in repr(held)


def test_trace_metadata_is_the_allow_list_and_nothing_else():
    """What keeps a key out of Langfuse is that the metadata is built from a fixed set of fields
    (`tracing.current_metadata`), none of which is a credential. Pinned by shape: a field added
    here is a field added to every trace, and must be argued for."""
    token = tracing._current.set({"trace_id": "t", "trace_name": "n", "session_id": "s"})
    try:
        metadata = tracing.current_metadata("annex_iii")
    finally:
        tracing._current.reset(token)
    assert metadata is not None
    assert set(metadata) == {"trace_id", "trace_name", "session_id", "generation_name", "tags"}
    assert KEY not in repr(metadata)


def test_the_key_is_not_in_the_access_repr_or_the_seams():
    access = LLMAccess(model=MODEL, api_key=KEY)
    assert KEY not in repr(access) and KEY not in str(access)
    for seam in (
        LLMBrain(model=MODEL, api_key=KEY),
        LLMJudge(model=MODEL, api_key=KEY),
        LLMSummariser(model=MODEL, api_key=KEY),
    ):
        assert KEY not in repr(seam)
        assert KEY not in repr(seam.profile) and KEY not in repr(seam.usage)


@pytest.mark.parametrize("bad", ["sk-has a space", "sk-non-ascii-é", "k" * 2049])
def test_a_malformed_key_is_refused_without_being_echoed(client, server, bad):
    response = client.post(
        "/api/review", json={"document": DOCUMENT}, headers={BYOK_HEADER: bad.encode("latin-1")}
    )
    assert response.status_code == 400
    assert bad not in response.text and "latin" not in response.text
    assert BYOK_HEADER in response.json()["detail"]


def test_a_google_key_shape_is_scrubbed():
    from aiact.scrubbing import REDACTED, scrub

    google = "AIza" + "S" * 35
    assert scrub(f"failed for {google}") == f"failed for {REDACTED}"


# ---- the page ----------------------------------------------------------------------------------
# Pinned the way the rest of the page is (see test_demo_mode): on the files the server serves. A
# browser run of the same page is in the task notes; there is no JS runner in this project.


def _page(client) -> tuple[str, str, str]:
    return (
        client.get("/").text,
        client.get("/static/report.js").text,
        client.get("/static/report.css").text,
    )


def test_the_page_carries_a_model_field_and_a_key_field(client):
    page, script, styles = _page(client)
    block = page.split('id="byok"')[1].split("</fieldset>")[0]
    assert "edit-only live-only" in page.split('id="byok"')[0][-80:]  # hidden in demo, and in view
    assert 'id="model"' in block and 'list="models"' in block and 'id="models"' in block
    assert 'id="api-key"' in block and 'type="password"' in block.split('id="api-key"')[1][:80]
    # Each field has a message of its own, and the block says what the fields are for.
    assert 'id="model-error"' in block and 'id="api-key-error"' in block and 'role="alert"' in block
    assert 'id="byok-why"' in block
    assert ".field-error" in styles and '.field input[aria-invalid="true"]' in styles
    assert "/api/models" in script and "function byokWhy()" in script


def test_the_key_is_kept_nowhere(client):
    """Never displayed, never stored, never past a reload: the promise the page makes beside the
    field, checked against the code that would break it."""
    page, script, _ = _page(client)
    field = page.split('id="api-key"')[1].split(">")[0]
    assert 'type="password"' in field  # never displayed
    assert 'autocomplete="off"' in field  # never restored by the browser on reload
    # Nothing that writes to storage touches the field, and the draft does not carry it.
    draft = script.split("function saveDraft()", 1)[1].split("\n}\n", 1)[0]
    assert "api-key" not in draft and '$("model").value' in draft  # the model, never the key
    for line in script.splitlines():
        if "api-key" in line:
            assert not any(w in line for w in ("store(", "localStorage", "console.")), line
    # The key goes from the field into the one request that sends it — in the header, not the body.
    run = script.split("async function runReview(event)", 1)[1].split("\n}\n", 1)[0]
    assert 'headers[byok().header || "X-LLM-API-Key"] = inputs.key' in run
    assert "inputs.key" not in run.split("body: JSON.stringify(")[1]
    assert "inputs.model ? { model: inputs.model }" in run
    # And it is cleared when the page goes.
    assert 'window.addEventListener("pagehide", () => { $("api-key").value = ""; });' in script
    assert "console." not in script


def test_the_page_validates_what_the_server_would_refuse(client):
    """The model pattern comes from the server (one source of truth); the key's shape and
    length mirror `_caller_key`, so a refusal is explained before a request is made."""
    from aiact.report_app.app import _KEY_MAX_LENGTH

    _, script, _ = _page(client)
    assert "new RegExp(info.model_pattern)" in script
    assert f"const KEY_MAX_LENGTH = {_KEY_MAX_LENGTH};" in script
    assert "const KEY_SHAPE = /^[\\x21-\\x7e]+$/;" in script
    assert "function modelError(value)" in script and "function keyError(value)" in script
    run = script.split("async function runReview(event)", 1)[1].split("\n}\n", 1)[0]
    assert run.index("if (!inputs) return;") < run.index("setBusy(true)")  # refused before busy


def test_the_page_is_not_locked_into_demo_where_a_key_would_do(client):
    """Without a server key the page used to lock into demo mode. A reader can now bring one, so
    the lock turns on only where no key would help: demo-only, or a server that refuses keys."""
    _, script, _ = _page(client)
    assert (
        "const liveReachable = () => modeInfo.live_available || "
        '(modeInfo.demo_mode !== "only" && byok().mode !== "off");'
    ) in script
    assert 'const demoLocked = () => modeInfo.demo_mode !== "off" && !liveReachable();' in script
    assert 'const stuck = modeInfo.demo_mode === "off" && !liveReachable();' in script


def test_demo_mode_is_unchanged_by_the_fields(client):
    """A demo review calls no model: it sends neither a model nor a key, and the fields are not
    shown beside the cases."""
    page, script, _ = _page(client)
    assert "live-only" in page.split('id="byok"')[0][-80:]
    run = script.split("async function runReview(event)", 1)[1].split("\n}\n", 1)[0]
    assert 'const inputs = inDemo ? { model: "", key: "" } : byokInputs();' in run
    assert 'const shown = info.mode !== "off" && modeInfo.demo_mode !== "only";' in script


def test_a_report_says_which_model_wrote_it(client):
    _, script, _ = _page(client)
    assert 'data.model ? el("span", {}, "Model ", el("b", {}, data.model)) : null' in script
