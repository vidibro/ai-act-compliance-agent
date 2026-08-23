"""Render a ComplianceReport as text a person can act on.

WHY THIS IS A MODULE AND NOT A PRINT LOOP IN THE SCRIPT. Half of what this ruleset finds is
`document_verifiable: false` — a duty discharged in a contract, a filing, an appointment or a
process, none of which a technical file can evidence. Those obligations never reach the judge and
so never become a Finding; the report carries them as rule ids alone, and everything that makes one
of them usable — WHICH members of the role owe it, WHEN it starts to apply, and WHAT would satisfy
it — lives on the rule in the spec.

Rendering them as a bare list of ids is therefore not a terse presentation of the obligation, it is
the loss of it. `AIA-PO-A22` on its own tells a provider established in the Union to confirm a duty
Art. 22(1) puts only on providers established in third countries; `AIA-ALL-A49-4` on its own tells a
biometrics provider nothing about the gap its own `evidence_expected` was written to disclose.

So the rule is looked up and its condition, date and expected evidence are rendered beside it. Here
rather than in `scripts/review.py` so that it is importable, and so a test can hold it to that.
"""

from __future__ import annotations

import textwrap

from aiact.schemas.enums import ActorRole, Verdict
from aiact.schemas.policy import PolicyRule, PolicySpec
from aiact.schemas.report import ComplianceReport

_MARK = {
    Verdict.PASS: "ok  ",
    Verdict.GAP: "GAP ",
    Verdict.INADEQUATE: "THIN",
    Verdict.NEEDS_REVIEW: "??  ",
    Verdict.NOT_APPLICABLE: "n/a ",
}


def _cite(rule: PolicyRule) -> str:
    source = rule.source
    paragraph = f"({source.paragraph})" if source.paragraph is not None else ""
    return f"Art. {source.article}{paragraph}"


def _wrapped(label: str, body: str, indent: str = "       ") -> list[str]:
    """One labelled block, wrapped to a terminal width, or nothing where there is no body."""
    if not body:
        return []
    text = " ".join(body.split())
    return textwrap.wrap(
        f"{label} {text}", width=96, initial_indent=indent, subsequent_indent=indent + "  "
    )


def _outstanding_block(rule: PolicyRule) -> list[str]:
    """One obligation nobody judged, with everything a reader needs to act on it.

    `activation_condition` comes FIRST and is the reason this function exists. The Act narrows
    several duties by a fact about the organisation rather than about the system — Art. 22(1) binds
    third-country providers, Art. 27(1) binds public bodies and public-service providers — and the
    ruleset's answer is to report the obligation to everyone WITH its condition attached rather than
    to guess who is exempt. That answer only works if the condition is rendered."""
    lines = [f"  --  {rule.rule_id:<16} {_cite(rule)}"]
    lines += _wrapped("applies to:", rule.activation_condition or "")
    lines += _wrapped("confirm:", rule.evidence_expected)
    if rule.effective_date is not None:
        lines += _wrapped("from:", rule.effective_date.isoformat())
    elif rule.effective_date_by_route:
        by_route = sorted(rule.effective_date_by_route.items(), key=lambda kv: kv[0].value)
        dates = ", ".join(f"{route.value} {day.isoformat()}" for route, day in by_route)
        lines += _wrapped("from:", dates)
    lines += _wrapped("note:", rule.effective_date_note or "")
    return lines


def render_report(report: ComplianceReport, spec: PolicySpec) -> str:
    """The whole report as text, grouped by the role that owes each obligation.

    Grouped by WHO OWES it, because a provider cannot act on a deployer's duty and a flat list
    invites them to try."""
    by_id = {rule.rule_id: rule for rule in spec.rules}
    out: list[str] = [
        f"risk class : {report.classification.overall_risk_class.value}",
        f"reasoning  : {report.classification.reasoning}",
        "",
    ]
    if report.scope_note:
        out += [f"!! {report.scope_note}", ""]

    # Art. 50 sits beside the tier, not inside it, and splits by duty-holder.
    for role, duties in report.classification.transparency_duties_by_role.items():
        cites = ", ".join(f"Art. 50({d.paragraph}) {d.value}" for d in duties)
        out.append(f"Art. 50, {role.value}: {cites}")
    if report.classification.transparency_duties:
        out.append("")

    for role in ActorRole:
        findings = [f for f in report.findings if f.role == role]
        outstanding = report.not_document_verifiable.get(role, [])
        if not findings and not outstanding:
            continue
        out.append(f"--- {role.value} ---")
        for finding in findings:
            rule = by_id.get(finding.rule_id)
            cite = _cite(rule) if rule else str(finding.citation.article)
            out.append(f"  {_MARK[finding.verdict]} {finding.rule_id:<16} {cite}")
            out += _wrapped("", finding.reasoning)
        if outstanding:
            out.append("  not checkable from the documentation — confirm separately:")
            for rule_id in outstanding:
                rule = by_id.get(rule_id)
                out += _outstanding_block(rule) if rule else [f"  --  {rule_id}"]
        counts = (report.summary.per_role or {}).get(role)
        if counts is not None:
            out.append(
                f"  {counts.total_applicable} checked — {counts.passed} pass, {counts.gaps} gap, "
                f"{counts.inadequate} inadequate, {counts.needs_review} needs review"
            )
        out.append("")

    if report.legacy_system_note:
        out += _wrapped("!!", report.legacy_system_note, indent="")
        out.append("")

    s = report.summary
    out.append(
        f"{s.total_applicable} applicable — {s.passed} pass, {s.gaps} gap, "
        f"{s.inadequate} inadequate, {s.needs_review} needs review"
    )
    return "\n".join(out)
