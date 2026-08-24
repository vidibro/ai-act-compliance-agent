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

from aiact.classify.llm_brain import LLMBrain, Unanswerable, _parse_bool, _parse_value
from aiact.schemas.enums import AnnexIIIArea, DerogationCondition
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Question


def a_question(node_id: str = "profiling", answer_type: str = "bool") -> Question:
    return Question(
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
    """bool("false") is True in Python, because every non-empty string is
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
    """`content` is None when the model produced no text (cut off, refusal, tool call). It must
    not fall through to value=None, which is a real verdict at two of the nodes."""
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
    assert answer.source.article == "6"
    assert answer.node_id == "profiling"


# --- an abstention actually reaches needs_review -------------------------------------------------
def test_abstention_routes_the_cascade_to_needs_review(stub_litellm):
    """The point of all the above: a low-confidence answer must escalate to a human, not produce
    a tier."""
    from aiact.classify import classify
    from aiact.schemas.enums import RiskClass

    stub_litellm("not json at all")
    result = classify("some ambiguous system", LLMBrain(model="stub/model"), "amb")
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW


# --- markdown-fenced JSON -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "content",
    [
        '{"value": true, "confidence": "high"}',
        '```json\n{"value": true, "confidence": "high"}\n```',
        '```\n{"value": true, "confidence": "high"}\n```',
        '   ```json\n{"value": true, "confidence": "high"}\n```   ',
    ],
)
def test_fenced_json_is_still_an_answer(stub_litellm, content):
    """OBSERVED IN A REAL RUN: every one of 36 calls abstained because the model wrapped its JSON
    in a ```json fence, so json.loads failed at char 0. response_format={"type": "json_object"} is
    advisory on some providers, not enforced — so the fence must be handled on our side."""
    stub_litellm(content)
    answer = LLMBrain(model="stub/model").decide(a_question(), "a system")
    assert answer.value is True
    assert answer.confidence == "high"


def test_a_fence_around_garbage_still_abstains(stub_litellm):
    """Unfencing must not turn an unreadable reply into a confident one."""
    stub_litellm("```json\nnot actually json\n```")
    answer = LLMBrain(model="stub/model").decide(a_question(), "a system")
    assert answer.confidence == "low"


# ==================================================================================================
# "the description does not say" — a THIRD state, distinct from both a verdict and a parse failure
# ==================================================================================================
def test_unknown_is_not_confused_with_the_none_verdict():
    """The whole reason UNKNOWN needs its own token: at annex_iii `null` already means "within no
    Annex III area" and at derogation "no derogation applies" — real verdicts with real
    consequences. "The text does not say" is a third thing and must not collapse into either."""
    assert _parse_value("annex_area", None) is None  # a verdict: no Annex III area
    assert _parse_value("derogation", None) is None  # a verdict: no derogation applies
    for answer_type in ("bool", "annex_area", "derogation"):
        with pytest.raises(Unanswerable):
            _parse_value(answer_type, "unknown")


@pytest.mark.parametrize("raw", ["unknown", "UNKNOWN", " Unknown "])
def test_unknown_is_accepted_however_it_is_cased(raw):
    with pytest.raises(Unanswerable):
        _parse_value("bool", raw)


def test_unknown_abstains_rather_than_answering(stub_litellm):
    """End to end: the model declines, the brain returns a low-confidence answer with no value —
    which the cascade routes to NEEDS_REVIEW rather than to a tier."""
    stub_litellm('{"value": "unknown", "reasoning": "the text never says", "confidence": "low"}')
    answer = LLMBrain(model="anthropic/claude-opus-4-8").decide(a_question(), "a vague description")
    assert answer.value is None
    assert answer.confidence == "low"
    assert answer.source is not None, "an abstention is still cited"


def test_every_question_type_is_offered_a_way_to_decline():
    """A question that permits only true or false INSTRUCTS the model to pick one, and it will —
    from what the text implies rather than what it states. That is how a system silent on what its
    ranking model optimises drew "evaluates and scores candidates" at high confidence."""
    from aiact.classify.llm_brain import _answer_instructions

    for answer_type in ("bool", "annex_area", "derogation"):
        assert "unknown" in _answer_instructions(answer_type), answer_type


# --- the quote has to be a quote ------------------------------------------------------------------
def test_a_quote_from_the_description_is_kept(stub_litellm):
    stub_litellm(
        '{"value": true, "reasoning": "it ranks", "confidence": "high",'
        ' "evidence_quote": "ranks candidates by fit"}'
    )
    answer = LLMBrain(model="stub/model").decide(
        a_question(), "The system parses CVs and ranks candidates by fit against the role."
    )
    assert answer.evidence_quote == "ranks candidates by fit"


def test_a_quote_that_is_not_in_the_description_is_dropped(stub_litellm):
    """The classifier's quote is the one line telling a user WHY their system was called high-risk.
    A paraphrase there points at a sentence they never wrote, and the fact it names — scoring — is
    exactly the fact that decides the class.

    The ANSWER stands. Measured on dev: the model invented nothing in 98 answers, and every quote
    this check rejected was a formatting slip on a correct answer."""
    stub_litellm(
        '{"value": true, "reasoning": "it scores", "confidence": "high",'
        ' "evidence_quote": "the system scores each candidate"}'
    )
    answer = LLMBrain(model="stub/model").decide(
        a_question(), "The system parses CVs and ranks candidates by fit against the role."
    )
    assert answer.value is True
    assert answer.evidence_quote is None


def test_an_answer_with_no_quote_is_still_an_answer(stub_litellm):
    """Measured on dev, this never happens — every substantive answer cited a span. Pinned anyway:
    the schema permits a null quote, so the parse path has to have a defined behaviour."""
    stub_litellm('{"value": false, "reasoning": "purely procedural", "confidence": "high"}')
    answer = LLMBrain(model="stub/model").decide(a_question(), "extracts fields from a CV")
    assert answer.value is False
    assert answer.evidence_quote is None


def test_the_prompt_forbids_reading_silence_as_denial():
    from aiact.classify.llm_brain import _SYSTEM_PROMPT

    assert "SILENCE IS NOT AN ANSWER" in _SYSTEM_PROMPT
    assert "not a description of a system that does not" in _SYSTEM_PROMPT
    # ...but reading plain language for its plain meaning is still required. Without this the rule
    # over-fires: demanding the fact appear in the QUESTION's terms cost cv_parsing_fields its
    # Annex III area ("applicant-tracking", "CVs" state a recruitment use in different words).
    assert "ordinary meaning" in _SYSTEM_PROMPT
    assert "does not address the point at all" in _SYSTEM_PROMPT
    # ...and the escape hatch is for missing FACTS, not for hard LAW — the same line the golden set
    # draws between difficulty `insufficient` and `ambiguous`. Without it the brain declined Art. 50
    # on descriptions that state the facts and leave only the legal conclusion arguable.
    assert "MISSING FACTS, not about difficult law" in _SYSTEM_PROMPT
