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
"""

from __future__ import annotations

from aiact.retrieval.store import DocumentIndex, Hit
from aiact.schemas.policy import PolicyRule

DEFAULT_K = 4
"""How many passages to put in front of the judge.

Not tuned — chosen because the corpus answers most obligations in one or two sections, and a couple
of spare slots let the judge see that the runners-up are unrelated. That last part matters: seeing
weak neighbours is evidence of absence in a way that a single confident-looking top hit is not.
"""


def query_for(rule: PolicyRule) -> str:
    """The retrieval query for one obligation.

    See the module docstring for why this is not the `requirement` text."""
    return rule.evidence_expected


def find_evidence(index: DocumentIndex, rule: PolicyRule, k: int = DEFAULT_K) -> list[Hit]:
    """Candidate evidence for `rule` in one document, nearest first.

    Raises for a rule the documentation cannot answer. Art. 17-21, 43, 47-49 and 72-73 are process
    and administrative obligations of the provider ORGANISATION — a quality management system, a
    registration in the EU database, a duty to cooperate. Searching a technical file for them
    returns the k least-unrelated paragraphs, which is exactly how a checker talks itself into
    PASS on an obligation the document was never capable of evidencing. The spec already records
    which rules those are; this refuses to guess where it has no standing to.
    """
    if not rule.document_verifiable:
        raise ValueError(
            f"{rule.rule_id} is not document-verifiable — it is a process obligation confirmed "
            f"outside the technical documentation. Retrieval would return unrelated passages and "
            f"invite a false PASS. Handle it as 'confirm separately', do not search for it."
        )
    return index.search(query_for(rule), k=k)
