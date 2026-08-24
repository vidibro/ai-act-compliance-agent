"""The classification cascade as a LangGraph — reproduces the EC AI Act Compliance Checker flow.

Order (Commission's, with our deliberate split of profiling before derogation):

    is_ai ─not AI─────────────────────────────────────────────► minimal
      │ AI
    territorial ─Art.2(1) reaches it nowhere───────────────────► OUT_OF_SCOPE
      │ a limb applies, or territory unaddressed
    scope ─Art.2(3),(4),(6),(8),(10)───────────────────────────► OUT_OF_SCOPE
      │ none ── or Art.2(12), which falls through (see below)
    gpai_model ─Art.3(63) a general-purpose MODEL, placed or not► GPAI_MODEL (Chapter V handover)
      │ an AI system — including one built ON such a model
    prohibited ─Art.5 yes──────────────────────────────────────► PROHIBITED
      │ no
    annex_i ─no Annex I product─┐                     Art. 6(1), door ONE
      │ safety component of one │
    third_party_assessment ─yes─┼─────────────────────────────► HIGH_RISK
      │ no (self-assessed)      │
      └──────────────────────►──┘
                                ▼
    annex_iii ─not in Annex III───────────────────────────────► minimal
      │ in Annex III                                  Art. 6(2), door TWO
    profiling ─Art.6(3) yes────────────────────────────────────► HIGH_RISK   (carve-back)
      │ no
    derogation ─no condition (a)-(d)───────────────────────────► HIGH_RISK
      │ a condition is met
    significant_risk ─poses one─────────────────────────────────► HIGH_RISK
                      └─ does not ──────────────────────────────► NOT_HIGH_RISK

Art. 2 comes FIRST because it is prior to everything else: a system the Regulation does not govern
is not a prohibited practice and has no risk tier. Asked after `is_ai` only because Art. 2 speaks
throughout of AI systems. It is TWO questions, in the order the Article puts them. Art. 2(1) is the
POSITIVE limb — does the Regulation reach this actor at all — and paragraphs (3)-(12) are exclusions
carved OUT of a Regulation already assumed to apply, so `territorial` is asked before `scope`. A
system Art. 2(1) never reached is not "excluded"; it was outside from the start, and its citation
says 2(1) rather than borrowing an exclusion's paragraph.

Both scope nodes clear a system only on an EXPLICIT finding. `territorial` needs `outside_union`
and `scope` needs a named paragraph; an unanswered or unrecognised value leaves the Regulation
applying in both. Over-inclusion is recoverable, a silent clearance is not — and territory is where
that matters most, because almost no document mentions it and `not_addressed` is the ordinary
answer.

OUT_OF_SCOPE is not a low tier — `minimal` means governed and owing Art. 4, this means owing
nothing at all — so `select_rules()` returns no obligations for it.

Art. 2(12), free and open-source, is the one exclusion that cannot be settled there. It is lifted
where the release is high-risk, an Art. 5 practice, or subject to Art. 50 — the very questions the
rest of the cascade answers. So that answer falls THROUGH and `decide_risk_class` resolves it at
the end, against real answers rather than a second copy of Arts. 5 and 50 judged by the scope node.

TWO independent doors into high-risk. Art. 6(1) is a CONJUNCTION — the system is a safety
component of (or is) a product under Annex I, AND that product needs third-party conformity
assessment. Failing the second condition is not an exit: a self-assessed product can still be
high-risk under Annex III, so the cascade falls through rather than concluding. The Art. 6(3)
derogations never reach a 6(1) system — they derogate from paragraph 2 alone.

Art. 6(3) is a CONJUNCTION TOO, and gets the same treatment: the paragraph exempts a system where
it "does not pose a significant risk of harm ... including by not materially influencing the
outcome of decision making", and the second subparagraph then adds that this "shall apply where any
of the following conditions is fulfilled". So `derogation` decides (a)-(d) and `significant_risk`
decides the chapeau, one limb each. Asked in that order because it is the order the text builds
them in — (a)-(d) is the gate that lets the first subparagraph operate at all — and because a
system with no condition never needs the second question.

Art. 2(2) then limits what a 6(1) system OWES: for products under Annex I Section B (vehicles,
aviation, rail, marine) only Art. 6(1), 102-109 and 112 apply, so Chapter III does not. That is
carried on AnnexIProduct.chapter_iii_applies and consumed when obligations are selected.

Art. 2(8) FALLS THROUGH TOO, for a different reason from Art. 2(12): it is temporal. A model in
development is excluded today and governed the day it ships, so exiting at `scope` would report
"nothing owed" to the one reader still able to prepare. It falls through exactly one node — the
Art. 3(63) question, which settles WHAT is being built — and then concludes either way.

A GENERAL-PURPOSE AI MODEL leaves the cascade entirely. Art. 6 does not classify it — Chapter V
does — so `GPAI_MODEL` is a handover rather than a tier, and it is asked after `scope` because
Arts. 2(6) and 2(8) exclude models as well as systems in terms. The line that matters is Art. 3(66):
a SYSTEM built on a general-purpose model is an ordinary AI system and classifies normally, so the
question tests generality rather than size. Routing out everything running on a foundation model
would exempt exactly the products the tier logic exists for.

Art. 50 transparency is NOT on this path. It is a separate axis — a minimal-risk generator and a
high-risk chatbot can both owe it — so `assemble` asks it unconditionally and reports it beside the
risk class. It never routes anything and never affects the tier.

Art. 25 is NOT HERE, and the line it sits on the far side of is what this cascade is for. Every
question above decides what the SYSTEM is, and the answer is a risk class. Art. 25 decides who the
READER is — whether they have become the provider of a system someone else placed on the market —
which changes whose obligations are owed and nothing about the tier. So it lives in the gap layer,
with the rest of the role logic (gap/roles.py).

Art. 50 stays, and the difference is worth stating because the two look alike from a distance:
transparency does not set a tier either, but the tier READS it. Art. 2(12) lifts the free and
open-source exclusion where the release "falls under Art. 50", so the same permissive licence lands
on OUT_OF_SCOPE or on `minimal` depending on this answer. A question the tier consumes belongs to
the cascade whether or not it has a branch of its own; Art. 25 consumes the tier instead, and
nothing reads it back.

Any node answering with LOW confidence routes straight to `assemble`, which yields NEEDS_REVIEW —
abstaining beats guessing. The flip lives in this routing: the SAME sub-answers, with profiling
true vs false, land on high_risk vs not_high_risk. The graph is brain-agnostic (see brain.py), so
this logic is proven deterministically before any LLM is involved.

`assemble` builds the real UseCaseClassification, whose validator re-checks the Art. 6(3)
carve-back — so a mis-wired route RAISES rather than emitting a wrong verdict.

SCOPE: ONE use case per run. GraphState carries a single description, so ClassificationResult
always comes back with exactly one entry in `use_cases`. Art. 6 classifies per intended purpose,
and one product can hold several classifications at once (a CV tool that parses, scores, AND
drafts job ads is three use cases in three different tiers) — but splitting a document into its
intended purposes is a separate step ABOVE this graph, deferred to M7 (see docs/ROADMAP.md). The
cascade needs no change to support it: it is already per-use-case, and would simply be run N times.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from aiact.anchoring import Provisions, anchor_questions
from aiact.brain import Brain
from aiact.config import get_settings
from aiact.schemas.classification import (
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import (
    AnnexIProduct,
    DerogationCondition,
    GpaiStatus,
    ProhibitedPractice,
    RiskClass,
    ScopeExclusion,
    TerritorialLink,
)
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer, Confidence, Question
from aiact.tracing import trace_run


def _act_date() -> date:
    """The pinned act version, read from settings rather than restated here.

    A module constant is how the two halves silently diverged: `anchoring` loads the LAW TEXT for a
    question from `settings.act_version_date`, while this stamped a hard-coded date on the citation
    beside it. A `.env` pinning one version and a constant naming another produces a verdict
    reasoned from one text and cited to a different one — which is unfalsifiable from the report."""
    return get_settings().act_version_date


def _src(article: int, paragraph: int | None = None, annex: str | None = None) -> LegalSource:
    return LegalSource(
        instrument="Regulation (EU) 2024/1689",
        article=article,
        paragraph=paragraph,
        annex=annex,
        act_version_date=_act_date(),
    )


# The cascade's questions, in the order the Commission's checker asks them (prohibited BEFORE
# high-risk; profiling as our separate node before derogation — see classification.py).
QUESTIONS: dict[str, Question] = {
    "is_ai": Question(
        "is_ai",
        _src(3, 1),
        "Is the described system an 'AI system' within the meaning of Article 3(1)?",
        "bool",
        label="Is it an AI system at all?",
    ),
    "territorial": Question(
        "territorial",
        _src(2, 1),
        # Art. 2(1) is the POSITIVE limb, and it is asked before the exclusions because it is prior
        # to them: paragraphs (3)-(12) carve OUT of a Regulation that already applies. A system with
        # no Union connection is not "excluded" — it was never reached.
        #
        # THE DEFAULT IS THAT IT APPLIES. Real documentation almost never states territory, so a
        # node that abstained on silence would make needs_review the answer for nearly every
        # document, and one that guessed a limb would invent the finding. `not_addressed` records
        # what actually happened and lets the assessment continue — over-inclusion, never a silent
        # clearance, the same rule `_scope_exclusion` follows.
        "Which limb of Article 2(1) brings this system within this Regulation's reach?\n"
        "- eu_placing_or_service (2(1)(a)): a provider places it on the market or puts it into "
        "service IN THE UNION. Where the provider is established does not matter — a third-country "
        "provider selling into the Union is squarely within this limb.\n"
        "- eu_deployer (2(1)(b)): the deployer is established or located in the Union.\n"
        "- third_country_output_used_in_union (2(1)(c)): provider and deployer are both "
        "outside the Union, but the OUTPUT the system produces is used in the Union.\n"
        "- eu_supply_chain (2(1)(d)-(f)): an importer, distributor, product manufacturer "
        "placing the system with its own product, or an authorised representative of a non-Union "
        "provider.\n"
        "- affected_persons_in_union (2(1)(g)): the people the system is used on are in the "
        "Union.\n"
        "- not_addressed: THE ORDINARY ANSWER. The description says nothing about territory, "
        "markets or where the system is sold, used or its output consumed. Give this rather than "
        "choosing a limb the text does not support — most documentation simply never says.\n"
        "- outside_union: give this ONLY where the description POSITIVELY establishes that the "
        "system reaches the Union nowhere — not placed or serviced here, no deployer here, its "
        "output not used here, and the people it is used on not here. A system described for one "
        "non-Union market does not qualify unless the text rules the Union out; saying where a "
        "company is based, or naming a home market, settles nothing on its own.",
        "territorial_link",
        label="Is it sold, used, or its output relied on in the EU?",
    ),
    "scope": Question(
        "scope",
        _src(2),
        # Asked before Art. 5, because a system the Regulation does not govern is not a prohibited
        # practice either — Art. 5 is a provision OF this Regulation. Asked after `is_ai` because
        # Art. 2 speaks throughout of AI systems.
        #
        # The qualifiers are the question. Every exclusion here is written narrowly, so each has a
        # near neighbour that reads like it and is not it: defence PROCUREMENT is not a defence
        # PURPOSE, a research GRANT is not a research PURPOSE, a CONSUMER product is not a personal
        # DEPLOYER. Granting an exclusion on a keyword clears a system the Regulation governs,
        # which is the worst direction to be wrong in.
        #
        # The 2(3) bullet carries an extra argument because "national security" is the widest of
        # those words and the only one that collides with a listed high-risk area. It is answered
        # structurally, from Annex III(6) and III(7) — a reading of 2(3) that swallows policing or
        # border management would leave both entries with nothing to cover, so it cannot be right.
        "Does Article 2 withhold this Regulation from the described system? Answer which "
        "paragraph, or none. Each is written narrowly, and the qualifier decides it:\n"
        "- 2(3) EXCLUSIVELY for military, defence or national security purposes. Turns on what the "
        "system is USED for, not on who bought it or under which procurement rules. NATIONAL "
        "SECURITY IS NOT A SYNONYM FOR POLICING, public safety or border management: Annex III(6) "
        "lists law enforcement and Annex III(7) lists migration, asylum and border control "
        "management as HIGH-RISK areas, so reading ordinary policing or border work as national "
        "security would empty both of those entries. Protecting a national frontier is border "
        "control.\n"
        "- 2(4) a third-country public authority or international organisation, under a law "
        "enforcement or judicial cooperation agreement with the Union. See the caution below.\n"
        "- 2(6) developed and put into service for the SOLE purpose of scientific research and "
        "development — science as the end, not a stage before a product.\n"
        "- 2(8) research, testing or development PRIOR to being placed on the market or put into "
        "service. Not available once the system is sold, supplied or in operational use, and not "
        "available for testing in real-world conditions.\n"
        "- 2(10) the deployer is a natural person using it in a PURELY personal, non-professional "
        "activity. This lifts that person's obligations only; the provider keeps all of theirs, so "
        "answer none when the description is written from the provider's side.\n"
        "- 2(12) released under a free and open-source licence. Answer this whenever the licence "
        "is free and open-source; whether the paragraph's exceptions take it back is decided "
        "later in this assessment, not by you.\n"
        "Answer none if no paragraph fits. That is the ordinary answer: the Regulation applying is "
        "the rule and these are the exceptions.\n"
        "CAUTION on 2(4): it applies only if the third country affords adequate safeguards for "
        "fundamental rights and freedoms. That is a finding about a COUNTRY, not about the system, "
        "so answer 2(4) only if the description STATES that such a finding exists. If it describes "
        "a cooperation framework without it, say the description does not state the facts needed — "
        "do not infer it from the existence of an agreement.",
        "scope_exclusion",
        label="Does this Regulation apply to the system at all?",
    ),
    "gpai_model": Question(
        "gpai_model",
        _src(3, 63),
        # THE MODEL/SYSTEM LINE IS THE WHOLE DIFFICULTY. Art. 3(66) makes a general-purpose AI
        # SYSTEM an ordinary AI system, so a hiring tool running on a foundation model is still
        # Annex III(4) high-risk. Routing out everything that mentions a large model would exempt
        # exactly the products the tier logic exists for.
        #
        # PRE-MARKET IS ITS OWN ANSWER, not a `no`. Art. 3(63) excludes models in research,
        # development or prototyping before placing — a TEMPORAL exclusion. Folding it into "not a
        # model" would drop a frontier model back into the risk cascade and report `minimal`, which
        # reads as a clearance of duties that switch on the day it ships.
        "What does this description describe, on the line Article 3, point (63) draws?\n"
        "- general_purpose_model: a model that displays SIGNIFICANT GENERALITY, competently "
        "performs a WIDE RANGE OF DISTINCT TASKS, and can be integrated into a VARIETY of "
        "downstream systems — and that has been placed on the market or put into service. The "
        "subject of the description is the MODEL itself: its weights, training, evaluations, "
        "licence, context length, how to run or fine-tune it.\n"
        "- general_purpose_model_pre_market: the same model, but still in research, development "
        "or prototyping and NOT YET placed on the market or put into service. Say this rather than "
        "'not a model' — the Art. 3(63) exclusion is about timing, not about what the thing is.\n"
        "- ai_system: anything else. Answer this where the description has an intended purpose, "
        "users, or a decision it feeds — that is an AI system even where it plainly runs on a "
        "general-purpose model underneath (Art. 3(66)). A chatbot, a coding assistant or a "
        "document summariser built on a foundation model is a SYSTEM. Answer it too for a model "
        "doing ONE thing — text-to-speech, demand forecasting, image segmentation, transcription — "
        "is not general however large or widely reused. Generality is the test that decides most "
        "cases.",
        "gpai_status",
        label="Is this a general-purpose AI model rather than a system?",
    ),
    "prohibited": Question(
        "prohibited",
        _src(5),
        # Answered as a POINT, not a boolean. This is the only class that tells a provider their
        # system may not ship at all, and a verdict citing Art. 5 as a whole cannot be checked or
        # argued with. Naming the point also forces the exception into view: every one of (d), (f),
        # (g) and (h) carries a carve-out, and a model asked only "is this banned?" never reaches
        # them.
        "Which point of Article 5(1) prohibits the described system, if any? Answer the point, or "
        "none. Each is narrow, and the qualifier decides it:\n"
        "- (a) subliminal, purposefully manipulative or deceptive techniques that materially "
        "distort behaviour and cause significant harm. Ordinary persuasion, advertising and "
        "recommendation are not this.\n"
        "- (b) exploits vulnerabilities of age, disability, or a specific social or economic "
        "situation, so as to distort behaviour and cause significant harm.\n"
        "- (ba) generating or manipulating REALISTIC intimate imagery of an identifiable person — "
        "their intimate parts, or them engaged in sexually explicit activity — without that "
        "person's explicit consent.\n"
        "- (bb) generating or manipulating child sexual abuse material within Directive "
        "2011/93/EU.\n"
        "  BOTH (ba) and (bb) are narrowed by Article 5(1a), and the qualifier is the whole test. "
        "CAPABILITY IS NOT ENOUGH: a general-purpose image, video or audio generator is not caught "
        "merely because such material could be coaxed out of it. Answer (ba) or (bb) only if the "
        "description shows one of: producing that material is the system's INTENDED PURPOSE; or it "
        "is a reasonably foreseeable and reproducible output, obtainable without significant "
        "technical modification, AND the description gives no reasonable safeguards against it "
        "(filtering, refusal training, output classification, misuse detection and correction); or "
        "the operator USES the system to produce such material. A described safeguard defeats the "
        "second limb — say none if the document describes one. For (ba) alone, Article 5(1b) also "
        "excludes editing that does not increase exposure or change the nature of what is "
        "depicted, such as cropping, relighting or captioning existing material.\n"
        "- (c) social scoring: evaluating persons over time on social behaviour or personal "
        "characteristics, where the score leads to detrimental treatment that is out of context or "
        "disproportionate. Scoring within one context on relevant data — credit from financial "
        "history, insurance from claims — is not this.\n"
        "- (d) predicting the risk of a person COMMITTING a criminal offence based SOLELY on "
        "profiling or personality traits. Does NOT cover a system supporting a human assessment "
        "already based on objective and verifiable facts linked to criminal activity.\n"
        "- (e) creating or expanding facial recognition databases by UNTARGETED scraping of facial "
        "images from the internet or CCTV.\n"
        "- (f) inferring emotions of a natural person in the workplace or in education "
        "institutions, EXCEPT for medical or safety reasons.\n"
        "- (g) biometric categorisation deducing race, political opinions, trade union membership, "
        "religious or philosophical beliefs, sex life or sexual orientation. Does NOT cover "
        "labelling or filtering of lawfully acquired biometric datasets.\n"
        "- (h) 'real-time' remote biometric identification in publicly accessible spaces for law "
        "enforcement. Both qualifiers are DEFINED and supplied: 'real-time' (Art. 3(42)) covers "
        "not only instant identification but LIMITED SHORT DELAYS, so a buffer of seconds does not "
        "take a system out of it — only identification run over already-recorded material is "
        "post-hoc. A 'publicly accessible space' (Art. 3(44)) is PUBLICLY OR PRIVATELY OWNED, so "
        "a shop, stadium or transport hub counts.\n"
        "Answer none if no point fits. That is the ordinary answer: Art. 5 bans ten specific "
        "practices, not everything that reads as sensitive or intrusive.",
        "prohibited_practice",
        label="Is the practice itself banned?",
    ),
    "annex_i": Question(
        "annex_i",
        _src(6, 1, annex="I"),
        # Art. 6(1) is the OTHER door into high-risk, and it is asked before Annex III because the
        # two routes are independent: an Annex I safety component is high-risk whatever Annex III
        # says, and the Art. 6(3) derogations cannot reach it — they derogate from 6(2) alone.
        # This node decides condition (a) only; condition (b) is the next node.
        "Is this AI system intended to be used as a SAFETY COMPONENT of a product, or is it "
        "itself a product, covered by one of the Union harmonisation instruments listed in "
        "Annex I (Article 6(1)(a))? Answer which product family, or none.\n"
        "'Safety component' is DEFINED at Art. 3(14) and supplied below, in TWO limbs: a component "
        "whose intended purpose is to prevent or mitigate risks to health and safety, OR one "
        "whose failure or malfunctioning endangers health and safety OF PERSONS OR PROPERTY. "
        "Either limb suffices — braking, pressure or dose control, collision avoidance, "
        "structural monitoring.\n"
        "THE EXCLUSION IS ART. 6(1a), supplied below, and it is worded: a system SOLELY used for "
        "NON-SAFETY-RELATED aspects of user assistance, performance optimisation, service "
        "efficiency, automation or convenience, or for quality control, does not qualify as a "
        "safety component. Apply that list and not a longer one — scheduling, billing, diagnostics "
        "reporting and fleet analytics sit within it. But Art. 6(1b) takes back what 6(1a) gives: "
        "NOTWITHSTANDING 6(1a), a system whose failure or malfunctioning would endanger health and "
        "safety qualifies anyway. So software alongside the product is excluded only where getting "
        "it wrong could not endanger health or safety; where it could, 6(1b) puts it back in.\n"
        "MACHINERY APPEARS TWICE, under two instruments, and the choice decides which obligations "
        "follow. Answer `machinery` (Directive 2006/42/EC) for a machine unless the description "
        "itself says the product is placed on the market under Regulation (EU) 2023/1230 — that "
        "Regulation replaces the Directive only from 20 January 2027, so the Directive governs "
        "anything on the market before then. Do not choose between them on how modern the machine "
        "sounds; choose on the instrument the document names.\n"
        "Answer none if the system is not embedded in, or sold as, a regulated physical product.",
        "annex_i_product",
        label="Is it a safety component of a regulated physical product?",
    ),
    "third_party_assessment": Question(
        "third_party_assessment",
        _src(6, 1, annex="I"),
        # Art. 6(1) is a CONJUNCTION: (a) AND (b). Most Annex I regimes let a manufacturer
        # self-assess for lower-risk classes, so treating (a) alone as sufficient would classify
        # self-certified products high-risk and demand Chapter III of systems that do not owe it.
        #
        # READ ONLY, NEVER DERIVE. Condition (b) turns on the SECTORAL instrument — the risk class
        # rules of the medical devices, machinery or vehicle regime, none of which are in this
        # Regulation and none of which this tool carries. Deriving the answer would mean applying
        # a body of law the tool has no text for, to a domain it cannot check itself, and emitting
        # a confident tier off the back of it. So the question is deliberately narrowed to what the
        # document SAYS, and silence routes to needs_review with a note naming the specialist.
        "Does the description STATE how the product's conformity is assessed under that Annex I "
        "legislation (Article 6(1)(b))? Answer true only if it says a THIRD PARTY assesses it — a "
        "notified body, a named certificate, an EU type-examination. Answer false only if it says "
        "the manufacturer self-assesses, self-certifies, or uses internal control.\n"
        "Do NOT infer the answer from the kind of product, its risk class, or what such products "
        "usually require. If the description does not state the conformity route, say so: that is "
        "a question for a specialist in that sector's rules, not something to deduce here.",
        "bool",
        label="Does that product need an outside body to certify it?",
    ),
    "annex_iii": Question(
        "annex_iii",
        _src(6, 2, annex="III"),
        # SCOPE ONLY — deliberately, on legal grounds. Art. 6(2) puts a system inside an Annex III
        # area; Art. 6(3) then takes it out "by derogation". They are sequential, and this node is
        # the first one. Left unqualified, the question invites both judgements at once — and
        # because Art. 6(3) sits in the same supplied Article 6 text, a model reads on and answers
        # "no area" for a system that IS in scope but has a narrow role. That collapses
        # not_high_risk (Art. 6(4) documentation and registration still owed) into minimal (nothing
        # owed), and it skips the derogation node entirely so the reason is never recorded.
        #
        # POINT 2 NEEDS ITS OWN TEST, and (0) is it. Tests (i) and (ii) ask whether the purpose acts
        # on a PERSON or their application, which is the right test for seven of the eight areas and
        # the wrong one for critical infrastructure: point 2's subject is a pipe, a road or a grid,
        # so a signal controller answers (ii) word for word and comes back `none` — reported as
        # `minimal`, one obligation in the whole report, for a system whose failure kills people.
        "Which Annex III high-risk area, if any, does this use case fall within (Article 6(2))? "
        "Decide SCOPE ONLY, by whether the described PURPOSE is part of a listed function.\n"
        "(0) POINT 2 IS DECIDED ON A DIFFERENT TEST, and it is the only area that is. Critical "
        "infrastructure names no natural person: it covers AI systems used as SAFETY COMPONENTS in "
        "the management and operation of critical digital infrastructure, road traffic, or the "
        "supply of water, gas, heating or electricity. 'Safety component' is DEFINED at Art. 3(14) "
        "and supplied below, in TWO limbs: a component that fulfils a safety function — its "
        "intended purpose being to prevent or mitigate risks to health and safety OF PERSONS OR "
        "PROPERTY — OR one whose failure or malfunctioning endangers the health and safety of "
        "persons or property. Either limb suffices: signal and traffic control, grid frequency "
        "response or load shedding, protection relays, pressure or flow control in a water or gas "
        "network, or the monitoring that trips them. Answer critical_infrastructure for those. Do "
        "NOT answer none merely because no person is acted on: tests (i) and (ii) below are the "
        "test for the SEVEN areas that are about people, not for this one.\n"
        "The exclusion is Art. 6(1a), also supplied, and it is worded and limited: a system SOLELY "
        "used for NON-SAFETY-RELATED aspects of user assistance, performance optimisation, service "
        "efficiency, automation or convenience, or for quality control, does not qualify as a "
        "safety component. Apply that list, not a longer one of your own — billing and customer "
        "outage notification sit within it. But Art. 6(1b) takes back what 6(1a) gives: "
        "NOTWITHSTANDING 6(1a), a system whose failure or malfunctioning would endanger health and "
        "safety DOES qualify. So an optimisation, forecasting, maintenance or capacity system is "
        "excluded only where getting it wrong could not endanger health or safety. Where it could "
        "— maintenance that leaves a corroding gas main unflagged, forecasting that under-calls "
        "grid load — 6(1b) puts it back in, and the answer is critical_infrastructure.\n"
        "For points 1 and 3 to 8, which are each about natural persons, two tests, both taken from "
        "the text:\n"
        "(i) IN scope if the purpose SUBSTANTIVELY acts on the person or their application within "
        "a listed function, INCLUDING where the system only prepares, extracts, organises or "
        "de-duplicates that material. For employment the listed functions are the recruitment or "
        "selection process (Annex III(4)(a)) and the named workforce decisions — promotion, "
        "termination, task allocation, performance evaluation (4(b)). A tool that processes job "
        "applications is used FOR recruitment even if it only parses or de-duplicates them. Do NOT "
        "exclude a system because its own role is narrow, procedural, preparatory or merely "
        "assistive: that narrowness is an Article 6(3) exemption assessed at a LATER step, not a "
        "reason to place it outside the area now.\n"
        "(ii) OUT of scope if the purpose does not act on the person or their application at all — "
        "either general workplace administration (leave and holiday tracking, IT provisioning, "
        "facilities for already-employed staff, and payroll PROCESSING that calculates and "
        "disburses pay already agreed) OR surrounding logistics handling calendars, rooms or "
        "reminders "
        "rather than the candidate or their application (e.g. scheduling interview slots) — even "
        "though it plainly operates in that setting. This list is a reading of the Annex and not "
        "a quotation. The exclusions the Annex itself enacts are the four in (iii) and there is no "
        "fifth to infer, so where an example here and the listed "
        "function disagree, the listed function wins. Anything that SETS or adjusts pay, bonus, "
        "grade or benefits is a decision affecting the terms of a work-related relationship under "
        "Annex III(4)(b) and stays IN, whatever the surrounding system is called.\n"
        "(iii) FOUR exclusions ARE decided here, because the Annex writes each one into the area "
        "itself rather than derogating from it. These four are the whole of what points 1 and 3 to "
        "8 exclude; every one of them is above in the supplied text, and there is no fifth.\n"
        "  - Point 1(a) does not cover biometric VERIFICATION the sole purpose of which is to "
        "confirm that a specific natural person is the person he or she claims to be — one face, "
        "fingerprint or voice matched against that same person's enrolled template, as when a "
        "device is unlocked or a ticket is checked against its own holder. Searching a person "
        "against a gallery of many is remote IDENTIFICATION and stays in scope. 'Sole' is strict: "
        "a system that also searches for unknown people, categorises them, or infers anything "
        "about them keeps the area.\n"
        "  - Point 5(b) covers evaluating CREDITWORTHINESS or establishing a credit score, WITH "
        "THE EXCEPTION of systems used for the purpose of DETECTING FINANCIAL FRAUD. A fraud "
        "detector is outside point 5 even though it scores natural persons.\n"
        "  - Point 7(d) covers detecting, recognising or identifying natural persons in migration, "
        "asylum or border control, WITH THE EXCEPTION of the VERIFICATION OF TRAVEL DOCUMENTS. "
        "Checking a document is excepted; identifying the person carrying it is not.\n"
        "  - Point 8(b) covers influencing the outcome of an election or referendum or voting "
        "behaviour, but DOES NOT INCLUDE AI systems to the output of which natural persons are "
        "not DIRECTLY EXPOSED — the Annex's own example is tools used to organise, optimise or "
        "structure political campaigns from an administrative or logistical point of view.\n"
        "Each exception belongs to its own point only: a system excepted under one point is still "
        "in scope under any other point whose listed function it serves.\n"
        "(iv) Points 1, 6 and 7 open with 'in so far as their use is permitted under relevant "
        "Union or national law'. Do NOT treat that as a test to apply here. Whether a Member State "
        "permits the use is a question for that State's law, not for this description, and a use "
        "that is not permitted is not thereby made low-risk — it is barred by that other law. "
        "Answer on the listed function the purpose serves.\n"
        "Answer the area, or none only if the purpose serves no listed function at all.",
        "annex_area",
        label="Is it used in a listed high-risk area?",
    ),
    "profiling": Question(
        "profiling",
        _src(6, 3),
        "Does this use case perform profiling of natural persons (Article 6(3))? Profiling is "
        "DEFINED, at Art. 3(52), by reference to Article 4(4) GDPR and supplied below: any "
        "automated processing of personal data to EVALUATE personal aspects of a natural person, "
        "in particular to analyse or predict performance at work, economic situation, health, "
        "preferences, interests, reliability, behaviour, location or movements. Evaluating or "
        "scoring a person is profiling; a purely procedural task on their file is not.\n"
        "THIS ANSWER OVERRIDES EVERY Art. 6(3) DEROGATION, so it is asked on the definition "
        "rather than on how narrow the system's role sounds.",
        "bool",
        label="Does it score, rank or judge people?",
    ),
    "derogation": Question(
        "derogation",
        _src(6, 3),
        # The SECOND subparagraph only. The chapeau is the `significant_risk` node — see there for
        # why the paragraph is split in two.
        #
        # EACH LIMB CARRIES ITS QUALIFIER, because two of the four are conjunctions whose second
        # half is what decides real cases. (c) reaches a system that detects decision patterns AND
        # is not meant to replace or influence the completed human assessment — a system that
        # detects a pattern and then feeds it back into the assessment is the case the point
        # excludes. (d) reaches a task preparatory TO AN ASSESSMENT RELEVANT TO AN ANNEX III USE
        # CASE, and without that tether it reads as a general exemption for anything preparatory.
        # A named condition routes to `significant_risk`, whose `false` ends at NOT_HIGH_RISK with
        # Arts. 9-15 and 16-21 gone, so a limb stated loosely is a false clearance.
        "Does an Article 6(3)(a)-(d) derogation apply? Answer which condition, or none. Each is a "
        "test in full — a system that meets the first half of (c) or (d) and not the second does "
        "NOT qualify:\n"
        "(a) narrow_procedural_task — intended to perform a NARROW PROCEDURAL task.\n"
        "(b) improves_completed_human_activity — intended to improve the result of a PREVIOUSLY "
        "COMPLETED human activity. The human work is already done; the system polishes it.\n"
        "(c) detects_decision_patterns — intended to detect decision-making patterns or deviations "
        "from prior decision-making patterns, AND is not meant to replace or influence the "
        "previously completed human assessment without proper human review. Both halves. A system "
        "that surfaces a pattern and then feeds it into the assessment, or that stands in for the "
        "human review, fails the second half and the derogation does not apply.\n"
        "(d) preparatory_task — intended to perform a preparatory task TO AN ASSESSMENT RELEVANT "
        "FOR THE PURPOSES OF THE USE CASES LISTED IN ANNEX III. Preparatory to the listed "
        "assessment, not preparatory in general.\n"
        "Answer none where the description does not establish the whole of any one condition.",
        "derogation",
        label="Is its role only a narrow one?",
    ),
    "significant_risk": Question(
        "significant_risk",
        _src(6, 3),
        # Art. 6(3)'s FIRST subparagraph, and the other half of a conjunction whose second half is
        # the `derogation` node. The paragraph exempts a system where it does not pose a significant
        # risk of harm AND one of (a)-(d) is met; a node asking only the conditions would clear a
        # system that performs a narrow procedural task and still decides the outcome.
        #
        # The structural argument is here for the same reason it is in the scope node: without it a
        # model answers from the area rather than from the system. Every system reaching this
        # question is in an Annex III area — they are listed there because that setting is risky —
        # so a reading that infers the risk from the listing makes Art. 6(3) unreachable in every
        # case, which cannot be what a paragraph written to be applied means.
        #
        # The test is narrowed to the one the paragraph itself names: whether the output materially
        # influences the outcome of decision making. That is a fact the description can state, and
        # is what keeps this from being an open-ended judgement about harm in the abstract.
        "Article 6(3) exempts an Annex III system from high-risk classification only where BOTH "
        "halves hold: it does not pose a significant risk of harm to the health, safety or "
        "fundamental rights of natural persons — INCLUDING by not materially influencing the "
        "outcome of decision making — AND one of the conditions (a)-(d) is met. The condition is "
        "already established. Answer the first half: does this system pose such a risk?\n"
        "Every system reaching this question is already within an Annex III area, so being listed "
        "there cannot itself be the answer — that reading would leave Art. 6(3) unable to exempt "
        "anything. Judge the system's OWN contribution to the decision taken about the person:\n"
        "- true if its output is relied on, weighted, scored or ranked in reaching that decision, "
        "or if it filters, orders or flags people so that some are treated differently before a "
        "human considers them.\n"
        "- false if a person reaches the same decision on the same material whether or not the "
        "system ran — it reformats, transcribes, routes, de-duplicates or summarises, and the "
        "substantive judgement is made elsewhere on the underlying evidence.\n"
        "If the description does not say how the output is used in the decision, say so. Do not "
        "assume either way: whether anyone relies on it is the whole question.",
        "bool",
        label="Could it still materially affect the decision?",
    ),
    "transparency": Question(
        "transparency",
        _src(50),
        # The examples span all four Art. 50 paragraphs: (1) and (2) bind the provider, (3) and (4)
        # the deployer. An example list stopping at the provider paragraphs tilts the answer even
        # though the full text is supplied as context, and omits this project's own emotion cases.
        "Which Article 50 transparency duties attach to this system? Answer EVERY one that "
        "applies — they are cumulative, and one system can owe several — or an empty list if none "
        "does. Answer regardless of the risk tier: Art. 50 is independent of it.\n"
        "- direct_interaction (50(1), the PROVIDER's duty): the system is intended to interact "
        "directly with natural persons. Not owed where that is obvious to a reasonably "
        "well-informed person.\n"
        "- synthetic_content_marking (50(2), the PROVIDER's duty): it generates synthetic audio, "
        "image, video or text, which must be marked machine-readably. NOT owed where the system "
        "performs an assistive function for standard editing, or does not substantially alter the "
        "deployer's input data or its semantics — polishing a person's own text is that carve-out; "
        "drafting the text is not.\n"
        "- emotion_or_biometric_categorisation (50(3), the DEPLOYER's duty): it is an emotion "
        "recognition or biometric categorisation system. Both are DEFINED and supplied: emotion "
        "recognition (Art. 3(39)) infers emotions ON THE BASIS OF BIOMETRIC DATA, so sentiment "
        "scoring of typed text is not one; biometric categorisation (Art. 3(40)) EXCEPTS a "
        "feature ancillary to another commercial service and strictly necessary for objective "
        "technical reasons. Attaches to the system TYPE, so answer it even where the practice is "
        "also prohibited under Art. 5.\n"
        "- deep_fake_disclosure (50(4), the DEPLOYER's duty): it generates or manipulates image, "
        "audio or video constituting a deep fake — DEFINED at Art. 3(60) and supplied below, "
        "which requires that the content resemble existing persons, objects, places, entities or "
        "events and would FALSELY APPEAR to a person to be authentic or truthful.\n"
        "- public_interest_text_disclosure (50(4), the DEPLOYER's duty): it generates text "
        "published to inform the public on matters of public interest. NOT owed where the content "
        "undergoes human review or editorial control with a person holding editorial "
        "responsibility.\n"
        "Every duty is disapplied where the system is authorised by law to detect, prevent, "
        "investigate or prosecute criminal offences.",
        "transparency_duties",
        label="Must people be told they are dealing with AI?",
    ),
}

# Which verbatim provisions each question must be answered against. The classification questions
# are anchored the same way the obligation `requirement` fields are: from the stored enacted text,
# never from a model's memory of the law. Annex III in particular IS the list of high-risk areas —
# asking "which Annex III area is this?" without supplying Annex III is exactly the unanchored
# guessing this project exists to avoid.
_QUESTION_CONTEXT: dict[str, Provisions] = {
    "is_ai": (("3",), ()),  # Art. 3 — the 'AI system' definition
    # Art. 3 too: the exclusions lean on defined terms the Article does not restate — 'placing on
    # the market' (3(9)-(10)) for 2(8), 'deployer' (3(4)) for 2(10), and 'testing in real-world
    # conditions' (3(57)), which is what stops 2(8) covering a live pilot.
    "territorial": (("2",), ()),  # Art. 2(1) — the positive limb
    "scope": (("2", "3"), ()),
    # Art. 3(63) definition + the Chapter V regime it hands to
    "gpai_model": (("3", "51", "53"), ()),
    "prohibited": (("5",), ()),  # Art. 5 — the prohibited practices
    "annex_i": (("6",), ("I",)),  # Art. 6(1) + the Annex I legislation list itself
    # Art. 2 as well: 2(2) is what makes the Section A/B split matter, and the model is
    # judging which instrument covers the product.
    "third_party_assessment": (("2", "6"), ("I",)),
    "annex_iii": (("6",), ("III",)),  # Art. 6(2) + the Annex III area list itself
    "profiling": (("6",), ()),  # Art. 6(3) — the carve-back
    "derogation": (("6",), ()),  # Art. 6(3)(a)-(d)
    "significant_risk": (("6",), ()),  # Art. 6(3) first subparagraph
    "transparency": (("50",), ()),  # Art. 50
}

# THE DEFINED TERMS EACH QUESTION TURNS ON — Article 3 points, supplied beside the provisions above.
# Art. 3 is 68 definitions and some 19 000 characters, so it is handed over by the point: naming
# them keeps a classification cheap, and it makes the supply checkable, which is the part that
# matters. The coverage ledger rules each of these `CASCADE <node>`, and
# `test_every_definition_the_ledger_hands_to_a_node_reaches_it` reads that claim back out.
#
# A DEFINITION IS NOT A GLOSS. Each of these carries a qualifier that decides cases and that a
# paraphrase drops: 3(42) covers "not only instant identification, but also limited short delays in
# order to avoid circumvention", 3(44) reaches a "publicly OR PRIVATELY owned" place, 3(40) excepts
# categorisation "ancillary to another commercial service and strictly necessary for objective
# technical reasons", and 3(14) has two limbs of which the second reaches property as well as
# persons. The questions state the test; these supply the words it is made of.
_QUESTION_DEFINITIONS: dict[str, tuple[int, ...]] = {
    "annex_i": (14,),  # 'safety component' — the whole test of Art. 6(1)(a)
    # 35/36 draw the Annex III(1)(a) line; 14 because branch (0) decides point 2 on the same
    # 'safety component' test Art. 6(1)(a) uses, and a node that decides on a term needs its words.
    "annex_iii": (14, 35, 36),
    "prohibited": (41, 42, 44),  # remote biometric identification, 'real-time', public space
    "profiling": (52,),  # 'profiling' — defined by reference to Art. 4(4) GDPR
    "transparency": (39, 40, 60),  # emotion recognition, biometric categorisation, 'deep fake'
}

# NON-BINDING Commission guidance to supply per question, by snippet ref (data/policy/guidance/).
# Only for questions the ENACTED TEXT leaves open: Art. 5(1)(f) prohibits emotion recognition "in
# the workplace" but never says whether hiring counts — so a model reading Art. 5 alone can only
# guess. The Commission's reading is supplied here (labelled non-binding), the same anti-memory
# discipline as _QUESTION_CONTEXT, one level up. A verdict reached with it says it rested on
# interpretation, not law. (Coarse for now: attached to the whole `prohibited` node; the snippet is
# only relevant to its Art. 5(1)(f) sub-question, harmless where it is not.)
_QUESTION_GUIDANCE: dict[str, tuple[str, ...]] = {
    "prohibited": ("C-2025-5052/workplace-covers-recruitment",),
}


def load_questions(
    version: str | date | None = None,
    articles_root: str | Path | None = None,
    annexes_root: str | Path | None = None,
    guidance_root: str | Path | None = None,
) -> dict[str, Question]:
    """QUESTIONS with each `context` filled from the verbatim article/annex store, and
    `guidance_context` filled from the guidance store where the enacted text leaves a question open.

    Use this for any brain that actually reads the law (LLMBrain). The bare QUESTIONS constant is
    left context-free so the deterministic ScriptedBrain path needs no file IO.

    The loading itself lives in `aiact.anchoring`, shared with the gap layer's own Art. 25 question:
    both layers put questions to a brain, neither may import the other, and a second copy of the
    integrity check that guards the article store is the last thing this project should carry.
    """
    return anchor_questions(
        QUESTIONS,
        _QUESTION_CONTEXT,
        _QUESTION_GUIDANCE,
        version=version,
        articles_root=articles_root,
        annexes_root=annexes_root,
        guidance_root=guidance_root,
        definitions=_QUESTION_DEFINITIONS,
    )


class GraphState(BaseModel):
    description: str
    use_case_id: str = "use_case"
    is_ai_system: Answer | None = None
    territorial_link: Answer | None = None
    scope_exclusion: Answer | None = None
    gpai_model: Answer | None = None
    prohibited: Answer | None = None
    in_annex_i: Answer | None = None
    third_party_assessment: Answer | None = None
    in_annex_iii: Answer | None = None
    performs_profiling: Answer | None = None
    derogation: Answer | None = None
    poses_significant_risk: Answer | None = None
    transparency: Answer | None = None
    result: ClassificationResult | None = None


def _is_low_confidence(a: Answer | None) -> bool:
    return a is not None and a.confidence == "low"


def _every_answer(state: GraphState) -> list[Answer]:
    """Every answer the cascade produced, in the order it asked them.

    The state fields ARE the cascade order, so listing them is the record of what was asked: a node
    the run never reached is None and drops out, which is what separates "answered no" from "never
    put" — two things a reader must not confuse.

    Unlike `_get_answers` this INCLUDES transparency, because the purpose is different: that one
    feeds the confidence rule and must exclude Art. 50, this one is the audit trail."""
    ordered = [
        state.is_ai_system,
        state.territorial_link,
        state.scope_exclusion,
        state.gpai_model,
        state.prohibited,
        state.in_annex_i,
        state.third_party_assessment,
        state.in_annex_iii,
        state.performs_profiling,
        state.derogation,
        state.poses_significant_risk,
        state.transparency,
    ]
    return [a for a in ordered if a is not None]


def _get_answers(state: GraphState) -> list[Answer]:
    """The answers that determine the RISK CLASS.

    `transparency` is deliberately absent. Art. 50 is a separate axis, not a step in the risk
    cascade — a minimal-risk generator and a high-risk chatbot can both trigger it. If it were
    counted here, a low-confidence transparency answer would wrongly drag the whole classification
    to needs_review, and an Art. 50 finding would look like it influenced the tier. It does not."""
    answers = [
        state.is_ai_system,
        state.territorial_link,
        state.scope_exclusion,
        state.gpai_model,
        state.prohibited,
        state.in_annex_i,
        state.third_party_assessment,
        state.in_annex_iii,
        state.performs_profiling,
        state.derogation,
        state.poses_significant_risk,
    ]
    return [a for a in answers if a is not None]


# What each node needed the DESCRIPTION to state, phrased for the person who has to go and write it.
# NOT the question text: that is addressed to a model reading the enacted provision beside it, and
# lands as jargon on an author ("does this use case perform profiling?").
_WHAT_THE_NODE_NEEDED: dict[str, str] = {
    "is_ai": "whether this is an AI system — does it infer its outputs, or follow rules a person "
    "wrote",
    "territorial": "where the system is placed, used, or its output consumed — whether any of "
    "that touches the Union",
    "scope": "who uses the system and what for — whether it is military, purely research, "
    "pre-market, or a private person's own use",
    "gpai_model": "whether the document describes a model or a product built with one — and, if a "
    "model, whether it is general enough to serve a wide range of distinct tasks",
    "prohibited": "whether it infers emotions, categorises people biometrically, scores social "
    "behaviour, or predicts who will commit an offence — and, where it does, whether an Art. 5 "
    "exception applies (medical or safety use, a lawfully acquired dataset, a human assessment on "
    "objective facts)",
    "annex_i": "whether the system is a safety component of a regulated physical product — "
    "a machine, a lift, a medical device, a vehicle",
    # Short by design: when this node abstains, `_handover` follows and names the instrument
    # and who answers, so anything more here is said twice.
    "third_party_assessment": "how the product's conformity is assessed — by a notified body, or "
    "by the manufacturer alone",
    "annex_iii": "what the system is actually used for",
    "profiling": "whether it evaluates, scores or ranks people — and on what",
    "derogation": "whether it only performs a narrow procedural task, improves prior human work, "
    "detects decision patterns, or prepares an assessment",
    "significant_risk": "how the system's output is used in the decision about the person — "
    "whether anyone relies on it, or it only prepares material judged elsewhere",
    "transparency": "whether it generates content, interacts with people directly, or infers "
    "emotions — and who operates it, since Art. 50 splits its duties between the provider and the "
    "deployer",
}


def _cite(source: LegalSource) -> str:
    cite = f"Art. {source.article}"
    if source.paragraph:
        cite += f"({source.paragraph})"
    return cite


def _handover(product: AnnexIProduct) -> str:
    """The Art. 6(1)(b) question named, with whose question it is — and that the silence is itself
    a finding.

    This tool declines condition (b) by design: it turns on the sectoral instrument, not on this
    Regulation (see the `third_party_assessment` question). Declining is only useful if the reader
    is told what is unresolved and who resolves it; "consult a specialist" is not an action.

    The closing sentence makes the silence a finding rather than an apology. A file for such a
    product is expected to record its conformity route — Annex IV puts the EU declaration of
    conformity in the technical documentation and Annex V fixes its contents down to the notified
    body's identification number, while the sectoral legislation demands the same independently.
    The omission is therefore a documentation shortcoming in its own right, and reporting only
    "the tool could not decide" puts the failure on the wrong side of the exchange."""
    return (
        f"UNRESOLVED — Art. 6(1)(b), conformity assessment route. This system is a safety "
        f"component of, or is itself, a product covered by {product.legislation}, so whether it is "
        f"high-risk turns on whether that product needs a third-party conformity assessment. That "
        f"is decided by the legislation above, not by the AI Act, and this tool does not apply it. "
        f"Ask {product.who_decides_conformity}. If the answer is yes, this system is high-risk "
        f"under Art. 6(1); if no, re-run and it will be assessed against Annex III instead. "
        f"Note that documentation for a product under this legislation is normally expected to "
        f"record its conformity route — the CE marking, the notified body's identification number, "
        f"or the EU declaration of conformity (Annex IV(9), contents fixed by Annex V). Its "
        f"absence here is worth fixing whichever way this classification resolves."
    )


def _why_it_could_not_decide(
    abstentions: list[Answer],
    annex_i_product: AnnexIProduct | None = None,
) -> str:
    """Name the MISSING FACT and the article that needed it, instead of 'a node abstained'.

    An answer of 'needs review' that does not say what was missing gives the reader nothing to act
    on — they cannot tell whether to edit their documentation, and if so what to add. The node_id
    and the citation were already on the answer and were being discarded here.

    Split by cause: a silent document is the user's to fix, an unreadable model reply is not, and
    telling someone to rewrite adequate documentation would be worse than saying nothing."""
    silent = [a for a in abstentions if a.abstained_because == "description_silent"]
    broken = [a for a in abstentions if a.abstained_because != "description_silent"]

    parts: list[str] = []
    if silent:
        missing = "; ".join(
            f"{_WHAT_THE_NODE_NEEDED.get(a.node_id or '', 'the fact this question turns on')} "
            f"({_cite(a.source)})"
            for a in silent
        )
        parts.append(
            f"The description does not state: {missing}. Add it and re-run — the answer cannot be "
            f"inferred from what is there, and guessing it would decide the risk class on a fact "
            f"the documentation never supplied."
        )
    if broken:
        nodes = ", ".join(f"{a.node_id} ({_cite(a.source)})" for a in broken)
        parts.append(
            f"No usable answer was returned for: {nodes}. This is a failure of the run, not of the "
            f"documentation — re-running may resolve it."
        )
    if annex_i_product is not None and any(
        a.node_id == "third_party_assessment" for a in abstentions
    ):
        parts.append(_handover(annex_i_product))
    return " ".join(parts) or "A classification node abstained; escalate to a human reviewer."


def _scope_exclusion(state: GraphState) -> ScopeExclusion | None:
    """The Art. 2 exclusion this system is under, or None for the ordinary case where it is not.

    Narrowed by TYPE, not by truthiness: only a named paragraph is an exclusion, because only a
    named paragraph can be cited. Anything else a brain puts here — a bare false, an unrecognised
    string — means it has not named one, and the safe reading of "not named" is that the Regulation
    applies. Over-inclusion, never a silent clearance."""
    a = state.scope_exclusion
    return a.value if a is not None and isinstance(a.value, ScopeExclusion) else None


def _scope_evidence(
    answer: Answer, exclusion: ScopeExclusion
) -> ClassificationEvidence:
    """Evidence for an Art. 2 verdict, pinpointed to the PARAGRAPH that decided it.

    One node answers all six exclusions, so its question is registered against Article 2 as a whole
    and its `source` carries no paragraph. Which paragraph applies is not known until the answer is
    in — so it is stamped on here. Without this the prose says "Art. 2(3)" while the structured
    citation says only "Art. 2", and a consumer reading the citation rather than the text gets a
    less precise answer than the tool actually holds."""
    evidence = ClassificationEvidence.from_answer(answer)
    pinpointed = evidence.source.model_copy(update={"paragraph": exclusion.paragraph})
    return evidence.model_copy(update={"source": pinpointed})


def _condition_letter(state: GraphState) -> str:
    """The Art. 6(3) point the derogation node named, for the citation in a verdict.

    Narrowed by TYPE for the same reason `_scope_exclusion` is: only a recognised condition can be
    cited by letter, and anything else a brain puts there has not named one. Falls back to
    "a)-(d" so the sentence still reads as a citation of the subparagraph as a whole."""
    a = state.derogation
    return a.value.letter if a is not None and isinstance(a.value, DerogationCondition) else "a)-(d"


# What a GPAI verdict SAYS. A handover, in the same shape as `_handover` for Art. 6(1)(b): name the
# regime, say plainly that this tool does not apply it, and point the reader at what to read. The
# alternative was `minimal`, which told a foundation-model provider they owed almost nothing.
#
# The dates are load-bearing. Chapter V has applied since 2 August 2025 (Art. 113(b)), which makes
# these the only obligations in this tool's field of view that are in force TODAY — every high-risk
# rule waits until 2 August 2026. A reader who takes "not assessed here" as "not urgent" would have
# it exactly backwards.
#
# The Art. 52(6) list is named because it is the one authoritative answer to the systemic-risk
# question, and because it is not yet findable — a reader who checks and finds nothing should know
# that is expected rather than assume they looked in the wrong place. See docs/ROADMAP.md (M4d-8).
# The Chapter V duties, named once. Shared by both model answers because they are the SAME duties —
# only the date they bite on differs.
_GPAI_DUTIES = (
    "Its provider owes Art. 53 — technical documentation to the minimum of Annex XI, information "
    "to downstream providers who build on the model, a policy to comply with Union copyright law, "
    "and a publicly available summary of the training content. Where the model carries SYSTEMIC "
    "RISK, Art. 55 adds model evaluation, adversarial testing, serious-incident reporting to the "
    "AI Office and cybersecurity protection. Systemic risk is presumed above 10^25 cumulative "
    "training FLOP (Art. 51(2)), and Art. 52 requires the provider to notify the Commission within "
    "two weeks of meeting or foreseeing that threshold. Art. 52(6) requires the Commission to "
    "publish and maintain a list of general-purpose AI models with systemic risk; that list is the "
    "authoritative answer, and at the time of writing it does not appear to be published, so its "
    "absence is not evidence that a model is unlisted. "
    "This verdict is about the MODEL only. A system built on a general-purpose model is an "
    "ordinary AI system (Art. 3(66)) and should be submitted separately — it may well be high-risk."
)

# What a GPAI verdict SAYS. A handover, in the same shape as `_handover` for Art. 6(1)(b): name the
# regime, say plainly that this tool does not apply it, and point the reader at what to read. The
# alternative was `minimal`, which told a foundation-model provider they owed almost nothing.
#
# The dates are load-bearing in BOTH branches, for opposite reasons. Chapter V has applied since
# 2 August 2025 (Art. 113(b)), so a placed model's duties are the only ones in this tool's field of
# view that are live TODAY — every high-risk rule waits until 2 August 2026. And a PRE-MARKET model
# is excluded by Art. 3(63) and Art. 2(8) only until it ships, which is a deadline rather than a
# clearance. Reporting the second as "outside scope" full stop would be true this morning and
# misleading by the time anyone acted on it.
_GPAI_PLACED = (
    "This describes a GENERAL-PURPOSE AI MODEL (Art. 3(63)), not an AI system. Article 6 does not "
    "classify it and it has no risk tier: it is governed instead by Chapter V, which this tool "
    f"does not assess. {_GPAI_DUTIES} "
    "NOTE THE DATE: Chapter V has applied since 2 August 2025 (Art. 113(b)), earlier than the "
    "high-risk obligations this tool does model, which apply from 2 August 2026. These duties are "
    "live now."
)

_GPAI_PRE_MARKET = (
    "This describes a GENERAL-PURPOSE AI MODEL (Art. 3(63)) that has NOT YET been placed on the "
    "market. Article 6 does not classify it and it has no risk tier. Art. 3(63) excludes models "
    "used for research, development or prototyping before they are placed on the market, and "
    "Art. 2(8) excludes the development activity itself — so nothing is owed under this Regulation "
    "TODAY. "
    "THAT IS A DEADLINE, NOT A CLEARANCE. Both exclusions end the moment the model is placed on "
    "the market or put into service, and Chapter V has been in application since 2 August 2025 "
    "(Art. 113(b)) — so the duties below attach on the day it ships, with no transition period to "
    f"prepare in. They are worth building toward now rather than discovering then. {_GPAI_DUTIES} "
    "Note also Art. 2(8)'s own limit: testing in REAL-WORLD CONDITIONS is not covered by that "
    "exclusion, so a live pilot may already have taken this outside it."
)


def _gpai_status(state: GraphState) -> GpaiStatus | None:
    """The Art. 3(63) answer, narrowed by TYPE for the reason `_scope_exclusion` is: only a
    recognised member is a finding, and an unrecognised one must not divert a system off the risk
    cascade on the strength of a value nobody can cite."""
    a = state.gpai_model
    return a.value if a is not None and isinstance(a.value, GpaiStatus) else None


def _gpai_handover(status: GpaiStatus) -> str:
    if status is GpaiStatus.GENERAL_PURPOSE_MODEL_PRE_MARKET:
        return _GPAI_PRE_MARKET
    return _GPAI_PLACED


def _rules_out_the_union(state: GraphState) -> bool:
    """Whether Art. 2(1) was answered as reaching the system nowhere.

    Narrowed by TYPE, exactly as `_scope_exclusion` is, and for the same reason: only the explicit
    `OUTSIDE_UNION` member clears a system. A missing answer, a bare `None`, an unrecognised string
    — anything that is not that finding leaves the Regulation applying. Over-inclusion is
    recoverable; a silent clearance is not."""
    a = state.territorial_link
    return (
        a is not None
        and isinstance(a.value, TerritorialLink)
        and a.value.rules_out_the_union
    )


def _decide_tier(state: GraphState) -> tuple[RiskClass, str, list[ClassificationEvidence]]:
    """Derive the risk class from whatever nodes were answered. Order encodes the cascade:
    abstention first, then Art. 2 scope, then prohibition, then the Annex III / profiling /
    derogation logic.

    Returns EVIDENCE, not bare citations: the deciding node's answer travels out whole, so the
    verdict names both the provision and the words in the documentation that triggered it."""
    evidence = ClassificationEvidence.from_answer
    answers = _get_answers(state)
    low_confidence = [a for a in answers if a.confidence == "low"]
    if low_confidence:
        return (
            RiskClass.NEEDS_REVIEW,
            _why_it_could_not_decide(
                low_confidence,
                state.in_annex_i.value if state.in_annex_i else None,
            ),
            [evidence(a) for a in low_confidence],
        )
    if state.is_ai_system and state.is_ai_system.value is not True:
        return (
            RiskClass.MINIMAL,
            "Not an AI system within Art. 3(1); outside the Regulation's risk tiers.",
            [evidence(state.is_ai_system)],
        )
    # Art. 2(1) before every exclusion: paragraphs (3)-(12) carve out of a Regulation that already
    # applies, so a system it never reached is not "excluded" — it was outside from the start, and
    # the citation must say 2(1) rather than borrow an exclusion's paragraph.
    if _rules_out_the_union(state):
        return (
            RiskClass.OUT_OF_SCOPE,
            "Art. 2(1) does not reach this system: it is not placed on the market or put into "
            "service in the Union, has no deployer here, its output is not used here, and the "
            "persons it is used on are not here. The Regulation never applies, so no exclusion is "
            "needed and nothing under it is owed.",
            # `_rules_out_the_union` is true only when the answer exists, so the guard is for the
            # type checker rather than for a reachable state.
            [evidence(state.territorial_link)] if state.territorial_link else [],
        )
    excluded = _scope_exclusion(state)
    # WHAT it is, before whether it is excluded. A general-purpose model still in development is
    # excluded by Art. 2(8) AND outside Art. 3(63) — both temporarily — and reporting only the
    # exclusion would tell the one reader who most needs Chapter V that nothing is owed. So the
    # Art. 3(63) answer is read first and the handover carries the date instead.
    gpai = _gpai_status(state)
    if gpai is not None and gpai.is_a_model:
        pre_market = (
            gpai is GpaiStatus.GENERAL_PURPOSE_MODEL_PRE_MARKET
            or excluded is ScopeExclusion.PRE_MARKET_DEVELOPMENT
        )
        status = GpaiStatus.GENERAL_PURPOSE_MODEL_PRE_MARKET if pre_market else gpai
        # `_gpai_status` returns a member only when the answer exists; the guard is for the
        # type checker rather than for a reachable state.
        return (
            RiskClass.GPAI_MODEL,
            _gpai_handover(status),
            [evidence(state.gpai_model)] if state.gpai_model else [],
        )
    # Art. 2(12) and Art. 2(8) are settled at the END: see _FALL_THROUGH_EXCLUSIONS. Art. 2(12)
    # because its carve-back names questions the cascade has yet to answer, Art. 2(8) because it is
    # temporal and the reader needs to know what attaches on placing. Every other exclusion is
    # unconditional on the facts of the system and concludes here.
    if excluded is not None and excluded not in _FALL_THROUGH_EXCLUSIONS:
        return (
            RiskClass.OUT_OF_SCOPE,
            f"Art. 2({excluded.paragraph}) withholds this Regulation from the system; no risk tier "
            f"is reached and nothing under this Regulation is owed.",
            (
                [_scope_evidence(state.scope_exclusion, excluded)]
                if state.scope_exclusion
                else []
            ),
        )
    if excluded is ScopeExclusion.PRE_MARKET_DEVELOPMENT:
        return (
            RiskClass.OUT_OF_SCOPE,
            "Art. 2(8) withholds this Regulation from research, testing and development activity "
            "before the system is placed on the market or put into service, so nothing is owed "
            "TODAY. That is a deadline, not a clearance: the exclusion ends on placing, and the "
            "obligations that then attach depend on the risk class the system will carry — which "
            "this assessment has not computed, because the exclusion applies now. Re-run it as the "
            "system it will be sold as. Note too that Art. 2(8) does not cover testing in "
            "REAL-WORLD CONDITIONS (Art. 3(57)), so a live pilot may already be outside it.",
            (
                [_scope_evidence(state.scope_exclusion, excluded)]
                if state.scope_exclusion
                else []
            ),
        )
    if state.prohibited is not None and state.prohibited.value is not None:
        practice = state.prohibited.value
        if not isinstance(practice, ProhibitedPractice):
            # A ban this tool cannot cite is one a provider cannot check or contest, and the class
            # carries the heaviest consequence there is. Declining beats both directions of guess:
            # naming a point nobody chose, and clearing a system that was called prohibited.
            return (
                RiskClass.NEEDS_REVIEW,
                "Art. 5 was answered as engaged, but no point of Art. 5(1) was named. A "
                "prohibition that cannot cite its point cannot be reported as one; escalate to a "
                "human reviewer.",
                [evidence(state.prohibited)],
            )
        pinpointed = ClassificationEvidence.from_answer(state.prohibited)
        pinpointed = pinpointed.model_copy(
            update={"source": pinpointed.source.model_copy(update={"paragraph": "1"})}
        )
        return (
            RiskClass.PROHIBITED,
            f"Prohibited practice under Art. 5(1)({practice.point}); evaluated before high-risk "
            f"classification. The system may not be placed on the market, put into service or "
            f"used at all.",
            [pinpointed],
        )
    if (
        state.in_annex_i
        and state.in_annex_i.value is not None
        and state.third_party_assessment
        and state.third_party_assessment.value is True
    ):
        # Art. 6(1) is the FIRST door into high-risk and it is independent of Annex III: both
        # conditions met means high-risk whatever Art. 6(2) would have said, and the Art. 6(3)
        # derogations never apply — they derogate from paragraph 2 alone.
        product = state.in_annex_i.value
        section = f"Annex I Section {product.section}"
        return (
            RiskClass.HIGH_RISK,
            f"Safety component of a product covered by {section} ({product.value}) that requires "
            f"third-party conformity assessment; high-risk under Art. 6(1).",
            [evidence(a) for a in (state.in_annex_i, state.third_party_assessment) if a],
        )
    if state.in_annex_iii and state.in_annex_iii.value is None:
        return (
            RiskClass.MINIMAL,
            "Falls within no Annex III high-risk area (Art. 6(2)); minimal risk.",
            [evidence(state.in_annex_iii)],
        )
    if state.performs_profiling and state.performs_profiling.value is True:
        # The carve-back is driven by profiling, but it only bites because the use case is in
        # Annex III — cite both, each with its own evidence.
        triggers = [state.in_annex_iii, state.performs_profiling]
        return (
            RiskClass.HIGH_RISK,
            "Performs profiling of natural persons; Art. 6(3) makes it high-risk "
            "notwithstanding any derogation.",
            [evidence(a) for a in triggers if a is not None],
        )
    if state.derogation is not None:
        if state.derogation.value is None:
            return (
                RiskClass.HIGH_RISK,
                "Within an Annex III area and no Art. 6(3)(a)-(d) condition is met; high-risk.",
                [evidence(state.in_annex_iii)] if state.in_annex_iii else [],
            )
        # Both limbs of Art. 6(3) now, and only the pair exempts. A condition alone does not: the
        # paragraph opens by requiring that the system pose no significant risk of harm, and the
        # conditions are what let that opening apply. So the exemption is granted on an explicit
        # `false` and on nothing else — a missing answer falls to the terminal below rather than
        # clearing a system by silence.
        risk = state.poses_significant_risk
        if risk is not None and risk.value is True:
            return (
                RiskClass.HIGH_RISK,
                f"Within an Annex III area and an Art. 6(3)({_condition_letter(state)}) condition "
                f"is met, but the system still poses a significant risk of harm — it materially "
                f"influences the outcome of decision making, so the derogation does not apply; "
                f"high-risk.",
                [evidence(a) for a in (state.in_annex_iii, risk) if a is not None],
            )
        if risk is not None and risk.value is False:
            return (
                RiskClass.NOT_HIGH_RISK,
                "Within an Annex III area, but an Art. 6(3) derogation applies: a condition under "
                "(a)-(d) is met and the system poses no significant risk of harm. Not high-risk. "
                "Art. 6(4) documentation still a must.",
                [evidence(a) for a in (state.derogation, risk) if a is not None],
            )
    return (
        RiskClass.NEEDS_REVIEW,
        "The cascade did not reach a defensible terminal; escalate to a human reviewer.",
        [],
    )


# The Art. 2(12) exceptions, as risk classes. A free and open-source release is excluded UNLESS it
# is placed on the market or put into service AS a high-risk system, or as one falling under Art. 5
# or Art. 50 — so these two tiers, and only these two, leave the exclusion standing. NOT_HIGH_RISK
# is deliberately among them: Art. 6(3) means the system is not high-risk, which is what the
# paragraph asks. NEEDS_REVIEW is deliberately not: an unresolved cascade cannot establish that the
# exceptions are absent, and silence is not evidence of absence.
_OPEN_SOURCE_SURVIVES = frozenset({RiskClass.MINIMAL, RiskClass.NOT_HIGH_RISK})


def decide_risk_class(
    state: GraphState, transparency: Answer | None = None
) -> tuple[RiskClass, str, list[ClassificationEvidence]]:
    """The tier, with the Art. 2(12) carve-back settled last.

    Art. 2(12) is the one exclusion whose condition is not a fact about the system in isolation: it
    is lifted where the release is high-risk, an Art. 5 practice, or subject to Art. 50. Those are
    the very questions the rest of the cascade answers, so the open-source answer falls THROUGH the
    cascade and is resolved here, against real answers, rather than being judged a second time by
    the scope node against a second copy of Arts. 5 and 50. One judgement, one place to be wrong.

    `transparency` is passed in because `assemble` answers it beside this call. It is not an input
    to the tier — it is read for this carve-back alone."""
    outcome = _decide_tier(state)
    answer = state.scope_exclusion
    if answer is None or _scope_exclusion(state) is not ScopeExclusion.FREE_OPEN_SOURCE:
        return outcome

    risk_class, _, _ = outcome
    # Any duty lifts the exclusion. Art. 2(12) asks whether the system "falls under Art. 50", not
    # whose duty it is — a deployer-side duty under 50(3) takes the release out of the exclusion
    # exactly as a provider-side one under 50(1) does.
    owes_transparency = transparency is not None and bool(transparency.value)
    if risk_class not in _OPEN_SOURCE_SURVIVES or owes_transparency:
        return outcome

    return (
        RiskClass.OUT_OF_SCOPE,
        "Released under a free and open-source licence and Art. 2(12) applies: it is not placed on "
        "the market as a high-risk system, is no Art. 5 practice, and owes no Art. 50 obligation. "
        "Nothing under this Regulation is owed.",
        [_scope_evidence(answer, ScopeExclusion.FREE_OPEN_SOURCE)],
    )


# --- routing ------------------------------------------------------------------------------------
# Each routing function runs right after its node, so `a` is set — but we guard `a is None`
# anyway: it satisfies the type checker and defensively routes an impossible missing answer to
# `assemble` (which yields needs_review) rather than crashing.
def _route_is_ai(state: GraphState) -> str:
    a = state.is_ai_system
    return (
        "assemble" if a is None or _is_low_confidence(a) or a.value is not True else "territorial"
    )


def _route_territorial(state: GraphState) -> str:
    """Art. 2(1) reaches the system, or it does not. Only an explicit `outside_union` finding ends
    the assessment; every other answer — a named limb, or the record that territory went
    unaddressed — continues it, and so does an unrecognised one."""
    a = state.territorial_link
    if a is None or _is_low_confidence(a):
        return "assemble"
    return "assemble" if _rules_out_the_union(state) else "scope"


def _route_scope(state: GraphState) -> str:
    """An Art. 2 exclusion ends the assessment — except Art. 2(12), which cannot be settled until
    the cascade has answered the questions its own exceptions name (high-risk, Art. 5, Art. 50).
    So an open-source answer continues, and `decide_risk_class` resolves it at the end."""
    a = state.scope_exclusion
    if a is None or _is_low_confidence(a):
        return "assemble"
    excluded = _scope_exclusion(state)
    if excluded is None or excluded in _FALL_THROUGH_EXCLUSIONS:
        return "gpai_model"
    return "assemble"


def _route_gpai(state: GraphState) -> str:
    """A general-purpose AI model leaves the risk cascade entirely: Art. 6 does not classify it, so
    every question after this one is a category error for it. Anything else — including a system
    built ON such a model, which Art. 3(66) makes an ordinary AI system — carries on."""
    a = state.gpai_model
    if a is None or _is_low_confidence(a):
        return "assemble"
    status = _gpai_status(state)
    if status is not None and status.is_a_model:
        return "assemble"
    # Art. 2(8) fell through to THIS question and no further. It is asked because a pre-market
    # general-purpose model needs its Chapter V duties named and dated rather than an exclusion;
    # once the answer is "an AI system", the exclusion concludes and running the Art. 6 track would
    # compute a tier for a system the Regulation does not currently govern.
    if _scope_exclusion(state) is ScopeExclusion.PRE_MARKET_DEVELOPMENT:
        return "assemble"
    return "prohibited"


_FALL_THROUGH_EXCLUSIONS = frozenset(
    {ScopeExclusion.FREE_OPEN_SOURCE, ScopeExclusion.PRE_MARKET_DEVELOPMENT}
)
"""Exclusions that do NOT conclude the assessment, for two different reasons.

Art. 2(12) falls through because its own carve-back names high-risk, Art. 5 and Art. 50 — questions
the rest of the cascade answers, so the exclusion cannot be settled until they are.

Art. 2(8) falls through because it is TEMPORAL. A model still in development is excluded today and
governed the day it ships, and the reader who most needs to know what Chapter V will demand is
exactly the one still building. Exiting here would report "outside scope, nothing owed" and stop,
which is true this morning and misleading by the time anyone acts on it. So the cascade carries on
to the Art. 3(63) question and finds out WHAT is being built before saying anything."""


def _route_prohibited(state: GraphState) -> str:
    """Any answer other than a clean `none` ends the cascade. A named point is a prohibition; an
    unrecognised value is a brain claiming one it cannot cite, which `_decide_tier` turns into
    needs_review rather than into either a ban or a clearance."""
    a = state.prohibited
    if a is None or _is_low_confidence(a):
        return "assemble"
    return "annex_i" if a.value is None else "assemble"


def _route_annex_i(state: GraphState) -> str:
    """No Annex I product means Art. 6(1) cannot apply; go straight to the Annex III route."""
    a = state.in_annex_i
    if a is None or _is_low_confidence(a):
        return "assemble"
    return "annex_iii" if a.value is None else "third_party_assessment"


def _route_third_party(state: GraphState) -> str:
    """Art. 6(1) needs BOTH conditions. Failing (b) is not an exit — a self-assessed product can
    still be high-risk under Annex III, so the cascade continues rather than concluding."""
    a = state.third_party_assessment
    if a is None or _is_low_confidence(a):
        return "assemble"
    return "assemble" if a.value is True else "annex_iii"


def _route_annex(state: GraphState) -> str:
    a = state.in_annex_iii
    if a is None or _is_low_confidence(a):
        return "assemble"
    return "assemble" if a.value is None else "profiling"


def _route_profiling(state: GraphState) -> str:
    a = state.performs_profiling
    return "assemble" if a is None or _is_low_confidence(a) or a.value is True else "derogation"


def _route_derogation(state: GraphState) -> str:
    """Art. 6(3) needs BOTH limbs, so a condition under (a)-(d) opens the second question rather
    than concluding. No condition ends it: the first subparagraph cannot apply at all, and the
    system is high-risk however small a risk it poses."""
    a = state.derogation
    if a is None or _is_low_confidence(a) or a.value is None:
        return "assemble"
    return "significant_risk"


def build_graph(
    brain: Brain,
    questions: dict[str, Question] | None = None,
):
    """Compile the cascade around a given brain.

    `questions` defaults to the context-free QUESTIONS. Pass `load_questions()` to anchor every
    question in the verbatim article/annex text — which any brain that actually reads the law
    should do."""
    asked = questions if questions is not None else QUESTIONS

    def _ask(node_id: str, description: str) -> Answer:
        question = asked[node_id]
        answer = brain.decide(question, description)
        # Record the non-binding guidance that was in context for this node onto the answer, so it
        # travels to the verdict. Done HERE, in the graph, not in each brain: it is bookkeeping
        # about what the question carried, not part of answering — so every brain gets it for free
        # and none needs to know guidance exists.
        # ...but NOT onto an abstention. A node that declined did not rest on the guidance — it
        # rested on nothing — and `rests_on_guidance` would then warn a reader that a verdict leaned
        # on Commission interpretation when no verdict was reached at all.
        declined = answer.abstained_because is not None
        if question.guidance_sources and not answer.guidance_sources and not declined:
            return answer.model_copy(update={"guidance_sources": list(question.guidance_sources)})
        return answer

    def node_is_ai(state: GraphState) -> dict[str, Any]:
        return {"is_ai_system": _ask("is_ai", state.description)}

    def node_territorial(state: GraphState) -> dict[str, Any]:
        return {"territorial_link": _ask("territorial", state.description)}

    def node_scope(state: GraphState) -> dict[str, Any]:
        return {"scope_exclusion": _ask("scope", state.description)}

    def node_gpai(state: GraphState) -> dict[str, Any]:
        return {"gpai_model": _ask("gpai_model", state.description)}

    def node_prohibited(state: GraphState) -> dict[str, Any]:
        return {"prohibited": _ask("prohibited", state.description)}

    def node_annex(state: GraphState) -> dict[str, Any]:
        return {"in_annex_iii": _ask("annex_iii", state.description)}

    def node_profiling(state: GraphState) -> dict[str, Any]:
        return {"performs_profiling": _ask("profiling", state.description)}

    def node_annex_i(state: GraphState) -> dict[str, Any]:
        return {"in_annex_i": _ask("annex_i", state.description)}

    def node_third_party(state: GraphState) -> dict[str, Any]:
        return {"third_party_assessment": _ask("third_party_assessment", state.description)}

    def node_derogation(state: GraphState) -> dict[str, Any]:
        return {"derogation": _ask("derogation", state.description)}

    def node_significant_risk(state: GraphState) -> dict[str, Any]:
        return {"poses_significant_risk": _ask("significant_risk", state.description)}

    def node_assemble(state: GraphState) -> dict[str, Any]:
        # Art. 50 runs HERE, unconditionally. Every path through the cascade reaches `assemble`,
        # so asking it here — and nowhere else — is what makes transparency independent of the
        # risk tier: it is answered for a minimal generator and a high-risk chatbot alike, and it
        # never routes anything. It is an output beside the risk class, not an input to it.
        transparency = _ask("transparency", state.description)

        risk_class, reasoning, triggered_by = decide_risk_class(state, transparency)
        confidence: Confidence = (
            "low" if any(a.confidence == "low" for a in _get_answers(state)) else "high"
        )
        use_case = UseCaseClassification(
            use_case_id=state.use_case_id,
            description=state.description,
            annex_i_product=state.in_annex_i.value if state.in_annex_i else None,
            third_party_assessment=state.third_party_assessment,
            annex_iii_area=state.in_annex_iii.value if state.in_annex_iii else None,
            performs_profiling=state.performs_profiling,
            derogation=state.derogation,
            poses_significant_risk=state.poses_significant_risk,
            risk_class=risk_class,
            triggered_by=triggered_by,
            reasoning=reasoning,
            confidence=confidence,
        )
        result = ClassificationResult(
            use_cases=[use_case],
            overall_risk_class=risk_class,
            reasoning=reasoning,
            triggered_by=triggered_by,
            confidence=confidence,
            transparency=transparency,
            # `transparency` is answered in this node, so it is not on the state yet — passed in
            # explicitly rather than read back, the same reason decide_risk_class takes it.
            answers=[*_every_answer(state), transparency],
        )
        return {"result": result, "transparency": transparency}

    g = StateGraph(GraphState)
    g.add_node("is_ai", node_is_ai)
    g.add_node("territorial", node_territorial)
    g.add_node("scope", node_scope)
    g.add_node("gpai_model", node_gpai)
    g.add_node("prohibited", node_prohibited)
    g.add_node("annex_i", node_annex_i)
    g.add_node("third_party_assessment", node_third_party)
    g.add_node("annex_iii", node_annex)
    g.add_node("profiling", node_profiling)
    g.add_node("derogation", node_derogation)
    g.add_node("significant_risk", node_significant_risk)
    g.add_node("assemble", node_assemble)

    g.add_edge(START, "is_ai")
    g.add_conditional_edges(
        "is_ai", _route_is_ai, {"territorial": "territorial", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "territorial", _route_territorial, {"scope": "scope", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "scope", _route_scope, {"gpai_model": "gpai_model", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "gpai_model", _route_gpai, {"prohibited": "prohibited", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "prohibited", _route_prohibited, {"annex_i": "annex_i", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "annex_i",
        _route_annex_i,
        {
            "third_party_assessment": "third_party_assessment",
            "annex_iii": "annex_iii",
            "assemble": "assemble",
        },
    )
    g.add_conditional_edges(
        "third_party_assessment",
        _route_third_party,
        {"annex_iii": "annex_iii", "assemble": "assemble"},
    )
    g.add_conditional_edges(
        "annex_iii",
        _route_annex,
        {"profiling": "profiling", "assemble": "assemble"},
    )
    g.add_conditional_edges(
        "profiling", _route_profiling, {"derogation": "derogation", "assemble": "assemble"}
    )
    g.add_conditional_edges(
        "derogation",
        _route_derogation,
        {"significant_risk": "significant_risk", "assemble": "assemble"},
    )
    g.add_edge("significant_risk", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


_ROUTERS = {
    "is_ai": _route_is_ai,
    "territorial": _route_territorial,
    "scope": _route_scope,
    "gpai_model": _route_gpai,
    "prohibited": _route_prohibited,
    "annex_i": _route_annex_i,
    "third_party_assessment": _route_third_party,
    "annex_iii": _route_annex,
    "profiling": _route_profiling,
    "derogation": _route_derogation,
}
_STATE_FIELD = {
    "is_ai": "is_ai_system",
    "territorial": "territorial_link",
    "scope": "scope_exclusion",
    "gpai_model": "gpai_model",
    "prohibited": "prohibited",
    "annex_i": "in_annex_i",
    "third_party_assessment": "third_party_assessment",
    "annex_iii": "in_annex_iii",
    "profiling": "performs_profiling",
    "derogation": "derogation",
    "significant_risk": "poses_significant_risk",
}


def route_for(answers: dict[str, Any]) -> list[str]:
    """Which nodes the cascade reaches if every question is answered as `answers` says.

    Walks the SAME `_route_*` functions the compiled graph uses, over a state built from those
    answers — never a second copy of the routing rules. A separate implementation would drift from
    the cascade silently, and it is the cascade's exits that carry the legal argument (Art. 6(1)
    failing condition (b) falls through to Annex III rather than concluding).

    `answers` maps node_id to the VALUE that node would report; a node absent from it is treated as
    unanswered, which ends the walk there. `transparency` is never in the result: it is asked in
    `assemble`, off this path, on every route.

    Used by the golden-set loader to check that a case pins exactly the nodes its own answers would
    reach — see `aiact.eval.classification_cases`."""
    state = GraphState(description="")
    for node_id, value in answers.items():
        field = _STATE_FIELD.get(node_id)
        if field is not None:
            setattr(
                state,
                field,
                Answer(
                    value=value, reasoning="", confidence="high", source=_src(6), node_id=node_id
                ),
            )

    reached: list[str] = []
    node = "is_ai"
    while node != "assemble":
        reached.append(node)
        router = _ROUTERS.get(node)
        # A node with no router runs straight into `assemble` — it is the end of the walk, and is
        # included because it was reached. `significant_risk` is the only one today.
        if router is None:
            break
        node = router(state)
    return reached


def classify(
    description: str,
    brain: Brain,
    use_case_id: str = "use_case",
    questions: dict[str, Question] | None = None,
) -> ClassificationResult:
    """Run the cascade on one use-case description and return its ClassificationResult."""
    compiled_graph = build_graph(brain, questions)
    # One trace per run, grouping each node's LLM call as a span — the decision path, made visible
    # in Langfuse. A strict no-op without keys (and for the deterministic ScriptedBrain, which makes
    # no LLM calls to trace); see aiact.tracing.
    with trace_run(f"classify:{use_case_id}", session_id=use_case_id):
        out = compiled_graph.invoke(GraphState(description=description, use_case_id=use_case_id))
    result = out["result"] if isinstance(out, dict) else out.result
    if result is None:
        raise RuntimeError("classification graph produced no result")
    return result
