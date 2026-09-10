# A segment's `norm_ids` claims norms whose words it does not contain

Repository: `ai-act-compliance-agent`. Pinned act version `2026-07-27`.
Written against commit `e0c655a` plus the uncommitted audit-round changes in the working tree.

## Symptom

`AIA-TEXT-A005-P001` is 51 characters:

```
1. The following AI practices shall be prohibited:
```

Its `norm_ids` lists **ten** norms — `AIA-NORM-A005-P1-A-MANIPULATIVE-TECHNIQUES` through
`…-P1-H-REAL-TIME-RBI`. None of those ten norms' quoted text appears anywhere in that segment. The
prohibited practices live in sibling segments `AIA-TEXT-A005-P002` … `-P013`, one per lettered
point, and each of those is the `primary_spans` entry of its own norm.

Anything that reads a segment and expects to find the norms it lists is misled. This surfaced from
a reviewer reading segments in a review UI: the segment announces ten prohibited practices and
contains none of them.

## Root cause

`norm_ids` is populated for **every** span a norm links, without distinguishing the role that span
plays.

`src/aiact/norm_builder.py`, in `_build_norms`, lines 492-512:

```python
primary = f"AIA-TEXT-{record.source}"
spans = [primary, *(f"AIA-TEXT-{span}" for span in record.qualifier_spans)]
effective = [f"AIA-TEXT-{span}" for span in record.effective_date_spans]
...
primary_text = str(segments_by_id[primary]["text"])
if record.quote not in primary_text:
    raise ValueError(f"{record.norm_id}: quote is not exact in {primary}: {record.quote!r}")
...
for span in [*spans, *effective]:          # <-- primary, qualifier and effective-date alike
    segment = segments_by_id[span]
    if segment["disposition"] != SegmentDisposition.NORMATIVE.value:
        raise ValueError(f"{record.norm_id}: linked span {span} is not normative")
    norm_ids = segment["norm_ids"]
    assert isinstance(norm_ids, list)
    if record.norm_id not in norm_ids:
        norm_ids.append(record.norm_id)
```

Note the asymmetry: exact-quote containment is checked **only** against `primary`. That check is
right — a qualifier is not meant to contain the quote — but it means `norm_ids` can assert a link
the segment's own text cannot support, and nothing detects it.

## The conflation is load-bearing, so both sides must change together

`src/aiact/norm_loader.py` rebuilds the same conflated set and requires exact equality:

```python
# lines 117-123
linked_from_norms: dict[str, set[str]] = {segment_id: set() for segment_id in segments_by_id}
for norm in norm_inventory.norms:
    ...
    for span in norm.all_spans:            # primary + qualifier + definition + effective_date
        linked_from_norms[span].add(norm.norm_id)

# lines 146-153
for segment in text_review.segments:
    declared = set(segment.norm_ids)
    actual = linked_from_norms[segment.segment_id]
    if declared != actual:
        raise ValueError(
            f"{segment.segment_id} norm links disagree: segment declares "
            f"{sorted(declared)}, norms link {sorted(actual)}"
        )
```

`Norm.all_spans` (`src/aiact/schemas/norm.py:251`) is
`primary_spans + qualifier_spans + definition_spans + effective_date_spans`, de-duplicated.

Changing the builder alone makes the loader raise on every affected segment.

## A validator blocks the naive fix

`src/aiact/schemas/norm.py:136-155`:

```python
class TextReviewSegment(BaseModel):
    ...
    norm_ids: list[str] = []

    @model_validator(mode="after")
    def _disposition_has_the_right_shape(self) -> TextReviewSegment:
        ...
        if self.disposition is SegmentDisposition.NORMATIVE and not self.norm_ids:
            raise ValueError("normative segment requires at least one norm_id")
        if self.disposition is not SegmentDisposition.NORMATIVE and self.norm_ids:
            raise ValueError("only normative segments may link norm_ids")
```

If `norm_ids` is narrowed to primary-only, every chapeau segment ends up with an empty list and
fails this validator, because no norm is extracted from a chapeau. The rule has to become "at least
one norm in either role", and the "only normative segments may link" rule has to cover the new
field too.

## Scale

353 segments list norms in `norm_ids` while being the `primary_spans` entry of none of them. Every
one is a stem whose list lives in sibling segments. Largest first:

| Segment | norms listed | chars | text |
|---|---:|---:|---|
| `AIA-TEXT-A003-P001` | 70 | 70 | For the purposes of this Regulation, the following definitions apply: |
| `AIA-TEXT-ANNEX-III-P001` | 25 | 103 | High-risk AI systems pursuant to Article 6(2) are the AI systems listed… |
| `AIA-TEXT-A013-P003` | 17 | 78 | 3. The instructions for use shall contain at least the following inform… |
| `AIA-TEXT-ANNEX-II-P001` | 16 | 83 | Criminal offences referred to in Article 5(1), first subparagraph, poi… |
| `AIA-TEXT-A016-P001` | 12 | 41 | Providers of high-risk AI systems shall: |
| `AIA-TEXT-ANNEX-I-P001` | 12 | 90 | Section A. List of Union harmonisation legislation based on the New Le… |
| `AIA-TEXT-A055-P001` | 10 | 129 | 1. In addition to the obligations listed in Articles 53 and 54, provid… |
| `AIA-TEXT-A005-P001` | 10 | 51 | 1. The following AI practices shall be prohibited: |
| `AIA-TEXT-A053-P001` | 9 | 49 | 1. Providers of general-purpose AI models shall: |

Span-role totals across the corpus: `primary_spans` 1491, `qualifier_spans` 794,
`definition_spans` 0, `effective_date_spans` 1.

Corpus size for reference: 133 documents, 1505 segments (1350 normative), 1491 norms.

## Proposed fix

Split the field by role on `TextReviewSegment`:

- `norm_ids` — norms whose `primary_spans` contains this segment, i.e. norms whose quoted text is
  in this segment. The name stays; its meaning narrows to the one readers already assume.
- `qualifying_norm_ids` — norms referencing this segment as `qualifier_spans`, `definition_spans`
  or `effective_date_spans`.

Then:

1. `norm_builder.py` — append to the list matching the role instead of looping over the union.
2. `norm_loader.py` — build two maps and compare each against its own field.
3. `schemas/norm.py` — relax the normative-segment validator to require at least one norm across
   both lists; extend the non-normative rule to reject entries in either list.
4. Regenerate, then confirm idempotence:

```bash
UV_CACHE_DIR=/tmp/uv-cache-aiact uv run python scripts/build_normative_coverage.py --act-version 2026-07-27
```

```bash
UV_CACHE_DIR=/tmp/uv-cache-aiact uv run python scripts/build_normative_coverage.py --act-version 2026-07-27 --check
```

Never hand-edit anything under `norms/`, `text-review/` or `report.md` — they are generated from
`segments/` and `source-records/`.

## Constraints that must not regress

- Quote containment stays exact and stays checked against primary spans only
  (`norm_builder.py:500`, `norm_loader.py:124`). A qualifier must never be required to contain the
  quote.
- Segment `sha256` values and the tamper-evident law store are untouched by this change.
- Segment and norm `review` records — `status`, `extracted_by`, `verified_by` — must be untouched.
  All 1505 segments are `approved` / `verified_by: vidibro`; all 634 in-scope norms are approved.
  This is a field-shape change, not a re-review.
- Counts must not move: 1491 norms, 1505 segments, 1350 normative.

## Tests

76 references to `norm_ids` across five files: `tests/test_norm_builder.py`,
`tests/test_norm_granularity.py`, `tests/test_norm_granularity_audit.py`,
`tests/test_normative_coverage.py`, `tests/test_normative_metrics.py`.

`src/aiact/norm_metrics.py:152` counts `len(segment.norm_ids) > 1` for the
`normative_segments_with_multiple_norms` metric, currently asserted as **382** in
`test_metrics_expose_many_to_many_and_implementation_debt`. Narrowing `norm_ids` to primary-only
changes that number. Decide deliberately whether the metric should count primary links only
(recommended — it is meant to measure segments that yielded several norms) and update the assertion
with the reason, rather than matching whatever number falls out.

Currently green: `UV_CACHE_DIR=/tmp/uv-cache-aiact uv run pytest -q` → 1166 passed.
Lint: `UV_CACHE_DIR=/tmp/uv-cache-aiact uv run ruff check src tests scripts`.

## Acceptance

- No segment lists a norm under `norm_ids` unless that norm's `norm_text` is an exact substring of
  the segment's `text`. Worth adding as a test — it is the missing invariant, and it is what would
  have caught this.
- `AIA-TEXT-A005-P001` has empty `norm_ids` and ten entries in `qualifying_norm_ids`.
- Builder `--check` reports no drift; full suite green; review records unchanged.

## Out of scope

Segmentation is not at fault here and should not be changed as part of this. Separately recorded
debt: `AIA-TEXT-ANNEX-VII-I4` is 4589 characters carrying 17 norms because Annex VII is segmented
by top-level heading rather than by paragraph. Different problem.
