"""Normative-coverage measurements and honest review-boundary checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aiact.norm_loader import load_normative_coverage
from aiact.norm_metrics import measure_normative_coverage
from aiact.schemas.norm import ConditionGroup
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
    assert metrics.documents_with_extracted_norms == 132
    assert metrics.documents_with_review_debt == 0
    assert metrics.exact_source_characters == 394_667
    assert set(metrics.norms_by_document) == {
        "annex I",
        "annex II",
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
        "article 16",
        "article 17",
        "article 18",
        "article 19",
        "article 20",
        "article 21",
        "article 22",
        "article 23",
        "article 24",
        "article 25",
        "article 26",
        "article 27",
        "article 28",
        "article 29",
        "article 30",
        "article 31",
        "article 32",
        "article 33",
        "article 34",
        "article 35",
        "article 36",
        "article 37",
        "article 38",
        "article 39",
        "article 40",
        "article 41",
        "article 42",
        "article 43",
        "article 44",
        "article 45",
        "article 46",
        "article 47",
        "article 48",
        "article 49",
        "article 50",
        "article 51",
        "article 52",
        "article 53",
        "article 54",
        "article 55",
        "article 56",
        "article 57",
        "article 58",
        "article 59",
        "article 60",
        "article 60a",
        "article 61",
        "article 62",
        "article 63",
        "article 64",
        "article 65",
        "article 66",
        "article 67",
        "article 68",
        "article 69",
        "article 70",
        "article 71",
        "article 72",
        "article 73",
        "article 74",
        "article 75",
        "article 75a",
        "article 75b",
        "article 75c",
        "article 75d",
        "article 76",
        "article 77",
        "article 78",
        "article 79",
        "article 80",
        "article 81",
        "article 82",
        "article 83",
        "article 84",
        "article 85",
        "article 86",
        "article 87",
        "article 88",
        "article 89",
        "article 90",
        "article 91",
        "article 92",
        "article 93",
        "article 94",
        "article 95",
        "article 96",
        "article 97",
        "article 98",
        "article 99",
        "article 100",
        "article 101",
        "article 102",
        "article 103",
        "article 104",
        "article 105",
        "article 106",
        "article 107",
        "article 108",
        "article 109",
        "article 110",
        "article 111",
        "article 112",
        "article 113",
        "annex III",
        "annex IV",
        "annex V",
        "annex VI",
        "annex VII",
        "annex VIII",
        "annex IX",
        "annex X",
        "annex XI",
        "annex XII",
        "annex XIII",
        "annex XIV",
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
    assert segments[0].review.status.value == "approved"
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
    assert single_set.implementation_refs == ["AIA-HR-A11-2"]
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


def test_article_sixteen_reuses_substantive_rules_without_duplicate_targets():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "16"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A016-")
    }

    assert len(segments) == 14
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 12
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert all(norm.qualifier_spans == ["AIA-TEXT-A016-P001"] for norm in norms.values())

    assert norms["AIA-NORM-A016-B-PROVIDER-IDENTIFICATION"].implementation_refs == [
        "AIA-PO-A16-B"
    ]
    assert norms["AIA-NORM-A016-K-DEMONSTRATE-CONFORMITY"].implementation_refs == [
        "AIA-PO-A16-K"
    ]
    assert norms["AIA-NORM-A016-L-ACCESSIBILITY"].implementation_refs == [
        "AIA-PO-A16-L"
    ]
    assert len(norms["AIA-NORM-A016-A-SECTION-2-COMPLIANCE"].implementation_refs) == 11
    assert len(norms["AIA-NORM-A016-F-CONFORMITY-ASSESSMENT"].implementation_refs) == 6
    corrective = norms["AIA-NORM-A016-J-CORRECTIVE-ACTION"]
    assert corrective.implementation_mode.value == "carried_by_other_norm"
    assert len(corrective.carried_by_norm_ids) == 4


def test_article_seventeen_models_thirteen_qms_aspects_without_micro_splitting():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "17"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A017-")
    }

    assert len(segments) == 18
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 21
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 19
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1
    assert sum(norm.kind.value == "legal_consequence" for norm in norms.values()) == 1
    assert all(norm.implementation_refs == ["AIA-PO-A17"] for norm in norms.values())

    aspect_ids = {
        norm_id
        for norm_id in norms
        if any(f"-P1-{point}-" in norm_id for point in "ABCDEFGHIJKLM")
    }
    assert len(aspect_ids) == 13
    assert all(norms[norm_id].qualifier_spans == ["AIA-TEXT-A017-P001"] for norm_id in aspect_ids)

    article_sixteen = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A016-C-QUALITY-MANAGEMENT"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert article_sixteen.carried_by_norm_ids == ["AIA-NORM-A017-P1-QMS"]


def test_article_eighteen_applies_one_retention_chapeau_to_five_document_types():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "18"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A018-")
    }

    assert len(segments) == 9
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 7
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    retention = {norm_id for norm_id in norms if "-P1-" in norm_id}
    assert len(retention) == 5
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A018-P001"]
        for norm_id in retention
    )
    member_state = norms["AIA-NORM-A018-P2-MEMBER-STATE-CONDITIONS"]
    assert member_state.implementation_mode.value == "none_required"
    provider_norms = set(norms) - {member_state.norm_id}
    assert all(
        norms[norm_id].implementation_refs == ["AIA-PO-A18"]
        for norm_id in provider_norms
    )

    article_sixteen = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A016-D-KEEP-DOCUMENTATION"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert set(article_sixteen.carried_by_norm_ids) == retention


def test_article_nineteen_separates_log_retention_duration_and_legal_exception():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "19"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A019-")
    }

    assert len(segments) == 3
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 5
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 4
    assert sum(norm.kind.value == "applicability" for norm in norms.values()) == 1
    assert all(norm.implementation_refs == ["AIA-PO-A19"] for norm in norms.values())

    paragraph_one = {norm_id for norm_id in norms if "-P1-" in norm_id}
    assert len(paragraph_one) == 4
    assert all(norms[norm_id].primary_spans == ["AIA-TEXT-A019-P001"] for norm_id in paragraph_one)
    exception = norms["AIA-NORM-A019-P1-OTHER-LAW-PERIOD"]
    assert exception.verification_mode.value == "reported_conditionally"

    article_sixteen = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A016-E-KEEP-LOGS"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert set(article_sixteen.carried_by_norm_ids) == paragraph_one


def test_article_twenty_keeps_alternative_corrective_outcomes_in_one_norm():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "20"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A020-")
    }

    assert len(segments) == 3
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 4
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    paragraph_one = {norm_id for norm_id in norms if "-P1-" in norm_id}
    paragraph_two = set(norms) - paragraph_one
    assert len(paragraph_one) == len(paragraph_two) == 2
    assert all(norms[norm_id].implementation_refs == ["AIA-PO-A20"] for norm_id in paragraph_one)
    assert all(
        norms[norm_id].implementation_refs == ["AIA-PO-A20-2"]
        for norm_id in paragraph_two
    )
    response = norms["AIA-NORM-A020-P1-CORRECTIVE-RESPONSE"]
    assert all(
        term in response.action
        for term in ("conformity", "withdrawing", "disabling", "recalling")
    )

    article_sixteen = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A016-J-CORRECTIVE-ACTION"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert set(article_sixteen.carried_by_norm_ids) == set(norms)


def test_article_twenty_one_separates_disclosure_language_and_log_access():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "21"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A021-")
    }

    assert len(segments) == 4
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 4
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    paragraph_one = {norm_id for norm_id in norms if "-P1-" in norm_id}
    assert len(paragraph_one) == 2
    assert all(norms[norm_id].implementation_refs == ["AIA-PO-A21"] for norm_id in paragraph_one)
    assert norms["AIA-NORM-A021-P2-PROVIDE-LOG-ACCESS"].implementation_refs == [
        "AIA-PO-A21-2"
    ]
    confidentiality = norms["AIA-NORM-A021-P3-CONFIDENTIALITY"]
    assert confidentiality.subjects[0].category.value == "public_authority"
    assert confidentiality.implementation_mode.value == "none_required"


def test_article_twenty_two_separates_provider_and_representative_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "22"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A022-")
    }

    assert len(segments) == 10
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 15
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    provider_norms = {
        "AIA-NORM-A022-P1-APPOINT-REPRESENTATIVE",
        "AIA-NORM-A022-P2-ENABLE-REPRESENTATIVE",
    }
    assert all(
        norms[norm_id].implementation_refs == ["AIA-PO-A22"]
        for norm_id in provider_norms
    )
    representative_norms = set(norms) - provider_norms
    assert all(
        norms[norm_id].implementation_refs == ["AIA-AR-A22"]
        for norm_id in representative_norms
    )

    mandate_items = {
        norm_id
        for norm_id in norms
        if any(f"-P3-{letter}-" in norm_id for letter in "ABCDE")
    }
    assert len(mandate_items) == 7
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A022-P003"]
        for norm_id in mandate_items
    )
    assert {
        norm_id for norm_id in mandate_items if "-P3-C-" in norm_id
    } == {
        "AIA-NORM-A022-P3-C-PROVIDE-CONFORMITY-INFORMATION",
        "AIA-NORM-A022-P3-C-PROVIDE-LOG-ACCESS",
    }
    assert {
        norm_id for norm_id in mandate_items if "-P3-E-" in norm_id
    } == {
        "AIA-NORM-A022-P3-E-REGISTER",
        "AIA-NORM-A022-P3-E-ENSURE-REGISTRATION-CORRECT",
    }


def test_article_twenty_three_separates_importer_checks_and_responses():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "23"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A023-")
    }

    assert len(segments) == 12
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 13
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert all(norm.implementation_refs == ["AIA-IM-A23"] for norm in norms.values())

    pre_market_checks = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A023-P1-")
    }
    assert len(pre_market_checks) == 4
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A023-P001"]
        for norm_id in pre_market_checks
    )
    paragraph_two = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A023-P2-")
    }
    assert paragraph_two == {
        "AIA-NORM-A023-P2-WITHHOLD-NONCONFORMING-SYSTEM",
        "AIA-NORM-A023-P2-INFORM-RISK",
    }
    paragraph_six = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A023-P6-")
    }
    assert paragraph_six == {
        "AIA-NORM-A023-P6-PROVIDE-CONFORMITY-INFORMATION",
        "AIA-NORM-A023-P6-AUTHORITY-LANGUAGE",
        "AIA-NORM-A023-P6-TECHNICAL-DOCUMENTATION-AVAILABLE",
    }
    assert norms["AIA-NORM-A023-P7-COOPERATE"].conditions == []


def test_article_twenty_four_separates_distributor_checks_and_responses():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "24"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A024-")
    }

    assert len(segments) == 7
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 10
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert all(norm.implementation_refs == ["AIA-DI-A24"] for norm in norms.values())

    paragraph_one = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A024-P1-")
    }
    assert paragraph_one == {
        "AIA-NORM-A024-P1-VERIFY-CE-MARKING",
        "AIA-NORM-A024-P1-VERIFY-ACCOMPANYING-DOCUMENTS",
        "AIA-NORM-A024-P1-VERIFY-OPERATOR-COMPLIANCE",
    }
    paragraph_two = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A024-P2-")
    }
    assert paragraph_two == {
        "AIA-NORM-A024-P2-WITHHOLD-NONCONFORMING-SYSTEM",
        "AIA-NORM-A024-P2-INFORM-RISK",
    }
    paragraph_four = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A024-P4-")
    }
    assert paragraph_four == {
        "AIA-NORM-A024-P4-CORRECTIVE-RESPONSE",
        "AIA-NORM-A024-P4-NOTIFY-RISK",
    }
    corrective = norms["AIA-NORM-A024-P4-CORRECTIVE-RESPONSE"]
    assert all(
        term in corrective.action
        for term in ("conformity", "withdrawal", "recall", "relevant operator")
    )
    assert norms["AIA-NORM-A024-P6-COOPERATE"].conditions == []


def test_article_twenty_five_separates_role_transfer_from_surviving_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "25"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A025-")
    }

    assert len(segments) == 18
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 15

    role_consequences = {
        norm_id
        for norm_id, norm in norms.items()
        if norm.kind.value == "legal_consequence"
    }
    assert len(role_consequences) == 6
    assert all(
        norms[norm_id].product_scope.value == "dependency_only"
        and norms[norm_id].implementation_mode.value == "none_required"
        for norm_id in role_consequences
    )

    initial_provider_norms = {
        norm_id
        for norm_id, norm in norms.items()
        if norm.implementation_refs == ["AIA-IP-A25-2"]
    }
    assert initial_provider_norms == {
        "AIA-NORM-A025-P2-COOPERATE",
        "AIA-NORM-A025-P2-PROVIDE-ASSISTANCE",
        "AIA-NORM-A025-P2-NO-COOPERATION-DUTY",
    }
    assistance = norms["AIA-NORM-A025-P2-PROVIDE-ASSISTANCE"]
    assert len(assistance.mandatory_content) == 3
    assert assistance.qualifier_spans == [
        "AIA-TEXT-A025-P007",
        "AIA-TEXT-A025-P008",
        "AIA-TEXT-A025-P009",
        "AIA-TEXT-A025-P010",
    ]

    agreement_norms = {
        norm_id
        for norm_id, norm in norms.items()
        if norm.implementation_refs == ["AIA-PO-A25-4"]
    }
    assert agreement_norms == {
        "AIA-NORM-A025-P4-WRITTEN-AGREEMENT",
        "AIA-NORM-A025-P4-OPEN-SOURCE-EXCEPTION",
    }
    ai_office_norms = {
        norm_id for norm_id in norms if "-AI-OFFICE-" in norm_id
    }
    assert len(ai_office_norms) == 3
    assert all(
        norms[norm_id].product_scope.value == "outside_supported_actor"
        for norm_id in ai_office_norms
    )
    protection = norms["AIA-NORM-A025-P5-PROTECT-RIGHTS-AND-SECRETS"]
    assert protection.implementation_mode.value == "missing"


def test_article_twenty_six_models_core_and_specialised_deployer_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "26"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A026-")
    }

    assert len(segments) == 13
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 44

    by_target = {
        target: {
            norm_id
            for norm_id, norm in norms.items()
            if norm.implementation_refs == [target]
        }
        for target in (
            "AIA-DP-A26",
            "AIA-DP-A26-8",
            "AIA-DP-A26-9",
            "AIA-DP-A26-10",
            "AIA-DP-A26-11",
            "AIA-DP-A26-12",
        )
    }
    assert len(by_target["AIA-DP-A26"]) == 18
    assert len(by_target["AIA-DP-A26-8"]) == 3
    assert len(by_target["AIA-DP-A26-9"]) == 1
    assert len(by_target["AIA-DP-A26-10"]) == 15
    assert len(by_target["AIA-DP-A26-11"]) == 3
    assert len(by_target["AIA-DP-A26-12"]) == 1

    paragraph_five = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A026-P5-")
    }
    assert len(paragraph_five) == 8
    paragraph_ten = {
        norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A026-P10-")
    }
    assert len(paragraph_ten) == 16
    assert {
        norm_id
        for norm_id in paragraph_ten
        if norms[norm_id].kind.value == "prohibition"
    } == {
        "AIA-NORM-A026-P10-PROHIBIT-UNTARGETED-USE",
        "AIA-NORM-A026-P10-NO-SOLE-OUTPUT-ADVERSE-DECISION",
    }
    member_state_power = norms["AIA-NORM-A026-P10-MEMBER-STATE-STRICTER-LAW"]
    assert member_state_power.kind.value == "power"
    assert member_state_power.product_scope.value == "outside_supported_actor"
    assert norms["AIA-NORM-A026-P8-DO-NOT-USE-UNREGISTERED"].kind.value == (
        "prohibition"
    )


def test_article_twenty_seven_keeps_fria_contents_in_one_assessment_norm():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "27"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A027-")
    }

    assert len(segments) == 12
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 9

    assessment = norms["AIA-NORM-A027-P1-PERFORM-FRIA"]
    assert assessment.implementation_refs == ["AIA-DP-A27"]
    assert len(assessment.mandatory_content) == 6
    assert assessment.qualifier_spans == [
        "AIA-TEXT-A027-P002",
        "AIA-TEXT-A027-P003",
        "AIA-TEXT-A027-P004",
        "AIA-TEXT-A027-P005",
        "AIA-TEXT-A027-P006",
        "AIA-TEXT-A027-P007",
    ]

    by_target = {
        target: {
            norm_id
            for norm_id, norm in norms.items()
            if norm.implementation_refs == [target]
        }
        for target in ("AIA-DP-A27", "AIA-DP-A27-2", "AIA-DP-A27-3")
    }
    assert len(by_target["AIA-DP-A27"]) == 2
    assert len(by_target["AIA-DP-A27-2"]) == 3
    assert len(by_target["AIA-DP-A27-3"]) == 2

    ai_office_norms = {
        norm_id
        for norm_id, norm in norms.items()
        if norm.subjects[0].subject_ref == "ai_office"
    }
    assert len(ai_office_norms) == 2
    assert all(
        norms[norm_id].product_scope.value == "outside_supported_actor"
        for norm_id in ai_office_norms
    )


def test_article_twenty_eight_is_complete_institutional_coverage():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "28"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A028-")
    ]

    assert len(segments) == 13
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 17
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)


def test_inventory_cannot_be_misreported_as_independently_approved(metrics):
    assert metrics.approved_characters == 390_556
    assert metrics.needs_review_characters == 0
    assert metrics.review_statuses == {
        "approved": 1467,
        "proposed": 1455,
    }
    assert metrics.timed_review_records == 0
    assert metrics.total_review_records == 2923


def test_semantic_pass_finds_propositions_a_shall_scan_misses(metrics):
    assert metrics.shall_vs_semantic_disagreements == 571
    assert metrics.shall_token_candidate_recall == pytest.approx(880 / 1451)
    assert "AIA-NORM-A011-P1-SIMPLIFY" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A043-P5-AMEND" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A060-P4-PERMISSION" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A075-P1E-WITHDRAW" in metrics.semantic_norms_without_shall_token


def test_metrics_expose_many_to_many_and_implementation_debt(metrics):
    assert metrics.normative_segments_with_multiple_norms == 358
    assert metrics.mapping_shape.one_norm_to_one_target == 26
    assert metrics.mapping_shape.many_norms_to_one_target == 349
    assert metrics.mapping_shape.one_norm_to_many_targets == 0
    assert metrics.mapping_shape.many_to_many == 15
    assert metrics.mapping_shape.unmapped == 1061
    assert metrics.semantic_vs_existing_implementation_disagreements == 239
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
        "AIA-NORM-A016-C-QUALITY-MANAGEMENT",
        "AIA-NORM-A016-D-KEEP-DOCUMENTATION",
        "AIA-NORM-A016-E-KEEP-LOGS",
        "AIA-NORM-A016-J-CORRECTIVE-ACTION",
        "AIA-NORM-A025-P5-PROTECT-RIGHTS-AND-SECRETS",
        "AIA-NORM-A036-P8-B-PROVIDER-REPLACEMENT-CONFIRMATION",
        "AIA-NORM-A040-P1-HARMONISED-STANDARD-PRESUMPTION",
        "AIA-NORM-A041-P3-COMMON-SPECIFICATION-PRESUMPTION",
        "AIA-NORM-A041-P5-JUSTIFY-EQUIVALENT-SOLUTIONS",
        "AIA-NORM-A042-P1-REPRESENTATIVE-DATA-PRESUMPTION",
        "AIA-NORM-A042-P2-CYBERSECURITY-CERTIFICATE-PRESUMPTION",
        "AIA-NORM-A042-P3-CYBER-RESILIENCE-DEEMING",
        "AIA-NORM-A044-P2-CERTIFICATE-VALIDITY-PERIOD",
        "AIA-NORM-A044-P2-EXTEND-CERTIFICATE",
        "AIA-NORM-A044-P2-SUPPLEMENT-VALIDITY",
        "AIA-NORM-A044-P3-CORRECTIVE-ACTION-EXCEPTION",
        "AIA-NORM-A046-P1-COMPLETE-ASSESSMENT-PROMPTLY",
        "AIA-NORM-A046-P7-SECTORAL-DEROGATIONS-ONLY",
        "AIA-NORM-A048-P1-GENERAL-CE-PRINCIPLES",
        "AIA-NORM-A048-P5-OTHER-LAW-COMPLIANCE",
        "AIA-NORM-A050-P3-DATA",
        "AIA-NORM-A050-P5-MANNER",
        "AIA-NORM-A051-P1-A-HIGH-IMPACT-SYSTEMIC-RISK",
        "AIA-NORM-A051-P1-B-EQUIVALENT-SYSTEMIC-RISK",
        "AIA-NORM-A051-P2-COMPUTE-PRESUMPTION",
        "AIA-NORM-A052-P3-SYSTEMIC-RISK-CONSEQUENCE",
        "AIA-NORM-A052-P5-REQUEST-CONTENT",
        "AIA-NORM-A059-P1-A-SUBSTANTIAL-PUBLIC-INTEREST",
        "AIA-NORM-A059-P1-B-DATA-NECESSITY",
        "AIA-NORM-A059-P1-C-MONITOR-AND-MITIGATE-RISKS",
        "AIA-NORM-A059-P1-CONDITIONAL-FURTHER-PROCESSING",
        "AIA-NORM-A059-P1-D-ISOLATED-PROTECTED-ENVIRONMENT",
        "AIA-NORM-A059-P1-E-SHARING-RESTRICTIONS",
        "AIA-NORM-A059-P1-F-NO-DATA-SUBJECT-EFFECT",
        "AIA-NORM-A059-P1-G-PROTECT-AND-DELETE-DATA",
        "AIA-NORM-A059-P1-H-KEEP-PROCESSING-LOGS",
        "AIA-NORM-A059-P1-I-DOCUMENT-TRAINING-TESTING-VALIDATION",
        "AIA-NORM-A059-P1-J-PUBLISH-PROJECT-SUMMARY",
        "AIA-NORM-A060-P1-REAL-WORLD-TESTING-PERMISSION",
        "AIA-NORM-A060-P2-PREMARKET-TESTING-PERMISSION",
        "AIA-NORM-A060-P4-A-SUBMIT-TESTING-PLAN",
        "AIA-NORM-A060-P4-B-APPROVAL-AND-TACIT-EFFECT",
        "AIA-NORM-A060-P4-C-REGISTER-TESTING",
        "AIA-NORM-A060-P4-D-UNION-ESTABLISHMENT",
        "AIA-NORM-A060-P4-E-TRANSFER-SAFEGUARDS",
        "AIA-NORM-A060-P4-F-DURATION-LIMIT",
        "AIA-NORM-A060-P4-G-PROTECT-VULNERABLE-SUBJECTS",
        "AIA-NORM-A060-P4-I-CONSENT-OR-SAFEGUARDS",
        "AIA-NORM-A060-P4-I-DELETE-SUBJECT-DATA",
        "AIA-NORM-A060-P4-I-NO-NEGATIVE-EFFECT",
        "AIA-NORM-A060-P4-J-QUALIFIED-OVERSIGHT",
        "AIA-NORM-A060-P4-K-REVERSIBLE-OUTPUTS",
        "AIA-NORM-A060-P7-IMMEDIATE-MITIGATION",
        "AIA-NORM-A060-P7-INCIDENT-RESPONSE",
        "AIA-NORM-A060-P7-RECALL-PROCEDURE",
        "AIA-NORM-A060-P7-SUSPEND-OR-TERMINATE",
        "AIA-NORM-A060-P8-NOTIFY-OUTCOMES",
        "AIA-NORM-A060A-P5-A-AGREE-TESTING-PLAN",
        "AIA-NORM-A060A-P5-B-COMPLY-WITH-INCORPORATED-SAFEGUARDS",
        "AIA-NORM-A060A-P6-COMPLY-WITH-SECTORAL-LAW",
        "AIA-NORM-A061-P1-OBTAIN-INFORMED-CONSENT",
        "AIA-NORM-A061-P2-DOCUMENT-AND-COPY-CONSENT",
        "AIA-NORM-A061-P2-GIVE-CONSENT-COPY",
        "AIA-NORM-A063-P1-SIMPLIFIED-SME-QUALITY-MANAGEMENT",
        "AIA-NORM-A071-P2-PROVIDER-ENTER-ANNEX-VIII-DATA",
        "AIA-NORM-A071-P2-REPRESENTATIVE-ENTER-ANNEX-VIII-DATA",
        "AIA-NORM-A071-P3-PUBLIC-DEPLOYER-ENTER-ANNEX-VIII-DATA",
        "AIA-NORM-A075A-P3-VOLUNTARY-REPLY-CORRECTNESS",
        "AIA-NORM-A075C-P3-DESCRIBE-IMPLEMENTED-MEASURES",
        "AIA-NORM-A111-P1-BRING-LARGE-SCALE-IT-INTO-COMPLIANCE",
        "AIA-NORM-A111-P2-PUBLIC-AUTHORITY-SYSTEM-COMPLIANCE",
        "AIA-NORM-A111-P3-LEGACY-GPAI-COMPLIANCE",
        "AIA-NORM-A111-P4-LEGACY-SYNTHETIC-CONTENT-COMPLIANCE",
        "AIA-NORM-ANNEX-I-01-MACHINERY-DIRECTIVE",
        "AIA-NORM-ANNEX-I-02-TOY-SAFETY",
        "AIA-NORM-ANNEX-I-03-RECREATIONAL-CRAFT",
        "AIA-NORM-ANNEX-I-04-LIFTS",
        "AIA-NORM-ANNEX-I-05-EXPLOSIVE-ATMOSPHERES",
        "AIA-NORM-ANNEX-I-06-RADIO-EQUIPMENT",
        "AIA-NORM-ANNEX-I-07-PRESSURE-EQUIPMENT",
        "AIA-NORM-ANNEX-I-08-CABLEWAYS",
        "AIA-NORM-ANNEX-I-09-PERSONAL-PROTECTIVE-EQUIPMENT",
        "AIA-NORM-ANNEX-I-10-GAS-APPLIANCES",
        "AIA-NORM-ANNEX-I-11-MEDICAL-DEVICES",
        "AIA-NORM-ANNEX-I-12-IN-VITRO-DIAGNOSTICS",
        "AIA-NORM-ANNEX-I-13-AVIATION-SECURITY",
        "AIA-NORM-ANNEX-I-14-L-CATEGORY-VEHICLES",
        "AIA-NORM-ANNEX-I-15-AGRICULTURAL-FORESTRY-VEHICLES",
        "AIA-NORM-ANNEX-I-16-MARINE-EQUIPMENT",
        "AIA-NORM-ANNEX-I-17-RAIL-INTEROPERABILITY",
        "AIA-NORM-ANNEX-I-18-MOTOR-VEHICLE-APPROVAL",
        "AIA-NORM-ANNEX-I-19-MOTOR-VEHICLE-GENERAL-SAFETY",
        "AIA-NORM-ANNEX-I-20-UNMANNED-AIRCRAFT",
        "AIA-NORM-ANNEX-I-21-MACHINERY-REGULATION",
        "AIA-NORM-ANNEX-II-01-TERRORISM",
        "AIA-NORM-ANNEX-II-02-HUMAN-TRAFFICKING",
        "AIA-NORM-ANNEX-II-03-CHILD-SEXUAL-EXPLOITATION",
        "AIA-NORM-ANNEX-II-04-DRUG-TRAFFICKING",
        "AIA-NORM-ANNEX-II-05-WEAPONS-TRAFFICKING",
        "AIA-NORM-ANNEX-II-06-MURDER-BODILY-INJURY",
        "AIA-NORM-ANNEX-II-07-HUMAN-ORGANS",
        "AIA-NORM-ANNEX-II-08-NUCLEAR-MATERIALS",
        "AIA-NORM-ANNEX-II-09-KIDNAPPING-HOSTAGE-TAKING",
        "AIA-NORM-ANNEX-II-10-ICC-CRIMES",
        "AIA-NORM-ANNEX-II-11-AIRCRAFT-SHIP-SEIZURE",
        "AIA-NORM-ANNEX-II-12-RAPE",
        "AIA-NORM-ANNEX-II-13-ENVIRONMENTAL-CRIME",
        "AIA-NORM-ANNEX-II-14-ROBBERY",
        "AIA-NORM-ANNEX-II-15-SABOTAGE",
        "AIA-NORM-ANNEX-II-16-CRIMINAL-ORGANISATION",
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
        "AIA-NORM-ANNEX-IX-REGISTRATION-INFORMATION",
        "AIA-NORM-ANNEX-V-DECLARATION-CONTENT",
        "AIA-NORM-ANNEX-VI-P1-PROCEDURE-CONTENT",
        "AIA-NORM-ANNEX-VI-P2-VERIFY-QMS",
        "AIA-NORM-ANNEX-VI-P3-EXAMINE-TECHNICAL-DOCUMENTATION",
        "AIA-NORM-ANNEX-VI-P4-VERIFY-CONSISTENCY",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION-CONTENT",
        "AIA-NORM-ANNEX-VII-INFORM-CHANGES",
        "AIA-NORM-ANNEX-VII-OVERVIEW-DOCUMENTATION-EXAMINATION",
        "AIA-NORM-ANNEX-VII-OVERVIEW-QMS-EXAMINATION",
        "AIA-NORM-ANNEX-VII-OVERVIEW-QMS-SURVEILLANCE",
        "AIA-NORM-ANNEX-VII-PROCEDURE-COMPOSITION",
        "AIA-NORM-ANNEX-VIII-A",
        "AIA-NORM-ANNEX-VIII-B",
        "AIA-NORM-ANNEX-VIII-C",
        "AIA-NORM-ANNEX-X-ECRIS-TCN",
        "AIA-NORM-ANNEX-X-ENTRY-EXIT-SYSTEM",
        "AIA-NORM-ANNEX-X-ETIAS",
        "AIA-NORM-ANNEX-X-ETIAS-EUROPOL",
        "AIA-NORM-ANNEX-X-EURODAC",
        "AIA-NORM-ANNEX-X-INTEROPERABILITY-BORDERS-VISA",
        "AIA-NORM-ANNEX-X-INTEROPERABILITY-POLICE-ASYLUM-MIGRATION",
        "AIA-NORM-ANNEX-X-SIS-BORDER-CHECKS",
        "AIA-NORM-ANNEX-X-SIS-POLICE-JUDICIAL",
        "AIA-NORM-ANNEX-X-SIS-RETURN",
        "AIA-NORM-ANNEX-X-VIS-ACCESS-CONDITIONS",
        "AIA-NORM-ANNEX-X-VIS-REFORM",
        "AIA-NORM-ANNEX-XI-SECTION-1-TECHNICAL-DOCUMENTATION",
        "AIA-NORM-ANNEX-XI-SECTION-2-SYSTEMIC-RISK-DOCUMENTATION",
        "AIA-NORM-ANNEX-XII-DOWNSTREAM-TRANSPARENCY-INFORMATION",
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
        "AIA-NORM-A025-P5-PROTECT-RIGHTS-AND-SECRETS",
        "AIA-NORM-A036-P8-B-PROVIDER-REPLACEMENT-CONFIRMATION",
        "AIA-NORM-A040-P1-HARMONISED-STANDARD-PRESUMPTION",
        "AIA-NORM-A041-P3-COMMON-SPECIFICATION-PRESUMPTION",
        "AIA-NORM-A041-P5-JUSTIFY-EQUIVALENT-SOLUTIONS",
        "AIA-NORM-A042-P1-REPRESENTATIVE-DATA-PRESUMPTION",
        "AIA-NORM-A042-P2-CYBERSECURITY-CERTIFICATE-PRESUMPTION",
        "AIA-NORM-A042-P3-CYBER-RESILIENCE-DEEMING",
        "AIA-NORM-A044-P2-CERTIFICATE-VALIDITY-PERIOD",
        "AIA-NORM-A044-P2-EXTEND-CERTIFICATE",
        "AIA-NORM-A044-P2-SUPPLEMENT-VALIDITY",
        "AIA-NORM-A044-P3-CORRECTIVE-ACTION-EXCEPTION",
        "AIA-NORM-A046-P1-COMPLETE-ASSESSMENT-PROMPTLY",
        "AIA-NORM-A046-P7-SECTORAL-DEROGATIONS-ONLY",
        "AIA-NORM-A048-P1-GENERAL-CE-PRINCIPLES",
        "AIA-NORM-A048-P5-OTHER-LAW-COMPLIANCE",
        "AIA-NORM-A050-P3-DATA",
        "AIA-NORM-A051-P1-A-HIGH-IMPACT-SYSTEMIC-RISK",
        "AIA-NORM-A051-P1-B-EQUIVALENT-SYSTEMIC-RISK",
        "AIA-NORM-A051-P2-COMPUTE-PRESUMPTION",
        "AIA-NORM-A052-P3-SYSTEMIC-RISK-CONSEQUENCE",
        "AIA-NORM-A052-P5-REQUEST-CONTENT",
        "AIA-NORM-A059-P1-A-SUBSTANTIAL-PUBLIC-INTEREST",
        "AIA-NORM-A059-P1-B-DATA-NECESSITY",
        "AIA-NORM-A059-P1-C-MONITOR-AND-MITIGATE-RISKS",
        "AIA-NORM-A059-P1-CONDITIONAL-FURTHER-PROCESSING",
        "AIA-NORM-A059-P1-D-ISOLATED-PROTECTED-ENVIRONMENT",
        "AIA-NORM-A059-P1-E-SHARING-RESTRICTIONS",
        "AIA-NORM-A059-P1-F-NO-DATA-SUBJECT-EFFECT",
        "AIA-NORM-A059-P1-G-PROTECT-AND-DELETE-DATA",
        "AIA-NORM-A059-P1-H-KEEP-PROCESSING-LOGS",
        "AIA-NORM-A059-P1-I-DOCUMENT-TRAINING-TESTING-VALIDATION",
        "AIA-NORM-A059-P1-J-PUBLISH-PROJECT-SUMMARY",
        "AIA-NORM-A060-P1-REAL-WORLD-TESTING-PERMISSION",
        "AIA-NORM-A060-P2-PREMARKET-TESTING-PERMISSION",
        "AIA-NORM-A060-P4-A-SUBMIT-TESTING-PLAN",
        "AIA-NORM-A060-P4-B-APPROVAL-AND-TACIT-EFFECT",
        "AIA-NORM-A060-P4-C-REGISTER-TESTING",
        "AIA-NORM-A060-P4-D-UNION-ESTABLISHMENT",
        "AIA-NORM-A060-P4-E-TRANSFER-SAFEGUARDS",
        "AIA-NORM-A060-P4-F-DURATION-LIMIT",
        "AIA-NORM-A060-P4-G-PROTECT-VULNERABLE-SUBJECTS",
        "AIA-NORM-A060-P4-I-CONSENT-OR-SAFEGUARDS",
        "AIA-NORM-A060-P4-I-DELETE-SUBJECT-DATA",
        "AIA-NORM-A060-P4-I-NO-NEGATIVE-EFFECT",
        "AIA-NORM-A060-P4-J-QUALIFIED-OVERSIGHT",
        "AIA-NORM-A060-P4-K-REVERSIBLE-OUTPUTS",
        "AIA-NORM-A060-P7-IMMEDIATE-MITIGATION",
        "AIA-NORM-A060-P7-INCIDENT-RESPONSE",
        "AIA-NORM-A060-P7-RECALL-PROCEDURE",
        "AIA-NORM-A060-P7-SUSPEND-OR-TERMINATE",
        "AIA-NORM-A060-P8-NOTIFY-OUTCOMES",
        "AIA-NORM-A060A-P5-A-AGREE-TESTING-PLAN",
        "AIA-NORM-A060A-P5-B-COMPLY-WITH-INCORPORATED-SAFEGUARDS",
        "AIA-NORM-A060A-P6-COMPLY-WITH-SECTORAL-LAW",
        "AIA-NORM-A061-P1-OBTAIN-INFORMED-CONSENT",
        "AIA-NORM-A061-P2-DOCUMENT-AND-COPY-CONSENT",
        "AIA-NORM-A061-P2-GIVE-CONSENT-COPY",
        "AIA-NORM-A063-P1-SIMPLIFIED-SME-QUALITY-MANAGEMENT",
        "AIA-NORM-A071-P2-PROVIDER-ENTER-ANNEX-VIII-DATA",
        "AIA-NORM-A071-P2-REPRESENTATIVE-ENTER-ANNEX-VIII-DATA",
        "AIA-NORM-A071-P3-PUBLIC-DEPLOYER-ENTER-ANNEX-VIII-DATA",
        "AIA-NORM-A075A-P3-VOLUNTARY-REPLY-CORRECTNESS",
        "AIA-NORM-A075C-P3-DESCRIBE-IMPLEMENTED-MEASURES",
        "AIA-NORM-A111-P1-BRING-LARGE-SCALE-IT-INTO-COMPLIANCE",
        "AIA-NORM-A111-P2-PUBLIC-AUTHORITY-SYSTEM-COMPLIANCE",
        "AIA-NORM-A111-P3-LEGACY-GPAI-COMPLIANCE",
        "AIA-NORM-A111-P4-LEGACY-SYNTHETIC-CONTENT-COMPLIANCE",
        "AIA-NORM-ANNEX-I-01-MACHINERY-DIRECTIVE",
        "AIA-NORM-ANNEX-I-02-TOY-SAFETY",
        "AIA-NORM-ANNEX-I-03-RECREATIONAL-CRAFT",
        "AIA-NORM-ANNEX-I-04-LIFTS",
        "AIA-NORM-ANNEX-I-05-EXPLOSIVE-ATMOSPHERES",
        "AIA-NORM-ANNEX-I-06-RADIO-EQUIPMENT",
        "AIA-NORM-ANNEX-I-07-PRESSURE-EQUIPMENT",
        "AIA-NORM-ANNEX-I-08-CABLEWAYS",
        "AIA-NORM-ANNEX-I-09-PERSONAL-PROTECTIVE-EQUIPMENT",
        "AIA-NORM-ANNEX-I-10-GAS-APPLIANCES",
        "AIA-NORM-ANNEX-I-11-MEDICAL-DEVICES",
        "AIA-NORM-ANNEX-I-12-IN-VITRO-DIAGNOSTICS",
        "AIA-NORM-ANNEX-I-13-AVIATION-SECURITY",
        "AIA-NORM-ANNEX-I-14-L-CATEGORY-VEHICLES",
        "AIA-NORM-ANNEX-I-15-AGRICULTURAL-FORESTRY-VEHICLES",
        "AIA-NORM-ANNEX-I-16-MARINE-EQUIPMENT",
        "AIA-NORM-ANNEX-I-17-RAIL-INTEROPERABILITY",
        "AIA-NORM-ANNEX-I-18-MOTOR-VEHICLE-APPROVAL",
        "AIA-NORM-ANNEX-I-19-MOTOR-VEHICLE-GENERAL-SAFETY",
        "AIA-NORM-ANNEX-I-20-UNMANNED-AIRCRAFT",
        "AIA-NORM-ANNEX-I-21-MACHINERY-REGULATION",
        "AIA-NORM-ANNEX-II-01-TERRORISM",
        "AIA-NORM-ANNEX-II-02-HUMAN-TRAFFICKING",
        "AIA-NORM-ANNEX-II-03-CHILD-SEXUAL-EXPLOITATION",
        "AIA-NORM-ANNEX-II-04-DRUG-TRAFFICKING",
        "AIA-NORM-ANNEX-II-05-WEAPONS-TRAFFICKING",
        "AIA-NORM-ANNEX-II-06-MURDER-BODILY-INJURY",
        "AIA-NORM-ANNEX-II-07-HUMAN-ORGANS",
        "AIA-NORM-ANNEX-II-08-NUCLEAR-MATERIALS",
        "AIA-NORM-ANNEX-II-09-KIDNAPPING-HOSTAGE-TAKING",
        "AIA-NORM-ANNEX-II-10-ICC-CRIMES",
        "AIA-NORM-ANNEX-II-11-AIRCRAFT-SHIP-SEIZURE",
        "AIA-NORM-ANNEX-II-12-RAPE",
        "AIA-NORM-ANNEX-II-13-ENVIRONMENTAL-CRIME",
        "AIA-NORM-ANNEX-II-14-ROBBERY",
        "AIA-NORM-ANNEX-II-15-SABOTAGE",
        "AIA-NORM-ANNEX-II-16-CRIMINAL-ORGANISATION",
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
        "AIA-NORM-ANNEX-VI-P1-PROCEDURE-CONTENT",
        "AIA-NORM-ANNEX-VI-P2-VERIFY-QMS",
        "AIA-NORM-ANNEX-VI-P3-EXAMINE-TECHNICAL-DOCUMENTATION",
        "AIA-NORM-ANNEX-VI-P4-VERIFY-CONSISTENCY",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION-CONTENT",
        "AIA-NORM-ANNEX-VII-INFORM-CHANGES",
        "AIA-NORM-ANNEX-VII-OVERVIEW-DOCUMENTATION-EXAMINATION",
        "AIA-NORM-ANNEX-VII-OVERVIEW-QMS-EXAMINATION",
        "AIA-NORM-ANNEX-VII-OVERVIEW-QMS-SURVEILLANCE",
        "AIA-NORM-ANNEX-VII-PROCEDURE-COMPOSITION",
        "AIA-NORM-ANNEX-VIII-A",
        "AIA-NORM-ANNEX-VIII-B",
        "AIA-NORM-ANNEX-VIII-C",
        "AIA-NORM-ANNEX-X-ECRIS-TCN",
        "AIA-NORM-ANNEX-X-ENTRY-EXIT-SYSTEM",
        "AIA-NORM-ANNEX-X-ETIAS",
        "AIA-NORM-ANNEX-X-ETIAS-EUROPOL",
        "AIA-NORM-ANNEX-X-EURODAC",
        "AIA-NORM-ANNEX-X-INTEROPERABILITY-BORDERS-VISA",
        "AIA-NORM-ANNEX-X-INTEROPERABILITY-POLICE-ASYLUM-MIGRATION",
        "AIA-NORM-ANNEX-X-SIS-BORDER-CHECKS",
        "AIA-NORM-ANNEX-X-SIS-POLICE-JUDICIAL",
        "AIA-NORM-ANNEX-X-SIS-RETURN",
        "AIA-NORM-ANNEX-X-VIS-ACCESS-CONDITIONS",
        "AIA-NORM-ANNEX-X-VIS-REFORM",
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


def test_article_thirty_two_creates_a_conditional_conformity_presumption():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "32"
    ]
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A032-P1-HARMONISED-STANDARDS-PRESUMPTION"
    )

    assert len(segments) == 2
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert segments[1].norm_ids == [norm.norm_id]
    assert norm.kind.value == "legal_consequence"
    assert norm.primary_spans == ["AIA-TEXT-A032-P001"]
    assert len(norm.conditions) == 3
    assert norm.implementation_mode.value == "none_required"


def test_article_thirty_three_separates_subcontracting_legal_effects():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "33"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A033-")
    }

    assert len(segments) == 5
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 6
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 5
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1
    assert len(segments[1].norm_ids) == 2
    assert len(segments[3].norm_ids) == 2
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    retention = norms["AIA-NORM-A033-P4-RETAIN-SUBCONTRACTING-DOCUMENTS"]
    assert len(retention.mandatory_content) == 2
    assert retention.conditions == [
        "retain the documents for five years from termination of the subcontracting"
    ]


def test_article_thirty_four_separates_operational_obligations():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "34"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A034-")
    }

    assert len(segments) == 4
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 5
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert len(segments[2].norm_ids) == 3
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    documentation = norms["AIA-NORM-A034-P3-PROVIDE-DOCUMENTATION"]
    assert documentation.mandatory_content == [
        "all relevant documentation",
        "provider documentation",
    ]
    assert documentation.conditions == [
        "the Article 28 notifying authority requests the documentation"
    ]


def test_article_thirty_five_keeps_publication_and_currency_separate():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "35"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A035-")
    }

    assert len(segments) == 3
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 3
    assert len(segments[2].norm_ids) == 2
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert all(
        norm.subjects[0].category.value == "union_institution_or_body"
        for norm in norms.values()
    )
    publication = norms["AIA-NORM-A035-P2-PUBLISH-NOTIFIED-BODY-LIST"]
    assert publication.mandatory_content == [
        "notified bodies",
        "identification numbers",
        "notified activities",
    ]


def test_article_thirty_six_preserves_certificate_change_workflows():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "36"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A036-")
    }

    assert len(segments) == 22
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 26
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 19
    assert sum(norm.kind.value == "legal_consequence" for norm in norms.values()) == 3
    assert sum(norm.kind.value == "applicability" for norm in norms.values()) == 2
    assert sum(norm.kind.value == "entitlement" for norm in norms.values()) == 1
    assert sum(norm.kind.value == "power" for norm in norms.values()) == 1

    suspension = norms["AIA-NORM-A036-P8-SUSPENSION-CERTIFICATE-VALIDITY"]
    assert suspension.qualifier_spans == [
        "AIA-TEXT-A036-P015",
        "AIA-TEXT-A036-P016",
    ]
    withdrawal = norms["AIA-NORM-A036-P9-WITHDRAWAL-CERTIFICATE-VALIDITY"]
    assert withdrawal.qualifier_spans == [
        "AIA-TEXT-A036-P018",
        "AIA-TEXT-A036-P019",
    ]
    provider = norms["AIA-NORM-A036-P8-B-PROVIDER-REPLACEMENT-CONFIRMATION"]
    assert provider.product_scope.value == "in_scope"
    assert provider.implementation_mode.value == "missing"


def test_article_thirty_seven_separates_challenge_and_escalation_effects():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "37"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A037-")
    }

    assert len(segments) == 5
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 7
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 6
    assert sum(norm.kind.value == "power" for norm in norms.values()) == 1
    assert len(segments[4].norm_ids) == 4
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    information = norms["AIA-NORM-A037-P2-PROVIDE-NOTIFICATION-INFORMATION"]
    assert information.mandatory_content == [
        "notification information",
        "information on maintaining notified-body competence",
    ]


def test_article_thirty_eight_captures_coordination_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "38"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A038-")
    ]

    assert len(segments) == 4
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 3
    assert all(norm.kind.value == "obligation" for norm in norms)
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert {norm.subjects[0].category.value for norm in norms} == {
        "union_institution_or_body",
        "public_authority",
    }


def test_article_thirty_nine_is_one_conditional_third_country_permission():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "39"
    ]
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A039-P1-THIRD-COUNTRY-BODY-AUTHORISATION"
    )

    assert len(segments) == 2
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert segments[1].norm_ids == [norm.norm_id]
    assert norm.kind.value == "permission"
    assert len(norm.conditions) == 2
    assert norm.product_scope.value == "outside_supported_actor"


def test_article_forty_separates_presumption_and_standardisation_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "40"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A040-")
    }

    assert len(segments) == 7
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 8
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 7
    assert sum(norm.kind.value == "legal_consequence" for norm in norms.values()) == 1
    assert len(segments[2].norm_ids) == 3
    presumption = norms["AIA-NORM-A040-P1-HARMONISED-STANDARD-PRESUMPTION"]
    assert presumption.product_scope.value == "in_scope"
    assert presumption.implementation_mode.value == "missing"
    assert len(presumption.conditions) == 2
    objectives = norms["AIA-NORM-A040-P3-STANDARDISATION-OBJECTIVES"]
    assert len(objectives.mandatory_content) == 4


def test_article_forty_one_preserves_common_specification_workflow():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "41"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A041-")
    }

    assert len(segments) == 15
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 11
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 9
    assert sum(norm.kind.value == "power" for norm in norms.values()) == 1
    assert sum(norm.kind.value == "legal_consequence" for norm in norms.values()) == 1
    power = norms["AIA-NORM-A041-P1-ADOPT-COMMON-SPECIFICATIONS"]
    assert power.qualifier_spans == [
        "AIA-TEXT-A041-P002",
        "AIA-TEXT-A041-P003",
        "AIA-TEXT-A041-P004",
        "AIA-TEXT-A041-P005",
        "AIA-TEXT-A041-P006",
        "AIA-TEXT-A041-P007",
    ]
    assert len(power.conditions) == 1
    assert power.conditions[0].operator == "all_of"
    presumption = norms["AIA-NORM-A041-P3-COMMON-SPECIFICATION-PRESUMPTION"]
    justification = norms["AIA-NORM-A041-P5-JUSTIFY-EQUIVALENT-SOLUTIONS"]
    assert presumption.implementation_mode.value == "missing"
    assert justification.implementation_mode.value == "missing"


def test_article_forty_two_keeps_three_conformity_presumptions_distinct():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "42"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A042-")
    ]

    assert len(segments) == 4
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 3
    assert all(norm.kind.value == "legal_consequence" for norm in norms)
    assert all(norm.product_scope.value == "in_scope" for norm in norms)
    assert all(norm.implementation_mode.value == "missing" for norm in norms)
    assert {len(norm.conditions) for norm in norms} == {1, 2}


def test_article_forty_three_reconciles_all_conformity_routes():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "43"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A043-")
    }

    assert len(segments) == 7
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 20
    assert len(segments[1].norm_ids) == 4
    assert len(segments[3].norm_ids) == 10
    assert len(segments[4].norm_ids) == 2
    assert len(segments[6].norm_ids) == 2
    assert norms["AIA-NORM-A043-P1-CHOOSE-CONFORMITY-ROUTE"].implementation_refs == [
        "AIA-PO-A43-1"
    ]
    assert norms["AIA-NORM-A043-P2-INTERNAL-CONTROL"].implementation_refs == [
        "AIA-PO-A43-2"
    ]
    assert norms["AIA-NORM-A043-P4-NEW-ASSESSMENT"].implementation_refs == [
        "AIA-PO-A43-4"
    ]
    exclusion = norms["AIA-NORM-A043-P4-PREDETERMINED-CHANGE-EXCLUSION"]
    assert exclusion.kind.value == "applicability"
    assert exclusion.product_scope.value == "dependency_only"


def test_article_forty_four_separates_certificate_status_effects():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "44"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A044-")
    }

    assert len(segments) == 5
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 8
    assert len(segments[2].norm_ids) == 3
    assert len(segments[3].norm_ids) == 3
    missing = [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert len(missing) == 4
    assert all(norm.product_scope.value == "in_scope" for norm in missing)
    extension = norms["AIA-NORM-A044-P2-EXTEND-CERTIFICATE"]
    assert extension.kind.value == "entitlement"
    assert len(extension.conditions) == 2


def test_article_forty_five_separates_event_notices_from_request_only_disclosures():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "45"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A045-")
    }

    assert len(segments) == 12
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 7
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert all(norm.review.status.value == "proposed" for norm in norms.values())
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    assert all(norm.implementation_mode.value == "none_required" for norm in norms.values())
    authority = norms["AIA-NORM-A045-P1-INFORM-NOTIFYING-AUTHORITY"]
    assert authority.qualifier_spans == [f"AIA-TEXT-A045-P{p:03}" for p in range(2, 6)]
    assert authority.mandatory_content == []  # Events are alternatives, not cumulative content.
    events = authority.conditions[0]
    assert events.operator == "any_of" and len(events.operands) == 4
    assert "supplement" in events.operands[0]
    assert "restricted" in events.operands[1]
    assert "circumstances" in events.operands[2]
    assert "received a market-surveillance-authority information request" in events.operands[3]
    activities = norms["AIA-NORM-A045-P1-DISCLOSE-ACTIVITIES-ON-REQUEST"]
    assert activities.qualifier_spans == ["AIA-TEXT-A045-P006"]
    assert "notifying authority requests" in activities.conditions[0]
    assert activities.mandatory_content == [
        "conformity assessment activities performed within the scope of the notification",
        "other activities performed, including cross-border activities and subcontracting",
    ]
    peers = norms["AIA-NORM-A045-P2-INFORM-OTHER-NOTIFIED-BODIES"]
    assert len(peers.qualifier_spans) == 2
    adverse = peers.conditions[0]
    assert adverse.operator == "any_of" and len(adverse.operands) == 2
    assert (
        "refused, suspended or withdrawn a quality management system approval"
        in adverse.operands[0]
    )
    assert "restricted" not in adverse.operands[0]  # Paragraph 2(a) does not list restriction.
    assert "restricted" in adverse.operands[1] and "supplement" in adverse.operands[1]
    assert peers.mandatory_content == []
    issued = norms["AIA-NORM-A045-P2-DISCLOSE-ISSUED-APPROVALS-ON-REQUEST"]
    assert issued.conditions[0].operator == "any_of"
    assert len(issued.conditions[0].operands) == 2
    assert all("requests information" in item for item in issued.conditions[0].operands)
    negative = norms["AIA-NORM-A045-P3-SHARE-ASSESSMENT-RESULTS"]
    positive = norms["AIA-NORM-A045-P3-SHARE-POSITIVE-RESULTS-ON-REQUEST"]
    assert "negative" in negative.conditions[0] and "positive" in positive.conditions[0]
    assert negative.conditions[1] == positive.conditions[1]
    assert "similar conformity assessment activities" in negative.conditions[1]
    assert "same types of AI systems" in negative.conditions[1]
    assert len(negative.conditions) == 2
    assert positive.conditions[2] == "that recipient requests the information"
    assert norms["AIA-NORM-A045-P4-CONFIDENTIALITY"].action == (
        "safeguard obtained information confidentiality under Article 78"
    )


def test_article_forty_six_preserves_derogation_lifecycle():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "46"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A046-")
    }

    assert len(segments) == 8
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 14
    authorisation = norms["AIA-NORM-A046-P1-DEROGATION-AUTHORISATION"]
    assert authorisation.kind.value == "power"
    assert authorisation.qualifier_spans == ["AIA-TEXT-A046-P003"]
    assert len(authorisation.conditions) == 3
    refusal = norms["AIA-NORM-A046-P2-REFUSAL-RESPONSE"]
    discard = norms["AIA-NORM-A046-P2-DISCARD-RESULTS-AND-OUTPUTS"]
    assert refusal.conditions == discard.conditions == [
        "the paragraph 1 authorisation requested for urgent use under paragraph 2 is refused"
    ]
    assert refusal.subjects == discard.subjects
    assert refusal.subjects[0].subject_ref == "law_enforcement_or_civil_protection_authority"
    assert "stop use" in refusal.action and "immediate effect" in refusal.action
    assert "discard" not in refusal.action
    assert "immediately discard all results and outputs" in discard.action
    assert "stop use" not in discard.action
    for obligation in (refusal, discard):
        assert obligation.kind.value == "obligation"
        assert obligation.primary_spans == ["AIA-TEXT-A046-P002"]
        assert obligation.mandatory_content == []  # Actions are separate norms, not payload items.
        assert obligation.review.status.value == "proposed"
        assert obligation.implementation_mode.value == "none_required"
    permission = norms["AIA-NORM-A046-P2-URGENT-USE-PERMISSION"]
    assert permission.kind.value == "permission"
    assert len(permission.conditions) == 2
    assert "without undue delay" in permission.conditions[1]
    missing = [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert {norm.norm_id for norm in missing} == {
        "AIA-NORM-A046-P1-COMPLETE-ASSESSMENT-PROMPTLY",
        "AIA-NORM-A046-P7-SECTORAL-DEROGATIONS-ONLY",
    }


def test_article_forty_seven_maps_complete_declaration_workflow():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "47"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A047-")
    }

    assert len(segments) == 6
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 12
    assert len(segments[1].norm_ids) == 4
    assert len(segments[2].norm_ids) == 3
    assert len(segments[3].norm_ids) == 2
    assert len(segments[4].norm_ids) == 2
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 11
    assert all(norm.implementation_mode.value == "compliance_rule" for norm in mapped)
    annex_content = norms["AIA-NORM-A047-P2-ANNEX-V-CONTENT"]
    assert len(annex_content.dependencies) == 8
    assert {dependency.resolution.value for dependency in annex_content.dependencies} == {
        "internal_resolved"
    }


def test_article_forty_eight_maps_ce_marking_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "48"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A048-")
    }

    assert len(segments) == 6
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 7
    assert len(segments[4].norm_ids) == 3
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 5
    assert all(norm.implementation_mode.value == "compliance_rule" for norm in mapped)
    missing = [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert {norm.norm_id for norm in missing} == {
        "AIA-NORM-A048-P1-GENERAL-CE-PRINCIPLES",
        "AIA-NORM-A048-P5-OTHER-LAW-COMPLIANCE",
    }
    digital_marking = norms["AIA-NORM-A048-P2-DIGITAL-CE-MARKING"]
    assert len(digital_marking.conditions) == 1


def test_article_forty_nine_maps_registration_routes_and_restricted_content():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "49"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A049-")
    }

    assert len(segments) == 11
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 10
    assert [len(segments[index].norm_ids) for index in (1, 2, 4, 9)] == [2, 2, 2, 2]
    assert all(segments[index].disposition.value == "normative" for index in range(5, 9))
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 8
    assert all(norm.implementation_mode.value == "compliance_rule" for norm in mapped)
    restricted = norms["AIA-NORM-A049-P4-RESTRICTED-INFORMATION"]
    assert len(restricted.mandatory_content) == 4
    assert len(restricted.qualifier_spans) == 4
    access = [norm for norm in norms.values() if norm.kind.value == "entitlement"]
    assert len(access) == 2
    assert all(norm.implementation_mode.value == "none_required" for norm in access)


def test_article_fifty_preserves_disclosure_test_and_technical_solution_qualifiers():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A050-")
    }
    assert len(norms) == 11
    disclose = norms["AIA-NORM-A050-P1-DISCLOSE"]
    assert disclose.exceptions == [
        "interaction with an AI system is obvious from the point of view of a natural person "
        "who is reasonably well-informed, observant and circumspect, taking into account "
        "the circumstances and the context of use",
        "AI system authorised by law to detect, prevent, investigate, or prosecute criminal "
        "offences, "
        "subject to safeguards for third-party rights and freedoms, unless the system is publicly "
        "available for reporting a criminal offence",
    ]
    marking = norms["AIA-NORM-A050-P2-MARK-DETECT"]
    assert marking.mandatory_content == [
        "machine-readable marking",
        "detectability as artificial or manipulated",
        "effective, interoperable, robust and reliable solution as technically feasible",
        "in ensuring those technical-solution qualities, take into account the specificities and "
        "limitations of various types of content",
        "in ensuring those technical-solution qualities, take into account "
        "the costs of implementation",
        "in ensuring those technical-solution qualities, take into account the generally "
        "acknowledged state of the art, as may be reflected in relevant technical standards",
    ]
    # Costs and technical feasibility do not become new exemptions from marking/detectability.
    assert marking.exceptions == [
        "assistive standard editing, or no substantial alteration of deployer input data "
        "or its semantics",
        "use authorised by law to detect, prevent, investigate, or prosecute criminal offences",
    ]
    assert disclose.implementation_refs == ["AIA-TR-A50-1"]
    assert marking.implementation_refs == ["AIA-TR-A50-2"]
    assert disclose.primary_spans == ["AIA-TEXT-A050-P1"]
    assert marking.primary_spans == ["AIA-TEXT-A050-P2"]
    for norm in (disclose, marking):
        assert norm.qualifier_spans == ["AIA-TEXT-A050-P5"]
        assert norm.review.status.value == "proposed"
        assert norm.verification_mode.value == "judged_from_document"
    article_segments = [
        s for s in bundle.text_review.segments
        if s.source.kind.value == "article" and s.source.document == "50"
    ]
    assert all(
        s.review.status.value == "approved" and s.review.verified_by == "vidibro"
        for s in article_segments
    )


def test_article_fifty_one_extracts_systemic_risk_classification_gates():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "51"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A051-")
    }

    assert len(segments) == 6
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 5
    assert len(segments[1].norm_ids) == 2
    assert len(segments[5].norm_ids) == 2
    classification = [norm for norm in norms.values() if norm.kind.value == "applicability"]
    assert len(classification) == 3
    assert all(norm.implementation_mode.value == "missing" for norm in classification)
    delegated_acts = [
        norm for norm in norms.values() if norm.subjects[0].subject_ref == "commission"
    ]
    assert len(delegated_acts) == 2
    assert all(norm.implementation_mode.value == "none_required" for norm in delegated_acts)
    presumption = norms["AIA-NORM-A051-P2-COMPUTE-PRESUMPTION"]
    assert presumption.conditions == [
        "cumulative training computation measured in floating-point operations exceeds 10^25"
    ]


def test_article_fifty_two_separates_notification_and_reassessment_procedure():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "52"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A052-")
    }

    assert len(segments) == 8
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 15
    assert [len(segments[index].norm_ids) for index in (1, 3, 6, 7)] == [3, 2, 4, 3]
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 2
    assert all(norm.implementation_refs == ["AIA-GP-A52-1"] for norm in mapped)
    missing = [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert {norm.norm_id for norm in missing} == {
        "AIA-NORM-A052-P3-SYSTEMIC-RISK-CONSEQUENCE",
        "AIA-NORM-A052-P5-REQUEST-CONTENT",
    }
    request_content = norms["AIA-NORM-A052-P5-REQUEST-CONTENT"]
    assert request_content.mandatory_content == [
        "objective reasons",
        "detailed reasons",
        "new reasons arising since the designation decision",
    ]
    permissions = [norm for norm in norms.values() if norm.kind.value == "permission"]
    assert len(permissions) == 2
    assert all(norm.implementation_mode.value == "none_required" for norm in permissions)


def test_article_fifty_three_maps_provider_duties_and_open_source_carveout():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "53"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A053-")
    }

    assert len(segments) == 14
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 20
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 18
    assert not [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    open_source = norms["AIA-NORM-A053-P2-OPEN-SOURCE-EXCEPTION"]
    systemic_override = norms["AIA-NORM-A053-P2-SYSTEMIC-RISK-OVERRIDE"]
    assert open_source.implementation_refs == ["AIA-GP-A53-1A", "AIA-GP-A53-1B"]
    assert systemic_override.implementation_refs == ["AIA-GP-A53-1A", "AIA-GP-A53-1B"]
    provider_rules = {ref for norm in mapped for ref in norm.implementation_refs}
    assert provider_rules == {
        "AIA-GP-A53-1A",
        "AIA-GP-A53-1B",
        "AIA-GP-A53-1C",
        "AIA-GP-A53-1D",
        "AIA-GP-A53-3",
        "AIA-GP-A53-4",
        "AIA-PO-A53-7",
    }


def test_article_fifty_four_maps_representative_mandate_lifecycle():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "54"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A054-")
    }

    assert len(segments) == 11
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 13
    assert all(norm.implementation_refs for norm in norms.values())
    assert not [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    exception = norms["AIA-NORM-A054-P6-OPEN-SOURCE-EXCEPTION"]
    override = norms["AIA-NORM-A054-P6-SYSTEMIC-RISK-OVERRIDE"]
    assert len(exception.implementation_refs) == 5
    assert exception.implementation_refs == override.implementation_refs
    representative = [
        norm
        for norm in norms.values()
        if norm.subjects[0].subject_ref == "authorised_representative"
    ]
    assert len(representative) == 8


def test_article_fifty_five_maps_systemic_risk_provider_controls():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "55"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A055-")
    }

    assert len(segments) == 8
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 14
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 13
    assert not [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert {ref for norm in mapped for ref in norm.implementation_refs} == {
        "AIA-GP-A55-1A",
        "AIA-GP-A55-1B",
        "AIA-GP-A55-1C",
        "AIA-GP-A55-1D",
        "AIA-GP-A55-2",
    }
    incident_report = norms["AIA-NORM-A055-P1-C-REPORT-INCIDENTS"]
    assert len(incident_report.mandatory_content) == 2
    confidentiality = norms["AIA-NORM-A055-P3-CONFIDENTIAL-TREATMENT"]
    assert confidentiality.implementation_mode.value == "none_required"


def test_article_fifty_six_extracts_institutional_code_governance():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "56"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A056-")
    ]

    assert len(segments) == 15
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 21
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)
    assert not [norm for norm in norms if norm.implementation_refs]
    code_coverage = next(norm for norm in norms if norm.norm_id.endswith("P2-CODE-COVERAGE"))
    assert len(code_coverage.mandatory_content) == 4
    assert len(code_coverage.qualifier_spans) == 4
    assert len([norm for norm in norms if norm.kind.value == "power"]) == 3


def test_article_fifty_seven_extracts_complete_sandbox_lifecycle():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "57"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A057-")
    }

    assert len(segments) == 27
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert segments[6].disposition.value == "normative"
    assert segments[6].norm_ids == ["AIA-NORM-A057-P3A-AI-OFFICE-SANDBOX"]
    assert len(norms) == 50
    assert all(norm.implementation_mode.value == "none_required" for norm in norms.values())
    objectives = norms["AIA-NORM-A057-P9-SANDBOX-OBJECTIVES"]
    assert len(objectives.mandatory_content) == 5
    assert len(objectives.qualifier_spans) == 5
    provider_consequences = [
        norm
        for norm in norms.values()
        if norm.subjects[0].category.value == "supported_operator"
    ]
    assert len(provider_consequences) == 4
    assert all(norm.product_scope.value == "no_product_action" for norm in provider_consequences)


def test_article_fifty_eight_extracts_sandbox_implementing_arrangements():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "58"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A058-")
    }

    assert len(segments) == 19
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 6
    assert all(norm.implementation_mode.value == "none_required" for norm in norms.values())
    arrangements = norms["AIA-NORM-A058-P1-DETAILED-SANDBOX-ARRANGEMENTS"]
    outcomes = norms["AIA-NORM-A058-P2-MINIMUM-IMPLEMENTING-ACT-OUTCOMES"]
    assert len(arrangements.mandatory_content) == 4
    assert len(arrangements.qualifier_spans) == 4
    assert len(outcomes.mandatory_content) == 9
    assert len(outcomes.qualifier_spans) == 9

    safeguards = norms["AIA-NORM-A058-P4-AGREE-REAL-WORLD-TESTING-SAFEGUARDS"]
    cooperation = norms["AIA-NORM-A058-P4-COOPERATE-ON-TESTING-PRACTICES"]
    testing_context = "the authority considers authorising supervised real-world sandbox testing"
    assert safeguards.conditions == [testing_context]
    assert cooperation.conditions == [testing_context, "where appropriate"]
    assert safeguards.kind.value == cooperation.kind.value == "obligation"
    assert safeguards.subjects == cooperation.subjects
    assert safeguards.subjects[0].subject_ref == "national_competent_authority"
    assert safeguards.subjects[0].category.value == "public_authority"
    assert "with participants" in safeguards.action
    assert "protect fundamental rights, health and safety" in safeguards.action
    assert "cooperate" not in safeguards.action
    assert safeguards.mandatory_content == [
        "testing terms and conditions", "safeguards protecting fundamental rights health and safety"
    ]
    assert "other national competent authorities" in cooperation.action
    assert "consistent real-world sandbox testing practices across the Union" in cooperation.action
    assert "agree" not in cooperation.action
    assert not cooperation.mandatory_content
    assert "Where appropriate" not in safeguards.norm_text
    assert cooperation.norm_text == (
        "Where appropriate, they shall cooperate with other national competent authorities "
        "with a view to ensuring consistent practices across the Union."
    )
    assert safeguards.primary_spans == cooperation.primary_spans == ["AIA-TEXT-A058-P018"]
    assert segments[-1].norm_ids == [safeguards.norm_id, cooperation.norm_id]
    assert all(norm.review.status.value == "proposed" for norm in norms.values())
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    assert all(not norm.implementation_refs for norm in norms.values())


def test_article_fifty_nine_extracts_conditional_sandbox_data_processing():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "59"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A059-")
    }

    assert len(segments) == 19
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 13
    permission = norms["AIA-NORM-A059-P1-CONDITIONAL-FURTHER-PROCESSING"]
    public_interest = norms["AIA-NORM-A059-P1-A-SUBSTANTIAL-PUBLIC-INTEREST"]
    assert permission.kind.value == "permission"
    assert len(permission.qualifier_spans) == 10
    assert len(public_interest.qualifier_spans) == 5
    assert not public_interest.mandatory_content
    assert public_interest.kind.value == "obligation"
    assert public_interest.subjects[0].subject_ref == "prospective_provider"
    assert public_interest.primary_spans == ["AIA-TEXT-A059-P002"]
    assert public_interest.qualifier_spans == [f"AIA-TEXT-A059-P{n:03}" for n in range(3, 8)]
    assert len(public_interest.conditions) == 1
    requirement = public_interest.conditions[0]
    assert isinstance(requirement, ConditionGroup) and requirement.operator == "all_of"
    assert len(requirement.operands) == 2
    purpose, areas = requirement.operands
    assert purpose == (
        "the AI system is developed for safeguarding substantial public interest by a public "
        "authority or another natural or legal person"
    )
    assert isinstance(areas, ConditionGroup) and areas.operator == "any_of"
    # Only the five enacted areas are alternatives. Their detail, including the health examples,
    # remains within each area instead of becoming extra alternatives or cumulative obligations.
    assert areas.operands == [
        "public safety and public health, including disease detection, diagnosis prevention, "
        "control and treatment and improvement of health care systems",
        "a high level of protection and improvement of the quality of the environment, protection "
        "of biodiversity, protection against pollution, green transition measures, climate change "
        "mitigation and adaptation measures",
        "energy sustainability",
        "safety and resilience of transport systems and mobility, critical infrastructure "
        "and networks",
        "efficiency and quality of public administration and public services",
    ]
    for area, span_id in zip(areas.operands, public_interest.qualifier_spans, strict=True):
        segment = next(segment for segment in segments if segment.segment_id == span_id)
        assert area in segment.text
        assert segment.norm_ids == [public_interest.norm_id]
    assert permission.conditions == [
        "the personal data were lawfully collected for other purposes",
        "processing occurs in an AI regulatory sandbox",
        "every Article 59(1) condition is met",
    ]
    # The parent permission still requires all ten lettered conditions, not any one of them.
    # Each has a child norm; expanding (a) does not duplicate the other conditions at the parent.
    for span_id in permission.qualifier_spans:
        segment = next(segment for segment in segments if segment.segment_id == span_id)
        assert permission.norm_id in segment.norm_ids
        children = [norm_id for norm_id in segment.norm_ids if norm_id != permission.norm_id]
        assert len(children) == 1
        assert norms[children[0]].primary_spans == [span_id]
    assert "every Article 59(1) condition" in (
        norms["AIA-NORM-A059-P2-LAW-ENFORCEMENT-LEGAL-BASIS"].action
    )
    assert all(norm.review.status.value == "proposed" for norm in norms.values())
    assert sum(norm.implementation_mode.value == "missing" for norm in norms.values()) == 11
    assert norms["AIA-NORM-A059-P2-LAW-ENFORCEMENT-LEGAL-BASIS"].product_scope.value == (
        "outside_supported_actor"
    )
    assert norms["AIA-NORM-A059-P3-PRESERVE-OTHER-DATA-LAW"].product_scope.value == (
        "no_product_action"
    )


def test_article_sixty_extracts_real_world_testing_lifecycle():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "60"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A060-")
    }

    assert len(segments) == 23
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 32
    permission = norms["AIA-NORM-A060-P4-PERMISSION"]
    assert len(permission.qualifier_spans) == 11
    assert len(permission.mandatory_content) == 11
    assert sum(norm.implementation_mode.value == "missing" for norm in norms.values()) == 19
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_sixty_registration_routes_are_alternatives_not_a_checklist():
    norms = {
        norm.norm_id: norm
        for norm in load_normative_coverage().norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A060-")
    }

    register = norms["AIA-NORM-A060-P4-C-REGISTER-TESTING"]
    # Three registration routes selected by system class. A mandatory-content list would read as
    # three cumulative registrations, so the exclusive gates are conditions instead.
    assert not register.mandatory_content
    assert len(register.conditions) == 1
    routes = register.conditions[0]
    assert isinstance(routes, ConditionGroup) and routes.operator == "any_of"
    assert [branch.operator for branch in routes.operands] == ["all_of"] * 3
    general, secure, point_two = routes.operands
    assert general.operands == [
        "the system is neither a high-risk AI system referred to in points 1, 6 and 7 of Annex III "
        "in the areas of law enforcement, migration, asylum and border control management nor a "
        "high-risk AI system referred to in point 2 of Annex III",
        "the testing is registered in accordance with Article 71(4) with a Union-wide unique "
        "single identification number and with the information specified in Annex IX",
    ]
    assert secure.operands == [
        "the system is a high-risk AI system referred to in points 1, 6 and 7 of Annex III in the "
        "areas of law enforcement, migration, asylum and border control management",
        "the testing is registered in the secure non-public section of the EU database according "
        "to Article 49(4), point (d), with a Union-wide unique single identification number and "
        "with the information specified therein",
    ]
    assert point_two.operands == [
        "the system is a high-risk AI system referred to in point 2 of Annex III",
        "the testing is registered in accordance with Article 49(5)",
    ]
    assert register.norm_text.endswith("in accordance with Article 49(5);")


def test_article_sixty_separates_deployer_information_consent_and_incident_duties():
    norms = {
        norm.norm_id: norm
        for norm in load_normative_coverage().norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A060-")
    }
    cooperation = (
        "the provider or prospective provider organises the testing in real world conditions in "
        "cooperation with one or more deployers or prospective deployers"
    )

    inform = norms["AIA-NORM-A060-P4-H-INFORM-AND-AGREE-ROLES"]
    agreement = norms["AIA-NORM-A060-P4-H-CONCLUDE-ROLES-AGREEMENT"]
    assert inform.subjects[0].subject_ref == "provider_or_prospective_provider"
    assert agreement.subjects[0].subject_ref == "provider_and_deployer"
    assert inform.conditions == agreement.conditions == [cooperation]
    assert inform.mandatory_content == [
        "all aspects of the testing relevant to the deployer's decision to participate",
        "Article 13 instructions for use of the AI system",
    ]
    assert not agreement.mandatory_content
    assert "conclude an agreement" in agreement.action

    # Law-enforcement status alone does not replace consent: the exception also requires that
    # seeking consent would prevent the system from being tested.
    substitute = [
        "the testing is in the case of law enforcement",
        "seeking informed consent would prevent the AI system from being tested",
    ]
    consent = norms["AIA-NORM-A060-P4-I-CONSENT-OR-SAFEGUARDS"]
    assert not consent.mandatory_content
    assert consent.exceptions == [
        "law-enforcement testing where seeking informed consent would prevent the AI system from "
        "being tested"
    ]
    assert norms["AIA-NORM-A060-P4-I-NO-NEGATIVE-EFFECT"].conditions == substitute
    assert norms["AIA-NORM-A060-P4-I-DELETE-SUBJECT-DATA"].conditions == substitute

    # Withdrawal and the deletion request are separate entitlements of the same person.
    withdraw = norms["AIA-NORM-A060-P5-WITHDRAW-AND-DELETE"]
    delete = norms["AIA-NORM-A060-P5-REQUEST-DATA-DELETION"]
    assert withdraw.kind.value == delete.kind.value == "entitlement"
    assert "without having to provide any justification" in withdraw.action
    assert "immediate and permanent deletion" in delete.action

    # Member States confer the powers; the authorities are the ones that must use them.
    confer = norms["AIA-NORM-A060-P6-CONFER-AND-USE-SURVEILLANCE-POWERS"]
    use = norms["AIA-NORM-A060-P6-USE-SURVEILLANCE-POWERS"]
    assert confer.subjects[0].subject_ref == "member_state"
    assert use.subjects[0].subject_ref == "market_surveillance_authority"
    assert len(confer.mandatory_content) == 3
    assert all(item.startswith("power to") for item in confer.mandatory_content)
    assert not use.mandatory_content

    incident = (
        "a serious incident is identified in the course of the testing in real world conditions"
    )
    report = norms["AIA-NORM-A060-P7-INCIDENT-RESPONSE"]
    mitigate = norms["AIA-NORM-A060-P7-IMMEDIATE-MITIGATION"]
    stop = norms["AIA-NORM-A060-P7-SUSPEND-OR-TERMINATE"]
    recall = norms["AIA-NORM-A060-P7-RECALL-PROCEDURE"]
    assert not report.mandatory_content
    assert report.conditions == mitigate.conditions == [incident]
    # Suspension or termination only follows a failure to adopt immediate mitigation.
    assert stop.conditions == [incident, "immediate mitigation measures are not adopted"]
    assert "or otherwise terminate it" in stop.action
    # The recall procedure duty is not itself conditional; the recall happens upon termination.
    assert not recall.conditions
    assert "upon such termination" in recall.action
    assert all(
        norm.subjects[0].subject_ref == "provider_or_prospective_provider"
        for norm in (report, mitigate, stop, recall)
    )


def test_article_sixty_a_extracts_section_b_testing_framework():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "60a"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A060A-")
    }

    assert len(segments) == 11
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 11
    framework = norms["AIA-NORM-A060A-P5-FRAMEWORK-REQUIREMENTS"]
    assert len(framework.qualifier_spans) == 4
    assert len(framework.mandatory_content) == 4
    assert sum(norm.implementation_mode.value == "missing" for norm in norms.values()) == 3

    # Close good-faith cooperation is owed by every framework State; removing practical obstacles
    # additionally depends on that removal being necessary.
    cooperate = norms["AIA-NORM-A060A-P4-COOPERATE-AND-REMOVE-OBSTACLES"]
    obstacles = norms["AIA-NORM-A060A-P4-REMOVE-PRACTICAL-OBSTACLES"]
    adopted = "the Member State has adopted a real-world testing framework"
    assert cooperate.conditions == [adopted]
    assert obstacles.conditions == [
        adopted,
        "removal is necessary to successfully implement the framework and test Section B "
        "AI-enabled products",
    ]
    assert "physical public infrastructure" in obstacles.action

    # Sectoral compliance is an operator duty; the second sentence limits those requirements.
    comply = norms["AIA-NORM-A060A-P6-COMPLY-WITH-SECTORAL-LAW"]
    limit = norms["AIA-NORM-A060A-P6-SECTORAL-REQUIREMENTS-DO-NOT-OBSTRUCT"]
    assert comply.kind.value == "obligation"
    assert comply.implementation_mode.value == "missing"
    assert limit.kind.value == "legal_consequence"
    assert limit.product_scope.value == "no_product_action"
    assert "to the extent necessary to enable the paragraph 1 testing" in limit.action
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_sixty_one_extracts_informed_consent_requirements():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "61"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A061-")
    }

    assert len(segments) == 8
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 3
    consent = norms["AIA-NORM-A061-P1-OBTAIN-INFORMED-CONSENT"]
    assert len(consent.qualifier_spans) == 5
    assert len(consent.mandatory_content) == 5
    # The information quality is part of the duty, not an optional presentation preference.
    assert "concise, clear, relevant and understandable" in consent.action
    # Point (c) keeps the no-detriment and no-justification safeguards on withdrawal.
    assert consent.mandatory_content[2] == (
        "their rights, and the guarantees regarding their participation, in particular their right "
        "to refuse to participate in, and the right to withdraw from, testing in real world "
        "conditions at any time without any resulting detriment and without having to provide any "
        "justification"
    )
    assert "Article 60(4) point (c)" in consent.mandatory_content[4]
    for item, span_id in zip(consent.mandatory_content, consent.qualifier_spans, strict=True):
        segment = next(segment for segment in segments if segment.segment_id == span_id)
        assert item in " ".join(segment.text.split())

    # Dating/documenting the consent and handing over a copy have different recipients.
    document = norms["AIA-NORM-A061-P2-DOCUMENT-AND-COPY-CONSENT"]
    copy = norms["AIA-NORM-A061-P2-GIVE-CONSENT-COPY"]
    assert document.mandatory_content == ["dated consent", "documented consent"]
    assert not copy.mandatory_content
    assert "subjects of testing or their legal representative" in copy.action
    assert document.primary_spans == copy.primary_spans == ["AIA-TEXT-A061-P007"]
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_sixty_two_extracts_sme_support_measures():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "62"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A062-")
    }

    assert len(segments) == 12
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 13
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    member_state = norms["AIA-NORM-A062-P1-MEMBER-STATE-SME-SUPPORT"]
    ai_office = norms["AIA-NORM-A062-P3-AI-OFFICE-SUPPORT"]
    assert len(member_state.qualifier_spans) == 4
    assert len(ai_office.qualifier_spans) == 4
    # Each lettered action is separately verifiable, so neither chapeau keeps a checklist.
    assert not member_state.mandatory_content
    assert not ai_office.mandatory_content
    for parent in (member_state, ai_office):
        for span_id in parent.qualifier_spans:
            segment = next(s for s in segments if s.segment_id == span_id)
            children = [n for n in segment.norm_ids if n != parent.norm_id]
            assert children
            assert all(norms[child].primary_spans == [span_id] for child in children)

    # Priority access is conditional and does not shut other eligible SMEs out of the sandbox.
    priority = norms["AIA-NORM-A062-P1-A-PRIORITY-SANDBOX-ACCESS"]
    preserved = norms["AIA-NORM-A062-P1-A-PRESERVE-OTHER-SME-ACCESS"]
    assert priority.conditions == [
        "the SME or start-up has a registered office or a branch in the Union",
        "the SME or start-up fulfils the sandbox eligibility conditions and selection criteria",
    ]
    assert preserved.kind.value == "legal_consequence"
    assert preserved.conditions == [
        "the other SMEs or start-ups also fulfil the eligibility conditions and selection criteria"
    ]

    # Using existing channels is unconditional; creating new ones is only where appropriate.
    assert not norms["AIA-NORM-A062-P1-C-USE-EXISTING-CHANNELS"].conditions
    assert norms["AIA-NORM-A062-P1-C-ESTABLISH-NEW-CHANNELS"].conditions == ["where appropriate"]

    # Templates follow a Board request; the other AI Office actions are standing duties.
    assert norms["AIA-NORM-A062-P3-A-PROVIDE-TEMPLATES"].conditions == [
        "the Board specifies the areas in its request"
    ]
    for suffix in (
        "B-INFORMATION-PLATFORM",
        "C-COMMUNICATION-CAMPAIGNS",
        "D-PROCUREMENT-BEST-PRACTICES",
    ):
        assert not norms[f"AIA-NORM-A062-P3-{suffix}"].conditions
    assert norms["AIA-NORM-A062-P2-PROPORTIONATE-SME-FEES"].mandatory_content == [
        "SME size",
        "market size",
        "other relevant indicators",
    ]
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_sixty_three_limits_the_sme_derogation():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "63"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A063-")
    }

    assert len(segments) == 3
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 3
    assert norms["AIA-NORM-A063-P1-SIMPLIFIED-SME-QUALITY-MANAGEMENT"].kind.value == (
        "permission"
    )
    assert norms["AIA-NORM-A063-P2-NO-BROADER-EXEMPTION"].product_scope.value == (
        "no_product_action"
    )


def test_article_sixty_four_extracts_ai_office_support_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "64"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A064-")
    ]

    assert len(segments) == 4
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 3
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)


def test_article_sixty_five_extracts_board_structure_and_operation():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "65"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A065-")
    }

    assert len(segments) == 14
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 16
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    capabilities = norms["AIA-NORM-A065-P4-REPRESENTATIVE-CAPABILITIES"]
    assert len(capabilities.qualifier_spans) == 3
    assert len(capabilities.mandatory_content) == 3
    rules = norms["AIA-NORM-A065-P5-ADOPT-RULES-OF-PROCEDURE"]
    assert len(rules.mandatory_content) == 5

    # Only convening the meetings is triggered by the Chair's request.
    secretariat = norms["AIA-NORM-A065-P8-AI-OFFICE-SECRETARIAT"]
    convene = norms["AIA-NORM-A065-P8-CONVENE-MEETINGS"]
    agenda = norms["AIA-NORM-A065-P8-PREPARE-AGENDA"]
    assert not secretariat.mandatory_content
    assert not secretariat.conditions
    assert convene.conditions == ["the Chair requests the meeting"]
    assert not agenda.conditions
    assert "rules of procedure" in agenda.action
    assert all(
        norm.subjects[0].subject_ref == "ai_office" for norm in (secretariat, convene, agenda)
    )
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_sixty_six_preserves_the_board_task_hierarchy():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "66"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A066-")
    }

    assert len(segments) == 24
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 17
    tasks = norms["AIA-NORM-A066-BOARD-ADVICE-AND-ASSISTANCE-TASKS"]
    powers = norms["AIA-NORM-A066-ENUMERATED-TASK-POWERS"]
    opinions = norms["AIA-NORM-A066-E-RECOMMENDATION-AND-OPINION-TOPICS"]

    # The chapeau imposes one duty; the lettered list is what the Board "may in particular" do.
    assert tasks.kind.value == "obligation"
    assert not tasks.qualifier_spans
    assert not tasks.mandatory_content
    assert powers.kind.value == "power"
    assert len(powers.qualifier_spans) == 15
    assert "not exhaustive" in powers.action
    for span_id in powers.qualifier_spans:
        segment = next(s for s in segments if s.segment_id == span_id)
        children = [n for n in segment.norm_ids if n != powers.norm_id]
        assert len(children) == 1
        child = norms[children[0]]
        assert child.kind.value == "power"
        assert child.primary_spans == [span_id]

    # Point (e) is a power over any relevant matter; the seven topics are inclusions, not a
    # seven-part checklist every opinion must satisfy.
    assert opinions.kind.value == "power"
    assert len(opinions.qualifier_spans) == 7
    assert len(opinions.mandatory_content) == 1
    scope = opinions.mandatory_content[0]
    assert scope.startswith("any relevant matters related to the implementation")
    assert "including" in scope
    for phrase in (
        "codes of conduct",
        "Article 73 serious incident reports",
        "Chapter III, Section 2",
        "Articles 40 and 41",
        "digital skills",
        "AI value chains",
        "revise Article 5 under Article 112",
    ):
        assert phrase in scope
    assert all(norm.review.status.value == "proposed" for norm in norms.values())
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())


def test_article_sixty_seven_extracts_advisory_forum_governance():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "67"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A067-")
    }

    assert len(segments) == 11
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 14
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    assert len(norms["AIA-NORM-A067-P2-BALANCED-MEMBERSHIP"].mandatory_content) == 3
    assert len(norms["AIA-NORM-A067-P5-PERMANENT-MEMBERS"].mandatory_content) == 5

    # Rules, the election and the co-chair term are three effects on one span.
    rules = norms["AIA-NORM-A067-P6-RULES-AND-COCHAIRS"]
    election = norms["AIA-NORM-A067-P6-ELECT-COCHAIRS"]
    term = norms["AIA-NORM-A067-P6-COCHAIR-TERM"]
    assert not rules.mandatory_content
    assert rules.kind.value == election.kind.value == "obligation"
    assert term.kind.value == "legal_consequence"
    assert "paragraph 2" in election.action
    assert "renewable once" in term.action
    assert {n.primary_spans[0] for n in (rules, election, term)} == {"AIA-TEXT-A067-P006"}

    # Two meetings a year are required; inviting experts is not.
    meetings = norms["AIA-NORM-A067-P7-MEETINGS-AND-INVITATIONS"]
    invite = norms["AIA-NORM-A067-P7-INVITE-EXPERTS"]
    assert meetings.kind.value == "obligation"
    assert not meetings.mandatory_content
    assert "at least twice a year" in meetings.action
    assert invite.kind.value == "power"

    # Preparing the annual report and publishing it are separately assessable.
    report = norms["AIA-NORM-A067-P10-ANNUAL-PUBLIC-REPORT"]
    publish = norms["AIA-NORM-A067-P10-PUBLISH-ANNUAL-REPORT"]
    assert not report.mandatory_content
    assert "publicly available" in publish.action
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_sixty_eight_extracts_scientific_panel_safeguards():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "68"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A068-")
    }

    assert len(segments) == 19
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 19
    tasks = norms["AIA-NORM-A068-P3-ADVISE-AND-SUPPORT-AI-OFFICE"]
    gpai = norms["AIA-NORM-A068-P3-A-GPAI-SUPPORT-TASKS"]
    assert len(tasks.qualifier_spans) == 4
    assert len(gpai.qualifier_spans) == 5
    # Each supported task is a separate action, so neither parent keeps a checklist.
    assert not tasks.mandatory_content
    assert not gpai.mandatory_content
    for parent in (tasks, gpai):
        for span_id in parent.qualifier_spans:
            segment = next(s for s in segments if s.segment_id == span_id)
            children = [n for n in segment.norm_ids if n != parent.norm_id]
            assert children
            assert all(norms[child].primary_spans == [span_id] for child in children)

    # Only support for the market surveillance authorities is request-triggered.
    assert norms["AIA-NORM-A068-P3-B-SUPPORT-SURVEILLANCE-AUTHORITIES"].conditions == [
        "the market surveillance authorities request the support"
    ]
    cross_border = norms["AIA-NORM-A068-P3-C-SUPPORT-CROSS-BORDER-SURVEILLANCE"]
    assert not cross_border.conditions
    assert "without prejudice" in cross_border.action
    # Article 90 qualifies the alert task specifically.
    assert "Article 90" in norms["AIA-NORM-A068-P3-A-I-ALERT-SYSTEMIC-RISK"].action

    # The four expert protections are distinct, and the prohibition is typed as one.
    integrity = norms["AIA-NORM-A068-P4-EXPERT-INTEGRITY-AND-DISCLOSURE"]
    assert not integrity.mandatory_content
    assert norms["AIA-NORM-A068-P4-NO-INSTRUCTIONS"].kind.value == "prohibition"
    assert "publicly available" in norms["AIA-NORM-A068-P4-DECLARATION-OF-INTERESTS"].action
    # The AI Office conflict-management duty stays a separate norm rather than being duplicated.
    assert norms["AIA-NORM-A068-P4-MANAGE-CONFLICTS"].subjects[0].subject_ref == "ai_office"
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_sixty_nine_extracts_member_state_expert_access():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "69"
    ]
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A069-")
    ]

    assert len(segments) == 4
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 3
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)


def test_article_seventy_extracts_national_authority_governance():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "70"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A070-")
    }

    assert len(segments) == 10
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 18
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())

    # Designation binds the Member State; independence and member conduct bind the authorities.
    designate = norms["AIA-NORM-A070-P1-DESIGNATE-AND-SAFEGUARD-AUTHORITIES"]
    independence = norms["AIA-NORM-A070-P1-INDEPENDENT-EXERCISE-OF-POWERS"]
    conduct = norms["AIA-NORM-A070-P1-MEMBER-CONDUCT"]
    flexibility = norms["AIA-NORM-A070-P1-ORGANISATIONAL-FLEXIBILITY"]
    assert designate.subjects[0].subject_ref == "member_state"
    assert designate.mandatory_content == [
        "at least one notifying authority",
        "at least one market surveillance authority",
    ]
    assert independence.subjects[0].subject_ref == "national_competent_authority"
    assert conduct.kind.value == "prohibition"
    # Consolidating the tasks is permitted only while those principles are observed.
    assert flexibility.kind.value == "permission"
    assert flexibility.conditions == [
        "the independence, impartiality, objectivity and member-conduct principles are observed"
    ]

    # The disclosure stages have different deadlines and recipients.
    communicate = norms["AIA-NORM-A070-P2-AUTHORITY-AND-CONTACT-DISCLOSURES"]
    contacts = norms["AIA-NORM-A070-P2-PUBLISH-CONTACT-INFORMATION"]
    point = norms["AIA-NORM-A070-P2-DESIGNATE-SINGLE-POINT-OF-CONTACT"]
    assert len(communicate.mandatory_content) == 3
    assert "2 August 2025" in contacts.action
    assert "2 August 2025" not in communicate.action
    assert "single point of contact" in point.action
    # The Commission's list publication was already a separate norm.
    assert norms["AIA-NORM-A070-P2-PUBLISH-CONTACT-LIST"].subjects[0].subject_ref == "commission"

    # Resourcing, staffing and the annual reassessment differ in duty-holder or timing.
    resources = norms["AIA-NORM-A070-P3-ADEQUATE-RESOURCES-AND-COMPETENCE"]
    personnel = norms["AIA-NORM-A070-P3-PERMANENT-EXPERT-PERSONNEL"]
    annual = norms["AIA-NORM-A070-P3-ANNUAL-REASSESSMENT"]
    assert len(resources.mandatory_content) == 4
    assert personnel.subjects[0].subject_ref == "national_competent_authority"
    assert len(personnel.mandatory_content) == 7
    assert annual.subjects[0].subject_ref == "member_state"
    assert "annually" in annual.action
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_seventy_one_extracts_database_and_data_entry_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "71"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A071-")
    }

    assert len(segments) == 7
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 13
    assert sum(norm.implementation_mode.value == "missing" for norm in norms.values()) == 3
    assert len(norms["AIA-NORM-A071-P5-DATABASE-DATA-MINIMISATION"].mandatory_content) == 2

    # Setting up the database and the two consultations happen at different stages.
    setup = norms["AIA-NORM-A071-P1-SET-UP-AND-MAINTAIN-DATABASE"]
    experts = norms["AIA-NORM-A071-P1-CONSULT-EXPERTS-ON-SPECIFICATIONS"]
    board = norms["AIA-NORM-A071-P1-CONSULT-BOARD-ON-UPDATES"]
    assert len(setup.mandatory_content) == 2
    assert experts.conditions == [
        "the Commission is setting the functional specifications of the database"
    ]
    assert board.conditions == [
        "the Commission is updating the functional specifications of the database"
    ]

    # Article 49 and Article 60 information follow different access regimes.
    public = norms["AIA-NORM-A071-P4-DATABASE-ACCESS-RULES"]
    restricted = norms["AIA-NORM-A071-P4-RESTRICTED-ARTICLE-60-ACCESS"]
    presentation = norms["AIA-NORM-A071-P4-NAVIGABLE-MACHINE-READABLE"]
    assert not public.mandatory_content
    assert public.exceptions == [
        "the section referred to in Article 49(4)",
        "the section referred to in Article 60(4), point (c)",
    ]
    assert restricted.exceptions == [
        "the prospective provider or provider has given consent for also making the information "
        "accessible the public"
    ]
    # The enacted "should" is preserved rather than promoted to a duty.
    assert presentation.kind.value == "legal_consequence"
    assert presentation.action.startswith("the information should be")

    # Controllership is a legal consequence; the support duty is a separate action.
    controller = norms["AIA-NORM-A071-P6-CONTROLLER-AND-OPERATOR-SUPPORT"]
    support = norms["AIA-NORM-A071-P6-OPERATOR-SUPPORT"]
    assert controller.kind.value == "legal_consequence"
    assert not controller.mandatory_content
    assert support.mandatory_content == [
        "adequate technical support",
        "adequate administrative support",
    ]
    assert all(norm.review.status.value == "proposed" for norm in norms.values())


def test_article_seventy_two_maps_post_market_monitoring_effects():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "72"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A072-")
    }

    assert len(segments) == 6
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 5
    provider_norms = [
        norm for norm in norms.values() if norm.subjects[0].category.value == "supported_operator"
    ]
    assert len(provider_norms) == 4
    assert all(norm.implementation_refs == ["AIA-PO-A72"] for norm in provider_norms)
    assert len(norms["AIA-NORM-A072-P2-OPERATE-LIFETIME-MONITORING"].mandatory_content) == 3


def test_article_seventy_three_maps_complete_incident_lifecycle():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "73"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A073-")
    }

    assert len(segments) == 14
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 13
    default_mapped = [
        norm for norm in norms.values() if norm.implementation_refs == ["AIA-ALL-A73"]
    ]
    assert len(default_mapped) == 8
    assert norms["AIA-NORM-A073-P10-MEDICAL-DEVICE-REPORTING"].implementation_refs == [
        "AIA-ALL-A73-10"
    ]
    assert len(norms["AIA-NORM-A073-P6-INVESTIGATE-ASSESS-AND-CORRECT"].mandatory_content) == 3


def test_article_seventy_four_maps_provider_access_duties():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "74"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A074-")
    }
    assert len(segments) == 21
    assert all(
        segment.review.status.value == "approved" and segment.review.verified_by == "codex"
        for segment in segments
    )
    assert len(norms) == 14
    documentation_access = norms["AIA-NORM-A074-P12-GRANT-DOCUMENTATION-AND-DATA-ACCESS"]
    source_code_access = norms["AIA-NORM-A074-P13-GRANT-SOURCE-CODE-ACCESS"]
    assert documentation_access.implementation_refs == ["AIA-PO-A74-12"]
    assert source_code_access.implementation_refs == ["AIA-PO-A74-13"]


def test_article_seventy_five_separates_provider_and_authority_effects():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "75"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A075-")
    }

    assert len(segments) == 23
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 25
    assert norms["AIA-NORM-A075-P1A-REPORT-SERIOUS-INCIDENTS"].implementation_refs == [
        "AIA-PO-A75-1a"
    ]
    assert norms["AIA-NORM-A075-P1E-FEES"].implementation_refs == ["AIA-PO-A75-1E"]
    assert len(norms["AIA-NORM-A075-P2A-REQUEST-ASSESSMENT"].mandatory_content) == 3


def test_article_seventy_six_extracts_real_world_testing_supervision():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "76"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A076-")
    }

    assert len(segments) == 9
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 7
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    assert len(norms["AIA-NORM-A076-P3-INTERVENE-IN-TESTING"].mandatory_content) == 2


def test_article_seventy_seven_extracts_fundamental_rights_cooperation():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "77"
    ]
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A077-")
    }

    assert len(segments) == 7
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "codex" for segment in segments)
    assert len(norms) == 7
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
    assert len(norms["AIA-NORM-A077-P2-IDENTIFY-PUBLISH-NOTIFY-AND-UPDATE"].mandatory_content) == 4


def test_article_seventy_eight_maps_the_special_provider_confidentiality_rule():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A078-")
    }

    assert len(norms) == 8
    provider = norms["AIA-NORM-A078-P3-KEEP-DOCUMENTATION-AND-ENABLE-ACCESS"]
    assert provider.implementation_refs == ["AIA-PO-A78-3"]
    assert len(provider.mandatory_content) == 3


def test_article_seventy_nine_maps_operator_enforcement_duties():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A079-")
    }

    assert len(norms) == 14
    mapped = [norm for norm in norms.values() if norm.implementation_refs == ["AIA-ALL-A79"]]
    assert len(mapped) == 2
    assert len(norms["AIA-NORM-A079-P6-NOTIFICATION-CONTENT"].mandatory_content) == 5


def test_article_eighty_maps_reclassified_provider_correction():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A080-")
    }

    assert len(norms) == 9
    mapped = [norm for norm in norms.values() if norm.implementation_refs == ["AIA-PO-A20"]]
    assert len(mapped) == 2
    assert sum(norm.kind.value == "legal_consequence" for norm in norms.values()) == 2


def test_article_eighty_one_extracts_union_safeguard_procedure():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A081-")
    ]

    assert len(norms) == 6
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert {norm.subjects[0].category.value for norm in norms} == {
        "member_state",
        "union_institution_or_body",
    }


def test_article_eighty_two_maps_compliant_system_risk_correction():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A082-")
    }

    assert len(norms) == 6
    assert norms["AIA-NORM-A082-P2-CORRECT-ALL-UNION-SYSTEMS"].implementation_refs == [
        "AIA-ALL-A82"
    ]
    assert len(norms["AIA-NORM-A082-P3-INFORM-ABOUT-RISK-FINDING"].mandatory_content) == 4


def test_article_eighty_three_keeps_formal_defects_as_one_enforcement_cycle():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A083-")
    }

    assert len(norms) == 2
    formal = norms["AIA-NORM-A083-P1-REQUIRE-END-TO-FORMAL-NONCOMPLIANCE"]
    assert len(formal.mandatory_content) == 7
    assert len(formal.qualifier_spans) == 7


def test_article_eighty_four_extracts_testing_support_structure_duties():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A084-")
    ]

    assert len(norms) == 2
    assert all(norm.subjects[0].category.value == "union_institution_or_body" for norm in norms)
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)


def test_article_eighty_five_extracts_complaint_entitlement_and_handling():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A085-")
    }

    assert len(norms) == 2
    assert norms["AIA-NORM-A085-P1-LODGE-COMPLAINT"].kind.value == "entitlement"
    assert norms["AIA-NORM-A085-P2-ACCOUNT-FOR-AND-HANDLE-COMPLAINTS"].subjects[
        0
    ].category.value == "public_authority"


def test_article_eighty_six_maps_the_deployer_explanation_duty():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A086-")
    }

    assert len(norms) == 4
    assert norms["AIA-NORM-A086-P1-PROVIDE-EXPLANATION"].implementation_refs == [
        "AIA-DP-A86"
    ]
    assert norms["AIA-NORM-A086-P1-RIGHT-TO-EXPLANATION"].kind.value == "entitlement"


def test_article_eighty_seven_applies_whistleblower_protection():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A087-")
    ]

    assert len(norms) == 1
    assert norms[0].kind.value == "applicability"
    assert norms[0].product_scope.value == "no_product_action"


def test_article_eighty_eight_extracts_gpai_enforcement_competence():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A088-")
    ]

    assert len(norms) == 3
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert sum(norm.kind.value == "power" for norm in norms) == 2


def test_article_eighty_nine_extracts_downstream_complaint_procedure():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A089-")
    }

    assert len(norms) == 3
    assert norms["AIA-NORM-A089-P2-LODGE-DOWNSTREAM-COMPLAINT"].kind.value == "entitlement"
    assert len(norms["AIA-NORM-A089-P2-COMPLAINT-CONTENT"].mandatory_content) == 3


def test_article_ninety_extracts_scientific_panel_alerts():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A090-")
    }

    assert len(norms) == 4
    assert len(norms["AIA-NORM-A090-P1-ISSUE-QUALIFIED-ALERT"].mandatory_content) == 2
    assert len(norms["AIA-NORM-A090-P3-QUALIFIED-ALERT-CONTENT"].mandatory_content) == 3


def test_article_ninety_one_maps_gpai_information_supply():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A091-")
    }

    assert len(norms) == 7
    assert norms["AIA-NORM-A091-P5-SUPPLY-REQUESTED-INFORMATION"].implementation_refs == [
        "AIA-GP-A91-5"
    ]
    assert len(norms["AIA-NORM-A091-P4-INFORMATION-REQUEST-CONTENT"].mandatory_content) == 4


def test_article_ninety_two_maps_gpai_model_access():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A092-")
    }

    assert len(norms) == 8
    assert norms["AIA-NORM-A092-P5-PROVIDE-MODEL-ACCESS"].implementation_refs == [
        "AIA-GP-A92-5"
    ]
    assert len(norms["AIA-NORM-A092-P1-CONDUCT-GPAI-EVALUATION"].mandatory_content) == 2


def test_article_ninety_three_extracts_commission_measure_powers():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A093-")
    }

    assert len(norms) == 3
    assert len(norms["AIA-NORM-A093-P1-REQUEST-GPAI-MEASURES"].mandatory_content) == 3
    assert norms["AIA-NORM-A093-P3-MAKE-COMMITMENTS-BINDING"].kind.value == "legal_consequence"


def test_article_ninety_four_applies_gpai_procedural_rights():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A094-")
    ]

    assert len(norms) == 1
    assert norms[0].kind.value == "applicability"
    assert norms[0].product_scope.value == "no_product_action"


def test_article_ninety_five_extracts_voluntary_code_framework():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A095-")
    }

    assert len(norms) == 4
    facilitated = norms["AIA-NORM-A095-P2-FACILITATE-SPECIFIC-REQUIREMENT-CODES"]
    assert len(facilitated.mandatory_content) == 5
    assert norms["AIA-NORM-A095-P3-DRAW-UP-VOLUNTARY-CODES"].kind.value == "power"


def test_articles_ninety_six_to_ninety_eight_extract_institutional_procedures():
    bundle = load_normative_coverage()
    by_article = {
        article: [
            norm
            for norm in bundle.norm_inventory.norms
            if norm.norm_id.startswith(f"AIA-NORM-A{article}-")
        ]
        for article in ("096", "097", "098")
    }

    assert {article: len(norms) for article, norms in by_article.items()} == {
        "096": 5,
        "097": 8,
        "098": 2,
    }
    assert len(by_article["096"][0].mandatory_content) == 7
    assert sum(norm.kind.value == "power" for norm in by_article["097"]) == 2
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in by_article["098"])


def test_article_ninety_nine_extracts_penalty_framework():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A099-")
    }

    assert len(norms) == 13
    assert len(norms["AIA-NORM-A099-P4-OPERATOR-FINE"].mandatory_content) == 8
    assert len(norms["AIA-NORM-A099-P7-CONSIDER-FINE-CIRCUMSTANCES"].mandatory_content) == 10


def test_articles_one_hundred_to_one_hundred_five_extract_enforcement_and_amendments():
    bundle = load_normative_coverage()
    counts = {
        article: sum(
            norm.norm_id.startswith(f"AIA-NORM-A{article}-")
            for norm in bundle.norm_inventory.norms
        )
        for article in ("100", "101", "102", "103", "104", "105")
    }

    assert counts == {"100": 7, "101": 7, "102": 1, "103": 1, "104": 1, "105": 1}
    amendments = [
        norm
        for norm in bundle.norm_inventory.norms
        if any(
            norm.norm_id.startswith(f"AIA-NORM-A{article}-")
            for article in ("102", "103", "104", "105")
        )
    ]
    assert all("Chapter III Section 2" in norm.action for norm in amendments)


def test_articles_one_hundred_six_to_one_hundred_ten_extract_amendments():
    bundle = load_normative_coverage()
    counts = {
        article: sum(
            norm.norm_id.startswith(f"AIA-NORM-A{article}-")
            for norm in bundle.norm_inventory.norms
        )
        for article in ("106", "107", "108", "109", "110")
    }

    assert counts == {"106": 1, "107": 1, "108": 6, "109": 1, "110": 1}
    representative_actions = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A110-REPRESENTATIVE-ACTIONS-APPLICABILITY"
    )
    assert representative_actions.kind.value == "applicability"
    assert representative_actions.product_scope.value == "no_product_action"


def test_article_one_hundred_eleven_extracts_transition_rules_and_debt():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A111-")
    }

    assert len(norms) == 6
    assert sum(norm.implementation_mode.value == "missing" for norm in norms.values()) == 4
    assert norms["AIA-NORM-A111-P2-LEGACY-HIGH-RISK-APPLICABILITY"].kind.value == (
        "applicability"
    )


def test_article_one_hundred_twelve_extracts_review_framework():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A112-")
    }

    assert len(norms) == 20
    assert len(norms["AIA-NORM-A112-P2-FOUR-YEAR-EVALUATION"].mandatory_content) == 3
    assert len(norms["AIA-NORM-A112-P4-REPORT-ATTENTION-AREAS"].mandatory_content) == 4
    methodology = norms["AIA-NORM-A112-P11-DEVELOP-RISK-EVALUATION-METHODOLOGY"]
    assert len(methodology.mandatory_content) == 3


def test_articles_seventy_five_a_and_b_extract_ai_office_enforcement_powers():
    bundle = load_normative_coverage()
    article_a = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A075A-")
    }
    article_b = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A075B-")
    ]

    assert len(article_a) == 21
    assert len(article_b) == 3
    assert len(article_a["AIA-NORM-A075A-P4-INSPECTION-POWERS"].mandatory_content) == 5
    assert article_a["AIA-NORM-A075A-P3-VOLUNTARY-REPLY-CORRECTNESS"].implementation_mode.value == (
        "missing"
    )


def test_articles_seventy_five_c_and_d_extract_penalties_and_safeguards():
    bundle = load_normative_coverage()
    article_c = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A075C-")
    }
    article_d = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A075D-")
    }

    assert len(article_c) == 18
    assert len(article_d) == 8
    assert len(article_c["AIA-NORM-A075C-P5-IMPOSE-PERIODIC-PENALTIES"].mandatory_content) == 7
    assert article_d["AIA-NORM-A075D-P2-NEGOTIATED-FILE-ACCESS"].kind.value == "entitlement"


def test_annex_inventory_keeps_external_actors_and_exact_mandatory_content():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    annex_vii = [
        norm for norm in norms.values() if norm.primary_spans[0].startswith("AIA-TEXT-ANNEX-VII-")
    ]
    assert len(annex_vii) == 30
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

    annex_four = norms["AIA-NORM-ANNEX-IV-CONTENT"]
    assert len(annex_four.mandatory_content) == 26
    assert annex_four.qualifier_spans[:10] == [
        "AIA-TEXT-ANNEX-IV-I1",
        *(f"AIA-TEXT-ANNEX-IV-I1-{letter}" for letter in "ABCDEFGH"),
        "AIA-TEXT-ANNEX-IV-I2",
    ]
    assert "cybersecurity measures" in annex_four.mandatory_content


def test_annex_one_extracts_each_harmonisation_instrument_and_its_uav_limit():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-I-")
    }

    assert len(norms) == 21
    assert {norm.primary_spans[0] for norm in norms.values()} == {
        "AIA-TEXT-ANNEX-I-P001",
        "AIA-TEXT-ANNEX-I-P002",
    }
    assert len(norms["AIA-NORM-ANNEX-I-20-UNMANNED-AIRCRAFT"].conditions) == 1
    assert all(norm.kind.value == "applicability" for norm in norms.values())


def test_annex_two_extracts_each_offence_category_under_the_article_five_exception():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-II-")
    ]

    assert len(norms) == 16
    assert all(norm.kind.value == "applicability" for norm in norms)
    assert all(norm.qualifier_spans == ["AIA-TEXT-ANNEX-II-P001"] for norm in norms)
    assert {norm.primary_spans[0] for norm in norms} == {
        f"AIA-TEXT-ANNEX-II-P{index:03d}" for index in range(2, 18)
    }


def test_annex_five_declaration_content_is_carried_by_article_forty_seven():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    annex = norms["AIA-NORM-ANNEX-V-DECLARATION-CONTENT"]
    article = norms["AIA-NORM-A047-P2-ANNEX-V-CONTENT"]

    assert len(annex.mandatory_content) == 8
    assert annex.carried_by_norm_ids == [article.norm_id]
    assert annex.implementation_mode.value == "carried_by_other_norm"
    assert [dependency.dependency_ref for dependency in article.dependencies] == [
        f"AIA-TEXT-ANNEX-V-P{index:03d}" for index in range(2, 10)
    ]


def test_annex_six_internal_control_defines_and_applies_all_three_checks():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-VI-")
    }

    assert len(norms) == 4
    procedure = norms["AIA-NORM-ANNEX-VI-P1-PROCEDURE-CONTENT"]
    assert procedure.kind.value == "applicability"
    assert procedure.qualifier_spans == [
        f"AIA-TEXT-ANNEX-VI-P{index:03d}" for index in range(2, 5)
    ]
    provider_checks = [norm for key, norm in norms.items() if "P1" not in key]
    assert all(norm.subjects[0].subject_ref == "provider" for norm in provider_checks)


def test_annex_seven_completion_covers_change_control_and_certificate_content():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-VII-")
    }

    assert len(norms) == 30
    assert len(norms["AIA-NORM-ANNEX-VII-CERTIFICATE-CONTENT"].mandatory_content) == 6
    assert norms["AIA-NORM-ANNEX-VII-INFORM-CHANGES"].subjects[0].subject_ref == "provider"
    assert norms["AIA-NORM-ANNEX-VII-ADDITIONAL-TESTS"].kind.value == "power"
    assert {norm.primary_spans[0] for norm in norms.values()} == {
        "AIA-TEXT-ANNEX-VII-I1",
        "AIA-TEXT-ANNEX-VII-I2",
        "AIA-TEXT-ANNEX-VII-I3",
        "AIA-TEXT-ANNEX-VII-I4",
        "AIA-TEXT-ANNEX-VII-I5",
    }


def test_annex_nine_registration_content_is_carried_by_article_sixty():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    annex = norms["AIA-NORM-ANNEX-IX-REGISTRATION-INFORMATION"]

    assert len(annex.mandatory_content) == 5
    assert annex.carried_by_norm_ids == ["AIA-NORM-A060-P4-C-REGISTER-TESTING"]
    assert annex.implementation_mode.value == "carried_by_other_norm"
    assert annex.qualifier_spans == [
        f"AIA-TEXT-ANNEX-IX-P{index:03d}" for index in range(2, 7)
    ]


def test_annex_ten_extracts_twelve_large_scale_it_instruments():
    bundle = load_normative_coverage()
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-X-")
    ]

    assert len(norms) == 12
    assert all(norm.kind.value == "applicability" for norm in norms)
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "annex" and segment.source.document == "X"
    ]
    assert sum(segment.disposition.value == "context_only" for segment in segments) == 4


def test_annex_eleven_separates_general_and_systemic_risk_documentation():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-XI-")
    }

    assert len(norms) == 3
    assert len(norms["AIA-NORM-ANNEX-XI-SECTION-1-TECHNICAL-DOCUMENTATION"].mandatory_content) == 11
    systemic = norms["AIA-NORM-ANNEX-XI-SECTION-2-SYSTEMIC-RISK-DOCUMENTATION"]
    assert len(systemic.mandatory_content) == 4
    assert systemic.conditions == ["the general-purpose AI model has systemic risk"]
    assert norms["AIA-NORM-ANNEX-XI-ENERGY-ESTIMATE-BASIS"].kind.value == "permission"


def test_annex_twelve_downstream_transparency_content_is_carried_by_article_fifty_three():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    annex = norms["AIA-NORM-ANNEX-XII-DOWNSTREAM-TRANSPARENCY-INFORMATION"]

    assert len(annex.mandatory_content) == 11
    assert annex.carried_by_norm_ids == ["AIA-NORM-A053-P1-B-ANNEX-XII-CONTENT"]
    assert annex.qualifier_spans == [
        f"AIA-TEXT-ANNEX-XII-P{index:03d}" for index in range(2, 15)
    ]


def test_annex_thirteen_separates_commission_criteria_from_the_user_presumption():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    criteria = norms["AIA-NORM-ANNEX-XIII-CONSIDER-SYSTEMIC-RISK-CRITERIA"]
    presumption = norms["AIA-NORM-ANNEX-XIII-TEN-THOUSAND-BUSINESS-USERS-PRESUMPTION"]

    assert len(criteria.mandatory_content) == 7
    assert criteria.product_scope.value == "outside_supported_actor"
    assert presumption.kind.value == "legal_consequence"
    assert presumption.product_scope.value == "dependency_only"
    assert "10,000" in presumption.action


def test_annex_fourteen_extracts_atomic_designation_code_mappings():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-XIV-")
    }

    assert len(norms) == 25
    assert sum("-AIP-" in norm_id for norm_id in norms) == 11
    assert sum("-AIB-" in norm_id for norm_id in norms) == 3
    assert sum("-AIH-" in norm_id for norm_id in norms) == 8
    assert norms["AIA-NORM-ANNEX-XIV-DESIGNATED-BODIES-ONLY"].kind.value == "prohibition"
    assert norms["AIA-NORM-ANNEX-XIV-USE-CODES-IN-APPLICATION"].subjects[0].subject_ref == (
        "conformity_assessment_body"
    )
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())
