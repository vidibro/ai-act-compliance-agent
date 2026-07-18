#!/usr/bin/env python3
"""Run a checker against the golden set and print the scorecard.

    python scripts/run_eval.py

Today the only checker is the keyword baseline — the strawman. Its scorecard is the target the
real agent has to beat, and the shape of its failure is the project's thesis stated as data.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiact.eval.baseline import KeywordBaseline  # noqa: E402
from aiact.eval.runner import report, run  # noqa: E402
from aiact.policy_loader import articles_dir_for, load_policy_spec  # noqa: E402
from aiact.schemas.eval import GoldenSet  # noqa: E402

_TITLE = re.compile(r"^title:\s*(.*)$", re.M)


def article_titles(spec, articles_root: Path | None) -> dict[str, str]:
    """rule_id -> the title of the article it cites (the baseline's only input)."""
    art_dir = articles_dir_for(spec.act_version_date, articles_root)
    titles: dict[str, str] = {}
    for rule in spec.rules:
        path = art_dir / f"article-{rule.source.article:03d}.md"
        titles[rule.rule_id] = _TITLE.search(path.read_text(encoding="utf-8")).group(1).strip()
    return titles


def main() -> None:
    ap = argparse.ArgumentParser(description="Score a checker against the golden set.")
    ap.add_argument("--golden", type=Path, default=Path("data/golden_set/golden_set.json"))
    ap.add_argument("--spec", type=Path, default=Path("data/policy/spec.yaml"))
    ap.add_argument("--articles-root", type=Path, default=None)
    ap.add_argument(
        "--split",
        choices=["dev", "test", "all"],
        default="dev",
        help="which split to score. Tune on `dev`; only `test` is a reportable number.",
    )
    args = ap.parse_args()

    spec = load_policy_spec(args.spec, args.articles_root)
    golden = GoldenSet.model_validate(json.loads(args.golden.read_text(encoding="utf-8")))
    cases = golden.for_split(args.split)
    n_dev = sum(c.split == "dev" for c in golden.cases)
    n_test = sum(c.split == "test" for c in golden.cases)
    print(
        f"golden set: {len(golden.cases)} cases (dev={n_dev}, test={n_test}) | "
        f"act {golden.act_version_date} | spec {golden.spec_version}"
    )
    print(f"scoring split={args.split}: {len(cases)} cases")
    if not cases:
        print(f"\nNo cases in split={args.split!r}. Nothing to score.")
        if args.split == "test":
            print("The held-out test split is empty by design — author it before quoting a score.")
        return

    scored = GoldenSet(
        system_id=golden.system_id,
        reference_path=golden.reference_path,
        act_version_date=golden.act_version_date,
        spec_version=golden.spec_version,
        cases=cases,
    )
    checker = KeywordBaseline(article_titles(spec, args.articles_root))
    results = run(checker, scored, spec)
    label = f"{checker.name}  [split={args.split}]"
    print(report(label, results))
    if args.split != "test":
        print("\n(reminder: this is not a reportable score — only split=test is.)")


if __name__ == "__main__":
    main()
