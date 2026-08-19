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

from datetime import UTC, datetime

from aiact.brain import Brain
from aiact.classify.graph import classify, load_questions
from aiact.gap import roles as role_questions
from aiact.gap.graph import DEFAULT_WORKERS, analyse
from aiact.gap.judge import LLMJudge
from aiact.schemas.classification import ClassificationResult
from aiact.schemas.enums import RiskClass
from aiact.schemas.policy import PolicySpec
from aiact.schemas.question import Question
from aiact.schemas.report import ComplianceReport, ReportSummary

_PROHIBITED_NOTE = (
    "No obligation check was run: the practice is prohibited under Art. 5. Chapter III sets out "
    "how a PERMITTED high-risk system must be built and documented, so checking documentation "
    "against it would imply the system may be placed on the market once the paperwork is fixed. "
    "It may not. Withdraw the practice."
)
_OUT_OF_SCOPE_NOTE = (
    "No obligation check was run, and none is owed: Art. 2 withholds this Regulation from the "
    "system entirely. This is not a low risk tier — a minimal-risk system is still governed and "
    "owes Art. 4 AI literacy, with Art. 50 possibly attaching, whereas an excluded one owes "
    "nothing under this Regulation at all. Other law may well still apply; this tool reads only "
    "Regulation (EU) 2024/1689. Every Art. 2 exclusion is narrow, so check the classification's "
    "stated reason against your own facts before relying on it."
)
_NEEDS_REVIEW_NOTE = (
    "No obligation check was run: the classification is unresolved, so which obligations apply is "
    "not yet known. Checking against a guessed risk class would produce findings a provider could "
    "act on that may not be owed. Resolve the classification first."
)


def _section_b_note(products: list[str]) -> str:
    """A Section B system is high-risk and owes no Chapter III. Both halves have to be said, or the
    empty findings list reads as a clean bill of health rather than a scope limit."""
    return (
        f"High-risk under Art. 6(1), but Chapter III was NOT checked: this system is a safety "
        f"component of a product covered by Annex I Section B ({', '.join(products)}). Under "
        f"Art. 2(2) only Art. 6(1), Arts. 102-109 and Art. 112 of this Regulation apply to such a "
        f"system — the requirements of Art. 9-15 and the provider obligations of Art. 16 onward do "
        f"not. Its safety duties come from that sectoral legislation instead, which is outside "
        f"this tool's scope."
    )


_GPAI_NOTE = (
    "No obligation check was run: this ruleset models the Art. 6 risk-tier track, and a "
    "general-purpose AI model is governed by Chapter V instead. An empty findings list here means "
    "NOT ASSESSED, not compliant — see docs/ROADMAP.md (M4d-8) for the Chapter V ruleset."
)


def _empty_report(
    system_id: str,
    spec: PolicySpec,
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
        summary=ReportSummary(
            total_applicable=0, passed=0, gaps=0, inadequate=0, needs_review=0
        ),
        scope_note=scope_note,
    )


def review(
    document: str,
    spec: PolicySpec,
    brain: Brain,
    judge: LLMJudge | None = None,
    system_id: str = "system",
    questions: dict[str, Question] | None = None,
    max_workers: int = DEFAULT_WORKERS,
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
    if overall == RiskClass.PROHIBITED:
        return _empty_report(system_id, spec, classification, _PROHIBITED_NOTE)
    if overall == RiskClass.NEEDS_REVIEW:
        return _empty_report(system_id, spec, classification, _NEEDS_REVIEW_NOTE)
    # A general-purpose AI model is not on the Art. 6 track at all, so there is nothing here to
    # check it against — but unlike out_of_scope it is NOT unburdened, and the note has to say so
    # or an empty findings list reads as a clean bill of health for a provider who owes Art. 53
    # today. The classification's own reasoning carries the full handover.
    if overall == RiskClass.GPAI_MODEL:
        return _empty_report(
            system_id, spec, classification, classification.reasoning + " " + _GPAI_NOTE
        )

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
    )

    # Art. 2(2). `select` already withholds Chapter III from a Section B use case, so the findings
    # are correct — but silently correct. Without this the report shows high_risk beside an empty
    # findings list, which reads as a clean bill of health rather than a limit on what was checked.
    section_b = sorted(
        {
            uc.annex_i_product.value
            for uc in classification.use_cases
            if uc.annex_i_product is not None and not uc.annex_i_product.chapter_iii_applies
        }
    )
    if section_b:
        return report.model_copy(update={"scope_note": _section_b_note(section_b)})
    return report
