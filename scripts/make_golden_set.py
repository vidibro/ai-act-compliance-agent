#!/usr/bin/env python3
"""Generate the golden set: degrade the reference document in known ways, emit exact ground truth.

    python scripts/make_golden_set.py                            # dev split
    python scripts/make_golden_set.py --plan ablations-heldout.yaml   # HELD-OUT split

Reads:
    data/golden_set/reference/<reference>.md   — complete, compliant, sections tagged by rule_id
    data/golden_set/<plan>.yaml                — which rule to degrade, how, expected verdict
Writes:
    data/golden_set/cases[-suffix]/<case_id>.md      — the document a checker sees (tags stripped)
    data/golden_set/golden_set[_suffix].json         — GoldenSet: cases + expected verdict per rule

ONE PLAN = ONE REFERENCE DOCUMENT = ONE OUTPUT FILE. That is why the held-out split is a separate
plan rather than more entries here: what a checker overfits is the PROSE of the document it was
tuned against, so the unit that has to be held out is the document. Separate outputs also mean the
dev set cannot pull held-out cases in by accident — see ablations-heldout.yaml.

Why generate rather than hand-write variants: ground truth is then EXACT. We know precisely which
section was removed / hollowed out / swapped for marketing copy, so the expected verdict follows by
construction instead of being one more judgement call nobody can check.

Deterministic: same reference + same plan -> byte-identical output. Standard library + pyyaml only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiact.policy_loader import load_policy_spec  # noqa: E402
from aiact.schemas.enums import Verdict  # noqa: E402
from aiact.schemas.eval import (  # noqa: E402
    AblationType,
    Difficulty,
    GoldenCase,
    GoldenSet,
)

GOLDEN_DIR = Path("data/golden_set")
SPEC_PATH = Path("data/policy/spec.yaml")

# <!-- rule: AIA-HR-A14 --> ... <!-- /rule -->
_SECTION = re.compile(
    r"<!--\s*rule:\s*(?P<rule>[A-Za-z0-9\-]+)\s*-->\n(?P<body>.*?)\n<!--\s*/rule\s*-->\n",
    re.S,
)
_LEADING_COMMENT = re.compile(r"\A<!--.*?^-->\n+", re.S | re.M)

# Expected verdict implied by each ablation type. A case may override via `expect:`.
_EXPECTED: dict[AblationType, Verdict] = {
    AblationType.REMOVED: Verdict.GAP,
    AblationType.PRESENT_BUT_INADEQUATE: Verdict.INADEQUATE,
    AblationType.DISTRACTOR: Verdict.GAP,
    AblationType.UNTOUCHED: Verdict.PASS,
}


def parse_reference(text: str) -> tuple[str, dict[str, str]]:
    """Return (template, {rule_id: section_body}).

    The template keeps a {rule_id} placeholder where each tagged section stood, so a case document
    is rendered by substituting either the original section or its degraded replacement.
    """
    sections: dict[str, str] = {}

    def grab(m: re.Match[str]) -> str:
        rule = m.group("rule")
        sections[rule] = m.group("body").strip("\n")
        return "\x00" + rule + "\x00"

    template = _SECTION.sub(grab, text)
    template = _LEADING_COMMENT.sub("", template)  # drop the authoring note
    return template, sections


def render(template: str, sections: dict[str, str], overrides: dict[str, str | None]) -> str:
    """Render a case document. An override of None removes the section outright."""
    out = template
    for rule, body in sections.items():
        replacement = overrides.get(rule, body) if rule in overrides else body
        marker = "\x00" + rule + "\x00"
        out = out.replace(marker, "" if replacement is None else replacement.strip("\n"))
    # Collapse the blank-line runs a removed section leaves behind.
    return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the golden set from the reference document.")
    ap.add_argument("--golden-dir", type=Path, default=GOLDEN_DIR)
    ap.add_argument("--spec", type=Path, default=SPEC_PATH)
    ap.add_argument(
        "--plan",
        default="ablations.yaml",
        help="ablation plan inside --golden-dir (default: ablations.yaml, the dev split). "
        "Output paths are derived from the plan name, so ablations-heldout.yaml writes "
        "cases-heldout/ and golden_set_heldout.json.",
    )
    args = ap.parse_args()

    plan = yaml.safe_load((args.golden_dir / args.plan).read_text(encoding="utf-8"))
    # "ablations.yaml" -> "", "ablations-heldout.yaml" -> "-heldout". One plan, one reference
    # document, one output file — keeping GoldenSet's "all cases from ONE reference" invariant true.
    variant = Path(args.plan).stem.removeprefix("ablations")
    ref_path = args.golden_dir / "reference" / plan["reference"]
    default_split = plan.get("default_split", "test")
    template, sections = parse_reference(ref_path.read_text(encoding="utf-8"))
    print(f"Reference: {ref_path}  ({len(sections)} tagged rule sections)")

    spec = load_policy_spec(args.spec)
    # The rules a high-risk employment system is actually judged on from its documentation.
    applicable = sorted(
        r.rule_id
        for r in spec.rules
        if r.document_verifiable and "high_risk" in [c.value for c in r.applies_to_risk_class]
    )
    missing = set(applicable) - set(sections)
    if missing:
        sys.exit(f"Reference document has no section for applicable rule(s): {sorted(missing)}")
    print(f"Applicable document-verifiable rules: {len(applicable)} -> {', '.join(applicable)}")

    cases_dir = args.golden_dir / f"cases{variant}"
    cases_dir.mkdir(parents=True, exist_ok=True)
    for stale in cases_dir.glob("*.md"):
        stale.unlink()

    cases: list[GoldenCase] = []
    for entry in plan["cases"]:
        rule_id = entry.get("rule_id")
        ablation = AblationType(entry["ablation"])
        difficulty = Difficulty(entry["difficulty"])
        case_id = f"{rule_id}__{ablation.value}" if rule_id else "pristine__untouched"

        if rule_id is None:
            overrides: dict[str, str | None] = {}
        elif ablation == AblationType.REMOVED:
            overrides = {rule_id: None}
        else:
            replacement = entry.get("replacement")
            if not replacement:
                sys.exit(f"{case_id}: ablation {ablation.value} needs a `replacement`.")
            overrides = {rule_id: replacement}

        doc = render(template, sections, overrides)
        doc_path = cases_dir / f"{case_id}.md"
        doc_path.write_text(doc, encoding="utf-8")

        # Ground truth: the degraded rule gets the ablation's verdict (or an explicit override);
        # every other applicable rule is untouched and must PASS.
        verdict = Verdict(entry["expect"]) if entry.get("expect") else _EXPECTED[ablation]
        expected = {r: Verdict.PASS for r in applicable}
        if rule_id:
            expected[rule_id] = verdict

        split = entry.get("split", default_split)
        cases.append(
            GoldenCase(
                case_id=case_id,
                system_id=plan["system_id"],
                document_path=str(doc_path),
                raw_text=doc,
                ablated_rule_id=rule_id,
                ablation=ablation,
                difficulty=difficulty,
                split=split,
                expected=expected,
            )
        )
        print(f"  + {case_id:45} {rule_id or '-':14} [{split:4}] -> {verdict.value}")

    golden = GoldenSet(
        system_id=plan["system_id"],
        reference_path=str(ref_path),
        act_version_date=spec.act_version_date.isoformat(),
        spec_version=spec.spec_version,
        cases=cases,
    )
    out = args.golden_dir / f"golden_set{variant.replace('-', '_')}.json"
    out.write_text(json.dumps(golden.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    n_dev = sum(c.split == "dev" for c in cases)
    n_test = sum(c.split == "test" for c in cases)
    print(f"\n{len(cases)} cases -> {out}   (dev={n_dev}, test={n_test})")
    print(f"{len(cases) * len(applicable)} rule-level judgements to score.")
    if n_test == 0:
        print("NOTE: this plan is all dev — tunable. The held-out split lives in its own plan.")
    if n_dev == 0:
        print("NOTE: HELD OUT. Do not tune against these. Run once; record the date and git sha.")


if __name__ == "__main__":
    main()
