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
whole document could not carry the same "verbatim, checkable" guarantee.

So the trust model is explicit:

| artifact | trust | role |
|---|---|---|
| `<doc>/source.pdf` | **authoritative, byte-exact** (sha256 in `source.md`) | the anchor everything traces to |
| `<doc>/snippets/*.md` | **hand-verified** (quoted by a person, checked against the cited page) | the citable unit |

We deliberately do **not** store a machine-extracted full text. We only need specific passages, and
each is lifted by hand and page-referenced so it stays checkable.

## Layout

```
guidance/
  <doc-ref>/            one directory per guidance document, e.g. C-2025-5052/
    source.pdf          the authoritative binary
    source.md           document metadata + sha256 of the PDF + non-binding caveat
    snippets/
      <slug>.md         one verbatim passage: quote + locator (paragraph/page) + source URL
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
- Guidance documents get re-issued (this one was: `C(2025) 884 final` draft-approval →
  `C(2025) 5052 final` finalised). `source.md` records which version, and the PDF sha detects silent
  changes at the source URL.
