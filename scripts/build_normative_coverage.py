"""Build normative-coverage artifacts for any versioned reviewed source inventory."""

from __future__ import annotations

import argparse
from pathlib import Path

from aiact.norm_builder import NormBuilderPaths, run_builder

ROOT = Path(__file__).resolve().parents[1]


def paths_for_version(version: str) -> NormBuilderPaths:
    source_root = ROOT / "data" / "policy" / "normative-coverage" / version
    return NormBuilderPaths(
        reviewed_documents=source_root / "segments",
        norm_sources=source_root / "source-records",
        articles_root=ROOT / "data" / "policy" / "articles",
        annexes_root=ROOT / "data" / "policy" / "annexes",
        guidance_root=ROOT / "data" / "policy" / "guidance",
        text_output=source_root / "text-review",
        norm_output=source_root / "norms",
        report_output=source_root / "report.md",
        generated_by="src/aiact/norm_builder.py",
        adjudications=source_root / "adjudications",
        policy_spec=ROOT / "data" / "policy" / "spec.yaml",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--act-version", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        run_builder(paths_for_version(args.act_version), check=args.check)
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
