# Normative coverage authoring inputs

Each directory is immutable with respect to its `act_version_date` and contains the reviewed inputs
for one stored Act snapshot:

- `segments.yaml` defines reviewed document divisions and extraction provenance. A stored article
  or annex omitted from this file is still emitted as one exact full-body `needs_review` segment.
- `source-records.yaml` defines exact norm quotations and their legal and implementation metadata.
  Its `implementation_targets` list is the versioned target catalog against which mappings and
  policy-rule interpretive links are validated.
- `text-review.yaml`, `norms.yaml`, and `report.md` are generated from those reviewed inputs and the
  integrity-checked article, annex, guidance, and implementation stores.

Offsets, hashes, complete-corpus debt segments, norm artifacts, and reports are generated. Do not
edit those derived values directly.

Build any stored version with:

```bash
python scripts/build_normative_coverage.py --act-version YYYY-MM-DD
```

Verify that committed artifacts reproduce exactly with:

```bash
python scripts/build_normative_coverage.py --act-version YYYY-MM-DD --check
```

Adding a new Act snapshot means adding a new version directory and new reviewed inputs. It must not
modify an earlier version's authoring records.
