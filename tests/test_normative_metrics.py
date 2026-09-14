"""Normative-coverage measurements and honest review-boundary checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from aiact.norm_loader import load_normative_coverage
from aiact.norm_metrics import measure_normative_coverage, render_coverage_markdown
from aiact.policy_loader import load_policy_spec
from aiact.schemas.norm import (
    ConditionGroup,
    ImplementationMode,
    NormRelationKind,
    ProductScope,
    VerificationMode,
)
from aiact.text_segments import corpus_documents, group_segments, load_source_body

ROOT = Path(__file__).resolve().parents[1]

UNCARRIED_UNREPORTED_NORMS: set[str] = set()


@pytest.fixture(scope="module")
def metrics():
    return measure_normative_coverage(load_normative_coverage())


def assert_segments_are_independently_approved(segments):
    """Segments carry a human sign-off from someone other than the extraction pass.

    Naming the verifier would pin who happened to do the reading, which changes when segments are
    re-read. What must hold is the separation itself.
    """
    for segment in segments:
        assert segment.review.status.value == "approved"
        assert segment.review.verified_by
        assert segment.review.verified_by != segment.review.extracted_by


def assert_extraction_never_approves(norms):
    """Approval is a separate human act, so extraction alone must not produce it.

    Pinning each norm to `proposed` would expire the moment a reviewer signs one off. What holds
    for the life of the corpus is the separation: the semantic pass extracts, and only a verifier
    who is not that pass can approve.
    """
    for norm in norms:
        assert norm.review.extracted_by == "semantic-legal-effect-pass"
        if norm.review.status.value == "approved":
            assert norm.review.verified_by
            assert norm.review.verified_by != norm.review.extracted_by


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


def test_segment_norm_linkages_are_unique():
    bundle = load_normative_coverage()

    for segment in bundle.text_review.segments:
        assert len(segment.norm_ids) == len(set(segment.norm_ids)), segment.segment_id
        assert len(segment.qualifying_norm_ids) == len(set(segment.qualifying_norm_ids)), (
            segment.segment_id
        )


def test_segment_primary_links_are_supported_by_the_segments_own_text():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    for segment in bundle.text_review.segments:
        for norm_id in segment.norm_ids:
            assert norms[norm_id].norm_text in segment.text, (segment.segment_id, norm_id)


def test_every_classification_question_target_names_a_cascade_node():
    """`applicability_question` claims the cascade decides a norm, so the claim must be checkable.

    The manifest declares one `AIA-CQ-` target per cascade node. Holding the two sets equal means a
    norm cannot point at a question that was renamed or deleted, and a new node cannot be added
    without deciding which norms it answers."""
    from aiact.classify.graph import QUESTIONS

    manifest = yaml.safe_load(
        (
            ROOT / "data/policy/normative-coverage/2026-07-27/source-records/manifest.yaml"
        ).read_text()
    )
    declared = {t for t in manifest["implementation_targets"] if t.startswith("AIA-CQ-")}

    assert declared == {f"AIA-CQ-{node.upper().replace('_', '-')}" for node in QUESTIONS}


def test_a_classification_answered_norm_points_at_a_cascade_node():
    """The two columns must agree: a norm the cascade answers is implemented by a question, and a
    norm implemented by a question is one the cascade answers."""
    bundle = load_normative_coverage()
    in_scope = [
        norm for norm in bundle.norm_inventory.norms if norm.product_scope is ProductScope.IN_SCOPE
    ]
    by_question = [
        norm
        for norm in in_scope
        if norm.implementation_mode is ImplementationMode.APPLICABILITY_QUESTION
    ]

    assert by_question
    for norm in by_question:
        assert norm.verification_mode is VerificationMode.ANSWERED_BY_CLASSIFICATION, norm.norm_id
        assert norm.implementation_refs, norm.norm_id
        assert all(ref.startswith("AIA-CQ-") for ref in norm.implementation_refs), norm.norm_id


def test_a_norm_agrees_with_the_document_verifiability_of_its_rules():
    """A rule's `document_verifiable` already decides how the gap layer treats it: true reaches the
    judge, false is reported as an outstanding confirmation. A norm naming that rule must say the
    same thing, or the ledger promises a verdict the pipeline never produces.

    `reported_conditionally` is exempt: a carve-out is shown conditionally whatever its rule does.
    So is a norm whose rules disagree with each other, which the mapping does not forbid."""
    bundle = load_normative_coverage()
    verifiable = {rule.rule_id: rule.document_verifiable for rule in load_policy_spec().rules}
    judged = {
        VerificationMode.JUDGED_BY_GAP_ANALYSIS,
        VerificationMode.REPORTED_NOT_JUDGED,
    }

    for norm in bundle.norm_inventory.norms:
        if norm.product_scope is not ProductScope.IN_SCOPE:
            continue
        if norm.verification_mode not in judged:
            continue
        rules = [ref for ref in norm.implementation_refs if ref in verifiable]
        if not rules or len({verifiable[ref] for ref in rules}) != 1:
            continue
        expected = (
            VerificationMode.JUDGED_BY_GAP_ANALYSIS
            if verifiable[rules[0]]
            else VerificationMode.REPORTED_NOT_JUDGED
        )
        assert norm.verification_mode is expected, (
            f"{norm.norm_id} is {norm.verification_mode.value} but {rules} are "
            f"document_verifiable={verifiable[rules[0]]}"
        )


def test_an_in_scope_duty_is_never_dropped_from_the_report():
    """An in-scope norm binds the reader, so omitting it understates what they owe.

    `not_reported` belongs to norms binding someone the product does not report for. The one
    in-scope exception is a norm another norm already reports, which is a presentation choice
    rather than a silence."""
    bundle = load_normative_coverage()
    unreported = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.product_scope is ProductScope.IN_SCOPE
        and norm.verification_mode is VerificationMode.NOT_REPORTED
    ]
    carried = [
        norm
        for norm in unreported
        if norm.implementation_mode is ImplementationMode.CARRIED_BY_OTHER_NORM
    ]

    assert {norm.norm_id for norm in unreported} - {
        norm.norm_id for norm in carried
    } == UNCARRIED_UNREPORTED_NORMS
    assert all(
        bundle.norm_inventory.target_norm_ids_for(norm.norm_id, NormRelationKind.CARRIED_BY_NORMS)
        for norm in carried
    )


def test_a_carried_norm_names_a_carrier_that_is_itself_reported():
    """Carrying only relocates a duty. A carrier that is itself unreported hides both norms, which
    the carried norm's own status cannot reveal."""
    bundle = load_normative_coverage()
    by_id = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    carried = [
        norm
        for norm in bundle.norm_inventory.norms
        if norm.product_scope is ProductScope.IN_SCOPE
        and norm.implementation_mode is ImplementationMode.CARRIED_BY_OTHER_NORM
    ]

    assert carried
    for norm in carried:
        assert bundle.norm_inventory.target_norm_ids_for(
            norm.norm_id, NormRelationKind.CARRIED_BY_NORMS
        ), norm.norm_id
        for carrier_id in bundle.norm_inventory.target_norm_ids_for(
            norm.norm_id, NormRelationKind.CARRIED_BY_NORMS
        ):
            carrier = by_id[carrier_id]
            assert carrier.verification_mode is not VerificationMode.NOT_REPORTED, (
                f"{norm.norm_id} is carried by {carrier_id}, which is itself not reported"
            )


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
    assert metrics.exact_source_characters == 395_046
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
    assert segments["AIA-TEXT-A002-P001"].norm_ids == []
    assert set(segments["AIA-TEXT-A002-P001"].qualifying_norm_ids) == set(norms)
    for index, norm in enumerate(norms.values(), start=2):
        assert norm.kind.value == "applicability"
        assert norm.primary_spans == [f"AIA-TEXT-A002-P{index:03d}"]
        assert norm.qualifier_spans == ["AIA-TEXT-A002-P001"]
        assert norm.implementation_mode.value == "applicability_question"


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
    norms = [norm for norm in bundle.norm_inventory.norms if norm.norm_id in segment.norm_ids]

    assert segment.disposition.value == "normative"
    assert {norm.norm_id for norm in norms} == {
        "AIA-NORM-A002-P3-OUTSIDE-UNION-LAW",
        "AIA-NORM-A002-P3-NATIONAL-SECURITY-COMPETENCE",
    }
    assert all(norm.product_scope.value == "no_product_action" for norm in norms)
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)
    assert all(norm.verification_mode.value == "not_reported" for norm in norms)


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
    assert norm.implementation_mode.value == "applicability_question"
    assert norm.verification_mode.value == "answered_by_classification"


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
    assert norm.implementation_mode.value == "applicability_question"
    assert norm.verification_mode.value == "answered_by_classification"


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
    assert norm.implementation_mode.value == "applicability_question"
    assert norm.verification_mode.value == "answered_by_classification"


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
    assert norm.verification_mode.value == "not_reported"
    assert norm.dependencies[0].dependency_ref == "Regulation (EU) 2022/2065, Chapter II"


def test_article_two_is_fully_reviewed_as_twenty_eight_atomic_norms():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "2"
    ]
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A002-")
    ]

    assert len(segments) == 26
    assert segments[0].disposition.value == "structural"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 27


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
    assert segments[norm.primary_spans[0]].norm_ids == [norm.norm_id]
    for segment_id in norm.qualifier_spans:
        assert segments[segment_id].qualifying_norm_ids == [norm.norm_id]


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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A003-")
    ]

    assert len(segments) == 83
    assert segments[0].disposition.value == "structural"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 72
    assert sum(norm.kind.value == "definition" for norm in norms) == 70
    assert sum(norm.kind.value == "legal_consequence" for norm in norms) == 2
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

    assert segments["AIA-TEXT-A003-P001"].norm_ids == []
    assert set(segments["AIA-TEXT-A003-P001"].qualifying_norm_ids) == set(definitions)
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
    }
    assert expected <= set(norms)
    for norm_id in expected:
        norm = norms[norm_id]
        assert norm.kind.value == "legal_consequence"
        assert norm.product_scope.value == "dependency_only"
        assert norm.implementation_mode.value == "none_required"
    testing = norms["AIA-NORM-A003-D057-TESTING-IN-REAL-WORLD-CONDITIONS"]
    assert len(testing.mandatory_content) == 2
    assert "does not qualify as placing" in testing.norm_text


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
    assert norm.implementation_mode.value == "compliance_rule"
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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A004A-")
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
    imported = set(
        bundle.norm_inventory.target_norm_ids_for(
            permission.norm_id, NormRelationKind.RELIES_ON_NORMS
        )
    )
    imported = {norm_id for norm_id in imported if norm_id.startswith("AIA-NORM-A004A-P1-")}
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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A005-")
    ]

    assert len(segments) == 35
    assert segments[0].disposition.value == "structural"
    assert segments[0].review.status.value == "approved"
    assert all(segment.disposition.value == "normative" for segment in segments[1:])
    assert all(segment.review.status.value == "approved" for segment in segments[1:])
    assert all(segment.review.verified_by == "vidibro" for segment in segments[1:])
    assert len(norms) == 38
    assert sum(norm.kind.value == "obligation" for norm in norms) == 17
    assert sum(norm.kind.value == "prohibition" for norm in norms) == 12
    assert sum(norm.kind.value == "applicability" for norm in norms) == 2
    assert sum(norm.kind.value == "legal_consequence" for norm in norms) == 3
    assert sum(norm.kind.value == "permission" for norm in norms) == 1
    assert sum(norm.kind.value == "power" for norm in norms) == 3


def test_article_five_paragraph_one_chapeau_qualifies_ten_prohibitions():
    bundle = load_normative_coverage()
    segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A005-P001"
    )
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id in segment.qualifying_norm_ids
    }

    assert segment.norm_ids == []
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


def test_article_five_norm_text_preserves_same_segment_exceptions():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    criminal_risk = norms["AIA-NORM-A005-P1-D-CRIMINAL-RISK-PROFILING"]
    biometric_categories = norms["AIA-NORM-A005-P1-G-SENSITIVE-BIOMETRIC-CATEGORISATION"]
    registration = norms["AIA-NORM-A005-P2-REGISTER-SYSTEM"]

    assert "this prohibition shall not apply" in criminal_risk.norm_text
    assert "this prohibition does not cover" in biometric_categories.norm_text
    assert "duly justified cases of urgency" in registration.norm_text
    assert "completed without undue delay" in registration.norm_text


def test_article_six_is_fully_approved_and_atomically_classified():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "6"
    ]
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A006-")
    ]

    assert len(segments) == 20
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 14
    assert sum(norm.kind.value == "applicability" for norm in norms) == 7
    assert sum(norm.kind.value == "obligation" for norm in norms) == 5
    assert sum(norm.kind.value == "power" for norm in norms) == 1
    assert sum(norm.kind.value == "prohibition" for norm in norms) == 1


def test_article_six_norm_text_preserves_classification_scope_and_delegated_act_gates():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    annex_i = norms["AIA-NORM-A006-P1-ANNEX-I-HIGH-RISK"]
    safety_override = norms["AIA-NORM-A006-P1B-HEALTH-SAFETY-OVERRIDE"]
    add_conditions = norms["AIA-NORM-A006-P6-AMEND-EXCEPTIONS"]
    delete_conditions = norms["AIA-NORM-A006-P7-DELETE-EXCEPTIONS"]

    assert annex_i.norm_text.startswith("Irrespective of whether")
    assert "regardless of whether" in annex_i.action
    assert safety_override.norm_text.startswith("Notwithstanding paragraph 1a")
    assert "AIA-NORM-A006-P1A-NON-SAFETY-ASSISTANCE" in (
        bundle.norm_inventory.target_norm_ids_for(
            safety_override.norm_id, NormRelationKind.RELIES_ON_NORMS
        )
    )
    assert "concrete and reliable evidence" in add_conditions.norm_text
    assert "concrete and reliable evidence" in delete_conditions.norm_text


def test_articles_eight_to_ten_norm_text_preserves_same_segment_qualifiers():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    product_compliance = norms["AIA-NORM-A008-P2-ENSURE-PRODUCT-COMPLIANCE"]
    integration = norms["AIA-NORM-A008-P2-INTEGRATE-COMPLIANCE-PROCESSES"]
    risk_interactions = norms["AIA-NORM-A009-P4-CONSIDER-INTERACTIONS"]
    combined_process = norms["AIA-NORM-A009-P10-INTEGRATE-RISK-PROCESSES"]
    special_data = norms["AIA-NORM-A010-P5-SPECIAL-CATEGORY-PROCESSING"]

    assert product_compliance.norm_text.startswith("Where a product contains an AI system")
    assert integration.norm_text.startswith("In ensuring the compliance of high-risk AI systems")
    assert integration.conditions == [
        *product_compliance.conditions,
        "integration is appropriate for ensuring consistency, avoiding duplication, and minimising "
        "additional burdens",
    ]
    assert "with a view to minimising risks" in risk_interactions.norm_text
    assert combined_process.norm_text.startswith("For providers of high-risk AI systems")
    assert special_data.norm_text.startswith("To the extent that it is strictly necessary")


def test_articles_eleven_to_fourteen_norm_text_preserves_operative_context():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    annex_amendment = norms["AIA-NORM-A011-P3-AMEND"]
    automatic_logging = norms["AIA-NORM-A012-P1-AUTOMATIC-LOGGING"]
    two_person_check = norms["AIA-NORM-A014-P5-TWO-PERSON-VERIFICATION"]

    assert "in light of technical progress" in annex_amendment.norm_text
    assert "all the information necessary" in annex_amendment.norm_text
    assert annex_amendment.conditions
    assert automatic_logging.norm_text.startswith("High-risk AI systems")
    assert two_person_check.norm_text.startswith("For high-risk AI systems")


def test_article_nineteen_external_law_overrides_both_ordinary_log_period_rules():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    retention_period = norms["AIA-NORM-A019-P1-RETENTION-PERIOD"]

    assert "at least six months" in retention_period.action
    assert "applicable Union or national law" in retention_period.exceptions[0]
    assert "unless provided otherwise" in retention_period.norm_text
    assert "AIA-NORM-A019-P1-OTHER-LAW-PERIOD" not in norms


def test_article_twenty_six_preserves_structured_triggers_and_complete_log_retention_rule():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    risk_notice = norms["AIA-NORM-A026-P5-RISK-NOTIFY"]
    incident_notice = norms["AIA-NORM-A026-P5-INCIDENT"]
    authorisation = norms["AIA-NORM-A026-P10-REQUEST-AUTHORISATION"]
    retention = norms["AIA-NORM-A026-P6-KEEP-CONTROLLED-LOGS"]

    assert risk_notice.conditions == [
        "the deployer has reason to consider that use in accordance with the instructions may "
        "result in the AI system presenting a risk within the meaning of Article 79(1)"
    ]
    assert incident_notice.norm_text.startswith("Where deployers have identified")
    assert authorisation.exceptions == [
        "initial identification of a potential suspect based on objective and verifiable facts "
        "directly linked to the offence"
    ]
    assert set(
        bundle.norm_inventory.target_norm_ids_for(
            authorisation.norm_id, NormRelationKind.RELIES_ON_NORMS
        )
    ) == {
        "AIA-NORM-A026-P10-PRESERVE-DIRECTIVE-2016-680"
    }
    assert retention.norm_text.startswith("Deployers of high-risk AI systems shall keep")
    assert "period appropriate to the intended purpose" in retention.norm_text
    assert "at least six months" in retention.action
    assert retention.exceptions == [
        "applicable Union or national law, particularly personal-data law, provides a different "
        "retention period"
    ]
    assert (
        not {
            "AIA-NORM-A026-P6-PURPOSE-APPROPRIATE-PERIOD",
            "AIA-NORM-A026-P6-SIX-MONTH-MINIMUM",
            "AIA-NORM-A026-P6-OTHER-LAW-PERIOD",
        }
        & norms.keys()
    )


def test_article_twenty_eight_unified_application_norm_names_its_authority_and_gate():
    bundle = load_normative_coverage()
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A028-P8-SINGLE-APPLICATION"
    )

    assert norm.norm_text.startswith("Notifying authorities designated pursuant to this Regulation")
    assert "where the relevant Union harmonisation legislation provides" in norm.norm_text


def test_article_thirty_one_liability_insurance_preserves_both_exceptions():
    bundle = load_normative_coverage()
    norm = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A031-P9-LIABILITY-INSURANCE"
    )

    assert len(norm.exceptions) == 2
    assert "liability is assumed by the Member State" in norm.exceptions[0]
    assert "Member State is itself directly responsible" in norm.exceptions[1]


def test_article_thirty_six_preserves_triggers_and_alternative_validity_routes():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    investigation = norms["AIA-NORM-A036-P4-INVESTIGATE-FAILURE"]
    provider_notice = norms["AIA-NORM-A036-P5-INFORM-PROVIDERS"]
    validity = norms["AIA-NORM-A036-P8-SUSPENSION-CERTIFICATE-VALIDITY"]

    assert "sufficient reason" in investigation.conditions[0]
    assert "suspended, restricted" in provider_notice.conditions[0]
    assert validity.exceptions == ["certificates that were unduly issued"]
    alternatives = validity.conditions[1]
    assert isinstance(alternatives, ConditionGroup) and alternatives.operator == "any_of"
    assert len(alternatives.operands) == 2
    assert all(
        isinstance(route, ConditionGroup) and route.operator == "all_of"
        for route in alternatives.operands
    )


def test_articles_forty_one_to_forty_six_preserve_gates_and_exceptions():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    standard = norms["AIA-NORM-A041-P4-ASSESS-HARMONISED-STANDARD"]
    modification = norms["AIA-NORM-A043-P4-NEW-ASSESSMENT"]
    certificate = norms["AIA-NORM-A044-P3-CERTIFICATE-MEASURE"]
    consultation = norms["AIA-NORM-A046-P5-CONSULT-MEMBER-STATE"]

    assert "adopted a harmonised standard" in standard.conditions[0]
    assert len(modification.conditions) == 2
    assert "corrective action" in certificate.exceptions[0]
    alternatives = consultation.conditions[0]
    assert isinstance(alternatives, ConditionGroup) and alternatives.operator == "any_of"
    assert len(alternatives.operands) == 3


def test_article_fifty_retains_complete_operative_context_without_merging_norms():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    interaction = norms["AIA-NORM-A050-P1-DISCLOSE"]
    synthetic = norms["AIA-NORM-A050-P2-MARK-DETECT"]
    emotion = norms["AIA-NORM-A050-P3-INFORM"]
    deepfake = norms["AIA-NORM-A050-P4-DEEPFAKE"]
    manner = norms["AIA-NORM-A050-P5-MANNER"]
    implementing_act = norms["AIA-NORM-A050-P7-ACT"]

    assert "unless this is obvious" in interaction.norm_text
    assert "effective, interoperable, robust and reliable" in synthetic.norm_text
    assert emotion.subjects[0].subject_ref == "deployer"
    assert "process the personal data" not in emotion.norm_text
    assert norms["AIA-NORM-A050-P3-DATA"].norm_text.startswith("shall process")
    assert "evidently artistic, creative, satirical" in deepfake.norm_text
    assert "time of the first interaction or exposure" in manner.norm_text
    assert "examination procedure laid down in Article 98(2)" in implementing_act.norm_text
    assert implementing_act.conditions == ["the Commission deems the code of practice inadequate"]


def test_list_item_norms_retain_their_enacting_chapeaux():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    documentation = norms["AIA-NORM-A053-P1-B-DRAW-KEEP-AND-MAKE-AVAILABLE-DOCUMENTATION"]
    assert documentation.qualifier_spans == ["AIA-TEXT-A053-P001"]
    incidents = norms["AIA-NORM-A055-P1-C-TRACK-DOCUMENT-AND-REPORT-INCIDENTS"]
    assert incidents.qualifier_spans == ["AIA-TEXT-A055-P001"]
    assert norms["AIA-NORM-A060-P4-K-REVERSIBLE-OUTPUTS"].qualifier_spans == ["AIA-TEXT-A060-P006"]
    assert norms["AIA-NORM-A062-P1-D-FACILITATE-STANDARDISATION-PARTICIPATION"].qualifier_spans == [
        "AIA-TEXT-A062-P001"
    ]
    assert norms["AIA-NORM-A066-A-TASK"].qualifier_spans == ["AIA-TEXT-A066-P001"]


def test_article_sixty_preserves_alternative_eligibility_and_approval_routes():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    permission = norms["AIA-NORM-A060-P1-REAL-WORLD-TESTING-PERMISSION"]
    approval = norms["AIA-NORM-A060-P4-B-APPROVAL-AND-TACIT-EFFECT"]
    establishment = norms["AIA-NORM-A060-P4-D-UNION-ESTABLISHMENT"]

    assert isinstance(permission.conditions[0], ConditionGroup)
    assert permission.conditions[0].operator == "any_of"
    assert isinstance(approval.conditions[0], ConditionGroup)
    assert approval.conditions[0].operator == "any_of"
    assert approval.conditions[0].operands[1].operator == "all_of"
    assert isinstance(establishment.conditions[0], ConditionGroup)
    assert establishment.conditions[0].operator == "any_of"


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
        "AIA-NORM-A006-P2-ANNEX-III-HIGH-RISK"
        in bundle.norm_inventory.target_norm_ids_for(
            norm.norm_id, NormRelationKind.RELIES_ON_NORMS
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
        norms["AIA-NORM-A007-P2-ADVERSE-OUTCOME-NOT-REVERSIBLE"].kind.value == "legal_consequence"
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
    chapeau = norms["AIA-NORM-A008-P1-COMPLY-SECTION-REQUIREMENTS"]
    assert chapeau.implementation_mode.value == "carried_by_other_norm"
    assert bundle.norm_inventory.target_norm_ids_for(
        chapeau.norm_id, NormRelationKind.CARRIED_BY_NORMS
    ) == ["AIA-NORM-A016-A-SECTION-2-COMPLIANCE"]
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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A009-")
    ]

    assert len(segments) == 20
    assert all(segment.review.status.value == "approved" for segment in segments)
    assert all(segment.review.verified_by == "vidibro" for segment in segments)
    assert len(norms) == 21
    assert sum(norm.kind.value == "obligation" for norm in norms) == 18
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
    assert len(norms) == 21
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 18
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 2
    assert sum(norm.kind.value == "applicability" for norm in norms.values()) == 1
    assert len(norms["AIA-NORM-A010-P3-DATASET-QUALITY"].mandatory_content) == 4

    carried_by = {
        "AIA-NORM-A010-P5-SPECIAL-CATEGORY-PROCESSING": (
            "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING"
        ),
        "AIA-NORM-A010-P5-B-REUSE-SECURITY": "AIA-NORM-A004A-P1-B-REUSE-SECURITY",
        "AIA-NORM-A010-P5-C-ACCESS-SAFEGUARDS": ("AIA-NORM-A004A-P1-C-ACCESS-SAFEGUARDS"),
        "AIA-NORM-A010-P5-D-NO-THIRD-PARTY-ACCESS": ("AIA-NORM-A004A-P1-D-NO-THIRD-PARTY-ACCESS"),
        "AIA-NORM-A010-P5-E-DELETE-DATA": "AIA-NORM-A004A-P1-E-DELETE-DATA",
        "AIA-NORM-A010-P5-F-RECORD-NECESSITY": ("AIA-NORM-A004A-P1-F-RECORD-NECESSITY"),
    }
    for norm_id, carrier_id in carried_by.items():
        norm = norms[norm_id]
        assert norm.implementation_mode.value == "carried_by_other_norm"
        assert bundle.norm_inventory.target_norm_ids_for(
            norm.norm_id, NormRelationKind.CARRIED_BY_NORMS
        ) == [carrier_id]

    uniquely_implemented = set(norms) - set(carried_by)
    assert all(
        norms[norm_id].implementation_refs == ["AIA-HR-A10"] for norm_id in uniquely_implemented
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
    assert len(norms) == 9
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 7
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1
    assert sum(norm.kind.value == "power" for norm in norms.values()) == 1

    draw = norms["AIA-NORM-A011-P1-DRAW"]
    demonstrate = norms["AIA-NORM-A011-P1-DEMONSTRATE"]
    assert draw.primary_spans == demonstrate.primary_spans == ["AIA-TEXT-A011-P1"]
    assert len(draw.mandatory_content) == 2
    assert len(demonstrate.mandatory_content) == 2

    single_set = norms["AIA-NORM-A011-P2-SINGLE-DOCUMENTATION-SET"]
    assert single_set.primary_spans == ["AIA-TEXT-A011-P2"]
    assert single_set.implementation_refs == ["AIA-HR-A11-2"]
    assert bundle.norm_inventory.target_norm_ids_for(
        single_set.norm_id, NormRelationKind.RELIES_ON_NORMS
    ) == ["AIA-NORM-A011-P1-ANNEX-IV"]
    assert [dependency.resolution.value for dependency in single_set.dependencies] == [
        "external_recorded"
    ]


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
    # One rule per lettered record, so a missing record is named rather than folded into a single
    # verdict over the list.
    assert {norm_id: norms[norm_id].implementation_refs for norm_id in biometric} == {
        "AIA-NORM-A012-P3-A-USE-PERIOD": ["AIA-HR-A12-3A"],
        "AIA-NORM-A012-P3-B-REFERENCE-DATABASE": ["AIA-HR-A12-3B"],
        "AIA-NORM-A012-P3-C-MATCHED-INPUT": ["AIA-HR-A12-3C"],
        "AIA-NORM-A012-P3-D-RESULT-VERIFIERS": ["AIA-HR-A12-3D"],
    }
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A012-P002"]
        for norm_id in general
        if "-P2-" in norm_id
    )
    assert all(norms[norm_id].qualifier_spans == ["AIA-TEXT-A012-P006"] for norm_id in biometric)


def test_article_thirteen_keeps_instruction_requirements_complete_without_overlap():
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
    assert len(norms) == 16
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    transparency = {norm_id for norm_id in norms if "-P1-" in norm_id or "-P2-" in norm_id}
    contents = set(norms) - transparency
    assert len(transparency) == 3
    assert len(contents) == 13
    assert all(norms[norm_id].implementation_refs == ["AIA-HR-A13"] for norm_id in transparency)
    assert all(norms[norm_id].implementation_refs == ["AIA-HR-A13-3"] for norm_id in contents)
    assert all("AIA-TEXT-A013-P003" in norms[norm_id].qualifier_spans for norm_id in contents)
    nested_characteristics = {
        norm_id for norm_id in contents if "-P3-B-" in norm_id and "CHARACTERISTICS" not in norm_id
    }
    assert len(nested_characteristics) == 7
    assert len(norms["AIA-NORM-A013-P2-PROVIDE-INSTRUCTIONS"].mandatory_content) == 7
    assert all(
        "AIA-TEXT-A013-P005" in norms[norm_id].qualifier_spans for norm_id in nested_characteristics
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
    assert len(norms) == 10
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 9
    assert sum(norm.kind.value == "applicability" for norm in norms.values()) == 1
    assert all(norm.implementation_refs == ["AIA-HR-A14"] for norm in norms.values())

    route = norms["AIA-NORM-A014-P3-COMMENSURATE-MEASURES"]
    assert len(route.mandatory_content) == 2
    assert route.qualifier_spans == ["AIA-TEXT-A014-P004", "AIA-TEXT-A014-P005"]
    capabilities = [norm for norm_id, norm in norms.items() if "-P4-" in norm_id]
    assert len(capabilities) == 5
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
    assert len(norms) == 14
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 13
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1

    commission = norms["AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"]
    assert commission.implementation_mode.value == "none_required"
    provider_norms = set(norms) - {commission.norm_id}
    assert all(norms[norm_id].implementation_refs == ["AIA-HR-A15"] for norm_id in provider_norms)

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
    assert {norms[norm_id].norm_text for norm_id in threats} == {
        "attacks trying to manipulate the training data set (data poisoning)",
        "pre-trained components used in training (model poisoning)",
        "inputs designed to cause the AI model to make a mistake "
        "(adversarial examples or model evasion)",
        "confidentiality attacks",
        "model flaws",
    }


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

    assert norms["AIA-NORM-A016-B-PROVIDER-IDENTIFICATION"].implementation_refs == ["AIA-PO-A16-B"]
    assert norms["AIA-NORM-A016-K-DEMONSTRATE-CONFORMITY"].implementation_refs == ["AIA-PO-A16-K"]
    assert norms["AIA-NORM-A016-L-ACCESSIBILITY"].implementation_refs == ["AIA-PO-A16-L"]
    assert len(norms["AIA-NORM-A016-A-SECTION-2-COMPLIANCE"].implementation_refs) == 14
    assert len(norms["AIA-NORM-A016-F-CONFORMITY-ASSESSMENT"].implementation_refs) == 6
    corrective = norms["AIA-NORM-A016-J-CORRECTIVE-ACTION"]
    assert corrective.implementation_mode.value == "carried_by_other_norm"
    assert (
        len(
            bundle.norm_inventory.target_norm_ids_for(
                corrective.norm_id, NormRelationKind.CARRIED_BY_NORMS
            )
        )
        == 3
    )


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
    assert len(norms) == 20
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 18
    assert sum(norm.kind.value == "permission" for norm in norms.values()) == 1
    assert sum(norm.kind.value == "legal_consequence" for norm in norms.values()) == 1
    assert all(norm.implementation_refs == ["AIA-PO-A17"] for norm in norms.values())

    aspect_ids = {
        norm_id for norm_id in norms if any(f"-P1-{point}-" in norm_id for point in "ABCDEFGHIJKLM")
    }
    assert len(aspect_ids) == 13
    assert all(norms[norm_id].qualifier_spans == ["AIA-TEXT-A017-P001"] for norm_id in aspect_ids)

    article_sixteen = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A016-C-QUALITY-MANAGEMENT"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert bundle.norm_inventory.target_norm_ids_for(
        article_sixteen.norm_id, NormRelationKind.CARRIED_BY_NORMS
    ) == ["AIA-NORM-A017-P1-QMS"]


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
    assert all(norms[norm_id].qualifier_spans == ["AIA-TEXT-A018-P001"] for norm_id in retention)
    member_state = norms["AIA-NORM-A018-P2-MEMBER-STATE-CONDITIONS"]
    assert member_state.implementation_mode.value == "none_required"
    provider_norms = set(norms) - {member_state.norm_id}
    assert all(norms[norm_id].implementation_refs == ["AIA-PO-A18"] for norm_id in provider_norms)

    article_sixteen = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A016-D-KEEP-DOCUMENTATION"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert (
        set(
            bundle.norm_inventory.target_norm_ids_for(
                article_sixteen.norm_id, NormRelationKind.CARRIED_BY_NORMS
            )
        )
        == retention
    )


def test_article_nineteen_keeps_the_legal_exception_in_the_retention_rule():
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
    assert len(norms) == 3
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 3
    assert all(norm.implementation_refs == ["AIA-PO-A19"] for norm in norms.values())

    paragraph_one = {norm_id for norm_id in norms if "-P1-" in norm_id}
    assert len(paragraph_one) == 2
    assert all(norms[norm_id].primary_spans == ["AIA-TEXT-A019-P001"] for norm_id in paragraph_one)
    retention = norms["AIA-NORM-A019-P1-RETENTION-PERIOD"]
    assert retention.exceptions

    article_sixteen = next(
        norm for norm in bundle.norm_inventory.norms if norm.norm_id == "AIA-NORM-A016-E-KEEP-LOGS"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert (
        set(
            bundle.norm_inventory.target_norm_ids_for(
                article_sixteen.norm_id, NormRelationKind.CARRIED_BY_NORMS
            )
        )
        == paragraph_one
    )


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
    assert len(norms) == 3
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    paragraph_one = {norm_id for norm_id in norms if "-P1-" in norm_id}
    paragraph_two = set(norms) - paragraph_one
    assert len(paragraph_one) == 2
    assert len(paragraph_two) == 1
    assert all(norms[norm_id].implementation_refs == ["AIA-PO-A20"] for norm_id in paragraph_one)
    assert all(norms[norm_id].implementation_refs == ["AIA-PO-A20-2"] for norm_id in paragraph_two)
    response = norms["AIA-NORM-A020-P1-CORRECTIVE-RESPONSE"]
    assert all(
        term in response.action for term in ("conformity", "withdrawing", "disabling", "recalling")
    )

    article_sixteen = next(
        norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id == "AIA-NORM-A016-J-CORRECTIVE-ACTION"
    )
    assert article_sixteen.implementation_mode.value == "carried_by_other_norm"
    assert set(
        bundle.norm_inventory.target_norm_ids_for(
            article_sixteen.norm_id, NormRelationKind.CARRIED_BY_NORMS
        )
    ) == set(norms)


def test_article_twenty_one_keeps_disclosure_language_with_the_requested_material():
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
    assert len(norms) == 3
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    paragraph_one = {norm_id for norm_id in norms if "-P1-" in norm_id}
    assert len(paragraph_one) == 1
    assert all(norms[norm_id].implementation_refs == ["AIA-PO-A21"] for norm_id in paragraph_one)
    assert norms["AIA-NORM-A021-P2-PROVIDE-LOG-ACCESS"].implementation_refs == ["AIA-PO-A21-2"]
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
    assert len(norms) == 14
    assert all(norm.kind.value == "obligation" for norm in norms.values())

    provider_norms = {
        "AIA-NORM-A022-P1-APPOINT-REPRESENTATIVE",
        "AIA-NORM-A022-P2-ENABLE-REPRESENTATIVE",
    }
    assert all(norms[norm_id].implementation_refs == ["AIA-PO-A22"] for norm_id in provider_norms)
    representative_norms = set(norms) - provider_norms
    assert all(
        norms[norm_id].implementation_refs == ["AIA-AR-A22"] for norm_id in representative_norms
    )

    mandate_items = {
        norm_id for norm_id in norms if any(f"-P3-{letter}-" in norm_id for letter in "ABCDE")
    }
    assert len(mandate_items) == 7
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A022-P003"] for norm_id in mandate_items
    )
    assert {norm_id for norm_id in mandate_items if "-P3-C-" in norm_id} == {
        "AIA-NORM-A022-P3-C-PROVIDE-CONFORMITY-INFORMATION",
        "AIA-NORM-A022-P3-C-PROVIDE-LOG-ACCESS",
    }
    assert {norm_id for norm_id in mandate_items if "-P3-E-" in norm_id} == {
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
    assert len(norms) == 12
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert all(norm.implementation_refs == ["AIA-IM-A23"] for norm in norms.values())

    pre_market_checks = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A023-P1-")}
    assert len(pre_market_checks) == 4
    assert all(
        norms[norm_id].qualifier_spans == ["AIA-TEXT-A023-P001"] for norm_id in pre_market_checks
    )
    paragraph_two = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A023-P2-")}
    assert paragraph_two == {
        "AIA-NORM-A023-P2-WITHHOLD-NONCONFORMING-SYSTEM",
        "AIA-NORM-A023-P2-INFORM-RISK",
    }
    paragraph_six = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A023-P6-")}
    assert paragraph_six == {
        "AIA-NORM-A023-P6-PROVIDE-CONFORMITY-INFORMATION",
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

    paragraph_one = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A024-P1-")}
    assert paragraph_one == {
        "AIA-NORM-A024-P1-VERIFY-CE-MARKING",
        "AIA-NORM-A024-P1-VERIFY-ACCOMPANYING-DOCUMENTS",
        "AIA-NORM-A024-P1-VERIFY-OPERATOR-COMPLIANCE",
    }
    paragraph_two = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A024-P2-")}
    assert paragraph_two == {
        "AIA-NORM-A024-P2-WITHHOLD-NONCONFORMING-SYSTEM",
        "AIA-NORM-A024-P2-INFORM-RISK",
    }
    paragraph_four = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A024-P4-")}
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
        norm_id for norm_id, norm in norms.items() if norm.kind.value == "legal_consequence"
    }
    assert len(role_consequences) == 6
    assert all(
        norms[norm_id].product_scope.value == "dependency_only"
        and norms[norm_id].implementation_mode.value == "none_required"
        for norm_id in role_consequences
    )

    initial_provider_norms = {
        norm_id for norm_id, norm in norms.items() if norm.implementation_refs == ["AIA-IP-A25-2"]
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
        norm_id for norm_id, norm in norms.items() if norm.implementation_refs == ["AIA-PO-A25-4"]
    }
    assert agreement_norms == {
        "AIA-NORM-A025-P4-WRITTEN-AGREEMENT",
        "AIA-NORM-A025-P4-OPEN-SOURCE-EXCEPTION",
    }
    ai_office_norms = {norm_id for norm_id in norms if "-AI-OFFICE-" in norm_id}
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
    assert len(norms) == 34

    by_target = {
        target: {norm_id for norm_id, norm in norms.items() if norm.implementation_refs == [target]}
        for target in (
            "AIA-DP-A26",
            "AIA-DP-A26-8",
            "AIA-DP-A26-9",
            "AIA-DP-A26-10",
            "AIA-DP-A26-11",
            "AIA-DP-A26-12",
        )
    }
    assert len(by_target["AIA-DP-A26"]) == 13
    assert len(by_target["AIA-DP-A26-8"]) == 3
    assert len(by_target["AIA-DP-A26-9"]) == 1
    assert len(by_target["AIA-DP-A26-10"]) == 12
    assert len(by_target["AIA-DP-A26-11"]) == 2
    assert len(by_target["AIA-DP-A26-12"]) == 1

    paragraph_five = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A026-P5-")}
    assert len(paragraph_five) == 6
    paragraph_ten = {norm_id for norm_id in norms if norm_id.startswith("AIA-NORM-A026-P10-")}
    assert len(paragraph_ten) == 13
    assert {norm_id for norm_id in paragraph_ten if norms[norm_id].kind.value == "prohibition"} == {
        "AIA-NORM-A026-P10-PROHIBIT-UNTARGETED-USE",
        "AIA-NORM-A026-P10-NO-SOLE-OUTPUT-ADVERSE-DECISION",
    }
    member_state_power = norms["AIA-NORM-A026-P10-MEMBER-STATE-STRICTER-LAW"]
    assert member_state_power.kind.value == "power"
    assert member_state_power.product_scope.value == "outside_supported_actor"
    assert norms["AIA-NORM-A026-P8-DO-NOT-USE-UNREGISTERED"].kind.value == ("prohibition")


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
        target: {norm_id for norm_id, norm in norms.items() if norm.implementation_refs == [target]}
        for target in ("AIA-DP-A27", "AIA-DP-A27-2", "AIA-DP-A27-3")
    }
    assert len(by_target["AIA-DP-A27"]) == 2
    assert len(by_target["AIA-DP-A27-2"]) == 3
    assert len(by_target["AIA-DP-A27-3"]) == 2

    ai_office_norms = {
        norm_id for norm_id, norm in norms.items() if norm.subjects[0].subject_ref == "ai_office"
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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A028-")
    ]

    assert len(segments) == 13
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 16
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)


def test_inventory_cannot_be_misreported_as_independently_approved(metrics):
    """Approved text is now the whole corpus, which is the number most likely to be quoted as
    though the Act were covered. Norm approval is counted separately and trails it, so the two are
    asserted together: character coverage is a statement about reading the source, not about the
    propositions extracted from it."""
    assert metrics.approved_characters == metrics.exact_source_characters == 395_046
    assert metrics.needs_review_characters == 0
    assert metrics.review_statuses == {
        "approved": 2098,
        "proposed": 823,
    }
    assert metrics.timed_review_records == 0
    assert metrics.total_review_records == 2922


def test_semantic_pass_finds_propositions_a_shall_scan_misses(metrics):
    assert metrics.shall_vs_semantic_disagreements == 536
    assert metrics.shall_token_candidate_recall == pytest.approx(855 / 1391)
    assert "AIA-NORM-A011-P1-SIMPLIFY" in metrics.semantic_norms_without_shall_token
    # Art. 26(5)'s informing limb is retained as content of the complete monitoring norm.
    assert "AIA-NORM-A026-P5-INFORM-PROVIDER" not in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A043-P5-AMEND" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A060-P4-PERMISSION" in metrics.semantic_norms_without_shall_token
    assert "AIA-NORM-A075-P1E-WITHDRAW" in metrics.semantic_norms_without_shall_token


def test_metrics_expose_many_to_many_and_implementation_debt(metrics):
    # Primary links measure norms yielded by a segment; qualifier-only chapeaux do not count.
    assert metrics.normative_segments_with_multiple_norms == 231
    # `AIA-GP-A91-5` and `AIA-PO-A75-1a` each carry two norms since Article 91(5) was split by
    # addressee and Article 75(1a)'s procedure sentence gained its own norm.
    # Article 55(1)(a) is one model-evaluation norm rather than three overlapping records.
    assert metrics.mapping_shape.one_norm_to_one_target == 35
    assert metrics.mapping_shape.many_norms_to_one_target == 391
    assert metrics.mapping_shape.one_norm_to_many_targets == 1
    # Annex VII point 5.2's second sentence gained its own norm and point 4.7's duty to inform the
    # notified body gained the refs its siblings already carried, so `AIA-PO-A43-1B` and
    # `AIA-PO-A43-3` each pick up two more of the norms they shared.
    assert metrics.mapping_shape.many_to_many == 17
    assert metrics.mapping_shape.unmapped == 947
    assert metrics.semantic_vs_existing_implementation_disagreements == 124
    assert metrics.semantic_norms_without_existing_implementation == [
        "AIA-NORM-A002-P13-LIMIT-HIGH-RISK-REQUIREMENTS",
        "AIA-NORM-A002-P2-INTEGRATED-SANDBOX-PROVISIONS",
        "AIA-NORM-A002-P2-SECTION-B-LIMIT",
        "AIA-NORM-A004A-P1-B-REUSE-SECURITY",
        "AIA-NORM-A004A-P1-C-ACCESS-SAFEGUARDS",
        "AIA-NORM-A004A-P1-D-NO-THIRD-PARTY-ACCESS",
        "AIA-NORM-A004A-P1-E-DELETE-DATA",
        "AIA-NORM-A004A-P1-F-RECORD-NECESSITY",
        "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING",
        "AIA-NORM-A004A-P2-OTHER-SYSTEM-BIAS-DATA-PROCESSING",
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
        "AIA-NORM-A005-P4-NOTIFICATION-CONTENT",
        "AIA-NORM-A005-P4-NOTIFY-AUTHORITIES",
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
        "AIA-NORM-A042-P1-REPRESENTATIVE-DATA-PRESUMPTION",
        "AIA-NORM-A042-P2-CYBERSECURITY-CERTIFICATE-PRESUMPTION",
        "AIA-NORM-A042-P3-CYBER-RESILIENCE-DEEMING",
        "AIA-NORM-A044-P2-CERTIFICATE-VALIDITY-PERIOD",
        "AIA-NORM-A044-P2-EXTEND-CERTIFICATE",
        "AIA-NORM-A044-P2-SUPPLEMENT-VALIDITY",
        "AIA-NORM-A046-P1-COMPLETE-ASSESSMENT-PROMPTLY",
        "AIA-NORM-A046-P7-SECTORAL-DEROGATIONS-ONLY",
        "AIA-NORM-A048-P1-GENERAL-CE-PRINCIPLES",
        "AIA-NORM-A048-P5-OTHER-LAW-COMPLIANCE",
        "AIA-NORM-A049-P2-PROVIDER-REGISTER-NON-HIGH-RISK",
        "AIA-NORM-A050-P3-DATA",
        "AIA-NORM-A050-P5-MANNER",
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
        "AIA-NORM-A060-P8-NOTIFY-OUTCOMES",
        "AIA-NORM-A060A-P5-A-AGREE-TESTING-PLAN",
        "AIA-NORM-A060A-P5-B-COMPLY-WITH-INCORPORATED-SAFEGUARDS",
        "AIA-NORM-A060A-P6-COMPLY-WITH-SECTORAL-LAW",
        "AIA-NORM-A061-P1-OBTAIN-INFORMED-CONSENT",
        "AIA-NORM-A061-P2-DOCUMENT-AND-COPY-CONSENT",
        "AIA-NORM-A061-P2-GIVE-CONSENT-COPY",
        "AIA-NORM-A063-P1-SIMPLIFIED-SME-QUALITY-MANAGEMENT",
        "AIA-NORM-A075A-P3-VOLUNTARY-REPLY-CORRECTNESS",
        "AIA-NORM-A075C-P3-DESCRIBE-IMPLEMENTED-MEASURES",
        "AIA-NORM-A111-P1-BRING-LARGE-SCALE-IT-INTO-COMPLIANCE",
        "AIA-NORM-A111-P2-PUBLIC-AUTHORITY-SYSTEM-COMPLIANCE",
        "AIA-NORM-A111-P3-LEGACY-GPAI-COMPLIANCE",
        "AIA-NORM-A111-P4-LEGACY-SYNTHETIC-CONTENT-COMPLIANCE",
        "AIA-NORM-ANNEX-IV-CONTENT",
        "AIA-NORM-ANNEX-IX-REGISTRATION-INFORMATION",
        "AIA-NORM-ANNEX-V-DECLARATION-CONTENT",
        "AIA-NORM-ANNEX-VI-P1-PROCEDURE-CONTENT",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION-CONTENT",
        "AIA-NORM-ANNEX-VII-OVERVIEW-DOCUMENTATION-EXAMINATION",
        "AIA-NORM-ANNEX-VII-OVERVIEW-QMS-EXAMINATION",
        "AIA-NORM-ANNEX-VII-PROCEDURE-COMPOSITION",
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
        "AIA-NORM-ANNEX-XI-SECTION-2-ADVERSARIAL-TESTING-AND-ADAPTATIONS",
        "AIA-NORM-ANNEX-XI-SECTION-2-SYSTEM-ARCHITECTURE",
        "AIA-NORM-ANNEX-XI-SECTION-2-SYSTEMIC-RISK-DOCUMENTATION",
        "AIA-NORM-ANNEX-XII-DOWNSTREAM-TRANSPARENCY-INFORMATION",
    ]
    assert metrics.implementation_debt_norm_ids == [
        "AIA-NORM-A002-P13-LIMIT-HIGH-RISK-REQUIREMENTS",
        "AIA-NORM-A002-P2-INTEGRATED-SANDBOX-PROVISIONS",
        "AIA-NORM-A002-P2-SECTION-B-LIMIT",
        "AIA-NORM-A004A-P1-B-REUSE-SECURITY",
        "AIA-NORM-A004A-P1-C-ACCESS-SAFEGUARDS",
        "AIA-NORM-A004A-P1-D-NO-THIRD-PARTY-ACCESS",
        "AIA-NORM-A004A-P1-E-DELETE-DATA",
        "AIA-NORM-A004A-P1-F-RECORD-NECESSITY",
        "AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING",
        "AIA-NORM-A004A-P2-OTHER-SYSTEM-BIAS-DATA-PROCESSING",
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
        "AIA-NORM-A005-P4-NOTIFICATION-CONTENT",
        "AIA-NORM-A005-P4-NOTIFY-AUTHORITIES",
        "AIA-NORM-A006-P4-PROVIDE-ASSESSMENT",
        "AIA-NORM-A006-P4-REGISTER-SYSTEM",
        "AIA-NORM-A011-P1-SIMPLIFY",
        "AIA-NORM-A025-P5-PROTECT-RIGHTS-AND-SECRETS",
        "AIA-NORM-A036-P8-B-PROVIDER-REPLACEMENT-CONFIRMATION",
        "AIA-NORM-A040-P1-HARMONISED-STANDARD-PRESUMPTION",
        "AIA-NORM-A041-P3-COMMON-SPECIFICATION-PRESUMPTION",
        "AIA-NORM-A042-P1-REPRESENTATIVE-DATA-PRESUMPTION",
        "AIA-NORM-A042-P2-CYBERSECURITY-CERTIFICATE-PRESUMPTION",
        "AIA-NORM-A042-P3-CYBER-RESILIENCE-DEEMING",
        "AIA-NORM-A044-P2-CERTIFICATE-VALIDITY-PERIOD",
        "AIA-NORM-A044-P2-EXTEND-CERTIFICATE",
        "AIA-NORM-A044-P2-SUPPLEMENT-VALIDITY",
        "AIA-NORM-A046-P1-COMPLETE-ASSESSMENT-PROMPTLY",
        "AIA-NORM-A046-P7-SECTORAL-DEROGATIONS-ONLY",
        "AIA-NORM-A048-P5-OTHER-LAW-COMPLIANCE",
        "AIA-NORM-A049-P2-PROVIDER-REGISTER-NON-HIGH-RISK",
        "AIA-NORM-A050-P3-DATA",
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
        "AIA-NORM-A060-P8-NOTIFY-OUTCOMES",
        "AIA-NORM-A060A-P5-A-AGREE-TESTING-PLAN",
        "AIA-NORM-A060A-P5-B-COMPLY-WITH-INCORPORATED-SAFEGUARDS",
        "AIA-NORM-A060A-P6-COMPLY-WITH-SECTORAL-LAW",
        "AIA-NORM-A061-P1-OBTAIN-INFORMED-CONSENT",
        "AIA-NORM-A061-P2-DOCUMENT-AND-COPY-CONSENT",
        "AIA-NORM-A061-P2-GIVE-CONSENT-COPY",
        "AIA-NORM-A063-P1-SIMPLIFIED-SME-QUALITY-MANAGEMENT",
        "AIA-NORM-A075A-P3-VOLUNTARY-REPLY-CORRECTNESS",
        "AIA-NORM-A075C-P3-DESCRIBE-IMPLEMENTED-MEASURES",
        "AIA-NORM-A111-P1-BRING-LARGE-SCALE-IT-INTO-COMPLIANCE",
        "AIA-NORM-A111-P2-PUBLIC-AUTHORITY-SYSTEM-COMPLIANCE",
        "AIA-NORM-A111-P3-LEGACY-GPAI-COMPLIANCE",
        "AIA-NORM-A111-P4-LEGACY-SYNTHETIC-CONTENT-COMPLIANCE",
        "AIA-NORM-ANNEX-VI-P1-PROCEDURE-CONTENT",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION",
        "AIA-NORM-ANNEX-VII-DOC-APPLICATION-CONTENT",
        "AIA-NORM-ANNEX-VII-OVERVIEW-DOCUMENTATION-EXAMINATION",
        "AIA-NORM-ANNEX-VII-OVERVIEW-QMS-EXAMINATION",
        "AIA-NORM-ANNEX-VII-PROCEDURE-COMPOSITION",
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
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 4
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert len(segments[2].norm_ids) == 2
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 3
    assert len(segments[2].norm_ids) == 2
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert all(
        norm.subjects[0].category.value == "union_institution_or_body" for norm in norms.values()
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 25
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 18
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 6
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 5
    assert sum(norm.kind.value == "power" for norm in norms.values()) == 1
    assert len(segments[4].norm_ids) == 3
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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A038-")
    ]

    assert len(segments) == 4
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 10
    assert sum(norm.kind.value == "obligation" for norm in norms.values()) == 8
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
    assert justification.implementation_mode.value == "compliance_rule"
    assert justification.implementation_refs == ["AIA-PO-A41-5"]


def test_article_forty_two_keeps_three_conformity_presumptions_distinct():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "42"
    ]
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A042-")
    ]

    assert len(segments) == 4
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 18
    assert len(segments[1].norm_ids) == 4
    assert len(segments[3].norm_ids) == 8
    assert len(segments[4].norm_ids) == 2
    assert len(segments[6].norm_ids) == 2
    assert norms["AIA-NORM-A043-P1-CHOOSE-CONFORMITY-ROUTE"].implementation_refs == ["AIA-PO-A43-1"]
    assert norms["AIA-NORM-A043-P2-INTERNAL-CONTROL"].implementation_refs == ["AIA-PO-A43-2"]
    assert norms["AIA-NORM-A043-P4-NEW-ASSESSMENT"].implementation_refs == ["AIA-PO-A43-4"]
    qms = norms["AIA-NORM-A043-P3-QMS"]
    assert qms.dependencies == []
    assert len(
        bundle.norm_inventory.target_norm_ids_for(qms.norm_id, NormRelationKind.RELIES_ON_NORMS)
    ) == 28
    exclusion = norms["AIA-NORM-A043-P4-PREDETERMINED-CHANGE-EXCLUSION"]
    assert exclusion.kind.value == "applicability"
    assert exclusion.product_scope.value == "dependency_only"


def test_article_forty_four_keeps_corrective_action_as_the_measure_exception():
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 7
    assert len(segments[2].norm_ids) == 3
    assert len(segments[3].norm_ids) == 2
    missing = [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert len(missing) == 3
    assert all(norm.product_scope.value == "in_scope" for norm in missing)
    extension = norms["AIA-NORM-A044-P2-EXTEND-CERTIFICATE"]
    assert extension.kind.value == "entitlement"
    assert len(extension.conditions) == 2
    measure = norms["AIA-NORM-A044-P3-CERTIFICATE-MEASURE"]
    assert "corrective action" in measure.exceptions[0]


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 7
    assert all(norm.kind.value == "obligation" for norm in norms.values())
    assert_extraction_never_approves(norms.values())
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 14
    authorisation = norms["AIA-NORM-A046-P1-DEROGATION-AUTHORISATION"]
    assert authorisation.kind.value == "power"
    assert authorisation.qualifier_spans == ["AIA-TEXT-A046-P003"]
    assert len(authorisation.conditions) == 3
    refusal = norms["AIA-NORM-A046-P2-REFUSAL-RESPONSE"]
    discard = norms["AIA-NORM-A046-P2-DISCARD-RESULTS-AND-OUTPUTS"]
    assert (
        refusal.conditions
        == discard.conditions
        == ["the paragraph 1 authorisation requested for urgent use under paragraph 2 is refused"]
    )
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 10
    assert len(segments[1].norm_ids) == 3
    assert len(segments[2].norm_ids) == 2
    assert len(segments[3].norm_ids) == 2
    assert len(segments[4].norm_ids) == 2
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 9
    assert all(norm.implementation_mode.value == "compliance_rule" for norm in mapped)
    annex_content = norms["AIA-NORM-A047-P2-ANNEX-V-CONTENT"]
    assert bundle.norm_inventory.target_norm_ids_for(
        annex_content.norm_id, NormRelationKind.RELIES_ON_NORMS
    ) == ["AIA-NORM-ANNEX-V-DECLARATION-CONTENT"]


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 7
    assert len(segments[4].norm_ids) == 3
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 5
    assert all(norm.implementation_mode.value == "compliance_rule" for norm in mapped)
    missing = [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert {norm.norm_id for norm in missing} == {"AIA-NORM-A048-P5-OTHER-LAW-COMPLIANCE"}
    principles = norms["AIA-NORM-A048-P1-GENERAL-CE-PRINCIPLES"]
    assert bundle.norm_inventory.target_norm_ids_for(
        principles.norm_id, NormRelationKind.CARRIED_BY_NORMS
    ) == ["AIA-NORM-A048-P3-AFFIX-CE-MARKING"]
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 9
    assert [len(segments[index].norm_ids) for index in (1, 2, 4, 9)] == [2, 2, 1, 2]
    assert all(segments[index].disposition.value == "normative" for index in range(5, 9))
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 6
    assert all(norm.implementation_mode.value == "compliance_rule" for norm in mapped)
    # The Art. 6(4) rule evidences the documented assessment, not this database entry.
    provider_entry = norms["AIA-NORM-A049-P2-PROVIDER-REGISTER-NON-HIGH-RISK"]
    assert provider_entry.implementation_mode.value == "missing"
    assert provider_entry.verification_mode.value == "reported_not_judged"
    restricted = norms["AIA-NORM-A049-P4-SECURE-NON-PUBLIC-SECTION"]
    assert len(restricted.mandatory_content) == 5
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
        assert norm.review.status.value == "approved"
        assert norm.review.verified_by == "vidibro"
        assert norm.verification_mode.value == "judged_by_gap_analysis"
    article_segments = [
        s
        for s in bundle.text_review.segments
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 4
    assert segments[1].norm_ids == []
    assert len(segments[1].qualifying_norm_ids) == 2
    assert len(segments[5].norm_ids) == 1
    classification = [norm for norm in norms.values() if norm.kind.value == "applicability"]
    assert len(classification) == 3
    assert all(
        norm.implementation_mode.value == "applicability_question" for norm in classification
    )
    delegated_acts = [
        norm for norm in norms.values() if norm.subjects[0].subject_ref == "commission"
    ]
    assert len(delegated_acts) == 1
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 13
    assert [len(segments[index].norm_ids) for index in (1, 3, 6, 7)] == [3, 2, 4, 1]
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
    published_list = norms["AIA-NORM-A052-P6-PUBLISH-LIST"]
    assert "keep the published list up to date" in published_list.mandatory_content
    assert any("trade secrets" in item for item in published_list.mandatory_content)


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 17
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 15
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 12
    assert all(norm.implementation_refs for norm in norms.values())
    assert not [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    exception = norms["AIA-NORM-A054-P6-OPEN-SOURCE-EXCEPTION"]
    assert len(exception.implementation_refs) == 5
    assert exception.exceptions == ["the general-purpose AI model presents systemic risk"]
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 8
    mapped = [norm for norm in norms.values() if norm.implementation_refs]
    assert len(mapped) == 7
    assert not [norm for norm in norms.values() if norm.implementation_mode.value == "missing"]
    assert {ref for norm in mapped for ref in norm.implementation_refs} == {
        "AIA-GP-A55-1A",
        "AIA-GP-A55-1B",
        "AIA-GP-A55-1C",
        "AIA-GP-A55-1D",
        "AIA-GP-A55-2",
    }
    incident_report = norms["AIA-NORM-A055-P1-C-TRACK-DOCUMENT-AND-REPORT-INCIDENTS"]
    assert len(incident_report.mandatory_content) == 2
    evaluation = norms["AIA-NORM-A055-P1-A-EVALUATE-MODEL"]
    assert evaluation.norm_text.startswith("perform model evaluation")
    assert "conducting and documenting adversarial testing" in evaluation.norm_text
    assert len(evaluation.mandatory_content) == 2
    assert "AIA-NORM-A055-P1-A-CONDUCT-ADVERSARIAL-TESTING" not in norms
    assert "AIA-NORM-A055-P1-A-DOCUMENT-ADVERSARIAL-TESTING" not in norms
    assert (
        "assess and mitigate"
        in norms["AIA-NORM-A055-P1-B-ASSESS-AND-MITIGATE-SYSTEMIC-RISKS"].action
    )
    assert (
        "physical infrastructure"
        in norms["AIA-NORM-A055-P1-D-MODEL-AND-INFRASTRUCTURE-CYBERSECURITY"].action
    )
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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A056-")
    ]

    assert len(segments) == 15
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 20
    assert all(norm.implementation_mode.value == "none_required" for norm in norms)
    assert not [norm for norm in norms if norm.implementation_refs]
    code_coverage = next(norm for norm in norms if norm.norm_id.endswith("P2-CODE-COVERAGE"))
    assert len(code_coverage.mandatory_content) == 4
    assert len(code_coverage.qualifier_spans) == 4
    assert len([norm for norm in norms if norm.kind.value == "power"]) == 3
    objectives = next(norm for norm in norms if norm.norm_id.endswith("OBJECTIVES-AND-COMMITMENTS"))
    assert any("interested parties" in item for item in objectives.mandatory_content)


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
    assert_segments_are_independently_approved(segments)
    assert segments[6].disposition.value == "normative"
    assert segments[6].norm_ids == []
    assert segments[6].qualifying_norm_ids == ["AIA-NORM-A057-P3A-AI-OFFICE-SANDBOX"]
    assert len(norms) == 49
    assert all(norm.implementation_mode.value == "none_required" for norm in norms.values())
    objectives = norms["AIA-NORM-A057-P9-SANDBOX-OBJECTIVES"]
    assert len(objectives.mandatory_content) == 5
    assert len(objectives.qualifier_spans) == 5
    provider_consequences = [
        norm for norm in norms.values() if norm.subjects[0].category.value == "supported_operator"
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
    assert_segments_are_independently_approved(segments)
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
        "testing terms and conditions",
        "safeguards protecting fundamental rights health and safety",
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
    assert_extraction_never_approves(norms.values())
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
    assert_segments_are_independently_approved(segments)
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
        assert segment.qualifying_norm_ids == [public_interest.norm_id]
    assert permission.conditions == [
        "the personal data were lawfully collected for other purposes",
        "processing occurs in an AI regulatory sandbox",
        "every Article 59(1) condition is met",
    ]
    condition_norm_ids = bundle.norm_inventory.target_norm_ids_for(
        permission.norm_id, NormRelationKind.CONDITIONAL_ON_NORMS
    )
    assert condition_norm_ids == [
        norm_id
        for norm_id in norms
        if norm_id.startswith("AIA-NORM-A059-P1-") and norm_id != permission.norm_id
    ]
    assert all(
        bundle.norm_inventory.source_norm_ids_for(norm_id, NormRelationKind.CONDITIONAL_ON_NORMS)
        == [permission.norm_id]
        for norm_id in condition_norm_ids
    )
    # The parent permission still requires all ten lettered conditions, not any one of them.
    # Each has a child norm; expanding (a) does not duplicate the other conditions at the parent.
    for span_id in permission.qualifier_spans:
        segment = next(segment for segment in segments if segment.segment_id == span_id)
        assert permission.norm_id in segment.qualifying_norm_ids
        children = segment.norm_ids
        assert len(children) == 1
        assert norms[children[0]].primary_spans == [span_id]
    assert "every Article 59(1) condition" in (
        norms["AIA-NORM-A059-P2-LAW-ENFORCEMENT-LEGAL-BASIS"].action
    )
    assert_extraction_never_approves(norms.values())
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 30
    permission = norms["AIA-NORM-A060-P4-PERMISSION"]
    condition_norm_ids = bundle.norm_inventory.target_norm_ids_for(
        permission.norm_id, NormRelationKind.CONDITIONAL_ON_NORMS
    )
    assert condition_norm_ids == [
        norm_id
        for norm_id in norms
        if norm_id.startswith("AIA-NORM-A060-P4-") and norm_id != permission.norm_id
    ]
    assert all(
        bundle.norm_inventory.source_norm_ids_for(norm_id, NormRelationKind.CONDITIONAL_ON_NORMS)
        == [permission.norm_id]
        for norm_id in condition_norm_ids
    )
    assert len(permission.qualifier_spans) == 11
    assert len(permission.mandatory_content) == 11
    assert sum(norm.implementation_mode.value == "missing" for norm in norms.values()) == 18
    assert_extraction_never_approves(norms.values())


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

    # Withdrawal and the deletion request are the two contents of one enacted entitlement.
    withdraw = norms["AIA-NORM-A060-P5-WITHDRAW-AND-DELETE"]
    assert withdraw.kind.value == "entitlement"
    assert "without having to provide any justification" in withdraw.action
    assert "immediate and permanent deletion" in withdraw.action
    assert len(withdraw.mandatory_content) == 2

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
    recall = norms["AIA-NORM-A060-P7-RECALL-PROCEDURE"]
    assert not report.mandatory_content
    assert report.conditions == mitigate.conditions == [incident]
    # Mitigation, and the fallback suspension or termination, form one alternative response.
    assert len(mitigate.mandatory_content) == 2
    assert "or terminate it" in mitigate.action
    # The recall procedure duty is not itself conditional; the recall happens upon termination.
    assert not recall.conditions
    assert "upon such termination" in recall.action
    assert all(
        norm.subjects[0].subject_ref == "provider_or_prospective_provider"
        for norm in (report, mitigate, recall)
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 10
    framework = norms["AIA-NORM-A060A-P5-FRAMEWORK-REQUIREMENTS"]
    assert len(framework.qualifier_spans) == 4
    assert len(framework.mandatory_content) == 4
    assert sum(norm.implementation_mode.value == "missing" for norm in norms.values()) == 3

    # Cooperation and necessary obstacle removal are the two contents of one requirement.
    cooperate = norms["AIA-NORM-A060A-P4-COOPERATE-AND-REMOVE-OBSTACLES"]
    adopted = "the Member State has adopted a real-world testing framework"
    assert cooperate.conditions == [adopted]
    assert len(cooperate.mandatory_content) == 2
    assert any("physical public infrastructure" in item for item in cooperate.mandatory_content)

    # Sectoral compliance is an operator duty; the second sentence limits those requirements.
    comply = norms["AIA-NORM-A060A-P6-COMPLY-WITH-SECTORAL-LAW"]
    limit = norms["AIA-NORM-A060A-P6-SECTORAL-REQUIREMENTS-DO-NOT-OBSTRUCT"]
    assert comply.kind.value == "obligation"
    assert comply.implementation_mode.value == "missing"
    assert limit.kind.value == "legal_consequence"
    assert limit.product_scope.value == "no_product_action"
    assert "to the extent necessary to enable the paragraph 1 testing" in limit.action
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
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
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
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
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 3
    assert norms["AIA-NORM-A063-P1-SIMPLIFIED-SME-QUALITY-MANAGEMENT"].kind.value == ("permission")
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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A064-")
    ]

    assert len(segments) == 4
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
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
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
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
    assert len(opinions.qualifier_spans) == 8
    assert opinions.qualifier_spans[0] == "AIA-TEXT-A066-P001"
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
    assert_extraction_never_approves(norms.values())
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
    assert_segments_are_independently_approved(segments)
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
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 18
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

    # Integrity and confidentiality share one grammatical subject; the prohibition remains separate.
    integrity = norms["AIA-NORM-A068-P4-EXPERT-INTEGRITY-AND-DISCLOSURE"]
    assert len(integrity.mandatory_content) == 2
    assert norms["AIA-NORM-A068-P4-NO-INSTRUCTIONS"].kind.value == "prohibition"
    assert "publicly available" in norms["AIA-NORM-A068-P4-DECLARATION-OF-INTERESTS"].action
    # The AI Office conflict-management duty stays a separate norm rather than being duplicated.
    assert norms["AIA-NORM-A068-P4-MANAGE-CONFLICTS"].subjects[0].subject_ref == "ai_office"
    assert_extraction_never_approves(norms.values())


def test_article_sixty_nine_extracts_member_state_expert_access():
    bundle = load_normative_coverage()
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "article" and segment.source.document == "69"
    ]
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A069-")
    ]

    assert len(segments) == 4
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
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
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 13
    entry = [norm for norm in norms.values() if "ENTER-ANNEX-VIII-DATA" in norm.norm_id]
    assert len(entry) == 3
    assert all(norm.implementation_mode.value == "compliance_rule" for norm in entry)
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
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 6
    provider_norms = [
        norm for norm in norms.values() if norm.subjects[0].category.value == "supported_operator"
    ]
    assert len(provider_norms) == 5
    assert all(norm.implementation_refs == ["AIA-PO-A72"] for norm in provider_norms)
    assert len(norms["AIA-NORM-A072-P2-OPERATE-LIFETIME-MONITORING"].mandatory_content) == 3

    # Having a plan and placing it in the Annex IV documentation are separately verifiable.
    plan = norms["AIA-NORM-A072-P3-PLAN-AND-TECHNICAL-DOCUMENTATION"]
    documented = norms["AIA-NORM-A072-P3-PLAN-IN-TECHNICAL-DOCUMENTATION"]
    assert "Annex IV" not in plan.action
    assert "Annex IV" in documented.action


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 15
    default_mapped = [
        norm for norm in norms.values() if norm.implementation_refs == ["AIA-ALL-A73"]
    ]
    assert len(default_mapped) == 10
    assert norms["AIA-NORM-A073-P10-MEDICAL-DEVICE-REPORTING"].implementation_refs == [
        "AIA-ALL-A73-10"
    ]

    # The two sentences have separately verifiable outcomes.
    investigate = norms["AIA-NORM-A073-P6-INVESTIGATE"]
    correct = norms["AIA-NORM-A073-P6-RISK-ASSESSMENT-AND-CORRECTIVE-ACTION"]
    reported = "a serious incident has been reported pursuant to paragraph 1"
    assert investigate.mandatory_content == [
        "necessary investigation of the serious incident and the AI system concerned",
    ]
    assert investigate.conditions == correct.conditions == [reported]
    assert correct.mandatory_content == ["risk assessment of the incident", "corrective action"]
    assert "corrective action" not in investigate.action
    assert "corrective action" not in investigate.norm_text
    assert "corrective action" in correct.action
    assert correct.norm_text == (
        "This shall include a risk assessment of the incident, and corrective action."
    )

    # Cooperation is a duty; altering the system before informing the authorities is prohibited.
    cooperate = norms["AIA-NORM-A073-P6-COOPERATE-AND-PRESERVE-SYSTEM"]
    preserve = norms["AIA-NORM-A073-P6-NO-EVIDENCE-AFFECTING-ALTERATION"]
    assert cooperate.kind.value == "obligation"
    assert "notified body" in cooperate.action
    assert preserve.kind.value == "prohibition"
    assert "prior to informing" not in preserve.action
    assert "before informing the competent authorities" in preserve.action

    # The seven-day measures and their notification procedure form one coordinated duty.
    measures = norms["AIA-NORM-A073-P8-SEVEN-DAY-AUTHORITY-ACTION"]
    assert "seven days" in measures.action
    assert "notification procedures" in measures.action
    assert len(measures.mandatory_content) == 2
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 18
    assert norms["AIA-NORM-A074-P7-REPORT-PRUDENTIALLY-RELEVANT-INFORMATION"].kind.value == (
        "recommendation"
    )
    documentation_access = norms["AIA-NORM-A074-P12-GRANT-DOCUMENTATION-AND-DATA-ACCESS"]
    source_code_access = norms["AIA-NORM-A074-P13-GRANT-SOURCE-CODE-ACCESS"]
    assert documentation_access.implementation_refs == ["AIA-PO-A74-12"]
    assert source_code_access.implementation_refs == ["AIA-PO-A74-13"]

    # The two annual reports have different recipients and contents.
    competition = norms["AIA-NORM-A074-P2-ANNUAL-SURVEILLANCE-REPORTING"]
    practices = norms["AIA-NORM-A074-P2-ANNUAL-PROHIBITED-PRACTICE-REPORTING"]
    assert "national competition authorities" in competition.action
    assert "national competition authorities" not in practices.action
    assert practices.mandatory_content == [
        "use of prohibited practices that occurred during that year",
        "measures taken",
    ]

    # Designation binds the Member State; the judicial-independence limit binds surveillance.
    designate = norms["AIA-NORM-A074-P8-SENSITIVE-SECTOR-AUTHORITIES"]
    judicial = norms["AIA-NORM-A074-P8-PRESERVE-JUDICIAL-INDEPENDENCE"]
    assert designate.subjects[0].subject_ref == "member_state"
    assert judicial.subjects[0].subject_ref == "market_surveillance_authority"
    assert judicial.kind.value == "prohibition"

    # Proposing joint activities is a power; the AI Office owes coordination support.
    joint = norms["AIA-NORM-A074-P11-JOINT-ACTIVITIES"]
    support = norms["AIA-NORM-A074-P11-AI-OFFICE-COORDINATION-SUPPORT"]
    assert joint.kind.value == "power"
    assert joint.subjects[0].subject_ref == "market_surveillance_authority_and_commission"
    assert support.kind.value == "obligation"
    assert support.subjects[0].subject_ref == "ai_office"
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 27
    assert norms["AIA-NORM-A075-P1A-REPORT-SERIOUS-INCIDENTS"].implementation_refs == [
        "AIA-PO-A75-1a"
    ]
    assert norms["AIA-NORM-A075-P1E-FEES"].implementation_refs == ["AIA-PO-A75-1E"]

    # The four exclusions belong to point (a) only, not to the platform branch in point (b).
    competence = norms["AIA-NORM-A075-P1-COMPETENCE"]
    assert len(competence.mandatory_content) == 2
    assert all(item.startswith("point (a) only, ") for item in competence.exceptions)
    assert len(competence.exceptions) == 4
    assert "very large online platform" in competence.mandatory_content[1]
    assert "very large online platform" not in " ".join(competence.exceptions)

    # Cooperation and the resulting notifications are one coordinated duty.
    cooperate = norms["AIA-NORM-A075-P2-COOPERATE-ON-GPAI-SYSTEMS"]
    assert "AI Office" in cooperate.action
    assert "Board" in cooperate.action
    assert len(cooperate.mandatory_content) == 2

    # The request power keeps its three content items and the duly-reasoned requirement.
    request = norms["AIA-NORM-A075-P2A-REQUEST-ASSESSMENT"]
    assert request.kind.value == "power"
    assert len(request.mandatory_content) == 3
    assert "duly reasoned" in request.action

    # The four-month deadline applies to the initial reply, not to the later updates.
    reply = norms["AIA-NORM-A075-P2A-RESPOND-AND-UPDATE"]
    updates = norms["AIA-NORM-A075-P2A-UPDATE-ON-PROCEEDINGS"]
    assert "four months" in reply.action
    assert "four months" not in updates.action
    assert updates.conditions == [
        "the AI Office decides to exercise its powers in accordance with Article 75a"
    ]
    assert not reply.conditions
    assert "without disclosing any confidential information" in updates.action
    assert_extraction_never_approves(norms.values())


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
    assert_segments_are_independently_approved(segments)
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
    assert_segments_are_independently_approved(segments)
    assert len(norms) == 8
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms.values())

    # The 2 November 2024 deadline covers identification and publication only.
    identify = norms["AIA-NORM-A077-P2-IDENTIFY-PUBLISH-NOTIFY-AND-UPDATE"]
    notify = norms["AIA-NORM-A077-P2-NOTIFY-LIST"]
    assert identify.mandatory_content == [
        "identification of the public authorities or bodies referred to in paragraph 1",
        "a publicly available list of them",
    ]
    assert "2 November 2024" in identify.action
    assert "2 November 2024" not in notify.action
    assert "other Member States" in notify.action
    assert "up to date" in notify.action
    assert len(notify.mandatory_content) == 2
    assert_extraction_never_approves(norms.values())


def test_article_seventy_eight_maps_the_special_provider_confidentiality_rule():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A078-")
    }

    assert len(norms) == 10
    provider = norms["AIA-NORM-A078-P3-KEEP-DOCUMENTATION-AND-ENABLE-ACCESS"]
    access = norms["AIA-NORM-A078-P3-ENABLE-IMMEDIATE-ACCESS"]
    clearance = norms["AIA-NORM-A078-P3-SECURITY-CLEARED-ACCESS-ONLY"]
    assert provider.implementation_refs == access.implementation_refs == ["AIA-PO-A78-3"]
    assert not provider.mandatory_content
    # Only the access duty is request-triggered, and the clearance limit binds the authority.
    assert len(provider.conditions) == 1
    assert access.conditions[-1] == "the market surveillance authority requests access or a copy"
    assert clearance.subjects[0].subject_ref == "market_surveillance_authority"
    assert clearance.kind.value == "prohibition"

    # The Article 5 trade-secret exception is scoped to point (a) and recorded as a dependency.
    confidentiality = norms["AIA-NORM-A078-P1-PROTECT-CONFIDENTIALITY"]
    assert len(confidentiality.mandatory_content) == 5
    assert confidentiality.exceptions == [
        "point (a) only, the cases referred to in Article 5 of Directive (EU) 2016/943"
    ]
    assert [dependency.dependency_ref for dependency in confidentiality.dependencies] == [
        "Article 5 of Directive (EU) 2016/943"
    ]

    # Consultation before disclosure does not override the separate sensitive-data exclusion.
    disclosure = norms["AIA-NORM-A078-P3-RESTRICT-CONFIDENTIAL-DISCLOSURE"]
    sensitive = norms["AIA-NORM-A078-P3-EXCLUDE-SENSITIVE-OPERATIONAL-DATA"]
    assert len(disclosure.conditions) == 2
    assert sensitive.kind.value == "prohibition"
    assert not sensitive.conditions
    assert_extraction_never_approves(norms.values())


def test_article_seventy_nine_maps_operator_enforcement_duties():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A079-")
    }

    assert len(norms) == 17
    mapped = [norm for norm in norms.values() if norm.implementation_refs == ["AIA-ALL-A79"]]
    assert len(mapped) == 2

    # Taking provisional measures and notifying them are separate actions.
    measures = norms["AIA-NORM-A079-P5-TAKE-AND-NOTIFY-PROVISIONAL-MEASURES"]
    notify = norms["AIA-NORM-A079-P5-NOTIFY-PROVISIONAL-MEASURES"]
    assert measures.conditions == [
        "the operator does not take adequate corrective action within the period referred to in "
        "paragraph 2"
    ]
    assert "without undue delay" in notify.action
    assert "without undue delay" not in measures.action

    # The notification enumerates the detailed grounds instead of one combined label.
    content = norms["AIA-NORM-A079-P6-NOTIFICATION-CONTENT"].mandatory_content
    assert len(content) == 9
    assert content[5].endswith("referred to in Article 5")
    assert "Chapter III, Section 2" in content[6]
    assert "Articles 40 and 41" in content[7]
    assert content[8].endswith("non-compliance with Article 50")

    # Deemed justification, the preserved procedural rights and the shorter clock are distinct.
    deemed = norms["AIA-NORM-A079-P8-DEEM-MEASURE-JUSTIFIED"]
    rights = norms["AIA-NORM-A079-P8-PRESERVE-OPERATOR-PROCEDURAL-RIGHTS"]
    shortened = norms["AIA-NORM-A079-P8-SHORTENED-ARTICLE-5-PERIOD"]
    assert "three months" in deemed.action and "30 days" in deemed.action
    assert "Article 18 of Regulation (EU)" in rights.action
    assert "30 days" in shortened.action
    assert all(norm.kind.value == "legal_consequence" for norm in (deemed, rights, shortened))
    assert_extraction_never_approves(norms.values())


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
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A081-")
    ]

    assert len(norms) == 7
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in norms)
    assert {norm.subjects[0].category.value for norm in norms} == {
        "member_state",
        "union_institution_or_body",
    }

    # Notifying the concerned authority and informing all others have different recipients.
    by_id = {norm.norm_id: norm for norm in norms}
    concerned = by_id["AIA-NORM-A081-P1-NOTIFY-DECISION"]
    others = by_id["AIA-NORM-A081-P1-INFORM-OTHER-AUTHORITIES"]
    assert "Member State concerned" in concerned.action
    assert "all other market surveillance authorities" in others.action


def test_article_eighty_two_maps_compliant_system_risk_correction():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A082-")
    }

    assert len(norms) == 7
    assert norms["AIA-NORM-A082-P2-CORRECT-ALL-UNION-SYSTEMS"].implementation_refs == [
        "AIA-ALL-A82"
    ]
    assert len(norms["AIA-NORM-A082-P3-INFORM-ABOUT-RISK-FINDING"].mandatory_content) == 4

    # The immediate deadline covers the concerned States and operators, not the wider notice.
    decision = norms["AIA-NORM-A082-P5-COMMUNICATE-DECISION"]
    others = norms["AIA-NORM-A082-P5-INFORM-OTHER-MEMBER-STATES"]
    assert "immediately" in decision.action
    assert "immediately" not in others.action
    assert "relevant operators" in decision.action
    assert "other Member States" in others.action
    assert_extraction_never_approves(norms.values())


def test_article_eighty_three_keeps_formal_defects_as_one_enforcement_cycle():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A083-")
    }

    assert len(norms) == 2
    formal = norms["AIA-NORM-A083-P1-REQUIRE-END-TO-FORMAL-NONCOMPLIANCE"]
    assert not formal.mandatory_content
    assert len(formal.qualifier_spans) == 7
    triggers = formal.conditions[0]
    assert isinstance(triggers, ConditionGroup) and triggers.operator == "any_of"
    assert len(triggers.operands) == 7


def test_article_eighty_four_extracts_testing_support_structure_duties():
    bundle = load_normative_coverage()
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A084-")
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

    # Considering and procedurally handling complaints are one coordinated duty.
    consider = norms["AIA-NORM-A085-P2-ACCOUNT-FOR-AND-HANDLE-COMPLAINTS"]
    assert consider.subjects[0].category.value == "public_authority"
    assert "market surveillance activities" in consider.action
    assert "dedicated procedures" in consider.action
    assert len(consider.mandatory_content) == 2
    assert_extraction_never_approves(norms.values())


def test_article_eighty_six_maps_the_deployer_explanation_duty():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A086-")
    }

    assert len(norms) == 4
    assert norms["AIA-NORM-A086-P1-PROVIDE-EXPLANATION"].implementation_refs == ["AIA-DP-A86"]
    assert norms["AIA-NORM-A086-P1-RIGHT-TO-EXPLANATION"].kind.value == "entitlement"


def test_article_eighty_seven_applies_whistleblower_protection():
    bundle = load_normative_coverage()
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A087-")
    ]

    assert len(norms) == 1
    assert norms[0].kind.value == "applicability"
    assert norms[0].product_scope.value == "no_product_action"


def test_article_eighty_eight_extracts_gpai_enforcement_competence():
    bundle = load_normative_coverage()
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A088-")
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
    alert = norms["AIA-NORM-A090-P1-ISSUE-QUALIFIED-ALERT"]
    assert not alert.mandatory_content
    triggers = alert.conditions[0]
    assert isinstance(triggers, ConditionGroup) and triggers.operator == "any_of"
    assert len(triggers.operands) == 2
    assert len(norms["AIA-NORM-A090-P3-QUALIFIED-ALERT-CONTENT"].mandatory_content) == 3


def test_article_ninety_one_maps_gpai_information_supply():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A091-")
    }

    assert len(norms) == 8
    assert norms["AIA-NORM-A091-P5-SUPPLY-REQUESTED-INFORMATION"].implementation_refs == [
        "AIA-GP-A91-5"
    ]
    # Paragraph 5's last two sentences bind different actors: the lawyer may supply, the client
    # stays liable. Only the second reaches a supported operator, so they are separate norms.
    assert norms["AIA-NORM-A091-P5-LAWYER-SUPPLY"].product_scope.value == "outside_supported_actor"
    client = norms["AIA-NORM-A091-P5-CLIENT-REMAINS-RESPONSIBLE"]
    assert client.product_scope.value == "in_scope"
    assert client.subjects[0].category.value == "supported_operator"
    assert len(norms["AIA-NORM-A091-P4-INFORMATION-REQUEST-CONTENT"].mandatory_content) == 4


def test_article_ninety_two_maps_gpai_model_access():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A092-")
    }

    assert len(norms) == 8
    # Paragraph 5 binds the provider to "supply the information requested" while the rest of the
    # Article speaks of access; the norm tracks the enacted words rather than the Article's subject.
    supply = norms["AIA-NORM-A092-P5-SUPPLY-REQUESTED-INFORMATION"]
    assert supply.implementation_refs == ["AIA-GP-A92-5"]
    assert "supply the information requested" in supply.norm_text
    # The two evaluation purposes are alternatives, each keeping its own enacted limits.
    evaluation = norms["AIA-NORM-A092-P1-CONDUCT-GPAI-EVALUATION"]
    assert not evaluation.mandatory_content
    assert evaluation.conditions[0] == "the AI Office has consulted the Board"
    purposes = evaluation.conditions[1]
    assert isinstance(purposes, ConditionGroup) and purposes.operator == "any_of"
    assert "Article 91 is insufficient" in purposes.operands[0]
    assert "general-purpose AI models with systemic risk" in purposes.operands[1]
    assert "Article 90(1), point (a)" in purposes.operands[1]


def test_article_ninety_three_extracts_commission_measure_powers():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A093-")
    }

    assert len(norms) == 3
    request = norms["AIA-NORM-A093-P1-REQUEST-GPAI-MEASURES"]
    assert not request.mandatory_content
    alternatives = request.conditions[1]
    assert isinstance(alternatives, ConditionGroup) and alternatives.operator == "any_of"
    assert len(alternatives.operands) == 3
    assert norms["AIA-NORM-A093-P3-MAKE-COMMITMENTS-BINDING"].kind.value == "power"


def test_article_ninety_four_applies_gpai_procedural_rights():
    bundle = load_normative_coverage()
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A094-")
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
    # The five topics are non-exhaustive examples, not mandatory code content or operator duties.
    facilitated = norms["AIA-NORM-A095-P2-FACILITATE-SPECIFIC-REQUIREMENT-CODES"]
    assert facilitated.mandatory_content == [
        "clear objectives",
        "key performance indicators measuring achievement of those objectives",
    ]
    assert len(facilitated.qualifier_spans) == 5
    assert "not exhaustive" in facilitated.action
    assert "voluntary" in facilitated.action
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
        "097": 11,
        "098": 2,
    }
    by_id = {norm.norm_id: norm for norms in by_article.values() for norm in norms}

    # The 1 August 2027 deadline belongs to point (g), not to the whole guideline duty.
    guidelines = by_id["AIA-NORM-A096-P1-DEVELOP-IMPLEMENTATION-GUIDELINES"]
    publication = by_id["AIA-NORM-A096-P1-G-PUBLISH-COMPLEMENTARITY-GUIDELINES"]
    assert len(guidelines.mandatory_content) == 7
    assert not guidelines.effective_date_spans
    assert "1 August 2027" not in guidelines.action
    assert publication.effective_date_spans == ["AIA-TEXT-A096-P008"]
    assert "1 August 2027" in publication.action
    deadline_segment = next(
        segment
        for segment in bundle.text_review.segments
        if segment.segment_id == "AIA-TEXT-A096-P008"
    )
    assert deadline_segment.norm_ids.count(publication.norm_id) == 1

    # Revocation, its effect and the preservation of acts already in force are distinct.
    revoke = by_id["AIA-NORM-A097-P3-REVOKE-DELEGATION"]
    ends = by_id["AIA-NORM-A097-P3-REVOCATION-ENDS-DELEGATION"]
    preserved = by_id["AIA-NORM-A097-P3-PRESERVE-ACTS-IN-FORCE"]
    assert revoke.kind.value == "power"
    assert ends.kind.value == preserved.kind.value == "legal_consequence"
    # The actual date alternatives replace the earlier "prospective" summary.
    assert "the day following publication" in ends.action
    assert "later date specified" in ends.action
    assert "already in force" in preserved.action

    # Entry into force has two alternatives; the extension is a separate power.
    entry = by_id["AIA-NORM-A097-P6-DELEGATED-ACT-ENTRY-CONDITION"]
    extension = by_id["AIA-NORM-A097-P6-EXTEND-OBJECTION-PERIOD"]
    assert len(entry.conditions) == 1
    alternatives = entry.conditions[0]
    assert isinstance(alternatives, ConditionGroup) and alternatives.operator == "any_of"
    assert "no objection has been expressed" in alternatives.operands[0]
    assert "will not object" in alternatives.operands[1]
    assert extension.kind.value == "power"
    assert extension.conditions == ["the European Parliament or the Council takes the initiative"]
    assert sum(norm.kind.value == "power" for norm in by_article["097"]) == 3
    assert all(norm.product_scope.value == "outside_supported_actor" for norm in by_article["098"])


def test_article_ninety_nine_extracts_penalty_framework():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A099-")
    }

    assert len(norms) == 13
    assert len(norms["AIA-NORM-A099-P7-CONSIDER-FINE-CIRCUMSTANCES"].mandatory_content) == 10

    # Initial notification and later amendments are the two timed contents of one lifecycle duty.
    notification = norms["AIA-NORM-A099-P2-NOTIFY-PENALTY-RULES"]
    assert "date of entry into application" in notification.action
    assert "subsequent amendments" in notification.action
    assert len(notification.mandatory_content) == 2

    # The fine ceiling, its turnover alternative and the Article 5 exclusion are explicit.
    fine = norms["AIA-NORM-A099-P4-OPERATOR-FINE"]
    assert not fine.mandatory_content
    triggers = fine.conditions[0]
    assert isinstance(triggers, ConditionGroup) and triggers.operator == "any_of"
    assert len(triggers.operands) == 8
    assert "EUR 15 000 000" in fine.action
    assert "3 % of its total worldwide annual turnover" in fine.action
    assert "preceding financial year" in fine.action
    assert fine.exceptions == [
        "the provisions laid down in Article 5, which carry the paragraph 3 fine instead"
    ]


def test_articles_one_hundred_to_one_hundred_five_extract_enforcement_and_amendments():
    bundle = load_normative_coverage()
    counts = {
        article: sum(
            norm.norm_id.startswith(f"AIA-NORM-A{article}-") for norm in bundle.norm_inventory.norms
        )
        for article in ("100", "101", "102", "103", "104", "105")
    }

    assert counts == {"100": 11, "101": 7, "102": 1, "103": 1, "104": 1, "105": 1}
    by_id = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    # Hearing, decision grounds and complainant association are separate protections.
    assert by_id["AIA-NORM-A100-P4-HEARING-RIGHTS"].conditions == [
        "the decision is taken pursuant to Article 100"
    ]
    assert "only on elements and circumstances" in by_id["AIA-NORM-A100-P4-DECISION-GROUNDS"].action
    assert by_id["AIA-NORM-A100-P4-ASSOCIATE-COMPLAINANTS"].conditions == ["there are complainants"]

    # File access is an entitlement of the parties, limited by the enacted interests.
    access = by_id["AIA-NORM-A100-P5-FILE-ACCESS-ENTITLEMENT"]
    assert access.kind.value == "entitlement"
    assert access.subjects[0].subject_ref == "party_concerned_in_article_100_proceedings"
    assert access.exceptions == [
        "the legitimate interest of individuals or undertakings in the protection of their "
        "personal data or business secrets"
    ]

    # Revenue allocation and the protection of the fined body are distinct consequences.
    assert "general budget of the Union" in (
        " ".join(by_id["AIA-NORM-A100-P6-FINE-FUNDS-AND-OPERATION"].action.split())
    )
    assert "effective operation" in by_id["AIA-NORM-A100-P6-PRESERVE-FINED-BODY-OPERATION"].action

    # Article 101 enumerates the fine-amount factors instead of one combined summary.
    amount = by_id["AIA-NORM-A101-P1-FIX-FINE-AMOUNT"]
    assert amount.mandatory_content == [
        "the nature, gravity and duration of the infringement",
        "due account of the principles of proportionality and appropriateness",
        "commitments made in accordance with Article 93(3) or made in relevant codes of practice "
        "in accordance with Article 56",
    ]
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
            norm.norm_id.startswith(f"AIA-NORM-A{article}-") for norm in bundle.norm_inventory.norms
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
    assert norms["AIA-NORM-A111-P2-LEGACY-HIGH-RISK-APPLICABILITY"].kind.value == ("applicability")
    legacy = norms["AIA-NORM-A111-P2-LEGACY-HIGH-RISK-APPLICABILITY"]
    assert len(legacy.conditions) == 2
    assert len(legacy.exceptions) == 2
    assert norms["AIA-NORM-A111-P3-LEGACY-GPAI-COMPLIANCE"].conditions == [
        "the general-purpose AI model was placed on the market before 2 August 2025"
    ]


def test_article_one_hundred_twelve_extracts_review_framework():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A112-")
    }

    assert len(norms) == 19
    assert len(norms["AIA-NORM-A112-P6-SUBMIT-STANDARDISATION-REPORT"].mandatory_content) == 2
    assert len(norms["AIA-NORM-A112-P2-FOUR-YEAR-EVALUATION"].mandatory_content) == 3
    assert len(norms["AIA-NORM-A112-P4-REPORT-ATTENTION-AREAS"].mandatory_content) == 4
    methodology = norms["AIA-NORM-A112-P11-DEVELOP-RISK-EVALUATION-METHODOLOGY"]
    assert len(methodology.mandatory_content) == 3
    assert norms["AIA-NORM-A112-P10-SUBMIT-AMENDMENT-PROPOSALS"].conditions == [
        "the Commission considers amendment necessary"
    ]
    assert len(norms["AIA-NORM-A112-P12-ACCOUNT-FOR-SECTOR-SPECIFICITIES"].conditions) == 1


def test_article_one_hundred_thirteen_preserves_deferred_application_exceptions():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A113-")
    }

    assert len(norms) == 8
    assert "2 December 2026" in norms["AIA-NORM-A113-A-EARLY"].exceptions[0]
    assert norms["AIA-NORM-A113-B"].exceptions == [
        "Article 101 is excluded from the 2 August 2025 application date"
    ]
    assert norms["AIA-NORM-A113-C-ANNEXIII"].exceptions
    assert norms["AIA-NORM-A113-C-ANNEXI"].exceptions


def test_articles_seventy_five_a_and_b_extract_ai_office_enforcement_powers():
    bundle = load_normative_coverage()
    article_a = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A075A-")
    }
    article_b = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-A075B-")
    ]

    assert len(article_a) == 24
    assert len(article_b) == 3
    assert len(article_a["AIA-NORM-A075A-P4-INSPECTION-POWERS"].mandatory_content) == 5
    assert article_a["AIA-NORM-A075A-P3-VOLUNTARY-REPLY-CORRECTNESS"].implementation_mode.value == (
        "missing"
    )

    # Common request fields, the two request-type branches and the copy are separate.
    common = article_a["AIA-NORM-A075A-P3-INFORMATION-REQUEST-CONTENT"]
    simple = article_a["AIA-NORM-A075A-P3-SIMPLE-REQUEST-ADDITIONS"]
    decision = article_a["AIA-NORM-A075A-P3-DECISION-REQUEST-ADDITIONS"]
    copy = article_a["AIA-NORM-A075A-P3-SEND-COPY-TO-TERRITORIAL-AUTHORITY"]
    assert len(common.mandatory_content) == 3
    assert not common.conditions
    assert simple.conditions == ["the request is a simple request"]
    assert decision.conditions == ["the request is made by decision"]
    assert "no obligation to provide the information" in simple.mandatory_content[0]
    assert "incorrect, incomplete or misleading" in decision.mandatory_content[0]
    assert "Court of Justice" in decision.mandatory_content[1]
    # Sending the copy is an action, not a field of the request.
    assert not copy.mandatory_content
    assert "market surveillance authority" in copy.action
    assert_extraction_never_approves(article_a.values())


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

    # Effectiveness, proportionality and the applicable ceiling form one payment-limit rule.
    limits = article_c["AIA-NORM-A075C-P5-PENALTY-PAYMENT-LIMITS"]
    assert not limits.conditions
    assert limits.mandatory_content == [
        "make the penalty payments effective and proportionate",
        "the basis is the average daily income or worldwide annual turnover",
        "the reference period is the preceding financial year",
        "the ceiling of 5 % applies per day",
        "the days are counted from the date appointed by the decision",
    ]


def test_annex_inventory_keeps_external_actors_and_exact_mandatory_content():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    annex_vii = [
        norm for norm in norms.values() if norm.primary_spans[0].startswith("AIA-TEXT-ANNEX-VII-")
    ]
    assert len(annex_vii) == 31
    assert {norm.subjects[0].category.value for norm in annex_vii} >= {
        "supported_operator",
        "notified_or_conformity_body",
    }

    # The application asks for the provider's own identity, and the representative's only when
    # the representative lodges it.
    application = norms["AIA-NORM-ANNEX-VII-QMS-APPLICATION"]
    assert application.mandatory_content[0] == "the name and address of the provider"
    assert application.mandatory_content[1].startswith(
        "if the application is lodged by an authorised representative"
    )
    assert len(application.mandatory_content) == 7
    # Both decisions may be notified to the provider or its authorised representative.
    for norm_id in ("AIA-NORM-ANNEX-VII-QMS-DECISION", "AIA-NORM-ANNEX-VII-DOC-DECISION"):
        assert "provider or its authorised representative" in norms[norm_id].action
    # Examining the proposed changes and notifying the decision are separate actions.
    change = norms["AIA-NORM-ANNEX-VII-QMS-CHANGE-DECISION"]
    notification = norms["AIA-NORM-ANNEX-VII-QMS-CHANGE-NOTIFICATION"]
    assert not change.mandatory_content
    assert "reassessment is necessary" in change.action
    assert notification.mandatory_content == [
        "the conclusions of the examination of the changes",
        "the reasoned assessment decision",
    ]

    section_a = norms["AIA-NORM-ANNEX-VIII-A"]
    assert len(section_a.mandatory_content) == 13
    assert section_a.mandatory_content[0] == (
        "The name, address and contact details of the provider;"
    )
    assert all("Section A item" not in item for item in section_a.mandatory_content)
    # The 13 entries are not 13 unconditional checks: one is optional and one is withheld.
    assert section_a.mandatory_content[12].endswith("(optional).")
    assert "entry 13 is optional" in section_a.action
    assert section_a.exceptions == [
        "entry 12 only, the electronic instructions for use are not provided for high-risk AI "
        "systems in the areas of law enforcement or migration, asylum and border control "
        "management referred to in Annex III, points 1, 6 and 7"
    ]
    assert "where their enacted condition is met" in norms["AIA-NORM-ANNEX-VIII-B"].action

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
    # One span per listed instrument, plus the Section A/B heading it is listed under.
    section_a = {f"AIA-TEXT-ANNEX-I-P{n:03d}" for n in range(2, 14)}
    section_b = {f"AIA-TEXT-ANNEX-I-P{n:03d}" for n in range(15, 24)}
    assert {norm.primary_spans[0] for norm in norms.values()} == section_a | section_b
    for norm in norms.values():
        heading = "P001" if norm.primary_spans[0] in section_a else "P014"
        assert norm.qualifier_spans == [f"AIA-TEXT-ANNEX-I-{heading}"]
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
    assert bundle.norm_inventory.target_norm_ids_for(
        annex.norm_id, NormRelationKind.CARRIED_BY_NORMS
    ) == [article.norm_id]
    assert annex.implementation_mode.value == "carried_by_other_norm"
    assert article.dependencies == []
    assert bundle.norm_inventory.target_norm_ids_for(
        article.norm_id, NormRelationKind.RELIES_ON_NORMS
    ) == [annex.norm_id]


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
    assert procedure.qualifier_spans == [f"AIA-TEXT-ANNEX-VI-P{index:03d}" for index in range(2, 5)]
    provider_checks = [norm for key, norm in norms.items() if "P1" not in key]
    assert all(norm.subjects[0].subject_ref == "provider" for norm in provider_checks)


def test_annex_seven_completion_covers_change_control_and_certificate_content():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-VII-")
    }

    assert len(norms) == 31
    assert len(norms["AIA-NORM-ANNEX-VII-CERTIFICATE-CONTENT"].mandatory_content) == 6
    assert norms["AIA-NORM-ANNEX-VII-INFORM-CHANGES"].subjects[0].subject_ref == "provider"
    assert norms["AIA-NORM-ANNEX-VII-ADDITIONAL-TESTS"].kind.value == "power"
    assert norms["AIA-NORM-ANNEX-VII-TESTS"].conditions == [
        "the notified body is not satisfied with the tests carried out by the provider"
    ]
    assert len(norms["AIA-NORM-ANNEX-VII-MODEL-ACCESS"].conditions) == 3
    assert len(norms["AIA-NORM-ANNEX-VII-ADDITIONAL-TESTS"].conditions) == 2
    primary_spans = {norm.primary_spans[0] for norm in norms.values()}
    assert "AIA-TEXT-ANNEX-VII-I3" not in primary_spans
    assert "AIA-TEXT-ANNEX-VII-I4" not in primary_spans
    assert primary_spans == {
        "AIA-TEXT-ANNEX-VII-P002",
        "AIA-TEXT-ANNEX-VII-P004",
        "AIA-TEXT-ANNEX-VII-P006",
        "AIA-TEXT-ANNEX-VII-P013",
        "AIA-TEXT-ANNEX-VII-P014",
        "AIA-TEXT-ANNEX-VII-P015",
        "AIA-TEXT-ANNEX-VII-P017",
        "AIA-TEXT-ANNEX-VII-P018",
        *{f"AIA-TEXT-ANNEX-VII-P{index:03d}" for index in range(22, 27)},
        "AIA-TEXT-ANNEX-VII-P029",
        "AIA-TEXT-ANNEX-VII-P030",
    }
    assert norms["AIA-NORM-ANNEX-VII-QMS-APPLICATION"].qualifier_spans == [
        f"AIA-TEXT-ANNEX-VII-P{index:03d}" for index in range(7, 13)
    ]
    assert norms["AIA-NORM-ANNEX-VII-DOC-APPLICATION-CONTENT"].qualifier_spans == [
        f"AIA-TEXT-ANNEX-VII-P{index:03d}" for index in range(19, 22)
    ]


def test_annex_nine_registration_content_is_carried_by_article_sixty():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    annex = norms["AIA-NORM-ANNEX-IX-REGISTRATION-INFORMATION"]

    assert len(annex.mandatory_content) == 5
    assert bundle.norm_inventory.target_norm_ids_for(
        annex.norm_id, NormRelationKind.CARRIED_BY_NORMS
    ) == ["AIA-NORM-A060-P4-C-REGISTER-TESTING"]
    assert annex.implementation_mode.value == "carried_by_other_norm"
    assert annex.qualifier_spans == [f"AIA-TEXT-ANNEX-IX-P{index:03d}" for index in range(2, 7)]


def test_annex_ten_extracts_twelve_large_scale_it_instruments():
    bundle = load_normative_coverage()
    norms = [
        norm for norm in bundle.norm_inventory.norms if norm.norm_id.startswith("AIA-NORM-ANNEX-X-")
    ]

    assert len(norms) == 12
    assert all(norm.kind.value == "applicability" for norm in norms)
    segments = [
        segment
        for segment in bundle.text_review.segments
        if segment.source.kind.value == "annex" and segment.source.document == "X"
    ]
    assert sum(segment.disposition.value == "context_only" for segment in segments) == 7


def test_annex_eleven_separates_general_and_systemic_risk_documentation():
    bundle = load_normative_coverage()
    norms = {
        norm.norm_id: norm
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-ANNEX-XI-")
    }

    assert len(norms) == 5
    assert len(norms["AIA-NORM-ANNEX-XI-SECTION-1-TECHNICAL-DOCUMENTATION"].mandatory_content) == 11
    assert norms["AIA-NORM-ANNEX-XI-ENERGY-ESTIMATE-BASIS"].kind.value == "permission"

    # Section 2's three numbered items differ in applicability, so each is its own norm.
    evaluation = norms["AIA-NORM-ANNEX-XI-SECTION-2-SYSTEMIC-RISK-DOCUMENTATION"]
    testing = norms["AIA-NORM-ANNEX-XI-SECTION-2-ADVERSARIAL-TESTING-AND-ADAPTATIONS"]
    architecture = norms["AIA-NORM-ANNEX-XI-SECTION-2-SYSTEM-ARCHITECTURE"]
    systemic_risk = "the general-purpose AI model has systemic risk"
    # Each item has its own span now that the source renders them as separate lines, and all three
    # are qualified by the Section 2 heading that names the addressee and the systemic-risk gate.
    for norm, span in (
        (evaluation, "AIA-TEXT-ANNEX-XI-P019"),
        (testing, "AIA-TEXT-ANNEX-XI-P020"),
        (architecture, "AIA-TEXT-ANNEX-XI-P021"),
    ):
        assert norm.primary_spans == [span]
        assert norm.qualifier_spans == ["AIA-TEXT-ANNEX-XI-P017", "AIA-TEXT-ANNEX-XI-P018"]
        assert norm.conditions[0] == systemic_risk
        assert bundle.norm_inventory.target_norm_ids_for(
            norm.norm_id, NormRelationKind.CARRIED_BY_NORMS
        ) == ["AIA-NORM-A053-P1-A-DRAW-KEEP-DOCUMENTATION"]
        assert norm.verification_mode.value == "judged_by_gap_analysis"

    # Item 1 is owed unconditionally; only items 2 and 3 carry the where-applicable gate.
    assert len(evaluation.conditions) == 2
    bases = evaluation.conditions[1]
    assert isinstance(bases, ConditionGroup) and bases.operator == "any_of"
    assert bases.operands == [
        "the evaluation strategies are described on the basis of available public evaluation "
        "protocols and tools",
        "the evaluation strategies are described on the basis of other evaluation methodologies",
    ]
    assert evaluation.mandatory_content == [
        "a detailed description of the evaluation strategies, including evaluation results",
        "evaluation criteria",
        "metrics",
        "the methodology on the identification of limitations",
    ]
    assert testing.conditions == [systemic_risk, "where applicable"]
    assert architecture.conditions == [systemic_risk, "where applicable"]

    # Red teaming stays an example and the and/or of internal and external testing survives.
    assert testing.mandatory_content == [
        "the measures put in place for the purpose of conducting internal and/or external "
        "adversarial testing (e.g. red teaming)",
        "model adaptations, including alignment and fine-tuning",
    ]
    assert not architecture.mandatory_content
    assert "build or feed into each other" in architecture.action
    # The four obligation norms were reviewed against their spans; the Section 1 energy permission
    # is not a gap-judged obligation and was never part of that pass.
    reviewed = {k: v for k, v in norms.items() if k != "AIA-NORM-ANNEX-XI-ENERGY-ESTIMATE-BASIS"}
    assert all(norm.review.status.value == "proposed" for norm in reviewed.values())
    assert all(not norm.review.verified_by for norm in reviewed.values())
    assert_extraction_never_approves(norms.values())


def test_annex_twelve_downstream_transparency_content_is_carried_by_article_fifty_three():
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    annex = norms["AIA-NORM-ANNEX-XII-DOWNSTREAM-TRANSPARENCY-INFORMATION"]

    assert len(annex.mandatory_content) == 11
    assert bundle.norm_inventory.target_norm_ids_for(
        annex.norm_id, NormRelationKind.CARRIED_BY_NORMS
    ) == ["AIA-NORM-A053-P1-B-ANNEX-XII-CONTENT"]
    assert annex.qualifier_spans == [f"AIA-TEXT-ANNEX-XII-P{index:03d}" for index in range(2, 15)]


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


def test_provisions_imposing_one_duty_name_each_other():
    """Separate provisions can impose one duty without either restating the other.

    `carried_by_norms` says a norm restates another and should not be reported twice;
    `implementation_refs` says two norms are checked by one rule. Neither holds for EU-database
    registration, where the duty is written out again for each actor in its own article. Without a
    third relation, the group agrees only because one reviewer read it that way, and a change to one
    provision leaves the others silently adrift.
    """
    bundle = load_normative_coverage()
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}

    high_risk = norms["AIA-NORM-A016-I-REGISTRATION"]
    assert set(bundle.norm_inventory.parallel_norm_ids_for(high_risk.norm_id)) == {
        "AIA-NORM-A022-P3-E-REGISTER",
        "AIA-NORM-A026-P8-REGISTER",
        "AIA-NORM-A071-P2-PROVIDER-ENTER-ANNEX-VIII-DATA",
        "AIA-NORM-A071-P2-REPRESENTATIVE-ENTER-ANNEX-VIII-DATA",
    }
    # Registering a system concluded NOT high-risk is a different duty in its own group.
    assert "AIA-NORM-A006-P4-REGISTER-SYSTEM" not in bundle.norm_inventory.parallel_norm_ids_for(
        high_risk.norm_id
    )
    assert set(bundle.norm_inventory.parallel_norm_ids_for("AIA-NORM-A006-P4-REGISTER-SYSTEM")) == {
        "AIA-NORM-A049-P2-PROVIDER-REGISTER-NON-HIGH-RISK",
        "AIA-NORM-A049-P2-REPRESENTATIVE-REGISTER-NON-HIGH-RISK",
    }

    # The same sentence written twice for two actors is the clearest case in the Act: an importer
    # duty in Article 23 and the matching distributor duty in Article 24.
    for importer, distributor in (
        (
            "AIA-NORM-A023-P2-WITHHOLD-NONCONFORMING-SYSTEM",
            "AIA-NORM-A024-P2-WITHHOLD-NONCONFORMING-SYSTEM",
        ),
        ("AIA-NORM-A023-P4-PRESERVE-COMPLIANCE", "AIA-NORM-A024-P3-PRESERVE-COMPLIANCE"),
        ("AIA-NORM-A023-P7-COOPERATE", "AIA-NORM-A024-P6-COOPERATE"),
    ):
        assert bundle.norm_inventory.parallel_norm_ids_for(importer) == [distributor]
        assert norms[importer].subjects[0].subject_ref == "importer"
        assert norms[distributor].subjects[0].subject_ref == "distributor"

    for norm in bundle.norm_inventory.norms:
        for partner_id in bundle.norm_inventory.parallel_norm_ids_for(norm.norm_id):
            assert norm.norm_id in bundle.norm_inventory.parallel_norm_ids_for(partner_id)
            # A restatement is already covered by `carried_by`; the two must not overlap.
            assert partner_id not in bundle.norm_inventory.target_norm_ids_for(
                norm.norm_id, NormRelationKind.CARRIED_BY_NORMS
            )


def test_report_lists_every_parallel_duty_group_with_its_provisions(metrics):
    """The relation exists so a reader can see every provision a duty is written in.

    A ledger link nothing renders leaves the reader exactly where the debt started: one provision
    per finding. So the report must carry each group, and each member beside the span it rests on.
    """
    groups = metrics.parallel_duty_groups
    linked = [norm_id for group in groups for norm_id in group.norm_ids]
    assert len(groups) == 21
    assert len(linked) == 63
    assert len(linked) == len(set(linked)), "a norm belongs to at most one group"

    registration = next(g for g in groups if "AIA-NORM-A016-I-REGISTRATION" in g.norm_ids)
    assert dict(zip(registration.norm_ids, registration.provisions, strict=True)) == {
        "AIA-NORM-A016-I-REGISTRATION": "AIA-TEXT-A016-P010",
        "AIA-NORM-A022-P3-E-REGISTER": "AIA-TEXT-A022-P008",
        "AIA-NORM-A026-P8-REGISTER": "AIA-TEXT-A026-P8",
        "AIA-NORM-A071-P2-PROVIDER-ENTER-ANNEX-VIII-DATA": "AIA-TEXT-A071-P002",
        "AIA-NORM-A071-P2-REPRESENTATIVE-ENTER-ANNEX-VIII-DATA": "AIA-TEXT-A071-P002",
    }

    report = render_coverage_markdown(metrics)
    assert "- Parallel-duty groups: 21, linking 63 norms" in report
    section = report.split("## Parallel duties", 1)[1].split("\n## ", 1)[0]
    for group in groups:
        for norm_id, provision in zip(group.norm_ids, group.provisions, strict=True):
            assert f"`{norm_id}` — `{provision}`" in section
