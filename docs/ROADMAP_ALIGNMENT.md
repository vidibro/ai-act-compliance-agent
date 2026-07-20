# Roadmap ↔ Repo Alignment

_Audit date: 2026-07-17. Updated 2026-07-18 (dev/held-out split landed; rule count + article-store
notes reconciled). Compares [ROADMAP.md](ROADMAP.md) against what is actually in the tree._

**Verified this run (2026-07-18):** `pytest` → 53 passed; `python scripts/run_eval.py` → runs on
the `dev` split (19 cases, 133 rule-level judgements), prints the CATCH / FALSE-POSITIVE /
INADEQUATE scorecard; `--split test` correctly reports the held-out split is empty by design.

## Milestone status

| Milestone | State | Evidence |
|---|---|---|
| **M0 — Schemas** | ✅ Done | `enums.py`, `policy.py`, `system.py`, `classification.py`, `report.py`, `eval.py`. Profiling carve-back enforced by validator (`classification.py:64` `_enforce_profiling_carve_back`). Eval-only enums (`AblationType`, `Difficulty`) moved out of `enums.py` into `eval.py`. |
| **M1 — Golden-set** | 🟡 Half | Layer 2 fully built + dev/test split architecture in place. Layer 1 + the 3 required cases still missing. See below. |
| **M2 — Policy spec** | ✅ Done (ahead) | `data/policy/spec.yaml` = **19 rules** (v0.4.0); `policy_loader.py` resolves `requirement` verbatim from the **version-scoped** article store `data/policy/articles/2024-07-12/` (all 113 articles ingested by `fetch_articles.py`); paraphrase rejected; a literal-substring test guarantees no drift. Coverage ledger `scope-2024-07-12.yaml` classifies all 113 articles (in-scope vs out-of-scope-with-reason); a test blocks any unclassified article. |
| **M3 — Classification graph** | ❌ Not started | `src/aiact/graph/` is empty (`.gitkeep` only). No LangGraph nodes, no Langfuse wiring. Schema exists, but nothing runs the cascade. |
| **M4 — Gap-analysis checker (RAG)** | ❌ Not started | `src/aiact/tools/` empty. No Chroma ingest/retrieval. Only the keyword strawman exists. |
| **M5 — Eval (numbers)** | 🟡 Harness done, no agent | `eval/runner.py` + `run_eval.py` produce the CATCH / FALSE-POSITIVE / INADEQUATE breakdown, now split-aware (`--split dev/test/all`). Only checker is `baseline.py` (strawman). No classification-accuracy eval, no cost reporting. |
| **M6 — Packaging** | ❌ Stub | `README.md` is ~18 lines (honest scaffold note + disclaimer). No FastAPI, no diagram, no demo, no trace shown. |

## The gap that matters most

The roadmap states the **required cases "are the point of the project"** — and none of the three exist:

- **The flip / misclassification case** (CV parser → `not_high_risk`; +1 sentence → `high_risk` via
  profiling carve-back). This is named as *both* the core differentiator *and* the 2-min demo. **Missing.**
- **The prohibited case** (video-interview emotion recognition, Art. 5). **Missing.** The
  "is hiring a workplace?" open question is also still unresolved.
- **The transparency case** (job-ad generator → `minimal` but Art. 50 applies). **Missing.**

More broadly: **Layer 1 (classification golden-set)** — real noisy texts with a buried decisive
fact — does not exist. The golden set is currently **Layer 2 only**: 18 ablation cases over
`AIA-HR-A09..A15` + 1 pristine, all derived from the single `hr-candidate-scoring.md` reference.

## Where effort actually went vs. the plan's sequencing

The roadmap's open question was "evals before a working agent = measuring nothing." What's on disk
is the **defensible** version of building-early:

- Layer-2 golden set is **generated, not hand-written** (`make_golden_set.py`, deterministic, tags
  stripped) → ground truth is exact by construction. ✅ matches the plan's intent.
- The eval already **proves the thesis on the strawman**: keyword baseline scores **INADEQUATE
  detection 0/6, 0 INADEQUATE verdicts emitted**, 100% false-positive-free on intact rules,
  ~88% overall — i.e. the number that looks fine hides the capability that matters. That's a real
  proof-point to keep.

But depth landed on the **gap-analysis / M4-eval** side (Layer 2), while the **classification /
M3** side (Layer 1 + the flip case) — the stated *differentiator and demo* — hasn't been started.
Two of the eval's own columns are still thin: `distractor` cases exist for only 4 of 7 rules
(A09, A10, A14, A15), so the curve the roadmap wants to show is partial.

## Resolved since the 2026-07-17 audit

- **dev/held-out split — DONE (audit action #3).** `eval.py` now has a `Split` type and a
  `GoldenCase.split` field (default `test` — a case is held out unless it opts into `dev`);
  `GoldenSet.for_split()` filters; `ablations.yaml` carries `default_split`; `run_eval.py` takes
  `--split dev/test/all` and refuses to score/quote an empty split. **Current structure: all 19
  cases are `dev`; the held-out `test` split is intentionally EMPTY, to be authored later as fresh,
  never-inspected documents.** Two tests pin this so it only changes deliberately. NOTE: this
  satisfies the *architecture* the audit asked for; it does **not** yet satisfy the roadmap's
  ~5/15 dev/test *ratio*, because there is no held-out data yet.
- **Article store is version-scoped** (`articles/<act_version_date>/`) and the loader asserts the
  store version matches the spec's pin — closing a silent text-drift hole the audit predates.
- **Coverage ledger** (`scope-2024-07-12.yaml`) added; authoring it surfaced **Art. 72 and 73** as
  provider obligations the initial ruleset had missed (hence 17 → 19 rules).
- **Date-label deviation resolved.** ROADMAP.md previously labelled the baseline "OJ 13.06.2024",
  which is wrong: **13 June 2024** is the *date of the act* (its adoption, and part of its title),
  while **12 July 2024** is the *OJ publication date* (OJ L, 2024/1689, 12.7.2024) — the manifestation
  actually fetched. Same original text, two different milestones. The repo already pinned the
  correct one (`act_version_date: 2024-07-12`, matching the EUR-Lex/Formex manifestation); ROADMAP.md
  is now corrected to match. (The earlier draft of this doc called the ingested text a "corrigendum"
  — that was inaccurate; it is the **original OJ publication**, no corrigendum or consolidation
  applied.)

## Deviations / decisions taken that the roadmap didn't specify

- Spec is versioned `0.4.0` and pins `act_version_date: 2024-07-12` (the OJ publication date — see
  the date-label resolution above; ROADMAP.md reconciled to match).
- Rule IDs split cleanly into `AIA-HR-*` (document-verifiable, Art. 9–15) and `AIA-PO-*` (process,
  `document_verifiable: false`) + one `AIA-NHR-A06-4`. This is a clean realisation of the roadmap's
  "honest `document_verifiable` flags" — arguably better than asked.
- Legal wording is **resolved verbatim from the article store at load time**, never hand-written in
  the spec — a stronger provenance guarantee than the roadmap specified.

## Suggested next actions (to re-align with the roadmap's own priorities)

1. **Build Layer 1 + the 3 required cases first** — especially the flip case. It's the demo, the
   differentiator, and the M3 DoD ("the flip case flips"). Right now the project cannot show its
   headline moment.
2. **Resolve the "workplace covers hiring?" question** (Commission Guidelines on prohibited
   practices) before labelling the prohibited case.
3. ~~Commit the dev/held-out split~~ — **DONE (structure)**; still needs real held-out `test` data
   authored to hit the roadmap's ~5/15 ratio.
4. Then start **M3 (LangGraph classification)** — it's the biggest unstarted block and gates the
   demo, the trace, and any classification eval numbers.
