"""Which obligations apply to a classified use case.

Deterministic and model-free: activation is a property of the ruleset (`applies_to_risk_class` or
`applies_to_transparency_duty`, `applies_to_role`, `applies_to_route`, `applies_to_annex_iii_area`,
`status`), not a judgement.
Only whether the documentation SATISFIES an active rule is a judgement, and that is the judge's job.

WHICH DOOR, WHICH AREA and — for one rule — WHETHER THE PROVIDER ROLE MOVED are conditions, not
decoration. Most obligations bind every high-risk
system alike, but a few name law that only reaches part of them — Art. 43 sends an Annex III point 1
system to a notified body, points 2 to 8 to internal control, and an Annex I system to its own
sectoral procedure. A rule that could not state that condition had to assume one area and cite its
law at every system, which is a confident wrong citation rather than a missing one.

Obligations attach per USE CASE, not per system. A product whose CV parsing is not_high_risk and
whose candidate scoring is high_risk owes Chapter III on the scoring use case alone, assessed
against that intended purpose — so selection runs per use case and the results are kept apart.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from aiact.schemas.classification import UseCaseClassification
from aiact.schemas.enums import (
    ActorRole,
    HighRiskRoute,
    ProviderReallocation,
    RiskClass,
    TransparencyDuty,
)
from aiact.schemas.policy import PolicyRule, PolicySpec


@dataclass(frozen=True)
class ActiveRules:
    """The obligations one use case must answer for, split by how they can be checked."""

    use_case_id: str
    role: ActorRole
    """WHOSE obligations these are. REQUIRED, with no default: a default would attribute an
    unattributed set to the provider, which is the one wrong answer that reads as plausible.

    Selection runs once per role and the results are kept apart. Art. 4 binds both, Arts. 9-21 the
    provider, Arts. 26-27 the deployer, and a report that merged them would hand each party duties
    it cannot discharge."""

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


def roles_with_rules(spec: PolicySpec) -> list[ActorRole]:
    """Every role the spec actually carries rules for, in `ActorRole` declaration order.

    DERIVED, never listed by hand. A hand-written list is a second place to keep in sync, and the
    failure it produces is silent: a role added to `spec.yaml` but missing from the list would never
    be selected for, so its rules would sit in the spec looking covered while activating for nobody.
    That is the failure the coverage ledger exists to prevent, one layer down — and the ledger now
    covers roles too: every `ActorRole` either has rules here or is listed in `scope-<version>.yaml`
    with a reason, enforced by a test. So a role missing from this list is a CI failure, never a
    silent omission from a report."""
    named = {role for rule in spec.rules for role in rule.applies_to_role}
    return [role for role in ActorRole if role in named]


def _route_of(use_case: UseCaseClassification) -> HighRiskRoute | None:
    """WHICH of Art. 6's doors this use case came through, or None where neither did.

    Annex I is checked FIRST because it is checked first in law: Art. 6(1) is an independent route
    and Art. 6(3) cannot derogate from it, so a system that is a certified safety component is an
    Annex I system whatever Annex III would have said about its purpose.

    Art. 6(1) is a conjunction, so a NAMED PRODUCT IS NOT THE ANNEX I ROUTE. A product whose
    manufacturer self-assesses fails condition (b), and the cascade carries it on to Annex III —
    where Art. 6(2) can make it high-risk by the other door. Reading the product alone would send
    such a use case down the sectoral conformity rule (`AIA-PO-A43-3`) instead of Art. 43(1)/(2)."""
    if use_case.high_risk_under_article_6_1:
        return HighRiskRoute.ANNEX_I
    if use_case.annex_iii_area is not None:
        return HighRiskRoute.ANNEX_III
    return None


def _route_matches(rule: PolicyRule, use_case: UseCaseClassification) -> bool:
    """A rule with no route condition fires whichever door was used — the ordinary case."""
    return rule.applies_to_route is None or rule.applies_to_route is _route_of(use_case)


def _tier_or_duty_matches(
    rule: PolicyRule,
    use_case: UseCaseClassification,
    duties: Sequence[TransparencyDuty],
) -> bool:
    """WHETHER this rule's activation condition is met — the tier for most rules, an Art. 50 duty
    for the few that name one.

    The two are alternatives, not filters applied in series, and the validator on `PolicyRule`
    guarantees a rule names exactly one. An Art. 50 rule fires on the duty ALONE, and the tier never
    narrows it — Art. 50(6) makes the Article ADDITIVE to Chapter III, so a high-risk system that
    generates content owes 50(2) on top of Arts. 9-21, and a minimal-risk one owes it with nothing
    else. What a high-risk scorer owes nothing under Art. 50 for is that it generates no content and
    holds no conversation; its tier has no part in that."""
    if rule.applies_to_transparency_duty:
        return any(duty in duties for duty in rule.applies_to_transparency_duty)
    return use_case.risk_class in rule.applies_to_risk_class


def _area_matches(rule: PolicyRule, use_case: UseCaseClassification) -> bool:
    """A rule that names Annex III areas fires only inside them.

    A use case with NO area — an Annex I system, or one whose area the run never established —
    matches no list, which is the safe direction: naming areas is how a rule says the law it cites
    is area-specific, and firing it outside them is what put Art. 43(2) on a biometrics system."""
    if not rule.applies_to_annex_iii_area:
        return True
    return use_case.annex_iii_area in rule.applies_to_annex_iii_area


def select_rules(
    spec: PolicySpec,
    use_case: UseCaseClassification,
    role: ActorRole,
    reallocation: ProviderReallocation | None = None,
    transparency_duties: Sequence[TransparencyDuty] = (),
) -> ActiveRules:
    """The obligations `role` owes for this use case, under its risk class.

    `reallocation` is the Art. 25 answer, and the ONE input here that is not a property of the
    classification. It exists because Art. 25(2) creates a duty that has no holder until the
    provider role has actually moved: the party that placed the system on the market and then
    stopped being its provider owes the new one cooperation and technical access. `None` — nothing
    moved, or the question went unanswered — leaves that rule unselected, because a duty asserted
    against a party the facts do not produce is an invented obligation rather than a cautious one.

    `transparency_duties` is the cascade's Art. 50 answer, and it activates the rules that gate on a
    duty instead of on a tier. It is a property of the SYSTEM rather than of one intended purpose —
    the cascade asks it once, at `assemble` — so where a classification holds several use cases the
    same duty is selected under each. Over-inclusive, and visibly so, which is the safe direction
    here: the alternative is guessing which purpose generates the content, and a duty filed under
    the wrong use case is one a reader looks for in the wrong document.

    **Art. 2** comes first, and it is the stronger case. Where the Regulation does not govern the
    system at all — military use, sole-purpose research, pre-market development, a natural person's
    own use, a free and open-source release — there are no obligations to select, not a reduced set.
    Distinct from the Section B limit below, where the system IS governed and owes Arts. 102-109.

    Risk class is not on its own sufficient. **Art. 2(2)**: where a system is high-risk under
    Art. 6(1) because it is a safety component of a product listed in Annex I **Section B** —
    vehicles, aviation, rail, marine — only Art. 6(1), Art. 60a and Arts. 102-112 apply. Chapter III
    does not. Such a system is genuinely high-risk and genuinely owes none of Art. 9-15, so
    selecting on the tier alone would raise every one of them against a provider the Regulation
    exempts.
    """
    # LOAD-BEARING, and it was not always: while every rule gated on a risk class, no rule listed
    # OUT_OF_SCOPE and the filter below emptied the set anyway. The Art. 50 rules gate on a DUTY and
    # name no risk class at all, so nothing downstream tests the tier for them — this return is the
    # only thing standing between an excluded system and a transparency obligation. Art. 2 withholds
    # the Regulation whole, Art. 50 included.
    # OUT_OF_SCOPE owes nothing; GPAI_MODEL owes plenty, but under Chapter V, which this ruleset
    # does not carry. Selecting Art. 6-track rules for a model would raise Chapter III duties
    # against a provider the Act never puts them on — and would hide the ones it does.
    if use_case.risk_class in (RiskClass.OUT_OF_SCOPE, RiskClass.GPAI_MODEL):
        return ActiveRules(use_case_id=use_case.use_case_id, role=role)

    # Art. 2(2) is exhaustive — "only Article 6(1), Article 60a and Articles 102 to 112 shall
    # apply" — so this withholds Art. 4 and Art. 50 from a Section B system as surely as it
    # withholds Chapter III, and from the deployer as surely as from the provider.
    #
    # It is also the widest exemption this module grants, which is why it is gated on the whole of
    # Art. 6(1) and not on the product. The paragraph opens "For AI systems classified as high-risk
    # AI systems in accordance with Article 6(1)": a self-assessed Section B product that is
    # high-risk under Art. 6(2) instead is not one, and returning empty for it would tell its
    # provider the Regulation exempts them from obligations they owe in full.
    if (
        use_case.high_risk_under_article_6_1
        and use_case.annex_i_product is not None
        and not use_case.annex_i_product.chapter_iii_applies
    ):
        return ActiveRules(use_case_id=use_case.use_case_id, role=role)

    active = [
        rule
        for rule in spec.rules
        if _tier_or_duty_matches(rule, use_case, transparency_duties)
        and role in rule.applies_to_role
        and _route_matches(rule, use_case)
        and _area_matches(rule, use_case)
        and (reallocation is not None or not rule.requires_provider_reallocation)
        and rule.status != "amended"
    ]
    # A rule carrying an `activation_condition` is NOT withheld here. The Act narrows some duties
    # to part of a role — Art. 27 binds deployers that are public bodies or private providers of
    # public services — and that narrowing is reported BESIDE the obligation, on the rule itself,
    # never by dropping it into a "might not apply" list. This report covers every role the Act
    # binds whoever is reading it; deciding on a reader's behalf which of their obligations to
    # demote is the same error as omitting a role for want of a ruleset.
    return ActiveRules(
        use_case_id=use_case.use_case_id,
        role=role,
        document_verifiable=tuple(
            r for r in active if r.status == "active" and r.document_verifiable
        ),
        not_document_verifiable=tuple(
            r for r in active if r.status == "active" and not r.document_verifiable
        ),
        postponed=tuple(r for r in active if r.status == "postponed"),
    )
