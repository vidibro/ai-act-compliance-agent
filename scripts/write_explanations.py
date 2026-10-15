#!/usr/bin/env python3
"""Write the plain-language explanation of every report row that has none, or whose wording changed.

    python scripts/write_explanations.py --dry-run     # list what would be written
    python scripts/write_explanations.py               # write them (needs a model key)
    python scripts/write_explanations.py --only AIA-RULE-HR-A09 AIA-NORM-A040-P1-HARMONISED-STANDARD

An explanation that is current is kept, reviewed or not. One whose wording changed is rewritten and
loses its review: `verified_by` is the reviewer's sign-off on that text, not on the row.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv  # noqa: E402

from aiact.policy_loader import load_policy_spec  # noqa: E402
from aiact.report_app import explanations  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list what would be written")
    parser.add_argument("--only", nargs="*", default=None, help="rule or norm ids to write")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    load_dotenv()
    spec = load_policy_spec()
    version = str(spec.act_version_date)
    rows = explanations.inputs(spec)
    stored = dict(explanations.load(version))
    todo = {
        row_id: text
        for row_id, text in rows.items()
        if (args.only is None or row_id in args.only)
        and explanations.current(row_id, text, version) is None
    }
    print(f"{len(rows)} rows, {len(rows) - len(todo)} current, {len(todo)} to write")
    if args.dry_run or not todo:
        for row_id in sorted(todo):
            print("  ", row_id)
        return

    explainer = explanations.LLMExplainer()
    today = datetime.now(UTC).date()

    def write(item: tuple[str, str]) -> tuple[str, str, str | None]:
        row_id, text = item
        try:
            return row_id, text, explainer.explain(text)
        except Exception as exc:  # one failed row must not lose the others
            print(f"  !! {row_id}: {exc}", file=sys.stderr)
            return row_id, text, None

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row_id, text, written in pool.map(write, sorted(todo.items())):
            if written is None:
                failed.append(row_id)
                continue
            stored[row_id] = explanations.Explanation(
                text=written,
                source_sha256=explanations.fingerprint(text),
                model=explainer.model,
                written_at=today,
            )
    # Rows that no longer exist are dropped, so the file never explains a rule that is gone.
    explanations.save(version, {k: v for k, v in stored.items() if k in rows})
    print(f"wrote {len(todo) - len(failed)}, failed {len(failed)}: {failed}")
    print(explainer.usage.summary(explainer.model))


if __name__ == "__main__":
    main()
