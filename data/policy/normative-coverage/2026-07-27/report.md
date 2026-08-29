# Normative Coverage Report

**Status:** proposed norm extraction; independently reviewed segments present

**Act version:** 2026-07-27

The inventory contains 133 complete source-body partitions, 1429 exact segments, and 110 proposed atomic norms. Every stored article and annex is present. Proposed
norms have been extracted from 11 documents; the remaining
work is retained explicitly rather than omitted. The inventory is not consumed by classification,
rule selection, judging, or reporting.

## Coverage measurements

- annex IV: 1
- annex VII: 18
- annex VIII: 3
- article 11: 9
- article 113: 8
- article 2: 28
- article 26: 8
- article 43: 12
- article 50: 11
- article 60: 4
- article 75: 8

### Norms per extracted provision

- AIA-TEXT-A002-P002: 1
- AIA-TEXT-A002-P003: 1
- AIA-TEXT-A002-P004: 1
- AIA-TEXT-A002-P005: 1
- AIA-TEXT-A002-P006: 1
- AIA-TEXT-A002-P007: 1
- AIA-TEXT-A002-P008: 1
- AIA-TEXT-A002-P009: 2
- AIA-TEXT-A002-P010: 2
- AIA-TEXT-A002-P011: 1
- AIA-TEXT-A002-P012: 1
- AIA-TEXT-A002-P013: 1
- AIA-TEXT-A002-P014: 1
- AIA-TEXT-A002-P015: 1
- AIA-TEXT-A002-P016: 2
- AIA-TEXT-A002-P017: 3
- AIA-TEXT-A002-P018: 1
- AIA-TEXT-A002-P019: 1
- AIA-TEXT-A002-P020: 2
- AIA-TEXT-A002-P021: 1
- AIA-TEXT-A002-P022: 1
- AIA-TEXT-A002-P025: 1
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
- Documents containing explicit review debt: 127
- Characters displayed by the extraction pass: 51948
- Independently approved characters: 6903
- Characters deliberately left as review debt: 342719
- Normative segments supporting multiple propositions: 20
- Semantic candidates a shall-token pass missed: 33
- Shall-token candidate recall: 70.0%
- In-scope semantic candidates absent from existing implementation: 25
- Detection-channel counts: cross_reference_structure=25, deeming_or_consequence=40, existing_implementation=37, other_modal=9, semantic_legal_effect=110, shall_token=77
- Mapping shapes, by norm: one-to-one=3, many-to-one=26, one-to-many=0, many-to-many=8, unmapped=73
- Implementation debt candidates: 23
- Interpretive links to non-binding guidance: 1
- Review records with measured elapsed time: 0/1540

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

Segment reviews covering 6903 source characters are independently approved. Approval applies to source coverage and segment dispositions; it does not by itself approve linked norm records. Remaining records are proposed findings or explicit `needs_review` debt. This report therefore does not claim legal completeness for the corpus.
