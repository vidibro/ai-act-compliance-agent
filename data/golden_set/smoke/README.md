# Smoke check — real-world descriptions (NOT a split, NOT scored)

Three anonymised descriptions drawn from real, public HR-AI vendor pages (July 2026). They exist to
answer **one question**, asked *before* tuning starts:

> Do the synthetic golden-set documents look like the documents we actually care about?

That is all. These are **not** a dev split, **not** a held-out split, and **not** scored. Nothing is
tuned against them and no number is reported from them. They are three real texts we read to check
that our guesses about real prose are roughly right — cheap insurance against discovering a
synthetic-vs-real gap only *after* the held-out set has been spent.

If they are ever labelled and scored, they stop being a smoke check and must be moved into a split
with the discipline that implies.

## Provenance and anonymisation

Sourced from public product/marketing pages of real vendors, then **rewritten**: no vendor, product
or customer names, no verbatim copy. What is deliberately preserved is the *shape* of the original —
register, ordering, hedging, contradiction, and where the decisive functional fact sits. What is
necessarily lost is the exact wording. So these are realistic, not authentic; treat them as a
sanity check on the synthetic set's realism, not as ground truth about any real product.

Vendor→archetype mapping is not recorded here, per the repo's legal-hygiene rule: no vendor name
sits next to a legal verdict.

| file | archetype | plausible class | why it was chosen |
|---|---|---|---|
| `screening-and-ranking.md` | CV screening that also scores | `high_risk` (Art. 6(3) profiling carve-back) | the flip, in the wild |
| `video-interview-analysis.md` | recorded-interview analysis | `prohibited` (Art. 5(1)(f)) | emotion inference in a hiring context |
| `interview-coordination.md` | scheduling/logistics | `minimal` | the false-positive control, in the wild |

"Plausible class" is the author's reading for orientation only — these are **not labelled cases**.

## What the comparison showed

Five differences between real vendor prose and our synthetic documents. Each is a way tuning against
the synthetic set alone could teach the checker the wrong lesson.

1. **Real pages carry human-in-the-loop reassurance that is legally irrelevant.** Every one of the
   three says some version of "your team decides" or "humans stay in charge". Under the Act this
   changes nothing: Annex III 4(a) catches systems used to filter or evaluate applicants whether or
   not a person signs off, and Art. 5(1)(f) does not care who makes the final call. But it *reads*
   exculpatory, and it sits exactly where a model looking for grounds to downgrade would find it.
   This is a **distractor claim** — the Layer 2 `distractor` ablation's exact logic (plausible,
   on-topic, non-responsive to what the law asks) applied to classification instead of gap
   analysis. Our Layer 1 cases contain almost none of it.

   *(An earlier draft called this a self-contradiction — "runs interviews without human
   intervention" versus "hiring managers retain final say". That was wrong: those describe
   different stages and are perfectly compatible. The problem is not inconsistency, it is that a
   true and reassuring statement is legally beside the point.)*

2. **The decisive fact is scattered, not buried.** Our `cv_parsing_plus_scoring` case hides the
   decisive sentence inside a paragraph. Real pages instead put it in a feature bullet under a
   *different heading* from the overview, so the overview alone reads as extraction-only. The
   failure mode is different: not "did you read closely enough" but "did you read the whole page".

3. **Adjacent-product noise.** A genuinely logistics-only scheduling product still carries a
   cross-sell line about identifying and advancing strong candidates — a stray phrase from a
   different product in the same suite. Our `interview_scheduler` case is clean of this. Real
   minimal-risk documents contain high-risk-sounding text that belongs to something else, which is
   a false-positive trap the synthetic set does not exercise at all.

4. **Absence, not inadequacy.** Marketing pages simply do not mention data governance, metrics,
   versioning or oversight. Our Layer 2 ablations model degradation as *removed*, *hollow*, or
   *distractor* — always within a document that otherwise covers everything. A real document where
   two-thirds of the Annex IV elements were never in scope is a shape we do not generate. (Layer 2
   inputs are technical files, not marketing pages, so this matters less there — but it is worth
   knowing before writing Layer 1 held-out cases.)

5. **Claims arrive bundled with outcomes.** Capabilities are stated next to benefit claims and
   customer statistics, so the legally decisive words sit in a sentence mostly about something
   else. Our synthetic prose separates function from benefit far more cleanly.

## What running them showed (2026-07-22, `claude-haiku-4-5`, ~$0.05, `scripts/run_smoke.py`)

Not scored — there is no ground truth here. Observed behaviour only.

| document | author's reading | classifier | |
|---|---|---|---|
| screening-and-ranking | high_risk | **high_risk** (high conf.) | agrees |
| video-interview-analysis | prohibited | **prohibited** (high conf.) | agrees, cites the guidance |
| interview-coordination | minimal | **not_high_risk** (high conf.) | diverges — see below |

**Neither predicted distractor fired.** The human-oversight reassurance did not drag the screening
tool below high-risk — the model quoted the fit-score/ranking language and answered the profiling
node `true`. The scheduler's cross-sell line did not drag it up to high-risk either. Both traps are
real in the prose; neither defeated the classifier. That is the smoke check passing.

**The divergence is the interesting result, and it is not obviously an error.** Our synthetic
`interview_scheduler` case expects `minimal` — scheduling falls outside Annex III 4 entirely. On the
real text the model instead found the use *within* Annex III 4 (recruitment) and then applied the
Art. 6(3)(a) narrow-procedural-task derogation, reaching `not_high_risk`. Both readings are
defensible: Annex III 4(a)'s "in particular" list is non-exhaustive, so a tool used *for* recruitment
arguably falls in scope and is then carved out. **The two paths are not equivalent in consequence** —
`not_high_risk` via derogation triggers the Art. 6(4) assessment-documentation and registration duty,
which `minimal` does not, and the model's own reasoning said so. This is a ground-truth question our
Layer 1 answer key currently decides one way without argument, and it deserves one.

**Art. 50 came back `true` on all three**, which is what led to discovering the axis was never
scored: `ClassificationCase.expected_transparency_obligation` was in the answer key, but
`run_golden()` compared **only** `expected_risk_class`. An entire ground-truth field was authored
and never checked. Now fixed — `src/aiact/eval/classification_score.py`.

**With scoring in place the axis read 3/6 — and the misses turned out to be ANSWER-KEY errors, not
model errors.** My first read here ("this looks like over-triggering") was too quick: Art. 50(3)
expressly names emotion recognition systems, so `true` on the two emotion cases had direct textual
support while the key's `false` had no recorded argument at all. The key was corrected on
2026-07-22 (see ROADMAP M3) and the axis now reads 6/6.

So this smoke check found a real defect twice over: an axis that was never scored, and then two
wrong labels inside it. Neither was reachable from the golden set, because the golden set was the
thing that was wrong.

**Verdict: the synthetic set is realistic enough to keep tuning against, with two gaps worth
closing.** Points 1 and 3 are cheap to fix and should shape the Layer 1 held-out cases when they are
authored: at least one high-risk case whose text prominently promises human oversight (which does
not change its class), and at least one minimal-risk case carrying high-risk-sounding cross-sell
noise from an adjacent product.
