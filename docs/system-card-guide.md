# How to write a system card that can be classified

> **Not legal advice.** This guide, and the tool it accompanies, produce a draft checklist for
> review by a qualified professional. Nothing here is the assessment or official position of the
> European Commission or any other authority.

This tool reads a description of your AI system and does two things. It works out the system's risk
class under Regulation (EU) 2024/1689. Then it lists the obligations that follow, and checks the
ones a document can show against what you wrote. It can only answer from what you write. If a fact
is missing, the honest answer is "needs review" — and this guide exists so you get a verdict
instead.

**A short card is enough for the classification.** Sections 1–11 cover what it needs. **The
obligations check reads more.** For a high-risk system it looks for your risk management, data
governance, logging, instructions for use, human oversight and accuracy measures — section 12. A
card without them still gets a report, but those obligations show as gaps. You can paste a card,
your technical documentation (Annex IV), or both together.

---

## Read this first: leaving something out does not make it go away

The single fact that most often decides the risk class — *does the system evaluate people?* — is
also the one most often left out of product descriptions. It is easy to describe a tool as
"streamlines hiring" and never mention that it ranks candidates.

If you omit it, one of two things happens, and both are bad for you:

- The tool says **needs review**, and you have learned nothing.
- Or worse, a reader assumes the benign reading, and you get a comfortable classification that
  **has no legal effect whatsoever.** Your obligations follow from what the system does, not from
  what your documentation says it does. A market surveillance authority will look at the system.

Write down the awkward parts. A high-risk classification is a manageable compliance workload; an
undocumented high-risk system is an enforcement problem.

## Three rules that matter more than the format

**1. Describe function, not benefit.** "Reduces time-to-hire by 70%" tells a classifier nothing.
"Computes a 0–100 fit score for each applicant against the role" decides the case.

**2. One section per intended purpose, not per product.** The Act classifies each *intended
purpose* separately, and one product often holds several classifications at once. A tool that parses
CVs, scores candidates, and drafts job adverts is three use cases in three different tiers. Merging
them produces one wrong answer instead of three right ones.

**3. Say what the system does *not* do.** Unusual for a product document, essential here. The
Art. 6(3) exemptions turn on absence — "extracts fields and does not score, rank or evaluate
candidates" is a claim the tool can act on. Silence is not. And silence is not a denial: a
description that never mentions scoring is not a description of a system that does not score.

---

## What to write, question by question

Each section answers one question the classifier asks, and cites the provision it comes from.

### 1. Is it an AI system? — Art. 3(1)

State how the system produces its outputs: does it **infer** them from input (a trained model,
statistics, machine learning), or does it follow rules a person wrote out? Both are fine answers;
what matters is that you say which. Name the technique if you can.

> *"A gradient-boosted model trained on historical application outcomes."*
> *"A rules engine; thresholds are configured by the customer and no model is involved."*

### 2. Does the Act reach it at all? — Art. 2

Two short facts. Both are usually left out, and when they are, the tool assumes the Act applies.

**Where it is used.** Say whether the system is sold or deployed in the EU, whether its output is
used there, or whether the people it is used on are there (Art. 2(1)). Where your company is based
does not settle this: a non-EU provider selling into the EU is covered.

**Whether an exclusion applies.** Art. 2 takes a few systems out, and each one is narrow:

- used **only** for military, defence or national security purposes (2(3)) — dual use stays in, and
  policing or border control is not national security
- developed and put into service **only** for scientific research (2(6))
- still in research, testing or development, and not yet placed on the market (2(8)) — testing in
  real-world conditions is not covered
- used by a person for a **purely personal**, non-professional activity (2(10)) — this frees that
  person, never the provider
- released under a free and open-source licence (2(12)) — this does not help a high-risk,
  prohibited or Art. 50 system

If none fits, you need not say anything. If one does, say which one and why.

### 3. Is it a prohibited practice? — Art. 5

Say explicitly whether the system does any of the following, because these are banned outright:

- (a) uses subliminal, manipulative or deceptive techniques, or (b) exploits vulnerability due to
  age, disability or social or economic situation
- (ba) generates or manipulates **realistic intimate imagery** of an identifiable person without
  their consent, or (bb) **child sexual abuse material** — both added by Regulation (EU) 2026/1744
  and applying from **2 December 2026**
- (c) scores people's **social behaviour** or personal traits, leading to detrimental treatment
- (d) predicts the risk that a person **commits a crime**, based solely on profiling or personality
  traits
- (e) builds or expands **facial recognition databases** by untargeted scraping of images from the
  internet or CCTV
- (f) infers **emotions** of people at work or in education — including during recruitment, which
  the Commission reads as part of "workplace"
- (g) categorises people **biometrically** to infer race, political opinions, trade union
  membership, religion, sex life or sexual orientation
- (h) runs **real-time remote biometric identification** in publicly accessible spaces for law
  enforcement

If it processes faces, voices, or video of people, say what it extracts from them. "Analyses video
interviews" is ambiguous in the way that matters most.

**If it generates images, video or audio of people, the safeguards are the answer.** Art. 5(1)(ba)
and (bb) do not ban a generator for being *capable* of producing that material — Art. 5(1a) catches
a provider only where producing it is the system's intended purpose, or where it is a reasonably
foreseeable and reproducible output **and** there are no reasonable safeguards against it. So the
card should say what those safeguards are: filtering, refusal training, output classification,
misuse detection, and how reported misuse gets corrected. A general-purpose generator whose card
describes none of that is closer to the second limb than its authors probably intend.

### 4. Is it part of a regulated product? — Art. 6(1), Annex I

The other way into high-risk, separate from the use-case list in section 5. It applies where the
system is a **safety component** of a product covered by an EU product law listed in Annex I —
machinery, medical devices, toys, lifts, radio equipment, vehicles and others — or is such a product
itself. A safety component either protects health and safety, or could endanger people or property
if it fails (Art. 3(14)).

Say two things:

- **which product, and which law** — name the instrument, e.g. Regulation (EU) 2017/745 on medical
  devices. For machinery, say whether the product is placed on the market under Directive 2006/42/EC
  or Regulation (EU) 2023/1230.
- **who assesses the product's conformity** under that law — a notified body, or the manufacturer
  itself. Only a notified body makes the system high-risk (Art. 6(1)(b)). The tool does not work
  this out from the type of product: if you don't say it, the answer is "needs review".

Software that only serves convenience, efficiency, user assistance or quality control is not a
safety component (Art. 6(1a)) — unless its failure could still endanger health or safety
(Art. 6(1b)). If the system is not part of a physical product, say so in one line.

### 5. What is it used for? — Art. 6(2), Annex III

State the **intended purpose** in terms of the sector and the decision it supports. The eight
high-risk areas are biometrics, critical infrastructure, education, **employment**, essential
services, law enforcement, migration, and justice/democracy.

Employment (Annex III(4)) covers recruitment and selection — placing targeted job adverts, filtering
applications, evaluating candidates — and decisions on promotion, termination, task allocation and
performance monitoring.

Biometrics (Annex III(1)) is the one area with a boundary inside it, and the card decides which side
you land on. If the system matches faces, voices or fingerprints, **say which direction the match
runs**:

- **one against that same person's own stored record**, to confirm they are who they claim to be —
  verification, and Annex III(1)(a) excludes it in terms
- **one against a gallery of many**, to establish who someone is — remote identification, and
  squarely in the area

"Uses facial recognition" does not distinguish them, and the exclusion is only for systems whose
**sole** purpose is that confirmation: if it also searches for unknown people or infers anything
about them, the exclusion is gone. Say whether a gallery exists and what is in it.

Name who is affected: applicants, employees, students, patients, the public.

### 6. Does it evaluate people? — Art. 6(3)

**The decisive question.** State plainly whether the system scores, ranks, rates, matches, filters or
otherwise evaluates natural persons — **and on what basis**.

"Sorts applications" is not enough. Sorting by submission time evaluates nobody. Sorting by predicted
fit evaluates everybody, and under the Art. 6(3) profiling carve-back that makes the system
high-risk **regardless of any exemption below**. Say which one you do.

> *"Applications are ordered by submission time; no model scores the candidate."*
> *"Each applicant receives a 0–100 fit score against the role; recruiters see a ranked list."*

### 7. Does an exemption apply? — Art. 6(3)(a)–(d), Art. 6(4)

Only reached if the system is in an Annex III area and does **not** evaluate people. Say which of
these fits, and why:

| | condition | typical example |
|---|---|---|
| (a) | narrow procedural task | extracting fields from a document without judging the person |
| (b) | improves a completed human activity | tidying prose a person already wrote |
| (c) | detects decision patterns or deviations | flagging that this year's decisions differ from last year's, without replacing the human assessment |
| (d) | preparatory task to an assessment | file conversion or indexing ahead of a human review |

**A condition is only half of it.** Art. 6(3) also requires that the system poses no significant
risk of harm — including by not materially influencing the decision. So say how the output is used.
If a person reaches the same decision on the same material whether or not the system ran, say so.
If people rely on the output, or it filters or orders people before a human looks at them, the
exemption fails whichever condition fits.

The burden is on you to establish both halves, and Art. 6(4) requires the assessment to be
documented before the system goes to market. The report checks that your document contains it:
which condition you rely on, and why the system poses no significant risk. An exemption you did not
claim is not one you get.

### 8. Does it generate content or talk to people? — Art. 50

Independent of everything above: a minimal-risk system can owe transparency duties and a high-risk
one can owe none. State whether the system:

- **interacts directly** with people — chat, voice, conversational messaging (Art. 50(1))
- **generates** synthetic text, image, audio or video (Art. 50(2))
- is an **emotion recognition or biometric categorisation** system (Art. 50(3)) — note this bites
  even where the system is prohibited under Art. 5
- produces **deep fakes**, or text published to inform the public on matters of public interest
  (Art. 50(4))

The provider's two duties are ones the report checks against your document, so answer the
follow-up too.

- **50(2): say how the output is marked, and how the mark is detected.** Both are required. Name the
  watermarking, provenance or metadata scheme and what it survives, then say how someone else can
  check a file for the mark — a detection tool, an API, a published specification. The paragraph
  asks for a mark software can read without a person, so "outputs are labelled as AI-generated" does
  not reach the duty. A visible label is a welcome extra, not the answer.
- **50(1): say how people are told they are dealing with AI**, inside the interaction itself — an
  opening statement, a persistent label, a spoken line. A notice in the terms of use, or a name like
  "assistant", does not reach them. If children, older people or people with disabilities are likely
  users, say how the notice is adapted. If you rely on the exception for what is obvious to a
  reasonably well-informed person, say so and say why: it is a judgement about the context of use,
  not a default.

### 9. Is it a MODEL rather than a system? — Art. 3(63), and then Chapter V

Everything above classifies an AI **system**. A general-purpose AI **model** is not on that track at
all: Art. 6 does not classify it, it has no risk tier, and Chapter V governs it instead — with
duties that have applied since **2 August 2025**, earlier than every high-risk obligation in this
guide. Say which one you are describing.

The test is **generality**, not size. Art. 3(63) reaches a model that displays significant
generality, performs a wide range of distinct tasks, and can be integrated into downstream systems.
A single-purpose pre-trained model — text-to-speech, demand forecasting, image segmentation — is not
one however large. And a *system* built on someone else's foundation model is an ordinary AI system
(Art. 3(66)), so a chatbot or a hiring tool goes back to the sections above.

If you are describing a model, two more facts decide what you owe, and **the tool will not guess
either of them**. It reads what you state and records "not stated" otherwise — which is honest, and
leaves every Chapter V obligation on your list with the condition attached.

**Does the model carry systemic risk? — Art. 51(1).** This turns the whole of Art. 55 on: model
evaluation with documented adversarial testing, Union-level risk assessment and mitigation,
serious-incident reporting to the AI Office, and cybersecurity for the model *and its physical
infrastructure*. Two limbs settle it, and either is enough:

- a **Commission designation** under Art. 51(1)(b) or Art. 52(4), or an **Art. 52(1) notification**
  you have already made — say so, and say when
- **cumulative training compute above 10^25 floating point operations**, which Art. 51(2) presumes
  to be high impact capabilities — so give the FLOP figure

A parameter count is not a compute figure and the tool will not convert one into the other. If your
compute is below the threshold, say the number anyway: it rules out the presumption, and the report
then says so rather than leaving the question open. It rules out nothing else — the Commission can
designate a model on the Annex XIII criteria at any level of compute.

**Is the release free and open-source, on all four limbs? — Art. 53(2) and Art. 54(6).** This is the
only thing in Chapter V that takes duties *off* you, and it is a conjunction. State every part:

- a licence permitting **access, use, modification AND distribution**
- the **parameters, including the weights**, publicly available
- the information on **model architecture** publicly available
- the information on **model usage** publicly available

"Open-weight" is not this claim, and neither is a licence you name without quoting its terms. Weights
behind an acceptable-use agreement, a request form, a commercial tier or a non-compete are not
publicly available, and a licence that forbids redistribution or caps users is not free and
open-source however it is labelled. Where all four hold, Art. 53(2) lifts the Annex XI technical
documentation and the Annex XII downstream information, and Art. 54(6) lifts the whole of Art. 54.

**Two things it never lifts**, and they catch most people: Art. 53(1)(c), a copyright policy that
identifies and complies with an Art. 4(3) Directive (EU) 2019/790 rights reservation *including
through state-of-the-art technologies*, and Art. 53(1)(d), a publicly available training-content
summary **on the AI Office's template**. Every provider owes both, open-source or not. And the whole
carve-out is **disapplied for a model with systemic risk** — so if the first question above answers
yes, the second one lifts nothing.

### 10. Which organisations are in the chain? — Art. 3(3)–(7), Art. 16(b), Art. 25, Art. 27

Obligations attach to a **role**, not to an organisation. One organisation can hold several, and a
single system usually involves more than one party. Name every party you know of and say what each
one does with the system.

You will be writing from inside one of them. The others still belong in the card: the report covers
every role the Act binds whoever wrote the document, and a party the card names gets a specific
answer where an unnamed one gets a generic one.

| role | what makes an organisation this | Art. |
|---|---|---|
| provider | developed it, or places it on the market under its own name or trademark | 3(3) |
| initial provider | placed it on the market, and then stopped being its provider because Art. 25 moved the role to someone else | 25(2) |
| deployer | uses it under its own authority, in a professional capacity | 3(4) |
| importer | established in the EU, places a third-country entity's system on the market | 3(6) |
| distributor | in the supply chain, makes it available on the EU market | 3(7) |
| authorised representative | mandated by a non-EU provider to act for it in the EU | 3(5) |

Then three facts about those parties that no description of the *system* can supply.

**Give the provider's name and an address that reaches it.** This one is an obligation in its own
right, not background. **Art. 16(b)** requires the provider's name, registered trade name or
registered trade mark, and the address at which it can be contacted, to be indicated **on the
system** — or, where that is not possible, on its packaging or its **accompanying documentation**.

So it is the one Art. 16 point a document can discharge, and the only place a reader can check it is
a document like this one. A trading name with no address does not satisfy it; neither does a website.
Where the details are already on the product itself — a start-up screen, a label, an about box — say
that, and the point is met however the card is worded.

*Two other points of Art. 16 stand alone in the same way, and neither is something you can write
your way out of: **(k)** demonstrating conformity to a national authority on reasoned request, and
**(l)** meeting the accessibility requirements of Directives (EU) 2016/2102 and (EU) 2019/882. The
report lists both and checks neither — (k) is a readiness of your organisation, and (l) is settled by
two instruments this tool does not read.*

**Has the provider role moved along the chain?** Under **Art. 25** a distributor, importer, deployer
or other third party *becomes the provider* — owing Art. 16 in full, not a share of it — where it
puts its own name or trademark on a high-risk system someone else placed on the market,
substantially modifies one, or changes the intended purpose of a system that was not high-risk so
that it becomes high-risk. Art. 25(3) does the same to a product manufacturer shipping bought-in AI
inside its own product.

"Substantially" is narrow and defined: **Art. 3(23)** means a change *not foreseen in the initial
conformity assessment*, affecting Chapter III compliance or the assessed intended purpose.
Configuring a system, tuning it within its documented envelope, or taking the vendor's updates is
not it.

So the card should show **both ends**: who placed the system on the market, and what any later party
does to it. A document that mentions only one party cannot answer this, and a role change is never
inferred from silence. The organisation this catches most often is the one least likely to write it
down — a company that white-labels a vendor's hiring tool is its provider, and will otherwise read
the short deployer column and think it is done.

**And the party that loses the role does not walk away.** Art. 25(2) says the original provider
"shall no longer be considered to be a provider of that specific AI system" — and then binds it
anyway: cooperate with the new provider, and supply the information, the reasonably expected
technical access and the other assistance needed to meet this Regulation, in particular for the
conformity assessment. So the report gives that party a column of its own, the **initial provider**,
and it appears exactly when the card shows the role moving. Two organisations to name, then, not
one: whoever holds the provider role now, and whoever held it before.

The duty falls away in one case, and it is a fact about the supply terms rather than the system: it
does not apply where the initial provider **clearly specified** that its system was not to be turned
into a high-risk one. If your terms say that, say so in the card.

**What kind of organisations are the deployers?** **Art. 27** requires a fundamental rights impact
assessment before first use — covering the deployer's processes, the period and frequency of use,
who is affected, the specific risks, the human oversight measures, and what happens if those risks
materialise. It does not reach every deployer. It binds those that are **bodies governed by public
law or private entities providing public services**, and deployers of **Annex III(5)(b) and (c)**
systems — creditworthiness and credit scoring, and risk assessment and pricing for life and health
insurance.

That turns on what the deploying organisation *is*, so no technical description settles it. A vendor
usually knows the answer for its customer base even though it is not the deployer itself: "sold to
municipalities" and "sold to private recruiters" lead to different obligations, and saying which
resolves the question for everyone reading.

**One line, two duties — and they do not answer alike.** **Art. 49(3)** also turns on this fact:
before putting a high-risk Annex III system into use, a **public authority** deploying it must
register itself, select the system and register its use in the EU database. That is a *separate*
entry from the provider's registration under Art. 49(1), which does not discharge it.

Art. 49(3) is the narrower of the two. Art. 27 reaches bodies governed by public law **and** private
entities providing public services; Art. 49(3) reaches public authorities, Union bodies, and persons
acting on their behalf. So a private company running a state healthcare contract owes the impact
assessment and, on that basis alone, not the registration — though it can still be caught as a
person acting on the authority's behalf, which is a fact about the contract rather than the company.
Worth saying either way if you know it.

**The tool reads this line if you write it.** Say nothing and the report records both conditions as
unresolved — which is honest, and useless. Name the kind of organisation and the report says whether
each Article reaches it. Saying nothing is never read as "commercial, so nothing owed": silence
clears no duty here.

*An existing GDPR data protection impact assessment does not discharge this. Art. 27(4) makes the
fundamental rights assessment complement it.*

### 11. Is it tested live before release, and when was it placed? — Art. 60, Art. 111

**Testing in real-world conditions — Art. 60 and 61.** Say whether the system is, or will be, run
with real people or on live inputs, outside the lab and outside an AI regulatory sandbox, before it
goes on the market — a pilot at a customer site, a live trial. If it is, duties bind **before the
testing starts**: a testing plan approved by the market surveillance authority, registration, and
the informed consent of the people taking part.

If it is not, say that in terms: tested only inside a sandbox, or never run on live inputs outside
the lab. The report then leaves those duties out. A description of offline evaluation — held-out
data, benchmarks — does not answer the question, so the report lists them with their condition
attached.

**The market placement date — Art. 111.** Systems already on the market before certain dates get
more time, and some high-risk systems get relief until they are significantly changed. The tool
does not apply this relief: the report lists every duty and adds a note. Give the date anyway — it
is what lets you and your adviser apply it.

### 12. If it is high-risk: what the report checks in your document — Arts. 9–16

Once a use case is high-risk, the report lists the provider's obligations and checks the ones a
document can show. Each check reads the Article paragraph by paragraph, so a one-line "risks are
managed" is a gap. Describe what you actually do:

| Art. | what to describe |
|---|---|
| 9 | **Risk management.** A process run and updated across the whole lifecycle. The risks to health, safety and fundamental rights you found, including from foreseeable misuse, and the measures you took. Residual risk judged acceptable, per hazard and overall, with the judgement stated. Testing before release against metrics and thresholds set in advance. Effects on people under 18 and other vulnerable groups. |
| 10 | **Data.** Where the training, validation and test data come from, and why they were first collected. How they were prepared — labelling, cleaning. What the data are assumed to measure. Whether there is enough, and whether it represents the people and setting the system will be used on. How bias was examined and mitigated. Known gaps, and how you handle them. |
| 11 | **Technical documentation.** Drawn up to Annex IV before release and kept current. For an Annex I product, one file that covers both this Act and the product's own law (Art. 11(2)). |
| 12 | **Logging.** Events recorded automatically over the system's life — enough to spot risks and substantial modifications, to support post-market monitoring, and to let deployers monitor operation. For remote biometric identification also: the start and end of each use, the reference database, the input that matched, and who verified the result (Art. 12(3)). |
| 13 | **Instructions for use.** Your contact details; the intended purpose; accuracy with its metrics, robustness and cybersecurity; known risks and foreseeable misuse; performance for specific groups; input data specifications; how to read the output; the human oversight measures; computing resources, lifetime and maintenance; how deployers collect and read the logs. |
| 14 | **Human oversight.** Who oversees the system and what they can do: understand its limits, watch for automation bias, interpret the output, decide not to use it, override it, stop it. For remote biometric identification, no action is taken on a match until two trained people have verified it (Art. 14(5)). |
| 15 | **Accuracy, robustness and cybersecurity.** The accuracy metrics you declare. Resilience to errors and faults. For a system that keeps learning, how biased feedback loops are prevented. Defences against data poisoning, model poisoning, adversarial examples, confidentiality attacks and model flaws. |
| 16(b) | **Provider identification.** Name and contact address — see section 10. |

The other obligations the report lists — registration, conformity assessment, quality management,
post-market monitoring, deployer duties — are things an organisation does rather than things a
document shows. They appear under **Check yourself**, with the date each one applies from.

---

## Template

Copy this, fill it in, delete the prompts. One block per intended purpose.

```markdown
# <system name> — system card

**Version / date:**

## Parties

<Name every organisation you know of and what it does with the system. Leave a line out rather
than guess; an unknown party is not the same as no party.>

- **Developed by:** <legal entity>
- **Placed on the market by:** <legal entity, and under whose name or trademark. Give the
  registered name or trade mark and an address that reaches you — Art. 16(b) requires it, and this
  is one of the places it may be given. If the same details are on the system itself or its
  packaging, say so.>
- **Deployed by:** <who uses it under their own authority — a named customer, or the kind of
  organisation it is sold to. For each: body governed by public law | private entity providing
  public services | neither (Art. 27, Art. 49(3)). If a private organisation operates the system
  on a public authority's behalf, say so — that is a separate limb of Art. 49(3).>
- **Importer / distributor / authorised representative:** <where a non-EU provider is involved>
- **Changed after placing?** <Does any later party put its name on it, modify it beyond what the
  original conformity assessment foresaw, or aim it at a new purpose? If so, who and what — that
  party becomes the provider (Art. 25(1)), and the one named above as placing it on the market
  becomes the INITIAL PROVIDER, owing cooperation and technical access under Art. 25(2). If your
  supply terms forbid such changes, say so: Art. 25(2) does not apply where the initial provider
  clearly specified the system was not to be turned into a high-risk one.>
- **This card is written by:** <legal entity, address> — <which of the roles above we hold>

## Scope and status

- **Where it is used:** <Sold or deployed in the EU? Output used in the EU? People it is used on in
  the EU? (Art. 2(1))>
- **Exclusions claimed:** <None, or which Art. 2 paragraph and why.>
- **Part of a regulated product:** <None. Or: the product, its Annex I law, and whether a notified
  body assesses its conformity (Art. 6(1)).>
- **Placed on the market:** <Date, or planned date (Art. 111).>
- **Live trials before release:** <Underway | planned | none — only inside an AI regulatory sandbox,
  or never run on live inputs outside the lab (Art. 60).>

## If this is a general-purpose AI MODEL rather than a system

<Delete this block for an AI system. Keep it where Art. 3(63) fits: significant generality, a wide
range of distinct tasks, integrable downstream. A system built ON a model is not this — use the
use-case blocks below instead.>

- **Placed on the market?** <Or still in research, development or prototyping — Art. 3(63) and
  Art. 2(8) both stop applying on the day it ships, and Chapter V has no transition period.>
- **Systemic risk (Art. 51):** <A Commission designation under Art. 51(1)(b) or 52(4), or an
  Art. 52(1) notification you have made, with dates. AND the cumulative training compute in FLOP —
  give the figure whether it is above or below 10^25. A parameter count is not a compute figure.>
- **Release terms (Arts. 53(2), 54(6)):** <All four limbs or none of the carve-out. The licence,
  quoted on whether it permits access, use, modification and distribution; and whether the
  parameters including the weights, the model architecture information and the model usage
  information are each publicly available — with no agreement, request form or paid tier in front
  of them.>
- **Downstream information (Art. 53(1)(b)):** <What you give providers who integrate the model, so
  they can understand its capabilities and limitations and meet their OWN obligations — Annex XII
  is the minimum.>
- **Copyright policy (Art. 53(1)(c)):** <How the policy identifies and complies with an Art. 4(3)
  Directive (EU) 2019/790 rights reservation, including the state-of-the-art technologies used to
  detect one at crawl time. Owed whatever the licence.>
- **Training-content summary (Art. 53(1)(d)):** <Where the public summary is, and that it follows
  the AI Office template. Owed whatever the licence.>
- **Authorised representative (Art. 54):** <Required by written mandate BEFORE placing on the Union
  market where the provider is established in a third country.>

## Use case 1: <name the purpose, e.g. "candidate shortlisting">

**Intended purpose.** <What decision does this support, in what sector, affecting whom?>

**How outputs are produced.** <Trained model? Rules a person wrote? Name the technique.>

**What it does to a person.** <Does it score, rank, rate, match, filter or evaluate people?
If yes: on what basis, and what does the output look like? If no: say so explicitly.>

**What it does not do.** <The claims your exemption depends on. Be specific.>

**Effect on the decision.** <How is the output used? Would a person reach the same decision on the
same material without it? (Art. 6(3))>

**Exemption claimed.** <None, or which Art. 6(3) condition and why the system poses no significant
risk of harm. This is the Art. 6(4) assessment.>

**Inputs.** <What data about people goes in? Faces, voices, video, CVs, performance records?
If it processes people's faces or voices, what does it extract from them?>

**Human involvement.** <Who sees the output, what can they change, can it be bypassed?
Note: this does not change the risk class — state it for the record, not as a defence.>

**Content generation / interaction.** <Does it generate text, image, audio or video? Does it
communicate directly with the people it affects? If it generates: how is the output marked so a
machine can detect it was artificially generated — which scheme, what does the marking survive, and
how does someone else detect it? If it interacts: how is the person told, inside the interaction,
that they are dealing with an AI system?>

**Out of scope.** <Uses you do not support and do not validate for.>

## Use case 2: ...

## High-risk documentation

<Only where a use case is high-risk. One heading per Article; section 12 of the guide lists what
each one needs. Or paste your Annex IV technical documentation after the card instead.>

### Risk management (Art. 9)
### Data and data governance (Art. 10)
### Technical documentation (Art. 11)
### Logging (Art. 12)
### Instructions for use (Art. 13)
### Human oversight (Art. 14)
### Accuracy, robustness and cybersecurity (Art. 15)
```

---

## Before you submit it

- [ ] The card says where the system is used, and claims an Art. 2 exclusion only with a reason
- [ ] A system inside a physical product names the product's Annex I law and who assesses its
      conformity (Art. 6(1))
- [ ] Every use case says whether it evaluates people, and on what
- [ ] Any biometric matching says which direction it runs — against the person's own record, or
      against a gallery of many (Annex III(1)(a))
- [ ] Nothing is described only by its benefit
- [ ] The awkward capability is written down, not implied
- [ ] Exemption claims are stated as claims, not left to inference — with the condition, and why
      the system poses no significant risk (Art. 6(3), 6(4))
- [ ] Art. 50 questions answered even if the risk tier is minimal — and where content is generated,
      the marking scheme and the way to detect it are named, not just asserted (Art. 50(2))
- [ ] Every party you know of is named, with what it does to the system
- [ ] The provider is identified by registered name or trade mark **and** a contact address, or the
      card says where on the system those details appear (Art. 16(b))
- [ ] Where one party placed the system and another changed or rebadged it, both ends are shown —
      the new provider and the initial provider are two different organisations, and each owes
      something (Art. 25(1) and 25(2))
- [ ] The deploying organisations are described by kind — public body, private provider of public
      services, or neither. Two duties turn on it and they differ (Art. 27, Art. 49(3))
- [ ] For a general-purpose MODEL: the cumulative training compute is given as a FLOP figure, and
      any Commission designation or Art. 52(1) notification is stated with its date (Art. 51)
- [ ] For a general-purpose MODEL: the licence terms are quoted on access, use, modification and
      distribution, and the card says whether the weights, the architecture information and the
      usage information are each publicly available — all four, or the carve-out is unavailable
      (Arts. 53(2), 54(6))
- [ ] The card says whether the system is trialled live before release, and when it was or will be
      placed on the market (Art. 60, Art. 111)
- [ ] For a high-risk use case: risk management, data, logging, instructions for use, human oversight
      and accuracy are each described, not asserted (Arts. 9–15)

If the tool still returns **needs review**, it will name the fact it was missing and the article that
needed it. Add that fact and run it again.

---

## Appendix — a worked example

An anonymised **real vendor product page**, rewritten to this guide: same product, same facts, no
marketing. Note what the page left out and the card states — that use case 2 scores applicants, and
that use case 1 does not.

The card classifies to the same tier as the original page (high-risk), and splitting the product by
purpose gives use case 1 its own, different verdict — not high-risk under Art. 6(3)(a), which the
page collapsed away.

The example stops at the classification. A real card for use case 2 would go on to the high-risk
documentation of section 12; without it, the report lists those obligations as gaps.

### Smart Screening — system card

**Version / date:** 3.4 — July 2026

#### Parties

- **Developed by:** Example Analytics Ltd, Dublin, Ireland
- **Placed on the market by:** Example Analytics Ltd, trading as Example Analytics, 12 Harcourt
  Road, Dublin 2, D02 XY45, Ireland. Contact: compliance@example-analytics.invalid. Placed on the
  market under its own name; no third party's system is incorporated, rebadged or resold here. The
  same name and address are shown on the product's sign-in screen (Art. 16(b)).
- **Deployed by:** our customers, who are private-sector recruiters and staffing agencies. We are
  aware of none that is a body governed by public law or a private entity providing public
  services; the product is not sold into public-sector recruitment. Where a customer is either,
  the Art. 27 assessment falls to them and the instructions for use say so.
- **Importer / distributor / authorised representative:** none. Sold directly, from the Union.
- **Changed after placing?** Customers configure scoring criteria within the documented envelope
  and receive our updates. No customer may retrain the model, add inputs, or resell the system
  under its own name; our terms forbid it, and they state expressly that the system is not to be
  turned into a different high-risk system. On our understanding that keeps Art. 25 from moving the
  provider role — so there is no initial provider distinct from us — and we say it here so a
  customer who does otherwise knows what it takes on.
- **This card is written by:** Example Analytics Ltd — the provider.

#### Scope and status

- **Where it is used:** sold to recruiters in the EU and used on applicants to EU-based roles.
- **Exclusions claimed:** none.
- **Part of a regulated product:** none. Standalone software.
- **Placed on the market:** version 1.0 in March 2024; version 3.4 in July 2026.
- **Live trials before release:** none. Each version is evaluated offline on held-out historical
  applications and is never run on live applications before release.

#### Use case 1: application field extraction

**Intended purpose.** Populating the recruiter's applicant-tracking database from submitted
applications, in private-sector recruitment. Affects: job applicants.

**How outputs are produced.** A trained document-understanding model extracts fields from
free-text CVs in several formats; date and job-title normalisation is rule-based.

**What it does to a person.** Nothing. This use case extracts stated facts from a document. It does
not score, rank, rate or evaluate the applicant, and produces no judgement about them.

**What it does not do.** No scoring, no ranking, no shortlisting, no comparison between applicants.
Extraction only.

**Effect on the decision.** None. Recruiters see the same facts the applicant wrote, in database
fields instead of a CV, and decide on them as they would without the system.

**Exemption claimed.** Art. 6(3)(a), a narrow procedural task: the system moves stated facts from
one format to another and forms no view of the applicant. It poses no significant risk of harm,
because no decision depends on its output beyond what the applicant wrote. Extraction errors are
visible to the recruiter against the original CV, which stays attached to the record.

**Inputs.** CV and application-form text. Name, contact details, employment history, education,
skills. No video, no audio, no photographs used as input to any model.

**Human involvement.** Recruiters read the extracted fields directly and correct them in the ATS.

**Content generation / interaction.** None. No text is generated; the system never communicates
with applicants.

**Out of scope.** Not validated for internal promotion, contractor selection, or academic admissions.

#### Use case 2: candidate fit scoring and ranking

**Intended purpose.** Producing a shortlist ordering for recruiters deciding whom to interview, in
private-sector recruitment. Affects: job applicants.

**How outputs are produced.** A model trained on historical application-to-interview outcomes,
scoring each applicant against the requisition.

**What it does to a person.** **It evaluates applicants.** Each applicant receives a 0–100 fit score
against the role, computed from required skills, preferred experience, seniority and
customer-configured criteria. Applicants are ranked by that score and presented to recruiters as an
ordered shortlist, strongest first.

**What it does not do.** Does not auto-reject: no configuration removes an applicant from the
recruiter's view on the basis of score.

**Effect on the decision.** Recruiters read the shortlist in score order and usually interview from
the top, so the score shapes who is considered first.

**Exemption claimed.** None. This use case profiles applicants, so it is high-risk.

**Inputs.** The extracted fields from use case 1, plus the requisition text. Name, photograph,
address and date of birth can be hidden from reviewers but are not model inputs in any case.

**Human involvement.** The recruiter decides who advances and may re-order or ignore the ranking.
*Stated for the record — we understand this does not change the risk class.*

**Content generation / interaction.** None.

**Out of scope.** Not validated outside the six requisition families listed in the technical file.

#### Use case 3: not applicable

No further intended purposes. The system generates no content and holds no conversation with
applicants at any point.
