"""Triage authored norms for semantic-validity review without changing approval state."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from build_normative_coverage import paths_for_version

from aiact.norm_builder import NormSourceRecord, build_artifacts, load_builder_inputs

STRUCTURAL_PREFIX = re.compile(r"^\s*(?:Article\s+\S+\s*)?(?:\d+\.|\([a-z]+\))?\s*", re.I)
LEGAL_EFFECT = re.compile(
    r"\b(?:shall|must|may(?:\s+only)?|is required to|are required to|does not apply|"
    r"is without prejudice|are without prejudice|is deemed|are deemed)\b",
    re.I,
)
CONDITION = re.compile(
    r"\b(?:if|where|when|provided that|subject to|unless|only if|only where|in the event that)\b",
    re.I,
)
EXCEPTION = re.compile(r"\b(?:except|unless|without prejudice|derogation|does not apply)\b", re.I)
DEADLINE = re.compile(
    r"\b(?:by\s+\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|within\s+\d+|no later than|"
    r"without undue delay|immediately|at least\s+\d+)\b",
    re.I,
)


def _semantic_text(record: NormSourceRecord) -> str:
    dumped = record.model_dump(mode="json")
    parts = [
        dumped["action"],
        json.dumps(dumped["conditions"], ensure_ascii=False),
        json.dumps(dumped["exceptions"], ensure_ascii=False),
        json.dumps(dumped["mandatory_content"], ensure_ascii=False),
        json.dumps(dumped["dependencies"], ensure_ascii=False),
    ]
    return " ".join(parts)


def _uncovered_text(text: str, quotes: list[str]) -> str:
    covered = [False] * len(text)
    for quote in quotes:
        start = text.find(quote)
        if start < 0:
            continue
        for index in range(start, start + len(quote)):
            covered[index] = True
    uncovered = "".join(
        character if not covered[index] else " " for index, character in enumerate(text)
    )
    return " ".join(STRUCTURAL_PREFIX.sub("", uncovered).split())


def audit(version: str) -> dict[str, object]:
    paths = paths_for_version(version)
    reviewed, sources = load_builder_inputs(paths)
    text_review, _norms = build_artifacts(reviewed, sources, paths)
    review_segments = text_review["segments"]
    assert isinstance(review_segments, list)
    segments = {str(item["segment_id"]): item for item in review_segments}
    records_by_source: dict[str, list[NormSourceRecord]] = defaultdict(list)
    for record in sources.records:
        records_by_source[f"AIA-TEXT-{record.source}"].append(record)

    candidates: list[dict[str, object]] = []
    for segment_id, segment in segments.items():
        if segment["disposition"] != "normative":
            continue
        records = records_by_source.get(segment_id, [])
        uncovered = _uncovered_text(str(segment["text"]), [record.quote for record in records])
        if uncovered and LEGAL_EFFECT.search(uncovered):
            candidates.append(
                {
                    "target": segment_id,
                    "signals": ["uncovered_legal_effect_text"],
                    "evidence": uncovered,
                }
            )

    for record in sources.records:
        signals = []
        semantic = _semantic_text(record)
        quote = record.quote.lstrip()
        if quote and quote[0].islower() and not record.qualifier_spans:
            signals.append("fragment_without_qualifier_span")
        if (
            CONDITION.search(record.quote)
            and not record.conditions
            and not CONDITION.search(record.action)
        ):
            signals.append("condition_not_structured_or_retained_in_action")
        if (
            EXCEPTION.search(record.quote)
            and not record.exceptions
            and not EXCEPTION.search(semantic)
        ):
            signals.append("exception_not_structured_or_retained")
        if DEADLINE.search(record.quote) and not DEADLINE.search(semantic):
            signals.append("deadline_not_structured_or_retained")
        if signals:
            candidates.append(
                {
                    "target": record.norm_id,
                    "signals": signals,
                    "evidence": record.quote,
                }
            )

    return {
        "status": "triage_only_not_legal_approval",
        "act_version": version,
        "segments_scanned": len(segments),
        "norms_scanned": len(sources.records),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--act-version", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(audit(args.act_version), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
