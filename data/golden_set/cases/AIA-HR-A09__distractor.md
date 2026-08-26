# TalentRank Candidate Scoring — Technical Documentation

**Provider:** Northwind Analytics B.V., trading as Northwind Analytics, Keizersgracht 100,
1015 CS Amsterdam, Netherlands. Contact: compliance@northwind-analytics.example.
The same details are affixed to the product's start-up screen and its packaging.**System:** TalentRank v4.2
**Document version:** 4.2.1 — March 2026
**Intended purpose:** TalentRank produces a ranked fit score (0–100) for applicants against a job
requisition, to support recruiter shortlisting decisions in the hiring process. The system is
placed on the EU market under the provider's own trademark.

## 1. General description

TalentRank ingests a candidate's application (CV, structured application form answers) and a job
requisition, and returns a fit score plus per-criterion sub-scores. The score is presented to a
recruiter in the applicant tracking system; the recruiter decides whom to advance.

The system evaluates natural persons and produces an assessment used in the selection of
candidates. It is therefore treated by the provider as high-risk under Annex III, point 4(a).

## 2. Our commitment to responsible AI

At Northwind, trustworthy AI is at the heart of everything we build. Our values —
fairness, accountability and transparency — guide every product decision. We are proud
signatories of three industry AI ethics charters, and our leadership team is committed to
advancing the responsible use of artificial intelligence across the recruitment sector.
We believe AI should empower people, never replace human judgement.
## 3. Data and data governance

**Design choices.** Training data comprises 412,000 historical application–outcome pairs from 38
client organisations across the EU (2019–2025), covering six requisition families (engineering,
sales, finance, operations, support, marketing). Target label is "advanced to on-site interview",
chosen over "hired" because hiring outcomes carry stronger downstream manager bias.

**Provenance and collection.** Data is obtained under data processing agreements with client
organisations; candidates were informed under the clients' privacy notices. No data is scraped
from public profiles or purchased from brokers.

**Preparation.** De-duplication removed 18,400 near-duplicate applications. Free-text CV fields
are normalised; name, address, photo, date of birth, gender and nationality fields are dropped at
ingestion and are not available to the model.

**Examination for bias.** The training set was examined for gender and age-proxy imbalance per
requisition family. Engineering applications were 71% male, reflecting historic applicant pools;
we treat this as a known bias source. Mitigation: (a) proxy-feature ablation testing — postcode
and career-gap features were found to carry gender/parenthood signal and were removed; (b)
reweighting of under-represented groups per family; (c) adverse-impact testing on a held-out set
stratified by declared gender and age band, where clients supply it under a separate lawful basis.

**Data gaps.** Two known gaps: (i) under-representation of applicants from Bulgaria, Romania and
Greece (<2% combined), so scores for these markets carry a wider confidence interval and this is
declared to deployers; (ii) no coverage of public-sector requisitions — such use is out of the
declared intended purpose.

**Relevance to intended purpose.** Data sets are restricted to the six validated requisition
families; the API rejects requisitions outside them.
## 4. Technical documentation (Annex IV coverage)

This file, together with its referenced annexes, constitutes the technical documentation drawn up
before placing on the market and kept up to date at each release.

- **General description of the system** — §1 (intended purpose, provider, deployer interaction,
  versions).
- **Detailed description of elements and development process** — §5 (architecture, training
  methodology), Annex A (model card, feature list).
- **Monitoring, functioning and control** — §7 (oversight), §8 (performance), §10 (post-market
  monitoring plan), including known limitations and expected input data.
- **Performance metrics** — §8, with accuracy, robustness and fairness figures per requisition
  family.
- **Risk management system** — §2.
- **Changes over the lifecycle** — Annex B (change log, retraining triggers, versioning policy).
- **Standards applied** — Annex C (harmonised standards list; none currently applied in full,
  gaps documented).
- **EU declaration of conformity** — Annex D.

Documentation is retained under the provider's retention procedure for 10 years after placing on
the market.
## 5. System architecture and development

TalentRank uses a gradient-boosted ranking model over 84 engineered features derived from
structured application fields and a sentence-transformer encoding of CV free text. Training runs
are versioned; each release is reproducible from a pinned dataset snapshot and config hash.

## 6. Record-keeping and logging

The system automatically records events (logs) over its lifetime. Each scoring request emits an
immutable log record containing: request timestamp (UTC), requisition id, candidate reference
(pseudonymous), model version and config hash, input feature vector hash, output fit score and
sub-scores, confidence interval, and the recruiter's subsequent action (advance / reject /
override) where returned by the deployer's applicant tracking system.

Logging is enabled by default and cannot be disabled by the deployer. Log records are written to
an append-only store with integrity hashing. The reference period of each log record and the
model version make it possible to reconstruct which model produced any historic score.
## 7. Human oversight

TalentRank is designed so that natural persons can effectively oversee it while in use.

**Interface tools.** The recruiter console shows, for every candidate: the fit score, the five
highest-contributing sub-scores with plain-language labels, the confidence interval, and a
"low-confidence" banner when the candidate's profile falls outside the validated distribution.
Ranking is never presented as a decision — only as a sortable column alongside the full
application.

**Ability to intervene and to not use the output.** The recruiter can (a) re-order or ignore the
ranking entirely; (b) mark a score as disregarded, with a reason captured in the log; (c) request
re-scoring after correcting parsed field errors. A deployer administrator can disable scoring for
a requisition or globally via a stop control in the admin console, which halts scoring within the
current session and leaves the applicant tracking system fully usable without scores.

**Countering automation bias.** The console suppresses the numeric score for candidates in the
lowest-confidence decile, showing only sub-scores, to prevent uncritical reliance on a single
number. Recruiters see a standing notice that the score is decision-support only.

**Competence of overseers.** Oversight is assigned to recruiters who have completed the supplied
2-hour TalentRank training module, covering the system's capacities and limitations, how to read
sub-scores and confidence, automation bias, and how to escalate suspected unfair ranking. The
deployer is instructed (§9) to assign oversight only to trained staff with authority to overrule
the ranking.
## 8. Accuracy, robustness and cybersecurity

**Accuracy.** Declared metric: ranking quality measured as NDCG@10 against the "advanced to
interview" label on a held-out temporal split (2025 applications, n=48,200).

| Requisition family | NDCG@10 | AUC | 95% CI (NDCG@10) |
|---|---|---|---|
| Engineering | 0.81 | 0.78 | ±0.014 |
| Sales | 0.78 | 0.75 | ±0.017 |
| Finance | 0.80 | 0.77 | ±0.016 |
| Operations | 0.76 | 0.73 | ±0.019 |
| Support | 0.79 | 0.76 | ±0.015 |
| Marketing | 0.74 | 0.71 | ±0.021 |

Adverse-impact selection-rate ratio at the top-20% cut: **0.94** (threshold for release: ≥0.80).

**Robustness.** Performance is monitored for consistency across the lifecycle; drift beyond 0.03
NDCG@10 against the release baseline triggers investigation and possible retraining. Tested
against: truncated CVs (5% NDCG@10 degradation at 50% truncation), non-English CVs in the six
supported languages (max 0.04 spread), malformed input fields (rejected with a typed error rather
than a silent default), and adversarial keyword stuffing (detected via feature-distribution
outlier check; flagged, not silently scored).

Fail-safe: on model unavailability the system returns no score rather than a default score, and
the applicant tracking system falls back to unranked review.

**Cybersecurity.** Model artefacts are signed and verified at load. Inference API requires mTLS
and per-deployer scoped tokens. Measures against model-poisoning at retraining: training data is
admitted only from contracted client pipelines with checksum verification and human sign-off on
dataset snapshots. Rate limiting and anomaly detection guard against model-extraction probing.
Penetration test: annual, latest February 2026, no critical findings outstanding.
## 9. Transparency and instructions for use

TalentRank is designed so that its operation is sufficiently transparent for deployers to
interpret its output and use it appropriately. The following instructions for use accompany the
system.
### 9.1 Contents of the instructions for use

**Provider identity and contact.** As stated in the header of this document.

**Characteristics and intended purpose.** TalentRank ranks applicants against a requisition to
support recruiter shortlisting. It is decision-support only; it does not make hiring decisions and
must not be wired to automatic rejection.

**Capabilities and limitations of performance.** Expected accuracy per requisition family is stated
in §8 with confidence intervals. Known limitations: (i) accuracy is lower for Marketing and
Operations families; (ii) scores for candidates from BG/RO/GR markets carry wider confidence
intervals owing to the data gap in §3; (iii) the system is not validated for public-sector
requisitions, internal promotion, or contractor selection, and must not be used for them; (iv)
performance degrades on CVs shorter than 200 words.

**Circumstances that may lead to risks.** Using the ranking as an automatic filter, using it
outside the six validated families, or assigning oversight to untrained staff.

**Human oversight measures.** The oversight measures the provider has built in, and the measures
the deployer must implement, are described in §7. The deployer must assign oversight to trained
recruiters with authority to overrule the ranking.

**Expected input data.** Structured requisition fields plus CV text in one of six supported
languages; see Annex A for the field schema.

**Pre-determined changes.** Two changes to the system and its performance were fixed at the
initial conformity assessment and are covered by it: quarterly retraining on the same feature
schema, and the addition of a supported language once its validation set clears the §8 thresholds.
Anything else is a new conformity assessment.

**Computational and hardware resources, maintenance and expected lifetime.** Scoring runs on the
provider's hosted service; a deployer needs no local accelerator, and the integration requires 2
vCPU and 4 GB of memory for the connector. Supported for 24 months from release; retraining cadence
and change policy in Annex B. Security and model updates ship monthly and are mandatory; deployers
are notified 60 days before a model version is retired.

**Logs.** The deployer's ability to collect and interpret logs is described in §6.
## 10. Post-market monitoring plan

Selection-rate ratio per protected group, score drift, recruiter override rate and reported
incidents are monitored monthly per deployer, with thresholds that trigger investigation. Serious
incidents are reported to market surveillance authorities under the provider's incident procedure.

## Annexes

- **Annex A** — Model card and feature list.
- **Annex B** — Change log, retraining triggers, versioning policy.
- **Annex C** — Harmonised standards applied and gaps.
- **Annex D** — EU declaration of conformity.
