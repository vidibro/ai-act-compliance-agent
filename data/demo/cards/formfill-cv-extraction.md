# FormFill — system card

**Version / date:** 2.8 — July 2026

## Parties

- **Developed by:** Tallinn Document AI OÜ, Tallinn, Estonia.
- **Placed on the market by:** Tallinn Document AI OÜ, Narva mnt 5, 10117 Tallinn, Estonia.
  Contact: compliance@tallinn-docai.example. The same details are shown on the product's settings
  page (Art. 16(b)).
- **Deployed by:** our customers, who are private-sector recruiters and staffing agencies in the
  Union. We sell into public-sector recruitment in no form.
- **Importer / distributor / authorised representative:** none. Sold directly, from the Union.
- **Changed after placing?** Customers map extracted fields to their own database columns. Our
  terms forbid retraining the model or using the fields to build any scoring feature.
- **This card is written by:** Tallinn Document AI OÜ — the provider.

## Scope and status

- **Where it is used:** sold to recruiters in the Union and used on applications for roles in
  the Union.
- **Exclusions claimed:** none.
- **Part of a regulated product:** none. Standalone software.
- **Placed on the market:** version 1.0 in January 2024; version 2.8 in July 2026.
- **Live trials before release:** none. Each version is validated offline on a held-out set of
  historical applications.

## Use case 1: application field extraction

**Intended purpose.** Populating the recruiter's applicant-tracking database from submitted
applications, in private-sector recruitment. Affects: job applicants.

**How outputs are produced.** A trained document-understanding model extracts fields from
free-text CVs and application forms in several formats; date and job-title normalisation is
rule-based.

**What it does to a person.** Nothing. This use case extracts stated facts from a document into
database fields. The system does not score, rank or evaluate the applicant, and it forms no view
of them.

**What it does not do.** No scoring, no ranking, no shortlisting, no matching against the vacancy,
no comparison between applicants. Extraction only. The product exposes no feature that orders or
filters applicants.

**Effect on the decision.** None. Recruiters see the same facts the applicant wrote, in database
fields instead of a CV, and decide on them as they would without the system. The original CV stays
attached to the record.

**Human involvement.** Recruiters read the extracted fields directly and correct them in the
tracking system. Extraction errors are visible against the original document.

**Content generation / interaction.** None. No text is generated and the system never communicates
with applicants.

## Art. 6(4) not-high-risk assessment

This assessment was documented before the system was placed on the market and is kept with the
technical file; the system is registered in the EU database under Art. 49(2).

**Annex III area.** The system is used in recruitment, an area listed in Annex III, point 4(a).

**Condition relied on.** The exemption relied on is Art. 6(3)(a), a narrow procedural task. The
system moves stated facts from one format to another, and it forms no view of the applicant.

**Why the derogation applies.** The system poses no significant risk of harm to health, safety or
fundamental rights, because no decision depends on its output beyond what the applicant wrote, and
it does not materially influence the outcome of any decision: the recruiter reads the same facts
either way. Extraction errors are visible to the recruiter against the original CV, which stays
attached to the record, and a wrong field is corrected rather than acted on.

**Profiling.** The system performs no profiling of natural persons. It infers no characteristic of
the applicant and builds no estimate about them; it transcribes what the application states.

**Review.** This assessment is reviewed at each release and whenever a feature is added. Any
feature that orders, filters or compares applicants would end the derogation and is excluded by
our terms and by the product's design.

## Out of scope

Not validated for internal promotion, contractor selection or academic admissions.
