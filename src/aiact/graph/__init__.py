"""Classification graph (M3): the LangGraph cascade that turns a use-case description into a risk
class, with an injectable brain.

Module layout:
    brain.py           the CONTRACT — the ClassificationBrain protocol, and nothing else. Depends
                       on neither the cascade nor any implementation. The question/answer shapes it
                       refers to live in schemas.classification.
    classify.py        the CASCADE — QUESTIONS (which questions, in what order), routing, assemble.
    scripted_brain.py  a brain that answers from a preset table (deterministic; proves routing).
    llm_brain.py       a brain that reads the description via LiteLLM (imported lazily).

LLMBrain is deliberately NOT re-exported here: importing it pulls the LLM path into scope, and the
deterministic ScriptedBrain route should stay usable without it. Import it explicitly when needed:
    from aiact.graph.llm_brain import LLMBrain
"""

from aiact.graph.brain import ClassificationBrain
from aiact.graph.classify import (
    QUESTIONS,
    GraphState,
    build_graph,
    classify,
    decide_risk_class,
)
from aiact.graph.scripted_brain import ScriptedBrain
from aiact.schemas.classification import ClassificationQuestion

__all__ = [
    # contract
    "ClassificationBrain",
    "ClassificationQuestion",
    # cascade
    "QUESTIONS",
    "GraphState",
    "build_graph",
    "classify",
    "decide_risk_class",
    # brains
    "ScriptedBrain",
]
