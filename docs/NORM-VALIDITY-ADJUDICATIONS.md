# Deterministic norm-validity adjudication

This mechanism makes repeated model-assisted reviews reproducible. Models may propose or challenge
norms, but they do not determine whether an existing audit finding is closed.

## The complete flow

1. Generate stable, source-bound findings for one article:

   ```sh
   .venv/bin/python scripts/audit_norm_validity.py \
     --act-version 2026-07-27 --article 15
   ```

2. Review each finding and record exactly one decision in the declared document shard under
   `data/policy/normative-coverage/2026-07-27/adjudications/`.

3. If it is not a defect, use `false_positive` or `accepted_with_basis`. Nothing is edited.

4. If it is a real defect, record `decision: fixed` and an exact patch under `fixes/`, then apply it:

   ```sh
   .venv/bin/python scripts/apply_norm_fixes.py \
     --act-version 2026-07-27 \
     --finding-id AIA-VALID-XXXXXXXXXXXXXXXX
   ```

   The command edits the canonical file under `source-records/`, rebuilds generated artifacts,
   refreshes that document's hash-bound audit attestation, and runs the strict build. If
   verification fails, it restores the original canonical file, audit attestation, and generated
   artifacts.

5. Enforce the complete closed decision set at any later time:

   ```sh
   .venv/bin/python scripts/build_normative_coverage.py \
     --act-version 2026-07-27 --check
   ```

The audit derives each `finding_id` from its target, rule, source segment, source hash, and a
canonical hash of the fields that the audit evaluates: norm text, action, qualifier spans,
conditions, exceptions, mandatory content, and dependencies. Relation and reporting metadata are
deliberately excluded: changing the implementation graph must not reopen a legal-content decision.
Changing models does not change the ID when they produce the same audited record. Changing enacted
source or audited legal content does.

## Actor, target, and temporal evidence

Two newer fields are audited by the same flow, but are deliberately migrated in batches:

- `actors[].basis_segment_ids` identifies the exact `AIA-TEXT-…` segment that proves one named
  actor. Each populated segment must contain a declared legal label for that canonical actor role.
  A mismatch produces `actor_basis_does_not_name_actor`.
- `targets[].basis_segment_ids` identifies the exact segment that proves one named target. Each
  populated segment must contain the target's normalised `target_ref`; a mismatch produces
  `target_basis_does_not_name_target`. `target_kind` is a closed application taxonomy and is
  hash-bound with the target assignment rather than inferred from loose keywords.
- `temporal_regime_id` connects a norm to one shared `TemporalRegime`. The regime records its
  application start/end dates, fixed calendar deadline, relative deadline, any timing condition,
  and exact legal-basis segments. A relative deadline records its quantity, unit, and trigger. The
  validator accepts either enacted equivalent: `within 15 calendar days` or `not later than 15
  calendar days`. For example, Article 46(4) is 15 `calendar_day` from receipt of the Article
  46(3) information. Every recorded date, period, and trigger must occur in the legal basis.

Each norm has at most one deadline constraint. When enacted text imposes both urgency and an outer
limit, the source record must split them into two norms which may map to the same rule. The related
permission or primary duty uses a `conditional_on_norms` relation to identify those timing duties.
For example, Article 73(2) has one immediate-report norm and one fifteen-day outer-limit norm;
Article 5(3) separately records the urgent-use permission, the request without undue delay, and the
twenty-four-hour outer limit.

An `upcoming`, `expired`, or conditionally timed norm remains reportable. A deadline is likewise
reportable before and after it passes; timing never removes a norm from the report.

While existing source records have not been migrated, an empty new field is not a finding. Once a
field is populated, its exact value is included in that article's audit attestation. Thus even a
clean assignment (one that produces no finding) makes an old adjudication shard stale until its
attestation is refreshed. An invalid assignment additionally requires a normal, source-bound
adjudication decision. This permits controlled migration without granting a silent bypass.

When an article is fully migrated, declare its completion gate in both its `index.yaml` scope entry
and its matching article shard:

```yaml
required_field_validations:
  - actor_evidence
  - temporal_regime
```

`actor_evidence` makes every listed actor without `basis_segment_ids` a finding.
`target_evidence` makes every listed target without `basis_segment_ids` a finding.
`temporal_regime` makes every norm without `temporal_regime_id` a finding. A norm that states a
calendar or relative deadline must reference a regime carrying the corresponding deadline form.
The strict build enforces the declared gate; it is the explicit point at which an article can no
longer rely on empty staged fields. Do not enable a gate until its source-record changes and their
adjudications are ready together.

## Decisions

- `false_positive` means the deterministic signal does not identify a defect. A nonempty reviewed
  reason is mandatory.
- `accepted_with_basis` means the norm is retained and the decision supplies exact legal-basis
  quotations that the short `norm_text` omitted. Every basis quote must occur exactly in its named
  source segment and carries that segment's hash.
- `fixed` means an exact, reviewed patch changed a canonical authoring file. The decision references
  `fixes/AIA-VALID-….patch.yaml` and stores that patch file's SHA-256 hash.

## Fix patch format

A fix patch is deliberately small and mechanical:

```yaml
schema_version: 1
finding_id: AIA-VALID-XXXXXXXXXXXXXXXX
target_file: source-records/articles/015.yaml
before_sha256: <SHA-256 of the complete file before the fix>
after_sha256: <SHA-256 of the complete file after the fix>
replacements:
  - old: <exact old text>
    new: <exact replacement text>
    expected_occurrences: 1
```

The patch is accepted only if all of these are true:

- the current canonical file has the exact `before_sha256`;
- every old fragment occurs exactly the declared number of times;
- applying the replacements produces the exact `after_sha256`;
- reversing the replacements reconstructs the exact original file;
- the old finding, including the same target/rule combination, is absent after rebuilding;
- every other active finding still has a current adjudication.

This separates two jobs: a person or model may *propose* the old/new text, while the scripts decide
deterministically whether that exact reviewed change was applied and whether it closed the finding.

The strict build fails when an enforced article has a finding without a decision, a non-fix decision
no longer has a finding, a fixed finding remains active, a fix file or target differs from its
recorded hashes, identifying fields disagree, or an exact legal-basis quotation no longer matches
the pinned source.

## Expanding the scope

Article 15 is the pilot. Decisions are sharded by source document: `adjudications/index.yaml`
declares the exact enforced scope and each expected shard, while `adjudications/articles/015.yaml`
holds Article 15's decisions. The loader rejects missing, undeclared, duplicated, wrong-version,
or wrong-document shards.

To add an article, run the scoped audit, decide all of its findings in its own shard, add its scope
and shard declaration to `index.yaml`, and run the strict build. Do not add an article with
undecided findings.
The strict build then also enforces norm-to-rule traceability for that article: each of its
compliance norms must be a `criteria` entry of every rule it names (see
`docs/NORM-TO-RULE-TRACEABILITY.md`).

The mechanism validates reproducibility and source linkage. It does not pretend that a regular
expression can decide a genuinely ambiguous legal interpretation; that decision remains explicit,
reviewed, and stable in the ledger.
