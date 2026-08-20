# How to write a system card that can be classified

> **Not legal advice.** This guide, and the tool it accompanies, produce a draft checklist for
> review by a qualified professional. Nothing here is the assessment or official position of the
> European Commission or any other authority.

This tool reads a description of your AI system and works out its risk class under Regulation (EU)
2024/1689. It can only answer from what you write. If a fact is missing, the honest answer is
"needs review" — and this guide exists so you get a verdict instead.

**It is not a technical file.** That is a different document, for a different step, and the Act
already specifies it: [Annex IV](../data/policy/annexes/2024-07-12/annex-IV.md), which applies once
you know you are high-risk. This card comes first, and nothing in the Regulation templates it.

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

### 2. Is it a prohibited practice? — Art. 5

Say explicitly whether the system does any of the following, because these are banned outright:

- infers **emotions** of people at work or in education (Art. 5(1)(f)) — including during
  recruitment, which the Commission reads as part of "workplace"
- categorises people **biometrically** to infer protected characteristics
- scores people's **social behaviour** leading to detrimental treatment
- uses subliminal or manipulative techniques, or exploits vulnerability
- generates or manipulates **realistic intimate imagery** of an identifiable person without their
  consent (Art. 5(1)(ba)), or **child sexual abuse material** (Art. 5(1)(bb)) — both added by
  Regulation (EU) 2026/1744 and applying from **2 December 2026**

If it processes faces, voices, or video of people, say what it extracts from them. "Analyses video
interviews" is ambiguous in the way that matters most.

**If it generates images, video or audio of people, the safeguards are the answer.** Art. 5(1)(ba)
and (bb) do not ban a generator for being *capable* of producing that material — Art. 5(1a) catches
a provider only where producing it is the system's intended purpose, or where it is a reasonably
foreseeable and reproducible output **and** there are no reasonable safeguards against it. So the
card should say what those safeguards are: filtering, refusal training, output classification,
misuse detection, and how reported misuse gets corrected. A general-purpose generator whose card
describes none of that is closer to the second limb than its authors probably intend.

### 3. What is it used for? — Art. 6(2), Annex III

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

### 4. Does it evaluate people? — Art. 6(3)

**The decisive question.** State plainly whether the system scores, ranks, rates, matches, filters or
otherwise evaluates natural persons — **and on what basis**.

"Sorts applications" is not enough. Sorting by submission time evaluates nobody. Sorting by predicted
fit evaluates everybody, and under the Art. 6(3) profiling carve-back that makes the system
high-risk **regardless of any exemption below**. Say which one you do.

> *"Applications are ordered by submission time; no model scores the candidate."*
> *"Each applicant receives a 0–100 fit score against the role; recruiters see a ranked list."*

### 5. Does an exemption apply? — Art. 6(3)(a)–(d)

Only reached if the system is in an Annex III area and does **not** evaluate people. Say which of
these fits, and why:

| | condition | typical example |
|---|---|---|
| (a) | narrow procedural task | extracting fields from a document without judging the person |
| (b) | improves a completed human activity | tidying prose a person already wrote |
| (c) | detects decision patterns or deviations | flagging that this year's decisions differ from last year's, without replacing the human assessment |
| (d) | preparatory task to an assessment | file conversion or indexing ahead of a human review |

The burden is on you to establish the condition, and Art. 6(4) requires the assessment to be
documented before the system goes to market. An exemption you did not claim is not one you get.

### 6. Does it generate content or talk to people? — Art. 50

Independent of everything above: a minimal-risk system can owe transparency duties and a high-risk
one can owe none. State whether the system:

- **interacts directly** with people — chat, voice, conversational messaging (Art. 50(1))
- **generates** synthetic text, image, audio or video (Art. 50(2))
- is an **emotion recognition or biometric categorisation** system (Art. 50(3)) — note this bites
  even where the system is prohibited under Art. 5
- produces **deep fakes**, or text published to inform the public on matters of public interest
  (Art. 50(4))

Each of these is an obligation the report then checks, so answer the follow-up too. For 50(2) that
means saying **how** the output is marked — a named watermarking, provenance or metadata scheme, and
what it survives. The paragraph asks for a marking a machine can detect, so "outputs are labelled as
AI-generated" is an answer that does not reach the duty. For 50(1), if you rely on the exception for
what is obvious to a reasonably well-informed person, say so and say why: it is a judgement about
the context of use, not a default.

### 7. Which organisations are in the chain? — Art. 3(3)–(7), Art. 16(b), Art. 25, Art. 27

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

## Use case 1: <name the purpose, e.g. "candidate shortlisting">

**Intended purpose.** <What decision does this support, in what sector, affecting whom?>

**How outputs are produced.** <Trained model? Rules a person wrote? Name the technique.>

**What it does to a person.** <Does it score, rank, rate, match, filter or evaluate people?
If yes: on what basis, and what does the output look like? If no: say so explicitly.>

**What it does not do.** <The claims your exemption depends on. Be specific.>

**Inputs.** <What data about people goes in? Faces, voices, video, CVs, performance records?
If it processes people's faces or voices, what does it extract from them?>

**Human involvement.** <Who sees the output, what can they change, can it be bypassed?
Note: this does not change the risk class — state it for the record, not as a defence.>

**Content generation / interaction.** <Does it generate text, image, audio or video? Does it
communicate directly with the people it affects? If it generates: how is the output marked so a
machine can detect it was artificially generated — which scheme, and what does the marking survive?
If it interacts: how is the person told they are dealing with an AI system?>

**Out of scope.** <Uses you do not support and do not validate for.>

## Use case 2: ...
```

---

## Before you submit it

- [ ] Every use case says whether it evaluates people, and on what
- [ ] Any biometric matching says which direction it runs — against the person's own record, or
      against a gallery of many (Annex III(1)(a))
- [ ] Nothing is described only by its benefit
- [ ] The awkward capability is written down, not implied
- [ ] Exemption claims are stated as claims, not left to inference
- [ ] Art. 50 questions answered even if the risk tier is minimal — and where content is generated,
      the marking scheme is named, not just asserted (Art. 50(2))
- [ ] Every party you know of is named, with what it does to the system
- [ ] The provider is identified by registered name or trade mark **and** a contact address, or the
      card says where on the system those details appear (Art. 16(b))
- [ ] Where one party placed the system and another changed or rebadged it, both ends are shown —
      the new provider and the initial provider are two different organisations, and each owes
      something (Art. 25(1) and 25(2))
- [ ] The deploying organisations are described by kind — public body, private provider of public
      services, or neither. Two duties turn on it and they differ (Art. 27, Art. 49(3))

If the tool still returns **needs review**, it will name the fact it was missing and the article that
needed it. Add that fact and run it again.

---

## Appendix — a worked example

The same system as `data/golden_set/smoke/screening-and-ranking.md`, an anonymised **real vendor
product page**, rewritten to this guide: same product, same facts, no marketing. Note what the page
left out and the card states — that use case 2 scores applicants, and that use case 1 does not.

Both classify to the same tier as the original page (`high_risk`, high confidence, no abstentions),
and splitting the product by purpose gives use case 1 its own, different verdict — `not_high_risk`
under Art. 6(3)(a), which the page collapsed away.

This card is template-derived and must never enter the golden set: a document written to our own
template is trivially readable by our own tool, so a score measured on it would mean nothing.

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

#### Use case 1: application field extraction

**Intended purpose.** Populating the recruiter's applicant-tracking database from submitted
applications, in private-sector recruitment. Affects: job applicants.

**How outputs are produced.** A trained document-understanding model extracts fields from
free-text CVs in several formats; date and job-title normalisation is rule-based.

**What it does to a person.** Nothing. This use case extracts stated facts from a document. It does
not score, rank, rate or evaluate the applicant, and produces no judgement about them.

**What it does not do.** No scoring, no ranking, no shortlisting, no comparison between applicants.
Extraction only.

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

**Inputs.** The extracted fields from use case 1, plus the requisition text. Name, photograph,
address and date of birth can be hidden from reviewers but are not model inputs in any case.

**Human involvement.** The recruiter decides who advances and may re-order or ignore the ranking.
*Stated for the record — we understand this does not change the risk class.*

**Content generation / interaction.** None.

**Out of scope.** Not validated outside the six requisition families listed in the technical file.

#### Use case 3: not applicable

No further intended purposes. The system generates no content and holds no conversation with
applicants at any point.
