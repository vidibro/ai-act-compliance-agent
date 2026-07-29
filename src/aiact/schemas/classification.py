"""Classification state and result — mirrors the official EC AI Act Compliance Checker flow.

One deliberate deviation from the Commission's checker: it merges the profiling carve-back into
a single answer option ("None of the above / performs profiling"). We split it into two
independent nodes, because Art. 6(3) says the carve-back applies *notwithstanding* the
exemptions — so profiling must be evaluated on its own, before exemptions are considered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

from aiact.schemas.enums import AnnexIIIArea, RiskClass
from aiact.schemas.policy import GuidanceSource, LegalSource
from aiact.schemas.system import SystemUnderReview

Confidence = Literal["high", "medium", "low"]

AbstentionCause = Literal["description_silent", "reply_unusable"]
"""WHY a node declined — the two causes need different things from the reader, so a report that
merges them sends people to fix the wrong thing.

- `description_silent` — the documentation does not contain the fact. The user must supply it; the
  report should name which fact and which article needs it. Re-running unchanged will not help.
- `reply_unusable` — the model returned something unreadable (empty, malformed, unparseable). The
  documentation may be perfectly adequate. Re-running may well fix it, and telling the user to edit
  their document would be wrong."""

EVIDENCE_QUOTE_MAX = 300  # force citing a pinpoint excerpt, not dumping a section


def _check_quote_length(v: str | None) -> str | None:
    if v is not None and len(v) > EVIDENCE_QUOTE_MAX:
        raise ValueError(
            f"evidence_quote must be under {EVIDENCE_QUOTE_MAX} chars "
            f"(got {len(v)}) — cite a pinpoint excerpt, do not dump a section."
        )
    return v


@dataclass(frozen=True)
class ClassificationQuestion:
    """One question the cascade asks, with the provision it rests on and the shape of a valid
    answer — the INPUT half of the contract whose output half is ClassificationAnswer.

    Named for what it IS (a legal question) rather than where it happens to be used: the graph
    binds one of these to each node, but nothing about the question is graph-specific. `node_id` is
    the only graph coupling — the key the cascade looks it up by, and what an answer carries back.

    A plain frozen dataclass, not a BaseModel: it is authored in code as a literal constant
    (see graph/classify.py QUESTIONS), never parsed from user input, so there is nothing to
    validate at a trust boundary."""

    node_id: str
    source: LegalSource
    text: str  # the question itself, put to a brain verbatim
    answer_type: str  # "bool" | "annex_area" | "derogation" — the shape a valid answer takes
    context: str = ""
    """The VERBATIM enacted text of the cited provision, for the brain to reason against.

    Empty by default so the deterministic path needs no file IO; `load_questions()` fills it from
    the article/annex store. A model must never answer "which Annex III area is this?" from its own
    memory of the Annex — the same rule that governs the obligation `requirement` fields."""

    guidance_context: str = ""
    """VERBATIM Commission guidance for this question — the SAME anti-memory rule as `context`, one
    level up. Where the enacted text leaves a question open (e.g. does Art. 5(1)(f) 'workplace'
    cover hiring?), a model answering from `context` alone can only GUESS; the answer isn't in the
    Act. So the authoritative interpretation is supplied here, labelled non-binding, rather than
    left to the model's memory. Filled by `load_questions()`; empty where no guidance applies."""

    guidance_sources: tuple[GuidanceSource, ...] = ()
    """Citations for whatever is in `guidance_context`, carried onto the answer so a verdict reached
    with guidance in context can say so. Non-binding by construction (see GuidanceSource)."""


class ClassificationAnswer(BaseModel):
    """Every classification decision must be evidence-backed and citable.

    `source` is required and has no default: an uncited node answer cannot be constructed."""

    value: Any  # narrow per node at the call site (bool, list[AnnexIIIArea], ...)
    reasoning: str
    evidence_quote: str | None = None  # short excerpt from the source doc
    evidence_chunk_id: str | None = None
    confidence: Confidence
    source: LegalSource
    node_id: str | None = None  # which cascade question produced this (see graph/classify.py)
    abstained_because: AbstentionCause | None = None  # set only when the node declined to answer
    guidance_sources: list[GuidanceSource] = []  # non-binding guidance that was in context for
    # this node — present so the verdict can record it rested on Commission interpretation, not law

    _quote_length = field_validator("evidence_quote")(_check_quote_length)


class ClassificationEvidence(BaseModel):
    """WHY a use case landed in its risk class, in the two halves that make a verdict auditable:
    the PROVISION that applies, and the WORDS IN THE DOCUMENTATION that made it apply.

    `triggered_by` pairs each citation with the words that triggered it. A bare list of provisions
    would say which article drove the verdict but not what in the documentation made it apply,
    leaving a reader unable to check the reasoning against the source text.

    `source` is required and has no default, for the same reason it is on ClassificationAnswer."""

    source: LegalSource
    node_id: str | None = None  # the cascade question that produced it ("profiling", ...)
    evidence_quote: str | None = None  # verbatim span of the DOCUMENTATION (not of the law)
    evidence_chunk_id: str | None = None
    reasoning: str | None = None  # the node's own one-line justification
    abstained_because: AbstentionCause | None = None  # travels through so the report can say
    # WHICH fact the documentation was missing, rather than only that something was inconclusive
    guidance: list[GuidanceSource] = []  # NON-BINDING Commission interpretation this rested on,
    # kept distinct from `source` (enacted law) so a reader can tell the two apart

    _quote_length = field_validator("evidence_quote")(_check_quote_length)

    @classmethod
    def from_answer(cls, answer: ClassificationAnswer) -> ClassificationEvidence:
        """Carry a node's answer through to the verdict without losing its evidence — including any
        non-binding guidance that was in context when the answer was reached."""
        return cls(
            source=answer.source,
            node_id=answer.node_id,
            evidence_quote=answer.evidence_quote,
            evidence_chunk_id=answer.evidence_chunk_id,
            reasoning=answer.reasoning,
            abstained_because=answer.abstained_because,
            guidance=list(answer.guidance_sources),
        )


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
    performs_profiling: ClassificationAnswer | None = None  # OUR SPLIT NODE. Art. 6(3) carve-back.
    # Decided per use case. If true -> high_risk, and derogation is not even considered.
    derogation: ClassificationAnswer | None = None  # Art. 6(3)(a)-(d). Only evaluated when
    # performs_profiling is false.
    risk_class: RiskClass
    triggered_by: list[ClassificationEvidence]  # which provisions drove it, and on what evidence
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
    is_ai_system: ClassificationAnswer | None = None  # Art. 3(1)
    actor_role: ClassificationAnswer | None = None  # Art. 3(3)
    in_eu_scope: ClassificationAnswer | None = None  # Art. 2
    is_excluded: ClassificationAnswer | None = None  # Art. 2
    prohibited_practices: ClassificationAnswer | None = None  # Art. 5  <- checked BEFORE high-risk
    is_safety_component: ClassificationAnswer | None = None  # Art. 6(1), Annex I
    annex_iii_areas: ClassificationAnswer | None = None  # Art. 6(2), Annex III
    transparency_triggers: ClassificationAnswer | None = None  # Art. 50 — checked independently of
    # the risk class; can apply to a minimal-risk system and a high-risk one alike
    use_cases: list[UseCaseClassification] = []  # the per-use-case work happens here


class ClassificationResult(BaseModel):
    """The classification verdict for the whole system, aggregated across its use cases."""

    use_cases: list[UseCaseClassification]
    overall_risk_class: RiskClass  # the most high-risk class across all use cases
    reasoning: str  # why this overall class, and which use case drove it
    triggered_by: list[ClassificationEvidence]
    confidence: Confidence
    transparency: ClassificationAnswer | None = None
    """Art. 50 — a SEPARATE AXIS from the risk tier, deliberately not folded into it. A minimal-risk
    text generator and a high-risk chatbot can both owe transparency, and a high-risk system may owe
    none. It is therefore answered for every classification and reported beside the risk class —
    never as an input to it."""

    @property
    def guidance_sources(self) -> list[GuidanceSource]:
        """Every non-binding guidance citation any verdict here rested on, de-duplicated by
        snippet_ref. A report reader uses this to see whether the classification leaned on
        Commission interpretation rather than enacted law alone."""
        seen: dict[str, GuidanceSource] = {}
        for evidence in self.triggered_by:
            for g in evidence.guidance:
                seen.setdefault(g.snippet_ref, g)
        return list(seen.values())

    @property
    def rests_on_guidance(self) -> bool:
        """True when the verdict leaned on non-binding Commission interpretation — the signal a
        report must surface, because such a verdict is weaker than one resting on enacted law."""
        return bool(self.guidance_sources)
