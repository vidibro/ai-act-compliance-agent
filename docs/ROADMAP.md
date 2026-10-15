# Development Roadmap — AI Act Compliance Agent

**Repo:** `~/projects/my/ai-act-compliance-agent`
**Baseline:** Regulation (EU) 2024/1689 (of 13 June 2024), as consolidated by Regulation (EU) 2026/1744 (Digital Omnibus on AI) and applicable from 27 July 2026 — pinned as `act_version_date: 2026-07-27`. The original OJ publication (OJ L, 2024/1689, 12.7.2024) is the text this project started from and is no longer in the store; it stays fetchable from the registry in `scripts/fetch_articles.py` — see *Provenance / legal hygiene*.
**Goal:** public proof-of-work — an end-to-end agentic system with real eval numbers, traces, and clean packaging. The agent spans all eight Annex III high-risk areas; the FIRST area taken all the way to eval numbers is employment (Annex III(4)). Depth in one *shipped* vertical beats breadth of half-built ones.

**North star:** what gates the roles I'm targeting is not knowledge of frameworks, it's public proof of a working system. One vertical agent, shipped with eval numbers and a trace, is the deliverable. Everything below serves that.

**Normative coverage migration:** the accepted strangler plan for moving from one disposition per
legal address to reviewed full-text spans and atomic normative propositions is recorded in
[`docs/NORMATIVE-COVERAGE-MIGRATION.md`](NORMATIVE-COVERAGE-MIGRATION.md). Preserve the current
coverage machinery during the migration. Phase 0's accepted scope and vocabulary are recorded in
[`docs/NORMATIVE-COVERAGE-SCOPE.md`](NORMATIVE-COVERAGE-SCOPE.md). The exact-span schemas, resolver,
cross-file validator, and versioned artifacts are complete. Every stored article and annex is now
present in the exact-span inventory. Reviewed findings live under
`data/policy/normative-coverage/<version>/` and compile through the version-independent
`src/aiact/norm_builder.py`; the representative extraction is proposed and measured in
[`data/policy/normative-coverage/2026-07-27/report.md`](../data/policy/normative-coverage/2026-07-27/report.md); independent review and timed
authoring remain before the pilot can exit.

## Locked decisions (do not relitigate)

- **Domain: EU AI Act.** The agent is architected to handle AI systems in **any of the eight Annex III high-risk areas** — biometrics (1), critical infrastructure (2), education (3), **employment (4)**, essential services (5), law enforcement (6), migration (7), justice & democracy (8). All eight are modelled in `AnnexIIIArea` and the classification graph reproduces the EC checker's multi-area flow, so no schema change is needed to cover a new area.
- **Employment (Annex III(4)) is the FIRST shipped vertical** — the one taken all the way to a golden-set, eval numbers, and a trace. Depth-first: employment ships end-to-end before a second area gets its own golden-set/gap-analysis coverage. This is a sequencing decision, not a limit on the architecture. Areas 1–3 and 5–8 classify but are not yet backed by area-specific golden-set cases.
- **Not CSRD, not M&A.** These are *other regulations/domains entirely* (sustainability reporting; deal due-diligence), outside the AI Act. Multi-area coverage *within* the AI Act is the goal; hopping to a different body of law is the scope creep the project guards against. See "Two ways projects like this die".
- Stack: Python 3.12+, Pydantic v2, LangGraph, Chroma (local), LiteLLM, Langfuse, LLM-as-judge, FastAPI. `uv` / `ruff` / `pytest`.
- **No RAG-metric library (Ragas and kin).** Those score free-form answers with an LLM because there is no exact key to compare against. Here there is one: every eval case resolves to a fixed label, and Layer 2's label is fixed by construction — the case is built by degrading a known-good document in one known way. Scoring is `expected == got`. Swapping an exact comparison for a paid, non-deterministic approximation of it would be a downgrade, and the numbers this project reports (catch rate per ablation type, false positives on untouched rules) are not metrics such a library has. Its one good idea is faithfulness — grading an output against the SOURCE rather than against an expected answer, which is the only thing you can check when no key exists. That idea is worth having; the library is not the way to get it. Applied to the `evidence_quote`, it is a substring check rather than a model call — `llm/quotes.py`.

**Measured on Layer 1 dev (2026-08-14), 18 cases / 100 node answers, `gemini-2.5-flash`, ~$0.12.** Every substantive answer cited a span — **silent: 0 of 98** — so the prompt's "tie the answer to a quotable span" rule holds on every node, bools and enums included. **The model invented nothing.** The check first rejected 6 quotes (6.1%); 4 were ellipsis-marked elisions of real text, which is ordinary citation practice and was the check's bug, not the model's. Handling the ellipsis took it to **2 of 98 (2.0%)**, both unmarked stitches — real sentences joined without marking the cut — and both attached to CORRECT answers (18/18 on the class axis, before and after). So a bad quote is DROPPED and the answer stands: escalating it to an abstention would have discarded right answers to catch nothing.
- Classification graph reproduces the official EC Compliance Checker flow, with TWO deliberate deviations, both splitting a node the checker merges: profiling is evaluated before derogations (the Art. 6(3) carve-back applies notwithstanding the exemptions), and Art. 6(3)'s own conjunction is split — `derogation` decides conditions (a)-(d), `significant_risk` decides the chapeau, and only both together exempt.
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
6. ~~**Layer 1 held-out cases**~~ ✅ **authored 2026-07-22**, ⚠️ **SPENT and folded into dev
   2026-08-15** — 9 cases, `split: test`, authored BLIND (labelled from the enacted text, classifier
   never run on them). All five risk classes; two second-of-their-kind grounds (Art. 5(1)(g)
   biometric categorisation; insufficient-input at the annex_iii node, not profiling); and the two
   traps the smoke check found that dev lacks — a high-risk case that loudly promises human
   oversight, a minimal case carrying cross-sell noise. Integrity pinned by `test_blind_batches.py`
   (no classifier run — that would leak it). Two further batches were authored blind later: Annex I
   (6 cases, 2026-07-30) and Art. 2 (9 cases, 2026-08-11), for 24 in all. **All 24 now live in
   `classification_cases.yaml` as dev** — see the SPENT note under M5. Layer 1 has no held-out split
   until a fresh one is authored; Layer 2's is untouched.
7. ✅ **DONE 2026-08-14 — the held-out reporting run: 15/24 at `6608c5b`.** Expecting a number below
   dev's was right, and the aggregate turned out to be the least interesting part: split by batch it
   is Art. 2 **8/9**, Annex I **2/6**, original **5/9**. See **THE HELD-OUT RESULT** under M5 for what
   each column means and what it found. It had been held back because the 2026-07-30 coverage audit
   found two missing cascade doors that change risk classes — **Annex I safety components (Art. 6(1))
   classified `minimal`**, a false clearance, and **Art. 2 applicability never asked at all** — and
   reporting against a cascade with two known holes produces a number that has to be thrown away.
   Both landed (M4d-1, M4d-2) before the run. **The set is now spent**; the next number needs fresh
   cases.

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

**The Annex III(1) carve-out — a third test at the same node (2026-08-20).** The node's two tests
answer *is this purpose part of a listed function*, and both exclusions it knew about were Art. 6(3)
ones assessed later. Point 1 carries an exclusion of a different kind: 1(a) lists remote biometric
identification and then says it *"shall not include"* verification whose **sole purpose** is
confirming a person is who they claim to be. That one IS decided here — it defines the area rather
than derogating from it — and it is a genuine boundary, not a technicality: one face against that
person's own stored template is out, the same face against a gallery of many is in. Test (iii) says
so, with `sole` marked strict, and with the exclusion confined to point 1 so a verification system
serving another listed function keeps that area. Test (iv) handles the chapeau on points 1, 6 and
7 — *"in so far as their use is permitted under relevant Union or national law"* — by saying it is
**not a test to apply here**: whether a Member State permits the use is that State's question, and
an impermissible use is not thereby made low-risk, it is barred by the other law. Left unaddressed
it is an invitation to answer "none" for a reason the node cannot assess, which is the same failure
the Art. 6(3) warning already guards against. Two dev cases, a flip pair in one venue —
`stadium_ticket_face_verification` (minimal) and `stadium_banned_person_face_identification`
(high_risk, biometrics). The pair is deliberately symmetric: the exclusion has to hold *and* have a
limit, because an area a classifier can be talked out of is worse than one it never had. These are
also the golden set's first **biometrics** cases, so the first to select `AIA-RULE-PO-A43-1` — the Annex
VII/notified-body branch — rather than `-A43-2`. Neither has been run against a model yet.

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

Layer 1 has **18 dev + 24 held-out = 42 cases** (≥15 met). Held-out authored blind in three batches; batch 1 measured at git `85ea48d` (7/9), then dev-side work below addressed the boundary it exposed, and the whole set was measured at `6608c5b` — see **the held-out result** under M5. All risk classes are
now represented, including `needs_review` via `ats_workflow_unspecified` (difficulty `insufficient`).

Two layers:

- **Layer 1 (classification):** real, noisy public texts (vendor pages, system cards) with a buried decisive fact. Ground truth = Art. 6(3) cascade. Split by `difficulty`.
- **Layer 2 (gap analysis):** synthetic technical docs with controlled ablations (`removed` / `present_but_inadequate` / `distractor` / `untouched`) generated from one full reference document. Ground truth is exact because we know what was altered.
- **Hold-out split** (e.g. 5 dev / 15 held-out) to avoid overfitting prompts. State this in README.

**Required cases (these must exist — they are the point of the project):**

- **The flip / misclassification case** (our core differentiator, make it an explicit test): a CV parser described as "field extraction only" → `not_high_risk` via derogation (a). Add one sentence — "…and ranks candidates by fit score" → `high_risk` via the profiling carve-back. Same document, one sentence, verdict flips. This is both the demo moment AND a regression test that the profiling node overrides a user-claimed derogation.
- **The prohibited case:** AI video-interview scoring facial expression / tone → likely prohibited (Art. 5, emotion recognition in the workplace), not high-risk. See open question below on whether "workplace" covers the hiring stage.
- **The transparency case:** job-ad generator → `minimal` risk BUT Art. 50 applies (generates synthetic text). Proves Art. 50 is evaluated independently of the risk class.

**DoD:** ≥15 classification cases incl. the three required cases above ✅ (42 — the three required cases all exist); ≥1 reference doc + ablation script producing a manifest ✅; dev/held-out split committed ✅ (Layer 2 both halves; Layer 1 18 dev + 24 held-out).

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

#### 🔴 DEBT — adversarial (prompt-injection) cases are not authored

`SECURITY.md` claims an injected document can bias **one** node's sub-answer and cannot reach the
verdict. The second half is deterministic and already proven by the `ScriptedBrain` routing tests;
the first half is a claim about a model and is currently **argued in prose, with no number behind
it**. The cases that would measure it do not exist.

**They belong in the PER-NODE eval, not end to end.** An end-to-end case asserts the risk class did
not move, which passes whenever any other node dominates the route — green while the injection
fully succeeded on the node it targeted. The per-node form is a **paired case** (same document,
clean and injected) scored on whether the targeted node's answer moves, which yields a flip rate:
the number `SECURITY.md` is missing.

**Blocked on the ruleset, deliberately.** Deferred with the rest of the Layer 2 authoring — see the
coverage gaps above — and to be picked up once the rule ids stop moving.

#### ✅ Resolved — "workplace" (Art. 5 emotion recognition) DOES cover hiring

The prohibited-practice ban on emotion recognition covers "workplace and education". Question was: does a recruitment / pre-employment interview count as "workplace"? **Resolved yes**, per the **Commission Guidelines on prohibited AI practices, C(2025) 5052 final (29 July 2025)** — "workplace" is to be interpreted broadly and expressly covers recruitment and hiring; the Guidelines give video-interview emotion analysis as a prohibited example. So `emotion_screening_candidates` is `prohibited`, not `needs_review`. (Note the version: C(2025) 5052 final, 29 Jul 2025, is the *finalised* guidelines — it supersedes C(2025) 884 final, 4 Feb 2025, which was only the *approval of the draft content*. Cite 5052.) The label carries a `guidance_refs` id into the new guidance store (`data/policy/guidance/`), which records the verbatim passage; a loader check makes a dangling or drifted citation fail.

> ⚠️ **Side effect — Layer 1 lost its only `needs_review` ground-truth case.** Resolving this label to `prohibited` means no classification case now exercises NEEDS_REVIEW. The abstention *path* is still covered by the graph routing tests (low confidence → needs_review), but a genuinely-ambiguous *ground-truth* case should be authored to restore coverage. **TODO: add one new ambiguous Layer 1 case.**
>
> ✅ **RESTORED 2026-07-22 via INSUFFICIENT INPUT, not legal ambiguity.** `ats_workflow_unspecified`: unambiguously an AI system, unambiguously used in recruitment, and silent on the one thing that decides the tier — what its ranking model orders on. Submission time evaluates nobody (Art. 6(3)(a) derogation → not_high_risk); predicted fit evaluates persons (profiling carve-back → high_risk). The text chooses neither, so `needs_review` is correct and no contested legal question was needed to author it. New `Difficulty.INSUFFICIENT` band keeps it apart from `ambiguous` (contested law), since averaging the two would make both bands unreadable. As predicted the cascade fails it — see the current-focus list.

#### ⏸ Deferred — is drafting a job advert "placing targeted job advertisements" (Annex III 4(a), high-risk)?

The `job_ad_generation` case turns on whether Annex III 4(a) — high-risk systems used "to place targeted job advertisements" — covers a tool that merely *drafts* advert copy (targeting is about *who sees* the ad, not *who writes* it). **Cannot be resolved authoritatively yet:** the relevant Commission guidance is the **draft** guidelines on classification of high-risk AI systems (Art. 6 / Annex III), published 19 May 2026 and open for consultation until **23 July 2026** — not adopted. Citing a draft under live consultation as ground truth would be wrong. **Action: leave `job_ad_generation` flagged as contested/provisional; revisit once the high-risk classification guidelines are formally adopted.** Unlike the prohibited-practices guidance (which resolved the emotion case cleanly), there is currently no adopted Commission position on this question.

### M2 — Policy spec (YAML)

The high-risk obligations from the EC checker — **38 rules**, `spec.yaml` v0.8.0 — in the `PolicyRule` schema. IDs split cleanly: `AIA-RULE-HR-*` (document-verifiable, Art. 9–15), `AIA-RULE-PO-*` (process, `document_verifiable: false`), `AIA-RULE-TR-*` (Art. 50 transparency, the only family gated on a duty rather than a tier), and one `AIA-RULE-NHR-A06-4`. Legal wording is resolved VERBATIM from the version-scoped article store at load time, never hand-written in the spec, and a literal-substring test blocks paraphrase drift. Honest `document_verifiable` flags (Art. 16–21/43/47–49 = process obligations, not doc-checkable). **Every role the Act binds is covered**: `AIA-RULE-DP-*` the deployer (Arts. 26–27, 49(3) and 86), `AIA-RULE-AR-*`/`AIA-RULE-IM-*`/`AIA-RULE-DI-*` the supply chain (Arts. 22–24), and `AIA-RULE-ALL-A04` Art. 4, which binds provider and deployer at every governed tier and is the rule that stops `minimal` collapsing into `out_of_scope` at the obligation layer. Selection runs once per *(use case, role)*, the covered roles are DERIVED from the ruleset rather than listed by hand, findings record the role, and the report groups by it. `ActorRole` is partitioned by the coverage ledger exactly as the articles are — rules or a written reason, enforced by a test — so a role cannot silently vanish from a report. One is listed out: `product_manufacturer`, because Art. 25(3) makes it the PROVIDER rather than giving it duties of its own — writing rules for it would state as a separate obligation set the very thing the Article says is the provider's. It is reached instead by the gap graph's `roles` node (M4d-4), which asks at high risk whether Art. 25(1)(a)–(c) or 25(3) has moved the provider's duties onto another party. Most of these obligations (Art. 9–15, 16–21) apply to **every** high-risk system regardless of area or route, so the spec largely generalises as-is. Where the law is NOT general, the rule now says so rather than assuming: `applies_to_route` (`HighRiskRoute`) and `applies_to_annex_iii_area` are activation conditions alongside risk class and role, both defaulting to no condition. **Art. 43 is what forced them** — conformity assessment is 43(1) for Annex III point 1 (a notified body may be required), 43(2) for points 2 to 8 (internal control, Annex VI), and 43(3) for an Annex I product (the sectoral act's own procedure). The spec previously carried 43(2) alone, with the comment *"employment is Annex III point 4"*, and fired it at all three — a confident wrong citation to two systems out of three. Now three rules, and a test asserts every high-risk system owes exactly one. `AIA-RULE-PO-A49` gained the same treatment: Art. 49(1) exempts Annex III point 2 and does not reach Annex I at all, and `AIA-RULE-ALL-A49-4` carries the secure-non-public-section variant for points 6 and 7. Point 1 in a law-enforcement deployment is knowingly under-covered — `AnnexIIIArea` records the listed area, not the sector of use — and the rule's `evidence_expected` says so. **Art. 27 needed a different mechanism**, and got one. Its condition is *who the deployer is* — a body governed by public law, or a private entity providing public services — or else that the system is Annex III(5)(b)/(c), a sub-point finer than `AnnexIIIArea` classifies to. Neither is a fact about the system, so `PolicyRule.activation_condition` states the condition in plain words and the report carries it beside the obligation. It **narrows the duty-holder, not the report**: the rule is still selected, still listed under the deployer, still counted. A first attempt gave it a separate `conditional` bucket meaning "may not apply to you", and that was wrong for the reason `roles_not_covered` was — this report covers every obligation the Act creates for every role it binds, whoever is reading, and the reader identifies their own column. Art. 27's area gating landed too: Art. 6(2) systems only (so never an Annex I one), excluding Annex III point 2. **Art. 49(3) then reused the whole mechanism** — deployer registration, `AIA-RULE-DP-A49-3`, area-gated in the same words as 49(1) and narrowed by the same fact about the organisation. It is the second duty to turn on `deployer_type` and it does NOT answer alike: Art. 27 reaches bodies governed by public law AND private entities providing public services, Art. 49(3) only public authorities, Union bodies and persons acting on their behalf. A private entity providing public services owes the impact assessment and not the registration, so `DeployerType` grew a second property rather than reusing `caught_by_article_27`, and the report's note now answers both — a reader told about one would carry the answer across, and for that value the inference is wrong. The `False` branch stays open about the acting-on-behalf limb, which is a fact about an arrangement that no description of an organisation establishes. Art. 49(4) came with it: the paragraph governs "the registration referred to in paragraphs 1, 2 and 3", so the secure-non-public-section rule binds the deployer too and was renamed `AIA-RULE-PO-A49-4` → `AIA-RULE-ALL-A49-4`. And the condition is no longer dead text: a second gap-layer question, `deployer_type`, reads what kind of organisation the documentation says operates the system — `DeployerType` is `public_body` / `public_service_provider` / `neither` / `not_stated`, with `not_stated` its own value for the reason `TerritorialLink.not_addressed` is. The report then says which side of Art. 27(1)'s first limb the document falls on, or that it does not say. It still never withholds the obligation. Measured like Art. 25: pinned on the 11 high-risk Annex III cases, one `public_body`, three `neither`, seven `not_stated`. **Art. 25(2) is now a rule too** — `AIA-RULE-IP-A25-2`, held by a new `ActorRole.INITIAL_PROVIDER`. The ledger had excluded Art. 25 whole on the ground that paragraphs (1)–(3) "assign the PROVIDER ROLE rather than create a duty of their own", which is true of (1) and (3) and false of (2): it strips the initial provider of the role and then imposes a cooperation duty on it — supply the information, technical access and assistance the new provider needs for the conformity assessment. A role of its own rather than a condition on `provider`, because attaching it there would put the duty on the organisation that just took the role ON. It is the only rule whose activation is answered by a QUESTION rather than by the classification (`requires_provider_reallocation`), so the gap graph's `roles` node now feeds `select_rules` — an edge that adds an obligation and never removes one. Art. 25(4)'s written-agreement duty stays unmodelled: it is discharged in a contract with a component supplier, not in the technical file. **Art. 16 is now cited too**, by three rules. The ledger had excluded it whole as "an umbrella list that cross-references Art. 17–21, 43, 47–49" — true of nine of its twelve points, and modelling those would report every finding twice, but points **(b)**, **(k)** and **(l)** cross-reference nothing and no rule carried them. (b) is the provider's name, trade mark and contact address; (k) is demonstrating conformity on a national authority's reasoned request; (l) is accessibility under Directives (EU) 2016/2102 and (EU) 2019/882. Citing a point rather than an article needed the loader to resolve one, which it now does — with a guard that refuses an under-specified citation, because Art. 9 has an (a) under paragraph 2 and another under paragraph 5, and quietly resolving to the first would cite one duty and quote another. **(b) is the only document-verifiable rule in the `AIA-RULE-PO-*` family**, and the Act is what makes it so: it names the accompanying documentation as a place the duty may be discharged, so a technical file that identifies no provider is a real finding rather than a scope limit. A test pins that exception by rule id, so a second one has to be argued for. (k) stays a readiness of the provider organisation and (l) is settled by two instruments this tool does not read — both confirm-separately. Both golden sets gained a provider-identification section and two cases each (`removed`, `distractor`), the distractor being the common real failure: the company named everywhere and an address nowhere.

**Art. 50 completes the axis** (M4d-3), and it is the one activation condition that is not a narrowing. `applies_to_transparency_duty` does not filter a tier-gated rule — it **replaces** the tier, and a validator rejects a rule naming both, or neither. It has to: Art. 50 cuts across the Art. 6 tiers in both directions. A minimal-risk text generator owes 50(2) and a high-risk candidate scorer owes nothing under Art. 50 at all, so a rule gated on `[minimal]` misses the high-risk chatbot and one gated on every tier watermarks a scorer that generates nothing. Four rules, `AIA-RULE-TR-A50-1` to `-4`, activated by the cascade's own `transparency` answer — the classification says which duty attached, the gap layer checks the documentation against it, which is what every other obligation this tool detects already got. Art. 50(4) is **one** rule reached by either of its duties: two subparagraphs, deep fakes and published public-interest text, one provision, and `LegalSource` cites no finer than the paragraph, so splitting would mean two rules quoting identical law. The **role split is enforced, not just documented** — `TransparencyDuty.owed_by` already knew that (1) and (2) bind the provider and (3) and (4) the deployer, and a validator now rejects a rule filed under any other role: a provider handed 50(3) cannot discharge it and the deployer's duty would go unnamed. `document_verifiable` follows the same seam without being told to: the provider's duties are built into the system and show in a technical file, the deployer's are performed in front of the affected person and no provider document evidences them. One consequence worth naming: `select_rules`'s early return for `out_of_scope` used to be **redundant** — no rule listed that tier, so the filter emptied the set anyway — and is now load-bearing, because a duty-gated rule names no tier for anything to filter. Art. 2 withholds the Regulation whole, Art. 50 included, and there is a test for it.

**Deliberately NOT done: Art. 50 still does not survive `prohibited`.** The M4d-3 note asked for it, on the ground that 50(3) attaches to the system TYPE and can stand beside an Art. 5 ban. The pipeline gates a prohibited practice out before the gap layer, and it stays gated. The reason is the one already written into `_PROHIBITED_NOTE`: Art. 5 bans placing on the market, putting into service and use, so there is no lawful deployment for 50(3)'s "inform the persons exposed" to attach to, and a report that answers a prohibition with a disclosure checklist reads as *fix the paperwork and proceed*. It may not. The enum's point still holds where it was made — Art. 5(1)(f) excepts medical and safety uses, and a system lawfully deployed under that exception is not classified `prohibited` here, so it reaches the gap layer and owes 50(3) in the ordinary way.
**DoD:** `data/policy/*.yaml` loads and validates against `PolicyRuleset`.

### M3 — Classification graph (LangGraph) ✅ built, traced and measured on both splits

Nodes reproduce the EC flow; profiling split out; per-use-case resolution. Each node returns a `Answer` with evidence + `LegalSource`. Wire Langfuse from the first node.

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

**DoD: ✅ met.** Layer-2 ablation docs run end to end → findings with citations; `untouched` requirements come back `pass` (98.3% false-positive control, 1 wrong judgement in 115). A throwaway script driving `classify()` and then `analyse()` by hand cost **$0.016** on a full document and reported `AIA-RULE-HR-A14` as a gap *because* its cross-reference resolved to nothing.

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

### M4d — SCOPE GAPS: what the Act says that the implementation does not

Found 2026-07-30 by auditing the cascade's six questions and the 19 spec rules against the coverage ledger and the enacted text. The ledger itself is sound — all 113 articles are partitioned and a test enforces it — but **it justifies three exclusions by pointing at machinery that does not exist**, and the schema documents a high-risk route the graph never takes.

These are not backlog items. Findings 1 and 2 change risk classes, so **the Layer 1 held-out run must not happen until they land** — otherwise the headline number is measured against a cascade with two missing doors, and has to be thrown away and re-run.

**Order:** 1 + 2 together (both are missing cascade nodes, both need golden-set cases) → 4 (list-only ships without ground truth) → 3 → 5, 6. **7 follows 4**, not because it is less urgent than 3 or 5 but because Art. 2(1) is written per role, so the role question has to be settled first or the build is guessing.

1 and 2 are done. 7 was found afterwards, on 2026-08-11, and is listed with the rest below.

Ordered below by what a wrong answer costs a user.

Triggered by noticing Art. 50 is answered and then never checked. Audited the cascade's six questions and the 19 spec rules against the coverage ledger and the enacted text. The ledger itself is sound — all 113 articles are partitioned and a test enforces it — but **it justifies three exclusions by pointing at machinery that does not exist**, and the schema documents a high-risk route the graph never takes.

Ordered by what a wrong answer costs a user.

#### M4d-10 — The `annex_iii` node asked a question seven of the eight areas answer ✅ FIXED 2026-08-21

**The defect.** The node's decision rule was two tests: *IN scope if the purpose substantively acts on the person or their application*, *OUT of scope if it does not act on the person or their application at all*. Read against the Annex, seven points name natural persons and **point 2 does not** — *"AI systems intended to be used as safety components in the management and operation of critical digital infrastructure, road traffic, or in the supply of water, gas, heating or electricity."* Pipes, roads and grids. A traffic signal controller or a grid protection relay satisfies the OUT test word for word, answers `none`, and is reported `minimal` — `select_rules` then returns exactly one obligation, `AIA-RULE-ALL-A04`. Arts. 9–15, 16–21, 43, 47–49 and 72–73 all drop. There is no second door: no Annex I instrument covers water, gas, heating or electricity supply, so `annex_i` cannot catch it either. **The widest false PASS the classification layer could produce, landing on the systems whose failure kills people.**

**The fix.** Point 2 gets the test the Act gives it, stated before the person tests and marked as the only area decided that way: Art. 3(14) — a safety function, or a failure or malfunctioning that endangers health and safety. Signal and traffic control, grid frequency response and load shedding, protection relays, pressure and flow control are named in; billing, demand forecasting, maintenance scheduling, capacity planning and outage notification are named out. Tests (i) and (ii) are now explicitly scoped to *"the SEVEN areas that are about people"*.

**The cause was measurement, not wording.** The golden set has 33 classified cases: **14 employment**, one each for migration, essential services and biometrics, 16 not-high-risk, and **zero for critical infrastructure, education, law enforcement and justice**. The prompt was written for employment, tuned on employment and scored on employment, so an area written out of it was invisible to every check in the repo. `test_the_annex_iii_areas_nothing_measures_are_declared` now names the four unmeasured areas as a set that may only SHRINK — declared rather than asserted empty, because a case needs a real document and cases come before numbers. Verified to fail in both directions: an area silently unmeasured, and a declared area that has since gained a case.

**Not verified by a run.** The prompt no longer contradicts the Annex; whether a model now answers `critical_infrastructure` for a SCADA description is unmeasured, and stays that way until a case exists. Found by an independent adversarial audit against the enacted text, not by the suite — 798 tests passed with the defect in place.

#### M4d-11 — The Annex I options were bare identifiers, and two of them are synonyms ✅ FIXED 2026-08-21

**The defect.** `_answer_instructions` rendered `AnnexIProduct` as `", ".join(p.value)` — `machinery, toys, … machinery_regulation` — with no instrument attached to any option. Annex I lists **machinery twice**: Directive 2006/42/EC at A/1 and Regulation (EU) 2023/1230 at B/21. As English words the two identifiers are synonyms; as law they are opposites, because A/1 is Section A and B/21 is Section B, from which **Art. 2(2) withholds Chapter III**. `machinery_regulation` sets `chapter_iii_applies = False`, and `select_rules` then returns an **empty `ActiveRules` for every role** — no Chapter III, no Art. 4, no Art. 50, a report with zero findings and a `scope_note` saying those obligations do not apply. B/14 and B/15 are a second adjacent pair, two vehicle Regulations whose numbers differ by one digit.

**The fix.** Options now render as `<value> = <legislation>`, using the `legislation` property the enum already carried and nothing used. The node also gets a decision rule for the pair, because the distinguishing fact is a date no system description states: Regulation (EU) 2023/1230 replaces the Directive only **from 20 January 2027**, so `machinery` is the answer for a machine unless the document itself names the Regulation. *"Do not choose between them on how modern the machine sounds; choose on the instrument the document names."*

**The strings the model reads are now derived.** `_ANNEX_I_LEGISLATION` was hand-written prose that nothing checked — the same defect as the transposed ledger entries in M4d-9, one layer over, and worse here because the cascade now depends on it. `provisions.annex_instruments()` reads the first OJ citation out of each annex item, and one implementation serves both the ledger check and `test_every_annex_i_option_names_the_instrument_the_annex_puts_at_that_item`. Verified by transposing a digit in B/21's citation: *"annex says Regulation (EU) 2023/1230, code says Regulation (EU) 2023/1231"*.

**Not verified by a run**, same as M4d-10: no golden case pins any Annex I product to a specific instrument, so whether a model now separates the two is unmeasured.

#### M4d-12 — Ten definitions were ruled `CASCADE <node>` and never put in front of that node ✅ FIXED 2026-08-21

**The defect.** `_QUESTION_CONTEXT` is the entire supply of law to a node, and it named Article 3 for two nodes only — `is_ai` and `gpai_model`. The ledger meanwhile ruled thirteen Art. 3 definitions `CASCADE <node>`, so **ten of them were claimed as asked by a node that never saw them**: 3(14) → `annex_i`, 3(35)/3(36) → `annex_iii`, 3(39)/3(40)/3(60) → `transparency`, 3(41)/3(42)/3(44) → `prohibited`, 3(52) → `profiling`. Each question answered on a hand-written gloss instead, and every gloss had dropped the qualifying half:

- **3(42)** covers *"not only instant identification, but also limited short delays in order to avoid circumvention"*. The prompt said only that post-hoc identification is not real-time — inviting *"we buffer thirty seconds, so it is not real-time"* to clear an Art. 5(1)(h) prohibition.
- **3(44)** reaches a *"publicly **or privately** owned"* place. The prompt never said privately owned counts, so a shop or stadium read as private.
- **3(40)** excepts categorisation *"ancillary to another commercial service and strictly necessary for objective technical reasons"*. `grep -rn "ancillary"` over `src/` and both policy files returned **zero hits**.
- **3(39)** infers emotions *"on the basis of their biometric data"* — omitted, so text sentiment analysis read as emotion recognition.
- **3(14)** has two limbs and reaches *"persons **or property**"*; the prompt carried the second limb only.
- **3(52)** defines profiling by reference to Art. 4(4) GDPR; the node that **overrides every Art. 6(3) derogation** got one hand-written sentence.

**Supplied by the point, not the article.** Art. 3 is 68 definitions and ~19 000 characters; handing it whole to five more nodes would multiply the cost of every classification for text the questions never use. `anchor_questions` takes a `definitions` map, and `_QUESTION_DEFINITIONS` names the two or three points each node turns on — ~2 900 characters in total across all ten. They are appended last and labelled, so they read as the meaning of terms used above rather than as further provisions.

**A resolver bug fell out of it.** `_extract_point` matched only the lettered pattern, so `resolve_requirement(dir, 3, None, point="14")` raised *"Article 3 has no point (14) (found: ['a', 'b', 'a', …])"* — it had found the sub-points nested inside the definitions. `provision_labels` gained `_NUMBERED_POINT` when Art. 3's definitions were first enumerated; the resolver never did. A digit label now selects the numbered pattern.

**The guard is the point.** `test_every_ruling_names_something_that_exists` checked that a cascade node id resolves — the weaker half of the claim. `test_every_definition_the_ledger_hands_to_a_node_reaches_it` reads the ledger's own `CASCADE <node>` ruling for each Art. 3 point and requires the definition's verbatim text to be in that node's built context. Verified by dropping 3(44) from the map: *"definitions the ledger hands to a node that never sees them: {'Art. 3(44)': 'prohibited'}"*.

#### M4d-13 — Forty annex items were marked CHECKED and no judge ever saw them ✅ FIXED 2026-08-21

**The defect.** `resolve_requirement` takes article, paragraph and point — **no annex parameter** — and `judge.py` contained no reference to annexes. `source.annex` was metadata. Yet the ledger wrote `RULE <id>` against 40 annex items: Annex IV(1)–(9), Annex VI(1)–(4), and Annex VIII's 27 items across its three Sections. `coverage.py`'s own docstring states the honest rule — *"the tool reading Annex III is not the same as anyone having ruled on what Annex III(5)(b) requires"* — and writing `RULE X` per item routed around it by hand.

**Where it bit hardest.** `AIA-RULE-HR-A11` is `check_type: completeness` — *"a prescribed list must be fully covered"* — and the prescribed list is Annex IV. Art. 11(1), the resolved requirement, says only that the documentation *"shall contain, at a minimum, the elements set out in Annex IV"*. The judge got the pointer, never the list, and worked from a paraphrase in `evidence_expected` that named **six of the nine elements** — omitting **IV(7)** harmonised standards applied, **IV(8)** the copy of the Art. 47 declaration of conformity, and **IV(9)** the Art. 72 post-market monitoring plan. Those three are exactly where a technical file stops short.

**Two different fixes, because they are two different problems.**

*Annex IV and VI — supply the text.* `PolicyRule.annex_context` is filled by the loader from `source.annex`, verbatim and integrity-checked on the same terms as the Article, and the judge prompt carries it in its own labelled block: *"Where the Article requires the elements it sets out, this Annex IS the list to judge completeness against."* Kept out of `requirement`, which must stay a literal substring of the cited Article. `AIA-RULE-HR-A11`'s evidence now enumerates all nine and says to judge against the supplied list rather than the summary. `provision_text` moved from `anchoring` into `policy_loader` so the store read and its integrity check stay in one place — `anchoring` imports from the loader, so it could not go the other way.

*Annex VIII — declare the debt.* Its 27 items were never checked by anything. `AIA-RULE-PO-A49`, `AIA-RULE-NHR-A06-4` and `AIA-RULE-DP-A49-3` have Art. 49(1), 6(4) and 49(3) as their subject and cite Annex **III**, the area gate; **Art. 49 never names Annex VIII at all** — it is Annex VIII's own Section headers that tie Section A to 49(1), B to 49(2), C to 49(3). Those rules check that registration was MADE, not what went into it. Moved to `annexes_awaiting_rules`, emptied by a rule for Art. 71(2)–(3), which is already declared owed and is where the duty is written as a duty.

**Coverage moves accordingly**: checked 122 → 95, owed 53 → 80. A number going the wrong way, and correctly so — 27 items stopped claiming a check nobody performs.

**The guard.** `test_every_annex_item_a_rule_checks_is_supplied_to_that_rule` requires any item ruled `RULE <id>` to be in an annex that rule actually cites and has resolved. Verified by removing `annex: "IV"` from the spec: all nine Annex IV items fail with *"AIA-RULE-HR-A11 cites annex None"*.

#### M4d-1 — Annex I safety components ✅ DONE 2026-07-30

**Was:** `RiskClass.HIGH_RISK` said it plainly — *"Either an Annex I safety component, or an Annex III use case…"* — and the cascade only ever asked the second. `decide_risk_class` routed `in_annex_iii.value is None` straight to `MINIMAL`, so an AI safety component of a machine, a lift, a surgical robot or a car was told it owed nothing. A false clearance: not a missed gap inside a report, but a high-risk system handed a clean bill of health.

**Built:** two nodes between `prohibited` and `annex_iii`, `AnnexIProduct` (all 20 instruments), `UseCaseClassification.annex_i_product`, and the Art. 2(2) exclusion in `select`. 10 tests in `tests/test_annex_i.py`.

Three things the enacted text forced, each of which a simpler implementation gets wrong:

1. **Art. 6(1) is a CONJUNCTION.** (a) safety component of an Annex I product AND (b) that product needs THIRD-PARTY conformity assessment. Most Annex I regimes let a manufacturer self-assess the lower risk classes, so treating (a) alone as sufficient would classify self-certified products high-risk.
2. **Failing (b) is not an exit.** A self-assessed Annex I product can still be high-risk under Annex III, so the cascade falls THROUGH to the Annex III route rather than concluding `minimal`. Treating it as an exit would re-create the original bug one branch over.
3. **Art. 2(2) is the trap.** For an Art. 6(1) system whose product sits in Annex I **Section B** — vehicles, aviation, rail, marine — only Art. 6(1), Arts. 102-109 and Art. 112 apply. **Chapter III does not.** Such a system is genuinely high-risk and genuinely owes none of Art. 9-15; routing it to `high_risk` without more would raise 18 obligations the Act withholds, trading a false clearance for a false accusation. The section is carried on `AnnexIProduct.chapter_iii_applies`, `select_rules()` returns nothing for Section B, and `review()` sets a `scope_note` — because high_risk beside an empty findings list is the most misreadable output this tool can produce.

**Measured live, 2026-07-30, Flash + thinking disabled, 4 cases, $0.0218 (~$0.0055/case):** surgical robot → high_risk via `medical_devices` (Section A); vehicle braking → high_risk via `motor_vehicles` (Section B, no Chapter III); self-certified drill press → minimal (both conditions required, fell through correctly); theatre-and-shift scheduler → `annex_i=None`, the distractor that sits in a medical setting without being a safety component. **4/4, all at high confidence.** Per-case classification cost rose from $0.0045 to $0.0055 — the two extra nodes, ~22%.

**Golden-set cases added, and the dev set re-run: 14/14 risk class, 14/14 Art. 50, zero abstentions, $0.0801 (~$0.0057/case).** Five new cases in `classification_cases.yaml` (dev, 9 → 14), and `ClassificationCase` gained `expected_annex_i_product` / `expected_third_party_assessment` with a validator enforcing the same Art. 6(1) invariants the cascade obeys — both limbs met is high_risk, and no Art. 6(3) derogation may coexist with it.

The five, and what each is for:
- `surgical_robot_dose_control` — Section A, both limbs. **The regression case**: in no Annex III area, so the old cascade cleared it.
- `vehicle_emergency_braking` — Section B. Same risk class, different consequence (Art. 2(2), no Chapter III).
- `drill_press_wear_monitor` ⇄ `drill_press_in_annex_iv` — **the Annex I FLIP, and a new kind**. Identical AI feature, opposite class, and the deciding fact is about the HOST PRODUCT's conformity route (Annex IV of the Machinery Directive → notified body) rather than about the AI at all. The project's existing flip (`cv_parsing_plus_scoring`) turns on one sentence about what the AI does; this one turns on one sentence about what it is bolted to. Flash got both, live.
- `theatre_and_shift_scheduler` — the false-positive control: dense medical vocabulary, purely administrative function, correctly `annex_i=None`. Plays the role for `annex_i` that `leave_balance_tracker` plays for `annex_iii`.

Per-case cost across the whole dev set rose $0.0045 → $0.0057 (+27%): two extra nodes, and they run on every case.

**Held-out authored blind, 2026-07-30.** Six cases, from six real FDA 510(k) summaries, written by a session that could not read this file, the dev cases, or the tests — enforced by a `PreToolUse` hook, not a promise (`.claude/hooks/heldout-guard.py`, kept disabled; re-enable only for another authoring run). Source PDFs are paraphrased and never committed — manufacturer-authored text published by a regulator is public, not public domain — so the repo keeps the hash rather than the bytes, in `data/golden_set/heldout_sources.yaml`.

That session marked four of the six `needs_review` rather than guess, because a US filing cannot state an EU conformity route. **That judgement is now the tool's design** — see the DECIDED note below. Its labels stand unedited.

**DECIDED 2026-07-30: read condition (b), never derive it.** Adjudicating those four sent us into MDR Annex VIII Rule 11 and MDCG 2025-6, whose Table 1 maps MDR class → Art. 6(1)(b). Applying it would have turned all four into `high_risk` and closed the coverage gap for free. **Rejected.** Art. 6(1)(b) turns on the SECTORAL instrument — twenty of them — and answering it means applying a body of law this tool holds no text for, in a domain neither author nor reviewer can check. A confident tier derived that way is exactly the false accusation the Section B branch exists to prevent, arriving by a different route.

So the `third_party_assessment` node asks only what the DOCUMENT states, and is explicitly told not to infer from product type or risk class. Silence routes to `needs_review` with a note naming the sector specialist. The disclaimer says so too, in `ComplianceReport.DISCLAIMER` and the README footer: *an open question is unfinished work, not a clean result*.

What this costs, stated plainly: **the Annex I route can only ever reach `high_risk` on a document that states its conformity route.** The five dev cases do (14/14 live, re-measured after the prompt narrowed), and a real EU technical file normally does — a CE marking and notified-body number is standard content. A US filing does not, which is why four held-out cases sit at `needs_review` by design rather than by failure.

#### M4d-2 — Art. 2 applicability ✅ DONE 2026-08-11 (dev measured; held-out pending)

**Was:** the ledger excluded Art. 2 because it is *"consumed by the classification graph (`ClassificationState.in_eu_scope` / `is_excluded`)"*. **No such node exists, and `ClassificationState` was a stranded model deleted on 2026-07-29** — referenced by nothing in `src/` even before that. So the justification was never true.

Consequence: the tool classified systems the Regulation does not govern. No scope question at all, and none of the exclusions — military, defence and national security (2(3)), third-country law-enforcement cooperation (2(4)), sole-purpose scientific R&D (2(6)), pre-market research and development (2(8)), purely personal non-professional use (2(10)), free and open-source release (2(12)). A defence contractor got a full Chapter III gap report for a system explicitly carved out.

It failed safe in direction — over-reporting, not under — but told users they owed duties they did not. `ClassificationCase.expected_scope_exclusion` now names the paragraph, and the validator refuses an out-of-scope case that also carries Art. 6 sub-answers, because Art. 6 classifies systems the Regulation governs and never reaches one it does not.

**Cases were written BEFORE the node, deliberately.** Nothing in the code consulted Art. 2 when they were authored, which is the one moment a held-out batch can be genuinely blind: there was no behaviour to observe. Cases written after watching a node fail are cases shaped by that failure. The order is the method, not a scheduling accident, and `docs/heldout-brief.md` states it. The authoring session was additionally told which gap it was covering, that every exclusion in the Article is qualified and so needs a near neighbour, and where to look for documents — TED, CORDIS, model-card and vendor-documentation registers — without being handed any particular one.

**`OUT_OF_SCOPE` is not `MINIMAL`,** and that distinction is the whole point of the class: a minimal-risk system is inside the Regulation and still owes Art. 4 AI literacy, with Art. 50 possibly attaching; an excluded system owes nothing at all. Collapsing the two would tell a defence contractor they hold duties the legislator expressly withheld.

**Held out: nine cases, authored blind 2026-08-11** from nine public documents — two TED procurement notices, three CORDIS project records, two Hugging Face model cards, a consumer user manual and a manufacturer press release. Five exclusions, each paired with a NEAR NEIGHBOUR that reads like it and is not it, because every exclusion in the Article is qualified — *exclusively*, *sole purpose*, *purely*, *prior to*, and 2(12)'s Art. 5/50 carve-back. The pairs are where the measurement is: a classifier that grants an exclusion on a keyword is worse than one that never grants any.

| Paragraph | Excluded | Near neighbour, in scope |
| --- | --- | --- |
| 2(3) military / defence / national security | EDA tender, UAS navigation in GNSS-denied airspace | customs + border-guard OSINT tools — bought under defence-and-security procurement law, and the exclusion turns on purpose of USE |
| 2(6) sole purpose of scientific R&D | CORDIS astrophysics classifier — no product, no customer, no natural person | — |
| 2(8) prior to placing on the market | CORDIS grid/rail/ATM operator project, validated only in simulators | pool drowning detection — an EU research grant, but paying customers already |
| 2(10) purely personal non-professional use | domestic oven bake-time predictor, answered for the household deployer | consumer camera drone — same everyday framing, answered for the provider |
| 2(12) free and open-source licence | Apache-2.0 time-series forecaster | Apache-2.0 text-to-speech — Art. 50(2) carve-back lifts the exclusion |

The 2(12) pair is the batch's flip, and it is a **new kind**: it flips on SCOPE rather than on tier. Same licence, same shape of publication, one excluded outright and one governed, separated only by whether the output is synthetic content Art. 50(2) requires to be marked.

The 2(10) pair carries the other thing Art. 2(1) is organised around — the exclusion attaches to a DEPLOYER, not to a system. The oven's manufacturer keeps every provider obligation it has; only the person baking is lifted out.

**Art. 2(4) has no held-out case, and will not get one.** Third-country public authorities and international organisations acting under law-enforcement or judicial cooperation agreements. The authoring session found no source document describing such a system without supplying the cooperation framework itself, and recorded the gap rather than inventing one.

That refusal was right, and the reason generalises. **2(4) is the only exclusion in the Article whose condition is about a COUNTRY rather than about the system** — it applies *"provided that"* the third country affords adequate safeguards for fundamental rights and freedoms. No system description states that; it is settled in the agreement and in the Commission's assessment. So 2(4) has the same shape as Art. 6(1)(b): **a condition to read, never to derive.** Deriving it means ruling on a country's data protection regime from a description of a piece of software — the same false-confidence trap the DECIDED note under M4d-1 rejects for sectoral conformity routes.

Covered instead by two DEV cases, where inventing the framework is legitimate: `third_country_mla_lead_ranking_with_safeguards` (the agreement records the adequacy finding → `out_of_scope`) and `third_country_mla_lead_ranking_unstated` (it does not → `needs_review`). The second is the load-bearing one. The failure it measures is granting the exclusion on the words "cooperation agreement", which would clear an Annex III(6) law-enforcement system outright.

**Dev set: 14 → 18.** Two Art. 2(3) cases (`defence_drone_swarm_coordination` ⇄ `border_surveillance_drone_analytics` — same aircraft, same defence-flavoured vocabulary, opposite sides, because border policing is law enforcement and not defence) plus the two 2(4) cases above.

**The manifest was widened.** `submission: K######` became `source_id`, a general identifier with a scheme prefix (`TED:`, `CORDIS:`, `HF:repo@revision`, `BSH:`, `DJI:`); an unprefixed value is still a 510(k) number. The property that earned its place survives — every part of the identifier must appear in the URL, so citation and document cannot drift apart. `test_the_documents_are_not_committed` now hashes tracked files against the manifest instead of globbing `K######.pdf`, which only ever caught one source type. Byte-stability was checked before hashing: TED PDFs and CORDIS `?format=json` reproduce exactly across fetches (CORDIS HTML does not), and Hugging Face URLs are pinned to a commit.

**Two contestable labels, recorded rather than hidden.** `h_pool_drowning_detection_rollout` — sorting swimmers into distressed or not, from video of how they move, sits close to Art. 3(40) biometric categorisation, since Art. 3(34) counts behavioural characteristics as biometric data. Art. 50(3) is read purpose-bound in the light of Annex III(1), consistently with `h_autonomous_retinopathy_screening`; if a reviewer disagrees, transparency flips to true. And both 2(12) cases read the released package — weights, inference library, model-selection helper — as an AI SYSTEM, where a reviewer could say bare weights are a model question instead. It cuts the same way for both, so the flip survives either reading.

**Built:** one node, `scope`, between `is_ai` and `prohibited`; `ScopeExclusion` (six paragraphs, each carrying its citation); `RiskClass.OUT_OF_SCOPE`; the `OUT_OF_SCOPE` branch in `select_rules()`; and the pipeline gate with its own note. 29 tests in `tests/test_scope.py` and `tests/test_pipeline.py`. **All 42 golden cases route correctly under the deterministic brain — 18/18 dev, 24/24 held out** — and `test_graph_reproduces_every_layer1_case`, which specified this work by failing, passes.

The specification WAS a failing test rather than a paragraph, which is what authoring the cases first buys: the build had a target it could not quietly redefine.

Three things the enacted text forced:

1. **Scope is decided BEFORE Art. 5 and before both Art. 6 doors.** Those are provisions OF this Regulation and cannot reach a system it does not govern. Asked after `is_ai` only because Art. 2 speaks throughout of AI systems — and a non-AI system stays `minimal`, not `out_of_scope`, because Art. 3(1) and Art. 2 fail for different reasons.
2. **`select_rules()` returns nothing at all for `OUT_OF_SCOPE`** — the stronger version of the Section B branch beside it. A Section B system IS governed and owes Arts. 102-109; an excluded one owes nothing. `ComplianceReport.scope_note` says which kind of nothing, because an empty findings list is otherwise the same output a clean bill of health produces.
3. **An exclusion is granted only on a NAMED paragraph.** `_scope_exclusion` narrows by TYPE, not truthiness: a bare false, an unparsed string, anything unclear leaves the system in scope. Over-inclusion is recoverable; a silent clearance is not. Caught by a pre-existing test double in `test_annex_i.py` that answers `false` for every node it does not know — which is exactly the input this rule exists for.

**DECIDED: Art. 2(12) falls through the cascade rather than being judged at the scope node.** It is the one exclusion whose condition is not a fact about the system in isolation — it is lifted where the release is high-risk, an Art. 5 practice, or subject to Art. 50. The alternative was to give the scope node its own copies of Arts. 5 and 50 and have it judge them there. **Rejected**: that is the same judgement made twice in two places, which can disagree, and it costs two more articles of context on every classification for a question the cascade already answers. So an open-source answer routes onward and `decide_risk_class` resolves it at the end, against real answers. One judgement, one place to be wrong.

`NEEDS_REVIEW` is deliberately not among the tiers the exclusion survives: an unresolved cascade has not established that the exceptions are absent, and granting it anyway reads silence as evidence.

**Cost, unmeasured.** One more LLM call per classification, carrying Art. 2 and Art. 3. Art. 3 is already loaded for `is_ai`, so the marginal context is one article. M4d-1's two nodes cost +27% per case; this should be less, but it is a guess until measured — see the open item below.

**Measured live, 2026-08-11, Flash, 18 dev cases, $0.1195 (~$0.0066/case, 100 calls): 18/18 risk class, 18/18 Art. 50.** Per-case cost rose $0.0057 → $0.0066, +16% — one extra node, and Art. 3 was already loaded for `is_ai`, so the marginal context is one article.

**The first run was 17/18, and the miss was the case written to catch it.** `border_surveillance_drone_analytics` — a border police force, bought under defence-and-security procurement law — was granted the Art. 2(3) exclusion at HIGH confidence, on the words *protecting national frontiers* read as national security. Exactly the false clearance the near-neighbour pairs exist to expose, and in the worst direction: an Annex III(7) system cleared outright.

**Fixed structurally, not by patching the case.** The question's 2(3) bullet now argues from Annex III: point 6 lists law enforcement and point 7 lists migration, asylum and border control management as HIGH-RISK areas, so a reading of "national security" that swallows policing or border work would leave both entries with nothing to cover and cannot be right. Verified against the stored Annex III text before it was written into the prompt. Re-run: 18/18, no regression on the other 17.

That is the general lesson for this node. "National security" is the widest of the words Art. 2 uses and the only one that collides with a listed high-risk area — so it is the one that needs an argument rather than a definition.

**The 2(4) abstention was verified to happen for the right reason.** `third_country_mla_lead_ranking_unstated` reaches `needs_review` from the SCOPE node with `abstained_because=description_silent`, not by a default further down — the false pass flagged when the deterministic suite could not tell them apart. Its sibling with the safeguards finding stated answers `third_country_law_enforcement_cooperation` at high confidence and cites the finding. Read, not derived, as designed.

**Still open:**
- **Held out has not been run.** The dev set is tunable and this node was tuned against it, so 18/18 is not a reportable number. The nine held-out Art. 2 cases are what measure it, and that run is the headline — see the unblocked item at the top of M4.
- `UseCaseClassification` does not carry the exclusion as a field, only in the reasoning and the evidence's `node_id`. Nothing consumes it yet — `select_rules()` keys on the risk class — so adding one would be speculative. Revisit if a report needs to render the paragraph.
- **This covers Art. 2's exclusions, not the whole Article.** Art. 2(1) — whether the Regulation reaches the system at all — is still never asked, and is a different shape of question. Tracked as M4d-7.

#### M4d-3 — Art. 50 is detected and then dropped ✅ closed 2026-08-20

The cascade answered *"does Art. 50 apply?"* into `ClassificationResult.transparency` and **no spec rule cited Art. 50**, so the documentation was never checked against it. Every other obligation we detect, we verify; this one we announced and abandoned.

The applicability question stays in classification — it is a property of the system, like "is it in Annex III?", and `assemble` is where it belongs because every path reaches it. What was missing was the CHECK. Four things made it more than a spec addition, and here is where each landed:

- **`select_rules()` keyed on `risk_class`, and Art. 50 is deliberately not a risk class.** Done, as `PolicyRule.applies_to_transparency_duty` — an axis that REPLACES the tier rather than narrowing it, with a validator rejecting a rule that names both or neither. See the M4 note above for why both directions fail.
- **The paragraphs split by role.** Done, and enforced rather than documented: a validator checks each rule is filed under the role `TransparencyDuty.owed_by` names. Selection already runs per role, so the deployer paragraphs are reported under the deployer whoever commissioned the run — this report has never been addressed to one reader.
- **It survives `prohibited`.** **Not done, deliberately** — see the M4 note for the reasoning. Art. 5 leaves no lawful deployment for 50(3) to attach to, and answering a ban with a disclosure checklist reads as *fix the paperwork and proceed*.
- **Its own application date** under Art. 113. Nothing special was needed: Art. 50 is Chapter IV and applies from 2026-08-02, the same `effective_date` as Chapter III's rules. The genuine outlier is Art. 4 (2025-02-02), which is already carried. Finding 5 remains open on its own terms — no report yet says that nothing here is in force until 2026-08-02.

Four rules, `AIA-RULE-TR-A50-1` to `-4`, resolved from `articles/2026-07-27/article-050.md`. Ten tests in `test_gap_rules.py` and one end-to-end in `test_pipeline.py` — a minimal-risk generator that owes 50(2) and nothing else, which is the case a tier-gated rule misses entirely. **Not yet measured**: no golden case exercises an Art. 50 rule, because the transparency duty a case carries is a classification pin, and neither reference document generates content. That is the same measurement debt the rest of M4d carries.

#### M4d-4 — Only the PROVIDER role exists; the other four are absent ✅ BUILT 2026-08-19 (`8371956`, `3bd3057`+)

> Built in two halves. The RULESET half (`8371956`): `AIA-RULE-DP-*` for the deployer, `AIA-RULE-AR-*`/`AIA-RULE-IM-*`/`AIA-RULE-DI-*` for the supply chain, and `AIA-RULE-ALL-A04` for Art. 4 at every governed tier; the `role` parameter was removed rather than defaulted, the covered roles are derived from `spec.rules`, and the coverage ledger partitions `ActorRole` the same way it partitions articles. The ROLE-ASSIGNMENT half — item 3 below: a `roles` node whose first question answers a `ProviderReallocation` enum over Art. 25(1)(a)–(c) and 25(3), asked only where the tier came out high-risk, since that is the only system Art. 25 reallocates the provider of. It lives in the GAP graph, not the cascade: every cascade question decides what the system IS and yields a risk class, while this one decides who the PARTIES are — it consumes the tier and nothing reads it back, so it belongs with the rest of the role logic. (Art. 50 looks like the same case and is not: the tier READS the transparency answer, through the Art. 2(12) open-source carve-back, so it stays.) The answer sits on `ComplianceReport`, and the brain contract moved up to `aiact.brain` now that two layers ask questions — `pipeline.review` hands the gap layer the brain, since a layer building its own would import an implementation from the other. Art. 3(23) is quoted into the question, because "substantial modification" without its definition reads as "significant" and every configured deployment becomes one. Four golden cases, one per limb, plus `null` on every other high-risk case. `product_manufacturer` stays in the ledger's `roles_out_of_scope` — but now because Art. 25(3) hands it the provider's ruleset, not because the step was missing.
>
> What is still open from this section: **judging** the non-provider roles. Their obligations are listed and cited, none is judged, and the Layer 2 corpus that would let them be judged does not exist — see "The real cost is the golden set" below. Art. 25(4)'s written-agreement duty is also unmodelled, deliberately: it is discharged in a contract with a component supplier, not in the technical file this tool reads.

`review()` takes `role: ActorRole = ActorRole.PROVIDER`, no node ever asks, and all 19 rules are `[provider]`. Deployer, importer, distributor and authorised representative are modelled in `ActorRole` and covered by nothing.

**Decided 2026-07-30: report every role, judge only the ones held.** The first instinct was to stay provider-only, on the grounds that duties a user does not hold are noise. Measuring it killed that objection.

**The noise barely exists.** The provider set is 19 rules from ~19 articles. Every other role is **ONE article**:

| role | article | duties | evidenced in a document? |
|---|---|---|---|
| authorised representative | 22 | 3 | **none** — appoint by mandate, perform mandated tasks, terminate on breach |
| importer | 23 | 7 | **~1** — the rest is verify, label, storage, keep 10 years, inform, cooperate |
| distributor | 24 | 6 | **~1** — verify CE marking, storage, corrective action, cooperate |
| deployer | 26 (+27 FRIA) | 12 (+5) | **~6** — the only role with real documentary substance |

The JUDGED list grows 7 → ~14, and only when the deployer role is held. Three of the four roles are almost entirely process obligations that the existing `document_verifiable: false` path already routes to *confirm separately* — no LLM call, no verdict, no false gap. Cost per run stays under $0.05.

**Why it is worth doing, not merely cheap.** Users do not know which roles they hold, and the Act's drafting is what confuses them:

- **Art. 26(7)** — a deployer who is an employer must inform workers' representatives BEFORE putting a high-risk system into service at the workplace. That is Annex III(4), this project's exact scope, and a provider-only report omits it entirely. The HR team reading our output is usually the deployer.
- **Art. 25(1)** — a distributor, importer or deployer **BECOMES a provider** by putting its name or trademark on the system, substantially modifying it, or changing its intended purpose to a high-risk one. A company white-labelling a vendor tool has silently taken on all 19 provider obligations. The ledger excludes Art. 25 as "relevant to ROLE ASSIGNMENT, not a documentation-checkable duty" — correct about the duty, silent about the assignment.

So a report covering every role is a decision aid, not padding: it is what a reader needs in order to decide whether to take a role on or delegate it.

**Shape:**
1. **Judge** the roles held — verdicts, evidence, citations, exactly as now.
2. **List** every other role's obligations — citations, no verdicts, zero LLM calls, under a heading that makes the conditional explicit ("if you also act as deployer, you would owe…"). An unheld role must never produce a GAP.
3. **A role-assignment section** on Art. 25's triggers — do you put your name on it, modify it, change its purpose? Three questions that move a party from deployer to provider. *(Built as the gap graph's `roles` node, with a fourth: Art. 25(3), the product manufacturer.)*

**Cost:** ~36 rules across 6 articles (22–27), all already resolved verbatim in the repo. `Finding` needs a `role` axis; `select_rules()` already filters on `applies_to_role`, so selection is unchanged. Six ledger entries flip in-scope.

**The real cost is the golden set, not the rules.** Layer 2's ground truth is ablations of a PROVIDER's technical file. Deployer duties cannot be evidenced there — they need deployment records, a FRIA, logs, evidence that instructions were followed. That is a new corpus authored from scratch, and until it exists the deployer rules are unmeasured. **Ship the LIST for all roles first** (no ground truth needed, since nothing is judged), and gate JUDGING a role on having cases for it.

#### M4d-5 — Nothing is in force yet, and no report says so ✅ BUILT 2026-10-06

**Built:** a document-verifiable duty whose date is still ahead is judged and carries `Finding.applies_from`; `ReportSummary` counts in-force findings at the top level and future ones in `upcoming`, keyed by date, so the headline gap count is in-force only. A duty whose date turns on an unsettled Art. 6 route is listed in `timing_not_active` and never judged. Process duties are dated the same way and rendered with their date. Since 2026-10-14 every rule takes its dates from one place, the timing table entry its `temporal_regime_id` names; the old `effective_date` / `effective_date_by_route` fields are gone. The eval is unaffected: it passes no `as_of_date`, so every rule is judged as before.


All rules carried `effective_date: 2026-08-02` (Art. 113) and `status: active`. Today's reports raise gaps against obligations that bind nobody yet, and `ActiveRules.postponed` is permanently empty because no rule uses `status: postponed` — the spec deliberately carries the date instead.

**Bigger since Regulation (EU) 2026/1744, and no longer one shared date.** Chapter III Sections 1–3 moved to 2 December 2027 (Annex III) / 2 August 2028 (Annex I) while Sections 4–5 stayed at 2 August 2026 — which has now *passed*. So a high-risk report today raises ~21 obligations that do not apply for another sixteen months, beside a handful that already do, and says nothing to distinguish them. That is a wider gap between the report and the law than when this was written.

**A third date now has to be rendered beside those two.** `ComplianceReport.legacy_system_note` carries Art. 111: a high-risk system already on the market may not be reached by Chapter III until it is significantly redesigned, and a synthetic-content generator placed before 2 August 2026 has until 2 December 2026 for Art. 50(2) rather than the date its rule carries. It is deliberately *reported and never applied* — the fact it turns on is the system's placement date, which no system card states, and Art. 111(2) is relief, so applying it wrongly clears a reader. Rendering has to keep that distinction visible: a reader who reads it as a granted exemption is worse off than one who never saw it.

The first of the three options below is gone with it: the rules no longer share a date, so it cannot be stated once at report level. What remains is to carry the resolved date per rule in the report, or to compare it against the generation date and route not-yet-effective rules into `postponed`, which would finally give that bucket a purpose.

**The second is a much larger change than it looks, and this is the note to read before starting it.** Almost every document-verifiable rule is in Sections 1–3, so routing on the date would empty `document_verifiable` for a high-risk system, produce a report with no findings at all, and break every golden case at once — the answer key scores GAP/PASS per rule and those rules would no longer be judged. Whether that is *right* is a genuine question: a report that raises no gaps because nothing applies yet is legally accurate and useless as a compliance tool, and "adopted, applies from 2027-12-02, here is what it will require" is probably what a reader wants. Whatever is chosen, the eval has to move with it rather than be discovered afterwards.

`PolicyRule.effective_date_for(route)` already resolves the right date, so the data half is done — what is missing is the decision about what a report does with it.

**DECIDED 2026-08-20: show the date per obligation. Do NOT route not-yet-effective rules out of the check.** An obligation that binds in sixteen months still has to be reported, with its date beside it, so a reader can sort what is owed now from what is owed later — *"adopted, applies from 2027-12-02, here is what it will require"*. Withholding it produces a report that is legally accurate and useless, and it would break every golden case for a reason that has nothing to do with the checker's quality. Deferred deliberately: the report's wording has to be settled across several of these date-and-tense problems at once (see the wording note below), not invented for this one. The pieces to build when it is taken up:

- **Resolution happens at report-assembly time, not at load.** The date depends on the Art. 6 route, so it cannot be a static field copied off the rule — `effective_date_for(route)` must be called with the use case's own route, which the report knows and the spec does not.
- **Both buckets or neither.** `Finding` carries no date today and `not_document_verifiable` is a bare `dict[ActorRole, list[str]]` of rule ids. Dating only the findings would leave the provider's process obligations — Arts. 17–21, all moved to 2027 — looking like the in-force ones, which is the failure this is meant to fix. That bucket has to grow beyond a list of strings.
- **`effective_date_note` is already written and needs rendering.** Nine rules carry one: the eight Section 5 obligations, explaining why they are in force ahead of the requirements they attest to, and `AIA-RULE-NHR-A06-4`, whose date is genuinely CONTESTED — Art. 113's limbs both describe systems that ARE high-risk and Art. 6(4) binds a provider whose system is not, so no limb reaches it. That note names the reading not taken and its date, because the two are sixteen months apart in the direction that matters: on the alternative the duty is owed now. Reporting one date silently would present our reading as the Act's.
- **`ReportSummary.gaps` is the number a reader anchors on, and it is about to mean two things.** A GAP against Art. 9 today is not non-compliance: nobody is in breach of a requirement that binds in sixteen months. The verdict may be right while the WORD is wrong. Leaning toward counting them apart — "3 gaps against obligations in force, 14 against obligations from 2027-12-02" — rather than renaming the verdict, but that is a wording decision, which is why it waits.
- **`ActiveRules.postponed` stays empty and that is now a decision, not an oversight.** Its docstring says "adopted but not yet applicable … reported so a provider can prepare, never a gap", which describes these rules exactly — but moving them there removes them from the check. The bucket keeps its meaning for a rule with `status: postponed`; the date does not route anything into it.
- **The same wording problem appears in three places now**, and they should be answered together rather than three ways: this; the Art. 5 prohibited note, which already says "applies from 2026-12-02 … treat this as a withdrawal deadline" (`pipeline._prohibited_note`); and the Section 5 oddity, where conformity assessment and registration apply *before* the requirements they attest to.

#### M4d-7 — Art. 2(1) territorial reach is never asked ✅ BUILT 2026-08-19 (`c853340`)

> Built as a `territorial` node between `is_ai` and `scope`, answering a `TerritorialLink` enum that names WHICH limb of 2(1) reaches the system. The design notes below were right about the shape and wrong about one thing: a bare `bool` would not do, because `not_addressed` had to be a distinct answer from "no limb applies". Almost no document mentions territory, so abstaining on silence would have made `needs_review` the verdict for nearly every real document — `not_addressed` records that honestly and continues. The polarity took two attempts: clearing on `None` made every unanswered node clear its system, so only an explicit `OUTSIDE_UNION` does. Two cases flip on territory alone (`us_only_tenant_screening` / `us_built_screening_used_in_ireland`).

<details><summary>original finding</summary>

Found 2026-08-11, while reviewing M4d-2. Not part of M4d-2, whose work is finished — a separate question that the 2026-07-30 audit and the M4d-2 build both missed.

**Art. 2(1) is the ENTRY condition, and the scope node asks only about EXITS.** The node answers "is this system excluded?" — military, research, pre-market, personal, open-source. Those are exceptions: the Regulation applies, and is then withheld. Paragraph 1 is the reverse and is prior to all of them. It reaches providers placing systems on the **Union** market, deployers **located in** the Union, third-country actors whose **output is used in** the Union, and importers, distributors, product manufacturers and authorised representatives. Answering "no exclusion applies" does not answer "does the Regulation reach you at all", and only one of those two is asked.

Consequence: the tool assumes the Act applies to everyone. A US tool sold only to US customers, whose output never lands in the Union, gets a full report of EU obligations it does not owe.

Fails **safe** — over-reporting, never a false clearance — which is why this is 🟠 and not 🔴.

**Why it cannot be a seventh `ScopeExclusion` member.** The enum encodes paragraphs that WITHHOLD the Regulation, and every member's value is a citation for a withholding. Territorial reach is the opposite shape: its absence is not an exclusion, it is the Regulation never arriving. Modelling it as an exclusion would make `Art. 2(1)` read as a carve-out in every report that cited it. It needs its own answer — most likely a `bool` node before `scope`, since an out-of-reach system is not excluded by anything, it is simply not addressed.

**One awkwardness to settle first, not during the build.** Art. 2(1) is written per ROLE — (a) binds providers, (b) deployers, (c) third-country actors by where the output is used. A document that never says which role it is written from cannot answer it, so this interacts directly with M4d-4 (report every role, judge only the ones held). Deciding the role question first would probably make this one small; doing them in the other order means guessing.

**No held-out coverage, and the batch cannot be reused.** `h_pool_drowning_detection_rollout` touches Art. 2(1) only from the far side — a non-EU provider that IS still bound, which tests that the tool does not wrongly grant territorial relief, not that it would ever recognise a system genuinely out of reach. Cases must be authored before the node, same discipline as M4d-2, and real documents that state where a system is sold are easy to find.

</details>

#### M4d-8 — Chapter V: general-purpose AI models are DETECTED, GATED and LISTED, not judged 🟡

Classification built 2026-08-19; the ruleset and both gates 2026-08-24. What is still deliberately absent is any judging.

**What was wrong.** The cascade began at Art. 3(1) and ended at Art. 6, so a foundation-model card answered "yes it's AI", found no Annex III area, and came back **`minimal`** — a false clearance for a provider owing Chapter V. Not an abstention: a wrong answer, in the one direction this project treats as unacceptable.

**What is built (option A, the handover).** A `gpai_model` node after `scope` — after, because Arts. 2(6) and 2(8) say "AI systems or AI models" in terms, so a research-only or pre-market model is excluded before the question is worth putting, and Art. 3(63) carries the same carve-out itself. A `true` exits to the new `RiskClass.GPAI_MODEL`, which is **not a risk tier** and says so: it is a handover naming Art. 53, Art. 55, the Art. 51(2) 10^25 FLOP presumption, the Art. 52 notification duty, and the fact Chapter V has applied since **2 August 2025** — earlier than every high-risk rule in `spec.yaml`. `select_rules` returns nothing for it and `review()` stops with a note saying **NOT ASSESSED, not compliant**.

**A PRE-MARKET model is a third answer, not a `no`.** The first cut answered a bool and told the model to say "false" for a model in development, since Art. 3(63) excludes those in terms. That reintroduced the bug it was fixing: a frontier model still in training would fall back into the risk cascade and report `minimal`, and worse, `scope` usually caught it at Art. 2(8) first and exited to `out_of_scope` before the GPAI question was ever asked. Either way a lab building a frontier model was told it owed nothing, with no mention of what attaches on the day it ships — and Chapter V has no transition period. So `GpaiStatus` has three values, and **Art. 2(8) now FALLS THROUGH** (exactly one node, to the Art. 3(63) question) the way Art. 2(12) does. A pre-market model lands on `GPAI_MODEL` with its duties named and dated; a pre-market *system* concludes at `out_of_scope` with the exclusion's temporal limit spelled out, including that Art. 2(8) does not cover testing in real-world conditions.

**The guard matters as much as the feature.** Art. 3(66) makes a system built ON a general-purpose model an ordinary AI system. Routing out everything that mentions a foundation model would exempt exactly the products the tier logic exists for, so the node tests **generality** (Art. 3(63): significant generality, a wide range of distinct tasks, integrable downstream) rather than size or reuse. A single-purpose pre-trained model — text-to-speech, demand forecasting — is not GPAI however large, which is why `h_open_licence_tts_voices` and `h_open_licence_demand_forecaster` stay where they are. `open_weight_frontier_model_card` and `llm_backed_cv_screener` are the pair that pins the line.

**What is built (option B, the Chapter V ruleset).** Sixteen `AIA-RULE-GP-*` rules, selected by `applies_to_risk_class: [gpai_model]` — the whole of the separation, since every Art. 6-track rule names a tier a model is not. `select_rules`' early return for `GPAI_MODEL` is gone; `OUT_OF_SCOPE` keeps its own, because a system the Regulation does not govern has no set to build. Art. 53(1) is four rules rather than one, because (a) and (b) are lifted by the 53(2) open-source carve-out and (c) and (d) are not, and a single verdict would let a copyright policy hide a missing Annex XI file. Art. 55(1) is four for the same reason. Art. 54 splits by PARTY as Art. 22 does — the provider appoints and enables, the representative performs and terminates — and needs no new `ActorRole`: Art. 3(3) and 3(5) already define 'provider' and 'authorised representative' over a general-purpose AI model as well as a system. Annexes XI and XII are cited and their items ruled.

**NOTHING IN THE CHAPTER IS JUDGED, and that is not a statement about the artefacts.** Annex XI documentation and the Art. 53(1)(d) training-content summary are documents a judge could read. They are withheld because the two gates deciding who owes what are answered by nobody — Art. 51 systemic risk, and the Art. 53(2)/54(6) open-source carve-out — so a verdict drawn from a model card would return a GAP against a provider that owes nothing, in a chapter with no golden set to measure that against. Each rule states its gate in `activation_condition` and is listed for confirmation. Art. 53(1)(c) and (d) are the two that owe nothing to either gate and are the ones to judge first, the day a general-purpose model reference document exists.

**The Art. 51 step is built, on the terms this section set for it.** `systemic_risk` READS A STATED CLAIM and abstains otherwise, exactly as the note below asked: a Commission designation or an Art. 52(1) notification answers `designated`, a stated cumulative training compute answers on the Art. 51(2) 10^25 threshold, and everything else answers `not_stated` — which is a value, not a `None`, because "the card does not say" is a finding a reader can act on and is not the same as no. `gpai_open_source_release` is its twin for the Art. 53(2)/54(6) carve-out, a conjunction of four limbs that one node answers for both Articles.

**NEITHER GATE WITHHOLDS AN OBLIGATION**, and a test pins it: the same model run with `not_stated`/`not_stated`, `below_threshold`/`fully_open` and `designated`/`not_open` must produce an identical Chapter V rule set. The gates are read from the same model card a judge would read, so letting them gate selection would let a card that understates its compute, or calls a restrictive licence open, clear four obligations at once. What they produce instead is `ComplianceReport.chapter_v_gate_note` — and the two are composed TOGETHER, because a fully open release lifts nothing while the model carries systemic risk, and a note written from the licence alone would tell a systemic-risk provider that Art. 54 had fallen away.

**Wait for the Commission's list before building the systemic-risk step.** Art. 52(6) requires the Commission to publish and maintain a list of general-purpose AI models with systemic risk. **As of 2026-08-19 that list does not appear to be published** — the Commission's GPAI guidance and Q&A pages do not link one, and the closest public artefact is the [GPAI Code of Practice](https://digital-strategy.ec.europa.eu/en/policies/contents-code-gpai) signatory roster, which names companies rather than models.

That list is the authoritative answer, and the alternatives are poor. Training FLOPs are almost never in a model card, so a node computing the 10^25 threshold would abstain on nearly every document; estimating it from parameter counts would be deriving a regulatory finding from a guess, which is exactly what the Art. 6(1)(b) `third_party_assessment` node refuses to do. **When the list is published, read it** — that turns a question the tool cannot answer into a lookup it can. Until then the systemic-risk step should only READ a stated claim (a notification, a Code of Practice signature, a declared threshold) and abstain otherwise.

The handover text already tells the reader the list is required, is authoritative, and appears not to exist yet — so someone who checks and finds nothing knows that is expected rather than assuming they searched badly.

**The measurement debt is declared, not hidden.** The golden set has two GPAI cases and both are classification cases, so nothing here is scored. That is why the ruleset ships as a LIST rather than as judgements — the same decision M4d-5 records for the deployer rules: ship the list for every role, and gate judging a role on having cases for it.

#### M4d-9 — The coverage ledger counts articles, and duties live in paragraphs 🟢 every provision ruled on; 52 duties declared unreported

**The gap this closes.** An article-level coverage guarantee asks *"is Article N accounted for?"* and answers yes as soon as **any** rule cites **any** paragraph of it. An article can therefore sit in the in-scope half while most of the duties inside it are modelled by nothing, and the ledger then reads as coverage — worse than an absence, because it invites no further look. Art. 16 is the worked example: excluded whole as an "umbrella list that cross-references other articles", true of nine of its twelve points and false of (b), (k) and (l). Fixing those three by hand left the shape intact, and it was still holding Art. 25(4), 27(3), 49(5), 50(5), 72(3) and 73(6).

**The Annexes were outside the partition entirely.** Every check ran over `articles/`. Operative content lives in the Annexes — Annex III *is* the area list, Annex IV *is* the technical documentation — so an amendment can land there without a word of the Articles changing. This consolidation added **Annex XIV** and moved the Machinery Regulation into **Annex I Section B**, from which Art. 2(2) withholds Chapter III.

**What is built.** Three partitions, each failing closed:

- **Annexes** — used by a rule (`source.annex`) or supplied by the cascade, or listed with a reason. **Pinned version only**, unlike the article partition: rulings for a superseded text buy nothing, since the ruleset does not resolve against that store and no report has ever come from it. Only the pinned version is in the store — `data/policy/{articles,annexes}/2024-07-12/` and `scope-2024-07-12.yaml` are deleted, and the article partition therefore selects everything today. It earns its keep at the next refresh, when a newer text lands beside this one and every changed article must be ruled on before the pin moves.
- **Paragraphs of cited articles** — `provision_labels()` enumerates every citable division (numbered paragraphs, or top-level lettered points for chapeau-plus-list articles like Art. 16), and each must be cited, ruled out of scope, handed to the cascade, or declared as awaiting a rule.
- **Cascade rulings name their node**, and a test checks it exists. This is the load-bearing one: *"the cascade handles it"* is only an answer if some node does. Nothing reads Art. 6(1c), so no entry claiming a node reads it can pass.

`_PARAGRAPH_START` is `^(\d+[a-z]*)\.` for the same reason. A consolidation inserts paragraphs without renumbering, and the letter has to be part of the match: without it `1a.` starts no paragraph and its text is absorbed into paragraph 1, which then resolves to several paragraphs of law under one citation. Art. 6(1c) is individually addressable.

**Every provision is now ruled on individually.** `src/aiact/provisions.py` enumerates **789 addresses** from the stored files — 676 article divisions and 113 annex items — and `src/aiact/coverage.py` resolves each to exactly one status. The count that mattered was BLANKET: a provision nobody read, wearing a ruling written about the article or annex around it. It stood at **426** when the mechanism was built and is now **0**, paid down chapter by chapter through Chapters I to XII and all fourteen annexes. `BLANKET_PROVISIONS` in `tests/test_coverage.py` holds it there: new text, a parser fix that makes a division visible, or an itemised article collapsed back to one line all read as the number moving.

| status | count | means |
|---|---|---|
| checked | 188 | a rule tests documentation against it, and names the rule |
| asked | 64 | the cascade decides it, and names the node |
| not owed | 537 | creates no duty for the roles this tool reports for, with a written reason |
| owed | 0 | a real duty this tool does not check, declared as a debt |
| blanket | 0 | nobody read it |
| unaccounted | 0 | nothing covers it — the failure state |

**What is owed: nothing.** `articles_awaiting_rules` and `annexes_awaiting_rules` are both **EMPTY**, and `OWED_PROVISIONS` in `tests/test_coverage.py` holds them there the way `BLANKET_PROVISIONS` holds the blanket at zero — the count only shrinks, and it going up means a reader is now being told nothing about a duty they have. Every duty this Regulation puts on a role the tool reports for is carried by a rule, and both of Chapter V's gates are asked: `systemic_risk` for the Art. 51 line and `gpai_open_source_release` for the Art. 53(2)/54(6) carve-out. Neither withholds an obligation — they decide what the report TELLS the reader about which side of each line their own document falls on.

**The screen that covered what the partition could not, and what is left of it.** While articles were ruled out *whole*, their paragraphs stayed unitemised and a real duty could sit inside one — Art. 8(2) proved it. `test_a_wholly_excluded_article_holds_no_unacknowledged_duty` screened every such article for a sentence putting `shall` on a provider, deployer, importer, distributor, authorised representative or operator; **48 articles hit**, each declared in `DUTY_BEARING_EXCLUSIONS`. **The scope of the match was the finding.** A first cut matched within a SENTENCE, which under-matched: splitting on `. ` breaks at "Art. 5" and "No 300/2008", so a duty whose subject and verb straddle a citation went unseen. It missed **Art. 41(5)** (justify a technical solution departing from a common specification) and **Art. 71(2)-(3)** (enter the Annex VIII data into the EU database), three real duties inside articles the ledger dismissed in one line. Paragraph scope over-matches instead, the correct direction: dismissing a false positive costs a line of writing, missing a duty costs a false PASS. **The list now holds one entry.** The screen was always a substitute for reading, and the reading is done — every other article on it has a ruling per paragraph, which is a stronger claim than a whole-article dismissal a regex agreed with. Only Art. 94 remains, because the text gives it no divisions to itemise. The mechanism stays: its stale-entry half is what would catch an itemised article being collapsed back.

**The bucket is deliberately separate from `article_rulings`**, and a test forbids an entry in it from claiming the cascade handles it. The two mean opposite things — *"considered, correctly silent"* versus *"a party owes this and no report says so"* — and collapsing the second into the first is exactly how a known gap becomes apparent coverage. Emptying it is the work; editing it away is not.

#### M4d-6 — The ledger cites a class that no longer exists 🟡 two of three fixed 2026-08-11

Arts. 2, 5 and 50 all justified themselves by reference to `ClassificationState`. It is gone. A ledger whose reasons are stale is worse than none, because the coverage test still passes and the file still reads as an audit.

**Arts. 2 and 5 rewritten** against what the code actually does: Art. 2 now cites the `scope` node, `ScopeExclusion` and `RiskClass.OUT_OF_SCOPE`, and separately records that Art. 2(2) is consumed by `AnnexIProduct.chapter_iii_applies` and the Section B branch of `select_rules()`. Art. 5's reasoning always survived the edit — the `prohibited` node is real — and now names it rather than the deleted class.

~~**Art. 50 remains stale**, and cannot be fixed by rewording: the justification claims it is modelled in the classification graph, and while the `transparency` node does answer it, nothing then CHECKS the documentation against it.~~ **Fixed 2026-08-20 by M4d-3, in the order this note asked for**: the check was built first, and the ledger entry then left `out_of_scope` because Art. 50 is cited — not rewritten to read plausibly while nothing checked it.

#### Checked and genuinely fine

- **The 19 rules against Chapter III** — Art. 9-15 and the Art. 16+ provider obligations are modelled individually, with Art. 8 correctly excluded as a chapeau that would double-count. Art. 16 is modelled point by point: the nine points that cross-reference Art. 17-21/43/47-49 are left to those rules, and the three that cross-reference nothing are rules of their own.
- **Art. 72/73** — in scope, and the ledger notes they were found *by* writing the ledger.
- **Art. 6(4)** — modelled as `AIA-RULE-NHR-A06-4`, and the pipeline gate was written around it.
- **Other Annex III areas** — the enum models all eight; Art. 9-15 apply to every high-risk system regardless of area, so employment scope constrains the golden set, not the ruleset.
- **GPAI (Ch. V), other actor roles, notified bodies, sandboxes, institutional and amending articles** — all excluded with reasons that hold.

### M5 — Eval (numbers)

- Classification: accuracy by `difficulty`; citation accuracy; reasoning-step accuracy.
- Gap: recall, precision, false-positive rate on `untouched`, accuracy by ablation type.
- Expect (and report) the curve: strong on `removed`, drop on `present_but_inadequate`, bigger drop on `distractor`. The curve IS the interview story.

**Strawman baseline already measured** (`python scripts/run_eval.py`, keyword matcher, Layer 2 dev, no API): overall **88.0%** — and that number is exactly why the breakdown is mandatory. Behind it: **INADEQUATE detection 0/6**, zero INADEQUATE verdicts emitted at all, catch rates 14.3% / 14.3% / 0.0% on removed / inadequate / distractor, and 100% clean on the 115 intact judgements. A checker that cannot make the project's central distinction still scores 88% on the aggregate. Keep this as the contrast the real numbers are reported against; a test pins the 0-INADEQUATE property so a future checker beating it registers as progress.

> ⚠️ **The distractor column is thin.** `distractor` cases exist for only **4 of 7** rules (A09, A10, A14, A15) — A11, A12 and A13 have none. The roadmap's headline curve (strong on `removed`, weaker on `present_but_inadequate`, weakest on `distractor`) is therefore partial at its most interesting end. Fill before reporting the curve.

**DoD:** one command produces the metrics table; cost per full run reported (LiteLLM).

#### THE HELD-OUT RESULT — Layer 1, measured once at `6608c5b`, 2026-08-14

**15/24 risk class (62.5%). Art. 50 19/24. $0.1493, 117 calls, Flash.** The set is now SPENT: any fix from here needs fresh cases before another number means anything.

> **SPENT, AND MOVED — 2026-08-15.** All 24 cases now live in `classification_cases.yaml` as `dev`. Every failure below was read and diagnosed, so the set was no longer blind whatever the file was called, and leaving the label on it invited someone to quote a number from it as if it were. Three things follow. The figure above **stands as a historical measurement at `6608c5b`** and is not reproducible after this date. Layer 1 has **no held-out split** until a fresh one is authored. And the labels **stay as written** — moving a case to dev makes it tunable, not rewritable; a label is revised only by an argument from the enacted text, never because a model disagreed with it.
>
> The gain is that dev goes 18 → 42 and the pin cleanup below stopped being a contamination question. The cost is that there is nothing to report against until the new set exists.

The aggregate is not the finding. Split by batch, because the three have different histories and different worth:

| batch | cases | score | status |
|---|---|---|---|
| 3 — Art. 2 (M4d-2) | 9 | **8/9** | blind, never seen |
| 2 — Annex I (M4d-1) | 6 | **2/6** | blind, never seen |
| 1 — original | 9 | **5/9** | seen once at `85ea48d` (7/9), tuned against indirectly since |

**Batch 3 holds up, and that is the answer to the question it was written for.** No policing-or-border confusion at all, so the Annex III(6)/(7) argument added after the dev miss GENERALISED rather than fitting `border_surveillance_drone_analytics`. All five exclusions landed; both open-source cases split correctly, the exclusion standing for the forecaster and lifted for the TTS model by Art. 50(2). One miss — `h_consumer_drone_subject_tracking`, expected `minimal`, got `out_of_scope`: a consumer product read as a personal-use deployer. A FALSE CLEARANCE, the direction that matters, and the prompt already carries a sentence against exactly it (*"answer none when the description is written from the provider's side"*). Not enough.

**Batch 2 is the real defect, and it is a defect in the design's own terms.** Four misses:

| case | expected | got |
|---|---|---|
| `h_lvo_triage_notification` | needs_review | **high_risk** |
| `h_autonomous_retinopathy_screening` | needs_review | **high_risk** |
| `h_fundus_camera_onh_montage` | minimal | needs_review |
| `h_pap_comfort_setting_recommender` | minimal | needs_review |

The first two are the serious ones. A 510(k) never states an EU conformity route, so Art. 6(1)(b) is structurally unanswerable from those documents — which is exactly why the blind author keyed them `needs_review`, and exactly what the **DECIDED: read condition (b), never derive it** note under M4d-1 exists to enforce. The node derived it anyway, confidently. The rule was written down, the prompt says *"Do NOT infer the answer from the kind of product, its risk class, or what such products usually require"*, and the model inferred it. The other two fail the opposite way — over-abstention — so the same node is wrong in both directions.

**Batch 1: 5/9 against 7/9**, but the model and effort settings changed between the two runs, so it is not a clean comparison. Worth naming anyway: `h_photo_ethnicity_sorting` went **prohibited → high_risk**, downgrading a banned practice to one that may ship once the paperwork is fixed.

**Art. 50: 19/24, and 3 of the 5 misses are a SCORECARD artifact.** All three are abstentions on `out_of_scope` cases, where nothing under Art. 50 is owed because the Regulation does not apply — scoring transparency there measures nothing. The 2 genuine misses are false positives (`h_interview_note_polisher`, `h_consumer_drone_subject_tracking`). Fix the scorer, not the model: an out-of-scope case should not carry a transparency column at all.

**What was deliberately NOT done:** no case edited, no prompt changed, no key revised. The legitimate moves are to accept and record (this entry), to fix the code or prompt and author fresh cases before re-measuring, or to argue a key wrong FROM THE TEXT — never from the model having disagreed.

#### M5-a — Per-node metrics: which QUESTION is weak, not which case ✅ BUILT 2026-08-15

**Was:** the number was end-to-end — one risk class per case, pass or fail. It could not say which of the nine cascade questions produced the failure, so a 2/6 batch said the Annex I route was broken and nothing about where. The diagnosis above was reached by reading cases by hand, which does not scale.

**Built:** `src/aiact/eval/node_score.py`, printed by `scripts/classify.py --golden` after the two headline axes. Per node: asked / pinned / correct / **wrong** / **abstained**, with the last two kept apart because they are different defects needing different fixes and one node can produce both. It costs nothing extra — the answers already pass through a normal run.

**It found a defect on a run that scored 18/18.** `candidate_dedupe_prep` answered derogation **(d) preparatory task** where the key says **(a) narrow procedural task**. Any derogation routes to `not_high_risk`, so the case passed and the aggregate was perfect. Right answer, wrong reasoning, invisible to every number that existed before.

**DECIDED: the answers ride on the RESULT, not on an eval-only wrapper.** The first build wrapped the brain to record what was asked. Rejected on review, and rightly: `GraphState` already held every answer and `assemble` was discarding most of them. `ClassificationResult.answers` now carries all of them in production too, both evals read from it, and `run_grounding.py`'s private recorder was deleted rather than shared. Net effect: one file fewer, and the report gains the audit trail — the Art. 2 and Art. 5 clearances a reader most wants were previously thrown away, since `triggered_by` keeps only the deciding nodes.

**`Question.label`** carries the plain-language form of each question, for reports. Not `text`, which is addressed to a model and full of instructions that mean nothing to a reader.

**The scoring rule needs BOTH halves — asked AND pinned** — because each alone fails in the opposite direction. Without ASKED, an `out_of_scope` case is marked wrong on Annex III, a question nobody put to it. Without PINNED, every unpinned node scores as though it had been. Both are tested explicitly.

**A PIN IS AN ASSERTION ABOUT THE ROUTE, not just about an answer.** Writing a field means "this question is expected to be asked, and this is the expected answer"; omitting it means "the cascade is not expected to reach it". `route_for()` in `classify/graph.py` walks the cascade's OWN `_route_*` functions — never a second copy of the rules — and the loader requires each case to pin exactly the on-route nodes. So a routing bug is now a load-time failure rather than something the scorer silently skips, which matters: a wrong route is how the Annex I hole survived, with cases scored on the nodes that ran and never on the nodes that should have.

`NEEDS_REVIEW` cases are **exempt**, and that is a gap in the answer key rather than a concession. Such a case abstains at one node and stops, so its route is as checkable as any other — but nothing records WHICH node. The obvious inference, that the first unpinned node is the abstention point, breaks on the two fields the risk class fills in: a case abstaining at `scope` is indistinguishable from one answering "no exclusion applies". Expressing it needs an `expected_abstains_at` field, which would also let a run be checked for abstaining in the RIGHT place — today a model that ducks the wrong question still passes. **Open decision.**

**Cleanup this forced, 2026-08-15:** 9 pins added to close asked-but-unpinned gaps, then 11 more added and 27 stray lines removed across the merged set. Every stray line asserted a verdict for a question its case never reaches.

**What the table says now, over 42 cases** — and the remaining problems are all in the golden set, not the scorer:

| | |
|---|---|
| `is_ai` | **no key at all.** 42 asked, 0 pinned. A `false` there routes straight to `minimal` and skips the whole cascade — the one node with no ground truth, printed as a blank row every run so it cannot be forgotten. |
| `scope` 35/42, `prohibited` 33/36, `annex_i` 21/25, `transparency` 36/42 | **base-rate dominated.** A constant reply scores each of those. Merging the blind batches doubled the volume and made the skew WORSE, because the added cases were mostly majority-class. |
| `third_party_assessment` 4, `derogation` 5 | **thin.** |
| derogation conditions | **1 of 4 exercised.** The node can return four Art. 6(3) conditions; the set only ever expects `narrow_procedural_task`. The (d)-for-(a) miss above is exactly what that blindness hides. |

That is the brief for the next held-out set: **minority answers, not more cases.**

#### M5-b — A fresh held-out split, authored to a coverage brief 🔴 next

Layer 1 has no held-out split. There is nothing to report a Layer 1 number against until this exists, so it blocks every future measurement of the classifier.

**What is different this time: the coverage is specified in advance.** The last three batches were shaped by whichever documents turned up, which is why the set ended up with two `high_risk` cases and none at all for `is_ai`. Choosing targets before authoring is not contamination — only the LABELS must be reached blind, and the table above says exactly where the set is blind to its own failures:

- **`is_ai = false`** — a rules engine, a lookup table, a fixed-formula calculator. Art. 3(1) turns on INFERENCE, nothing tests that line, and a wrong answer there clears any system in the world.
- **Art. 6(3) conditions (b), (c) and (d)** — three of the four derogations are never expected anywhere.
- **Art. 50 duties (4) deep fakes and (4) public-interest text** — never expected anywhere, and the node now answers a LIST of duties rather than a boolean, so a run naming the wrong duty is newly visible. Of the 43 cases, 37 expect no duty at all: (1) once, (2) twice, (3) three times.
- **Art. 5(1) points (a)–(e) and (h)** — the set expects only (f) emotion inference and (g) biometric categorisation. Six of the eight prohibitions are never exercised, and the node now answers WHICH point rather than a bare boolean, so that blindness is newly measurable.
- **Minority answers** for `scope`, `prohibited`, `annex_i` and `transparency`: more exclusions, more banned practices, more Annex I products, more Art. 50 triggers.
- **`third_party_assessment`** on documents that DO state a conformity route — an EU technical file rather than a US filing, so the node can be measured reaching `high_risk` and not only abstaining.

The method is unchanged and already written down: `docs/heldout-brief.md`, with `.claude/hooks/heldout-guard.py` armed. Cases go in a NEW file carrying `default_split: test`; every tool keys on that field, not on the filename.

**Also add `expected_is_ai_system` first** — the field does not exist, so `is_ai` cases cannot be expressed at all. Required rather than defaulted, so no case can omit it by accident. The 42 existing cases all answer `true`, which is why that column alone would score 42/42 and prove nothing without the negatives above.

#### Reasoning grounding — the second number, for the half that has no key

`src/aiact/eval/grounding.py`, `python scripts/run_grounding.py --layer classify|gap`. The scorecards score ANSWERS, which are closed questions with exact keys. The one-sentence `reasoning` beside each answer is an OPEN question — a hundred wordings are equally right, no key can exist — so nothing measured it, and a right answer reached by misreading scored exactly like one reached from evidence. This grades that sentence the only way an open output can be graded: **against the SOURCE the answer was reached from, never against an expected sentence.** Kept out of the answer path entirely — it is a model's opinion, which is what the scorecard proper refuses to be.

**Measured on dev (2026-08-14), `gemini-2.5-flash` grading `gemini-2.5-flash`.**

- **Layer 1: 98 of 98 supported (100.0%)**, grader cost ~$0.092 on top of the ~$0.12 run.
- **Layer 2: 132 of 133 supported (99.2%)**, grader cost ~$0.117 on top of the ~$0.19 run.

> **Read the process before the numbers, because the process is the finding.** Four rounds were run before these. Every single unsupported claim in the first three was the GRADER's fault, not the model's — and each time it looked like a real defect, with a plausible mechanism attached:
>
> | round | what the grader was given | result | what the findings actually were |
> |---|---|---|---|
> | 1 | the material only | 71.4% / — | **28 of 28** were true statements of law, absent from a document that was never going to contain them |
> | 2 | material, plus "ignore legal claims" | 92.9% / 88.0% | the exclusion leaked; a further tuning pass went *backwards* (→88.8%, inside run-to-run variance) |
> | 3 | material + enacted text | 99.0% / 95.5% | the QUESTION text was still missing — a node quoting its own instructions scored as invention |
> | 4 | **the prompt itself, as sent** | **100.0% / 99.2%** | — |
>
> Two findings were written up here as structural before being retracted: an `AIA-RULE-HR-A11` cluster (9 of 16, "covers all required elements of Annex IV" — read as a completeness check answered from `k` excerpts) and `border_surveillance_drone_analytics/scope` ("listed in Annex III(7)" — read as the model answering from memory of the Act, against the anti-memory rule the article store exists to enforce). Both dissolved once the grader saw what the model saw. The Annex III(7) sentence is in the scope QUESTION, written into `graph.py` deliberately by the "National security is not border control" commit; the model was quoting its instructions.
>
> **The lesson is the design rule at the top of `grounding.py`: never rebuild the prompt, carry it.** A hand-assembled "what the model saw" is wrong by whatever you forgot, it fails by INVENTING findings rather than missing them, and it goes stale the moment either prompt changes. `Judgement.prompt` and `LLMBrain._user_content` now supply it directly.

**How to read 100.0% / 99.2%.** Two things are unresolved and both push the same way:

- **The grader marks its own work.** `ReasoningGrader` defaults to `settings.llm_model`, so this is `gemini-2.5-flash` grading `gemini-2.5-flash` — shared blind spots, and self-preference. A near-perfect self-grade is exactly what that bias predicts, so these are a FLOOR on the defect rate, not a measurement of it. Grading with a different family is the next change and is cheap: the calls are short.
- **This metric has variance the verdict scorecard does not.** `expected == got` returns the same number every run; this one does not, and its size is unmeasured. The single Layer 2 finding (`AIA-RULE-HR-A15__removed/AIA-RULE-HR-A11`) is n=1 and nothing should be built on it.

Its honest value today is as a **regression guard** — it would catch a prompt change that let either model start reasoning past its source — not as a discovery tool. It has found nothing about the system yet. It found a great deal about itself.

### M6 — Packaging (this is a deliverable, not an afterthought)

README (problem → architecture diagram → eval numbers up top → use cases), 2-min demo (the flip-test: one sentence flips not_high_risk → high_risk), clean commit history, FastAPI endpoint (document in → structured report out).

> ~~**First job here: compose the two graphs.**~~ ✅ **done 2026-07-30** — `src/aiact/pipeline.py`, `review()`, plus `scripts/review.py` and 7 tests. One document in, classified, then checked against whatever obligations that classification activates. Verified live on both paths: the compliant reference document classifies `high_risk` via the Art. 6(3) carve-back and passes 7/7 with 11 process obligations listed separately; a prohibited practice stops at the gate.
>
> **The gate is NOT "high risk only" — that was the plan and it was wrong.** `AIA-RULE-NHR-A06-4` applies to `not_high_risk`: a provider claiming an Art. 6(3) derogation must document that assessment and register under Art. 49(2). Gating on high-risk would have silently dropped a real obligation, and a test now pins that a `not_high_risk` classification still reaches it. What the gate actually stops is `prohibited` (Chapter III describes how a PERMITTED system must be built; checking documentation against it implies the system may ship once the paperwork is fixed) and `needs_review` (which obligations apply is not yet known). `minimal` is not gated at all, and that turned out to matter: `AIA-RULE-ALL-A04` (Art. 4 AI literacy) attaches to it, and so does any Art. 50 rule whose duty the cascade found. A gate there would have hidden both.
>
> **`ComplianceReport.scope_note`** was added for this: an empty `findings` list reads as a clean bill of health, so whenever the pipeline reaches that state deliberately the report says why in the report itself.
>
> **`review()` opens no trace of its own.** Both layers already open one, and an outer `trace_run` would mint a trace id the inner ones immediately replace — an empty parent with its children elsewhere. They group by SESSION, which is why `system_id` is threaded into both.
>
> Left for the FastAPI layer: `tests/test_pipeline.py` is the check neither eval can make — Layer 1 stops at the risk class, Layer 2 is handed the correct classification, so a misclassification propagating into an empty report is only reachable at the seam.

Make the harness engineering visible. The observability/trace layer, the per-rule tool calls, the provider abstraction — these are engineering, not plumbing to hide. Show a Langfuse trace in the README. (Personal angle worth surfacing in interviews: prior experience running LiteLLM as a proxy with header rewriting, and MCP work — most candidates only use these as an SDK. That's harness engineering; name it.)

> ✅ **Endpoint built 2026-10-07** — `POST /api/review` in `src/aiact/report_app/` (`make app`, port 8766), separate from the internal backend UI (`src/aiact/backend/`, `make backend`, port 8765 — named the coverage UI until 2026-10-14). It takes raw text plus a `system_id`, so `SystemUnderReview` and `DocumentChunk` were deleted, and `ComplianceReport`'s docstring no longer names them. The response carries the report plus every rule and norm it names, resolved (requirement, citation, what would satisfy it, the date it applies from per use case), and the report's notes as fields. Model keys still come from the environment; per-request keys are M9.

> ✅ **Report page built 2026-10-07 to 2026-10-15** — plain HTML/JS served by the same app, in the backend's orange/white/black. Top to bottom:
> - **The system and its classification**: a name and short summary written by a model from the document (shown only, never read by the review), then the risk class with its basis.
> - **Verdict**: says what was actually judged. "Documentation falls short / meets today's duties / ready or not ready for {date}" for a regulated system, and "Compliant" only when every duty in force a document can show is met AND every other duty in force is ticked off on the reader's checklist. One line per point in time (Now, From {date}, Your checklist), each with the duties to fix under it, linking to the row. Prohibited, unclassifiable and out-of-scope systems get their own answers.
> - **Operator duties**: one list, every row tagged with the roles that owe it. Filters for operator, check result (Met · Partly met · Not met · Unclear · Duty · Done) and date (all / in force now / starts later); column names stay pinned while scrolling. Duties a document can show are "Checked against your document"; the rest are "Not verifiable from documentation", each with a tick box kept in the browser per system. Notes on facts the document did not settle sit in one panel above the list.
> - **Other provisions**: permissions, rights, legal effects, limitations, and what authorities must or may do, tagged by operator or authority and labelled by type, never judged.
> - **Readable everywhere**: no internal ids reach the page — criteria show their provision and action, rule cross-references show the article, guidance tags show the Commission document. Hovering a role in a filter shows its Art. 3 definition (or, for a role Art. 3 does not define, a marked summary). The last report and draft survive a reload, and a saved report refreshes its rule texts from the current spec.
> - **System-card guide** at `/guide`, rendered from `docs/system-card-guide.md` and copyable as Markdown, linked from the input and from an unclassifiable verdict.
>
> Backend changes it forced: duties that bind only under an unsettled condition (Art. 26(7), 48(5)) get their own `conditional_duties` bucket instead of falling into the scope list, and **every rule's dates now come from one place** — `PolicyRule.temporal_regime_id`, an entry of the norm inventory's timing table, replacing `effective_date` / `effective_date_by_route` (2026-10-14). The old split let 39 route-dated rules be treated as in force when they start in 2027. Art. 111 now applies from 2 August 2026 with its own deadline, shown as "by {date}".
>
> **Open:** the verdict counts every role's duties and ignores the operator filter; the high-risk path has only been checked on offline reports, because both recent real runs of the guide's example misclassified it as Art. 5(1)(c) social scoring (tuning waits for the UI to settle).

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
- **Art. 50 goes per use case.** It is asked once per cascade run, so N runs produce N answers for a field currently typed as a single `Answer | None`. The job-ad generator owes transparency; the scorer may not.
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
| whether it infers **emotions**, scrapes faces, scores social behaviour, manipulates — and whether an Art. 5 exception applies (medical or safety use, a lawfully acquired dataset, a human assessment on objective facts) | `prohibited` | Art. 5(1)(a)–(h) |
| the **Annex III area** it operates in, if any | `annex_iii` | Art. 6(2), Annex III |
| whether it **evaluates or ranks natural persons** — the single most decisive fact | `profiling` | Art. 6(3) |
| whether it only performs a narrow procedural task / improves prior human work / detects patterns / is preparatory | `derogation` | Art. 6(3)(a)–(d) |
| **who relies on the output** — whether a person reviews every case regardless, or the system settles some alone | `significant_risk` | Art. 6(3), first subparagraph |
| whether it **generates content or interacts with people directly**, infers emotions, or produces deep fakes — and whether the author is provider or deployer, since Art. 50 splits its duties between them | `transparency` | Art. 50(1)–(4) |
| whether the author is **provider or deployer** | scope | Art. 3(3), Art. 3(4) |

Plus the framing rules that make a card classifiable at all: describe **function, not benefit**;
state what the system does **to a person**; one section **per intended purpose** rather than per
product (which also seeds M7); and say what it does **not** do, since derogations turn on absence
— including who acts on its output, since a narrow role exempts nothing if it decides the outcome.

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

- Pin `act_version_date` everywhere. Currently pinned: `act_version_date: 2026-07-27` (the consolidation applicable from that date; verbatim article store in `data/policy/articles/2026-07-27/`).
- **The Omnibus consolidation is ADOPTED.** **Regulation (EU) 2026/1744** of 8 July 2026 (Digital Omnibus on AI) amends the Act, applicable **27 July 2026**. The ruleset, the cascade and the coverage ledger all resolve against `data/policy/{articles,annexes}/2026-07-27/`, and the original store is deleted now that nothing pins it. `test_every_fetched_version_is_covered_or_declared_untriaged` is what kept the intermediate state declared rather than silent, and stays for the next refresh: a fetched version has a coverage ledger or a written reason it does not, and never neither. What the refresh found — **36 articles changed, 6 inserted** (4a, 60a, 75a–75d), **Annexes I and VIII changed, Annex XIV added** — matches the amending act's own enacting terms exactly, which is two independent sources agreeing. It also found a live defect: `render_article` matched `(\d+)` on "Article 4a" and returned **4**, which would have silently overwritten Article 4 rather than failing. Article ids are strings throughout now, and a duplicate id exits.
- **What the amendment costs us, not yet paid** (in the order it should be):
  1. **Five rules carry superseded text** — `AIA-RULE-ALL-A04` (Art. 4 replaced whole), `AIA-RULE-HR-A10` (10(1) replaced, 10(5) **deleted**, 10(6) replaced), `AIA-RULE-HR-A11` (11(1) 2nd subpara), `AIA-RULE-IP-A25-2` (25(2) replaced and expanded with points (a)–(c)), `AIA-RULE-PO-A43-3` (43(3) replaced). Ten more cite an amended article but an untouched paragraph.
  2. ~~**`effective_date` is wrong on every Chapter III Section 1–3 rule.**~~ ✅ **done 2026-08-20**, and the two readings that were mine rather than the text's are now carried as `effective_date_note` on the rules they affect rather than as comments only we read — see M4d-5. `PolicyRule.effective_date_by_route` carries the two dates the amended Art. 113 gives — **2 December 2027** for a system high-risk under Art. 6(2)/Annex III, **2 August 2028** under Art. 6(1)/Annex I — and `effective_date_for(route)` resolves them. Structurally the same answer as `applies_to_route`: there the route decides WHICH law applies, here WHEN. A validator rejects a rule stating its date both ways, and an unknown route resolves to the EARLIER date deliberately, because telling a reader they have until 2028 when the answer was 2027 is the direction that costs them. **21 rules** (Arts. 6–27, less Art. 6(4)) took the split; the section boundaries were read out of the consolidated Formex rather than assumed. Sections 4 and 5 were not moved, so **Arts. 43 and 47–49 keep 2 August 2026 — already passed.** Conformity assessment and registration therefore apply *before* the requirements they attest to. That is what Art. 113(c) says, it is pinned by a test, and it is odd enough that it should be checked against a practitioner rather than trusted because our parser produced it. **Art. 6(4) is the one date the Article does not settle**: its limbs run to systems "classified as high-risk pursuant to Article 6(2)" and "6(1)", and Art. 6(4)'s subject is a system the provider concluded is NOT high-risk, so it answers to neither literally. It takes the Annex III date, on the ground that Art. 6(3) derogates from 6(2) alone; the arguable alternative — falling back to the general date — would make the duty apply sixteen months before the classification it documents. Recorded in the spec as a choice, not a reading. **The dates are recorded, not enforced**: nothing gates a rule out of a report for being inapplicable today, so a high-risk report still raises all of Chapter III. Making them live is M4d-5 and a bigger change — see below.
  3. ~~**Art. 5 gained two prohibitions**~~ ✅ **done 2026-08-20.** Points (ba) and (bb) — non-consensual intimate imagery and CSAM — are `ProhibitedPractice` members, inserted in the Article's own order so `point` runs `a, b, ba, bb, c…` rather than a contiguous alphabet. **The prompt is where the work was.** Art. 5(1a) narrows both, and it turns on SAFEGUARDS rather than capability: a provider is caught only where producing that material is the system's intended purpose, or where it is a reasonably foreseeable and reproducible output *and* the system has no reasonable safeguards against it; a deployer only where it uses the system for that purpose. Art. 5(1b) further excludes editing that does not increase exposure. Without that qualifier in the question, any image generator answers (ba) — and a false `prohibited` is the most damaging verdict this tool produces, because it tells an organisation to withdraw a lawful product and skips the obligation check entirely. Two dev cases pin the boundary: `image_generator_with_safeguards` (minimal, owing Art. 50(2)) and `nudify_app_no_consent` (prohibited). **And Art. 5 now has two application dates** — the first time it has had more than one. `ProhibitedPractice.applies_from` carries them (2 Feb 2025, or 2 Dec 2026 for the inserted points), `ClassificationResult.prohibited_practice` reads the point off the cascade's own answers, and the pipeline's prohibited note says *when* a not-yet-applicable ban bites instead of saying "withdraw the practice" about something the Article does not yet reach. That is M4d-5 in miniature, and answerable because the date is a property of the point rather than of the whole ruleset.
  4. **New provisions nothing has ruled on**: Arts. 4a, 60a, 75a–75d, Annex XIV.
- **Enacted law and Commission interpretation are stored and cited separately, and never merged.** `data/policy/articles|annexes/` hold verbatim enacted text cited with `LegalSource`; `data/policy/guidance/` holds verbatim passages from Commission Communications cited with `GuidanceSource` (`binding: false`, structurally enforced by a validator). Each guidance snippet records its document sha256 and its own body sha256, so a drifted or dangling citation fails at load rather than degrading silently. Any verdict that leaned on interpretation reports `rests_on_guidance` and names the CJEU as the authoritative interpreter. Two documents, one snippet each: `C-2025-5052/workplace-covers-recruitment` (Art. 5(1)(f), "workplace" reaches recruitment) and `C-2026-5054/machine-readable-marking-defined` (Art. 50(2), what a machine-readable mark is). The PDF behind each is now hash-checked too — a snippet's own sha proves the quote has not drifted, and said nothing about whether the document it was verified against is still the same file. **Re-verified 2026-08-20**: the stored PDF is byte-identical to the live one at its pinned URL (sha256 `298bf867…`), so the snippet stands.
- **Guidance still owed, checked 2026-08-20.** The **high-risk classification guidelines** (Art. 6 / Annex III) are **still not adopted** — draft of 19 May 2026, with a further round with the AI Board before adoption — so `job_ad_generation` stays contested and the M4 note's action is unchanged. (That note says the consultation closed 23 July 2026; sources say **23 June 2026**.) **`C(2026) 5054 final`, 20 July 2026 — Guidelines on the transparency obligations under Article 50**, 51 pages, adopted twelve days before Art. 50 began to apply. **Stored 2026-08-20.** We modelled Art. 50 as four rules the day before finding it, with `evidence_expected` written from the bare Article text — and paragraph (71) turns out to ground the one interpretive claim we had invented: that a human-readable "AI-generated" label does not discharge Art. 50(2). It does not, but the same passage adds that such labels are not *excluded*, they are a complement — the half an interpretation written from the bare Article was most likely to miss. **Cited by the rule that needs it, 2026-08-20.** `PolicyRule.guidance_refs` is the only guidance a rule authors; `guidance_context` and `guidance_sources` are injected by the loader exactly as `requirement` is injected from `source`, so a rule can no more hand-write an interpretation than it can hand-write the Article — the loader rejects both, and a dangling ref fails the LOAD rather than the run. The judge sees the passage in its own block, labelled non-binding and placed after the enacted text, because a judge shown the two as one passage would weigh an interpretation as law. `Finding.guidance` records what the judge was SHOWN — taken from the rule, not from the model's reply, since the model is never asked and a self-report would be the wrong evidence — and `ComplianceReport.guidance_sources` rolls up BOTH halves, the classification's and the obligation check's, because a reader asking how much of a report rests on interpretation is asking about the report. `AIA-RULE-TR-A50-2` is the only rule citing guidance and a test keeps it that way: a ruleset quietly accumulating interpretations is one whose verdicts are progressively less grounded in the Article they cite.
- Vendor names never sit next to a legal verdict in the public repo. Classify anonymised function descriptions; keep vendor→archetype mapping private.
- Ground truth is an engineer's reading of the law, cross-checked against the Commission's own Guidelines/checker where possible. Say so. Don't oversell it as a benchmark.

## Not this project — sectoral classification ("go deep")

Rejected on 2026-07-30 and recorded so the reasoning survives, because it will look tempting again.

**The idea.** Art. 6(1)(b) asks whether a product needs third-party conformity assessment. That is answerable — for medical devices, MDR Annex VIII Rule 11 gives the class from the intended purpose, and MDCG 2025-6 Table 1 maps class → yes/no. Encode the equivalent for each Annex I instrument and the tool could resolve the Annex I route end to end instead of handing it back.

**Why not.** Three reasons, in order of weight:

1. **Nobody here can check it.** The AI Act work is verifiable by a careful reader against text this repo resolves verbatim. MDR Rule 11 classification is a specialist judgement, and a wrong class silently flips the risk tier. The project would be shipping confident answers in a field it cannot audit — the precise failure it was built to avoid.
2. **It is twenty instruments, not one.** Medical devices are the tractable one. Machinery Annex IV, ATEX categories, PED tables, vehicle type-approval, marine equipment — each is its own body of rules, and stopping after the easy one produces a tool that is authoritative about medical AI and silently wrong about lifts.
3. **It is a different product.** Answering "what class is my device under MDR" is a regulatory-affairs tool. Answering "what does the AI Act require of me" is this one. Users of the first already have specialists; users of the second mostly do not.

**If it is ever built,** the shape is clear and it should be a separate deliverable with its own eval and its own reviewer: per-instrument classification rules as guidance (not law — MDCG documents are explicitly non-binding, so `data/policy/guidance/` and `rests_on_guidance`, never `articles/`), a sectoral eval set labelled by someone qualified in that sector, and a report that names which instrument and which rule decided the class. ~~The useful middle step, far cheaper than the whole thing: when the tool parks a question, say WHICH rule is unresolved and WHICH specialist answers it.~~ **Built 2026-07-30** — `AnnexIProduct.legislation` and `.who_decides_conformity`, surfaced by `_handover` in the classification reasoning. A parked Art. 6(1)(b) now names the instrument (`Regulation (EU) 2017/745`), the specialist (the MDR notified body, or the regulatory-affairs lead holding the Annex VIII class), and what each answer would mean. Per sector, because the right answer differs: a vehicle is type-approved, a machine self-certifies unless listed in Annex IV of the Machinery Directive, an unmanned aircraft goes to EASA. Three tests pin it, including one that every one of the 20 products has both fields — a product with neither would abstain into silence.
