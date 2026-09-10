#!/usr/bin/env python3
"""Grade the REASONING of a run against the source it was reached from. COSTS MONEY.

    python scripts/run_grounding.py --layer classify     # every cascade answer
    python scripts/run_grounding.py --layer gap          # every rule verdict

The grader defaults to AIACT_LLM_MODEL, so it marks its own work unless AIACT_GRADER_MODEL names
another; the scorecard says which.

Separate from run_eval.py on purpose. That script scores ANSWERS against an exact key and needs no
model to do it; this one scores SENTENCES, which have no key, so a model has to read them. Two
different kinds of number should not arrive looking alike — and this one costs a second call per
judgement on top of the run it is grading.

Neither number replaces the other. A run can be perfectly grounded and wrong, or right for reasons
it cannot support. This says only whether the justification stayed inside its source.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv  # noqa: E402

from aiact.classify.graph import classify, load_questions  # noqa: E402
from aiact.classify.llm_brain import LLMBrain  # noqa: E402
from aiact.eval.classification_cases import load_classification_cases  # noqa: E402
from aiact.eval.grounding import Grounding, ReasoningGrader, report  # noqa: E402
from aiact.gap.judge import LLMJudge  # noqa: E402
from aiact.llm import flatten  # noqa: E402
from aiact.policy_loader import load_policy_spec  # noqa: E402
from aiact.schemas.eval import GoldenSet, Split  # noqa: E402
from aiact.tracing import trace_run  # noqa: E402


def grade_classification(
    grader: ReasoningGrader, split: Split, cases_path: Path
) -> list[Grounding]:
    """Every cascade answer, against the prompt that produced it.

    Abstentions are skipped: their `reasoning` is OUR sentence about why the model declined, not
    the model's claim about the description, and grading our own text would measure nothing.
    """
    cases = [c for c in load_classification_cases(cases_path).cases if c.split == split]
    inner = LLMBrain()
    questions = load_questions()
    print(f"layer=classify  split={split}  cases={len(cases)}  brain={inner.model}")

    results: list[Grounding] = []
    for case in cases:
        result = classify(case.description, inner, case.case_id, questions=questions)
        for answer in result.answers:
            if answer.abstained_because is not None:
                continue
            # `load_questions()` is deterministic and this is the same dict the run was given, so
            # looking the question up by `node_id` yields the object the node was actually handed.
            question = questions[answer.node_id or ""]
            # The BUILDER, called with the arguments this run used — never a rebuild of its output.
            # It carries the question text as well as the law and the description, and questions
            # cite provisions of their own (`scope` names Annex III(6) and (7)).
            shown = flatten(inner._user_content(question, case.description))
            results.append(
                grader.grade(
                    answer.reasoning, shown, label=f"{case.case_id}/{answer.node_id}"
                )
            )
            print(results[-1].outcome[0], end="", flush=True)
    print(f"\n\nrun cost   : {inner.usage.summary(inner.model)}")
    return results


def grade_gap(
    grader: ReasoningGrader, split: Split, golden_path: Path, spec_path: Path
) -> list[Grounding]:
    """Every rule verdict, against the prompt that produced it.

    `Judgement.prompt` is what makes this exact: the judge records its whole user turn as sent, so
    the grader reads the same text — enacted provision, rubric, outline, resolved cross-references
    and excerpts — rather than a caller's approximation of it.
    """
    golden = GoldenSet.model_validate(json.loads(golden_path.read_text(encoding="utf-8")))
    spec = load_policy_spec(spec_path, None)
    cases = golden.for_split(split)
    judge = LLMJudge()
    rules = {r.rule_id: r for r in spec.rules}
    print(f"layer=gap  split={split}  cases={len(cases)}  judge={judge.model}")

    results: list[Grounding] = []
    for case in cases:
        for rule_id in case.expected:
            rule = rules[rule_id]
            if not rule.document_verifiable:
                continue  # never reaches a model, so there is no reasoning to grade
            judgement = judge.judge(rule, case.raw_text)
            if not judgement.prompt:
                continue
            results.append(
                grader.grade(
                    judgement.reasoning, judgement.prompt, label=f"{case.case_id}/{rule_id}"
                )
            )
            print(results[-1].outcome[0], end="", flush=True)
    print(f"\n\nrun cost   : {judge.usage.summary(judge.model)}")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--layer", choices=["classify", "gap"], default="classify")
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument(
        "--model",
        default=None,
        help="the GRADER's model (LiteLLM string). Defaults to AIACT_GRADER_MODEL, and to "
        "AIACT_LLM_MODEL when that is unset — which means the system marks its own work.",
    )
    ap.add_argument("--cases", type=Path, default=Path("data/golden_set/classification_cases.yaml"))
    ap.add_argument("--golden", type=Path, default=Path("data/golden_set/golden_set.json"))
    ap.add_argument("--spec", type=Path, default=Path("data/policy/spec.yaml"))
    args = ap.parse_args()

    load_dotenv()
    grader = ReasoningGrader(model=args.model)
    with trace_run(f"grounding:{args.layer}", session_id=f"grounding-{args.split}"):
        if args.layer == "classify":
            results = grade_classification(grader, args.split, args.cases)
        else:
            results = grade_gap(grader, args.split, args.golden, args.spec)

    print(
        report(
            f"layer={args.layer}  split={args.split}  grader={grader.model}",
            results,
            grades_itself=grader.grades_itself,
        )
    )
    print(f"\ngrader cost: {grader.usage.summary(grader.model)}")
    if args.split != "test":
        print("\n(reminder: this is not a reportable score — only split=test is.)")


if __name__ == "__main__":
    main()
