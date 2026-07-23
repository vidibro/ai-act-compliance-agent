"""The classification cascade as a LangGraph — reproduces the EC AI Act Compliance Checker flow.

Order (Commission's, with our deliberate split of profiling before derogation):

    is_ai ─not AI─────────────────────────────────────────────► minimal
      │ AI
    prohibited ─Art.5 yes──────────────────────────────────────► PROHIBITED
      │ no
    annex_iii ─not in Annex III───────────────────────────────► minimal
      │ in Annex III
    profiling ─Art.6(3) yes────────────────────────────────────► HIGH_RISK   (carve-back)
      │ no
    derogation ─Art.6(3)(a-d) applies──────────────────────────► NOT_HIGH_RISK
                └─ none ──────────────────────────────────────► HIGH_RISK

Art. 50 transparency is NOT on this path. It is a separate axis — a minimal-risk generator and a
high-risk chatbot can both owe it — so `assemble` asks it unconditionally and reports it beside the
risk class. It never routes anything and never affects the tier.

Any node answering with LOW confidence routes straight to `assemble`, which yields NEEDS_REVIEW —
abstaining beats guessing. The flip lives in this routing: the SAME sub-answers, with profiling
true vs false, land on high_risk vs not_high_risk. The graph is brain-agnostic (see brain.py), so
this logic is proven deterministically before any LLM is involved.

`assemble` builds the real UseCaseClassification, whose validator re-checks the Art. 6(3)
carve-back — so a mis-wired route RAISES rather than emitting a wrong verdict.

SCOPE: ONE use case per run. GraphState carries a single description, so ClassificationResult
always comes back with exactly one entry in `use_cases`. Art. 6 classifies per intended purpose,
and one product can hold several classifications at once (a CV tool that parses, scores, AND
drafts job ads is three use cases in three different tiers) — but splitting a document into its
intended purposes is a separate step ABOVE this graph, deferred to M7 (see docs/ROADMAP.md). The
cascade needs no change to support it: it is already per-use-case, and would simply be run N times.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from aiact.config import get_settings
from aiact.graph.brain import ClassificationBrain
from aiact.guidance import load_snippet
from aiact.schemas.classification import (
    ClassificationAnswer,
    ClassificationEvidence,
    ClassificationQuestion,
    ClassificationResult,
    Confidence,
    UseCaseClassification,
)
from aiact.schemas.enums import RiskClass
from aiact.schemas.policy import GuidanceSource, LegalSource

_ACT_DATE = date(2024, 7, 12)


def _src(article: int, paragraph: int | None = None, annex: str | None = None) -> LegalSource:
    return LegalSource(
        instrument="Regulation (EU) 2024/1689",
        article=article,
        paragraph=paragraph,
        annex=annex,
        act_version_date=_ACT_DATE,
    )


# The cascade's questions, in the order the Commission's checker asks them (prohibited BEFORE
# high-risk; profiling as our separate node before derogation — see classification.py).
QUESTIONS: dict[str, ClassificationQuestion] = {
    "is_ai": ClassificationQuestion(
        "is_ai",
        _src(3, 1),
        "Is the described system an 'AI system' within the meaning of Article 3(1)?",
        "bool",
    ),
    "prohibited": ClassificationQuestion(
        "prohibited",
        _src(5),
        "Is the described system a prohibited practice under Article 5 (for example, inferring "
        "emotions of natural persons in the workplace)?",
        "bool",
    ),
    "annex_iii": ClassificationQuestion(
        "annex_iii",
        _src(6, 2, annex="III"),
        # SCOPE ONLY — deliberately, on legal grounds. Art. 6(2) puts a system inside an Annex III
        # area; Art. 6(3) then takes it out "by derogation". They are sequential, and this node is
        # the first one. Left unqualified, the question invites both judgements at once — and
        # because Art. 6(3) sits in the same supplied Article 6 text, a model reads on and answers
        # "no area" for a system that IS in scope but has a narrow role. That collapses
        # not_high_risk (Art. 6(4) documentation and registration still owed) into minimal (nothing
        # owed), and it skips the derogation node entirely so the reason is never recorded.
        "Which Annex III high-risk area, if any, does this use case fall within (Article 6(2))? "
        "Decide SCOPE ONLY: does the described purpose match one of the Annex III area "
        "descriptions? Do NOT consider whether the system's role is narrow, procedural, "
        "preparatory, or merely assistive — Article 6(3) exemptions are assessed separately at a "
        "later step, and a system can fall within an Annex III area and still be exempt there. "
        "Answer the area, or none only if the purpose matches no Annex III area at all.",
        "annex_area",
    ),
    "profiling": ClassificationQuestion(
        "profiling",
        _src(6, 3),
        "Does this use case perform profiling of natural persons (Article 6(3))? Profiling means "
        "evaluating or scoring a person, as opposed to a purely procedural task.",
        "bool",
    ),
    "derogation": ClassificationQuestion(
        "derogation",
        _src(6, 3),
        "Does an Article 6(3)(a)-(d) derogation apply — narrow procedural task; improves a "
        "completed human activity; detects decision patterns; or a preparatory task? Answer which, "
        "or none.",
        "derogation",
    ),
    "transparency": ClassificationQuestion(
        "transparency",
        _src(50),
        # The examples span all FOUR paragraphs on purpose. They previously named only (1) and (2),
        # silently omitting emotion recognition and deep fakes — half the article, and the half that
        # covers this project's own prohibited cases. The full text is supplied as context either
        # way, so the model could reach 50(3) regardless; an example list that stops at the
        # provider paragraphs still tilts it, and Art. 50 binds providers AND deployers.
        "Do Article 50 transparency obligations apply to this system — under any paragraph, and "
        "whether the duty falls on the provider or the deployer? For example: it interacts "
        "directly with natural persons (50(1)); it generates synthetic audio, image, video or "
        "text (50(2)); it is an emotion recognition or biometric categorisation system (50(3)); "
        "it produces deep fakes or public-interest text (50(4)).",
        "bool",
    ),
}

# Which verbatim provisions each question must be answered against. The classification questions
# are anchored the same way the obligation `requirement` fields are: from the stored enacted text,
# never from a model's memory of the law. Annex III in particular IS the list of high-risk areas —
# asking "which Annex III area is this?" without supplying Annex III is exactly the unanchored
# guessing this project exists to avoid.
_QUESTION_CONTEXT: dict[str, tuple[tuple[int, ...], tuple[str, ...]]] = {
    "is_ai": ((3,), ()),  # Art. 3 — the 'AI system' definition
    "prohibited": ((5,), ()),  # Art. 5 — the prohibited practices
    "annex_iii": ((6,), ("III",)),  # Art. 6(2) + the Annex III area list itself
    "profiling": ((6,), ()),  # Art. 6(3) — the carve-back
    "derogation": ((6,), ()),  # Art. 6(3)(a)-(d)
    "transparency": ((50,), ()),  # Art. 50
}

# NON-BINDING Commission guidance to supply per question, by snippet ref (data/policy/guidance/).
# Only for questions the ENACTED TEXT leaves open: Art. 5(1)(f) prohibits emotion recognition "in
# the workplace" but never says whether hiring counts — so a model reading Art. 5 alone can only
# guess. The Commission's reading is supplied here (labelled non-binding), the same anti-memory
# discipline as _QUESTION_CONTEXT, one level up. A verdict reached with it says it rested on
# interpretation, not law. (Coarse for now: attached to the whole `prohibited` node; the snippet is
# only relevant to its Art. 5(1)(f) sub-question, harmless where it is not.)
_QUESTION_GUIDANCE: dict[str, tuple[str, ...]] = {
    "prohibited": ("C-2025-5052/workplace-covers-recruitment",),
}


def _provision_text(path: Path) -> str:
    """Read a stored article/annex file, stripping its YAML front matter."""
    raw = path.read_text(encoding="utf-8")
    _, sep, body = raw.partition("\n---\n")
    return (body if sep else raw).strip()


def load_questions(
    version: str | date | None = None,
    articles_root: str | Path | None = None,
    annexes_root: str | Path | None = None,
    guidance_root: str | Path | None = None,
) -> dict[str, ClassificationQuestion]:
    """QUESTIONS with each `context` filled from the verbatim article/annex store, and
    `guidance_context` filled from the guidance store where the enacted text leaves a question open.

    Use this for any brain that actually reads the law (LLMBrain). The bare QUESTIONS constant is
    left context-free so the deterministic ScriptedBrain path needs no file IO.
    """
    settings = get_settings()
    v = version or settings.act_version_date
    v_str = v.isoformat() if isinstance(v, date) else str(v)
    art_dir = Path(articles_root or settings.policy_articles_path) / v_str
    ann_dir = Path(annexes_root or settings.policy_annexes_path) / v_str

    resolved: dict[str, ClassificationQuestion] = {}
    for node_id, question in QUESTIONS.items():
        articles, annexes = _QUESTION_CONTEXT.get(node_id, ((), ()))
        chunks: list[str] = []
        for n in articles:
            p = art_dir / f"article-{n:03d}.md"
            if not p.is_file():
                raise FileNotFoundError(
                    f"{node_id}: no stored text for Article {n} at {p}. Run: "
                    f"python scripts/fetch_articles.py --version-date {v_str}"
                )
            chunks.append(_provision_text(p))
        for roman in annexes:
            p = ann_dir / f"annex-{roman}.md"
            if not p.is_file():
                raise FileNotFoundError(
                    f"{node_id}: no stored text for Annex {roman} at {p}. Run: "
                    f"python scripts/fetch_articles.py --version-date {v_str}"
                )
            chunks.append(_provision_text(p))

        # Non-binding guidance, where the enacted text leaves the question open.
        g_chunks: list[str] = []
        g_sources: list[GuidanceSource] = []
        for ref in _QUESTION_GUIDANCE.get(node_id, ()):
            snippet = load_snippet(ref, guidance_root)
            g_chunks.append(f"[{snippet.document}, {snippet.locator}]\n{snippet.body}")
            g_sources.append(snippet.to_source())

        resolved[node_id] = replace(
            question,
            context="\n\n".join(chunks),
            guidance_context="\n\n".join(g_chunks),
            guidance_sources=tuple(g_sources),
        )
    return resolved


class GraphState(BaseModel):
    description: str
    use_case_id: str = "use_case"
    is_ai_system: ClassificationAnswer | None = None
    prohibited: ClassificationAnswer | None = None
    in_annex_iii: ClassificationAnswer | None = None
    performs_profiling: ClassificationAnswer | None = None
    derogation: ClassificationAnswer | None = None
    transparency: ClassificationAnswer | None = None
    result: ClassificationResult | None = None


def _is_low_confidence(a: ClassificationAnswer | None) -> bool:
    return a is not None and a.confidence == "low"


def _get_answers(state: GraphState) -> list[ClassificationAnswer]:
    """The answers that determine the RISK CLASS.

    `transparency` is deliberately absent. Art. 50 is a separate axis, not a step in the risk
    cascade — a minimal-risk generator and a high-risk chatbot can both trigger it. If it were
    counted here, a low-confidence transparency answer would wrongly drag the whole classification
    to needs_review, and an Art. 50 finding would look like it influenced the tier. It does not."""
    answers = [
        state.is_ai_system,
        state.prohibited,
        state.in_annex_iii,
        state.performs_profiling,
        state.derogation,
    ]
    return [a for a in answers if a is not None]


# What each node needed the DESCRIPTION to state, phrased for the person who has to go and write it.
# NOT the question text: that is addressed to a model reading the enacted provision beside it, and
# lands as jargon on an author ("does this use case perform profiling?").
_WHAT_THE_NODE_NEEDED: dict[str, str] = {
    "is_ai": "whether this is an AI system — does it infer its outputs, or follow rules a person "
    "wrote",
    "prohibited": "whether it infers emotions, categorises people biometrically, or scores social "
    "behaviour",
    "annex_iii": "what the system is actually used for",
    "profiling": "whether it evaluates, scores or ranks people — and on what",
    "derogation": "whether it only performs a narrow procedural task, improves prior human work, "
    "detects decision patterns, or prepares an assessment",
    "transparency": "whether it generates content or interacts with people directly",
}


def _cite(source: LegalSource) -> str:
    cite = f"Art. {source.article}"
    if source.paragraph:
        cite += f"({source.paragraph})"
    return cite


def _why_it_could_not_decide(abstentions: list[ClassificationAnswer]) -> str:
    """Name the MISSING FACT and the article that needed it, instead of 'a node abstained'.

    An answer of 'needs review' that does not say what was missing gives the reader nothing to act
    on — they cannot tell whether to edit their documentation, and if so what to add. The node_id
    and the citation were already on the answer and were being discarded here.

    Split by cause: a silent document is the user's to fix, an unreadable model reply is not, and
    telling someone to rewrite adequate documentation would be worse than saying nothing."""
    silent = [a for a in abstentions if a.abstained_because == "description_silent"]
    broken = [a for a in abstentions if a.abstained_because != "description_silent"]

    parts: list[str] = []
    if silent:
        missing = "; ".join(
            f"{_WHAT_THE_NODE_NEEDED.get(a.node_id or '', 'the fact this question turns on')} "
            f"({_cite(a.source)})"
            for a in silent
        )
        parts.append(
            f"The description does not state: {missing}. Add it and re-run — the answer cannot be "
            f"inferred from what is there, and guessing it would decide the risk class on a fact "
            f"the documentation never supplied."
        )
    if broken:
        nodes = ", ".join(f"{a.node_id} ({_cite(a.source)})" for a in broken)
        parts.append(
            f"No usable answer was returned for: {nodes}. This is a failure of the run, not of the "
            f"documentation — re-running may resolve it."
        )
    return " ".join(parts) or "A classification node abstained; escalate to a human reviewer."


def decide_risk_class(state: GraphState) -> tuple[RiskClass, str, list[ClassificationEvidence]]:
    """Derive the risk class from whatever nodes were answered. Order encodes the cascade:
    abstention first, then prohibition, then the Annex III / profiling / derogation logic.

    Returns EVIDENCE, not bare citations: the deciding node's answer travels out whole, so the
    verdict names both the provision and the words in the documentation that triggered it."""
    evidence = ClassificationEvidence.from_answer
    answers = _get_answers(state)
    low_confidence = [a for a in answers if a.confidence == "low"]
    if low_confidence:
        return (
            RiskClass.NEEDS_REVIEW,
            _why_it_could_not_decide(low_confidence),
            [evidence(a) for a in low_confidence],
        )
    if state.is_ai_system and state.is_ai_system.value is not True:
        return (
            RiskClass.MINIMAL,
            "Not an AI system within Art. 3(1); outside the Regulation's risk tiers.",
            [evidence(state.is_ai_system)],
        )
    if state.prohibited and state.prohibited.value is True:
        return (
            RiskClass.PROHIBITED,
            "Prohibited practice under Art. 5; evaluated before high-risk classification.",
            [evidence(state.prohibited)],
        )
    if state.in_annex_iii and state.in_annex_iii.value is None:
        return (
            RiskClass.MINIMAL,
            "Falls within no Annex III high-risk area (Art. 6(2)); minimal risk.",
            [evidence(state.in_annex_iii)],
        )
    if state.performs_profiling and state.performs_profiling.value is True:
        # The carve-back is driven by profiling, but it only bites because the use case is in
        # Annex III — cite both, each with its own evidence.
        triggers = [state.in_annex_iii, state.performs_profiling]
        return (
            RiskClass.HIGH_RISK,
            "Performs profiling of natural persons; Art. 6(3) makes it high-risk "
            "notwithstanding any derogation.",
            [evidence(a) for a in triggers if a is not None],
        )
    if state.derogation is not None:
        if state.derogation.value is not None:
            return (
                RiskClass.NOT_HIGH_RISK,
                "Within an Annex III area, but an Art. 6(3) derogation applies; not high-risk. "
                "Art. 6(4) documentation still a must.",
                [evidence(state.derogation)],
            )
        return (
            RiskClass.HIGH_RISK,
            "Within an Annex III area with no applicable Art. 6(3) derogation; high-risk.",
            [evidence(state.in_annex_iii)] if state.in_annex_iii else [],
        )
    return (
        RiskClass.NEEDS_REVIEW,
        "The cascade did not reach a defensible terminal; escalate to a human reviewer.",
        [],
    )


# --- routing ------------------------------------------------------------------------------------
# Each routing function runs right after its node, so `a` is set — but we guard `a is None`
# anyway: it satisfies the type checker and defensively routes an impossible missing answer to
# `assemble` (which yields needs_review) rather than crashing.
def _route_is_ai(state: GraphState) -> str:
    a = state.is_ai_system
    return "assemble" if a is None or _is_low_confidence(a) or a.value is not True else "prohibited"


def _route_prohibited(state: GraphState) -> str:
    a = state.prohibited
    return "assemble" if a is None or _is_low_confidence(a) or a.value is True else "annex_iii"


def _route_annex(state: GraphState) -> str:
    a = state.in_annex_iii
    if a is None or _is_low_confidence(a):
        return "assemble"
    return "assemble" if a.value is None else "profiling"


def _route_profiling(state: GraphState) -> str:
    a = state.performs_profiling
    return "assemble" if a is None or _is_low_confidence(a) or a.value is True else "derogation"


def build_graph(
    brain: ClassificationBrain,
    questions: dict[str, ClassificationQuestion] | None = None,
):
    """Compile the cascade around a given brain.

    `questions` defaults to the context-free QUESTIONS. Pass `load_questions()` to anchor every
    question in the verbatim article/annex text — which any brain that actually reads the law
    should do."""
    asked = questions if questions is not None else QUESTIONS

    def _ask(node_id: str, description: str) -> ClassificationAnswer:
        question = asked[node_id]
        answer = brain.decide(question, description)
        # Record the non-binding guidance that was in context for this node onto the answer, so it
        # travels to the verdict. Done HERE, in the graph, not in each brain: it is bookkeeping
        # about what the question carried, not part of answering — so every brain gets it for free
        # and none needs to know guidance exists.
        # ...but NOT onto an abstention. A node that declined did not rest on the guidance — it
        # rested on nothing — and `rests_on_guidance` would then warn a reader that a verdict leaned
        # on Commission interpretation when no verdict was reached at all.
        declined = answer.abstained_because is not None
        if question.guidance_sources and not answer.guidance_sources and not declined:
            return answer.model_copy(
                update={"guidance_sources": list(question.guidance_sources)}
            )
        return answer

    def node_is_ai(state: GraphState) -> dict[str, Any]:
        return {"is_ai_system": _ask("is_ai", state.description)}

    def node_prohibited(state: GraphState) -> dict[str, Any]:
        return {"prohibited": _ask("prohibited", state.description)}

    def node_annex(state: GraphState) -> dict[str, Any]:
        return {"in_annex_iii": _ask("annex_iii", state.description)}

    def node_profiling(state: GraphState) -> dict[str, Any]:
        return {"performs_profiling": _ask("profiling", state.description)}

    def node_derogation(state: GraphState) -> dict[str, Any]:
        return {"derogation": _ask("derogation", state.description)}

    def node_assemble(state: GraphState) -> dict[str, Any]:
        # Art. 50 runs HERE, unconditionally. Every path through the cascade reaches `assemble`,
        # so asking it here — and nowhere else — is what makes transparency independent of the
        # risk tier: it is answered for a minimal generator and a high-risk chatbot alike, and it
        # never routes anything. It is an output beside the risk class, not an input to it.
        transparency = _ask("transparency", state.description)

        risk_class, reasoning, triggered = decide_risk_class(state)
        confidence: Confidence = (
            "low" if any(a.confidence == "low" for a in _get_answers(state)) else "high"
        )
        use_case = UseCaseClassification(
            use_case_id=state.use_case_id,
            description=state.description,
            annex_iii_area=state.in_annex_iii.value if state.in_annex_iii else None,
            performs_profiling=state.performs_profiling,
            derogation=state.derogation,
            risk_class=risk_class,
            triggered_by=triggered,
            reasoning=reasoning,
            confidence=confidence,
        )
        result = ClassificationResult(
            use_cases=[use_case],
            overall_risk_class=risk_class,
            reasoning=reasoning,
            triggered_by=triggered,
            confidence=confidence,
            transparency=transparency,
        )
        return {"result": result, "transparency": transparency}

    g = StateGraph(GraphState)
    g.add_node("is_ai", node_is_ai)
    g.add_node("prohibited", node_prohibited)
    g.add_node("annex_iii", node_annex)
    g.add_node("profiling", node_profiling)
    g.add_node("derogation", node_derogation)
    g.add_node("assemble", node_assemble)

    g.add_edge(START, "is_ai")
    g.add_conditional_edges(
        "is_ai", _route_is_ai, {"prohibited": "prohibited", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "prohibited", _route_prohibited, {"annex_iii": "annex_iii", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "annex_iii",
        _route_annex,
        {"profiling": "profiling", "assemble": "assemble"},
    )
    g.add_conditional_edges(
        "profiling", _route_profiling, {"derogation": "derogation", "assemble": "assemble"}
    )
    g.add_edge("derogation", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


def classify(
    description: str,
    brain: ClassificationBrain,
    use_case_id: str = "use_case",
    questions: dict[str, ClassificationQuestion] | None = None,
) -> ClassificationResult:
    """Run the cascade on one use-case description and return its ClassificationResult."""
    compiled_graph = build_graph(brain, questions)
    out = compiled_graph.invoke(GraphState(description=description, use_case_id=use_case_id))
    result = out["result"] if isinstance(out, dict) else out.result
    if result is None:
        raise RuntimeError("classification graph produced no result")
    return result
