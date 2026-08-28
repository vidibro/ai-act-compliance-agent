# Normative Coverage Report

**Status:** proposed extraction; independent legal review not yet performed

**Act version:** 2026-07-27

The inventory contains 133 complete source-body partitions, 204 exact segments, and 82 proposed atomic norms. Every stored article and annex is present. Proposed
norms have been extracted from 10 documents; the remaining
work is retained explicitly rather than omitted. The inventory is not consumed by classification,
rule selection, judging, or reporting.

## Coverage measurements

- annex IV: 1
- annex VII: 18
- annex VIII: 3
- article 11: 9
- article 113: 8
- article 26: 8
- article 43: 12
- article 50: 11
- article 60: 4
- article 75: 8

### Norms per extracted provision

- AIA-TEXT-A011-P1: 8
- AIA-TEXT-A011-P3: 1
- AIA-TEXT-A026-P5: 8
- AIA-TEXT-A043-P3: 10
- AIA-TEXT-A043-P5: 1
- AIA-TEXT-A043-P6: 1
- AIA-TEXT-A050-P1: 1
- AIA-TEXT-A050-P2: 1
- AIA-TEXT-A050-P3: 2
- AIA-TEXT-A050-P4: 2
- AIA-TEXT-A050-P5: 1
- AIA-TEXT-A050-P6: 1
- AIA-TEXT-A050-P7: 3
- AIA-TEXT-A060-P4: 4
- AIA-TEXT-A075-P1: 1
- AIA-TEXT-A075-P1E: 7
- AIA-TEXT-A113-A: 2
- AIA-TEXT-A113-B: 1
- AIA-TEXT-A113-C: 2
- AIA-TEXT-A113-D: 1
- AIA-TEXT-A113-ENTRY: 1
- AIA-TEXT-A113-GENERAL: 1
- AIA-TEXT-ANNEX-IV-CHAPEAU: 1
- AIA-TEXT-ANNEX-VII-I3: 6
- AIA-TEXT-ANNEX-VII-I4: 10
- AIA-TEXT-ANNEX-VII-I5: 2
- AIA-TEXT-ANNEX-VIII-A: 1
- AIA-TEXT-ANNEX-VIII-B: 1
- AIA-TEXT-ANNEX-VIII-C: 1

- Exact source characters partitioned: 394667
- Documents containing explicit review debt: 129
- Characters displayed by the extraction pass: 37582
- Independently approved characters: 0
- Characters deliberately left as review debt: 357085
- Normative segments supporting multiple propositions: 14
- Semantic candidates a shall-token pass missed: 13
- Shall-token candidate recall: 84.1%
- In-scope semantic candidates absent from existing implementation: 7
- Detection-channel counts: cross_reference_structure=9, deeming_or_consequence=17, existing_implementation=37, other_modal=7, semantic_legal_effect=82, shall_token=69
- Mapping shapes, by norm: one-to-one=3, many-to-one=26, one-to-many=0, many-to-many=8, unmapped=45
- Implementation debt candidates: 5
- Interpretive links to non-binding guidance: 1
- Review records with measured elapsed time: 0/287

## Findings

1. `shall` is not an adequate candidate detector. The exact norm quotes show permissions, powers,
   deeming rules, legal consequences, and operative content lists that semantic review found
   without that token.
2. Exact document partitioning prevents an extraction pass from claiming an article was reviewed
   when only a paragraph reached it. Unreviewed divisions remain visible as `needs_review`.
3. Paragraph offsets alone are too coarse for atomic review. `norm_text` now records an exact,
   loader-validated quotation inside a primary span, while conditions and qualifier spans preserve
   surrounding legal effect.
4. Commission guidance remains separate: the Article 50(2) interpretation links three
   integrity-checked snippets to the enacted norm and existing policy rule without treating the
   guidance as binding law.
5. Timing data cannot yet support a full-authoring estimate. Missing elapsed time is recorded
   explicitly and must be captured automatically by the review interface.

## Review boundary

No segment or norm is independently approved. Records are either proposed findings or explicit
`needs_review` debt. Approval still requires a different reviewer identity and proof that the full
exact slice was displayed. This report is therefore evidence about schema fitness and
extraction-method failure modes, not a legal completeness claim.
