# TalentRank Candidate Scoring — Technical Documentation (Article 15 extract)

**Provider:** Northwind Analytics B.V., Keizersgracht 100, 1015 CS Amsterdam, Netherlands.
**System:** TalentRank v4.2
**Document version:** 4.2.1 — March 2026
**Intended purpose:** TalentRank produces a ranked fit score (0–100) for applicants against a job
requisition, to support recruiter shortlisting decisions in the hiring process. It is treated by
the provider as high-risk under Annex III, point 4(a).

## 8. Accuracy, robustness and cybersecurity

### 8.1 Accuracy

Declared metric: ranking quality measured as NDCG@10 against the "advanced to interview" label on a
held-out temporal split (2025 applications, n=48,200). The same levels and metrics are declared to
deployers in the instructions for use, section 9.3.

| Requisition family | NDCG@10 | AUC | 95% CI (NDCG@10) |
|---|---|---|---|
| Engineering | 0.81 | 0.78 | ±0.014 |
| Sales | 0.78 | 0.75 | ±0.017 |
| Finance | 0.80 | 0.77 | ±0.016 |
| Operations | 0.76 | 0.73 | ±0.019 |

Every release is re-scored on the frozen 2025 benchmark before it ships, and a release whose
NDCG@10 falls more than 0.02 below the declared level in any family is not shipped. Deployed
releases are re-scored quarterly on fresh labelled samples so that the declared levels stay true
for the whole period a release is in service.

### 8.2 Robustness

Technical measures: malformed or truncated input fields are rejected with a typed error rather than
scored with a default; non-English CVs in the six supported languages are scored within a 0.04
NDCG@10 spread. Organisational measures: a named on-call engineer owns scoring availability, and
deployers are notified of any outage within one hour.

Fail-safe: on scoring-service unavailability the system returns no score rather than a default
score, and the applicant tracking system falls back to unranked review.

TalentRank does not continue to learn after being placed on the market. Model weights are frozen
per release, deployer interactions are never used as training data, and retraining happens only
through a new release built from the contracted training pipeline, so no output of a deployed
release can become input to its own future operation.

### 8.3 Cybersecurity

Threat model. The threat model covers attackers who seek to change which candidates are shortlisted
or to extract applicant data. It is reviewed at every release and its measures are sized to that
risk: a manipulated ranking changes access to employment for real applicants.

Unauthorised alteration. Model artefacts are signed at build and verified at load; the inference API
requires mTLS and per-deployer scoped tokens; every configuration change is written to an
append-only audit log. Penetration test: annual, latest February 2026, no critical findings open.

Data poisoning. Training data is admitted only from contracted client pipelines, with checksum
verification of every file. Each dataset snapshot is screened for label-flipping and injected
duplicate records before sign-off; a snapshot that fails screening is quarantined, the release built
from it is withdrawn, and the last clean snapshot is restored.

Model poisoning. The one pre-trained component used in training, a sentence-embedding encoder, is
pinned by hash to a vendor release with a signed provenance attestation. Before adoption it is
tested for backdoor triggers with a trigger-reconstruction scan; a component that fails is not used,
and a trigger found later leads to its replacement and a retrained release.

Adversarial examples and model evasion. CVs are screened for keyword stuffing and hidden text (white
or zero-size fonts) with a feature-distribution outlier check; flagged applications are routed to
manual review rather than scored. The model is trained with perturbed CVs so that invisible or
repeated terms do not move the score, and a confirmed evasion technique is added to the screening
rules within five working days.

Confidentiality attacks. The API rate-limits each deployer and runs query-pattern anomaly detection
to detect model-extraction and membership-inference probing; scores are returned as integers without
per-feature attributions, and a detected probe revokes the token and is reported to the deployer.
