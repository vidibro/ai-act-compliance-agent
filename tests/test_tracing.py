"""Tracing must be invisible without keys — the property CI depends on.

The whole no-op guarantee is what keeps the test suite and the ScriptedBrain path free of a Langfuse
dependency and of network. These tests pin it: with no keys, nothing registers, nothing is emitted,
and a run is byte-identical to an untraced one. The keyed path (an actual trace appearing in
Langfuse) needs real keys and is verified by hand, not here.
"""

from __future__ import annotations

import pytest

from aiact import tracing


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    """Guarantee the unconfigured environment regardless of the developer's real .env."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)


def test_unconfigured_without_keys():
    assert tracing.langfuse_configured() is False


def test_one_key_is_not_enough(monkeypatch):
    """A half-configured environment counts as OFF — a missing trace beats a run that fails trying
    to authenticate against a backend it cannot reach."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-only")
    assert tracing.langfuse_configured() is False


def test_empty_string_keys_count_as_off(monkeypatch):
    """The committed .env.example ships `LANGFUSE_PUBLIC_KEY=...`; a value that resolves to empty
    must not switch tracing on."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    assert tracing.langfuse_configured() is False


def test_enable_tracing_is_a_noop_without_keys():
    assert tracing.enable_tracing() is False


def test_trace_run_yields_and_publishes_no_context_without_keys():
    with tracing.trace_run("classify:x", session_id="x"):
        # inside the scope, but with no keys there is nothing to pick up
        assert tracing.current_metadata("profiling") is None


def test_current_metadata_is_none_outside_any_scope():
    assert tracing.current_metadata("profiling") is None


def test_trace_context_does_not_leak_after_the_scope():
    with tracing.trace_run("classify:x"):
        pass
    assert tracing.current_metadata("is_ai") is None


def test_a_classify_run_without_keys_makes_no_llm_metadata(monkeypatch):
    """End to end through the deterministic path: a full classify() run with no keys never produces
    trace metadata, so the LLM call (when there is one) is identical to the untraced call."""
    from aiact.graph import ScriptedBrain, classify

    seen: list[dict | None] = []

    class Probe(ScriptedBrain):
        def decide(self, question, description):
            seen.append(tracing.current_metadata(question.node_id))
            return super().decide(question, description)

    classify("x", Probe({"is_ai": True, "prohibited": True}), "case-x")
    assert seen and all(m is None for m in seen)
