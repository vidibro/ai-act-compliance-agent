#!/usr/bin/env python3
"""Run a checker against the golden set and print the scorecard.

    python scripts/run_eval.py

Two checkers:

    python scripts/run_eval.py                  # keyword baseline — the strawman, free and offline
    python scripts/run_eval.py --checker judge   # the LLM judge — COSTS MONEY, one call per rule

The baseline's scorecard is the target the real agent has to beat, and the shape of its failure is
the project's thesis stated as data: 88.0% overall, 0 of 6 on INADEQUATE. Always read the judge's
number against that breakdown, never against the aggregate alone.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv  # noqa: E402

from aiact.eval.baseline import KeywordBaseline  # noqa: E402
from aiact.eval.runner import Checker, report, run  # noqa: E402
from aiact.gap.judge import LLMJudge  # noqa: E402
from aiact.policy_loader import (  # noqa: E402
    article_filename,
    articles_dir_for,
    load_policy_spec,
)
from aiact.schemas.eval import GoldenSet  # noqa: E402
from aiact.scrubbing import install_excepthook  # noqa: E402
from aiact.tracing import trace_run  # noqa: E402

_TITLE = re.compile(r"^title:\s*(.*)$", re.M)


def article_titles(spec, articles_root: Path | None) -> dict[str, str]:
    """rule_id -> the title of the article it cites (the baseline's only input)."""
    art_dir = articles_dir_for(spec.act_version_date, articles_root)
    titles: dict[str, str] = {}
    for rule in spec.rules:
        path = art_dir / article_filename(rule.source.article)
        m = _TITLE.search(path.read_text(encoding="utf-8"))
        if m is None:
            raise ValueError(f"{path} has no title in its front matter")
        titles[rule.rule_id] = m.group(1).strip()
    return titles


def main() -> None:
    ap = argparse.ArgumentParser(description="Score a checker against the golden set.")
    ap.add_argument("--golden", type=Path, default=Path("data/golden_set/golden_set.json"))
    ap.add_argument("--spec", type=Path, default=Path("data/policy/spec.yaml"))
    ap.add_argument("--articles-root", type=Path, default=None)
    ap.add_argument(
        "--checker",
        choices=["baseline", "judge"],
        default="baseline",
        help="`baseline` is the free keyword strawman. `judge` runs the LLM checker: one API call "
        "per (case, rule), so a full dev run is ~133 calls and costs real money.",
    )
    ap.add_argument("--model", default=None, help="override the judge's model (LiteLLM string)")
    ap.add_argument(
        "--no-reference-content",
        action="store_true",
        help="resolved cross-references report only that a section EXISTS, without pulling its "
        "text into the prompt. Cheaper; tests whether the content injection earns its tokens.",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=8,
        help="concurrent judgements (LLM checker only). The calls are independent; running them "
        "one at a time turned a 5-minute job into 35.",
    )
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
    if args.checker == "judge":
        load_dotenv()  # the CLI boundary owns .env; the library stays free of it
        install_excepthook()  # scrub the keys just loaded out of any traceback
        # Named before it is widened to Checker: `model` belongs to the LLM judge, not to every
        # checker — a keyword baseline calls no model and should not have to claim one.
        judge = LLMJudge(model=args.model, reference_content=not args.no_reference_content)
        print(f"checker: {judge.name} ({judge.model}) — {len(cases) * 7} calls, be patient\n")
        checker: Checker = judge
    else:
        checker = KeywordBaseline(article_titles(spec, args.articles_root))

    workers = args.workers if args.checker == "judge" else 1
    with trace_run(f"gap-eval:{args.checker}", session_id=golden.system_id):
        results = run(checker, scored, spec, max_workers=workers, progress=args.checker == "judge")

    label = f"{checker.name}  [split={args.split}]"
    print(report(label, results))
    if isinstance(checker, LLMJudge):
        print(f"\n{checker.usage.summary(checker.model)}")
    if args.split != "test":
        print("\n(reminder: this is not a reportable score — only split=test is.)")


if __name__ == "__main__":
    main()
