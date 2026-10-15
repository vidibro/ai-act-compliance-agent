"""Flatten the coverage artifacts into one JSON payload for the coverage map.

Read-only: every value comes from the validated loaders, so the map shows what the build accepts.
Aggregation happens in the browser, so filters (actor, review status, scope) recount without a
round trip.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from aiact.config import get_settings
from aiact.guidance import DEFAULT_GUIDANCE_ROOT
from aiact.guidance_coverage import (
    COVERAGE_FILE,
    PARAGRAPHS_FILE,
    GuidanceCoverage,
    parse_ranges,
)
from aiact.policy_loader import source_body
from aiact.schemas.eval import GoldenSet
from aiact.schemas.norm import NormativeCoverageBundle, SegmentSource, SourceKind
from aiact.schemas.policy import PolicyRule, PolicyRuleset
from aiact.text_segments import group_segments, source_path

GOLDEN_SETS = {
    "dev": Path("data/golden_set/golden_set.json"),
    "heldout": Path("data/golden_set/golden_set_heldout.json"),
}
_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}
_TITLE = re.compile(r"^title:[ \t]*(\S.*?)\s*$", re.M)


def _roman(numeral: str) -> int:
    values = [_ROMAN[c] for c in numeral.upper()]
    return sum(-v if v < nxt else v for v, nxt in zip(values, [*values[1:], 0], strict=True))


def _doc_key(kind: SourceKind | str, number: str) -> str:
    return f"{SourceKind(kind).value}:{number.lstrip('0').lower() or '0'}"


def _order(kind: SourceKind, number: str) -> tuple[int, int, str]:
    if kind is SourceKind.ANNEX:
        return (1, _roman(number), "")
    digits = re.match(r"\d+", number)
    return (0, int(digits.group()) if digits else 0, number)


def _title(source: SegmentSource) -> str:
    settings = get_settings()
    path = source_path(source, settings.policy_articles_path, settings.policy_annexes_path)
    match = _TITLE.search(path.read_text(encoding="utf-8"))
    if match:
        return match.group(1)
    # Annex front matter has an empty title; the heading after "ANNEX N" carries it.
    lines = [line.strip() for line in source_body(path).splitlines() if line.strip()]
    return lines[1] if len(lines) > 1 else ""


def _documents(bundle: NormativeCoverageBundle) -> list[dict[str, Any]]:
    grouped = group_segments(bundle.text_review.segments)
    documents = []
    for (kind, number), segments in sorted(grouped.items(), key=lambda item: _order(*item[0])):
        documents.append(
            {
                "key": _doc_key(kind, number),
                "kind": kind.value,
                "number": number,
                "title": _title(segments[0].source),
                "segments": dict(Counter(segment.disposition.value for segment in segments)),
            }
        )
    return documents


def _norms(bundle: NormativeCoverageBundle) -> list[dict[str, Any]]:
    inventory = bundle.norm_inventory
    segment_doc = {
        segment.segment_id: _doc_key(segment.source.kind, segment.source.document)
        for segment in bundle.text_review.segments
    }
    interpreted = {norm_id for link in inventory.interpretations for norm_id in link.norm_ids}
    norms = []
    for norm in inventory.norms:
        # [] is a universal norm owed by every actor; "none" assigns no actor at all.
        if norm.actors == "none":
            actors = ["(none)"]
        else:
            actors = [actor.actor_ref.value for actor in norm.actors] or ["(everyone)"]
        norms.append(
            {
                "id": norm.norm_id,
                "doc": segment_doc[norm.primary_spans[0]],
                "kind": norm.kind.value,
                "actors": actors,
                "action": norm.action,
                "scope": norm.product_scope.value,
                "mode": norm.implementation_mode.value,
                "verification": norm.verification_mode.value,
                "status": norm.review.status.value,
                "refs": list(norm.implementation_refs),
                "guidance": norm.norm_id in interpreted,
                "regime": norm.temporal_regime_id,
            }
        )
    return norms


def _case_counts() -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {}
    for split, path in GOLDEN_SETS.items():
        golden = GoldenSet.model_validate(json.loads(path.read_text(encoding="utf-8")))
        counts[split] = Counter(
            case.ablated_rule_id for case in golden.cases if case.ablated_rule_id
        )
    return counts


def _applies_from(spec: PolicyRuleset, rule: PolicyRule) -> str | None:
    """When the rule starts to apply, as one short text: a date, or one per Art. 6 route."""
    regime = spec.temporal_regime_for(rule)
    if regime.application_routes:
        return " / ".join(str(item.application_start) for item in regime.application_routes)
    return str(regime.application_start) if regime.application_start else None


def _rules(spec: PolicyRuleset) -> list[dict[str, Any]]:
    cases = _case_counts()
    rules = []
    for rule in spec.rules:
        source = rule.source
        doc = (
            _doc_key(SourceKind.ARTICLE, str(source.article))
            if source.article
            else _doc_key(SourceKind.ANNEX, str(source.annex))
        )
        rules.append(
            {
                "id": rule.rule_id,
                "doc": doc,
                "roles": [str(role) for role in rule.applies_to_role],
                "document_verifiable": rule.document_verifiable,
                "guidance": len(rule.guidance_refs),
                "cases_dev": cases["dev"][rule.rule_id],
                "cases_heldout": cases["heldout"][rule.rule_id],
                "applies_from": _applies_from(spec, rule),
            }
        )
    return rules


def _guidance(root: Path) -> list[dict[str, Any]]:
    documents = []
    for coverage_path in sorted(root.glob(f"*/{COVERAGE_FILE}")):
        folder = coverage_path.parent
        coverage = GuidanceCoverage.model_validate(
            yaml.safe_load(coverage_path.read_text(encoding="utf-8"))
        )
        paragraphs = yaml.safe_load((folder / PARAGRAPHS_FILE).read_text(encoding="utf-8"))
        decisions = Counter(decision.decision.value for decision in coverage.decisions.values())
        documents.append(
            {
                "id": folder.name,
                "document": paragraphs.get("document", folder.name),
                "paragraphs": len(paragraphs["paragraphs"]),
                "awaiting": len(parse_ranges(coverage.awaiting_review)),
                **dict(decisions),
            }
        )
    return documents


def build_coverage_map(
    bundle: NormativeCoverageBundle,
    spec: PolicyRuleset,
    guidance_root: Path = DEFAULT_GUIDANCE_ROOT,
) -> dict[str, Any]:
    return {
        "act_version_date": bundle.norm_inventory.act_version_date.isoformat(),
        "documents": _documents(bundle),
        "norms": _norms(bundle),
        "rules": _rules(spec),
        "guidance": _guidance(guidance_root),
    }
