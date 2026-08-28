"""Shadow schemas for exact text review and atomic legal propositions.

These models do not participate in classification, rule selection, judging, or reporting. They
are the Phase 1 assurance layer beneath those runtime paths.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from aiact.schemas.interpretation import InterpretiveLink
from aiact.schemas.review import ReviewRecord, ReviewStatus


class SourceKind(StrEnum):
    ARTICLE = "article"
    ANNEX = "annex"


class SegmentDisposition(StrEnum):
    NORMATIVE = "normative"
    CONTEXT_ONLY = "context_only"
    STRUCTURAL = "structural"
    NEEDS_REVIEW = "needs_review"


class NormKind(StrEnum):
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    ENTITLEMENT = "entitlement"
    POWER = "power"
    APPLICABILITY = "applicability"
    DEFINITION = "definition"
    LEGAL_CONSEQUENCE = "legal_consequence"


class SubjectCategory(StrEnum):
    SUPPORTED_OPERATOR = "supported_operator"
    EXTERNAL_PRIVATE_PARTY = "external_private_party"
    NATURAL_PERSON = "natural_person"
    UNION_INSTITUTION_OR_BODY = "union_institution_or_body"
    MEMBER_STATE = "member_state"
    PUBLIC_AUTHORITY = "public_authority"
    NOTIFIED_OR_CONFORMITY_BODY = "notified_or_conformity_body"
    OTHER = "other"
    UNRESOLVED = "unresolved"


class ProductScope(StrEnum):
    IN_SCOPE = "in_scope"
    OUTSIDE_SUPPORTED_ACTOR = "outside_supported_actor"
    DEPENDENCY_ONLY = "dependency_only"
    NO_PRODUCT_ACTION = "no_product_action"
    UNRESOLVED = "unresolved"


class ImplementationMode(StrEnum):
    COMPLIANCE_RULE = "compliance_rule"
    APPLICABILITY_QUESTION = "applicability_question"
    REPORT_ONLY = "report_only"
    SCOPE_NOTE = "scope_note"
    CARRIED_BY_OTHER_NORM = "carried_by_other_norm"
    NONE_REQUIRED = "none_required"
    MISSING = "missing"
    UNRESOLVED = "unresolved"


class VerificationMode(StrEnum):
    JUDGED_FROM_DOCUMENT = "judged_from_document"
    RESOLVED_FROM_DESCRIPTION = "resolved_from_description"
    LISTED_FOR_CONFIRMATION = "listed_for_confirmation"
    REPORTED_CONDITIONALLY = "reported_conditionally"
    NOT_ASSESSED = "not_assessed"
    UNRESOLVED = "unresolved"


class DependencyResolution(StrEnum):
    INTERNAL_RESOLVED = "internal_resolved"
    EXTERNAL_RECORDED = "external_recorded"
    GUIDANCE_LINKED = "guidance_linked"
    NATIONAL_OR_FACTUAL = "national_or_factual"
    MISSING = "missing"
    UNRESOLVED = "unresolved"


class SegmentSource(BaseModel):
    kind: SourceKind
    document: str = Field(min_length=1)
    act_version_date: date


class TextReviewSegment(BaseModel):
    segment_id: str = Field(pattern=r"^AIA-TEXT-[A-Z0-9-]+$")
    source: SegmentSource
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str
    disposition: SegmentDisposition
    disposition_reason: str = ""
    norm_ids: list[str] = []
    review: ReviewRecord

    @model_validator(mode="after")
    def _disposition_has_the_right_shape(self) -> TextReviewSegment:
        if self.end <= self.start:
            raise ValueError("segment end must be greater than start")
        if self.disposition is SegmentDisposition.NORMATIVE and not self.norm_ids:
            raise ValueError("normative segment requires at least one norm_id")
        if self.disposition is not SegmentDisposition.NORMATIVE and self.norm_ids:
            raise ValueError("only normative segments may link norm_ids")
        if (
            self.disposition is SegmentDisposition.CONTEXT_ONLY
            and not self.disposition_reason.strip()
        ):
            raise ValueError("context_only segment requires disposition_reason")
        if self.disposition is SegmentDisposition.NEEDS_REVIEW:
            if self.review.status is ReviewStatus.APPROVED:
                raise ValueError("needs_review segment cannot have an approved review")
        elif self.review.status is ReviewStatus.NEEDS_REVIEW:
            raise ValueError("review status needs_review requires segment disposition needs_review")
        return self


class TextReviewInventory(BaseModel):
    act_version_date: date
    corpus_complete: bool = False
    segments: list[TextReviewSegment] = []

    @model_validator(mode="after")
    def _segment_ids_are_unique(self) -> TextReviewInventory:
        ids = [s.segment_id for s in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate segment_id")
        return self


class NormSubject(BaseModel):
    subject_ref: str = Field(min_length=1)
    category: SubjectCategory


class NormDependency(BaseModel):
    dependency_ref: str = Field(min_length=1)
    resolution: DependencyResolution
    detail: str = ""

    @model_validator(mode="after")
    def _unresolved_or_missing_dependency_is_explained(self) -> NormDependency:
        if (
            self.resolution
            in {
                DependencyResolution.MISSING,
                DependencyResolution.UNRESOLVED,
            }
            and not self.detail.strip()
        ):
            raise ValueError(f"dependency {self.resolution.value} requires detail")
        return self


class Norm(BaseModel):
    norm_id: str = Field(pattern=r"^AIA-NORM-[A-Z0-9-]+$")
    act_version_date: date
    kind: NormKind
    subjects: list[NormSubject] = Field(min_length=1)
    action: str = Field(min_length=1)
    primary_spans: list[str] = Field(min_length=1)
    qualifier_spans: list[str] = []
    definition_spans: list[str] = []
    effective_date_spans: list[str] = []
    conditions: list[str] = []
    exceptions: list[str] = []
    mandatory_content: list[str] = []
    dependencies: list[NormDependency] = []
    product_scope: ProductScope
    product_scope_reason: str = ""
    implementation_mode: ImplementationMode
    implementation_refs: list[str] = []
    carried_by_norm_ids: list[str] = []
    superseded_by_norm_ids: list[str] = []
    implementation_reason: str = ""
    verification_mode: VerificationMode
    review: ReviewRecord

    @property
    def all_spans(self) -> list[str]:
        return list(
            dict.fromkeys(
                self.primary_spans
                + self.qualifier_spans
                + self.definition_spans
                + self.effective_date_spans
            )
        )

    @model_validator(mode="after")
    def _scope_and_implementation_are_explained(self) -> Norm:
        if self.product_scope not in {ProductScope.IN_SCOPE, ProductScope.UNRESOLVED}:
            if not self.product_scope_reason.strip():
                raise ValueError(f"product_scope={self.product_scope.value} requires a reason")
        if (
            self.implementation_mode
            in {
                ImplementationMode.COMPLIANCE_RULE,
                ImplementationMode.APPLICABILITY_QUESTION,
                ImplementationMode.REPORT_ONLY,
                ImplementationMode.SCOPE_NOTE,
            }
            and not self.implementation_refs
        ):
            raise ValueError(
                f"implementation_mode={self.implementation_mode.value} requires implementation_refs"
            )
        if self.implementation_mode is ImplementationMode.CARRIED_BY_OTHER_NORM:
            if not self.carried_by_norm_ids:
                raise ValueError("carried_by_other_norm requires carried_by_norm_ids")
            if self.norm_id in self.carried_by_norm_ids:
                raise ValueError("a norm cannot be carried by itself")
        elif self.carried_by_norm_ids:
            raise ValueError(
                "carried_by_norm_ids requires implementation_mode=carried_by_other_norm"
            )
        if self.implementation_mode is ImplementationMode.NONE_REQUIRED:
            if not self.implementation_reason.strip():
                raise ValueError("none_required implementation requires a reason")
        if self.review.status is ReviewStatus.SUPERSEDED:
            if not self.superseded_by_norm_ids:
                raise ValueError("superseded norm requires superseded_by_norm_ids")
            if self.norm_id in self.superseded_by_norm_ids:
                raise ValueError("a norm cannot supersede itself")
        elif self.superseded_by_norm_ids:
            raise ValueError("superseded_by_norm_ids requires review status superseded")
        if self.review.status is ReviewStatus.REJECTED:
            raise ValueError("rejected candidates belong in extraction history, not norm inventory")
        return self


class NormInventory(BaseModel):
    act_version_date: date
    norms: list[Norm] = []
    interpretations: list[InterpretiveLink] = []

    @model_validator(mode="after")
    def _ids_are_unique(self) -> NormInventory:
        norm_ids = [n.norm_id for n in self.norms]
        interpretation_ids = [i.interpretation_id for i in self.interpretations]
        if len(norm_ids) != len(set(norm_ids)):
            raise ValueError("duplicate norm_id")
        if len(interpretation_ids) != len(set(interpretation_ids)):
            raise ValueError("duplicate interpretation_id")
        return self


class NormativeCoverageBundle(BaseModel):
    """Both shadow artifacts after their cross-file and source validation has succeeded."""

    text_review: TextReviewInventory
    norm_inventory: NormInventory
    validated_documents: int
    validated_segments: int
    validated_norms: int
    runtime_integrated: Literal[False] = False
