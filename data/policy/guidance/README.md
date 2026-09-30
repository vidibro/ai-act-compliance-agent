# Commission guidance store

Interpretive guidance from the European Commission, kept **separate from the enacted-law store**
(`../articles/`, `../annexes/`) because it is a different kind of thing: the Commission's
**non-binding** reading of the AI Act, not the Act itself. The Court of Justice of the EU is the
only authoritative interpreter.

## Why this store is shaped differently from the article store

The Act is published as Formex XML, so `fetch_articles.py` can extract it verbatim and
deterministically, and a test asserts every `requirement` is a literal substring of the stored
text. Commission guidance is a **Communication** (e.g. `C(2025) 5052 final`) distributed only as a
**PDF** — never in the Official Journal, so there is no Formex, no CELEX, no structured source to
derive. PDF text extraction is lossy and extractor-dependent, so a machine transcription of the
whole document cannot carry the same "verbatim, checkable" guarantee on its own; two independent
engines agreeing on it is what earns it trust.

So the trust model is explicit:

| artifact | trust | role |
|---|---|---|
| `<doc>/source.pdf` | **authoritative, byte-exact** (sha256 in `source.md`) | the anchor everything traces to |
| `<doc>/paragraphs.yaml` | **derived, two engines** (regenerated from the PDF and compared byte for byte in tests) | the list of numbered paragraphs, and the text quotes are checked against |
| `<doc>/coverage.yaml` | **reviewed** (a decision per paragraph) | what was read, and what it did to the product |
| `<doc>/snippets/*.md` | **hand-verified, then machine-checked** (quoted by a person, matched against `paragraphs.yaml`) | the citable unit |

The extraction is never the authority. pdfplumber reads each numbered paragraph's body text — the
font sizes and page area `source.md` declares, which leaves out footnotes, footnote markers and page
numbers — and PDFium, an independent engine, reads the same body again. Where both yield the same
characters, spacing aside, the paragraph's text is trusted; where they differ (so far only the
overview table each document opens with), a decision resting on it needs a person to check the page.

`coverage.yaml` gives every paragraph a decision — `used`, `not_followed` or `no_effect`, the last
two with a reason — or lists it under `awaiting_review`, which is declared debt and may only shrink.
`aiact.guidance_coverage` fails the build on a paragraph with neither, on a quote that does not match
the extracted text, and on a `used` passage no question or rule receives (or a `not_followed` one that
some question or rule does). No build can prove a decision right; it proves none was skipped.
Regenerate the extraction with `scripts/extract_guidance_paragraphs.py`.

## Layout

```
guidance/
  <doc-ref>/            one directory per guidance document, e.g. C-2025-5052/
    source.pdf          the authoritative binary
    source.md           document metadata + sha256 of the PDF + non-binding caveat + body layout
    paragraphs.yaml     GENERATED machine extraction of the numbered paragraphs
    coverage.yaml       a decision for every paragraph, or awaiting review
    snippets/
      <slug>.md         one verbatim passage: quote + locator + `paragraphs:` + source URL
```

## Snippets are reusable across domains

A snippet is an ID'd interpretive fact (`<doc-ref>/<slug>`), not a per-case note. Recruitment is
one of eight Annex III high-risk areas; the same guidance — and, once adopted, the high-risk
classification guidelines under Art. 6 — will inform cases and rules across the other areas too. A
golden case, a `PolicyRule`, or a classification question cites a snippet by ID; many may cite the
same one. Add a passage when a second thing needs it, not before.

## Provenance / honesty rules

- Every snippet carries `binding: false`. A verdict that rests on a snippet must say it rests on
  **Commission interpretation**, not on enacted law.
- Guidance documents get re-issued (the prohibited-practices one was: `C(2025) 884 final`
  draft-approval → `C(2025) 5052 final` finalised). `source.md` records which version, and the PDF
  sha detects silent changes at the source URL. It does NOT detect a re-issue at a *new* URL, which
  is why `supersedes` is written by hand.
- **Do not read a document's status off its title page.** Both stored PDFs open with *"Approval of
  the content of the draft Communication"* — for `C(2025) 884` that meant draft, for
  `C(2026) 5054` it is the College's adoption wrapper on the final text. The Commission's own
  download labels settle it; each `source.md` records which, and why.
- A snippet's sha proves the QUOTE has not drifted. `source.md`'s `pdf_sha256` proves the DOCUMENT
  behind it has not — swap the PDF for another revision and every snippet still passes its own
  check while its page numbers point into a file that no longer says what they say. Both are
  tested (`tests/test_guidance.py`).
