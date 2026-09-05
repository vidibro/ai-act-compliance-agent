# Normative Coverage Migration

**Status:** full-corpus proposed extraction complete; independent assurance and implementation
reconciliation in progress

**Act snapshot:** `2026-07-27`

**Decision date:** 2026-08-28

**Related:** [Development roadmap](ROADMAP.md),
[Phase 0 scope contract](NORMATIVE-COVERAGE-SCOPE.md)

## Why this migration exists

The current coverage machinery proves an important but narrower claim than the product ultimately
needs: every address emitted by `src/aiact/provisions.py` has a disposition. For the pinned Act it
currently partitions the stored text into provisions marked checked by a rule, asked by a graph
node, ruled not owed, declared owed, covered only by a blanket, or unaccounted.

That is **address coverage**, not yet **normative coverage**. One paragraph can contain several
separate duties, actors, conditions, exceptions, deadlines, recipients, and cross-references. A
single rule citing that paragraph can make the address read `checked` while covering only one of
those propositions. Repeated audits found exactly this defect class.

The goal of this migration is a stronger, mechanically testable claim:

> Every independently meaningful legal proposition in the pinned Act has an explicit, reviewed
> disposition, every implemented proposition has a tested path into the application, and every
> part of the enacted text has demonstrably been reviewed.

The existing provision partition remains useful. It becomes the structural layer beneath the new
normative layer rather than being discarded.

## Lessons from the previous audits

### Modal-word searches are candidate generators, not a denominator

Searching for `shall` found dense provisions and real omissions, but the Act also creates legal
effects without that word. Relevant forms include prohibitions, conditional permissions, passive
requirements, responsibilities, exclusive conditions, deadlines, deeming clauses, exceptions,
and duties imported by cross-reference.

Signals such as the following help find candidates but cannot establish completeness:

- `shall`, `shall not`, `must`, `is required to`, `is responsible for`;
- `may only`, `only where`, `provided that`, `subject to`, `unless`;
- `without undue delay`, `at the latest`, `before`, `after`;
- `shall be deemed`, `shall apply`, `shall cease`, `shall ensure`;
- permissions whose cumulative conditions function as mandatory requirements;
- cross-references that import a duty, exception, definition, or procedure from another address.

Candidate discovery therefore combines deterministic signals, grammatical/semantic analysis,
source-only LLM extraction, cross-reference expansion, and independent review. None of those is
the completeness guarantee. The full-text review partition below is.

### Audit completion must be computed, never self-reported

Several audit passes stated that an entire article had been analysed even though later work showed
that only part of its text had reached the auditor. Future review tooling must record the exact
source spans shown and decided. An article is complete only when the union of approved review spans
covers its entire enacted body. A prose claim such as “119/119 articles read” is not evidence.

### Capture-recapture is not a stopping rule

Independent blind audits remain useful for discovery, but capture-recapture does not certify this
corpus. Defects cluster by drafting pattern, auditors have unequal detection probabilities, later
briefs are informed by earlier findings, and fixes change the population between rounds. Overlap is
a signal to keep looking, not an estimate that proves how many defects remain.

### “Covered” must be split into distinct assurance levels

The product must not compress these into one percentage:

1. the legal proposition was identified;
2. its applicability is decided correctly;
3. it is selected for the correct actor and facts;
4. it reaches the user-facing report;
5. it is judged against documentation where that is possible;
6. the judgment behaviour is measured by an evaluation case.

A rule that is listed but not document-verifiable is covered at a different level from one that is
actually judged. A condition disclosed in prose but not resolved is different again.

## Target model

The new system has three connected inventories: enacted-text review segments, normative
propositions, and non-binding interpretive links for guidance that affects behaviour.

### 1. Text review segments

Segments prove what source text was examined. They form a complete partition of every integrity-
checked enacted body, including whitespace and structural text.

Illustrative shape:

```yaml
segment_id: AIA-TEXT-026-005-07
source:
  kind: article
  document: "26"
  division: "5"
  start: 1842
  end: 2077
  sha256: "..."
text: >-
  If the deployer is not able to reach the provider ...
disposition: normative
norm_ids:
  - AIA-NORM-026-005-D
review:
  extracted_by: source-pass-a
  verified_by: reviewer-b
  status: approved
```

The offsets are relative to the verified enacted body for the pinned version. `text` is retained
for human review, but is not an independent copy of the law: the loader must require it to equal
the exact source slice and must verify its hash.

The canonical segment dispositions are fixed by the
[Phase 0 scope contract](NORMATIVE-COVERAGE-SCOPE.md). Broad labels that conceal an unresolved legal
judgment are not acceptable.

### 2. Normative propositions

A norm is one independently meaningful legal proposition. A provision may create several norms,
and one norm may depend on several non-contiguous spans.

Illustrative shape:

```yaml
norm_id: AIA-NORM-050-001-A
type: obligation
subject:
  - provider
action: ensure_direct_interaction_disclosure
primary_spans:
  - AIA-TEXT-050-001-01
qualifier_spans:
  - AIA-TEXT-050-005-01
definition_spans:
  - AIA-TEXT-003-066-01
effective_date_spans:
  - AIA-TEXT-113-B-01
conditions:
  - direct_interaction_with_natural_person
exceptions:
  - obvious_from_context_to_reasonably_well_informed_person
product_disposition: implemented
rule_ids:
  - AIA-TR-A50-1
verification_mode: document_verifiable
review:
  status: approved
```

Norm types must cover more than positive operator duties:

- obligation;
- prohibition;
- applicability condition;
- exception or relief;
- deadline or transitional rule;
- mandatory content;
- role allocation or reallocation;
- definition or dependency;
- right or permission;
- enforcement-triggered duty;
- institutional duty outside the supported product scope.

The full Act is inventoried even where the product does not report for the addressee. Product scope
is a disposition on a discovered norm, not a reason to omit the norm from the denominator.

The canonical norm, product-scope, implementation, verification, review, and dependency
vocabularies are fixed by the [Phase 0 scope contract](NORMATIVE-COVERAGE-SCOPE.md).

### 3. Interpretive links

The separately stored, non-binding Commission guidance is not a source of enacted norms, but it is
a third assurance inventory wherever it affects behaviour. Every guidance-derived classification,
rule interpretation, or expected label links a verified snippet to the enacted norm it interprets,
declares whether the interpretation expands, narrows, clarifies, or defines evidence, and states
how much of the source PDF was actually reviewed. The canonical `InterpretiveEffect` and
`GuidanceReviewScope` vocabularies are fixed in the Phase 0 scope contract.

## Required invariants

The migration is complete only when CI enforces all of the following.

### Source and review integrity

- Every stored article and annex contributes a verified enacted body.
- Review segments cover every source character without gaps.
- Every stored segment text equals its source slice and matches its hash.
- Overlaps are either forbidden or explicitly typed; accidental overlap fails validation.
- Every segment has a review status and reviewer provenance.
- `needs_review` remains visible debt and cannot count as complete.
- Every guidance document and snippet used by the application passes the existing PDF/snippet hash
  and omission checks.
- Guidance review scope is recorded without presenting a bounded passage review as full-document
  coverage.

### Norm integrity

- Every normative segment links to at least one norm.
- Every norm links to at least one primary source span.
- Qualifiers, exceptions, definitions, cross-references, and timing sources are explicit spans.
- Every norm has a subject, legal type, product disposition, and pinned Act version.
- Every in-scope norm maps to a rule, graph question, report-only obligation, or declared missing
  implementation.
- Every `outside scope`, `institutional`, `right`, and `duplicate` disposition carries a reviewed
  reason rather than a bare label.

### Implementation integrity

- Every `PolicyRule` links back to one or more norm IDs.
- Every classification or role question links back to the norm IDs it decides.
- A rule's roles and activation gates cannot be narrower than the mapped norm without an explicit
  legal basis.
- Every implemented norm has a positive reachability witness.
- Every gate has an adjacent negative or boundary witness.
- Every applicable norm is visible in the final report as a finding, an outstanding confirmation,
  a postponed obligation, a conditional obligation, or an explicit scope note.
- Every document-verifiable norm has behavioural evaluation coverage or declared evaluation debt.
- Every guidance reference used by a question, rule, or golden label maps through an approved
  interpretive link to the enacted norm it affects and the implementation target that consumes it.
- A guidance-derived claim without a verified snippet, declared effect, and review scope fails the
  assurance gate.

## Extraction and review workflow

### Source-first extraction

The extractor sees only the pinned enacted text and the extraction schema. It does not see
`spec.yaml`, the existing scope ledger, graph questions, tests, audit reports, or implementation
comments. This avoids fitting the legal inventory to what the application already believes.

Use several independent candidate channels:

1. deterministic modality and deadline signals;
2. grammatical actor/action/object analysis;
3. cross-reference and definition expansion;
4. a structured, source-only LLM extraction pass;
5. a second blind pass with a materially different prompt or model.

Every candidate records the exact text it was derived from. Disagreement is routed to review; it is
not silently resolved by majority vote.

### Independent implementation inventory

Separately inventory the existing rules, questions, route predicates, role predicates, dates,
exceptions, report paths, and judgment modes. Reconcile that inventory against the source-first
norms only after both exist.

### Adjudication

For each norm, an independent reviewer verifies:

- the exact enacted span;
- legal type and duty-holder;
- action and mandatory content;
- conditions, exceptions, timing, and recipient;
- imported meaning from definitions and cross-references;
- product disposition;
- correctness of any mapped implementation.

Agents can perform extraction and adversarial review. A final dismissal of a plausible operator
duty should receive human legal review before it counts as approved.

## Strangler migration phases

The runtime remains stable while the assurance layer is introduced. Existing tests are preserved
unless reconciliation proves current behaviour legally wrong.

### Phase 0 — scope contract and vocabulary

- Define whether the product reports for all operators, all current `ActorRole` members, or another
  explicit subset.
- Inventory every addressee in the Act even where it is outside the product scope.
- Finalise the segment dispositions, norm types, product dispositions, and review states.
- Define what counts as ignorable source whitespace and how headings are treated.

**Exit:** a written scope contract and stable schema vocabulary.

**Completed 2026-08-28:** [`NORMATIVE-COVERAGE-SCOPE.md`](NORMATIVE-COVERAGE-SCOPE.md) fixes the
corpus and product denominators, exact full-text review semantics, atomicity rules, assurance
metrics, and the canonical Phase 0 vocabulary. Phase 1 must implement that contract without
changing runtime behaviour.

### Phase 1 — schema, resolver, and shadow loader

- Add segment and norm Pydantic schemas.
- Add interpretive-link and guidance-review-scope schemas without changing the existing guidance
  resolver or its non-binding source type.
- Add exact-span resolution against the integrity-checked article and annex store.
- Add validators for hashes, offsets, gaps, overlaps, references, and versions.
- Load the new artifacts in tests only; do not change classification, selection, judging, or
  reporting.

Likely additions:

- `src/aiact/schemas/norm.py`
- `src/aiact/norm_loader.py`
- `src/aiact/text_segments.py`
- `src/aiact/schemas/interpretation.py`
- `data/policy/normative-coverage/2026-07-27/norms/`
- `data/policy/normative-coverage/2026-07-27/text-review/`

The two YAML artifacts may be combined if the pilot shows that review remains practical.

**Exit:** shadow artifacts load and validate without changing a report.

**Completed 2026-08-28:** Phase 1 adds shadow-only Pydantic contracts for exact source segments,
atomic norms, independent review provenance, and non-binding interpretive links. The loader resolves
every included article or annex against its integrity-checked, version-pinned source body and
rejects gaps, overlaps, truncation, altered text or hashes, duplicate YAML keys and IDs, broken
cross-references, carried-norm cycles, and guidance-linked dependencies without reviewed guidance.
Empty versioned artifacts establish the migration boundary without entering classification,
selection, judging, or reporting. The representative-provision pilot is now the next phase.

### Phase 2 — representative pilot

Pilot on provisions selected for different failure modes:

- Art. 11(1)
- Art. 26(5)
- Art. 43(3)
- Art. 50
- Art. 60(4)
- Art. 75(1e)
- Art. 113
- Annex IV
- relevant Annex VII and Annex VIII items
- several apparently institutional or non-normative provisions

Measure:

- norms per provision;
- review time per segment and norm;
- disagreements between extraction passes;
- missed candidates by detection channel;
- one-to-one versus many-to-many rule mappings;
- implementation defects discovered;
- usability of offsets and text rendering during review.

**Exit:** corrected schema and a data-backed estimate for full authoring.

**Full-corpus proposed extraction 2026-08-28:** the representative pilot was expanded, in source
order, into a complete proposed inventory. It now partitions all 133 source bodies in the pinned
corpus into 1,505 exact segments. It now proposes 1,487 norms across 132 documents; Article 1 supplies
reviewed subject-matter context without an atomic norm. No article or annex remains as `needs_review`
debt, and structural headings remain separately identified.
The reproducible measurements are in the versioned
[`report.md`](../data/policy/normative-coverage/2026-07-27/report.md). The extraction added loader-validated exact
`norm_text`, candidate-detection provenance, and review timing fields. Its semantic pass found 572 of
1,487 proposed propositions whose exact operative quote contains no `shall` token. No source characters
remain marked `needs_review`.

Of the 1,505 segments, 1,501 are approved and four remain `proposed`: Annex VIII. The
Article 5 heading, all Article 50 and Article 113 segments, and the 27 finer-grained Annex IV
segments were independently confirmed on
2026-09-02. Their linked norm records, like all 1,487 extracted
norms, remain `proposed`; approving a source segment does not independently approve the legal
propositions extracted from it. Elapsed review time was not captured. The remaining assurance
boundary is independent approval of the proposed segments and norms, followed by implementation
reconciliation. The original pilot exit criterion did not produce a measured full-authoring estimate
because the work proceeded directly into full-corpus extraction.

#### Versioned authoring and reproducible compilation

Reviewed legal judgments are versioned inputs rather than Python declarations:

- `data/policy/normative-coverage/2026-07-27/segments/` records reviewed document divisions and
  the provenance of the extraction run;
- `data/policy/normative-coverage/2026-07-27/source-records/` records exact norm quotations,
  subjects, dispositions, mappings, dependencies, carrier relationships, and interpretive links.
- Generated `text-review/`, `norms/`, and `report.md` live beside those inputs, making the
  directory a self-contained assurance package for the Act snapshot.

Each YAML directory has a small `manifest.yaml` plus `articles/` and `annexes/` shards. The loader
merges them into the same validated inventories exposed before sharding, while an individual legal
review now rewrites only its own authored and generated document files.

`src/aiact/norm_builder.py` contains the reusable compiler. It discovers the complete article and
annex denominator for the input version, partitions exact source bodies, computes offsets and
hashes, compiles source records into validated norms, checks implementation references, and renders
the coverage report. `scripts/build_normative_coverage.py --act-version <YYYY-MM-DD>` is the single
entry point for every snapshot.

A later Act snapshot receives a new directory under `data/policy/normative-coverage/`; it does not
modify the reviewed inputs for `2026-07-27`. The generic builder contains no article numbers,
paragraph markers, norm findings, carrier relationships, or guidance interpretations.

### Phase 3 — extraction and review tooling

Likely scripts:

- `scripts/extract_norm_candidates.py`
- `scripts/review_text_segments.py`
- `scripts/check_norm_coverage.py`
- `scripts/render_norm_matrix.py`
- `scripts/diff_versions.py`

The review interface must present bounded source text with surrounding context and record what was
actually shown. Completion comes from approved span coverage, never from auditor self-report.

**Exit:** repeatable source-first extraction and review workflow.

**Implemented through 2026-08-31:** versioned candidate runs enumerate every paragraph-sized segment
and source character even when multi-channel heuristics find no candidate. Candidate records are
revalidated against the exact source inventory. Reviewed judgments are stored in sharded authored
inputs and compiled into the generated text-review, norm, and report artifacts. A dedicated review
interface, review-matrix rendering, and cross-version diff tooling remain optional workflow debt;
they do not block adjudication through the current source-order workflow.

### Current checkpoint — independent assurance and implementation reconciliation

The extraction result is an auditable draft, not a claim that every legal proposition is finally
approved or executable. Work now proceeds in this order:

1. independently decide the four proposed source segments and resolve the four `unresolved`
   implementation modes;
2. independently audit proposed norms, prioritising prohibitions, applicability, supported-actor
   obligations, exceptions, deadlines, and cross-document dependencies;
3. reconcile every in-scope norm with existing rules, classification questions, gap questions,
   shared predicates, report-only behavior, or an explicit carrier norm;
4. group compatible norms by actor, action, trigger, lifecycle, and evidence requirement rather
   than creating one `PolicyRule` per norm;
5. implement genuine gaps in shadow mode, then require reachability and report-surfacing evidence.

Current implementation baseline: 625 norms are `in_scope`; 239 have no direct existing
implementation reference. Of those, 17 are intentionally `carried_by_other_norm`, while 218 are
`missing` and four are `unresolved`. The resulting 222 implementation-debt records are mapping and
design candidates, not a forecast of 222 new rules.

**Granularity audit checkpoint 2026-09-02:** Annex IV items 1 and 2 were split into lettered
subitems, its carried technical-documentation norm was expanded from nine headings to 26 concrete
content requirements, and the user confirmed its source review in commit `0951522`.
A reproducible read-only scan now visits all 133 documents / 1,471 segments and flags 88 candidates.
Full source-to-norm comparison of those candidates recommends 46 splits, eight expansions and 34
retentions; four additional qualifier defects were identified outside the detector. The
[source-ordered audit ledger](NORMATIVE-COVERAGE-GRANULARITY-AUDIT.md) records each decision and the
remaining work. Problems include combined duty-holders, powers summarised as duties, missing
qualifiers, and conditional checklist fields treated as universally mandatory. These findings
initially left the 1,347 proposed norms and implementation-debt counts unchanged. A second pass
compared all 146 populated content lists: the [content audit register](NORMATIVE-COVERAGE-CONTENT-AUDIT.md)
adds 19 split proposals and 12 expansions at norm level, with 38 references to existing decisions
and 77 records without additional focused findings. Do not add these norm-level counts to the
segment counts as if they measured the same thing.

**First correction batch:** Articles 3 and 6 now preserve explicit nested AND/OR conditions;
Article 31's five recorded compound segments were decomposed, increasing its norms from 13 to 19
and the corpus from 1,347 to 1,353. Existing IDs retain a narrowed original duty; six new IDs cover
the separated duties. All remain proposed. The live detector now flags 83 segments; the historical
88-row ledger is preserved. No new user approval or runtime integration is claimed. The remaining
216 implementation-debt records are unchanged. Articles 40, 41 and 43 have also been corrected:
illustrative resource reductions no longer form a third deliverable, common-specification conditions
preserve explicit AND/OR structure, and Annex III point 1 scope and the special-authority route are
explicit. Article 45 now separates event notifications from requested disclosures in paragraphs 1–3,
with explicit alternative event triggers and preserved recipient limits. Its norms increased from
four to seven, taking the corpus to 1,356; all remain proposed. No runtime changes or new user approvals
were made. Article 46 now separates immediate stopping from immediate discarding of all results and
outputs following urgent-use authorisation refusal. It has fourteen norms instead of thirteen,
taking the corpus to 1,357 proposed norms with unchanged implementation debt. Article 50's two
qualifier gaps are also corrected: the objective person/context test and all three considerations
for the qualities of technical marking solutions are explicit. Article 50 still has eleven norms;
no new runtime behavior or independent legal approval is claimed.

Article 57's nine flagged segments and the requested-proof/exit-report finding are corrected,
along with nearby compound effects involving EDPS references, evidence consideration and optional
joint-sandbox support. Its 22 norms became 50, bringing the corpus to 1,385. The extraction separates
powers/permissions from duties, preserves actor-specific reporting and distinct no-fine conditions,
and links P006 as a normative limitation preserving Member State competence. Twelve focused
semantic regressions cover these corrections. All norms remain proposed; the P006 disposition
change is a codex correction, not user verification. Implementation debt remains 216, with 233
in-scope semantic norms lacking existing implementation coverage. At that checkpoint the detector
had 74 candidates and the inventory had 143 populated content lists; historical audit tables are retained.

Article 58 now separates agreement of testing safeguards with participants from cooperation with
other national competent authorities, retaining the shared testing context and cooperation's
additional where-appropriate condition. Its five norms became six, taking the corpus to 1,386;
all remain proposed, with source review provenance and implementation debt unchanged. Focused
regressions preserve actors, recipients, triggers, content and source links. The live detector now
has 73 candidates; at this checkpoint the inventory had 143 populated content lists.

Article 59's public-interest criterion now preserves the shared purpose/development-actor premise
AND one or more of five full enacted areas. Public-health examples and environmental details are
retained inside their respective areas, not flattened into cumulative duties. These alternatives
are stored as conditions rather than mandatory content. Article 59 retains 13 proposed norms and
the corpus total remains 1,386; source approvals, the 73 detector candidates and implementation
debt are unchanged. There are now 142 populated content lists. Regressions check the grouped logic,
exact source details and the parent permission's continued linkage to all ten lettered conditions.
This is not independent norm approval or executable implementation of those conditions.

Article 60 now separates the Member State duty to confer real-world testing supervision powers from
the authorities' duty to use them, and splits paragraph 7 into Article 73 incident reporting,
immediate mitigation, the conditional suspension-or-termination duty and the prompt-recall
procedure. Point 4(h) separates informing participating deployers from the jointly concluded roles
agreement, and 4(i) separates Article 61 consent from the law-enforcement substitute's
no-negative-effect and deletion duties, which both require that seeking consent would prevent
testing. Point 4(c)'s registration routes are mutually exclusive alternatives with their exact
Annex III scopes rather than three cumulative checks, and its previously truncated quote now covers
the whole point. Its 24 norms became 32, taking the corpus to 1,394; all remain proposed and no
source approval changed. Implementation debt rises from 216 to 221 records and in-scope norms
without existing coverage from 233 to 238, because five separated provider duties were previously
hidden inside two checklists. The live detector now has 71 candidates and the inventory has 139
populated content lists.

Article 60a now separates the operator duty to comply with the Section B harmonisation provisions from the limitation preventing those requirements from obstructing Article 60a testing, and separates the unconditional close-cooperation duty from removing practical obstacles where necessary. Its nine norms became eleven, taking the corpus to 1,396. Both separated effects sit outside the supported reporting surface, so implementation debt stays at 221 and populated content lists at 139; the live detector has 70 candidates.

Article 61 now separates dating and documenting the informed consent from giving a copy to the
subjects of testing or their legal representative, and restores the full enacted detail of the
five information items, including withdrawal at any time without detriment or justification and
the concise, clear, relevant and understandable information quality. Its two norms became three,
taking the corpus to 1,397; implementation debt rises to 222 because the separated copy duty has
no existing rule. The live detector has 69 candidates and 139 populated content lists remain.

Article 62's two chapeau duties are now decomposed into their lettered actions, including the
non-preclusion rule protecting other eligible SMEs and the where-appropriate establishment of
new advice channels. Its three norms became thirteen, taking the corpus to 1,407, and the two
chapeau content lists are gone, leaving 137. Every Article 62 addressee is outside the supported
reporting surface, so implementation debt stays at 222 and the detector at 69 candidates.

Article 65 now separates the AI Office's secretariat, meeting-convening and agenda duties, with
the Chair's request triggering only the convening. Its fourteen norms became sixteen, taking the
corpus to 1,409 and leaving 136 populated content lists; implementation debt and the 69 detector
candidates are unchanged.

Article 66 now distinguishes the Board's duty to advise and assist from the non-exhaustive list
of tasks it may in particular perform, with a power norm per lettered task. Point (e) states one
non-exhaustive scope covering every enacted topic instead of seven mandatory contents. Its two
norms became seventeen, taking the corpus to 1,424 and leaving 135 populated content lists.
Every Article 66 addressee is outside the supported reporting surface, so implementation debt
stays at 222 and the detector at 69 candidates.

Article 67 now separates the advisory forum's rules of procedure, co-chair election and co-chair
term, its two required annual meetings from the optional invitation of experts, and the annual
report from its publication. Its ten norms became fourteen, taking the corpus to 1,428 and
leaving 132 populated content lists. The detector drops to 67 candidates; implementation debt
stays at 222 because every addressee is outside the supported reporting surface.

Article 68 now maps the scientific panel's supported tasks and its experts' protections to
individual norms, preserving the request trigger for market surveillance support, the
Article 74(11) without-prejudice limit, the Article 90 alert qualification and the separate
AI Office conflict-management duty. Its eight norms became nineteen, taking the corpus to 1,439
and leaving 129 populated content lists; implementation debt and the 67 detector candidates are
unchanged.

Article 70 now separates the Member State designation duty from the authorities' independence,
their members' conduct prohibition and the conditional permission to consolidate tasks; its
disclosure stages by deadline and recipient; and its resourcing duty from the authorities'
permanent expert staffing and the annual reassessment. Its eleven norms became eighteen, taking
the corpus to 1,446 with 130 populated content lists. The detector drops to 65 candidates and
implementation debt stays at 222.

Article 71 now separates database set-up from the expert and Board consultations, the Article 49
public-access duty and its two excluded sections from the Article 60 restriction and its
provider-consent exception, and controllership from operator support. The enacted "should" for
navigable machine-readable information is kept as a non-duty consequence. Its eight norms became
thirteen, taking the corpus to 1,451 with 129 populated content lists; the detector drops to 63
candidates and implementation debt stays at 222.

Article 72's retain decision needed no change. Article 73 now separates the without-delay
investigation from the corrective action it must lead to, the cooperation duty from the typed
prohibition on evidence-affecting alteration, and the seven-day Article 19 measures from the
Regulation (EU) 2019/1020 notification procedures. Its thirteen norms became sixteen, taking the
corpus to 1,454; the two new provider duties map to the existing Article 73 report-only
obligation, so implementation debt stays at 222 with 129 populated content lists and 60 detector
candidates.

Article 74 now separates the competition-information and prohibited-practice annual reports, the
Member State designation duty from the prohibition on surveillance affecting judicial
independence, and the joint-activity power from the AI Office's coordination-support duty. Its
fourteen norms became seventeen, taking the corpus to 1,457 with 130 populated content lists;
the detector drops to 57 candidates and implementation debt stays at 222.

Article 75 now separates cooperation with the AI Office from informing the Board and the other
market surveillance authorities, and the four-month initial reply from the conditional updates
on proceedings. Its competence norm enumerates the four point (a) exclusions explicitly, and the
assessment request records that it must be duly reasoned. Its twenty-five norms became
twenty-seven, taking the corpus to 1,459 with 131 populated content lists; the detector drops to
55 candidates and implementation debt stays at 222.

Article 75a now separates the fields every information request must state from the
simple-request and decision-request additions and from sending a copy to the operator's
territorial market surveillance authority. Its twenty-one norms became twenty-four, taking the
corpus to 1,462 with 133 populated content lists; the detector and implementation debt are
unchanged.

Article 75c's periodic-penalty rule now separates the unconditional effectiveness and
proportionality requirement from the where-applicable 5 % ceiling, which states its
income or worldwide-turnover basis, reference year, per-day rate and decision-appointed start
date. Its eighteen norms became nineteen, taking the corpus to 1,463 with 134 populated content
lists; the detector drops to 54 candidates and implementation debt stays at 222.

Article 76's retain decision needed no change. Article 77 now separates identifying and
publishing the fundamental-rights authority list by 2 November 2024 from notifying it to the
Commission and the other Member States and from keeping it up to date. Its seven norms became
nine, taking the corpus to 1,465; content lists stay at 134, the detector drops to 53 candidates
and implementation debt stays at 222.

Article 78 now separates the consultation requirement before disclosing confidentially
exchanged information from the prohibition on exchanging sensitive operational data, and the
premises, request-triggered access and security-clearance rules from one another. Its
confidentiality duty enumerates the five protected interests and records the Article 5 of
Directive (EU) 2016/943 exception against point (a) as an external dependency. Its eight norms
became eleven, taking the corpus to 1,468 with 133 populated content lists; the detector drops
to 51 candidates and implementation debt stays at 222.

Article 79 now separates taking the provisional measures from notifying them, enumerates the
nine notification content entries including the four non-compliance grounds, and distinguishes
deemed justification, the preserved Article 18 procedural rights and the 30-day Article 5
period. Its fourteen norms became seventeen, taking the corpus to 1,471 with 133 populated
content lists; the detector drops to 49 candidates and implementation debt stays at 222.

Article 82 now separates the immediate communication of the Commission's decision to the
concerned Member States and operators from informing the other Member States, which the source
does not place under the same immediacy requirement. Its six norms became seven, taking the
corpus to 1,472; content lists stay at 133, the detector drops to 48 candidates and
implementation debt stays at 222.

Article 85 now separates taking complaints into account when conducting market surveillance
from handling them under the authorities' dedicated procedures. Its two norms became three,
taking the corpus to 1,473; content lists stay at 133, the detector drops to 47 candidates and
implementation debt stays at 222.

Article 92's evaluation power now states its two alternative purposes explicitly, keeping the
systemic-risk limit and the Article 90(1), point (a) alert reference inside the second branch
and Board consultation as a shared condition. Its norm count is unchanged, the corpus stays at
1,473 and populated content lists drop to 132; the detector and implementation debt are
unchanged.

Articles 95 to 97 are now corrected. Article 95's five code-of-conduct topics are examples
inside one non-exhaustive scope entry; Article 96 enumerates its seven guideline subjects and
gives point (g)'s 1 August 2027 publication its own norm; and Article 97 separates the
revocation power, the revocation's effect with its actual dates, the preservation of acts
already in force, the two entry-into-force alternatives and the objection-period extension
power. The corpus is 1,477 proposed norms with 132 populated content lists; the detector drops
to 45 candidates and implementation debt stays at 222.

Articles 99 to 101 are now corrected. Article 99 separates the initial penalty-rule notification
from later amendments and states the operator fine's listed provisions, ceiling, reference year
and Article 5 exclusion; Article 100 separates the hearing, decision grounds, complainant
association, defence safeguard, file-access entitlement, budget allocation and the protection of
the fined body; and Article 101 enumerates the three fine-amount factors. The corpus is 1,482
proposed norms with 133 populated content lists; the detector drops to 41 candidates and
implementation debt stays at 222.

Annex VII and Annex VIII complete the recorded queue. The quality-management application asks
for the provider's own identity and the representative's only where the representative lodges
it; both assessment decisions may be notified to the provider or its authorised representative;
and examining proposed changes is separate from notifying the decision. Annex VIII-A keeps its
13 exact entries while recording the optional URL and the entry-12 non-disclosure requirement,
and Annex VIII-B records its conditional entries. The corpus is 1,483 proposed norms with 133
populated content lists, 41 detector candidates and 222 implementation-debt records.
All recorded article and annex findings in both ledgers are now applied. What remains is the
unflagged-source semantic review, independent approval of the four proposed Annex VIII segments
and of every proposed norm, and the four unresolved implementation modes.

An unflagged-source sweep for norms whose exact quote spans several `shall` sentences found
Article 72(3), where basing the monitoring system on a plan is now separate from placing that
plan in the Annex IV technical documentation, and Article 81(1), where notifying the concerned
market surveillance authority is now separate from informing all the others. The corpus is 1,485
proposed norms. That sweep is one defect shape, not a completed semantic review.

Annex XI Section 2's three numbered items are now three norms rather than one norm with four
content entries: item 1 is owed unconditionally and keeps its alternative public-protocol or
other-methodology bases, while items 2 and 3 each carry their own where-applicable gate. All
three remain carried by the Article 53(1)(a) Annex XI content norm, so implementation debt stays
at 222 while in-scope norms without a direct implementation reference rise to 241. The corpus is
1,487 proposed norms with 134 populated content lists. Section 2 is still one source segment;
that packed line is now split at source instead.

**Formex rendering fix, 2026-09-04.** `_split` treated a `<GR.SEQ>` holding bare `<NP>` points
as inline, so Annex XI Section 2, Annex I's two legislation lists and comparable blocks in
Annexes VII, VIII, X and XIV collapsed onto one line each, with every label glued to its text
(`1.A detailed description…`). The converter now renders numbered points as blocks, gives a
grouped sequence's title its own line, and indents a category whose whole body is running text.
The store was re-derived from the pinned 2026-07-27 manifestation: all 119 articles came back
byte-identical, six annexes changed, and every one of them is identical to its predecessor once
whitespace is removed — no enacted word was added, lost or altered.

The corpus therefore partitions into 1,505 segments rather than 1,471, and each listed
instrument, numbered point and section heading is now its own reviewable span. Annex I's 21
instruments moved off two shared spans onto one each, qualified by the Section A or Section B
heading they are listed under; Annex XI Section 2's three norms took the three item spans the
granularity ledger had asked for. Norm, content-list, detector-candidate and implementation-debt
totals are otherwise unchanged at 1,487 / 134 / 43 / 222. The 34 new segments inherit their
document's `codex` provenance and `approved` status: the text behind them was already approved,
but the cut points are new and have had no independent review. Articles 47–49 and 51–56 have no open recorded finding in
these ledgers.

Correct the recorded defects and complete the unflagged-source semantic audit before declaring
extraction complete or compiling new runtime rules. A full-corpus heuristic scan is not a full
semantic audit; neither modal counts nor exact source-span retention proves that each legal effect
is represented. Norm splitting must follow independent applicability/action/actor/verification,
not merely produce one norm per verb or checklist item.

### Phase 4 — link the current implementation in shadow mode

- Add optional `norm_ids` to `PolicyRule`.
- Add norm links to classification questions and gap-role questions, either directly or through a
  mapping artifact.
- Backfill all existing rules and nodes.
- Backfill interpretive links for every existing `guidance_ref` consumed by rules, questions, and
  golden labels.
- Validate citations, roles, routes, areas, conditions, qualifiers, and dates against mapped norms.
- Continue using the current runtime selection logic.

**Exit:** every existing rule and question maps to reviewed norms or carries explicit migration
debt.

### Phase 5 — full-Act text segmentation and norm inventory

- Partition every stored article and annex into review spans.
- Run both source-first extraction passes.
- Adjudicate every segment and norm.
- Reconcile the existing `scope-2026-07-27.yaml` entries into the new dispositions.
- Keep the old ledger as a comparison oracle until every entry is linked or retired.

**Exit:** 100% approved text-span coverage and no undisposed norm.

**Extraction status:** complete as a proposed corpus inventory. Exact source partitioning and
disposition authoring cover all 133 documents and all source characters. The exit criterion remains
open because four segments and all 1,487 norm records still require independent assurance. Corrections
found during assurance must be made in `segments/` and `source-records/`, followed by regeneration;
generated `text-review/` and `norms/` files are never hand-edited.

### Phase 6 — normative coverage compiler and CI gate

- Extend or complement `src/aiact/coverage.py` with atom-level coverage.
- Preserve the address-level partition as a structural metric.
- Fail CI on source gaps, unreviewed spans, undisposed norms, missing mappings, invalid references,
  unreachable rules, or missing report paths.
- Report assurance metrics separately rather than as one “100% covered” number.

**Exit:** atom coverage is the authoritative completeness gate.

### Phase 7 — executable witnesses and mutation tests

For every implemented norm require:

- a positive activation scenario;
- an adjacent negative or exception scenario;
- a report-surfacing assertion.

Mutation tests should demonstrate failure when a rule is removed or when its role, route, Annex III
area, prohibited practice, exception, qualifier, deadline, effective date, or report path is
changed.

**Exit:** mapped law is not merely present in data; it is reachable and observable.

### Phase 8 — behavioural evaluation completion

- Add cases for document-verifiable norms not represented in the golden set.
- Keep selection/report tests for norms that cannot be judged from submitted documentation.
- Add cases for newly discovered document-verifiable norms.
- Re-run held-out evaluation only after the inventory and behaviour have stabilised.

At migration start the golden sets exercise 9 of 14 document-verifiable rules. The known missing
set is:

- `AIA-HR-A11-2`
- `AIA-HR-A12-3`
- `AIA-NHR-A06-4`
- `AIA-TR-A50-1`
- `AIA-TR-A50-2`

**Exit:** every document-verifiable norm has behavioural coverage or explicit evaluation debt.

### Phase 9 — retire only what the new system supersedes

- Make `norm_ids` mandatory on rules and questions.
- Reduce or retire duplicated parts of the old scope ledger.
- Preserve provision enumeration and law-integrity checks.
- Update documentation to distinguish address, normative, reachability, report, and judgment
  coverage.

**Exit:** no runtime or assurance claim depends solely on the old address disposition.

## Test impact

### Expected to remain largely intact

- classification graph topology and behaviour;
- gap graph topology;
- retrieval and judging;
- reporting contracts;
- law-integrity checks;
- most rule-selection tests;
- existing golden cases.

### Expected to be extended

- `PolicyRule` and `PolicyRuleset` schemas;
- `policy_loader.py`;
- configuration paths;
- coverage and provision tests;
- selection reachability tests;
- report provenance tests;
- version-refresh workflow.

### Expected to change substantially

- `tests/test_coverage.py`;
- the interpretation and eventual shape of `scope-2026-07-27.yaml`;
- `spec.yaml` through the addition of norm links;
- coverage reporting and its acceptance criteria.

Runtime and golden tests change only where legal reconciliation demonstrates that current behaviour
is wrong. A data-model migration alone is not a reason to rebaseline an expected legal result.

## Assurance metrics

Publish separate measures:

| Measure | Meaning |
|---|---|
| Source-address coverage | Every stored legal address is enumerated |
| Reviewed-text coverage | Every enacted source span has an approved disposition |
| Norm disposition coverage | Every extracted legal proposition has a reviewed disposition |
| In-scope implementation coverage | Every in-scope norm maps to a rule or node |
| Applicability coverage | Conditions and exceptions are executable or explicitly unresolved |
| Reachability coverage | Every implemented norm has a positive activation witness |
| Boundary coverage | Every gate has a negative or exception witness |
| Report-surfacing coverage | Every applicable norm is visible to the reader |
| Judgment coverage | Document-verifiable norms have behavioural evaluation cases |
| Independent-review coverage | Norms and dismissals have separate verification |
| Guidance-use traceability | Every behaviour-affecting interpretation maps to verified guidance |
| Guidance review-scope coverage | Every used snippet states how much source context was reviewed |

No aggregate percentage replaces these measures.

## Rough effort

The original estimates below are retained as planning history. Full-corpus extraction established
an actual inventory of 1,487 proposed norms, so remaining effort is driven by independent legal
assurance, many-to-many implementation mapping, and behavioral proof rather than extraction volume:

| Work | Estimate |
|---|---:|
| Schema, source spans, loader, validation | 3–5 days |
| Extraction and review tooling | 5–8 days |
| Pilot and design correction | 4–6 days |
| Backfill and reconcile existing rules | 5–10 days |
| Full-Act segmentation and norm authoring | 10–25 days |
| Coverage compiler and CI integration | 5–8 days |
| Reachability, mutation, and report tests | 5–10 days |
| Golden-set additions and reruns | 4–8 days |

The original total was roughly **6–10 person-weeks**. It must not be used as a remaining-work
estimate: several infrastructure and authoring stages are complete, while the unexpectedly large
norm inventory makes assurance and mapping more substantial than the original pilot could measure.
A new forecast should be based on measured review and reconciliation throughput from representative
batches of the 1,487 records.

## Immediate next action

Every recorded row in the
[granularity correction and completion queue](NORMATIVE-COVERAGE-GRANULARITY-AUDIT.md#correction-and-completion-queue)
is applied. The remaining work is the unflagged-source semantic pass, which a heuristic sweep cannot
close. Independently review the four proposed source segments in Annex VIII;
exactly retained content still needs optional/conditional field semantics. Apply only confirmed
user provenance to authored `segments/` records and regenerate derived artifacts. Keep codex audit
findings distinct from user approvals. Measure norm-review throughput and resolve the remaining
`unresolved` implementation modes alongside assurance work; do not compile new runtime rules from
known defective norm records.

### Open debt: a shared requirement cites only one provision

Where several provisions state the same requirement, a report should say so — breaching one
Section 2 duty ordinarily breaches Article 8(1) and Article 16(a) with it, and a reader planning
remediation needs every provision they answer to.

The ledger records the overlap: `carried_by_norm_ids` names the carrier for 20 restatements, and
65 of the 91 policy rules are the implementation target of more than one norm, covering 369 norms
in all. `AIA-HR-A09` alone carries norms from Articles 8, 9 and 16.

Nothing surfaces it. `PolicyRule.source` is a single `LegalSource`, so a verdict cites one article,
and the norm layer is not imported by the pipeline at all — this is a runtime change, not a ledger
one. Closing it means giving a rule the provisions it answers to and rendering them together, which
also serves `Report-surfacing coverage` above.

### Open debt: one duty in several provisions has no recorded link

The ledger can say a norm restates another (`carried_by_norm_ids`) or that two norms share a rule
(`implementation_refs`). It cannot say that separate provisions impose one duty when neither holds.

Four provisions require an EU-database registration — Article 6(4), Article 49(2) and Article 71(2)
twice over. None carries another, none has a rule, and they sit in three files. They agree today
only because one reviewer judged them alike; change one and nothing marks the others as drifted.

Whoever closes this decides what the relation is called and whether it is derived from shared
subject and action or authored. Until then, treat any claim that a group of norms is "consistent"
as prose, not as a checked property.
