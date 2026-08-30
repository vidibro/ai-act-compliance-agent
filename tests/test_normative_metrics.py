"""Normative-coverage measurements and honest review-boundary checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aiact.norm_loader import load_normative_coverage
from aiact.norm_metrics import measure_normative_coverage
from aiact.text_segments import corpus_documents, group_segments, load_source_body

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def metrics():
    return measure_normative_coverage(load_normative_coverage())


def test_generated_coverage_artifacts_are_reproducible():
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_normative_coverage.py",
            "--act-version",
            "2026-07-27",
            "--check",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_inventory_partitions_the_complete_versioned_corpus(metrics):
    bundle = load_normative_coverage()
    grouped = group_segments(bundle.text_review.segments)
    expected = corpus_documents(
        bundle.text_review.act_version_date,
        ROOT / "data" / "policy" / "articles",
        ROOT / "data" / "policy" / "annexes",
    )

    assert bundle.text_review.corpus_complete is True
    assert set(grouped) == expected
    assert metrics.documents == 133
    assert metrics.documents_with_extracted_norms == 25
    assert metrics.documents_with_review_debt == 112
    assert metrics.exact_source_characters == 394_667
    assert set(metrics.norms_by_document) == {
        "article 2",
        "article 3",
        "article 4",
        "article 4a",
        "article 5",
        "article 6",
        "article 7",
        "article 8",
        "article 9",
        "article 10",
        "article 11",
        "article 12",
        "article 13",
        "article 14",
        "article 15",
        "article 26",
        "article 43",
        "article 50",
        "article 60",
        "article 75",
        "article 113",
        "annex III",
        "annex IV",
        "annex VII",
        "annex VIII",
    }


def test_reviewed_context_only_article_retains_exact_paragraph_partition():
    bundle = load_normative_coverage()
    article_one = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "1"
    ]

    assert len(article_one) == 10
    assert article_one[0].segment_id == "AIA-TEXT-A001-HEAD"
    assert article_one[0].disposition.value == "structural"
    assert article_one[1].segment_id == "AIA-TEXT-A001-P001"
    assert article_one[1].text.startswith("1. The purpose")
    source = load_source_body(
        article_one[0].source,
        ROOT / "data" / "policy" / "articles",
        ROOT / "data" / "policy" / "annexes",
    )
    assert "".join(segment.text for segment in article_one) == source
    assert all(segment.disposition.value == "context_only" for segment in article_one[1:])
    assert all(segment.review.status.value == "approved" for segment in article_one)
    assert all(segment.review.verified_by == "vidibro" for segment in article_one)
    assert all(segment.disposition_reason for segment in article_one[1:])
    assert all(segment.norm_ids == [] for segment in article_one)


def test_article_two_scope_chapeau_qualifies_seven_applicability_norms():
    bundle = load_normative_coverage()
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A002-P1-")
    }

    assert len(norms) == 7
    assert set(segments["AIA-TEXT-A002-P001"].norm_ids) == set(norms)
    for index, norm in enumerate(norms.values(), start=2):
        assert norm.kind.value == "applicability"
        assert norm.primary_spans == [f"AIA-TEXT-A002-P{index:03d}"]
        assert norm.qualifier_spans == ["AIA-TEXT-A002-P001"]
        assert norm.implementation_mode.value == "missing"


def test_article_two_section_b_limit_has_two_applicability_norms():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A002-P009"
    )
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id in segment.norm_ids
    }

    assert segment.disposition.value == "normative"
    assert set(norms) == {
        "AIA-NORM-A002-P2-SECTION-B-LIMIT",
        "AIA-NORM-A002-P2-INTEGRATED-SANDBOX-PROVISIONS",
    }
    assert all(norm.kind.value == "applicability" for norm in norms.values())
    assert all(norm.primary_spans == [segment.segment_id] for norm in norms.values())
    assert all(norm.implementation_mode.value == "missing" for norm in norms.values())


def test_article_two_competence_limits_require_no_product_action():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A002-P010"
    )
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id in segment.norm_ids
    ]

    assert segment.disposition.value == "normative"
    assert {norm.norm_id for norm in norms} == {
        "AIA-NORM-A002-P3-OUTSIDE-UNION-LAW",
        "AIA-NORM-A002-P3-NATIONAL-SECURITY-COMPETENCE",
    }
    assert all(norm.product_scope.value == "no_product_action" for norm in norms)
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)
    assert all(norm.verification_mode.value == "not_assessed" for norm in norms)


def test_article_two_military_exclusion_remains_implementation_debt():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A002-P011"
    )
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A002-P3-MILITARY-EXCLUSION"
    )

    assert segment.disposition.value == "normative"
    assert segment.norm_ids == [norm.norm_id]
    assert norm.kind.value == "applicability"
    assert norm.product_scope.value == "in_scope"
    assert norm.implementation_mode.value == "missing"
    assert norm.verification_mode.value == "unresolved"


def test_article_two_military_output_exclusion_remains_separate_norm():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A002-P012"
    )
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A002-P3-MILITARY-OUTPUT-EXCLUSION"
    )

    assert segment.disposition.value == "normative"
    assert segment.norm_ids == [norm.norm_id]
    assert norm.kind.value == "applicability"
    assert norm.product_scope.value == "in_scope"
    assert norm.implementation_mode.value == "missing"
    assert norm.verification_mode.value == "unresolved"


def test_article_two_international_cooperation_exclusion_is_in_scope():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A002-P013"
    )
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A002-P4-INTERNATIONAL-COOPERATION-EXCLUSION"
    )

    assert segment.disposition.value == "normative"
    assert segment.norm_ids == [norm.norm_id]
    assert norm.kind.value == "applicability"
    assert norm.product_scope.value == "in_scope"
    assert norm.implementation_mode.value == "missing"
    assert norm.verification_mode.value == "unresolved"


def test_article_two_intermediary_liability_saving_clause_needs_no_product_action():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A002-P014"
    )
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A002-P5-INTERMEDIARY-LIABILITY-SAVING"
    )

    assert segment.disposition.value == "normative"
    assert segment.norm_ids == [norm.norm_id]
    assert norm.kind.value == "applicability"
    assert norm.product_scope.value == "no_product_action"
    assert norm.implementation_mode.value == "none_required"
    assert norm.verification_mode.value == "not_assessed"
    assert norm.dependencies[0].dependency_ref == "Regulation (EU) 2022/2065, Chapter II"


def test_article_two_is_fully_reviewed_as_twenty_eight_atomic_norms():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "2"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A002-")
    ]

    assert len(segments) == 26
    assert segments[0].disposition.value == "structural"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 28


def test_article_two_paragraph_thirteen_uses_two_cumulative_qualifier_spans():
    bundle = load_normative_coverage()
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A002-P13-LIMIT-HIGH-RISK-REQUIREMENTS"
    )

    assert norm.primary_spans == ["AIA-TEXT-A002-P022"]
    assert norm.qualifier_spans == ["AIA-TEXT-A002-P023", "AIA-TEXT-A002-P024"]
    assert len(norm.conditions) == 2
    for segment_id in [*norm.primary_spans, *norm.qualifier_spans]:
        assert segments[segment_id].norm_ids == [norm.norm_id]


def test_article_two_commission_delegated_act_has_deadline_and_four_contents():
    bundle = load_normative_coverage()
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A002-P13-COMMISSION-DELEGATED-ACTS"
    )

    assert norm.kind.value == "obligation"
    assert "2 August 2027" in norm.norm_text
    assert len(norm.mandatory_content) == 4
    assert norm.product_scope.value == "no_product_action"
    assert norm.implementation_mode.value == "none_required"


def test_article_three_is_fully_reviewed_as_definitions_and_embedded_consequences():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "3"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A003-")
    ]

    assert len(segments) == 83
    assert segments[0].disposition.value == "structural"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 73
    assert sum(norm.kind.value == "definition" for norm in norms) == 70
    assert sum(norm.kind.value == "legal_consequence" for norm in norms) == 3
    definition_norms = [norm for norm in norms if norm.kind.value == "definition"]
    assert all(norm.product_scope.value == "dependency_only" for norm in definition_norms)
    assert all(norm.implementation_mode.value == "none_required" for norm in definition_norms)


def test_article_three_chapeau_and_nested_lists_are_qualifier_spans():
    bundle = load_normative_coverage()
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    definitions = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A003-") and norm.kind.value == "definition"
    }

    assert set(segments["AIA-TEXT-A003-P001"].norm_ids) == set(definitions)
    assert all("AIA-TEXT-A003-P001" in norm.qualifier_spans for norm in definitions.values())
    assert definitions["AIA-NORM-A003-D045-LAW-ENFORCEMENT-AUTHORITY"].qualifier_spans == [
        "AIA-TEXT-A003-P001",
        "AIA-TEXT-A003-P049",
        "AIA-TEXT-A003-P050",
    ]
    assert definitions["AIA-NORM-A003-D049-SERIOUS-INCIDENT"].qualifier_spans == [
        "AIA-TEXT-A003-P001",
        "AIA-TEXT-A003-P055",
        "AIA-TEXT-A003-P056",
        "AIA-TEXT-A003-P057",
        "AIA-TEXT-A003-P058",
    ]
    assert definitions["AIA-NORM-A003-D061-WIDESPREAD-INFRINGEMENT"].qualifier_spans == [
        "AIA-TEXT-A003-P001",
        "AIA-TEXT-A003-P071",
        "AIA-TEXT-A003-P072",
        "AIA-TEXT-A003-P073",
        "AIA-TEXT-A003-P074",
        "AIA-TEXT-A003-P075",
    ]


def test_article_three_preserves_embedded_reference_and_market_consequences():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A003-")
    }

    expected = {
        "AIA-NORM-A003-D047-AI-OFFICE-REFERENCE",
        "AIA-NORM-A003-D048-EDPS-REFERENCE",
        "AIA-NORM-A003-D057-REAL-WORLD-TESTING-NON-MARKET-EFFECT",
    }
    assert expected <= set(norms)
    for norm_id in expected:
        norm = norms[norm_id]
        assert norm.kind.value == "legal_consequence"
        assert norm.product_scope.value == "dependency_only"
        assert norm.implementation_mode.value == "none_required"


def test_article_four_is_fully_reviewed_as_four_atomic_obligations():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "4"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A004-")
    }

    assert len(segments) == 4
    assert segments[0].disposition.value == "structural"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 4
    assert all(norm.kind.value == "obligation" for norm in norms.values())


def test_article_four_literacy_norm_keeps_context_and_individual_guarantee_limit():
    bundle = load_normative_coverage()
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A004-P1-AI-LITERACY-MEASURES"
    )

    assert norm.subjects[0].subject_ref == "provider_or_deployer"
    assert norm.product_scope.value == "in_scope"
    assert norm.implementation_mode.value == "missing"
    assert len(norm.conditions) == 3
    assert norm.exceptions == [
        "the obligation does not require a guaranteed specific AI-literacy level for any "
        "particular individual among the covered staff or other persons"
    ]


def test_article_four_institutional_norms_are_outside_supported_actor_scope():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A004-P2-")
        or norm.norm_id == "AIA-NORM-A004-P3-BOARD-RECOMMENDATIONS"
    ]

    assert len(norms) == 3
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)


def test_article_four_a_is_fully_reviewed_as_permissions_safeguards_and_consequence():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "4a"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A004A-")
    ]

    assert len(segments) == 12
    assert segments[0].disposition.value == "structural"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 8
    assert sum(norm.kind.value == "permission" for norm in norms) == 2
    assert sum(norm.kind.value == "obligation" for norm in norms) == 5
    assert sum(norm.kind.value == "legal_consequence" for norm in norms) == 1


def test_article_four_a_high_risk_permission_carries_all_six_qualifier_spans():
    bundle = load_normative_coverage()
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING"
    )

    assert norm.kind.value == "permission"
    assert norm.qualifier_spans == [
        "AIA-TEXT-A004A-P002",
        "AIA-TEXT-A004A-P003",
        "AIA-TEXT-A004A-P004",
        "AIA-TEXT-A004A-P005",
        "AIA-TEXT-A004A-P006",
        "AIA-TEXT-A004A-P007",
    ]
    assert len(norm.conditions) == 4
    assert norm.product_scope.value == "in_scope"
    assert norm.implementation_mode.value == "missing"


def test_article_four_a_second_permission_imports_safeguards_without_creating_bias_duty():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A004A-")
    }
    permission = norms["AIA-NORM-A004A-P2-OTHER-SYSTEM-BIAS-DATA-PROCESSING"]
    consequence = norms["AIA-NORM-A004A-P2-NO-BIAS-DETECTION-DUTY"]

    assert permission.qualifier_spans == [
        "AIA-TEXT-A004A-P009",
        "AIA-TEXT-A004A-P010",
    ]
    imported = {
        dependency.dependency_ref
        for dependency in permission.dependencies
        if dependency.dependency_ref.startswith("AIA-NORM-A004A-P1-")
    }
    assert imported == {
        "AIA-NORM-A004A-P1-B-REUSE-SECURITY",
        "AIA-NORM-A004A-P1-C-ACCESS-SAFEGUARDS",
        "AIA-NORM-A004A-P1-D-NO-THIRD-PARTY-ACCESS",
        "AIA-NORM-A004A-P1-E-DELETE-DATA",
        "AIA-NORM-A004A-P1-F-RECORD-NECESSITY",
    }
    assert consequence.kind.value == "legal_consequence"
    assert consequence.product_scope.value == "dependency_only"
    assert consequence.implementation_mode.value == "none_required"


def test_article_five_is_fully_approved():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "5"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A005-")
    ]

    assert len(segments) == 35
    assert segments[0].disposition.value == "structural"
    assert segments[0].review.status.value == "proposed"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments[1:])
    assert all(segment.review.verified_by == "vidibro" for segment in segments[1:])
    assert len(norms) == 40
    assert sum(norm.kind.value == "obligation" for norm in norms) == 18
    assert sum(norm.kind.value == "prohibition" for norm in norms) == 13
    assert sum(norm.kind.value == "applicability" for norm in norms) == 2
    assert sum(norm.kind.value == "legal_consequence" for norm in norms) == 3
    assert sum(norm.kind.value == "permission" for norm in norms) == 1
    assert sum(norm.kind.value == "power" for norm in norms) == 3


def test_article_five_paragraph_one_chapeau_carries_ten_prohibitions():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A005-P001"
    )
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id in segment.norm_ids
    }

    assert len(norms) == 10
    assert all(norm.kind.value == "prohibition" for norm in norms.values())
    assert all(norm.qualifier_spans[0] == segment.segment_id for norm in norms.values())


def test_article_five_social_scoring_and_rbi_lists_remain_qualifier_spans():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    assert norms["AIA-NORM-A005-P1-C-SOCIAL-SCORING"].qualifier_spans == [
        "AIA-TEXT-A005-P001",
        "AIA-TEXT-A005-P007",
        "AIA-TEXT-A005-P008",
    ]
    assert norms["AIA-NORM-A005-P1-H-REAL-TIME-RBI"].qualifier_spans == [
        "AIA-TEXT-A005-P001",
        "AIA-TEXT-A005-P014",
        "AIA-TEXT-A005-P015",
        "AIA-TEXT-A005-P016",
    ]


def test_article_five_one_a_and_one_b_narrow_the_new_content_prohibitions():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    market_scope = norms["AIA-NORM-A005-P1A-MARKET-SERVICE-SCOPE"]
    use_scope = norms["AIA-NORM-A005-P1A-DEPLOYER-USE-SCOPE"]
    non_manipulation = norms["AIA-NORM-A005-P1B-NON-MANIPULATION"]

    assert market_scope.qualifier_spans == [
        "AIA-TEXT-A005-P018",
        "AIA-TEXT-A005-P020",
        "AIA-TEXT-A005-P021",
    ]
    assert use_scope.qualifier_spans == ["AIA-TEXT-A005-P018"]
    assert market_scope.kind.value == "applicability"
    assert use_scope.kind.value == "applicability"
    assert non_manipulation.kind.value == "legal_consequence"
    assert non_manipulation.product_scope.value == "in_scope"


def test_article_six_is_fully_approved_and_atomically_classified():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "6"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A006-")
    ]

    assert len(segments) == 20
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 17
    assert sum(norm.kind.value == "applicability" for norm in norms) == 7
    assert sum(norm.kind.value == "obligation" for norm in norms) == 8
    assert sum(norm.kind.value == "power" for norm in norms) == 1
    assert sum(norm.kind.value == "prohibition" for norm in norms) == 1


def test_annex_three_supplies_twenty_five_article_six_classification_routes():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "annex" and segment.source.document == "III"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-III-")
    ]

    assert len(segments) == 34
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 25
    assert all(norm.kind.value == "applicability" for norm in norms)
    assert all(
        any(
            dependency.dependency_ref == "AIA-NORM-A006-P2-ANNEX-III-HIGH-RISK"
            for dependency in norm.dependencies
        )
        for norm in norms
    )


def test_article_seven_constrains_annex_three_amendment_powers():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "7"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A007-")
    }

    assert len(segments) == 21
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 4
    assert sum(norm.kind.value == "power" for norm in norms.values()) == 2
    assert norms["AIA-NORM-A007-P2-CONSIDER-RISK-CRITERIA"].kind.value == "obligation"
    assert (
        norms["AIA-NORM-A007-P2-ADVERSE-OUTCOME-NOT-REVERSIBLE"].kind.value
        == "legal_consequence"
    )


def test_article_eight_links_product_compliance_without_overclaiming_carriers():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "8"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A008-")
    }

    assert len(segments) == 3
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 4
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 3
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1
    assert norms["AIA-NORM-A008-P1-COMPLY-SECTION-REQUIREMENTS"].implementation_mode.value == (
        "unresolved"
    )
    assert norms["AIA-NORM-A008-P2-ENSURE-PRODUCT-COMPLIANCE"].implementation_refs == [
        "AIA-PO-A08-2"
    ]


def test_article_nine_is_atomic_and_mapped_to_the_risk_management_rule():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "9"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A009-")
    ]

    assert len(segments) == 20
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 30
    assert sum(norm.kind.value == "obligation" for norm in norms) == 27
    assert sum(norm.kind.value == "permission" for norm in norms) == 2
    assert sum(norm.kind.value == "applicability" for norm in norms) == 1
    assert all(norm.implementation_refs == ["AIA-HR-A09"] for norm in norms)


def test_article_ten_covers_dataset_quality_and_reuses_article_4a_safeguards():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "10"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A010-")
    }

    assert len(segments) == 21
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 24
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 21
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 2
    assert sum(norm.kind.value == "applicability" for norm in norms.values()) == 1

    carried_by = {
        "AIA-NORM-A010-P5-SPECIAL-CATEGORY-PROCESSING": (
            "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING"
        ),
        "AIA-NORM-A010-P5-B-REUSE-SECURITY": "AIA-NORM-A004A-P1-B-REUSE-SECURITY",
        "AIA-NORM-A010-P5-C-ACCESS-SAFEGUARDS": (
            "AIA-NORM-A004A-P1-C-ACCESS-SAFEGUARDS"
        ),
        "AIA-NORM-A010-P5-D-NO-THIRD-PARTY-ACCESS": (
            "AIA-NORM-A004A-P1-D-NO-THIRD-PARTY-ACCESS"
        ),
        "AIA-NORM-A010-P5-E-DELETE-DATA": "AIA-NORM-A004A-P1-E-DELETE-DATA",
        "AIA-NORM-A010-P5-F-RECORD-NECESSITY": (
            "AIA-NORM-A004A-P1-F-RECORD-NECESSITY"
        ),
    }
    for norm_id, carrier_id in carried_by.items():
        norm = norms[norm_id]
        assert norm.implementation_mode.value == "carried_by_other_norm"
        assert norm.carried_by_norm_ids == [carrier_id]

    uniquely_implemented = set(norms) - set(carried_by)
    assert all(
        norms[norm_id].implementation_refs == ["AIA-HR-A10"]
        for norm_id in uniquely_implemented
    )


def test_article_eleven_separates_documentation_content_and_assessment_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "11"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A011-")
    }

    assert len(segments) == 4
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 11
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 9
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1
    assert sum(norm.kind.value == "power" for norm in norms.values()) == 1

    demonstrate = norms["AIA-NORM-A011-P1-DEMONSTRATE"]
    assessment = norms["AIA-NORM-A011-P1-ASSESSMENT-INFORMATION"]
    assert demonstrate.primary_spans == assessment.primary_spans == ["AIA-TEXT-A011-P1"]

    single_set = norms["AIA-NORM-A011-P2-SINGLE-DOCUMENTATION-SET"]
    assert single_set.primary_spans == ["AIA-TEXT-A011-P2"]
    assert single_set.implementation_refs == ["AIA-HR-A11"]
    assert len(single_set.dependencies) == 2


def test_article_twelve_separates_general_and_biometric_logging_requirements():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "12"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A012-")
    }

    assert len(segments) == 11
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 8
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    general = {norm_id for norm_id in norms if "-P1-" in norm_id or "-P2-" in norm_id}
    biometric = set(norms) - general
    assert len(general) == 4
    assert len(biometric) == 4
    assert all(norms[norm_id].implementation_refs == ["AIA-HR-A12"] for norm_id in general)
    assert all(
        norms[norm_id].implementation_refs == ["AIA-HR-A12-3"]
        for norm_id in biometric
    )
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A012-P002"]
        for norm_id in general
        if "-P2-" in norm_id
    )
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A012-P006"]
        for norm_id in biometric
    )


def test_article_thirteen_keeps_instruction_qualities_and_contents_atomic():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "13"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A013-")
    }

    assert len(segments) == 17
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 27
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    transparency = {norm_id for norm_id in norms if "-P1-" in norm_id or "-P2-" in norm_id}
    contents = set(norms) - transparency
    assert len(transparency) == 10
    assert len(contents) == 17
    assert all(
        norms[norm_id].implementation_refs == ["AIA-HR-A13"]
        for norm_id in transparency
    )
    assert all(
        norms[norm_id].implementation_refs == ["AIA-HR-A13-3"]
        for norm_id in contents
    )
    assert all("AIA-TEXT-A013-P003" in norms[norm_id].qualifier_spans for norm_id in contents)
    nested_characteristics = {
        norm_id for norm_id in contents if "-P3-B-" in norm_id and "CHARACTERISTICS" not in norm_id
    }
    assert len(nested_characteristics) == 8
    assert all(
        "AIA-TEXT-A013-P005" in norms[norm_id].qualifier_spans
        for norm_id in nested_characteristics
    )


def test_article_fourteen_models_oversight_capabilities_and_alternative_routes():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "14"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A014-")
    }

    assert len(segments) == 14
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 14
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 13
    assert sum(norm.kind.value == "applicability" for norm in norms.values()) == 1
    assert all(norm.implementation_refs == ["AIA-HR-A14"] for norm in norms.values())

    route = norms["AIA-NORM-A014-P3-MEASURE-ROUTES"]
    assert route.qualifier_spans == ["AIA-TEXT-A014-P004", "AIA-TEXT-A014-P005"]
    capabilities = [norm for norm_id, norm in norms.items() if "-P4-" in norm_id]
    assert len(capabilities) == 8
    assert all(norm.qualifier_spans == ["AIA-TEXT-A014-P006"] for norm in capabilities)
    exception = norms["AIA-NORM-A014-P5-DISPROPORTIONATE-EXCEPTION"]
    assert exception.verification_mode.value == "reported_conditionally"
    assert len(exception.conditions) == 2


def test_article_fifteen_combines_each_threat_with_the_full_mitigation_cycle():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "15"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A015-")
    }

    assert len(segments) == 10
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 20
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 19
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1

    commission = norms["AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"]
    assert commission.implementation_mode.value == "none_required"
    provider_norms = set(norms) - {commission.norm_id}
    assert all(
        norms[norm_id].implementation_refs == ["AIA-HR-A15"]
        for norm_id in provider_norms
    )

    threats = {
        "AIA-NORM-A015-P5-DATA-POISONING",
        "AIA-NORM-A015-P5-MODEL-POISONING",
        "AIA-NORM-A015-P5-ADVERSARIAL-ATTACKS",
        "AIA-NORM-A015-P5-CONFIDENTIALITY-ATTACKS",
        "AIA-NORM-A015-P5-MODEL-FLAWS",
    }
    assert all(
        all(
            term in norms[norm_id].action
            for term in ("prevent", "detect", "respond", "resolve", "control")
        )
        for norm_id in threats
    )
    assert all(len(norms[norm_id].conditions) == 1 for norm_id in threats)


def test_inventory_cannot_be_misreported_as_independently_approved(metrics):
    assert metrics.approved_characters == 80_895
    assert metrics.needs_review_characters == 270_823
    assert metrics.review_statuses == {
        "approved": 344,
        "needs_review": 930,
        "proposed": 565,
    }
    assert metrics.timed_review_records == 0
    assert metrics.total_review_records == 1840


def test_semantic_pass_finds_propositions_a_shall_scan_misses(metrics):
    assert metrics.shall_vs_semantic_disagreements == 223
    assert metrics.shall_token_candidate_recall == pytest.approx(187 / 410)
    assert "AIA-NORM-A011-P1-SIMPLIFY" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A043-P5-AMEND" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A060-P4-PERMISSION" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A075-P1E-WITHDRAW" in metrics.semantic_norms_without_shall_token


def test_metrics_expose_many_to_many_and_implementation_debt(metrics):
    assert metrics.normative_segments_with_multiple_norms == 96
    assert metrics.mapping_shape.one_norm_to_one_target == 3
    assert metrics.mapping_shape.many_norms_to_one_target == 147
    assert metrics.mapping_shape.many_to_many == 8
    assert metrics.mapping_shape.unmapped == 252
    assert metrics.semantic_vs_existing_implementation_disagreements == 103
    assert metrics.semantic_norms_without_existing_implementation == [
        "AIA-NORM-A002-P1-A-PROVIDER",
        "AIA-NORM-A002-P1-B-DEPLOYER",
        "AIA-NORM-A002-P1-C-THIRD-COUNTRY-OUTPUT",
        "AIA-NORM-A002-P1-D-IMPORT-DISTRIBUTE",
        "AIA-NORM-A002-P1-E-PRODUCT-MANUFACTURER",
        "AIA-NORM-A002-P1-F-AUTHORISED-REPRESENTATIVE",
        "AIA-NORM-A002-P1-G-AFFECTED-PERSON",
        "AIA-NORM-A002-P10-PERSONAL-USE-DEPLOYER-EXCLUSION",
        "AIA-NORM-A002-P12-OPEN-SOURCE-AI-SYSTEM-EXCLUSION",
        "AIA-NORM-A002-P13-LIMIT-HIGH-RISK-REQUIREMENTS",
        "AIA-NORM-A002-P2-INTEGRATED-SANDBOX-PROVISIONS",
        "AIA-NORM-A002-P2-SECTION-B-LIMIT",
        "AIA-NORM-A002-P3-MILITARY-EXCLUSION",
        "AIA-NORM-A002-P3-MILITARY-OUTPUT-EXCLUSION",
        "AIA-NORM-A002-P4-INTERNATIONAL-COOPERATION-EXCLUSION",
        "AIA-NORM-A002-P6-SCIENTIFIC-RD-EXCLUSION",
        "AIA-NORM-A002-P8-PRE-MARKET-RD-EXCLUSION",
        "AIA-NORM-A002-P8-REAL-WORLD-TESTING-CARVEOUT",
        "AIA-NORM-A004-P1-AI-LITERACY-MEASURES",
        "AIA-NORM-A004A-P1-B-REUSE-SECURITY",
        "AIA-NORM-A004A-P1-C-ACCESS-SAFEGUARDS",
        "AIA-NORM-A004A-P1-D-NO-THIRD-PARTY-ACCESS",
        "AIA-NORM-A004A-P1-E-DELETE-DATA",
        "AIA-NORM-A004A-P1-F-RECORD-NECESSITY",
        "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING",
        "AIA-NORM-A004A-P2-OTHER-SYSTEM-BIAS-DATA-PROCESSING",
        "AIA-NORM-A005-P1-A-MANIPULATIVE-TECHNIQUES",
        "AIA-NORM-A005-P1-B-VULNERABILITY-EXPLOITATION",
        "AIA-NORM-A005-P1-BA-NONCONSENSUAL-INTIMATE-MATERIAL",
        "AIA-NORM-A005-P1-BB-DIRECTIVE-MATERIAL",
        "AIA-NORM-A005-P1-C-SOCIAL-SCORING",
        "AIA-NORM-A005-P1-D-CRIMINAL-RISK-PROFILING",
        "AIA-NORM-A005-P1-E-UNTARGETED-FACIAL-SCRAPING",
        "AIA-NORM-A005-P1-F-WORKPLACE-EDUCATION-EMOTION-INFERENCE",
        "AIA-NORM-A005-P1-G-SENSITIVE-BIOMETRIC-CATEGORISATION",
        "AIA-NORM-A005-P1-H-REAL-TIME-RBI",
        "AIA-NORM-A005-P1A-DEPLOYER-USE-SCOPE",
        "AIA-NORM-A005-P1A-MARKET-SERVICE-SCOPE",
        "AIA-NORM-A005-P1B-NON-MANIPULATION",
        "AIA-NORM-A005-P2-COMPLETE-FRIA",
        "AIA-NORM-A005-P2-CONFIRM-TARGETED-IDENTITY",
        "AIA-NORM-A005-P2-CONSIDER-IMPACTS",
        "AIA-NORM-A005-P2-NATIONAL-SAFEGUARDS",
        "AIA-NORM-A005-P2-REGISTER-SYSTEM",
        "AIA-NORM-A005-P3-CONSIDER-P2-ELEMENTS",
        "AIA-NORM-A005-P3-DELETE-ON-REJECTION",
        "AIA-NORM-A005-P3-NO-SOLE-OUTPUT-ADVERSE-DECISION",
        "AIA-NORM-A005-P3-PRIOR-AUTHORISATION",
        "AIA-NORM-A005-P3-RESTRICT-AUTHORISATION",
        "AIA-NORM-A005-P3-STOP-ON-REJECTION",
        "AIA-NORM-A005-P3-URGENT-USE",
        "AIA-NORM-A005-P4-EXCLUDE-SENSITIVE-DATA",
        "AIA-NORM-A005-P4-NOTIFICATION-CONTENT",
        "AIA-NORM-A005-P4-NOTIFY-AUTHORITIES",
        "AIA-NORM-A006-P1-ANNEX-I-HIGH-RISK",
        "AIA-NORM-A006-P1A-NON-SAFETY-ASSISTANCE",
        "AIA-NORM-A006-P1B-HEALTH-SAFETY-OVERRIDE",
        "AIA-NORM-A006-P1C-NON-SAFETY-ASSESSMENT",
        "AIA-NORM-A006-P2-ANNEX-III-HIGH-RISK",
        "AIA-NORM-A006-P3-INSIGNIFICANT-RISK-EXCEPTION",
        "AIA-NORM-A006-P3-PROFILING-OVERRIDE",
        "AIA-NORM-A006-P4-DOCUMENT-ASSESSMENT",
        "AIA-NORM-A006-P4-PROVIDE-ASSESSMENT",
        "AIA-NORM-A006-P4-REGISTER-SYSTEM",
        "AIA-NORM-A008-P1-COMPLY-SECTION-REQUIREMENTS",
        "AIA-NORM-A010-P5-B-REUSE-SECURITY",
        "AIA-NORM-A010-P5-C-ACCESS-SAFEGUARDS",
        "AIA-NORM-A010-P5-D-NO-THIRD-PARTY-ACCESS",
        "AIA-NORM-A010-P5-E-DELETE-DATA",
        "AIA-NORM-A010-P5-F-RECORD-NECESSITY",
        "AIA-NORM-A010-P5-SPECIAL-CATEGORY-PROCESSING",
        "AIA-NORM-A011-P1-SIMPLIFY",
        "AIA-NORM-A050-P3-DATA",
        "AIA-NORM-A050-P5-MANNER",
        "AIA-NORM-ANNEX-III-1A-REMOTE-BIOMETRIC-IDENTIFICATION",
        "AIA-NORM-ANNEX-III-1B-BIOMETRIC-CATEGORISATION",
        "AIA-NORM-ANNEX-III-1C-EMOTION-RECOGNITION",
        "AIA-NORM-ANNEX-III-2-CRITICAL-INFRASTRUCTURE",
        "AIA-NORM-ANNEX-III-3A-EDUCATION-ACCESS",
        "AIA-NORM-ANNEX-III-3B-LEARNING-OUTCOMES",
        "AIA-NORM-ANNEX-III-3C-EDUCATION-LEVEL",
        "AIA-NORM-ANNEX-III-3D-TEST-BEHAVIOUR",
        "AIA-NORM-ANNEX-III-4A-RECRUITMENT",
        "AIA-NORM-ANNEX-III-4B-WORKER-MANAGEMENT",
        "AIA-NORM-ANNEX-III-5A-ESSENTIAL-BENEFITS",
        "AIA-NORM-ANNEX-III-5B-CREDITWORTHINESS",
        "AIA-NORM-ANNEX-III-5C-LIFE-HEALTH-INSURANCE",
        "AIA-NORM-ANNEX-III-5D-EMERGENCY-RESPONSE",
        "AIA-NORM-ANNEX-III-6A-VICTIM-RISK",
        "AIA-NORM-ANNEX-III-6B-LAW-ENFORCEMENT-POLYGRAPH",
        "AIA-NORM-ANNEX-III-6C-EVIDENCE-RELIABILITY",
        "AIA-NORM-ANNEX-III-6D-OFFENDING-RISK",
        "AIA-NORM-ANNEX-III-6E-LAW-ENFORCEMENT-PROFILING",
        "AIA-NORM-ANNEX-III-7A-BORDER-POLYGRAPH",
        "AIA-NORM-ANNEX-III-7B-BORDER-RISK",
        "AIA-NORM-ANNEX-III-7C-ASYLUM-VISA-RESIDENCE",
        "AIA-NORM-ANNEX-III-7D-BORDER-IDENTIFICATION",
        "AIA-NORM-ANNEX-III-8A-JUSTICE",
        "AIA-NORM-ANNEX-III-8B-ELECTION-INFLUENCE",
        "AIA-NORM-ANNEX-IV-CONTENT",
        "AIA-NORM-ANNEX-VIII-A",
        "AIA-NORM-ANNEX-VIII-B",
        "AIA-NORM-ANNEX-VIII-C",
    ]
    assert metrics.implementation_debt_norm_ids == [
        "AIA-NORM-A002-P1-A-PROVIDER",
        "AIA-NORM-A002-P1-B-DEPLOYER",
        "AIA-NORM-A002-P1-C-THIRD-COUNTRY-OUTPUT",
        "AIA-NORM-A002-P1-D-IMPORT-DISTRIBUTE",
        "AIA-NORM-A002-P1-E-PRODUCT-MANUFACTURER",
        "AIA-NORM-A002-P1-F-AUTHORISED-REPRESENTATIVE",
        "AIA-NORM-A002-P1-G-AFFECTED-PERSON",
        "AIA-NORM-A002-P10-PERSONAL-USE-DEPLOYER-EXCLUSION",
        "AIA-NORM-A002-P12-OPEN-SOURCE-AI-SYSTEM-EXCLUSION",
        "AIA-NORM-A002-P13-LIMIT-HIGH-RISK-REQUIREMENTS",
        "AIA-NORM-A002-P2-INTEGRATED-SANDBOX-PROVISIONS",
        "AIA-NORM-A002-P2-SECTION-B-LIMIT",
        "AIA-NORM-A002-P3-MILITARY-EXCLUSION",
        "AIA-NORM-A002-P3-MILITARY-OUTPUT-EXCLUSION",
        "AIA-NORM-A002-P4-INTERNATIONAL-COOPERATION-EXCLUSION",
        "AIA-NORM-A002-P6-SCIENTIFIC-RD-EXCLUSION",
        "AIA-NORM-A002-P8-PRE-MARKET-RD-EXCLUSION",
        "AIA-NORM-A002-P8-REAL-WORLD-TESTING-CARVEOUT",
        "AIA-NORM-A004-P1-AI-LITERACY-MEASURES",
        "AIA-NORM-A004A-P1-B-REUSE-SECURITY",
        "AIA-NORM-A004A-P1-C-ACCESS-SAFEGUARDS",
        "AIA-NORM-A004A-P1-D-NO-THIRD-PARTY-ACCESS",
        "AIA-NORM-A004A-P1-E-DELETE-DATA",
        "AIA-NORM-A004A-P1-F-RECORD-NECESSITY",
        "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING",
        "AIA-NORM-A004A-P2-OTHER-SYSTEM-BIAS-DATA-PROCESSING",
        "AIA-NORM-A005-P1-A-MANIPULATIVE-TECHNIQUES",
        "AIA-NORM-A005-P1-B-VULNERABILITY-EXPLOITATION",
        "AIA-NORM-A005-P1-BA-NONCONSENSUAL-INTIMATE-MATERIAL",
        "AIA-NORM-A005-P1-BB-DIRECTIVE-MATERIAL",
        "AIA-NORM-A005-P1-C-SOCIAL-SCORING",
        "AIA-NORM-A005-P1-D-CRIMINAL-RISK-PROFILING",
        "AIA-NORM-A005-P1-E-UNTARGETED-FACIAL-SCRAPING",
        "AIA-NORM-A005-P1-F-WORKPLACE-EDUCATION-EMOTION-INFERENCE",
        "AIA-NORM-A005-P1-G-SENSITIVE-BIOMETRIC-CATEGORISATION",
        "AIA-NORM-A005-P1-H-REAL-TIME-RBI",
        "AIA-NORM-A005-P1A-DEPLOYER-USE-SCOPE",
        "AIA-NORM-A005-P1A-MARKET-SERVICE-SCOPE",
        "AIA-NORM-A005-P1B-NON-MANIPULATION",
        "AIA-NORM-A005-P2-COMPLETE-FRIA",
        "AIA-NORM-A005-P2-CONFIRM-TARGETED-IDENTITY",
        "AIA-NORM-A005-P2-CONSIDER-IMPACTS",
        "AIA-NORM-A005-P2-NATIONAL-SAFEGUARDS",
        "AIA-NORM-A005-P2-REGISTER-SYSTEM",
        "AIA-NORM-A005-P3-CONSIDER-P2-ELEMENTS",
        "AIA-NORM-A005-P3-DELETE-ON-REJECTION",
        "AIA-NORM-A005-P3-NO-SOLE-OUTPUT-ADVERSE-DECISION",
        "AIA-NORM-A005-P3-PRIOR-AUTHORISATION",
        "AIA-NORM-A005-P3-RESTRICT-AUTHORISATION",
        "AIA-NORM-A005-P3-STOP-ON-REJECTION",
        "AIA-NORM-A005-P3-URGENT-USE",
        "AIA-NORM-A005-P4-EXCLUDE-SENSITIVE-DATA",
        "AIA-NORM-A005-P4-NOTIFICATION-CONTENT",
        "AIA-NORM-A005-P4-NOTIFY-AUTHORITIES",
        "AIA-NORM-A006-P1-ANNEX-I-HIGH-RISK",
        "AIA-NORM-A006-P1A-NON-SAFETY-ASSISTANCE",
        "AIA-NORM-A006-P1B-HEALTH-SAFETY-OVERRIDE",
        "AIA-NORM-A006-P1C-NON-SAFETY-ASSESSMENT",
        "AIA-NORM-A006-P2-ANNEX-III-HIGH-RISK",
        "AIA-NORM-A006-P3-INSIGNIFICANT-RISK-EXCEPTION",
        "AIA-NORM-A006-P3-PROFILING-OVERRIDE",
        "AIA-NORM-A006-P4-DOCUMENT-ASSESSMENT",
        "AIA-NORM-A006-P4-PROVIDE-ASSESSMENT",
        "AIA-NORM-A006-P4-REGISTER-SYSTEM",
        "AIA-NORM-A008-P1-COMPLY-SECTION-REQUIREMENTS",
        "AIA-NORM-A011-P1-SIMPLIFY",
        "AIA-NORM-A050-P3-DATA",
        "AIA-NORM-ANNEX-III-1A-REMOTE-BIOMETRIC-IDENTIFICATION",
        "AIA-NORM-ANNEX-III-1B-BIOMETRIC-CATEGORISATION",
        "AIA-NORM-ANNEX-III-1C-EMOTION-RECOGNITION",
        "AIA-NORM-ANNEX-III-2-CRITICAL-INFRASTRUCTURE",
        "AIA-NORM-ANNEX-III-3A-EDUCATION-ACCESS",
        "AIA-NORM-ANNEX-III-3B-LEARNING-OUTCOMES",
        "AIA-NORM-ANNEX-III-3C-EDUCATION-LEVEL",
        "AIA-NORM-ANNEX-III-3D-TEST-BEHAVIOUR",
        "AIA-NORM-ANNEX-III-4A-RECRUITMENT",
        "AIA-NORM-ANNEX-III-4B-WORKER-MANAGEMENT",
        "AIA-NORM-ANNEX-III-5A-ESSENTIAL-BENEFITS",
        "AIA-NORM-ANNEX-III-5B-CREDITWORTHINESS",
        "AIA-NORM-ANNEX-III-5C-LIFE-HEALTH-INSURANCE",
        "AIA-NORM-ANNEX-III-5D-EMERGENCY-RESPONSE",
        "AIA-NORM-ANNEX-III-6A-VICTIM-RISK",
        "AIA-NORM-ANNEX-III-6B-LAW-ENFORCEMENT-POLYGRAPH",
        "AIA-NORM-ANNEX-III-6C-EVIDENCE-RELIABILITY",
        "AIA-NORM-ANNEX-III-6D-OFFENDING-RISK",
        "AIA-NORM-ANNEX-III-6E-LAW-ENFORCEMENT-PROFILING",
        "AIA-NORM-ANNEX-III-7A-BORDER-POLYGRAPH",
        "AIA-NORM-ANNEX-III-7B-BORDER-RISK",
        "AIA-NORM-ANNEX-III-7C-ASYLUM-VISA-RESIDENCE",
        "AIA-NORM-ANNEX-III-7D-BORDER-IDENTIFICATION",
        "AIA-NORM-ANNEX-III-8A-JUSTICE",
        "AIA-NORM-ANNEX-III-8B-ELECTION-INFLUENCE",
        "AIA-NORM-ANNEX-VIII-A",
        "AIA-NORM-ANNEX-VIII-B",
        "AIA-NORM-ANNEX-VIII-C",
    ]


def test_article_50_guidance_stays_non_binding_and_separate(metrics):
    bundle = load_normative_coverage()
    assert metrics.interpretive_links == 1
    link = bundle.norm_inventory.interpretations[0]
    assert link.binding is False
    assert link.norm_ids == ["AIA-NORM-A050-P2-MARK-DETECT"]
    assert set(link.snippet_refs) == {
        "C-2026-5054/machine-readable-marking-defined",
        "C-2026-5054/both-elements-required",
        "C-2026-5054/detection-must-be-available",
    }


def test_annex_inventory_keeps_external_actors_and_exact_mandatory_content():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    annex_vii = [
        norm for norm in norms.values() if norm.primary_spans[0].startswith("AIA-TEXT-ANNEX-VII-")
    ]
    assert len(annex_vii) == 18
    assert {norm.subjects[0].category.value for norm in annex_vii} >= {
        "supported_operator",
        "notified_or_conformity_body",
    }

    section_a = norms["AIA-NORM-ANNEX-VIII-A"]
    assert len(section_a.mandatory_content) == 13
    assert section_a.mandatory_content[0] == (
        "The name, address and contact details of the provider;"
    )
    assert all("Section A item" not in item for item in section_a.mandatory_content)
