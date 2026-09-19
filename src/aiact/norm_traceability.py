"""Deterministic norm-to-rule traceability for the adjudicated scope.

A norm-validity decision proves a norm's meaning can be reconstructed. This module proves the next
link: every compliance norm in the enforced scope is a criterion of each rule it names, every
criterion names a norm that names its rule back, and each criterion is materialised from that norm
unchanged. It reads the rule side from the loaded policy spec, so the check sees exactly what the
judge will be shown.

The scope is the validity ledger's `enforced_scope`, because a criterion is reconstructible only
from an adjudicated norm. A cross-reference norm may instead be discharged by a typed relation:
Article 16(a), for example, allocates the provider duty to the existing Section 2 rules, while
Article 16(c) is carried by Article 17's substantive norm.
"""

from __future__ import annotations

from pathlib import Path

from aiact.classify.graph import QUESTIONS
from aiact.norm_validity import (
    FieldValidation,
    audit_norm_validity,
    load_adjudication_ledger,
)
from aiact.policy_loader import criterion_from_norm, load_policy_spec, report_norm_from_norm
from aiact.schemas.enums import ActorCategory
from aiact.schemas.norm import (
    ImplementationMode,
    Norm,
    NormativeCoverageBundle,
    NormKind,
    NormRelationKind,
    ProductScope,
    SourceKind,
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
    if any(actor.category is ActorCategory.UNRESOLVED for actor in norm.actors):
        errors.append("an actor is unresolved")
    return errors


def _report_reconstruction_errors(
    norm: Norm, *, external_conditional_obligation: bool
) -> list[str]:
    """Structured fields a report-only legal statement needs."""
    errors = []
    if norm.review.status is not ReviewStatus.APPROVED:
        errors.append(f"review status is {norm.review.status.value}, not approved")
    if norm.implementation_mode is not ImplementationMode.REPORT_ONLY:
        errors.append(f"implementation_mode is {norm.implementation_mode.value}")
    if norm.product_scope is not ProductScope.IN_SCOPE:
        errors.append(f"product_scope is {norm.product_scope.value}")
    if (
        norm.kind
        not in {
            NormKind.PERMISSION,
            NormKind.LEGAL_CONSEQUENCE,
            NormKind.APPLICABILITY,
        }
        and not external_conditional_obligation
        and not any(actor.category is ActorCategory.PUBLIC_AUTHORITY for actor in norm.actors)
    ):
        errors.append(f"kind is {norm.kind.value}, not reportable")
    if norm.verification_mode is VerificationMode.UNRESOLVED:
        errors.append("verification_mode is unresolved")
    if any(actor.category is ActorCategory.UNRESOLVED for actor in norm.actors):
        errors.append("an actor is unresolved")
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
    # The audit is recomputed below against the SAME gates the ledger declares. Without them a
    # migrated article is re-audited ungated, and the rule -> norm direction then demands
    # decisions for finding ids the gated audit no longer produces.
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]] = {
        (item.kind, item.document): set(item.required_field_validations)
        for item in ledger.enforced_scope
    }
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    rules = {rule.rule_id: rule for rule in spec.rules}
    report_norms = {report_norm.norm_id: report_norm for report_norm in spec.report_norms}

    relation_targets_by_norm: dict[str, set[str]] = {}
    external_conditional_obligation_ids: set[str] = set()
    for relation in bundle.norm_inventory.relations:
        if relation.kind in {
            NormRelationKind.ALLOCATES_DUTY_TO_POLICY_RULES,
            NormRelationKind.CARRIED_BY_POLICY_RULES,
        }:
            relation_targets_by_norm.setdefault(relation.source_norm_id, set()).update(
                relation.target_rule_ids
            )
        if relation.kind is NormRelationKind.SUBJECT_TO_EXTERNAL_REQUIREMENTS:
            external_conditional_obligation_ids.add(relation.source_norm_id)

    def in_scope(norm: Norm) -> bool:
        source = segments[norm.primary_spans[0]].source
        return (source.kind, source.document) in scope

    errors: list[str] = []
    classification_question_ids = {
        f"AIA-CQ-{question_id.upper().replace('_', '-')}" for question_id in QUESTIONS
    }

    # Enforced scope means every live in-scope norm has a decided implementation path.  `missing`
    # and `unresolved` are authoring debt states, never valid runtime treatments.
    for norm in sorted(norms.values(), key=lambda item: item.norm_id):
        if not in_scope(norm) or norm.review.status is ReviewStatus.SUPERSEDED:
            continue
        if norm.implementation_mode in {
            ImplementationMode.MISSING,
            ImplementationMode.UNRESOLVED,
        }:
            errors.append(
                f"{norm.norm_id} is in enforced scope but implementation_mode is "
                f"{norm.implementation_mode.value}"
            )
        if norm.implementation_mode is ImplementationMode.APPLICABILITY_QUESTION:
            # `applicability_question` describes the implementation path, not the legal effect.
            # Article 5's classification questions determine whether prohibitions and a saving
            # clause apply; forcing them to `kind: applicability` would erase that distinction.
            if norm.verification_mode is not VerificationMode.ANSWERED_BY_CLASSIFICATION:
                errors.append(
                    f"{norm.norm_id} is an applicability_question but verification_mode is "
                    f"{norm.verification_mode.value}"
                )
            unknown_questions = sorted(set(norm.implementation_refs) - classification_question_ids)
            if unknown_questions:
                errors.append(
                    f"{norm.norm_id} names unknown classification question(s) {unknown_questions}"
                )

    # A permission or legal consequence has no pass/fail answer.  A norm may either materialise
    # directly as report-only, or be an exact duplicate carried by such a norm.  It can never use
    # a compliance rule: that would allow a reader-facing allowed/legal-effect route to disappear
    # into a pass/fail result.
    for norm in sorted(norms.values(), key=lambda item: item.norm_id):
        if not in_scope(norm) or norm.review.status is ReviewStatus.SUPERSEDED:
            continue
        if (
            norm.kind in {NormKind.PERMISSION, NormKind.LEGAL_CONSEQUENCE}
            and norm.product_scope is ProductScope.IN_SCOPE
            and norm.implementation_mode is not ImplementationMode.APPLICABILITY_QUESTION
            and norm.implementation_mode
            not in {ImplementationMode.REPORT_ONLY, ImplementationMode.CARRIED_BY_OTHER_NORM}
        ):
            errors.append(
                f"{norm.norm_id} is {norm.kind.value} in enforced scope but "
                f"implementation_mode is {norm.implementation_mode.value}; permissions and "
                "legal consequences must be report_only or carried_by_other_norm"
            )

    # Report-only legal statements are not criteria: they tell a reader what is allowed, what
    # relief applies, or when a rule is narrowed, never whether an obligation passed. They still
    # need an exact bidirectional activation link, or could silently disappear.
    for norm in sorted(norms.values(), key=lambda item: item.norm_id):
        if not in_scope(norm) or norm.review.status is ReviewStatus.SUPERSEDED:
            continue
        if norm.implementation_mode is not ImplementationMode.REPORT_ONLY:
            continue
        external_conditional_obligation = (
            norm.kind is NormKind.OBLIGATION
            and norm.verification_mode is VerificationMode.REPORTED_CONDITIONALLY
            and norm.norm_id in external_conditional_obligation_ids
        )
        if (
            norm.kind
            not in {
                NormKind.PERMISSION,
                NormKind.LEGAL_CONSEQUENCE,
                NormKind.APPLICABILITY,
            }
            and not external_conditional_obligation
            and not any(actor.category is ActorCategory.PUBLIC_AUTHORITY for actor in norm.actors)
        ):
            errors.append(
                f"{norm.norm_id} is report_only but has non-reportable kind {norm.kind.value}"
            )
            continue
        projection = report_norms.get(norm.norm_id)
        if projection is None:
            errors.append(f"{norm.norm_id} has no materialised report norm")
            continue
        if list(projection.activation_rule_ids) != list(norm.implementation_refs):
            errors.append(
                f"{norm.norm_id} report activation rules {projection.activation_rule_ids} differ "
                f"from canonical implementation_refs {norm.implementation_refs}"
            )
        for problem in _report_reconstruction_errors(
            norm, external_conditional_obligation=external_conditional_obligation
        ):
            errors.append(f"{norm.norm_id} cannot be materialised as a report norm: {problem}")

    direct_norms_by_rule: dict[str, list[Norm]] = {}
    for norm in norms.values():
        if not in_scope(norm) or norm.implementation_mode is not ImplementationMode.COMPLIANCE_RULE:
            continue
        relation_targets = relation_targets_by_norm.get(norm.norm_id, set())
        for rule_id in norm.implementation_refs:
            if rule_id not in relation_targets:
                direct_norms_by_rule.setdefault(rule_id, []).append(norm)

    carried_relations_by_source: dict[str, list] = {}
    for relation in bundle.norm_inventory.relations:
        if relation.kind is NormRelationKind.CARRIED_BY_NORMS:
            carried_relations_by_source.setdefault(relation.source_norm_id, []).append(relation)

    def resolved_rule_ids(norm_id: str, path: tuple[str, ...] = ()) -> set[str]:
        """Policy rules reached by a norm-carried duty, following its reviewed chain."""
        if norm_id in path:
            return set()
        target = norms[norm_id]
        if target.implementation_mode in {
            ImplementationMode.COMPLIANCE_RULE,
            ImplementationMode.REPORT_ONLY,
        }:
            return set(target.implementation_refs)
        relations = carried_relations_by_source.get(norm_id, [])
        if (
            target.implementation_mode is not ImplementationMode.CARRIED_BY_OTHER_NORM
            or len(relations) != 1
        ):
            return set()
        return set().union(
            *(resolved_rule_ids(child, (*path, norm_id)) for child in relations[0].target_norm_ids)
        )

    def report_only_carrier_ids(norm_id: str, path: tuple[str, ...] = ()) -> set[str]:
        """Canonical reader-facing norms reached by a carried permission/effect."""
        if norm_id in path:
            return set()
        target = norms[norm_id]
        if target.implementation_mode is ImplementationMode.REPORT_ONLY:
            return {norm_id}
        relations = carried_relations_by_source.get(norm_id, [])
        if (
            target.implementation_mode is not ImplementationMode.CARRIED_BY_OTHER_NORM
            or len(relations) != 1
        ):
            return set()
        return set().union(
            *(
                report_only_carrier_ids(child, (*path, norm_id))
                for child in relations[0].target_norm_ids
            )
        )

    # A carried permission or legal effect is valid only when its one canonical chain ends in a
    # materialised report-only norm.  This preserves one report entry while making disappearance
    # impossible.
    for norm in sorted(norms.values(), key=lambda item: item.norm_id):
        if (
            not in_scope(norm)
            or norm.review.status is ReviewStatus.SUPERSEDED
            or norm.kind not in {NormKind.PERMISSION, NormKind.LEGAL_CONSEQUENCE}
            or norm.implementation_mode is not ImplementationMode.CARRIED_BY_OTHER_NORM
        ):
            continue
        relations = carried_relations_by_source.get(norm.norm_id, [])
        if len(relations) != 1:
            errors.append(
                f"{norm.norm_id} carried permission/legal consequence requires exactly one "
                f"carried_by_norms relation, found {len(relations)}"
            )
        elif not report_only_carrier_ids(norm.norm_id):
            errors.append(
                f"{norm.norm_id} carried permission/legal consequence does not resolve to a "
                "report_only norm"
            )

    # Norm -> rule: every enforced compliance norm is either a criterion, a typed relation, or an
    # unambiguous one-to-one rule. The last form needs no criterion container to preserve identity.
    for norm in sorted(norms.values(), key=lambda item: item.norm_id):
        if not in_scope(norm) or norm.implementation_mode is not ImplementationMode.COMPLIANCE_RULE:
            continue
        if norm.review.status is ReviewStatus.SUPERSEDED:
            continue
        for rule_id in norm.implementation_refs:
            rule = rules.get(rule_id)
            if rule is None:
                errors.append(f"{norm.norm_id} names rule {rule_id}, which is not in the spec")
            elif rule_id in relation_targets_by_norm.get(norm.norm_id, set()):
                continue
            elif norm.norm_id in {criterion.norm_id for criterion in rule.criteria}:
                continue
            elif not rule.criteria and direct_norms_by_rule.get(rule_id) == [norm]:
                continue
            else:
                errors.append(f"{rule_id} omits criterion {norm.norm_id}, which names it")

    # A norm marked as carried by another norm is not an implementation gap we report twice.
    # It still needs one explicit, live path to a policy rule.  Without this check Article 16(c),
    # (d), (e), or (j) could lose its relation and silently disappear from the report.
    for norm in sorted(norms.values(), key=lambda item: item.norm_id):
        if (
            not in_scope(norm)
            or norm.implementation_mode is not ImplementationMode.CARRIED_BY_OTHER_NORM
            or norm.review.status is ReviewStatus.SUPERSEDED
        ):
            continue
        relations = carried_relations_by_source.get(norm.norm_id, [])
        if len(relations) != 1:
            errors.append(
                f"{norm.norm_id} carried_by_other_norm requires exactly one carried_by_norms "
                f"relation, found {len(relations)}"
            )
            continue
        relation = relations[0]
        for target_id in relation.target_norm_ids:
            reached = resolved_rule_ids(target_id)
            if not reached:
                errors.append(
                    f"{relation.relation_id} target {target_id} does not resolve to a policy rule"
                )
                continue
            for rule_id in sorted(reached):
                if rule_id not in rules:
                    errors.append(
                        f"{relation.relation_id} target {target_id} resolves to missing rule "
                        f"{rule_id}"
                    )

    # Rule -> norm: every criterion resolves to one reconstructible norm that names the rule back.
    decisions: dict[str, list[str]] = {}
    for decision in ledger.decisions:
        decisions.setdefault(decision.finding_id, []).append(decision.decision)
    findings_by_target: dict[str, list[str]] = {}
    for finding in audit_norm_validity(
        bundle, scope=scope, required_field_validations=required_field_validations
    ):
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
    # And the reverse direction: each materialised entry must still be the exact canonical norm.
    for report_norm in sorted(spec.report_norms, key=lambda item: item.norm_id):
        target = norms.get(report_norm.norm_id)
        if target is None:
            errors.append(f"report norm {report_norm.norm_id} names a missing canonical norm")
            continue
        if not in_scope(target):
            errors.append(
                f"report norm {report_norm.norm_id} cannot be reconstructed: its document is "
                "outside the adjudicated validity scope"
            )
            continue
        external_conditional_obligation = (
            target.kind is NormKind.OBLIGATION
            and target.verification_mode is VerificationMode.REPORTED_CONDITIONALLY
            and target.norm_id in external_conditional_obligation_ids
        )
        for problem in _report_reconstruction_errors(
            target, external_conditional_obligation=external_conditional_obligation
        ):
            errors.append(f"report norm {report_norm.norm_id} cannot be reconstructed: {problem}")
        if report_norm != report_norm_from_norm(target):
            errors.append(f"report norm {report_norm.norm_id} differs from its canonical norm")
    for relation in sorted(bundle.norm_inventory.relations, key=lambda item: item.relation_id):
        source = norms[relation.source_norm_id]
        if not in_scope(source):
            continue
        if relation.kind in {
            NormRelationKind.ALLOCATES_DUTY_TO_POLICY_RULES,
            NormRelationKind.CARRIED_BY_POLICY_RULES,
        }:
            for rule_id in relation.target_rule_ids:
                rule = rules.get(rule_id)
                if rule is None:
                    errors.append(
                        f"{relation.relation_id} names rule {rule_id}, which is not in the spec"
                    )
                    continue
                if source.norm_id in {criterion.norm_id for criterion in rule.criteria}:
                    errors.append(
                        f"{relation.relation_id} source {source.norm_id} is redundantly a "
                        "criterion "
                        f"of {rule_id}"
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
