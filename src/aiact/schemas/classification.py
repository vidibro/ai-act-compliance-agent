"""Classification state and result — mirrors the official EC AI Act Compliance Checker flow.

One deliberate deviation from the Commission's checker: it merges the profiling carve-back into
a single answer option ("None of the above / performs profiling"). We split it into two
independent nodes, because Art. 6(3) says the carve-back applies *notwithstanding* the
exemptions — so profiling must be evaluated on its own, before exemptions are considered.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator

from aiact.schemas.enums import AnnexIIIArea, RiskClass
from aiact.schemas.policy import LegalSource
from aiact.schemas.system import SystemUnderReview

Confidence = Literal["high", "medium", "low"]


class NodeAnswer(BaseModel):
    """Every classification decision must be evidence-backed and citable.

    `source` is required and has no default: an uncited node answer cannot be constructed."""

    value: Any  # narrow per node at the call site (bool, list[AnnexIIIArea], ...)
    reasoning: str
    evidence_quote: str | None = None  # short excerpt from the source doc
    evidence_chunk_id: str | None = None
    confidence: Confidence
    source: LegalSource


class UseCaseClassification(BaseModel):
    """Risk is decided PER USE CASE, not per system.

    The Commission is explicit: where a system covers several Annex III use cases and only
    some are high-risk, the Chapter 3 obligations apply ONLY to the high-risk use case, and
    the requirements are assessed against THAT intended purpose.

    So one product can hold several classifications at once. A multi-function HR tool might be:
      - CV parsing (field extraction only) -> not_high_risk, derogation (a)
      - candidate scoring                  -> high_risk, profiling carve-back
      - job-ad text generation             -> minimal, but Art. 50 transparency applies

    Profiling and derogation are decided HERE, not at system level — the same product can
    profile in one use case and not in another."""

    use_case_id: str  # "cv_parsing", "candidate_scoring"
    description: str  # what the system does in this use case
    annex_iii_area: AnnexIIIArea | None = None
    annex_iii_use_case: LegalSource | None = None  # e.g. Annex III(4)(a)
    performs_profiling: NodeAnswer | None = None  # OUR SPLIT NODE. Art. 6(3) carve-back.
    # Decided per use case. If true -> high_risk, and derogation is not even considered.
    derogation: NodeAnswer | None = None  # Art. 6(3)(a)-(d). Only evaluated when
    # performs_profiling is false.
    risk_class: RiskClass
    triggered_by: list[LegalSource]  # which articles/annex points drove this verdict
    reasoning: str
    confidence: Confidence

    @model_validator(mode="after")
    def _enforce_profiling_carve_back(self) -> UseCaseClassification:
        """Art. 6(3): NOTWITHSTANDING any derogation, an Annex III system is ALWAYS high-risk
        where it performs profiling of natural persons. Encode it so it cannot be violated by
        accident: profiling true => no derogation, and risk_class must be high_risk."""
        if self.performs_profiling is not None and self.performs_profiling.value is True:
            if self.derogation is not None:
                raise ValueError(
                    f"UseCaseClassification {self.use_case_id!r}: performs_profiling is true, "
                    f"so the Art. 6(3) carve-back applies and derogation must be None."
                )
            if self.risk_class != RiskClass.HIGH_RISK:
                raise ValueError(
                    f"UseCaseClassification {self.use_case_id!r}: performs_profiling is true, "
                    f"so risk_class must be high_risk (got {self.risk_class})."
                )
        return self


class ClassificationState(BaseModel):
    """System-level checks. These apply to the system as a whole, before we look at
    what it does in each individual use case."""

    system: SystemUnderReview
    is_ai_system: NodeAnswer | None = None  # Art. 3(1)
    actor_role: NodeAnswer | None = None  # Art. 3(3)
    in_eu_scope: NodeAnswer | None = None  # Art. 2
    is_excluded: NodeAnswer | None = None  # Art. 2
    prohibited_practices: NodeAnswer | None = None  # Art. 5  <- checked BEFORE high-risk
    is_safety_component: NodeAnswer | None = None  # Art. 6(1), Annex I
    annex_iii_areas: NodeAnswer | None = None  # Art. 6(2), Annex III
    transparency_triggers: NodeAnswer | None = None  # Art. 50 — checked independently of
    # the risk class; can apply to a minimal-risk system and a high-risk one alike
    use_cases: list[UseCaseClassification] = []  # the per-use-case work happens here


class ClassificationResult(BaseModel):
    """The classification verdict for the whole system, aggregated across its use cases."""

    use_cases: list[UseCaseClassification]
    overall_risk_class: RiskClass  # the most high-risk class across all use cases
    reasoning: str  # why this overall class, and which use case drove it
    triggered_by: list[LegalSource]
    confidence: Confidence
