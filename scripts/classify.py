#!/usr/bin/env python3
"""Classify a use-case description through the M3 graph.

    # deterministic scripted demo — the flip, no API key needed:
    python scripts/classify.py --demo

    # real classification with the configured LLM (needs an API key):
    python scripts/classify.py --text "A tool that scores and ranks job applicants by fit."

    # run the whole Layer 1 golden set through the LLM and score classification accuracy:
    python scripts/classify.py --golden
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiact.eval.classification_cases import load_classification_cases  # noqa: E402
from aiact.graph import ScriptedBrain, classify  # noqa: E402
from aiact.graph.classify import load_questions  # noqa: E402
from aiact.schemas.enums import AnnexIIIArea, DerogationCondition  # noqa: E402
from aiact.usage import PRICES_AS_OF  # noqa: E402


def _print(result) -> None:
    uc = result.use_cases[0]
    print(f"  risk class : {result.overall_risk_class.value}")
    print(f"  confidence : {result.confidence}")
    print(f"  reasoning  : {result.reasoning}")
    if uc.performs_profiling is not None:
        print(f"  profiling  : {uc.performs_profiling.value}")
    print("  triggered by:")
    if not result.triggered_by:
        print("    -")
    for e in result.triggered_by:
        cite = f"Art.{e.source.article}" + (f"({e.source.paragraph})" if e.source.paragraph else "")
        if e.source.annex:
            cite += f", Annex {e.source.annex}"
        print(f"    {cite} [{e.node_id or '?'}]")
        # the point of the whole change: WHICH words in the documentation drove this
        print(f"      quote: {e.evidence_quote or '(none supplied)'}")


def demo() -> None:
    """The flip, deterministically — no LLM."""
    parser = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": DerogationCondition.NARROW_PROCEDURAL_TASK,
        }
    )
    scorer = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": False,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,
        }
    )
    print("\nCV parser (extracts fields only):")
    _print(classify("cv parser", parser, "cv_parsing_fields"))
    print("\n+ one sentence: 'also scores and ranks candidates':")
    _print(classify("cv parser + scoring", scorer, "cv_parsing_plus_scoring"))
    print("\n=> the flip: not_high_risk -> high_risk, via the Art. 6(3) profiling carve-back.\n")


def run_golden() -> None:
    from aiact.graph.llm_brain import LLMBrain

    cases = load_classification_cases()
    brain = LLMBrain()
    anchored = load_questions()
    print(f"Classifying {len(cases.cases)} Layer 1 cases with model={brain.model}")
    print("questions anchored in verbatim article + Annex III text\n")
    correct = 0
    for case in cases.cases:
        result = classify(case.description, brain, case.case_id, questions=anchored)
        got = result.overall_risk_class
        ok = got == case.expected_risk_class
        correct += ok
        mark = "OK  " if ok else "MISS"
        print(
            f"  {mark} {case.case_id:30} "
            f"expected {case.expected_risk_class.value:14} got {got.value}"
        )
    print(f"\nclassification accuracy: {correct}/{len(cases.cases)}")
    print(f"run cost           : {brain.usage.summary(brain.model)}")
    per_case = brain.usage.estimated_cost_usd(brain.model)
    if per_case is not None and cases.cases:
        print(f"per case           : ~${per_case / len(cases.cases):.4f}")
    print(f"(prices as of {PRICES_AS_OF}; estimated — see src/aiact/usage.py)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Classify a use case through the M3 graph.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--demo", action="store_true", help="deterministic flip demo, no API key")
    g.add_argument("--text", help="classify this description with the configured LLM")
    g.add_argument("--golden", action="store_true", help="run the Layer 1 golden set with the LLM")
    args = ap.parse_args()

    if args.demo:
        demo()
    elif args.golden:
        run_golden()
    else:
        from aiact.graph.llm_brain import LLMBrain

        print(f"\nDescription: {args.text}\n")
        _print(classify(args.text, LLMBrain(), questions=load_questions()))
        print()


if __name__ == "__main__":
    main()
