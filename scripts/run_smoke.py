#!/usr/bin/env python3
"""Smoke check — run the anonymised real-world descriptions through the M3 cascade.

    python scripts/run_smoke.py

NOT an eval. `data/golden_set/smoke/` has no ground truth and is part of no split, so nothing here
is scored and no number from it may be reported. The question is qualitative and asked once, before
tuning starts: does the classifier behave sanely on REAL vendor prose, or only on ours?

Specifically watching for the two gaps the read-through found:
  - the human-in-the-loop reassurance every real page carries (legally irrelevant to the class,
    but it reads exculpatory) — does it drag a high-risk system down?
  - the scheduler's cross-sell line for a screening product it does not itself perform — does it
    drag a minimal-risk system up?
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiact.classify.graph import classify, load_questions  # noqa: E402
from aiact.classify.llm_brain import LLMBrain  # noqa: E402

SMOKE = Path(__file__).resolve().parents[1] / "data" / "golden_set" / "smoke"

# The author's reading, for orientation only — these are NOT labels and are not scored against.
READING = [
    ("screening-and-ranking", "high_risk (Art. 6(3) profiling carve-back)"),
    ("video-interview-analysis", "prohibited (Art. 5(1)(f))"),
    ("interview-coordination", "minimal"),
]


def main() -> None:
    brain = LLMBrain()
    questions = load_questions()
    print(f"Smoke check — model={brain.model}, real vendor prose, NOT scored\n")

    for name, reading in READING:
        text = (SMOKE / f"{name}.md").read_text(encoding="utf-8")
        result = classify(text, brain, name, questions=questions)
        uc = result.use_cases[0]

        print(f"=== {name}   ({len(text)} chars) ===")
        print(f"  author's reading : {reading}")
        print(f"  got              : {result.overall_risk_class.value}  [{result.confidence}]")
        print(f"  reasoning        : {result.reasoning}")
        if uc.annex_iii_area is not None:
            print(f"  annex III area   : {uc.annex_iii_area.value}")
        if uc.performs_profiling is not None:
            print(f"  profiling        : {uc.performs_profiling.value}")
        for e in result.triggered_by:
            cite = f"Art.{e.source.article}"
            if e.source.paragraph:
                cite += f"({e.source.paragraph})"
            print(f"  [{e.node_id}] {cite}")
            print(f"      why  : {(e.reasoning or '')[:200]}")
            print(f"      quote: {(e.evidence_quote or '(none)')[:170]}")
        if result.rests_on_guidance:
            print(f"  guidance         : {[g.reference for g in result.guidance_sources]}")
        if result.transparency is not None:
            print(f"  art.50           : {result.transparency.value}")
        print()

    print(f"cost: {brain.usage.summary(brain.model)}")


if __name__ == "__main__":
    main()
