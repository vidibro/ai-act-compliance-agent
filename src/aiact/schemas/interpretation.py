"""Non-binding interpretations that influence application behaviour.

Commission guidance never becomes enacted law by being supplied to a question or judge. These
types keep that boundary structural while making every behaviour-affecting use traceable to the
legal norm it interprets, the implementation target that consumes it, and the amount of source
context actually reviewed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from aiact.schemas.review import ReviewRecord


class InterpretiveEffect(StrEnum):
    CLARIFIES_TERM = "clarifies_term"
    NARROWS_SCOPE = "narrows_scope"
    EXPANDS_SCOPE = "expands_scope"
    DEFINES_EVIDENCE = "defines_evidence"
    DEFINES_MECHANISM = "defines_mechanism"
    RESOLVES_AMBIGUITY = "resolves_ambiguity"
    OTHER = "other"
    UNRESOLVED = "unresolved"


class GuidanceReviewScope(StrEnum):
    FULL_DOCUMENT = "full_document"
    SECTION = "section"
    PAGE_RANGE = "page_range"
    PASSAGE_WITH_CONTEXT = "passage_with_context"
    SNIPPET_ONLY = "snippet_only"
    UNRESOLVED = "unresolved"


class InterpretationTargetKind(StrEnum):
    CLASSIFICATION_QUESTION = "classification_question"
    ROLE_QUESTION = "role_question"
    POLICY_RULE = "policy_rule"
    GOLDEN_LABEL = "golden_label"
    OTHER = "other"


class InterpretationTarget(BaseModel):
    kind: InterpretationTargetKind
    target_id: str = Field(min_length=1)


class InterpretiveLink(BaseModel):
    """One reviewed use of non-binding guidance.

    `binding` is a literal false rather than a boolean convention: constructing a link that calls
    Commission interpretation binding is impossible.
    """

    interpretation_id: str = Field(pattern=r"^AIA-INT-[A-Z0-9-]+$")
    snippet_refs: list[str] = Field(min_length=1)
    norm_ids: list[str] = Field(min_length=1)
    targets: list[InterpretationTarget] = Field(min_length=1)
    effect: InterpretiveEffect
    effect_explanation: str = ""
    review_scope: GuidanceReviewScope
    review_scope_detail: str = ""
    binding: Literal[False] = False
    review: ReviewRecord

    @model_validator(mode="after")
    def _explain_open_ended_values(self) -> InterpretiveLink:
        if self.effect is InterpretiveEffect.OTHER and not self.effect_explanation.strip():
            raise ValueError("effect=other requires effect_explanation")
        if self.effect is InterpretiveEffect.UNRESOLVED and self.effect_explanation.strip():
            return self
        if (
            self.review_scope
            in {
                GuidanceReviewScope.SECTION,
                GuidanceReviewScope.PAGE_RANGE,
                GuidanceReviewScope.PASSAGE_WITH_CONTEXT,
            }
            and not self.review_scope_detail.strip()
        ):
            raise ValueError(f"review_scope={self.review_scope.value} requires review_scope_detail")
        return self
