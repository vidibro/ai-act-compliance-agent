"""Golden-set integrity tests.

The golden set is the ruler. If it is wrong, every number measured against it is wrong and nobody
finds out — so the ruler itself gets tested: the ablated section really is gone/hollow, the
untouched sections really are intact, and the rule tags never leak into what the checker sees.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiact.eval.baseline import KeywordBaseline, keywords_from_title
from aiact.eval.runner import run
from aiact.policy_loader import load_policy_spec
from aiact.schemas.enums import Verdict
from aiact.schemas.eval import AblationType, GoldenCase, GoldenSet

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_JSON = ROOT / "data" / "golden_set" / "golden_set.json"
SPEC_PATH = ROOT / "data" / "policy" / "spec.yaml"
ARTICLES_ROOT = ROOT / "data" / "policy" / "articles"


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    if not GOLDEN_JSON.is_file():
        pytest.skip("golden set not generated; run scripts/make_golden_set.py")
    return GoldenSet.model_validate(json.loads(GOLDEN_JSON.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec(SPEC_PATH, ARTICLES_ROOT)


def test_golden_set_loads(golden: GoldenSet):
    assert golden.cases
    assert golden.system_id == "hr-candidate-scoring"
    ids = [c.case_id for c in golden.cases]
    assert len(ids) == len(set(ids)), "case_ids must be unique"


def test_every_case_expects_all_applicable_rules(golden: GoldenSet, spec):
    """A case scores every applicable rule, so each one measures both catching and false alarms."""
    applicable = {
        r.rule_id
        for r in spec.rules
        if r.document_verifiable and any(c.value == "high_risk" for c in r.applies_to_risk_class)
    }
    for case in golden.cases:
        assert set(case.expected) == applicable, f"{case.case_id} does not score every rule"


def test_expected_verdict_matches_ablation_type(golden: GoldenSet):
    """Ground truth must follow from what was degraded — that is what makes it exact."""
    implied = {
        AblationType.REMOVED: Verdict.GAP,
        AblationType.PRESENT_BUT_INADEQUATE: Verdict.INADEQUATE,
        AblationType.DISTRACTOR: Verdict.GAP,
    }
    for case in golden.cases:
        if case.ablated_rule_id is None:
            continue
        got = case.expected[case.ablated_rule_id]
        # AIA-HR-A12 is a deliberate `ambiguous` override: a presence check is satisfied by a bare
        # assertion, so its hollowed-out case expects PASS, not INADEQUATE.
        if case.case_id == "AIA-HR-A12__present_but_inadequate":
            assert got == Verdict.PASS
            continue
        assert got == implied[case.ablation], f"{case.case_id} expects {got}"


def test_untouched_rules_expect_pass(golden: GoldenSet):
    for case in golden.cases:
        for rule_id, verdict in case.expected.items():
            if rule_id != case.ablated_rule_id:
                assert verdict == Verdict.PASS, f"{case.case_id}/{rule_id} should be untouched"


def test_pristine_case_is_all_pass(golden: GoldenSet):
    """Measures false positives: a checker that flags anything here is crying wolf."""
    pristine = next(c for c in golden.cases if c.ablation == AblationType.UNTOUCHED)
    assert pristine.ablated_rule_id is None
    assert set(pristine.expected.values()) == {Verdict.PASS}


def test_rule_tags_never_leak_into_case_documents(golden: GoldenSet):
    """The <!-- rule: ... --> tags are authoring metadata. If they reached the checker it could
    find the answer key in the input."""
    for case in golden.cases:
        assert "<!-- rule:" not in case.raw_text, f"{case.case_id} leaks rule tags"
        assert "<!--" not in case.raw_text, f"{case.case_id} leaks an HTML comment"


def test_removed_case_actually_drops_the_section(golden: GoldenSet):
    """Art. 14's oversight detail must be gone when Art. 14 is the removed rule."""
    case = next(c for c in golden.cases if c.case_id == "AIA-HR-A14__removed")
    assert "stop control" not in case.raw_text
    assert "automation bias" not in case.raw_text.lower() or "§7" in case.raw_text
    pristine = next(c for c in golden.cases if c.ablation == AblationType.UNTOUCHED)
    assert len(case.raw_text) < len(pristine.raw_text)


def test_inadequate_case_keeps_the_topic_but_drops_the_substance(golden: GoldenSet):
    """The defining property of PRESENT_BUT_INADEQUATE: the words are there, the substance is not.
    This is precisely what defeats keyword matching."""
    case = next(c for c in golden.cases if c.case_id == "AIA-HR-A14__present_but_inadequate")
    # Topic words survive — this is exactly why a keyword checker says PASS here.
    assert "human oversight" in case.raw_text.lower()
    # ...but every concrete oversight measure Art. 14 actually demands is gone. (Terms are chosen
    # to be unique to §7: things like "sub-scores" legitimately recur in §1 and §6, which is itself
    # a good illustration of why topic words are worthless as evidence.)
    for substance in ("stop control", "training module", "recruiter console"):
        assert substance not in case.raw_text, f"{substance!r} should have been hollowed out"


def test_case_documents_on_disk_match_the_manifest(golden: GoldenSet):
    for case in golden.cases:
        path = ROOT / case.document_path
        assert path.is_file(), f"{case.case_id}: {path} missing"
        assert path.read_text(encoding="utf-8") == case.raw_text


def test_ablated_rule_must_carry_an_expectation():
    with pytest.raises(ValueError, match="carries no expected verdict"):
        GoldenCase(
            case_id="bad",
            system_id="s",
            document_path="p",
            raw_text="t",
            ablated_rule_id="AIA-HR-A14",
            ablation=AblationType.REMOVED,
            difficulty="obvious",
            split="dev",
            expected={"AIA-HR-A09": Verdict.PASS},
        )


def test_untouched_case_cannot_name_an_ablated_rule():
    with pytest.raises(ValueError, match="ablated_rule_id must be None"):
        GoldenCase(
            case_id="bad",
            system_id="s",
            document_path="p",
            raw_text="t",
            ablated_rule_id="AIA-HR-A14",
            ablation=AblationType.UNTOUCHED,
            difficulty="obvious",
            split="dev",
            expected={"AIA-HR-A14": Verdict.PASS},
        )


def test_split_field_defaults_to_test_when_unset():
    """A hand-built case with no split is HELD OUT by default — never tuned against by accident."""
    c = GoldenCase(
        case_id="x", system_id="s", document_path="p", raw_text="t",
        ablated_rule_id=None, ablation=AblationType.UNTOUCHED, difficulty="obvious",
        expected={},
    )
    assert c.split == "test"


def test_every_current_case_is_dev_and_test_is_empty(golden: GoldenSet):
    """Current structure: all cases are dev; the held-out test split is intentionally empty and
    will be authored later. When that changes, this test should be updated deliberately."""
    assert {c.split for c in golden.cases} == {"dev"}
    assert golden.for_split("test") == []
    assert len(golden.for_split("dev")) == len(golden.cases)
    assert len(golden.for_split("all")) == len(golden.cases)


# --- The baseline's failure is the project's thesis, so we pin it as a regression test ----------
def test_keywords_are_derived_from_article_titles_not_hand_tuned():
    assert keywords_from_title("Human oversight") == {"human", "oversight"}
    assert keywords_from_title("Accuracy, robustness and cybersecurity") == {
        "accuracy",
        "robustness",
        "cybersecurity",
    }


def test_keyword_baseline_cannot_detect_inadequate(golden: GoldenSet, spec):
    """THE HEADLINE. A word-matching checker never emits INADEQUATE — it is structurally blind to
    the distinction this project exists to make. If a future checker makes this test fail, that is
    progress, not a regression."""
    titles = {r.rule_id: "Human oversight" for r in spec.rules}
    titles.update({r.rule_id: r.rule_id for r in spec.rules})
    checker = KeywordBaseline({r.rule_id: "placeholder title" for r in spec.rules})
    results = run(checker, golden, spec)
    assert all(r.got != Verdict.INADEQUATE for r in results)
