"""Schema contract tests.

For each model: one valid instance constructs cleanly, and each validator rejects its invalid
case. Plus an end-to-end multi-use-case system resolving to three different risk classes at once.
"""

from __future__ import annotations

import warnings
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from aiact.schemas import (
    ActorCategory,
    ActorRole,
    AnnexIIIArea,
    Answer,
    CheckType,
    ClassificationEvidence,
    ClassificationResult,
    ComplianceReport,
    DerogationCondition,
    DocumentChunk,
    Finding,
    LegalSource,
    NormActor,
    NormTarget,
    ObligationStatus,
    PolicyRule,
    PolicyRuleset,
    ReportSummary,
    RiskClass,
    SystemUnderReview,
    TargetKind,
    TemporalRegime,
    TemporalStatus,
    UseCaseClassification,
    Verdict,
)

ACT_DATE = date(2024, 7, 12)


def test_norm_actor_uses_one_closed_role_catalogue_and_derives_its_category():
    actor = NormActor(actor_ref=ActorRole.PROVIDER)

    assert actor.category is ActorCategory.SUPPORTED_OPERATOR
    assert ActorRole.COMMISSION.category is ActorCategory.UNION_INSTITUTION_OR_BODY
    with pytest.raises(ValidationError, match="actor_ref"):
        NormActor(actor_ref="provider_or_deployer")
    with pytest.raises(ValidationError, match="category"):
        NormActor(actor_ref="provider", category="supported_operator")


def test_norm_actor_keeps_its_own_legal_basis_segments():
    actor = NormActor(actor_ref="provider", basis_segment_ids=["AIA-TEXT-A015-P1"])

    assert actor.basis_segment_ids == ["AIA-TEXT-A015-P1"]
    with pytest.raises(ValidationError, match="basis_segment_ids"):
        NormActor(
            actor_ref="provider",
            basis_segment_ids=["AIA-TEXT-A015-P1", "AIA-TEXT-A015-P1"],
        )


def test_norm_target_has_a_normalised_kind_and_its_own_evidence_segments():
    target = NormTarget(
        target_ref="high-risk AI system",
        target_kind=TargetKind.AI_SYSTEM,
        basis_segment_ids=["AIA-TEXT-A015-P001"],
    )

    assert target.target_kind is TargetKind.AI_SYSTEM
    assert target.basis_segment_ids == ["AIA-TEXT-A015-P001"]
    with pytest.raises(ValidationError, match="basis_segment_ids"):
        NormTarget(
            target_ref="high-risk AI system",
            basis_segment_ids=["AIA-TEXT-A015-P001", "AIA-TEXT-A015-P001"],
        )


def test_temporal_regime_labels_dates_without_hiding_a_norm():
    regime = TemporalRegime(
        regime_id="AIA-TEMP-ARTICLE-113-DEFAULT",
        application_start=date(2026, 8, 2),
        legal_basis_spans=["AIA-TEXT-A113-P1"],
    )

    assert regime.status_on(date(2026, 8, 1)) is TemporalStatus.UPCOMING
    assert regime.status_on(date(2026, 8, 2)) is TemporalStatus.ACTIVE


def test_temporal_regime_allows_a_deadline_without_making_a_norm_expire():
    regime = TemporalRegime(
        regime_id="AIA-TEMP-A096-P1-G-PUBLISH-DEADLINE",
        deadline=date(2027, 8, 1),
        legal_basis_spans=["AIA-TEXT-A096-P008"],
    )

    assert regime.deadline == date(2027, 8, 1)
    assert regime.status_on(date(2027, 8, 2)) is TemporalStatus.ACTIVE


def test_temporal_regime_preserves_a_relative_deadline_and_trigger():
    regime = TemporalRegime(
        regime_id="AIA-TEMP-A046-P4-OBJECTION-PERIOD",
        relative_deadline={
            "quantity": 15,
            "unit": "calendar_day",
            "trigger": "receipt of the information referred to in paragraph 3",
        },
        legal_basis_spans=["AIA-TEXT-A046-P004"],
    )

    assert regime.relative_deadline is not None
    assert regime.relative_deadline.enacted_period_variants == [
        "within 15 calendar days",
        "within fifteen calendar days",
        "not later than 15 calendar days",
        "not later than fifteen calendar days",
    ]


def test_temporal_regime_allows_a_relative_deadline_without_an_enacted_trigger():
    regime = TemporalRegime(
        regime_id="AIA-TEMP-A075-P3-SUPPLY-INFORMATION-THIRTY-DAYS",
        relative_deadline={"quantity": 30, "unit": "day"},
        legal_basis_spans=["AIA-TEXT-A075-P022"],
    )

    assert regime.relative_deadline is not None
    assert regime.relative_deadline.trigger is None


def test_temporal_regime_preserves_a_qualitative_deadline():
    regime = TemporalRegime(
        regime_id="AIA-TEMP-A005-P3-URGENT-AUTHORISATION-WITHOUT-UNDUE-DELAY",
        qualitative_deadline={"kind": "without_undue_delay"},
        legal_basis_spans=["AIA-TEXT-A005-P028"],
    )

    assert regime.qualitative_deadline is not None
    assert regime.qualitative_deadline.kind.enacted_text == "without undue delay"


def test_temporal_regime_rejects_multiple_deadline_constraints():
    with pytest.raises(ValidationError, match="at most one deadline constraint"):
        TemporalRegime(
            regime_id="AIA-TEMP-INVALID-MULTIPLE-DEADLINES",
            deadline=date(2027, 8, 1),
            relative_deadline={
                "quantity": 15,
                "unit": "calendar_day",
                "trigger": "receipt",
            },
            legal_basis_spans=["AIA-TEXT-A096-P008"],
        )


# --------------------------------------------------------------------------------------
# Builders — small helpers so each test states only what it cares about.
# --------------------------------------------------------------------------------------
def a_source(**overrides) -> LegalSource:
    kwargs = dict(instrument="Regulation (EU) 2024/1689", article=6, act_version_date=ACT_DATE)
    kwargs.update(overrides)
    return LegalSource(**kwargs)


def a_node(value, **overrides) -> Answer:
    kwargs = dict(
        value=value,
        reasoning="decisive fact located in the documentation",
        confidence="high",
        source=a_source(),
    )
    kwargs.update(overrides)
    return Answer(**kwargs)


def an_evidence(**overrides) -> ClassificationEvidence:
    """A triggering provision PLUS the documentation span that triggered it. `**overrides` go to
    the LegalSource, since that is what a test usually varies."""
    return ClassificationEvidence(
        source=a_source(**overrides),
        evidence_quote="the system ranks candidates by predicted job fit",
    )


def a_use_case(**overrides) -> UseCaseClassification:
    kwargs = dict(
        use_case_id="cv_parsing",
        description="extracts structured fields from CVs",
        annex_iii_area=AnnexIIIArea.EMPLOYMENT,
        # Art. 6(3) exempts on both limbs, so a not_high_risk use case must carry both to construct.
        derogation=a_node(DerogationCondition.NARROW_PROCEDURAL_TASK),
        poses_significant_risk=a_node(False),
        risk_class=RiskClass.NOT_HIGH_RISK,
        triggered_by=[an_evidence(annex="III", annex_point="4(a)")],
        reasoning="field extraction only; derogation (a) applies",
        confidence="high",
    )
    kwargs.update(overrides)
    return UseCaseClassification(**kwargs)


def a_rule(**overrides) -> PolicyRule:
    kwargs = dict(
        rule_id="AIA-RULE-HR-A14",
        requirement="High-risk AI systems shall be designed to allow effective human oversight.",
        source=a_source(article=14),
        applies_to_risk_class=[RiskClass.HIGH_RISK],
        applies_to_role=[ActorRole.PROVIDER],
        obligation_status=ObligationStatus.MANDATORY,
        check_type=CheckType.SUBSTANCE,
        evidence_expected="described oversight measures, interface, intervention ability",
        document_verifiable=True,
        status="active",
    )
    kwargs.update(overrides)
    return PolicyRule(**kwargs)


# --------------------------------------------------------------------------------------
# Valid construction of each model.
# --------------------------------------------------------------------------------------
def test_legal_source_requires_act_version_date():
    with pytest.raises(ValidationError):
        LegalSource(instrument="Regulation (EU) 2024/1689", article=6)  # no act_version_date


def test_document_chunk_and_system_valid():
    chunk = DocumentChunk(
        chunk_id="c1", text="…", section="Human oversight", char_start=0, char_end=3
    )
    system = SystemUnderReview(
        system_id="sys-1",
        source_type="technical_documentation",
        raw_text="full document text",
        chunks=[chunk],
    )
    assert system.chunks[0].chunk_id == "c1"


def test_policy_rule_and_spec_valid():
    spec = PolicyRuleset(
        spec_version="0.1.0",
        act_version_date=ACT_DATE,
        source_note="derived from EC Compliance Checker",
        rules=[a_rule()],
    )
    assert spec.rules[0].rule_id == "AIA-RULE-HR-A14"


def test_node_answer_requires_source():
    with pytest.raises(ValidationError):
        Answer(value=True, reasoning="x", confidence="high")  # no source


# --------------------------------------------------------------------------------------
# Validators — each rejects its invalid case.
# --------------------------------------------------------------------------------------
def test_policy_rule_warns_on_substance_but_not_document_verifiable():
    with pytest.warns(UserWarning, match="substance"):
        a_rule(check_type=CheckType.SUBSTANCE, document_verifiable=False)


def test_policy_rule_no_warning_when_consistent():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning fails the test
        a_rule(check_type=CheckType.SUBSTANCE, document_verifiable=True)
        a_rule(check_type=CheckType.PRESENCE, document_verifiable=False)


def test_profiling_carve_back_forbids_derogation():
    with pytest.raises(ValidationError, match="derogation must be None"):
        a_use_case(
            use_case_id="candidate_scoring",
            performs_profiling=a_node(True),
            derogation=a_node(True),
            risk_class=RiskClass.HIGH_RISK,
        )


def test_profiling_carve_back_forces_high_risk():
    # derogation cleared explicitly so the carve-back is what raises: the builder supplies one by
    # default, and profiling-with-a-derogation trips a different validator first.
    with pytest.raises(ValidationError, match="must be high_risk"):
        a_use_case(
            use_case_id="candidate_scoring",
            performs_profiling=a_node(True),
            derogation=None,
            risk_class=RiskClass.NOT_HIGH_RISK,
        )


def test_profiling_carve_back_satisfied():
    uc = a_use_case(
        use_case_id="candidate_scoring",
        description="scores candidate fit",
        performs_profiling=a_node(True),
        derogation=None,
        risk_class=RiskClass.HIGH_RISK,
        reasoning="profiling of natural persons; Art. 6(3) carve-back",
    )
    assert uc.risk_class == RiskClass.HIGH_RISK


def test_finding_gap_requires_reasoning():
    with pytest.raises(ValidationError, match="non-empty reasoning"):
        Finding(
            rule_id="AIA-RULE-HR-A14",
            use_case_id="candidate_scoring",
            role=ActorRole.PROVIDER,
            verdict=Verdict.GAP,
            reasoning="   ",
            citation=a_source(article=14),
            confidence="high",
        )


def test_finding_evidence_quote_length_capped():
    with pytest.raises(ValidationError, match="under 300"):
        Finding(
            rule_id="AIA-RULE-HR-A14",
            use_case_id="candidate_scoring",
            role=ActorRole.PROVIDER,
            verdict=Verdict.PASS,
            evidence_quote="x" * 301,
            reasoning="ok",
            citation=a_source(article=14),
            confidence="high",
        )


# --------------------------------------------------------------------------------------
# End-to-end: multi-use-case system -> three different risk classes at once.
# --------------------------------------------------------------------------------------
def _multi_use_case_report(policy_spec: PolicyRuleset) -> ComplianceReport:
    parser = a_use_case(
        use_case_id="cv_parsing",
        description="extracts structured fields from CVs without evaluating the person",
        risk_class=RiskClass.NOT_HIGH_RISK,
        derogation=a_node(True, source=a_source(article=6, paragraph=3, point="a")),
    )
    scorer = a_use_case(
        use_case_id="candidate_scoring",
        description="produces a candidate fit score used in shortlisting",
        performs_profiling=a_node(True, source=a_source(article=6, paragraph=3)),
        derogation=None,
        risk_class=RiskClass.HIGH_RISK,
        reasoning="profiling of natural persons; always high-risk notwithstanding derogations",
    )
    generator = a_use_case(
        use_case_id="job_ad_generation",
        description="drafts job advert text",
        annex_iii_area=None,
        risk_class=RiskClass.MINIMAL,
        triggered_by=[an_evidence(article=50)],
        reasoning="outside Annex III; Art. 50 transparency applies independently",
    )

    classification = ClassificationResult(
        use_cases=[parser, scorer, generator],
        overall_risk_class=RiskClass.HIGH_RISK,  # most severe across use cases
        reasoning="candidate_scoring performs profiling; drives the overall class to high_risk",
        triggered_by=[an_evidence(article=6, paragraph=3)],
        confidence="high",
    )

    finding = Finding(
        rule_id="AIA-RULE-HR-A14",
        use_case_id="candidate_scoring",
        role=ActorRole.PROVIDER,
        verdict=Verdict.INADEQUATE,
        evidence_quote="We ensure appropriate human oversight of the system.",
        reasoning="asserts oversight but names no measures, interface, or intervention ability",
        citation=a_source(article=14),
        confidence="high",
    )

    return ComplianceReport.model_validate(
        dict(
            system_id="sys-hr-1",
            act_version_date=ACT_DATE,
            spec_version=policy_spec.spec_version,
            generated_at=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
            classification=classification,
            findings=[finding],
            not_document_verifiable={},
            summary=ReportSummary(
                total_applicable=1, passed=0, gaps=0, inadequate=1, needs_review=0
            ),
        ),
        context={"policy_spec": policy_spec},
    )


def test_multi_use_case_three_risk_classes():
    spec = PolicyRuleset(
        spec_version="0.1.0",
        act_version_date=ACT_DATE,
        source_note="derived from EC Compliance Checker",
        rules=[a_rule()],
    )
    report = _multi_use_case_report(spec)

    classes = {uc.use_case_id: uc.risk_class for uc in report.classification.use_cases}
    assert classes == {
        "cv_parsing": RiskClass.NOT_HIGH_RISK,
        "candidate_scoring": RiskClass.HIGH_RISK,
        "job_ad_generation": RiskClass.MINIMAL,
    }
    assert len(set(classes.values())) == 3  # three distinct classes at once
    assert report.classification.overall_risk_class == RiskClass.HIGH_RISK
    assert report.disclaimer.startswith("This report is generated by an automated tool")


def test_report_rejects_finding_with_unknown_use_case():
    spec = PolicyRuleset(
        spec_version="0.1.0",
        act_version_date=ACT_DATE,
        source_note="derived from EC Compliance Checker",
        rules=[a_rule()],
    )
    bad_finding = Finding(
        rule_id="AIA-RULE-HR-A14",
        use_case_id="does_not_exist",
        role=ActorRole.PROVIDER,
        verdict=Verdict.PASS,
        reasoning="ok",
        citation=a_source(article=14),
        confidence="high",
    )
    classification = ClassificationResult(
        use_cases=[a_use_case(use_case_id="cv_parsing")],
        overall_risk_class=RiskClass.NOT_HIGH_RISK,
        reasoning="single use case",
        triggered_by=[an_evidence()],
        confidence="high",
    )
    with pytest.raises(ValidationError, match="unknown use_case_id"):
        ComplianceReport.model_validate(
            dict(
                system_id="sys-1",
                act_version_date=ACT_DATE,
                spec_version="0.1.0",
                generated_at=datetime(2026, 7, 13, tzinfo=UTC),
                classification=classification,
                findings=[bad_finding],
                not_document_verifiable={},
                summary=ReportSummary(
                    total_applicable=1, passed=1, gaps=0, inadequate=0, needs_review=0
                ),
            ),
            context={"policy_spec": spec},
        )


def test_report_rejects_finding_with_unknown_rule_id():
    spec = PolicyRuleset(
        spec_version="0.1.0",
        act_version_date=ACT_DATE,
        source_note="derived from EC Compliance Checker",
        rules=[a_rule(rule_id="AIA-RULE-HR-A14")],
    )
    finding = Finding(
        rule_id="AIA-RULE-HR-A99",  # not in the spec
        use_case_id="cv_parsing",
        role=ActorRole.PROVIDER,
        verdict=Verdict.PASS,
        reasoning="ok",
        citation=a_source(article=14),
        confidence="high",
    )
    classification = ClassificationResult(
        use_cases=[a_use_case(use_case_id="cv_parsing")],
        overall_risk_class=RiskClass.NOT_HIGH_RISK,
        reasoning="single use case",
        triggered_by=[an_evidence()],
        confidence="high",
    )
    with pytest.raises(ValidationError, match="not present in the loaded PolicyRuleset"):
        ComplianceReport.model_validate(
            dict(
                system_id="sys-1",
                act_version_date=ACT_DATE,
                spec_version="0.1.0",
                generated_at=datetime(2026, 7, 13, tzinfo=UTC),
                classification=classification,
                findings=[finding],
                not_document_verifiable={},
                summary=ReportSummary(
                    total_applicable=1, passed=1, gaps=0, inadequate=0, needs_review=0
                ),
            ),
            context={"policy_spec": spec},
        )
