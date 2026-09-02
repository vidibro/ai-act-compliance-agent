"""Print reproducible corpus-wide granularity candidates without changing review status."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from aiact.norm_granularity import scan_granularity
from aiact.norm_loader import load_normative_coverage

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--act-version", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    policy = ROOT / "data" / "policy"
    coverage = policy / "normative-coverage" / args.act_version.isoformat()
    bundle = load_normative_coverage(
        coverage / "text-review",
        coverage / "norms",
        articles_root=policy / "articles",
        annexes_root=policy / "annexes",
        guidance_root=policy / "guidance",
    )
    candidates = scan_granularity(bundle)
    content_norms = [
        {
            "norm_id": norm.norm_id,
            "content_entries": len(norm.mandatory_content),
            "source_span_ids": norm.all_spans,
        }
        for norm in bundle.norm_inventory.norms
        if norm.mandatory_content
    ]
    print(
        json.dumps(
            {
                "status": "triage_only_not_legal_approval",
                "act_version": args.act_version.isoformat(),
                "documents_scanned": bundle.validated_documents,
                "segments_scanned": len(bundle.text_review.segments),
                "source_characters_scanned": sum(len(s.text) for s in bundle.text_review.segments),
                "candidate_count": len(candidates),
                "candidates": [asdict(candidate) for candidate in candidates],
                "content_norm_count": len(content_norms),
                "content_norms": content_norms,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
