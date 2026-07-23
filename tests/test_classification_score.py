"""Layer 1 scoring — both axes, and the ways a one-number score would lie.

The Art. 50 axis went unmeasured from the day the golden set was authored: the answer key carried
`expected_transparency_obligation`, the runner compared only `expected_risk_class`. These tests pin
the behaviour that would have caught it.

No LLM, no network — scoring is pure, so it is tested rather than merely observed during a paid run.
"""

from __future__ import annotations

import pytest

from aiact.eval.classification_score import score_case, score_run
from aiact.schemas.classification import (
    ClassificationAnswer,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import RiskClass
from aiact.schemas.eval import ClassificationCase
from aiact.schemas.policy import LegalSource

ART50 = LegalSource(
    instrument="Regulation (EU) 2024/1689", article=50, act_version_date="2024-07-12"
)


def case(case_id: str, risk: RiskClass, transparency: bool) -> ClassificationCase:
    return ClassificationCase(
        case_id=case_id,
        description="a description",
        expected_risk_class=risk,
        expected_transparency_obligation=transparency,
        decisive_fact="the fact that fixes the class",
        difficulty="obvious",
    )


def result(risk: RiskClass, transparency: bool | None, *, answered: bool = True):
    answer = (
        ClassificationAnswer(
            value=transparency,
            reasoning="r",
            confidence="high" if answered else "low",
            source=ART50,
            node_id="transparency",
        )
        if answered
        else None
    )
    use_case = UseCaseClassification(
        use_case_id="u",
        description="d",
        risk_class=risk,
        triggered_by=[],
        reasoning="r",
        confidence="high",
    )
    return ClassificationResult(
        use_cases=[use_case],
        overall_risk_class=risk,
        reasoning="r",
        triggered_by=[],
        confidence="high",
        transparency=answer,
    )


# --- the two axes are scored independently ------------------------------------------------------
def test_right_class_wrong_art50_is_only_half_right():
    """THE BUG THIS MODULE EXISTS FOR. Before, this run scored 1/1 and looked perfect."""
    s = score_case(case("c", RiskClass.HIGH_RISK, False), result(RiskClass.HIGH_RISK, True))
    assert s.class_correct is True
    assert s.transparency_correct is False


def test_wrong_class_right_art50_is_also_only_half_right():
    s = score_case(case("c", RiskClass.MINIMAL, True), result(RiskClass.HIGH_RISK, True))
    assert s.class_correct is False
    assert s.transparency_correct is True


def test_run_score_has_no_single_combined_accuracy():
    """Averaging a risk tier and a transparency duty produces a number nobody can act on, so the
    property deliberately does not exist."""
    run = score_run([(case("c", RiskClass.MINIMAL, False), result(RiskClass.MINIMAL, False))])
    assert not hasattr(run, "accuracy")
    assert not hasattr(run, "overall_accuracy")


# --- abstention is neither right nor wrong ------------------------------------------------------
def test_an_abstained_art50_answer_is_not_counted_correct():
    s = score_case(case("c", RiskClass.MINIMAL, False), result(RiskClass.MINIMAL, None))
    assert s.transparency_abstained is True
    assert s.transparency_correct is False, "value=None is an absence of an answer, not a `false`"


def test_a_missing_art50_answer_abstains_rather_than_defaulting_to_false():
    """If the node never ran, the case must not be credited with a correct `no obligation`."""
    s = score_case(
        case("c", RiskClass.MINIMAL, False), result(RiskClass.MINIMAL, None, answered=False)
    )
    assert s.got_transparency is None
    assert s.transparency_abstained is True
    assert s.transparency_correct is False


# --- the failure mode the smoke check actually found --------------------------------------------
def test_false_positives_and_negatives_are_reported_separately():
    run = score_run(
        [
            (case("fp", RiskClass.HIGH_RISK, False), result(RiskClass.HIGH_RISK, True)),
            (case("fn", RiskClass.MINIMAL, True), result(RiskClass.MINIMAL, False)),
            (case("ok", RiskClass.MINIMAL, False), result(RiskClass.MINIMAL, False)),
        ]
    )
    assert run.transparency_false_positives == 1
    assert run.transparency_false_negatives == 1
    assert run.transparency_correct == 1
    assert run.class_correct == 3, "all three tiers right — and Art. 50 right only once"


def test_always_true_art50_is_flagged_as_unmeasured():
    """A node that answers TRUE on everything scores the base rate and discriminates nothing. That
    is what the smoke check saw on real vendor prose, and the report must say so out loud rather
    than printing a respectable-looking fraction."""
    run = score_run(
        [
            (case("a", RiskClass.MINIMAL, True), result(RiskClass.MINIMAL, True)),
            (case("b", RiskClass.HIGH_RISK, False), result(RiskClass.HIGH_RISK, True)),
        ]
    )
    assert run.transparency_correct == 1
    assert any("always says yes" in line for line in run.lines())


def test_a_discriminating_art50_node_is_not_flagged():
    run = score_run(
        [
            (case("a", RiskClass.MINIMAL, True), result(RiskClass.MINIMAL, True)),
            (case("b", RiskClass.HIGH_RISK, False), result(RiskClass.HIGH_RISK, False)),
        ]
    )
    assert run.transparency_correct == 2
    assert not any("always says yes" in line for line in run.lines())


def test_lines_report_both_axes_on_separate_lines():
    run = score_run([(case("c", RiskClass.MINIMAL, False), result(RiskClass.MINIMAL, False))])
    lines = run.lines()
    assert any("risk-class accuracy" in line for line in lines)
    assert any("art.50 accuracy" in line for line in lines)


@pytest.mark.parametrize("expected", [True, False])
def test_matching_art50_answer_scores_correct(expected: bool):
    s = score_case(case("c", RiskClass.MINIMAL, expected), result(RiskClass.MINIMAL, expected))
    assert s.transparency_correct is True
