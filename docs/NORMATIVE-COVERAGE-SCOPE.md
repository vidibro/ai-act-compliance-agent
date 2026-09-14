# Normative Coverage Scope Contract

**Status:** accepted; Phase 0 complete

**Act snapshot:** `2026-07-27`

**Parent plan:** [Normative Coverage Migration](NORMATIVE-COVERAGE-MIGRATION.md)

## Purpose

This contract fixes the denominator and vocabulary for the normative-coverage migration before
schemas, extraction tooling, or legal atoms are authored. Later phases may add values only through
an explicit change to this document; they must not silently reinterpret an existing value.

The contract separates three questions that the old coverage ledger sometimes compressed:

1. **What legal propositions exist in the pinned corpus?**
2. **Which of them is this product intended to report?**
3. **At what level does the implementation handle each in-scope proposition?**

No proposition disappears merely because the present product does not report it.

## The assurance claim

When the migration is complete, the repository may claim:

> Every character of the pinned operative corpus has an approved review disposition. Every legal
> proposition found in that corpus has an explicit source-backed norm and product disposition.
> Every in-scope norm has a tested implementation or is declared missing or unresolved.

It may **not** shorten that to “the whole AI Act is covered” without also stating the corpus and
product boundaries below.

## Corpus boundary

### In the legal denominator

The legal denominator is every integrity-checked enacted body stored under:

- `data/policy/articles/2026-07-27/`
- `data/policy/annexes/2026-07-27/`

It includes:

- article and annex headings, recorded as structural text;
- chapeaux, closing text, paragraphs, points, sub-points, tables, and lists;
- duties and prohibitions addressed to any person, body, authority, institution, or Member State;
- rights, permissions, powers, definitions, exceptions, reliefs, transitions, deadlines, penalties,
  role changes, deeming provisions, and other legal consequences;
- propositions that the present product does not implement.

The source body is the exact Unicode text after the generated YAML front matter. It includes the
article or annex heading that some current loaders strip for rule resolution. Segment offsets are
Unicode code-point offsets into that exact body; hashes are calculated over the UTF-8 encoding of
the exact slice.

### Recorded as dependencies, not silently treated as analysed

The corpus contains references whose operative meaning lives elsewhere. A norm must record these
as dependencies when they affect its meaning:

- another provision of this Regulation;
- another Union instrument;
- national law;
- a harmonised standard or common specification;
- Commission guidance;
- a designation, decision, authorisation, or other external legal/factual determination.

An internal dependency can link to another reviewed span or norm. An external dependency receives
an explicit `external` resolution status. Quoting the cross-reference proves only that the pointer
was reviewed; it does not prove that the referenced instrument was analysed.

### Outside the present corpus claim

The following are not part of the denominator unless they are later added as versioned source
stores:

- recitals, because the present store contains the operative articles and annexes only;
- other language versions;
- the full text of referenced Union or national instruments;
- case law and later authoritative interpretations;
- amendments or consolidations after `2026-07-27`;
- whether the stored legal text itself is an authoritative interpretation of contested law.

This limitation does not permit the norm inventory to ignore a cross-reference. It requires the
dependency to be visible and prevents the product from claiming it reviewed text it does not hold.

## Commission guidance boundary

Commission guidance stored under `data/policy/guidance/` is a separate, non-binding interpretive
corpus. It is not part of the enacted-law denominator and must never be counted as a legal norm or
merged into a norm's enacted source spans. It nevertheless affects application behaviour and is
therefore inside the assurance system.

The guidance store has two source levels:

- `<document>/source.pdf` is the authoritative binary for that Communication, verified by the
  `pdf_sha256` recorded in `source.md`;
- `<document>/snippets/*.md` is the hand-verified, citable passage used by the implementation,
  carrying its own body hash, page/paragraph locator, non-binding flag, topic, source URL, and an
  `omits` declaration.

The repository deliberately does not claim a byte-addressable full-text transcription of each PDF.
Consequently, enacted-law character coverage and guidance coverage use different denominators:

- **enacted-law completeness** is an exact partition of the entire stored text;
- **guidance-use completeness** means every interpretive claim that affects behaviour is linked to
  a verified snippet and every such link declares what the guidance changes;
- **guidance-review scope** records whether the full PDF, a section, a page range, or only the cited
  passage and its immediate context was reviewed. A bounded review must never be described as a
  review of the whole guidance document.

Every use of guidance by a classification question, role question, policy rule, golden label, or
other decision surface must carry an `InterpretiveLink` with:

- one or more `snippet_refs`;
- the enacted norm IDs being interpreted;
- the implementation targets that receive the interpretation;
- an `InterpretiveEffect`;
- the review scope in which the snippet was checked;
- an explicit statement that the source is non-binding.

`InterpretiveEffect` has these Phase 0 values:

- `clarifies_term` — supplies the Commission's reading of a word or phrase;
- `narrows_scope` — supports an exception, limitation, or narrower application;
- `expands_scope` — supports application to facts not unambiguously covered by the bare wording;
- `defines_evidence` — explains what implementation or evidence the Commission considers
  sufficient;
- `defines_mechanism` — explains a technical or procedural mechanism required by the provision;
- `resolves_ambiguity` — chooses between plausible readings not captured more specifically above;
- `other` — requires a reviewed explanation;
- `unresolved` — effect not yet approved and always counted as debt.

`GuidanceReviewScope` has these values:

- `full_document` — every PDF page was presented and reviewed;
- `section` — identified sections were reviewed in full;
- `page_range` — an exact inclusive page range was reviewed;
- `passage_with_context` — the cited passage and a declared amount of surrounding context were
  reviewed;
- `snippet_only` — only the stored quote was verified; this is valid provenance but the weakest
  completeness claim;
- `unresolved` — review boundary is unknown and always counted as debt.

The existing snippet `omits` field protects against a quote silently stopping before a qualification
at its locator. It does not prove that another page of the PDF contains no relevant qualification.
That broader limit belongs to `GuidanceReviewScope` and must remain visible.

Guidance can support an interpretation but cannot turn a proposition into enacted law. Reports must
continue to distinguish legal citations from guidance citations and must say when a classification
or finding rests on Commission interpretation.

## Product boundary

### Product purpose

The product classifies an AI system or general-purpose AI model and reports obligations relevant to
the regulated private or public actors responsible for placing, supplying, deploying, or changing
it. It is not a compliance system for Union institutions, Member States, supervisory bodies, or
notified bodies.

### Supported operator roles

The product-facing actor scope is the operator cast defined by Art. 3(8), represented through the
current roles:

- provider;
- product manufacturer;
- deployer;
- authorised representative;
- importer;
- distributor.

`initial_provider` is a product reporting role rather than a separate Art. 3(8) actor. It denotes
the party that placed the system on the market before Art. 25 moved the provider role and that can
retain the cooperation duty under Art. 25(2).

A product manufacturer normally reaches provider duties by becoming the provider under Art. 3(3)
or Art. 25(3). The norm inventory still records `product_manufacturer` where the Act uses that
subject; mapping it to provider behaviour is an implementation decision, not permission to omit
the norm.

### Actors inventoried but outside the current product-facing scope

Every proposition addressed to another actor remains in the legal inventory. Actor categories
outside the current reporting surface include, without claiming this list is exhaustive:

- third-party suppliers and other private parties not acting as an operator;
- affected persons and other natural persons;
- the Commission, AI Office, AI Board, advisory forum, and scientific panel;
- Member States and their public authorities;
- national competent and market-surveillance authorities;
- notifying authorities and notified bodies;
- data-protection and fundamental-rights authorities;
- courts, judicial bodies, and law-enforcement authorising bodies;
- standardisation organisations and other bodies named by the Act.

An obligation on such an actor is `outside_supported_actor`, not `non_normative`, `not_owed`, or
absent. This is particularly important for bilateral provisions: the provider-facing half can be
implemented while the other party's half remains outside the product scope, but both are norms.

### What product scope does not decide

Product scope does not decide that an organisation actually holds a role, that a factual trigger is
met, or that a contested legal interpretation is correct. Those are applicability or review
questions and must remain visible in their own fields.

## Full-text review contract

### Exact partition

For each source body, approved review segments must form an ordered, contiguous partition:

- the first segment starts at offset `0`;
- each segment ends where the next begins;
- the final segment ends at `len(source_body)`;
- there are no gaps or accidental overlaps;
- concatenating the segment texts reproduces the source body exactly.

Whitespace is not ignored by the partition. It travels with the neighbouring segment or is placed
in a structural segment. This makes completeness an exact equality rather than a heuristic about
“meaningful” characters.

### What the reviewer actually saw

Approval requires proof that the reviewer was shown the full segment without hidden truncation.
Review tooling must record:

- segment ID and exact source offsets;
- source version and slice hash;
- reviewer or review-pass identity;
- the presentation mode and whether pagination was required;
- confirmation that every page/chunk of the segment was displayed;
- review decision and timestamp or review-run identifier.

Review records may include elapsed seconds. Missing timing does not invalidate an otherwise honest
proposed record, but it prevents estimation of full-corpus authoring effort. The review interface
must capture timing automatically rather than asking reviewers to reconstruct it after the fact.

The UI may include surrounding context, but context does not count as reviewed unless it belongs to
an independently approved segment. A reviewer cannot approve an article or annex as one opaque
unit merely by asserting that it was read.

### Review segment dispositions

`SegmentDisposition` has exactly these Phase 0 values:

- `normative` — the span creates, changes, qualifies, imports, or explains a legal proposition and
  links to one or more norms;
- `context_only` — enacted prose relevant to interpretation but not independently represented as a
  norm; a reason is required;
- `structural` — heading, numbering, table structure, separator, or whitespace carrying no
  independent proposition;
- `needs_review` — no approved disposition yet; always counts as migration debt.

Definitions, qualifiers, exceptions, and cross-references are normally `normative`; they are not
downgraded to context merely because they do not contain a freestanding duty.

`context_only` and `structural` require human verification. An extractor may propose them but may
not approve them.

### Exact proposition text and detection provenance

A paragraph-level source span may support several independently applicable
norms. Every norm therefore carries `norm_text`: an exact enacted quotation that the loader proves
occurs inside one of the norm's primary spans. The quotation does not replace qualifier, condition,
exception, dependency, or effective-date spans; it prevents a paraphrased `action` from being the
only visible statement of what exact words the norm claims.

Where one legal effect applies only if independently modelled norms are satisfied, the parent records
those IDs in `condition_norm_ids`; generated child norms carry the reciprocal
`condition_of_norm_ids`. This relationship is authored only for an enacted cumulative-condition
structure. Shared articles, qualifiers, or nearby list items are not enough to infer it.

Every proposed norm also records one or more candidate-detection channels. These are extraction
provenance, not legal classifications:

- `semantic_legal_effect`
- `shall_token`
- `other_modal`
- `deeming_or_consequence`
- `cross_reference_structure`
- `existing_implementation`

The `shall_token` channel deliberately preserves the earlier heuristic as a measurable baseline.
It is never sufficient for completeness and does not outrank semantic review.

## Norm vocabulary

### Norm kind

`NormKind` records the primary legal effect and has these values:

- `obligation` — a subject is required to act, maintain a state, provide something, or ensure an
  outcome;
- `prohibition` — a subject or practice is forbidden or restricted from acting;
- `permission` — the law permits conduct, commonly subject to conditions;
- `entitlement` — a person or body is granted a right, claim, access, request, or procedural
  protection;
- `power` — an authority or body is empowered to decide, request, investigate, authorise, adopt, or
  enforce;
- `applicability` — a scope rule, condition, exception, relief, transition, temporal gate, or
  classification rule changes whether another proposition applies;
- `definition` — a term is given operative meaning used by other norms;
- `legal_consequence` — the law changes a status or role, deems something satisfied, imposes a
  penalty, or produces another automatic result not adequately described by the values above.

Deadlines, recipients, mandatory content, conditions, and exceptions are structured components of
a norm. They do not become separate `NormKind` values solely because they are important. They may
become separate norms when independently actionable or independently applicable.

### Subjects

A norm carries one or more `subject_refs`, each a stable slug taken from the enacted text or a
normalised legal role. Subjects are not restricted to `ActorRole`.

Each subject also carries one `SubjectCategory`:

- `supported_operator`
- `external_private_party`
- `natural_person`
- `union_institution_or_body`
- `member_state`
- `public_authority`
- `notified_or_conformity_body`
- `other`
- `unresolved`

The category supports coverage reporting; it does not replace the precise subject reference.

### Product scope

`ProductScope` answers only whether the present product promises to report the norm:

- `in_scope` — the product is intended to handle it;
- `outside_supported_actor` — the norm binds or serves an actor outside the current reporting
  surface;
- `dependency_only` — it supplies meaning to in-scope norms but has no independent product output;
- `no_product_action` — it is legally real but creates no reportable compliance action for the
  supported actor;
- `unresolved` — scope has not been approved.

Every value except `in_scope` and `unresolved` requires a reviewed reason. `unresolved` always
counts as debt.

### Implementation mode

`ImplementationMode` is independent of product scope and records how an in-scope norm reaches the
application:

- `compliance_rule` — mapped to one or more `PolicyRule` entries;
- `applicability_question` — decided by a classification or role question;
- `report_only` — surfaced for confirmation without being judged;
- `scope_note` — surfaced through an explicit report-level explanation;
- `carried_by_other_norm` — a true restatement or dependency whose product effect is implemented by
  another named norm; the target norm is required;
- `none_required` — approved as requiring no distinct runtime behaviour; a reason is required;
- `missing` — in product scope but not implemented;
- `unresolved` — implementation mapping has not been approved.

`missing` and `unresolved` are visible debt. `carried_by_other_norm` cannot point to itself and
cannot form a cycle.

### Verification mode

`VerificationMode` records the strongest treatment the application performs:

- `judged_by_gap_analysis` — documentation is evaluated and receives a verdict;
- `answered_by_classification` — applicability is answered from the submitted system description;
- `reported_not_judged` — the obligation is shown as owed, with no verdict;
- `reported_conditionally` — shown as conditional, with an unresolved condition about the
  duty-holder or facts;
- `not_reported` — absent from the report, because the norm binds someone the product does not
  report for;
- `unresolved` — verification treatment has not been approved.

This field prevents `reported_not_judged` from being mistaken for a passed check.

Both engines read the one submitted document, so the first two differ in what SILENCE means, not in
where the text comes from. The document is itself the compliance artefact an obligation demands, so
an absent fact is a `gap` finding; an absent fact proves nothing about what a system *is*, so the
cascade abstains rather than deciding a risk class the documentation never supported. Crossing the
two inverts the report: a hidden gap in one direction, a gap reported against an undetermined tier
in the other.

### Review status

`ReviewStatus` has these values:

- `proposed` — produced by extraction or initial authoring;
- `approved` — independently verified against every linked source span;
- `rejected` — candidate reviewed and determined not to be a norm; retained only in extraction
  audit history, not in the final norm inventory;
- `needs_review` — ambiguous, incomplete, or disputed; always migration debt;
- `superseded` — replaced by named norm IDs without deleting audit history.

An extractor and final verifier must be distinguishable review identities. Self-verification does
not count as independent-review coverage.

### Dependency resolution

There is no legacy dependency field. Every relationship is a typed canonical norm relation:
`relies_on_norms`, `subject_to_external_requirements`,
`interpreted_by_commission_guidance`, `national_law_regulation`, `unresolved_dependency`, or
`missing_dependency`. The last two are visible debt and must carry a written explanation.

In particular, `national_law_regulation` is a targetless report boundary: it says the norm must be
aligned with applicable national law, but this project neither selects a country nor assesses that
law.

## Atomicity rules

A norm should be split when any component can vary independently in applicability, duty-holder,
deadline, recipient, required action, exception, product implementation, or verification mode.

A norm should normally remain whole when several clauses are inseparable mandatory content of one
action and always travel together. Mandatory content may be stored as structured elements so that a
single rule cannot silently implement only the first item.

Examples of reasons to split:

- two different actors owe different halves of the same sentence;
- one action has a different deadline from the next;
- a condition activates only one sub-clause;
- refusal triggers stopping use and separately triggers deletion;
- a provision creates both an authority power and an operator cooperation duty;
- one sentence restates another duty while adding a new recipient or procedure.

Examples of reasons not to split automatically:

- repeated adjectives describing one standard;
- a list that is mandatory content of one indivisible document, provided every item is represented
  structurally and tested for completeness;
- explanatory text with no independent legal effect.

Atomicity is adjudicated from legal effect, not punctuation or occurrences of modal words.

Condition groups may explicitly preserve conjunctions and alternatives using `operator: all_of`
or `operator: any_of` with at least two `operands`, each a nonempty text premise or nested group.
For example, a shared risk premise AND any of four qualifying uses remains one applicability norm,
not four cumulative obligations. Legacy prose conditions remain supported without automatically
inferring their logic. These groups record legal structure; they are not executable runtime predicates.

## Completion and assurance accounting

Phase 0 fixes the following separate metrics:

- `source_address_coverage`
- `reviewed_text_coverage`
- `norm_disposition_coverage`
- `in_scope_implementation_coverage`
- `applicability_coverage`
- `reachability_coverage`
- `boundary_coverage`
- `report_surfacing_coverage`
- `judgment_coverage`
- `independent_review_coverage`
- `guidance_use_traceability`
- `guidance_review_scope_coverage`

No aggregate “coverage percentage” replaces them. A metric may be 100% only when its own debt
states are zero.

## Change control

Changing an existing vocabulary value's meaning is a migration, not a documentation edit. It
requires:

1. an explicit update to this contract;
2. migration of every stored record using the old meaning;
3. tests that distinguish the new meaning;
4. a note in the parent migration document.

Adding a source version creates a new `data/policy/normative-coverage/<version>/` authoring
directory and new generated text and norm inventories. It does not mutate the reviewed inputs or
generated artifacts for `2026-07-27`.

## Phase 0 exit decision

Phase 0 is complete because this contract now fixes:

- the operative corpus denominator;
- treatment of external dependencies and absent recitals;
- the separate non-binding guidance denominator and interpretive-link vocabulary;
- the product-facing actor boundary;
- exact full-text review semantics;
- segment, norm, subject, scope, implementation, verification, review, and dependency vocabularies;
- atomicity rules;
- assurance metrics and change control.

Phase 1 may implement these terms as schemas and validators in shadow mode. It must not change
runtime reports.
