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
    assert metrics.documents_with_extracted_norms == 10
    assert metrics.documents_with_review_debt == 129
    assert metrics.exact_source_characters == 394_667
    assert set(metrics.norms_by_document) == {
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


def test_unextracted_article_is_retained_as_exact_full_body_review_debt():
    bundle = load_normative_coverage()
    article_one = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "1"
    ]

    assert len(article_one) == 1
    segment = article_one[0]
    assert segment.segment_id == "AIA-TEXT-A001-FULL"
    assert segment.start == 0
    assert segment.end == len(
        load_source_body(
            segment.source,
            ROOT / "data" / "policy" / "articles",
            ROOT / "data" / "policy" / "annexes",
        )
    )
    assert segment.disposition.value == "needs_review"
    assert segment.review.status.value == "needs_review"
    assert segment.norm_ids == []


def test_inventory_cannot_be_misreported_as_independently_approved(metrics):
    assert metrics.approved_characters == 0
    assert metrics.needs_review_characters == 357_085
    assert metrics.review_statuses == {"needs_review": 154, "proposed": 132}
    assert metrics.timed_review_records == 0
    assert metrics.total_review_records == 287


def test_semantic_pass_finds_propositions_a_shall_scan_misses(metrics):
    assert metrics.shall_vs_semantic_disagreements == 13
    assert metrics.shall_token_candidate_recall == pytest.approx(69 / 82)
    assert "AIA-NORM-A011-P1-SIMPLIFY" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A043-P5-AMEND" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A060-P4-PERMISSION" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A075-P1E-WITHDRAW" in metrics.semantic_norms_without_shall_token


def test_metrics_expose_many_to_many_and_implementation_debt(metrics):
    assert metrics.normative_segments_with_multiple_norms == 14
    assert metrics.mapping_shape.many_norms_to_one_target == 26
    assert metrics.mapping_shape.many_to_many == 8
    assert metrics.mapping_shape.unmapped == 45
    assert metrics.semantic_vs_existing_implementation_disagreements == 7
    assert metrics.semantic_norms_without_existing_implementation == [
        "AIA-NORM-A011-P1-SIMPLIFY",
        "AIA-NORM-A050-P3-DATA",
        "AIA-NORM-A050-P5-MANNER",
        "AIA-NORM-ANNEX-IV-CONTENT",
        "AIA-NORM-ANNEX-VIII-A",
        "AIA-NORM-ANNEX-VIII-B",
        "AIA-NORM-ANNEX-VIII-C",
    ]
    assert metrics.implementation_debt_norm_ids == [
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
