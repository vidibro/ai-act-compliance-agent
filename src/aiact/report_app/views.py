"""The review response: the report plus everything a page needs to show it without the spec.

A `ComplianceReport` names rules and norms by id, and its notes are properties that serialisation
drops. A page cannot act on an id, so this resolves each one the report names and carries the notes
as fields.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import date

from pydantic import BaseModel

from aiact.report_app import explanations
from aiact.report_app.citations import segment_citations
from aiact.report_app.law import Provision, article_of, paragraph_text, references
from aiact.reporting import application_date, cite, condition_text, deadline
from aiact.schemas.classification import UseCaseClassification
from aiact.schemas.norm import NormKind
from aiact.schemas.policy import PolicyRule, PolicyRuleset, ReportNorm
from aiact.schemas.report import ComplianceReport
from aiact.summary import SystemSummary


class CriterionView(BaseModel):
    """One separately judged part of a rule, as a reader names it."""

    citation: str
    """The provision it comes from, e.g. "Art. 13(3)(b)(iv)"."""
    action: str
    """What it requires, in a few words."""


class RuleView(BaseModel):
    """One obligation the report names, in the words a reader acts on."""

    explanation: str | None = None
    """What the duty means, in one to three plain sentences; None where none is written yet."""

    rule_id: str
    citation: str
    action: str | None
    requirement: str
    evidence_expected: str
    activation_condition: str | None
    document_verifiable: bool
    application_dates: dict[str, date | None]
    """When the obligation starts to apply, per use case id. None where the date turns on an
    Article 6 route the classification has not settled."""
    deadline: date | None = None
    """By when the obligation must be met, where its provision sets a date (Art. 111)."""
    effective_date_note: str | None
    references: list[Provision] = []
    """The other articles and annexes the requirement cites, with their titles."""
    criteria: dict[str, CriterionView] = {}
    """The rule's separately judged parts, by norm id, so a finding's criteria read as text."""


class NormView(BaseModel):
    """A permission, right or legal effect the report lists without judging."""

    norm_id: str
    kind: NormKind
    explanation: str | None = None
    """What the provision means, in one to three plain sentences; None where none is written."""
    actors: list[str]
    """Who the provision names, e.g. "law_enforcement_authority"."""
    action: str
    conditions: str | None
    exceptions: str | None
    source_spans: list[str]
    citations: list[str]
    """The source text as a reader cites it, e.g. "Art. 99(3)", one per distinct provision."""
    law: str = ""
    """The paragraph of the Act the provision comes from, in full — the context its one-line
    action leaves out."""
    references: list[Provision] = []
    """The other articles and annexes that paragraph cites, with their titles."""
    application_dates: dict[str, date | None] = {}
    """When the provision starts to apply, per use case id: the earliest date among the rules that
    bring it into the report. None where none of those dates is settled."""


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
    rule_ids = (
        {finding.rule_id for finding in report.findings}
        | {rule_id for ids in report.not_document_verifiable.values() for rule_id in ids}
        | {notice.rule_id for notice in report.timing_not_active}
    )
    norm_ids = set(report.public_authority_statements)
    for bucket in (
        report.permissions,
        report.rights,
        report.legal_consequences,
        report.conditional_duties,
        report.conditional_applicability,
    ):
        norm_ids |= {norm_id for ids in bucket.values() for norm_id in ids}

    return ReviewResponse(
        system_name=summary.name if summary else None,
        system_summary=summary.summary if summary else None,
        report=report,
        rules=resolve_rules(rule_ids, report.classification.use_cases, spec),
        norms=resolve_norms(norm_ids, spec, report.classification.use_cases),
        notes=ReportNotes(
            legacy_system=report.legacy_system_note,
            provider_reallocation=report.provider_reallocation_note,
            deployer_type=report.deployer_type_note,
            real_world_testing=report.real_world_testing_note,
            chapter_v_gate=report.chapter_v_gate_note,
            rests_on_guidance=report.rests_on_guidance,
        ),
    )


def resolve_rules(
    rule_ids: Iterable[str], use_cases: list[UseCaseClassification], spec: PolicyRuleset
) -> dict[str, RuleView]:
    """The named rules as a reader acts on them. An id the spec does not know is left out."""
    by_id = {rule.rule_id: rule for rule in spec.rules}
    readable = _readable(by_id)
    return {
        rule_id: RuleView(
            rule_id=rule_id,
            citation=cite(rule),
            action=rule.action,
            requirement=rule.requirement,
            evidence_expected=readable(rule.evidence_expected),
            activation_condition=readable(rule.activation_condition),
            document_verifiable=rule.document_verifiable,
            application_dates={
                use_case.use_case_id: application_date(rule, spec, use_case)
                for use_case in use_cases
            },
            deadline=deadline(rule, spec),
            references=references(rule.requirement, str(rule.source.article or "")),
            **_explained(rule_id, explanations.rule_input(rule), spec),
            effective_date_note=readable(rule.effective_date_note),
            criteria={
                criterion.norm_id: CriterionView(
                    # The first span is the criterion's own provision; the rest are context.
                    citation=_cite_spans(criterion.source_spans[:1])[0],
                    action=_sentence(criterion.action),
                )
                for criterion in rule.criteria
            },
        )
        for rule_id in sorted(set(rule_ids))
        if (rule := by_id.get(rule_id)) is not None
    }


_RULE_ID = re.compile(r"AIA-RULE-[A-Za-z0-9-]*[A-Za-z0-9]")
_GUIDANCE_TAG = re.compile(r"\[non-binding guidance: C-(\d{4})-(\d+)/[^\]]+\]")


def _readable(by_id: dict[str, PolicyRule]) -> Callable[[str | None], str | None]:
    """A rule text with every other rule it names given as that rule's citation, and every guidance
    tag as the Commission document it points to. Ids are how the ruleset cross-references itself;
    a reader knows the provisions and the documents, not the ids."""

    def replace(match: re.Match[str]) -> str:
        rule = by_id.get(match.group())
        return cite(rule) if rule is not None else match.group()

    def readable(text: str | None) -> str | None:
        if not text:
            return text
        text = _GUIDANCE_TAG.sub(r"(non-binding Commission guidance C(\1) \2)", text)
        return _RULE_ID.sub(replace, text)

    return readable


def _sentence(action: str) -> str:
    """A norm's action as a reader sees it on its own. Norms store it as the second half of a
    sentence ("include testing in ..."), to follow the actor; on its own it starts one."""
    return action[:1].upper() + action[1:]


def _explained(row_id: str, row_input: str, spec: PolicyRuleset) -> dict[str, object]:
    """The row's stored explanation, if it was written from the wording the row shows now."""
    found = explanations.current(row_id, row_input, spec.act_version_date)
    if found is None:
        return {}
    return {"explanation": found.text}


def _law(spans: list[str]) -> str:
    """The paragraphs a norm's source spans belong to, each once, in order. A lead-in on its own
    ("Providers of high-risk AI systems shall:") says nothing without its points and is left out;
    its article still shows as the norm's basis."""
    texts = (paragraph_text(span) for span in spans)
    return "\n\n".join(dict.fromkeys(t for t in texts if t and not t.rstrip().endswith(":")))


def _cite_spans(spans: list[str]) -> list[str]:
    """The provisions a list of text segments come from, as a reader cites them, once each."""
    citations = segment_citations()
    return list(dict.fromkeys(citations.get(span, span) for span in spans))


def resolve_norms(
    norm_ids: Iterable[str],
    spec: PolicyRuleset,
    use_cases: Iterable[UseCaseClassification] = (),
) -> dict[str, NormView]:
    """The named report norms in readable form. An id the spec does not know is left out."""
    norms_by_id = {norm.norm_id: norm for norm in spec.report_norms}
    rules_by_id = {rule.rule_id: rule for rule in spec.rules}

    def start(norm: ReportNorm, use_case: UseCaseClassification) -> date | None:
        dates = [
            day
            for rule_id in norm.activation_rule_ids
            if (rule := rules_by_id.get(rule_id)) is not None
            and (day := application_date(rule, spec, use_case)) is not None
        ]
        return min(dates, default=None)

    return {
        norm_id: NormView(
            norm_id=norm_id,
            kind=norm.kind,
            actors=norm.actors,
            action=_sentence(norm.action),
            conditions=condition_text(norm.conditions) if norm.conditions else None,
            exceptions=condition_text(norm.exceptions) if norm.exceptions else None,
            source_spans=norm.source_spans,
            citations=_cite_spans(norm.source_spans),
            **_explained(norm_id, explanations.norm_input(norm), spec),
            law=(law := _law(norm.source_spans)),
            references=references(law, article_of(norm.source_spans)),
            application_dates={
                use_case.use_case_id: start(norm, use_case) for use_case in use_cases
            },
        )
        for norm_id in sorted(set(norm_ids))
        if (norm := norms_by_id.get(norm_id)) is not None
    }
