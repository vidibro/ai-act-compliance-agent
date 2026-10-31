# SepsisWatch — system card

**Version / date:** 2.3 — June 2026

## Parties

- **Developed by:** Rheinklinik Software GmbH, Heidelberg, Germany.
- **Placed on the market by:** Rheinklinik Software GmbH, Im Neuenheimer Feld 582, 69120
  Heidelberg, Germany. Contact: regulatory@rheinklinik-software.example. The same name and address
  are shown on the product's about screen and in the instructions for use (Art. 16(b)).
- **Deployed by:** hospitals that run our software inside their patient data management system.
  Our customers are public hospitals and university clinics in Germany, Austria and the
  Netherlands; these are bodies governed by public law.
- **Importer / distributor / authorised representative:** none. Sold directly, from the Union.
- **Changed after placing?** Hospitals configure alert thresholds within the documented range and
  receive our updates. Our terms forbid retraining the model or changing its intended purpose.
- **This card is written by:** Rheinklinik Software GmbH — the provider and the manufacturer.

## Scope and status

- **Where it is used:** placed on the market in the Union and used in hospitals in the Union.
- **Exclusions claimed:** none.
- **Part of a regulated product:** yes. SepsisWatch is itself a medical device under Regulation
  (EU) 2017/745 on medical devices, class IIb, and medical devices are listed in Annex I,
  Section A, of the AI Act. The software is the safety component of the care pathway it supports:
  a missed or late alert can endanger a patient's health.
- **Who assesses the product's conformity:** conformity is assessed by a notified body designated
  under Regulation (EU) 2017/745 (notified body 0123, Annex IX quality management system route).
  The EU certificate is listed in Annex B of this card.
- **Placed on the market:** version 1.0 in May 2024; version 2.3 in June 2026.
- **Live trials before release:** a clinical investigation ran in 2023 under the medical device
  rules, inside the hospital setting. Each later version is validated on retrospective records.

## Use case 1: early warning of sepsis

**Intended purpose.** Continuous monitoring of adult inpatients on general wards for early signs of
sepsis, producing an alert to the ward nurse and the attending physician. Affects: patients.

**How outputs are produced.** A gradient-boosted model trained on 1.4 million hours of vital-sign
and laboratory time series from 11 hospitals, producing an hourly deterioration score from heart
rate, respiratory rate, temperature, blood pressure, oxygen saturation, lactate and white cell
count.

**What it does to a person.** It produces a clinical risk estimate for the patient being monitored
and raises an alert when the estimate crosses the configured threshold. It recommends no treatment.

**What it does not do.** It does not diagnose, prescribe, or change any device setting. It reads
monitoring data and writes an alert; nothing else.

**Effect on the decision.** The alert prompts a bedside assessment by a clinician, who decides.
Clinicians see the contributing measurements beside the alert.

**Human involvement.** A nurse acknowledges every alert; an unacknowledged alert escalates to the
attending physician after fifteen minutes.

**Content generation / interaction.** None. The system does not generate text and does not
interact with patients.

## Risk management

A risk management system is established, implemented, documented and maintained for the whole
lifecycle of SepsisWatch, integrated with the ISO 14971 risk management file required under the
medical device rules, and reviewed at every release and after every reported incident. Identified
risks to health and safety: a missed case (false negative) delaying treatment; alert fatigue from
false positives leading staff to ignore true alerts; degraded accuracy for patient groups
under-represented in the training data, in particular patients under 40 and patients with chronic
kidney disease. Reasonably foreseeable misuse analysed: use on paediatric wards and in intensive
care, both outside the intended purpose; the software refuses to run on beds registered to those
units. Adopted measures: threshold tuned per ward to a sensitivity of at least 0.85 at a positive
predictive value of at least 0.25; mandatory bedside assessment protocol in the instructions for
use; monthly review of alert-to-confirmation ratios per ward through post-market monitoring.
Residual risk after these measures is judged acceptable against the benefit of earlier treatment,
and that judgement is recorded in the risk management file with the clinical evidence it rests on.

## Accuracy and robustness

Declared performance on the held-out validation set (3 hospitals, 212,000 patient-hours, 2025):
sensitivity 0.87, specificity 0.91, positive predictive value 0.27, area under the ROC curve 0.93,
median lead time before clinical recognition 5.2 hours. Per-subgroup sensitivity is reported in
Annex A and ranges from 0.81 to 0.90. Robustness: missing vital signs are handled by carrying the
last value forward for at most two hours and then suppressing the score with a "data incomplete"
flag; the model is tested against sensor-dropout and unit-mismatch scenarios before each release.
Cybersecurity: the model and its thresholds are signed and verified at load; inputs are accepted
only from the hospital's authenticated data management system.

## Human oversight

Clinicians can override or dismiss any alert. Oversight is appropriate to the setting.

## Out of scope

Not validated for children, for intensive care units, or for use outside a hospital ward.

## Annexes

- **Annex A** — Performance by subgroup and by hospital.
- **Annex B** — EU certificate issued by notified body 0123 and declaration of conformity.
