"""The gap-analysis graph: classification + documentation -> ComplianceReport.

The judge is stubbed. What is pinned here is the wiring around it — which obligations activate,
which are reported without being judged, and whether the tally can be read at face value.
"""

from __future__ import annotations

from datetime import date

import pytest

from aiact.gap.graph import analyse
from aiact.gap.rules import roles_with_rules, select_rules
from aiact.policy_loader import load_policy_spec
from aiact.schemas.classification import (
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import ActorRole, DerogationCondition, RiskClass, Verdict
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer

DOCUMENT = "# Doc\n\n## Human oversight\n\nA panel reviews every recommendation.\n"


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def a_use_case(use_case_id: str, risk_class: RiskClass) -> UseCaseClassification:
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
    return UseCaseClassification(
        use_case_id=use_case_id,
        description="a system",
        risk_class=risk_class,
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
    """Returns a fixed verdict, and records what it was asked."""

    def __init__(self, verdict: Verdict = Verdict.PASS) -> None:
        self.verdict = verdict
        self.asked: list[str] = []

    def judge(self, rule, document):  # noqa: ANN001 - mirrors LLMJudge.judge
        from aiact.gap.judge import Judgement

        self.asked.append(rule.rule_id)
        return Judgement(
            verdict=self.verdict,
            reasoning="stubbed",
            evidence_quote="A panel reviews every recommendation.",
            evidence_chunk_id="c000",
            confidence="high",
        )


# --- what activates ------------------------------------------------------------------------------
def test_only_the_rules_for_this_risk_class_activate(spec):
    high = select_rules(spec, a_use_case("scoring", RiskClass.HIGH_RISK), ActorRole.PROVIDER)
    minimal = select_rules(spec, a_use_case("chat", RiskClass.MINIMAL), ActorRole.PROVIDER)
    assert high.document_verifiable, "a high-risk use case owes Chapter III"
    assert not minimal.document_verifiable, "a minimal-risk use case owes no Chapter III"
    # But NOT nothing at all: Art. 4 binds every tier the Regulation governs, and an empty set here
    # would make `minimal` indistinguishable from `out_of_scope` — the collapse the class exists to
    # prevent.
    assert [r.rule_id for r in minimal.all_rules] == ["AIA-ALL-A04"]


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
    assert "AIA-HR-A14" in provider_ids and "AIA-HR-A14" not in deployer_ids
    assert deployer_ids == {"AIA-ALL-A04", "AIA-DP-A26", "AIA-DP-A27", "AIA-DP-A86"}
    assert provider_ids & deployer_ids == {"AIA-ALL-A04"}


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
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    by_use_case = {f.use_case_id for f in report.findings}
    assert by_use_case == {"parsing", "scoring"}
    scoring = [f.rule_id for f in report.findings if f.use_case_id == "scoring"]
    parsing = [f.rule_id for f in report.findings if f.use_case_id == "parsing"]
    assert len(scoring) > len(parsing), "high-risk activates the Chapter III requirements"
    assert parsing == ["AIA-NHR-A06-4"], "not_high_risk owes the Art. 6(4) assessment"


def test_process_obligations_are_reported_but_never_judged(spec):
    """Art. 17-21 and the conformity/registration duties apply, but a technical file cannot
    evidence them. Judging them would invite a false PASS; omitting them would read as full
    coverage of Chapter III."""
    judge = StubJudge()
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        judge=judge,  # type: ignore[arg-type]
        max_workers=1,
    )
    outstanding = report.not_document_verifiable
    assert "AIA-PO-A17" in outstanding[ActorRole.PROVIDER]
    assert "AIA-PO-A17" not in judge.asked
    # Grouped by who owes them: a provider cannot confirm that a deployer informed its workers.
    assert outstanding[ActorRole.DEPLOYER] == [
        "AIA-ALL-A04",
        "AIA-DP-A26",
        "AIA-DP-A27",
        "AIA-DP-A86",
    ]
    flat = {r for ids in outstanding.values() for r in ids}
    assert not flat & {f.rule_id for f in report.findings}


# --- the report ----------------------------------------------------------------------------------
def test_the_report_is_assembled_and_validates(spec):
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
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
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    assert report.summary.per_use_case is not None
    assert set(report.summary.per_use_case) == {"parsing", "scoring"}


def test_concurrent_and_sequential_runs_agree(spec):
    """A report whose contents depended on thread scheduling would not be defensible."""
    classification = a_classification(a_use_case("scoring", RiskClass.HIGH_RISK))
    one = analyse(DOCUMENT, classification, spec, judge=StubJudge(), max_workers=1)  # type: ignore[arg-type]
    many = analyse(DOCUMENT, classification, spec, judge=StubJudge(), max_workers=8)  # type: ignore[arg-type]
    assert [f.rule_id for f in one.findings] == [f.rule_id for f in many.findings]


# --- which duty-holders a report covers -----------------------------------------------------------
def test_the_covered_roles_come_from_the_spec(spec):
    """DERIVED, not listed by hand. A hand-written list is a second place to keep in sync, and the
    failure is silent: a rule added for a new role would never be selected for, so it would sit in
    the spec looking covered while activating for nobody."""
    assert roles_with_rules(spec) == [
        ActorRole.PROVIDER,
        ActorRole.DEPLOYER,
        ActorRole.IMPORTER,
        ActorRole.DISTRIBUTOR,
        ActorRole.AUTHORISED_REPRESENTATIVE,
    ]


def test_the_supply_chain_roles_each_owe_their_own_article(spec):
    """Arts. 22-24 are duties of the representative, importer and distributor themselves — not a
    weaker echo of the provider's. Each role must select its own rule and nobody else's."""
    scoring = a_use_case("scoring", RiskClass.HIGH_RISK)
    owed = {
        role: {r.rule_id for r in select_rules(spec, scoring, role).all_rules}
        for role in (ActorRole.IMPORTER, ActorRole.DISTRIBUTOR, ActorRole.AUTHORISED_REPRESENTATIVE)
    }
    assert owed[ActorRole.IMPORTER] == {"AIA-IM-A23"}
    assert owed[ActorRole.DISTRIBUTOR] == {"AIA-DI-A24"}
    assert owed[ActorRole.AUTHORISED_REPRESENTATIVE] == {"AIA-AR-A22"}


def test_the_report_lists_every_role_the_act_binds(spec):
    """The whole point of the change: one run, every duty-holder. Reaching the report matters, not
    just the helper — silence there is what a reader takes for a clean bill of health."""
    report = analyse(
        DOCUMENT,
        a_classification(a_use_case("scoring", RiskClass.HIGH_RISK)),
        spec,
        judge=StubJudge(),  # type: ignore[arg-type]
        max_workers=1,
    )
    outstanding = report.not_document_verifiable
    assert "AIA-IM-A23" in outstanding[ActorRole.IMPORTER]
    assert "AIA-DI-A24" in outstanding[ActorRole.DISTRIBUTOR]
    assert "AIA-AR-A22" in outstanding[ActorRole.AUTHORISED_REPRESENTATIVE]
    assert "AIA-DP-A26" in outstanding[ActorRole.DEPLOYER]
    assert "AIA-PO-A17" in outstanding[ActorRole.PROVIDER]
    # Every role the ruleset covers appears; which roles those are is settled by the coverage
    # ledger before shipping, not narrated in the report — see test_policy_loader.
    assert set(outstanding) == set(roles_with_rules(spec))
