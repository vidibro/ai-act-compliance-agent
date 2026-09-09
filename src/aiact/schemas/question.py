"""The QUESTION/ANSWER contract — one narrow legal question, put to a brain, answered from a
document against verbatim law.

Shared by both askers, which is why it is not in `classification.py`. The classification cascade
asks what a system IS; the gap layer asks Art. 25 — who the READER is. Neither owns this shape, and
naming it after one of them was the same category error as putting the Art. 25 node in the cascade.

Nothing here knows about risk classes, rules or reports. What makes an answer trustworthy lives
entirely in this pair: the question carries the enacted text it must be answered against
(`context`) and the provision it rests on (`source`), and the answer carries evidence from the
document, a confidence, and — when the description simply does not say — a reason for declining
instead of a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, field_validator

from aiact.schemas.policy import GuidanceSource, LegalSource

Confidence = Literal["high", "medium", "low"]

AbstentionCause = Literal["description_silent", "reply_unusable"]
"""WHY a node declined — the two causes need different things from the reader, so a report that
merges them sends people to fix the wrong thing.

- `description_silent` — the documentation does not contain the fact. The user must supply it; the
  report should name which fact and which article needs it. Re-running unchanged will not help.
- `reply_unusable` — the model returned something unreadable (empty, malformed, unparseable). The
  documentation may be perfectly adequate. Re-running may well fix it, and telling the user to edit
  their document would be wrong."""

EVIDENCE_QUOTE_MAX = 300  # force citing a pinpoint excerpt, not dumping a section


def _check_not_raw_text(v: Any) -> Any:
    """Every node's value is a bool, an enum member, a list of them, or None. A bare `str` is text
    that reached a verdict unparsed — the enum members are StrEnum, so this tests the exact type."""
    if type(v) is str:
        raise ValueError(
            f"Answer.value must be parsed, not raw text (got {v[:60]!r}). A node's value is a "
            f"bool, an enum member, a list of them, or None."
        )
    return v


def _check_quote_length(v: str | None) -> str | None:
    if v is not None and len(v) > EVIDENCE_QUOTE_MAX:
        raise ValueError(
            f"evidence_quote must be under {EVIDENCE_QUOTE_MAX} chars "
            f"(got {len(v)}) — cite a pinpoint excerpt, do not dump a section."
        )
    return v


@dataclass(frozen=True)
class Question:
    """One question the cascade asks, with the provision it rests on and the shape of a valid
    answer — the INPUT half of the contract whose output half is Answer.

    Named for what it IS (a legal question) rather than where it happens to be used. Both askers
    bind one of these to each node — the classification cascade and the gap layer's Art. 25
    question alike — and nothing about the shape is specific to either. `node_id` is the only
    coupling: the key an asker looks it up by, and what an answer carries back.

    A plain frozen dataclass, not a BaseModel: it is authored in code as a literal constant (see
    the QUESTIONS tables in classify/graph.py and gap/roles.py), never parsed from user input, so
    there is nothing to validate at a trust boundary."""

    node_id: str
    source: LegalSource
    text: str  # the question itself, put to a brain verbatim
    answer_type: str  # "bool" | "annex_area" | "derogation" — the shape a valid answer takes

    label: str = ""
    """The same question in one plain line, for a human reading a report."""
    context: str = ""
    """The VERBATIM enacted text of the cited provision, for the brain to reason against.

    Empty by default so the deterministic path needs no file IO; each asker's `load_questions()`
    fills it from the article/annex store, via `aiact.anchoring`. A model must never answer "which
    Annex III area is this?" from its own memory of the Annex — the same rule that governs the
    obligation `requirement` fields."""

    guidance_context: str = ""
    """VERBATIM Commission guidance for this question — the SAME anti-memory rule as `context`, one
    level up. Where the enacted text leaves a question open (e.g. does Art. 5(1)(f) 'workplace'
    cover hiring?), a model answering from `context` alone can only GUESS; the answer isn't in the
    Act. So the authoritative interpretation is supplied here, labelled non-binding, rather than
    left to the model's memory. Filled by `load_questions()`; empty where no guidance applies."""

    guidance_sources: tuple[GuidanceSource, ...] = ()
    """Citations for whatever is in `guidance_context`, carried onto the answer so a verdict reached
    with guidance in context can say so. Non-binding by construction (see GuidanceSource)."""


class Answer(BaseModel):
    """Every decision a brain makes must be evidence-backed and citable.

    `source` is required and has no default: an uncited answer cannot be constructed."""

    value: Any  # narrow per node at the call site (bool, list[AnnexIIIArea], ...)
    reasoning: str
    evidence_quote: str | None = None  # short excerpt from the source doc
    evidence_chunk_id: str | None = None
    confidence: Confidence
    source: LegalSource
    node_id: str | None = None  # which question produced this — the key in an asker's QUESTIONS
    abstained_because: AbstentionCause | None = None  # set only when the node declined to answer
    guidance_sources: list[GuidanceSource] = []  # non-binding guidance that was in context for
    # this node — present so the verdict can record it rested on Commission interpretation, not law

    _quote_length = field_validator("evidence_quote")(_check_quote_length)
    _value_parsed = field_validator("value")(_check_not_raw_text)


_T = TypeVar("_T")


def narrow(answer: Answer | None, kind: type[_T]) -> _T | None:
    """The answer's value, but only if it is the type the caller can act on.

    Narrowing by TYPE rather than by truthiness, which is a rule this codebase applies everywhere a
    brain's answer drives a decision: a value nobody recognises is not a finding, and a finding that
    cannot be cited must not change what a report says. `None` covers all three of "not asked",
    "answered nothing" and "answered something unusable" — the caller that needs to tell those apart
    reads the Answer itself, which is why this returns the value and not a verdict."""
    value = answer.value if answer is not None else None
    return value if isinstance(value, kind) else None
