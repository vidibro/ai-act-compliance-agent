"""Art. 6(1) — the second door into high-risk, and what Art. 2(2) does to it.

A cascade that asks only about Annex III clears an AI braking controller or a surgical robot: they
appear in no listed area, so "no area" reads as `minimal` and a system owing everything is told it
owes nothing. That is a FALSE CLEARANCE, the failure mode this project treats as unacceptable, and
the first test here is the one that catches it.

The second half is the mirror image. Art. 2(2) exempts Section B products (vehicles, aviation,
rail, marine) from Chapter III even though they ARE high-risk, so routing them to high_risk without
more raises 18 obligations the Act withholds — a false accusation for a false clearance.
"""

from __future__ import annotations

from datetime import date

import pytest

from aiact.classify import ScriptedBrain, classify
from aiact.gap.judge import Judgement
from aiact.gap.rules import select_rules
from aiact.pipeline import review
from aiact.policy_loader import load_policy_spec
from aiact.schemas.classification import (
    ClassificationAnswer,
    ClassificationEvidence,
    UseCaseClassification,
)
from aiact.schemas.enums import (
    _ANNEX_I_CONFORMITY_ROUTE,
    _ANNEX_I_LEGISLATION,
    ActorRole,
    AnnexIIIArea,
    AnnexIProduct,
    ProhibitedPractice,
    RiskClass,
    Verdict,
)
from aiact.schemas.policy import LegalSource

DOCUMENT = "# Doc\n\n## Safety\n\nThe controller halts the actuator on fault.\n"


def a_use_case(product: AnnexIProduct) -> UseCaseClassification:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689",
        article=6,
        paragraph=1,
        act_version_date=date(2024, 7, 12),
    )
    return UseCaseClassification(
        use_case_id="uc",
        description="d",
        risk_class=RiskClass.HIGH_RISK,
        annex_i_product=product,
        reasoning="r",
        confidence="high",
        triggered_by=[
            ClassificationEvidence(source=source, quote="safety component", reasoning="Art. 6(1)")
        ],
    )


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


class StubJudge:
    name = "stub"

    def __init__(self):
        self.calls = []

    def judge(self, rule, document):
        self.calls.append(rule.rule_id)
        return Judgement(Verdict.PASS, "stub", None, None, "high")


def brain(**answers) -> ScriptedBrain:
    return ScriptedBrain({"is_ai": True, "prohibited": None, **answers})


# --- Annex I is a real route into high-risk -------------------------------------------------------
def test_a_surgical_robot_is_high_risk_not_minimal():
    """Nothing about a surgical robot appears in Annex III — it is not hiring, credit or law
    enforcement — so the Annex III question alone answers `none`. Art. 6(1) is the only route that
    reaches it, and without this node the verdict is `minimal`."""
    result = classify(
        "AI dose controller inside a surgical robot",
        brain(annex_i=AnnexIProduct.MEDICAL_DEVICES, third_party_assessment=True),
        "robot",
    )
    assert result.overall_risk_class == RiskClass.HIGH_RISK
    assert "6(1)" in result.reasoning
    assert result.use_cases[0].annex_i_product == AnnexIProduct.MEDICAL_DEVICES


def test_both_conditions_are_required():
    """Art. 6(1) is a conjunction. Most Annex I regimes let a manufacturer self-assess the lower
    risk classes, so condition (a) alone would sweep in products that self-certify."""
    result = classify(
        "AI in a self-certified machine",
        brain(annex_i=AnnexIProduct.MACHINERY, third_party_assessment=False, annex_iii=None),
        "machine",
    )
    assert result.overall_risk_class == RiskClass.MINIMAL


def test_failing_the_second_condition_falls_through_rather_than_concluding():
    """A self-assessed Annex I product can still be high-risk by the OTHER door. Treating a failed
    Art. 6(1) as an exit would clear it on the Annex III route without ever asking — the same false
    clearance, one branch over."""
    result = classify(
        "self-certified machine that also ranks job applicants",
        brain(
            annex_i=AnnexIProduct.MACHINERY,
            third_party_assessment=False,
            annex_iii=AnnexIIIArea.EMPLOYMENT,
            profiling=True,
        ),
        "both",
    )
    assert result.overall_risk_class == RiskClass.HIGH_RISK
    assert "profiling" in result.reasoning.lower()


def test_the_article_6_3_derogations_never_reach_an_annex_i_system():
    """Art. 6(3) derogates from paragraph 2 only. A 6(1) system is high-risk full stop, so the
    cascade must not even ask — a narrow-task answer must not be able to downgrade it."""
    result = classify(
        "AI lift brake monitor performing a narrow procedural task",
        brain(
            annex_i=AnnexIProduct.LIFTS,
            third_party_assessment=True,
            derogation="narrow_procedural_task",
        ),
        "lift",
    )
    assert result.overall_risk_class == RiskClass.HIGH_RISK


def test_a_prohibited_practice_still_outranks_annex_i():
    result = classify(
        "emotion inference built into a medical device",
        ScriptedBrain(
            {
                "is_ai": True,
                "prohibited": ProhibitedPractice.SOCIAL_SCORING,
                "annex_i": AnnexIProduct.MEDICAL_DEVICES,
                "third_party_assessment": True,
            }
        ),
        "banned",
    )
    assert result.overall_risk_class == RiskClass.PROHIBITED


# --- Art. 2(2): Section B is high-risk AND owes no Chapter III ------------------------------------
def test_annex_i_splits_into_exactly_the_act_s_two_sections():
    products = list(AnnexIProduct)
    assert len(products) == 20, "Annex I lists 20 instruments"
    assert sum(p.section == "A" for p in products) == 12, "Section A lists 12"
    assert sum(p.section == "B" for p in products) == 8, "Section B lists 8"
    assert all(p.chapter_iii_applies == (p.section == "A") for p in products)


def test_section_a_owes_the_full_chapter_iii(spec):
    uc = a_use_case(AnnexIProduct.MEDICAL_DEVICES)
    assert select_rules(spec, uc, ActorRole.PROVIDER).all_rules, "Section A owes Art. 9-15"


def test_section_b_owes_nothing_under_this_regulation(spec):
    """Art. 2(2): for a Section B product only Art. 6(1), 102-109 and 112 apply. Its safety duties
    come from the sectoral legislation instead."""
    uc = a_use_case(AnnexIProduct.MOTOR_VEHICLES)
    assert select_rules(spec, uc, ActorRole.PROVIDER).all_rules == ()


def test_a_section_b_report_says_why_it_is_empty(spec):
    """High-risk beside an empty findings list is the most misreadable output the tool can produce.
    It must state that Chapter III was withheld, and on what authority."""
    judge = StubJudge()
    report = review(
        DOCUMENT,
        spec,
        brain(annex_i=AnnexIProduct.MOTOR_VEHICLES, third_party_assessment=True),
        judge=judge,
        system_id="brakes",
    )
    assert report.classification.overall_risk_class == RiskClass.HIGH_RISK
    assert judge.calls == [], "no Chapter III rule may be judged for a Section B product"
    assert report.findings == []
    assert report.scope_note and "2(2)" in report.scope_note


def test_a_section_a_report_is_checked_normally(spec):
    judge = StubJudge()
    report = review(
        DOCUMENT,
        spec,
        brain(annex_i=AnnexIProduct.MEDICAL_DEVICES, third_party_assessment=True),
        judge=judge,
        system_id="robot",
    )
    assert judge.calls, "Section A owes Chapter III and must be judged"
    assert report.scope_note is None


# --- the handover: a parked question names its owner ----------------------------------------------
def a_silent_doc_brain(product: AnnexIProduct):
    """A brain that identifies the product but finds the conformity route unstated — the real shape
    of a technical file that never mentions its notified body."""

    class SilentOnConformity:
        name = "silent-on-conformity"

        def decide(self, question, description):
            common = {"source": question.source, "node_id": question.node_id, "reasoning": "r"}
            if question.node_id == "annex_i":
                return ClassificationAnswer(value=product, confidence="high", **common)
            if question.node_id == "third_party_assessment":
                return ClassificationAnswer(
                    value=None,
                    confidence="low",
                    abstained_because="description_silent",
                    **common,
                )
            # Every other node answers "nothing here": True only for is_ai, and None elsewhere.
            # `prohibited` in particular must be None rather than False — it answers with an
            # Art. 5(1) point, and a bare false is a value it cannot cite, which the cascade
            # rightly refuses to read as a clearance.
            return ClassificationAnswer(
                value=True if question.node_id == "is_ai" else None, confidence="high", **common
            )

    return SilentOnConformity()


def test_an_unresolved_conformity_route_names_the_law_and_the_specialist():
    """Art. 6(1)(b) turns on the SECTORAL instrument, which this tool does not apply. Declining is
    only useful if the reader learns what is unresolved and who resolves it — "consult a
    specialist" is not an action."""
    result = classify("x", a_silent_doc_brain(AnnexIProduct.MEDICAL_DEVICES), "uc")

    assert result.overall_risk_class == RiskClass.NEEDS_REVIEW
    why = result.reasoning
    assert "6(1)(b)" in why, "the unresolved question must be named"
    assert "2017/745" in why, "the instrument that decides it must be named"
    assert "notified body" in why, "the specialist who answers it must be named"


def test_the_handover_is_per_sector_not_generic():
    """A vehicle is type-approved, a machine may self-certify under Annex IV — pointing everyone at
    a notified body would be wrong for both."""
    vehicle = classify("x", a_silent_doc_brain(AnnexIProduct.MOTOR_VEHICLES), "uc").reasoning
    assert "2018/858" in vehicle
    assert "type-approval" in vehicle

    machine = classify("x", a_silent_doc_brain(AnnexIProduct.MACHINERY), "uc").reasoning
    assert "2006/42/EC" in machine
    assert "Annex IV" in machine, "the Machinery Directive's own test should be named"


def test_every_annex_i_product_has_a_handover():
    """Both mappings are exhaustive and neither carries a default.

    A default would be the dangerous option: an instrument added to Annex I would inherit whatever
    it defaulted to — "ask the notified body" is right for most Section A products and wrong for
    every transport one — and the report would state it confidently. Without one, the same addition
    raises here instead."""
    products = set(AnnexIProduct)
    assert set(_ANNEX_I_LEGISLATION) == products, "every product needs its instrument named"
    assert set(_ANNEX_I_CONFORMITY_ROUTE) == products, "every product needs its specialist named"

    for product in products:
        assert product.legislation.strip()
        assert product.who_decides_conformity.strip()


def test_a_product_missing_from_the_mappings_raises():
    """The guarantee the missing default buys: silence is impossible, so a half-updated Annex I
    fails loudly rather than misinforming a reader about who to ask."""
    orphan = AnnexIProduct.LIFTS
    saved = _ANNEX_I_CONFORMITY_ROUTE.pop(orphan)
    try:
        with pytest.raises(KeyError):
            _ = orphan.who_decides_conformity
    finally:
        _ANNEX_I_CONFORMITY_ROUTE[orphan] = saved


def test_a_missing_conformity_route_is_reported_as_a_documentation_gap():
    """Silence about the conformity route is not merely inconvenient for the tool — Annex IV(9)
    puts the EU declaration of conformity in the technical documentation and Annex V fixes its
    contents, and the sectoral legislation demands the same independently. Reporting only that the
    tool could not decide would put the failure on the wrong side of the exchange."""
    why = classify("x", a_silent_doc_brain(AnnexIProduct.MEDICAL_DEVICES), "uc").reasoning

    assert "declaration of conformity" in why
    assert "Annex V" in why, "the provision fixing what the declaration must contain"
    assert "worth fixing" in why, "the reader needs an action, not an apology"
