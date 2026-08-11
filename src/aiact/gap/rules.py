"""Which obligations apply to a classified use case.

Deterministic and model-free: activation is a property of the ruleset (`applies_to_risk_class`,
`applies_to_role`, `status`), not a judgement. Only whether the documentation SATISFIES an active
rule is a judgement, and that is the judge's job.

Obligations attach per USE CASE, not per system. A product whose CV parsing is not_high_risk and
whose candidate scoring is high_risk owes Chapter III on the scoring use case alone, assessed
against that intended purpose — so selection runs per use case and the results are kept apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aiact.schemas.classification import UseCaseClassification
from aiact.schemas.enums import ActorRole
from aiact.schemas.policy import PolicyRule, PolicySpec


@dataclass(frozen=True)
class ActiveRules:
    """The obligations one use case must answer for, split by how they can be checked."""

    use_case_id: str
    document_verifiable: tuple[PolicyRule, ...] = ()
    """Checkable against the technical documentation. These reach the judge."""

    not_document_verifiable: tuple[PolicyRule, ...] = ()
    """Process and administrative obligations of the provider ORGANISATION — a quality management
    system, a registration in the EU database, a duty to cooperate. They apply, but a technical file
    cannot evidence them, so they are reported as outstanding confirmations rather than gaps."""

    postponed: tuple[PolicyRule, ...] = field(default=())
    """Adopted but not yet applicable. Reported so a provider can prepare, never a gap."""

    @property
    def all_rules(self) -> tuple[PolicyRule, ...]:
        return self.document_verifiable + self.not_document_verifiable + self.postponed


def select(spec: PolicySpec, use_case: UseCaseClassification, role: ActorRole) -> ActiveRules:
    """The obligations `role` owes for this use case, under its risk class.

    Risk class is not on its own sufficient. **Art. 2(2)**: where a system is high-risk under
    Art. 6(1) because it is a safety component of a product listed in Annex I **Section B** —
    vehicles, aviation, rail, marine — only Art. 6(1), Arts. 102-109 and Art. 112 apply. Chapter III
    does not. Such a system is genuinely high-risk and genuinely owes none of Art. 9-15, so
    selecting on the tier alone would raise every one of them against a provider the Regulation
    exempts.
    """
    if use_case.annex_i_product is not None and not use_case.annex_i_product.chapter_iii_applies:
        return ActiveRules(use_case_id=use_case.use_case_id)

    active = [
        rule
        for rule in spec.rules
        if use_case.risk_class in rule.applies_to_risk_class
        and role in rule.applies_to_role
        and rule.status != "amended"
    ]
    return ActiveRules(
        use_case_id=use_case.use_case_id,
        document_verifiable=tuple(
            r for r in active if r.status == "active" and r.document_verifiable
        ),
        not_document_verifiable=tuple(
            r for r in active if r.status == "active" and not r.document_verifiable
        ),
        postponed=tuple(r for r in active if r.status == "postponed"),
    )
