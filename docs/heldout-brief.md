# Held-out authoring brief

The method for adding **held-out** classification cases. Reusable: it is written for whatever gap is
being covered, not for one batch. Read the whole file before starting.

## Why this is different from ordinary work here

A held-out score answers one question: *how does the classifier do on cases nobody arranged for it?*
That answer is only worth having if whoever wrote the cases did not know how the classifier behaves.
So this session works from **the enacted text and the source documents, and nothing else**.

A `PreToolUse` hook enforces it — `.claude/hooks/heldout-guard.py`, activated by renaming
`.claude/settings.heldout.json.disabled` to `.claude/settings.json`. Several files in this repo will
refuse to open. That is not a misconfiguration and there is no workaround to find: **the block is
the task.** If you catch yourself reasoning toward "I only need the format from that file", stop —
the format is available from the files you can read.

Do **not** run the classifier. Not once, not to check. A case you have watched the model answer is a
dev case, and the point of this session is to produce cases that are not.

The same rule applies in reverse, and it is the reason to do this BEFORE the code it will measure:
author the cases first, then build. Cases written after watching a node fail are cases shaped by
that failure.

## Input

The person who started this session will name a directory of source documents. Prefer real
documents — filings, technical files, vendor material — over invented ones: a description written by
someone who has read this repo carries its assumptions, and a real one does not. They should be
chosen without regard to what a classifier would make of them.

Third-party documents are **not committed**, whatever their licence. Public to read is not public to
redistribute. Paraphrase into your own words; do not copy sentences across.

## What to produce

Write cases to a NEW file under `data/golden_set/`, carrying `default_split: test`. It is the
`default_split` — not the filename — that marks a set held out, and every tool reads it from there.
For each source document:

1. **Write the `description`** — what a classifier will read, in your own words. Aim for the
   register of the existing held-out cases: what the system does, what it acts on, who is in the
   loop. Include what the document says even where it seems beside the point; a real system card is
   not curated. Do not add facts the document does not state, and do not sharpen an ambiguity it
   leaves open — an unclear source makes an `insufficient` case, which is worth having.

2. **Decide the answer key from the law** — `expected_risk_class` and the sub-answers. The schema is
   `ClassificationCase` in `src/aiact/schemas/eval.py`; it is documented and validated, and the
   validator rejects a key that contradicts the Regulation.

3. **Write `decisive_fact`** — the one fact that fixes the class, and why. If you cannot state it in
   a sentence, you have not decided the case yet.

4. **Set `split: test`** explicitly, even though it is the default.

5. **Record provenance** in `data/golden_set/heldout_sources.yaml` — one entry per case: identifier,
   URL, `sha256`, size, retrieval date. The documents are not kept, so the hash is what lets a
   reader fetch the original and prove it is the one the case was written from.
   `tests/test_heldout_sources.py` enforces this and will fail without it.

## The law you need

- `data/policy/articles/2026-07-27/article-006.md` — the classification rules
- `data/policy/articles/2026-07-27/article-002.md` — scope, and what it limits
- `data/policy/annexes/2026-07-27/annex-I.md` — the harmonisation legislation list
- `data/policy/annexes/2026-07-27/annex-III.md` — the listed high-risk areas
- `data/policy/articles/2026-07-27/article-050.md` — transparency, answered for every case

Read them. Do not work from memory of the AI Act: the point of this repo is that the text is
resolved verbatim from the Official Journal, and a case argued from recollection is worth less than
no case.

## Two things that will come up

**The source will not contain every fact the answer key wants.** A document written for one
jurisdiction, or one purpose, simply will not address what another regime asks. Where that happens
you have two honest options: reason from the enacted text to a class the document DOES support, or
record the case as `insufficient` with `needs_review` expected. Never invent the missing fact. Say
which you did, in `notes`.

**Real documents are messy.** Marketing language, irrelevant sections, a decisive fact stated once
in the middle of a table. Preserve that in the description — it is the `buried` difficulty band, and
it is more informative than a clean case.

## When you are done

Report: how many cases, their expected classes, and any case you found genuinely contestable.
Do not report a score, because you must not have run one.

Then tell the user to rename `.claude/settings.json` back to
`.claude/settings.heldout.json.disabled`. The guard blocks files ordinary work on this project
needs, which is why it stays off between authoring runs.
