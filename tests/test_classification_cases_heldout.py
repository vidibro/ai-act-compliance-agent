"""Layer 1 HELD-OUT split — integrity of the answer key only.

These tests validate the RULER (labels are well-formed, the split is genuinely held out, the two
smoke-check traps are present). They never run the classifier on a held-out description — doing so
here would leak the set, and the score belongs in a deliberate reporting run, not in `make check`.
"""

from __future__ import annotations

from pathlib import Path

from aiact.eval.classification_cases import load_classification_cases
from aiact.schemas.enums import RiskClass

ROOT = Path(__file__).resolve().parents[1]
HELDOUT = ROOT / "data" / "golden_set" / "classification_cases_heldout.yaml"
DEV = ROOT / "data" / "golden_set" / "classification_cases.yaml"


def _heldout():
    return load_classification_cases(HELDOUT)


def _dev():
    return load_classification_cases(DEV)


def test_loads_and_is_entirely_held_out():
    cases = _heldout().cases
    assert cases
    assert {c.split for c in cases} == {"test"}, "a dev case here would poison the reported number"


def test_every_risk_class_is_present():
    present = {c.expected_risk_class for c in _heldout().cases}
    for rc in RiskClass:
        assert rc in present, f"held-out set does not exercise {rc}"


def test_the_two_smoke_check_traps_are_present():
    """The whole reason to author a held-out set by hand rather than re-use dev: it can carry the
    failure modes real prose has and the dev set lacks."""
    by_id = {c.case_id: c for c in _heldout().cases}

    # A high-risk system that loudly promises human oversight — the reassurance must not downgrade.
    oversight = by_id["h_scoring_with_oversight_theatre"]
    assert oversight.expected_risk_class == RiskClass.HIGH_RISK
    assert "control" in oversight.description.lower()

    # A minimal system carrying cross-sell noise for a separate high-risk product — must not upgrade
    crosssell = by_id["h_onboarding_logistics_crosssell"]
    assert crosssell.expected_risk_class == RiskClass.MINIMAL
    assert "score" in crosssell.description.lower()  # the high-risk-sounding decoy


def test_held_out_and_dev_are_disjoint():
    """No shared case_id, and no reused description — a held-out case that echoes a dev one is not
    held out in any meaningful sense."""
    dev, held = _dev().cases, _heldout().cases
    assert not ({c.case_id for c in dev} & {c.case_id for c in held})
    dev_desc = {c.description.strip() for c in dev}
    assert all(c.description.strip() not in dev_desc for c in held)


def test_every_held_out_case_argues_its_art_50_label():
    """Same discipline the dev set is held to: no Art. 50 position asserted without a paragraph."""
    for c in _heldout().cases:
        basis = c.transparency_basis.strip()
        assert len(basis) > 20, f"{c.case_id}: Art. 50 label with no argument"
        assert "50(" in basis, f"{c.case_id}: names no Art. 50 paragraph"


def test_insufficient_case_pins_nothing_it_cannot_know():
    """The domain is unknown, so the tier is undecidable — the decisive sub-answers must stay null,
    not default to a value the description never supports."""
    c = {x.case_id: x for x in _heldout().cases}["h_people_analytics_unstated_domain"]
    assert c.expected_risk_class == RiskClass.NEEDS_REVIEW
    assert c.expected_annex_iii_area is None
    assert c.expected_performs_profiling is None
    assert c.expected_derogation is None
