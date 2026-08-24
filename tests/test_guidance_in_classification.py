"""Path 2 — non-binding Commission guidance reaches the classifier and surfaces in the verdict.

The point (see the workplace/recruitment case): Art. 5(1)(f) prohibits emotion recognition "in the
workplace" but the Act never says whether hiring counts, so a model reading Art. 5 alone can only
guess. The authoritative interpretation is supplied to the node, labelled non-binding, and any
verdict reached with it must SAY it rested on interpretation, not enacted law.

Driven with ScriptedBrain — no LLM, no API key — because this is graph wiring, not model behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aiact.classify.graph import classify, load_questions
from aiact.classify.scripted_brain import ScriptedBrain
from aiact.schemas.enums import ProhibitedPractice, RiskClass
from aiact.schemas.policy import GuidanceSource

ROOT = Path(__file__).resolve().parents[1]
ARTS = ROOT / "data" / "policy" / "articles"
ANNS = ROOT / "data" / "policy" / "annexes"
GUID = ROOT / "data" / "policy" / "guidance"
REF = "C-2025-5052/workplace-covers-recruitment"


def anchored():
    return load_questions("2026-07-27", ARTS, ANNS, GUID)


# --- the GuidanceSource type --------------------------------------------------------------------
def test_guidance_source_cannot_be_binding():
    """Structural guarantee: a 'binding guidance source' is unconstructable — enacted law is cited
    with LegalSource, not this."""
    with pytest.raises(ValidationError, match="must be False"):
        GuidanceSource(
            issuer="European Commission",
            reference="C(2025) 5052 final",
            snippet_ref=REF,
            locator="para 254",
            binding=True,
        )


def test_a_snippet_becomes_a_guidance_source():
    from aiact.guidance import load_snippet

    src = load_snippet(REF, GUID).to_source()
    assert src.reference == "C(2025) 5052 final"
    assert src.snippet_ref == REF
    assert "254" in src.locator
    assert src.binding is False


# --- guidance is attached only where the enacted text is open -----------------------------------
def test_guidance_is_attached_to_the_prohibited_node_only():
    q = anchored()
    assert q["prohibited"].guidance_context, "Art. 5 leaves 'workplace covers hiring?' open"
    assert q["prohibited"].guidance_sources[0].snippet_ref == REF
    # the verbatim interpretive sentence is actually in the prompt context
    assert "candidates during the selection and hiring process" in q["prohibited"].guidance_context
    # every other node is guidance-free
    for node_id in ("is_ai", "annex_iii", "profiling", "derogation", "transparency"):
        assert q[node_id].guidance_context == "", f"{node_id} should carry no guidance"
        assert q[node_id].guidance_sources == ()


def test_bare_questions_carry_no_guidance():
    """The deterministic path stays file-IO-free: the bare QUESTIONS constant has no guidance."""
    from aiact.classify.graph import QUESTIONS

    assert all(q.guidance_context == "" for q in QUESTIONS.values())
    assert all(q.guidance_sources == () for q in QUESTIONS.values())


# --- the verdict records it rested on non-binding interpretation --------------------------------
def test_a_prohibited_verdict_carries_the_guidance_it_rested_on():
    brain = ScriptedBrain({"is_ai": True, "prohibited": ProhibitedPractice.SOCIAL_SCORING})
    result = classify("emotion recognition in recruitment", brain, "rec", questions=anchored())

    assert result.overall_risk_class == RiskClass.PROHIBITED
    assert result.rests_on_guidance is True
    assert [g.reference for g in result.guidance_sources] == ["C(2025) 5052 final"]

    # the guidance rides on the deciding node's evidence, next to (not merged with) the law
    prohibited_ev = next(e for e in result.triggered_by if e.node_id == "prohibited")
    assert prohibited_ev.source.article == "5"  # enacted law
    assert prohibited_ev.guidance[0].snippet_ref == REF  # non-binding interpretation, distinct


def test_guidance_flows_without_an_llm():
    """The attach happens in the GRAPH, not the brain — so even the scripted path carries it, and
    no brain needs to know guidance exists."""
    result = classify(
        "x",
        ScriptedBrain({"is_ai": True, "prohibited": ProhibitedPractice.SOCIAL_SCORING}),
        "x",
        questions=anchored(),
    )
    assert result.rests_on_guidance is True


def test_a_verdict_decided_without_the_guidance_node_does_not_cite_it():
    """Not-an-AI-system exits before the prohibited node; guidance was never consulted, so the
    verdict must not claim it rested on interpretation."""
    result = classify(
        "a plain SQL report", ScriptedBrain({"is_ai": False}), "sql", questions=anchored()
    )
    assert result.overall_risk_class == RiskClass.MINIMAL
    assert result.rests_on_guidance is False
    assert result.guidance_sources == []


def test_guidance_is_deduplicated_in_the_result():
    result = classify(
        "x",
        ScriptedBrain({"is_ai": True, "prohibited": ProhibitedPractice.SOCIAL_SCORING}),
        "x",
        questions=anchored(),
    )
    refs = [g.snippet_ref for g in result.guidance_sources]
    assert refs == list(dict.fromkeys(refs)), "no duplicate guidance citations"


# --- the LLM prompt actually contains the guidance ----------------------------------------------
def test_the_llm_prompt_includes_labelled_non_binding_guidance():
    from aiact.classify.llm_brain import LLMBrain

    q = anchored()["prohibited"]
    content = LLMBrain(model="anthropic/claude-opus-4-8")._user_content(q, "a use case")
    text = content if isinstance(content, str) else " ".join(p["text"] for p in content)
    assert "NON-BINDING" in text
    assert "candidates during the selection and hiring process" in text  # the guidance passage
    assert "Enacted text" in text  # kept distinct from the law


def test_an_abstention_does_not_claim_to_rest_on_guidance():
    """A node that declined rested on nothing. Attaching the guidance anyway made the report warn
    that a verdict leaned on non-binding Commission interpretation when no verdict was reached."""
    from aiact.brain import Brain  # noqa: F401
    from aiact.schemas.question import Answer

    class Declining:
        name = "declining"

        def decide(self, question, description):
            if question.node_id == "is_ai":
                return Answer(
                    value=True,
                    reasoning="yes",
                    confidence="high",
                    source=question.source,
                    node_id="is_ai",
                )
            return Answer(
                value=None,
                reasoning="declined",
                confidence="low",
                source=question.source,
                node_id=question.node_id,
                abstained_because="description_silent",
            )

    result = classify("a vague description", Declining(), "vague", questions=anchored())
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
    assert result.rests_on_guidance is False
    assert result.guidance_sources == []
