"""Rule ACTIVATION — which obligations a classified use case actually owes.

The headline here is Art. 43. Conformity assessment is not one duty with one citation: an Annex III
point 1 system may need a notified body (43(1)), points 2 to 8 self-assess under Annex VI (43(2)),
and an Annex I system follows its own sectoral act instead (43(3)). Three mutually exclusive
branches, and the spec used to carry one of them — 43(2), written for employment — and fire it at
all three. A wrong citation is worse than a missing one: it is a confident instruction to follow
law that does not govern you.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from aiact.gap.rules import select_rules
from aiact.policy_loader import load_policy_spec
from aiact.schemas.classification import ClassificationEvidence, UseCaseClassification
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    AnnexIProduct,
    HighRiskRoute,
    RiskClass,
)
from aiact.schemas.policy import LegalSource, PolicyRule

ACT_DATE = date(2024, 7, 12)


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def a_use_case(
    area: AnnexIIIArea | None = None, product: AnnexIProduct | None = None
) -> UseCaseClassification:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=ACT_DATE
    )
    return UseCaseClassification(
        use_case_id="uc",
        description="a system",
        annex_iii_area=area,
        annex_i_product=product,
        risk_class=RiskClass.HIGH_RISK,
        reasoning="fixture",
        confidence="high",
        triggered_by=[ClassificationEvidence(source=source, reasoning="fixture")],
    )


def _rule_ids(spec, use_case, role=ActorRole.PROVIDER) -> set[str]:
    return {r.rule_id for r in select_rules(spec, use_case, role).all_rules}


# --- Art. 43 — one duty, three bodies of law ------------------------------------------------------
@pytest.mark.parametrize(
    "area,expected",
    [
        (AnnexIIIArea.BIOMETRICS, "AIA-PO-A43-1"),
        (AnnexIIIArea.EMPLOYMENT, "AIA-PO-A43-2"),
        (AnnexIIIArea.CRITICAL_INFRASTRUCTURE, "AIA-PO-A43-2"),
        (AnnexIIIArea.JUSTICE_DEMOCRACY, "AIA-PO-A43-2"),
    ],
)
def test_the_conformity_route_follows_the_annex_iii_point(spec, area, expected):
    """43(1) reaches point 1 alone; 43(2) reaches points 2 to 8. Exactly one fires per area, and
    never the other — a system told to self-assess when it needs a notified body has been given a
    clean bill of health it did not earn."""
    ids = _rule_ids(spec, a_use_case(area=area))
    art43 = {r for r in ids if r.startswith("AIA-PO-A43")}
    assert art43 == {expected}


def test_an_annex_i_system_follows_its_own_legislation(spec):
    """Art. 43(3): the sectoral act supplies the procedure, not this Regulation. Both Annex III
    branches are silent here — neither was written for a system with no Annex III area at all."""
    ids = _rule_ids(spec, a_use_case(product=AnnexIProduct.MEDICAL_DEVICES))
    art43 = {r for r in ids if r.startswith("AIA-PO-A43")}
    assert art43 == {"AIA-PO-A43-3"}


def test_every_high_risk_system_owes_exactly_one_conformity_rule(spec):
    """The three branches partition high risk: no system may owe two conformity procedures, and
    none may owe none. A gap here reads in a report as "no conformity assessment required"."""
    cases = [a_use_case(area=area) for area in AnnexIIIArea] + [
        a_use_case(product=p) for p in AnnexIProduct if p.chapter_iii_applies
    ]
    for uc in cases:
        art43 = {r for r in _rule_ids(spec, uc) if r.startswith("AIA-PO-A43")}
        label = uc.annex_iii_area or uc.annex_i_product
        assert len(art43) == 1, f"{label}: expected one Art. 43 rule, got {sorted(art43)}"


# --- Art. 49 — the exception that used to be ignored ----------------------------------------------
def test_critical_infrastructure_owes_no_registration(spec):
    """Art. 49(1) reaches Annex III "with the exception of point 2". The rule was written for
    employment and gated on the tier, so it raised registration against point 2 as well."""
    critical = _rule_ids(spec, a_use_case(area=AnnexIIIArea.CRITICAL_INFRASTRUCTURE))
    assert "AIA-PO-A49" not in critical
    assert "AIA-PO-A49" in _rule_ids(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT))


def test_an_annex_i_system_is_not_registered_under_article_49(spec):
    """49(1) reaches systems "listed in Annex III". An Annex I one is not."""
    assert "AIA-PO-A49" not in _rule_ids(spec, a_use_case(product=AnnexIProduct.MEDICAL_DEVICES))


def test_law_enforcement_registers_in_the_non_public_section(spec):
    """Art. 49(4) does not replace the registration — it says where it goes and how little it
    carries. Both rules fire, and only in the areas the paragraph names."""
    police = _rule_ids(spec, a_use_case(area=AnnexIIIArea.LAW_ENFORCEMENT))
    assert {"AIA-PO-A49", "AIA-PO-A49-4"} <= police

    hiring = _rule_ids(spec, a_use_case(area=AnnexIIIArea.EMPLOYMENT))
    assert "AIA-PO-A49-4" not in hiring


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
        assert {"AIA-HR-A09", "AIA-HR-A15", "AIA-PO-A17"} <= ids


def test_an_area_condition_cannot_also_claim_the_annex_i_route():
    """Such a rule could never fire — an Annex I use case carries no Annex III area — and a rule
    that never fires is indistinguishable in a report from an obligation nobody owes."""
    with pytest.raises(ValueError, match="could never activate"):
        PolicyRule(
            rule_id="BAD",
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

    assert "AIA-DP-A27" in {r.rule_id for r in active.not_document_verifiable}


def test_a_narrowed_duty_names_the_organisations_it_binds(spec):
    """The narrowing is only useful if it says WHICH organisations are caught — and it must say so
    about the parties, not about "you". This report describes what the Act requires of each role
    for this system; it is not addressed to whoever happens to be reading, and the deployer it
    describes is often not the organisation that wrote the document."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-DP-A27")
    condition = rule.activation_condition

    assert condition is not None
    assert "governed by public law" in condition
    assert "5(b)" in condition and "5(c)" in condition
    assert not re.search(r"\byou(r|rs|rself)?\b", condition, re.I)


def test_art_27_never_reaches_the_systems_it_excludes(spec):
    """Art. 27(1) reaches Art. 6(2) systems "with the exception of" Annex III point 2. An Annex I
    safety component is not an Art. 6(2) system at all, so it is outside on the same words."""
    for uc in (
        a_use_case(area=AnnexIIIArea.CRITICAL_INFRASTRUCTURE),
        a_use_case(product=AnnexIProduct.MEDICAL_DEVICES),
    ):
        assert "AIA-DP-A27" not in _rule_ids(spec, uc, ActorRole.DEPLOYER)


def test_a_narrowed_duty_is_selected_exactly_like_an_unnarrowed_one(spec):
    """`activation_condition` is reporting, not filtering. A rule carrying one is selected by the
    same conditions as any other and lands in the same buckets — the only difference is that the
    reader is told which members of the role owe it."""
    narrowed = [r for r in spec.rules if r.activation_condition is not None]
    assert narrowed, "the mechanism is unused — Art. 27 should carry it"
    for rule in narrowed:
        for role in rule.applies_to_role:
            for area in rule.applies_to_annex_iii_area or list(AnnexIIIArea):
                active = select_rules(spec, a_use_case(area=area), role)
                assert rule.rule_id in {r.rule_id for r in active.all_rules}, (
                    f"{rule.rule_id} states a condition and was withheld for {role}/{area} — "
                    f"a condition is reported beside a duty, never used to drop it"
                )
