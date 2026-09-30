---
issuer: European Commission
document: >-
  Communication from the Commission — Guidelines on the implementation of the transparency
  obligations for certain AI systems under Article 50 of Regulation (EU) 2024/1689 (AI Act)
reference: C(2026) 5054 final
adopted: 2026-07-20
language: EN
pages: 51
binding: false
authoritative_form: PDF (source.pdf in this directory) — never published in the OJ; no Formex/CELEX
  manifestation exists, so unlike the Act text there is no structured source to derive.
source_url: https://ai-act-service-desk.ec.europa.eu/sites/default/files/2026-07/guidelines_on_the_implementation_of_the_transparency_obligations_for_certain_ai_systems_under_article_50_of_the_ai_act_bzptwqhk0ikg1dtlddap41psfy_131215.pdf
pdf_sha256: 30861fc5de31205846f023068069c92fabc7271ebeac6af7bef68b97f0a33f66
supersedes: >-
  Nothing. This is the first Commission guidance on Art. 50. It replaces the draft published for
  consultation, which is not stored here.
retrieved_at: 2026-08-20
# What `paragraphs.yaml` reads as body text: these font sizes, above this line (points from the
# page head). That leaves out footnotes, footnote markers and page numbers; the contents page
# comes before paragraph (1) and is dropped with the cover.
body_font_sizes: [10.6, 11.0, 12.0, 13.0]
body_bottom_limit: 790
---

The authoritative document is `source.pdf` (sha256 above). `paragraphs.yaml` is a machine
extraction of its numbered paragraphs, read by two independent engines and never authoritative;
`coverage.yaml` records a decision for each. `snippets/` holds the passages we rely on, each quoted
by hand, checked against its cited PDF page, and matched against the extraction by the build.

These are the Commission's **non-binding** interpretation of Article 50 (`binding: false`). The
Court of Justice of the EU is the only authoritative interpreter. Any verdict that rests on a
snippet here must say it rests on Commission interpretation, not on enacted law.

## READ THIS BEFORE JUDGING ITS STATUS FROM THE FIRST PAGE

The PDF's own title page reads *"Approval of the content of the draft Communication from the
Commission"*. That wording is the College's adoption procedure, not a statement that these are
draft guidelines, and it is the same wording that made `C(2025) 884 final` a genuine draft-approval
later superseded by `C(2025) 5052 final` — so the resemblance is a trap worth naming rather than
leaving for the next reader to fall into.

These are FINAL. The Commission published two documents on 20 July 2026 and labels them itself:

  - `131215` — *"Guidelines on the implementation of the transparency obligations…"* — **this file**
  - `131214` — *"Communication to the Commission — Approval of the content of the Guidelines…"*,
    note "of the Guidelines", not "of the draft Guidelines"

If a later reference number appears for the same subject, treat this one as superseded and check
which the Commission is citing — the prohibited-practices guidance was re-issued exactly that way.
The `pdf_sha256` above detects a silent change at the source URL; it does not detect a re-issue at
a new one.

## Timing

Adopted less than two weeks before the Art. 50 obligations began to apply on 2 August 2026, and
after Regulation (EU) 2026/1744 was adopted — so unlike the prohibited-practices guidance, this one
was written against a text close to the version pinned in `data/policy/articles/2026-07-27/`.
