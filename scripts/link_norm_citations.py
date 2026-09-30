"""Add a relies_on_norms relation for every citation a norm has no relation to.

Reads the current inventory, finds each cited article or annex of this Regulation that a norm is
not yet linked to (aiact.norm_citations), and appends one relation per cited phrase to the
source-records manifest. Rebuild afterwards:

    python scripts/link_norm_citations.py --act-version 2026-07-27
    python scripts/build_normative_coverage.py --act-version 2026-07-27
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

import yaml

from aiact.norm_citations import unlinked_citations
from aiact.norm_loader import load_normative_coverage

ROOT = Path(__file__).resolve().parents[1]
MARKER = "interpretations:\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--act-version", required=True)
    args = parser.parse_args()
    manifest = (
        ROOT / "data/policy/normative-coverage" / args.act_version / "source-records/manifest.yaml"
    )

    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    segments = {segment.segment_id: segment.text for segment in bundle.text_review.segments}
    existing = {relation.relation_id for relation in bundle.norm_inventory.relations}
    missing = unlinked_citations(bundle)
    if not missing:
        print("every citation is linked")
        return 0

    per_norm: Counter[str] = Counter()
    lines = [
        "  # One relation per cited article or annex of this Regulation, found in the norm's own",
        "  # wording by scripts/link_norm_citations.py.",
    ]
    for item in missing:
        norm = norms[item.norm_id]
        per_norm[item.norm_id] += 1
        stem = item.norm_id.removeprefix("AIA-NORM-")
        relation_id = f"AIA-REL-{stem}-CITES-{per_norm[item.norm_id]:02d}"
        while relation_id in existing:
            per_norm[item.norm_id] += 1
            relation_id = relation_id[:-2] + f"{per_norm[item.norm_id]:02d}"
        existing.add(relation_id)
        span = next(
            (s for s in norm.primary_spans if item.citation in segments[s]), norm.primary_spans[0]
        )
        detail = yaml.safe_dump({"detail": f"Cites {item.citation}."}, width=10_000).strip()
        lines += [
            f"  - relation_id: {relation_id}",
            f"    source_norm_id: {item.norm_id}",
            "    kind: relies_on_norms",
            "    target_norm_ids:",
            *[f"    - {target}" for target in item.targets],
            "    legal_basis_spans:",
            f"    - {span}",
            f"    {detail}",
        ]

    text = manifest.read_text(encoding="utf-8")
    if text.count(MARKER) != 1 or not re.search(r"^norm_relations:$", text, re.M):
        raise SystemExit(f"{manifest}: expected norm_relations followed by one {MARKER!r}")
    manifest.write_text(text.replace(MARKER, "\n".join(lines) + "\n" + MARKER), encoding="utf-8")
    print(f"added {len(missing)} relations for {len(per_norm)} norms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
