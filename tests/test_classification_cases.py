"""Layer 1 (classification) golden-set integrity tests.

The headline test is `test_the_flip_case_flips`: two descriptions one sentence apart resolve to
different risk classes. That is the project's differentiator, pinned as data before the classifier
that must reproduce it exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.eval.classification_cases import load_classification_cases
from aiact.schemas.enums import AnnexIIIArea, DerogationCondition, RiskClass
from aiact.schemas.eval import ClassificationCase

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
    assert cases.act_version_date == "2024-07-12"


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


def test_decidable_risk_classes_are_represented(cases):
    """The set exercises every DECIDABLE outcome.

    NEEDS_REVIEW is deliberately absent: the one ambiguous case (emotion_screening_candidates) was
    resolved to `prohibited` once Commission guidance C(2025) 5052 settled the hiring-context
    question. The abstention PATH is still covered by the graph routing tests (low confidence ->
    needs_review), but Layer 1 now lacks a genuinely-ambiguous GROUND-TRUTH case. That is a known
    gap — a fresh ambiguous case should be authored to restore needs_review coverage here (see
    ROADMAP)."""
    present = {c.expected_risk_class for c in cases.cases}
    for rc in (
        RiskClass.PROHIBITED,
        RiskClass.HIGH_RISK,
        RiskClass.NOT_HIGH_RISK,
        RiskClass.MINIMAL,
    ):
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


def test_every_case_states_a_decisive_fact(cases):
    for c in cases.cases:
        assert len(c.decisive_fact.strip()) > 20, f"{c.case_id} has no real decisive_fact"


def test_current_cases_are_all_dev(cases):
    """Mirrors the Layer 2 decision: current cases are dev; held-out test authored later."""
    assert {c.split for c in cases.cases} == {"dev"}
    assert cases.for_split("test") == []


# --- validator behaviour: the answer key cannot contradict the law ------------------------------
def test_profiling_true_forces_high_risk():
    with pytest.raises(ValueError, match="carve-back forces high_risk"):
        ClassificationCase(
            case_id="bad",
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
            description="d",
            expected_risk_class=RiskClass.HIGH_RISK,
            expected_performs_profiling=True,
            expected_derogation=DerogationCondition.NARROW_PROCEDURAL_TASK,
            decisive_fact="profiling with a contradictory derogation",
            difficulty="obvious",
        )


def test_prohibited_flag_must_match_class():
    with pytest.raises(ValueError, match="PROHIBITED class"):
        ClassificationCase(
            case_id="bad",
            description="d",
            expected_risk_class=RiskClass.HIGH_RISK,
            expected_prohibited=True,
            decisive_fact="prohibited flag but high_risk class",
            difficulty="obvious",
        )


def test_derogation_implies_not_high_risk():
    with pytest.raises(ValueError, match="must be\\s+not_high_risk"):
        ClassificationCase(
            case_id="bad",
            description="d",
            expected_risk_class=RiskClass.MINIMAL,
            expected_derogation=DerogationCondition.PREPARATORY_TASK,
            decisive_fact="derogation but labelled minimal",
            difficulty="obvious",
        )


def test_dangling_flips_from_is_rejected(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text(
        "act_version_date: 2024-07-12\n"
        "default_split: dev\n"
        "cases:\n"
        "  - case_id: only\n"
        "    description: d\n"
        "    expected_risk_class: minimal\n"
        "    decisive_fact: a lonely case pointing nowhere in particular\n"
        "    difficulty: obvious\n"
        "    flips_from: does_not_exist\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="names no case"):
        load_classification_cases(bad)
