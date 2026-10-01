"""Classification state and result — mirrors the official EC AI Act Compliance Checker flow.

What the cascade's answers ADD UP TO: which provision drove a verdict, what one use case is, and
the risk class for the system. The answers themselves are `schemas.question`, which lives apart
because the gap layer asks questions too — nothing about a Question or an Answer is specific to
classification, and naming that shape after this layer would say it was.

One deliberate deviation from the Commission's checker: it merges the profiling carve-back into
a single answer option ("None of the above / performs profiling"). We split it into two
independent nodes, because Art. 6(3) says the carve-back applies *notwithstanding* the
exemptions — so profiling must be evaluated on its own, before exemptions are considered.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

from pydantic import BaseModel, field_validator, model_validator

from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    AnnexIProduct,
    OpenSourceRelease,
    ProhibitedPractice,
    RiskClass,
    SystemicRisk,
    TransparencyDuty,
)
from aiact.schemas.policy import GuidanceSource, LegalSource
from aiact.schemas.question import (
    AbstentionCause,
    Answer,
    Confidence,
    _check_quote_length,
)

_E = TypeVar("_E", bound=StrEnum)


class ClassificationEvidence(BaseModel):
    """WHY a use case landed in its risk class, in the two halves that make a verdict auditable:
    the PROVISION that applies, and the WORDS IN THE DOCUMENTATION that made it apply.

    `triggered_by` pairs each citation with the words that triggered it. A bare list of provisions
    would say which article drove the verdict but not what in the documentation made it apply,
    leaving a reader unable to check the reasoning against the source text.

    `source` is required and has no default, for the same reason it is on Answer."""

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
    def from_answer(cls, answer: Answer) -> ClassificationEvidence:
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
    annex_i_product: AnnexIProduct | None = None
    """Art. 6(1)(a) ALONE — the product family the cascade named, whether or not Art. 6(1) went on
    to fire. Condition (a) is half of a conjunction, so this field does not on its own say the use
    case is high-risk by the Annex I route: read `high_risk_under_article_6_1` for that. Carried
    because a named product is worth reporting either way, and because Art. 2(2) makes the SECTION
    decide what is owed once Art. 6(1) HAS fired."""

    third_party_assessment: Answer | None = None
    """Art. 6(1)(b), the other half. Recorded beside (a) because every consumer of the Annex I
    route needs BOTH: Art. 2(2) withholds Chapter III from a system "classified as high-risk in
    accordance with Article 6(1)", and Art. 113(c)(ii) dates one "classified as high-risk pursuant
    to Article 6(1) and Annex I". A product named under (a) that self-assesses is neither — the
    cascade carries it on to Annex III, where it can be high-risk under Art. 6(2) and owe
    Chapter III in full."""

    systemic_risk: Answer | None = None
    """Art. 51(1) — whether the description STATES that this general-purpose AI model is one with
    systemic risk. Asked of a model and of nothing else, so `None` on every Art. 6-track use case.

    IT NARROWS NOTHING. Every Art. 55 rule is selected for every model whatever this says, and each
    carries the condition itself; what this decides is what the report tells the reader about which
    side of the Art. 51 line their own document falls on. Withholding four obligations on a model's
    reading of a compute figure would be a clearance, and a clearance is the one error direction
    this project does not accept — the same reasoning `deployer_type` records for Art. 27."""

    gpai_open_source_release: Answer | None = None
    """Arts. 53(2) and 54(6) — whether the release meets the open-source carve-out on all four
    limbs. Asked of a model, and read WITH `systemic_risk`, never alone: both carve-outs are
    disapplied for a model with systemic risk, so a fully open release lifts nothing until the
    Art. 51 line is answered too. Narrows nothing, for the reason above."""

    annex_iii_area: AnnexIIIArea | None = None
    annex_iii_use_case: LegalSource | None = None  # e.g. Annex III(4)(a)
    performs_profiling: Answer | None = None  # OUR SPLIT NODE. Art. 6(3) carve-back.
    # Decided per use case. If true -> high_risk, and derogation is not even considered.
    derogation: Answer | None = None  # Art. 6(3)(a)-(d). Only evaluated when
    # performs_profiling is false.
    poses_significant_risk: Answer | None = None
    """Art. 6(3), first subparagraph. The OTHER half of the derogation test, and the half that is
    easy to lose: the paragraph exempts a system only where it poses no significant risk of harm —
    "including by not materially influencing the outcome of decision making" — AND a condition under
    (a)-(d) is met. Recorded separately from `derogation` because a use case can satisfy a condition
    and still be high-risk, and a report that showed only the condition would make that verdict
    look like an error."""

    risk_class: RiskClass
    triggered_by: list[ClassificationEvidence]  # which provisions drove it, and on what evidence
    reasoning: str
    confidence: Confidence

    @property
    def high_risk_under_article_6_1(self) -> bool:
        """Whether Art. 6(1) is the door this use case came through — BOTH conditions, not (a).

        THE ONE TEST FOR EVERY ART. 6(1) CONSEQUENCE, and there are three: Art. 2(2) withholds
        Chapter III from a Section B system, Art. 113(c) dates Chapter III to 2 August 2028 rather
        than 2 December 2027, and `HighRiskRoute.ANNEX_I` selects the sectoral conformity rule over
        Art. 43(1)/(2). All three are keyed on classification "in accordance with Article 6(1)", so
        all three read this and none reads the product alone.

        Answering (b) `false` is not an exit from the cascade — Art. 6(3) cannot derogate from
        Art. 6(1), but nothing stops Art. 6(2) from reaching the same system through Annex III. Such
        a use case is high-risk, carries an Annex I product, and owes Chapter III entire."""
        return (
            self.annex_i_product is not None
            and self.third_party_assessment is not None
            and self.third_party_assessment.value is True
        )

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

    @model_validator(mode="after")
    def _enforce_derogation_conjunction(self) -> UseCaseClassification:
        """Art. 6(3) exempts on BOTH limbs or on neither: a condition under (a)-(d) AND no
        significant risk of harm. Encoded here for the same reason the carve-back above is — the
        cascade could route this wrong, and a wrong NOT_HIGH_RISK is the direction that costs a
        provider the whole of Chapter III."""
        if self.risk_class != RiskClass.NOT_HIGH_RISK:
            return self
        if self.derogation is None or self.derogation.value is None:
            raise ValueError(
                f"UseCaseClassification {self.use_case_id!r}: not_high_risk is reached only by "
                f"Art. 6(3), so a condition under (a)-(d) must be named."
            )
        if self.poses_significant_risk is None or self.poses_significant_risk.value is not False:
            raise ValueError(
                f"UseCaseClassification {self.use_case_id!r}: an Art. 6(3)(a)-(d) condition is "
                f"met, but the paragraph also requires that the system pose no significant risk "
                f"of harm. That must be answered false, not left open."
            )
        return self


class ClassificationResult(BaseModel):
    """The classification verdict for the whole system, aggregated across its use cases."""

    use_cases: list[UseCaseClassification]
    overall_risk_class: RiskClass  # the most high-risk class across all use cases
    reasoning: str  # why this overall class, and which use case drove it
    triggered_by: list[ClassificationEvidence]
    confidence: Confidence

    answers: list[Answer] = []
    """EVERY question the cascade asked, in the order it asked them — not only the deciding ones.

    `triggered_by` is the subset that fixed the class, and on its own it loses most of the
    assessment: a use case can be cleared under Art. 2, cleared under Art. 5 and ruled out of
    Annex I, and a result carrying only the Annex III and profiling answers shows none of that
    work. Which questions were PUT is also the only way to tell a node that answered "no" from one
    the cascade never reached, and those mean entirely different things to a reader."""
    transparency: Answer | None = None
    """Art. 50 — a SEPARATE AXIS from the risk tier, deliberately not folded into it. A minimal-risk
    text generator and a high-risk chatbot can both owe transparency, and a high-risk system may owe
    none. It is therefore answered for every classification and reported beside the risk class —
    never as an input to it."""

    @property
    def prohibited_practice(self) -> ProhibitedPractice | None:
        """WHICH point of Art. 5(1) banned the practice, or None where none did.

        Read off the cascade's own answers rather than stored again, so it cannot disagree with the
        verdict it came from. A reader needs the point and not just the tier: Art. 5's points do not
        all begin to apply on the same day any more, so `prohibited` alone no longer settles whether
        a practice is banned NOW — see `ProhibitedPractice.applies_from`."""
        for answer in self.answers:
            if answer.node_id == "prohibited" and isinstance(answer.value, ProhibitedPractice):
                return answer.value
        return None

    @property
    def stated_systemic_risk(self) -> SystemicRisk | None:
        """Art. 51(1) as the documentation answered it, or None where the question was not put.

        Narrowed by TYPE, as every other read of an Answer is: only a recognised member is a
        finding. `None` here means "no model was classified", not "no systemic risk" — the two
        readings are sixteen obligations apart."""
        return self._model_answer("systemic_risk", SystemicRisk)

    @property
    def stated_gpai_open_source_release(self) -> OpenSourceRelease | None:
        """Arts. 53(2) and 54(6) as the documentation answered them, or None where not put."""
        return self._model_answer("gpai_open_source_release", OpenSourceRelease)

    def _model_answer(self, node_id: str, kind: type[_E]) -> _E | None:
        """The value of a Chapter V gate answer, from whichever use case carries it.

        Read off the use cases rather than stored again, for the reason `prohibited_practice` is:
        a second copy could disagree with the verdict it came from. A model classification holds
        exactly one use case, so "whichever" is "the one"."""
        for use_case in self.use_cases:
            answer = getattr(use_case, node_id, None)
            if answer is not None and isinstance(answer.value, kind):
                return answer.value
        return None

    @property
    def transparency_duties(self) -> list[TransparencyDuty]:
        """The Art. 50 duties this system owes, in paragraph order. Empty where none attach."""
        value = self.transparency.value if self.transparency is not None else None
        duties = [d for d in value if isinstance(d, TransparencyDuty)] if value else []
        return sorted(duties, key=lambda d: (d.paragraph, d.value))

    @property
    def transparency_duties_by_role(self) -> dict[ActorRole, list[TransparencyDuty]]:
        """The same duties split by WHO owes them — the shape a report renders from.

        Art. 50(1) and (2) bind the provider, (3) and (4) the deployer, and the split is not
        cosmetic: they are discharged in different documents by different parties. A report listing
        them as one block hands a provider duties it cannot discharge and leaves the deployer's
        unattributed. Roles with no duty are absent rather than present-and-empty, so a caller
        iterating this never renders an empty heading."""
        by_role: dict[ActorRole, list[TransparencyDuty]] = {}
        for duty in self.transparency_duties:
            by_role.setdefault(duty.owed_by, []).append(duty)
        return by_role

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
