"""Source-first candidate detection that preserves the complete review denominator."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from aiact.schemas.norm import (
    CandidateDetectionChannel,
    NormativeCoverageBundle,
    SegmentDisposition,
    TextReviewSegment,
)
from aiact.schemas.norm_review import NormCandidate, NormCandidateRun

_CHANNEL_PATTERNS: tuple[tuple[CandidateDetectionChannel, re.Pattern[str]], ...] = (
    (CandidateDetectionChannel.SHALL_TOKEN, re.compile(r"\bshall\b", re.IGNORECASE)),
    (
        CandidateDetectionChannel.OTHER_MODAL,
        re.compile(
            r"\b(?:must|may|is empowered|are empowered|is entitled|are entitled|"
            r"is required to|are required to|is to|are to)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateDetectionChannel.DEEMING_OR_CONSEQUENCE,
        re.compile(
            r"\b(?:is|are|shall be)\s+(?:deemed|considered)|"
            r"\b(?:shall cease|shall apply|shall not apply|does not apply|do not apply|"
            r"is prohibited|are prohibited)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CandidateDetectionChannel.CROSS_REFERENCE_STRUCTURE,
        re.compile(
            r"\b(?:in accordance with|referred to in|subject to|without prejudice to|"
            r"by way of derogation from|for the purposes of)\b",
            re.IGNORECASE,
        ),
    ),
)


def _candidate_bounds(text: str, match_start: int, match_end: int) -> tuple[int, int]:
    starts = [0]
    for delimiter in ("\n", ". ", "; ", ": "):
        found = text.rfind(delimiter, 0, match_start)
        if found >= 0:
            starts.append(found + len(delimiter))
    start = max(starts)

    ends = [len(text)]
    for delimiter in ("\n", ".", ";"):
        found = text.find(delimiter, match_end)
        if found >= 0:
            ends.append(found if delimiter == "\n" else found + 1)
    end = min(ends)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _candidate_id(segment_id: str, start: int, end: int, text: str) -> str:
    identity = f"{segment_id}\0{start}\0{end}\0{text}".encode()
    return f"AIA-CAND-{hashlib.sha256(identity).hexdigest()[:16].upper()}"


def _add_candidate(
    found: dict[tuple[str, int, int], dict[str, object]],
    segment: TextReviewSegment,
    relative_start: int,
    relative_end: int,
    channel: CandidateDetectionChannel,
) -> None:
    start = segment.start + relative_start
    end = segment.start + relative_end
    text = segment.text[relative_start:relative_end]
    key = segment.segment_id, start, end
    item = found.setdefault(
        key,
        {
            "segment": segment,
            "text": text,
            "channels": set(),
        },
    )
    channels = item["channels"]
    assert isinstance(channels, set)
    channels.add(channel)


def extract_norm_candidates(
    bundle: NormativeCoverageBundle,
    *,
    run_id: str,
    extractor_id: str,
    include_reviewed_segments: bool = False,
    created_at: datetime | None = None,
) -> NormCandidateRun:
    """Propose source-backed passages without treating candidate recall as review coverage."""
    segments = [
        segment
        for segment in bundle.text_review.segments
        if include_reviewed_segments or segment.disposition is SegmentDisposition.NEEDS_REVIEW
    ]
    segments.sort(
        key=lambda segment: (
            segment.source.kind.value,
            segment.source.document,
            segment.start,
        )
    )
    found: dict[tuple[str, int, int], dict[str, object]] = {}

    for segment in segments:
        for channel, pattern in _CHANNEL_PATTERNS:
            for match in pattern.finditer(segment.text):
                start, end = _candidate_bounds(segment.text, match.start(), match.end())
                if start < end:
                    _add_candidate(found, segment, start, end, channel)

    candidates: list[NormCandidate] = []
    for (segment_id, start, end), item in sorted(found.items()):
        candidate_segment = item["segment"]
        text = item["text"]
        channels = item["channels"]
        assert isinstance(candidate_segment, TextReviewSegment)
        assert isinstance(text, str)
        assert isinstance(channels, set)
        candidates.append(
            NormCandidate(
                candidate_id=_candidate_id(segment_id, start, end, text),
                segment_id=segment_id,
                source=candidate_segment.source,
                start=start,
                end=end,
                sha256=hashlib.sha256(text.encode()).hexdigest(),
                text=text,
                detection_channels=sorted(channels, key=lambda channel: channel.value),
            )
        )

    return NormCandidateRun(
        run_id=run_id,
        act_version_date=bundle.text_review.act_version_date,
        extractor_id=extractor_id,
        created_at=created_at or datetime.now(UTC),
        segment_scope="all" if include_reviewed_segments else "needs_review",
        segment_ids_considered=[segment.segment_id for segment in segments],
        source_characters_considered=sum(len(segment.text) for segment in segments),
        candidates=candidates,
    )


def validate_candidate_run(
    run: NormCandidateRun,
    bundle: NormativeCoverageBundle,
) -> None:
    """Prove every candidate is an exact slice of a segment in the declared run denominator."""
    if run.act_version_date != bundle.text_review.act_version_date:
        raise ValueError("candidate run and normative inventory use different Act versions")
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    expected_ids = {
        segment.segment_id
        for segment in bundle.text_review.segments
        if run.segment_scope == "all" or segment.disposition is SegmentDisposition.NEEDS_REVIEW
    }
    declared_ids = set(run.segment_ids_considered)
    if declared_ids != expected_ids:
        missing = sorted(expected_ids - declared_ids)
        extra = sorted(declared_ids - expected_ids)
        raise ValueError(
            f"candidate run denominator disagrees with its scope; "
            f"missing={missing[:20]}, extra={extra[:20]}"
        )
    declared_characters = sum(len(segments[segment_id].text) for segment_id in declared_ids)
    if run.source_characters_considered != declared_characters:
        raise ValueError(
            "candidate run source character count disagrees with its segment denominator"
        )
    for candidate in run.candidates:
        segment = segments.get(candidate.segment_id)
        if segment is None:
            raise ValueError(f"{candidate.candidate_id} references unknown segment")
        if candidate.source != segment.source:
            raise ValueError(f"{candidate.candidate_id} source disagrees with its segment")
        if candidate.start < segment.start or candidate.end > segment.end:
            raise ValueError(f"{candidate.candidate_id} falls outside its segment")
        relative_start = candidate.start - segment.start
        relative_end = candidate.end - segment.start
        if segment.text[relative_start:relative_end] != candidate.text:
            raise ValueError(f"{candidate.candidate_id} is not the exact declared source slice")
