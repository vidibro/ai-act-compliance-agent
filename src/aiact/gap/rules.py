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
from datetime import date

from aiact.schemas.classification import UseCaseClassification
from aiact.schemas.enums import (
    ActorRole,
    HighRiskRoute,
    ProhibitedPractice,
    ProviderReallocation,
    RealWorldTesting,
    RiskClass,
    TransparencyDuty,
)
from aiact.schemas.norm import TemporalStatus
from aiact.schemas.policy import PolicyRule, PolicyRuleset


@dataclass(frozen=True)
class TimingNotice:
    """One selected rule whose date is in the future or turns on an unsettled route."""

    rule: PolicyRule
    status: TemporalStatus
    route: HighRiskRoute | None
    application_date: date | None
    legal_basis_spans: tuple[str, ...]


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

    upcoming: tuple[TimingNotice, ...] = ()
    """Selected duties with a known future application date. The document-verifiable ones are
    judged and reported with that date; the rest are listed with it."""

    timing_unresolved: tuple[TimingNotice, ...] = ()
    """Selected duties whose legal route has not yet been classified; reported, never judged."""

    @property
    def all_rules(self) -> tuple[PolicyRule, ...]:
        return (
            self.document_verifiable
            + self.not_document_verifiable
            + self.postponed
            + tuple(item.rule for item in self.upcoming)
            + tuple(item.rule for item in self.timing_unresolved)
        )


def roles_with_rules(spec: PolicyRuleset) -> list[ActorRole]:
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


def route_of(use_case: UseCaseClassification) -> HighRiskRoute | None:
    """WHICH of Art. 6's doors this use case came through, or None where neither did.

    Annex I is checked FIRST because it is checked first in law: Art. 6(1) is an independent route
    and Art. 6(3) cannot derogate from it, so a system that is a certified safety component is an
    Annex I system whatever Annex III would have said about its purpose.

    Art. 6(1) is a conjunction, so a NAMED PRODUCT IS NOT THE ANNEX I ROUTE. A product whose
    manufacturer self-assesses fails condition (b), and the cascade carries it on to Annex III —
    where Art. 6(2) can make it high-risk by the other door. Reading the product alone would send
    such a use case down the sectoral conformity rule (`AIA-RULE-PO-A43-3`) instead of
    Art. 43(1)/(2)."""
    if use_case.high_risk_under_article_6_1:
        return HighRiskRoute.ANNEX_I
    if use_case.annex_iii_area is not None:
        return HighRiskRoute.ANNEX_III
    return None


def _route_matches(rule: PolicyRule, use_case: UseCaseClassification) -> bool:
    """A rule with no route condition fires whichever door was used — the ordinary case."""
    return rule.applies_to_route is None or rule.applies_to_route is route_of(use_case)


def _timing_notice(
    spec: PolicyRuleset, rule: PolicyRule, use_case: UseCaseClassification, as_of_date: date
) -> TimingNotice | None:
    """Resolve a fully migrated rule's canonical norm timing for this classified use case."""
    regime = spec.temporal_regime_for(rule)
    if regime is None:
        return None
    route = route_of(use_case)
    status = regime.status_on(as_of_date, route)
    if status not in {TemporalStatus.UPCOMING, TemporalStatus.CONDITIONAL_TIMING}:
        return None
    application_date = regime.application_start
    if route is not None:
        application_date = next(
            (item.application_start for item in regime.application_routes if item.route is route),
            application_date,
        )
    return TimingNotice(
        rule=rule,
        status=status,
        route=route,
        application_date=application_date,
        legal_basis_spans=tuple(regime.legal_basis_spans),
    )


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
    holds no conversation; its tier has no part in that.

    ONE TIER IS NOT A TIER AT ALL, and it is the exception. Art. 50 binds providers and deployers of
    AI SYSTEMS — 50(2) says so in terms, "providers of AI systems, including general-purpose AI
    systems" — and Art. 3(63) makes a general-purpose AI MODEL a different thing from the Art. 3(66)
    system BUILT ON one. GPAI_MODEL is the tier for the model, so no Art. 50 duty reaches it. The
    tier cannot do this work through `applies_to_risk_class`, because an Art. 50 rule names no risk
    class at all: the duty rules apply across every tier by design, and a model is the one
    classification that is not a tier of system."""
    if rule.applies_to_transparency_duty:
        if use_case.risk_class is RiskClass.GPAI_MODEL:
            return False
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


def _practice_matches(rule: PolicyRule, practice: ProhibitedPractice | None) -> bool:
    """A rule that names an Art. 5(1) practice fires only for that practice.

    Empty list is no condition, which is every rule outside Art. 5. A rule that names one reaches
    the LAWFUL BRANCH of a prohibition — Art. 5(1)(h) bans real-time remote biometric
    identification for law enforcement "unless and in so far as such use is strictly necessary",
    and a deployer operating under an Art. 5(5) national authorisation still owes Art. 5(2), (3)
    and (4). A classification with no practice matches no list, which keeps those duties off every
    system that is not on that branch."""
    if not rule.applies_to_prohibited_practice:
        return True
    return practice in rule.applies_to_prohibited_practice


def _testing_matches(rule: PolicyRule, answer: RealWorldTesting | None) -> bool:
    """A rule that depends on the Art. 60 route fires unless the description rules the route out.

    THE OPPOSITE DEFAULT TO ART. 25, and the difference is which way silence cuts. A reallocation
    that has not been established did not happen, and asserting Art. 25(2) would invent a party.
    Here the party is this system's provider, and what is uncertain is whether they are running a
    trial — something a technical file has no reason to mention either way. So `NOT_STATED` selects
    and only `NONE` withholds, which is how the cascade already treats Art. 2(1): a document that
    never addresses a question has not answered it in the reader's favour.

    `None` — the question was not put, because the system is not high-risk — withholds too. Art. 60
    governs high-risk systems alone, so there is nothing for the route to be elected on."""
    if not rule.requires_real_world_testing:
        return True
    return answer is not None and answer is not RealWorldTesting.NONE


def select_rules(
    spec: PolicyRuleset,
    use_case: UseCaseClassification,
    role: ActorRole,
    reallocation: ProviderReallocation | None = None,
    transparency_duties: Sequence[TransparencyDuty] = (),
    real_world_testing: RealWorldTesting | None = None,
    prohibited_practice: ProhibitedPractice | None = None,
    as_of_date: date | None = None,
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
    # OUT_OF_SCOPE owes nothing under this Regulation, so there is no set to build. GPAI_MODEL is
    # DELIBERATELY NOT HERE: it owes Chapter V, and the separation is done by the rules themselves
    # — every Art. 6-track rule names a tier that a model is not, and every Chapter V rule names
    # `gpai_model` and nothing else. Returning early for a model would hide the duties it does owe,
    # which is the failure this tier exists to prevent. The Art. 50 rules name no tier and so are
    # separated one layer down, in `_tier_or_duty_matches`.
    if use_case.risk_class is RiskClass.OUT_OF_SCOPE:
        return ActiveRules(use_case_id=use_case.use_case_id, role=role)

    # Art. 2(2)'s first sentence is a closed list — "only Article 6(1), Article 60a and Articles 102
    # to 112 shall apply" — so this withholds Art. 4 and Art. 50 from a Section B system as surely
    # as it withholds Chapter III, and from the deployer as surely as from the provider. The
    # paragraph's SECOND sentence adds Arts. 57 to 59 where the high-risk requirements have been
    # integrated into the sectoral legislation; those three are sandbox provisions that bind no
    # party this reports for, so nothing is withheld here that they would supply.
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
        rule.for_role(role)
        for rule in spec.rules
        if _tier_or_duty_matches(rule, use_case, transparency_duties)
        and role in rule.applies_to_role
        and _route_matches(rule, use_case)
        and _area_matches(rule, use_case)
        and (reallocation is not None or not rule.requires_provider_reallocation)
        and _testing_matches(rule, real_world_testing)
        and _practice_matches(rule, prohibited_practice)
        and rule.status != "amended"
    ]
    # A rule carrying an `activation_condition` is NOT withheld here. The Act narrows some duties
    # to part of a role — Art. 27 binds deployers that are public bodies or private providers of
    # public services — and that narrowing is reported BESIDE the obligation, on the rule itself,
    # never by dropping it into a "might not apply" list. This report covers every role the Act
    # binds whoever is reading it; deciding on a reader's behalf which of their obligations to
    # demote is the same error as omitting a role for want of a ruleset.
    notices = [
        notice
        for rule in active
        if as_of_date is not None
        if (notice := _timing_notice(spec, rule, use_case, as_of_date)) is not None
    ]
    deferred_ids = {notice.rule.rule_id for notice in notices}
    ordinary = [rule for rule in active if rule.rule_id not in deferred_ids]
    return ActiveRules(
        use_case_id=use_case.use_case_id,
        role=role,
        document_verifiable=tuple(
            r for r in ordinary if r.status == "active" and r.document_verifiable
        ),
        not_document_verifiable=tuple(
            r for r in ordinary if r.status == "active" and not r.document_verifiable
        ),
        postponed=tuple(r for r in ordinary if r.status == "postponed"),
        upcoming=tuple(notice for notice in notices if notice.status is TemporalStatus.UPCOMING),
        timing_unresolved=tuple(
            notice for notice in notices if notice.status is TemporalStatus.CONDITIONAL_TIMING
        ),
    )
