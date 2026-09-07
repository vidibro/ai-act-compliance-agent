"""Layer 1 (classification) golden-set integrity tests.

The headline test is `test_the_flip_case_flips`: two descriptions one sentence apart resolve to
different risk classes. That is the project's differentiator, pinned as data before the classifier
that must reproduce it exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.eval.classification_cases import load_classification_cases
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    DerogationCondition,
    ProhibitedPractice,
    ProviderReallocation,
    RiskClass,
    ScopeExclusion,
    TerritorialLink,
    TransparencyDuty,
)
from aiact.schemas.eval import ClassificationCase, Difficulty

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "golden_set" / "classification_cases.yaml"


@pytest.fixture(scope="module")
def cases():
    return load_classification_cases(CASES_PATH)


def _by_id(cases):
    return {c.case_id: c for c in cases.cases}


def test_loads_and_ids_unique(cases):
    ids = [c.case_id for c in cases.cases]
    assert ids
    assert len(ids) == len(set(ids))
    assert cases.act_version_date == "2026-07-27"


def test_the_flip_case_flips(cases):
    """THE HEADLINE. cv_parsing_fields and cv_parsing_plus_scoring differ by ~one sentence, and the
    risk class flips not_high_risk -> high_risk via the Art. 6(3) profiling carve-back."""
    c = _by_id(cases)
    parser = c["cv_parsing_fields"]
    scorer = c["cv_parsing_plus_scoring"]

    assert parser.expected_risk_class == RiskClass.NOT_HIGH_RISK
    assert scorer.expected_risk_class == RiskClass.HIGH_RISK
    assert scorer.flips_from == "cv_parsing_fields"

    # The carve-back is the reason: the scorer profiles, the parser is a narrow procedural task.
    assert scorer.expected_performs_profiling is True
    assert scorer.expected_derogation is None
    assert parser.expected_performs_profiling is False
    assert parser.expected_derogation == DerogationCondition.NARROW_PROCEDURAL_TASK
    assert parser.expected_annex_iii_area == AnnexIIIArea.EMPLOYMENT
    assert scorer.expected_annex_iii_area == AnnexIIIArea.EMPLOYMENT


def test_flip_pair_shares_almost_all_text(cases):
    """A keyword classifier can't tell them apart — that is the point. Their descriptions overlap
    heavily; only the decisive sentence differs."""
    c = _by_id(cases)
    a = set(c["cv_parsing_fields"].description.split())
    b = set(c["cv_parsing_plus_scoring"].description.split())
    overlap = len(a & b) / len(a | b)
    assert overlap > 0.55, f"flip pair should share most words (Jaccard={overlap:.2f})"


def test_all_risk_classes_are_represented(cases):
    """Every outcome the cascade can produce, NEEDS_REVIEW included.

    That last one was missing for a while: the only ambiguous case (emotion_screening_candidates)
    resolved to `prohibited` once Commission guidance C(2025) 5052 settled the hiring-context
    question, and nothing replaced it. `ats_workflow_unspecified` restores it from the other
    direction — not contested law, but a description that never supplies the decisive fact."""
    present = {c.expected_risk_class for c in cases.cases}
    for rc in RiskClass:
        assert rc in present, f"no case exercises {rc}"


def test_both_emotion_cases_are_prohibited_one_via_guidance(cases):
    """Both emotion-recognition cases are prohibited, but by different routes — and the one that
    relies on non-binding Commission interpretation says so with a guidance_ref."""
    c = _by_id(cases)

    # Employee monitoring: prohibited on the bare Article 5 text — no guidance needed.
    workplace = c["emotion_monitoring_employees"]
    assert workplace.expected_risk_class == RiskClass.PROHIBITED
    assert workplace.expected_prohibited is True
    assert workplace.guidance_refs == []

    # Recruitment: prohibited only because guidance reads 'workplace' to cover hiring — so the label
    # must carry the (non-binding) basis it rests on.
    recruitment = c["emotion_screening_candidates"]
    assert recruitment.expected_risk_class == RiskClass.PROHIBITED
    assert recruitment.expected_prohibited is True
    assert recruitment.guidance_refs == ["C-2025-5052/workplace-covers-recruitment"]


def test_transparency_obligation_can_attach_to_minimal_risk(cases):
    c = _by_id(cases)
    ad = c["job_ad_generation"]
    assert ad.expected_risk_class == RiskClass.MINIMAL
    assert ad.expected_transparency_obligation is True


def test_a_renamed_pin_is_rejected_rather_than_dropped(cases):
    """`extra="forbid"`. A misspelled or renamed key would otherwise be ignored, leaving the YAML
    reading as though a node were pinned while it silently went unmeasured — the exact blindness
    per-node scoring exists to surface."""
    with pytest.raises(ValueError, match="expected_transparancy_duties"):
        ClassificationCase(
            case_id="typo",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.MINIMAL,
            expected_transparancy_duties=[],  # note the typo
            decisive_fact="a fact long enough to pass",
            difficulty="obvious",
        )


def test_every_case_states_a_decisive_fact(cases):
    for c in cases.cases:
        assert len(c.decisive_fact.strip()) > 20, f"{c.case_id} has no real decisive_fact"


# --- Art. 3(1) ------------------------------------------------------------------------------------
def test_every_case_argues_whether_it_is_an_ai_system(cases):
    """Stricter than the schema, and for the reason the Art. 50 twin exists: this label was a
    default nobody had to defend. Every case said `true`, the column read "every expected answer
    identical — unmeasured" on every run, and when rule-based systems were finally examined two
    labels were wrong. A basis makes the claim checkable at authoring time."""
    for c in cases.cases:
        basis = c.is_ai_basis.strip()
        assert len(basis) > 20, f"{c.case_id} asserts an Art. 3(1) label without argument"
        assert "infer" in basis.lower(), (
            f"{c.case_id}: Art. 3(1) turns on INFERENCE, so the basis must speak to it — "
            f"sophistication is not the test"
        )


def test_the_is_ai_column_is_not_answerable_by_a_constant(cases):
    """`is_ai` is the FIRST node and a `false` routes straight to minimal, skipping Art. 2, Art. 5
    and both Art. 6 doors. A set that only ever expects `true` cannot tell a working node from one
    that always agrees — on the node where a wrong answer clears any system there is."""
    labels = [c.expected_is_ai_system for c in cases.cases]
    assert any(labels) and not all(labels), "the set must exercise both answers"


def test_both_sides_of_the_inference_line_are_traps(cases):
    """Cheap `false` cases would teach the wrong rule — that plain-looking software is not AI. The
    set carries the mirror pair: a rule engine deep inside recruitment that infers nothing, and a
    spreadsheet add-in that fits a model."""
    c = _by_id(cases)
    rules_engine = c["panel_conflict_rule_checker"]
    assert rules_engine.expected_is_ai_system is False
    assert rules_engine.expected_risk_class == RiskClass.MINIMAL

    looks_humble = c["absence_pattern_spreadsheet_addin"]
    assert looks_humble.expected_is_ai_system is True
    assert looks_humble.expected_risk_class == RiskClass.HIGH_RISK


# --- Art. 50 ------------------------------------------------------------------------------------
def test_emotion_recognition_systems_owe_art_50_transparency(cases):
    """Art. 50(3) binds deployers of an EMOTION RECOGNITION SYSTEM to inform those exposed. It
    attaches to the system type and has only a law-enforcement carve-out — the Art. 5 prohibition
    does not disapply it. Both labels said `false` until 2026-07-22; the model said `true` and had
    the better textual argument."""
    c = _by_id(cases)
    for case_id in ("emotion_monitoring_employees", "emotion_screening_candidates"):
        case = c[case_id]
        assert case.expected_prohibited is True
        assert case.expected_transparency_duties == [
            TransparencyDuty.EMOTION_OR_BIOMETRIC_CATEGORISATION
        ], f"{case_id}: Art. 50(3) attaches"
        assert "50(3)" in case.transparency_basis
        # And it is the DEPLOYER's duty, not the provider's — the half a boolean could not carry.
        assert case.expected_transparency_duties[0].owed_by == ActorRole.DEPLOYER


def test_the_flip_changes_the_tier_and_leaves_art_50_alone(cases):
    """The two axes are independent, and the flip pair is where that is provable: one added
    sentence moves not_high_risk -> high_risk while Art. 50 stays false on both."""
    c = _by_id(cases)
    before, after = c["cv_parsing_fields"], c["cv_parsing_plus_scoring"]
    assert before.expected_risk_class != after.expected_risk_class
    assert before.expected_transparency_obligation is False
    assert after.expected_transparency_obligation is False


def test_every_case_argues_its_art_50_label_either_way(cases):
    """Stricter than the schema, which only compels a basis when the obligation is TRUE. The labels
    that were wrong were all `false` — a default nobody had to defend. In the committed answer key
    every case defends its Art. 50 position, whichever way it lands."""
    for c in cases.cases:
        basis = c.transparency_basis.strip()
        assert len(basis) > 20, f"{c.case_id} asserts an Art. 50 label without argument"
        assert "50(" in basis, f"{c.case_id} names no Art. 50 paragraph"


# --- needs_review via INSUFFICIENT INPUT --------------------------------------------------------
def test_needs_review_coverage_exists_again(cases):
    """Lost when emotion_screening_candidates resolved to prohibited. Restored WITHOUT needing a
    contested legal question: here the law is clear and the description is silent."""
    review = [c for c in cases.cases if c.expected_risk_class == RiskClass.NEEDS_REVIEW]
    assert review, "no case exercises NEEDS_REVIEW ground truth"


def test_the_insufficient_case_pins_nothing_it_cannot_know(cases):
    """The decisive sub-answers must be null, not `false`. Recording `performs_profiling: false`
    would assert the system does not evaluate people — which is precisely the inference from
    silence this case exists to forbid."""
    c = _by_id(cases)["ats_workflow_unspecified"]
    assert c.expected_risk_class == RiskClass.NEEDS_REVIEW
    assert c.difficulty == Difficulty.INSUFFICIENT
    assert c.expected_performs_profiling is None
    assert c.expected_derogation is None, "a derogation inferred from silence is unsupported"


def test_the_insufficient_case_is_silent_not_negative(cases):
    """Its whole value is the ABSENCE of the decisive fact. If the description ever states that the
    system does not evaluate candidates, it stops being undecidable and becomes interview_scheduler
    — that one sentence is the entire difference between the two cases."""
    c = _by_id(cases)
    undecidable = c["ats_workflow_unspecified"].description.lower()
    for negation in ("does not assess", "does not rank", "does not evaluate", "no evaluation"):
        assert negation not in undecidable, f"{negation!r} would make this case decidable"
    for claim in ("score", "ranks", "fit", "predict"):
        assert claim not in undecidable, f"{claim!r} would make this case decidable the other way"
    # the sibling it must NOT collapse into does state it
    assert "does not assess" in c["interview_scheduler"].description.lower()


def test_insufficient_is_not_the_same_band_as_ambiguous(cases):
    """`ambiguous` is contested LAW; `insufficient` is missing INPUT. Averaging them would make
    per-difficulty reporting meaningless, which is the only reason the band exists."""
    assert Difficulty.INSUFFICIENT != Difficulty.AMBIGUOUS
    by_band = {c.case_id: c.difficulty for c in cases.cases}
    assert by_band["ats_workflow_unspecified"] == Difficulty.INSUFFICIENT


def test_a_true_art_50_label_cannot_be_asserted_without_a_basis():
    with pytest.raises(ValueError, match="transparency_basis is empty"):
        ClassificationCase(
            case_id="bare",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.MINIMAL,
            expected_transparency_duties=[TransparencyDuty.DIRECT_INTERACTION],
            decisive_fact="a fact long enough to pass",
            difficulty="obvious",
        )


def test_current_cases_are_all_dev(cases):
    """Mirrors the Layer 2 decision: current cases are dev; held-out test authored later."""
    assert {c.split for c in cases.cases} == {"dev"}
    assert cases.for_split("test") == []


# --- validator behaviour: the answer key cannot contradict the law ------------------------------
def test_profiling_true_forces_high_risk():
    with pytest.raises(ValueError, match="carve-back forces high_risk"):
        ClassificationCase(
            case_id="bad",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.NOT_HIGH_RISK,
            expected_performs_profiling=True,
            decisive_fact="profiling but mislabelled not-high-risk",
            difficulty="obvious",
        )


def test_profiling_true_forbids_derogation():
    with pytest.raises(ValueError, match="no derogation can apply"):
        ClassificationCase(
            case_id="bad",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.HIGH_RISK,
            expected_performs_profiling=True,
            expected_derogation=DerogationCondition.NARROW_PROCEDURAL_TASK,
            decisive_fact="profiling with a contradictory derogation",
            difficulty="obvious",
        )


def test_prohibited_flag_must_match_class():
    with pytest.raises(ValueError, match="exactly when the class is PROHIBITED"):
        ClassificationCase(
            case_id="bad",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.HIGH_RISK,
            expected_prohibited_practice=ProhibitedPractice.SOCIAL_SCORING,
            decisive_fact="a named Art. 5 point but a high_risk class",
            difficulty="obvious",
        )


def test_derogation_implies_not_high_risk():
    with pytest.raises(ValueError, match="must be\\s+not_high_risk"):
        ClassificationCase(
            case_id="bad",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.MINIMAL,
            expected_derogation=DerogationCondition.PREPARATORY_TASK,
            expected_poses_significant_risk=False,
            decisive_fact="derogation but labelled minimal",
            difficulty="obvious",
        )


def _derogation_case(**overrides) -> ClassificationCase:
    kwargs = dict(
        case_id="bad",
        expected_is_ai_system=True,
        description="d",
        expected_risk_class=RiskClass.NOT_HIGH_RISK,
        expected_derogation=DerogationCondition.NARROW_PROCEDURAL_TASK,
        expected_poses_significant_risk=False,
        decisive_fact="narrow procedural task nobody relies on",
        difficulty="obvious",
    )
    kwargs.update(overrides)
    return ClassificationCase(**kwargs)


def test_a_derogation_case_must_answer_both_limbs():
    """Art. 6(3) exempts on a condition AND no significant risk of harm. A case naming only the
    condition pins half the test, and the half it omits is the one that decides the tier."""
    with pytest.raises(ValueError, match="conjunction"):
        _derogation_case(expected_poses_significant_risk=None)


def test_the_chapeau_answer_decides_which_tier_the_case_claims():
    """The SAME condition lands on two tiers. Both pairings must be constructible, and each must
    force its own class — otherwise the key could assert a condition exempts on its own."""
    assert _derogation_case().expected_risk_class == RiskClass.NOT_HIGH_RISK
    assert (
        _derogation_case(
            expected_poses_significant_risk=True, expected_risk_class=RiskClass.HIGH_RISK
        ).expected_risk_class
        == RiskClass.HIGH_RISK
    )
    with pytest.raises(ValueError, match="must be high_risk"):
        _derogation_case(expected_poses_significant_risk=True)


def test_the_chapeau_is_not_pinnable_without_a_condition():
    """It is only reached once one of (a)-(d) is met, so an answer to it alone describes a
    question the cascade never puts."""
    with pytest.raises(ValueError, match="only reached once one of"):
        _derogation_case(expected_derogation=None, expected_risk_class=RiskClass.HIGH_RISK)


def _scope_case(**overrides) -> ClassificationCase:
    kwargs = dict(
        case_id="s",
        expected_is_ai_system=True,
        description="d",
        expected_risk_class=RiskClass.OUT_OF_SCOPE,
        expected_scope_exclusion=ScopeExclusion.SCIENTIFIC_RESEARCH,
        scope_exclusion_basis="Art. 2(6): built for the sole purpose of research.",
        decisive_fact="sole purpose scientific research",
        difficulty="obvious",
    )
    kwargs.update(overrides)
    return ClassificationCase(**kwargs)


def test_an_ordinary_exclusion_and_the_class_are_the_same_fact():
    """Every Art. 2 exclusion but one is unconditional on the facts of the system, so naming it and
    naming OUT_OF_SCOPE are two ways of saying the same thing."""
    assert _scope_case().expected_risk_class == RiskClass.OUT_OF_SCOPE
    with pytest.raises(ValueError, match="same fact stated two ways"):
        _scope_case(expected_risk_class=RiskClass.MINIMAL)


def test_art_2_12_may_name_its_paragraph_and_still_be_governed():
    """THE EXCEPTION, and the graph is built around it. A free and open-source answer FALLS THROUGH
    the cascade, because Art. 2(12)'s carve-back names high-risk, Art. 5 and Art. 50 — the very
    questions the remaining nodes answer. So such a case legitimately ends at `minimal` while the
    scope node answered `free_open_source`, and a key that could not say so would mark a correct
    run wrong for describing the route the graph actually takes."""
    case = _scope_case(
        expected_risk_class=RiskClass.MINIMAL,
        expected_scope_exclusion=ScopeExclusion.FREE_OPEN_SOURCE,
        scope_exclusion_basis="Art. 2(12): Apache 2.0, lifted because Art. 50(2) attaches.",
        expected_transparency_duties=[TransparencyDuty.SYNTHETIC_CONTENT_MARKING],
        transparency_basis="Art. 50(2): every output is synthetic audio.",
    )
    assert case.expected_scope_exclusion is ScopeExclusion.FREE_OPEN_SOURCE
    # And because it falls through, it both may and must pin the Art. 6 answers on the way past.
    assert _scope_case(
        expected_risk_class=RiskClass.MINIMAL,
        expected_scope_exclusion=ScopeExclusion.FREE_OPEN_SOURCE,
        scope_exclusion_basis="Art. 2(12): permissively licensed, and no carve-back applies.",
        expected_annex_iii_area=None,
    )


def test_out_of_scope_must_say_which_of_the_two_routes_put_it_there():
    """OUT_OF_SCOPE is reached two ways and they are different findings: an exclusion carved out
    of a Regulation that applies, or Art. 2(1) never reaching the system. A case must name one."""
    with pytest.raises(ValueError, match="names neither an Art. 2 exclusion"):
        _scope_case(expected_scope_exclusion=None, scope_exclusion_basis="")


def test_a_system_the_regulation_never_reaches_needs_no_exclusion():
    """Art. 2(1) failing is not an exclusion — nothing was carved out — so such a case names no
    paragraph of (3)-(12), and may not claim one."""
    outside = _scope_case(
        expected_scope_exclusion=None,
        scope_exclusion_basis="",
        expected_territorial_link=TerritorialLink.OUTSIDE_UNION,
    )
    assert outside.expected_risk_class == RiskClass.OUT_OF_SCOPE

    with pytest.raises(ValueError, match="cannot also be excluded"):
        _scope_case(expected_territorial_link=TerritorialLink.OUTSIDE_UNION)
    with pytest.raises(ValueError, match="has no tier"):
        _scope_case(
            expected_risk_class=RiskClass.MINIMAL,
            expected_scope_exclusion=None,
            scope_exclusion_basis="",
            expected_territorial_link=TerritorialLink.OUTSIDE_UNION,
        )


def test_a_concluding_exclusion_cannot_carry_art_6_answers():
    """Art. 6 classifies systems the Regulation governs, so an excluded one never reaches it —
    unless the exclusion is the one that falls through."""
    with pytest.raises(ValueError, match="never reached by it"):
        _scope_case(expected_annex_iii_area=AnnexIIIArea.EMPLOYMENT)


def test_dangling_flips_from_is_rejected(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text(
        "act_version_date: 2026-07-27\n"
        "default_split: dev\n"
        "cases:\n"
        "  - case_id: only\n"
        "    description: d\n"
        "    expected_risk_class: minimal\n"
        "    expected_is_ai_system: true\n"
        "    decisive_fact: a lonely case pointing nowhere in particular\n"
        "    difficulty: obvious\n"
        "    flips_from: does_not_exist\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="names no case"):
        load_classification_cases(bad)


# --- where a case gives up ------------------------------------------------------------------
def _case_yaml(tmp_path, body: str):
    p = tmp_path / "c.yaml"
    p.write_text(
        "act_version_date: 2026-07-27\ndefault_split: dev\ncases:\n" + body, encoding="utf-8"
    )
    return p


def test_needs_review_requires_an_abstention_point(tmp_path):
    """The class says a run should decline; it does not say WHERE, and the two are different
    claims. Without the node, a model that ducks a question it could have answered still lands on
    the right label and nothing can tell the difference."""
    bad = _case_yaml(
        tmp_path,
        "  - case_id: x\n"
        "    description: d\n"
        "    expected_risk_class: needs_review\n"
        "    expected_is_ai_system: true\n"
        "    decisive_fact: the description never says what it ranks on\n"
        "    difficulty: insufficient\n",
    )
    with pytest.raises(ValueError, match="expected_abstains_at"):
        load_classification_cases(bad)


def test_an_abstention_point_off_the_route_is_rejected(tmp_path):
    """Naming a node the cascade never reaches describes a run that cannot happen."""
    bad = _case_yaml(
        tmp_path,
        "  - case_id: x\n"
        "    description: d\n"
        "    expected_risk_class: needs_review\n"
        "    expected_is_ai_system: true\n"
        "    expected_abstains_at: derogation\n"
        "    expected_annex_i_product: null\n"
        "    expected_annex_iii_area: null\n"
        "    decisive_fact: no Annex III area, so profiling and derogation are never asked\n"
        "    difficulty: insufficient\n",
    )
    with pytest.raises(ValueError, match="never reaches that node"):
        load_classification_cases(bad)


def test_pins_past_the_abstention_point_are_rejected(tmp_path):
    """Once a node abstains the cascade stops, so every question after it is never put. Pinning one
    states an answer for a question nobody asked."""
    bad = _case_yaml(
        tmp_path,
        "  - case_id: x\n"
        "    description: d\n"
        "    expected_risk_class: needs_review\n"
        "    expected_is_ai_system: true\n"
        "    expected_abstains_at: annex_iii\n"
        "    expected_annex_i_product: null\n"
        "    expected_performs_profiling: false\n"
        "    decisive_fact: the domain is never stated\n"
        "    difficulty: insufficient\n",
    )
    with pytest.raises(ValueError, match="questions never put"):
        load_classification_cases(bad)


def test_every_needs_review_case_names_where_it_gives_up(cases):
    """And the node it names is one the cascade actually has."""
    from aiact.eval.node_score import NODE_KEYS

    review = [c for c in cases.cases if c.expected_risk_class == RiskClass.NEEDS_REVIEW]
    assert review
    for c in review:
        assert c.expected_abstains_at in NODE_KEYS, c.case_id


# --- Art. 25 — the answer key's own role question ------------------------------------------------
def test_a_reallocation_can_only_be_claimed_by_a_high_risk_case():
    """Art. 25(1) reallocates the provider of "a high-risk AI system" and 25(3) of a high-risk
    safety component. A case labelling any other class with a limb asserts something the Article
    cannot support — and would pin a node the run never puts."""
    with pytest.raises(ValueError, match="of nothing else"):
        ClassificationCase(
            case_id="bad",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.MINIMAL,
            expected_provider_reallocation=ProviderReallocation.NAME_OR_TRADEMARK,
            provider_reallocation_basis="rebadged, but the system is not high-risk",
            decisive_fact="a reallocation claimed on a minimal-risk system",
            difficulty="obvious",
        )


def test_a_reallocation_must_show_its_working():
    """Same pairing as `scope_exclusion_basis`. Limb (b) is why: Art. 3(23) defines 'substantial
    modification' narrowly, and a label pinned on the word "customised" tests the wrong thing."""
    with pytest.raises(ValueError, match="provider_reallocation_basis is empty"):
        ClassificationCase(
            case_id="bad",
            expected_is_ai_system=True,
            description="d",
            expected_risk_class=RiskClass.HIGH_RISK,
            expected_annex_iii_area=AnnexIIIArea.EMPLOYMENT,
            expected_performs_profiling=True,
            expected_provider_reallocation=ProviderReallocation.SUBSTANTIAL_MODIFICATION,
            decisive_fact="a reallocation with no argument behind it",
            difficulty="obvious",
        )


def test_a_high_risk_case_must_pin_art_25(tmp_path):
    """The node is gated on the CLASS, not on the route, so the loader's reached-but-unpinned check
    has to know that. A high-risk case leaving it out leaves a question the run WILL ask with
    nothing to check it against."""
    bad = _case_yaml(
        tmp_path,
        "  - case_id: unpinned\n"
        "    description: d\n"
        "    expected_risk_class: high_risk\n"
        "    expected_is_ai_system: true\n"
        "    expected_annex_i_product: null\n"
        "    expected_annex_iii_area: employment\n"
        "    expected_performs_profiling: true\n"
        "    expected_transparency_duties: []\n"
        "    decisive_fact: high risk by profiling, silent on who the provider is\n"
        "    difficulty: obvious\n",
    )
    with pytest.raises(ValueError, match="provider_reallocation.*is not set"):
        load_classification_cases(bad)


def test_art_25_is_measured_in_both_directions(cases):
    """A column whose every expected answer is None measures the base rate, not the node — and this
    node's failure mode IS silence, so the positive cases are the ones that measure anything."""
    high_risk = [c for c in cases.cases if c.expected_risk_class == RiskClass.HIGH_RISK]
    claimed = {c.expected_provider_reallocation for c in high_risk}
    assert None in claimed, "no case exercises the ordinary answer"
    assert set(ProviderReallocation) <= claimed, "every Art. 25 limb needs a case"


def test_the_annex_iii_areas_nothing_measures_are_declared(cases):
    """THE HOLE THAT LET THE `annex_iii` PROMPT BE WRONG ABOUT CRITICAL INFRASTRUCTURE.

    That node's tests (i) and (ii) ask whether a purpose acts on a PERSON. Seven areas are about
    people and one — point 2, critical infrastructure — is about pipes, roads and grids, so a
    signal controller answered the OUT test word for word and came back `none`. Nothing caught it
    because 14 of the classified cases are employment and four areas have no case at all: an area
    nothing measures is an area whose prompt wording is an assertion.

    Declared rather than asserted empty, because authoring a case needs a real document and the
    discipline is that cases come before numbers. The set may only SHRINK."""
    unmeasured = {
        AnnexIIIArea.CRITICAL_INFRASTRUCTURE,
        AnnexIIIArea.EDUCATION,
        AnnexIIIArea.JUSTICE_DEMOCRACY,
    }
    measured = {c.expected_annex_iii_area for c in cases.cases} - {None}
    assert not (measured & unmeasured), (
        f"declared unmeasured but a case now exercises it: {sorted(measured & unmeasured)}. "
        f"Remove it from the set."
    )
    still_missing = set(AnnexIIIArea) - measured - unmeasured
    assert not still_missing, (
        f"no case exercises {sorted(still_missing)}, and it is not declared. Author a case, or "
        f"declare it here with the reason the area goes unmeasured."
    )


def test_every_art_25_limb_can_cite_itself():
    """A limb added without its citation would be reported under a paragraph belonging to another
    one — the same failure `_PROHIBITED_POINT` guards against."""
    assert [r.citation for r in ProviderReallocation] == [
        "Art. 25(1)(a)",
        "Art. 25(1)(b)",
        "Art. 25(1)(c)",
        "Art. 25(3)",
    ]
