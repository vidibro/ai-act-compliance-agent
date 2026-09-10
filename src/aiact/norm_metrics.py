"""Measurements for an exact normative-coverage inventory."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from pydantic import BaseModel

from aiact.schemas.norm import (
    CandidateDetectionChannel,
    ImplementationMode,
    NormativeCoverageBundle,
    ProductScope,
)
from aiact.schemas.review import ReviewStatus


class MappingShape(BaseModel):
    one_norm_to_one_target: int
    many_norms_to_one_target: int
    one_norm_to_many_targets: int
    many_to_many: int
    unmapped: int


class CoverageMetrics(BaseModel):
    act_version_date: date
    documents: int
    documents_with_extracted_norms: int
    documents_with_review_debt: int
    segments: int
    norms: int
    exact_source_characters: int
    fully_displayed_characters: int
    approved_characters: int
    needs_review_characters: int
    normative_segments_with_multiple_norms: int
    norms_by_document: dict[str, int]
    norms_by_provision: dict[str, int]
    norm_kinds: dict[str, int]
    product_scopes: dict[str, int]
    implementation_modes: dict[str, int]
    review_statuses: dict[str, int]
    detection_channels: dict[str, int]
    semantic_norms_without_shall_token: list[str]
    shall_vs_semantic_disagreements: int
    shall_token_candidate_recall: float
    semantic_norms_without_existing_implementation: list[str]
    semantic_vs_existing_implementation_disagreements: int
    mapping_shape: MappingShape
    implementation_debt_norm_ids: list[str]
    timed_review_records: int
    total_review_records: int
    measured_review_seconds: float
    interpretive_links: int


def _mapping_shape(bundle: NormativeCoverageBundle) -> MappingShape:
    target_to_norms: dict[str, set[str]] = defaultdict(set)
    for norm in bundle.norm_inventory.norms:
        for target in norm.implementation_refs:
            target_to_norms[target].add(norm.norm_id)

    one_one = many_one = one_many = many_many = unmapped = 0
    for norm in bundle.norm_inventory.norms:
        targets = norm.implementation_refs
        if not targets:
            unmapped += 1
            continue
        shared = any(len(target_to_norms[target]) > 1 for target in targets)
        if len(targets) == 1 and not shared:
            one_one += 1
        elif len(targets) == 1:
            many_one += 1
        elif shared:
            many_many += 1
        else:
            one_many += 1
    return MappingShape(
        one_norm_to_one_target=one_one,
        many_norms_to_one_target=many_one,
        one_norm_to_many_targets=one_many,
        many_to_many=many_many,
        unmapped=unmapped,
    )


def measure_normative_coverage(bundle: NormativeCoverageBundle) -> CoverageMetrics:
    """Measure distinct assurance dimensions; do not collapse them into one percentage."""
    segments = bundle.text_review.segments
    norms = bundle.norm_inventory.norms
    segments_by_id = {segment.segment_id: segment for segment in segments}
    document_review_statuses: dict[tuple[str, str], list[ReviewStatus]] = defaultdict(list)
    for segment in segments:
        source = segment.source
        document_review_statuses[(source.kind.value, source.document)].append(segment.review.status)

    norm_documents: Counter[str] = Counter()
    norm_provisions: Counter[str] = Counter()
    for norm in norms:
        source = segments_by_id[norm.primary_spans[0]].source
        norm_documents[f"{source.kind.value} {source.document}"] += 1
        norm_provisions[norm.primary_spans[0]] += 1

    without_shall = sorted(
        norm.norm_id
        for norm in norms
        if CandidateDetectionChannel.SHALL_TOKEN not in norm.detection_channels
    )
    shall_count = len(norms) - len(without_shall)
    without_implementation = sorted(
        norm.norm_id
        for norm in norms
        if norm.product_scope is ProductScope.IN_SCOPE
        and CandidateDetectionChannel.EXISTING_IMPLEMENTATION not in norm.detection_channels
    )

    reviews = [
        *(segment.review for segment in segments),
        *(norm.review for norm in norms),
        *(link.review for link in bundle.norm_inventory.interpretations),
    ]
    timed = [record.elapsed_seconds for record in reviews if record.elapsed_seconds is not None]

    debt_modes = {ImplementationMode.MISSING, ImplementationMode.UNRESOLVED}
    return CoverageMetrics(
        act_version_date=bundle.text_review.act_version_date,
        documents=bundle.validated_documents,
        documents_with_extracted_norms=len(norm_documents),
        documents_with_review_debt=sum(
            ReviewStatus.NEEDS_REVIEW in statuses
            for statuses in document_review_statuses.values()
        ),
        segments=bundle.validated_segments,
        norms=bundle.validated_norms,
        exact_source_characters=sum(len(segment.text) for segment in segments),
        fully_displayed_characters=sum(
            len(segment.text) for segment in segments if segment.review.fully_displayed
        ),
        approved_characters=sum(
            len(segment.text)
            for segment in segments
            if segment.review.status is ReviewStatus.APPROVED
        ),
        needs_review_characters=sum(
            len(segment.text)
            for segment in segments
            if segment.review.status is ReviewStatus.NEEDS_REVIEW
        ),
        normative_segments_with_multiple_norms=sum(
            len(segment.norm_ids) > 1 for segment in segments
        ),
        norms_by_document=dict(sorted(norm_documents.items())),
        norms_by_provision=dict(sorted(norm_provisions.items())),
        norm_kinds=dict(sorted(Counter(norm.kind.value for norm in norms).items())),
        product_scopes=dict(sorted(Counter(norm.product_scope.value for norm in norms).items())),
        implementation_modes=dict(
            sorted(Counter(norm.implementation_mode.value for norm in norms).items())
        ),
        review_statuses=dict(
            sorted(
                Counter(
                    [
                        *(segment.review.status.value for segment in segments),
                        *(norm.review.status.value for norm in norms),
                    ]
                ).items()
            )
        ),
        detection_channels=dict(
            sorted(
                Counter(
                    channel.value for norm in norms for channel in norm.detection_channels
                ).items()
            )
        ),
        semantic_norms_without_shall_token=without_shall,
        shall_vs_semantic_disagreements=len(without_shall),
        shall_token_candidate_recall=shall_count / len(norms) if norms else 1.0,
        semantic_norms_without_existing_implementation=without_implementation,
        semantic_vs_existing_implementation_disagreements=len(without_implementation),
        mapping_shape=_mapping_shape(bundle),
        implementation_debt_norm_ids=sorted(
            norm.norm_id for norm in norms if norm.implementation_mode in debt_modes
        ),
        timed_review_records=len(timed),
        total_review_records=len(reviews),
        measured_review_seconds=sum(timed),
        interpretive_links=len(bundle.norm_inventory.interpretations),
    )


def render_coverage_markdown(metrics: CoverageMetrics) -> str:
    """Render a reproducible report beside the migration plan."""
    norms_by_document = "\n".join(
        f"- {document}: {count}" for document, count in metrics.norms_by_document.items()
    )
    norms_by_provision = "\n".join(
        f"- {provision}: {count}" for provision, count in metrics.norms_by_provision.items()
    )
    multi_norm_segments = metrics.normative_segments_with_multiple_norms
    timed_reviews = f"{metrics.timed_review_records}/{metrics.total_review_records}"
    mapping = metrics.mapping_shape
    implementation_disagreements = metrics.semantic_vs_existing_implementation_disagreements
    inventory_summary = (
        f"{metrics.documents} complete source-body partitions, {metrics.segments} exact segments, "
        f"and {metrics.norms} proposed atomic norms"
    )
    mapping_summary = (
        f"one-to-one={mapping.one_norm_to_one_target}, "
        f"many-to-one={mapping.many_norms_to_one_target}, "
        f"one-to-many={mapping.one_norm_to_many_targets}, "
        f"many-to-many={mapping.many_to_many}, unmapped={mapping.unmapped}"
    )
    channel_counts = ", ".join(
        f"{channel}={count}" for channel, count in metrics.detection_channels.items()
    )
    if metrics.approved_characters:
        report_status = "proposed norm extraction; independently reviewed segments present"
        review_boundary = (
            f"Segment reviews covering {metrics.approved_characters} source characters are "
            "independently approved. Approval applies to source coverage and segment dispositions; "
            "it does not by itself approve linked norm records. Remaining records are proposed "
            "findings or explicit `needs_review` debt. This report therefore does not claim legal "
            "completeness for the corpus."
        )
    else:
        report_status = "proposed extraction; independent legal review not yet performed"
        review_boundary = (
            "No segment or norm is independently approved. Records are either proposed findings "
            "or explicit\n`needs_review` debt. Approval still requires a different reviewer "
            "identity "
            "and proof that the full\nexact slice was displayed. This report is therefore evidence "
            "about schema fitness and\n"
            "extraction-method failure modes, not a legal completeness claim."
        )
    return f"""# Normative Coverage Report

**Status:** {report_status}

**Act version:** {metrics.act_version_date.isoformat()}

The inventory contains {inventory_summary}. Every stored article and annex is present. Proposed
norms have been extracted from {metrics.documents_with_extracted_norms} documents; the remaining
work is retained explicitly rather than omitted. The inventory is not consumed by classification,
rule selection, judging, or reporting.

## Coverage measurements

{norms_by_document}

### Norms per extracted provision

{norms_by_provision}

- Exact source characters partitioned: {metrics.exact_source_characters}
- Documents containing explicit review debt: {metrics.documents_with_review_debt}
- Characters displayed by the extraction pass: {metrics.fully_displayed_characters}
- Independently approved characters: {metrics.approved_characters}
- Characters deliberately left as review debt: {metrics.needs_review_characters}
- Normative segments yielding multiple propositions: {multi_norm_segments}
- Semantic candidates a shall-token pass missed: {metrics.shall_vs_semantic_disagreements}
- Shall-token candidate recall: {metrics.shall_token_candidate_recall:.1%}
- In-scope semantic candidates absent from existing implementation: {implementation_disagreements}
- Detection-channel counts: {channel_counts}
- Mapping shapes, by norm: {mapping_summary}
- Implementation debt candidates: {len(metrics.implementation_debt_norm_ids)}
- Interpretive links to non-binding guidance: {metrics.interpretive_links}
- Review records with measured elapsed time: {timed_reviews}

## Findings

1. `shall` is not an adequate candidate detector. The exact norm quotes show permissions, powers,
   deeming rules, legal consequences, and operative content lists that semantic review found
   without that token.
2. Exact document partitioning prevents an extraction pass from claiming an article was reviewed
   when only a paragraph reached it. Unreviewed divisions remain visible as `needs_review`.
3. Paragraph offsets alone are too coarse for atomic review. `norm_text` now records an exact,
   loader-validated quotation inside a primary span, while conditions and qualifier spans preserve
   surrounding legal effect.
4. Commission guidance remains separate: the Article 50(2) interpretation links three
   integrity-checked snippets to the enacted norm and existing policy rule without treating the
   guidance as binding law.
5. Timing data cannot yet support a full-authoring estimate. Missing elapsed time is recorded
   explicitly and must be captured automatically by the review interface.

## Review boundary

{review_boundary}
"""
