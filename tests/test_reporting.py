"""What the reader actually receives.

Everything else in this suite tests which obligations ACTIVATE. This file tests that the ones which
activate arrive intact, and it covers the half of the ruleset where that is easiest to lose.

A `document_verifiable: false` obligation — an appointment, a filing, a contract, a process — never
reaches the judge, so it never becomes a Finding carrying reasoning of its own. The report holds it
as a rule id and nothing else, and everything that makes it actionable lives on the rule in the
spec:

    activation_condition   WHICH members of the role owe it (Art. 22(1): third-country providers)
    evidence_expected      WHAT would satisfy it, including gaps the rule declares about itself
    effective_date_note    WHY its date is not the one the reader expects

A renderer that prints the id alone therefore drops the obligation rather than abbreviating it.
These tests derive the rules carrying each field from the spec and require the rendered report to
carry it too.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aiact.policy_loader import load_policy_spec
from aiact.reporting import render_report
from aiact.schemas.classification import (
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import ActorRole, AnnexIIIArea, RiskClass
from aiact.schemas.policy import LegalSource
from aiact.schemas.report import ComplianceReport, ReportSummary


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def _report(spec, outstanding: dict[ActorRole, list[str]]) -> ComplianceReport:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=spec.act_version_date
    )
    use_case = UseCaseClassification(
        use_case_id="uc",
        description="a system",
        risk_class=RiskClass.HIGH_RISK,
        annex_iii_area=AnnexIIIArea.EMPLOYMENT,
        reasoning="fixture",
        confidence="high",
        triggered_by=[ClassificationEvidence(source=source, reasoning="fixture")],
    )
    return ComplianceReport(
        system_id="sys",
        act_version_date=spec.act_version_date,
        spec_version=spec.spec_version,
        generated_at=datetime.now(UTC),
        classification=ClassificationResult(
            use_cases=[use_case],
            overall_risk_class=RiskClass.HIGH_RISK,
            reasoning="fixture",
            triggered_by=[ClassificationEvidence(source=source, reasoning="fixture")],
            confidence="high",
        ),
        findings=[],
        not_document_verifiable=outstanding,
        summary=ReportSummary(total_applicable=0, passed=0, gaps=0, inadequate=0, needs_review=0),
    )


def test_every_condition_the_spec_writes_reaches_the_reader(spec):
    """A CONDITION THAT IS NOT RENDERED IS A CONDITION THAT WAS DROPPED, and dropping it turns a
    narrow duty into a universal one.

    `PolicyRule.activation_condition` says of itself: "IT NARROWS THE DUTY-HOLDER, NOT THE REPORT.
    Such a rule is still selected, still listed under its role… the obligation is stated WITH its
    condition rather than as an unqualified duty of every deployer." `select_rules` holds up its
    half — the rule is never withheld. This is the other half.

    Every rule carrying a condition is rendered here and the condition must survive. DERIVED from
    the spec, so a rule that gains a condition is covered without anyone remembering to add it."""
    conditioned = [r for r in spec.rules if r.activation_condition]
    assert conditioned, "no rule carries an activation_condition — re-derive this test"

    text = render_report(
        _report(spec, {ActorRole.PROVIDER: [r.rule_id for r in conditioned]}), spec
    )
    for rule in conditioned:
        assert rule.rule_id in text, f"{rule.rule_id} is not rendered at all"
        opening = " ".join(rule.activation_condition.split())[:60]
        assert opening in " ".join(text.split()), (
            f"{rule.rule_id} is rendered without its activation_condition. A reader is told to "
            f"confirm an obligation the Act does not put on them."
        )


def test_an_obligation_nobody_judged_still_says_what_would_satisfy_it(spec):
    """`evidence_expected` reaches the judge only for `document_verifiable: true` rules — the judge
    returns NOT_APPLICABLE before building a prompt otherwise. For every process obligation it is
    therefore the renderer or nobody.

    AIA-ALL-A49-4 is the case that makes this load-bearing rather than cosmetic. The spec declares
    that rule deliberately under-inclusive — `AnnexIIIArea` cannot express "Annex III point 1 used
    FOR law enforcement", so a police face-matching system is not selected for it — and says the gap
    "is recorded in `evidence_expected` so a biometrics provider is told to check it themselves".
    That sentence is only true if this holds."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-ALL-A49-4")
    assert not rule.document_verifiable, "re-derive this test: the rule now reaches the judge"
    text = " ".join(
        render_report(_report(spec, {ActorRole.PROVIDER: [rule.rule_id]}), spec).split()
    )
    assert " ".join(rule.evidence_expected.split())[:60] in text


def test_a_timing_note_travels_with_the_obligation_it_qualifies(spec):
    """`effective_date_note` says of itself: "carried to the report, not left in a comment only we
    read." The Section 5 rules apply from 2 August 2026 while the Section 2 requirements they attest
    to wait until December 2027, and a reader meeting that unexplained concludes the tool is broken
    — the damaging response being to disregard the date rather than the note."""
    noted = [r for r in spec.rules if r.effective_date_note and not r.document_verifiable]
    assert noted, "no unjudged rule carries an effective_date_note — re-derive this test"
    text = " ".join(
        render_report(_report(spec, {ActorRole.PROVIDER: [r.rule_id for r in noted]}), spec).split()
    )
    for rule in noted:
        assert " ".join(rule.effective_date_note.split())[:60] in text, rule.rule_id
        assert rule.effective_date is not None and rule.effective_date.isoformat() in text
