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
    assert metrics.documents_with_extracted_norms == 12
    assert metrics.documents_with_review_debt == 126
    assert metrics.exact_source_characters == 394_667
    assert set(metrics.norms_by_document) == {
        "article 2",
        "article 3",
        "article 11",
        "article 26",
        "article 43",
        "article 50",
        "article 60",
        "article 75",
        "article 113",
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


def test_inventory_cannot_be_misreported_as_independently_approved(metrics):
    assert metrics.approved_characters == 24_941
    assert metrics.needs_review_characters == 324_704
    assert metrics.review_statuses == {
        "approved": 119,
        "needs_review": 1140,
        "proposed": 353,
    }
    assert metrics.timed_review_records == 0
    assert metrics.total_review_records == 1613


def test_semantic_pass_finds_propositions_a_shall_scan_misses(metrics):
    assert metrics.shall_vs_semantic_disagreements == 104
    assert metrics.shall_token_candidate_recall == pytest.approx(79 / 183)
    assert "AIA-NORM-A011-P1-SIMPLIFY" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A043-P5-AMEND" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A060-P4-PERMISSION" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A075-P1E-WITHDRAW" in metrics.semantic_norms_without_shall_token


def test_metrics_expose_many_to_many_and_implementation_debt(metrics):
    assert metrics.normative_segments_with_multiple_norms == 24
    assert metrics.mapping_shape.many_norms_to_one_target == 26
    assert metrics.mapping_shape.many_to_many == 8
    assert metrics.mapping_shape.unmapped == 146
    assert metrics.semantic_vs_existing_implementation_disagreements == 25
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
        "AIA-NORM-A011-P1-SIMPLIFY",
        "AIA-NORM-A050-P3-DATA",
        "AIA-NORM-A050-P5-MANNER",
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
        "AIA-NORM-A011-P1-SIMPLIFY",
        "AIA-NORM-A050-P3-DATA",
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
