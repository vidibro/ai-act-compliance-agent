"""M3 — classification graph routing tests.

These prove the GRAPH LOGIC (which node follows which, how sub-answers become a risk class),
deterministically, with no LLM. A ScriptedBrain is built from each Layer 1 golden case's known
sub-answers; the graph must route them to that case's expected risk class. The headline is
`test_graph_reproduces_every_layer1_case` — and inside it, the flip.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from aiact.classify import ScriptedBrain, build_graph, classify
from aiact.eval.classification_cases import load_classification_cases
from aiact.schemas.classification import ClassificationAnswer
from aiact.schemas.enums import AnnexIIIArea, DerogationCondition, RiskClass
from aiact.schemas.eval import ClassificationCase
from aiact.schemas.policy import LegalSource

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "golden_set" / "classification_cases.yaml"


@pytest.fixture(scope="module")
def cases():
    return load_classification_cases(CASES_PATH)


def _brain_from_case(case: ClassificationCase) -> ScriptedBrain:
    """Feed the graph the case's KNOWN sub-answers. The graph's job is to route them correctly —
    reading the text is the LLMBrain's job, tested separately."""
    answers = {
        "is_ai": True,  # every Layer 1 case is an AI system
        "prohibited": case.expected_prohibited,
        "annex_i": case.expected_annex_i_product,
        "third_party_assessment": case.expected_third_party_assessment,
        "annex_iii": case.expected_annex_iii_area,
        "profiling": case.expected_performs_profiling,
        "derogation": case.expected_derogation,
        "transparency": case.expected_transparency_obligation,
    }
    # A needs_review case models genuine legal ambiguity — here, at the Art. 5 prohibition question.
    low_confidence = (
        frozenset({"prohibited"})
        if case.expected_risk_class == RiskClass.NEEDS_REVIEW
        else frozenset()
    )
    return ScriptedBrain(answers, low_confidence)


def test_graph_reproduces_every_layer1_case(cases):
    """Given each golden case's sub-answers, the cascade lands on its expected risk class."""
    for case in cases.cases:
        result = classify(case.description, _brain_from_case(case), case.case_id)
        assert result.overall_risk_class == case.expected_risk_class, (
            f"{case.case_id}: graph routed to {result.overall_risk_class}, "
            f"expected {case.expected_risk_class}"
        )


def test_the_flip_flips_through_the_graph(cases):
    """THE HEADLINE. Same sub-answers except profiling; the class flips via the Art. 6(3)
    carve-back — end to end through LangGraph."""
    by_id = {c.case_id: c for c in cases.cases}
    parser = classify(
        by_id["cv_parsing_fields"].description,
        _brain_from_case(by_id["cv_parsing_fields"]),
        "cv_parsing_fields",
    )
    scorer = classify(
        by_id["cv_parsing_plus_scoring"].description,
        _brain_from_case(by_id["cv_parsing_plus_scoring"]),
        "cv_parsing_plus_scoring",
    )
    assert parser.overall_risk_class == RiskClass.NOT_HIGH_RISK
    assert scorer.overall_risk_class == RiskClass.HIGH_RISK
    # The reason is the carve-back, and the verdict is cited.
    assert scorer.triggered_by and any(e.source.article == 6 for e in scorer.triggered_by)
    assert "profiling" in scorer.reasoning.lower()


def test_prohibited_short_circuits_before_profiling():
    """Art. 5 is checked before high-risk: a prohibited case never even asks about profiling."""
    brain = ScriptedBrain({"is_ai": True, "prohibited": True})
    result = classify("emotion recognition of employees", brain, "emo")
    assert result.overall_risk_class == RiskClass.PROHIBITED
    uc = result.use_cases[0]
    assert uc.performs_profiling is None  # the profiling node was never reached
    assert uc.derogation is None


def test_not_an_ai_system_is_minimal():
    brain = ScriptedBrain({"is_ai": False})
    result = classify("a plain SQL report with no model", brain, "sql")
    assert result.overall_risk_class == RiskClass.MINIMAL


def test_low_confidence_anywhere_yields_needs_review():
    """Abstaining beats guessing: a low-confidence answer routes to NEEDS_REVIEW."""
    brain = ScriptedBrain(
        {"is_ai": True, "prohibited": False}, low_confidence=frozenset({"prohibited"})
    )
    result = classify("genuinely ambiguous case", brain, "amb")
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
    assert result.confidence == "low"


def test_annex_iii_no_derogation_is_high_risk():
    """Within Annex III, not profiling, but no derogation applies -> high_risk."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": None,
        }
    )
    result = classify("annex III use case, no derogation", brain, "hr")
    assert result.overall_risk_class == RiskClass.HIGH_RISK


def test_every_verdict_is_cited():
    """No risk verdict without a legal source — the same rule the schemas enforce."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": DerogationCondition.NARROW_PROCEDURAL_TASK,
        }
    )
    result = classify("cv parser", brain, "p")
    assert result.overall_risk_class == RiskClass.NOT_HIGH_RISK
    assert result.triggered_by
    assert all(e.source.act_version_date.isoformat() == "2024-07-12" for e in result.triggered_by)


def test_assemble_result_passes_use_case_validator():
    """The carve-back is re-checked when the graph builds the real UseCaseClassification: a
    profiling=true result MUST carry no derogation and be high_risk, or construction raises."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,
        }
    )
    result = classify("scorer", brain, "s")
    uc = result.use_cases[0]
    assert uc.performs_profiling.value is True
    assert uc.derogation is None
    assert uc.risk_class == RiskClass.HIGH_RISK


def test_build_graph_is_compilable():
    """The graph compiles and exposes the expected nodes."""
    compiled = build_graph(ScriptedBrain({"is_ai": True}))
    node_names = set(compiled.get_graph().nodes)
    expected = ("is_ai", "prohibited", "annex_iii", "profiling", "derogation", "assemble")
    for n in expected:
        assert n in node_names
    # Art. 50 is NOT a node: it is asked inside `assemble`, off the risk cascade entirely.
    assert "transparency" not in node_names


# --- Art. 50 transparency: a SEPARATE AXIS, not a step in the cascade -------------------------
def test_transparency_is_checked_for_a_high_risk_use_case():
    """Transparency must not sit on the minimal-risk branch only, or a
    high-risk system was never asked about Art. 50. It applies independently of the tier."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,  # -> high_risk
            "transparency": True,  # ...and it ALSO interacts with people
        }
    )
    result = classify("an AI chatbot that interviews and scores candidates", brain, "chatbot")
    assert result.overall_risk_class == RiskClass.HIGH_RISK
    assert result.transparency is not None, "Art. 50 must be asked even for a high-risk system"
    assert result.transparency.value is True
    assert result.transparency.source.article == 50


def test_transparency_is_checked_on_every_path():
    """Prohibited, minimal, needs_review — every terminal still answers Art. 50."""
    paths = {
        "prohibited": {"is_ai": True, "prohibited": True, "transparency": False},
        "minimal": {"is_ai": True, "prohibited": False, "annex_iii": None, "transparency": True},
        "not_ai": {"is_ai": False, "transparency": False},
    }
    for name, answers in paths.items():
        result = classify("x", ScriptedBrain(answers), name)
        assert result.transparency is not None, f"{name}: Art. 50 was not asked"


def test_transparency_never_influences_the_risk_class():
    """A low-confidence Art. 50 answer must NOT drag the classification to needs_review — the two
    axes are independent."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,
            "transparency": True,
        },
        low_confidence=frozenset({"transparency"}),
    )
    result = classify("scorer that also chats", brain, "s")
    assert result.overall_risk_class == RiskClass.HIGH_RISK  # unaffected
    assert result.confidence == "high"  # unaffected
    # the uncertainty is reported on its own axis, not spread to the risk verdict
    assert result.transparency.confidence == "low"


# --- anchoring: questions must carry VERBATIM law, not rely on model memory --------------------
def test_load_questions_anchors_every_question_in_stored_text():
    """The classification questions are anchored the same way obligation `requirement` fields are.
    Asking "which Annex III area is this?" without supplying Annex III would be exactly the
    unanchored guessing the article store exists to prevent."""
    from aiact.classify.graph import QUESTIONS, load_questions

    anchored = load_questions(
        "2024-07-12", ROOT / "data" / "policy" / "articles", ROOT / "data" / "policy" / "annexes"
    )
    assert set(anchored) == set(QUESTIONS)
    for node_id, q in anchored.items():
        assert q.context.strip(), f"{node_id} has no enacted text to reason against"


def test_annex_iii_question_contains_the_actual_annex_iii():
    """The decisive one: the area list itself must be in the prompt, verbatim."""
    from aiact.classify.graph import load_questions

    q = load_questions(
        "2024-07-12", ROOT / "data" / "policy" / "articles", ROOT / "data" / "policy" / "annexes"
    )["annex_iii"]
    assert "Employment, workers" in q.context  # Annex III point 4
    assert "detecting financial fraud" in q.context  # the 5(b) carve-out
    assert "referred to in Annex III shall be considered to be high-risk" in q.context  # Art. 6(2)


def test_bare_questions_stay_context_free():
    """The deterministic ScriptedBrain path must need no file IO — that is what keeps the routing
    tests and the demo runnable with nothing but the repo."""
    from aiact.classify.graph import QUESTIONS

    assert all(q.context == "" for q in QUESTIONS.values())


def test_verdict_carries_the_documentation_evidence_not_just_a_citation():
    """A citation alone says WHICH article applied, never WHY. Every triggering entry must carry
    the node that decided it and the span of documentation that drove it, so a reader can check
    the verdict against the submitted text."""

    class QuotingBrain(ScriptedBrain):
        """ScriptedBrain, but it also reports where in the description it found the answer."""

        def decide(self, question, description):
            answer = super().decide(question, description)
            return answer.model_copy(
                update={"evidence_quote": f"...{question.node_id} evidence in: {description}"}
            )

    brain = QuotingBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,
        }
    )
    result = classify("ranks and scores job applicants by predicted fit", brain, "scoring")

    assert result.overall_risk_class == RiskClass.HIGH_RISK
    assert result.triggered_by
    for evidence in result.triggered_by:
        assert evidence.node_id, "evidence must name the question that produced it"
        assert evidence.evidence_quote, "evidence must quote the documentation"
        assert evidence.reasoning
    # The carve-back cites BOTH halves of its legal basis: in Annex III, and profiling.
    assert {e.node_id for e in result.triggered_by} == {"annex_iii", "profiling"}
    # And the same evidence reaches the per-use-case verdict, not just the top-level one.
    assert result.use_cases[0].triggered_by == result.triggered_by


def test_evidence_quote_cannot_dump_a_section():
    """Same 300-char pinpoint rule the Finding schema enforces."""
    from aiact.schemas.classification import ClassificationEvidence
    from aiact.schemas.policy import LegalSource

    with pytest.raises(ValidationError, match="under 300"):
        ClassificationEvidence(
            source=LegalSource(
                instrument="Regulation (EU) 2024/1689",
                article=6,
                act_version_date=date(2024, 7, 12),
            ),
            evidence_quote="x" * 301,
        )


# ==================================================================================================
# needs_review must say WHAT was missing — "a node abstained" gives the reader nothing to act on
# ==================================================================================================
def _abstention(node_id: str, article: int, cause: str, paragraph: int | None = None):
    return ClassificationAnswer(
        value=None,
        reasoning="declined",
        confidence="low",
        source=LegalSource(
            instrument="Regulation (EU) 2024/1689",
            article=article,
            paragraph=paragraph,
            act_version_date=date(2024, 7, 12),
        ),
        node_id=node_id,
        abstained_because=cause,
    )


def test_a_silent_description_is_told_which_fact_is_missing():
    from aiact.classify.graph import _why_it_could_not_decide

    why = _why_it_could_not_decide([_abstention("profiling", 6, "description_silent", 3)])
    assert "evaluates, scores or ranks people" in why  # the fact, in the author's words
    assert "Art. 6(3)" in why  # and the provision that needed it
    assert "Add it and re-run" in why


def test_an_unusable_reply_is_not_blamed_on_the_documentation():
    """Telling someone to rewrite adequate documentation because the MODEL failed would be worse
    than saying nothing — they would go and edit a document that was never the problem."""
    from aiact.classify.graph import _why_it_could_not_decide

    why = _why_it_could_not_decide([_abstention("profiling", 6, "reply_unusable", 3)])
    assert "failure of the run, not of the documentation" in why
    assert "does not state" not in why


def test_both_causes_are_reported_separately_in_one_run():
    from aiact.classify.graph import _why_it_could_not_decide

    why = _why_it_could_not_decide(
        [
            _abstention("annex_iii", 6, "description_silent", 2),
            _abstention("transparency", 50, "reply_unusable"),
        ]
    )
    assert "what the system is actually used for" in why
    assert "Art. 6(2)" in why
    assert "transparency (Art. 50)" in why


def test_every_cascade_node_can_name_the_fact_it_needed():
    """A node added later without an entry would silently degrade to 'the fact this question turns
    on', which is the vague message this replaced."""
    from aiact.classify.graph import _WHAT_THE_NODE_NEEDED, QUESTIONS

    assert set(_WHAT_THE_NODE_NEEDED) == set(QUESTIONS)


def test_the_abstention_cause_survives_into_the_verdict():
    """It is set on the ANSWER inside the brain and read off the EVIDENCE in the report, so it has
    to travel the whole way — that hop is where node_id and the citation were being dropped."""
    brain = ScriptedBrain({"is_ai": True})
    result = classify("a vague description", brain, "vague")
    # ScriptedBrain answers only is_ai, so the cascade abstains at the next node it reaches.
    assert result.overall_risk_class in (RiskClass.NEEDS_REVIEW, RiskClass.MINIMAL)
