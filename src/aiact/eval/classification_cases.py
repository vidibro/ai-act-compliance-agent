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
    answers: dict[str, object] = {}
    for node_id, field in NODE_KEYS.items():
        if field is None:
            continue
        if field in DERIVED_FROM_CLASS or field in case.model_fields_set:
            answers[node_id] = getattr(case, field)

    walked = route_for(answers)

    # A NEEDS_REVIEW case is checked against the node it abstains at, not a terminal: it stops
    # there, so `expected_abstains_at` names the node and the pins are checked around it. The node
    # cannot be inferred as "the first unpinned one", because the fields DERIVED_FROM_CLASS fills in
    # make a case abstaining at `scope` look exactly like one answering "no exclusion applies".
    if case.expected_risk_class == RiskClass.NEEDS_REVIEW:
        node = case.expected_abstains_at
        if node not in walked:
            raise ValueError(
                f"{case.case_id} in {path}: expected_abstains_at={node!r}, but the cascade never "
                f"reaches that node on this case. It runs {' -> '.join(walked)}."
            )
        # Against the CASCADE ORDER, not the walked route: an unpinned abstention node halts the
        # walk, so nothing is ever "after" it there. NODE_KEYS is declared in cascade order, which
        # is what makes the index comparison meaningful. `transparency` is exempt — `assemble` asks
        # it on every route, abstention or not.
        order = [n for n in NODE_KEYS if n != "transparency"]
        past = [
            n
            for n in order[order.index(str(node)) + 1 :]
            if (f := NODE_KEYS.get(n)) and f in case.model_fields_set
        ]
        if past:
            fields = ", ".join(str(NODE_KEYS[n]) for n in past)
            raise ValueError(
                f"{case.case_id} in {path}: abstains at `{node}`, so the cascade stops there — but "
                f"it pins {fields}, stating answers for questions never put. Remove them."
            )
        return

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
