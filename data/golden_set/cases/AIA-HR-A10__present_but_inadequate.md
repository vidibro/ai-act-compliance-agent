The tags are stripped from generated case documents; they never reach the agent.

Written to be realistic, not ideal: it reads like a real vendor's technical file, with concrete
figures and named measures, because a checker that only passes on perfect prose is useless.
-->

# TalentRank Candidate Scoring — Technical Documentation

**Provider:** Northwind Analytics B.V., Amsterdam, Netherlands
**System:** TalentRank v4.2
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

## 2. Risk management system

A risk management system is established, implemented, documented and maintained across the whole
TalentRank lifecycle, and is reviewed at each quarterly release gate and on any material model
change. It is owned by the Responsible AI board and minuted.

**Identified risks (health, safety, fundamental rights).** The principal identified risk is
discriminatory ranking against protected groups, in particular indirect discrimination via proxy
features (postcode, career-gap length, name-derived signals). Secondary risks: over-reliance by
recruiters on the score (automation bias), and degraded ranking quality for occupations
under-represented in training data.

**Reasonably foreseeable misuse.** We analysed use of the score as an automatic reject threshold
without human review, and use for occupations outside the requisition families the system was
validated on. Both are analysed as foreseeable misuse and mitigated: the API refuses requisitions
outside validated families, and no auto-reject endpoint is exposed.

**Post-market monitoring input.** Risk estimates are re-evaluated against field data from the
post-market monitoring system (see §8): monthly selection-rate monitoring per protected group,
recruiter override rates, and reported incidents feed the next risk review.

**Adopted measures.** (a) Proxy features removed at feature-selection stage and re-tested; (b)
adverse-impact testing gate at 0.80 selection-rate ratio blocking release; (c) score presented
only with sub-score explanations to counter automation bias; (d) recruiter training material
supplied to deployers under Art. 13.

**Residual risk.** Residual adverse-impact risk after mitigation is judged acceptable: measured
selection-rate ratio 0.94 (see §7), with per-release re-testing. Residual automation-bias risk is
carried and addressed through oversight measures in §6.
## 3. Data and data governance

TalentRank is trained on a large, high-quality dataset of historical applications. We apply
appropriate data governance practices and our data sets are relevant and representative for
the intended purpose. Data quality is a priority for our engineering team.
## 4. Technical documentation (Annex IV coverage)

This file, together with its referenced annexes, constitutes the technical documentation drawn up
before placing on the market and kept up to date at each release.

- **General description of the system** — §1 (intended purpose, provider, deployer interaction,
  versions).
- **Detailed description of elements and development process** — §5 (architecture, training
  methodology), Annex A (model card, feature list).
- **Monitoring, functioning and control** — §6 (oversight), §7 (performance), §8 (post-market
  monitoring plan), including known limitations and expected input data.
- **Performance metrics** — §7, with accuracy, robustness and fairness figures per requisition
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

**Provider identity and contact.** Northwind Analytics B.V., Keizersgracht 100, 1015 CS Amsterdam,
Netherlands. Contact: compliance@northwind-analytics.example.

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

**Maintenance and expected lifetime.** Supported for 24 months from release; retraining cadence
and change policy in Annex B. Deployers are notified 60 days before a model version is retired.

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
