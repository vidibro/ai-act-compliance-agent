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

If it processes faces, voices, or video of people, say what it extracts from them. "Analyses video
interviews" is ambiguous in the way that matters most.

### 3. What is it used for? — Art. 6(2), Annex III

State the **intended purpose** in terms of the sector and the decision it supports. The eight
high-risk areas are biometrics, critical infrastructure, education, **employment**, essential
services, law enforcement, migration, and justice/democracy.

Employment (Annex III(4)) covers recruitment and selection — placing targeted job adverts, filtering
applications, evaluating candidates — and decisions on promotion, termination, task allocation and
performance monitoring.

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

### 7. Are you the provider or the deployer? — Art. 3(3), Art. 3(4)

The **provider** develops the system, or places it on the market under its own name or trademark.
The **deployer** uses it under its own authority. Obligations attach to the role, not to the
organisation, and one organisation can hold both — assessed separately for each. This tool currently
checks **provider** obligations.

---

## Template

Copy this, fill it in, delete the prompts. One block per intended purpose.

```markdown
# <system name> — system card

**Provider:** <legal entity, address>
**Our role:** provider | deployer | both (explain)
**Version / date:**

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
communicate directly with the people it affects?>

**Out of scope.** <Uses you do not support and do not validate for.>

## Use case 2: ...
```

---

## Before you submit it

- [ ] Every use case says whether it evaluates people, and on what
- [ ] Nothing is described only by its benefit
- [ ] The awkward capability is written down, not implied
- [ ] Exemption claims are stated as claims, not left to inference
- [ ] Art. 50 questions answered even if the risk tier is minimal

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

**Provider:** Example Analytics Ltd, Dublin, Ireland
**Our role:** provider
**Version / date:** 3.4 — July 2026

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
