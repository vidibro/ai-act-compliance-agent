"""The brain CONTRACT — what a brain must do. Nothing else.

One Protocol, no data types and no implementation. The question and answer shapes live in
`schemas.question`, which is kept apart for the same reason this is:

    classify/graph.py  ──►  brain.py  ◄──  classify/scripted_brain.py
    (the ASKER: which       (contract)      classify/llm_brain.py
     questions, in                          (the ANSWERERS)
     what order)

An ASKER decides which questions are put and in what order; a brain only answers whatever it is
handed. Keeping the contract in its own module is what makes those two independent — a brain never
imports an asker, and no asker imports a brain implementation.

It sits at the top level rather than under `classify/` because nothing about it is specific to
classifying a system. A Brain answers a Question, whatever the question happens to be about.

Because `source` on every Question is a LegalSource, every Answer the
graph emits is citable by construction — the same 'no verdict without a citation' rule the schemas
enforce.
"""

from __future__ import annotations

from typing import Protocol

from aiact.schemas.question import Answer, Question


class Brain(Protocol):
    """Answers ONE Question about a described system.

    The brain makes the atomic judgement; the asker owns the legal argument around it — which
    questions are put, in what order, and what their answers add up to. Structural
    (Protocol), so an implementation need not import or subclass this — matching the shape is
    enough. See ScriptedBrain (deterministic, scripted_brain.py) and LLMBrain (reads the text,
    llm_brain.py)."""

    name: str

    def decide(
        self, question: Question, description: str
    ) -> Answer: ...
