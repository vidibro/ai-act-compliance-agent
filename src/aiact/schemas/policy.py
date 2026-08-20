"""The ruleset: individual provider obligations, their legal source, and how to check them.

A PolicySpec is loaded from data (derived from the EC Compliance Checker) — regulatory
movement lives in the data, never hard-coded here.
"""

from __future__ import annotations

import warnings
from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    CheckType,
    HighRiskRoute,
    ObligationStatus,
    RiskClass,
)


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

    applies_to_route: HighRiskRoute | None = None
    """WHICH of Art. 6's two doors this rule needs the use case to have come through, or None for
    the ordinary case where it does not care.

    None means NO CONDITION, not "neither" — Arts. 9-15 and 17-21 bind every high-risk system
    whichever door it came through, and that is most of the ruleset. Art. 43 is why the field
    exists: 43(3) governs an Annex I system and 43(1)-(2) an Annex III one, so a single rule would
    have to cite one of them at both."""

    applies_to_annex_iii_area: list[AnnexIIIArea] = []
    """WHICH Annex III areas this rule fires for. Empty is the ordinary case: no area condition.

    A non-empty list is a condition on the AREA and therefore also on the route — an Annex I system
    has no Annex III area, so it can never match one. Art. 43 again: 43(1) reaches Annex III point 1
    alone and 43(2) points 2 to 8, and until this field existed the spec carried 43(2) with the
    comment "employment is Annex III point 4" and fired it at biometrics too. A condition written in
    a comment is not a condition."""
    activation_condition: str | None = None
    """WHICH members of the role owe this, where the Act binds only some of them — stated plainly,
    in terms of the organisations concerned rather than of whoever is reading.

    The Regulation sometimes narrows a duty by a fact about the ORGANISATION rather than about the
    system. Art. 27 is the case: the fundamental rights impact assessment binds deployers that are
    bodies governed by public law or private entities providing public services, not deployers at
    large. Nothing in a system's documentation establishes that, and nothing in this ruleset can
    derive it — READ, NEVER DERIVED, the same discipline as Art. 6(1)(b) and Art. 2(4) in the
    cascade.

    IT NARROWS THE DUTY-HOLDER, NOT THE REPORT. Such a rule is still selected, still listed under
    its role, and still counted. The report describes what the Act requires of each role for this
    system; it is not addressed to one organisation, and dropping an obligation into a "might not
    apply" list would be the tool deciding on someone's behalf which of their duties to demote —
    the same error as omitting a role because no ruleset was written for it. What this field buys
    is that the obligation is stated WITH its condition rather than as an unqualified duty of every
    deployer."""

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
    def _area_and_route_agree(self) -> PolicyRule:
        """Naming Annex III areas already fixes the route, so a rule may not also claim Annex I.

        Not pedantry: such a rule could never fire — an Annex I use case carries no Annex III area —
        and a rule that never fires is indistinguishable in a report from an obligation nobody
        owes."""
        if self.applies_to_annex_iii_area and self.applies_to_route is HighRiskRoute.ANNEX_I:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: applies_to_annex_iii_area names areas but "
                f"applies_to_route is annex_i. An Annex I use case has no Annex III area, so this "
                f"rule could never activate."
            )
        return self

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
