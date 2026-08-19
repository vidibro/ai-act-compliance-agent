"""Which obligations apply to a classified use case.

Deterministic and model-free: activation is a property of the ruleset (`applies_to_risk_class`,
`applies_to_role`, `applies_to_route`, `applies_to_annex_iii_area`, `status`), not a judgement.
Only whether the documentation SATISFIES an active rule is a judgement, and that is the judge's job.

WHICH DOOR AND WHICH AREA are conditions, not decoration. Most obligations bind every high-risk
system alike, but a few name law that only reaches part of them — Art. 43 sends an Annex III point 1
system to a notified body, points 2 to 8 to internal control, and an Annex I system to its own
sectoral procedure. A rule that could not state that condition had to assume one area and cite its
law at every system, which is a confident wrong citation rather than a missing one.

Obligations attach per USE CASE, not per system. A product whose CV parsing is not_high_risk and
whose candidate scoring is high_risk owes Chapter III on the scoring use case alone, assessed
against that intended purpose — so selection runs per use case and the results are kept apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aiact.schemas.classification import UseCaseClassification
from aiact.schemas.enums import ActorRole, HighRiskRoute, RiskClass
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
    Annex I system whatever Annex III would have said about its purpose."""
    if use_case.annex_i_product is not None:
        return HighRiskRoute.ANNEX_I
    if use_case.annex_iii_area is not None:
        return HighRiskRoute.ANNEX_III
    return None


def _route_matches(rule: PolicyRule, use_case: UseCaseClassification) -> bool:
    """A rule with no route condition fires whichever door was used — the ordinary case."""
    return rule.applies_to_route is None or rule.applies_to_route is _route_of(use_case)


def _area_matches(rule: PolicyRule, use_case: UseCaseClassification) -> bool:
    """A rule that names Annex III areas fires only inside them.

    A use case with NO area — an Annex I system, or one whose area the run never established —
    matches no list, which is the safe direction: naming areas is how a rule says the law it cites
    is area-specific, and firing it outside them is what put Art. 43(2) on a biometrics system."""
    if not rule.applies_to_annex_iii_area:
        return True
    return use_case.annex_iii_area in rule.applies_to_annex_iii_area


def select_rules(spec: PolicySpec, use_case: UseCaseClassification, role: ActorRole) -> ActiveRules:
    """The obligations `role` owes for this use case, under its risk class.

    **Art. 2** comes first, and it is the stronger case. Where the Regulation does not govern the
    system at all — military use, sole-purpose research, pre-market development, a natural person's
    own use, a free and open-source release — there are no obligations to select, not a reduced set.
    Distinct from the Section B limit below, where the system IS governed and owes Arts. 102-109.

    Risk class is not on its own sufficient. **Art. 2(2)**: where a system is high-risk under
    Art. 6(1) because it is a safety component of a product listed in Annex I **Section B** —
    vehicles, aviation, rail, marine — only Art. 6(1), Arts. 102-109 and Art. 112 apply. Chapter III
    does not. Such a system is genuinely high-risk and genuinely owes none of Art. 9-15, so
    selecting on the tier alone would raise every one of them against a provider the Regulation
    exempts.
    """
    # Redundant against today's spec, and kept deliberately: no rule lists OUT_OF_SCOPE among its
    # risk classes, so the filter below would empty the set anyway. That is a property of the
    # current 19 rules rather than of the law, and the day a rule is written with a wider
    # `applies_to_risk_class` this is what stops it attaching to a system the Regulation does not
    # govern. Stated here because a silent emptiness cannot be told apart from an intended one.
    # OUT_OF_SCOPE owes nothing; GPAI_MODEL owes plenty, but under Chapter V, which this ruleset
    # does not carry. Selecting Art. 6-track rules for a model would raise Chapter III duties
    # against a provider the Act never puts them on — and would hide the ones it does.
    if use_case.risk_class in (RiskClass.OUT_OF_SCOPE, RiskClass.GPAI_MODEL):
        return ActiveRules(use_case_id=use_case.use_case_id, role=role)

    # Art. 2(2) is exhaustive — "only Article 6(1), Articles 102 to 109 and Article 112 apply" — so
    # this withholds Art. 4 from a Section B system as surely as it withholds Chapter III, and from
    # the deployer as surely as from the provider.
    if use_case.annex_i_product is not None and not use_case.annex_i_product.chapter_iii_applies:
        return ActiveRules(use_case_id=use_case.use_case_id, role=role)

    active = [
        rule
        for rule in spec.rules
        if use_case.risk_class in rule.applies_to_risk_class
        and role in rule.applies_to_role
        and _route_matches(rule, use_case)
        and _area_matches(rule, use_case)
        and rule.status != "amended"
    ]
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
