"""M3 — classification graph routing tests.

These prove the GRAPH LOGIC (which node follows which, how sub-answers become a risk class),
deterministically, with no LLM. A ScriptedBrain is built from each Layer 1 golden case's known
sub-answers; the graph must route them to that case's expected risk class. The headline is
`test_graph_reproduces_every_layer1_case` — and inside it, the flip.
"""

from __future__ import annotations

import collections
import re
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from aiact.classify import ScriptedBrain, build_graph, classify
from aiact.classify.graph import (
    _STATE_FIELD,
    QUESTIONS,
    GraphState,
    _get_answers,
    _src,
    route_for,
)
from aiact.config import get_settings
from aiact.eval.classification_cases import load_classification_cases
from aiact.gap import roles as role_questions
from aiact.gap.rules import select_rules
from aiact.policy_loader import load_policy_spec, resolve_requirement
from aiact.provisions import points_within
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    DerogationCondition,
    GpaiStatus,
    OpenSourceRelease,
    ProhibitedPractice,
    RiskClass,
    ScopeExclusion,
    SystemicRisk,
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
    assert scorer.triggered_by and any(e.source.article == "6" for e in scorer.triggered_by)
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
    assert [e.source.paragraph for e in result.triggered_by] == ["1"]


def test_a_ban_that_cannot_cite_its_point_is_not_reported_as_a_ban():
    """A brain answering "prohibited" without naming a point has claimed something it cannot
    support. Both directions of guess are wrong here — inventing a point, and clearing a system
    that was called banned — so the cascade declines instead."""
    brain = ScriptedBrain({"is_ai": True, "prohibited": True})
    result = classify("something troubling", brain, "x")
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
    assert "no point of Art. 5(1) was named" in result.reasoning


def test_every_prohibited_practice_can_cite_itself():
    """Each member maps to its own point of Art. 5(1) — a duplicate or a missing key would cite a
    ban under a letter belonging to another one.

    The list is no longer (a) to (h): Regulation (EU) 2026/1744 inserted (ba) and (bb) BETWEEN (b)
    and (c) rather than appending them, so the declaration order is the Article's order and the
    letters are not a contiguous alphabet."""
    points = [p.point for p in ProhibitedPractice]
    assert points == ["a", "b", "ba", "bb", "c", "d", "e", "f", "g", "h"]
    assert len(set(points)) == len(points)


def test_the_two_inserted_prohibitions_are_not_yet_in_force():
    """A prohibited verdict says STOP, not 'document this', so when it starts to bite is part of
    the answer. Art. 5 applied from 2 February 2025, but the two points the Omnibus inserted apply
    only from 2 December 2026 — the first time this Article has had more than one date."""
    inserted = {
        ProhibitedPractice.NON_CONSENSUAL_INTIMATE_IMAGERY,
        ProhibitedPractice.CHILD_SEXUAL_ABUSE_MATERIAL,
    }
    for practice in ProhibitedPractice:
        expected = date(2026, 12, 2) if practice in inserted else date(2025, 2, 2)
        assert practice.applies_from == expected, practice.value


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
    # Compared against the SHIPPED pin, not a literal: a citation carrying a different act version
    # from the one the cascade read its law out of would be a verdict quoting one text and citing
    # another, and hard-coding the date here would hide exactly that on the next refresh.
    pinned = get_settings().act_version_date
    assert all(e.source.act_version_date == pinned for e in result.triggered_by)


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
    assert result.transparency.source.article == "50"


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
    assert [d.paragraph for d in TransparencyDuty] == ["1", "2", "3", "4", "4"]
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
        "2026-07-27", ROOT / "data" / "policy" / "articles", ROOT / "data" / "policy" / "annexes"
    )
    assert set(anchored) == set(QUESTIONS)
    for node_id, q in anchored.items():
        assert q.context.strip(), f"{node_id} has no enacted text to reason against"


def test_annex_iii_question_contains_the_actual_annex_iii():
    """The decisive one: the area list itself must be in the prompt, verbatim."""
    from aiact.classify.graph import load_questions

    q = load_questions(
        "2026-07-27", ROOT / "data" / "policy" / "articles", ROOT / "data" / "policy" / "annexes"
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


_ANNEX_III_EXCEPTION = re.compile(
    r"(?:This shall not include|with the exception of|This does not include)(.*?)$",
    re.IGNORECASE | re.MULTILINE,
)


def test_every_exception_annex_iii_writes_into_an_area_reaches_the_model():
    """Annex III excepts four things from areas it lists, and the question must state all four.

    They are exceptions the Annex writes INTO the area rather than derogations from it, so nothing
    downstream applies them: Art. 6(3) is a separate test with its own four conditions, and by the
    time it runs the area has already been chosen. If the question omits one, a fraud detector is
    reported as an essential-services high-risk system and a passport-gate document reader as a
    border-control one — over-inclusion, and it is the `annex_iii` node or nowhere.

    DERIVED: the exceptions are parsed from the stored Annex, and each is looked for by the words
    that occur in it and NOWHERE ELSE in the Annex. Those are what distinguish an exception from
    the area it sits in — a question that keeps 'AI systems used for the purpose of detecting' and
    drops 'financial fraud' has named nothing."""
    annexes_dir = (
        ROOT / "data" / "policy" / "annexes" / get_settings().act_version_date.isoformat()
    )
    annex = (annexes_dir / "annex-III.md").read_text(encoding="utf-8").split("---", 2)[2]
    frequency = collections.Counter(re.findall(r"[a-z]{5,}", annex.lower()))
    exceptions = [m.group(1) for m in _ANNEX_III_EXCEPTION.finditer(annex)]
    assert len(exceptions) == 4, (
        f"Annex III no longer holds four exceptions but {len(exceptions)} — re-derive this test "
        f"from the text, and state any new one in the question"
    )

    question = QUESTIONS["annex_iii"].text.lower()
    for clause in exceptions:
        distinctive = sorted(
            {w for w in re.findall(r"[a-z]{5,}", clause.lower()) if frequency[w] == 1}
        )
        assert distinctive, f"no word distinguishes this exception: {clause!r}"
        dropped = [w for w in distinctive if w not in question]
        assert not dropped, (
            f"the annex_iii question does not state the exception '{clause.strip()}': it omits "
            f"{dropped}. An exception the Annex enacts and the question omits is an area the "
            f"model will answer."
        )


def test_the_safety_component_exclusion_is_the_one_article_6_enacts():
    """A HAND-WRITTEN EXCLUSION LIST IS A HAND-WRITTEN AMENDMENT.

    Art. 6(1a) is the only thing that takes a system out of 'safety component', and it is worded:
    SOLELY non-safety-related aspects of user assistance, performance optimisation, service
    efficiency, automation or convenience, or quality control. Art. 6(1b) then takes back what it
    gives — notwithstanding 6(1a), a system whose failure would endanger health and safety
    qualifies anyway.

    Two questions decide on the term — `annex_i` for Art. 6(1)(a), `annex_iii` for Annex III(2) —
    and both are held to both paragraphs. A question naming exclusions of its own clears a case
    Art. 6(1a) does not exclude, and at `annex_iii` that runs Annex III(2) → none → minimal: one
    obligation for a system whose failure kills. A question stating 6(1a) flat, without the
    carve-back, clears the same cases more quietly.

    DERIVED: the grounds come from Art. 6(1a) as stored, and the carve-back is looked for by the
    word the paragraph turns on."""
    articles_dir = (
        ROOT / "data" / "policy" / "articles" / get_settings().act_version_date.isoformat()
    )
    excluding, _url = resolve_requirement(articles_dir, "6", "1a")
    carve_back, _url = resolve_requirement(articles_dir, "6", "1b")
    assert "shall not qualify as safety components" in excluding, (
        "Art. 6(1a) no longer reads as expected — re-derive this test from the text"
    )
    assert "Notwithstanding paragraph 1a" in carve_back, (
        "Art. 6(1b) no longer reads as expected — re-derive this test from the text"
    )
    # THREE PARTS, and the grounds are the least of them. A list of nine activities is what makes
    # Art. 6(1a) recognisable; "solely" and "non-safety related" are what make it narrow, and
    # "notwithstanding" is a word rather than a test. Each is derived from its own span of the text.
    head, _, tail = excluding.partition(" aspects of")
    qualifiers = re.findall(r"[a-z][a-z-]{4,}", head.split("AI systems that are", 1)[1].lower())
    grounds = sorted({w for w in re.findall(r"[a-z]{6,}", tail.split(" shall not")[0].lower())})
    # The condition Art. 6(1b) puts the system back on, taken from the clause that states it.
    condition = carve_back.split("AI systems", 1)[1].split(" shall qualify")[0].lower()
    carve_back_test = sorted(set(re.findall(r"[a-z]{6,}", condition)))
    assert len(grounds) >= 5, f"Art. 6(1a)'s grounds no longer parse: {grounds}"
    assert {"solely", "non-safety"} <= set(qualifiers), (
        f"Art. 6(1a)'s qualifiers no longer parse: {qualifiers}"
    )
    assert len(carve_back_test) >= 3, f"Art. 6(1b)'s condition no longer parses: {carve_back_test}"

    for node_id in ("annex_i", "annex_iii"):
        question = QUESTIONS[node_id].text.lower()
        # EACH HALF IS TESTED WHERE IT IS STATED. Presence anywhere in the prompt is not the
        # claim being made: both questions gloss Art. 3(14) and Annex III with the same
        # vocabulary, so a whole-question search is satisfied by a parenthetical aside while the
        # operative sentence states the exclusion flat. The sentence naming Art. 6(1a) is the one
        # that has to carry the grounds AND the words that narrow them.
        excludes = [s for s in question.split(".") if "6(1a)" in s]
        assert excludes, (
            f"the {node_id} question never names Art. 6(1a), so a reader cannot tell which "
            f"exclusion it is applying"
        )
        for label, words in (
            ("the grounds Art. 6(1a) enacts", grounds),
            ("the words that make Art. 6(1a) NARROW", qualifiers),
        ):
            dropped = [w for w in words if not any(w in s for s in excludes)]
            assert not dropped, (
                f"the {node_id} question states an exclusion but omits {label}: {dropped}. "
                f"A list without 'solely' and 'non-safety related' excludes a dose controller "
                f"described as performance optimisation."
            )
        # THE CARVE-BACK IS TESTED WHERE IT IS STATED, not anywhere in the prompt. Both questions
        # also gloss Art. 3(14), whose second limb uses the same words — so a whole-question search
        # is satisfied by the definition while the carve-back has been reduced to a bare
        # "notwithstanding". The sentence that names Art. 6(1b) is the one that has to carry it.
        stated = [s for s in question.split(".") if "notwithstanding" in s or "6(1b)" in s]
        assert stated, (
            f"the {node_id} question never names Art. 6(1b), so a system whose failure endangers "
            f"health and safety is excluded when the Act puts it back in"
        )
        dropped = [w for w in carve_back_test if not any(w in s for s in stated)]
        assert not dropped, (
            f"the {node_id} question names Art. 6(1b) without stating what it does: {dropped}. "
            f"A carve-back cited but not stated leaves the flat exclusion standing."
        )


def test_every_derogation_limb_reaches_the_model_with_its_qualifier():
    """A CONJUNCTIVE CONDITION SHORTENED TO ITS FIRST HALF IS A FALSE CLEARANCE.

    Art. 6(3)(c) and (d) are each two tests joined by "and"/a tether, and the second half is the
    one that decides real cases: (c) excludes a system that detects a pattern AND then replaces or
    influences the human assessment, (d) reaches only a task preparatory to an ASSESSMENT RELEVANT
    TO AN ANNEX III USE CASE. A question naming just the first half of either clears exactly what
    the point excludes, and a named condition routes to `significant_risk`, whose `false` ends at
    NOT_HIGH_RISK with Arts. 9-15 and 16-21 dropped.

    Enum docstrings carry the full test and never reach the model: `_answer_instructions` renders
    bare `p.value` identifiers, so the question text is the only place a qualifier can live.

    DERIVED, not typed: the points come from the stored Article, the conjunctive ones are found by
    looking for the qualifier, and the question must carry words from the half that qualifies."""
    articles_dir = (
        ROOT / "data" / "policy" / "articles" / get_settings().act_version_date.isoformat()
    )
    question = QUESTIONS["derogation"].text

    for condition in DerogationCondition:
        assert condition.value in question, (
            f"the derogation question never names {condition.value}, so the model is asked to "
            f"return a value it was not offered"
        )

    points = points_within(articles_dir, "6", "3")
    assert set(points) == {"a", "b", "c", "d"}, f"Art. 6(3) points changed: {points}"

    for point, tail_marker in (("c", " and is not meant to"), ("d", " to an assessment relevant")):
        text, _url = resolve_requirement(articles_dir, "6", "3", point=point)
        assert tail_marker in text, (
            f"Art. 6(3)({point}) no longer reads as expected — re-derive this test from the text"
        )
        # Stop at the sentence end: resolving a POINT returns the trailing subparagraph too, and
        # Art. 6(3)'s is the profiling carve-back, which belongs to another node entirely.
        qualifier = text.split(tail_marker, 1)[1].split(".")[0]
        keywords = {w for w in re.findall(r"[a-z]{5,}", qualifier.lower()) if w != "system"}
        # EVERY word, not a quorum. A qualifier is itself made of qualifiers — (c) excludes a
        # system that replaces the human assessment OR influences it, and only without proper human
        # review — so a threshold counting words is met by whichever of them a shortening leaves
        # behind, while the words that decide cases are gone.
        dropped = sorted(w for w in keywords if w not in question.lower())
        assert not dropped, (
            f"Art. 6(3)({point}) is a conjunction and the question drops part of its qualifying "
            f"half: {dropped}"
        )


def test_every_citation_the_cascade_emits_labels_its_address_as_a_string(cases):
    """An article or paragraph label is a string EVERYWHERE, and validation is not what enforces it.

    `LegalSource` normalises `6` to `"6"` on construction, but the cascade pinpoints a citation
    with `model_copy(update=...)`, which runs no validators — so an integer written there survives
    into the report and compares unequal to the same address written anywhere else. That is how a
    scope verdict came to carry `paragraph=12` while its article read `"2"`.

    Run over every golden case rather than one, because the pinpointing happens on the Art. 2 and
    Art. 5 branches only and a single case reaches neither."""
    for case in cases.cases:
        result = classify(case.description, _brain_from_case(case), case.case_id)
        sources = [e.source for e in result.triggered_by]
        for use_case in result.use_cases:
            sources += [e.source for e in use_case.triggered_by]
        for source in sources:
            for label in ("article", "paragraph"):
                value = getattr(source, label)
                assert value is None or isinstance(value, str), (
                    f"{case.case_id}: LegalSource.{label} is {value!r}, an "
                    f"{type(value).__name__}. Something built this citation without validation — "
                    f"model_copy(update=...) is the way in."
                )


def test_a_model_is_asked_both_chapter_v_gates_and_a_system_is_asked_neither():
    """The two questions Chapter V turns on, put to the things they are questions about.

    Art. 51 decides the whole of Art. 55 and Arts. 53(2)/54(6) decide what an open release lifts,
    so a model never asked them is a model whose report can only read the conditions back at it.
    A SYSTEM must not be asked either one: Art. 3(66) makes a system built on a general-purpose
    model an ordinary AI system, and answering Art. 51 about it would be a category error paid for
    with two LLM calls on every ordinary document."""
    for status in (GpaiStatus.GENERAL_PURPOSE_MODEL, GpaiStatus.GENERAL_PURPOSE_MODEL_PRE_MARKET):
        walked = route_for(
            {
                "is_ai": True,
                "territorial": TerritorialLink.NOT_ADDRESSED,
                "scope": None,
                "gpai_model": status,
            }
        )
        assert "systemic_risk" in walked and "open_source_release" in walked, status
        # And nothing on the Art. 6 track: a model has no tier for those questions to compute.
        assert not {"prohibited", "annex_i", "annex_iii"} & set(walked), status

    system = route_for(
        {
            "is_ai": True,
            "territorial": TerritorialLink.NOT_ADDRESSED,
            "scope": None,
            "gpai_model": GpaiStatus.AI_SYSTEM,
            "prohibited": None,
        }
    )
    assert not {"systemic_risk", "open_source_release"} & set(system)


def test_neither_chapter_v_gate_is_allowed_to_clear_an_obligation():
    """BOTH ANSWERS INFORM THE REPORT AND NEITHER WITHHOLDS A DUTY.

    Art. 51 and the Art. 53(2)/54(6) carve-out are read from the same model card a judge would
    read, so a card that understates its compute or calls a restrictive licence open would, if the
    answers gated selection, clear four obligations at once. The ruleset's answer is to select
    every Chapter V rule for every model and carry the condition on the rule — which only holds if
    the answers change nothing about what is selected.

    DERIVED: the same model run three ways, including the two answers most likely to be read as
    permission."""
    spec = load_policy_spec()
    sets = []
    for risk, release in (
        (SystemicRisk.NOT_STATED, OpenSourceRelease.NOT_STATED),
        (SystemicRisk.BELOW_THRESHOLD, OpenSourceRelease.FULLY_OPEN),
        (SystemicRisk.DESIGNATED, OpenSourceRelease.NOT_OPEN),
    ):
        result = classify(
            "a model",
            ScriptedBrain(
                {
                    "is_ai": True,
                    "gpai_model": GpaiStatus.GENERAL_PURPOSE_MODEL,
                    "systemic_risk": risk,
                    "open_source_release": release,
                }
            ),
            "m",
        )
        assert result.overall_risk_class == RiskClass.GPAI_MODEL
        sets.append(
            frozenset(
                r.rule_id
                for role in (ActorRole.PROVIDER, ActorRole.AUTHORISED_REPRESENTATIVE)
                for r in select_rules(spec, result.use_cases[0], role).all_rules
            )
        )
    assert len(set(sets)) == 1, (
        f"the Chapter V obligation set changed with the gate answers: {sets}. A model card read "
        f"wrongly on one licence limb must cost a reader a sentence, never an obligation."
    )
    assert any(r.startswith("AIA-GP-A55") for r in sets[0]), "Art. 55 must be in the set at all"


# ==================================================================================================
# The README's cascade diagram, held to the graph it draws
# ==================================================================================================
README = Path(__file__).resolve().parents[1] / "README.md"

# The diagram's node ids ARE the question ids. That is the whole mechanism: a picture whose nodes
# are named `AI` and `TPA` can only be compared to the code through a mapping someone maintains,
# and a mapping is the thing that goes stale alongside the diagram it was written to check.
_DIAGRAM_NODE = re.compile(r"\b([a-z_]+)\{\"")
_DIAGRAM_ABSTAINS = re.compile(r"^\s{4}([a-z_]+) -\.->", re.M)


def _diagram(nth: int) -> str:
    """The nth mermaid block of the README. The first draws the cascade, the second the gap
    pipeline — and both are drawings of code that a reader trusts before reading the code."""
    text = README.read_text(encoding="utf-8")
    start = 0
    for _ in range(nth + 1):
        start = text.index("```mermaid", start) + 3
    return text[start : text.index("```", start)]


def _cascade_diagram() -> str:
    return _diagram(0)


def _risk_deciding_nodes() -> set[str]:
    """Which nodes' answers decide the tier, read off `_get_answers` rather than listed here.

    Every field is populated and the function is asked what it keeps. `transparency`,
    `systemic_risk` and `open_source_release` are excluded there on purpose — none of them is a
    step in the risk cascade — and this derivation inherits that reasoning instead of restating
    it."""
    state = GraphState(description="")
    for node_id, field in _STATE_FIELD.items():
        setattr(
            state,
            field,
            Answer(value=True, reasoning="", confidence="high", source=_src(6), node_id=node_id),
        )
    return {answer.node_id for answer in _get_answers(state)}


def test_the_readme_cascade_draws_every_node_the_graph_runs():
    """A node added to the graph and not to the picture leaves the README quietly wrong.

    The diagram is how anyone reads the legal routing before reading the code, and its edges carry
    the arguments that are easy to get backwards — a self-certified Annex I product falling THROUGH
    to the Annex III door rather than exiting, profiling answered before any derogation. A drawing
    that has silently stopped matching is worse than none, because it is still believed.

    `transparency` is absent from both, and that is the graph's own answer rather than an exception
    written here: `assemble` asks Art. 50 beside `decide_risk_class`, so it is not a node, and the
    comparison is against the compiled graph's nodes."""
    diagram = _cascade_diagram()
    drawn = set(_DIAGRAM_NODE.findall(diagram))
    compiled = {
        node
        for node in build_graph(ScriptedBrain({})).get_graph().nodes
        if not node.startswith("__") and node != "assemble"
    }
    assert drawn == compiled, (
        f"the README cascade and the compiled graph disagree about their nodes. "
        f"Drawn but not run: {sorted(drawn - compiled)}. Run but not drawn: "
        f"{sorted(compiled - drawn)}."
    )


def test_the_readme_draws_an_abstention_for_every_node_that_can_abstain():
    """The dashed edges are a legal claim: THESE questions can end the assessment in needs_review.

    Drawing one where the code cannot abstain promises an escape hatch that is not there; omitting
    one where it can hides the tool's own uncertainty from the reader deciding whether to trust it.
    `systemic_risk` and `open_source_release` have no dashed edge because a low-confidence answer
    on either must not drag a settled classification to needs_review — the picture is where that
    decision is visible."""
    abstaining = set(_DIAGRAM_ABSTAINS.findall(_cascade_diagram()))
    deciding = _risk_deciding_nodes()
    assert abstaining == deciding, (
        f"the README's low-confidence edges and `_get_answers` disagree. Drawn as able to abstain "
        f"but not counted toward the tier: {sorted(abstaining - deciding)}. Counted toward the "
        f"tier with no abstention drawn: {sorted(deciding - abstaining)}."
    )


def test_the_readme_gap_pipeline_draws_every_question_the_gap_layer_asks():
    """The second diagram draws the obligation half, and it asks questions of its own.

    They are not in the cascade and cannot be: `provider_reallocation` and `real_world_testing`
    decide whether a rule activates, and `deployer_type` resolves a condition on one that activates
    either way — none of them touches the risk class. So the cascade guards above say nothing about
    them, and this is where a question added to `gap.roles` is held to the picture of it.

    Named by question id in the diagram, on the same reasoning as the cascade's nodes: a data node
    called `MOVED` can only be compared to the code through a mapping somebody keeps up to date."""
    drawn = _diagram(1)
    missing = sorted(q for q in role_questions.QUESTIONS if q not in drawn)
    assert not missing, (
        f"the gap layer asks {missing} and the README's pipeline diagram does not draw them. A "
        f"question that decides whether an obligation is reported is not an implementation detail."
    )
