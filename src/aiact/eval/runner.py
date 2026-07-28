"""Score a checker against the golden set.

Two numbers matter, and reporting only one of them is how eval harnesses lie:

  CATCH   — on the degraded rule, did the checker return the expected verdict?
            Broken down per AblationType, because the classes are not equally hard: `removed` is
            trivial, `present_but_inadequate` and `distractor` are the ones that separate reading
            from word-matching.

  FALSE POSITIVES — on the rules that were left intact, did the checker leave them alone?
            A checker that flags everything catches every defect and is worthless. Untouched
            rules are scored as seriously as ablated ones.

An aggregate accuracy over both would hide exactly the failure we care about, so we never print
one without the breakdown.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from aiact.schemas.enums import Verdict
from aiact.schemas.eval import AblationType, GoldenCase, GoldenSet
from aiact.schemas.policy import PolicyRule, PolicySpec


class Checker(Protocol):
    name: str

    def check(self, rule: PolicyRule, document: str) -> Verdict: ...


class Result:
    """One rule-level judgement."""

    def __init__(
        self, case: GoldenCase, rule_id: str, expected: Verdict, got: Verdict, is_ablated: bool
    ) -> None:
        self.case = case
        self.rule_id = rule_id
        self.expected = expected
        self.got = got
        self.is_ablated = is_ablated
        self.correct = expected == got

    @property
    def ablation_type(self) -> AblationType:
        return self.case.ablation


def run(
    checker: Checker,
    golden: GoldenSet,
    spec: PolicySpec,
    max_workers: int = 1,
    progress: bool = False,
) -> list[Result]:
    """Score `checker` over every (case, rule) pair.

    `max_workers` > 1 runs the judgements concurrently. They are independent by construction — one
    rule against one document, no shared state and no ordering — so the only thing sequencing buys
    is a slow run: 133 LLM calls at ~15s each is over half an hour of doing nothing in particular.
    Threads (not processes) because the work is entirely waiting on HTTP.

    Results are re-sorted into the input order afterwards, so a concurrent run and a sequential run
    produce the same list. A scorecard that depended on scheduling would be indefensible.

    `progress` writes to stderr, not stdout: a long run with no output is indistinguishable from a
    hung one, and that ambiguity cost half an hour of watching nothing happen.
    """
    rules = {r.rule_id: r for r in spec.rules}
    jobs = [
        (index, case, rule_id, expected)
        for index, (case, rule_id, expected) in enumerate(
            (case, rule_id, expected)
            for case in golden.cases
            for rule_id, expected in case.expected.items()
        )
    ]

    done = 0

    def judge_one(job: tuple[int, GoldenCase, str, Verdict]) -> tuple[int, Result]:
        index, case, rule_id, expected = job
        got = checker.check(rules[rule_id], case.raw_text)
        ablated = rule_id == case.ablated_rule_id
        return index, Result(case, rule_id, expected, got, is_ablated=ablated)

    def tick(result: Result) -> None:
        nonlocal done
        done += 1
        if progress:
            mark = "." if result.correct else "x"
            end = f" {done}/{len(jobs)}\n" if done % 40 == 0 or done == len(jobs) else ""
            print(f"{mark}{end}", end="", file=sys.stderr, flush=True)

    if max_workers <= 1:
        collected = []
        for job in jobs:
            index, result = judge_one(job)
            tick(result)
            collected.append((index, result))
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(judge_one, job) for job in jobs]
            collected = []
            for future in as_completed(futures):
                index, result = future.result()
                tick(result)
                collected.append((index, result))

    return [result for _, result in sorted(collected, key=lambda pair: pair[0])]


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:5.1f}%" if d else "    - "


def report(checker_name: str, results: list[Result]) -> str:
    lines: list[str] = []
    bar = "=" * 74
    lines.append(f"\n{bar}\n  {checker_name}  —  {len(results)} rule-level judgements\n{bar}")

    # --- CATCH: the degraded rule, per ablation type ---
    by_ablation: dict[AblationType, list[Result]] = defaultdict(list)
    for r in results:
        if r.is_ablated:
            by_ablation[r.ablation_type].append(r)

    lines.append("\nCATCH — did it return the expected verdict on the DEGRADED rule?\n")
    lines.append(f"  {'ablation':26} {'n':>3}  {'correct':>8}   expected -> got")
    lines.append(f"  {'-' * 68}")
    for ablation in (
        AblationType.REMOVED,
        AblationType.PRESENT_BUT_INADEQUATE,
        AblationType.DISTRACTOR,
    ):
        rs = by_ablation.get(ablation, [])
        if not rs:
            continue
        ok = sum(r.correct for r in rs)
        got = ", ".join(sorted({f"{r.expected.value}->{r.got.value}" for r in rs}))
        lines.append(f"  {ablation.value:26} {len(rs):>3}  {_pct(ok, len(rs)):>8}   {got}")

    # --- FALSE POSITIVES: rules left intact ---
    intact = [r for r in results if not r.is_ablated]
    fp = [r for r in intact if not r.correct]
    lines.append("\nFALSE POSITIVES — did it leave the UNTOUCHED rules alone?\n")
    lines.append(
        f"  intact judgements: {len(intact)}   "
        f"correct: {_pct(len(intact) - len(fp), len(intact))}"
    )
    if fp:
        for rule_id, expected, got in sorted(
            {(x.rule_id, x.expected.value, x.got.value) for x in fp}
        ):
            lines.append(f"    ! {rule_id}: expected {expected}, got {got}")

    # --- The headline the project actually cares about ---
    inadequate_cases = [r for r in results if r.expected == Verdict.INADEQUATE]
    caught = sum(r.correct for r in inadequate_cases)
    lines.append(
        f"\nINADEQUATE detection (the core capability): "
        f"{caught}/{len(inadequate_cases)}  {_pct(caught, len(inadequate_cases))}"
    )
    emitted = sum(1 for r in results if r.got == Verdict.INADEQUATE)
    lines.append(f"INADEQUATE verdicts emitted at all: {emitted}")

    overall = sum(r.correct for r in results)
    lines.append(
        f"\nOverall (do not read this without the breakdown above): "
        f"{_pct(overall, len(results))}"
    )
    return "\n".join(lines)
