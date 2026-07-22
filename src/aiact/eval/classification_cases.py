"""Load the Layer 1 (classification) golden set from YAML.

Unlike the Layer 2 set, these cases are authored directly — there is no reference document to
degrade — so the YAML IS the source of truth. This loader just reads it, applies the per-set
`default_split`, and validates each case through ClassificationCase (which re-enforces the
Regulation's own invariants). No LLM, no generation step.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from aiact.guidance import load_snippet
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

    return ClassificationGoldenSet(act_version_date=str(raw["act_version_date"]), cases=cases)
