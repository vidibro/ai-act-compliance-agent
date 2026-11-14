# LiftGuard — system card

**Version / date:** 1.4 — February 2026

## Parties

- **Developed by:** Ascensori Intelligenti S.r.l., Milan, Italy.
- **Placed on the market by:** Ascensori Intelligenti S.r.l., Via Tortona 37, 20144 Milan, Italy.
  Contact: info@ascensori-intelligenti.example.
- **Deployed by:** building operators and lift maintenance companies in the Union.
- **This card is written by:** Ascensori Intelligenti S.r.l. — the provider.

## Scope and status

- **Where it is used:** placed on the market in the Union and installed in lifts in the Union.
- **Exclusions claimed:** none.
- **Part of a regulated product:** yes. LiftGuard is a safety component of lifts covered by
  Directive 2014/33/EU on lifts and safety components for lifts, which is listed in Annex I of the
  AI Act. Its failure could endanger the safety of passengers.
- **Placed on the market:** version 1.0 in September 2025.

## Use case 1: predictive door and brake safety interlock

**Intended purpose.** Monitoring door sensor and brake actuator signals in passenger lifts,
predicting imminent brake or door failure and holding the car at the nearest landing with doors
open when a failure is predicted. Affects: lift passengers and maintenance staff.

**How outputs are produced.** A recurrent neural network trained on 38,000 hours of sensor traces
from 900 lifts classifies the current signal window as normal, degraded or imminent failure.

**What it does to a person.** Nothing about any person; it reads machine signals and stops the
lift safely.

**Human involvement.** A maintenance technician is notified on every hold and releases the lift
after inspection.

**Content generation / interaction.** The display in the car shows a fixed "Lift held for safety
check" notice. No text is generated.

## Out of scope

Not for escalators, goods lifts or construction hoists.
