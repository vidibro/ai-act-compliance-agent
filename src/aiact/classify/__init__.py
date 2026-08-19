"""Classification graph (M3): the LangGraph cascade that turns a use-case description into a risk
class, with an injectable brain.

Layer one of two. The gap layer (`aiact.gap`) is its counterpart; neither imports the other, and
what they genuinely share lives outside both — model-call plumbing, provider profiles, usage,
tracing, the question-anchoring in `aiact.anchoring`, and the brain CONTRACT in `aiact.brain`. That
last one moved up when the gap layer gained a question of its own (Art. 25, who the reader is): a
brain answers one narrow legal question about a document, which is not specific to this layer. The
brain IMPLEMENTATIONS still live here, and the gap layer is handed one rather than building it.

Module layout:
    graph.py           the CASCADE — QUESTIONS (which questions, in what order), routing, assemble.
    scripted_brain.py  a brain that answers from a preset table (deterministic; proves routing).
    llm_brain.py       a brain that reads the description via LiteLLM (imported lazily).

LLMBrain is deliberately NOT re-exported here: importing it pulls the LLM path into scope, and the
deterministic ScriptedBrain route should stay usable without it. Import it explicitly when needed:
    from aiact.classify.llm_brain import LLMBrain
"""

from aiact.brain import Brain
from aiact.classify.graph import (
    QUESTIONS,
    GraphState,
    build_graph,
    classify,
    decide_risk_class,
)
from aiact.classify.scripted_brain import ScriptedBrain
from aiact.schemas.question import Question

__all__ = [
    # contract
    "Brain",
    "Question",
    # cascade
    "QUESTIONS",
    "GraphState",
    "build_graph",
    "classify",
    "decide_risk_class",
    # brains
    "ScriptedBrain",
]
