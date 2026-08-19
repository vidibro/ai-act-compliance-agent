"""The QUESTION/ANSWER contract — one narrow legal question, put to a brain, answered from a
document against verbatim law.

Kept apart from `classification.py`, and named for what it IS rather than for the layer that
happens to ask it. Nothing in this pair knows about risk classes, rules or reports: a question
carries the enacted text it must be answered against (`context`) and the provision it rests on
(`source`), and an answer carries evidence from the document, a confidence, and — when the
description simply does not say — a reason for declining instead of a verdict. That is the whole
of what makes an answer trustworthy, and none of it is specific to classifying a system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

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

    Named for what it IS (a legal question) rather than where it happens to be used: the graph
    binds one of these to each node, but nothing about the question is graph-specific. `node_id` is
    the only graph coupling — the key the cascade looks it up by, and what an answer carries back.

    A plain frozen dataclass, not a BaseModel: it is authored in code as a literal constant
    (see graph/classify.py QUESTIONS), never parsed from user input, so there is nothing to
    validate at a trust boundary."""

    node_id: str
    source: LegalSource
    text: str  # the question itself, put to a brain verbatim
    answer_type: str  # "bool" | "annex_area" | "derogation" — the shape a valid answer takes

    label: str = ""
    """The same question in one plain line, for a human reading a report."""
    context: str = ""
    """The VERBATIM enacted text of the cited provision, for the brain to reason against.

    Empty by default so the deterministic path needs no file IO; `load_questions()` fills it from
    the article/annex store. A model must never answer "which Annex III area is this?" from its own
    memory of the Annex — the same rule that governs the obligation `requirement` fields."""

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
    """Every classification decision must be evidence-backed and citable.

    `source` is required and has no default: an uncited node answer cannot be constructed."""

    value: Any  # narrow per node at the call site (bool, list[AnnexIIIArea], ...)
    reasoning: str
    evidence_quote: str | None = None  # short excerpt from the source doc
    evidence_chunk_id: str | None = None
    confidence: Confidence
    source: LegalSource
    node_id: str | None = None  # which cascade question produced this (see graph/classify.py)
    abstained_because: AbstentionCause | None = None  # set only when the node declined to answer
    guidance_sources: list[GuidanceSource] = []  # non-binding guidance that was in context for
    # this node — present so the verdict can record it rested on Commission interpretation, not law

    _quote_length = field_validator("evidence_quote")(_check_quote_length)
