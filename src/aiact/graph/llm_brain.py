"""LLMBrain — answers a classification node by actually reading the description, via LiteLLM.

This is the brain that reads text; the graph around it (classify.py) is identical to the one the
ScriptedBrain drives. LiteLLM routes to whatever provider `settings.llm_model` names, so the model
choice is config, not code.

Deliberately thin: one node question -> one small structured answer. The graph, not the model, owns
the legal cascade — so the model is never asked "what risk class is this?", only narrow, checkable
questions like "does this use case perform profiling?". That keeps each judgement auditable and is
what the eval measures.

Requires an API key for the configured model; importing this module does not (litellm is imported
lazily), so the deterministic ScriptedBrain path stays dependency-light.

This class names NO vendor-specific request parameters. Sampling, reasoning depth, and prompt
caching all differ per provider — and Anthropic's current models reject `temperature` outright —
so their shapes live behind the provider seam (providers.py) and are splatted in. That is what
keeps 'the model choice is config, not code' actually true rather than aspirational.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from aiact.config import get_settings
from aiact.providers import ProviderProfile, profile_for
from aiact.schemas.classification import (
    ClassificationAnswer,
    ClassificationQuestion,
    Confidence,
)
from aiact.schemas.enums import AnnexIIIArea, DerogationCondition
from aiact.usage import Usage

if TYPE_CHECKING:
    from aiact.graph.brain import ClassificationBrain

_EVIDENCE_MAX_LENGTH = 300

_SYSTEM_PROMPT = (
    "You are a careful EU AI Act classification assistant. You answer ONE narrow question about "
    "a described AI use case, based only on the description. You never decide the overall risk "
    "class. Answer ONLY from the enacted text supplied and the description — never from memory of "
    "the law. If the description does not let you answer confidently, say so with low confidence — "
    "abstaining is better than guessing. Reply with a single JSON object and nothing else."
)


def _answer_instructions(answer_type: str) -> str:
    if answer_type == "bool":
        return 'set "value" to true or false'
    if answer_type == "annex_area":
        areas = ", ".join(a.value for a in AnnexIIIArea)
        return f'set "value" to one of [{areas}] or null if it falls within no Annex III area'
    if answer_type == "derogation":
        conds = ", ".join(d.value for d in DerogationCondition)
        return f'set "value" to one of [{conds}] or null if no derogation applies'
    raise ValueError(f"unknown answer_type {answer_type!r}")


# Models very often wrap JSON in a markdown fence, even when told to reply with JSON and nothing
# else, and even with response_format={"type": "json_object"} set — that flag is advisory rather
# than enforced on several providers. json.loads then fails at char 0 on the backtick. Stripping
# the fence is provider-agnostic: it costs nothing where the reply is already bare JSON, and it is
# the difference between an answer and an abstention where it is not.
_FENCED_JSON = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _unfence(raw: str) -> str:
    match = _FENCED_JSON.match(raw)
    return match.group(1) if match else raw


class Unanswerable(Exception):
    """The reply could not be read as a valid answer to this question.

    Raised instead of guessing. `decide` turns it into a low-confidence answer, which the cascade
    routes to NEEDS_REVIEW — a model whose output we cannot parse has not answered."""


# A model asked for a boolean sometimes sends the STRING "false" rather than JSON `false`. Every
# non-empty string is truthy in Python, so bool("false") is True — which at the profiling node
# would invert the answer and route the use case to high_risk via the Art. 6(3) carve-back, with
# full confidence. Hence an explicit vocabulary, and an abstention for anything outside it.
_TRUE_WORDS = frozenset({"true", "yes", "y", "1"})
_FALSE_WORDS = frozenset({"false", "no", "n", "0"})


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):  # checked FIRST — bool is a subclass of int
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        word = value.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
    raise Unanswerable(f"cannot read {value!r} as true or false")


def _parse_value(answer_type: str, value: object) -> object:
    """Turn the model's raw JSON value into the typed value the schema expects.

    `None` here is a REAL ANSWER, not missing data: at the annex_iii node it means 'no Annex III
    area' (-> minimal risk), at derogation it means 'no derogation applies' (-> high risk). So the
    several ways a model writes 'nothing here' normalise to None, while anything UNRECOGNISED
    raises rather than being quietly folded into one of those verdicts."""
    if answer_type == "bool":
        return _parse_bool(value)
    if value is None or (isinstance(value, str) and value.strip().lower() in ("none", "null", "")):
        return None
    if answer_type == "annex_area":
        try:
            return AnnexIIIArea(str(value).strip().lower())
        except ValueError as exc:
            raise Unanswerable(f"{value!r} is not an Annex III area") from exc
    if answer_type == "derogation":
        try:
            return DerogationCondition(str(value).strip().lower())
        except ValueError as exc:
            raise Unanswerable(f"{value!r} is not an Art. 6(3) derogation") from exc
    raise ValueError(f"unknown answer_type {answer_type!r}")


class LLMBrain:
    """Answers one question with a single LiteLLM completion, parsed into a
    ClassificationAnswer."""

    name: str = "llm"
    model: str
    profile: ProviderProfile
    usage: Usage
    """Running token/cost tally for this brain's whole run. Cost compounds across repeated eval
    runs, so it is measured rather than argued about — see usage.py."""

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        profile: ProviderProfile | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        # No sampling/thinking/caching parameters are named in this class — the provider seam owns
        # them, because every one of them is vendor-specific (see providers.py).
        self.profile = profile or profile_for(self.model, effort or settings.llm_effort)
        self.usage = Usage()

    def _abstain(self, question: ClassificationQuestion, why: str) -> ClassificationAnswer:
        """No usable answer -> answer with LOW confidence, which the cascade routes to
        NEEDS_REVIEW. For a compliance tool a confident wrong answer is the worst outcome, so an
        unreadable reply must escalate to a human rather than degrade into a default verdict."""
        return ClassificationAnswer(
            value=None,
            reasoning=f"Abstained on {question.node_id!r}: {why}.",
            confidence="low",
            source=question.source,
            node_id=question.node_id,
        )

    def _user_content(self, question: ClassificationQuestion, description: str) -> Any:
        """Build the user turn, split at the CACHE BOUNDARY.

        The verbatim enacted text is identical for every use case we classify at a given node —
        Annex III does not change between candidates — so it is the stable prefix, and the question
        plus the description are the volatile suffix. Caching is a prefix match, so the stable half
        must come first and carry the breakpoint; anything volatile ahead of it would invalidate
        the whole thing.

        Returns a plain string where the provider has no cache-marker surface, so the unverified
        path stays maximally portable."""
        law = (
            f"Enacted text you must answer against (verbatim):\n"
            f'"""\n{question.context}\n"""\n\n'
            if question.context
            else ""
        )
        task = (
            f"Question: {question.text}\n\n"
            f"Use-case description:\n\"\"\"\n{description}\n\"\"\"\n\n"
            f"Answer as JSON with keys: value ({_answer_instructions(question.answer_type)}), "
            f'"reasoning" (one sentence), "evidence_quote" (the span of the DESCRIPTION that '
            f"drove your answer, copied exactly, under {_EVIDENCE_MAX_LENGTH} characters — never a "
            f"quote of the law, and null only if nothing in the description supports it), "
            f'"confidence" (one of "high", "medium", "low").'
        )
        if not self.profile.caches(law):
            return law + task
        return [
            {"type": "text", "text": law, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": task},
        ]

    def decide(self, question: ClassificationQuestion, description: str) -> ClassificationAnswer:
        import litellm  # lazy: only needed when actually classifying with a model

        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": self._user_content(question, description)},
            ],
            response_format={"type": "json_object"},
            **self.profile.completion_kwargs,
        )
        self.usage.record(response)  # counted even if we abstain below: a wasted call still costs

        # `choices` is a list because the API can return n independent completions; we never pass
        # n, so there is exactly one. `content` is None (not "") when the model produced no text at
        # all — a cut-off generation, a refusal, a tool call. That is an ABSENCE of an answer, and
        # must not fall through to `value=None`, which at annex_iii/derogation is a real verdict.
        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            return self._abstain(question, "the model returned an empty completion")
        try:
            data = json.loads(_unfence(raw))
        except json.JSONDecodeError as exc:
            return self._abstain(question, f"the model's reply was not valid JSON: {exc}")
        if not isinstance(data, dict):
            return self._abstain(question, f"expected a JSON object, got {type(data).__name__}")

        try:
            value = _parse_value(question.answer_type, data.get("value"))
        except Unanswerable as exc:
            return self._abstain(question, f"unusable answer: {exc}")
        confidence: Confidence = data.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        quote = data.get("evidence_quote")
        if isinstance(quote, str):
            quote = quote[:_EVIDENCE_MAX_LENGTH]
        else:
            quote = None

        return ClassificationAnswer(
            value=value,
            reasoning=(
                str(data.get("reasoning", "")).strip()
                or f"model answer for {question.node_id}"
            ),
            evidence_quote=quote,
            confidence=confidence,
            source=question.source,
            node_id=question.node_id,
        )


if TYPE_CHECKING:
    # Compile-time proof that LLMBrain satisfies the ClassificationBrain protocol (see brain.py).
    _llm_conforms: ClassificationBrain = LLMBrain()
