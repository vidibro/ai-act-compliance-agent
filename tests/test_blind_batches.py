"""The blind-authored batches, now part of the dev set — integrity of the answer key only.

24 of the 42 Layer 1 cases were written by sessions that could not read this repo: not the roadmap,
not the other cases, not the tests. They were measured once and moved into `dev`, because a set
whose every failure has been read and diagnosed is no longer blind whatever it is labelled.

What survives the move is the reason they are good cases. Their labels were reached from the
enacted text by someone who could not see how the classifier behaves, so they are not shaped around
its habits — and the traps they carry came from real prose rather than from imagining what would be
hard. These tests pin those properties. They never run the classifier: what is checked is the
RULER, not the thing being measured.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.eval.classification_cases import load_classification_cases
from aiact.schemas.enums import RiskClass

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "golden_set" / "classification_cases.yaml"

# Authored blind, in three batches: the original 9, six Annex I cases from FDA filings, and nine
# Art. 2 cases from tenders, project records, model cards, a manual and a press release.
BLIND_PREFIX = "h_"


@pytest.fixture(scope="module")
def cases():
    return load_classification_cases(CASES).cases


@pytest.fixture(scope="module")
def blind(cases):
    return [c for c in cases if c.case_id.startswith(BLIND_PREFIX)]


def test_the_blind_batches_are_all_here(blind):
    """Twenty-four, and the count is pinned because losing one silently would remove exactly the
    cases nobody arranged for the classifier."""
    assert len(blind) == 24


def test_the_two_smoke_check_traps_are_present(blind):
    """The reason to author from real prose rather than re-use dev: it carries failure modes an
    invented description does not think to include."""
    by_id = {c.case_id: c for c in blind}

    # A high-risk system that loudly promises human oversight — the reassurance is legally
    # irrelevant to the tier and must not pull it down.
    oversight = by_id["h_scoring_with_oversight_theatre"]
    assert oversight.expected_risk_class == RiskClass.HIGH_RISK
    assert "control" in oversight.description.lower()

    # A minimal system carrying cross-sell noise for a separate high-risk product — must not pull UP
    crosssell = by_id["h_onboarding_logistics_crosssell"]
    assert crosssell.expected_risk_class == RiskClass.MINIMAL
    assert "score" in crosssell.description.lower()  # the high-risk-sounding decoy


def test_the_art_2_flip_turns_on_scope_not_on_tier(blind):
    """The Art. 2 batch's flip, and a kind the set had none of: two permissively licensed releases,
    one excluded outright and one governed, separated only by whether the output is synthetic
    content Art. 50(2) requires to be marked."""
    by_id = {c.case_id: c for c in blind}
    excluded = by_id["h_open_licence_demand_forecaster"]
    governed = by_id["h_open_licence_tts_voices"]

    assert excluded.expected_risk_class == RiskClass.OUT_OF_SCOPE
    assert excluded.expected_transparency_obligation is False
    assert governed.expected_risk_class == RiskClass.MINIMAL
    assert governed.expected_transparency_obligation is True
    assert governed.flips_from == excluded.case_id


def test_every_case_argues_its_art_50_label(cases):
    """Applies to the whole set now, not only the blind half: no Art. 50 position asserted without
    naming the paragraph it rests on."""
    for c in cases:
        basis = c.transparency_basis.strip()
        assert len(basis) > 20, f"{c.case_id}: Art. 50 label with no argument"
        assert "50(" in basis, f"{c.case_id}: names no Art. 50 paragraph"


def test_insufficient_case_pins_nothing_it_cannot_know(blind):
    """The domain is unknown, so the tier is undecidable — the decisive sub-answers stay null rather
    than defaulting to a value the description never supports."""
    c = {x.case_id: x for x in blind}["h_people_analytics_unstated_domain"]
    assert c.expected_risk_class == RiskClass.NEEDS_REVIEW
    assert c.expected_annex_iii_area is None
    assert c.expected_performs_profiling is None
    assert c.expected_derogation is None
