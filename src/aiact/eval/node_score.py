"""EVAL ONLY — score each cascade QUESTION, not just the risk class it added up to.

The end-to-end score says a case passed or failed. It cannot say WHICH of the nine questions
produced the failure, so a weak split tells you a route is broken and nothing about where — leaving
the cases to be read by hand, which does not scale with the golden set.

It costs nothing extra, and needs no eval-only instrumentation: `ClassificationResult.answers`
carries every question the cascade asked, in production as much as here. This is bookkeeping over a
run that happened anyway, never a second spend.

WRONG AND ABSTAINED ARE KEPT APART. They are different defects needing different fixes, and one
node can produce both — answering confidently against the key on some cases while declining on
others whose descriptions do state the fact. A single accuracy figure nets those against each other
and hides that the node fails in both directions at once.

WHAT IS SCORED, AND WHY BOTH CONDITIONS ARE NEEDED
A node is scored on a case only when the run ASKED it and the case PINS it.

  ASKED    A cascade that exits early never reaches the later questions. An `out_of_scope` case
           stops before Annex III, so counting Annex III against it would measure a question nobody
           put. `ClassificationResult.answers` is the record of what was actually put.

  PINNED   `None` in the answer key means two things — "the answer is none" and "this case does not
           fix this node" — and `model_fields_set` separates them, since Pydantic records whether
           the YAML wrote the field at all. That is necessary and not sufficient: authors also
           wrote explicit `null` to mean "never reached" (an out-of-scope case sets
           `expected_annex_iii_area: null` because the cascade stops first). ASKED is what disposes
           of those, which is why neither condition works alone.

           Two fields skip that test entirely because the risk class fixes them — see
           DERIVED_FROM_CLASS. A case need not restate what its own class already settles.

READ THE POSITIVE COUNT BEFORE THE ACCURACY. A node whose expected answer is the same on nearly
every case can score well by never varying: on a set with one prohibited case, a node that always
answers "not prohibited" is right 23 times out of 24. The table prints the positive/negative split
beside each row and flags any column a constant answer would carry, because that number measures
the base rate rather than the node.

A node with no key at all is reported as a blank row rather than omitted, so that gap stays visible
on every run instead of being inferred from an absence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from aiact.schemas.enums import RiskClass
from aiact.schemas.eval import ClassificationCase
from aiact.schemas.question import Answer

Outcome = Literal["correct", "wrong", "abstained"]

# node_id -> the ClassificationCase field holding its expected answer. None where no key exists.
# EVERY question the tool puts appears, from both askers — the classification cascade and the gap
# layer's Art. 25 role question — so a newly added one must be given a key or an explicit None here
# rather than silently going unmeasured, the failure this whole module exists to make visible. The
# answer key does not care which graph asks: it is a fact about the case.
NODE_KEYS: dict[str, str | None] = {
    "is_ai": "expected_is_ai_system",
    "territorial": "expected_territorial_link",
    "scope": "expected_scope_exclusion",
    "gpai_model": "expected_gpai_status",
    "systemic_risk": "expected_systemic_risk",
    "open_source_release": "expected_open_source_release",
    "prohibited": "expected_prohibited_practice",
    "annex_i": "expected_annex_i_product",
    "third_party_assessment": "expected_third_party_assessment",
    "annex_iii": "expected_annex_iii_area",
    "profiling": "expected_performs_profiling",
    "derogation": "expected_derogation",
    "significant_risk": "expected_poses_significant_risk",
    "transparency": "expected_transparency_duties",
    "provider_reallocation": "expected_provider_reallocation",
    "real_world_testing": "expected_real_world_testing",
    "deployer_type": "expected_deployer_type",
}

# Fields every case carries whether or not its YAML names them, so the `model_fields_set` test does
# not apply. Two reasons, and both make the field a fact about the case rather than a choice:
#
#   FIXED BY THE RISK CLASS   `ClassificationCase`'s validator ties these to the class — an Art. 5
#                             point is named exactly when the class is PROHIBITED, and an Art. 2
#                             exclusion exactly when it is OUT_OF_SCOPE. A fact the answer key
#                             already settles needs no second statement.
#                             ONE EXCEPTION, and it is why these fields are exempt rather than
#                             required: Art. 2(12) falls THROUGH the cascade, so a free and
#                             open-source case can answer `scope` and still end at `minimal`. Such a
#                             case writes the field explicitly; every other case leaves it unwritten
#                             and is scored against `None`, which is what its class already says.
#   REQUIRED                  `expected_is_ai_system` has no default, so it is always written.
#
# The rule they bypass exists for the ENUM fields, where `None` is ambiguous between "the answer is
# none" and "unpinned". Here there is nothing to disambiguate.
DERIVED_FROM_CLASS = frozenset(
    {
        "expected_prohibited_practice",
        "expected_scope_exclusion",
        "expected_is_ai_system",
        "expected_territorial_link",
        "expected_gpai_status",
    }
)

_SKEW_WARNING_AT = 0.8
"""Share of one expected answer above which a column is flagged as base-rate-dominated.

A judgement call, not a threshold with a principle behind it: at 0.8 a constant reply already
scores 80%, which reads as a passing node. Set low enough to catch the columns that need reading
twice, high enough not to shout on a genuinely balanced one."""


@dataclass(frozen=True)
class NodeScore:
    """One node, on one case."""

    case_id: str
    node_id: str
    expected: Any
    got: Any
    outcome: Outcome
    case_expects_review: bool = False
    """Whether the CASE's expected class is needs_review — which changes what an abstention means.

    On an `insufficient` case the description genuinely lacks the fact, and declining is the answer
    the key wants; reporting that beside a node that abstained on an answerable question would call
    the intended behaviour a defect. Carried rather than folded into `outcome`, because whether the
    node abstained is a fact and whether that was right is a reading of the case."""

    @property
    def label(self) -> str:
        return f"{self.case_id}/{self.node_id}"


def _abstained(answer: Answer) -> bool:
    """A node declined rather than answered.

    Two signals, because two brains produce them differently: `LLMBrain` sets `abstained_because`,
    while a scripted brain only lowers confidence. The cascade routes on confidence, so that is the
    one that decides — an answer the graph treats as an abstention is scored as one.
    """
    return answer.abstained_because is not None or answer.confidence == "low"


def score_nodes(case: ClassificationCase, answers: list[Answer]) -> list[NodeScore]:
    """The scoreable nodes for one case: asked by the run, and pinned by the case."""
    scores: list[NodeScore] = []
    for answer in answers:
        node_id = answer.node_id or ""
        field = NODE_KEYS.get(node_id)
        if field is None:
            continue
        if field not in DERIVED_FROM_CLASS and field not in case.model_fields_set:
            continue
        expected = getattr(case, field)
        if _abstained(answer):
            outcome: Outcome = "abstained"
        else:
            outcome = "correct" if answer.value == expected else "wrong"
        scores.append(
            NodeScore(
                case_id=case.case_id,
                node_id=node_id,
                expected=expected,
                got=answer.value,
                outcome=outcome,
                case_expects_review=case.expected_risk_class == RiskClass.NEEDS_REVIEW,
            )
        )
    return scores


@dataclass(frozen=True)
class NodeRunScore:
    """Per-node results over a whole run, with the ASKED counts kept beside them.

    `asked` is carried separately from the scores because the gap between them is itself the
    finding: a node asked 24 times and pinned 4 is a node whose measurement is thin, and a reader
    who sees only "4/4 correct" has been told the opposite of the truth.
    """

    scores: list[NodeScore]
    asked: Counter[str]

    def outcomes(self, node_id: str) -> Counter[str]:
        return Counter(s.outcome for s in self.scores if s.node_id == node_id)

    def majority_share(self, node_id: str) -> tuple[Any, int, int]:
        """The most common EXPECTED answer for a node, how often it recurs, and out of how many.

        This is what a constant answer would score. Reported beside the accuracy because the two
        are easily confused: a node scoring 23/24 on a set whose key says the same thing 23 times
        has demonstrated nothing about the node."""
        expected = [s.expected for s in self.scores if s.node_id == node_id]
        if not expected:
            return None, 0, 0
        counts = Counter(repr(e) for e in expected)
        top, hits = counts.most_common(1)[0]
        return top, hits, len(expected)

    def failures(self) -> list[NodeScore]:
        """Every node-level miss, in run order — what to read after the table."""
        return [s for s in self.scores if s.outcome != "correct"]

    def lines(self) -> list[str]:
        out = [
            "",
            "per-node accuracy — scored only where the run ASKED the node and the case PINS it",
            f"  {'node':24} {'asked':>5} {'pinned':>6} {'correct':>7} {'wrong':>5} {'abstain':>7}",
        ]
        for node_id in NODE_KEYS:
            asked = self.asked.get(node_id, 0)
            counts = self.outcomes(node_id)
            # A NODE THE RUN NEVER ASKED STILL GETS A ROW. Skipping it hides the one state worth
            # seeing — a node wired into the graph that no case reaches, whose answer therefore
            # decides obligations nothing measures. The row carries the reason so it does not read
            # as a zero score.
            if not asked:
                out.append(
                    f"  {node_id:24} {0:5} {sum(counts.values()):6} {'-':>7} {'-':>5} {'-':>7}"
                    f"   NEVER ASKED — no case reaches this node"
                )
                continue
            pinned = sum(counts.values())
            if NODE_KEYS[node_id] is None:
                out.append(
                    f"  {node_id:24} {asked:5} {'-':>6} {'-':>7} {'-':>5} {'-':>7}"
                    f"   NO KEY — unmeasured"
                )
                continue
            _, hits, total = self.majority_share(node_id)
            # A column a constant answer would nearly carry is measuring the base rate, not the
            # node. Flagged inline rather than in a footnote, beside the number it qualifies.
            skew = (
                f"   ! {hits}/{total} share one expected answer — a constant reply scores this"
                if total and hits / total >= _SKEW_WARNING_AT and hits < total
                else "   ! every expected answer identical — unmeasured"
                if total and hits == total
                else ""
            )
            out.append(
                f"  {node_id:24} {asked:5} {pinned:6} {counts['correct']:7} "
                f"{counts['wrong']:5} {counts['abstained']:7}{skew}"
            )
        failures = self.failures()
        if failures:
            out.append("")
            out.append("  nodes that did not match the key:")
            for s in failures:
                # An abstention on a case the key marks needs_review is the INTENDED answer — the
                # description genuinely lacks the fact. Saying so here stops the list reading as a
                # defect count when part of it is the tool working.
                intended = (
                    "  (case expects needs_review — declining is the intended answer)"
                    if s.outcome == "abstained" and s.case_expects_review
                    else ""
                )
                detail = f"expected {s.expected!r}, got {s.got!r}"
                out.append(f"    {s.outcome:9} [{s.label}] {detail}{intended}")
        return out


def score_node_run(
    pairs: list[tuple[ClassificationCase, list[Answer]]],
) -> NodeRunScore:
    """Score a whole run, given each case and EVERY answer the tool produced for it.

    Takes the answers rather than the ClassificationResult because they no longer all come from one
    place: the cascade's are on `result.answers`, and Art. 25 is answered by the gap layer. The
    caller assembles the list, which is also what keeps this module from having to know which graph
    asked what."""
    scores: list[NodeScore] = []
    asked: Counter[str] = Counter()
    for case, answers in pairs:
        scores.extend(score_nodes(case, answers))
        asked.update(a.node_id or "?" for a in answers)
    return NodeRunScore(scores=scores, asked=asked)
