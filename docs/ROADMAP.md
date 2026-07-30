# Development Roadmap — AI Act Compliance Agent

**Repo:** `~/projects/my/ai-act-compliance-agent`
**Baseline:** Regulation (EU) 2024/1689 (of 13 June 2024), published OJ L, 2024/1689, 12.7.2024 — pinned as `act_version_date: 2024-07-12` (the OJ publication date; 13 June 2024 is the date of the act, not the OJ date)
**Goal:** public proof-of-work — an end-to-end agentic system with real eval numbers, traces, and clean packaging. The agent spans all eight Annex III high-risk areas; the FIRST area taken all the way to eval numbers is employment (Annex III(4)). Depth in one *shipped* vertical beats breadth of half-built ones.

**North star:** what gates the roles I'm targeting is not knowledge of frameworks, it's public proof of a working system. One vertical agent, shipped with eval numbers and a trace, is the deliverable. Everything below serves that.

## Locked decisions (do not relitigate)

- **Domain: EU AI Act.** The agent is architected to handle AI systems in **any of the eight Annex III high-risk areas** — biometrics (1), critical infrastructure (2), education (3), **employment (4)**, essential services (5), law enforcement (6), migration (7), justice & democracy (8). All eight are modelled in `AnnexIIIArea` and the classification graph reproduces the EC checker's multi-area flow, so no schema change is needed to cover a new area.
- **Employment (Annex III(4)) is the FIRST shipped vertical** — the one taken all the way to a golden-set, eval numbers, and a trace. Depth-first: employment ships end-to-end before a second area gets its own golden-set/gap-analysis coverage. This is a sequencing decision, not a limit on the architecture. Areas 1–3 and 5–8 classify but are not yet backed by area-specific golden-set cases.
- **Not CSRD, not M&A.** These are *other regulations/domains entirely* (sustainability reporting; deal due-diligence), outside the AI Act. Multi-area coverage *within* the AI Act is the goal; hopping to a different body of law is the scope creep the project guards against. See "Two ways projects like this die".
- Stack: Python 3.11+, Pydantic v2, LangGraph, Chroma (local), LiteLLM, Langfuse, Ragas + LLM-as-judge, FastAPI. `uv` / `ruff` / `pytest`.
- Classification graph reproduces the official EC Compliance Checker flow, with ONE deliberate deviation: profiling is a separate node evaluated before derogations (Art. 6(3) carve-back applies notwithstanding the exemptions).
- Ruleset is derived from the official EC checker output — not hand-invented, not LLM-generated. rule-compiler is NOT needed for v0.1. (Started at 18; the Art. 1–113 coverage ledger surfaced **Art. 72 and 73** as provider obligations the initial pass had missed, so `spec.yaml` v0.4.0 carries **19** rules.)
- Risk is decided per use case, not per system (Commission multi-sector rule).
- Positioning: the official checker asks the user the classifying questions; this agent reads the document and answers them itself, with citations — and catches the case where a provider genuinely misclassifies (e.g. a parser that quietly scores candidates → profiling).
- Framing: draft compliance checklist for expert review. NOT legal advice. Keep the Commission-style disclaimer everywhere.

## ✅ Resolved — sequencing (the "evals before the agent" worry)

The original worry was evals with nothing to evaluate. Settled the right way round: the golden-set
exists for **both** layers, and the Layer 1 classifier runs against it end-to-end and produces a real
number (5/6, see M3). Data landed before code, per death-mode #1 below.

The live sequencing risk is now a different one: **the held-out `test` split is empty in both layers**,
so every number so far is a *dev* number and may not be reported as anything else. Authoring held-out
cases is what converts "it works" into a publishable metric — and it must happen before any prompt
tuning against Layer 2.

## ▶ Current focus (decided 2026-07-22) — finish CLASSIFICATION to eval numbers, then start M4

Depth-first, per the north star: one job taken all the way beats two half-built ones. M8 is promoted
out of the tail because it is blocked by nothing — it depends on the cascade (M3, built), not on M4
or M5. Ordered so that the ruler is fixed before anything is measured against it, and ground truth
is authored before the code it judges:

1. ~~**Fix the Art. 50 answer key**~~ ✅ **done 2026-07-22.** Root cause was the field's silence on
   role, not the labels; two flipped to `true` on Art. 50(3), every case now records a
   `transparency_basis` naming its paragraph, and a validator compels one whenever the obligation
   is claimed. Dev score 3/6 → 6/6 — see the caveat in M3 about how much of that is the model
   improving versus the key conceding.
2. ~~**Author the insufficient-input case**~~ ✅ **done 2026-07-22** — `ats_workflow_unspecified`,
   plus a new `Difficulty.INSUFFICIENT` band (missing INPUT, kept apart from `ambiguous`, which is
   contested LAW). Restores Layer 1's `needs_review` coverage; all five risk classes now appear.
   **Fails against today's cascade as intended**, and instructively: the first draft left AI-ness
   unstated too and died at `is_ai` ("executes explicit instructions", HIGH confidence) — right
   disease, wrong node, and two unknowns at once. Re-drafted so exactly one fact is missing, it now
   fails at `profiling`: the model reads "an ML component determines queue order" as "evaluates and
   scores candidates", a fact the text does not contain, and answers `high_risk` at HIGH confidence.
   Note the direction flipped between drafts (`minimal`, then `high_risk`) — **which way it guesses
   is arbitrary; that it guesses confidently from silence is the defect.**
3. ~~**Silence ≠ inference**~~ ✅ **done 2026-07-22.** Root cause was smaller than the prompt: a bool
   question INSTRUCTED the model to "set value to true or false" — no third option — so it obeyed and
   picked one from what the text implied. Added an explicit `UNKNOWN` token (separate from `null`,
   which at annex_iii/derogation is already a real verdict) and offered it on every answer type.
   **Risk class 5/7 → 7/7, Art. 50 7/7 → 6/7.** Two over-correction rounds, both worth recording:
   demanding the fact appear in the QUESTION's terms cost `cv_parsing_fields` its Annex III area
   ("applicant-tracking", "CVs" state a recruitment use in other words); and the hatch then
   swallowed hard legal calls until told that `UNKNOWN` is about MISSING FACTS, not difficult law —
   the same line the golden set draws between `insufficient` and `ambiguous` difficulty.
4. ~~**Report the missing fact**~~ ✅ **done 2026-07-22.** `needs_review` now names the missing fact
   and the article that needed it, in the AUTHOR's words rather than the model's ("whether it
   evaluates, scores or ranks people — and on what (Art. 6(3))"), via `_WHAT_THE_NODE_NEEDED` — a
   test pins that every cascade node has an entry. New `AbstentionCause` keeps the two causes apart:
   `description_silent` (the user must supply the fact; re-running unchanged will not help) versus
   `reply_unusable` (a run failure — the documentation may be fine, and telling someone to rewrite
   adequate documentation would be worse than saying nothing). Also fixed a bug found while
   testing: an abstention was reporting that it "rests on non-binding Commission guidance" when it
   had rested on nothing — guidance now attaches only to answers that actually answered.

   > ⚠️ **Watch: over-abstention at `prohibited`.** On one live run the vague ATS case declined
   > there, on the ground that the description never states whether it infers emotions. Literally
   > true — and almost no description ever says "we do not infer emotions", so if that reasoning
   > generalises the tool abstains on nearly everything. Not happening yet (dev is 7/7), but the
   > distinction to make if it does: a description that never RAISES a capability is not silent
   > about it, whereas one that names an unspecified component (as this case does deliberately) is.
5. ~~**The system-card guide**~~ ✅ **done 2026-07-22** — `docs/system-card-guide.md`, one section
   per cascade question, each citing its provision, plus a fill-in template and a pre-submit
   checklist. Leads with the omission warning (an undocumented capability changes the report, not
   the legal position) and the three framing rules: function not benefit, one section per intended
   purpose, and say what the system does NOT do — since the Art. 6(3) exemptions turn on absence.
   Worked example folded into the guide as an appendix, rewriting the smoke set's real vendor page
   to the template. **Verified:** the card's scoring section classifies `high_risk` [high, no
   abstentions] exactly as the raw product page does. The DoD's "with higher confidence" is not
   measurable — the page was already `high`; the honest claim is parity, not improvement.
   Incidental confirmation of framing rule 2: the card's extraction section classifies
   `not_high_risk` (Art. 6(3)(a), profiling false) where the page collapsed the whole product into
   one `high_risk` verdict — two purposes, two tiers, which is what M7 will automate.
6. ~~**Layer 1 held-out cases**~~ ✅ **authored 2026-07-22** — `classification_cases_heldout.yaml`,
   9 cases, `split: test`, authored BLIND (labelled from the enacted text, classifier never run on
   them). All five risk classes; two second-of-their-kind grounds (Art. 5(1)(g) biometric
   categorisation; insufficient-input at the annex_iii node, not profiling); and the two traps the
   smoke check found that dev lacks — a high-risk case that loudly promises human oversight, a
   minimal case carrying cross-sell noise. Integrity pinned by `test_classification_cases_heldout.py`
   (no classifier run — that would leak it). **The reporting run is still pending**: run once against
   a frozen commit, record the date and git sha, and EXPECT a lower number than dev's 7/7 — that is
   the honest figure appearing for the first time, not a regression.
### The Annex III scope boundary (dev-side fix, 2026-07-22)

The held-out run's two risk misses both sat on the *minimal vs not_high_risk* line — is a
recruitment-adjacent tool inside Annex III(4) at all? Step 1 was legal, not tuning: read the text,
decide who was right. Verdict — the **model** had the boundary roughly inverted, not my key.

- Onboarding/admin around already-hired staff → **outside** Annex III (no 4(a) recruitment, no 4(b)
  named decision) → minimal. My label right, model wrong.
- Recruitment-phase preparatory tools (parse, OCR, de-duplicate applications) → **inside** 4(a)
  then carved back by Art. 6(3) → not_high_risk. Structural tell: 6(3)(a)/(d) only make sense if
  preparatory tasks are in scope to begin with. My label right, model wrong.

Fixed on the DEV side only (held-out untouched): two new dev cases on the exact line
(`leave_balance_tracker` → minimal; `candidate_dedupe_prep` → not_high_risk), and the annex_iii node
rewritten as two explicit tests — IN if the purpose substantively acts on the person or their
application (including mere preparation of it); OUT for general admin (leave, payroll, IT) or
surrounding logistics (calendars, rooms, scheduling). Took three iterations, each caught by a dev
regression: v1 fixed admin but broke `cv_parsing_fields`; v2 fixed parsing but tipped
`interview_scheduler`; v3 (substantive-processing vs logistics) landed **dev 9/9** with no
regression. The distinction is the Act's own — every 4(a) example substantively acts on the
candidate or application; scheduling and room-booking do not.

> Held-out is now owed a re-measure to see if the fix generalises — but sparingly, and NOT now: it
> was authored to catch exactly this, and re-running after every dev change spends its honesty. Defer
> to a genuine milestone (end of the classification block), and expect it still won't be a clean 9/9.

7. ~~**Langfuse**~~ 🟡 **plumbing done 2026-07-22; visible trace needs your keys.** `src/aiact/tracing.py`
   wires LiteLLM's Langfuse callback: one trace per `classify()` run, each node's LLM call a span
   under it tagged by `node_id` — the decision path. STRICT no-op without keys (never imports
   langfuse, no network, run is byte-identical), verified by `test_tracing.py` and a manual check.
   `enable_tracing()` gates on BOTH keys being non-empty; the golden runner prints ON/off. **What
   remains is yours:** set `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` (see `.env.example`), run
   `scripts/classify.py --golden`, confirm one trace per case with node spans, and capture the
   screenshot the M3/M6 DoD wants. M4's retrieval is now born observable, which was the reason to
   wire this before it.

   **Decision (2026-07-22): Langfuse Cloud, free tier — not self-hosted.** The trace data is
   anonymised function descriptions and legal classifications (the repo rule already keeps vendor
   names out), so shipping it to a third party is low-stakes, and Cloud is two keys vs a Docker +
   Postgres stack for one screenshot. `LANGFUSE_HOST` already points at `cloud.langfuse.com`. Free
   tier is ~50k trace-events/month against ~40 calls per golden run — effectively $0; verify the
   current limit on their site at signup. Langfuse only OBSERVES: it adds no model cost, and the
   ~$0.13/run Anthropic spend in `usage.py` is unchanged whether tracing is on or off. Self-hosting
   stays a known option for confidential data or fully-offline runs (a fair interview point), not
   needed here.

8. ~~**Verify the article/annex store's sha256 at load**~~ ✅ **done 2026-07-26.** `verify_integrity`
   in `policy_loader.py`, applied at BOTH read paths: `_read_article` (resolving a rule's
   requirement) and — the one that matters more — `_provision_text` in `classify.py`, which puts law
   text straight into the prompt and previously had no check at all. All 126 stored files verify;
   tampering, a whitespace-only edit, or deleting the `sha256:` line each raise
   (`tests/test_law_integrity.py`, 7 tests). The covered span was derived from the generator, not
   guessed: `fetch_articles.py` writes `front + body` and hashes `body`, so the check hashes the
   full body INCLUDING the "Article N / title" heading that `_read_article` strips for its own use.
   SECURITY.md's caveat is now a done item.

Then **M4**. Its Layer 2 data is already complete (dev + held-out), so nothing in this block blocks
it — but note M4 is the largest unstarted piece of the deliverable, so this block must stay tight
rather than expand to fill the time.

## Milestones

### M0 — Schemas ✅ (in progress / done)

Pydantic v2 contracts: enums, policy, system, classification (per-use-case), report. Citation structurally unavoidable; carve-back enforced by validator.
**DoD:** all models construct; validators reject invalid cases; multi-use-case test (parser + scorer + job-ad generator → 3 risk classes) passes; ruff clean.

### M1 — Golden-set (DATA — the real blocker, do before eval tuning) 🟡 Layer 2 done, Layer 1 short

**Status:** Layer 2 is **complete, dev AND held-out** — two reference documents, 38 case documents:

| | reference | manifest | output | cases | split |
|---|---|---|---|---|---|
| dev | `hr-candidate-scoring.md` (Annex III 4(a), recruitment) | `ablations.yaml` | `golden_set.json` | 19 | `dev` — tunable |
| held-out | `internal-mobility.md` (Annex III 4(b), promotion) | `ablations-heldout.yaml` | `golden_set_heldout.json` | 19 | `test` — reportable |

**The held-out unit is the DOCUMENT, not the answer key.** Layer 2 ground truth is exact by
construction — we know what we deleted — so what a checker actually overfits is one document's
prose: heading style, vocabulary, section order, register. More ablations of the same reference
would not be held out in any meaningful sense. Hence a second, deliberately dissimilar system
(employees/line managers/readiness bands, precision@5 and calibration rather than NDCG, lettered
parts in a different order), with a test asserting the two share no vendor, system or section
vocabulary. Distribution is mirrored exactly — same 19 cases, same ablation and difficulty mix —
because a held-out set estimates performance on unseen cases from the *same* population; making it
harder would produce a pessimistic number that measures nothing.

**Authored before any M4 code existed**, which is what makes it genuinely held out: no retrieval
behaviour had been observed and so none could have shaped it. Run once, at reporting time; record
the date and git sha with the number. If it is ever tuned against, it is dev permanently.

Layer 1 has **9 dev + 9 held-out = 18 cases** (≥15 met). Held-out authored blind; measured once at git `85ea48d` (7/9), then dev-side work below addressed the boundary it exposed — a re-measure is owed, sparingly. All five risk classes are
now represented, including `needs_review` via `ats_workflow_unspecified` (difficulty `insufficient`).

Two layers:

- **Layer 1 (classification):** real, noisy public texts (vendor pages, system cards) with a buried decisive fact. Ground truth = Art. 6(3) cascade. Split by `difficulty`.
- **Layer 2 (gap analysis):** synthetic technical docs with controlled ablations (`removed` / `present_but_inadequate` / `distractor` / `untouched`) generated from one full reference document. Ground truth is exact because we know what was altered.
- **Hold-out split** (e.g. 5 dev / 15 held-out) to avoid overfitting prompts. State this in README.

**Required cases (these must exist — they are the point of the project):**

- **The flip / misclassification case** (our core differentiator, make it an explicit test): a CV parser described as "field extraction only" → `not_high_risk` via derogation (a). Add one sentence — "…and ranks candidates by fit score" → `high_risk` via the profiling carve-back. Same document, one sentence, verdict flips. This is both the demo moment AND a regression test that the profiling node overrides a user-claimed derogation.
- **The prohibited case:** AI video-interview scoring facial expression / tone → likely prohibited (Art. 5, emotion recognition in the workplace), not high-risk. See open question below on whether "workplace" covers the hiring stage.
- **The transparency case:** job-ad generator → `minimal` risk BUT Art. 50 applies (generates synthetic text). Proves Art. 50 is evaluated independently of the risk class.

**DoD:** ≥15 classification cases incl. the three required cases above ❌ (6/15 — the three required cases all exist); ≥1 reference doc + ablation script producing a manifest ✅; dev/held-out split committed 🟡 (Layer 2 ✅ both halves; Layer 1 held-out still empty).

**Outstanding Layer 1 work:** ~9 more cases, of which at least one must be a genuinely-ambiguous
`needs_review` ground truth (see the side-effect note below), and the rest should be authored as
*never-inspected* held-out cases rather than more dev cases.

**Agreed sourcing strategy (2026-07-22): synthetic held-out first, real cases later.** Author the
held-out splits synthetically, develop against dev, and only once the synthetic held-out number is
satisfactory add real-world sourced cases. Rationale: for Layer 2 synthetic is the *only* option —
exact ablation ground truth requires authoring the document — and for Layer 1 it unblocks progress
without waiting on sourcing and anonymisation.

> ⚠️ **What a synthetic held-out number does and does not prove.** It proves the prompts were not
> memorised against the dev cases — a real and worthwhile claim. It does **not** prove the system
> works on real documents, because dev and test share an author, a register and an idea of what
> "buried" looks like; real vendor prose is messier, hedged, internally inconsistent, and silent in
> places no synthetic document is. Report it as "held-out synthetic", never as real-world accuracy.
> Mitigation agreed: pull **2–3 real anonymised descriptions in early as a distribution smoke-check**
> (not scored, not part of any split) so any synthetic-vs-real gap is discovered while it can still
> be acted on — rather than after the synthetic set is exhausted and burned.
>
> ✅ **Done (2026-07-22): `data/golden_set/smoke/`** — three anonymised real vendor descriptions
> (screening-and-ranking, video-interview-analysis, interview-coordination). Verdict: the synthetic
> set is realistic enough to keep tuning against, with **two gaps to close when Layer 1 held-out
> cases are authored** — (a) real pages prominently promise **human oversight, which is legally
> irrelevant to the class** (Annex III 4(a) and Art. 5(1)(f) apply regardless of who signs off) but
> reads exculpatory: a *distractor claim* our Layer 1 cases barely contain; (b) real minimal-risk
> pages carry **cross-sell noise from adjacent high-risk products**, a false-positive trap the
> synthetic set does not exercise. Full findings in that directory's README.

#### ✅ Resolved — "workplace" (Art. 5 emotion recognition) DOES cover hiring

The prohibited-practice ban on emotion recognition covers "workplace and education". Question was: does a recruitment / pre-employment interview count as "workplace"? **Resolved yes**, per the **Commission Guidelines on prohibited AI practices, C(2025) 5052 final (29 July 2025)** — "workplace" is to be interpreted broadly and expressly covers recruitment and hiring; the Guidelines give video-interview emotion analysis as a prohibited example. So `emotion_screening_candidates` is `prohibited`, not `needs_review`. (Note the version: C(2025) 5052 final, 29 Jul 2025, is the *finalised* guidelines — it supersedes C(2025) 884 final, 4 Feb 2025, which was only the *approval of the draft content*. Cite 5052.) The label carries a `guidance_refs` id into the new guidance store (`data/policy/guidance/`), which records the verbatim passage; a loader check makes a dangling or drifted citation fail.

> ⚠️ **Side effect — Layer 1 lost its only `needs_review` ground-truth case.** Resolving this label to `prohibited` means no classification case now exercises NEEDS_REVIEW. The abstention *path* is still covered by the graph routing tests (low confidence → needs_review), but a genuinely-ambiguous *ground-truth* case should be authored to restore coverage. **TODO: add one new ambiguous Layer 1 case.**
>
> ✅ **RESTORED 2026-07-22 via INSUFFICIENT INPUT, not legal ambiguity.** `ats_workflow_unspecified`: unambiguously an AI system, unambiguously used in recruitment, and silent on the one thing that decides the tier — what its ranking model orders on. Submission time evaluates nobody (Art. 6(3)(a) derogation → not_high_risk); predicted fit evaluates persons (profiling carve-back → high_risk). The text chooses neither, so `needs_review` is correct and no contested legal question was needed to author it. New `Difficulty.INSUFFICIENT` band keeps it apart from `ambiguous` (contested law), since averaging the two would make both bands unreadable. As predicted the cascade fails it — see the current-focus list.

#### ⏸ Deferred — is drafting a job advert "placing targeted job advertisements" (Annex III 4(a), high-risk)?

The `job_ad_generation` case turns on whether Annex III 4(a) — high-risk systems used "to place targeted job advertisements" — covers a tool that merely *drafts* advert copy (targeting is about *who sees* the ad, not *who writes* it). **Cannot be resolved authoritatively yet:** the relevant Commission guidance is the **draft** guidelines on classification of high-risk AI systems (Art. 6 / Annex III), published 19 May 2026 and open for consultation until **23 July 2026** — not adopted. Citing a draft under live consultation as ground truth would be wrong. **Action: leave `job_ad_generation` flagged as contested/provisional; revisit once the high-risk classification guidelines are formally adopted.** Unlike the prohibited-practices guidance (which resolved the emotion case cleanly), there is currently no adopted Commission position on this question.

### M2 — Policy spec (YAML)

The high-risk obligations from the EC checker — **19 rules**, `spec.yaml` v0.4.0 — in the `PolicyRule` schema. IDs split cleanly: `AIA-HR-*` (document-verifiable, Art. 9–15), `AIA-PO-*` (process, `document_verifiable: false`), and one `AIA-NHR-A06-4`. Legal wording is resolved VERBATIM from the version-scoped article store at load time, never hand-written in the spec, and a literal-substring test blocks paraphrase drift. Honest `document_verifiable` flags (Art. 16–21/43/47–49 = process obligations, not doc-checkable). Most of these obligations (Art. 9–15, 16–21) apply to **every** Annex III high-risk system regardless of area, so the spec largely generalises as-is. A few rules encode **employment-specific** choices that a second area would need to revisit — e.g. `AIA-PO-A43` picks the internal-control route (Annex VI, because employment is Annex III point 4) and `AIA-PO-A49` disapplies the point-2 registration exception. Area-specific derogation/conformity paths get split out when the second vertical lands.
**DoD:** `data/policy/*.yaml` loads and validates against `PolicySpec`.

### M3 — Classification graph (LangGraph) 🟡 built and scoring; Langfuse NOT wired

Nodes reproduce the EC flow; profiling split out; per-use-case resolution. Each node returns a `ClassificationAnswer` with evidence + `LegalSource`. Wire Langfuse from the first node.

**Built beyond the original sketch** (none of this was in the plan; record it so M6 can show it):

- **Evidence trail** — `ClassificationEvidence` carries `evidence_quote`: *which words in the documentation* drove each node's answer, not just which article was cited.
- **Provider seam** (`providers.py`) — every vendor-specific request parameter lives behind `ProviderProfile`, so "the model choice is config, not code" is true rather than aspirational. Profiles for Anthropic (adaptive/legacy), OpenAI (reasoning/classic), Gemini, Mistral. Guards the cross-vendor trap where LiteLLM translates `reasoning_effort` into a `thinking=` block that current Anthropic models reject with 400.
- **Cost instrumentation** (`usage.py`) — token/cost tally per run, printed by the golden runner. Unpriced models report "cost unknown", never a silent $0. Cache writes tracked separately from reads, and an ignored cache marker is reported rather than hidden.
- **Non-binding guidance layer** (`guidance.py` + `data/policy/guidance/`) — verbatim Commission passages, sha256-integrity-checked, supplied to the node where the enacted text leaves a question open, labelled NON-BINDING in the prompt, and surfaced in the verdict via `result.rests_on_guidance`. `GuidanceSource` is structurally unable to be `binding: true` — enacted law is cited with `LegalSource` and the two are never merged.

**Baseline measured (2026-07-22)** — Layer 1 dev set, `claude-haiku-4-5`, questions anchored in verbatim article/Annex text. **Two axes, reported separately and never averaged** (`src/aiact/eval/classification_score.py`):

- **risk class 9/9 (DEV, 9 cases)** — was 7/7 on 7 cases; +2 boundary cases added and the annex_iii node sharpened (see the Annex III boundary note below). Includes `job_ad_generation`, the deferred contested label the abstention work incidentally fixed.
- **Art. 50 6/7** — 0 false-positive, 0 false-negative, 1 abstained. Was 3/7 before the answer key was corrected, 7/7 briefly, then 5/7 while the abstention rule over-fired.

> ⚠️ **TREAT 7/7 AS A CEILING ARTEFACT, NOT A RESULT.** The dev set is SEVEN cases and the prompt was
> revised three times against it in one sitting, each time after reading which cases failed. That is
> what dev is for and none of it was cheating — but a number produced that way measures the prompt's
> fit to seven known descriptions, not the classifier's ability. **No Layer 1 held-out set exists**,
> so there is currently no honest number to report at all. Authoring one (current-focus item 6) is
> what would make any of this publishable; until then this figure belongs in a lab notebook.
>
> The single Art. 50 abstention is on `ats_workflow_unspecified`, whose ML component is deliberately
> unspecified — so "cannot tell whether Art. 50 attaches" is arguably the *correct* read and the
> `false` label the arguable one. Deliberately NOT flipped: moving the target to wherever the model
> lands is the failure mode already recorded above for the emotion cases, and doing it twice would
> make the answer key a record of model behaviour rather than of the law.

**HELD-OUT reporting run (2026-07-22, git `85ea48d`, `claude-haiku-4-5`, one run, read-only — NOT tuned against).** The first honest Layer 1 number:

- **risk class 7/9** (dev was 7/7 — the drop is the point, not a regression).
- **Art. 50 5/9** — 0 false-positive, 0 false-negative, **4 abstained**. Never wrong; over-cautious.

Both risk misses sit on the SAME fuzzy line — *minimal* (outside Annex III) vs *not_high_risk* (inside Annex III but derogated) — and in OPPOSITE directions from my labels: `h_onboarding_logistics_crosssell` I called minimal, the model said not_high_risk; `h_application_file_indexer` I called not_high_risk (derogation d), the model said minimal. Neither is the classifier being dumb; that boundary is genuinely hard and carries real consequence (not_high_risk still owes Art. 6(4)). It also exposes that **my own answer key may draw that line inconsistently** across the two cases. **Left untouched on purpose** — editing a held-out case after seeing it fail is exactly the tuning this set exists to prevent. The fix is a deliberate labelling decision or fresh cases, recorded for later, never a post-hoc patch. The 4 Art. 50 abstentions are the over-abstention risk already flagged in step 4, now visible on the transparency axis: for a compliance tool, declining beats a confident wrong answer, but it is worth watching.

~$0.084 per run (~$0.014 per case). Prompt caching is currently INERT: the stable prefix (~2.7k tokens) sits under Haiku 4.5's 4,096-token minimum, so the marker is sent and ignored — the runner says so out loud.

> ⚠️ **The Art. 50 axis was never scored until now.** `expected_transparency_obligation` had been in the answer key since the golden set was authored; the runner compared only `expected_risk_class`. So the Art. 50 node ran on every case from M3 onward and was never once checked. Found by the real-world smoke check, not by the eval — which is itself the argument for having run it.
>
> ✅ **Art. 50 answer key reviewed and corrected (2026-07-22).** Root cause was not the labels but the FIELD: Art. 50 is titled "Transparency obligations for providers AND deployers" and its paragraphs split by role — (1) direct interaction and (2) marking synthetic output bind the provider, (3) emotion recognition and (4) deep fakes bind the deployer — while `expected_transparency_obligation` said nothing about which it meant. Nobody had decided, so no label could be right or wrong. Now defined as *any* Art. 50 duty on either role, and every case carries a `transparency_basis` naming its paragraph, enforced by a validator whenever the obligation is claimed.
>
> Two labels changed, both `false` → `true`: `emotion_monitoring_employees` and `emotion_screening_candidates`, on Art. 50(3), which attaches to the *system type* and carves out only law-enforcement use. The Art. 5 prohibition does not disapply it — and Art. 5(1)(f) itself excepts medical and safety purposes, under which such a system is lawfully deployable and 50(3) squarely bites. `interview_scheduler` stays `false`: matching stated availability and emitting invitations is not being "intended to interact directly" under 50(1). Worth noting its real-world sibling in `data/golden_set/smoke/` converses over SMS and WhatsApp and would plausibly go the other way — the difference between the two is exactly the kind of fact a system card must state (M8).
>
> The node question was also widened: its examples named only paragraphs (1) and (2), omitting emotion recognition and deep fakes — half the article, and the half covering this project's own prohibited cases.
>
> ⚠️ **What 6/6 does NOT prove.** Two of the three "fixes" were the answer key moving to where the model already was — the model had said `true` on both emotion cases before anything changed, so that is us conceding, not the model improving. The only genuinely new behaviour is `interview_scheduler` flipping `true` → `false` after the question was widened. And the prompt was changed while looking at dev results, which is what dev is for, but means this is a *dev* number in the fullest sense. The real test is the held-out Layer 1 split, which does not exist yet.

**⚠️ Remaining DoD gap: Langfuse is not wired.** It is a declared dependency and a line in `config.py`'s docstring, nothing more. No node emits a trace. This is the last item standing between M3 and ✅, and M6's DoD ("a trace is shown") depends on it.

Art. 50 is NOT a node on the main branch. Transparency is checked independently of the risk class — a minimal-risk generator and a high-risk chatbot can both trigger it. Implement it as a separate check that always runs, not as a step in the risk cascade. Easy to get wrong because it doesn't sit on the main path.

Order matters: prohibited (Art. 5) is evaluated BEFORE high-risk. A prohibited system never reaches Art. 6.
**DoD:** each golden-set Layer-1 case runs end-to-end → `ClassificationResult`; trace visible in Langfuse showing the decision path; the flip case flips.

**Scope taken: ONE use case per run.** `GraphState` carries a single `description` + `use_case_id`, so `assemble` always emits `use_cases=[one]`. This is a deliberate cut, not an oversight — see M7 below. Everything through M6 is built on single-use-case input.

### M4 — Gap-analysis checker (RAG) ✅ DoD met — retrieval, judge and graph built and measured

Chroma ingest + retrieval as a TOOL the agent calls per active rule. Verdict per rule: pass / gap / inadequate / not_applicable. This is where `inadequate` vs `gap` earns its keep.

**Status: DoD met. Retrieval, judge and graph built; the distractor column and the reference tool's keep/drop remain open.**

Done — `src/aiact/retrieval/` (chunking + Chroma) and `src/aiact/tools/evidence.py` (the per-rule tool), 25 tests:
- **Heading-aware chunking** with exact source offsets, so a verdict can cite `Part E — … [chars N-M]` and have it resolve. A chunk never straddles two sections — evidence for Art. 14 must not arrive carrying half of Art. 15's.
- **One Chroma collection per document, named by the document's sha256.** Cross-document leakage is unreachable rather than merely unlikely (crediting a provider with another file's evidence is the worst bug this project could ship), and re-indexing unchanged text is free, so the eval re-runs without re-embedding.
- **Local embeddings** (Chroma's bundled all-MiniLM-L6-v2 ONNX). Chosen so the eval stays offline, free and reproducible, and so searching a document never ships it to a third party; `embedding_function` is a parameter, so it is a choice not a constraint.
- **In-memory by default — the tool keeps no copy of the document it checks.** Indexing a 22k-character file costs ~300 ms against LLM calls that cost seconds, so persistence buys nothing worth keeping a provider's confidential technical file for. Persistence is opt-in for the eval (whose corpus is already committed here), `drop()` cleans up, and a test asserts the default writes nothing to disk. SECURITY.md's retention claim rests on that test.
- **The tool refuses non-document-verifiable rules.** Art. 17-21/43/47-49/72-73 are process obligations of the provider organisation; searching a technical file for them returns four unrelated paragraphs and hands a checker every chance to talk itself into PASS.
- Retrieval query is `evidence_expected`, not `requirement` — legislative register embeds badly against product prose. The spec's retrieval hint, finally used for retrieval.

Pinned in the tests because everything downstream depends on it: **a vector search always returns k results.** There is no "nothing found", so retrieval can never conclude GAP on its own — only a judge reading the passages can. That is precisely why GAP-vs-INADEQUATE has to be a model judgement.

**Measured on dev (2026-07-27), ad hoc — reproduce by indexing the pristine case document and calling `find_evidence` per rule; the numbers below are the record.** Retrieval routes correctly: the top hit is the right section for **7 of 7** document-verifiable rules on the pristine document. Dev only — the held-out document's lettered layout has deliberately NOT been run, so "nothing keys on section position" is still a design claim, not a measurement.

Then the number that matters. Top-hit cosine distance, pristine vs each ablation:

| rule | pristine | removed | inadequate | distractor |
|---|---|---|---|---|
| A09 | 1.072 | 1.142 | **1.067** | 1.142 |
| A10 | 1.302 | 1.433 | **0.982** | 1.352 |
| A11 | 0.963 | 1.013 | 1.013 | — |
| A12 | 1.074 | 1.528 | **0.956** | — |
| A13 | 1.309 | 1.326 | 1.326 | — |
| A14 | 0.905 | 1.245 | **1.067** | 1.245 |
| A15 | 1.019 | 1.059 | **0.942** | 1.059 |

`removed` moves distance the right way every time, but by as little as 0.05 (A13, A15) — nowhere near a usable threshold. And on `present_but_inadequate` distance goes the WRONG way in 5 of 7: the hollow assertion scores *closer* to the requirement than the real section it replaced. That is not a defect, it is what similarity measures — "we ensure human oversight" restates the obligation, while the compliant section is full of stop controls and training modules, i.e. specifics that no abstract statement of the requirement resembles.

**So similarity is anti-correlated with compliance on exactly the class the project exists to detect.** Any threshold on distance would rank empty assurances above genuine evidence — the strawman's failure mode with better maths. It settles a design question rather than raising one: distance is context for a judge, never a verdict, and the checker must read the passages. Report this table next to the keyword baseline's 0-of-6; together they are the argument for the architecture.

**The judge is built** (`src/aiact/gap/judge.py`, 26 tests) and wired into the runner as a `Checker`: `python scripts/run_eval.py --checker judge`. Per-rule rubrics come from `CheckType`, so a PRESENCE obligation is not judged by a SUBSTANCE standard — which is what the Art. 12 `expect: pass` probe exists to catch.

**Dev, 2026-07-27, Haiku 4.5, k=10 — 133 judgements, $0.48:**

| | strawman | judge |
|---|---|---|
| **INADEQUATE detection** | **0 / 6** | **6 / 6** |
| `present_but_inadequate` | 14.3% | **100%** |
| false positives (115 intact) | 100% | **100%** |
| `removed` | 14.3% | 14.3% |
| `distractor` | 0% | 25% |
| overall | 88.0% | 93.2% |

The headline is the first row: the distinction the project exists to make, which word-matching cannot make at all, is made 6 times out of 6 — **without** paying for it in false alarms. That combination is the claim; either half alone is cheap.

**`k` is a function of chunk size, and forgetting that cost a full run.** The first attempt scored **45.1%** — worse than the strawman — emitting INADEQUATE 79 times in 133. Not bad judgement: starvation. `k=4` was chosen when chunks were 1200 characters and showed ~32% of a file; the 128-token budget cut the average chunk to ~330 characters, so the same k showed **10%**. A judge shown a risk section's opening but not its mitigations three chunks later sees a process with nothing behind it and correctly calls it hollow. On the pristine compliant document, k=4 passed 3/7; k=10 passes 7/7 for 15% more tokens. **The chunking change was measured on what got EMBEDDED and silently changed what got JUDGED** — exactly the false-positive mechanism predicted in M4c, arriving from the direction nobody was watching.

**Remaining weakness: GAP.** `removed` 1/7 and `distractor` 1/4, unchanged by k (identical at k=4 and k=10, so this is not an evidence-volume problem). Both fail as `gap → inadequate` and, worse, `gap → pass`. The likely cause is the corpus doing what the roadmap already warned it does: a realistic technical file cross-references itself, so deleting §7 leaves "oversight measures are described in §7" standing elsewhere, and a pointer to nothing reads as an empty assertion rather than an absence. `gap → pass` is the dangerous one — a false clearance — and is what to attack next.

**Cost note:** the cache marker is sent and ignored on every call; the stable prefix is below Haiku's 4,096-token minimum. Real, but small next to the win from fixing k.

#### Model / effort sweep — dev, 2026-07-28, 133 judgements per run

Run through a LiteLLM proxy (`litellm_proxy/…`), so the sweep cost nothing; the dollar column is list price, because a free key during development hides a cost the caller pays under BYOK.

| checker | INADEQUATE | false pos | `removed` | `distractor` | overall | **$/run** | out tok |
|---|---|---|---|---|---|---|---|
| strawman (keywords) | 0/6 | 100% | 14.3% | 0% | 88.0% | **$0** | — |
| Haiku 4.5 *(no reasoning knob)* | **6/6** | 81.7% | 42.9% | 50% | 79.7% | $0.61 | 47k |
| Gemini 2.5 Pro, effort=high | 4/6 | 88.7% | **85.7%** | 50% | 86.5% | $3.63 | 320k |
| Gemini 2.5 Pro, **effort=low** | 5/6 | **95.7%** | 71.4% | 50% | **92.5%** | $1.77 | 134k |
| Gemini 2.5 Flash, effort=high | 1/6 | 66.1% | 57.1% | **75%** | 63.9% | $1.04 | 375k |
| Gemini 2.5 Flash, **effort=low** | 4/6 | 93.9% | 57.1% | 25% | 88.7% | $0.43 | 131k |
| **Gemini 2.5 Flash, effort=disable** | 5/6 | **98.3%** | 57.1% | 25% | **93.2%** | **$0.16** | **24k** |

**The transferable finding: LOW reasoning effort beats HIGH on every model tested, and costs half.** Flash went 1/6 → 4/6 on INADEQUATE and 66% → 94% on false positives; Pro went 4/6 → 5/6 and 88.7% → 95.7%. Both roughly halved their output bill, and reasoning tokens bill as output — at effort=high one call measured 2,388 reasoning tokens against 163 tokens of actual JSON.

Why it should have been predictable: the judge's task is bounded — read ten passages, apply one rubric, emit one of four tokens. Extended deliberation gives a model room to talk itself out of "this is hollow" and into "well, something is here". Corroborated from the other direction by Haiku, which has no effort knob at all, does no explicit reasoning, and holds the best INADEQUATE score in the table.

**The effect is monotonic all the way to zero**, and the last row is the recommendation: **Gemini 2.5 Flash with thinking DISABLED — cheapest tested AND best overall AND cleanest false-positive record** (1 wrong judgement in 115). It beats Pro-at-high-effort on every axis except `removed`, for **1/22nd the cost**.

Note the trap it exposes: on Gemini, OMITTING `reasoning_effort` is not the same as disabling it. Measured on one call — omit: 2,215 reasoning tokens; `low`: 843; `disable`: 0. Gemini 2.5 thinks by default and generously, where Anthropic's Haiku has nothing to think with. So "no reasoning parameter" means opposite things per vendor, which is precisely the class of thing `providers.py` exists to record — and `disable` is NOT a portable effort level (Anthropic has nothing to disable, OpenAI's reasoning family cannot be turned off).

**Caveat on the comparison:** every row ran a prompt iterated against HAIKU, so Haiku's 6/6 INADEQUATE is partly home advantage and the cheap cells are being judged on someone else's homework. Tuning for Flash-disable is the next move, not buying the expensive model.

**Settled:** effort is now three settings — `AIACT_LLM_EFFORT` (default) plus a `CLASSIFY` and a `JUDGE` override, all pinned to `none`. The classifier was then measured on Flash with thinking disabled: **9/9 risk class, 9/9 Art. 50, zero abstentions, $0.0045/case** — so both layers run the cheapest configuration tested, and the knobs exist for the next model swap.

#### The graph

`src/aiact/gap/graph.py` — three nodes, one of which uses a model:

    select_rules      which obligations apply, per use case      — pure data (gap/rules.py)
    check_compliance  does the documentation satisfy each one    — one LLM call per rule, concurrent
    assemble_report   findings, outstanding confirmations, counts — pure data

Selection is deterministic on purpose: activation is a property of the ruleset (`applies_to_risk_class`, `applies_to_role`, `status`), not a judgement. Only whether the documentation SATISFIES an active rule is a judgement. Same split as the classification cascade, for the same reason.

Three things the design pins, each because the alternative is a wrong report rather than a slow one:
- **Selection runs per USE CASE, not per system.** A product whose CV parsing is `not_high_risk` and whose candidate scoring is `high_risk` owes Chapter III on the scoring use case alone, assessed against that intended purpose — so the results are kept apart and the summary tallies both ways.
- **Non-document-verifiable rules are reported, never judged.** They land in `not_document_verifiable` as outstanding confirmations. Omitting them would read as full coverage of the Chapter III duties, which it is not; judging them would hand the checker four unrelated paragraphs and every chance to talk itself into PASS.
- **`NOT_APPLICABLE` is counted in neither `total_applicable` nor any verdict bucket.** A rule that never activated is not a check that passed.

Judgements share no state, so they run on a thread pool (`DEFAULT_WORKERS = 8`); `pool.map` preserves input order, so findings come back in rule order regardless of scheduling — a report whose contents depended on thread timing would not be defensible.

**DoD: ✅ met.** Layer-2 ablation docs run end to end → findings with citations; `untouched` requirements come back `pass` (98.3% false-positive control, 1 wrong judgement in 115). A throwaway script driving `classify()` and then `analyse()` by hand cost **$0.016** on a full document and reported `AIA-HR-A14` as a gap *because* its cross-reference resolved to nothing.

**The two graphs are NOT composed.** `analyse()` takes a `ClassificationResult` as an argument, and nothing in `src/` produces one and passes it on — only tests and that throwaway script call it. The seam is designed and typed; the caller does not exist. See M6.

**Still open in M4:**
1. **The distractor column is 4 cases.** One flip moves it 25 points, so it is not yet a measurement. Fill A11, A12 and A13.
2. **Does the cross-reference tool earn its place?** With it 91.0% / 95.7%; without it 93.2% / 98.3%. It is correct and it settles the GAP ambiguity deterministically, but it has not paid for itself. Decide on more cases, not on principle.
3. **Held-out has never been run** for Layer 2, and Layer 1 is owed a re-measure after the Annex III boundary fix and the model switch.

#### M4b — Non-English documentation (DECIDED: do it; sequenced after the judge works)

**The Act is a 24-language instrument.** A German provider's technical file is written in German, and a compliance tool that answers "translate it first" has inverted its own purpose. English-only was considered and **rejected as a product answer**, not deferred for lack of interest.

**Measured 2026-07-27, the current stack is English-only in practice:**

| setup | correct top hit | distances |
|---|---|---|
| EN document, EN query | **7 / 7** | 0.9 – 1.3 |
| DE document, EN query (what we have) | **3 / 7** | 1.4 – 1.8 |
| DE document, DE query | 4 / 4 | — (only 8 chunks; encouraging, not proven) |

At 1.4–1.8 the model is guessing, and two of the three hits look like cognate luck (*Dokumentation*, *Cybersicherheit*). The cause is the tokenizer: 30,522 English wordpieces, so `aufsicht`, `überwachung`, `nadzór`, `точность` are all out-of-vocabulary and shatter into meaningless fragments. Cyrillic and Greek are worse.

**The fix is a one-argument swap** — `paraphrase-multilingual-MiniLM-L12-v2` or `multilingual-e5-base`, which place a sentence and its translation at the same point, so the English `evidence_expected` hints keep working unchanged against a German document. `embedding_function` is already a parameter; the seam exists.

**Why it is sequenced after the judge, not before:** the golden set is entirely English, so swapping now produces a number nothing can verify — and multilingual models typically trade a little English accuracy for coverage, so the swap could quietly degrade the measured 7/7 with no way to notice. Needs a translated ablation set first (one reference document translated, same ablations — ground truth stays exact by construction).

Two things beyond retrieval that come with it, listed so they are not discovered late:
- **The judge must read the source language, and evidence quotes must stay in it.** Citing a translated sentence in a compliance report points at wording that is not in the provider's file — the same failure the sha256 check exists to prevent, arriving by a different route.
- **The article store is ENG Formex only.** Fine while the model reads both, but it means a German report cites English law text. Decide deliberately. EUR-Lex publishes all 24 language versions and each is equally authentic, so the text is available — but `fetch_articles.py` is not ready for it: `LANGUAGE = "ENG"` is a module constant and `ENG` is hardcoded into the resource URLs (lines 70, 103-106). Making it a real argument is a small job, and the store is already version-scoped by directory, so a language axis would sit alongside that naturally.

#### M4c — Overlap for UNSTRUCTURED documents (conditional, decide against the judge's numbers)

Chunking currently uses **no overlap**, and the reason was: a heading is a boundary the author deliberately placed, so there is nothing arbitrary to repair — while duplicated text would corrupt evidence counting (a judge reading k=4 passages that are really two-and-a-half reads repetition as corroboration) and make offsets ambiguous (one quote, two locators).

**That reasoning only holds for structured input.** Both reference documents have headings; a real provider's file may be a wall of text. Measured 2026-07-27 on a synthetic unstructured document (no headings, no paragraph breaks):

| input | chunks | all fit window | offsets exact | mid-sentence cuts |
|---|---|---|---|---|
| wall of text, 3.9k chars | 7 | ✅ | ✅ | none |
| headings + huge paragraphs, 7.9k | 14 | ✅ | ✅ | none |

Nothing breaks — the sentence splitter already handles it, since a document that IS one paragraph is just the extreme case of an over-long one. But quality degrades in two specific ways: `heading_path` is empty, so chunks carry no context into their vector; and chunks **mix obligations**, because nothing marks where one topic ends. Retrieval scored 5/6 on that document, and several hits were luck — the "correct" chunk also contained two unrelated obligations.

With no authored boundaries the cuts ARE arbitrary, which is precisely the situation overlap exists for. So the decision should be **conditional on structure**, not global: no overlap when headings are present, overlap when they are not. That also confines the duplication cost to the case that needs it.

**Do not add it on principle — add it on evidence.** The signal to watch is false INADEQUATE verdicts on unstructured documents whose content is actually complete: that is the fingerprint of an argument split across two chunks, where the judge sees a process with its measures missing. If the judge's eval shows it, add conditional overlap; if it does not, the duplication is not worth paying for.

Related: M8's system-card guide already tells users what structure to supply for CLASSIFICATION. The same argument extends to gap analysis — a technical file with headings is checked better, and saying so in the guide is fairer than silently penalising unstructured input.

### M5 — Eval (numbers)

- Classification: accuracy by `difficulty`; citation accuracy; reasoning-step accuracy.
- Gap: recall, precision, false-positive rate on `untouched`, accuracy by ablation type.
- Expect (and report) the curve: strong on `removed`, drop on `present_but_inadequate`, bigger drop on `distractor`. The curve IS the interview story.

**Strawman baseline already measured** (`python scripts/run_eval.py`, keyword matcher, Layer 2 dev, no API): overall **88.0%** — and that number is exactly why the breakdown is mandatory. Behind it: **INADEQUATE detection 0/6**, zero INADEQUATE verdicts emitted at all, catch rates 14.3% / 14.3% / 0.0% on removed / inadequate / distractor, and 100% clean on the 115 intact judgements. A checker that cannot make the project's central distinction still scores 88% on the aggregate. Keep this as the contrast the real numbers are reported against; a test pins the 0-INADEQUATE property so a future checker beating it registers as progress.

> ⚠️ **The distractor column is thin.** `distractor` cases exist for only **4 of 7** rules (A09, A10, A14, A15) — A11, A12 and A13 have none. The roadmap's headline curve (strong on `removed`, weaker on `present_but_inadequate`, weakest on `distractor`) is therefore partial at its most interesting end. Fill before reporting the curve.

**DoD:** one command produces the metrics table; cost per full run reported (LiteLLM).

### M6 — Packaging (this is a deliverable, not an afterthought)

README (problem → architecture diagram → eval numbers up top → use cases), 2-min demo (the flip-test: one sentence flips not_high_risk → high_risk), clean commit history, FastAPI endpoint (document in → structured report out).

> **First job here: compose the two graphs.** `classify()` and `analyse()` both work and are both measured, but nothing calls them in sequence — the pipeline exists as two halves with a typed seam (`ClassificationResult`) and no caller.
>
> **One document in.** Both halves already take a single string, and the composed entry point does the same: the user submits their documentation once, it is classified, and the same text is checked against whatever obligations that classification activates. Documentation quality is a quality-of-answer problem, not an input-format problem — a thin document yields a thin report, and M8's guide is where that is addressed.
>
> The two real decisions:
> - **Gating.** Chapter III attaches to high-risk use cases only. No high-risk use case → no gap analysis, and the report must SAY so rather than return an empty finding list that reads like a clean bill of health. `prohibited` is its own answer and must not fall through to obligation-checking.
> - **Per use case.** `analyse()` already selects per use case; the orchestrator passes the whole `ClassificationResult` through, never a collapsed overall class.
>
> Do this before the FastAPI layer, so the endpoint wraps a working pipeline instead of defining one.

Make the harness engineering visible. The observability/trace layer, the per-rule tool calls, the provider abstraction — these are engineering, not plumbing to hide. Show a Langfuse trace in the README. (Personal angle worth surfacing in interviews: prior experience running LiteLLM as a proxy with header rewriting, and MCP work — most candidates only use these as an SDK. That's harness engineering; name it.)

> **Decide `SystemUnderReview` and `DocumentChunk` here.** Both are exported from `schemas/` and referenced by nothing in `src/` — only by `test_schemas.py` and one docstring. They are anticipatory rather than dead: `SystemUnderReview` is the plausible request type for this endpoint. The endpoint settles it. If it takes raw text plus a `system_id` (what `gap.graph.analyse` already takes), both should be deleted — `DocumentChunk` is in any case superseded by `retrieval.Chunk`, which is what actually carries chunks at runtime. A schema nothing produces or consumes advertises a contract that does not exist. `ClassificationState` was removed for exactly this reason; these two were left only because M6 might still claim them.
>
> Also fix `ComplianceReport`'s docstring while there — it says "for one SystemUnderReview", which stopped being true when `analyse()` took a `system_id` and a document instead.

**DoD:** a stranger understands it in 2 min; `git clone` + README → runs; a trace is shown.

### M7 — Multi-use-case decomposition (deferred; do NOT start before M6 ships)

Art. 6 classifies per **intended purpose**, not per product, and the Commission is explicit that Chapter 3 obligations attach only to the high-risk use case, assessed against *that* purpose. So one product legitimately holds several classifications at once — the example already written into `UseCaseClassification`'s docstring: CV parsing → `not_high_risk` (derogation (a)); candidate scoring → `high_risk` (profiling carve-back); job-ad generation → `minimal` + Art. 50.

Collapsing a multi-purpose product into one classification fails in both directions: **under-report** (the whole product reads as not-high-risk because the benign purpose dominates the prose) or **over-report** (Art. 9–15 gap findings raised against a use case those obligations never attached to).

Shape:

    docs ──► extract_use_cases ──► [M3 cascade] × N ──► aggregate
                                                       overall = most severe
                                                       triggered_by = union
                                                       reasoning names the driving use case

What changes:
- The cascade itself: **nothing.** It is already per-use-case and brain-agnostic.
- `classify()` becomes a loop; the most-severe-wins aggregation moves into its own function with its own deterministic test — that rule is legal logic, not plumbing.
- **Art. 50 goes per use case.** It is asked once per cascade run, so N runs produce N answers for a field currently typed as a single `ClassificationAnswer | None`. The job-ad generator owes transparency; the scorer may not.
- `ClassificationResult.use_cases` is already a list, and `analyse()` already selects obligations per use case — so the downstream half of this is built. What is missing is upstream: something that produces more than one entry in that list.
- **Scope the EVIDENCE per use case, not just the rules.** `node_check_compliance` builds jobs carrying a `use_case_id`, then judges every one of them against the WHOLE document. Harmless while `classify()` yields exactly one use case — the document IS that use case's document — and a false clearance the moment it yields two: retrieval for the scoring use case's Art. 14 check can return the oversight paragraph written about the CV parser, and the scorer is credited with a control it does not have. **Cross-use-case evidence leakage** — the same class of bug as cross-document leakage, which per-document Chroma collections already make unreachable; this one is not yet closed. Deliberately deferred rather than missed: scoping evidence to a use case requires knowing which passages belong to it, which IS the decomposition problem, so it cannot be solved before the split works. Cheap to add then — `judge(rule, document)` gains a `use_case` argument, one call site. The `Checker` protocol stays as it is; the Layer-2 eval is per-rule-per-document by construction and has no use cases.

**Why it needs its own eval layer, and why that's the real cost:** the split is the hardest judgement in the pipeline and the least verifiable — "is this one purpose or three?" has no crisp answer in the enacted text, and a wrong split silently changes every downstream verdict. The current Layer 1 golden set is one-description-one-expected-class and **cannot measure it at all**. M7 requires cases whose ground truth is the *decomposition* (multi-function product doc → expected set of use cases), scored on set agreement, before any of its output can be trusted.
**DoD:** a multi-function reference doc yields ≥2 use cases with different risk classes; decomposition eval reports set agreement against hand-authored ground truth; obligations are raised only against the high-risk use case.

### M8 — System-card guide for CLASSIFICATION input ⬅️ PROMOTED to current focus (see top)

*Numbered M8 by when it was written down, not by when it runs. It is blocked by nothing: it depends
on the cascade (M3, built), not on M4 or M5. Sequenced at the top of this file.*

**The problem.** The agent reads what it is given. Users without documentation hand over a product
page, and the smoke check (`data/golden_set/smoke/`) showed exactly what that costs: real marketing
prose classified `not_high_risk` where the equivalent tidy description classified `minimal`, because
marketing copy states benefits and buries function. The fix is better input, not more tuning.

**Scope: the classification half only.** This is the system card a user writes *before* they know
their tier — the input to the Art. 5 / Art. 6 cascade. It is NOT a technical-documentation guide:
Annex IV already is one, it is authoritative, and the README points at it directly (see below).
The two are separate artefacts answering separate questions, and conflating them once already cost
this milestone a wrongful deletion.

**Why the Act cannot supply this one.** Annex IV presupposes a high-risk classification and so
describes the file you owe *after* the question is settled. Nothing in the Regulation templates the
description you need *to settle it*. The nearest authority is the Commission's own AI Act Compliance
Checker, which asks the user these questions directly — and answering them from a document instead
is this project's whole positioning.

**Content: the facts the cascade actually turns on,** one section per node, each citing its article.

| the card must state | node | source |
|---|---|---|
| that it is an AI system, and its **intended purpose** | `is_ai` | Art. 3(1) |
| whether it infers **emotions**, scrapes faces, scores social behaviour, manipulates | `prohibited` | Art. 5 |
| the **Annex III area** it operates in, if any | `annex_iii` | Art. 6(2), Annex III |
| whether it **evaluates or ranks natural persons** — the single most decisive fact | `profiling` | Art. 6(3) |
| whether it only performs a narrow procedural task / improves prior human work / detects patterns / is preparatory | `derogation` | Art. 6(3)(a)–(d) |
| whether it **generates content or interacts with people directly** | `transparency` | Art. 50 |
| whether the author is **provider or deployer** | scope | Art. 3(3), Art. 3(4) |

Plus the framing rules that make a card classifiable at all: describe **function, not benefit**;
state what the system does **to a person**; one section **per intended purpose** rather than per
product (which also seeds M7); and say what it does **not** do, since derogations turn on absence.

> ⚠️ **OMISSION IS THE RISK, not gaming.** A card written to satisfy the classifier is fine —
> describing your system accurately is the goal, not a loophole. The hazard runs the other way: a
> user who omits the ranking sentence gets a comfortable `not_high_risk`. The guide must say plainly
> that an omission changes the report, not the legal position, and that the flip case exists
> precisely because that sentence is the one providers leave out.

**The guide should not only be a document — the agent should say what is missing.** A vendor cannot
be expected to know in advance what makes a description valid; the tool already knows, per node.
`_abstain()` returns a low-confidence answer carrying its `node_id`, so *which* question went
unanswered is available today and is merely collapsed into `needs_review`. Surfacing it turns the
guide into a loop: *"You did not state whether the system ranks or scores candidates. Art. 6(3)
cannot be decided without it — add it and re-run."* Cheap, and far more likely to be acted on than a
document read up front.

> ⚠️ **Silence is not evidence of absence — and the cascade currently treats it as such.** A
> description that never mentions ranking may mean the system does not rank, or that the vendor did
> not say. For the Art. 6(3) derogations the difference is decisive: "narrow procedural task"
> requires positive evidence that the system does not evaluate people. **Live, not theoretical** —
> in the smoke check, `interview-coordination` (a marketing page that never addresses evaluation)
> returned `narrow_procedural_task` → `not_high_risk` at *high* confidence. Possibly right about
> that product, but reached from a document that never spoke to the question. Fix candidates: have
> the derogation node distinguish "the text asserts the system does not evaluate" from "the text is
> silent", and route silence to a request for information rather than to a derogation. Needs a
> golden-set case whose ground truth is *insufficient input* — a class Layer 1 does not yet have.

**Sequencing.** Depends only on the cascade (M3, built) — not on M4 or M5. Could ship alongside M6
packaging, where it doubles as documentation of what the agent actually reads. Worth doing before
authoring the Layer 1 held-out cases, since the card's sections are a checklist of what those cases
must vary.

**DoD:** `docs/system-card-guide.md` with a fill-in template, every ask citing its article; a card
written from it for one of the smoke-check systems classifies to the same tier as the full product
page, with higher confidence; the report names the specific fact and article a low-confidence node
was missing, rather than only saying `needs_review`; a silent description does not yield a
derogation; the omission warning stated explicitly; framing kept as draft-for-expert-review, not
legal advice.

### M9 — BYOK deployment (needs M6's FastAPI layer first)

Make the deployed product **bring-your-own-key (BYOK)**: each caller supplies their own LLM key so
they pay for their own inference and the operator never holds their credential.

> `SECURITY.md` **already exists** at the repo root (written 2026-07-22). It documents the current
> CLI/library posture — prompt-injection threat model first, secret handling, data flow, non-goals —
> and marks the BYOK controls below as **Planned**. When BYOK lands, move those items from Planned to
> current and add the test that proves the key never leaks.

**BYOK — per-request keys, not one operator key.** Today keys come from the environment (a single
operator identity: LiteLLM reads e.g. `ANTHROPIC_API_KEY`, and `get_settings()` reads the rest). For
a real product each caller supplies their own LLM key, so they pay for their own inference and the
operator never holds their credential. Shape:

- The FastAPI request carries the caller's key (Authorization header / a per-request field); it is
  injected into the LiteLLM call as `api_key=` **per request** and never persisted, never written to
  Chroma, never logged, never placed in Langfuse metadata (the trace metadata is an explicit
  allow-list today — `trace_id`, `node_id`, tags — which already keeps keys out; a test should pin
  that it never widens to carry a secret).
- `get_settings()` is `@lru_cache`-friendly for config but MUST NOT cache a secret across requests —
  keys live on the request, not on a process-global Settings. This is the one place the current
  env-based model has to change.
- Optional BYO Langfuse and BYO vector store per tenant, same principle, later.
- Redaction: keys scrubbed from error messages and stack traces before they leave the process.

**DoD:** a BYOK request path where the caller's key is used for that request and provably not
persisted or logged — a test asserts the key never appears in trace metadata, logs, or the vector
store; the corresponding `SECURITY.md` items moved from **Planned** to current.

## Backlog (post-v0.1, only after M6 ships)

- rule-compiler (generate policy spec from Act text) — for scaling to other Annex III areas.
- Deployer obligations (Art. 26) — separate ruleset.
- CSRD as a second domain — "same architecture, different rules" (mention only).
- Multi-language (Act available in DE on EUR-Lex).

## Two ways projects like this die (re-read when tempted)

1. **Data after code.** No golden-set → no eval → no numbers → indistinguishable from a tutorial.
2. **Scope creep / domain-hopping.** One shipped use case beats three half-built domains.

## Provenance / legal hygiene

- Pin `act_version_date` everywhere. Check EUR-Lex for a consolidated (Omnibus) version; record `amended_by` if found. Currently pinned: `act_version_date: 2024-07-12` (OJ publication date of the original text; verbatim article store lives in `data/policy/articles/2024-07-12/`).
- **Enacted law and Commission interpretation are stored and cited separately, and never merged.** `data/policy/articles|annexes/` hold verbatim enacted text cited with `LegalSource`; `data/policy/guidance/` holds verbatim passages from Commission Communications cited with `GuidanceSource` (`binding: false`, structurally enforced by a validator). Each guidance snippet records its document sha256 and its own body sha256, so a drifted or dangling citation fails at load rather than degrading silently. Any verdict that leaned on interpretation reports `rests_on_guidance` and names the CJEU as the authoritative interpreter. Currently one snippet: `C-2025-5052/workplace-covers-recruitment`.
- Vendor names never sit next to a legal verdict in the public repo. Classify anonymised function descriptions; keep vendor→archetype mapping private.
- Ground truth is an engineer's reading of the law, cross-checked against the Commission's own Guidelines/checker where possible. Say so. Don't oversell it as a benchmark.
