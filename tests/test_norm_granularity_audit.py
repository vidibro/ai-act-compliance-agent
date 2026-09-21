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
    assert len(bundle.text_review.segments) == 1530
    # Count only norms yielded by the segment itself. Qualifier-only links no longer suppress the
    # multiple-modal signal merely because several child norms depend on the same chapeau.
    assert len(candidates) == 56

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
    closed_by_splitting.add("AIA-TEXT-A077-P004")
    closed_by_splitting |= {"AIA-TEXT-A078-P008", "AIA-TEXT-A078-P009"}
    closed_by_splitting |= {"AIA-TEXT-A079-P007", "AIA-TEXT-A079-P014"}
    closed_by_splitting.add("AIA-TEXT-A082-P005")
    closed_by_splitting.add("AIA-TEXT-A085-P002")
    closed_by_splitting |= {"AIA-TEXT-A097-P003", "AIA-TEXT-A097-P006"}
    closed_by_splitting.add("AIA-TEXT-A099-P002")
    closed_by_splitting |= {"AIA-TEXT-ANNEX-VII-I3", "AIA-TEXT-ANNEX-VII-I4"}
    closed_by_splitting |= {f"AIA-TEXT-A100-P{p:03}" for p in (11, 12, 13)}
    # These signals were previously hidden because qualifier links inflated the segment's apparent
    # extraction count. The role split exposes them without changing their reviewed legal content.
    exposed_by_link_role_split = {
        "AIA-TEXT-A006-P019",
        "AIA-TEXT-A009-P002",
        "AIA-TEXT-A010-P002",
        "AIA-TEXT-A014-P003",
        "AIA-TEXT-A025-P001",
        "AIA-TEXT-A025-P012",
        "AIA-TEXT-A049-P004",
        "AIA-TEXT-A050-P5",
        "AIA-TEXT-A052-P007",
        "AIA-TEXT-A060-P008",
        "AIA-TEXT-A073-P010",
        "AIA-TEXT-A075-P015",
        "AIA-TEXT-A085-P002",
    }
    assert (set(ids) - closed_by_splitting) | exposed_by_link_role_split == {
        candidate.segment_id for candidate in candidates
    }

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
    assert len(expected_content) == 179
    baseline_content = {norm_id: int(count) for norm_id, count, _ in content_rows}
    baseline_content["AIA-NORM-A002-P11-MORE-FAVOURABLE-WORKER-RULES"] = 2
    baseline_content["AIA-NORM-A005-P6-PROVIDE-TEMPLATE"] = 2
    baseline_content["AIA-NORM-A006-P5-PROVIDE-GUIDELINES"] = 2
    baseline_content["AIA-NORM-A003-D057-TESTING-IN-REAL-WORLD-CONDITIONS"] = 2
    baseline_content["AIA-NORM-A005-P4-NOTIFICATION-CONTENT"] = 2
    baseline_content["AIA-NORM-A006-P8-NO-REDUCED-PROTECTION"] = 3
    baseline_content["AIA-NORM-A014-P3-COMMENSURATE-MEASURES"] = 2
    baseline_content["AIA-NORM-A043-P3-QMS"] = 2
    baseline_content["AIA-NORM-A047-P2-ANNEX-V-CONTENT"] = 2
    baseline_content["AIA-NORM-A049-P4-SECURE-NON-PUBLIC-SECTION"] = 5
    baseline_content["AIA-NORM-A053-P1-A-DRAW-KEEP-DOCUMENTATION"] = 4
    baseline_content["AIA-NORM-A068-P4-EXPERT-INTEGRITY-AND-DISCLOSURE"] = 2
    baseline_content["AIA-NORM-A078-P2-PROTECT-OBTAINED-DATA"] = 2
    baseline_content["AIA-NORM-A112-P6-SUBMIT-STANDARDISATION-REPORT"] = 2
    baseline_content["AIA-NORM-ANNEX-VII-OVERVIEW-QMS-EXAMINATION"] = 2
    baseline_content.pop("AIA-NORM-A049-P4-RESTRICTED-INFORMATION", None)
    baseline_content.pop("AIA-NORM-A053-P1-A-ANNEX-XI-CONTENT", None)
    # Art. 22(3)'s mandate norm was renamed when its tasks were separated from addressability.
    baseline_content["AIA-NORM-A022-P3-MANDATE-EMPOWER-TASKS"] = 6
    baseline_content["AIA-NORM-A005-P2-CONSIDER-IMPACTS"] = 2
    baseline_content["AIA-NORM-A009-P1-ESTABLISH-IMPLEMENT-DOCUMENT-AND-MAINTAIN"] = 4
    baseline_content["AIA-NORM-A009-P2-LIFECYCLE-PROCESS"] = 2
    baseline_content["AIA-NORM-A009-P5-ACCEPTABLE-RESIDUAL-RISK"] = 2
    baseline_content["AIA-NORM-A009-P6-TEST-PERFORMANCE-AND-COMPLIANCE"] = 2
    baseline_content["AIA-NORM-A010-P3-DATASET-QUALITY"] = 4
    baseline_content["AIA-NORM-A011-P1-DRAW"] = 2
    baseline_content["AIA-NORM-A011-P1-DEMONSTRATE"] = 2
    baseline_content["AIA-NORM-A013-P2-PROVIDE-INSTRUCTIONS"] = 7
    baseline_content["AIA-NORM-A013-P3-B-II-PERFORMANCE-AND-AFFECTING-CIRCUMSTANCES"] = 2
    baseline_content["AIA-NORM-A013-P3-D-HUMAN-OVERSIGHT"] = 2
    baseline_content["AIA-NORM-A013-P3-E-RESOURCES-LIFETIME-AND-MAINTENANCE"] = 3
    baseline_content["AIA-NORM-A015-P1-PERFORMANCE-AND-LIFECYCLE-CONSISTENCY"] = 4
    baseline_content["AIA-NORM-A020-P2-INVESTIGATE-RISK"] = 3
    baseline_content["AIA-NORM-A026-P5-MONITOR"] = 2
    baseline_content["AIA-NORM-A026-P5-RISK-NOTIFY"] = 2
    baseline_content["AIA-NORM-A026-P10-DOCUMENT-EACH-USE"] = 2
    baseline_content["AIA-NORM-A026-P3-PRESERVE-OTHER-OBLIGATIONS"] = 2
    baseline_content["AIA-NORM-A028-P5-NO-CONFORMITY-ACTIVITIES"] = 2
    baseline_content["AIA-NORM-A031-P5-DIRECT-INVOLVEMENT-PROHIBITED"] = 2
    baseline_content.pop("AIA-NORM-A034-P2-PROPORTIONALITY-FACTORS", None)
    baseline_content["AIA-NORM-A034-P2-AVOID-UNNECESSARY-BURDENS"] = 4
    baseline_content["AIA-NORM-A036-P6-PRESERVE-FILES"] = 2
    baseline_content["AIA-NORM-A037-P4-INFORM-NOTIFYING-STATE"] = 2
    baseline_content["AIA-NORM-A041-P6-ASSESS-DEFICIENCY-INFORMATION"] = 2
    baseline_content["AIA-NORM-A047-P1-DRAW-UP-DECLARATION"] = 2
    baseline_content["AIA-NORM-A051-P3-AMEND-THRESHOLDS"] = 2
    baseline_content["AIA-NORM-A040-P2-RESOURCE-PERFORMANCE-DELIVERABLES"] = 2
    baseline_content.pop("AIA-NORM-A045-P1-INFORM-NOTIFYING-AUTHORITY", None)
    baseline_content.pop("AIA-NORM-A045-P2-INFORM-OTHER-NOTIFIED-BODIES", None)
    baseline_content["AIA-NORM-A045-P1-DISCLOSE-ACTIVITIES-ON-REQUEST"] = 2
    baseline_content.pop("AIA-NORM-A046-P2-REFUSAL-RESPONSE", None)
    baseline_content["AIA-NORM-A050-P2-MARK-DETECT"] = 6
    baseline_content["AIA-NORM-A052-P6-PUBLISH-LIST"] = 3
    baseline_content.pop("AIA-NORM-A055-P1-C-REPORT-INCIDENTS", None)
    baseline_content["AIA-NORM-A055-P1-A-EVALUATE-MODEL"] = 2
    baseline_content["AIA-NORM-A055-P1-C-TRACK-DOCUMENT-AND-REPORT-INCIDENTS"] = 2
    baseline_content["AIA-NORM-A056-P4-OBJECTIVES-AND-COMMITMENTS"] = 4
    baseline_content.pop("AIA-NORM-A057-P3A-AI-OFFICE-SANDBOX", None)
    baseline_content.pop("AIA-NORM-A057-P4-RESOURCE-AND-AUTHORITY-COORDINATION", None)
    baseline_content["AIA-NORM-A057-P5-CONTROLLED-SANDBOX-LIFECYCLE"] = 4
    baseline_content.pop("AIA-NORM-A057-P7-SANDBOX-EVIDENCE-PACKAGE", None)
    baseline_content["AIA-NORM-A057-P7-EXIT-REPORT"] = 3
    baseline_content["AIA-NORM-A057-P16-SANDBOX-REPORTING"] = 8
    baseline_content.pop("AIA-NORM-A059-P1-A-SUBSTANTIAL-PUBLIC-INTEREST", None)
    baseline_content.pop("AIA-NORM-A060-P4-C-REGISTER-TESTING", None)
    baseline_content.pop("AIA-NORM-A060-P4-I-CONSENT-OR-SAFEGUARDS", None)
    baseline_content.pop("AIA-NORM-A060-P7-INCIDENT-RESPONSE", None)
    baseline_content["AIA-NORM-A060-P4-H-INFORM-AND-AGREE-ROLES"] = 2
    baseline_content["AIA-NORM-A060-P6-CONFER-AND-USE-SURVEILLANCE-POWERS"] = 3
    baseline_content["AIA-NORM-A060-P5-WITHDRAW-AND-DELETE"] = 2
    baseline_content["AIA-NORM-A060-P7-IMMEDIATE-MITIGATION"] = 2
    baseline_content["AIA-NORM-A060A-P4-COOPERATE-AND-REMOVE-OBSTACLES"] = 2
    baseline_content["AIA-NORM-A061-P2-DOCUMENT-AND-COPY-CONSENT"] = 2
    baseline_content.pop("AIA-NORM-A062-P1-MEMBER-STATE-SME-SUPPORT", None)
    baseline_content.pop("AIA-NORM-A062-P3-AI-OFFICE-SUPPORT", None)
    baseline_content.pop("AIA-NORM-A065-P8-AI-OFFICE-SECRETARIAT", None)
    baseline_content.pop("AIA-NORM-A066-BOARD-ADVICE-AND-ASSISTANCE-TASKS", None)
    baseline_content["AIA-NORM-A066-E-RECOMMENDATION-AND-OPINION-TOPICS"] = 1
    baseline_content.pop("AIA-NORM-A067-P6-RULES-AND-COCHAIRS", None)
    baseline_content.pop("AIA-NORM-A067-P7-MEETINGS-AND-INVITATIONS", None)
    baseline_content.pop("AIA-NORM-A067-P10-ANNUAL-PUBLIC-REPORT", None)
    baseline_content.pop("AIA-NORM-A068-P3-ADVISE-AND-SUPPORT-AI-OFFICE", None)
    baseline_content.pop("AIA-NORM-A068-P3-A-GPAI-SUPPORT-TASKS", None)
    baseline_content["AIA-NORM-A068-P4-EXPERT-INTEGRITY-AND-DISCLOSURE"] = 2
    baseline_content["AIA-NORM-A070-P1-DESIGNATE-AND-SAFEGUARD-AUTHORITIES"] = 2
    baseline_content["AIA-NORM-A070-P2-AUTHORITY-AND-CONTACT-DISCLOSURES"] = 3
    baseline_content["AIA-NORM-A070-P3-ADEQUATE-RESOURCES-AND-COMPETENCE"] = 4
    baseline_content["AIA-NORM-A070-P3-PERMANENT-EXPERT-PERSONNEL"] = 7
    baseline_content["AIA-NORM-A071-P1-SET-UP-AND-MAINTAIN-DATABASE"] = 2
    baseline_content.pop("AIA-NORM-A071-P4-DATABASE-ACCESS-RULES", None)
    baseline_content.pop("AIA-NORM-A071-P6-CONTROLLER-AND-OPERATOR-SUPPORT", None)
    baseline_content["AIA-NORM-A071-P6-OPERATOR-SUPPORT"] = 2
    baseline_content["AIA-NORM-A073-P6-INVESTIGATE"] = 1
    baseline_content["AIA-NORM-A073-P6-RISK-ASSESSMENT-AND-CORRECTIVE-ACTION"] = 2
    baseline_content["AIA-NORM-A073-P8-SEVEN-DAY-AUTHORITY-ACTION"] = 2
    baseline_content["AIA-NORM-A074-P2-ANNUAL-PROHIBITED-PRACTICE-REPORTING"] = 2
    baseline_content.pop("AIA-NORM-A074-P13-GRANT-SOURCE-CODE-ACCESS", None)
    baseline_content["AIA-NORM-A075-P2A-RESPOND-AND-UPDATE"] = 1
    baseline_content["AIA-NORM-A075-P2-COOPERATE-ON-GPAI-SYSTEMS"] = 2
    baseline_content["AIA-NORM-A075-P2A-UPDATE-ON-PROCEEDINGS"] = 2
    baseline_content["AIA-NORM-A075A-P3-INFORMATION-REQUEST-CONTENT"] = 3
    baseline_content["AIA-NORM-A075A-P3-SIMPLE-REQUEST-ADDITIONS"] = 2
    baseline_content["AIA-NORM-A075A-P3-DECISION-REQUEST-ADDITIONS"] = 2
    baseline_content["AIA-NORM-A075C-P3-ORDER-COMPLIANCE-MEASURES"] = 2
    baseline_content["AIA-NORM-A075C-P5-PENALTY-PAYMENT-LIMITS"] = 5
    baseline_content["AIA-NORM-A077-P2-IDENTIFY-PUBLISH-NOTIFY-AND-UPDATE"] = 2
    baseline_content["AIA-NORM-A077-P2-NOTIFY-LIST"] = 2
    baseline_content.pop("AIA-NORM-A078-P3-KEEP-DOCUMENTATION-AND-ENABLE-ACCESS", None)
    baseline_content["AIA-NORM-A079-P6-NOTIFICATION-CONTENT"] = 9
    baseline_content.pop("AIA-NORM-A083-P1-REQUIRE-END-TO-FORMAL-NONCOMPLIANCE", None)
    baseline_content["AIA-NORM-A085-P2-ACCOUNT-FOR-AND-HANDLE-COMPLAINTS"] = 2
    baseline_content.pop("AIA-NORM-A090-P1-ISSUE-QUALIFIED-ALERT", None)
    baseline_content.pop("AIA-NORM-A092-P1-CONDUCT-GPAI-EVALUATION", None)
    baseline_content.pop("AIA-NORM-A093-P1-REQUEST-GPAI-MEASURES", None)
    baseline_content["AIA-NORM-A095-P2-FACILITATE-SPECIFIC-REQUIREMENT-CODES"] = 2
    baseline_content["AIA-NORM-A096-P1-INVOLVE-BOARD"] = 4
    baseline_content.pop("AIA-NORM-A099-P4-OPERATOR-FINE", None)
    # Art. 99(2) became three norms when its deadlines were split, so the single one is gone.
    baseline_content.pop("AIA-NORM-A099-P2-NOTIFY-PENALTY-RULES", None)
    baseline_content["AIA-NORM-A101-P1-FIX-FINE-AMOUNT"] = 3
    baseline_content.pop("AIA-NORM-A101-P1-IMPOSE-GPAI-FINES", None)
    baseline_content["AIA-NORM-ANNEX-VII-QMS-APPLICATION"] = 7
    baseline_content.pop("AIA-NORM-ANNEX-VII-QMS-CHANGE-DECISION", None)
    baseline_content["AIA-NORM-ANNEX-VII-QMS-CHANGE-NOTIFICATION"] = 2
    baseline_content["AIA-NORM-ANNEX-XI-SECTION-2-ADVERSARIAL-TESTING-AND-ADAPTATIONS"] = 2
    assert baseline_content == expected_content
