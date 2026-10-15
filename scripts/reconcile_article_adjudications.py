"""Reconcile all recorded norm-validity decisions for one enacted article.

Unlike ``apply_norm_fixes.py``, this command treats an article as one unit: it applies every
recorded ``fixed`` patch for the article, rebuilds once, refreshes its audit attestation once,
then requires the complete strict build to pass.  Any failure restores the canonical source files
and the article shard before regenerating the derived artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml
from build_normative_coverage import paths_for_version

from aiact.norm_builder import build_artifacts, load_builder_inputs, run_builder
from aiact.norm_validity import (
    AdjudicationScope,
    FieldValidation,
    ValidityAdjudication,
    ValidityAdjudicationLedger,
    apply_recorded_fix,
    audit_attestation,
    audit_norm_validity,
    enforce_validity_adjudications,
    load_adjudication_ledger,
    load_fix_patch,
)
from aiact.schemas.norm import (
    NormativeCoverageBundle,
    NormInventory,
    SourceKind,
    TextReviewInventory,
)


@dataclass(frozen=True)
class ReconciliationResult:
    article: str
    fixed_decisions: int
    changed_patches: int


def _build_current_bundle(version: str) -> NormativeCoverageBundle:
    paths = paths_for_version(version)
    reviewed, sources = load_builder_inputs(paths)
    text_payload, norm_payload = build_artifacts(reviewed, sources, paths)
    text_review = TextReviewInventory.model_validate(text_payload)
    norm_inventory = NormInventory.model_validate(norm_payload)
    documents = {(segment.source.kind, segment.source.document) for segment in text_review.segments}
    return NormativeCoverageBundle(
        text_review=text_review,
        norm_inventory=norm_inventory,
        validated_documents=len(documents),
        validated_segments=len(text_review.segments),
        validated_norms=len(norm_inventory.norms),
    )


def _required_field_validations(
    ledger: ValidityAdjudicationLedger,
) -> dict[tuple[SourceKind, str], set[FieldValidation]]:
    return {
        (item.kind, item.document): set(item.required_field_validations)
        for item in ledger.enforced_scope
    }


def _article_scope(ledger: ValidityAdjudicationLedger, article: str) -> AdjudicationScope:
    scope = next(
        (
            item
            for item in ledger.enforced_scope
            if item.kind == SourceKind.ARTICLE and item.document == article
        ),
        None,
    )
    if scope is None:
        raise ValueError(f"article {article} is not in the enforced adjudication scope")
    return scope


def _decisions_for_scope(
    ledger: ValidityAdjudicationLedger, scope: AdjudicationScope
) -> list[ValidityAdjudication]:
    return [
        decision
        for decision in ledger.decisions
        if ledger.shard_scope_by_finding[decision.finding_id] == scope
    ]


def _shard_path(ledger_path: Path, scope: AdjudicationScope) -> Path:
    manifest = yaml.safe_load((ledger_path / "index.yaml").read_text(encoding="utf-8"))
    declared = next(
        (
            item
            for item in manifest["shards"]
            if item["kind"] == scope.kind.value and item["document"] == scope.document
        ),
        None,
    )
    if declared is None:
        raise ValueError(f"article {scope.document} has no declared adjudication shard")
    return ledger_path / declared["file"]


def _refresh_article_audit(
    *,
    ledger_path: Path,
    scope: AdjudicationScope,
    bundle: NormativeCoverageBundle,
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]],
) -> tuple[Path, bytes]:
    shard_path = _shard_path(ledger_path, scope)
    before = shard_path.read_bytes()
    shard = yaml.safe_load(before)
    shard["audit"] = audit_attestation(
        bundle,
        scope={(scope.kind, scope.document)},
        required_field_validations=required_field_validations,
    ).model_dump(mode="json")
    shard_path.write_text(yaml.safe_dump(shard, sort_keys=False), encoding="utf-8")
    return shard_path, before


def _preflight_fixed_decisions(
    *,
    ledger_path: Path,
    decisions: list[ValidityAdjudication],
    bundle: NormativeCoverageBundle,
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]],
) -> dict[Path, bytes]:
    """Prove each pending patch belongs to a currently active finding before any write."""
    current_findings = {
        finding.finding_id: finding
        for finding in audit_norm_validity(
            bundle, required_field_validations=required_field_validations
        )
    }
    originals: dict[Path, bytes] = {}
    target_counts: Counter[Path] = Counter()
    for decision in decisions:
        patch, _ = load_fix_patch(ledger_path, decision)
        target = ledger_path.parent / patch.target_file
        if not target.is_file():
            raise ValueError(f"validity fix target is missing: {target}")
        target_counts[target] += 1
        originals[target] = target.read_bytes()

        # A previously applied patch has already passed this identity check.  A pending one
        # must still describe the exact finding it was reviewed to resolve.
        if hashlib.sha256(originals[target]).hexdigest() == patch.after_sha256:
            continue
        finding = current_findings.get(decision.finding_id)
        if finding is None:
            raise ValueError(
                f"validity finding {decision.finding_id} is not active before "
                "article reconciliation"
            )
        compared = (
            (decision.target, finding.target),
            (decision.rule, finding.rule),
            (decision.source_ref, finding.source_ref),
            (decision.source_sha256, finding.source_sha256),
            (decision.target_sha256, finding.target_sha256),
        )
        if any(declared != actual for declared, actual in compared):
            raise ValueError(
                f"validity finding {decision.finding_id} no longer matches its recorded decision"
            )

    repeated = sorted(str(path) for path, count in target_counts.items() if count > 1)
    if repeated:
        raise ValueError(
            "article reconciliation cannot apply multiple exact-hash fix patches to the same "
            "authoring file; consolidate the fixes into one reviewed source change first: "
            + ", ".join(repeated)
        )
    return originals


def reconcile_article(version: str, article: str) -> ReconciliationResult:
    """Apply and verify every recorded fixed decision for one article atomically."""
    paths = paths_for_version(version)
    if paths.adjudications is None:
        raise ValueError("norm builder has no adjudication ledger")
    ledger = load_adjudication_ledger(paths.adjudications)
    scope = _article_scope(ledger, article)
    requirements = _required_field_validations(ledger)
    fixed = [
        decision for decision in _decisions_for_scope(ledger, scope) if decision.decision == "fixed"
    ]
    originals = _preflight_fixed_decisions(
        ledger_path=paths.adjudications,
        decisions=fixed,
        bundle=_build_current_bundle(version),
        required_field_validations=requirements,
    )

    original_shard: tuple[Path, bytes] | None = None
    changed_patches = 0
    try:
        for decision in fixed:
            _, changed = apply_recorded_fix(paths.adjudications, decision.finding_id)
            changed_patches += changed
        run_builder(paths, check=False)
        updated_bundle = _build_current_bundle(version)
        original_shard = _refresh_article_audit(
            ledger_path=paths.adjudications,
            scope=scope,
            bundle=updated_bundle,
            required_field_validations=requirements,
        )
        enforce_validity_adjudications(updated_bundle, paths.adjudications)
        run_builder(paths, check=True)
    except Exception:
        if original_shard is not None:
            original_shard[0].write_bytes(original_shard[1])
        for target, content in originals.items():
            target.write_bytes(content)
        run_builder(paths, check=False)
        raise
    return ReconciliationResult(article, len(fixed), changed_patches)


def check_article(version: str, article: str) -> None:
    """Prove the requested article is in the closed ledger and the whole build is current."""
    paths = paths_for_version(version)
    if paths.adjudications is None:
        raise ValueError("norm builder has no adjudication ledger")
    ledger = load_adjudication_ledger(paths.adjudications)
    _article_scope(ledger, article)
    enforce_validity_adjudications(_build_current_bundle(version), paths.adjudications)
    run_builder(paths, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--act-version", required=True)
    parser.add_argument("--article", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--apply-fixed", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            check_article(args.act_version, args.article)
            print(f"article {args.article}: reconciliation is current")
        else:
            result = reconcile_article(args.act_version, args.article)
            print(
                f"article {result.article}: reconciled {result.fixed_decisions} fixed decision(s); "
                f"{result.changed_patches} patch(es) changed"
            )
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
