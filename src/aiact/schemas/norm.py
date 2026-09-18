"""Schemas for exact text review and atomic legal propositions.

These models form an independently validated assurance layer beneath the runtime paths. They do
not participate in classification or rule selection. Judging and reporting read them in one place
only: a rule's `criteria` name norms by id, and the policy loader materialises each criterion from
the generated norm it names.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aiact.schemas.enums import ActorCategory, ActorRole, ProhibitedPractice
from aiact.schemas.interpretation import InterpretiveLink
from aiact.schemas.review import ReviewRecord, ReviewStatus

NormativeSegmentId = Annotated[str, Field(pattern=r"^AIA-TEXT-[A-Z0-9-]+$")]


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
    RECOMMENDATION = "recommendation"
    APPLICABILITY = "applicability"
    DEFINITION = "definition"
    LEGAL_CONSEQUENCE = "legal_consequence"


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
    """WHICH engine treats a norm, and what an absent fact produces there.

    Ordered strongest treatment first. Both engines read the one submitted document, so the
    distinction is not where the text comes from — it is what SILENCE means:

    - `judged_by_gap_analysis` — the gap layer rules on the documentation. The document is itself
      the compliance artefact, so silence is the finding: a `gap`, meaning WRITE THIS.
    - `answered_by_classification` — the cascade answers one applicability question. Silence proves
      nothing about the system, so the node abstains (`description_silent`) rather than deciding a
      risk class on a fact the documentation never supplied.
    - `reported_not_judged` — printed as owed, with no verdict: the duty applies, and nothing in a
      document can evidence compliance with it.
    - `reported_conditionally` — printed as conditional, with no verdict: whether the duty applies
      at all turns on a fact about the duty-holder or on other law.
    - `not_reported` — absent from the report. Correct for a norm binding someone the product does
      not report for; an in-scope duty belongs in one of the two above instead.
    - `unresolved` — no treatment approved yet. Visible debt, and the builder's default for an
      in-scope norm, so it means unlabelled rather than undecidable.

    Mislabelling across the first two inverts the report: an obligation marked as a classification
    question hides a real gap, and a classification question marked as an obligation reports a gap
    against a system whose tier was never determined."""

    JUDGED_BY_GAP_ANALYSIS = "judged_by_gap_analysis"
    ANSWERED_BY_CLASSIFICATION = "answered_by_classification"
    REPORTED_NOT_JUDGED = "reported_not_judged"
    REPORTED_CONDITIONALLY = "reported_conditionally"
    NOT_REPORTED = "not_reported"
    UNRESOLVED = "unresolved"


class NormRelationKind(StrEnum):
    """A legal effect that connects a norm to implementation elsewhere.

    These are deliberately narrow, executable relation types. They are not a generic citation
    graph: each says why a norm is represented without becoming another criterion of the target
    rule.
    """

    ALLOCATES_DUTY_TO_POLICY_RULES = "allocates_duty_to_policy_rules"
    CARRIED_BY_POLICY_RULES = "carried_by_policy_rules"
    SUBJECT_TO_EXTERNAL_REQUIREMENTS = "subject_to_external_requirements"
    CONDITIONAL_ON_NORMS = "conditional_on_norms"
    CARRIED_BY_NORMS = "carried_by_norms"
    PARALLEL_NORMS = "parallel_norms"
    RELIES_ON_NORMS = "relies_on_norms"
    INTERPRETED_BY_COMMISSION_GUIDANCE = "interpreted_by_commission_guidance"
    NATIONAL_LAW_REGULATION = "national_law_regulation"
    UNRESOLVED_DEPENDENCY = "unresolved_dependency"
    MISSING_DEPENDENCY = "missing_dependency"


class NormRelation(BaseModel):
    """One reviewed internal or external implementation relation for a norm."""

    model_config = ConfigDict(extra="forbid")

    relation_id: str = Field(pattern=r"^AIA-REL-[A-Z0-9-]+$")
    source_norm_id: str = Field(pattern=r"^AIA-NORM-[A-Z0-9-]+$")
    kind: NormRelationKind
    target_rule_ids: list[str] = []
    target_norm_ids: list[str] = []
    external_requirements: list[str] = []
    guidance_refs: list[str] = []
    report_for_prohibited_practices: list[ProhibitedPractice] = []
    legal_basis_spans: list[str] = Field(min_length=1)
    detail: str = ""

    @model_validator(mode="after")
    def _target_matches_relation_kind(self) -> NormRelation:
        has_rules = bool(self.target_rule_ids)
        has_norms = bool(self.target_norm_ids)
        has_external = bool(self.external_requirements)
        has_guidance = bool(self.guidance_refs)
        has_report_practices = bool(self.report_for_prohibited_practices)
        if self.kind is NormRelationKind.SUBJECT_TO_EXTERNAL_REQUIREMENTS:
            if has_rules or has_norms or has_guidance or has_report_practices or not has_external:
                raise ValueError(
                    "subject_to_external_requirements needs external_requirements "
                    "and no target rules"
                )
            if not self.detail.strip():
                raise ValueError("subject_to_external_requirements requires detail")
        elif self.kind in {
            NormRelationKind.CONDITIONAL_ON_NORMS,
            NormRelationKind.CARRIED_BY_NORMS,
            NormRelationKind.PARALLEL_NORMS,
            NormRelationKind.RELIES_ON_NORMS,
        }:
            if has_rules or has_external or has_guidance or has_report_practices or not has_norms:
                raise ValueError(
                    f"{self.kind.value} needs target_norm_ids and no rule or external targets"
                )
        elif self.kind is NormRelationKind.INTERPRETED_BY_COMMISSION_GUIDANCE:
            if has_rules or has_norms or has_external or has_report_practices or not has_guidance:
                raise ValueError("interpreted_by_commission_guidance needs guidance_refs only")
        elif self.kind is NormRelationKind.NATIONAL_LAW_REGULATION:
            if (
                has_rules
                or has_norms
                or has_external
                or has_guidance
                or not has_report_practices
                or not self.detail.strip()
            ):
                raise ValueError(
                    "national_law_regulation needs detail and report_for_prohibited_practices only"
                )
        elif self.kind in {
            NormRelationKind.UNRESOLVED_DEPENDENCY,
            NormRelationKind.MISSING_DEPENDENCY,
        }:
            if (
                has_rules
                or has_norms
                or has_external
                or has_guidance
                or has_report_practices
                or not self.detail.strip()
            ):
                raise ValueError(f"{self.kind.value} needs detail only")
        elif not has_rules or has_norms or has_external or has_guidance or has_report_practices:
            raise ValueError(
                f"{self.kind.value} needs target_rule_ids and no external requirements"
            )
        if len(self.target_rule_ids) != len(set(self.target_rule_ids)):
            raise ValueError("norm relation target_rule_ids must not contain duplicates")
        if len(self.target_norm_ids) != len(set(self.target_norm_ids)):
            raise ValueError("norm relation target_norm_ids must not contain duplicates")
        for name, values in (("guidance_refs", self.guidance_refs),):
            if len(values) != len(set(values)):
                raise ValueError(f"norm relation {name} must not contain duplicates")
        if len(self.external_requirements) != len(set(self.external_requirements)):
            raise ValueError("norm relation external_requirements must not contain duplicates")
        if len(self.report_for_prohibited_practices) != len(
            set(self.report_for_prohibited_practices)
        ):
            raise ValueError(
                "norm relation report_for_prohibited_practices must not contain duplicates"
            )
        return self


class CandidateDetectionChannel(StrEnum):
    """Why an extraction pass proposed a legal proposition.

    These observations are not substitutes for semantic review. In particular, shall_token
    preserves the token heuristic as a measurable baseline.
    """

    SEMANTIC_LEGAL_EFFECT = "semantic_legal_effect"
    SHALL_TOKEN = "shall_token"
    OTHER_MODAL = "other_modal"
    DEEMING_OR_CONSEQUENCE = "deeming_or_consequence"
    CROSS_REFERENCE_STRUCTURE = "cross_reference_structure"
    EXISTING_IMPLEMENTATION = "existing_implementation"


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
    qualifying_norm_ids: list[str] = []
    review: ReviewRecord

    @model_validator(mode="after")
    def _disposition_has_the_right_shape(self) -> TextReviewSegment:
        if self.end <= self.start:
            raise ValueError("segment end must be greater than start")
        linked_norm_ids = [*self.norm_ids, *self.qualifying_norm_ids]
        if self.disposition is SegmentDisposition.NORMATIVE and not linked_norm_ids:
            raise ValueError("normative segment requires at least one linked norm_id")
        if self.disposition is not SegmentDisposition.NORMATIVE and linked_norm_ids:
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


class NormActor(BaseModel):
    """A person or body to which the norm assigns a legal effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: ActorRole
    basis_segment_ids: list[NormativeSegmentId] = []

    @model_validator(mode="after")
    def _basis_spans_are_unique(self) -> NormActor:
        if len(self.basis_segment_ids) != len(set(self.basis_segment_ids)):
            raise ValueError("actor basis_segment_ids must not contain duplicates")
        return self

    @property
    def category(self) -> ActorCategory:
        """The actor's fixed classification from the single ActorRole catalogue."""
        return self.actor_ref.category


class NormTarget(BaseModel):
    """An object, activity, concept, or legal state to which the norm relates."""

    target_ref: str = Field(min_length=1)


class TemporalStatus(StrEnum):
    """How a temporal regime should be presented for a report date.

    A temporal status never suppresses a norm. In particular, UPCOMING duties stay visible so a
    reader can prepare for them before their application date.
    """

    ACTIVE = "active"
    UPCOMING = "upcoming"
    EXPIRED = "expired"
    CONDITIONAL_TIMING = "conditional_timing"


class TemporalRegime(BaseModel):
    """One source-backed application-time regime shared by one or more norms.

    The Regulation's general application date is normally one regime; transitional provisions and
    time-limited effects are separate regimes. The date and its legal basis live here once rather
    than being copied into every norm.
    """

    model_config = ConfigDict(extra="forbid")

    regime_id: str = Field(pattern=r"^AIA-TEMP-[A-Z0-9-]+$")
    application_start: date | None = None
    application_end: date | None = None
    timing_conditions: list[str] = []
    legal_basis_spans: list[NormativeSegmentId] = Field(min_length=1)

    @model_validator(mode="after")
    def _is_a_real_and_unambiguous_regime(self) -> TemporalRegime:
        if (
            self.application_start is None
            and self.application_end is None
            and not self.timing_conditions
        ):
            raise ValueError("temporal regime requires an application date or timing condition")
        if (
            self.application_start is not None
            and self.application_end is not None
            and self.application_end < self.application_start
        ):
            raise ValueError("temporal regime application_end must not precede application_start")
        if len(self.timing_conditions) != len(set(self.timing_conditions)):
            raise ValueError("temporal regime timing_conditions must not contain duplicates")
        if len(self.legal_basis_spans) != len(set(self.legal_basis_spans)):
            raise ValueError("temporal regime legal_basis_spans must not contain duplicates")
        return self

    def status_on(self, as_of_date: date) -> TemporalStatus:
        """Return a report label; never use timing to omit a norm from the report."""
        if self.application_start is not None and as_of_date < self.application_start:
            return TemporalStatus.UPCOMING
        if self.application_end is not None and as_of_date > self.application_end:
            return TemporalStatus.EXPIRED
        if self.timing_conditions:
            return TemporalStatus.CONDITIONAL_TIMING
        return TemporalStatus.ACTIVE


class ConditionGroup(BaseModel):
    """Explicit legal conjunction/disjunction, not an executable runtime predicate.

    Legacy prose conditions remain supported; no logical grouping is inferred from them.
    """

    model_config = ConfigDict(extra="forbid")

    operator: Literal["all_of", "any_of"]
    operands: list[str | ConditionGroup] = Field(min_length=2)

    @model_validator(mode="after")
    def _leaves_are_nonempty(self) -> ConditionGroup:
        if any(isinstance(item, str) and not item.strip() for item in self.operands):
            raise ValueError("condition operands must not be blank")
        return self


class Norm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    norm_id: str = Field(pattern=r"^AIA-NORM-[A-Z0-9-]+$")
    act_version_date: date
    kind: NormKind
    actors: list[NormActor] = []
    targets: list[NormTarget] = []
    action: str = Field(min_length=1)
    norm_text: str = Field(min_length=1)
    detection_channels: list[CandidateDetectionChannel] = Field(min_length=1)
    primary_spans: list[str] = Field(min_length=1)
    qualifier_spans: list[str] = []
    definition_spans: list[str] = []
    # Legacy source-span field. It currently also contains ordinary deadlines, so it remains
    # readable until each existing record is migrated to an application regime or another field.
    effective_date_spans: list[str] = []
    application_regime_id: str | None = Field(
        default=None, pattern=r"^AIA-TEMP-[A-Z0-9-]+$"
    )
    conditions: list[str | ConditionGroup] = []
    exceptions: list[str] = []
    mandatory_content: list[str] = []
    product_scope: ProductScope
    product_scope_reason: str = ""
    implementation_mode: ImplementationMode
    implementation_refs: list[str] = []
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
                + [segment for actor in self.actors for segment in actor.basis_segment_ids]
            )
        )

    @model_validator(mode="after")
    def _scope_and_implementation_are_explained(self) -> Norm:
        if not self.norm_text.strip():
            raise ValueError("norm_text must contain an exact enacted quotation")
        if not self.actors and not self.targets:
            raise ValueError("norm requires at least one actor or target")
        actor_refs = [actor.actor_ref for actor in self.actors]
        if len(actor_refs) != len(set(actor_refs)):
            raise ValueError("actors must not contain duplicate actor_ref values")
        target_refs = [target.target_ref for target in self.targets]
        if len(target_refs) != len(set(target_refs)):
            raise ValueError("targets must not contain duplicate target_ref values")
        if len(self.detection_channels) != len(set(self.detection_channels)):
            raise ValueError("detection_channels must not contain duplicates")
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
        if self.implementation_mode is ImplementationMode.NONE_REQUIRED:
            if not self.implementation_reason.strip():
                raise ValueError("none_required implementation requires a reason")
        if self.review.status is ReviewStatus.REJECTED:
            raise ValueError("rejected candidates belong in extraction history, not norm inventory")
        return self


class NormInventory(BaseModel):
    act_version_date: date
    norms: list[Norm] = []
    temporal_regimes: list[TemporalRegime] = []
    relations: list[NormRelation] = []
    interpretations: list[InterpretiveLink] = []

    def target_norm_ids_for(self, source_norm_id: str, kind: NormRelationKind) -> list[str]:
        """Return canonical norm targets for the given reviewed relation kind."""
        return [
            target_norm_id
            for relation in self.relations
            if relation.source_norm_id == source_norm_id and relation.kind is kind
            for target_norm_id in relation.target_norm_ids
        ]

    def external_requirements_for(self, source_norm_id: str) -> list[str]:
        """Return external requirements canonically linked from one norm."""
        return [
            requirement
            for relation in self.relations
            if (
                relation.source_norm_id == source_norm_id
                and relation.kind is NormRelationKind.SUBJECT_TO_EXTERNAL_REQUIREMENTS
            )
            for requirement in relation.external_requirements
        ]

    def source_norm_ids_for(self, target_norm_id: str, kind: NormRelationKind) -> list[str]:
        """Return canonical relation sources that name this norm as a target."""
        return [
            relation.source_norm_id
            for relation in self.relations
            if relation.kind is kind and target_norm_id in relation.target_norm_ids
        ]

    def parallel_norm_ids_for(self, norm_id: str) -> list[str]:
        for relation in self.relations:
            if relation.kind is NormRelationKind.PARALLEL_NORMS:
                members = [relation.source_norm_id, *relation.target_norm_ids]
                if norm_id in members:
                    return [member for member in members if member != norm_id]
        return []

    @model_validator(mode="after")
    def _ids_are_unique(self) -> NormInventory:
        norm_ids = [n.norm_id for n in self.norms]
        relation_ids = [relation.relation_id for relation in self.relations]
        interpretation_ids = [i.interpretation_id for i in self.interpretations]
        if len(norm_ids) != len(set(norm_ids)):
            raise ValueError("duplicate norm_id")
        regime_ids = [regime.regime_id for regime in self.temporal_regimes]
        if len(regime_ids) != len(set(regime_ids)):
            raise ValueError("duplicate temporal regime_id")
        unknown_regimes = sorted(
            {
                norm.application_regime_id
                for norm in self.norms
                if norm.application_regime_id is not None
            }
            - set(regime_ids)
        )
        if unknown_regimes:
            raise ValueError(f"norms reference unknown temporal regime(s): {unknown_regimes}")
        unused_regimes = sorted(
            set(regime_ids)
            - {
                norm.application_regime_id
                for norm in self.norms
                if norm.application_regime_id is not None
            }
        )
        if unused_regimes:
            raise ValueError(f"temporal regimes are not used by any norm: {unused_regimes}")
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("duplicate norm relation_id")
        unknown_relation_sources = sorted(
            {relation.source_norm_id for relation in self.relations} - set(norm_ids)
        )
        if unknown_relation_sources:
            raise ValueError(
                f"norm relations reference unknown source norm(s): {unknown_relation_sources}"
            )
        if len(interpretation_ids) != len(set(interpretation_ids)):
            raise ValueError("duplicate interpretation_id")
        return self


class NormativeCoverageBundle(BaseModel):
    """Both assurance artifacts after cross-file and source validation succeeds."""

    text_review: TextReviewInventory
    norm_inventory: NormInventory
    validated_documents: int
    validated_segments: int
    validated_norms: int
    runtime_integrated: Literal[False] = False
