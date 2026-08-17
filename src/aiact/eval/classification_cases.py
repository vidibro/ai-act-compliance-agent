"""Load the Layer 1 (classification) golden set from YAML.

Unlike the Layer 2 set, these cases are authored directly — there is no reference document to
degrade — so the YAML IS the source of truth. This loader just reads it, applies the per-set
`default_split`, and validates each case through ClassificationCase (which re-enforces the
Regulation's own invariants). No LLM, no generation step.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from aiact.classify.graph import route_for
from aiact.eval.node_score import DERIVED_FROM_CLASS, NODE_KEYS
from aiact.guidance import load_snippet
from aiact.schemas.enums import RiskClass
from aiact.schemas.eval import ClassificationCase, ClassificationGoldenSet

DEFAULT_PATH = Path("data/golden_set/classification_cases.yaml")


def load_classification_cases(
    path: str | Path | None = None, guidance_root: str | Path | None = None
) -> ClassificationGoldenSet:
    p = Path(path) if path is not None else DEFAULT_PATH
    if not p.is_file():
        raise FileNotFoundError(f"Classification cases not found at {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))

    default_split = raw.get("default_split", "test")
    cases = [
        ClassificationCase.model_validate({"split": default_split, **entry})
        for entry in raw.get("cases", [])
    ]

    ids = [c.case_id for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"Duplicate case_id(s) in {p}: {sorted(duplicates)}")

    # Every flips_from must name a real sibling — a dangling link is a broken demo.
    known = set(ids)
    for c in cases:
        if c.flips_from is not None and c.flips_from not in known:
            raise ValueError(
                f"{c.case_id}: flips_from={c.flips_from!r} names no case in {p}."
            )

    # Every guidance_ref must resolve to a real, integrity-checked snippet — a label justified by
    # a citation that doesn't exist (or has drifted from its verified text) is worse than none.
    for c in cases:
        for ref in c.guidance_refs:
            try:
                load_snippet(ref, guidance_root)
            except (FileNotFoundError, ValueError) as exc:
                raise ValueError(f"{c.case_id}: guidance_ref {ref!r} — {exc}") from exc

    for c in cases:
        _check_pins_match_the_route(c, p)

    return ClassificationGoldenSet(act_version_date=str(raw["act_version_date"]), cases=cases)


def _check_pins_match_the_route(case: ClassificationCase, path: Path) -> None:
    """A case must pin EXACTLY the nodes its own answers would reach.

    Writing a field means "this question is expected to be asked, and this is the expected answer";
    omitting it means "the cascade is not expected to reach this question at all". Both halves are
    checked, because each failure is a different kind of wrong:

      PINNED BUT UNREACHED   asserts a verdict about a question nobody puts. An out-of-scope case
                             that sets `expected_annex_iii_area: null` is not saying "no Annex III
                             area" — the cascade stops at `scope` — it is filling in a blank.
      REACHED BUT UNPINNED   leaves a question the run WILL ask with nothing to check it against,
                             so the node scores on fewer cases than it runs on and a defect there
                             can hide behind cases that never measured it.

    The route is walked with the cascade's own `_route_*` functions, so the expectation cannot
    drift from the graph. Two fields are exempt from the second half: `expected_prohibited` and
    `expected_scope_exclusion` are fixed by the risk class, so a case need not restate them.
    """
    # `is_ai` has no field in the answer key, so the walk is seeded with the assumption every
    # Layer 1 case makes: the described system IS an AI system. A case that describes something
    # outside Art. 3(1) cannot be expressed here at all — the gap `NODE_KEYS` reports as NO KEY.
    answers: dict[str, object] = {"is_ai": True}
    for node_id, field in NODE_KEYS.items():
        if field is None:
            continue
        if field in DERIVED_FROM_CLASS or field in case.model_fields_set:
            answers[node_id] = getattr(case, field)

    # NEEDS_REVIEW cases are exempt, and the reason is a gap in the answer key rather than a
    # concession. Such a case abstains at ONE node and stops there, so its route is as checkable as
    # any other — but nothing records WHICH node, and it cannot be inferred. The obvious rule, that
    # the first unpinned node is the abstention point, breaks on the two fields DERIVED_FROM_CLASS
    # fills in: a case abstaining at `scope` is indistinguishable from one that answered "no
    # exclusion applies", because the class fixes that value either way. Expressing it needs a field
    # naming the node; until there is one, checking these cases would enforce a route the key cannot
    # state. Tracked in docs/ROADMAP.md.
    if case.expected_risk_class == RiskClass.NEEDS_REVIEW:
        return

    walked = route_for(answers)

    # A missing answer HALTS the walk, so everything past it is unknown rather than unreachable.
    # Reporting the downstream nodes too would tell the author to delete lines that are correct —
    # the fix is the one missing pin, after which the rest of the route resolves.
    if walked and walked[-1] not in answers:
        halted_at = walked[-1]
        raise ValueError(
            f"{case.case_id} in {path}: `{halted_at}` IS reached on this case but "
            f"{NODE_KEYS[halted_at]} is not set — add it. The route past this node cannot be "
            f"determined until it is."
        )

    # `transparency` is asked in `assemble`, which every route reaches, so it is off the walk and
    # always expected — Art. 50 is a separate axis from the tier and is answered for every system.
    reached = set(walked) | {"transparency"}
    problems: list[str] = []
    for node_id, field in NODE_KEYS.items():
        if field is None or field in DERIVED_FROM_CLASS:
            continue
        pinned = field in case.model_fields_set
        if pinned and node_id not in reached:
            problems.append(
                f"{field} is set, but the cascade never reaches `{node_id}` on this case — "
                f"remove the line"
            )
        elif not pinned and node_id in reached:
            problems.append(
                f"`{node_id}` IS reached on this case but {field} is not set — add it"
            )
    if problems:
        raise ValueError(
            f"{case.case_id} in {path}: the pinned answers do not match the route this case "
            f"takes.\n  - " + "\n  - ".join(problems)
        )
