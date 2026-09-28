"""Rule ACTIVATION — which obligations a classified use case actually owes.

The headline here is Art. 43. Conformity assessment is not one duty with one citation: an Annex III
point 1 system may need a notified body (43(1)), points 2 to 8 self-assess under Annex VI (43(2)),
and an Annex I system follows its own sectoral act instead (43(3)). Three mutually exclusive
branches, so one rule gated on the tier alone cites the wrong procedure to two systems out of
three. A wrong citation is worse than a missing one: it is a confident instruction to follow law
that does not govern you.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from aiact.config import get_settings
from aiact.gap.rules import roles_with_rules, select_rules
from aiact.policy_loader import load_policy_spec
from aiact.schemas.classification import ClassificationEvidence, UseCaseClassification
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    AnnexIProduct,
    DerogationCondition,
    HighRiskRoute,
    ProhibitedPractice,
    ProviderReallocation,
    RealWorldTesting,
    RiskClass,
    TransparencyDuty,
)
from aiact.schemas.norm import TemporalStatus
from aiact.schemas.policy import LegalSource, PolicyRule
from aiact.schemas.question import Answer

# Fixture LegalSources only — read rather than restated, for the reason given in
# tests/test_policy_loader.py: the act version already lives in two places that must agree.
ACT_DATE = get_settings().act_version_date


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def a_use_case(
    area: AnnexIIIArea | None = None,
    product: AnnexIProduct | None = None,
    third_party: bool = True,
    risk_class: RiskClass = RiskClass.HIGH_RISK,
) -> UseCaseClassification:
    """`third_party` answers Art. 6(1)(b), and naming a product without it is not the Annex I route.

    Defaulted to true so that `product=` alone reads as the Art. 6(1) case it is meant to be. Pass
    false for the other one: a self-assessed product whose use case is high-risk under Art. 6(2).

    `risk_class` defaults to high_risk because most rules are on the Art. 6 track. Chapter V is the
    other track — a general-purpose AI model has no area and no route, and its rules name
    `gpai_model` and nothing else."""
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=ACT_DATE
    )
    return UseCaseClassification(
        use_case_id="uc",
        description="a system",
        annex_iii_area=area,
        annex_i_product=product,
        third_party_assessment=(
            None
            if product is None
            else Answer(
                value=third_party,
                reasoning="fixture",
                confidence="high",
                source=source,
                node_id="third_party_assessment",
            )
        ),
        risk_class=risk_class,
        # Art. 6(3) is the ONLY door to not_high_risk, and the schema enforces both its limbs — a
        # named condition under (a)-(d) and no significant risk of harm. A fixture that set the
        # tier without them would be a use case the cascade could never produce.
        derogation=(
            _an_answer(DerogationCondition.NARROW_PROCEDURAL_TASK, "derogation", source)
            if risk_class is RiskClass.NOT_HIGH_RISK
            else None
        ),
        poses_significant_risk=(
            _an_answer(False, "poses_significant_risk", source)
            if risk_class is RiskClass.NOT_HIGH_RISK
            else None
        ),
        reasoning="fixture",
        confidence="high",
        triggered_by=[ClassificationEvidence(source=source, reasoning="fixture")],
    )


def _an_answer(value, node_id: str, source: LegalSource) -> Answer:
    return Answer(
        value=value, reasoning="fixture", confidence="high", source=source, node_id=node_id
    )


def _a_rule(**overrides) -> PolicyRule:
    """A minimal valid rule, for testing what the schema REFUSES to build."""
    fields = {
        "rule_id": "AIA-RULE-TEST",
        "requirement": "x",
        "source": LegalSource(
            instrument="Regulation (EU) 2024/1689", article=50, act_version_date=ACT_DATE
        ),
        "applies_to_role": [ActorRole.PROVIDER],
        "obligation_status": "mandatory",
        "check_type": "presence",
        "evidence_expected": "x",
        "document_verifiable": False,
        "status": "active",
    }
    return PolicyRule(**(fields | overrides))


def _rule_ids(spec, use_case, role=ActorRole.PROVIDER) -> set[str]:
    return {r.rule_id for r in select_rules(spec, use_case, role).all_rules}


# --- Art. 43 — one duty, three bodies of law ------------------------------------------------------
# The three route rules answer "which procedure applies the FIRST time", and the partition the
# tests below pin is over those three. Two more Art. 43 rules answer different questions and are
# subtracted rather than folded in, because a system owing one of them beside its route is the
# correct answer, not a second conformity procedure:
#
#   AIA-RULE-PO-A43-4 asks when the procedure must be run AGAIN. Route-independent, so it fires
#     beside whichever of the three was selected.
#   AIA-RULE-PO-A43-1A and -1B say what EACH BRANCH OF THE ART. 43(1) CHOICE CONSISTS OF — -1A
#     the three internal-control verifications of Annex VI, -1B the Annex VII notified-body route
#     with its two applications, access duties and surveillance. Neither is a fourth route: both
#     fire beside AIA-RULE-PO-A43-1 for a biometrics system, whose Art. 43(1) choice this tool
#     cannot make on its behalf, and each carries the branch condition as its activation_condition.
#     They are a pair
#     because the paragraph offers a pair, and listing only one would assert the branch it leaves
#     open.
_ART_43_NOT_A_ROUTE_CHOICE = {"AIA-RULE-PO-A43-4", "AIA-RULE-PO-A43-1A", "AIA-RULE-PO-A43-1B"}


@pytest.mark.parametrize(
    "area,expected",
    [
        (AnnexIIIArea.BIOMETRICS, "AIA-RULE-PO-A43-1"),
        (AnnexIIIArea.EMPLOYMENT, "AIA-RULE-PO-A43-2"),
        (AnnexIIIArea.CRITICAL_INFRASTRUCTURE, "AIA-RULE-PO-A43-2"),
        (AnnexIIIArea.JUSTICE_DEMOCRACY, "AIA-RULE-PO-A43-2"),
    ],
)
def test_the_conformity_route_follows_the_annex_iii_point(spec, area, expected):
    """43(1) reaches point 1 alone; 43(2) reaches points 2 to 8. Exactly one fires per area, and
    never the other — a system told to self-assess when it needs a notified body has been given a
    clean bill of health it did not earn."""
    ids = _rule_ids(spec, a_use_case(area=area))
    art43 = {r for r in ids if r.startswith("AIA-RULE-PO-A43")}
    assert "AIA-RULE-PO-A43-4" in art43, "Art. 43(4) binds whichever route was taken"
    assert art43 - _ART_43_NOT_A_ROUTE_CHOICE == {expected}


def test_an_annex_i_system_follows_its_own_legislation(spec):
    """Art. 43(3): the sectoral act supplies the procedure, not this Regulation. Both Annex III
    branches are silent here — neither was written for a system with no Annex III area at all."""
    ids = _rule_ids(spec, a_use_case(product=AnnexIProduct.MEDICAL_DEVICES))
    art43 = {r for r in ids if r.startswith("AIA-RULE-PO-A43")}
    assert art43 - _ART_43_NOT_A_ROUTE_CHOICE == {"AIA-RULE-PO-A43-3"}


def test_every_high_risk_system_owes_exactly_one_conformity_rule(spec):
    """The three branches partition high risk: no system may owe two conformity procedures, and
    none may owe none. A gap here reads in a report as "no conformity assessment required"."""
    cases = [a_use_case(area=area) for area in AnnexIIIArea] + [
        a_use_case(product=p) for p in AnnexIProduct if p.chapter_iii_applies
    ]
    for uc in cases:
        art43 = {
            r for r in _rule_ids(spec, uc) if r.startswith("AIA-RULE-PO-A43")
        } - _ART_43_NOT_A_ROUTE_CHOICE
        label = uc.annex_iii_area or uc.annex_i_product
        assert len(art43) == 1, f"{label}: expected one Art. 43 route rule, got {sorted(art43)}"


# --- Art. 49 — the exception inside the area gate ----------------------------------------------
def test_critical_infrastructure_owes_no_registration(spec):
    """Art. 49(1) reaches Annex III "with the exception of point 2", so an area gate does the work a
    tier gate cannot: gated on high_risk alone this raises EU-database registration against point 2.

    NO EU-DATABASE REGISTRATION IS NOT NO REGISTRATION. Art. 49(5) sends the same system to a
    national register instead, and the two are asserted together so that neither reading can be
    taken from this test on its own."""
    critical = _rule_ids(spec, a_use_case(area=AnnexIIIArea.CRITICAL_INFRASTRUCTURE))
    employment = _rule_ids(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT))
    assert "AIA-RULE-PO-A49" not in critical
    assert "AIA-RULE-PO-A49" in employment
    assert "AIA-RULE-PO-A49-5" in critical, "point 2 registers at national level under Art. 49(5)"
    assert "AIA-RULE-PO-A49-5" not in employment, "Art. 49(5) reaches point 2 and nothing else"


def test_an_annex_i_system_is_not_registered_under_article_49(spec):
    """49(1) reaches systems "listed in Annex III". An Annex I one is not."""
    assert "AIA-RULE-PO-A49" not in _rule_ids(
        spec, a_use_case(product=AnnexIProduct.MEDICAL_DEVICES)
    )


def test_law_enforcement_registers_in_the_non_public_section(spec):
    """Art. 49(4) does not replace the registration — it says where it goes and how little it
    carries. Both rules fire, and only in the areas the paragraph names."""
    police = _rule_ids(spec, a_use_case(area=AnnexIIIArea.LAW_ENFORCEMENT))
    assert {"AIA-RULE-PO-A49", "AIA-RULE-ALL-A49-4"} <= police

    hiring = _rule_ids(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT))
    assert "AIA-RULE-ALL-A49-4" not in hiring


# --- the mechanism itself -------------------------------------------------------------------------
def test_a_rule_with_no_conditions_still_fires_everywhere(spec):
    """The defaults must mean NO CONDITION, not "neither route" — most of the ruleset binds every
    high-risk system whichever door it came through, and a default that narrowed would silently
    empty the report."""
    for uc in (
        a_use_case(area=AnnexIIIArea.EMPLOYMENT),
        a_use_case(area=AnnexIIIArea.BIOMETRICS),
        a_use_case(product=AnnexIProduct.MEDICAL_DEVICES),
    ):
        ids = _rule_ids(spec, uc)
        assert {"AIA-RULE-HR-A09", "AIA-RULE-HR-A15", "AIA-RULE-PO-A17"} <= ids


def test_an_area_condition_cannot_also_claim_the_annex_i_route():
    """Such a rule could never fire — an Annex I use case carries no Annex III area — and a rule
    that never fires is indistinguishable in a report from an obligation nobody owes."""
    with pytest.raises(ValueError, match="could never activate"):
        PolicyRule(
            rule_id="AIA-RULE-TEST",
            requirement="x",
            source=LegalSource(
                instrument="Regulation (EU) 2024/1689", article=43, act_version_date=ACT_DATE
            ),
            applies_to_risk_class=[RiskClass.HIGH_RISK],
            applies_to_role=[ActorRole.PROVIDER],
            applies_to_route=HighRiskRoute.ANNEX_I,
            applies_to_annex_iii_area=[AnnexIIIArea.EMPLOYMENT],
            obligation_status="mandatory",
            check_type="presence",
            evidence_expected="x",
            document_verifiable=False,
            status="active",
        )


def test_every_area_scoped_rule_cites_the_law_for_those_areas(spec):
    """A rule naming areas is asserting that the provision it cites governs THEM. Nothing here can
    check that automatically, so what is checked is the pairing that made the old bug possible: an
    area-scoped rule must pin a paragraph, because it is the paragraph that varies by area."""
    scoped = [r for r in spec.rules if r.applies_to_annex_iii_area]
    assert scoped, "the area mechanism is unused — the Art. 43/49 split should use it"
    for rule in scoped:
        assert rule.source.paragraph is not None, (
            f"{rule.rule_id} names Annex III areas but cites {rule.source.article} as a whole. "
            f"Area-specific law lives in a paragraph."
        )


# --- Art. 27 — a duty the Act narrows within a role ----------------------------------------------
def test_art_27_is_reported_under_the_deployer_role_like_any_other(spec):
    """Art. 27(1) binds only SOME deployers — public bodies, private providers of public services,
    and deployers of Annex III(5)(b)/(c) systems. That narrowing is reported with the obligation,
    never used to withhold it.

    The report covers every obligation the Act creates for every role it binds, whoever happens to
    be reading. Demoting this one into a "might not apply to you" list would be the tool deciding
    on a reader's behalf which of their duties to take seriously — the same error as omitting a
    role because no ruleset was written for it."""
    active = select_rules(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT), ActorRole.DEPLOYER)

    assert "AIA-RULE-DP-A27" in {r.rule_id for r in active.not_document_verifiable}


# --- Art. 60 — the elective route ---------------------------------------------------------------
_TESTING_RULES = {"AIA-RULE-PO-A60-4", "AIA-RULE-PO-A60-7", "AIA-RULE-PO-A60-8", "AIA-RULE-PO-A61"}


def test_only_a_document_that_rules_out_testing_withholds_the_testing_duties(spec):
    """Silence selects. Only `RealWorldTesting.NONE` drops the Art. 60 and 61 duties.

    THE DEFAULT RUNS THE OPPOSITE WAY TO ART. 25, and the difference is what the silence is about.
    A reallocation nobody established did not happen, and Art. 25(2) asserted anyway invents a
    party. Here the party is this system's provider and what is uncertain is whether they are
    running a trial — something a technical file has no reason to mention either way, so reading
    its silence as a clearance drops six duties on evidence nobody supplied. The cascade already
    treats Art. 2(1) this way, and this is that reasoning applied one layer down.

    A DOCUMENT THAT SAYS `NONE` IS ANSWERED, not ignored: it positively establishes retrospective
    validation, or a trial inside a sandbox, where Art. 76(2) puts the authority in charge of
    Art. 60 compliance instead. That is the one case where withholding is what the Act says."""
    use_case = a_use_case(area=AnnexIIIArea.EMPLOYMENT)
    selects = {
        answer: _TESTING_RULES
        <= {
            r.rule_id
            for r in select_rules(
                spec, use_case, ActorRole.PROVIDER, real_world_testing=answer
            ).all_rules
        }
        for answer in (*RealWorldTesting, None)
    }
    assert selects[RealWorldTesting.UNDERWAY]
    assert selects[RealWorldTesting.PLANNED]
    assert selects[RealWorldTesting.NOT_STATED], (
        "a document that never mentions a trial had the Art. 60 duties withheld — silence is not "
        "a statement that no trial happened, and these bind before the trial starts"
    )
    assert not selects[RealWorldTesting.NONE], (
        "a document that positively rules out real-world testing is still shown the Art. 60 duties"
    )
    assert not selects[None], (
        "the question was not put — the system is not high-risk — and the duties were selected "
        "anyway. Art. 60(1) governs high-risk systems and no other tier."
    )


def test_the_testing_duties_reach_no_tier_the_article_does_not_govern(spec):
    """Art. 60(1) opens on high-risk systems, on either Art. 6 route. Nothing else.

    The gate lives in `gap.roles.ask_real_world_testing`, so a lower tier never gets the question
    and `None` withholds. Asserted from the other end as well — the rules themselves must name the
    tier — because a rule that named `minimal` would be selected the moment anything answered."""
    for rule_id in sorted(_TESTING_RULES):
        rule = next(r for r in spec.rules if r.rule_id == rule_id)
        assert rule.applies_to_risk_class == [RiskClass.HIGH_RISK], rule_id
        # Art. 60(4)(h) and (j) also bind a deployer taking part; every other testing duty is the
        # provider's alone.
        expected = (
            [ActorRole.PROVIDER, ActorRole.DEPLOYER]
            if rule_id == "AIA-RULE-PO-A60-4"
            else [ActorRole.PROVIDER]
        )
        assert rule.applies_to_role == expected, rule_id
        assert rule.requires_real_world_testing, rule_id


def test_a_deployer_taking_part_in_testing_reads_only_its_own_criteria(spec):
    """Art. 60(4) is one rule for both parties. The provider reads all fourteen points; a deployer
    taking part owes the roles-and-responsibilities agreement of (h) and the oversight of (j), and
    a report that handed it the other twelve would name duties it cannot discharge."""
    use_case = a_use_case(area=AnnexIIIArea.EMPLOYMENT)

    def testing_rule(role: ActorRole) -> PolicyRule:
        selected = select_rules(spec, use_case, role, real_world_testing=RealWorldTesting.UNDERWAY)
        return next(r for r in selected.all_rules if r.rule_id == "AIA-RULE-PO-A60-4")

    assert len(testing_rule(ActorRole.PROVIDER).criteria) == 14
    assert [c.norm_id for c in testing_rule(ActorRole.DEPLOYER).criteria] == [
        "AIA-NORM-A060-P4-H-CONCLUDE-ROLES-AGREEMENT",
        "AIA-NORM-A060-P4-J-QUALIFIED-OVERSIGHT",
    ]


def test_a_narrowed_duty_names_the_organisations_it_binds(spec):
    """The narrowing is only useful if it says WHICH organisations are caught — and it must say so
    about the parties, not about "you". This report describes what the Act requires of each role
    for this system; it is not addressed to whoever happens to be reading, and the deployer it
    describes is often not the organisation that wrote the document."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-DP-A27")
    condition = rule.activation_condition

    assert condition is not None
    assert "governed by public law" in condition
    assert "5(b)" in condition and "5(c)" in condition
    assert not re.search(r"\byou(r|rs|rself)?\b", condition, re.I)


def test_art_111_1_reaches_only_the_areas_annex_x_systems_serve(spec):
    """Every Annex X act sets up a border, visa, asylum or criminal-records database, so the 2030
    deadline reaches high-risk systems in the law enforcement and migration areas and no others —
    not an employment system, and not a minimal one."""
    rule = "AIA-RULE-ALL-A111-1"
    for area in (AnnexIIIArea.LAW_ENFORCEMENT, AnnexIIIArea.MIGRATION):
        for role in (ActorRole.PROVIDER, ActorRole.DEPLOYER, ActorRole.IMPORTER):
            assert rule in _rule_ids(spec, a_use_case(area=area), role)
    assert rule not in _rule_ids(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT))
    assert rule not in _rule_ids(spec, _a_minimal_use_case())


def test_art_27_never_reaches_the_systems_it_excludes(spec):
    """Art. 27(1) reaches Art. 6(2) systems "with the exception of" Annex III point 2. An Annex I
    safety component is not an Art. 6(2) system at all, so it is outside on the same words."""
    for uc in (
        a_use_case(area=AnnexIIIArea.CRITICAL_INFRASTRUCTURE),
        a_use_case(product=AnnexIProduct.MEDICAL_DEVICES),
    ):
        assert "AIA-RULE-DP-A27" not in _rule_ids(spec, uc, ActorRole.DEPLOYER)


def test_a_narrowed_duty_is_selected_exactly_like_an_unnarrowed_one(spec):
    """`activation_condition` is reporting, not filtering. A rule carrying one is selected by the
    same conditions as any other and lands in the same buckets — the only difference is that the
    reader is told which members of the role owe it."""
    narrowed = [r for r in spec.rules if r.activation_condition is not None]
    assert narrowed, "the mechanism is unused — Art. 27 should carry it"
    for rule in narrowed:
        # THREE MECHANISMS GATE ON SOMETHING OTHER THAN THIS FIELD, and none of them is it.
        # Art. 25(2)'s duty has no holder until the provider role moves; the Art. 60 and 61 duties
        # have none until a provider elects real-world testing; the Art. 5(2) to (4) conditions
        # reach only the practice point (h) banned. Supplying all three answers isolates what is
        # under test — that STATING a condition never withholds — from the mechanisms that do.
        moved = (
            ProviderReallocation.NAME_OR_TRADEMARK if rule.requires_provider_reallocation else None
        )
        testing = RealWorldTesting.UNDERWAY if rule.requires_real_world_testing else None
        practice = (
            rule.applies_to_prohibited_practice[0] if rule.applies_to_prohibited_practice else None
        )
        # THE USE CASE THIS RULE IS FOR, not an arbitrary one. The TIER, the ROUTE and the AREA
        # are gates on the SYSTEM, and withholding on them is correct: Art. 11(2) reaches an
        # Annex I product and nothing else, and a Chapter V rule withheld from a high-risk system
        # is on the other track rather than narrowed. What is under test is the one gate that is
        # NOT about the system — the condition, which narrows the duty-HOLDER and must never
        # withhold on top of the three that are.
        annex_i = rule.applies_to_route is HighRiskRoute.ANNEX_I
        product = AnnexIProduct.MEDICAL_DEVICES if annex_i else None
        # high_risk where the rule names it, because that is the case the fixture is built around;
        # otherwise the first tier it does name, any of which is a use case it must be selected for.
        # A rule gated on an Art. 50 duty names no tier and is owed at any, minimal included.
        tier = (
            RiskClass.HIGH_RISK
            if RiskClass.HIGH_RISK in rule.applies_to_risk_class
            else rule.applies_to_risk_class[0]
            if rule.applies_to_risk_class
            else RiskClass.MINIMAL
        )
        annex_iii = tier in (RiskClass.HIGH_RISK, RiskClass.NOT_HIGH_RISK)
        for role in rule.applies_to_role:
            for area in rule.applies_to_annex_iii_area or list(AnnexIIIArea):
                use_case = a_use_case(
                    area=area if annex_iii and not product else None,
                    product=product,
                    risk_class=tier,
                )
                active = select_rules(
                    spec,
                    use_case,
                    role,
                    reallocation=moved,
                    real_world_testing=testing,
                    prohibited_practice=practice,
                    transparency_duties=list(rule.applies_to_transparency_duty),
                )
                assert rule.rule_id in {r.rule_id for r in active.all_rules}, (
                    f"{rule.rule_id} states a condition and was withheld for {role}/{area} — "
                    f"a condition is reported beside a duty, never used to drop it"
                )


# --- Art. 25(2) — the duty that outlives the provider role ---------------------------------------
def test_the_initial_provider_owes_nothing_until_the_role_moves(spec):
    """Art. 25(2) binds the party that placed the system on the market and then stopped being its
    provider. Where no reallocation occurred there is no such party — the provider IS the initial
    provider — so asserting the duty would invent an organisation and give it homework."""
    active = select_rules(
        spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT), ActorRole.INITIAL_PROVIDER
    )
    assert active.all_rules == ()


@pytest.mark.parametrize("limb", list(ProviderReallocation))
def test_a_reallocation_creates_the_cooperation_duty(spec, limb):
    """Every limb of Art. 25 produces a new provider, and therefore an initial provider that owes
    Art. 25(2): supply the information, technical access and assistance the new one needs, in
    particular for the conformity assessment."""
    active = select_rules(
        spec,
        a_use_case(area=AnnexIIIArea.EMPLOYMENT),
        ActorRole.INITIAL_PROVIDER,
        reallocation=limb,
    )
    assert {r.rule_id for r in active.all_rules} == {"AIA-RULE-IP-A25-2"}
    assert active.not_document_verifiable, "a relational duty between two organisations"


def test_the_cooperation_duty_is_not_the_current_provider_s(spec):
    """The direction is the whole point. Art. 25(2) binds the party that has STOPPED being the
    provider; attaching it to `provider` would put it on the organisation that just took the role
    on — the exact mis-attribution `Finding.role` exists to prevent."""
    provider = select_rules(
        spec,
        a_use_case(area=AnnexIIIArea.EMPLOYMENT),
        ActorRole.PROVIDER,
        reallocation=ProviderReallocation.NAME_OR_TRADEMARK,
    )
    assert "AIA-RULE-IP-A25-2" not in {r.rule_id for r in provider.all_rules}


def test_a_reallocation_adds_an_obligation_and_removes_none(spec):
    """The Art. 25 answer is the one thing `roles` feeds into selection, and it may only ADD. A
    report whose provider obligations shrank because a role moved would be reporting less law than
    the Act contains."""
    use_case = a_use_case(area=AnnexIIIArea.EMPLOYMENT)
    for role in (ActorRole.PROVIDER, ActorRole.DEPLOYER):
        without = {r.rule_id for r in select_rules(spec, use_case, role).all_rules}
        with_move = {
            r.rule_id
            for r in select_rules(
                spec, use_case, role, reallocation=ProviderReallocation.SUBSTANTIAL_MODIFICATION
            ).all_rules
        }
        assert without == with_move


def test_only_one_rule_is_gated_on_the_reallocation(spec):
    """A condition answered by a QUESTION rather than by the classification is the exception, and
    should stay one: every other rule must activate from the classification alone, or a run whose
    Art. 25 question failed would silently under-report."""
    gated = {r.rule_id for r in spec.rules if r.requires_provider_reallocation}
    assert gated == {"AIA-RULE-IP-A25-2"}


# --- Art. 50 — the activation axis that is not a tier ------------------------------------------
#
# Every other rule in the spec activates from the risk class. Art. 50 cannot: it cuts ACROSS the
# tiers, and the two directions fail differently. Gate it on `minimal` and a high-risk chatbot owes
# nothing under 50(1); gate it on every tier and a candidate scorer that generates nothing is told
# to watermark its output. The tests below pin both directions.


def _a_minimal_use_case() -> UseCaseClassification:
    use_case = a_use_case()
    return use_case.model_copy(update={"risk_class": RiskClass.MINIMAL})


def _tr_ids(spec, use_case, role, duties) -> set[str]:
    active = select_rules(spec, use_case, role, transparency_duties=duties)
    return {r.rule_id for r in active.all_rules if r.rule_id.startswith("AIA-RULE-TR-")}


def test_a_minimal_system_owes_a_transparency_duty(spec):
    """The direction a tier-gated rule gets wrong. A text generator can be minimal risk and still
    owe 50(2) — that is the whole reason Art. 50 is answered on its own axis."""
    duties = [TransparencyDuty.SYNTHETIC_CONTENT_MARKING]
    # Art. 111(4) gives a generator already on the market until 2 December 2026 for the same duty.
    assert _tr_ids(spec, _a_minimal_use_case(), ActorRole.PROVIDER, duties) == {
        "AIA-RULE-TR-A50-2",
        "AIA-RULE-TR-A111-4",
    }


def test_a_high_risk_system_owing_no_duty_owes_no_transparency_rule(spec):
    """The other direction, and the one that would flood a report. Most high-risk systems owe
    nothing under Art. 50: a candidate scorer holds no conversation and generates no content."""
    use_case = a_use_case(area=AnnexIIIArea.EMPLOYMENT)
    assert _tr_ids(spec, use_case, ActorRole.PROVIDER, []) == set()
    assert _tr_ids(spec, use_case, ActorRole.DEPLOYER, []) == set()


def test_the_tier_never_narrows_a_duty_that_attached(spec):
    """Same duty, every governed tier, same rule. The duty is the condition; the tier is not one."""
    duties = [TransparencyDuty.DIRECT_INTERACTION]
    for risk_class in (RiskClass.MINIMAL, RiskClass.NOT_HIGH_RISK, RiskClass.HIGH_RISK):
        use_case = a_use_case(area=AnnexIIIArea.EMPLOYMENT).model_copy(
            update={"risk_class": risk_class}
        )
        assert _tr_ids(spec, use_case, ActorRole.PROVIDER, duties) == {"AIA-RULE-TR-A50-1"}


def test_a_transparency_duty_is_added_to_chapter_iii_never_instead_of_it(spec):
    """Art. 50(6): paragraphs 1 to 4 'shall not affect the requirements and obligations set out in
    Chapter III'. A high-risk system that generates content owes 50(2) AND all of Arts. 9-21 — the
    Article is additive, and a duty rule must never displace a tier rule."""
    use_case = a_use_case(area=AnnexIIIArea.EMPLOYMENT)
    duties = [TransparencyDuty.SYNTHETIC_CONTENT_MARKING]
    without = {r.rule_id for r in select_rules(spec, use_case, ActorRole.PROVIDER).all_rules}
    with_duty = {
        r.rule_id
        for r in select_rules(
            spec, use_case, ActorRole.PROVIDER, transparency_duties=duties
        ).all_rules
    }
    assert without < with_duty, "the duty removed a Chapter III obligation"
    assert with_duty - without == {"AIA-RULE-TR-A50-2", "AIA-RULE-TR-A111-4"}


def test_transparency_rules_are_filed_under_the_role_that_owes_them(spec):
    """Art. 50 splits by role and the split is not cosmetic: (1) and (2) are built into the system
    by the provider, (3) and (4) are performed in front of the affected person by the deployer. A
    provider handed 50(3) cannot discharge it, and the deployer's duty would go unnamed."""
    for duty in TransparencyDuty:
        rules = [r for r in spec.rules if duty in r.applies_to_transparency_duty]
        assert rules, f"no rule carries {duty.value}"
        for rule in rules:
            assert rule.applies_to_role == [duty.owed_by]


def test_both_duties_of_paragraph_four_reach_the_same_rule(spec):
    """50(4) is one paragraph with two subparagraphs — deep fakes, and published public-interest
    text. One provision, one citation, either duty."""
    use_case = _a_minimal_use_case()
    for duty in (
        TransparencyDuty.DEEP_FAKE_DISCLOSURE,
        TransparencyDuty.PUBLIC_INTEREST_TEXT_DISCLOSURE,
    ):
        assert _tr_ids(spec, use_case, ActorRole.DEPLOYER, [duty]) == {"AIA-RULE-TR-A50-4"}


def test_an_out_of_scope_system_owes_no_transparency_duty_either(spec):
    """Art. 2 withholds the Regulation whole, Art. 50 included. This is the case the early return in
    `select_rules` now exists for: a duty-gated rule names no risk class, so nothing further down
    tests the tier for it."""
    use_case = a_use_case().model_copy(update={"risk_class": RiskClass.OUT_OF_SCOPE})
    duties = list(TransparencyDuty)
    for role in (ActorRole.PROVIDER, ActorRole.DEPLOYER):
        assert _tr_ids(spec, use_case, role, duties) == set()


def test_a_section_b_system_owes_no_transparency_duty_either(spec):
    """Art. 2(2) is exhaustive — 'only Article 6(1), Article 60a and Articles 102 to 112 shall
    apply'."""
    use_case = a_use_case(product=AnnexIProduct.MOTOR_VEHICLES)
    duties = list(TransparencyDuty)
    for role in (ActorRole.PROVIDER, ActorRole.DEPLOYER):
        assert _tr_ids(spec, use_case, role, duties) == set()


def test_a_rule_may_not_gate_on_both_a_tier_and_a_duty():
    with pytest.raises(ValueError, match="names both applies_to_transparency_duty"):
        _a_rule(
            applies_to_risk_class=[RiskClass.MINIMAL],
            applies_to_transparency_duty=[TransparencyDuty.DIRECT_INTERACTION],
        )


def test_a_rule_gating_on_neither_is_rejected():
    """A rule nothing can activate reads in the spec as covered and in every report as absent."""
    with pytest.raises(ValueError, match="names neither"):
        _a_rule()


def test_a_transparency_rule_filed_under_the_wrong_role_is_rejected():
    """50(3) is the deployer's. Filed under the provider it would select for a party that cannot
    discharge it — caught at load time rather than in a report."""
    with pytest.raises(ValueError, match=r"Art. 50\(3\) is owed by deployer"):
        _a_rule(
            applies_to_transparency_duty=[TransparencyDuty.EMOTION_OR_BIOMETRIC_CATEGORISATION],
            applies_to_role=[ActorRole.PROVIDER],
        )


# --- Art. 49(3) — the deployer registers too ---------------------------------------------------
def test_the_deployer_owes_its_own_registration(spec):
    """Two entries in one database, made by two parties. A provider that registered correctly under
    49(1) has not registered its deployer's USE, so a report showing only the provider's duty
    leaves a public authority believing it is covered."""
    provider = _rule_ids(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT), ActorRole.PROVIDER)
    deployer = _rule_ids(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT), ActorRole.DEPLOYER)

    assert "AIA-RULE-PO-A49" in provider and "AIA-RULE-PO-A49" not in deployer
    assert "AIA-RULE-DP-A49-3" in deployer and "AIA-RULE-DP-A49-3" not in provider


def test_deployer_registration_carries_the_same_annex_iii_exception(spec):
    """49(3) excepts point 2 in the same words as 49(1) — 'with the exception of ... point 2 of
    Annex III' — and reaches no Annex I system at all."""
    critical = _rule_ids(
        spec, a_use_case(area=AnnexIIIArea.CRITICAL_INFRASTRUCTURE), ActorRole.DEPLOYER
    )
    annex_i = _rule_ids(spec, a_use_case(product=AnnexIProduct.MEDICAL_DEVICES), ActorRole.DEPLOYER)

    assert "AIA-RULE-DP-A49-3" not in critical
    assert "AIA-RULE-DP-A49-3" not in annex_i


def test_the_secure_section_covers_the_deployer_registration_too(spec):
    """Art. 49(4) governs 'the registration referred to in paragraphs 1, 2 and 3' — so a public
    authority deploying a law-enforcement system registers in the secure non-public section on the
    same terms as the provider. A rule bound to the provider alone would tell only half the parties
    where their entry goes."""
    police_deployer = _rule_ids(
        spec, a_use_case(area=AnnexIIIArea.LAW_ENFORCEMENT), ActorRole.DEPLOYER
    )
    police_provider = _rule_ids(
        spec, a_use_case(area=AnnexIIIArea.LAW_ENFORCEMENT), ActorRole.PROVIDER
    )

    assert "AIA-RULE-ALL-A49-4" in police_deployer
    assert "AIA-RULE-ALL-A49-4" in police_provider


def test_the_authority_that_is_its_own_provider_is_told_where_its_file_lives(spec):
    """Art. 78(3)'s second subparagraph is a duty on a PROVIDER inside an article of authority
    duties, and it reaches the three areas the paragraph names, on the provider side only.

    A DEPLOYER MUST NOT SELECT IT. The paragraph binds "law enforcement, immigration or asylum
    authorities [that] are providers" — the file is kept by whoever drew it up, and telling a
    deploying police force to hold Annex IV documentation it never wrote sends it looking for a
    document that is not its to keep. The mirror of `AIA-RULE-ALL-A49-4`, which binds both roles
    because Art. 49(4) governs the deployer's own registration too; the difference is in the
    paragraphs, not in the population.

    Pinned per rule rather than derived, and deliberately: what went wrong here was a ledger entry
    that summarised a two-subparagraph provision from its first subparagraph, and no mechanical
    test separates that from an accurate summary. The subject of the duty is "Those authorities",
    which is a provider only by reading back to the sentence before it.
    """
    for area in (AnnexIIIArea.BIOMETRICS, AnnexIIIArea.LAW_ENFORCEMENT, AnnexIIIArea.MIGRATION):
        use_case = a_use_case(area=area)
        assert "AIA-RULE-PO-A78-3" in _rule_ids(spec, use_case, ActorRole.PROVIDER), area.value
        assert "AIA-RULE-PO-A78-3" not in _rule_ids(spec, use_case, ActorRole.DEPLOYER), area.value
    outside = a_use_case(area=AnnexIIIArea.EMPLOYMENT)
    assert "AIA-RULE-PO-A78-3" not in _rule_ids(spec, outside, ActorRole.PROVIDER)


# --- Art. 113 — when each obligation starts ----------------------------------------------------
#
# One rule, two start dates. The Omnibus rewrote Art. 113 so Chapter III Sections 1-3 apply from
# 2 December 2027 to a system high-risk by the Annex III door and 2 August 2028 by the Annex I one,
# which is the same shape of problem `applies_to_route` was built for: there the route decided WHICH
# law applies, here it decides WHEN.

# Chapter III Sections 1, 2 and 3 = Arts. 6 to 27. Section 5 (Arts. 40-49) was NOT moved.
# Article ids are STRINGS everywhere — see LegalSource.article — so the range is spelled as one.
_ROUTE_SPLIT_ARTICLES = {str(n) for n in range(6, 28)}
_ANNEX_III_DATE = date(2027, 12, 2)
_ANNEX_I_DATE = date(2028, 8, 2)
_GENERAL_DATE = date(2026, 8, 2)


def test_chapter_iii_obligations_start_on_the_route_s_date(spec):
    """Every rule citing Arts. 6-27 carries both dates, and resolves to the right one per door."""
    split = [r for r in spec.rules if r.source.article in _ROUTE_SPLIT_ARTICLES]
    assert len(split) == 50, "Arts. 6-27 should be the whole of Chapter III Sections 1-3"
    for rule in split:
        if rule.rule_id in {
            "AIA-RULE-NHR-A06-4",
            "AIA-RULE-NHR-A06-4-REGISTER",
            "AIA-RULE-NHR-A06-4-PROVIDE-ASSESSMENT",
        }:
            continue  # not a high-risk system at all — see its comment in spec.yaml
        regime = spec.temporal_regime_for(rule)
        if regime is not None:
            assert rule.effective_date is None and not rule.effective_date_by_route
            assert (
                regime.status_on(_ANNEX_III_DATE, HighRiskRoute.ANNEX_III) is TemporalStatus.ACTIVE
            )
            assert (
                regime.status_on(_ANNEX_III_DATE, HighRiskRoute.ANNEX_I) is TemporalStatus.UPCOMING
            )
        else:
            assert rule.effective_date is None, f"{rule.rule_id} states a single date"
            assert rule.effective_date_for(HighRiskRoute.ANNEX_III) == _ANNEX_III_DATE, rule.rule_id
            assert rule.effective_date_for(HighRiskRoute.ANNEX_I) == _ANNEX_I_DATE, rule.rule_id


def test_the_sections_the_omnibus_left_alone_keep_the_general_date(spec):
    """Arts. 43 and 47-49 sit in Section 5, which Art. 113(c) does not name, so they still apply
    from 2 August 2026. Conformity assessment and registration therefore apply BEFORE the
    requirements they attest to — the Article's own result, and the reason this is pinned rather
    than smoothed over."""
    for rule_id in (
        "AIA-RULE-PO-A43-1",
        "AIA-RULE-PO-A47",
        "AIA-RULE-PO-A49",
        "AIA-RULE-DP-A49-3",
        "AIA-RULE-ALL-A49-4",
    ):
        rule = next(r for r in spec.rules if r.rule_id == rule_id)
        assert rule.effective_date == _GENERAL_DATE, rule_id
        assert not rule.effective_date_by_route, f"{rule_id} was not moved by the Omnibus"


def test_no_rule_still_carries_a_date_the_omnibus_moved(spec):
    """The migration tripwire. 2026-08-02 was the date on every Chapter III rule before the
    amendment, so one left behind in Sections 1-3 is an unmigrated rule rather than a decision."""
    stale = [
        r.rule_id
        for r in spec.rules
        if r.source.article in _ROUTE_SPLIT_ARTICLES and r.effective_date == _GENERAL_DATE
    ]
    assert not stale, f"still on the pre-Omnibus date: {stale}"


def test_a_rule_may_not_state_its_date_twice():
    with pytest.raises(ValueError, match="sets both effective_date"):
        _a_rule(
            applies_to_risk_class=[RiskClass.HIGH_RISK],
            effective_date=_GENERAL_DATE,
            effective_date_by_route={HighRiskRoute.ANNEX_III: _ANNEX_III_DATE},
        )


def test_an_unknown_route_resolves_to_the_earlier_date(spec):
    """Deliberately the earlier one. Telling a reader they have until 2028 when the answer might
    have been 2027 is the direction that costs them a deadline."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-HR-A09")
    regime = spec.temporal_regime_for(rule)
    assert regime is not None
    assert regime.status_on(_ANNEX_III_DATE) is TemporalStatus.CONDITIONAL_TIMING


def test_canonical_article_9_timing_withholds_only_the_judge(spec):
    """A future Article 9 duty remains visible, but cannot manufacture a current gap."""
    active = select_rules(
        spec,
        a_use_case(area=AnnexIIIArea.EMPLOYMENT),
        ActorRole.PROVIDER,
        as_of_date=date(2026, 9, 22),
    )
    notices = [notice for notice in active.upcoming if notice.rule.rule_id == "AIA-RULE-HR-A09"]
    assert len(notices) == 1
    assert notices[0].route is HighRiskRoute.ANNEX_III
    assert notices[0].application_date == _ANNEX_III_DATE
    assert notices[0].legal_basis_spans == ("AIA-TEXT-A113-C",)
    assert "AIA-RULE-HR-A09" not in {rule.rule_id for rule in active.document_verifiable}


# Chapter III Section 5 — Arts. 40 to 49. Not moved by the Omnibus, so in force ahead of the
# requirements it attests to.
_SECTION_5_ARTICLES = {str(n) for n in range(40, 50)}


def test_every_section_5_rule_explains_why_it_is_already_in_force(spec):
    """These apply from 2 August 2026 while the Section 2 requirements they assess, declare, mark or
    register wait until December 2027. A reader meeting that unexplained reasonably concludes the
    tool is broken, and the damaging response is to disregard the date rather than the note. So the
    explanation travels WITH the obligation instead of living in a comment only we read."""
    section_5 = [r for r in spec.rules if r.source.article in _SECTION_5_ARTICLES]
    assert len(section_5) == 22, "Arts. 41, 43 and 46-49 are the whole of Section 5 in this ruleset"
    for rule in section_5:
        # ONE RULE IN SECTION 5 TAKES THE OTHER DATE, and it is the same contested reading
        # AIA-RULE-NHR-A06-4 carries: Art. 49(2) registers an Art. 6(3) conclusion, and Art. 6
        # sits in
        # Section 1, which Art. 113(c) DID move. Splitting the paragraph — the provider on the
        # deferred date, its authorised representative on the general one — would put the two
        # parties to one registration on dates sixteen months apart. Its note argues the choice and
        # names the reading not taken, which is what this test exists to require.
        if rule.rule_id == "AIA-RULE-AR-A49-2":
            continue
        assert rule.effective_date == _GENERAL_DATE, rule.rule_id
        note = rule.effective_date_note or ""
        assert "2 December 2027" in note and "2 August 2026" in note, rule.rule_id
        assert "Section 5" in note, rule.rule_id


def test_the_contested_date_names_the_reading_it_did_not_take(spec):
    """Art. 6(4) binds a provider whose system is NOT high-risk, and Art. 113's limbs both describe
    systems that are — so no limb reaches it and a date had to be chosen. Choosing silently would
    present our reading as the Act's, and the two readings are sixteen months apart in the direction
    that matters: the alternative means the duty is owed NOW."""
    for rule_id in ("AIA-RULE-NHR-A06-4", "AIA-RULE-AR-A49-2"):
        rule = next(r for r in spec.rules if r.rule_id == rule_id)
        note = rule.effective_date_note or ""

        assert rule.effective_date == date(2027, 12, 2), rule_id
        assert "CONTESTED" in note, rule_id
        assert "2 August 2026" in note, f"{rule_id}: name the reading not taken, with its date"
        assert "take advice" in note, rule_id


def test_a_timing_note_never_stands_in_for_a_date(spec):
    """The note qualifies a date; it does not replace one. A rule carrying prose about when it
    applies and no resolvable date would read as an answer while being none."""
    for rule in spec.rules:
        if rule.effective_date_note:
            resolved = rule.effective_date_for(HighRiskRoute.ANNEX_III)
            assert resolved is not None, f"{rule.rule_id} explains a date it does not have"


def test_no_article_50_duty_reaches_a_general_purpose_model(spec):
    """ART. 50 BINDS AI SYSTEMS, AND A MODEL IS NOT ONE.

    Art. 50(2) says it in terms — "providers of AI systems, including general-purpose AI systems" —
    and Art. 3(63) makes a general-purpose AI MODEL a distinct thing from the Art. 3(66) system
    BUILT ON one. A model card describing a text generator answers the cascade's transparency
    question easily, so nothing about the document stops the duty attaching; the tier has to.

    THE TIER CANNOT DO IT THROUGH `applies_to_risk_class`. The Art. 50 rules name no risk class at
    all — that is what makes them additive to every tier — so `_tier_or_duty_matches` returns on the
    duty and never reaches the tier test. `select_rules` returning early for OUT_OF_SCOPE is the
    only comparable guard, and GPAI_MODEL deliberately has no such return, because it owes
    Chapter V.

    Left unguarded, the failure is a manufactured GAP under Art. 50(2) in a report that says
    nothing was judged — and a provider that spends its attention on a marking duty it does not
    owe is not spending it on Art. 53(3).

    DERIVED: every duty at once, over every role the spec carries rules for."""
    model = a_use_case(risk_class=RiskClass.GPAI_MODEL)
    for role in roles_with_rules(spec):
        selected = select_rules(
            spec, model, role, transparency_duties=list(TransparencyDuty)
        ).all_rules
        offending = [r.rule_id for r in selected if r.applies_to_transparency_duty]
        assert not offending, (
            f"{offending} attach an Art. 50 duty to a general-purpose AI MODEL for the "
            f"{role.value} role. Art. 50 reaches providers and deployers of AI SYSTEMS."
        )


def test_only_chapter_iii_sections_1_to_3_carry_two_start_dates(spec):
    """The converse of the guard above, and the half a rule can slip through.

    Art. 113(c) defers Arts. 6 to 27 and nothing else. A rule OUTSIDE that range carrying the
    split states a date the Article does not give it, and `reporting._outstanding_block` prints
    that date to the reader as the day the duty begins — so the error is a live obligation
    presented as a future one. The forward guard cannot see it: it iterates the rules inside the
    range and never asks which rules outside it also took the split."""
    outside = [
        r.rule_id
        for r in spec.rules
        if r.effective_date_by_route and r.source.article not in _ROUTE_SPLIT_ARTICLES
    ]
    assert not outside, (
        f"{outside} cite an article outside Chapter III Sections 1-3 and carry two start dates. "
        f"Art. 113 gives those articles one date; state it as `effective_date`."
    )


# --- Art. 5(1)(h) — the one prohibition with a lawful branch --------------------------------------

_ART_5_LAWFUL_BRANCH = {"AIA-RULE-DP-A05-2", "AIA-RULE-DP-A05-3", "AIA-RULE-DP-A05-4"}
# The ban itself as a duty: points (ba) and (bb) apply later than the rest, hence two rules.
_ART_5_BAN = {"AIA-RULE-ALL-A05-1", "AIA-RULE-ALL-A05-1BA"}


def test_the_lawful_branch_duties_reach_only_the_practice_that_has_one(spec):
    """Art. 5(2) to (4) are conditions on point (h) and on nothing else in the Article.

    Every other point of Art. 5(1) bans outright: a system classified prohibited for social scoring
    owes withdrawal, and listing a fundamental rights impact assessment beside that would describe a
    route the Act does not open. Point (h) is drafted the other way — banned "unless and in so far
    as such use is strictly necessary", with Art. 5(5) letting a Member State authorise it — so a
    deployer there owes the paragraphs that condition the exception."""
    use_case = a_use_case(risk_class=RiskClass.PROHIBITED, area=None, product=None)
    lawful = select_rules(
        spec,
        use_case,
        ActorRole.DEPLOYER,
        prohibited_practice=ProhibitedPractice.REALTIME_REMOTE_BIOMETRIC_IDENTIFICATION,
    )
    assert {r.rule_id for r in lawful.all_rules} == _ART_5_LAWFUL_BRANCH | {"AIA-RULE-ALL-A05-1"}

    for practice in ProhibitedPractice:
        if practice is ProhibitedPractice.REALTIME_REMOTE_BIOMETRIC_IDENTIFICATION:
            continue
        other = select_rules(spec, use_case, ActorRole.DEPLOYER, prohibited_practice=practice)
        selected = [r.rule_id for r in other.all_rules]
        assert len(selected) == 1 and selected[0] in _ART_5_BAN, (
            f"{practice.value} bans outright and owes withdrawal alone, but {selected} were "
            "selected for it"
        )


def test_a_prohibited_classification_never_reaches_a_chapter_iii_duty(spec):
    """Checking documentation against Chapter III would tell a reader the system ships once the
    paperwork is fixed. Nothing in Chapter III names this tier, and this holds it that way.

    Art. 5's own conditions are a different thing and are the reason the tier reaches selection at
    all: they say what the Article costs a deployer holding the national authorisation, and saying
    so implies nothing about whether the system may be placed on the market."""
    use_case = a_use_case(risk_class=RiskClass.PROHIBITED, area=None, product=None)
    for role in ActorRole:
        active = select_rules(
            spec,
            use_case,
            role,
            prohibited_practice=ProhibitedPractice.REALTIME_REMOTE_BIOMETRIC_IDENTIFICATION,
        )
        for rule in active.all_rules:
            assert rule.rule_id in _ART_5_LAWFUL_BRANCH | _ART_5_BAN, (
                f"{rule.rule_id} was selected for a prohibited system. Only Art. 5's own "
                f"ban and conditions belong here — nothing in Chapter III applies to a banned "
                f"practice."
            )


def test_the_practice_gate_is_the_only_thing_holding_those_duties_back(spec):
    """A prohibited classification whose practice is unknown selects nothing, rather than
    everything. `None` reaches this function when the cascade abstained at `prohibited` — and a
    fundamental rights impact assessment asserted on an unidentified practice is an invented duty
    in the same way Art. 25(2) would be."""
    use_case = a_use_case(risk_class=RiskClass.PROHIBITED, area=None, product=None)
    silent = select_rules(spec, use_case, ActorRole.DEPLOYER, prohibited_practice=None)
    assert not silent.all_rules
