"""The provider seam — vendor-specific request shaping, kept out of the brain.

These pin the two things that would silently break a cross-vendor run: sending a parameter a
provider rejects (a 400 on every call), and emitting a cache marker a provider does not understand.
"""

from __future__ import annotations

import sys
import types
from datetime import date

import pytest

from aiact.graph.llm_brain import LLMBrain
from aiact.providers import ProviderProfile, estimate_tokens, profile_for
from aiact.schemas.classification import ClassificationQuestion
from aiact.schemas.policy import LegalSource


def a_question(context: str = "") -> ClassificationQuestion:
    return ClassificationQuestion(
        node_id="annex_iii",
        source=LegalSource(
            instrument="Regulation (EU) 2024/1689",
            article=6,
            paragraph=2,
            annex="III",
            act_version_date=date(2024, 7, 12),
        ),
        text="Which Annex III area, if any?",
        answer_type="annex_area",
        context=context,
    )


@pytest.fixture
def capture(monkeypatch):
    """Stub litellm and record the kwargs the brain actually sends."""
    sent: dict = {}

    def completion(**kwargs):
        sent.clear()
        sent.update(kwargs)
        message = types.SimpleNamespace(content='{"value": null, "confidence": "high"}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
    return sent


# --- parameter shaping --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "model",
    ["anthropic/claude-opus-4-8", "anthropic/claude-sonnet-5", "claude-opus-4-7"],
)
def test_current_anthropic_models_never_receive_temperature(model, capture):
    """THE 400 THIS GUARDS. temperature/top_p/top_k are rejected outright by these models — one
    stray parameter fails every call in the run."""
    LLMBrain(model=model).decide(a_question(), "a system")
    assert "temperature" not in capture
    assert "top_p" not in capture
    assert "top_k" not in capture


def test_current_anthropic_models_ask_for_thinking_explicitly(capture):
    """Thinking is OFF when the parameter is omitted — so it must be named, not assumed."""
    LLMBrain(model="anthropic/claude-opus-4-8", effort="high").decide(a_question(), "a system")
    assert capture["thinking"] == {"type": "adaptive"}
    assert capture["output_config"] == {"effort": "high"}


def test_effort_is_config_not_code(capture):
    LLMBrain(model="anthropic/claude-opus-4-8", effort="low").decide(a_question(), "a system")
    assert capture["output_config"] == {"effort": "low"}


def test_legacy_anthropic_models_still_get_temperature(capture):
    """The seam exists because the answer differs BY MODEL, not by vendor."""
    LLMBrain(model="anthropic/claude-haiku-4-5").decide(a_question(), "a system")
    assert capture["temperature"] == 0.0
    assert "thinking" not in capture


def test_unknown_providers_get_the_conservative_shape(capture):
    """An unverified provider must receive only what everything accepts — no guessed parameter
    names, because a guess is a 400 on every call."""
    LLMBrain(model="somevendor/some-model").decide(a_question(), "a system")
    assert capture["temperature"] == 0.0
    assert "thinking" not in capture
    assert "output_config" not in capture
    assert profile_for("somevendor/some-model").verified is False


def test_json_mode_is_sent_everywhere(capture):
    """The one request parameter that IS broadly portable."""
    LLMBrain(model="somevendor/some-model").decide(a_question(), "a system")
    assert capture["response_format"] == {"type": "json_object"}


# --- cache boundary -----------------------------------------------------------------------------
def test_long_verbatim_context_is_marked_as_the_cache_prefix(capture):
    """Annex III is identical for every use case at this node, so it is the stable prefix. It must
    come FIRST and carry the breakpoint — caching is a prefix match, so anything volatile ahead of
    it invalidates the lot."""
    LLMBrain(model="anthropic/claude-opus-4-8").decide(a_question("ANNEX III " * 4000), "a system")
    content = capture["messages"][1]["content"]
    assert isinstance(content, list) and len(content) == 2
    assert content[0]["cache_control"] == {"type": "ephemeral"}
    assert "ANNEX III" in content[0]["text"]
    assert "cache_control" not in content[1], "the volatile half must not be cached"
    assert "a system" in content[1]["text"]


def test_short_context_is_not_marked(capture):
    """Below the provider's minimum a marker is silently ignored — do not pretend otherwise."""
    LLMBrain(model="anthropic/claude-opus-4-8").decide(a_question("Article 3(1)."), "a system")
    assert isinstance(capture["messages"][1]["content"], str)


def test_providers_without_a_cache_surface_get_a_plain_string(capture):
    """A cache marker other vendors do not understand is at best ignored, at worst a 400."""
    LLMBrain(model="somevendor/some-model").decide(a_question("ANNEX III " * 4000), "a system")
    assert isinstance(capture["messages"][1]["content"], str)


def test_profile_can_be_injected_for_a_provider_we_have_not_profiled(capture):
    """The seam is open: a new vendor is a ProviderProfile, not an edit to the brain."""
    custom = ProviderProfile(profile_id="test", completion_kwargs={"reasoning_effort": "medium"})
    LLMBrain(model="x/y", profile=custom).decide(a_question(), "a system")
    assert capture["reasoning_effort"] == "medium"
    assert "temperature" not in capture


def test_token_estimate_is_only_used_for_the_cache_threshold():
    assert estimate_tokens("x" * 4000) == 1000
