# Reusable norm-granularity triage

Run from the repository root for an available versioned normative-coverage inventory:

```sh
uv run python scripts/audit_norm_granularity.py --act-version 2026-07-27
```

The command loads and validates the version's generated source partitions and norm inventory,
then prints JSON to standard output. It does not edit files, approve records, or change runtime
rules. Replace the date to audit another available snapshot; regenerate stale artifacts first
with `scripts/build_normative_coverage.py`.

The output includes:

- document, segment and source-character scan totals;
- candidate segment IDs, exact source hashes and linked norm IDs;
- counts/signals for internal enumerations and multiple modal clauses linked to at most one norm;
- every norm with a populated content list, its entry count and source-span IDs.

Use the results to prioritise comparison of the source with the extracted actions, actors,
conditions, exceptions and content. A list may describe one document, alternative conditions,
optional powers or separate actions. The scanner cannot make that distinction for you.

These are heuristics, not a legal-completeness gate. Inline or unnumbered lists, implicit duties,
missing qualifiers and errors within multi-norm segments can be missed; legitimate compound
requirements can be flagged. Successful execution means the scan ran, not that its candidates
are errors or that unflagged norms are correct. Candidate counts will change after corrections.

Reusable scanner tests live in `tests/test_norm_granularity.py`; audit-specific reconciliation
belongs in separate tests so the tool does not depend on one audit's decisions or counts.
