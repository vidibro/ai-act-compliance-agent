"""Settle an aggregate rule from whatever its judge said about each criterion.

Code, not the judge, owns which criteria exist and what the rule verdict is. A judge may rule on
criteria; this module lines its answers up against the rule's declared list, turns any it skipped
into NEEDS_REVIEW, and computes the rule verdict with `aggregate_criteria`. So a judge that returns
a sibling's pass, or no criteria at all, cannot pass the rule.
"""

from __future__ import annotations

from collections.abc import Iterable

from aiact.schemas.enums import Verdict
from aiact.schemas.policy import PolicyRule
from aiact.schemas.question import Confidence, clip_reasoning
from aiact.schemas.report import CriterionFinding, aggregate_criteria

_CONFIDENCE_ORDER: dict[Confidence, int] = {"low": 0, "medium": 1, "high": 2}


def not_judged(rule: PolicyRule) -> list[CriterionFinding]:
    """Criteria the gap layer lists but never judges: permissions and duties reported unjudged."""
    return [
        CriterionFinding(
            norm_id=criterion.norm_id,
            mandatory=False,
            verdict=Verdict.NOT_APPLICABLE,
            reasoning=(
                f"{criterion.kind.value}, {criterion.verification_mode.value}: listed with "
                f"{rule.rule_id}, not judged and cannot fail it."
            ),
            confidence="high",
        )
        for criterion in rule.criteria
        if not criterion.mandatory
    ]


def settle_criteria(
    rule: PolicyRule,
    reported: Iterable[CriterionFinding],
    *,
    whole_rule: Verdict | None = None,
) -> list[CriterionFinding]:
    """One finding per declared criterion, in the rule's order.

    `whole_rule` is for a verdict reached without judging the criteria — NOT_APPLICABLE for a rule
    the documentation cannot evidence. Every mandatory criterion then carries it; nothing else can
    fill a criterion the judge did not rule on."""
    by_id: dict[str, CriterionFinding] = {}
    for item in reported:
        if item.norm_id in by_id:
            raise ValueError(f"{rule.rule_id}: criterion {item.norm_id} was judged twice.")
        by_id[item.norm_id] = item
    declared = {criterion.norm_id for criterion in rule.criteria}
    unknown = sorted(set(by_id) - declared)
    if unknown:
        raise ValueError(f"{rule.rule_id}: judge ruled on undeclared criteria {unknown}.")

    unjudged = {finding.norm_id: finding for finding in not_judged(rule)}
    settled: list[CriterionFinding] = []
    for criterion in rule.criteria:
        if not criterion.mandatory:
            settled.append(unjudged[criterion.norm_id])
            continue
        finding: CriterionFinding | None = by_id.get(criterion.norm_id)
        if whole_rule is not None:
            finding = CriterionFinding(
                norm_id=criterion.norm_id,
                mandatory=True,
                verdict=whole_rule,
                reasoning=f"{rule.rule_id} was not judged criterion by criterion.",
                confidence="high",
            )
        elif finding is None:
            finding = CriterionFinding(
                norm_id=criterion.norm_id,
                mandatory=True,
                verdict=Verdict.NEEDS_REVIEW,
                reasoning=f"The judge returned no verdict for {criterion.norm_id}.",
                confidence="low",
            )
        settled.append(finding.model_copy(update={"mandatory": True}))
    return settled


def aggregate_reasoning(rule: PolicyRule, criteria: list[CriterionFinding]) -> str:
    """Name every mandatory criterion that stops the rule passing, with its own reason."""
    mandatory = [c for c in criteria if c.mandatory]
    if not mandatory:
        return f"All {len(criteria)} criteria of {rule.rule_id} are reported, not document-judged."
    open_items = [c for c in mandatory if c.verdict is not Verdict.PASS]
    if not open_items:
        return clip_reasoning(f"All {len(mandatory)} mandatory criteria of {rule.rule_id} pass.")
    listed = "; ".join(f"{c.norm_id} ({c.verdict.value}): {c.reasoning}" for c in open_items)
    # Clipped: each criterion keeps its full reason in `Finding.criteria`, which the report prints.
    return clip_reasoning(
        f"{len(open_items)} of {len(mandatory)} mandatory criteria do not pass — {listed}"
    )


def aggregate_confidence(criteria: list[CriterionFinding]) -> Confidence:
    """The weakest mandatory criterion's confidence: a rule is no surer than its least sure part."""
    mandatory = [c.confidence for c in criteria if c.mandatory]
    return min(mandatory, key=_CONFIDENCE_ORDER.__getitem__) if mandatory else "high"


def settle(
    rule: PolicyRule, verdict: Verdict, reported: Iterable[CriterionFinding]
) -> tuple[Verdict, list[CriterionFinding]]:
    """The rule verdict and its criteria. A rule without criteria keeps the verdict it was given."""
    if not rule.criteria:
        return verdict, []
    if not any(criterion.mandatory for criterion in rule.criteria):
        # A non-document-verifiable aggregate still needs every norm listed in the report. It is
        # not a model verdict, so it must never become a pass merely because no criterion is
        # document-judged.
        return Verdict.NOT_APPLICABLE, not_judged(rule)
    whole = Verdict.NOT_APPLICABLE if verdict is Verdict.NOT_APPLICABLE else None
    criteria = settle_criteria(rule, reported, whole_rule=whole)
    return aggregate_criteria(criteria), criteria
