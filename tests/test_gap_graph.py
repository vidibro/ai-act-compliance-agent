"""The gap-analysis graph: classification + documentation -> ComplianceReport.

The judge is stubbed. What is pinned here is the wiring around it — which obligations activate,
which are reported without being judged, and whether the tally can be read at face value.
"""

from __future__ import annotations

from datetime import date

import pytest

from aiact.gap.graph import analyse
from aiact.gap.rules import select_rules
from aiact.policy_loader import load_policy_spec
from aiact.schemas.classification import (
    ClassificationAnswer,
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import ActorRole, DerogationCondition, RiskClass, Verdict
from aiact.schemas.policy import LegalSource

DOCUMENT = "# Doc\n\n## Human oversight\n\nA panel reviews every recommendation.\n"


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def a_use_case(use_case_id: str, risk_class: RiskClass) -> UseCaseClassification:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=date(2024, 7, 12)
    )
    def an_answer(value):
        return ClassificationAnswer(
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
    assert not minimal.all_rules, "a minimal-risk use case owes none of these obligations"


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
    assert "AIA-PO-A17" in report.not_document_verifiable
    assert "AIA-PO-A17" not in judge.asked
    assert not set(report.not_document_verifiable) & {f.rule_id for f in report.findings}


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
