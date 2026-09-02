"""Granularity signals are reproducible triage, never approval or completeness proof."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aiact.norm_granularity import granularity_signals, scan_granularity
from aiact.norm_loader import load_normative_coverage


@pytest.mark.parametrize(
    ("text", "norm_count", "expected"),
    [
        ("Contents:\n  (a) identity\n  (b) intended purpose", 1, (2, 0, ("internal_list",))),
        ("Contents:\n  1. identity\n  2. purpose", 2, (2, 0, ("internal_list",))),
        ("Shall report. They\nshall cooperate.", 1, (0, 2, ("multiple_modals_single_norm",))),
        ("They shall report and must cooperate.", 2, (0, 2, ())),
        ("They shall report and must cooperate.", 0, (0, 2, ("multiple_modals_single_norm",))),
        (
            "They are\nrequired to report and may only stop later.",
            1,
            (0, 2, ("multiple_modals_single_norm",)),
        ),
        (
            "They shall report unless another body is required to report.",
            1,
            (0, 2, ("multiple_modals_single_norm",)),
        ),
        (
            "It must contain:\n  (a) identity\n  (b) what it shall do",
            1,
            (2, 2, ("internal_list", "multiple_modals_single_norm")),
        ),
        # Absence of a signal does NOT imply absence of multiple legal effects.
        ("Record identity, notify authorities and maintain records.", 1, (0, 0, ())),
        ("A small shallot and a mustache.", 1, (0, 0, ())),
    ],
)
def test_granularity_signals(text, norm_count, expected):
    assert granularity_signals(text, norm_count) == expected


def test_scan_preserves_review_and_reports_source_identity():
    bundle = load_normative_coverage()
    before = bundle.model_dump()
    candidates = scan_granularity(bundle)
    assert bundle.model_dump() == before
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    expected = {
        segment.segment_id
        for segment in bundle.text_review.segments
        if granularity_signals(segment.text, len(segment.norm_ids))[2]
    }
    assert {candidate.segment_id for candidate in candidates} == expected
    assert len(candidates) == len(expected)
    for candidate in candidates:
        source = segments[candidate.segment_id]
        assert candidate.source_sha256 == hashlib.sha256(source.text.encode()).hexdigest()
        assert candidate.norm_ids == tuple(source.norm_ids)
        assert candidate.signals


def test_cli_reports_inventory_without_claiming_approval():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/audit_norm_granularity.py"),
            "--act-version",
            "2026-07-27",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "triage_only_not_legal_approval"
    assert report["act_version"] == "2026-07-27"
    assert report["documents_scanned"] > 0
    assert report["segments_scanned"] >= report["candidate_count"] > 0
    assert report["source_characters_scanned"] > 0
    assert report["candidate_count"] == len(report["candidates"])
    assert report["content_norm_count"] == len(report["content_norms"]) > 0
    assert all(
        norm["content_entries"] > 0 and norm["source_span_ids"] for norm in report["content_norms"]
    )
