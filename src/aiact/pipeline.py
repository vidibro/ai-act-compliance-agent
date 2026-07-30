"""The whole review: one document in, one ComplianceReport out.

    classify  what is this system, per use case      — aiact.classify
    analyse   does its documentation satisfy the      — aiact.gap
              obligations that classification activates

The two layers are built to be independent and stay that way: neither imports the other, and this
module is the only place that knows both. It owns exactly one decision — whether the obligation
check should run at all — because that is a legal question rather than a property of either graph.

ONE DOCUMENT. Both layers read the same text. The classification cascade wants the intended
purpose and what the system does to a person; the judge wants the Annex IV technical content. A
document thin on either produces a report thin in the matching half, which is a quality-of-answer
problem and not an input-format one.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiact.classify.brain import ClassificationBrain
from aiact.classify.graph import classify, load_questions
from aiact.gap.graph import DEFAULT_WORKERS, analyse
from aiact.gap.judge import LLMJudge
from aiact.schemas.classification import ClassificationQuestion, ClassificationResult
from aiact.schemas.enums import ActorRole, RiskClass
from aiact.schemas.policy import PolicySpec
from aiact.schemas.report import ComplianceReport, ReportSummary

_PROHIBITED_NOTE = (
    "No obligation check was run: the practice is prohibited under Art. 5. Chapter III sets out "
    "how a PERMITTED high-risk system must be built and documented, so checking documentation "
    "against it would imply the system may be placed on the market once the paperwork is fixed. "
    "It may not. Withdraw the practice."
)
_NEEDS_REVIEW_NOTE = (
    "No obligation check was run: the classification is unresolved, so which obligations apply is "
    "not yet known. Checking against a guessed risk class would produce findings a provider could "
    "act on that may not be owed. Resolve the classification first."
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
        not_document_verifiable=[],
        summary=ReportSummary(
            total_applicable=0, passed=0, gaps=0, inadequate=0, needs_review=0
        ),
        scope_note=scope_note,
    )


def review(
    document: str,
    spec: PolicySpec,
    brain: ClassificationBrain,
    judge: LLMJudge | None = None,
    system_id: str = "system",
    role: ActorRole = ActorRole.PROVIDER,
    questions: dict[str, ClassificationQuestion] | None = None,
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
    if overall == RiskClass.PROHIBITED:
        return _empty_report(system_id, spec, classification, _PROHIBITED_NOTE)
    if overall == RiskClass.NEEDS_REVIEW:
        return _empty_report(system_id, spec, classification, _NEEDS_REVIEW_NOTE)

    return analyse(
        document,
        classification,
        spec,
        judge=judge,
        system_id=system_id,
        role=role,
        max_workers=max_workers,
    )
