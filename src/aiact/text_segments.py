"""Resolve exact normative-review spans against the pinned enacted corpus."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date
from pathlib import Path

from aiact.policy_loader import article_filename, source_body
from aiact.schemas.norm import SegmentSource, SourceKind, TextReviewSegment

SourceKey = tuple[SourceKind, str]


def source_path(
    source: SegmentSource,
    articles_root: str | Path,
    annexes_root: str | Path,
) -> Path:
    """Resolve a segment source to the version-pinned stored document."""
    version = source.act_version_date.isoformat()
    if source.kind is SourceKind.ARTICLE:
        return Path(articles_root) / version / article_filename(source.document)
    return Path(annexes_root) / version / f"annex-{source.document}.md"


def load_source_body(
    source: SegmentSource,
    articles_root: str | Path,
    annexes_root: str | Path,
) -> str:
    path = source_path(source, articles_root, annexes_root)
    if not path.is_file():
        raise FileNotFoundError(f"normative coverage source does not exist: {path}")
    return source_body(path, expected_version=source.act_version_date.isoformat())


def validate_document_partition(
    segments: list[TextReviewSegment],
    body: str,
    where: str,
) -> None:
    """Require an included document to be partitioned exactly, with no gap or overlap."""
    ordered = sorted(segments, key=lambda segment: (segment.start, segment.end))
    if not ordered:
        raise ValueError(f"{where} is declared reviewed but has no segments")
    cursor = 0
    for segment in ordered:
        if segment.start != cursor:
            relation = "gap" if segment.start > cursor else "overlap"
            raise ValueError(
                f"{where}: {relation} before {segment.segment_id}: expected start {cursor}, "
                f"got {segment.start}"
            )
        if segment.end > len(body):
            raise ValueError(
                f"{where}: {segment.segment_id} ends at {segment.end}, beyond body length "
                f"{len(body)}"
            )
        exact = body[segment.start : segment.end]
        if segment.text != exact:
            raise ValueError(
                f"{where}: {segment.segment_id} text is not the exact source slice "
                f"[{segment.start}:{segment.end}]"
            )
        actual = hashlib.sha256(exact.encode("utf-8")).hexdigest()
        if segment.sha256 != actual:
            raise ValueError(
                f"{where}: {segment.segment_id} sha256 does not match its exact source slice"
            )
        cursor = segment.end
    if cursor != len(body):
        raise ValueError(
            f"{where}: partition stops at {cursor}, leaving {len(body) - cursor} characters unseen"
        )


def group_segments(
    segments: list[TextReviewSegment],
) -> dict[SourceKey, list[TextReviewSegment]]:
    grouped: dict[SourceKey, list[TextReviewSegment]] = defaultdict(list)
    for segment in segments:
        grouped[(segment.source.kind, segment.source.document)].append(segment)
    return dict(grouped)


def corpus_documents(
    version: date,
    articles_root: str | Path,
    annexes_root: str | Path,
) -> set[SourceKey]:
    """Every stored source document for a version, independently of review artifacts."""
    version_name = version.isoformat()
    articles = {
        (SourceKind.ARTICLE, path.stem.removeprefix("article-").lstrip("0") or "0")
        for path in (Path(articles_root) / version_name).glob("article-*.md")
    }
    annexes = {
        (SourceKind.ANNEX, path.stem.removeprefix("annex-"))
        for path in (Path(annexes_root) / version_name).glob("annex-*.md")
    }
    return articles | annexes
