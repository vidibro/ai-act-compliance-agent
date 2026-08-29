"""Source-first candidate detection preserves exact text and uncovered segments."""

from __future__ import annotations

import hashlib
from datetime import date

import pytest

from aiact.norm_extraction import extract_norm_candidates, validate_candidate_run
from aiact.schemas.norm import (
    CandidateDetectionChannel,
    NormativeCoverageBundle,
    NormInventory,
    SegmentDisposition,
    SegmentSource,
    SourceKind,
    TextReviewInventory,
    TextReviewSegment,
)
from aiact.schemas.review import ReviewRecord, ReviewStatus


def bundle_for(*texts: str) -> NormativeCoverageBundle:
    source = SegmentSource(
        kind=SourceKind.ARTICLE,
        document="1",
        act_version_date=date(2030, 1, 2),
    )
    cursor = 0
    segments = []
    for index, text in enumerate(texts, start=1):
        segments.append(
            TextReviewSegment(
                segment_id=f"AIA-TEXT-A001-P{index}",
                source=source,
                start=cursor,
                end=cursor + len(text),
                sha256=hashlib.sha256(text.encode()).hexdigest(),
                text=text,
                disposition=SegmentDisposition.NEEDS_REVIEW,
                disposition_reason="Awaiting semantic review.",
                review=ReviewRecord(
                    status=ReviewStatus.NEEDS_REVIEW,
                    extracted_by="extractor-a",
                ),
            )
        )
        cursor += len(text)
    return NormativeCoverageBundle(
        text_review=TextReviewInventory(
            act_version_date=date(2030, 1, 2),
            corpus_complete=True,
            segments=segments,
        ),
        norm_inventory=NormInventory(act_version_date=date(2030, 1, 2)),
        validated_documents=1,
        validated_segments=len(segments),
        validated_norms=0,
    )


def test_non_shall_modal_and_legal_consequence_are_candidates():
    bundle = bundle_for(
        "Providers must retain logs. "
        "A provider is considered responsible when it changes the model."
    )

    run = extract_norm_candidates(
        bundle,
        run_id="run-1",
        extractor_id="extractor-a",
    )

    assert len(run.candidates) == 2
    assert CandidateDetectionChannel.OTHER_MODAL in run.candidates[0].detection_channels
    assert CandidateDetectionChannel.SHALL_TOKEN not in run.candidates[0].detection_channels
    assert CandidateDetectionChannel.DEEMING_OR_CONSEQUENCE in run.candidates[1].detection_channels
    validate_candidate_run(run, bundle)


def test_zero_candidate_segment_remains_in_the_run_denominator():
    text = "A heading and explanatory sentence with no candidate signal."
    bundle = bundle_for(text)

    run = extract_norm_candidates(
        bundle,
        run_id="run-2",
        extractor_id="extractor-a",
    )

    assert run.candidates == []
    assert run.segment_ids_considered == ["AIA-TEXT-A001-P1"]
    assert run.source_characters_considered == len(text)


def test_candidate_validation_rejects_text_moved_outside_its_source_slice():
    bundle = bundle_for("The provider shall retain logs.")
    run = extract_norm_candidates(
        bundle,
        run_id="run-3",
        extractor_id="extractor-a",
    )
    candidate = run.candidates[0]
    candidate.start += 1
    candidate.end += 1

    with pytest.raises(ValueError, match="falls outside its segment"):
        validate_candidate_run(run, bundle)
