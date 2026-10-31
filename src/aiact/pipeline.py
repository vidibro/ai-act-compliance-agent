"""The whole review: one document in, one ComplianceReport out.

    classify  what is this system, per use case      — aiact.classify
    analyse   does its documentation satisfy the      — aiact.gap
              obligations that classification activates

The two layers are built to be independent and stay that way: neither imports the other, and this
module is the only place that knows both. It owns exactly one decision — whether the obligation
check should run at all — because that is a legal question rather than a property of either graph.
It also hands the gap layer the BRAIN, which that layer needs for its Art. 25 role question and
cannot build for itself without importing an implementation from the classification layer.

ONE DOCUMENT. Both layers read the same text. The classification cascade wants the intended
purpose and what the system does to a person; the judge wants the Annex IV technical content. A
document thin on either produces a report thin in the matching half, which is a quality-of-answer
problem and not an input-format one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from aiact.brain import Brain
from aiact.classify.graph import classify, load_questions
from aiact.gap import roles as role_questions
from aiact.gap.graph import DEFAULT_WORKERS, analyse
from aiact.gap.judge import Judge
from aiact.schemas.classification import ClassificationResult
from aiact.schemas.enums import ProhibitedPractice, RiskClass
from aiact.schemas.policy import PolicyRuleset
from aiact.schemas.question import Question
from aiact.schemas.report import ComplianceReport, ReportSummary
from aiact.scope_notes import section_b_note

_PROHIBITED_NOTE = (
    "No obligation check was run: the practice is prohibited under Art. 5. Chapter III sets out "
    "how a PERMITTED high-risk system must be built and documented, so checking documentation "
    "against it would imply the system may be placed on the market once the paperwork is fixed. "
    "It may not. Withdraw the practice."
)


def _national_law_note(spec: PolicyRuleset, practice: ProhibitedPractice | None) -> str:
    details = [
        notice.detail
        for notice in spec.national_law_notices
        if practice in notice.prohibited_practices
    ]
    if not details:
        return ""
    return (
        "National-law alignment required: this application does not identify or assess applicable "
        "national law. " + " ".join(details)
    )


def _use_only_note(spec: PolicyRuleset, classification: ClassificationResult) -> str:
    """Point (h) bans only the use, so the report has findings and the reader needs to know why a
    practice named in Art. 5 was checked against Chapter III rather than withdrawn."""
    national_law_note = _national_law_note(spec, classification.prohibited_practice)
    return (
        "Art. 5(1)(h) bans only the USE of real-time remote biometric identification in publicly "
        "accessible spaces for law enforcement, so this system is not prohibited and Chapter III "
        "was checked: its provider owes the high-risk requirements. A deployer may use it that way "
        "only where the use is strictly necessary for one of the named objectives and a Member "
        "State authorises it under Art. 5(5); without that national law the use is prohibited. The "
        "Article 5 conditions listed in this report apply to an authorised use. "
        f"{national_law_note}"
    ).strip()


def _prohibited_note(spec: PolicyRuleset, classification: ClassificationResult) -> str:
    """The Art. 5 note, plus the date the ban bites where that is not yet.

    Art. 5 applied from 2 February 2025 and for a long time that was true of every point in it, so
    "this is prohibited" carried its own timing. Regulation (EU) 2026/1744 inserted points (ba) and
    (bb) and gave them 2 December 2026. Telling an organisation to withdraw a practice that the
    Article does not yet reach is wrong in one direction; saying nothing about the date is wrong in
    the other, because the practice does become unlawful and building toward it is not a plan. So
    the verdict stands and the note says when.
    """
    practice = classification.prohibited_practice
    national_law_note = _national_law_note(spec, practice)
    if practice is None or practice.applies_from <= datetime.now(UTC).date():
        return " ".join(part for part in (_PROHIBITED_NOTE, national_law_note) if part)
    return (
        f"No obligation check was run: Art. 5(1)({practice.point}) prohibits this practice from "
        f"{practice.applies_from.isoformat()}. That date has NOT passed — the prohibition is "
        f"enacted and in force as law but does not yet apply, so the practice is not unlawful "
        f"under this Regulation today and will be on that date without any further step. Chapter "
        f"III is not checked against it: it sets out how a PERMITTED high-risk system must be "
        f"built, and no documentation makes a practice that is about to be banned shippable. "
        f"Treat this as a withdrawal deadline, not a gap to close. {national_law_note}"
    )


_OUT_OF_SCOPE_NOTE = (
    "No obligation check was run, and none is owed: Art. 2 withholds this Regulation from the "
    "system entirely. This is not a low risk tier — a minimal-risk system is still governed and "
    "owes Art. 4 AI literacy, with Art. 50 possibly attaching, whereas an excluded one owes "
    "nothing under this Regulation at all. Other law may well still apply; this tool reads only "
    "Regulation (EU) 2024/1689. Every Art. 2 exclusion is narrow, so the classification's stated "
    "reason should be checked against the facts of the deployment before it is relied on."
)
_NEEDS_REVIEW_NOTE = (
    "No obligation check was run: the classification is unresolved, so which obligations apply is "
    "not yet known. Checking against a guessed risk class would produce findings a provider could "
    "act on that may not be owed. Resolve the classification first."
)


_GPAI_NOTE = (
    "Chapter V obligations are listed, and NONE OF THEM IS JUDGED AGAINST THIS DOCUMENT. Two gates "
    "decide who owes what in Chapter V — whether the model carries SYSTEMIC RISK under Art. 51, "
    "which turns the whole of Art. 55 on, and whether it is released under a free and open-source "
    "licence with public weights, architecture and usage information, which turns Art. 53(1)(a) "
    "and (b) and the whole of Art. 54 off. Both are answered from this documentation and the "
    "answers are above; neither is used to withhold an obligation, because both are read from the "
    "same document a judge would read and a card that understates its compute or overstates its "
    "licence would otherwise clear four duties at once. So every obligation below is listed with "
    "the condition it depends on, for confirmation rather than as an assessment. The Art. 6 "
    "risk-tier requirements — Arts. 9 to 15 and the provider obligations from Art. 16 — are absent "
    "because Chapter V is a separate track, not because they were met."
)


def _empty_report(
    system_id: str,
    spec: PolicyRuleset,
    classification: ClassificationResult,
    scope_note: str,
) -> ComplianceReport:
    """A report that checked nothing, and says why in the report itself."""
    return ComplianceReport(
        system_id=system_id,
        act_version_date=spec.act_version_date,
        spec_version=spec.spec_version,
        generated_at=datetime.now(UTC),
        classification=classification,
        findings=[],
        not_document_verifiable={},
        summary=ReportSummary(total_applicable=0, passed=0, gaps=0, inadequate=0, needs_review=0),
        scope_note=scope_note,
    )


def review(
    document: str,
    spec: PolicyRuleset,
    brain: Brain,
    judge: Judge | None = None,
    system_id: str = "system",
    questions: dict[str, Question] | None = None,
    max_workers: int = DEFAULT_WORKERS,
    as_of_date: date | None = None,
) -> ComplianceReport:
    """Classify `document`, then check it against the obligations that classification activates.

    `questions` defaults to `load_questions()` — the law-anchored set. The context-free QUESTIONS
    exist for tests, and a real review should read the enacted text.
    """
    # Not wrapped in a trace_run of its own: both layers open one, and an outer scope would mint a
    # trace id the inner ones immediately replace — an empty parent with its children elsewhere.
    # They group by SESSION instead, which is why system_id is threaded into both.
    classification = classify(
        document,
        brain,
        use_case_id=system_id,
        questions=load_questions() if questions is None else questions,
    )

    # The only decision this module makes. Note what is NOT here: a high-risk gate. A
    # not_high_risk use case still owes Art. 6(4) — document the derogation assessment and
    # register it — and `select` already resolves that per risk class. Gating on high_risk
    # would silently drop a real obligation.
    overall = classification.overall_risk_class
    if overall == RiskClass.OUT_OF_SCOPE:
        return _empty_report(system_id, spec, classification, _OUT_OF_SCOPE_NOTE)
    # PROHIBITED DOES NOT SHORT-CIRCUIT, so the ban itself reaches the report as a duty: the rules
    # naming the practice are selected and nothing from Chapter III, since no Chapter III rule names
    # the prohibited tier. The reasoning in `_PROHIBITED_NOTE` holds — checking documentation
    # against Chapter III would imply the system ships once the paperwork is fixed.
    #
    # Point (h) never reaches this tier. It bans only the USE of real-time remote biometric
    # identification, so the cascade gives the system its ordinary tier, Chapter III is checked,
    # and the deployer's ban and the Art. 5(2) to (4) conditions arrive as rules beside it.
    prohibited = overall == RiskClass.PROHIBITED
    if overall == RiskClass.NEEDS_REVIEW:
        return _empty_report(system_id, spec, classification, _NEEDS_REVIEW_NOTE)

    # The same brain both layers use. The gap layer needs one for the Art. 25 role question and
    # cannot build its own without importing a classification brain — so this module, the only one
    # that knows both layers, hands it over.
    report = analyse(
        document,
        classification,
        spec,
        brain=brain,
        judge=judge,
        system_id=system_id,
        max_workers=max_workers,
        questions=role_questions.load_questions(),
        as_of_date=as_of_date or datetime.now(UTC).date(),
    )

    # Art. 2(2). `select` already withholds Chapter III from a Section B use case, so the findings
    # are correct — but silently correct. Without this the report shows high_risk beside an empty
    # findings list, which reads as a clean bill of health rather than a limit on what was checked.
    #
    # Tested on the same `high_risk_under_article_6_1` that governs `select`, so the note and the
    # findings can never disagree: this sentence tells a reader the Regulation exempts them, and it
    # is only true of a system Art. 6(1) itself classified.
    #
    # EVERY high-risk use case, not one of them. The note says Chapter III "was NOT checked", and
    # that is only true where nothing was: a system holding one Section B use case and one ordinary
    # Annex III use case has real findings, and this sentence would tell its reader to disregard
    # them.
    high_risk = [uc for uc in classification.use_cases if uc.risk_class == RiskClass.HIGH_RISK]
    withheld = [
        uc
        for uc in high_risk
        if uc.high_risk_under_article_6_1
        and uc.annex_i_product is not None
        and not uc.annex_i_product.chapter_iii_applies
    ]
    section_b = sorted({uc.annex_i_product.value for uc in withheld if uc.annex_i_product})
    if section_b and len(withheld) == len(high_risk):
        return report.model_copy(update={"scope_note": section_b_note(section_b)})

    # The Art. 5 verdict, carried through to a report whose findings list is empty because nothing
    # from Chapter III was selected for a practice banned outright.
    if prohibited:
        return report.model_copy(update={"scope_note": _prohibited_note(spec, classification)})
    # Point (h): the report has Chapter III findings AND the deployer's ban, and the reader needs
    # both halves at once — the system may ship, its use may not, unless national law authorises it.
    if classification.prohibited_practice is not None and (
        classification.prohibited_practice.bans_only_use
    ):
        return report.model_copy(update={"scope_note": _use_only_note(spec, classification)})

    # A model's obligations are listed and none is judged, so its findings list is empty for a
    # reason that has nothing to do with the documentation. Said here, because an empty findings
    # list beside a column of obligations reads as a clean bill of health for the provider who owes
    # them today — Chapter V has applied since 2 August 2025.
    if overall == RiskClass.GPAI_MODEL:
        return report.model_copy(update={"scope_note": _GPAI_NOTE})
    return report
