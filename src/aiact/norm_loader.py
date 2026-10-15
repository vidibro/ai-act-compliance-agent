"""Load and cross-validate normative-coverage assurance artifacts.

This module is intentionally separate from the runtime pipeline. It validates assurance data
against the pinned corpus without changing classification or reports.
"""

from __future__ import annotations

from pathlib import Path

from aiact.config import get_settings
from aiact.guidance import load_snippet
from aiact.schemas.norm import (
    ImplementationMode,
    NormativeCoverageBundle,
    NormInventory,
    NormRelationKind,
    TextReviewInventory,
)
from aiact.text_segments import (
    corpus_documents,
    group_segments,
    load_source_body,
    validate_document_partition,
)
from aiact.yaml_loader import load_yaml_mapping_or_shards


def _assert_no_carried_cycles(inventory: NormInventory) -> None:
    edges = {
        norm.norm_id: inventory.target_norm_ids_for(norm.norm_id, NormRelationKind.CARRIED_BY_NORMS)
        for norm in inventory.norms
        if norm.implementation_mode is ImplementationMode.CARRIED_BY_OTHER_NORM
    }

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            cycle = " -> ".join((*path[path.index(node) :], node))
            raise ValueError(f"carried_by_other_norm cycle: {cycle}")
        for target in edges.get(node, []):
            visit(target, (*path, node))

    for norm_id in edges:
        visit(norm_id, ())


def load_normative_coverage(
    text_review_path: str | Path | None = None,
    norm_inventory_path: str | Path | None = None,
    articles_root: str | Path | None = None,
    annexes_root: str | Path | None = None,
    guidance_root: str | Path | None = None,
) -> NormativeCoverageBundle:
    """Load both artifacts and prove their source and cross-file invariants."""
    settings = get_settings()
    coverage_root = (
        Path(settings.policy_normative_coverage_path) / settings.act_version_date.isoformat()
    )
    text_path = (
        Path(text_review_path) if text_review_path is not None else coverage_root / "text-review"
    )
    norm_path = (
        Path(norm_inventory_path) if norm_inventory_path is not None else coverage_root / "norms"
    )
    article_root = Path(articles_root or settings.policy_articles_path)
    annex_root = Path(annexes_root or settings.policy_annexes_path)

    text_review = TextReviewInventory.model_validate(
        load_yaml_mapping_or_shards(text_path, description="normative coverage artifact")
    )
    norm_inventory = NormInventory.model_validate(
        load_yaml_mapping_or_shards(norm_path, description="normative coverage artifact")
    )
    if text_review.act_version_date != norm_inventory.act_version_date:
        raise ValueError(
            "text-review and norm inventories use different Act versions: "
            f"{text_review.act_version_date} != {norm_inventory.act_version_date}"
        )

    version = text_review.act_version_date
    for segment in text_review.segments:
        if segment.source.act_version_date != version:
            raise ValueError(
                f"{segment.segment_id} uses Act version {segment.source.act_version_date}, "
                f"inventory uses {version}"
            )
    for norm in norm_inventory.norms:
        if norm.act_version_date != version:
            raise ValueError(
                f"{norm.norm_id} uses Act version {norm.act_version_date}, inventory uses {version}"
            )

    grouped = group_segments(text_review.segments)
    for (kind, document), segments in grouped.items():
        source = segments[0].source
        body = load_source_body(source, article_root, annex_root)
        validate_document_partition(segments, body, f"{kind.value} {document}")

    if text_review.corpus_complete:
        expected = corpus_documents(version, article_root, annex_root)
        present = set(grouped)
        if present != expected:
            missing = sorted(f"{kind.value} {doc}" for kind, doc in expected - present)
            extra = sorted(f"{kind.value} {doc}" for kind, doc in present - expected)
            raise ValueError(
                f"corpus_complete inventory disagrees with source store; "
                f"missing={missing[:20]}, extra={extra[:20]}"
            )

    segments_by_id = {segment.segment_id: segment for segment in text_review.segments}
    norms_by_id = {norm.norm_id: norm for norm in norm_inventory.norms}

    for relation in norm_inventory.relations:
        unknown_spans = [span for span in relation.legal_basis_spans if span not in segments_by_id]
        if unknown_spans:
            raise ValueError(
                f"{relation.relation_id} references unknown legal-basis span(s): {unknown_spans}"
            )
        non_normative_spans = [
            span
            for span in relation.legal_basis_spans
            if segments_by_id[span].disposition.value != "normative"
        ]
        if non_normative_spans:
            raise ValueError(
                f"{relation.relation_id} legal-basis span(s) are not normative: "
                f"{non_normative_spans}"
            )
        unknown_targets = [
            target for target in relation.target_norm_ids if target not in norms_by_id
        ]
        if unknown_targets:
            raise ValueError(
                f"{relation.relation_id} references unknown target norm(s): {unknown_targets}"
            )
        if relation.kind is NormRelationKind.CONDITIONAL_ON_NORMS:
            if relation.source_norm_id in relation.target_norm_ids:
                raise ValueError(f"{relation.relation_id} makes a norm its own condition")

    for regime in norm_inventory.temporal_regimes:
        unknown_spans = [span for span in regime.legal_basis_spans if span not in segments_by_id]
        if unknown_spans:
            raise ValueError(
                f"{regime.regime_id} references unknown legal-basis span(s): {unknown_spans}"
            )
        non_normative_spans = [
            span
            for span in regime.legal_basis_spans
            if segments_by_id[span].disposition.value != "normative"
        ]
        if non_normative_spans:
            raise ValueError(
                f"{regime.regime_id} legal-basis span(s) are not normative: {non_normative_spans}"
            )

    primary_links: dict[str, set[str]] = {segment_id: set() for segment_id in segments_by_id}
    qualifying_links: dict[str, set[str]] = {segment_id: set() for segment_id in segments_by_id}
    for norm in norm_inventory.norms:
        unknown = [span for span in norm.all_spans if span not in segments_by_id]
        if unknown:
            raise ValueError(f"{norm.norm_id} references unknown segment(s): {unknown}")
        for span in norm.primary_spans:
            primary_links[span].add(norm.norm_id)
        for span in [
            *norm.qualifier_spans,
            *norm.definition_spans,
        ]:
            qualifying_links[span].add(norm.norm_id)
        for span in (
            segment for actor in norm.assigned_actors for segment in actor.basis_segment_ids
        ):
            if span not in norm.primary_spans:
                qualifying_links[span].add(norm.norm_id)
        for span in (segment for target in norm.targets for segment in target.basis_segment_ids):
            if span not in norm.primary_spans:
                qualifying_links[span].add(norm.norm_id)
        nonmatching_primary_spans = [
            span for span in norm.primary_spans if norm.norm_text not in segments_by_id[span].text
        ]
        if nonmatching_primary_spans:
            raise ValueError(
                f"{norm.norm_id} norm_text is not an exact substring of primary span(s): "
                f"{nonmatching_primary_spans}"
            )
    for segment in text_review.segments:
        declared_primary = set(segment.norm_ids)
        actual_primary = primary_links[segment.segment_id]
        if declared_primary != actual_primary:
            raise ValueError(
                f"{segment.segment_id} primary norm links disagree: segment declares "
                f"{sorted(declared_primary)}, norms link {sorted(actual_primary)}"
            )
        declared_qualifying = set(segment.qualifying_norm_ids)
        actual_qualifying = qualifying_links[segment.segment_id]
        if declared_qualifying != actual_qualifying:
            raise ValueError(
                f"{segment.segment_id} qualifying norm links disagree: segment declares "
                f"{sorted(declared_qualifying)}, norms link {sorted(actual_qualifying)}"
            )

    seen_parallel: set[str] = set()
    for relation in norm_inventory.relations:
        if relation.kind is not NormRelationKind.PARALLEL_NORMS:
            continue
        members = [relation.source_norm_id, *relation.target_norm_ids]
        if len(members) < 2 or len(members) != len(set(members)):
            raise ValueError(f"{relation.relation_id} must name distinct parallel norms")
        overlap = set(members) & seen_parallel
        if overlap:
            raise ValueError(f"parallel norm relation overlap: {sorted(overlap)}")
        seen_parallel.update(members)

    _assert_no_carried_cycles(norm_inventory)

    for link in norm_inventory.interpretations:
        unknown = [norm_id for norm_id in link.norm_ids if norm_id not in norms_by_id]
        if unknown:
            raise ValueError(f"{link.interpretation_id} references unknown norm(s): {unknown}")
        for ref in link.snippet_refs:
            load_snippet(ref, guidance_root)

    return NormativeCoverageBundle(
        text_review=text_review,
        norm_inventory=norm_inventory,
        validated_documents=len(grouped),
        validated_segments=len(text_review.segments),
        validated_norms=len(norm_inventory.norms),
    )
