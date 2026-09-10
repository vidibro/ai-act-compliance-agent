"""`reasoning` is the only free text a model writes into a report."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from aiact.schemas.enums import ActorRole, Verdict
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import REASONING_MAX, Answer, clip_reasoning
from aiact.schemas.report import Finding

SOURCE = LegalSource(
    instrument="Regulation (EU) 2024/1689", article=6, act_version_date=date(2024, 7, 12)
)


def test_a_short_reason_is_untouched():
    assert clip_reasoning("It scores applicants.") == "It scores applicants."


def test_whitespace_is_flattened():
    """A model that returns a wrapped paragraph must not widen every report line."""
    assert clip_reasoning("one\n  two\tthree") == "one two three"


def test_a_long_reason_is_clipped_and_marked():
    clipped = clip_reasoning("x" * (REASONING_MAX * 3))
    assert len(clipped) == REASONING_MAX
    assert clipped.endswith("…")


def test_the_clip_output_always_satisfies_the_schema():
    answer = Answer(
        value=True,
        reasoning=clip_reasoning("y" * 5_000),
        confidence="high",
        source=SOURCE,
    )
    assert len(answer.reasoning) <= REASONING_MAX


@pytest.mark.parametrize("model", ["answer", "finding"])
def test_an_unclipped_reason_is_refused(model):
    """The backstop. Every call site clips, so reaching this is a bug, not a long document."""
    long = "z" * (REASONING_MAX + 1)
    with pytest.raises(ValidationError):
        if model == "answer":
            Answer(value=True, reasoning=long, confidence="high", source=SOURCE)
        else:
            Finding(
                rule_id="AIA-HR-A14",
                use_case_id="u",
                role=ActorRole.PROVIDER,
                verdict=Verdict.GAP,
                reasoning=long,
                citation=SOURCE,
                confidence="high",
            )


def test_a_model_paragraph_becomes_a_clipped_answer_not_a_crash(monkeypatch):
    """End to end through decide(): an overlong reason must not turn a usable answer into an
    exception halfway through a run."""
    import sys
    import types

    from aiact.classify.llm_brain import LLMBrain
    from aiact.schemas.question import Question

    body = '{"value": true, "reasoning": "%s", "confidence": "high"}' % ("w" * 4_000)
    message = types.SimpleNamespace(content=body)
    response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])
    monkeypatch.setitem(
        sys.modules, "litellm", types.SimpleNamespace(completion=lambda **kw: response)
    )
    question = Question(node_id="profiling", source=SOURCE, text="?", answer_type="bool")

    answer = LLMBrain(model="stub/model").decide(question, "a system")

    assert answer.value is True
    assert len(answer.reasoning) == REASONING_MAX
