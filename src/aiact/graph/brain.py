"""The brain CONTRACT — what a brain must do. Nothing else.

One Protocol, no data types and no implementation. The question and answer shapes live in
`schemas.classification`, with the rest of the classification contract:

    classify.py  ──►  brain.py  ◄──  scripted_brain.py / llm_brain.py
    (the cascade:      (contract)      (implementations)
     QUESTIONS,
     routing)

The cascade decides WHICH questions are asked and in what order (that logic, and the questions
themselves, live in classify.py). A brain only answers whatever it is handed. Keeping the contract
in its own module is what makes those two independent — a brain never imports the cascade, and the
cascade never imports a brain.

Because `source` on every ClassificationQuestion is a LegalSource, every ClassificationAnswer the
graph emits is citable by construction — the same 'no verdict without a citation' rule the schemas
enforce.
"""

from __future__ import annotations

from typing import Protocol

from aiact.schemas.classification import ClassificationAnswer, ClassificationQuestion


class ClassificationBrain(Protocol):
    """Answers ONE ClassificationQuestion about a use-case description.

    The brain makes the atomic judgement; the graph owns the legal cascade around it. Structural
    (Protocol), so an implementation need not import or subclass this — matching the shape is
    enough. See ScriptedBrain (deterministic, scripted_brain.py) and LLMBrain (reads the text,
    llm_brain.py)."""

    name: str

    def decide(
        self, question: ClassificationQuestion, description: str
    ) -> ClassificationAnswer: ...
