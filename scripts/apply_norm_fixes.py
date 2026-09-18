"""Apply one reviewed norm fix, rebuild artifacts, and prove its finding is gone."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml
from build_normative_coverage import paths_for_version

from aiact.norm_builder import build_artifacts, load_builder_inputs, run_builder
from aiact.norm_validity import (
    FieldValidation,
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


def _build_current_bundle(version: str) -> NormativeCoverageBundle:
    paths = paths_for_version(version)
    reviewed, sources = load_builder_inputs(paths)
    text_payload, norm_payload = build_artifacts(reviewed, sources, paths)
    text_review = TextReviewInventory.model_validate(text_payload)
    norm_inventory = NormInventory.model_validate(norm_payload)
    documents = {
        (segment.source.kind, segment.source.document) for segment in text_review.segments
    }
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
    """Use the ledger's gates for every audit this fix workflow performs."""
    return {
        (item.kind, item.document): set(item.required_field_validations)
        for item in ledger.enforced_scope
    }


def _refresh_decision_shard_audit(
    *,
    ledger_path: Path,
    ledger: ValidityAdjudicationLedger,
    finding_id: str,
    bundle: NormativeCoverageBundle,
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]],
) -> tuple[Path, bytes]:
    """Replace only the repaired document's attestation with its rebuilt deterministic snapshot."""
    scope = ledger.shard_scope_by_finding[finding_id]
    manifest_path = ledger_path / "index.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    declared = next(
        item
        for item in manifest["shards"]
        if item["kind"] == scope.kind.value and item["document"] == scope.document
    )
    shard_path = ledger_path / declared["file"]
    before = shard_path.read_bytes()
    shard = yaml.safe_load(before)
    shard["audit"] = audit_attestation(
        bundle,
        scope={(scope.kind, scope.document)},
        required_field_validations=required_field_validations,
    ).model_dump(mode="json")
    shard_path.write_text(yaml.safe_dump(shard, sort_keys=False), encoding="utf-8")
    return shard_path, before


def apply_and_verify(version: str, finding_id: str) -> tuple[str, bool]:
    paths = paths_for_version(version)
    if paths.adjudications is None:
        raise ValueError("norm builder has no adjudication ledger")
    ledger = load_adjudication_ledger(paths.adjudications)
    required_field_validations = _required_field_validations(ledger)
    decision = next(
        (item for item in ledger.decisions if item.finding_id == finding_id), None
    )
    if decision is None:
        raise ValueError(f"unknown validity finding: {finding_id}")
    if decision.decision != "fixed":
        raise ValueError(f"validity finding {finding_id} is not adjudicated as fixed")

    patch, _ = load_fix_patch(paths.adjudications, decision)
    target_path = paths.adjudications.parent / patch.target_file
    original = target_path.read_bytes() if target_path.is_file() else None

    current_bundle = _build_current_bundle(version)
    current = {
        finding.finding_id: finding
        for finding in audit_norm_validity(
            current_bundle,
            required_field_validations=required_field_validations,
        )
    }
    already_applied = (
        original is not None and hashlib.sha256(original).hexdigest() == patch.after_sha256
    )
    if not already_applied:
        finding = current.get(finding_id)
        if finding is None:
            raise ValueError(
                f"validity finding {finding_id} is not active before applying its patch"
            )
        compared = (
            (decision.target, finding.target),
            (decision.rule, finding.rule),
            (decision.source_ref, finding.source_ref),
            (decision.source_sha256, finding.source_sha256),
            (decision.target_sha256, finding.target_sha256),
        )
        if any(declared != actual for declared, actual in compared):
            raise ValueError(f"validity finding {finding_id} no longer matches its decision")

    target, changed = apply_recorded_fix(paths.adjudications, finding_id)
    original_shard: tuple[Path, bytes] | None = None
    try:
        updated_bundle = _build_current_bundle(version)
        original_shard = _refresh_decision_shard_audit(
            ledger_path=paths.adjudications,
            ledger=ledger,
            finding_id=finding_id,
            bundle=updated_bundle,
            required_field_validations=required_field_validations,
        )
        enforce_validity_adjudications(updated_bundle, paths.adjudications)
        run_builder(paths, check=False)
        run_builder(paths, check=True)
    except Exception:
        if original_shard is not None:
            original_shard[0].write_bytes(original_shard[1])
        if changed and original is not None:
            target.write_bytes(original)
            run_builder(paths, check=False)
        raise
    return str(target), changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--act-version", required=True)
    parser.add_argument("--finding-id", required=True)
    args = parser.parse_args()
    try:
        target, changed = apply_and_verify(args.act_version, args.finding_id)
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    state = "applied and verified" if changed else "already applied and verified"
    print(f"{args.finding_id}: {state}: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
