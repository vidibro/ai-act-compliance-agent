"""M5-a — per-node scoring: which QUESTION is weak, not which case.

The end-to-end score says a case failed; it cannot say which of the nine questions did it. What is
pinned here is the rule that makes a per-node denominator honest — **score a node only where the
run ASKED it and the case PINS it** — because each half alone gives a wrong answer, in opposite
directions:

  without ASKED   a node the cascade never reached is counted against the case, so an out-of-scope
                  case is marked wrong on Annex III, a question nobody put to it.
  without PINNED  `None` in the answer key means both "the answer is none" and "this case does not
                  fix this node", and every unpinned node scores as though it had been.

Two fields are exempt from PINNED because the risk class already fixes them, and one node is exempt
from scoring because no case can pin it at all. Both exemptions are asserted here rather than left
to the reader of the table.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from aiact.classify import ScriptedBrain, classify
from aiact.eval.node_score import (
    DERIVED_FROM_CLASS,
    NODE_KEYS,
    NodeRunScore,
    score_node_run,
    score_nodes,
)
from aiact.schemas.classification import ClassificationAnswer
from aiact.schemas.enums import AnnexIIIArea, RiskClass, ScopeExclusion
from aiact.schemas.eval import ClassificationCase, Difficulty
from aiact.schemas.policy import LegalSource

SOURCE = LegalSource(
    instrument="Regulation (EU) 2024/1689", article=6, act_version_date=date(2024, 7, 12)
)


def a_case(**overrides) -> ClassificationCase:
    """A case that pins ONLY what `overrides` names — which is the property under test."""
    base = dict(
        case_id="c",
        description="x",
        expected_risk_class=RiskClass.MINIMAL,
        decisive_fact="f",
        difficulty=Difficulty.OBVIOUS,
    )
    return ClassificationCase(**{**base, **overrides})


def an_answer(value, confidence="high", abstained=None) -> ClassificationAnswer:
    return ClassificationAnswer(
        value=value,
        reasoning="r",
        confidence=confidence,
        source=SOURCE,
        abstained_because=abstained,
    )


def an_answer_at(node_id: str, value, confidence="high", abstained=None) -> ClassificationAnswer:
    """An answer tagged with the node that produced it — which is the only link back to the
    question now that nothing records the questions separately."""
    return ClassificationAnswer(
        value=value,
        reasoning="r",
        confidence=confidence,
        source=SOURCE,
        node_id=node_id,
        abstained_because=abstained,
    )


# --- the two conditions ---------------------------------------------------------------------------
def test_a_node_the_case_does_not_pin_is_not_scored():
    """`expected_annex_iii_area` defaults to None, which means 'unpinned' here — not 'no area'.
    Scoring it would mark the case against a key it never claimed."""
    case = a_case()
    assert "expected_annex_iii_area" not in case.model_fields_set
    scores = score_nodes(case, [an_answer_at("annex_iii", AnnexIIIArea.EMPLOYMENT)])
    assert scores == []


def test_a_node_the_case_pins_as_none_IS_scored():
    """Written explicitly in the YAML, `null` is a real answer — 'falls within no Annex III area',
    which is what makes a case minimal. `model_fields_set` is what tells the two apart."""
    case = a_case(expected_annex_iii_area=None)
    assert "expected_annex_iii_area" in case.model_fields_set
    scores = score_nodes(case, [an_answer_at("annex_iii", None)])
    assert [s.outcome for s in scores] == ["correct"]


def test_a_node_that_was_never_asked_is_not_scored():
    """The other half of the rule. A pinned node still scores nothing if the cascade exited before
    reaching it — `asked` is the record of what was actually put."""
    case = a_case(expected_annex_iii_area=None)
    assert score_nodes(case, []) == []


def test_pinned_but_unasked_is_exactly_the_out_of_scope_shape():
    """Not hypothetical: every Art. 2 case writes `expected_annex_iii_area: null` because the
    author had to fill the field, while the cascade stops at `scope` and never asks it. Without the
    ASKED condition all five would score as Annex III answers nobody gave."""
    case = a_case(
        expected_risk_class=RiskClass.OUT_OF_SCOPE,
        expected_scope_exclusion=ScopeExclusion.SCIENTIFIC_RESEARCH,
        scope_exclusion_basis="Art. 2(6)",
        expected_annex_iii_area=None,
    )
    asked = [an_answer_at("scope", ScopeExclusion.SCIENTIFIC_RESEARCH)]
    assert [s.node_id for s in score_nodes(case, asked)] == ["scope"]


# --- wrong vs abstained ---------------------------------------------------------------------------
def test_a_wrong_answer_and_an_abstention_are_different_outcomes():
    """The two failures need different fixes — a wrong answer means the question is misread, an
    abstention means it is ducked — and one node can produce both. Netting them into a single
    accuracy figure hides that it fails in both directions at once."""
    # high_risk, because the answer key's own validator enforces the Art. 6(3) carve-back:
    # profiling true cannot coexist with any other class.
    case = a_case(expected_risk_class=RiskClass.HIGH_RISK, expected_performs_profiling=True)
    wrong = score_nodes(case, [an_answer_at("profiling", False)])
    declined = score_nodes(
        case, [an_answer_at("profiling", None, "low", "description_silent")]
    )
    assert [s.outcome for s in wrong] == ["wrong"]
    assert [s.outcome for s in declined] == ["abstained"]


def test_low_confidence_counts_as_abstention_even_with_a_value():
    """The cascade routes on CONFIDENCE, so an answer the graph treats as an abstention is scored
    as one. A scripted brain lowers confidence without setting `abstained_because`."""
    # high_risk, because the answer key's own validator enforces the Art. 6(3) carve-back:
    # profiling true cannot coexist with any other class.
    case = a_case(expected_risk_class=RiskClass.HIGH_RISK, expected_performs_profiling=True)
    scores = score_nodes(case, [an_answer_at("profiling", True, "low")])
    assert [s.outcome for s in scores] == ["abstained"]


# --- the mapping ----------------------------------------------------------------------------------
def test_every_cascade_node_has_an_entry():
    """A newly added node must be given a key or an explicit None, rather than going silently
    unmeasured — the failure this module exists to make visible."""
    from aiact.classify.graph import QUESTIONS

    assert set(QUESTIONS) == set(NODE_KEYS)


def test_is_ai_is_recorded_as_having_no_key():
    """Not an oversight to be tidied away: no case in either split carries ground truth for it, a
    false answer there skips the entire cascade, and the blank row is what keeps that visible."""
    assert NODE_KEYS["is_ai"] is None


@pytest.mark.parametrize("node_id,field", [(k, v) for k, v in NODE_KEYS.items() if v])
def test_every_named_key_is_a_real_case_field(node_id, field):
    assert field in ClassificationCase.model_fields


# --- end to end, through the real cascade ---------------------------------------------------------
def test_asked_counts_come_from_the_run_not_the_answer_key():
    """`triggered_by` keeps only the DECIDING nodes; `answers` is what makes the routing ones
    visible, and the asked/pinned gap is itself the finding — a node asked 24 times and pinned 4 is
    thinly measured, however well it scores."""
    case = a_case(expected_annex_iii_area=None, expected_transparency_obligation=False)
    brain = ScriptedBrain({"is_ai": True, "prohibited": False, "annex_iii": None})
    result = classify(case.description, brain, case.case_id)

    run = score_node_run([(case, result)])
    # Asked covers everything the cascade put, including the node no case can pin.
    assert run.asked["is_ai"] == 1
    assert run.asked["scope"] == 1
    assert run.asked["annex_iii"] == 1
    # Scored covers what the YAML pinned, PLUS what the risk class settles on its own.
    assert {s.node_id for s in run.scores} == {"scope", "prohibited", "annex_iii", "transparency"}
    assert "is_ai" not in {s.node_id for s in run.scores}


def test_the_table_reports_a_no_key_node_as_a_blank_row():
    case = a_case(expected_annex_iii_area=None)
    brain = ScriptedBrain({"is_ai": True, "prohibited": False, "annex_iii": None})
    result = classify(case.description, brain, case.case_id)

    text = "\n".join(score_node_run([(case, result)]).lines())
    assert "NO KEY — unmeasured" in text
    assert "is_ai" in text


def test_an_abstention_on_a_needs_review_case_is_marked_as_intended():
    """`insufficient` cases exist to be declined. Listing that beside a node that ducked an
    answerable question would report the tool working as a defect."""
    case = a_case(
        expected_risk_class=RiskClass.NEEDS_REVIEW,
        expected_performs_profiling=None,
    )
    scores = score_nodes(case, [an_answer_at("profiling", None, "low", "description_silent")])
    run = NodeRunScore(scores=scores, asked=Counter({"profiling": 1}))
    assert scores[0].case_expects_review is True
    assert "declining is the intended answer" in "\n".join(run.lines())


def test_an_abstention_on_an_answerable_case_carries_no_such_note():
    case = a_case(expected_risk_class=RiskClass.HIGH_RISK, expected_performs_profiling=True)
    scores = score_nodes(case, [an_answer_at("profiling", None, "low", "description_silent")])
    run = NodeRunScore(scores=scores, asked=Counter({"profiling": 1}))
    assert scores[0].case_expects_review is False
    assert "intended answer" not in "\n".join(run.lines())


# --- derived from the risk class ------------------------------------------------------------------
def test_prohibited_and_scope_are_scored_without_being_written_in_the_yaml():
    """`ClassificationCase`'s validator makes both strict equivalences with the risk class —
    prohibited is true exactly when the class is PROHIBITED, an exclusion is set exactly when it is
    OUT_OF_SCOPE. A fact the key already settles needs no second statement, and requiring one would
    leave two nodes near-unmeasured for no gain."""
    case = a_case()  # pins nothing at all
    assert "expected_prohibited" not in case.model_fields_set
    assert "expected_scope_exclusion" not in case.model_fields_set

    scores = score_nodes(
        case,
        [an_answer_at("prohibited", False), an_answer_at("scope", None)],
    )
    assert {s.node_id: s.outcome for s in scores} == {"prohibited": "correct", "scope": "correct"}


def test_a_derived_answer_can_still_be_wrong():
    """Derived does not mean assumed correct — a minimal case whose `prohibited` node says True is
    a real miss, and one that would previously have gone unscored."""
    scores = score_nodes(a_case(), [an_answer_at("prohibited", True)])
    assert [s.outcome for s in scores] == ["wrong"]


def test_every_derived_field_is_a_real_case_field():
    for field in DERIVED_FROM_CLASS:
        assert field in ClassificationCase.model_fields


# --- base rate ------------------------------------------------------------------------------------
def test_a_column_a_constant_answer_would_carry_is_flagged():
    """A node whose key says the same thing on nearly every case scores well by never varying.
    Flagged beside the number, because the accuracy alone reads as a working node."""
    cases = [a_case(case_id=f"c{i}") for i in range(10)]
    pairs = [(c, score_nodes(c, [an_answer_at("prohibited", False)])) for c in cases]
    run = NodeRunScore(
        scores=[s for _, ss in pairs for s in ss], asked=Counter({"prohibited": 10})
    )
    assert "every expected answer identical — unmeasured" in "\n".join(run.lines())


def test_a_balanced_column_is_not_flagged():
    mixed = [a_case(case_id="ok")] + [
        a_case(
            case_id=f"banned{i}",
            expected_risk_class=RiskClass.PROHIBITED,
            expected_prohibited=True,
        )
        for i in range(3)
    ]
    scores = [
        s
        for c in mixed
        for s in score_nodes(
            c, [an_answer_at("prohibited", c.expected_risk_class == RiskClass.PROHIBITED)]
        )
    ]
    run = NodeRunScore(scores=scores, asked=Counter({"prohibited": len(mixed)}))
    assert "share one expected answer" not in "\n".join(run.lines())
