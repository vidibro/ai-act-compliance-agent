"""M4d-2 — Art. 2 applicability: does the Regulation govern this system at all?

The prior question, and the one the cascade never asked. Without it a defence targeting system was
handed a full Chapter III gap report for obligations the legislator expressly withheld.

Deterministic throughout: a ScriptedBrain supplies the sub-answers, so what is proven here is the
cascade's ROUTING and the legal invariants around it, not a model's reading.

Two properties carry most of the weight, and they pull in opposite directions:
  - scope is decided BEFORE Art. 5 and before both Art. 6 doors, because those are provisions OF
    this Regulation and cannot reach a system it does not govern;
  - an exclusion is granted only on a NAMED paragraph, so every unclear answer leaves the system in
    scope. Over-inclusion is recoverable; a silent clearance is not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.classify import ScriptedBrain, classify
from aiact.gap.rules import select_rules
from aiact.policy_loader import load_policy_spec
from aiact.schemas.classification import ClassificationEvidence, UseCaseClassification
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    AnnexIProduct,
    ProhibitedPractice,
    RiskClass,
    ScopeExclusion,
)

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_2 = ROOT / "data" / "policy" / "articles" / "2024-07-12" / "article-002.md"


def brain(**answers) -> ScriptedBrain:
    """Every case is an AI system and no case is prohibited unless it says so — those two are
    upstream of scope and would otherwise short-circuit what is being measured."""
    return ScriptedBrain({"is_ai": True, "prohibited": None, **answers})


# --- the exclusions themselves --------------------------------------------------------------------
@pytest.mark.parametrize("exclusion", [e for e in ScopeExclusion if e is not e.FREE_OPEN_SOURCE])
def test_every_named_exclusion_puts_the_system_out_of_scope(exclusion):
    """Art. 2(12) is excepted and tested separately — it is the only one that cannot be settled at
    the scope node."""
    result = classify("x", brain(scope=exclusion), "uc")
    assert result.overall_risk_class == RiskClass.OUT_OF_SCOPE


@pytest.mark.parametrize("exclusion", list(ScopeExclusion))
def test_the_verdict_names_the_paragraph_it_rests_on(exclusion):
    """An exclusion that cannot cite its paragraph is an assertion. Art. 2's paragraphs differ
    sharply in what they withhold and from whom, so 'Art. 2 applies' tells a reader nothing they
    can check."""
    result = classify("x", brain(scope=exclusion, annex_iii=None, transparency=False), "uc")
    assert result.overall_risk_class == RiskClass.OUT_OF_SCOPE
    assert f"Art. 2({exclusion.paragraph})" in result.reasoning


def test_no_exclusion_leaves_the_ordinary_cascade_untouched():
    """The control. Answering `none` at scope must change nothing — otherwise the node is not a
    gate but a distortion."""
    result = classify(
        "x",
        brain(scope=None, annex_iii=AnnexIIIArea.EMPLOYMENT, profiling=True),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.HIGH_RISK


# --- ordering: scope is prior to everything else --------------------------------------------------
def test_scope_outranks_the_art_5_prohibition():
    """Art. 5 is a provision OF this Regulation. A system Art. 2 withholds it from cannot be a
    prohibited practice under it — however much the conduct would otherwise qualify."""
    result = classify(
        "x",
        brain(
            scope=ScopeExclusion.MILITARY_DEFENCE_NATIONAL_SECURITY,
            prohibited=ProhibitedPractice.SOCIAL_SCORING,
        ),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.OUT_OF_SCOPE


def test_scope_outranks_both_art_6_doors():
    """Annex I and Annex III classify systems the Regulation governs. Reaching either for an
    excluded system would demand Chapter III of a system that owes nothing."""
    result = classify(
        "x",
        brain(
            scope=ScopeExclusion.SCIENTIFIC_RESEARCH,
            annex_i=AnnexIProduct.MEDICAL_DEVICES,
            third_party_assessment=True,
            annex_iii=AnnexIIIArea.EMPLOYMENT,
        ),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.OUT_OF_SCOPE


def test_a_non_ai_system_is_still_minimal_not_out_of_scope():
    """Art. 3(1) and Art. 2 fail for different reasons and the cascade must not merge them: this
    Regulation has nothing to say about a rules engine, but Art. 2 is not why."""
    result = classify("x", ScriptedBrain({"is_ai": False}), "uc")
    assert result.overall_risk_class == RiskClass.MINIMAL


# --- Art. 2(12): the carve-back the scope node cannot settle --------------------------------------
def test_an_open_source_release_owing_nothing_else_is_excluded():
    result = classify(
        "x",
        brain(scope=ScopeExclusion.FREE_OPEN_SOURCE, annex_iii=None, transparency=False),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.OUT_OF_SCOPE


def test_an_art_50_obligation_lifts_the_open_source_exclusion():
    """Art. 2(12)'s own words: the exclusion does not apply to a system falling under Art. 50. This
    is the flip the held-out batch turns on — two permissively licensed releases, one excluded and
    one governed, separated only by whether the output is synthetic content."""
    result = classify(
        "x",
        brain(scope=ScopeExclusion.FREE_OPEN_SOURCE, annex_iii=None, transparency=True),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.MINIMAL


def test_a_prohibited_open_source_release_stays_prohibited():
    result = classify(
        "x",
        brain(scope=ScopeExclusion.FREE_OPEN_SOURCE, prohibited=ProhibitedPractice.SOCIAL_SCORING),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.PROHIBITED


def test_a_high_risk_open_source_release_stays_high_risk():
    result = classify(
        "x",
        brain(
            scope=ScopeExclusion.FREE_OPEN_SOURCE,
            annex_iii=AnnexIIIArea.EMPLOYMENT,
            profiling=True,
        ),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.HIGH_RISK


def test_an_unresolved_open_source_release_is_not_excluded():
    """NEEDS_REVIEW is not one of the tiers Art. 2(12) survives. An unresolved cascade has not
    established that the exceptions are absent, and granting the exclusion anyway would read
    silence as evidence — the failure this project exists to avoid."""
    result = classify(
        "x",
        ScriptedBrain(
            {"is_ai": True, "prohibited": None, "scope": ScopeExclusion.FREE_OPEN_SOURCE},
            frozenset({"annex_iii"}),
        ),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW


# --- abstention and the safe direction ------------------------------------------------------------
def test_an_abstention_at_scope_is_needs_review_and_says_what_was_missing():
    result = classify(
        "x",
        ScriptedBrain({"is_ai": True}, frozenset({"scope"})),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
    assert "Art. 2" in result.reasoning


def test_an_answer_that_names_no_paragraph_leaves_the_system_in_scope():
    """A brain that puts something other than an exclusion here — a bare false, an unparsed
    string — has not named a paragraph. Only a named one can be cited, so the safe reading is that
    the Regulation applies. Over-inclusion is recoverable; a silent clearance is not."""
    result = classify(
        "x",
        brain(scope=False, annex_iii=AnnexIIIArea.EMPLOYMENT, profiling=True),
        "uc",
    )
    assert result.overall_risk_class == RiskClass.HIGH_RISK


# --- what an excluded system OWES -----------------------------------------------------------------
def test_an_excluded_system_is_selected_no_obligations_at_all():
    """Distinct from the Annex I Section B case, which owes Arts. 102-109. This owes nothing."""
    spec = load_policy_spec()
    use_case = UseCaseClassification(
        use_case_id="uc",
        description="x",
        risk_class=RiskClass.OUT_OF_SCOPE,
        triggered_by=[],
        reasoning="Art. 2(3)",
        confidence="high",
    )
    active = select_rules(spec, use_case, ActorRole.PROVIDER)
    assert not active.document_verifiable
    assert not active.not_document_verifiable
    assert not active.postponed


# --- the enum against the enacted text ------------------------------------------------------------
def test_each_exclusion_cites_a_paragraph_that_exists_in_article_2():
    """The paragraph numbers are citations, so they are checked against the stored Official Journal
    text rather than against memory of it — the same rule the classification questions obey."""
    text = ARTICLE_2.read_text(encoding="utf-8")
    for exclusion in ScopeExclusion:
        assert f"\n{exclusion.paragraph}. " in text, (
            f"{exclusion.value} cites Art. 2({exclusion.paragraph}), which is not a paragraph of "
            f"the stored Article 2"
        )


def test_only_art_2_4_must_be_stated_rather_than_derived():
    """Every other exclusion turns on a fact about the system, which a description can establish.
    Art. 2(4) turns on whether a COUNTRY affords adequate safeguards — settled in the cooperation
    agreement and the Commission's assessment, never in a system description. Same shape as
    Art. 6(1)(b), and treated the same way: read it, never derive it."""
    stated = {e for e in ScopeExclusion if e.must_be_stated}
    assert stated == {ScopeExclusion.THIRD_COUNTRY_LAW_ENFORCEMENT_COOPERATION}


def test_every_exclusion_carries_a_paragraph():
    """No default in the mapping: a newly added exclusion must be given its paragraph deliberately,
    rather than inheriting a plausible wrong one."""
    for exclusion in ScopeExclusion:
        assert isinstance(exclusion.paragraph, int)


# --- evidence -------------------------------------------------------------------------------------
def test_the_exclusion_travels_out_as_evidence():
    """A verdict with no evidence cannot be audited. The scope answer carries the same way every
    other deciding answer does."""
    result = classify(
        "x", brain(scope=ScopeExclusion.PERSONAL_NON_PROFESSIONAL), "uc"
    )
    assert result.triggered_by
    assert all(isinstance(e, ClassificationEvidence) for e in result.triggered_by)
    assert any(e.node_id == "scope" for e in result.triggered_by)


@pytest.mark.parametrize("exclusion", list(ScopeExclusion))
def test_the_citation_pinpoints_the_paragraph_not_just_the_article(exclusion):
    """One node answers all six exclusions, so its question is registered against Article 2 as a
    whole. Which paragraph decided it is stamped on the evidence afterwards — otherwise the prose
    reads "Art. 2(3)" while the structured citation reads only "Art. 2", and anything consuming
    the citation gets less than the tool actually holds."""
    result = classify("x", brain(scope=exclusion, annex_iii=None, transparency=False), "uc")
    scope_evidence = [e for e in result.triggered_by if e.node_id == "scope"]
    assert scope_evidence, "the deciding answer must travel out as evidence"
    assert scope_evidence[0].source.article == 2
    assert scope_evidence[0].source.paragraph == exclusion.paragraph
