"""Report deterministic, source-bound norm-validity findings without changing decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_normative_coverage import paths_for_version

from aiact.norm_builder import build_artifacts, load_builder_inputs
from aiact.norm_validity import audit_attestation, audit_norm_validity
from aiact.schemas.norm import (
    NormativeCoverageBundle,
    NormInventory,
    SourceKind,
    TextReviewInventory,
)


def audit(version: str, articles: set[str] | None = None) -> dict[str, object]:
    paths = paths_for_version(version)
    reviewed, sources = load_builder_inputs(paths)
    text_payload, norm_payload = build_artifacts(reviewed, sources, paths)
    text_review = TextReviewInventory.model_validate(text_payload)
    norm_inventory = NormInventory.model_validate(norm_payload)
    documents = {
        (segment.source.kind, segment.source.document) for segment in text_review.segments
    }
    bundle = NormativeCoverageBundle(
        text_review=text_review,
        norm_inventory=norm_inventory,
        validated_documents=len(documents),
        validated_segments=len(text_review.segments),
        validated_norms=len(norm_inventory.norms),
    )
    scope = (
        {(SourceKind.ARTICLE, article) for article in articles}
        if articles is not None
        else None
    )
    findings = audit_norm_validity(bundle, scope=scope)
    attestation = audit_attestation(bundle, scope=scope or documents)
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    norms_in_scope = [
        norm
        for norm in bundle.norm_inventory.norms
        if scope is None
        or (
            segments[norm.primary_spans[0]].source.kind,
            segments[norm.primary_spans[0]].source.document,
        )
        in scope
    ]
    segments_in_scope = [
        segment
        for segment in bundle.text_review.segments
        if scope is None or (segment.source.kind, segment.source.document) in scope
    ]

    return {
        "status": "deterministic_structural_audit_not_legal_approval",
        "act_version": version,
        "scope": sorted(articles) if articles is not None else "all",
        "segments_scanned": len(segments_in_scope),
        "norms_scanned": len(norms_in_scope),
        "finding_count": len(findings),
        "audit_attestation": attestation.model_dump(mode="json"),
        "findings": [finding.as_dict() for finding in findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--act-version", required=True)
    parser.add_argument(
        "--article",
        action="append",
        help="limit the audit to one article; repeat to select more than one",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(
        audit(args.act_version, set(args.article) if args.article else None),
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
