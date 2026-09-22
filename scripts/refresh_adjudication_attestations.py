"""Refresh deterministic audit attestations without changing any legal adjudication."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from build_normative_coverage import paths_for_version

from aiact.norm_builder import build_artifacts, load_builder_inputs
from aiact.norm_validity import (
    FieldValidation,
    ValidityAdjudicationLedger,
    audit_attestation,
    enforce_validity_adjudications,
    load_adjudication_ledger,
)
from aiact.schemas.norm import (
    NormativeCoverageBundle,
    NormInventory,
    SourceKind,
    TextReviewInventory,
)


def _bundle(version: str) -> NormativeCoverageBundle:
    paths = paths_for_version(version)
    reviewed, sources = load_builder_inputs(paths)
    text_payload, norm_payload = build_artifacts(reviewed, sources, paths)
    text_review = TextReviewInventory.model_validate(text_payload)
    norm_inventory = NormInventory.model_validate(norm_payload)
    documents = {(item.source.kind, item.source.document) for item in text_review.segments}
    return NormativeCoverageBundle(
        text_review=text_review,
        norm_inventory=norm_inventory,
        validated_documents=len(documents),
        validated_segments=len(text_review.segments),
        validated_norms=len(norm_inventory.norms),
    )


def _required_validations(
    ledger: ValidityAdjudicationLedger,
) -> dict[tuple[SourceKind, str], set[FieldValidation]]:
    return {
        (item.kind, item.document): set(item.required_field_validations)
        for item in ledger.enforced_scope
    }


def refresh(version: str) -> int:
    """Rewrite only audit snapshots, then prove every decision still matches the rebuilt audit.

    This is the reproducible response to a shared structural migration, such as changing a temporal
    regime. It cannot approve a new finding or hide a changed one: `enforce_validity_adjudications`
    runs before returning and restores every shard if any recorded decision is stale or missing.
    """
    paths = paths_for_version(version)
    if paths.adjudications is None:
        raise ValueError("norm builder has no adjudication ledger")
    ledger_path = paths.adjudications
    ledger = load_adjudication_ledger(ledger_path)
    bundle = _bundle(version)
    required = _required_validations(ledger)
    manifest_path = ledger_path / "index.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    snapshots: dict[Path, bytes] = {}
    try:
        for declared in manifest["shards"]:
            shard_path = ledger_path / declared["file"]
            snapshots[shard_path] = shard_path.read_bytes()
            shard = yaml.safe_load(snapshots[shard_path])
            kind = SourceKind(declared["kind"])
            document = str(declared["document"])
            shard["audit"] = audit_attestation(
                bundle,
                scope={(kind, document)},
                required_field_validations=required,
            ).model_dump(mode="json")
            shard_path.write_text(yaml.safe_dump(shard, sort_keys=False), encoding="utf-8")
        enforce_validity_adjudications(bundle, ledger_path)
    except Exception:
        for path, contents in snapshots.items():
            path.write_bytes(contents)
        raise
    return len(snapshots)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--act-version", required=True)
    args = parser.parse_args()
    try:
        count = refresh(args.act_version)
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"refreshed and verified {count} adjudication attestations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
