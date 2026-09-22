"""The gap-analysis graph: classification + documentation -> ComplianceReport.

The judge is stubbed. What is pinned here is the wiring around it — which obligations activate,
which are reported without being judged, and whether the tally can be read at face value.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from aiact.classify import ScriptedBrain
from aiact.gap import roles
from aiact.gap.graph import analyse
from aiact.gap.rules import roles_with_rules, select_rules
from aiact.policy_loader import load_policy_spec
from aiact.schemas.classification import (
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    DeployerType,
    DerogationCondition,
    ProviderReallocation,
    RiskClass,
    TransparencyDuty,
    Verdict,
)
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = "# Doc\n\n## Human oversight\n\nA panel reviews every recommendation.\n"


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def a_use_case(use_case_id: str, risk_class: RiskClass) -> UseCaseClassification:
    """A use case as the cascade actually produces one.

    The Annex III area is set for every tier the Art. 6(2) route can reach — high_risk and
    not_high_risk both mean "in a listed area", the second by derogation. Some rules are gated on
    the area (Arts. 27, 43, 49), so a fixture without one is not a simpler use case, it is an
    impossible one, and it would quietly under-select."""
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=date(2024, 7, 12)
    )
    def an_answer(value):
        return Answer(
            value=value, reasoning="fixture", confidence="high", source=source
        )

    # Art. 6(3) exempts only on both limbs, so a not_high_risk use case cannot be constructed
    # without them — see UseCaseClassification._enforce_derogation_conjunction.
    derogated = risk_class == RiskClass.NOT_HIGH_RISK
    in_annex_iii = risk_class in (RiskClass.HIGH_RISK, RiskClass.NOT_HIGH_RISK)
    return UseCaseClassification(
        use_case_id=use_case_id,
        description="a system",
        risk_class=risk_class,
        annex_iii_area=AnnexIIIArea.EMPLOYMENT if in_annex_iii else None,
        derogation=an_answer(DerogationCondition.NARROW_PROCEDURAL_TASK) if derogated else None,
        poses_significant_risk=an_answer(False) if derogated else None,
        reasoning="fixture",
        confidence="high",
        triggered_by=[
            ClassificationEvidence(source=source, quote="scores candidates", reasoning="Art. 6(3)")
        ],
    )


def a_classification(*use_cases: UseCaseClassification) -> ClassificationResult:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=date(2024, 7, 12)
    )
    return ClassificationResult(
        use_cases=list(use_cases),
        overall_risk_class=max(
            (uc.risk_class for uc in use_cases), key=lambda r: r == RiskClass.HIGH_RISK
        ),
        reasoning="fixture",
        triggered_by=[
            ClassificationEvidence(source=source, quote="scores candidates", reasoning="Art. 6(3)")
        ],
        confidence="high",
    )


class StubJudge:
    """Returns a fixed verdict, and records what it was asked.

    An aggregate rule gets the same verdict on every mandatory criterion, as LLMJudge would return
    it; the graph recomputes the rule verdict from those."""

    def __init__(self, verdict: Verdict = Verdict.PASS) -> None:
        self.verdict = verdict
        self.asked: list[str] = []

    def judge(self, rule, document):  # noqa: ANN001 - mirrors LLMJudge.judge
        from aiact.gap.judge import Judgement
        from aiact.schemas.report import CriterionFinding

        self.asked.append(rule.rule_id)
        return Judgement(
            verdict=self.verdict,
            reasoning="stubbed",
            evidence_quote="A panel reviews every recommendation.",
            evidence_chunk_id="c000",
            confidence="high",
            criteria=tuple(
                CriterionFinding(
                    norm_id=c.norm_id,
                    mandatory=True,
                    verdict=self.verdict,
                    reasoning="stubbed",
                    confidence="high",
                )
                for c in rule.criteria
                if c.mandatory
            ),
        )


# --- what activates ------------------------------------------------------------------------------
def test_only_the_rules_for_this_risk_class_activate(spec):
    high = select_rules(spec, a_use_case("scoring", RiskClass.HIGH_RISK), ActorRole.PROVIDER)
    minimal = select_rules(spec, a_use_case("chat", RiskClass.MINIMAL), ActorRole.PROVIDER)
    assert high.document_verifiable, "a high-risk use case owes Chapter III"
    assert not minimal.document_verifiable, "a minimal-risk use case owes no Chapter III"
    # But NOT nothing at all: Art. 4 binds every tier the Regulation governs, and an empty set here
    # would make `minimal` indistinguishable from `out_of_scope` — the collapse the class exists to
    # prevent. Art. 79 joins it for the same reason, one Article further on: it reaches any system
    # presenting a risk rather than a tier, and 79(6)(d) names Art. 50 as a ground. Art. 53(7) is
    # the fourth and is not about the system at all: a provider of any governed tier that built on
    # someone else's general-purpose AI model holds that model's Annex XII documentation in
    # confidence.
    assert sorted(r.rule_id for r in minimal.all_rules) == [
        "AIA-RULE-ALL-A04",
        "AIA-RULE-ALL-A04A",
        "AIA-RULE-ALL-A75c-3",
            "AIA-RULE-ALL-A79",
            "AIA-RULE-PO-A53-7",
            "AIA-RULE-PO-A59-P1-E",
        ]


def test_an_out_of_scope_use_case_owes_nothing_at_all(spec):
    """The contrast that gives `minimal` its meaning. A minimal system is inside the Regulation and
    owes Art. 4; an excluded one owes nothing under this Regulation, Art. 4 included."""
    out = select_rules(spec, a_use_case("military", RiskClass.OUT_OF_SCOPE), ActorRole.PROVIDER)
    assert out.all_rules == ()


def test_each_role_gets_its_own_obligations(spec):
    """Duties attach to the role. The provider owes Chapter III, the deployer owes Arts. 26-27, and
    Art. 4 lands on both — so the same use case yields two different sets."""
    scoring = a_use_case("scoring", RiskClass.HIGH_RISK)
    provider = select_rules(spec, scoring, ActorRole.PROVIDER)
    deployer = select_rules(spec, scoring, ActorRole.DEPLOYER)
    assert provider.role == ActorRole.PROVIDER and deployer.role == ActorRole.DEPLOYER

    provider_ids = {r.rule_id for r in provider.all_rules}
    deployer_ids = {r.rule_id for r in deployer.all_rules}
    assert "AIA-RULE-HR-A14" in provider_ids and "AIA-RULE-HR-A14" not in deployer_ids
    assert deployer_ids == {
        "AIA-RULE-ALL-A04",
        "AIA-RULE-ALL-A04A",
        "AIA-RULE-ALL-A73",
        "AIA-RULE-ALL-A73-10",
        "AIA-RULE-ALL-A75c-3",
        "AIA-RULE-ALL-A79",
        "AIA-RULE-ALL-A82",
        "AIA-RULE-DP-A26",
            "AIA-RULE-DP-A26-11",
            "AIA-RULE-DP-A26-12",
            "AIA-RULE-DP-A26-6",
            "AIA-RULE-DP-A26-7",
            "AIA-RULE-DP-A26-8",
            "AIA-RULE-DP-A26-8-UNREGISTERED-NOTICE",
            "AIA-RULE-DP-A26-8-UNREGISTERED-PROHIBITION",
            "AIA-RULE-DP-A26-9",
        "AIA-RULE-DP-A27",
        "AIA-RULE-DP-A27-2",
        "AIA-RULE-DP-A27-3",
        "AIA-RULE-DP-A46-2",
        "AIA-RULE-DP-A49-3",
        "AIA-RULE-DP-A71-3",
        "AIA-RULE-DP-A86",
    }
    # The rules that bind by something other than the role: Art. 4 by the tier, and Arts. 75c(3),
    # 79 and 82 by an act of an authority — an AI Office non-compliance decision, an opened
    # evaluation, a finding that a complying system still presents a risk. Art. 73 joins them by an
    # EVENT: the report is the provider's under 73(1), and Art. 26(5) hands it to a deployer that
    # has identified a serious incident and cannot reach the provider.
    assert provider_ids & deployer_ids == {
            "AIA-RULE-ALL-A04",
            "AIA-RULE-ALL-A04A",
            "AIA-RULE-ALL-A73",
        "AIA-RULE-ALL-A73-10",
        "AIA-RULE-ALL-A75c-3",
        "AIA-RULE-ALL-A79",
        "AIA-RULE-ALL-A82",
    }


def test_selection_is_per_use_case(spec):
    """Obligations attach to the intended purpose, not the product. A file whose parsing is
    not_high_risk and whose scoring is high_risk owes Chapter III on the scoring use case only."""
    report = analyse(
        DOCUMENT,
        a_classification(
            a_use_case("parsing", RiskClass.NOT_HIGH_RISK),
            a_use_case("scoring", RiskClass.HIGH_RISK),
        ),
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    by_use_case = {f.use_case_id for f in report.findings}
    assert by_use_case == {"parsing", "scoring"}
    scoring = [f.rule_id for f in report.findings if f.use_case_id == "scoring"]
    parsing = [f.rule_id for f in report.findings if f.use_case_id == "parsing"]
    assert len(scoring) > len(parsing), "high-risk activates the Chapter III requirements"
    assert parsing == ["AIA-RULE-NHR-A06-4"], "not_high_risk owes the Art. 6(4) assessment"


def test_process_obligations_are_reported_but_never_judged(spec):
    """Art. 17-21 and the conformity/registration duties apply, but a technical file cannot
    evidence them. Judging them would invite a false PASS; omitting them would read as full
    coverage of Chapter III."""
    judge = StubJudge()
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        brain=ScriptedBrain({}),
        judge=judge,  # type: ignore[arg-type]
        max_workers=1,
    )
    outstanding = report.not_document_verifiable
    assert "AIA-RULE-PO-A17" in outstanding[ActorRole.PROVIDER]
    assert report.permissions[ActorRole.PROVIDER] == [
        "AIA-NORM-A002-P13-LIMIT-HIGH-RISK-REQUIREMENTS",
        "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING",
        "AIA-NORM-A004A-P2-OTHER-SYSTEM-BIAS-DATA-PROCESSING",
        "AIA-NORM-A008-P2-INTEGRATE-COMPLIANCE-PROCESSES",
        "AIA-NORM-A009-P10-INTEGRATE-RISK-PROCESSES",
        "AIA-NORM-A009-P7-REAL-WORLD-TESTING",
        "AIA-NORM-A010-P3-COMBINED-DATASETS",
        "AIA-NORM-A011-P1-SIMPLIFY",
        "AIA-NORM-A015-P4-REDUNDANCY",
        "AIA-NORM-A017-P3-SECTORAL-INTEGRATION",
    ]
    assert report.legal_consequences[ActorRole.PROVIDER] == [
        "AIA-NORM-A017-P4-FINANCIAL-DEEMING",
        "AIA-NORM-A040-P1-HARMONISED-STANDARD-PRESUMPTION",
        "AIA-NORM-A041-P3-COMMON-SPECIFICATION-PRESUMPTION",
        "AIA-NORM-A042-P1-REPRESENTATIVE-DATA-PRESUMPTION",
        "AIA-NORM-A042-P2-CYBERSECURITY-CERTIFICATE-PRESUMPTION",
        "AIA-NORM-A042-P3-CYBER-RESILIENCE-DEEMING",
    ]
    assert report.conditional_applicability[ActorRole.PROVIDER] == [
        "AIA-NORM-A009-P3-MITIGABLE-RISK-SCOPE",
        "AIA-NORM-A010-P6-TESTING-DATA-ONLY",
        "AIA-NORM-A014-P5-DISPROPORTIONATE-EXCEPTION",
        "AIA-NORM-A025-P4-OPEN-SOURCE-EXCEPTION",
    ]
    assert "AIA-RULE-PO-A17" not in judge.asked
    # Grouped by who owes them: a provider cannot confirm that a deployer informed its workers.
    assert outstanding[ActorRole.DEPLOYER] == [
        "AIA-RULE-ALL-A04",
        "AIA-RULE-ALL-A04A",
        "AIA-RULE-ALL-A73",
        "AIA-RULE-ALL-A73-10",
        "AIA-RULE-ALL-A75c-3",
        "AIA-RULE-ALL-A79",
        "AIA-RULE-ALL-A82",
        "AIA-RULE-DP-A26",
        "AIA-RULE-DP-A26-11",
        "AIA-RULE-DP-A26-12",
        "AIA-RULE-DP-A26-6",
        "AIA-RULE-DP-A26-7",
        "AIA-RULE-DP-A26-8",
        "AIA-RULE-DP-A26-8-UNREGISTERED-NOTICE",
        "AIA-RULE-DP-A26-8-UNREGISTERED-PROHIBITION",
        "AIA-RULE-DP-A26-9",
        "AIA-RULE-DP-A27",
        "AIA-RULE-DP-A27-2",
        "AIA-RULE-DP-A27-3",
        "AIA-RULE-DP-A46-2",
        "AIA-RULE-DP-A49-3",
        "AIA-RULE-DP-A71-3",
        "AIA-RULE-DP-A86",
    ]
    flat = {r for ids in outstanding.values() for r in ids}
    assert not flat & {f.rule_id for f in report.findings}


# --- the report ----------------------------------------------------------------------------------
def test_the_report_is_assembled_and_validates(spec):
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        system_id="talentrank",
        max_workers=1,
    )
    assert report.system_id == "talentrank"
    assert report.act_version_date == spec.act_version_date
    assert report.disclaimer, "every report carries the disclaimer"
    # A finding without a citation is an opinion.
    assert all(f.citation.article for f in report.findings)


@pytest.mark.parametrize(
    ("verdict", "field"),
    [
        (Verdict.PASS, "passed"),
        (Verdict.GAP, "gaps"),
        (Verdict.INADEQUATE, "inadequate"),
        (Verdict.NEEDS_REVIEW, "needs_review"),
    ],
)
def test_the_tally_counts_each_verdict_in_its_own_bucket(spec, verdict, field):
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(verdict),  # type: ignore[arg-type]
        max_workers=1,
    )
    assert getattr(report.summary, field) == report.summary.total_applicable
    assert report.summary.total_applicable == len(report.findings)


def test_not_applicable_is_counted_as_neither_applicable_nor_passed(spec):
    """A rule that never activated is not a check that passed — folding it into either number
    would inflate coverage."""
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(Verdict.NOT_APPLICABLE),  # type: ignore[arg-type]
        max_workers=1,
    )
    assert report.summary.total_applicable == 0
    assert report.summary.passed == 0
    assert report.findings, "the finding is still reported, just not counted"


def test_the_summary_breaks_down_per_use_case(spec):
    report = analyse(
        DOCUMENT,
        a_classification(
            a_use_case("parsing", RiskClass.NOT_HIGH_RISK),
            a_use_case("scoring", RiskClass.HIGH_RISK),
        ),
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    assert report.summary.per_use_case is not None
    assert set(report.summary.per_use_case) == {"parsing", "scoring"}


def test_concurrent_and_sequential_runs_agree(spec):
    """A report whose contents depended on thread scheduling would not be defensible."""
    classification = a_classification(a_use_case("scoring", RiskClass.HIGH_RISK))
    one = analyse(
        DOCUMENT,
        classification,
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    many = analyse(
        DOCUMENT,
        classification,
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=8,
    )
    assert [f.rule_id for f in one.findings] == [f.rule_id for f in many.findings]


# --- which duty-holders a report covers -----------------------------------------------------------
def test_the_covered_roles_come_from_the_spec(spec):
    """DERIVED, not listed by hand. A hand-written list is a second place to keep in sync, and the
    failure is silent: a rule added for a new role would never be selected for, so it would sit in
    the spec looking covered while activating for nobody."""
    assert roles_with_rules(spec) == [
        ActorRole.PROVIDER,
        ActorRole.PROSPECTIVE_PROVIDER,
        ActorRole.INITIAL_PROVIDER,
        ActorRole.SANDBOX_PARTICIPANT,
        ActorRole.DEPLOYER,
        ActorRole.IMPORTER,
        ActorRole.DISTRIBUTOR,
        ActorRole.AUTHORISED_REPRESENTATIVE,
        ActorRole.GPAI_PROVIDER,
    ]


def test_the_supply_chain_roles_each_owe_their_own_article(spec):
    """Arts. 22-24 are duties of the representative, importer and distributor themselves — not a
    weaker echo of the provider's. Each role must select its own rule and nobody else's.

    Arts. 79 and 82 sit beside each of them and are subtracted here rather than listed three times:
    both bind the OPERATOR, which Art. 3(8) defines to include all three, so they are the rules
    these roles share with the provider and with each other."""
    scoring = a_use_case("scoring", RiskClass.HIGH_RISK)
    owed = {
        role: {r.rule_id for r in select_rules(spec, scoring, role).all_rules}
        for role in (ActorRole.IMPORTER, ActorRole.DISTRIBUTOR, ActorRole.AUTHORISED_REPRESENTATIVE)
    }
    shared = {"AIA-RULE-ALL-A79", "AIA-RULE-ALL-A82"}
    assert all(shared <= ids for ids in owed.values()), "Arts. 79 and 82 bind every operator"
    assert owed[ActorRole.IMPORTER] - shared == {"AIA-RULE-IM-A23"}
    assert owed[ActorRole.DISTRIBUTOR] - shared == {"AIA-RULE-DI-A24"}
    # The representative owes one more than its own Article: Art. 71(2) names it in the paragraph
    # — the Annex VIII data is entered "by the provider or, where applicable, by the authorised
    # representative" — so it is a duty-holder there and not merely the provider's agent.
    assert owed[ActorRole.AUTHORISED_REPRESENTATIVE] - shared == {
        "AIA-RULE-AR-A22",
        "AIA-RULE-PO-A71-2",
    }


def test_the_report_lists_every_role_the_act_binds(spec):
    """The whole point of the change: one run, every duty-holder. Reaching the report matters, not
    just the helper — silence there is what a reader takes for a clean bill of health."""
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    outstanding = report.not_document_verifiable
    assert "AIA-RULE-IM-A23" in outstanding[ActorRole.IMPORTER]
    assert "AIA-RULE-DI-A24" in outstanding[ActorRole.DISTRIBUTOR]
    assert "AIA-RULE-AR-A22" in outstanding[ActorRole.AUTHORISED_REPRESENTATIVE]
    assert "AIA-RULE-DP-A26" in outstanding[ActorRole.DEPLOYER]
    assert "AIA-RULE-PO-A17" in outstanding[ActorRole.PROVIDER]
    # Every role the ruleset covers appears — except `initial_provider`, and its absence is the
    # finding rather than an omission: Art. 25(2) has no holder unless the provider role moved, and
    # here it did not. Which roles the ruleset covers is settled by the coverage ledger before
    # shipping, not narrated in the report — see test_policy_loader.
    # `gpai_provider` joins `initial_provider` in the same way: the AIA-RULE-GP-* rules gate on the
    # `gpai_model` class, which a high-risk SYSTEM is not, so the role is covered by the ruleset and
    # owes nothing on this run.
    assert set(outstanding) == set(roles_with_rules(spec)) - {
        ActorRole.INITIAL_PROVIDER,
        ActorRole.GPAI_PROVIDER,
    }


def test_article_59_permission_is_rendered_only_for_its_prospective_provider(spec):
    """A permission can activate through duties held by several roles without changing its owner."""
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    permission = "AIA-NORM-A059-P1-CONDITIONAL-FURTHER-PROCESSING"
    assert permission in report.permissions[ActorRole.PROSPECTIVE_PROVIDER]
    assert permission not in report.permissions.get(ActorRole.PROVIDER, [])
    assert permission not in report.permissions.get(ActorRole.SANDBOX_PARTICIPANT, [])


# --- Art. 25 — the one question about WHO rather than WHAT ---------------------------------------
def _report(spec, risk_class, answer=None, low_confidence=frozenset()):
    return analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", risk_class)),
        spec,
        brain=ScriptedBrain({roles.NODE_ID: answer}, low_confidence),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )


@pytest.mark.parametrize("limb", list(ProviderReallocation))
def test_art_25_names_who_the_provider_is(spec, limb):
    """Every limb reallocates the provider, and the report says which limb and what it costs.

    Stated about the PARTIES, never about "you": the report describes a value chain, and the
    organisation that took the role on may not be the one that wrote the document."""
    report = _report(spec, RiskClass.HIGH_RISK, limb)

    assert report.becomes_provider is limb
    note = report.provider_reallocation_note
    assert note is not None
    assert limb.citation in note
    assert "PROVIDER" in note
    assert "Art. 16" in note
    assert not re.search(r"\byou(r|rs|rself)?\b", note, re.I)


def test_art_25_never_changes_what_is_owed(spec):
    """It assigns a ROLE. The obligations were settled by the classification, and a report whose
    findings moved with this answer would mean the tier had been decided from who was reading."""
    without = _report(spec, RiskClass.HIGH_RISK, None)
    with_limb = _report(spec, RiskClass.HIGH_RISK, ProviderReallocation.NAME_OR_TRADEMARK)

    assert [f.rule_id for f in without.findings] == [f.rule_id for f in with_limb.findings]
    assert without.summary == with_limb.summary


def test_art_25_is_not_put_below_high_risk(spec):
    """Every limb of Art. 25(1) speaks of "a high-risk AI system", and 25(3) of a high-risk safety
    component. Nothing else has a provider for this Article to reallocate, so asking could only
    produce a finding the Article cannot support. `None` records that it was never put — which is
    not the same as an answer clearing the reader."""
    report = _report(spec, RiskClass.NOT_HIGH_RISK, ProviderReallocation.NAME_OR_TRADEMARK)

    assert report.provider_reallocation is None
    assert report.becomes_provider is None
    assert report.provider_reallocation_note is None


def test_no_reallocation_leaves_the_roles_as_the_document_describes_them(spec):
    """`None` is a real answer and the ordinary one: nobody's role changed hands. It must read as
    that rather than as a finding, so no note is rendered — but the question WAS put, and the
    report keeps that distinct from never having asked."""
    report = _report(spec, RiskClass.HIGH_RISK, None)

    assert report.provider_reallocation is not None
    assert report.becomes_provider is None
    assert report.provider_reallocation_note is None


def test_a_reallocation_that_cannot_be_cited_is_not_reported_as_one(spec):
    """Narrowing by TYPE, not by truthiness — the same discipline the cascade's own helpers follow.
    A brain putting an unrecognised value here has named no limb, and a reallocation nobody can
    cite is one the reader cannot check or contest."""
    report = _report(spec, RiskClass.HIGH_RISK, RiskClass.HIGH_RISK)  # not an Art. 25 limb

    assert report.becomes_provider is None
    assert report.provider_reallocation_note is None


def test_the_reallocation_note_names_what_the_initial_provider_now_owes(spec):
    """Art. 25(2) is the half that is invisible from the value alone: the party that placed the
    system on the market stops being its provider and owes the new one cooperation and technical
    access. A note omitting it names a burden and withholds the remedy."""
    note = _report(
        spec, RiskClass.HIGH_RISK, ProviderReallocation.SUBSTANTIAL_MODIFICATION
    ).provider_reallocation_note

    assert note is not None
    assert "Art. 25(2)" in note
    assert "stops being the provider" in note


def test_an_art_25_abstention_does_not_touch_the_findings(spec):
    """A run that cannot tell who the provider is has still checked the documentation. The
    obligations of both roles are listed either way, so declining here costs a reader nothing
    beyond the answer itself."""
    report = _report(
        spec, RiskClass.HIGH_RISK, None, low_confidence=frozenset({roles.NODE_ID})
    )

    assert report.findings
    assert report.provider_reallocation is not None
    assert report.provider_reallocation.confidence == "low"
    assert report.becomes_provider is None


def test_the_art_25_question_is_anchored_in_the_articles_it_turns_on():
    """Limb (b) turns on the Art. 3(23) definition of 'substantial modification', and Art. 16 is
    what the reallocation costs. Neither may be answered from a model's memory."""
    q = roles.load_questions(
        "2026-07-27", ROOT / "data" / "policy" / "articles", ROOT / "data" / "policy" / "annexes"
    )[roles.NODE_ID]

    assert "‘substantial modification’ means" in q.context  # Art. 3(23)
    assert "shall be considered to be a provider of a high-risk AI system" in q.context  # 25(1)
    assert "Providers of high-risk AI systems shall" in q.context  # Art. 16


# --- Art. 27 — reading the deployer's organisation out of the document ---------------------------
def _deployer_report(spec, risk_class, answer, area=AnnexIIIArea.EMPLOYMENT):
    use_case = a_use_case("scoring", risk_class)
    if area is None:
        use_case = use_case.model_copy(update={"annex_iii_area": None})
    return analyse(
        DOCUMENT,
        a_classification(use_case),
        spec,
        brain=ScriptedBrain({roles.DEPLOYER_NODE_ID: answer}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )


@pytest.mark.parametrize(
    "kind,caught",
    [
        (DeployerType.PUBLIC_BODY, True),
        (DeployerType.PUBLIC_SERVICE_PROVIDER, True),
        (DeployerType.NEITHER, False),
        (DeployerType.NOT_STATED, None),
    ],
)
def test_the_document_settles_art_27_where_it_names_the_deployer(spec, kind, caught):
    """Art. 27(1)'s condition is a fact about the ORGANISATION, so a report that restates it as
    prose leaves the reader to answer what the documentation already settles. Three outcomes, and
    the third is not the second: a document that does not say is not a document describing a
    private commercial deployer."""
    report = _deployer_report(spec, RiskClass.HIGH_RISK, kind)

    assert report.deployer_organisation is kind
    assert kind.caught_by_article_27 is caught
    note = report.deployer_type_note
    assert note is not None
    assert "Art. 27" in note


def test_reading_the_deployer_never_withholds_the_obligation(spec):
    """Art. 27 stays listed under the deployer whatever the answer. The report describes what the
    Act requires of each role; an obligation dropped because one limb of its condition looks
    unmet would be the tool deciding on someone's behalf which of their duties to take
    seriously."""
    for kind in DeployerType:
        report = _deployer_report(spec, RiskClass.HIGH_RISK, kind)
        assert "AIA-RULE-DP-A27" in report.not_document_verifiable[ActorRole.DEPLOYER]


def test_silence_is_reported_as_unresolved_not_as_a_clearance(spec):
    """The failure this guards is the whole reason `not_stated` is a value: reading "sold to
    recruiters" as "commercial, so no assessment owed" would clear a duty on evidence nobody
    supplied."""
    note = _deployer_report(spec, RiskClass.HIGH_RISK, DeployerType.NOT_STATED).deployer_type_note

    assert note is not None
    assert "unresolved" in note
    assert "not a finding that it does not" in note


def test_the_deployer_question_is_not_put_where_no_duty_turns_on_it(spec):
    """Art. 27(1) opens on "a high-risk AI system referred to in Article 6(2)", so an Annex I
    system carries no duty narrowed by the deployer's organisation, and nor does a lower tier.
    `None` records that the question was never put — not an answer of "not stated"."""
    annex_i = _deployer_report(spec, RiskClass.HIGH_RISK, DeployerType.PUBLIC_BODY, area=None)
    not_high = _deployer_report(spec, RiskClass.NOT_HIGH_RISK, DeployerType.PUBLIC_BODY)

    for report in (annex_i, not_high):
        assert report.deployer_type is None
        assert report.deployer_organisation is None
        assert report.deployer_type_note is None


def test_the_deployer_question_is_anchored_in_article_27():
    """The question turns on Art. 3(4)'s definition of 'deployer' and on who Art. 27(1) reaches;
    neither may be answered from a model's memory."""
    q = roles.load_questions(
        "2026-07-27", ROOT / "data" / "policy" / "articles", ROOT / "data" / "policy" / "annexes"
    )[roles.DEPLOYER_NODE_ID]

    assert "bodies governed by public law" in q.context  # Art. 27(1)
    assert "‘deployer’ means" in q.context  # Art. 3(4)


# --- Art. 49(3) — the same fact, a narrower duty -----------------------------------------------
@pytest.mark.parametrize(
    "kind,art_27,art_49_3",
    [
        (DeployerType.PUBLIC_BODY, True, True),
        (DeployerType.PUBLIC_SERVICE_PROVIDER, True, False),
        (DeployerType.NEITHER, False, False),
        (DeployerType.NOT_STATED, None, None),
    ],
)
def test_article_49_3_is_narrower_than_article_27_on_the_same_answer(kind, art_27, art_49_3):
    """One fact about the deployer, two duties, and they DIVERGE — a private entity providing
    public services owes the fundamental rights impact assessment and not the registration.
    Art. 27 reaches it for what it does; Art. 49(3) reaches public authorities for what they are.
    Collapsing the two would hand a hospital company a registration duty the Article withholds."""
    assert kind.caught_by_article_27 is art_27
    assert kind.caught_by_article_49_3 is art_49_3


def test_the_report_answers_both_duties_that_turn_on_the_deployer(spec):
    """A reader told only about Art. 27 would reasonably carry the answer across to Art. 49(3), and
    for one of the four values that inference is wrong."""
    for kind in DeployerType:
        note = _deployer_report(spec, RiskClass.HIGH_RISK, kind).deployer_type_note
        assert note is not None
        assert "Art. 27" in note and "Art. 49(3)" in note


def test_the_public_service_provider_is_told_the_two_answers_differ(spec):
    """The one value where the duties part company, so the one the note has to be explicit for."""
    note = _deployer_report(
        spec, RiskClass.HIGH_RISK, DeployerType.PUBLIC_SERVICE_PROVIDER
    ).deployer_type_note

    assert note is not None
    assert "Art. 27(1) reaches" in note
    assert "Art. 49(3) is narrower and does not reach it" in note
    # Never a clean "you are exempt": the acting-on-behalf limb is left open.
    assert "acting on a public authority's behalf" in note


def test_deployer_registration_is_never_withheld_from_the_report(spec):
    """Same discipline as Art. 27: the rule stays listed under the deployer whatever the answer.
    The condition narrows the duty-holder, not the report."""
    for kind in DeployerType:
        report = _deployer_report(spec, RiskClass.HIGH_RISK, kind)
        assert "AIA-RULE-DP-A49-3" in report.not_document_verifiable[ActorRole.DEPLOYER]


def _legacy_report(spec, risk_class, area=AnnexIIIArea.EMPLOYMENT, duties=()):
    use_case = a_use_case("scoring", risk_class)
    if area is None:
        use_case = use_case.model_copy(update={"annex_iii_area": None})
    classification = a_classification(use_case)
    if duties:
        # transparency_duties is DERIVED from the cascade's own answer, so the fixture supplies the
        # answer rather than the list — setting the property would test a shape nothing produces.
        answer = Answer(
            value=list(duties),
            reasoning="fixture",
            confidence="high",
            source=LegalSource(
                instrument="Regulation (EU) 2024/1689",
                article=50,
                act_version_date=date(2024, 7, 12),
            ),
            node_id="transparency",
        )
        classification = classification.model_copy(update={"transparency": answer})
    return analyse(
        DOCUMENT,
        classification,
        spec,
        brain=ScriptedBrain({}),
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )


def test_art_111_names_the_relief_without_granting_it(spec):
    """The report says a legacy system may owe less, and that the tool cannot tell if it is one.

    Art. 111(2) is RELIEF, so the failure direction is inverted from every other note here: guessing
    it right costs nothing, guessing it wrong clears a reader who is not cleared. The date it turns
    on — when the system was placed on the market — appears in no system card, so it is read and
    never derived, the same treatment Art. 6(1)(b) gets."""
    note = _legacy_report(spec, RiskClass.HIGH_RISK).legacy_system_note

    assert note is not None
    assert "Art. 111(2)" in note
    assert "2 December 2027" in note  # Art. 113(c)(i), the Annex III route
    assert "Art. 5" in note  # the relief does not reach the prohibitions
    assert "2 August 2030" in note  # nor a public-authority system
    assert "not stated in the documentation" in note
    assert not re.search(r"\byou(r|rs|rself)?\b", note, re.I)


def test_art_111_dates_the_two_routes_apart(spec):
    """Art. 113(c) gives Annex III and Annex I different dates, so Art. 111(2)'s window differs too.
    One date for both would be wrong for whichever route it was not written for."""
    annex_iii = _legacy_report(spec, RiskClass.HIGH_RISK).legacy_system_note
    assert annex_iii is not None and "2 December 2027" in annex_iii


def test_art_111_never_withholds_an_obligation(spec):
    """The whole point of reporting it rather than applying it. A report whose findings or counts
    moved with this note would be granting relief on a fact nothing established."""
    with_note = _legacy_report(spec, RiskClass.HIGH_RISK)
    assert with_note.legacy_system_note is not None
    assert with_note.findings
    assert with_note.summary.total_applicable > 0


def test_art_111_is_silent_where_no_legacy_relief_could_apply(spec):
    """Art. 111(2) speaks of high-risk systems, and 111(4) of the Art. 50(2) marking duty. A note on
    a system owing neither would be describing relief from nothing."""
    assert _legacy_report(spec, RiskClass.MINIMAL, area=None).legacy_system_note is None


def test_art_111_4_rides_on_the_duty_not_the_tier(spec):
    """Art. 50 is gated on the duty throughout, and its transitional deadline has to follow it —
    a minimal-risk generator owes Art. 50(2) and gets the later date with it."""
    duties = [TransparencyDuty.SYNTHETIC_CONTENT_MARKING]
    note = _legacy_report(spec, RiskClass.MINIMAL, area=None, duties=duties).legacy_system_note

    assert note is not None
    assert "Art. 111(4)" in note
    assert "2 December 2026" in note
    assert "Art. 111(2)" not in note  # minimal risk, so the Chapter III limb does not fire


def test_future_canonical_rule_is_reported_but_not_judged(spec):
    """Article 9's future route is a preparation notice, never a document verdict."""
    judge = StubJudge()
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        brain=ScriptedBrain({}),
        judge=judge,  # type: ignore[arg-type]
        max_workers=1,
        as_of_date=date(2026, 9, 22),
    )
    notices = [notice for notice in report.timing_not_active if notice.rule_id == "AIA-RULE-HR-A09"]
    assert len(notices) == 1
    assert notices[0].status == "upcoming"
    assert notices[0].application_date == date(2027, 12, 2)
    assert notices[0].legal_basis_segment_ids == ["AIA-TEXT-A113-C"]
    assert "AIA-RULE-HR-A09" not in judge.asked
    assert all(finding.rule_id != "AIA-RULE-HR-A09" for finding in report.findings)
