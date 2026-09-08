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
    assert len(bundle.text_review.segments) == 1505
    assert len(candidates) == 43

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
    closed_by_splitting.add("AIA-TEXT-A060A-P010")
    closed_by_splitting.add("AIA-TEXT-A061-P007")
    closed_by_splitting |= {"AIA-TEXT-A067-P006", "AIA-TEXT-A067-P010"}
    closed_by_splitting |= {"AIA-TEXT-A070-P001", "AIA-TEXT-A070-P003"}
    closed_by_splitting |= {"AIA-TEXT-A071-P001", "AIA-TEXT-A071-P004"}
    closed_by_splitting |= {f"AIA-TEXT-A073-P{p:03}" for p in (7, 8, 10)}
    closed_by_splitting |= {f"AIA-TEXT-A074-P{p:03}" for p in (4, 12, 15)}
    closed_by_splitting |= {"AIA-TEXT-A075-P015", "AIA-TEXT-A075-P021"}
    closed_by_splitting.add("AIA-TEXT-A075C-P018")
    closed_by_splitting.add("AIA-TEXT-A077-P004")
    closed_by_splitting |= {"AIA-TEXT-A078-P008", "AIA-TEXT-A078-P009"}
    closed_by_splitting |= {"AIA-TEXT-A079-P007", "AIA-TEXT-A079-P014"}
    closed_by_splitting.add("AIA-TEXT-A082-P005")
    closed_by_splitting.add("AIA-TEXT-A085-P002")
    closed_by_splitting |= {"AIA-TEXT-A097-P003", "AIA-TEXT-A097-P006"}
    closed_by_splitting.add("AIA-TEXT-A099-P002")
    closed_by_splitting |= {f"AIA-TEXT-A100-P{p:03}" for p in (11, 12, 13)}
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
    assert len(expected_content) == 136
    baseline_content = {norm_id: int(count) for norm_id, count, _ in content_rows}
    baseline_content["AIA-NORM-A005-P2-CONSIDER-IMPACTS"] = 2
    baseline_content["AIA-NORM-A040-P2-RESOURCE-PERFORMANCE-DELIVERABLES"] = 2
    baseline_content.pop("AIA-NORM-A045-P1-INFORM-NOTIFYING-AUTHORITY")
    baseline_content.pop("AIA-NORM-A045-P2-INFORM-OTHER-NOTIFIED-BODIES")
    baseline_content["AIA-NORM-A045-P1-DISCLOSE-ACTIVITIES-ON-REQUEST"] = 2
    baseline_content.pop("AIA-NORM-A046-P2-REFUSAL-RESPONSE")
    baseline_content["AIA-NORM-A050-P2-MARK-DETECT"] = 6
    baseline_content.pop("AIA-NORM-A057-P3A-AI-OFFICE-SANDBOX")
    baseline_content.pop("AIA-NORM-A057-P4-RESOURCE-AND-AUTHORITY-COORDINATION")
    baseline_content["AIA-NORM-A057-P5-CONTROLLED-SANDBOX-LIFECYCLE"] = 4
    baseline_content.pop("AIA-NORM-A057-P7-SANDBOX-EVIDENCE-PACKAGE")
    baseline_content["AIA-NORM-A057-P7-EXIT-REPORT"] = 3
    baseline_content["AIA-NORM-A057-P16-SANDBOX-REPORTING"] = 7
    baseline_content["AIA-NORM-A057-P16-FINAL-SANDBOX-REPORT"] = 7
    baseline_content.pop("AIA-NORM-A059-P1-A-SUBSTANTIAL-PUBLIC-INTEREST")
    baseline_content.pop("AIA-NORM-A060-P4-C-REGISTER-TESTING")
    baseline_content.pop("AIA-NORM-A060-P4-I-CONSENT-OR-SAFEGUARDS")
    baseline_content.pop("AIA-NORM-A060-P7-INCIDENT-RESPONSE")
    baseline_content["AIA-NORM-A060-P4-H-INFORM-AND-AGREE-ROLES"] = 2
    baseline_content["AIA-NORM-A060-P6-CONFER-AND-USE-SURVEILLANCE-POWERS"] = 3
    baseline_content["AIA-NORM-A061-P2-DOCUMENT-AND-COPY-CONSENT"] = 2
    baseline_content.pop("AIA-NORM-A062-P1-MEMBER-STATE-SME-SUPPORT")
    baseline_content.pop("AIA-NORM-A062-P3-AI-OFFICE-SUPPORT")
    baseline_content.pop("AIA-NORM-A065-P8-AI-OFFICE-SECRETARIAT")
    baseline_content.pop("AIA-NORM-A066-BOARD-ADVICE-AND-ASSISTANCE-TASKS")
    baseline_content["AIA-NORM-A066-E-RECOMMENDATION-AND-OPINION-TOPICS"] = 1
    baseline_content.pop("AIA-NORM-A067-P6-RULES-AND-COCHAIRS")
    baseline_content.pop("AIA-NORM-A067-P7-MEETINGS-AND-INVITATIONS")
    baseline_content.pop("AIA-NORM-A067-P10-ANNUAL-PUBLIC-REPORT")
    baseline_content.pop("AIA-NORM-A068-P3-ADVISE-AND-SUPPORT-AI-OFFICE")
    baseline_content.pop("AIA-NORM-A068-P3-A-GPAI-SUPPORT-TASKS")
    baseline_content.pop("AIA-NORM-A068-P4-EXPERT-INTEGRITY-AND-DISCLOSURE")
    baseline_content["AIA-NORM-A070-P1-DESIGNATE-AND-SAFEGUARD-AUTHORITIES"] = 2
    baseline_content["AIA-NORM-A070-P2-AUTHORITY-AND-CONTACT-DISCLOSURES"] = 3
    baseline_content["AIA-NORM-A070-P3-ADEQUATE-RESOURCES-AND-COMPETENCE"] = 4
    baseline_content["AIA-NORM-A070-P3-PERMANENT-EXPERT-PERSONNEL"] = 7
    baseline_content["AIA-NORM-A071-P1-SET-UP-AND-MAINTAIN-DATABASE"] = 2
    baseline_content.pop("AIA-NORM-A071-P4-DATABASE-ACCESS-RULES")
    baseline_content.pop("AIA-NORM-A071-P6-CONTROLLER-AND-OPERATOR-SUPPORT")
    baseline_content["AIA-NORM-A071-P6-OPERATOR-SUPPORT"] = 2
    baseline_content["AIA-NORM-A073-P6-INVESTIGATE-ASSESS-AND-CORRECT"] = 2
    baseline_content["AIA-NORM-A074-P2-ANNUAL-PROHIBITED-PRACTICE-REPORTING"] = 2
    baseline_content["AIA-NORM-A075-P2A-RESPOND-AND-UPDATE"] = 1
    baseline_content["AIA-NORM-A075-P2A-UPDATE-ON-PROCEEDINGS"] = 2
    baseline_content["AIA-NORM-A075A-P3-INFORMATION-REQUEST-CONTENT"] = 3
    baseline_content["AIA-NORM-A075A-P3-SIMPLE-REQUEST-ADDITIONS"] = 2
    baseline_content["AIA-NORM-A075A-P3-DECISION-REQUEST-ADDITIONS"] = 2
    baseline_content["AIA-NORM-A075C-P3-ORDER-COMPLIANCE-MEASURES"] = 2
    baseline_content["AIA-NORM-A075C-P5-PENALTY-PAYMENT-CEILING"] = 4
    baseline_content["AIA-NORM-A077-P2-IDENTIFY-PUBLISH-NOTIFY-AND-UPDATE"] = 2
    baseline_content.pop("AIA-NORM-A078-P3-KEEP-DOCUMENTATION-AND-ENABLE-ACCESS")
    baseline_content["AIA-NORM-A079-P6-NOTIFICATION-CONTENT"] = 9
    baseline_content.pop("AIA-NORM-A092-P1-CONDUCT-GPAI-EVALUATION")
    baseline_content["AIA-NORM-A095-P2-FACILITATE-SPECIFIC-REQUIREMENT-CODES"] = 1
    baseline_content["AIA-NORM-A101-P1-FIX-FINE-AMOUNT"] = 3
    baseline_content["AIA-NORM-ANNEX-VII-QMS-APPLICATION"] = 7
    baseline_content.pop("AIA-NORM-ANNEX-VII-QMS-CHANGE-DECISION")
    baseline_content["AIA-NORM-ANNEX-VII-QMS-CHANGE-NOTIFICATION"] = 2
    baseline_content["AIA-NORM-ANNEX-XI-SECTION-2-ADVERSARIAL-TESTING-AND-ADAPTATIONS"] = 2
    assert baseline_content == expected_content
