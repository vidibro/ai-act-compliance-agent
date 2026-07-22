"""The ruleset: individual provider obligations, their legal source, and how to check them.

A PolicySpec is loaded from data (derived from the EC Compliance Checker) — regulatory
movement lives in the data, never hard-coded here.
"""

from __future__ import annotations

import warnings
from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from aiact.schemas.enums import ActorRole, CheckType, ObligationStatus, RiskClass


class LegalSource(BaseModel):
    """A pinpoint citation into a legal instrument. Carried by every verdict in the system so
    that no assessment can exist without pointing at the article it rests on."""

    instrument: str  # "Regulation (EU) 2024/1689"
    article: int | None = None
    paragraph: int | None = None
    point: str | None = None  # "a", "b", ...
    annex: str | None = None  # "III", "IV"
    annex_point: str | None = None  # "4(a)"
    act_version_date: date  # pinned snapshot — REQUIRED for reproducibility
    url: str | None = None  # canonical location of the cited provision — lets a future
    # rule-refresh tool re-fetch the verbatim text and diff it against a new Act version


class GuidanceSource(BaseModel):
    """A pinpoint citation into NON-BINDING interpretive guidance (a Commission Communication).

    Deliberately a DIFFERENT type from LegalSource, and never merged with it. A verdict that rests
    on the Commission's *interpretation* is not the same as one that rests on *enacted law*, and a
    compliance reader must be able to tell them apart — the Court of Justice of the EU is the only
    authoritative interpreter. `binding` is False by construction (a validator forbids True), so a
    'binding guidance source' cannot be built by accident."""

    issuer: str  # "European Commission"
    reference: str  # "C(2025) 5052 final"
    snippet_ref: str  # "C-2025-5052/workplace-covers-recruitment" — id into the guidance store
    locator: str  # "paragraph (254), p. 86"
    topic: str = ""  # human-readable summary of what the passage says
    binding: bool = False
    url: str | None = None

    @field_validator("binding")
    @classmethod
    def _guidance_is_never_binding(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "GuidanceSource.binding must be False — Commission guidance is non-binding "
                "interpretation; enacted law is cited with LegalSource, not this."
            )
        return v


class PolicyRule(BaseModel):
    """One obligation the documentation is checked against."""

    rule_id: str  # "AIA-HR-A06" — stable, human-readable
    requirement: str  # the obligation, in the Commission's own wording
    source: LegalSource
    applies_to_risk_class: list[RiskClass]
    applies_to_role: list[ActorRole]
    obligation_status: ObligationStatus
    check_type: CheckType
    evidence_expected: str  # what in the documentation would satisfy this
    document_verifiable: bool  # see model_validator below
    effective_date: date | None = None
    status: Literal["active", "postponed", "amended"]
    # "postponed": adopted but not yet applicable (e.g. Annex III obligations whose
    # application date was pushed back). Regulatory movement lives in DATA, not in code.
    amended_by: str | None = None

    @model_validator(mode="after")
    def _warn_substance_but_not_document_verifiable(self) -> PolicyRule:
        """A substance check that isn't document-verifiable is almost always a modelling slip:
        substance verdicts (including INADEQUATE) are drawn FROM the documentation, so a rule
        that demands substance yet claims it can't be seen in the docs contradicts itself.
        Warn rather than raise — the spec author may have a deliberate reason."""
        if self.check_type == CheckType.SUBSTANCE and not self.document_verifiable:
            warnings.warn(
                f"PolicyRule {self.rule_id!r}: check_type=substance but "
                f"document_verifiable=False — a substance judgement is drawn from the "
                f"documentation, so this pairing is likely a mistake.",
                stacklevel=2,
            )
        return self


class PolicySpec(BaseModel):
    """The full loaded ruleset for one pinned version of the Regulation."""

    spec_version: str
    act_version_date: date
    source_note: str  # provenance: derived from EC Compliance Checker
    rules: list[PolicyRule]
