"""The judge: decide whether a document satisfies ONE obligation, from retrieved evidence.

Decides PASS / GAP / INADEQUATE for one obligation. The GAP-vs-INADEQUATE distinction is the
capability the project is built around: word matching cannot tell "we ensure human oversight" from
three paragraphs of actual oversight measures.

Shape, mirroring `graph/llm_brain.py`: one narrow question, one small structured answer, parsed and
constrained. The model is asked ONLY "does this excerpt satisfy this requirement?" — never which
rules apply, never the risk class, never what to do about it. Rule selection is data
(`applies_to_risk_class`, `document_verifiable`), and the verdict vocabulary is a fixed enum.

Four things this file refuses to do, each learned rather than assumed:

  - **Treat retrieval rank as evidence.** A vector search always returns k results; there is no
    "nothing found". The top hit in a document that says nothing about Art. 14 is still the top hit,
    with a confident-looking rank. So the excerpts arrive labelled as SEARCH RESULTS that may be
    irrelevant, and the model is told to say so.

  - **Trust proximity.** A hollow restatement of an obligation resembles that obligation more
    closely than a page of specifics does, so similarity is anti-correlated with compliance on
    exactly the class that matters. The prompt says so outright.

  - **Guess when the evidence is thin.** An unreadable or unsure answer becomes NEEDS_REVIEW. For a
    compliance tool a false PASS is the most expensive error available: it tells a provider they are
    covered when they are not.

  - **Publish a quote it cannot find.** The `evidence_quote` is checked against the document
    (`llm/quotes.py`) and dropped when it is not there. A paraphrase presented as a citation sends
    a reviewer looking for text that does not exist. The VERDICT survives — it was reached from
    real excerpts, and dev measurement found bad quotes to be citation-formatting slips on correct
    answers rather than a symptom of a model that was not reading.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from typing import Any

from aiact.config import get_settings
from aiact.gap.criteria import aggregate_confidence, aggregate_reasoning, settle
from aiact.llm import DATA_NOT_INSTRUCTIONS, fence, flatten, new_marker, unfence, verbatim
from aiact.providers import ProviderProfile, gateway_kwargs, profile_for
from aiact.retrieval.store import DocumentIndex, Hit, document_id
from aiact.schemas.enums import CheckType, Verdict
from aiact.schemas.norm import ConditionClause, LogicalExpression
from aiact.schemas.policy import PolicyRule, RuleCriterion
from aiact.schemas.question import Confidence, clip_reasoning
from aiact.schemas.report import CriterionFinding
from aiact.tools.evidence import DEFAULT_K, find_evidence
from aiact.tools.references import Reference, resolve_all
from aiact.tracing import current_metadata
from aiact.usage import Usage

_EVIDENCE_MAX_LENGTH = 300

# Transient API failures are retried, with backoff, by LiteLLM. A full eval run is 133 calls, so a
# 429 or gateway 5xx along the way is likely, and one failure would otherwise lose the whole run.
#
# Exhausted retries PROPAGATE rather than degrading into NEEDS_REVIEW: an infrastructure failure
# entering the scorecard as an abstention would corrupt the number silently.
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
    # GAP vs INADEQUATE is the distinction the project is measured on, so the boundary is stated as
    # a decidable test rather than a description.
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
    # Keyed to the ACTION the finding implies, not to how much text is present: phrased any other
    # way, models hedge every absence into "inadequate" and almost nothing is ever a gap.
    "\nThe test between them is what the provider must DO next:\n"
    '- "gap" means WRITE THIS — the content does not exist anywhere in the document.\n'
    '- "inadequate" means STRENGTHEN THIS — the content exists and falls short.\n'
    '\nSo "Our human oversight measures are appropriate to the risk" is inadequate: it is about '
    'oversight, it exists, and it needs strengthening. "We are proud signatories of three AI '
    'ethics charters" is a gap: it is not about oversight at all.\n'
    "\nCross-references are resolved for you and reported as facts. If a reference is marked DOES "
    'NOT EXIST, it is a pointer to nothing: "the oversight measures are described in §7" with no '
    "§7 is a GAP, and the work to be done is writing that section from scratch. If it is marked "
    "EXISTS, the pointer is legitimate drafting — the content is in the document even when it is "
    "not among your excerpts, and you must not hold that against the provider. Do not second-guess "
    "either marking from the excerpts alone."
    "\n\n" + DATA_NOT_INSTRUCTIONS
)

# What "satisfying" means per check type. An obligation to DESCRIBE a capability and one to REPORT
# FIGURES fail differently; a single rubric would either excuse missing numbers or demand depth the
# article never asks for.
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
        "This is a METRICS check: concrete figures must be present, AND they must measure the "
        "property this article asks about. Figures that quantify something else — a fairness or "
        "selection-rate ratio where the article asks for accuracy — are not evidence for this "
        "obligation, however precise they look. Ask what each number MEASURES before crediting it. "
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

    criteria: tuple[CriterionFinding, ...] = ()
    """One verdict per criterion, for a rule that declares criteria; `verdict` is then their
    aggregate, computed in code. Empty for a rule judged as one obligation."""

    prompt: str = ""
    """The COMPLETE user turn this verdict came from — enacted text, rubric, document outline,
    resolved cross-references and excerpts, exactly as sent.

    The same rationale as `hits`, extended to the whole input. `hits` records the excerpts alone;
    anything grading this verdict against what the judge was shown needs all of it, including the
    cross-reference facts the judge is TOLD rather than asked to infer. Recorded here so no caller
    has to rebuild it, which would go stale the moment `_user_content` changes.

    In memory only. `Finding` is what leaves this process, and it does not carry this — a provider's
    confidential technical file has no business being copied into a report twice."""


def _unsure(why: str, hits: tuple[Hit, ...] = (), prompt: str = "") -> Judgement:
    """No usable verdict -> NEEDS_REVIEW at low confidence.

    Never GAP. An unreadable reply says nothing about the provider's documentation, and defaulting
    to a finding would manufacture accusations out of our own failures.
    """
    return Judgement(
        verdict=Verdict.NEEDS_REVIEW,
        reasoning=clip_reasoning(why),
        evidence_quote=None,
        evidence_chunk_id=None,
        confidence="low",
        hits=hits,
        prompt=prompt,
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
        reference_content: bool = True,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.profile = profile or profile_for(self.model, effort or settings.effort_for("judge"))
        self.k = k
        # Whether a resolved cross-reference brings its section's text along, or only the fact that
        # it exists. Existence settles GAP; the content is what lets "metrics are in §8" reach PASS.
        self.reference_content = reference_content
        self.usage = Usage()
        # One index per document: every rule asked of the same file reuses it rather than
        # re-embedding. The lock matters because the eval judges concurrently.
        self._indexes: dict[str, DocumentIndex] = {}
        self._index_lock = threading.Lock()

    def index_for(self, document: str) -> DocumentIndex:
        doc_id = document_id(document)
        with self._index_lock:
            if doc_id not in self._indexes:
                self._indexes[doc_id] = DocumentIndex.build(document)
            return self._indexes[doc_id]

    def _user_content(
        self,
        rule: PolicyRule,
        hits: tuple[Hit, ...],
        outline: tuple[str, ...] = (),
        references: tuple[Reference, ...] = (),
    ) -> Any:
        """Build the user turn, stable half first (see llm_brain._user_content for why).

        The obligation — enacted text, expected evidence, rubric — is identical across every
        document judged against this rule, so it is the cacheable prefix. The excerpts are the
        volatile suffix.
        """
        rubric = _RUBRIC.get(rule.check_type, _RUBRIC[CheckType.SUBSTANCE])
        # Labelled NON-BINDING and kept in its own block, never folded into the enacted text above.
        # The Commission's reading of a provision is not the provision: a judge shown the two as one
        # passage would weigh an interpretation as law, and the finding could not say which it
        # rested on. Part of the stable half because it is per-rule, so it caches with the rest.
        guidance = ""
        if rule.guidance_context:
            guidance = (
                f"NON-BINDING guidance from the European Commission on this provision. It is the "
                f"Commission's interpretation, NOT enacted text — the Court of Justice of the EU "
                f"is the only authoritative interpreter. Use it to read the obligation above; "
                f"never treat it as adding a requirement the Article does not contain:\n"
                f'"""\n{rule.guidance_context}\n"""\n\n'
            )
        # THE ANNEX THE ARTICLE POINTS AT, where it cites one. Art. 11(1) requires documentation
        # containing "at a minimum, the elements set out in Annex IV" — the Article names a list and
        # the Annex is the list, so a completeness verdict reached without it rests on whatever the
        # judge remembers Annex IV to contain. Enacted text like the requirement, and kept in its
        # own block only so the citation stays the Article the rule cites.
        annex = ""
        if rule.annex_context:
            annex = (
                f"Annex {rule.source.annex}, referred to by that provision (verbatim, enacted "
                f"text). Where the Article requires the elements it sets out, this Annex IS the "
                f"list to judge completeness against:\n"
                f'"""\n{rule.annex_context}\n"""\n\n'
            )
        # THE PROVISIONS THAT QUALIFY THE ONE UNDER REVIEW. A duty and the condition on how it must
        # be discharged are often written in different paragraphs — Art. 50(1) requires the
        # disclosure, Art. 50(5) requires it to be clear and given at first interaction — and a
        # judge shown only the first passes a disclosure the second rules out. Labelled with their
        # own addresses so the verdict still belongs to the paragraph the rule cites.
        qualifiers = ""
        if rule.qualifier_context:
            qualifiers = (
                f"Provisions that QUALIFY the obligation above (verbatim, enacted text). They do "
                f"not add a separate duty — they condition how this one must be discharged, and "
                f"documentation that fails them fails this obligation:\n"
                f'"""\n{rule.qualifier_context}\n"""\n\n'
            )
        stable = (
            f"Obligation under review: {rule.rule_id} (Article {rule.source.article}"
            f"{f'({rule.source.paragraph})' if rule.source.paragraph else ''}).\n\n"
            f"Enacted text you must judge against (verbatim):\n"
            f'"""\n{rule.requirement}\n"""\n\n'
            f"{qualifiers}"
            f"{annex}"
            f"{guidance}"
            f"What documentation satisfying this looks like:\n"
            f'"""\n{rule.evidence_expected}\n"""\n\n'
            f"{rubric}\n\n"
            f"{_criteria_block(rule)}"
        )

        excerpts = "\n\n".join(
            f"[{hit.chunk.chunk_id}] (section: {hit.chunk.heading_path})\n{hit.chunk.body}"
            for hit in hits
        )
        # The document's full section list, so the judge can tell "not retrieved" from "not present"
        # instead of hedging every absence into INADEQUATE.
        contents = "\n".join(f"- {section}" for section in outline)

        marker = new_marker(excerpts, contents, *(c.body for r in references for c in r.chunks))
        followed = ""
        if references:
            lines = []
            for ref in references:
                if ref.resolves:
                    lines.append(f"- {ref.token} EXISTS -> {ref.section}")
                else:
                    lines.append(f"- {ref.token} DOES NOT EXIST in this document")
            # A referenced section the excerpts did not already include. Capped at two: enough to
            # settle a pointer without pulling the document back in.
            seen = {hit.chunk.heading_path for hit in hits}
            extra = (
                [r for r in references if r.resolves and r.chunks and r.section not in seen][:2]
                if self.reference_content
                else []
            )
            bodies = "".join(
                f"\n\nContent of {r.token} ({r.section}):\n" + "\n\n".join(c.body for c in r.chunks)
                for r in extra
            )
            followed = (
                "Cross-references appearing in the excerpts, resolved against the document "
                "for you — these are FACTS, not inferences:\n"
                + fence("REFERENCES", "\n".join(lines) + bodies, marker)
                + "\n\n"
            )

        task = (
            f"Complete list of sections in this document — nothing else exists in it:\n"
            f"{fence('SECTIONS', contents, marker)}\n\n"
            f"{followed}"
            f"The excerpts below are what a search for THIS obligation returned across ALL of "
            f"those sections. So if the substance were anywhere in the document, it would be here: "
            f"treat its absence from the excerpts as absence from the document. And if an excerpt "
            f"points at a section that is NOT in the list above, that section does not exist — a "
            f"pointer to nothing is not evidence that the obligation is met.\n\n"
            f"Excerpts retrieved from the provider's documentation. These are SEARCH RESULTS, "
            f"one search per duty this obligation names, NOT a list ordered by relevance — the "
            f"search always returns this many, so "
            f"some or all may be unrelated to the obligation. Judge what they say; do not assume "
            f"an excerpt is responsive because it was returned. In particular, a passage that "
            f"merely restates the obligation in the obligation's own words scores HIGHLY in this "
            f"search while containing no substance at all — rank is not evidence.\n"
            f"{fence('EXCERPTS', excerpts, marker)}\n\n"
        )
        fields = (
            f'"verdict" (one of "pass", "gap", "inadequate", '
            f'"{UNSURE}"), "reasoning" (one sentence naming what is present or missing), '
            # One contiguous span from ONE excerpt: a quote stitched across excerpts reads as
            # verbatim evidence while matching nothing in the document.
            f'"evidence_quote" (ONE contiguous span copied exactly from a SINGLE excerpt, under '
            f"{_EVIDENCE_MAX_LENGTH} characters — not a stitched-together summary, never a quote "
            f"of the enacted text, and null if nothing in the excerpts is responsive), "
            f'"evidence_chunk_id" (the id of that one excerpt, bare, like c012 — not a list and '
            f'not in brackets), "confidence" (one of "high", "medium", "low")'
        )
        if _judged(rule):
            task += (
                f'Answer as JSON with one key, "criteria": a list with exactly one object per '
                f'criterion listed above, each with keys "norm_id" (copied exactly), {fields}.'
            )
        else:
            task += f"Answer as JSON with keys: {fields}."
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
                reasoning=clip_reasoning(
                    f"{rule.rule_id} is a process obligation of the provider organisation, not a "
                    f"property of the technical documentation — confirm it separately."
                ),
                evidence_quote=None,
                evidence_chunk_id=None,
                confidence="high",
            )

        index = self.index_for(document)
        hits = tuple(find_evidence(index, rule, k=self.k))
        # From the EXCERPTS only: the judge can reason about pointers it was shown, not others.
        seen_text = "\n".join(hit.chunk.body for hit in hits)
        refs = tuple(resolve_all(index, seen_text, document))
        user_content = self._user_content(rule, hits, outline(index), refs)
        # Kept as sent, not rebuilt later: see Judgement.prompt.
        prompt = flatten(user_content)
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
            **gateway_kwargs(),
            **self.profile.completion_kwargs,
        )
        self.usage.record(response, cache_marked=isinstance(user_content, list))

        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            return _unsure(f"{rule.rule_id}: the model returned an empty completion.", hits, prompt)
        try:
            data = json.loads(unfence(raw))
        except json.JSONDecodeError as exc:
            return _unsure(
                f"{rule.rule_id}: the model's reply was not valid JSON: {exc}.", hits, prompt
            )
        if not isinstance(data, dict):
            return _unsure(
                f"{rule.rule_id}: expected a JSON object, got {type(data).__name__}.", hits, prompt
            )

        if _judged(rule):
            return self._to_criteria_judgement(rule, data, hits, document, prompt)
        return self._to_judgement(rule, data, hits, document, prompt)

    def _to_criteria_judgement(
        self,
        rule: PolicyRule,
        data: dict[str, Any],
        hits: tuple[Hit, ...],
        document: str,
        prompt: str = "",
    ) -> Judgement:
        """Parse one verdict per criterion; the rule verdict is computed, never read.

        Each entry goes through the same parsing as a whole-rule verdict, so an unreadable entry is
        NEEDS_REVIEW for that criterion alone. An entry naming no declared criterion, or one named
        twice, is discarded rather than trusted: the settled list is built from the rule."""
        declared = {criterion.norm_id for criterion in rule.criteria if criterion.mandatory}
        entries = data.get("criteria")
        reported: dict[str, CriterionFinding] = {}
        seen: set[str] = set()
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            norm_id = str(entry.get("norm_id", "")).strip()
            if norm_id not in declared:
                continue
            if norm_id in seen:
                reported.pop(norm_id, None)
                continue
            seen.add(norm_id)
            one = self._to_judgement(rule, entry, hits, document, prompt, label=norm_id)
            reported[norm_id] = CriterionFinding(
                norm_id=norm_id,
                mandatory=True,
                verdict=one.verdict,
                reasoning=one.reasoning,
                evidence_quote=one.evidence_quote,
                evidence_chunk_id=one.evidence_chunk_id,
                confidence=one.confidence,
            )
        verdict, criteria = settle(rule, Verdict.NEEDS_REVIEW, reported.values())
        # The rule-level quote points at an open criterion first: that is what a reader must fix.
        quoted = [c for c in criteria if c.evidence_quote]
        cited = next((c for c in quoted if c.verdict is not Verdict.PASS), None) or next(
            iter(quoted), None
        )
        return Judgement(
            verdict=verdict,
            reasoning=aggregate_reasoning(rule, criteria),
            evidence_quote=cited.evidence_quote if cited else None,
            evidence_chunk_id=cited.evidence_chunk_id if cited else None,
            confidence=aggregate_confidence(criteria),
            hits=hits,
            criteria=tuple(criteria),
            prompt=prompt,
        )

    def _to_judgement(
        self,
        rule: PolicyRule,
        data: dict[str, Any],
        hits: tuple[Hit, ...],
        document: str,
        prompt: str = "",
        label: str | None = None,
    ) -> Judgement:
        label = label or rule.rule_id
        token = str(data.get("verdict", "")).strip().lower()
        if token == UNSURE:
            return _unsure(
                f"{label}: the excerpts did not settle the question — "
                f"{str(data.get('reasoning', '')).strip() or 'no reason given'}.",
                hits,
            )
        verdict = _VERDICTS.get(token)
        if verdict is None:
            return _unsure(f"{label}: {token!r} is not a verdict.", hits)

        confidence: Confidence = data.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"

        # Checked against the whole document, not just the excerpts: a legitimate quote can come
        # from a cross-referenced section pulled in beside them, and either way the claim being
        # verified is that this text is in the provider's documentation.
        quote = verbatim(data.get("evidence_quote"), document)
        if quote is not None:
            quote = quote[:_EVIDENCE_MAX_LENGTH]
        chunk_id = _resolve_chunk_id(data.get("evidence_chunk_id"), quote, hits)

        reasoning = str(data.get("reasoning", "")).strip()
        if verdict in (Verdict.GAP, Verdict.INADEQUATE) and not reasoning:
            # Finding's own validator refuses this too; catching it here keeps the failure a
            # NEEDS_REVIEW rather than an exception halfway through a run.
            return _unsure(
                f"{label}: a {verdict.value} verdict arrived with no reasoning.", hits
            )

        return Judgement(
            verdict=verdict,
            reasoning=clip_reasoning(reasoning or f"model verdict for {label}"),
            evidence_quote=quote,
            evidence_chunk_id=chunk_id,
            confidence=confidence,
            hits=hits,
            prompt=prompt,
        )

    def check(self, rule: PolicyRule, document: str) -> Verdict:
        """The `Checker` protocol (eval/runner.py) — verdict only, for scoring."""
        return self.judge(rule, document).verdict


def _judged(rule: PolicyRule) -> bool:
    """Whether this rule is judged criterion by criterion."""
    return any(criterion.mandatory for criterion in rule.criteria)


def _condition_text(condition: ConditionClause | LogicalExpression) -> str:
    if isinstance(condition, ConditionClause):
        return condition.text
    joiner = " AND " if condition.operator == "all_of" else " OR "
    return "(" + joiner.join(_condition_text(item) for item in condition.operands) + ")"


def _criterion_lines(criterion: RuleCriterion) -> str:
    lines = [
        f"- {criterion.norm_id}",
        f"    duty-holder: {', '.join(criterion.actors)}",
        f"    must: {criterion.action}",
        f'    enacted words: "{criterion.norm_text}"',
    ]
    if criterion.conditions:
        lines.append(f"    only where: {_condition_text(criterion.conditions)}")
    if criterion.exceptions:
        lines.append(f"    except: {_condition_text(criterion.exceptions)}")
    lines += [f"    must include: {m}" for m in criterion.mandatory_content]
    return "\n".join(lines)


def _criteria_block(rule: PolicyRule) -> str:
    """The criteria the verdict is split into, each materialised from its canonical norm.

    Listed so the model rules on each one against its own evidence. Evidence for one criterion is
    never evidence for another: a document that covers four of five AI-specific attacks has said
    nothing about the fifth."""
    judged = [criterion for criterion in rule.criteria if criterion.mandatory]
    if not judged:
        return ""
    listed = "\n".join(_criterion_lines(criterion) for criterion in judged)
    return (
        f"This obligation is judged as {len(judged)} SEPARATE CRITERIA. Rule on each one on its "
        f"own evidence. A criterion passes only on evidence about THAT criterion — never because "
        f"the section it would sit in exists, and never because a sibling criterion is met. Where "
        f"the documentation itself establishes that a criterion's condition does not hold, that "
        f"statement is its evidence: rule pass and quote it. Silence about the condition is not "
        f"such evidence.\n{listed}\n\n"
    )


def outline(index: DocumentIndex) -> tuple[str, ...]:
    """Every section of the document, in order, deduplicated.

    This is the document's table of contents, and it is what lets the judge distinguish a section
    that was not retrieved from one that does not exist."""
    seen: dict[str, None] = {}
    for chunk in index.chunks.values():
        if chunk.heading_path:
            seen.setdefault(chunk.heading_path, None)
    return tuple(seen)


def _resolve_chunk_id(reported: object, quote: str | None, hits: tuple[Hit, ...]) -> str | None:
    """Work out which excerpt the quote came from, tolerantly but never by invention.

    Two passes, in this order:

      1. Believe a reported id that names a real excerpt. Parsing is lenient about FORM, since
         models answer with brackets and lists (`"[c020], [c023]"`) and a strict equality check
         would throw away a locator that is half the value of a finding.

      2. Otherwise LOCATE the quote: whichever excerpt contains it. Models judge text well and
         track which box it came from only adequately.

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
