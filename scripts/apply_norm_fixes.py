"""Apply one reviewed norm fix, rebuild artifacts, and prove its finding is gone."""

from __future__ import annotations

import argparse
import hashlib

from build_normative_coverage import paths_for_version

from aiact.norm_builder import build_artifacts, load_builder_inputs, run_builder
from aiact.norm_validity import (
    apply_recorded_fix,
    audit_norm_validity,
    enforce_validity_adjudications,
    load_adjudication_ledger,
    load_fix_patch,
)
from aiact.schemas.norm import NormativeCoverageBundle, NormInventory, TextReviewInventory


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


def apply_and_verify(version: str, finding_id: str) -> tuple[str, bool]:
    paths = paths_for_version(version)
    if paths.adjudications is None:
        raise ValueError("norm builder has no adjudication ledger")
    ledger = load_adjudication_ledger(paths.adjudications)
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
        for finding in audit_norm_validity(current_bundle)
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
    try:
        updated_bundle = _build_current_bundle(version)
        enforce_validity_adjudications(updated_bundle, paths.adjudications)
        run_builder(paths, check=False)
        run_builder(paths, check=True)
    except Exception:
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
