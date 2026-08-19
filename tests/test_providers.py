"""The provider seam — vendor-specific request shaping, kept out of the brain.

These pin the two things that would silently break a cross-vendor run: sending a parameter a
provider rejects (a 400 on every call), and emitting a cache marker a provider does not understand.
"""

from __future__ import annotations

import sys
import types
from datetime import date

import pytest

from aiact.classify.llm_brain import LLMBrain
from aiact.providers import ProviderProfile, estimate_tokens, profile_for
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Question


def a_question(context: str = "") -> Question:
    return Question(
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
    """temperature/top_p/top_k are rejected outright by these models — one
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


def test_we_always_try_to_cache_where_the_provider_supports_it(capture):
    """We do NOT gate on an estimated token count. A marker on a too-short prefix is silently
    ignored at zero cost; skipping one that WOULD have qualified silently loses the saving. We
    guessed wrong by 19% once and lost every cache in a run to it — so try, and let the usage
    counters report what actually happened."""
    LLMBrain(model="anthropic/claude-opus-4-8").decide(a_question("Article 3(1)."), "a system")
    assert isinstance(capture["messages"][1]["content"], list)


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


def test_token_estimate_matches_the_measured_ratio():
    """4.75 chars/token, measured against the article store — 17,589 chars of Article 3 came back
    as 3,800 real prompt tokens. The old 4.0 guess over-counted by ~19%."""
    assert estimate_tokens("x" * 4750) == 1000


# --- cross-vendor profiles ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("model", "profile_id"),
    [
        ("anthropic/claude-opus-4-8", "anthropic-adaptive"),
        ("anthropic/claude-haiku-4-5", "anthropic-legacy"),
        ("openai/gpt-5.6-sol", "openai-reasoning"),
        ("openai/gpt-4.1", "openai-classic"),
        ("gemini/gemini-3.1-pro", "google-gemini"),
        ("vertex_ai/gemini-3-flash", "google-gemini"),
        ("mistral/mistral-large-3", "mistral"),
        ("somevendor/whatever", "generic"),
    ],
)
def test_every_shortlisted_model_resolves_to_its_own_shape(model, profile_id):
    assert profile_for(model).profile_id == profile_id


def test_anthropic_never_receives_reasoning_effort(capture):
    """THE CROSS-VENDOR TRAP. LiteLLM normalises `reasoning_effort` across OpenAI/Gemini/Mistral,
    but translates it for Anthropic into the `budget_tokens` shape their current models reject with
    a 400. The one parameter that looks portable is the one that must not be applied uniformly."""
    for model in ("anthropic/claude-opus-4-8", "anthropic/claude-haiku-4-5"):
        LLMBrain(model=model).decide(a_question(), "a system")
        assert "reasoning_effort" not in capture, model


@pytest.mark.parametrize("model", ["openai/gpt-5.6-sol", "gemini/gemini-3.1-pro"])
def test_reasoning_families_get_effort_and_no_sampling(model, capture):
    LLMBrain(model=model, effort="medium").decide(a_question(), "a system")
    assert capture["reasoning_effort"] == "medium"
    assert "temperature" not in capture, "rejected while reasoning is active"
    assert "thinking" not in capture, "that is Anthropic's spelling, not theirs"


def test_mistral_gets_temperature_not_effort(capture):
    """Large/Medium are not reasoning-tuned; sending an effort knob they don't have is a guess."""
    LLMBrain(model="mistral/mistral-large-3").decide(a_question(), "a system")
    assert capture["temperature"] == 0.0
    assert "reasoning_effort" not in capture


@pytest.mark.parametrize(
    "model", ["openai/gpt-5.6-sol", "gemini/gemini-3.1-pro", "mistral/mistral-large-3"]
)
def test_only_anthropic_gets_an_inline_cache_marker(model, capture):
    """Others cache automatically or via a separate API — neither takes an inline breakpoint."""
    LLMBrain(model=model).decide(a_question("ANNEX III " * 4000), "a system")
    assert isinstance(capture["messages"][1]["content"], str)


def test_cache_minimum_is_per_model_not_per_vendor():
    """Claude's minimum cacheable prefix spans 1024-4096 across the family. Assuming one number
    means either emitting no-op markers or silently losing caches we could have had."""
    assert profile_for("anthropic/claude-haiku-4-5").cache_min_tokens == 4096
    assert profile_for("anthropic/claude-sonnet-4-5").cache_min_tokens == 1024


def test_only_researched_profiles_claim_to_be_verified():
    for model in ("anthropic/claude-opus-4-8", "openai/gpt-5.6-sol", "mistral/mistral-large-3"):
        assert profile_for(model).verified is True
    assert profile_for("newvendor/newmodel").verified is False


# --- usage & cost ---------------------------------------------------------------------------
def test_usage_is_recorded_even_when_the_answer_is_unusable(monkeypatch):
    """A call we end up abstaining on still cost money — it must appear in the tally, or the run
    looks cheaper than it was exactly when something is going wrong."""

    def completion(**kwargs):
        message = types.SimpleNamespace(content="not json at all")
        usage = types.SimpleNamespace(prompt_tokens=3000, completion_tokens=100)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=usage)

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
    brain = LLMBrain(model="anthropic/claude-haiku-4-5")
    answer = brain.decide(a_question(), "a system")
    assert answer.confidence == "low"
    assert brain.usage.calls == 1
    assert brain.usage.input_tokens == 3000


def test_unpriced_model_reports_no_cost_rather_than_zero():
    """A silent $0 reads as 'free'. Unknown must look unknown."""
    from aiact.usage import Usage

    u = Usage(calls=1, input_tokens=1000, output_tokens=100)
    assert u.estimated_cost_usd("newvendor/newmodel") is None
    assert "no price on file" in u.summary("newvendor/newmodel")


def test_cost_uses_longest_prefix_match():
    """'gemini-3.5-flash' must not resolve to the cheaper 'gemini-3-flash' entry."""
    from aiact.usage import price_for

    assert price_for("gemini/gemini-3.5-flash").input_per_mtok == 1.50
    assert price_for("gemini/gemini-3-flash").input_per_mtok == 0.50


def test_cached_tokens_are_billed_at_the_cached_rate():
    from aiact.usage import Usage

    plain = Usage(calls=1, input_tokens=1_000_000, output_tokens=0)
    cached = Usage(calls=1, input_tokens=1_000_000, output_tokens=0, cached_input_tokens=1_000_000)
    model = "anthropic/claude-haiku-4-5"
    assert plain.estimated_cost_usd(model) == pytest.approx(1.00)
    assert cached.estimated_cost_usd(model) == pytest.approx(0.10)


def test_missing_usage_block_is_counted_not_ignored(monkeypatch):
    """A partial tally must not pass as a complete one."""

    def completion(**kwargs):
        message = types.SimpleNamespace(content='{"value": true, "confidence": "high"}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
    brain = LLMBrain(model="anthropic/claude-haiku-4-5")
    brain.decide(a_question(), "a system")
    assert brain.usage.unpriced_calls == 1
    assert "reported no usage" in brain.usage.summary(brain.model)


def test_a_cache_marker_that_was_ignored_is_reported(monkeypatch):
    """A marked prefix the provider silently ignores because the prefix
    was under its minimum, and the run reported a clean-looking cost with no hint anything was
    wrong. Reads alone could not distinguish this from "written but not yet read"."""
    from aiact.usage import Usage

    ignored = Usage(calls=6, input_tokens=20_000, output_tokens=500, cache_marked_calls=6)
    assert ignored.cache_was_ignored is True
    assert "IGNORED" in ignored.summary("anthropic/claude-haiku-4-5")

    working = Usage(
        calls=6,
        input_tokens=20_000,
        output_tokens=500,
        cache_marked_calls=6,
        cached_input_tokens=15_000,
        cache_creation_tokens=3_000,
    )
    assert working.cache_was_ignored is False
    assert "IGNORED" not in working.summary("anthropic/claude-haiku-4-5")
    assert "cache 15,000 read / 3,000 written" in working.summary("anthropic/claude-haiku-4-5")


def test_cache_writes_are_billed_at_a_premium():
    """A run that only ever WRITES the cache costs more than not caching — 1.25x on Anthropic.
    Hiding that would make a broken cache look free."""
    from aiact.usage import Usage

    model = "anthropic/claude-haiku-4-5"
    plain = Usage(calls=1, input_tokens=1_000_000)
    writing = Usage(calls=1, input_tokens=1_000_000, cache_creation_tokens=1_000_000)
    assert plain.estimated_cost_usd(model) == pytest.approx(1.00)
    assert writing.estimated_cost_usd(model) == pytest.approx(1.25)


def test_cache_marking_is_reported_through_the_brain(monkeypatch):
    def completion(**kwargs):
        message = types.SimpleNamespace(content='{"value": true, "confidence": "high"}')
        usage = types.SimpleNamespace(prompt_tokens=3800, completion_tokens=20)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=usage)

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
    brain = LLMBrain(model="anthropic/claude-haiku-4-5")
    brain.decide(a_question("ANNEX III " * 4000), "a system")
    assert brain.usage.cache_marked_calls == 1
    assert brain.usage.cache_was_ignored is True, "provider reported no cache activity"


# ==================================================================================================
# Reasoning depth: the portable "off", and the per-job split
# ==================================================================================================
def test_no_thinking_is_translated_per_vendor_never_passed_through():
    """MEASURED best setting for the judge is "no thinking" — and it is the least portable value
    there is. Gemini spells it `disable`; Anthropic's adaptive models have no off switch and want
    `thinking` omitted entirely; OpenAI's reasoning family cannot be disabled at all. Passing the
    literal through would 400 on one vendor and silently mean nothing on another."""
    from aiact.providers import NO_THINKING, profile_for

    gemini = profile_for("litellm_proxy/gemini-2.5-flash", NO_THINKING)
    assert gemini.completion_kwargs["reasoning_effort"] == "disable"

    # Anthropic adaptive: absence IS off, so the whole thinking block goes.
    adaptive = profile_for("anthropic/claude-sonnet-5", NO_THINKING)
    assert "thinking" not in adaptive.completion_kwargs
    assert "output_config" not in adaptive.completion_kwargs

    # OpenAI reasoning: cannot be turned off; clamp to the nearest honest value rather than error.
    openai = profile_for("openai/gpt-5.6-sol", NO_THINKING)
    assert openai.completion_kwargs["reasoning_effort"] == "low"

    # No profile may ever emit the portable token itself.
    for model in (
        "litellm_proxy/gemini-2.5-flash",
        "anthropic/claude-sonnet-5",
        "anthropic/claude-haiku-4-5",
        "openai/gpt-5.6-sol",
        "mistral/mistral-large-3",
    ):
        assert NO_THINKING not in str(profile_for(model, NO_THINKING).completion_kwargs)


def test_a_gateway_prefix_does_not_hide_the_vendor():
    """Routing through a LiteLLM proxy replaces the vendor in the model string. Without seeing
    through it, `litellm_proxy/gemini-2.5-flash` resolves to the UNVERIFIED generic profile: the
    call still succeeds, just without the vendor's parameters, and nothing says so."""
    from aiact.providers import profile_for, vendor_behind

    assert vendor_behind("litellm_proxy/gemini-2.5-flash") == ("gemini", "gemini-2.5-flash")
    direct = profile_for("gemini/gemini-2.5-flash", "low")
    proxied = profile_for("litellm_proxy/gemini-2.5-flash", "low")
    assert proxied.profile_id == direct.profile_id
    assert proxied.completion_kwargs == direct.completion_kwargs
    assert proxied.verified, "a proxied model must not fall back to the unverified profile"


def test_effort_is_per_job_with_a_shared_fallback(monkeypatch):
    """The jobs measured in opposite directions: the judge is best with reasoning OFF (5/6 vs
    1/6 on INADEQUATE, and cheaper), while the classifier has never been measured across levels.
    One shared setting would force a guess on whichever job was not being tuned. `grade` is a third
    job for the same reason — it reads a sentence rather than answering a question, and there is no
    ground to assume the depth that suits one suits the other."""
    from aiact.config import Settings

    # Settings reads the developer's real .env FILE, not just the process environment, so
    # monkeypatch.delenv is not enough — `_env_file=None` is what actually isolates this. Without
    # it the test passes or fails depending on whose machine it runs on.
    for key in (
        "AIACT_LLM_EFFORT",
        "AIACT_JUDGE_EFFORT",
        "AIACT_CLASSIFY_EFFORT",
        "AIACT_GRADER_EFFORT",
    ):
        monkeypatch.delenv(key, raising=False)

    shared = Settings(_env_file=None, llm_effort="high")
    assert shared.effort_for("judge") == "high"
    assert shared.effort_for("classify") == "high"
    assert shared.effort_for("grade") == "high"

    split = Settings(_env_file=None, llm_effort="high", judge_effort="none")
    assert split.effort_for("judge") == "none"
    assert split.effort_for("classify") == "high", "overriding one job must not move the other"
    assert split.effort_for("grade") == "high"

    # "none" is a VALUE in this vocabulary, not an absence, and it is a truthy string — so an
    # override set to it must win rather than falling through to the shared default.
    graded = Settings(_env_file=None, llm_effort="high", grader_effort="none")
    assert graded.effort_for("grade") == "none"
    assert graded.effort_for("judge") == "high"
