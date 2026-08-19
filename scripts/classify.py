#!/usr/bin/env python3
"""Classify a use-case description through the M3 graph.

# deterministic scripted demo — the flip, no API key needed:
python scripts/classify.py --demo

# real classification with the configured LLM (needs an API key):
python scripts/classify.py --text "A tool that scores and ranks job applicants by fit."

# run the whole Layer 1 golden set through the LLM and score classification accuracy:
python scripts/classify.py --golden

# the same, against a HELD-OUT split — the reportable number, and running it spends the set:
python scripts/classify.py --golden --cases data/golden_set/<held-out file>.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiact.classify import ScriptedBrain, classify  # noqa: E402
from aiact.classify.graph import load_questions  # noqa: E402
from aiact.eval.classification_cases import load_classification_cases  # noqa: E402
from aiact.eval.classification_score import score_case, score_run  # noqa: E402
from aiact.eval.node_score import score_node_run  # noqa: E402
from aiact.gap import roles as role_questions  # noqa: E402
from aiact.schemas.enums import AnnexIIIArea, DerogationCondition  # noqa: E402
from aiact.tracing import enable_tracing  # noqa: E402
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
        if e.abstained_because == "description_silent":
            # Not a finding about the system — a finding about the DOCUMENT. Says what to add.
            print("      ! the description does not answer this; supply the fact and re-run")
        elif e.abstained_because == "reply_unusable":
            print("      ! no usable answer returned — a run failure, not a documentation gap")
        # the point of the whole change: WHICH words in the documentation drove this
        print(f"      quote: {e.evidence_quote or '(none supplied)'}")
    # Art. 50 sits BESIDE the tier, never inside it — a minimal-risk generator can owe it and a
    # high-risk scorer can owe none.
    if result.transparency is not None:
        duties = result.transparency_duties_by_role
        owed = (
            "; ".join(
                f"{role.value}: "
                + ", ".join(f"Art. 50({d.paragraph}) {d.value}" for d in ds)
                for role, ds in duties.items()
            )
            or "no duty attaches"
        )
        print(f"  art. 50    : {owed} [{result.transparency.confidence}]")
    if result.rests_on_guidance:
        print("  ⚠ rests partly on NON-BINDING Commission interpretation:")
        for g in result.guidance_sources:
            print(f"    {g.reference}, {g.locator} [{g.snippet_ref}]")
        print("    (non-binding; the Court of Justice of the EU is the authoritative interpreter)")


def demo() -> None:
    """The flip, deterministically — no LLM."""
    parser = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": False,
            "derogation": DerogationCondition.NARROW_PROCEDURAL_TASK,
            # Art. 6(3) exempts on BOTH limbs: a narrow role AND no significant risk of harm.
            "significant_risk": False,
            "transparency": [],
        }
    )
    scorer = ScriptedBrain(
        {
            "is_ai": True,
            "prohibited": None,
            "annex_iii": AnnexIIIArea.EMPLOYMENT,
            "profiling": True,
            "transparency": [],
        }
    )
    print("\nCV parser (extracts fields only):")
    _print(classify("cv parser", parser, "cv_parsing_fields"))
    print("\n+ one sentence: 'also scores and ranks candidates':")
    _print(classify("cv parser + scoring", scorer, "cv_parsing_plus_scoring"))
    print("\n=> the flip: not_high_risk -> high_risk, via the Art. 6(3) profiling carve-back.\n")


def _held_out_banner() -> None:
    """Stamp the commit, and say out loud what a held-out run costs.

    A held-out score is only worth reporting if it can be tied to the code that produced it and to
    a set nobody has tuned against. Neither is checkable after the fact from a number in a
    document, so both are printed here: the commit, and whether the tree was clean at the time.
    A dirty tree does not stop the run — it means the result is not reproducible, which is the
    reader's problem to know about rather than the script's to prevent.
    """
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False
        ).stdout.strip()

    commit = git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = " ** WORKING TREE DIRTY — result is not reproducible **"
    state = dirty if git("status", "-s") else " (clean)"
    print("=" * 96)
    print("HELD-OUT SET. This is the reportable number, and running it spends the set:")
    print("  - do not edit a case because it failed. That is the tuning this split exists to stop.")
    print("  - fix the CODE or the PROMPT, or record the disagreement, and re-run sparingly.")
    print(f"  commit: {commit}{state}")
    print("=" * 96)


def run_golden(cases_path: Path | None = None) -> None:
    from aiact.classify.llm_brain import LLMBrain

    cases = load_classification_cases(cases_path)
    brain = LLMBrain()
    anchored = load_questions()
    traced = enable_tracing()
    where = cases_path or "data/golden_set/classification_cases.yaml (dev)"
    if any(c.split == "test" for c in cases.cases):
        _held_out_banner()
    print(f"Classifying {len(cases.cases)} Layer 1 cases from {where}")
    print(f"model={brain.model}")
    print(f"Langfuse tracing: {'ON' if traced else 'off (no keys) — traces not recorded'}")
    print("questions anchored in verbatim article + Annex III text\n")
    role_qs = role_questions.load_questions()
    pairs = []
    node_pairs = []
    for case in cases.cases:
        result = classify(case.description, brain, case.case_id, questions=anchored)
        pairs.append((case, result))
        # Art. 25 is asked by the GAP layer, not the cascade, so its answer is not on `result`.
        # It is still measured here: the answer key is a fact about the case, and running the whole
        # pipeline just to reach one question would pay for a full document review per case. The
        # gate is `gap.roles.ask`'s own, so this asks exactly what a real review would.
        art25 = role_questions.ask(
            brain, case.description, result.overall_risk_class, role_qs
        )
        node_pairs.append((case, [*result.answers, *([art25] if art25 else [])]))
        score = score_case(case, result)
        # Art. 50 is reported per case beside the class, not folded into it — a run can get every
        # tier right while owing the wrong transparency duty on all of them.
        art50 = "  art50 " + ("OK  " if score.transparency_correct else "MISS")
        art50 += f" exp {str(case.expected_transparency_obligation):5} got {score.got_transparency}"
        mark = "OK  " if score.class_correct else "MISS"
        print(
            f"  {mark} {case.case_id:30} "
            f"expected {case.expected_risk_class.value:14} got {result.overall_risk_class.value:14}"
            f"{art50}"
        )
    print()
    for line in score_run(pairs).lines():
        print(line)
    # The per-node table follows the two headline axes rather than replacing them: it says WHICH
    # question was weak, which the terminal class cannot.
    for line in score_node_run(node_pairs).lines():
        print(line)
    print()
    print(f"run cost           : {brain.usage.summary(brain.model)}")
    per_case = brain.usage.estimated_cost_usd(brain.model)
    if per_case is not None and cases.cases:
        print(f"per case           : ~${per_case / len(cases.cases):.4f}")
    print(f"(prices as of {PRICES_AS_OF}; estimated — see src/aiact/usage.py)")


def main() -> None:
    # Load .env into the process environment at the CLI boundary, BEFORE anything reads it. LiteLLM
    # loads .env on import, but that is lazy (first model call) — too late for enable_tracing(),
    # which checks the Langfuse keys up front. Doing it here makes the order deterministic for both
    # provider auth and tracing. Kept out of the library/tracing module on purpose: that stays pure
    # so its no-op tests are not at the mercy of a developer's real .env.
    from dotenv import load_dotenv

    load_dotenv()

    ap = argparse.ArgumentParser(description="Classify a use case through the M3 graph.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--demo", action="store_true", help="deterministic flip demo, no API key")
    g.add_argument("--text", help="classify this description with the configured LLM")
    g.add_argument("--golden", action="store_true", help="run the Layer 1 golden set with the LLM")
    ap.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="which case file --golden runs. Defaults to the DEV set, which is the tunable one. "
        "Point it at a held-out file to measure — and read the warning that prints before "
        "doing so. Detection is on the file's `default_split`, not its name.",
    )
    args = ap.parse_args()

    if args.demo:
        demo()
    elif args.golden:
        run_golden(args.cases)
    else:
        from aiact.classify.llm_brain import LLMBrain

        print(f"\nDescription: {args.text}\n")
        _print(classify(args.text, LLMBrain(), questions=load_questions()))
        print()


if __name__ == "__main__":
    main()
