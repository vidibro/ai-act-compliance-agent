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
from aiact.classify.graph import route_for
from aiact.eval.classification_cases import load_classification_cases
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    DerogationCondition,
    GpaiStatus,
    ProhibitedPractice,
    RiskClass,
    ScopeExclusion,
    TerritorialLink,
    TransparencyDuty,
)
from aiact.schemas.eval import ClassificationCase
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer

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
        "territorial": case.expected_territorial_link,
        "scope": case.expected_scope_exclusion,
        "gpai_model": case.expected_gpai_status,
        "prohibited": case.expected_prohibited_practice,
        "annex_i": case.expected_annex_i_product,
        "third_party_assessment": case.expected_third_party_assessment,
        "annex_iii": case.expected_annex_iii_area,
        "profiling": case.expected_performs_profiling,
        "derogation": case.expected_derogation,
        "significant_risk": case.expected_poses_significant_risk,
        "transparency": case.expected_transparency_duties,
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
    brain = ScriptedBrain({"is_ai": True, "prohibited": ProhibitedPractice.SOCIAL_SCORING})
    result = classify("emotion recognition of employees", brain, "emo")
    assert result.overall_risk_class == RiskClass.PROHIBITED
    uc = result.use_cases[0]
    assert uc.performs_profiling is None  # the profiling node was never reached
    assert uc.derogation is None


def test_the_ban_names_the_point_it_rests_on():
    """A prohibition is the heaviest verdict this tool emits — the provider may not ship at all.
    "Art. 5" alone gives them nothing to check it against, so the point is in the reasoning and the
    citation is pinpointed to Art. 5(1) rather than left at the Article."""
    brain = ScriptedBrain(
        {"is_ai": True, "prohibited": ProhibitedPractice.EMOTION_INFERENCE_WORKPLACE_EDUCATION}
    )
    result = classify("infers employee emotions from webcam", brain, "emo")
    assert result.overall_risk_class == RiskClass.PROHIBITED
    assert "Art. 5(1)(f)" in result.reasoning
    assert [e.source.paragraph for e in result.triggered_by] == [1]


def test_a_ban_that_cannot_cite_its_point_is_not_reported_as_a_ban():
    """A brain answering "prohibited" without naming a point has claimed something it cannot
    support. Both directions of guess are wrong here — inventing a point, and clearing a system
    that was called banned — so the cascade declines instead."""
    brain = ScriptedBrain({"is_ai": True, "prohibited": True})
    result = classify("something troubling", brain, "x")
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
    assert "no point of Art. 5(1) was named" in result.reasoning


def test_every_prohibited_practice_can_cite_itself():
    """Art. 5(1) runs (a) to (h) and each member must map to its own letter — a duplicate or a
    missing key would cite a ban under a letter belonging to another one."""
    points = [p.point for p in ProhibitedPractice]
    assert points == list("abcdefgh")


def test_a_general_purpose_model_leaves_the_risk_cascade():
    """Art. 6 does not classify a GPAI model, so asking which Annex III area it falls into is a
    category error and answering `minimal` because it falls into none is a false clearance. The
    verdict is a handover naming the regime that does govern it."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "territorial": TerritorialLink.NOT_ADDRESSED,
            "scope": None,
            "gpai_model": GpaiStatus.GENERAL_PURPOSE_MODEL,
            "transparency": [],
        }
    )
    result = classify("an open-weight base model", brain, "m")
    assert result.overall_risk_class == RiskClass.GPAI_MODEL
    uc = result.use_cases[0]
    assert uc.annex_iii_area is None and uc.performs_profiling is None

    # The handover has to be actionable, and has to say when. Chapter V is in force NOW.
    for expected in ("Art. 3(63)", "Art. 53", "Art. 55", "Art. 52(6)", "2 August 2025", "10^25"):
        assert expected in result.reasoning, f"the handover must name {expected}"


def test_a_pre_market_model_is_named_and_dated_not_cleared():
    """The exclusion is a DEADLINE. Art. 3(63) and Art. 2(8) both put a model in development outside
    the Regulation TODAY, and both end on the day it ships — with Chapter V already in application
    since 2 August 2025, so there is no transition period to prepare in. Reporting only "out of
    scope, nothing owed" would be true this morning and misleading by the time anyone acted on it.
    """
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "territorial": TerritorialLink.NOT_ADDRESSED,
            "scope": ScopeExclusion.PRE_MARKET_DEVELOPMENT,
            "gpai_model": GpaiStatus.GENERAL_PURPOSE_MODEL_PRE_MARKET,
            "transparency": [],
        }
    )
    result = classify("a frontier model still in training", brain, "pre")
    assert result.overall_risk_class == RiskClass.GPAI_MODEL
    assert "NOT YET been placed on the market" in result.reasoning
    assert "DEADLINE, NOT A CLEARANCE" in result.reasoning
    # The duties are still listed in full — the whole point of not stopping at the exclusion.
    for expected in ("Art. 53", "Art. 55", "Annex XI", "2 August 2025"):
        assert expected in result.reasoning, f"a pre-market model must still be told of {expected}"


def test_art_2_8_falls_through_to_the_model_question_and_no_further():
    """Art. 2(8) is asked past for ONE question — what is being built — because a general-purpose
    model needs its duties named. Once the answer is "an AI system" the exclusion concludes, rather
    than computing a tier for a system the Regulation does not currently govern."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "territorial": TerritorialLink.NOT_ADDRESSED,
            "scope": ScopeExclusion.PRE_MARKET_DEVELOPMENT,
            "gpai_model": GpaiStatus.AI_SYSTEM,
            "transparency": [],
        }
    )
    result = classify("a hiring tool still in development", brain, "dev")
    assert result.overall_risk_class == RiskClass.OUT_OF_SCOPE
    assert "deadline, not a clearance" in result.reasoning
    assert "REAL-WORLD CONDITIONS" in result.reasoning
    # It stopped at the model question — the Art. 6 track was never run.
    asked = [a.node_id for a in result.answers]
    assert "gpai_model" in asked and "annex_iii" not in asked


def test_a_system_built_on_a_general_purpose_model_is_still_classified():
    """THE GUARD. Art. 3(66) makes a system based on a general-purpose model an ordinary AI system.
    Routing out everything that runs on a foundation model would exempt exactly the products the
    tier logic exists for."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "territorial": TerritorialLink.NOT_ADDRESSED,
            "scope": None,
            "gpai_model": GpaiStatus.AI_SYSTEM,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,
            "transparency": [],
        }
    )
    result = classify("an LLM-backed CV screener", brain, "s")
    assert result.overall_risk_class == RiskClass.HIGH_RISK


def test_a_system_the_regulation_never_reaches_is_out_of_scope():
    """Art. 2(1) is the POSITIVE limb and it is asked before every exclusion. Without it a system
    placed nowhere in the Union, whose output is never used here, comes back with a full risk tier
    and a list of duties nobody owes."""
    brain = ScriptedBrain(
        {"is_ai": True, "territorial": TerritorialLink.OUTSIDE_UNION, "transparency": []}
    )
    result = classify("US-only tenant screening", brain, "us")
    assert result.overall_risk_class == RiskClass.OUT_OF_SCOPE
    assert "Art. 2(1)" in result.reasoning
    # NOT an exclusion: nothing was carved out, so no paragraph of (3)-(12) is cited.
    assert result.use_cases[0].annex_iii_area is None


def test_only_an_explicit_finding_clears_a_system_on_territory():
    """The polarity that matters. Everywhere else in this cascade `None` is the SAFE answer — no
    exclusion, no area, no ban. Here the unsafe reading is the one that clears a system entirely,
    so it must be stated to be reached: an unanswered or unrecognised value leaves the Regulation
    applying, exactly as `_scope_exclusion` does."""
    for value in (None, "somewhere else", True):
        brain = ScriptedBrain(
            {
                "is_ai": True,
                "territorial": value,
                "prohibited": None,
                "annex_iii": AnnexIIIArea.EMPLOYMENT,
                "profiling": True,
                "transparency": [],
            }
        )
        result = classify("scores candidates", brain, "x")
        assert result.overall_risk_class == RiskClass.HIGH_RISK, (
            f"territorial={value!r} must not clear a system — only an explicit outside_union does"
        )


def test_silence_about_territory_does_not_stop_the_assessment():
    """`not_addressed` is the ordinary answer, because real documentation almost never mentions
    territory. Abstaining on it would make needs_review the verdict for nearly every document."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "territorial": TerritorialLink.NOT_ADDRESSED,
            "prohibited": None,
            "annex_iii": None,
            "transparency": [],
        }
    )
    assert classify("a tool", brain, "x").overall_risk_class == RiskClass.MINIMAL


def test_not_an_ai_system_is_minimal():
    brain = ScriptedBrain({"is_ai": False})
    result = classify("a plain SQL report with no model", brain, "sql")
    assert result.overall_risk_class == RiskClass.MINIMAL


def test_low_confidence_anywhere_yields_needs_review():
    """Abstaining beats guessing: a low-confidence answer routes to NEEDS_REVIEW."""
    brain = ScriptedBrain(
        {"is_ai": True, "prohibited": None}, low_confidence=frozenset({"prohibited"})
    )
    result = classify("genuinely ambiguous case", brain, "amb")
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
    assert result.confidence == "low"


def test_annex_iii_no_derogation_is_high_risk():
    """Within Annex III, not profiling, but no derogation applies -> high_risk."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": None,
        }
    )
    result = classify("annex III use case, no derogation", brain, "hr")
    assert result.overall_risk_class == RiskClass.HIGH_RISK


def _derogation_brain(poses_significant_risk: bool | None) -> ScriptedBrain:
    return ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": DerogationCondition.NARROW_PROCEDURAL_TASK,
            "significant_risk": poses_significant_risk,
        }
    )


def test_a_derogation_condition_alone_does_not_exempt():
    """Art. 6(3) is a CONJUNCTION. A system meeting condition (a) is exempt only where it ALSO
    poses no significant risk of harm — so the same condition lands on two different tiers, and
    only the chapeau separates them. Asking (a)-(d) alone would clear both."""
    exempt = classify("narrow task, nobody relies on it", _derogation_brain(False), "p")
    assert exempt.overall_risk_class == RiskClass.NOT_HIGH_RISK

    decides = classify("narrow task that auto-rejects", _derogation_brain(True), "p")
    assert decides.overall_risk_class == RiskClass.HIGH_RISK
    assert "materially influences" in decides.reasoning


def test_the_chapeau_is_not_asked_when_no_condition_is_met():
    """No condition under (a)-(d) means the first subparagraph cannot apply at all, so the second
    question is never put — it could not change the answer."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": None,
        }
    )
    result = classify("annex III use case, no derogation", brain, "hr")
    assert result.overall_risk_class == RiskClass.HIGH_RISK
    assert "significant_risk" not in [a.node_id for a in result.answers]


def test_an_unanswered_chapeau_does_not_exempt():
    """Silence must not clear a system. A derogation condition with no answer on the other limb
    reaches no defensible terminal, so the cascade declines rather than granting the exemption."""
    result = classify("narrow task, use unstated", _derogation_brain(None), "p")
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW


def test_route_for_walks_through_the_chapeau():
    """The loader's route check must know the second limb is reached — otherwise a case pinning it
    would be told to delete the line."""
    reached = route_for(
        {
            "is_ai": True,
            "territorial": TerritorialLink.NOT_ADDRESSED,
            "scope": None,
            "gpai_model": GpaiStatus.AI_SYSTEM,
            "prohibited": None,
            "annex_i": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": DerogationCondition.NARROW_PROCEDURAL_TASK,
        }
    )
    assert reached[-2:] == ["derogation", "significant_risk"]


def test_every_verdict_is_cited():
    """No risk verdict without a legal source — the same rule the schemas enforce."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": DerogationCondition.NARROW_PROCEDURAL_TASK,
            "significant_risk": False,
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
            "prohibited": None,
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
    expected = (
        "is_ai",
        "prohibited",
        "annex_iii",
        "profiling",
        "derogation",
        "significant_risk",
        "assemble",
    )
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
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,  # -> high_risk
            "transparency": [TransparencyDuty.DIRECT_INTERACTION],  # ...and it ALSO talks to people
        }
    )
    result = classify("an AI chatbot that interviews and scores candidates", brain, "chatbot")
    assert result.overall_risk_class == RiskClass.HIGH_RISK
    assert result.transparency is not None, "Art. 50 must be asked even for a high-risk system"
    assert result.transparency.value == [TransparencyDuty.DIRECT_INTERACTION]
    assert result.transparency.source.article == 50


def test_transparency_is_checked_on_every_path():
    """Prohibited, minimal, needs_review — every terminal still answers Art. 50."""
    paths = {
        "prohibited": {
            "is_ai": True,
            "prohibited": ProhibitedPractice.SOCIAL_SCORING,
            "transparency": [],
        },
        "minimal": {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": None,
            "transparency": [TransparencyDuty.SYNTHETIC_CONTENT_MARKING],
        },
        "not_ai": {"is_ai": False, "transparency": []},
    }
    for name, answers in paths.items():
        result = classify("x", ScriptedBrain(answers), name)
        assert result.transparency is not None, f"{name}: Art. 50 was not asked"


def test_art_50_duties_are_cumulative_and_split_by_role():
    """One system can owe several duties at once, and they are not all its own: 50(1) and 50(2)
    bind the provider, 50(3) and 50(4) the deployer. A report grouping them into one block hands
    a provider duties it cannot discharge and leaves the deployer's unattributed."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": None,
            "transparency": [
                TransparencyDuty.DIRECT_INTERACTION,  # 50(1), provider
                TransparencyDuty.SYNTHETIC_CONTENT_MARKING,  # 50(2), provider
                TransparencyDuty.DEEP_FAKE_DISCLOSURE,  # 50(4), deployer
            ],
        }
    )
    result = classify("an avatar that chats and generates video", brain, "avatar")
    by_role = result.transparency_duties_by_role
    assert by_role[ActorRole.PROVIDER] == [
        TransparencyDuty.DIRECT_INTERACTION,
        TransparencyDuty.SYNTHETIC_CONTENT_MARKING,
    ]
    assert by_role[ActorRole.DEPLOYER] == [TransparencyDuty.DEEP_FAKE_DISCLOSURE]


def test_a_system_owing_nothing_under_art_50_lists_no_role():
    """An empty answer is a real one. Roles with no duty are absent rather than present-and-empty,
    so a report iterating this never renders a heading with nothing under it."""
    brain = ScriptedBrain(
        {"is_ai": True, "prohibited": None, "annex_iii": None, "transparency": []}
    )
    result = classify("a batch job that reformats CSVs", brain, "csv")
    assert result.transparency_duties == []
    assert result.transparency_duties_by_role == {}


def test_every_transparency_duty_knows_its_paragraph_and_its_role():
    """Art. 50 runs (1) to (4), with (4) carrying two duties. Each must name its own paragraph and
    the party that owes it — a duty attributed to the wrong role is worse than an unattributed one.
    """
    assert [d.paragraph for d in TransparencyDuty] == [1, 2, 3, 4, 4]
    assert [d.owed_by for d in TransparencyDuty] == [
        ActorRole.PROVIDER,
        ActorRole.PROVIDER,
        ActorRole.DEPLOYER,
        ActorRole.DEPLOYER,
        ActorRole.DEPLOYER,
    ]


def test_transparency_never_influences_the_risk_class():
    """A low-confidence Art. 50 answer must NOT drag the classification to needs_review — the two
    axes are independent."""
    brain = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,
            "transparency": [TransparencyDuty.DIRECT_INTERACTION],
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
            "prohibited": None,
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
    return Answer(
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


def test_the_demo_script_still_shows_the_flip(capsys):
    """The demo is the project's front door — `python scripts/classify.py --demo`, no API key. Its
    ScriptedBrain answers are a hand-written table, so a new cascade node silently turns the flip
    into two `needs_review` lines and every test still passes. Run it here so that cannot happen."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "classify_script", ROOT / "scripts" / "classify.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.demo()

    out = capsys.readouterr().out
    assert "risk class : not_high_risk" in out, "the parser half of the flip no longer lands"
    assert "risk class : high_risk" in out, "the scorer half of the flip no longer lands"
    assert "needs_review" not in out, "a cascade node the demo does not answer has broken it"
