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
from typing import TYPE_CHECKING, Any

from aiact.config import get_settings
from aiact.llm import unfence
from aiact.providers import ProviderProfile, gateway_kwargs, profile_for
from aiact.schemas.classification import (
    AbstentionCause,
    ClassificationAnswer,
    ClassificationQuestion,
    Confidence,
)
from aiact.schemas.enums import AnnexIIIArea, AnnexIProduct, DerogationCondition, ScopeExclusion
from aiact.tracing import current_metadata
from aiact.usage import Usage

if TYPE_CHECKING:
    from aiact.classify.brain import ClassificationBrain

_EVIDENCE_MAX_LENGTH = 300

# The literal a model sends when the DESCRIPTION does not settle the question. Needed as a separate
# token because `null` is already taken: at annex_iii it means "within no Annex III area" and at
# derogation "no derogation applies" — both real verdicts with real legal consequences. "The text
# does not say" is a third thing, and collapsing it into either is how silence becomes a finding.
UNKNOWN = "unknown"


_SYSTEM_PROMPT = (
    "You are a careful EU AI Act classification assistant. You answer ONE narrow question about "
    "a described AI use case, based only on the description. You never decide the overall risk "
    "class. Answer ONLY from the enacted text supplied, any Commission guidance supplied, and the "
    "description — never from memory of the law. Commission guidance is NON-BINDING "
    "interpretation: rely on it where the enacted text leaves the question open, but do not treat "
    "it as the law itself. "
    # The rule that matters is about STATED vs IMPLIED, not about confidence. "Answer confidently or
    # say you are unsure" leaves the model free to treat an inference as a fact and then be sure of
    # it: "an ML component determines queue order" reads as "evaluates and
    # scores candidates". Tying the answer to a quotable span makes the test mechanical.
    "SILENCE IS NOT AN ANSWER. Answer from what the description states — in whatever words it "
    "uses; a fact can be stated plainly without repeating the terms of the question, and you "
    "should read ordinary language for its ordinary meaning. But do not supply a fact the text "
    f'never gives. Return "{UNKNOWN}" with low confidence when the description does not address '
    "the point at all, so that answering either way would mean assuming something it never says. "
    "In particular do not read an absent statement as a denial: a description that never mentions "
    "scoring is not a description of a system that does not score. "
    # The distinction the golden set draws between `insufficient` and `ambiguous` difficulty, given
    # to the model directly. Without it the escape hatch swallows every hard legal call: Art. 50
    # descriptions state the facts ("sends the invitations") and leave the CONCLUSION arguable, and
    # the brain was declining those as though the text were silent.
    f'"{UNKNOWN}" is about MISSING FACTS, not about difficult law. Where the description supplies '
    "the facts but the legal conclusion is genuinely arguable, give your best reading and lower "
    "your confidence — that is a judgement, and making it is your job. Declining is a useful "
    "answer; a confident wrong one is the worst outcome. "
    "Reply with a single JSON object and nothing else."
)


def _answer_instructions(answer_type: str) -> str:
    """What the model may put in "value" — INCLUDING the option to decline.

    Every branch offers a way out, because omitting one is not neutral: a question that permits only
    true or false instructs the model to pick one, and it will, from whatever the text implies
    rather than what it states. That is exactly how `ats_workflow_unspecified` — silent on what its
    ranking model optimises — drew "evaluates and scores candidates" at high confidence."""
    if answer_type == "bool":
        return (
            f'set "value" to true or false, or "{UNKNOWN}" if the description does not state the '
            f"facts needed to answer"
        )
    if answer_type == "annex_area":
        areas = ", ".join(a.value for a in AnnexIIIArea)
        return (
            f'set "value" to one of [{areas}]; null if it falls within no Annex III area; or '
            f'"{UNKNOWN}" if the description does not say what the system is used for'
        )
    if answer_type == "annex_i_product":
        products = ", ".join(p.value for p in AnnexIProduct)
        return (
            f'set "value" to one of [{products}]; null if the system is not a safety component '
            f"of, or itself, a product covered by Annex I; or \"{UNKNOWN}\" if the description "
            f"does not say what product the system is part of"
        )
    if answer_type == "derogation":
        conds = ", ".join(d.value for d in DerogationCondition)
        return (
            f'set "value" to one of [{conds}]; null if no derogation applies; or "{UNKNOWN}" if '
            f"the description does not establish that any condition is met"
        )
    if answer_type == "scope_exclusion":
        exclusions = ", ".join(e.value for e in ScopeExclusion)
        return (
            f'set "value" to one of [{exclusions}]; null if no Article 2 exclusion applies and the '
            f'Regulation governs the system; or "{UNKNOWN}" if the description does not state the '
            f"facts the exclusion turns on"
        )
    raise ValueError(f"unknown answer_type {answer_type!r}")


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
    raises rather than being quietly folded into one of those verdicts.

    `UNKNOWN` is the THIRD state and is checked first: 'the description does not say'. It is not a
    verdict and must never become one — silence is not evidence of absence, and a derogation
    inferred from silence hands a provider an exemption they never claimed (Art. 6(3) puts the
    burden on establishing the condition; Art. 6(4) requires it documented)."""
    if isinstance(value, str) and value.strip().lower() == UNKNOWN:
        raise Unanswerable("the description does not state the facts needed to answer")
    if answer_type == "bool":
        return _parse_bool(value)
    if value is None or (isinstance(value, str) and value.strip().lower() in ("none", "null", "")):
        return None
    if answer_type == "annex_area":
        try:
            return AnnexIIIArea(str(value).strip().lower())
        except ValueError as exc:
            raise Unanswerable(f"{value!r} is not an Annex III area") from exc
    if answer_type == "annex_i_product":
        try:
            return AnnexIProduct(str(value).strip().lower())
        except ValueError as exc:
            raise Unanswerable(f"{value!r} is not an Annex I product family") from exc
    if answer_type == "derogation":
        try:
            return DerogationCondition(str(value).strip().lower())
        except ValueError as exc:
            raise Unanswerable(f"{value!r} is not an Art. 6(3) derogation") from exc
    if answer_type == "scope_exclusion":
        try:
            return ScopeExclusion(str(value).strip().lower())
        except ValueError as exc:
            raise Unanswerable(f"{value!r} is not an Art. 2 exclusion") from exc
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
        self.profile = profile or profile_for(self.model, effort or settings.effort_for("classify"))
        self.usage = Usage()

    def _abstain(
        self,
        question: ClassificationQuestion,
        why: str,
        cause: AbstentionCause = "reply_unusable",
    ) -> ClassificationAnswer:
        """No usable answer -> answer with LOW confidence, which the cascade routes to
        NEEDS_REVIEW. For a compliance tool a confident wrong answer is the worst outcome, so an
        unreadable reply must escalate to a human rather than degrade into a default verdict.

        `cause` defaults to `reply_unusable` because most callers here ARE model failures — empty
        completions, malformed JSON. Only a deliberate UNKNOWN means the documentation is silent,
        and the two must not be reported the same way: one asks the user to edit their document,
        the other to re-run."""
        return ClassificationAnswer(
            value=None,
            reasoning=f"Abstained on {question.node_id!r}: {why}.",
            confidence="low",
            source=question.source,
            node_id=question.node_id,
            abstained_because=cause,
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
        # Guidance sits in the STABLE prefix beside the enacted text — it too is identical for every
        # use case at this node — and is clearly separated and labelled non-binding, so the model
        # can lean on it where the Act is silent without mistaking it for the law.
        guidance = (
            f"Commission guidance (NON-BINDING interpretation — rely on it where the enacted text "
            f"leaves the question open, but it is not the law itself):\n"
            f'"""\n{question.guidance_context}\n"""\n\n'
            if question.guidance_context
            else ""
        )
        stable = law + guidance
        task = (
            f"Question: {question.text}\n\n"
            f"Use-case description:\n\"\"\"\n{description}\n\"\"\"\n\n"
            f"Answer as JSON with keys: value ({_answer_instructions(question.answer_type)}), "
            f'"reasoning" (one sentence), "evidence_quote" (the span of the DESCRIPTION that '
            f"drove your answer, copied exactly, under {_EVIDENCE_MAX_LENGTH} characters — never a "
            f"quote of the law; if the description does not address the point at all, that is the "
            f'case for "{UNKNOWN}" rather than a quote that merely sounds related), '
            f'"confidence" (one of "high", "medium", "low").'
        )
        if not self.profile.caches(stable):
            return stable + task
        return [
            {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": task},
        ]

    def decide(self, question: ClassificationQuestion, description: str) -> ClassificationAnswer:
        import litellm  # lazy: only needed when actually classifying with a model

        user_content = self._user_content(question, description)
        # Trace metadata is present only when Langfuse keys are configured AND we are inside a
        # classify() trace scope; otherwise None, and the call is identical to an untraced one.
        metadata = current_metadata(question.node_id)
        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            **({"metadata": metadata} if metadata else {}),
            **gateway_kwargs(),
            **self.profile.completion_kwargs,
        )
        # counted even if we abstain below: a wasted call still costs
        self.usage.record(response, cache_marked=isinstance(user_content, list))

        # `choices` is a list because the API can return n independent completions; we never pass
        # n, so there is exactly one. `content` is None (not "") when the model produced no text at
        # all — a cut-off generation, a refusal, a tool call. That is an ABSENCE of an answer, and
        # must not fall through to `value=None`, which at annex_iii/derogation is a real verdict.
        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            return self._abstain(question, "the model returned an empty completion")
        try:
            data = json.loads(unfence(raw))
        except json.JSONDecodeError as exc:
            return self._abstain(question, f"the model's reply was not valid JSON: {exc}")
        if not isinstance(data, dict):
            return self._abstain(question, f"expected a JSON object, got {type(data).__name__}")

        try:
            value = _parse_value(question.answer_type, data.get("value"))
        except Unanswerable as exc:
            # A deliberate UNKNOWN is the model doing its job, not failing at it: the documentation
            # does not settle the question. Everything else here is a genuine parse failure.
            silent = str(data.get("value", "")).strip().lower() == UNKNOWN
            return self._abstain(
                question,
                f"unusable answer: {exc}" if not silent else str(exc),
                cause="description_silent" if silent else "reply_unusable",
            )
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
