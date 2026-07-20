"""LLMBrain — parsing the model's reply, and refusing to guess when it can't be parsed.

No network and no API key: `litellm` is stubbed, so these test OUR handling of a reply, which is
where the damage happens. The theme throughout: an unreadable answer must become an ABSTENTION
(low confidence -> NEEDS_REVIEW), never a default verdict, because at these nodes the defaults are
themselves real legal verdicts.
"""

from __future__ import annotations

import sys
import types
from datetime import date

import pytest

from aiact.graph.llm_brain import LLMBrain, Unanswerable, _parse_bool, _parse_value
from aiact.schemas.classification import ClassificationQuestion
from aiact.schemas.enums import AnnexIIIArea, DerogationCondition
from aiact.schemas.policy import LegalSource


def a_question(node_id: str = "profiling", answer_type: str = "bool") -> ClassificationQuestion:
    return ClassificationQuestion(
        node_id=node_id,
        source=LegalSource(
            instrument="Regulation (EU) 2024/1689",
            article=6,
            paragraph=3,
            act_version_date=date(2024, 7, 12),
        ),
        text="Does this use case perform profiling of natural persons?",
        answer_type=answer_type,
    )


@pytest.fixture
def stub_litellm(monkeypatch):
    """Install a fake `litellm` whose completion returns a chosen `content`."""

    def _install(content: str | None):
        message = types.SimpleNamespace(content=content)
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])
        module = types.SimpleNamespace(completion=lambda **kwargs: response)
        monkeypatch.setitem(sys.modules, "litellm", module)

    return _install


# --- the string-"false" trap -------------------------------------------------------------------
@pytest.mark.parametrize("raw", [False, "false", "False", " FALSE ", "no", "n", "0", 0])
def test_falsey_answers_are_read_as_false(raw):
    """THE BUG THIS GUARDS. bool("false") is True in Python, because every non-empty string is
    truthy. At the profiling node that inverts the answer and routes the use case to high_risk via
    the Art. 6(3) carve-back — confidently, and wrongly."""
    assert _parse_bool(raw) is False


@pytest.mark.parametrize("raw", [True, "true", "TRUE", " yes ", "y", "1", 1])
def test_truthy_answers_are_read_as_true(raw):
    assert _parse_bool(raw) is True


@pytest.mark.parametrize("raw", ["maybe", "", None, "unclear", 7, [], {"a": 1}])
def test_unrecognised_booleans_refuse_to_guess(raw):
    with pytest.raises(Unanswerable):
        _parse_bool(raw)


def test_string_false_no_longer_flips_the_profiling_verdict(stub_litellm):
    """End to end through decide(): the model says "false" as a string; the answer must be False,
    not a high-confidence True."""
    stub_litellm('{"value": "false", "reasoning": "purely procedural", "confidence": "high"}')
    answer = LLMBrain(model="stub/model").decide(a_question(), "extracts fields from a CV")
    assert answer.value is False
    assert answer.confidence == "high"  # a parseable answer keeps the model's own confidence


# --- None is a verdict, not missing data --------------------------------------------------------
@pytest.mark.parametrize("raw", [None, "none", "null", "", "  NULL  "])
def test_nothing_here_normalises_to_none(raw):
    """At annex_iii, None means 'no Annex III area' -> minimal risk. It is a real answer."""
    assert _parse_value("annex_area", raw) is None


def test_known_enum_values_parse():
    assert _parse_value("annex_area", "employment") is AnnexIIIArea.EMPLOYMENT
    assert (
        _parse_value("derogation", "narrow_procedural_task")
        is DerogationCondition.NARROW_PROCEDURAL_TASK
    )


@pytest.mark.parametrize(
    ("answer_type", "raw"),
    [("annex_area", "hr_stuff"), ("derogation", "seems_fine")],
)
def test_unknown_enum_values_abstain_instead_of_crashing(answer_type, raw):
    """Previously raised a bare ValueError out of the graph, killing the run. An invented area is
    a failure to answer, not a crash — and must not be folded into None, which IS a verdict."""
    with pytest.raises(Unanswerable):
        _parse_value(answer_type, raw)


# --- unusable replies escalate ------------------------------------------------------------------
@pytest.mark.parametrize("content", [None, "", "   "])
def test_empty_completion_abstains(stub_litellm, content):
    """`content` is None when the model produced no text (cut off, refusal, tool call). It used to
    fall back to "{}", which read as value=None — a real verdict at two of the nodes."""
    stub_litellm(content)
    answer = LLMBrain(model="stub/model").decide(a_question("annex_iii", "annex_area"), "a system")
    assert answer.confidence == "low"
    assert answer.value is None
    assert "empty completion" in answer.reasoning


def test_non_json_reply_abstains(stub_litellm):
    stub_litellm("I'm sorry, I can't help with that.")
    answer = LLMBrain(model="stub/model").decide(a_question(), "a system")
    assert answer.confidence == "low"
    assert "not valid JSON" in answer.reasoning


def test_json_that_is_not_an_object_abstains(stub_litellm):
    stub_litellm("[1, 2, 3]")
    answer = LLMBrain(model="stub/model").decide(a_question(), "a system")
    assert answer.confidence == "low"


def test_unparseable_value_abstains(stub_litellm):
    stub_litellm('{"value": "probably", "confidence": "high"}')
    answer = LLMBrain(model="stub/model").decide(a_question(), "a system")
    assert answer.confidence == "low", "a high-confidence unreadable answer is still no answer"
    assert "unusable answer" in answer.reasoning


def test_every_abstention_is_still_cited(stub_litellm):
    """Abstaining does not exempt an answer from the citation rule."""
    stub_litellm(None)
    answer = LLMBrain(model="stub/model").decide(a_question(), "a system")
    assert answer.source.article == 6
    assert answer.node_id == "profiling"


# --- an abstention actually reaches needs_review -------------------------------------------------
def test_abstention_routes_the_cascade_to_needs_review(stub_litellm):
    """The point of all the above: a low-confidence answer must escalate to a human, not produce
    a tier."""
    from aiact.graph import classify
    from aiact.schemas.enums import RiskClass

    stub_litellm("not json at all")
    result = classify("some ambiguous system", LLMBrain(model="stub/model"), "amb")
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
