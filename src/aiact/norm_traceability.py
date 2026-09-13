"""Deterministic norm-to-rule traceability for the adjudicated scope.

A norm-validity decision proves a norm's meaning can be reconstructed. This module proves the next
link: every compliance norm in the enforced scope is a criterion of each rule it names, every
criterion names a norm that names its rule back, and each criterion is materialised from that norm
unchanged. It reads the rule side from the loaded policy spec, so the check sees exactly what the
judge will be shown.

The scope is the validity ledger's `enforced_scope`, because a criterion is reconstructible only
from an adjudicated norm. A norm outside it may still point at a rule — the Article 16(a) umbrella
duty names every Section 2 rule — and is not required to be one of that rule's criteria until its
document is adjudicated.
"""

from __future__ import annotations

from pathlib import Path

from aiact.norm_validity import audit_norm_validity, load_adjudication_ledger
from aiact.policy_loader import criterion_from_norm, load_policy_spec
from aiact.schemas.norm import (
    ImplementationMode,
    Norm,
    NormativeCoverageBundle,
    ProductScope,
    SourceKind,
    SubjectCategory,
    VerificationMode,
)
from aiact.schemas.policy import PolicyRuleset
from aiact.schemas.review import ReviewStatus

_ACCEPTED_DECISIONS = {"accepted_with_basis", "false_positive"}


def _reconstruction_errors(norm: Norm) -> list[str]:
    """Structured fields a criterion needs before its meaning can be materialised."""
    errors = []
    if norm.review.status is not ReviewStatus.APPROVED:
        errors.append(f"review status is {norm.review.status.value}, not approved")
    if norm.implementation_mode is not ImplementationMode.COMPLIANCE_RULE:
        errors.append(f"implementation_mode is {norm.implementation_mode.value}")
    if norm.product_scope is not ProductScope.IN_SCOPE:
        errors.append(f"product_scope is {norm.product_scope.value}")
    if norm.verification_mode is VerificationMode.UNRESOLVED:
        errors.append("verification_mode is unresolved")
    if any(subject.category is SubjectCategory.UNRESOLVED for subject in norm.subjects):
        errors.append("a subject is unresolved")
    return errors


def traceability_errors(
    bundle: NormativeCoverageBundle,
    spec: PolicyRuleset,
    ledger_path: Path,
) -> list[str]:
    """Every broken norm <-> rule link in the enforced scope, in deterministic order."""
    ledger = load_adjudication_ledger(ledger_path)
    scope: set[tuple[SourceKind, str]] = {
        (item.kind, item.document) for item in ledger.enforced_scope
    }
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    rules = {rule.rule_id: rule for rule in spec.rules}

    def in_scope(norm: Norm) -> bool:
        source = segments[norm.primary_spans[0]].source
        return (source.kind, source.document) in scope

    errors: list[str] = []

    # Norm -> rule: every enforced compliance norm is a criterion of every rule it names.
    for norm in sorted(norms.values(), key=lambda item: item.norm_id):
        if not in_scope(norm) or norm.implementation_mode is not ImplementationMode.COMPLIANCE_RULE:
            continue
        if norm.review.status is ReviewStatus.SUPERSEDED:
            continue
        for rule_id in norm.implementation_refs:
            rule = rules.get(rule_id)
            if rule is None:
                errors.append(f"{norm.norm_id} names rule {rule_id}, which is not in the spec")
            elif norm.norm_id not in {criterion.norm_id for criterion in rule.criteria}:
                errors.append(f"{rule_id} omits criterion {norm.norm_id}, which names it")

    # Rule -> norm: every criterion resolves to one reconstructible norm that names the rule back.
    decisions: dict[str, list[str]] = {}
    for decision in ledger.decisions:
        decisions.setdefault(decision.finding_id, []).append(decision.decision)
    findings_by_target: dict[str, list[str]] = {}
    for finding in audit_norm_validity(bundle, scope=scope):
        decided = decisions.get(finding.finding_id, [])
        if not decided or not set(decided) <= _ACCEPTED_DECISIONS:
            findings_by_target.setdefault(finding.target, []).append(finding.finding_id)
    for rule in sorted(spec.rules, key=lambda item: item.rule_id):
        ids = [criterion.norm_id for criterion in rule.criteria]
        for norm_id in sorted({norm_id for norm_id in ids if ids.count(norm_id) > 1}):
            errors.append(f"{rule.rule_id} lists criterion {norm_id} more than once")
        for criterion in rule.criteria:
            target = norms.get(criterion.norm_id)
            if target is None:
                errors.append(f"{rule.rule_id} names missing norm {criterion.norm_id}")
                continue
            if rule.rule_id not in target.implementation_refs:
                errors.append(
                    f"{rule.rule_id} names {target.norm_id}, which does not point back to it"
                )
            if not in_scope(target):
                errors.append(
                    f"{rule.rule_id} criterion {target.norm_id} cannot be reconstructed: its "
                    f"document is outside the adjudicated validity scope"
                )
                continue
            for problem in _reconstruction_errors(target):
                errors.append(
                    f"{rule.rule_id} criterion {target.norm_id} cannot be reconstructed: {problem}"
                )
            for finding_id in findings_by_target.get(target.norm_id, []):
                errors.append(
                    f"{rule.rule_id} criterion {target.norm_id} cannot be reconstructed: validity "
                    f"finding {finding_id} has no accepted decision"
                )
            if criterion != criterion_from_norm(target):
                errors.append(
                    f"{rule.rule_id} criterion {target.norm_id} differs from its canonical norm"
                )
    return errors


def enforce_norm_rule_traceability(
    bundle: NormativeCoverageBundle,
    ledger_path: Path,
    *,
    spec_path: Path,
    articles_root: Path,
    annexes_root: Path,
    guidance_root: Path,
    norms_root: Path,
) -> int:
    """Raise unless norm <-> rule links are complete and bidirectional; return criteria checked."""
    spec = load_policy_spec(
        spec_path,
        articles_root=articles_root,
        guidance_root=guidance_root,
        annexes_root=annexes_root,
        norms_root=norms_root,
    )
    errors = traceability_errors(bundle, spec, ledger_path)
    if errors:
        raise ValueError("norm-to-rule traceability failed:\n  " + "\n  ".join(errors))
    return sum(len(rule.criteria) for rule in spec.rules)
