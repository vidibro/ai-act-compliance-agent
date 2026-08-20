# PathFinder Internal Mobility — Provider Technical File

| | |
|---|---|
| **Provider** | Meridian Workforce Intelligence GmbH (trade mark: Meridian WI), Leopoldstraße 210, 80804 Munich, Germany |
| **Provider contact** | ai-compliance@meridian-wi.example — also shown on the sign-in screen of every PathFinder release || **System** | PathFinder, release 7.3 |
| **File revision** | R7.3-b — May 2026 |
| **Classification** | High-risk, Annex III point 4(b) |
| **Conformity route** | Internal control (Annex VI) |

**Intended purpose.** PathFinder recommends internal candidates for open positions, successor
slates and development assignments within an employing organisation, and produces a readiness
band for each employee against a target role. Output supports the decisions of line managers and
talent review panels on promotion, lateral moves and task allocation. PathFinder does not decide
anything; it proposes and explains.

The system evaluates natural persons in an existing employment relationship and is used to inform
promotion and task-allocation decisions. Meridian therefore treats it as high-risk under Annex III
point 4(b) and acts as provider under Article 16.

---

## Part A — What the system does

PathFinder reads an employee's internal profile (role history, grade band, completed competency
assessments, certifications, mobility preferences, tenure) together with a target role profile
drawn from the client's competency framework. For each employee–role pair it returns:

- a **readiness band** — `ready now`, `ready 6–12 months`, `development needed`;
- the **competency deltas** driving that band, expressed as named gaps;
- a **confidence indicator**, and an out-of-distribution flag where the employee's history is
  unlike anything in the client's validated population.

Panels see a shortlist of up to twenty employees per target role, ordered by readiness band and
then alphabetically — never by a raw numeric score, which earlier field testing showed panels
treated as a ranking of worth.

### A.1 Model and build process

PathFinder pairs a two-tower retrieval model over competency embeddings with a calibrated
gradient-boosted classifier that maps an employee–role pair to a readiness band. Calibration is
isotonic, fitted per client on a rolling 18-month window. Builds are reproducible: every release
pins a dataset snapshot id, a feature-config hash and a seed, all recorded in the release record
(Annex 2).

Performance appraisal free text is deliberately **not** an input. Pilot analysis found it carried
strong manager-identity and gender signal with negligible predictive lift; the decision and its
evidence are recorded in Annex 1.

---

## Part B — Data foundation

PathFinder is trained on a large and carefully curated set of internal mobility records from
our client base. We apply appropriate data governance throughout, and our training data is
relevant, representative and suitable for the intended purpose. Data quality is reviewed by
our data engineering team on an ongoing basis.
---

## Part C — Risk management

Meridian operates a documented risk management system covering the whole PathFinder lifecycle. It
is established at design, reviewed at every release gate and at any material change to the model,
data or intended purpose, and re-run in full annually. The Product Risk Council owns it; decisions
and dissent are minuted, and the minutes form part of the technical file.

**Identified risks to health, safety and fundamental rights.**

1. *Entrenchment of historical progression patterns.* The dominant risk. Because the target is
   drawn from past internal moves, groups historically passed over may receive systematically
   lower readiness bands — indirect discrimination on sex, age, disability and family status.
2. *Career-break and part-time penalty.* Interrupted or reduced-hours histories resemble
   low-progression histories in the data, and are correlated with parenthood and disability.
3. *Panel automation bias.* Talent review panels under time pressure may adopt the shortlist as
   the decision rather than as an input.
4. *Feedback loops.* Recommendations shape who moves, and who moves becomes next year's training
   data, amplifying an initial skew over successive retraining cycles.
5. *Employee-facing harm from opaque bands.* An employee told only "development needed" without
   named gaps cannot act on it, which converts a support tool into an unappealable judgement.

**Estimation and evaluation under foreseeable misuse.** Analysed and mitigated: use as an
automatic filter that suppresses employees below a band from panel view; use for redundancy
selection or performance management, which is outside the intended purpose and legally distinct;
use for external candidates; and use in grade bands or job families the system is not validated
for. The API rejects unvalidated bands and families outright, exposes no filter-below-band
parameter, and the contract prohibits redundancy use.

**Evaluation against post-market monitoring data.** Risk estimates are revised against field data
under Part I: quarterly parity of `ready now` rates by sex, age band and working-time pattern per
client; panel override and shortlist-adoption rates; complaints raised through the client's
grievance channel and reported to Meridian; and drift in the input population.

**Risk management measures adopted.**

| Risk | Measure | Evidence |
|---|---|---|
| 1, 2 | Proxy-feature ablation; parity release gate at 0.85 | Part D, Annex 1 |
| 3 | Bands not scores; no auto-filter; mandatory panel prompt to record reasons for departing from or adopting the shortlist | Part E |
| 4 | Feedback-loop audit each retraining cycle comparing the outcome distribution of PathFinder-influenced moves against the pre-deployment baseline; retraining blocked on divergence beyond 0.05 | Annex 2 |
| 5 | Named competency gaps returned with every band; employee-facing explanation view mandated in the deployer contract | Part E, Part G |

**Residual risk.** Residual indirect-discrimination risk is judged acceptable but not eliminated:
the measured parity ratio is 0.91 across the deployed population (Part D), above the 0.85 gate but
below unity, and the system cannot correct upstream inequality in who was given development
opportunities. This residual is stated to deployers in Part G, and the accompanying instruction is
that PathFinder must not be the sole basis for a promotion decision. Residual feedback-loop risk
is carried and monitored rather than closed, since it can only be observed over multiple cycles.
---

## Part D — Performance, resilience and security

**Declared accuracy metrics.** Two are declared, because the system does two things. Retrieval
quality is precision@5 against sustained placement on a held-out temporal split (2025 moves,
n = 71,400). Band quality is expected calibration error over the three readiness bands.

| Job family | Precision@5 | ECE | 95% CI (P@5) |
|---|---|---|---|
| Engineering | 0.62 | 0.031 | ±0.011 |
| Field operations | 0.58 | 0.037 | ±0.013 |
| Commercial | 0.60 | 0.029 | ±0.012 |
| Finance & control | 0.64 | 0.026 | ±0.014 |
| Administration | 0.57 | 0.041 | ±0.012 |
| Care & support | 0.55 | 0.044 | ±0.015 |
| Legal | 0.49 | 0.068 | ±0.031 |
| Clinical | 0.47 | 0.071 | ±0.034 |

Legal and clinical figures are reported despite falling below Meridian's 0.55 internal target;
they are declared as limitations in Part G rather than suppressed, and both families carry a
mandatory low-confidence banner in the panel view.

**Parity gate.** Ratio of `ready now` rates between the lowest- and highest-rated group by sex,
age band and working-time pattern, measured per job family. Release is blocked below **0.85**.
Current deployed release: **0.91** (lowest family: care & support, 0.87).

**Robustness.** Consistency is measured across the lifecycle and against degraded input.

- Sparse profiles (fewer than three completed competency assessments): precision@5 falls to 0.44;
  such employees are flagged low-confidence and the band is withheld below two assessments.
- Grade-band remapping after a client re-org: regression-tested against six historical re-orgs;
  maximum precision@5 movement 0.03.
- Stale profiles (no update in 24 months): detected and surfaced to the panel as a data-quality
  warning rather than scored silently.
- Adversarial competency-keyword stuffing in self-assessed fields: detected by an outlier check on
  the self-reported/manager-verified ratio; flagged for panel attention, never silently scored.
- Drift: precision@5 movement beyond 0.04 against the release baseline, or ECE beyond 0.06,
  triggers investigation and possible retraining.

**Fail-safe behaviour.** On model or feature-store unavailability PathFinder returns no
recommendation and the panel workflow continues unassisted. It never returns a default band, and
never falls back to a previous model version silently — a version mismatch surfaces in the panel
view and in the event record.

**Cybersecurity.** Model artefacts and feature configurations are signed; signatures are verified
at load and a failed verification blocks startup. The inference API requires mTLS with
per-deployer scoped tokens. Against data poisoning at retraining, snapshots are admitted only from
contracted HRIS pipelines with checksum verification and a two-person sign-off recorded in the
release record. Against model extraction, per-token rate limits and a query-pattern anomaly
detector apply. Employee protected attributes live in a separate store with independent access
control and are unreachable from the inference path. Penetration testing is annual, most recently
January 2026; two medium findings were remediated in R7.2, none outstanding.
---

## Part E — Oversight by managers and panels

PathFinder is built so that the line managers and talent review panels using it can effectively
oversee it while it is in use.

**Interface tools provided.** The panel view presents, for every recommended employee: the
readiness band, the named competency gaps behind it, the confidence indicator, the date of the
underlying assessments, and an out-of-distribution banner where applicable. Employees absent from
the shortlist can be searched and added by any panel member, and the panel view shows the count of
employees considered but not shortlisted, so the shortlist is visibly a subset rather than the
field. Numeric scores are not exposed anywhere in the interface, by design.

**Ability to interpret the output.** Every band links to the competency deltas that produced it
and to the assessment records behind them. The interface states, on the same screen as the
recommendation, the relevant limitations from Part G for the job family in view.

**Ability to intervene, to override, and to not use the output.** Panel members can disregard the
shortlist entirely, add or remove any employee with a recorded reason, and export the unranked
employee list to run the review without PathFinder. A client administrator can disable
recommendations for a job family or for the whole tenant from the administration console; the
control takes effect within the current session and leaves the mobility workflow fully usable.
Where a panel departs from the shortlist, PathFinder records the reason but never challenges,
re-scores or re-ranks in response.

**Measures against automation bias.** The shortlist is ordered by band and then alphabetically, so
it carries no implied ranking within a band. Bands below `ready now` are shown with equal visual
weight. The panel must record a one-line rationale for each employee advanced, whether or not
PathFinder recommended them, so adopting the shortlist is not the path of least resistance.
Quarterly, Meridian reports each client's shortlist-adoption rate back to them, flagging tenants
above 90% for review as a possible automation-bias signal.

**Competence, training and authority of overseers.** Oversight is exercised by line managers and
HR business partners who have completed Meridian's 3-hour PathFinder module: what the system does
and does not measure, how to read bands and confidence, the limitations in Part G, automation
bias, and how to raise a suspected unfair recommendation. Deployers are instructed in Part G to
assign oversight only to trained staff who hold the authority to depart from a recommendation
without escalation, and works councils receive the same material on request.
---

## Part F — Event records

PathFinder automatically records events over its lifetime. Every recommendation request writes an
immutable record to an append-only, integrity-hashed store, containing: UTC timestamp; tenant and
target-role identifiers; pseudonymous employee references for the population considered and for
the shortlist returned; model version, calibration version and feature-config hash; the readiness
band and competency deltas returned; the confidence indicator and any out-of-distribution flag;
and the panel's subsequent action per employee, including additions, removals and recorded
rationales, where the client's HRIS returns them.

Recording is enabled by default and cannot be switched off by the deployer. Retention is 24 months
by default and configurable upward to meet national employment-law requirements. Because every
record carries its model and calibration version alongside the reference period, any historic
recommendation can be reconstructed and attributed to the exact build that produced it.
---

## Part G — Instructions for use

PathFinder is designed so that its operation is sufficiently transparent for deployers to
interpret its output and use it appropriately. The following instructions accompany the system and
are supplied to every deployer before use.

**Identity and contact of the provider.** As given in the file header above.

**Characteristics and intended purpose.** PathFinder recommends internal employees for open
positions, successor slates and development assignments, and returns a readiness band with named
competency gaps. It is decision-support for line managers and talent review panels. It does not
decide, and it must not be configured as an automatic filter.

**Capabilities and limitations of performance.** Expected accuracy per job family is stated in
Part D with confidence intervals. Known limitations:

- Legal and clinical families perform materially below the other six (precision@5 0.49 and 0.47)
  owing to the data gaps in Part B; both carry a mandatory low-confidence banner.
- Grade bands 1–2 are not validated and are refused by the API.
- Public-administration employers are outside the validated population.
- Employees with fewer than three completed competency assessments receive lower-quality
  recommendations; below two, no band is returned at all.
- Profiles not updated within 24 months are flagged; recommendations based on them are unreliable.
- The measured parity ratio is 0.91, not 1.0. PathFinder reflects historical progression patterns
  it was trained on and cannot correct upstream inequality in development opportunity.

**Circumstances which may lead to risks to health, safety or fundamental rights.** Using the
shortlist as the decision rather than an input; using PathFinder for redundancy selection,
performance management, disciplinary processes or external recruitment, all outside the intended
purpose; applying it to unvalidated grade bands or job families; assigning oversight to untrained
staff or to staff without authority to depart from a recommendation; and withholding the named
competency gaps from the employee, which removes the only actionable part of the output.

**Human oversight measures.** The oversight the provider has built in, and the measures the
deployer must implement, are set out in Part E. The deployer must: assign panel oversight to
trained staff with authority to overrule; keep the employee-facing explanation view enabled; and
review shortlist-adoption rates quarterly against the report Meridian supplies.

**Expected input data.** Employee profiles and target-role profiles conforming to the client's
mapped competency framework; the field schema and mapping requirements are in Annex 1. Protected
attributes are neither required nor accepted on the inference path.

**Maintenance, changes and expected lifetime.** Each release is supported for 18 months. Retraining
cadence, change-notification policy and the version-retirement schedule are in Annex 2. Deployers
receive 90 days' notice before a model version is withdrawn, and a change log for every release
that alters band boundaries or calibration.

**Log collection and interpretation.** The deployer's ability to collect, access and interpret
event records is described in Part F; the export schema is in Annex 3.
---

## Part H — Technical documentation index (Annex IV)

This file and the annexes it references constitute the technical documentation drawn up before
PathFinder was placed on the market, and kept up to date at each release.

- **General description of the system** — front matter and Part A: intended purpose, provider
  identity, deployer interaction, releases and versioning.
- **Detailed description of the elements and of the development process** — Part A.1 (architecture,
  training methodology, calibration), Annex 1 (model card, full feature list, excluded-feature
  decisions with evidence).
- **Monitoring, functioning and control of the system** — Part E (oversight), Part D (performance
  and its limits), Part I (post-market monitoring plan), including known limitations, expected
  input data and foreseeable unintended outcomes.
- **Performance metrics** — Part D: precision@5 and expected calibration error per job family with
  confidence intervals, plus the parity gate and its measured value.
- **Risk management system** — Part C, with the Product Risk Council minutes as an appendix.
- **Changes made through the lifecycle** — Annex 2: change log, retraining triggers, calibration
  refits, version-retirement policy.
- **Standards applied** — Annex 4: harmonised standards and common specifications applied; where
  none is applied in full, the gap and the alternative solution adopted are recorded.
- **EU declaration of conformity** — Annex 5.
- **Post-market monitoring plan** — Annex 6.

The file is retained under Meridian's records procedure for ten years from placing on the market,
and is made available to national competent authorities on reasoned request.
---

## Part I — Post-market monitoring

Meridian collects and reviews, per client and per quarter: parity of `ready now` rates by sex, age
band and working-time pattern; precision@5 and calibration drift against the release baseline;
shortlist-adoption and override rates; data-quality warnings raised; and complaints reaching
Meridian through client grievance channels. Thresholds trigger investigation, and where a client's
parity ratio falls below 0.85 in any job family, recommendations for that family are suspended for
that tenant pending review. Serious incidents are reported to the relevant market surveillance
authority under Meridian's incident procedure.

## Annexes

- **Annex 1** — Model card, feature list, excluded-feature decisions and their evidence.
- **Annex 2** — Change log, retraining triggers, calibration refits, version-retirement policy.
- **Annex 3** — Event-record export schema.
- **Annex 4** — Harmonised standards applied and documented gaps.
- **Annex 5** — EU declaration of conformity.
- **Annex 6** — Post-market monitoring plan.
