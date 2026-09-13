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
   reruns the audit, and runs the strict build. If verification fails, it restores the original
   canonical file and generated artifacts.

5. Enforce the complete closed decision set at any later time:

   ```sh
   .venv/bin/python scripts/build_normative_coverage.py \
     --act-version 2026-07-27 --check
   ```

The audit derives each `finding_id` from its target, rule, source segment, source hash, and a
canonical hash of the audited norm or linked norm quotations. Changing models does not change the
ID when they produce the same record. Changing the enacted source or audited record does.

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
