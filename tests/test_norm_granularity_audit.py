"""Snapshot-specific audit reconciliation, separate from the reusable scanner tests."""

import hashlib
import re
from pathlib import Path

from aiact.norm_granularity import scan_granularity
from aiact.norm_loader import load_normative_coverage


def test_pinned_corpus_triage_is_documented_without_mutating_review():
    root = Path(__file__).resolve().parents[1]
    policy = root / "data/policy"
    coverage = policy / "normative-coverage/2026-07-27"
    bundle = load_normative_coverage(
        coverage / "text-review",
        coverage / "norms",
        articles_root=policy / "articles",
        annexes_root=policy / "annexes",
        guidance_root=policy / "guidance",
    )
    before = bundle.model_dump()
    candidates = scan_granularity(bundle)
    assert bundle.model_dump() == before
    assert bundle.validated_documents == 133
    assert len(bundle.text_review.segments) == 1471
    assert len(candidates) == 71

    segments = {s.segment_id: s for s in bundle.text_review.segments}
    for candidate in candidates:
        source = segments[candidate.segment_id]
        assert candidate.source_sha256 == hashlib.sha256(source.text.encode()).hexdigest()
        assert candidate.norm_ids == tuple(source.norm_ids)

    report = (root / "docs/NORMATIVE-COVERAGE-GRANULARITY-AUDIT.md").read_text()
    rows = re.findall(r"^\| (AIA-TEXT-\S+) \| (retain|split|expand) \|", report, re.MULTILINE)
    ids = [segment_id for segment_id, _ in rows]
    assert len(ids) == len(set(ids)), "Document each triage candidate exactly once"
    # Keep the audit baseline: splitting a norm can remove its original scan signal.
    closed_by_splitting = {f"AIA-TEXT-A031-P{p:03}" for p in (5, 6, 7, 11, 12)}
    closed_by_splitting |= {
        f"AIA-TEXT-A057-P{p:03}" for p in (5, 7, 8, 12, 20, 21, 24, 25, 26)
    }
    closed_by_splitting.add("AIA-TEXT-A058-P018")
    closed_by_splitting |= {"AIA-TEXT-A060-P019", "AIA-TEXT-A060-P020"}
    assert set(ids) - closed_by_splitting == {candidate.segment_id for candidate in candidates}

    content_report = (root / "docs/NORMATIVE-COVERAGE-CONTENT-AUDIT.md").read_text()
    content_rows = re.findall(
        r"^\| (AIA-NORM-\S+) \| (\d+) \| (split|expand|existing|no additional finding) \|",
        content_report,
        re.MULTILINE,
    )
    expected_content = {
        norm.norm_id: len(norm.mandatory_content)
        for norm in bundle.norm_inventory.norms
        if norm.mandatory_content
    }
    assert len(content_rows) == 146  # Historical audit baseline.
    assert len(expected_content) == 139
    baseline_content = {norm_id: int(count) for norm_id, count, _ in content_rows}
    # Article 40's example is now nested in its proper deliverable, not a third requirement.
    baseline_content["AIA-NORM-A040-P2-RESOURCE-PERFORMANCE-DELIVERABLES"] = 2
    # Article 45's event lists became alternative conditions, not mandatory content.
    baseline_content.pop("AIA-NORM-A045-P1-INFORM-NOTIFYING-AUTHORITY")
    baseline_content.pop("AIA-NORM-A045-P2-INFORM-OTHER-NOTIFIED-BODIES")
    baseline_content["AIA-NORM-A045-P1-DISCLOSE-ACTIVITIES-ON-REQUEST"] = 2
    # Article 46's stopping and discarding actions are now distinct norms.
    baseline_content.pop("AIA-NORM-A046-P2-REFUSAL-RESPONSE")
    # Article 50 now explicitly carries all three technical-solution consideration factors.
    baseline_content["AIA-NORM-A050-P2-MARK-DETECT"] = 6
    # Article 57 separates powers/actions and the two reporting stages.
    baseline_content.pop("AIA-NORM-A057-P3A-AI-OFFICE-SANDBOX")
    baseline_content.pop("AIA-NORM-A057-P4-RESOURCE-AND-AUTHORITY-COORDINATION")
    baseline_content["AIA-NORM-A057-P5-CONTROLLED-SANDBOX-LIFECYCLE"] = 4
    baseline_content.pop("AIA-NORM-A057-P7-SANDBOX-EVIDENCE-PACKAGE")
    baseline_content["AIA-NORM-A057-P7-EXIT-REPORT"] = 3
    baseline_content["AIA-NORM-A057-P16-SANDBOX-REPORTING"] = 7
    baseline_content["AIA-NORM-A057-P16-FINAL-SANDBOX-REPORT"] = 7
    # Article 59's public-interest areas are alternative eligibility grounds, not a checklist.
    baseline_content.pop("AIA-NORM-A059-P1-A-SUBSTANTIAL-PUBLIC-INTEREST")
    # Article 60's registration routes are mutually exclusive gates, not three cumulative checks;
    # its consent and incident duties are now separate norms instead of content items.
    baseline_content.pop("AIA-NORM-A060-P4-C-REGISTER-TESTING")
    baseline_content.pop("AIA-NORM-A060-P4-I-CONSENT-OR-SAFEGUARDS")
    baseline_content.pop("AIA-NORM-A060-P7-INCIDENT-RESPONSE")
    baseline_content["AIA-NORM-A060-P4-H-INFORM-AND-AGREE-ROLES"] = 2
    baseline_content["AIA-NORM-A060-P6-CONFER-AND-USE-SURVEILLANCE-POWERS"] = 3
    assert baseline_content == expected_content
