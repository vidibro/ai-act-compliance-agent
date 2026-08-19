"""ScriptedBrain — answers from a preset table instead of reading the description.

Its purpose is to make the graph's ROUTING provable without an LLM: feed the cascade known
sub-answers and assert it lands on the right risk class. That is what lets the flip
(not_high_risk -> high_risk via the Art. 6(3) profiling carve-back) be a deterministic test and a
zero-cost demo, rather than something that only works when a model happens to cooperate.

Primarily a test/demo double — but it is also the shape two genuinely useful brains will take:
a ReplayBrain (answers recorded from an earlier run, so a report regenerates identically) and a
ReviewerBrain (a human supplies the answer a NEEDS_REVIEW case abstained on). Both are "answers
from a table"; only the table's origin differs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiact.schemas.question import Answer, Question

if TYPE_CHECKING:
    from aiact.brain import Brain


class ScriptedBrain:
    """Deterministic brain: returns preset answers. Proves the graph's ROUTING without an LLM.

    `answers` maps node_id -> the value that node should report (bool / AnnexIIIArea|None /
    DerogationCondition|None). Any node_id in `low_confidence` is answered with confidence "low",
    which the cascade treats as 'abstain' -> NEEDS_REVIEW."""

    name: str = "scripted"
    answers: dict[str, Any]
    low_confidence: frozenset[str]

    def __init__(self, answers: dict[str, Any], low_confidence: frozenset[str] = frozenset()):
        self.answers = answers
        self.low_confidence = low_confidence

    def decide(self, question: Question, description: str) -> Answer:
        return Answer(
            value=self.answers.get(question.node_id),
            reasoning=f"scripted answer for node {question.node_id!r}",
            confidence="low" if question.node_id in self.low_confidence else "high",
            source=question.source,
            node_id=question.node_id,
        )


if TYPE_CHECKING:
    # Compile-time proof that ScriptedBrain satisfies the Brain protocol —
    # name AND signature. mypy errors here if `decide`'s shape ever drifts.
    _scripted_conforms: Brain = ScriptedBrain({})
