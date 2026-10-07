"""The review response: the report plus everything a page needs to show it without the spec.

A `ComplianceReport` names rules and norms by id, and its notes are properties that serialisation
drops. A page cannot act on an id, so this resolves each one the report names and carries the notes
as fields.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from aiact.report_app.citations import segment_citations
from aiact.reporting import application_date, cite, condition_text
from aiact.schemas.norm import NormKind
from aiact.schemas.policy import PolicyRuleset
from aiact.schemas.report import ComplianceReport
from aiact.summary import SystemSummary


class RuleView(BaseModel):
    """One obligation the report names, in the words a reader acts on."""

    rule_id: str
    citation: str
    requirement: str
    evidence_expected: str
    activation_condition: str | None
    document_verifiable: bool
    application_dates: dict[str, date | None]
    """When the obligation starts to apply, per use case id. None where the date turns on an
    Article 6 route the classification has not settled."""
    effective_date_note: str | None


class NormView(BaseModel):
    """A permission, right or legal effect the report lists without judging."""

    norm_id: str
    kind: NormKind
    action: str
    conditions: str | None
    exceptions: str | None
    source_spans: list[str]
    citations: list[str]
    """The source text as a reader cites it, e.g. "Art. 99(3)", one per distinct provision."""


class ReportNotes(BaseModel):
    """The report's notes. Each is None where it does not apply to this system."""

    legacy_system: str | None
    provider_reallocation: str | None
    deployer_type: str | None
    real_world_testing: str | None
    chapter_v_gate: str | None
    rests_on_guidance: bool


class ReviewResponse(BaseModel):
    system_name: str | None
    """The system's name as the document gives it; None where it gives none."""
    system_summary: str | None
    """What the system does, in two or three sentences written by the model from the document.
    Shown to the reader only; the review itself never reads it."""
    report: ComplianceReport
    rules: dict[str, RuleView]
    norms: dict[str, NormView]
    notes: ReportNotes


def build_response(
    report: ComplianceReport, spec: PolicyRuleset, summary: SystemSummary | None = None
) -> ReviewResponse:
    by_id = {rule.rule_id: rule for rule in spec.rules}
    norms_by_id = {norm.norm_id: norm for norm in spec.report_norms}
    use_cases = report.classification.use_cases

    rule_ids = (
        {finding.rule_id for finding in report.findings}
        | {rule_id for ids in report.not_document_verifiable.values() for rule_id in ids}
        | {notice.rule_id for notice in report.timing_not_active}
    )
    rules = {
        rule_id: RuleView(
            rule_id=rule_id,
            citation=cite(rule),
            requirement=rule.requirement,
            evidence_expected=rule.evidence_expected,
            activation_condition=rule.activation_condition,
            document_verifiable=rule.document_verifiable,
            application_dates={
                use_case.use_case_id: application_date(rule, spec, use_case)
                for use_case in use_cases
            },
            effective_date_note=rule.effective_date_note,
        )
        for rule_id in sorted(rule_ids)
        if (rule := by_id.get(rule_id)) is not None
    }

    norm_ids = set(report.public_authority_statements)
    for bucket in (
        report.permissions,
        report.rights,
        report.legal_consequences,
        report.conditional_applicability,
    ):
        norm_ids |= {norm_id for ids in bucket.values() for norm_id in ids}
    norms = {
        norm_id: NormView(
            norm_id=norm_id,
            kind=norm.kind,
            action=norm.action,
            conditions=condition_text(norm.conditions) if norm.conditions else None,
            exceptions=condition_text(norm.exceptions) if norm.exceptions else None,
            source_spans=norm.source_spans,
            citations=list(
                dict.fromkeys(segment_citations().get(span, span) for span in norm.source_spans)
            ),
        )
        for norm_id in sorted(norm_ids)
        if (norm := norms_by_id.get(norm_id)) is not None
    }

    return ReviewResponse(
        system_name=summary.name if summary else None,
        system_summary=summary.summary if summary else None,
        report=report,
        rules=rules,
        norms=norms,
        notes=ReportNotes(
            legacy_system=report.legacy_system_note,
            provider_reallocation=report.provider_reallocation_note,
            deployer_type=report.deployer_type_note,
            real_world_testing=report.real_world_testing_note,
            chapter_v_gate=report.chapter_v_gate_note,
            rests_on_guidance=report.rests_on_guidance,
        ),
    )
