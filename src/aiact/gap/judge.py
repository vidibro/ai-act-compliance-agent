"""The judge: decide whether a document satisfies ONE obligation, from retrieved evidence.

This is where the project's central claim is cashed out. A keyword baseline scores 88.0% overall and
**0 of 6** on INADEQUATE — it cannot make the distinction at all, because matching words cannot tell
"we ensure human oversight" from three paragraphs of actual oversight measures. The judge exists to
make that distinction, and the eval exists to say by how much.

Shape, mirroring `graph/llm_brain.py`: one narrow question, one small structured answer, parsed and
constrained. The model is asked ONLY "does this excerpt satisfy this requirement?" — never which
rules apply, never the risk class, never what to do about it. Rule selection is data
(`applies_to_risk_class`, `document_verifiable`), and the verdict vocabulary is a fixed enum.

Three things this file refuses to do, each learned rather than assumed:

  - **Treat retrieval rank as evidence.** A vector search always returns k results; there is no
    "nothing found". The top hit in a document that says nothing about Art. 14 is still the top hit,
    with a confident-looking rank. So the excerpts arrive labelled as SEARCH RESULTS that may be
    irrelevant, and the model is told to say so.

  - **Trust proximity.** Measured on the dev corpus: a hollowed-out section scores CLOSER to the
    requirement than the compliant section it replaced, in 5 of 7 cases. An empty restatement of an
    obligation genuinely resembles that obligation more than a page of specifics does. Similarity
    is therefore anti-correlated with compliance on exactly the class we care about, and the prompt
    says so outright.

  - **Guess when the evidence is thin.** An unreadable or unsure answer becomes NEEDS_REVIEW. For a
    compliance tool a false PASS is the most expensive error available: it tells a provider they are
    covered when they are not.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from aiact.config import get_settings
from aiact.providers import ProviderProfile, profile_for
from aiact.retrieval.store import DocumentIndex, Hit, document_id
from aiact.schemas.classification import Confidence
from aiact.schemas.enums import CheckType, Verdict
from aiact.schemas.policy import PolicyRule
from aiact.tools.evidence import DEFAULT_K, find_evidence
from aiact.tracing import current_metadata
from aiact.usage import Usage

_EVIDENCE_MAX_LENGTH = 300

# Transient API failures are retried, with backoff, by LiteLLM.
#
# A full dev run is 133 sequential calls, so the chance that none of them hits a 429 or a gateway
# 5xx is not high — and one such failure used to abort the run and lose every judgement before it.
# (Observed: a Cloudflare 520 from api.anthropic.com, flagged retryable, mid-diagnostic.)
#
# Note what is deliberately NOT done: a failed call must not degrade into NEEDS_REVIEW. That would
# let an infrastructure blip enter the scorecard as if the judge had abstained on the evidence,
# quietly corrupting the number the whole project is judged by. A crashed run is honest and
# repeatable; a wrong number is neither. So retries first, and if they are exhausted, the exception
# propagates. Same distinction the classifier draws between `description_silent` and
# `reply_unusable`: whose fault it is changes what the reader should do.
_NUM_RETRIES = 3

# The literal for "the excerpts do not let me rule". Kept distinct from every substantive verdict
# for the same reason `UNKNOWN` is distinct from `null` in the classifier: "I cannot tell" is not
# "the documentation is missing this", and reporting one as the other is how a tool invents gaps.
UNSURE = "unsure"

_VERDICTS = {
    "pass": Verdict.PASS,
    "gap": Verdict.GAP,
    "inadequate": Verdict.INADEQUATE,
}

_SYSTEM_PROMPT = (
    "You are a careful EU AI Act compliance reviewer. You judge ONE obligation at a time against "
    "excerpts from a provider's technical documentation, and you answer only from the enacted text "
    "and the excerpts supplied — never from memory of the law, never from what a system like this "
    "usually does. You do not decide which obligations apply; that is already settled. "
    #
    # The three verdicts, written so the boundaries are decidable rather than evocative. GAP vs
    # INADEQUATE is the distinction the whole project is measured on, so it gets the most words.
    "\n\nYour verdict is exactly one of:\n"
    '- "pass": the excerpts contain substantive evidence that satisfies the requirement.\n'
    '- "inadequate": the excerpts DO address this requirement, but with no substance — an '
    "assertion that the obligation is met, restating it in its own words, with none of the "
    "specifics it demands. This is a real finding, not a soft pass.\n"
    '- "gap": the requirement is not addressed at all. Either nothing in the excerpts is about it, '
    "or what stands in its place is about something else — general assurances of responsibility, "
    "ethics or trustworthiness that never engage this obligation.\n"
    f'- "{UNSURE}": the excerpts are ambiguous or contradictory and you cannot honestly rule.\n'
    #
    # The line between INADEQUATE and GAP, stated as a test rather than a vibe, because the golden
    # set separates them by construction and a checker that blurs them scores as if it read nothing.
    # The boundary is defined by the ACTION the finding implies, not by how much text is present.
    # Stated the other way round, judges hedged every absence into "inadequate": a sentence claiming
    # the content exists elsewhere reads like an attempt, so almost nothing was ever a gap.
    "\nThe test between them is what the provider must DO next:\n"
    '- "gap" means WRITE THIS — the content does not exist anywhere in the document.\n'
    '- "inadequate" means STRENGTHEN THIS — the content exists and falls short.\n'
    '\nSo "Our human oversight measures are appropriate to the risk" is inadequate: it is about '
    'oversight, it exists, and it needs strengthening. "We are proud signatories of three AI '
    'ethics charters" is a gap: it is not about oversight at all.\n'
    #
    # The qualification matters as much as the rule. Stated absolutely ("a pointer is not
    # content"), this penalised LEGITIMATE cross-references and produced false findings against
    # compliant documentation — a technical file that says "metrics are in §8", where §8 exists and
    # holds them, is correctly drafted. The judge sees only excerpts, so it must not read "not
    # retrieved" as "not written".
    '\nCross-references need care. "The oversight measures are described in §7" is a GAP when the '
    "section list contains no §7 — a pointer to nothing is not content, and the work to be done is "
    "writing it from scratch. But when the referenced section DOES exist in the list, the pointer "
    "is legitimate drafting: the content is in the document even if it is not among your excerpts, "
    "and you must not hold its absence from the excerpts against the provider. Check the list "
    "before judging a reference."
)

# What "satisfying" means per check type. This is why `CheckType` exists on a rule: an obligation to
# DESCRIBE a capability and an obligation to REPORT FIGURES fail in different ways, and one rubric
# for both would either excuse missing numbers or invent gaps where a description is all the law
# asks for. The Art. 12 case in the golden set exists precisely to catch a judge that over-demands.
_RUBRIC: dict[CheckType, str] = {
    CheckType.PRESENCE: (
        "This is a PRESENCE check: the requirement is satisfied once the documentation states that "
        "the thing exists and describes it. Do not demand metrics, procedures or depth the article "
        "does not ask for — over-demanding here produces false findings."
    ),
    CheckType.SUBSTANCE: (
        "This is a SUBSTANCE check: existence is NOT enough. The described content must actually "
        "meet what the article demands. A claim that the obligation is met, with no measures "
        "behind it, is inadequate."
    ),
    CheckType.METRICS: (
        # "Figures must be present" was not enough, and the failure was a false PASS — the most
        # expensive error this tool can make. With Art. 15's own section deleted, the judge found a
        # selection-rate ratio of 0.94 in the risk section and confidence intervals in the
        # transparency section, and cleared the document. Those are FAIRNESS figures; Art. 15 asks
        # about accuracy and robustness. A number near the topic is not a number about the topic.
        "This is a METRICS check: concrete figures must be present, AND they must measure the "
        "property this article asks about. Figures that quantify something else — a fairness or "
        "selection-rate ratio where the article asks for accuracy — are not evidence for this "
        "obligation, however precise they look. Ask what each number MEASURES before crediting it. "
        # The counterweight, added after the first version cried wolf on compliant documentation:
        # it rejected NDCG@10 as "ranking quality, not accuracy" and demanded thresholds and
        # justifications Art. 15 never asks for. "Is this number the right KIND" is the question;
        # "is this number good enough" is the provider's judgement, not ours.
        "But do not go the other way: the standard metric of the system's own task IS its accuracy "
        "metric, and you must not demand targets, thresholds or justifications the article does "
        "not require. Declared figures for the right property are a pass even if you would have "
        "chosen different ones. A claim of high accuracy or strong robustness with NO numbers is "
        "inadequate, not a pass."
    ),
    CheckType.COMPLETENESS: (
        "This is a COMPLETENESS check: a prescribed list must be covered. Missing elements are a "
        "shortfall in an otherwise-present set — judge against the list, not against the presence "
        "of a section with the right title."
    ),
}


@dataclass(frozen=True)
class Judgement:
    """One rule's verdict, with the evidence it rests on."""

    verdict: Verdict
    reasoning: str
    evidence_quote: str | None
    evidence_chunk_id: str | None
    confidence: Confidence
    hits: tuple[Hit, ...] = ()
    """The excerpts the judge saw. Carried so a reviewer can check not just the verdict but what it
    was shown — a wrong verdict on the right passage and a wrong verdict on the wrong passage are
    different bugs, and only this tells them apart."""


def _unsure(why: str, hits: tuple[Hit, ...] = ()) -> Judgement:
    """No usable verdict -> NEEDS_REVIEW at low confidence.

    Never GAP. An unreadable reply says nothing about the provider's documentation, and defaulting
    to a finding would manufacture accusations out of our own failures.
    """
    return Judgement(
        verdict=Verdict.NEEDS_REVIEW,
        reasoning=why,
        evidence_quote=None,
        evidence_chunk_id=None,
        confidence="low",
        hits=hits,
    )


class LLMJudge:
    """Judges one rule against one document, using retrieval to find the evidence.

    Satisfies the `Checker` protocol in `eval/runner.py`, so it can be scored against the keyword
    baseline without any graph existing yet.
    """

    name: str = "llm-judge"

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        profile: ProviderProfile | None = None,
        k: int = DEFAULT_K,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.profile = profile or profile_for(self.model, effort or settings.llm_effort)
        self.k = k
        self.usage = Usage()
        # One index per document, keyed by content hash. The eval asks 7 rules of each of 19
        # documents; without this, every question would re-embed the whole file — 133 indexings
        # instead of 19, for identical results.
        self._indexes: dict[str, DocumentIndex] = {}

    def index_for(self, document: str) -> DocumentIndex:
        doc_id = document_id(document)
        if doc_id not in self._indexes:
            self._indexes[doc_id] = DocumentIndex.build(document)
        return self._indexes[doc_id]

    def _user_content(
        self, rule: PolicyRule, hits: tuple[Hit, ...], outline: tuple[str, ...] = ()
    ) -> Any:
        """Build the user turn, stable half first (see llm_brain._user_content for why).

        The obligation — enacted text, expected evidence, rubric — is identical across every
        document judged against this rule, so it is the cacheable prefix. The excerpts are the
        volatile suffix.
        """
        rubric = _RUBRIC.get(rule.check_type, _RUBRIC[CheckType.SUBSTANCE])
        stable = (
            f"Obligation under review: {rule.rule_id} (Article {rule.source.article}"
            f"{f'({rule.source.paragraph})' if rule.source.paragraph else ''}).\n\n"
            f"Enacted text you must judge against (verbatim):\n"
            f'"""\n{rule.requirement}\n"""\n\n'
            f"What documentation satisfying this looks like:\n"
            f'"""\n{rule.evidence_expected}\n"""\n\n'
            f"{rubric}\n\n"
        )

        excerpts = "\n\n".join(
            f"[{hit.chunk.chunk_id}] (section: {hit.chunk.heading_path})\n{hit.chunk.body}"
            for hit in hits
        )
        # The document's full section list. Cheap (a few dozen headings) and it closes the single
        # biggest hole in the judge's view: shown only excerpts, it cannot tell "not retrieved" from
        # "not present", so it hedges every absence into INADEQUATE. Its own reasoning said so —
        # "the excerpts do not contain the actual description, only a pointer to it".
        #
        # With the outline it can do what a human reviewer does: follow the cross-reference. A file
        # that says "oversight measures are described in §7" while the outline has no §7 is not
        # addressing the obligation, it is pointing at nothing.
        contents = "\n".join(f"- {section}" for section in outline)
        task = (
            f"Complete list of sections in this document — nothing else exists in it:\n"
            f"{contents}\n\n"
            f"The excerpts below are what a search for THIS obligation returned across ALL of "
            f"those sections. So if the substance were anywhere in the document, it would be here: "
            f"treat its absence from the excerpts as absence from the document. And if an excerpt "
            f"points at a section that is NOT in the list above, that section does not exist — a "
            f"pointer to nothing is not evidence that the obligation is met.\n\n"
            f"Excerpts retrieved from the provider's documentation. These are SEARCH RESULTS "
            f"ordered by similarity, NOT by relevance — the search always returns this many, so "
            f"some or all may be unrelated to the obligation. Judge what they say; do not assume "
            f"an excerpt is responsive because it was returned. In particular, a passage that "
            f"merely restates the obligation in the obligation's own words scores HIGHLY in this "
            f"search while containing no substance at all — rank is not evidence.\n"
            f'"""\n{excerpts}\n"""\n\n'
            f'Answer as JSON with keys: "verdict" (one of "pass", "gap", "inadequate", '
            f'"{UNSURE}"), "reasoning" (one sentence naming what is present or missing), '
            # A quote is only worth carrying if a human can find it again. Asking for ONE
            # contiguous span from ONE excerpt is not fussiness: the first live run returned a
            # quote stitched together from three excerpts with "..." between them, which reads as
            # verbatim evidence and matches nothing in the document.
            f'"evidence_quote" (ONE contiguous span copied exactly from a SINGLE excerpt, under '
            f"{_EVIDENCE_MAX_LENGTH} characters — not a stitched-together summary, never a quote "
            f"of the enacted text, and null if nothing in the excerpts is responsive), "
            f'"evidence_chunk_id" (the id of that one excerpt, bare, like c012 — not a list and '
            f'not in brackets), "confidence" (one of "high", "medium", "low").'
        )
        if not self.profile.caches(stable):
            return stable + task
        return [
            {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": task},
        ]

    def judge(self, rule: PolicyRule, document: str) -> Judgement:
        """Retrieve evidence for `rule` in `document` and rule on it."""
        import litellm  # lazy: importing this module must not require an API stack

        if not rule.document_verifiable:
            return Judgement(
                verdict=Verdict.NOT_APPLICABLE,
                reasoning=(
                    f"{rule.rule_id} is a process obligation of the provider organisation, not a "
                    f"property of the technical documentation — confirm it separately."
                ),
                evidence_quote=None,
                evidence_chunk_id=None,
                confidence="high",
            )

        index = self.index_for(document)
        hits = tuple(find_evidence(index, rule, k=self.k))
        user_content = self._user_content(rule, hits, outline(index))
        metadata = current_metadata(rule.rule_id)
        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            num_retries=_NUM_RETRIES,
            **({"metadata": metadata} if metadata else {}),
            **self.profile.completion_kwargs,
        )
        self.usage.record(response, cache_marked=isinstance(user_content, list))

        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            return _unsure(f"{rule.rule_id}: the model returned an empty completion.", hits)
        try:
            data = json.loads(_unfence(raw))
        except json.JSONDecodeError as exc:
            return _unsure(f"{rule.rule_id}: the model's reply was not valid JSON: {exc}.", hits)
        if not isinstance(data, dict):
            return _unsure(
                f"{rule.rule_id}: expected a JSON object, got {type(data).__name__}.", hits
            )

        return self._to_judgement(rule, data, hits)

    def _to_judgement(
        self, rule: PolicyRule, data: dict[str, Any], hits: tuple[Hit, ...]
    ) -> Judgement:
        token = str(data.get("verdict", "")).strip().lower()
        if token == UNSURE:
            return _unsure(
                f"{rule.rule_id}: the excerpts did not settle the question — "
                f"{str(data.get('reasoning', '')).strip() or 'no reason given'}.",
                hits,
            )
        verdict = _VERDICTS.get(token)
        if verdict is None:
            return _unsure(f"{rule.rule_id}: {token!r} is not a verdict.", hits)

        confidence: Confidence = data.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"

        quote = data.get("evidence_quote")
        quote = quote[:_EVIDENCE_MAX_LENGTH] if isinstance(quote, str) and quote.strip() else None
        chunk_id = _resolve_chunk_id(data.get("evidence_chunk_id"), quote, hits)

        reasoning = str(data.get("reasoning", "")).strip()
        if verdict in (Verdict.GAP, Verdict.INADEQUATE) and not reasoning:
            # Finding's own validator refuses this too; catching it here keeps the failure a
            # NEEDS_REVIEW rather than an exception halfway through a run.
            return _unsure(
                f"{rule.rule_id}: a {verdict.value} verdict arrived with no reasoning.", hits
            )

        return Judgement(
            verdict=verdict,
            reasoning=reasoning or f"model verdict for {rule.rule_id}",
            evidence_quote=quote,
            evidence_chunk_id=chunk_id,
            confidence=confidence,
            hits=hits,
        )

    def check(self, rule: PolicyRule, document: str) -> Verdict:
        """The `Checker` protocol (eval/runner.py) — verdict only, for scoring."""
        return self.judge(rule, document).verdict


def outline(index: DocumentIndex) -> tuple[str, ...]:
    """Every section of the document, in order, deduplicated.

    This is the document's table of contents, and it is what lets the judge distinguish a section
    that was not retrieved from one that does not exist."""
    seen: dict[str, None] = {}
    for chunk in index.chunks.values():
        if chunk.heading_path:
            seen.setdefault(chunk.heading_path, None)
    return tuple(seen)


def _resolve_chunk_id(
    reported: object, quote: str | None, hits: tuple[Hit, ...]
) -> str | None:
    """Work out which excerpt the quote came from, tolerantly but never by invention.

    Two passes, in this order:

      1. Believe the model if what it reported names a real excerpt. Parsing is lenient about FORM
         because the first live run answered `"[c020], [c023], [c021]"` — bracketed, and three of
         them. The information was there and a strict equality check threw it away; the locator is
         half the value of a finding, so it is worth reading what the model meant.

      2. Otherwise LOCATE the quote. Whichever excerpt actually contains it is the honest answer,
         and it beats the model's own bookkeeping — the model is good at judging text and merely
         adequate at remembering which box it came from.

    Returns None when neither works. A locator that does not resolve is worse than no locator: it
    looks checkable and is not.
    """
    known = {hit.chunk.chunk_id: hit for hit in hits}
    if isinstance(reported, str):
        for candidate in re.findall(r"c\d+", reported):
            if candidate in known:
                return candidate
    if quote:
        needle = " ".join(quote.split())[:80]
        for hit in hits:
            if needle and needle in " ".join(hit.chunk.body.split()):
                return hit.chunk.chunk_id
    return None


def _unfence(raw: str) -> str:
    """Strip a ```json fence. `response_format=json_object` is advisory on several providers, and
    json.loads then fails at character 0 on the backtick."""
    text = raw.strip()
    if not text.startswith("```"):
        return text
    body = text.split("\n", 1)[1] if "\n" in text else ""
    return body.rsplit("```", 1)[0].strip()
