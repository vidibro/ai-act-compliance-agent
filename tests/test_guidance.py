"""The Commission-guidance store — reference resolution and integrity.

Guidance is the Commission's NON-BINDING interpretation, stored separately from enacted law. These
pin the two things that keep a guidance citation honest: it must resolve to a real snippet, and the
quoted text must still match the sha it was verified under (so a citation can't silently drift from
the passage a human checked against the PDF).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.eval.classification_cases import load_classification_cases
from aiact.guidance import load_snippet, snippet_path

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE_ROOT = ROOT / "data" / "policy" / "guidance"
CASES = ROOT / "data" / "golden_set" / "classification_cases.yaml"
REF = "C-2025-5052/workplace-covers-recruitment"


def test_ref_maps_to_the_snippet_path():
    assert snippet_path(REF, GUIDANCE_ROOT).name == "workplace-covers-recruitment.md"
    assert snippet_path(REF, GUIDANCE_ROOT).parent.name == "snippets"


@pytest.mark.parametrize("bad", ["no-slash", "C-2025-5052/", "/slug", "a/b/c"])
def test_malformed_refs_are_rejected(bad):
    with pytest.raises(ValueError, match="guidance ref must be"):
        snippet_path(bad, GUIDANCE_ROOT)


def test_the_recruitment_snippet_loads_and_is_verbatim():
    ex = load_snippet(REF, GUIDANCE_ROOT)
    assert ex.binding is False, "guidance is non-binding — the flag must say so"
    assert "para" in ex.locator.lower() or "p." in ex.locator
    # the two load-bearing sentences, verbatim from para 254
    assert "should be interpreted broadly" in ex.body
    assert "candidates during the selection and hiring process" in ex.body
    assert "during the recruitment process is prohibited" in ex.body


def test_missing_snippet_raises():
    with pytest.raises(FileNotFoundError):
        load_snippet("C-2025-5052/does-not-exist", GUIDANCE_ROOT)


def test_a_drifted_quote_fails_its_integrity_check(tmp_path):
    """If the quoted text is edited without re-verifying against the PDF, the stored sha no longer
    matches and the snippet refuses to load — this stops a citation quietly becoming wrong."""
    doc = tmp_path / "C-9999-0000" / "snippets"
    doc.mkdir(parents=True)
    src = GUIDANCE_ROOT / "C-2025-5052" / "snippets" / "workplace-covers-recruitment.md"
    tampered = src.read_text().replace("interpreted broadly", "interpreted narrowly")
    (doc / "tampered.md").write_text(tampered)
    with pytest.raises(ValueError, match="does not match its stored sha256"):
        load_snippet("C-9999-0000/tampered", tmp_path)


# --- wiring into the golden set -----------------------------------------------------------------
def test_every_golden_guidance_ref_resolves():
    """The loader resolves each ref; this asserts the set as shipped has no dangling citation."""
    gs = load_classification_cases(CASES, GUIDANCE_ROOT)
    refs = [r for c in gs.cases for r in c.guidance_refs]
    assert REF in refs, "the recruitment case should cite the workplace-covers-recruitment snippet"
    for ref in refs:
        load_snippet(ref, GUIDANCE_ROOT)  # raises if missing or drifted


def test_a_dangling_guidance_ref_fails_the_loader(tmp_path):
    bad = tmp_path / "cases.yaml"
    bad.write_text(
        "act_version_date: 2024-07-12\n"
        "default_split: dev\n"
        "cases:\n"
        "  - case_id: x\n"
        "    description: y\n"
        "    expected_risk_class: prohibited\n"
        "    expected_is_ai_system: true\n"
        "    expected_prohibited: true\n"
        "    guidance_refs: [C-2025-5052/nope]\n"
        "    decisive_fact: z\n"
        "    difficulty: obvious\n"
    )
    with pytest.raises(ValueError, match="guidance_ref"):
        load_classification_cases(bad, GUIDANCE_ROOT)


def test_the_recruitment_case_is_now_prohibited_and_cited():
    gs = load_classification_cases(CASES, GUIDANCE_ROOT)
    case = next(c for c in gs.cases if c.case_id == "emotion_screening_candidates")
    assert case.expected_risk_class.value == "prohibited"
    assert case.expected_prohibited is True
    assert case.guidance_refs == [REF], "the prohibited label must carry its non-binding basis"
