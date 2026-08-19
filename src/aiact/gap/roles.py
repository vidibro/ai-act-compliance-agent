"""Art. 25 — WHO owes the obligations, when the provider's role has changed hands.

This lives in the gap layer rather than in the classification cascade, and the line is worth
stating because the two questions look alike from a distance. Every question the cascade asks
decides what the SYSTEM is, and the answer is a risk class. This one decides who the READER is. It
consumes the tier — Art. 25(1) reallocates the provider of "a high-risk AI system", 25(3) of a
high-risk safety component — and nothing reads it back. So it belongs with the rest of the role
logic, beside `select_rules`, which already runs once per (use case, role).

It is not a rule, and is deliberately not in spec.yaml. The reallocated party owes Art. 16, which
is already modelled rule by rule; a rule here would double-count every provider finding. What this
produces is a statement about WHOSE those findings are.

Asked with the same machinery as the cascade's questions — a Question put to a
Brain, anchored in verbatim law, free to abstain — because that machinery is what
makes the answer citable and auditable. The gap layer's own model is the JUDGE, whose contract is
`judge(rule, document)`; this is not a rule check, so it needs the other kind of asker.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from aiact.anchoring import Provisions, anchor_questions
from aiact.brain import Brain
from aiact.schemas.enums import RiskClass
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer, Question

_ACT_DATE = date(2024, 7, 12)

NODE_ID = "provider_reallocation"

QUESTIONS: dict[str, Question] = {
    NODE_ID: Question(
        NODE_ID,
        LegalSource(
            instrument="Regulation (EU) 2024/1689",
            article=25,
            act_version_date=_ACT_DATE,
        ),
        # THE DEFAULT IS THAT NOTHING HAPPENED, and unlike the cascade's scope questions that
        # default is the safe one: answering `none` leaves the report as it already is, with both
        # roles' obligations listed. Inventing a reallocation would tell a deployer they owe
        # Chapter III.
        #
        # Limb (b) is the one that needs an anchor rather than a judgement, so the Art. 3(23)
        # definition is quoted into the question. Without it "substantial" reads as "significant",
        # and every configured deployment becomes a modification.
        "Has the reader of this document BECOME the provider of this high-risk AI system under "
        "Article 25 — that is, did someone else place it on the market? Answer which "
        "circumstance, or none.\n"
        "- name_or_trademark (25(1)(a)): they put their own name or trademark on a high-risk AI "
        "system already placed on the market or put into service by someone else — white-labelling "
        "or rebadging a vendor's tool.\n"
        "- substantial_modification (25(1)(b)): they make a SUBSTANTIAL MODIFICATION to a "
        "high-risk system already on the market, and it remains high-risk. Art. 3(23) defines "
        "that narrowly: a change NOT foreseen or planned in the provider's initial conformity "
        "assessment, which affects compliance with Chapter III Section 2 or modifies the intended "
        "purpose that was assessed. Configuring a system, tuning it within its documented "
        "envelope, or taking the vendor's updates is NOT this.\n"
        "- intended_purpose_change (25(1)(c)): they change the intended purpose of a system that "
        "was NOT classified as high-risk — including a general-purpose AI system — so that it "
        "becomes high-risk. Taking a general text or document tool and pointing it at a listed "
        "use is this limb.\n"
        "- product_manufacturer (25(3)): the system is a safety component of a product they "
        "manufacture, and it goes to market with that product under their name or trademark, or "
        "is put into service under it after the product shipped.\n"
        "Answer none if the document describes an organisation that DEVELOPED this system itself, "
        "or one that simply uses a system as supplied. Those are the ordinary cases: the first is "
        "already the provider under Art. 3(3) without any help from Art. 25, and the second is a "
        "plain deployer. Art. 25 is about a role CHANGING HANDS, so answer a circumstance only "
        "where the document shows both parties — someone who placed the system on the market, and "
        "the reader doing one of the four things above to it afterwards.",
        "provider_reallocation",
        label="Have you become the provider of someone else's system?",
    ),
}

# Art. 3 as well as Art. 25: limb (b) turns on the Art. 3(23) definition of 'substantial
# modification', and Art. 16 is what the reallocation costs — the duty set the new provider takes
# on whole.
_QUESTION_CONTEXT: dict[str, Provisions] = {NODE_ID: ((3, 16, 25), ())}

# What the DESCRIPTION had to state, phrased for the person who has to go and write it — the same
# contract the cascade's `_WHAT_THE_NODE_NEEDED` holds, so an abstention here can name the missing
# fact rather than reporting that a question went unanswered.
WHAT_THE_NODE_NEEDED = (
    "who placed this system on the market, and what the organisation reading this document does "
    "to it — rebadge it, change it beyond what its supplier assessed, aim it at a new purpose, or "
    "ship it inside their own product"
)


def load_questions(
    version: str | date | None = None,
    articles_root: str | Path | None = None,
    annexes_root: str | Path | None = None,
) -> dict[str, Question]:
    """QUESTIONS with `context` filled from the verbatim article store.

    Same split as the cascade's: the bare QUESTIONS constant stays context-free so a deterministic
    brain needs no file IO, and any brain that actually reads the law uses this."""
    return anchor_questions(
        QUESTIONS,
        _QUESTION_CONTEXT,
        version=version,
        articles_root=articles_root,
        annexes_root=annexes_root,
    )


def ask(
    brain: Brain,
    document: str,
    risk_class: RiskClass,
    questions: dict[str, Question] | None = None,
) -> Answer | None:
    """The Art. 25 question, put only where the tier makes it answerable.

    The gate lives HERE rather than in the graph node, because it is a legal condition rather than
    a routing choice and two callers depend on it — the gap graph, and the eval harness that
    measures this answer. Every limb of Art. 25(1) speaks of "a high-risk AI system" and 25(3) of a
    high-risk safety component, so nothing else has a provider for this Article to reallocate.
    Asking anyway could only produce a finding the Article cannot support.

    `None` means the question was NOT PUT, which is not the same as an answer of "nobody was
    reallocated" — the caller must keep those apart, or a system Art. 25 was never asked about
    reads as one it cleared."""
    if risk_class is not RiskClass.HIGH_RISK:
        return None
    asked = questions if questions is not None else QUESTIONS
    return brain.decide(asked[NODE_ID], document)
