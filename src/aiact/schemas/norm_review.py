"""Audit records for source-first norm candidate extraction."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from aiact.schemas.norm import (
    CandidateDetectionChannel,
    SegmentSource,
)


class NormCandidate(BaseModel):
    candidate_id: str = Field(pattern=r"^AIA-CAND-[A-F0-9]{16}$")
    segment_id: str = Field(pattern=r"^AIA-TEXT-[A-Z0-9-]+$")
    source: SegmentSource
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str = Field(min_length=1)
    detection_channels: list[CandidateDetectionChannel] = Field(min_length=1)

    @model_validator(mode="after")
    def _candidate_shape_is_exact(self) -> NormCandidate:
        if self.end <= self.start:
            raise ValueError("candidate end must be greater than start")
        if self.end - self.start != len(self.text):
            raise ValueError("candidate offsets must match its exact character length")
        if len(self.detection_channels) != len(set(self.detection_channels)):
            raise ValueError("candidate detection channels must be unique")
        if self.sha256 != hashlib.sha256(self.text.encode()).hexdigest():
            raise ValueError("candidate hash must match its exact text")
        return self


class NormCandidateRun(BaseModel):
    run_id: str = Field(min_length=1)
    act_version_date: date
    extractor_id: str = Field(min_length=1)
    created_at: datetime
    segment_scope: Literal["needs_review", "all"]
    segment_ids_considered: list[str]
    source_characters_considered: int = Field(ge=0)
    candidates: list[NormCandidate] = []

    @model_validator(mode="after")
    def _run_denominator_and_ids_are_stable(self) -> NormCandidateRun:
        if self.created_at.tzinfo is None:
            raise ValueError("candidate run timestamp must include a timezone")
        if len(self.segment_ids_considered) != len(set(self.segment_ids_considered)):
            raise ValueError("considered segment IDs must be unique")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        considered = set(self.segment_ids_considered)
        unknown = sorted(
            candidate.segment_id
            for candidate in self.candidates
            if candidate.segment_id not in considered
        )
        if unknown:
            raise ValueError(
                f"candidates reference segments outside the run denominator: {unknown}"
            )
        return self
