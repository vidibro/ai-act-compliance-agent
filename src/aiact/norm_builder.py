"""Compile reviewed, versioned legal findings into exact normative-coverage artifacts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from aiact.norm_loader import load_normative_coverage
from aiact.norm_metrics import measure_normative_coverage, render_coverage_markdown
from aiact.policy_loader import article_filename, source_body
from aiact.schemas.interpretation import InterpretationTargetKind, InterpretiveLink
from aiact.schemas.norm import (
    ConditionGroup,
    DependencyResolution,
    ImplementationMode,
    NormDependency,
    NormKind,
    ProductScope,
    SegmentDisposition,
    SourceKind,
    SubjectCategory,
    VerificationMode,
)
from aiact.text_segments import corpus_documents
from aiact.yaml_loader import load_yaml_mapping_or_shards

DEFAULT_REVIEW_DEBT_REASON = "Not yet semantically extracted; retained as explicit review debt."


class DivisionSource(BaseModel):
    label: str = Field(pattern=r"^[A-Z0-9-]+$")
    marker: str | None
    disposition: SegmentDisposition
    reason: str = ""
    verified_by: str = ""

    @model_validator(mode="after")
    def _review_metadata_matches_disposition(self) -> DivisionSource:
        if self.verified_by.strip() and self.disposition is SegmentDisposition.NEEDS_REVIEW:
            raise ValueError("review-debt division cannot have a verifier")
        if self.disposition is SegmentDisposition.CONTEXT_ONLY and not self.reason.strip():
            raise ValueError("context-only division requires a reason")
        return self


class ParagraphOverride(BaseModel):
    disposition: SegmentDisposition
    reason: str = ""
    verified_by: str = ""

    @model_validator(mode="after")
    def _review_metadata_matches_disposition(self) -> ParagraphOverride:
        if self.verified_by.strip() and self.disposition is SegmentDisposition.NEEDS_REVIEW:
            raise ValueError("review-debt paragraph cannot have a verifier")
        if self.disposition is SegmentDisposition.CONTEXT_ONLY and not self.reason.strip():
            raise ValueError("context-only paragraph requires a reason")
        return self


class DocumentSource(BaseModel):
    kind: SourceKind
    number: str = Field(min_length=1)
    segmentation: Literal["declared", "paragraphs"] = "declared"
    paragraph_disposition: SegmentDisposition = SegmentDisposition.NEEDS_REVIEW
    paragraph_reason: str = DEFAULT_REVIEW_DEBT_REASON
    paragraph_overrides: dict[str, ParagraphOverride] = Field(default_factory=dict)
    verified_by: str = ""
    divisions: list[DivisionSource] = Field(min_length=1)

    @model_validator(mode="after")
    def _markers_define_an_ordered_partition(self) -> DocumentSource:
        if self.divisions[0].marker is not None:
            raise ValueError("the first division marker must be null")
        if any(division.marker is None for division in self.divisions[1:]):
            raise ValueError("every division after the first requires a marker")
        labels = [division.label for division in self.divisions]
        if len(labels) != len(set(labels)):
            raise ValueError("division labels must be unique within a document")
        has_review_debt = any(
            division.disposition is SegmentDisposition.NEEDS_REVIEW for division in self.divisions
        )
        if self.segmentation == "paragraphs":
            has_review_debt = self.paragraph_disposition is SegmentDisposition.NEEDS_REVIEW
        if self.verified_by.strip() and has_review_debt:
            raise ValueError("verified document cannot contain review-debt divisions")
        if (
            self.segmentation == "paragraphs"
            and self.paragraph_disposition is SegmentDisposition.CONTEXT_ONLY
            and not self.paragraph_reason.strip()
        ):
            raise ValueError("context-only paragraph segmentation requires a reason")
        invalid_overrides = sorted(
            label for label in self.paragraph_overrides if re.fullmatch(r"P\d{3}", label) is None
        )
        if invalid_overrides:
            raise ValueError(f"invalid paragraph override labels: {invalid_overrides}")
        return self


class ReviewedDocumentInventory(BaseModel):
    act_version_date: date
    review_run_id: str = Field(min_length=1)
    extracted_by: str = "semantic-legal-effect-pass"
    presentation_mode: str = "exact-source-slice"
    documents: list[DocumentSource] = []

    @model_validator(mode="after")
    def _document_addresses_are_unique(self) -> ReviewedDocumentInventory:
        addresses = [(document.kind, document.number) for document in self.documents]
        if len(addresses) != len(set(addresses)):
            raise ValueError("reviewed document addresses must be unique")
        return self


class NormSourceRecord(BaseModel):
    """Reviewed authoring input from which a complete runtime-independent Norm is compiled."""

    norm_id: str = Field(pattern=r"^AIA-NORM-[A-Z0-9-]+$")
    source: str = Field(pattern=r"^[A-Z0-9-]+$")
    quote: str = Field(min_length=1)
    action: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    subject_category: SubjectCategory
    kind: NormKind = NormKind.OBLIGATION
    product_scope: ProductScope = ProductScope.IN_SCOPE
    product_scope_reason: str = ""
    implementation_refs: list[str] = []
    implementation_mode: ImplementationMode | None = None
    implementation_reason: str = ""
    verification_mode: VerificationMode | None = None
    conditions: list[str | ConditionGroup] = []
    exceptions: list[str] = []
    mandatory_content: list[str] = []
    mandatory_content_source: Literal["numbered_items"] | None = None
    dependencies: list[NormDependency] = []
    condition_norm_ids: list[str] = []
    qualifier_spans: list[str] = []
    effective_date_spans: list[str] = []
    verified_by: str = ""


class NormSourceInventory(BaseModel):
    act_version_date: date
    implementation_targets: list[str] = []
    records: list[NormSourceRecord] = []
    carried_by: dict[str, list[str]] = {}
    interpretations: list[InterpretiveLink] = []

    @model_validator(mode="after")
    def _source_ids_are_unique(self) -> NormSourceInventory:
        norm_ids = [record.norm_id for record in self.records]
        if len(norm_ids) != len(set(norm_ids)):
            raise ValueError("norm source record IDs must be unique")
        if len(self.implementation_targets) != len(set(self.implementation_targets)):
            raise ValueError("implementation target IDs must be unique")
        referenced = {target for record in self.records for target in record.implementation_refs}
        unknown_targets = sorted(referenced - set(self.implementation_targets))
        if unknown_targets:
            raise ValueError(
                "norm source records reference undeclared implementation targets: "
                f"{unknown_targets}"
            )
        interpreted_rules = {
            target.target_id
            for link in self.interpretations
            for target in link.targets
            if target.kind is InterpretationTargetKind.POLICY_RULE
        }
        unknown_interpreted_rules = sorted(interpreted_rules - set(self.implementation_targets))
        if unknown_interpreted_rules:
            raise ValueError(
                "interpretive links reference undeclared policy-rule targets: "
                f"{unknown_interpreted_rules}"
            )
        return self


@dataclass(frozen=True)
class NormBuilderPaths:
    reviewed_documents: Path
    norm_sources: Path
    articles_root: Path
    annexes_root: Path
    guidance_root: Path
    text_output: Path
    norm_output: Path
    report_output: Path
    generated_by: str


def load_builder_inputs(
    paths: NormBuilderPaths,
) -> tuple[ReviewedDocumentInventory, NormSourceInventory]:
    reviewed = ReviewedDocumentInventory.model_validate(
        load_yaml_mapping_or_shards(
            paths.reviewed_documents, description="reviewed document inventory"
        )
    )
    sources = NormSourceInventory.model_validate(
        load_yaml_mapping_or_shards(paths.norm_sources, description="norm source inventory")
    )
    if reviewed.act_version_date != sources.act_version_date:
        raise ValueError(
            "reviewed documents and norm sources use different Act versions: "
            f"{reviewed.act_version_date} != {sources.act_version_date}"
        )
    return reviewed, sources


def _document_sort_key(document: DocumentSource) -> tuple[int, int, str]:
    if document.kind is SourceKind.ANNEX:
        return 1, 0, document.number
    match = re.fullmatch(r"(\d+)([a-z]?)", document.number)
    if match is None:
        raise ValueError(f"invalid article identifier {document.number!r}")
    return 0, int(match.group(1)), match.group(2)


def _complete_document_inventory(
    reviewed: ReviewedDocumentInventory,
    paths: NormBuilderPaths,
) -> tuple[DocumentSource, ...]:
    version = reviewed.act_version_date
    declared = {(document.kind, document.number): document for document in reviewed.documents}
    expected = corpus_documents(version, paths.articles_root, paths.annexes_root)
    unknown = sorted((kind.value, document) for kind, document in set(declared) - expected)
    if unknown:
        raise ValueError(f"reviewed document inventory references unknown sources: {unknown}")

    documents = [
        declared.get(
            key,
            DocumentSource(
                kind=key[0],
                number=key[1],
                segmentation="paragraphs",
                divisions=[
                    DivisionSource(
                        label="FULL",
                        marker=None,
                        disposition=SegmentDisposition.NEEDS_REVIEW,
                        reason=DEFAULT_REVIEW_DEBT_REASON,
                    )
                ],
            ),
        )
        for key in expected
    ]
    return tuple(sorted(documents, key=_document_sort_key))


def _source_file(document: DocumentSource, version: date, paths: NormBuilderPaths) -> Path:
    root = paths.articles_root if document.kind is SourceKind.ARTICLE else paths.annexes_root
    version_root = root / version.isoformat()
    if document.kind is SourceKind.ARTICLE:
        return version_root / article_filename(document.number)
    return version_root / f"annex-{document.number}.md"


def _segment_id(document: DocumentSource, label: str) -> str:
    if document.kind is SourceKind.ARTICLE:
        match = re.fullmatch(r"(\d+)([a-z]?)", document.number)
        if match is None:
            raise ValueError(f"invalid article identifier {document.number!r}")
        prefix = f"A{int(match.group(1)):03d}{match.group(2).upper()}"
    else:
        prefix = f"ANNEX-{document.number}"
    return f"AIA-TEXT-{prefix}-{label}"


def _line_start(body: str, marker: str, cursor: int) -> int:
    start = body.find(marker, cursor)
    while start >= 0 and start > 0 and body[start - 1] != "\n":
        start = body.find(marker, start + 1)
    return start


def _review(
    reviewed: ReviewedDocumentInventory,
    status: str,
    fully_displayed: bool,
    verified_by: str = "",
) -> dict[str, object]:
    return {
        "status": status,
        "extracted_by": reviewed.extracted_by,
        "verified_by": verified_by,
        "review_run_id": reviewed.review_run_id,
        "presentation_mode": reviewed.presentation_mode,
        "display_chunks": 1 if fully_displayed else 0,
        "fully_displayed": fully_displayed,
        "elapsed_seconds": None,
    }


def _paragraph_partition(
    body: str,
    disposition: SegmentDisposition,
    reason: str,
    overrides: dict[str, ParagraphOverride],
) -> tuple[list[DivisionSource], list[int]]:
    """Split a stored source into its structural heading and source-format paragraphs.

    The Formex-derived Markdown stores each legal paragraph or nested list item on one non-empty
    line. Blank lines and trailing newlines stay attached to the preceding segment, preserving an
    exact, gap-free partition of the source body.
    """
    heading_break = body.find("\n\n")
    content_start = heading_break + 2 if heading_break >= 0 else 0
    paragraph_starts = [
        match.start() for match in re.finditer(r"(?m)^(?=[^\n]*\S)", body[content_start:])
    ]
    paragraph_starts = [content_start + start for start in paragraph_starts]

    divisions: list[DivisionSource] = []
    starts: list[int] = []
    if content_start > 0:
        divisions.append(
            DivisionSource(
                label="HEAD",
                marker=None,
                disposition=SegmentDisposition.STRUCTURAL,
            )
        )
        starts.append(0)
    for index, start in enumerate(paragraph_starts, start=1):
        label = f"P{index:03d}"
        override = overrides.get(label)
        divisions.append(
            DivisionSource(
                label=label,
                marker=body[start : body.find("\n", start) if "\n" in body[start:] else len(body)],
                disposition=override.disposition if override else disposition,
                reason=override.reason if override else reason,
                verified_by=override.verified_by if override else "",
            )
        )
        starts.append(start)
    if not divisions:
        divisions.append(
            DivisionSource(
                label="P001",
                marker=None,
                disposition=disposition,
                reason=reason,
            )
        )
        starts.append(0)
    return divisions, starts


def _build_segments(
    reviewed: ReviewedDocumentInventory,
    paths: NormBuilderPaths,
) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    version_text = reviewed.act_version_date.isoformat()
    for document in _complete_document_inventory(reviewed, paths):
        body = source_body(
            _source_file(document, reviewed.act_version_date, paths),
            expected_version=version_text,
        )
        if document.segmentation == "paragraphs":
            divisions, starts = _paragraph_partition(
                body,
                document.paragraph_disposition,
                document.paragraph_reason,
                document.paragraph_overrides,
            )
        else:
            divisions = document.divisions
            starts = []
            cursor = 0
            for index, division in enumerate(divisions):
                if index == 0:
                    start = 0
                else:
                    assert division.marker is not None
                    start = _line_start(body, division.marker, cursor)
                    if start < 0:
                        raise ValueError(
                            f"{document.kind.value} {document.number}: marker "
                            f"{division.marker!r} not found"
                        )
                starts.append(start)
                cursor = start + 1

        for index, division in enumerate(divisions):
            start = starts[index]
            end = starts[index + 1] if index + 1 < len(starts) else len(body)
            exact = body[start:end]
            is_debt = division.disposition is SegmentDisposition.NEEDS_REVIEW
            verified_by = division.verified_by or document.verified_by
            review_status = (
                "needs_review" if is_debt else "approved" if verified_by.strip() else "proposed"
            )
            segments.append(
                {
                    "segment_id": _segment_id(document, division.label),
                    "source": {
                        "kind": document.kind.value,
                        "document": document.number,
                        "act_version_date": version_text,
                    },
                    "start": start,
                    "end": end,
                    "sha256": hashlib.sha256(exact.encode()).hexdigest(),
                    "text": exact,
                    "disposition": division.disposition.value,
                    "disposition_reason": division.reason,
                    "norm_ids": [],
                    "qualifying_norm_ids": [],
                    "review": _review(
                        reviewed,
                        review_status,
                        not is_debt,
                        verified_by,
                    ),
                }
            )
    return segments


def _detection_channels(record: NormSourceRecord) -> list[str]:
    quote = record.quote.lower()
    channels = ["semantic_legal_effect"]
    if "shall" in quote:
        channels.append("shall_token")
    if any(token in quote for token in (" may ", "is empowered", "will be needed")):
        channels.append("other_modal")
    if record.kind in {NormKind.LEGAL_CONSEQUENCE, NormKind.APPLICABILITY}:
        channels.append("deeming_or_consequence")
    if record.dependencies or record.qualifier_spans:
        channels.append("cross_reference_structure")
    if record.implementation_refs:
        channels.append("existing_implementation")
    return channels


def _resolved_mode(record: NormSourceRecord) -> ImplementationMode:
    if record.implementation_mode is not None:
        return record.implementation_mode
    if record.implementation_refs:
        return ImplementationMode.COMPLIANCE_RULE
    if record.product_scope is ProductScope.IN_SCOPE:
        return ImplementationMode.MISSING
    return ImplementationMode.NONE_REQUIRED


def _resolved_verification(record: NormSourceRecord) -> VerificationMode:
    if record.verification_mode is not None:
        return record.verification_mode
    if record.product_scope is ProductScope.IN_SCOPE:
        return VerificationMode.UNRESOLVED
    return VerificationMode.NOT_REPORTED


def _numbered_items(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"(?ms)^    \d+\. (.*?)(?=^    \d+\. |\Z)", text)
    ]


def _build_norms(
    reviewed: ReviewedDocumentInventory,
    source_inventory: NormSourceInventory,
    segments: list[dict[str, object]],
    paths: NormBuilderPaths,
) -> list[dict[str, object]]:
    version_text = reviewed.act_version_date.isoformat()
    segments_by_id = {str(segment["segment_id"]): segment for segment in segments}
    known_rule_ids = set(source_inventory.implementation_targets)
    known_norm_ids = {record.norm_id for record in source_inventory.records}
    norms: list[dict[str, object]] = []

    for record in source_inventory.records:
        primary = f"AIA-TEXT-{record.source}"
        qualifiers = [f"AIA-TEXT-{span}" for span in record.qualifier_spans]
        effective = [f"AIA-TEXT-{span}" for span in record.effective_date_spans]
        unknown_spans = [
            span for span in [primary, *qualifiers, *effective] if span not in segments_by_id
        ]
        if unknown_spans:
            raise ValueError(f"{record.norm_id}: unknown source-record span(s) {unknown_spans}")
        primary_text = str(segments_by_id[primary]["text"])
        if record.quote not in primary_text:
            raise ValueError(f"{record.norm_id}: quote is not exact in {primary}: {record.quote!r}")
        unknown_rules = sorted(set(record.implementation_refs) - known_rule_ids)
        if unknown_rules:
            raise ValueError(f"{record.norm_id}: unknown implementation rule(s) {unknown_rules}")
        unknown_conditions = sorted(set(record.condition_norm_ids) - known_norm_ids)
        if unknown_conditions:
            raise ValueError(f"{record.norm_id}: unknown condition norm(s) {unknown_conditions}")
        if record.norm_id in record.condition_norm_ids:
            raise ValueError(f"{record.norm_id}: a norm cannot be its own condition")
        for span, link_field in [
            (primary, "norm_ids"),
            *((span, "qualifying_norm_ids") for span in [*qualifiers, *effective]),
        ]:
            segment = segments_by_id[span]
            if segment["disposition"] != SegmentDisposition.NORMATIVE.value:
                raise ValueError(f"{record.norm_id}: linked span {span} is not normative")
            norm_ids = segment[link_field]
            assert isinstance(norm_ids, list)
            if record.norm_id not in norm_ids:
                norm_ids.append(record.norm_id)

        dependencies = [
            {
                "dependency_ref": dependency.dependency_ref,
                "resolution": dependency.resolution.value,
                "detail": dependency.detail,
            }
            for dependency in record.dependencies
        ]
        for dependency in dependencies:
            if (
                dependency["resolution"] == DependencyResolution.INTERNAL_RESOLVED.value
                and dependency["dependency_ref"] not in known_norm_ids
                and dependency["dependency_ref"] not in segments_by_id
            ):
                raise ValueError(
                    f"{record.norm_id}: internal dependency "
                    f"{dependency['dependency_ref']} is unknown"
                )

        mandatory_content = list(record.mandatory_content)
        if record.mandatory_content_source == "numbered_items":
            mandatory_content = _numbered_items(primary_text)
            if not mandatory_content:
                raise ValueError(f"{record.norm_id}: no numbered mandatory-content items found")

        norm: dict[str, object] = {
            "norm_id": record.norm_id,
            "act_version_date": version_text,
            "kind": record.kind.value,
            "subjects": [
                {
                    "subject_ref": record.subject_ref,
                    "category": record.subject_category.value,
                }
            ],
            "action": record.action,
            "norm_text": record.quote,
            "detection_channels": _detection_channels(record),
            "primary_spans": [primary],
            "qualifier_spans": qualifiers,
            "effective_date_spans": effective,
            "conditions": record.model_dump(mode="json")["conditions"],
            "exceptions": record.exceptions,
            "mandatory_content": mandatory_content,
            "dependencies": dependencies,
            "product_scope": record.product_scope.value,
            "product_scope_reason": record.product_scope_reason,
            "implementation_mode": _resolved_mode(record).value,
            "implementation_refs": record.implementation_refs,
            "implementation_reason": record.implementation_reason,
            "verification_mode": _resolved_verification(record).value,
            "review": _review(
                reviewed,
                "approved" if record.verified_by.strip() else "proposed",
                True,
                record.verified_by,
            ),
        }
        if record.condition_norm_ids:
            norm["condition_norm_ids"] = record.condition_norm_ids
        norms.append(norm)

    norms_by_id = {str(norm["norm_id"]): norm for norm in norms}
    for norm in norms:
        for condition_id in norm.get("condition_norm_ids", []):
            condition = norms_by_id[str(condition_id)]
            parents = condition.setdefault("condition_of_norm_ids", [])
            assert isinstance(parents, list)
            parents.append(norm["norm_id"])
    for norm_id, carriers in source_inventory.carried_by.items():
        if norm_id not in norms_by_id:
            raise ValueError(f"carried_by references unknown source norm {norm_id}")
        unknown_carriers = sorted(set(carriers) - known_norm_ids)
        if unknown_carriers:
            raise ValueError(f"{norm_id}: unknown carrier norm(s) {unknown_carriers}")
        norms_by_id[norm_id]["carried_by_norm_ids"] = carriers
    return norms


def build_artifacts(
    reviewed: ReviewedDocumentInventory,
    source_inventory: NormSourceInventory,
    paths: NormBuilderPaths,
) -> tuple[dict[str, object], dict[str, object]]:
    """Compile versioned reviewed inputs without reading or writing generated artifacts."""
    segments = _build_segments(reviewed, paths)
    norms = _build_norms(reviewed, source_inventory, segments, paths)
    return (
        {
            "act_version_date": reviewed.act_version_date.isoformat(),
            "corpus_complete": True,
            "segments": segments,
        },
        {
            "act_version_date": reviewed.act_version_date.isoformat(),
            "norms": norms,
            "interpretations": [
                link.model_dump(mode="json") for link in source_inventory.interpretations
            ],
        },
    )


def render_artifacts(
    reviewed: ReviewedDocumentInventory,
    source_inventory: NormSourceInventory,
    paths: NormBuilderPaths,
) -> tuple[str, str]:
    text_review, norms = build_artifacts(reviewed, source_inventory, paths)
    heading = (
        f"# Generated by {paths.generated_by} from versioned reviewed inputs; "
        "do not edit generated offsets.\n"
    )
    return (
        heading + yaml.safe_dump(text_review, sort_keys=False, width=100),
        heading + yaml.safe_dump(norms, sort_keys=False, width=100),
    )


def _document_shard_path(kind: str, document: str) -> Path:
    if kind == SourceKind.ARTICLE.value:
        match = re.fullmatch(r"(\d+)([a-z]?)", document)
        if match is None:
            raise ValueError(f"invalid article identifier {document!r}")
        return Path("articles") / f"{int(match.group(1)):03d}{match.group(2)}.yaml"
    return Path("annexes") / f"{document}.yaml"


def _render_sharded_artifacts(
    reviewed: ReviewedDocumentInventory,
    source_inventory: NormSourceInventory,
    paths: NormBuilderPaths,
) -> tuple[dict[Path, str], dict[Path, str]]:
    text_review, norm_inventory = build_artifacts(reviewed, source_inventory, paths)
    heading = (
        f"# Generated by {paths.generated_by} from versioned reviewed inputs; "
        "do not edit generated offsets.\n"
    )
    text_files = {
        paths.text_output / "manifest.yaml": heading
        + yaml.safe_dump(
            {key: value for key, value in text_review.items() if key != "segments"},
            sort_keys=False,
            width=100,
        )
    }
    review_segments = text_review["segments"]
    assert isinstance(review_segments, list)
    segments_by_document: dict[tuple[str, str], list[dict[str, object]]] = {}
    for segment in review_segments:
        assert isinstance(segment, dict)
        source = segment["source"]
        assert isinstance(source, dict)
        key = str(source["kind"]), str(source["document"])
        segments_by_document.setdefault(key, []).append(segment)
    for (kind, document), segments in segments_by_document.items():
        path = paths.text_output / _document_shard_path(kind, document)
        text_files[path] = heading + yaml.safe_dump(
            {"segments": segments}, sort_keys=False, width=100
        )

    norm_files = {
        paths.norm_output / "manifest.yaml": heading
        + yaml.safe_dump(
            {key: value for key, value in norm_inventory.items() if key != "norms"},
            sort_keys=False,
            width=100,
        )
    }
    segment_documents = {
        str(segment["segment_id"]): (
            str(segment["source"]["kind"]),
            str(segment["source"]["document"]),
        )
        for segment in review_segments
    }
    inventory_norms = norm_inventory["norms"]
    assert isinstance(inventory_norms, list)
    norms_by_document: dict[tuple[str, str], list[dict[str, object]]] = {}
    for norm in inventory_norms:
        assert isinstance(norm, dict)
        primary_spans = norm["primary_spans"]
        assert isinstance(primary_spans, list)
        key = segment_documents[str(primary_spans[0])]
        norms_by_document.setdefault(key, []).append(norm)
    for (kind, document), norms in norms_by_document.items():
        path = paths.norm_output / _document_shard_path(kind, document)
        norm_files[path] = heading + yaml.safe_dump({"norms": norms}, sort_keys=False, width=100)
    return text_files, norm_files


def _check_or_write_files(expected: dict[Path, str], *, root: Path, check: bool) -> None:
    expected_paths = set(expected)
    existing_paths = set(root.rglob("*.yaml")) if root.is_dir() else set()
    stale = sorted(existing_paths - expected_paths)
    changed = sorted(
        path
        for path, content in expected.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    )
    if check:
        if stale or changed:
            paths = [*(str(path) for path in changed), *(str(path) for path in stale)]
            raise ValueError(f"generated coverage artifacts are stale: {', '.join(paths)}")
        return
    for path in stale:
        path.unlink()
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")


def run_builder(paths: NormBuilderPaths, *, check: bool) -> None:
    """Write or reproducibly verify artifacts and their rendered metrics report."""
    reviewed, source_inventory = load_builder_inputs(paths)
    if paths.text_output.suffix == ".yaml" and paths.norm_output.suffix == ".yaml":
        text, norms = render_artifacts(reviewed, source_inventory, paths)
        expected_artifacts = ((paths.text_output, text), (paths.norm_output, norms))
        if check:
            stale = [
                str(path)
                for path, expected in expected_artifacts
                if not path.is_file() or path.read_text(encoding="utf-8") != expected
            ]
            if stale:
                raise ValueError(f"generated coverage artifacts are stale: {', '.join(stale)}")
        else:
            for path, content in expected_artifacts:
                path.write_text(content, encoding="utf-8")
    else:
        text_files, norm_files = _render_sharded_artifacts(reviewed, source_inventory, paths)
        _check_or_write_files(text_files, root=paths.text_output, check=check)
        _check_or_write_files(norm_files, root=paths.norm_output, check=check)

    bundle = load_normative_coverage(
        paths.text_output,
        paths.norm_output,
        articles_root=paths.articles_root,
        annexes_root=paths.annexes_root,
        guidance_root=paths.guidance_root,
    )
    report = render_coverage_markdown(measure_normative_coverage(bundle))
    if check:
        if not paths.report_output.is_file() or (
            paths.report_output.read_text(encoding="utf-8") != report
        ):
            raise ValueError(f"generated coverage report is stale: {paths.report_output}")
    else:
        paths.report_output.write_text(report, encoding="utf-8")
