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
biometrics provider to register somewhere its `activation_condition` says most biometric systems
must not, and names none of the reduced Annex VIII fields that make the entry checkable.

So the rule is looked up and its condition, date and expected evidence are rendered beside it. Here
rather than in `scripts/review.py` so that it is importable, and so a test can hold it to that.

THE SAME LOSS IS POSSIBLE ANYWHERE THE REPORT COMPUTES SOMETHING. `ComplianceReport` composes three
notes as properties — the Art. 25 role change, what the deployer's own type settles, the legacy
system deadline — and a renderer that never reads one has found the thing and told nobody. A
`Finding` likewise carries the use case it is about and how sure the judge was, and two findings for
one rule are a contradiction on adjacent lines without the first. So the rule for this module is
that every field either reaches the text or has a written reason not to, and
`tests/test_reporting.py` is where each is held to it.
"""

from __future__ import annotations

import textwrap

from aiact.schemas.enums import ActorRole, Verdict
from aiact.schemas.policy import PolicyRule, PolicyRuleset
from aiact.schemas.report import ComplianceReport, Finding

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
        f"{label} {text}",
        width=96,
        initial_indent=indent,
        subsequent_indent=indent + "  ",
        # NEVER INSIDE A WORD. The Act's terms of art are hyphenated — "non-safety-related",
        # "administration-of-justice", "high-risk" — and a line break in the middle of one leaves
        # the reader searching the text for a term that is not written anywhere in it.
        break_on_hyphens=False,
        break_long_words=False,
    )


def _condition(rule: PolicyRule) -> list[str]:
    """WHICH members of the role owe this obligation.

    The Act narrows several duties by a fact about the organisation rather than about the system —
    Art. 22(1) binds third-country providers, Art. 27(1) binds public bodies and public-service
    providers — and the ruleset's answer is to report the obligation to everyone WITH its condition
    attached rather than to guess who is exempt. That answer only works if the condition is
    rendered, and it works the same way whether or not a judge looked at the documentation."""
    return _wrapped("applies to:", rule.activation_condition or "")


def _timing(rule: PolicyRule) -> list[str]:
    """WHEN the obligation starts to apply, and why that date is not the expected one.

    Rendered for judged and unjudged obligations alike: a PASS on a duty that does not begin until
    December 2027 says something different from a PASS on one that is already live, and Art. 6(4)
    — the only judged rule with a note — carries a date the Regulation does not settle."""
    if rule.effective_date is not None:
        lines = _wrapped("from:", rule.effective_date.isoformat())
    elif rule.effective_date_by_route:
        by_route = sorted(rule.effective_date_by_route.items(), key=lambda kv: kv[0].value)
        dates = ", ".join(f"{route.value} {day.isoformat()}" for route, day in by_route)
        lines = _wrapped("from:", dates)
    else:
        lines = []
    return lines + _wrapped("note:", rule.effective_date_note or "")


def _outstanding_block(rule: PolicyRule) -> list[str]:
    """One obligation nobody judged, with everything a reader needs to act on it.

    `evidence_expected` is the part only this branch renders. For a judged rule it was in front of
    the judge and the verdict's own reasoning answers it; for an unjudged one it is the whole of
    what the reader has to go on."""
    lines = [f"  --  {rule.rule_id:<16} {_cite(rule)}"]
    lines += _condition(rule)
    lines += _wrapped("confirm:", rule.evidence_expected)
    return lines + _timing(rule)


def _criteria_block(finding: Finding) -> list[str]:
    """Every criterion of an aggregate rule, named by its norm, with its own verdict.

    Each one is listed, passing or not, so a reader can see the rule was checked in full; a reason
    is printed for each that did not pass, since that is what the reader must act on."""
    if not finding.criteria:
        return []
    lines = ["       criteria:"]
    for criterion in finding.criteria:
        note = "" if criterion.mandatory else "   (not judged; cannot fail the rule)"
        lines.append(f"         {_MARK[criterion.verdict]} {criterion.norm_id}{note}")
        if criterion.mandatory and criterion.verdict is not Verdict.PASS:
            lines += _wrapped("", criterion.reasoning, indent="              ")
    return lines


def render_report(report: ComplianceReport, spec: PolicyRuleset) -> str:
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

    # WHOSE report this is, before anything it contains. Art. 25 moves the provider role, and a
    # reader who was not told reads the longest column below as somebody else's work. The enum
    # value alone does not say that; the note does, and it also carries Art. 25(2) — the party
    # they bought from has stopped being the provider and owes them cooperation.
    if report.provider_reallocation_note:
        out += _wrapped("!!", report.provider_reallocation_note, indent="") + [""]
    if report.deployer_type_note:
        out += _wrapped("!!", report.deployer_type_note, indent="") + [""]
    # The only note attached to a WITHHOLDING. Six obligations are listed or not listed on this
    # answer, so a renderer that skipped it would leave a reader unable to tell a system that
    # cleared Art. 60 from one nobody asked about.
    if report.real_world_testing_note:
        out += _wrapped("!!", report.real_world_testing_note, indent="") + [""]
    # Chapter V lists every obligation for every model, because neither of its two gates is a fact
    # a model card reliably settles. This is the other half: the reader is told what their OWN
    # document says about each line, rather than having the condition read back at them.
    if report.chapter_v_gate_note:
        out += _wrapped("!!", report.chapter_v_gate_note, indent="") + [""]

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
            # THE USE CASE AND THE CONFIDENCE ARE PART OF THE VERDICT. One rule is judged once per
            # use case, so a two-purpose system produces two findings with the same id and role —
            # a pass and a gap on adjacent lines, and without the label nothing says they are about
            # different things. And an unlabelled low-confidence PASS reads as a confident one,
            # which for a compliance tool is the most expensive error available.
            out.append(
                f"  {_MARK[finding.verdict]} {finding.rule_id:<16} {cite}"
                f"   [{finding.use_case_id}, {finding.confidence} confidence]"
            )
            out += _wrapped("", finding.reasoning)
            out += _criteria_block(finding)
            if rule is not None:
                out += _condition(rule) + _timing(rule)
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
    # WHAT THE COUNT ABOVE LEAVES OUT. `total_applicable` counts verdicts, and half this ruleset
    # produces none: a process obligation never reaches the judge, so it is listed above and
    # counted nowhere. For a general-purpose AI model that is EVERY obligation it owes, and the
    # footer then reads "0 applicable — 0 pass, 0 gap" under a column of fourteen duties, which is
    # the exact shape of a clean bill of health. Naming the outstanding count is what stops the
    # last line of the report contradicting the body of it.
    unjudged = sum(len(ids) for ids in report.not_document_verifiable.values())
    if unjudged:
        out.append(
            f"{unjudged} further obligation{'s' if unjudged > 1 else ''} listed above that "
            f"nobody judged — a technical file cannot evidence them, so each is a separate "
            f"confirmation and none of them is a pass"
        )

    # WHICH verdicts rested on non-binding interpretation. A finding reached with the Commission's
    # reading in front of the judge is weaker than one resting on the Article alone, and the report
    # computes the rollup precisely so a reader can weigh it.
    if report.rests_on_guidance:
        out += ["", "some verdicts above rest on non-binding Commission guidance:"]
        out += [
            f"  {g.issuer} {g.reference}, {g.locator}{f' — {g.topic}' if g.topic else ''}"
            for g in report.guidance_sources
        ]

    # Three paragraphs, wrapped one at a time: the second says the tool does not apply Annex I
    # product law, and the third is the OTHER place Art. 25 is explained — that silence about a
    # role change is not a finding that none happened. Collapsing them into one block buries both.
    for paragraph in report.disclaimer.split("\n\n"):
        out += ["", *_wrapped("", paragraph, indent="")]
    return "\n".join(out)
