"""Independent-review provenance shared by legal spans, norms, and interpretations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ReviewStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    SUPERSEDED = "superseded"


class ReviewRecord(BaseModel):
    status: ReviewStatus
    extracted_by: str = ""
    verified_by: str = ""
    review_run_id: str = ""
    presentation_mode: str = ""
    display_chunks: int = Field(default=0, ge=0)
    fully_displayed: bool = False

    @model_validator(mode="after")
    def _approved_means_independently_and_fully_reviewed(self) -> ReviewRecord:
        if self.status is not ReviewStatus.APPROVED:
            return self
        if not self.extracted_by.strip() or not self.verified_by.strip():
            raise ValueError("approved review requires extracted_by and verified_by")
        if self.extracted_by == self.verified_by:
            raise ValueError("approved review requires an independent verifier")
        if not self.fully_displayed or self.display_chunks < 1:
            raise ValueError("approved review requires the full source to have been displayed")
        return self
