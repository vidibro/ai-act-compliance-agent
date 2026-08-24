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
from aiact.eval.runner import rules_a_case_is_scored_on, run
from aiact.policy_loader import load_policy_spec
from aiact.schemas.enums import CheckType, Verdict
from aiact.schemas.eval import AblationType, GoldenCase, GoldenSet

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_JSON = ROOT / "data" / "golden_set" / "golden_set.json"
HELDOUT_JSON = ROOT / "data" / "golden_set" / "golden_set_heldout.json"
SPEC_PATH = ROOT / "data" / "policy" / "spec.yaml"
ARTICLES_ROOT = ROOT / "data" / "policy" / "articles"


def _load(path: Path) -> GoldenSet:
    if not path.is_file():
        pytest.skip(f"{path.name} not generated; run scripts/make_golden_set.py")
    return GoldenSet.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    """The DEV set — hr-candidate-scoring, tunable."""
    return _load(GOLDEN_JSON)


@pytest.fixture(scope="module")
def heldout() -> GoldenSet:
    """The HELD-OUT set — internal-mobility. Never tuned against; the only reportable score."""
    return _load(HELDOUT_JSON)


@pytest.fixture(scope="module", params=["dev", "heldout"])
def any_golden(request) -> GoldenSet:
    """Both sets. Every structural invariant below is a property of the RULER, not of one document,
    so it must hold for the held-out set too — otherwise the half we actually report is the
    untested half."""
    return _load(GOLDEN_JSON if request.param == "dev" else HELDOUT_JSON)


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec(SPEC_PATH, ARTICLES_ROOT)


def test_golden_set_loads(golden: GoldenSet):
    assert golden.cases
    assert golden.system_id == "hr-candidate-scoring"
    ids = [c.case_id for c in golden.cases]
    assert len(ids) == len(set(ids)), "case_ids must be unique"


def test_every_case_expects_all_applicable_rules(any_golden: GoldenSet, spec):
    """A case scores every applicable rule, so each one measures both catching and false alarms.

    APPLICABLE IS SELECTED, not filtered here. `select_rules` gates on the Art. 6 route and the
    Annex III area as well as the tier, and a filter written out here would have to keep pace with
    all three. A rule bound to Annex I products, or to Annex III point 1(a) biometrics, is not owed
    by an employment document — demanding it would mean writing a reference section that evidences
    an obligation the system does not have, which makes the ruler wrong rather than the checker."""
    applicable = {r.rule_id for r in rules_a_case_is_scored_on(spec, any_golden)}
    assert applicable, "no rule is selected for this golden set — re-derive"
    for case in any_golden.cases:
        assert set(case.expected) == applicable, f"{case.case_id} does not score every rule"


def test_expected_verdict_matches_ablation_type(any_golden: GoldenSet, spec):
    """Ground truth must follow from what was degraded — that is what makes it exact.

    A CASE THAT EXPECTS A PASS ON A DEGRADED SECTION IS THE RULER REWARDING A FALSE PASS, which is
    worse than a bug in the thing being ruled: prompt tuning driven by such a case pushes the judge
    toward accepting exactly the documents this ruleset exists to catch. `make_golden_set.py` lets
    a plan override the implied verdict with `expect:`, and the only defensible ground for
    overriding INADEQUATE to PASS is that the rule asks for PRESENCE — where the check is
    `substance` or `completeness`, a hollowed-out section is inadequate by construction.

    So the exception is DERIVED from the rule rather than named by case id. A rule whose
    `check_type` changes takes its ablations with it, instead of leaving a pinned expectation
    behind that now says the opposite of what the rule says."""
    implied = {
        AblationType.REMOVED: Verdict.GAP,
        AblationType.PRESENT_BUT_INADEQUATE: Verdict.INADEQUATE,
        AblationType.DISTRACTOR: Verdict.GAP,
    }
    by_id = {rule.rule_id: rule for rule in spec.rules}
    for case in any_golden.cases:
        if case.ablated_rule_id is None:
            continue
        got = case.expected[case.ablated_rule_id]
        if got == implied[case.ablation]:
            continue
        rule = by_id[case.ablated_rule_id]
        assert case.ablation is AblationType.PRESENT_BUT_INADEQUATE and got is Verdict.PASS, (
            f"{case.case_id} expects {got.value} where the ablation implies "
            f"{implied[case.ablation].value}, and no check_type justifies that"
        )
        assert rule.check_type is CheckType.PRESENCE, (
            f"{case.case_id} expects a PASS on a hollowed-out section, but "
            f"{rule.rule_id} is a {rule.check_type.value} check — its own evidence_expected asks "
            f"for more than the assertion the case leaves behind, so the ruler and the rule "
            f"disagree and the ruler is the one that scores the judge"
        )


def test_untouched_rules_expect_pass(any_golden: GoldenSet):
    for case in any_golden.cases:
        for rule_id, verdict in case.expected.items():
            if rule_id != case.ablated_rule_id:
                assert verdict == Verdict.PASS, f"{case.case_id}/{rule_id} should be untouched"


def test_pristine_case_is_all_pass(any_golden: GoldenSet):
    """Measures false positives: a checker that flags anything here is crying wolf."""
    pristine = next(c for c in any_golden.cases if c.ablation == AblationType.UNTOUCHED)
    assert pristine.ablated_rule_id is None
    assert set(pristine.expected.values()) == {Verdict.PASS}


def test_rule_tags_never_leak_into_case_documents(any_golden: GoldenSet):
    """The <!-- rule: ... --> tags are authoring metadata. If they reached the checker it could
    find the answer key in the input."""
    for case in any_golden.cases:
        assert "<!-- rule:" not in case.raw_text, f"{case.case_id} leaks rule tags"
        assert "<!--" not in case.raw_text, f"{case.case_id} leaks an HTML comment"
        assert "-->" not in case.raw_text, f"{case.case_id} leaks a comment close"
        assert "never reach the agent" not in case.raw_text, (
            f"{case.case_id} leaks the reference document's authoring commentary"
        )
        assert case.raw_text.lstrip().startswith("#"), (
            f"{case.case_id} does not start at the document title — something precedes it"
        )


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


def test_case_documents_on_disk_match_the_manifest(any_golden: GoldenSet):
    for case in any_golden.cases:
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


# --- the dev / held-out separation --------------------------------------------------------------
def test_dev_set_is_entirely_dev(golden: GoldenSet):
    """The tunable half. Every case here may be looked at, iterated on, and tuned against."""
    assert {c.split for c in golden.cases} == {"dev"}
    assert golden.for_split("test") == []
    assert len(golden.for_split("all")) == len(golden.cases)


def test_heldout_set_is_entirely_held_out(heldout: GoldenSet):
    """The reportable half. A single `dev` case leaking in here would make the reported number
    partly a memorised one."""
    assert heldout.system_id == "internal-mobility"
    assert {c.split for c in heldout.cases} == {"test"}
    assert heldout.for_split("dev") == []


def test_heldout_matches_the_dev_distribution(golden: GoldenSet, heldout: GoldenSet):
    """A held-out set estimates performance on UNSEEN cases from the SAME population. Making it
    harder yields a pessimistic number that measures nothing; making it easier flatters. So the
    ablation mix, the difficulty mix and the deliberate Art. 12 probe are mirrored exactly."""

    def shape(g: GoldenSet):
        # `or ""` because the pristine case's ablated_rule_id is None, which will not sort against
        # a str; enum .value for a stable, readable comparison.
        return sorted(
            (c.ablated_rule_id or "", c.ablation.value, c.difficulty.value) for c in g.cases
        )

    assert shape(heldout) == shape(golden)
    assert len(heldout.cases) == len(golden.cases)


def test_the_two_sets_are_genuinely_different_documents(golden: GoldenSet, heldout: GoldenSet):
    """What a gap checker overfits is the PROSE — headings, vocabulary, register — not the answer
    key, which is exact by construction. So re-ablating the same document would not be held out at
    all. These must share no system, no vendor and no section vocabulary."""
    dev_text = " ".join(c.raw_text for c in golden.cases)
    held_text = " ".join(c.raw_text for c in heldout.cases)

    for dev_only in ("TalentRank", "Northwind", "requisition", "recruiter", "NDCG"):
        assert dev_only in dev_text
        assert dev_only not in held_text, f"{dev_only!r} leaked into the held-out documents"
    for held_only in ("PathFinder", "Meridian", "readiness band", "line manager", "precision@5"):
        assert held_only in held_text
        assert held_only not in dev_text, f"{held_only!r} leaked into the dev documents"

    # Different Annex III sub-point, so the subject matter differs and not just the nouns.
    assert "4(a)" in dev_text and "4(b)" in held_text


def test_heldout_inadequate_case_keeps_the_topic_but_drops_the_substance(heldout: GoldenSet):
    """The dev set's headline property, re-asserted on the document we actually report from."""
    case = next(c for c in heldout.cases if c.case_id == "AIA-HR-A14__present_but_inadequate")
    assert "human oversight" in case.raw_text.lower()  # topic survives -> keyword checker passes it
    # Terms unique to Part E. "alphabetically" is NOT usable — it legitimately recurs in Part A,
    # which is itself the lesson: topic words are worthless as evidence of an obligation being met.
    for substance in ("administration console", "3-hour PathFinder module", "equal visual weight"):
        assert substance not in case.raw_text, f"{substance!r} should have been hollowed out"


# --- The baseline's failure is the project's thesis, so we pin it as a regression test ----------
def test_keywords_are_derived_from_article_titles_not_hand_tuned():
    assert keywords_from_title("Human oversight") == {"human", "oversight"}
    assert keywords_from_title("Accuracy, robustness and cybersecurity") == {
        "accuracy",
        "robustness",
        "cybersecurity",
    }


def test_keyword_baseline_cannot_detect_inadequate(any_golden: GoldenSet, spec):
    """THE HEADLINE. A word-matching checker never emits INADEQUATE — it is structurally blind to
    the distinction this project exists to make. If a future checker makes this test fail, that is
    progress, not a regression."""
    titles = {r.rule_id: "Human oversight" for r in spec.rules}
    titles.update({r.rule_id: r.rule_id for r in spec.rules})
    checker = KeywordBaseline({r.rule_id: "placeholder title" for r in spec.rules})
    results = run(checker, any_golden, spec)
    assert all(r.got != Verdict.INADEQUATE for r in results)
