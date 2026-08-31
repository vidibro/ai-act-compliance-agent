"""Generate source-backed candidate passages while preserving the full review denominator."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

from aiact.config import get_settings
from aiact.norm_extraction import extract_norm_candidates
from aiact.norm_loader import load_normative_coverage

SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
ROOT = Path(__file__).resolve().parents[1]


def rooted(path: str | Path) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else ROOT / resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--act-version", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--extractor-id", required=True)
    parser.add_argument("--all-segments", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if SAFE_ID.fullmatch(args.run_id) is None:
        parser.error("--run-id may contain only letters, digits, dot, underscore, and hyphen")

    settings = get_settings()
    requested_version = args.act_version
    coverage_root = rooted(settings.policy_normative_coverage_path) / requested_version
    bundle = load_normative_coverage(
        coverage_root / "text-review",
        coverage_root / "norms",
        articles_root=rooted(settings.policy_articles_path),
        annexes_root=rooted(settings.policy_annexes_path),
        guidance_root=ROOT / "data" / "policy" / "guidance",
    )
    if bundle.text_review.act_version_date.isoformat() != requested_version:
        parser.error("requested version disagrees with the normative coverage artifacts")

    run = extract_norm_candidates(
        bundle,
        run_id=args.run_id,
        extractor_id=args.extractor_id,
        include_reviewed_segments=args.all_segments,
    )
    destination = args.output or coverage_root / "candidate-runs" / f"{args.run_id}.yaml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(run.model_dump(mode="json"), sort_keys=False, width=100)
    try:
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        parser.error(f"candidate run already exists: {destination}")

    print(
        f"wrote {destination}: considered={len(run.segment_ids_considered)} segments, "
        f"characters={run.source_characters_considered}, candidates={len(run.candidates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
