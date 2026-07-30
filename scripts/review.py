#!/usr/bin/env python3
"""Review a document end to end: classify it, then check it against the obligations that activates.

# a full review of one document (needs an API key):
python scripts/review.py path/to/system-card.md

# one of the worked reference documents:
python scripts/review.py data/golden_set/reference/<name>.md --system-id ref
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv  # noqa: E402

from aiact.pipeline import review  # noqa: E402
from aiact.policy_loader import load_policy_spec  # noqa: E402
from aiact.schemas.enums import Verdict  # noqa: E402
from aiact.tracing import enable_tracing  # noqa: E402

_MARK = {
    Verdict.PASS: "ok  ",
    Verdict.GAP: "GAP ",
    Verdict.INADEQUATE: "THIN",
    Verdict.NEEDS_REVIEW: "??  ",
    Verdict.NOT_APPLICABLE: "n/a ",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--system-id", default=None, help="defaults to the file stem")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    load_dotenv()  # the CLI boundary owns .env; the library stays free of it
    from aiact.classify.llm_brain import LLMBrain  # lazy: importing needs no API stack

    text = args.document.read_text(encoding="utf-8")
    system_id = args.system_id or args.document.stem
    brain = LLMBrain()

    print(f"Reviewing {args.document} ({len(text)} chars) — model={brain.model}")
    print(f"Langfuse tracing: {'ON' if enable_tracing() else 'off (no keys)'}\n")

    report = review(
        text,
        load_policy_spec(),
        brain,
        system_id=system_id,
        max_workers=args.workers,
    )

    print(f"risk class : {report.classification.overall_risk_class.value}")
    print(f"reasoning  : {report.classification.reasoning}\n")

    if report.scope_note:
        print(f"!! {report.scope_note}\n")

    for finding in report.findings:
        src = finding.citation
        cite = f"Art.{src.article}" + (f"({src.paragraph})" if src.paragraph else "")
        print(f"  {_MARK[finding.verdict]} {finding.rule_id:<16} {cite}")
        print(f"       {finding.reasoning[:160]}")

    if report.not_document_verifiable:
        print(f"\n  confirm separately: {', '.join(report.not_document_verifiable)}")

    s = report.summary
    print(
        f"\n{s.total_applicable} applicable — {s.passed} pass, {s.gaps} gap, "
        f"{s.inadequate} inadequate, {s.needs_review} needs review"
    )


if __name__ == "__main__":
    main()
