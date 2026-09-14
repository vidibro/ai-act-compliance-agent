# Norm-to-rule traceability: implementation handoff

## Goal

Extend the existing deterministic norm-validity mechanism so it also proves that every accepted
norm is implemented as a checkable compliance criterion.

The complete chain must become:

```text
enacted text
  -> structured norm
  -> adjudicated norm-validity finding
  -> obligation criterion -> criterion verdict -> named report result
     OR report-only permission/legal effect -> named report result
```

Changing the model must not change which legal requirements exist, which rule implements them, or
which criteria must be checked. A model may judge evidence for a criterion, but it may not invent,
remove, merge, or silently skip criteria.

## Deterministic rule grouping

A policy rule is a group of norms, not a free-text summary. The loader resolves every listed norm
from the canonical inventory and rejects a group that mixes any of these properties:

1. **Legal kind:** one rule contains one `NormKind`. Obligations/prohibitions are judged rules;
   permissions and legal consequences are never criterion members.
2. **Duty-holder:** all criteria name the same subject set. Different actors get separate rules and
   separate report sections.
3. **Assessment treatment:** all criteria use one verification mode. A rule is either judged or
   reported for separate confirmation; it cannot combine those two answers.

The rule itself owns the remaining shared properties: its activation gate, expected evidence,
effective date and outcome. Norms may share a rule only when that one activation and one evidence
check really apply to all of them. If either differs, make another rule.

`permission` and `legal_consequence` norms with `implementation_mode: report_only` are instead
materialised into `PolicyRuleset.report_norms`. They retain canonical action, conditions,
exceptions, source spans and activating rule ids. The strict build checks this link both ways, and
the report renders them under **permitted implementation routes** or **conditional legal effects**.
They neither pass nor fail an obligation.

For every live norm in the adjudicated enforced scope, this is mandatory: the strict build rejects
a `permission` or `legal_consequence` whose implementation mode is anything other than
`report_only`. It therefore cannot be hidden in a standalone compliance rule.

## What already exists

The current uncommitted work implements this reproducible flow:

```text
audit_norm_validity.py
  -> adjudications/index.yaml + document shard
  -> apply_norm_fixes.py (only for decision: fixed)
  -> build_normative_coverage.py --check
```

See `docs/NORM-VALIDITY-ADJUDICATIONS.md`. Preserve that work. Do not replace it with another
model-based audit.

Article 15 is the enforced pilot. Its current audit has seven adjudicated findings. In particular,
`AIA-NORM-A015-P5-MODEL-FLAWS` is intentionally retained as `accepted_with_basis` because its full
meaning can be reconstructed from:

- target text: `model flaws`;
- structured action: implement measures to prevent, detect, respond to, resolve and control;
- structured condition: measures addressing the AI-specific vulnerability are appropriate;
- recorded Article 15(5) chapeau and Article 16(a) provider basis.

This proves norm validity. Article 15's twelve obligation norms now point to the aggregate policy
rule `AIA-HR-A15` and each gets its own verdict. Its technical-redundancy permission is a canonical
report-only route instead.

## Adopted decision rule

A norm is complete enough to retain when its complete legal effect can be assembled from its
structured fields plus its hash-bound, exact legal basis.

Retaining the norm is only half of the decision. A retained compliance norm is implemented only if
all four checks below pass:

1. **Reconstruction:** subject, action, object, conditions, exceptions and mandatory content can be
   reconstructed from structured norm data plus recorded legal basis.
2. **Traceability:** the norm points to a real policy rule and that rule explicitly points back to
   the norm as a criterion.
3. **Independent checkability:** the criterion receives its own evidence verdict. It cannot pass
   merely because another criterion under the same aggregate rule passed.
4. **Observable failure:** a targeted fixture that satisfies sibling criteria but omits this one
   produces a failing/uncertain criterion result that names the omitted norm in the report.

The deterministic machinery owns the first two checks and the presence/aggregation rules for the
last two. A semantic evidence judge may still be model-based. Its uncertainty must be returned as
`unsure`; determinism must not be claimed for the legal meaning of arbitrary product documents.

## Pilot design for Article 15

Keep `AIA-HR-A15` as the user-facing aggregate rule, but give it explicit subcriteria. Use norm IDs
as the stable criterion IDs. Do not manually duplicate action and condition prose in `spec.yaml` if
they can be materialised from the normative-coverage inventory; duplicated prose creates a second
source of truth.

Conceptually:

```yaml
- rule_id: AIA-HR-A15
  # existing fields remain
  criteria:
    - norm_id: AIA-NORM-A015-P5-DATA-POISONING
    - norm_id: AIA-NORM-A015-P5-MODEL-POISONING
    - norm_id: AIA-NORM-A015-P5-ADVERSARIAL-ATTACKS
    - norm_id: AIA-NORM-A015-P5-CONFIDENTIALITY-ATTACKS
    - norm_id: AIA-NORM-A015-P5-MODEL-FLAWS
    # Include only obligations/prohibitions with the same subject and verification treatment.
```

At load/build time, resolve each `norm_id` to the canonical generated norm and derive its subject,
kind, action, text/object, conditions, exceptions, mandatory content and source spans. Never ask a
model to perform this mapping.

The strict validator must fail for Article 15 when any of these is true:

- a norm says `implementation_refs: [AIA-HR-A15]` but the rule omits that norm from `criteria`;
- the rule names a missing norm;
- the rule names a norm that does not point back to that rule;
- the same norm is listed twice;
- a criterion cannot be reconstructed from canonical structured data and accepted legal basis;
- the judge or report silently drops an applicable criterion;
- the aggregate rule is `pass` while any mandatory criterion is `gap`, `inadequate`, or `unsure`.

Use a conservative aggregate rule:

```text
all criteria pass                  -> aggregate pass
one or more gap/inadequate         -> aggregate failing result
no failure, but one or more unsure -> aggregate unsure
```

Do not let an average, majority, confidence score, or a sibling criterion hide a failed criterion.

## Required Article 15 behavioural fixture

Add one focused fixture for `AIA-NORM-A015-P5-MODEL-FLAWS`:

- it provides credible evidence for the other Article 15 cybersecurity threat controls;
- it says nothing substantive about detecting, preventing, responding to, resolving or controlling
  model flaws;
- expected model-flaws criterion verdict: `gap` or `inadequate`, according to the fixture wording;
- expected aggregate `AIA-HR-A15` verdict: not `pass`;
- the generated report must contain the exact norm ID and a reason identifying model-flaw controls.

Also add a deterministic unit test with a stub criterion judge. Return `pass` for every sibling and
`gap` for model flaws. This test must prove aggregation and report preservation without calling an
LLM. A separate golden/evaluation test may measure a real model, but it must not be the sole
enforcement mechanism.

## Suggested implementation order

1. Read the policy, norm, finding/report, judge and golden-set schemas before editing.
2. Add the smallest backward-compatible criterion schema. Existing rules without criteria must
   continue to load while Article 15 is the pilot, unless a deliberate migration covers them all.
3. Add Article 15 criterion references to `data/policy/spec.yaml`.
4. Extend `build_normative_coverage.py --check` (prefer a reusable module, not logic embedded only
   in the CLI) with the bidirectional norm-to-rule checks.
5. Make evidence judgment operate per criterion for the pilot and implement conservative aggregate
   status.
6. Preserve criterion results in the report. Keep the aggregate rule result for compatibility.
7. Add the model-flaws omission fixture and deterministic stub-judge test.
8. Run focused tests, lint, type checking, the Article 15 audit and the strict coverage check.

Do not begin by rewriting all policy rules. Complete and verify Article 15 first.

## Acceptance criteria

The work is complete only when all of these statements are demonstrated by automated tests:

- Every Article 15 norm implemented by `AIA-HR-A15` has exactly one explicit criterion.
- Every Article 15 criterion resolves to exactly one canonical norm that points back to the rule.
- `AIA-NORM-A015-P5-MODEL-FLAWS` is materialised with the full mitigation action and its condition,
  despite its two-word source slice.
- Deleting its criterion makes `build_normative_coverage.py --check` fail.
- A stub judge returning a model-flaws gap cannot yield aggregate `pass`.
- The report names `AIA-NORM-A015-P5-MODEL-FLAWS` and preserves its verdict/reason.
- The targeted omission fixture cannot pass Article 15 merely because sibling controls are present.
- Existing norm-validity adjudication tests continue to pass.
- No test needs a live model or network call to prove the structural guarantees.

## Verification commands

Use the repository's virtual environment:

```sh
.venv/bin/python scripts/audit_norm_validity.py --act-version 2026-07-27 --article 15
.venv/bin/python scripts/build_normative_coverage.py --act-version 2026-07-27 --check
.venv/bin/pytest tests/test_norm_validity.py tests/test_norm_builder.py tests/test_normative_metrics.py
.venv/bin/pytest tests/test_policy_loader.py tests/test_gap_judge.py tests/test_gap_graph.py tests/test_schemas.py
.venv/bin/pytest tests/test_golden_set.py
```

Run Ruff and mypy using the repository's established commands/configuration on every changed Python
file. Report any pre-existing unrelated failures separately; do not weaken tests to obtain green.

## Pilot implementation (Article 15)

- `data/policy/spec.yaml`: `AIA-HR-A15` lists its 13 Article 15 provider norms under `criteria`,
  as `norm_id` only.
- `src/aiact/policy_loader.py`: resolves each criterion from the generated `norms/` shards into a
  `RuleCriterion` (subjects, kind, action, text, conditions, exceptions, mandatory content, spans,
  verification mode). Any hand-written field, a missing norm, a norm that does not point back, or a
  duplicate fails the load.
- `RuleCriterion.mandatory` is derived: an obligation or prohibition that is
  `judged_by_gap_analysis`. `AIA-NORM-A015-P4-REDUNDANCY` (a permission, reported conditionally) is
  listed and reported as not judged, and cannot fail the rule.
- `src/aiact/norm_traceability.py`: the bidirectional check run by
  `build_normative_coverage.py --check`. Its scope is the validity ledger's `enforced_scope`,
  because a criterion can be reconstructed only from an adjudicated norm.
- `src/aiact/gap/judge.py`: an aggregate rule is judged in one model call that returns one verdict
  per mandatory criterion. The rule verdict is computed in code (`gap/criteria.py`,
  `schemas/report.py:aggregate_criteria`), never read from the model. A criterion the reply omits,
  repeats, or answers unreadably becomes `needs_review`.
- Aggregation: any `gap`/`inadequate` fails the rule — `gap` if no mandatory criterion was
  addressed, otherwise `inadequate`. No failure but any `needs_review` gives `needs_review`. Only all
  `pass` gives `pass`. `Finding` refuses a verdict that disagrees with its criteria, and
  `ComplianceReport` refuses a finding whose criteria differ from the rule's when reloaded through
  `aiact.report_loader.load_compliance_report(path, spec)`. That is the required entry point for a
  persisted JSON report: it supplies the authoritative policy spec as validation context, so a
  report with a silently dropped criterion is rejected.
- The report lists every criterion by norm ID with its own verdict, and the reason for each one
  that did not pass.
- Fixture: `data/golden_set/criteria/AIA-NORM-A015-P5-MODEL-FLAWS__omitted.md`. Tests:
  `tests/test_norm_traceability.py` (no model or network calls).

One live run with `gemini-2.5-flash` returned `gap` for `MODEL-FLAWS` and `inadequate` for
`AIA-HR-A15`; it is an evaluation observation, not a deterministic guarantee. Retrieval per
criterion is still not implemented: retrieval queries by `evidence_expected` facets.

## Typed norm relations

The norm inventory also carries a small relation layer for legal effects that are neither an
independent criterion nor an ordinary textual dependency. It intentionally does **not** model every
cross-reference in the Regulation.

- `allocates_duty_to_policy_rules`: a norm assigns responsibility for existing substantive rule
  checks. Article 16(a) assigns the provider duty for the Section 2 rules; it is not an extra
  criterion on each of those rules.
- `carried_by_policy_rules`: existing substantive policy rules discharge the cross-reference norm.
  Article 16(f)–(i) are the pilot examples.
- `subject_to_external_requirements`: the AI Act creates a duty, but named external instruments supply
  its substantive requirements. Article 16(l) records the accessibility Directives without claiming
  that this project checks those Directives.
- `conditional_on_norms`: a permission or conditional norm applies only when every named norm is
  satisfied. Articles 59(1) and 60(4) are the first migration. This is the only representation of
  those condition links; `Norm` does not carry copied condition-ID fields.
- `relies_on_norms`: one norm relies on another AI Act norm. The target must be a norm ID, never a
  source span.
- `interpreted_by_commission_guidance`: a Commission-guidance snippet supplies a recorded
  interpretation; it does not create a new legal duty.
- `national_law_regulation`: applicable national law affects the norm. It has no country or legal
  instrument target: the generated report must say that alignment is required, while this project
  does not identify or assess national law. Its explicit `report_for_prohibited_practices` activation
  is materialised into the live report from the relation itself; the policy spec cannot hand-write it.
- `unresolved_dependency` and `missing_dependency`: visible extraction debt. Both require a written
  explanation and cannot pretend to have a target.

Every relation has a stable ID, a source norm, exact legal-basis spans, and typed targets. The
builder and loader reject unknown sources, targets, self-conditions, or non-normative legal-basis
spans; policy-rule relation targets must exactly equal the source norm's `implementation_refs`.

Traceability accepts exactly three implementations for an enforced compliance norm: one explicit
criterion; one typed relation; or one unambiguous one-norm/one-rule mapping. Anything else fails the
strict build as an ambiguous missing criterion. Article 16 is now an enforced, zero-finding pilot:
its empty decision shard is intentional and a future structural finding fails the build until it is
explicitly adjudicated.

## Migration path to other Articles

1. Decide the Article's validity findings, add its document shard, and declare it in
   `adjudications/index.yaml` under `enforced_scope`.
   From then on the strict build also requires each of its compliance norms to be a criterion of
   every rule it names, so steps 1 and 2 land together.
2. Add `criteria` to each rule its norms name, then run the strict build.
3. Article 16 is the reference case for cross-references. `AIA-NORM-A016-A-SECTION-2-COMPLIANCE`
   names every Section 2 rule (including `AIA-HR-A15`) as the provider-allocation basis, not as a
   separate duty. It is an allocation relation rather than a criterion of fourteen rules. Its other
   cross-references are either carried by named policy rules or by named substantive norms, which
   must themselves resolve to policy rules.
4. Rules with a single norm need no criteria. Criteria pay off where one rule aggregates several
   separately breachable duties.

## Guardrails for the next model

- Inspect `git status` first. The norm-validity implementation is uncommitted user work.
- Do not discard, reset, or rewrite the current adjudication mechanism.
- Treat `.cache/aiact-2026-07-27.fmx.zip` and its extracted canonical Article source as the pinned
  legal ground truth.
- Do not decide validity from the short `norm_text` alone.
- Do not treat `MODEL-FLAWS` as a risk-classification branch. Classification activates high-risk
  obligations; model flaws is a provider-compliance criterion after activation.
- Do not claim that stable IDs or deterministic validators prove a contested legal interpretation.
  They prove that the same recorded interpretation is applied reproducibly.
- Stop after the Article 15 pilot is fully tested and explain the migration path before expanding
  to every Article.
