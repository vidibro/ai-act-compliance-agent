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
from aiact.schemas.classification import ClassificationResult
from aiact.schemas.enums import RiskClass
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer, Question

_ACT_DATE = date(2024, 7, 12)

NODE_ID = "provider_reallocation"
DEPLOYER_NODE_ID = "deployer_type"

QUESTIONS: dict[str, Question] = {
    DEPLOYER_NODE_ID: Question(
        DEPLOYER_NODE_ID,
        LegalSource(
            instrument="Regulation (EU) 2024/1689",
            article=27,
            paragraph=1,
            act_version_date=_ACT_DATE,
        ),
        # A fact about the DEPLOYING ORGANISATION, which several deployer duties turn on and no
        # description of a system supplies. Art. 27 is the one modelled today; Art. 49(3) narrows
        # deployer registration the same way.
        #
        # NARROW AND FACTUAL, deliberately. The model is not asked "does Art. 27 apply?" — that is
        # a legal conclusion the code draws, and it has a second limb (Annex III(5)(b)/(c)) this
        # question knows nothing about. It is asked what kind of organisation the document says
        # operates the system, which is a fact the document either states or does not.
        "What kind of organisation does this description say DEPLOYS the system — that is, uses it "
        "under its own authority? Answer about the deployer, not about whoever built or sells the "
        "system.\n"
        "- public_body: a body governed by public law — a public authority or agency, or an entity "
        "established to meet needs in the general interest and controlled or financed by the "
        "state. A ministry, a municipality, a public hospital, a state school, a court.\n"
        "- public_service_provider: a PRIVATE entity providing public services — education, "
        "healthcare, social services, social housing, administration of justice. Private in form, "
        "public in function.\n"
        "- neither: a private organisation providing no public service. A commercial employer, a "
        "recruitment agency, a bank, a retailer. Answer this only where the description "
        "POSITIVELY establishes it — that the system is sold to, or operated by, ordinary "
        "commercial customers.\n"
        "- not_stated: THE ORDINARY ANSWER. The description says nothing about who operates the "
        "system or what kind of organisation they are. Most documentation describes a system and "
        "not its customers. Give this rather than inferring a commercial deployer from silence: a "
        "document that never mentions the deploying organisation is not a document about a private "
        "one.\n"
        "Where the description names several kinds of deployer, or a vendor selling into both "
        "public and private sectors, answer the one that brings the widest duties — "
        "public_body over public_service_provider over neither.",
        "deployer_type",
        label="What kind of organisation operates the system?",
    ),
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
        "Does this description show the provider role MOVING under Article 25 — one party placed "
        "this high-risk AI system on the market, and another has since done something to it that "
        "makes it the provider instead? Answer which circumstance, or none.\n"
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
        "Answer none where the description is of an organisation that DEVELOPED this system "
        "itself, or of one that simply uses a system as supplied. Those are the ordinary cases: "
        "the first is already the provider under Art. 3(3) without any help from Art. 25, and the "
        "second is a plain deployer. Art. 25 is about a role CHANGING HANDS, so answer a "
        "circumstance only where the description shows BOTH ENDS — a party that placed the system "
        "on the market, and another party doing one of the four things above to it afterwards.",
        "provider_reallocation",
        label="Has the provider role moved to another party?",
    ),
}

# Art. 3 as well as Art. 25: limb (b) turns on the Art. 3(23) definition of 'substantial
# modification', and Art. 16 is what the reallocation costs — the duty set the new provider takes
# on whole.
_QUESTION_CONTEXT: dict[str, Provisions] = {
    NODE_ID: ((3, 16, 25), ()),
    # Art. 27 itself, and Art. 3 for the definition of 'deployer' at 3(4) — the question turns on
    # who uses the system under their own authority, not on who supplies it.
    DEPLOYER_NODE_ID: ((3, 27), ()),
}

# What the DESCRIPTION had to state, phrased for the person who has to go and write it — the same
# contract the cascade's `_WHAT_THE_NODE_NEEDED` holds, so an abstention here can name the missing
# fact rather than reporting that a question went unanswered.
WHAT_THE_NODE_NEEDED = {
    NODE_ID: (
        "who placed this system on the market, and what any later party does to it — rebadge it, "
        "change it beyond what its supplier assessed, aim it at a new purpose, or ship it inside a "
        "product of their own"
    ),
    DEPLOYER_NODE_ID: (
        "what kind of organisation operates the system — a public authority, a private entity "
        "providing a public service, or an ordinary commercial one"
    ),
}


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


def ask_deployer_type(
    brain: Brain,
    document: str,
    classification: ClassificationResult,
    questions: dict[str, Question] | None = None,
) -> Answer | None:
    """What kind of organisation deploys the system, asked where a deployer duty turns on it.

    Put for a HIGH-RISK system in an ANNEX III area. Art. 6(1) systems are outside Art. 27(1),
    which opens on "a high-risk AI system referred to in Article 6(2)", and no lower tier carries a
    deployer duty narrowed this way. The Annex III point 2 exclusion is NOT applied here: it is the
    rule's business which obligations the answer bears on, and the fact is worth recording for the
    reader whatever Art. 27 does with it.

    The answer NEVER withholds an obligation. Art. 27 is selected and listed under the deployer
    whatever comes back; this only lets the report say which side of the condition the document
    falls on, instead of restating the condition and ignoring a document that answers it."""
    if classification.overall_risk_class is not RiskClass.HIGH_RISK:
        return None
    if not any(uc.annex_iii_area is not None for uc in classification.use_cases):
        return None
    asked = questions if questions is not None else QUESTIONS
    return brain.decide(asked[DEPLOYER_NODE_ID], document)


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
