"""The retrieval TOOL: given one obligation, pull the passages of a document that might satisfy it.

This is the seam between the ruleset and the vector store. It answers exactly one question —
*"where, if anywhere, does this document address this obligation?"* — and deliberately does not
answer *"is the obligation satisfied?"*. That judgement needs the enacted text, the evidence, and a
model; it lives in the checker, not here.

Keeping the split sharp is what makes the eval's central distinction measurable at all. GAP and
INADEQUATE are both "the evidence is not good enough", and they differ only in WHY: nothing was
found, versus something was found and it is empty. A tool that returned a verdict would have to
collapse them; a tool that returns evidence lets the judge separate them.

Query construction: the query is the rule's `evidence_expected`, not its `requirement`. The
requirement is enacted legislative drafting ("shall be designed and developed in such a way that…");
the documentation is product prose ("panel members can return a case for re-review"). Embedding
legislative register against product register retrieves badly. `evidence_expected` was written to
describe what satisfying documentation LOOKS LIKE, which is the same register as the target — it is
the retrieval hint the spec always intended, finally used for retrieval.

AND IT IS SEVERAL QUERIES, not one. Being the query makes `evidence_expected` decide what the judge
is SHOWN and not only what it is told to check, and one vector for a text naming four duties lands
near whichever of them the text mostly talks about. `queries_for` splits it and `find_evidence`
spends the budget a duty at a time, so the passage answering the fourth duty is retrieved on that
duty's own terms rather than on the text's average.
"""

from __future__ import annotations

import re

from aiact.retrieval.store import DocumentIndex, Hit
from aiact.schemas.policy import PolicyRule

DEFAULT_K = 10
"""How many passages to put in front of the judge.

k is a function of CHUNK SIZE: with a 128-token budget the average chunk is ~330 characters, so ten
passages cover roughly a quarter of a technical file. Too few and the judge sees a section's opening
without the measures that follow it, and correctly calls complete documentation hollow. Shrink the
chunk and this must go up.
"""


def query_for(rule: PolicyRule) -> str:
    """The retrieval query for one obligation.

    See the module docstring for why this is not the `requirement` text."""
    return rule.evidence_expected


# A sentence short enough to be a fragment carries no duty of its own — a list label, an aside, a
# clause the splitter cut at an abbreviation. Below this it is noise as a query and would spend a
# slot on whatever the index happens to sit nearest.
_MIN_QUERY_WORDS = 6

# Sentence end: a full stop, colon or semicolon followed by space. Not a comma, because the Act's
# duties are written as comma-separated limbs of one sentence and splitting there would ask for
# half a requirement.
#
# THE ABBREVIATIONS ARE EXCLUDED BY NAME. Evidence texts cite the Act constantly, and a citation
# carries a full stop in the middle of a clause: splitting at "under Art. 15(4) however strong its
# accuracy figures are" yields a query beginning "15(4) however strong", which names no duty, is
# long enough to survive the word-count filter, and spends a slot. `Art`, `Arts`, `No` and `Reg`
# are the ones the stored Act and the evidence texts use.
_SENTENCE_END = re.compile(r"(?<=[.:;])(?<!\bArt\.)(?<!\bArts\.)(?<!\bNo\.)(?<!\bReg\.)\s+")


def queries_for(rule: PolicyRule) -> list[str]:
    """The query and its facets: the whole evidence text, then each duty it names separately.

    ONE QUERY CANNOT REACH A DUTY THE REST OF THE TEXT OUTVOTES. An evidence text that names
    accuracy, robustness and three classes of AI-specific attack embeds to a point near the
    document's accuracy prose, because that is what most of the text is about; the sentence about
    feedback loops contributes a fraction of the vector and the passage that breaches it can sit
    outside the whole result set. Splitting restores it: that sentence is its own query, and it
    retrieves its own passage on its own terms.

    WHICH MATTERS MOST FOR TEXT THAT BREACHES rather than text that is missing. The query describes
    what compliance looks like, so a passage saying the obligation is not met is far from it by
    construction — and the judge is told to read absence from the excerpts as absence from the
    document. A duty with no facet of its own is a duty whose breach the judge cannot be shown."""
    whole = query_for(rule)
    facets = [
        s.strip()
        for s in _SENTENCE_END.split(" ".join(whole.split()))
        if len(s.split()) >= _MIN_QUERY_WORDS
    ]
    # A single-sentence evidence text splits into one facet that IS the whole text, and a text
    # whose first sentence runs to the end splits into a facet that starts it. Either way the
    # second query embeds where the first already did and buys nothing for the slot it costs.
    return [whole] + [f for f in facets if not whole.startswith(f)]


def find_evidence(index: DocumentIndex, rule: PolicyRule, k: int = DEFAULT_K) -> list[Hit]:
    """Candidate evidence for `rule` in one document, k passages, nearest first.

    Raises for a rule the documentation cannot answer. Art. 17-21, 43, 47-49 and 72-73 are process
    and administrative obligations of the provider ORGANISATION — a quality management system, a
    registration in the EU database, a duty to cooperate. Searching a technical file for them
    returns the k least-unrelated paragraphs, which is exactly how a checker talks itself into
    PASS on an obligation the document was never capable of evidencing. The spec already records
    which rules those are; this refuses to guess where it has no standing to.

    THE BUDGET IS SPENT A FACET AT A TIME, not on one ranking. `queries_for` breaks the evidence
    text into the duties it names, and each of them takes its best unclaimed passage in turn before
    any of them takes a second. A duty the whole-text query cannot reach — because the rest of the
    text outvotes it in the embedding — reaches its own passage here, which is the difference
    between a judge that can see a breach and one that is shown only compliant prose and told to
    treat what it was not shown as absent.

    ROUND-ROBIN AND NOT A MERGED RANKING, because merging by distance reinstates the problem: the
    passage that BREACHES an obligation is semantically far from a query describing compliance, so
    it loses every global comparison and wins only against the other candidates for its own facet.
    The whole text goes first, so a document with nothing to hide is retrieved much as before.
    """
    if not rule.document_verifiable:
        raise ValueError(
            f"{rule.rule_id} is not document-verifiable — it is a process obligation confirmed "
            f"outside the technical documentation. Retrieval would return unrelated passages and "
            f"invite a false PASS. Handle it as 'confirm separately', do not search for it."
        )
    queries = queries_for(rule)
    # EVERY FACET GETS A SLOT, so k is a floor and not a ceiling. A rule naming sixteen duties
    # spends the first ten slots on its first ten facets and the rest never reach the index at
    # all — and those are the later points of a list, which is where an instructions-for-use or
    # data-governance rule keeps the items a file most often omits. Returning six more passages
    # for such a rule costs prompt; not returning them costs the judge the only evidence it would
    # have had for duties it is still asked to rule on.
    budget = max(k, len(queries))
    ranked = [iter(index.search(query, k=budget)) for query in queries]
    taken: dict[str, Hit] = {}
    while ranked and len(taken) < budget:
        for hits in list(ranked):
            hit = next((h for h in hits if h.chunk.chunk_id not in taken), None)
            if hit is None:
                ranked.remove(hits)
                continue
            taken[hit.chunk.chunk_id] = hit
            if len(taken) == budget:
                break
    return list(taken.values())
