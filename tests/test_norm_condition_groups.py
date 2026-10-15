"""Explicit condition grouping survives authoring, generation and loading."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from aiact.norm_loader import load_normative_coverage
from aiact.schemas.norm import LogicalExpression, NormRelationKind

LEAF = {"text": "shared premise", "basis_segment_ids": ["AIA-TEXT-A003-P001"]}


@pytest.mark.parametrize(
    "value",
    [
        {"operator": "xor", "operands": [LEAF]},
        {"operator": "all_of", "operands": []},
        {
            "operator": "all_of",
            "operands": [{"text": " ", "basis_segment_ids": ["AIA-TEXT-A003-P001"]}],
        },
        {"operator": "all_of", "operands": [LEAF], "typo": True},
        {"operator": "any_of", "operands": [LEAF, {"operator": "all_of", "operands": []}]},
    ],
)
def test_condition_groups_reject_ambiguous_or_empty_structure(value):
    with pytest.raises(ValidationError):
        LogicalExpression.model_validate(value)


def test_nested_condition_groups_round_trip():
    value = {
        "operator": "all_of",
        "operands": [
            LEAF,
            {
                "operator": "any_of",
                "operands": [
                    {"text": "alternative a", "basis_segment_ids": ["AIA-TEXT-A003-P001"]},
                    {"text": "alternative b", "basis_segment_ids": ["AIA-TEXT-A003-P002"]},
                ],
            },
        ],
    }
    assert LogicalExpression.model_validate(value).model_dump(mode="json") == value


@pytest.fixture(scope="module")
def corrected_bundle():
    policy = Path(__file__).resolve().parents[1] / "data/policy"
    coverage = policy / "normative-coverage/2026-07-27"
    return load_normative_coverage(
        coverage / "text-review",
        coverage / "norms",
        articles_root=policy / "articles",
        annexes_root=policy / "annexes",
        guidance_root=policy / "guidance",
    )


def test_article_three_preserves_both_routes_and_cross_border_threshold(corrected_bundle):
    norm = next(
        n
        for n in corrected_bundle.norm_inventory.norms
        if n.norm_id.endswith("A003-D061-WIDESPREAD-INFRINGEMENT")
    )
    root = norm.conditions
    assert isinstance(root, LogicalExpression) and root.operator == "all_of"
    assert "contrary to Union law" in root.operands[0]
    routes = root.operands[1]
    assert isinstance(routes, LogicalExpression) and routes.operator == "any_of"
    assert len(routes.operands) == 2
    connections, concurrent = routes.operands
    # The two-Member-State threshold is stated ONCE and shared by the three connecting factors,
    # rather than repeated inside each: the enacted sentence reads "residing in at least two
    # Member States other than the Member State in which" and then lists where.
    assert connections.operator == "all_of" and len(connections.operands) == 2
    threshold, where = connections.operands
    assert "at least two Member States other than" in threshold
    assert where.operator == "any_of" and len(where.operands) == 3
    assert "originated or took place" in where.operands[0]
    assert "authorised representative" in where.operands[1]
    assert "when the infringement is committed by the deployer" in where.operands[2]
    assert concurrent.operator == "all_of" and len(concurrent.operands) == 3
    assert "common features" in concurrent.operands[1]
    assert "same operator, in at least three" in concurrent.operands[2]
    assert norm.kind.value == "definition"
    assert norm.review.status.value == "proposed"


def test_article_six_keeps_four_alternatives_and_human_review_qualification(corrected_bundle):
    norm = next(
        n
        for n in corrected_bundle.norm_inventory.norms
        if n.norm_id.endswith("A006-P3-INSIGNIFICANT-RISK-EXCEPTION")
    )
    root = norm.conditions[0]
    assert root.operator == "all_of" and len(root.operands) == 2
    assert "does not pose a significant risk" in root.operands[0]
    alternatives = root.operands[1]
    assert alternatives.operator == "any_of" and len(alternatives.operands) == 4
    assert "narrow procedural task" in alternatives.operands[0]
    assert "previously completed human activity" in alternatives.operands[1]
    patterns = alternatives.operands[2]
    assert patterns.operator == "all_of" and len(patterns.operands) == 2
    assert "deviations from prior decision-making patterns" in patterns.operands[0]
    assert "without proper human review" in patterns.operands[1]
    assert "preparatory task" in alternatives.operands[3]
    assert "performs profiling of natural persons" in norm.exceptions[0].operands[0]
    assert "AIA-TEXT-A006-P014" in norm.qualifier_spans
    # The norm and its spans carry separate approvals, taken at different times against different
    # questions: the spans that this is the enacted text, the norm that these four alternatives are
    # what it says. Neither implies the other, which is why both are asserted here.
    assert norm.review.status.value == "approved"
    assert norm.review.verified_by == "vidibro"
    assert all(
        s.review.verified_by == "vidibro"
        for s in corrected_bundle.text_review.segments
        if s.source.kind.value == "article" and s.source.document in {"3", "6"}
    )


def test_article_thirty_one_separates_actions_actors_and_exceptions(corrected_bundle):
    norms = {
        n.norm_id.removeprefix("AIA-NORM-A031-"): n
        for n in corrected_bundle.norm_inventory.norms
        if n.norm_id.startswith("AIA-NORM-A031-")
    }
    assert len(norms) == 18
    assert [operand.text for operand in norms["P7-CONFIDENTIALITY-AND-SECRECY"].exceptions] == [
        "except when its disclosure is required by law"
    ]
    staff = norms["P7-STAFF-PROFESSIONAL-SECRECY"]
    assert staff.actors[0].actor_ref == "conformity_assessment_body_personnel"
    assert "notifying authorities of the Member State" in staff.exceptions[0].text
    assert all("disclosure" not in operand.text for operand in staff.exceptions)
    for suffix in (
        "P5-DIRECT-INVOLVEMENT-PROHIBITED",
        "P5-CONFLICTING-ACTIVITIES-PROHIBITED",
    ):
        assert norms[suffix].kind.value == "prohibition"
    assert norms["P5-DIRECT-INVOLVEMENT-PROHIBITED"].mandatory_content == [
        "no direct involvement in designing, developing, marketing or using high-risk AI systems",
        "no representation of parties engaged in those activities",
    ]
    assert "consultancy" in norms["P5-CONFLICTING-ACTIVITIES-PROHIBITED"].action
    assert "independence, objectivity" in norms["P6-INDEPENDENT-OPERATION"].action
    assert "document and implement" in norms["P6-IMPARTIALITY-SYSTEM"].action
    assert "external" in norms["P11-INTERNAL-COMPETENCE-AND-STAFF"].action
    assert (
        "administrative, technical, legal and scientific"
        in norms["P11-PERMANENT-EXPERT-STAFF"].action
    )
    assert "Article 38" in norms["P12-COORDINATION-AND-STANDARDS"].action
    assert "or ensure awareness" in norms["P12-STANDARDISATION-OR-STANDARDS-CURRENCY"].action
    for suffix in (
        "P5-DIRECT-INVOLVEMENT-PROHIBITED",
        "P9-LIABILITY-INSURANCE",
    ):
        assert norms[suffix].review.status.value == "approved"
    assert all(
        n.review.status.value == "proposed"
        for suffix, n in norms.items()
        if suffix not in {"P5-DIRECT-INVOLVEMENT-PROHIBITED", "P9-LIABILITY-INSURANCE"}
    )
    assert all(n.implementation_mode.value == "none_required" for n in norms.values())


def test_article_forty_preserves_illustrative_deliverable(corrected_bundle):
    norms = {n.norm_id: n for n in corrected_bundle.norm_inventory.norms}
    resource = norms["AIA-NORM-A040-P2-RESOURCE-PERFORMANCE-DELIVERABLES"]
    assert len(resource.mandatory_content) == 2
    assert "such as reducing" in resource.mandatory_content[0]
    assert "during its lifecycle" in resource.mandatory_content[0]
    assert (
        resource.mandatory_content[1] == "energy-efficient development of general-purpose AI models"
    )


def test_article_forty_one_preserves_standardisation_conditions(corrected_bundle):
    norms = {n.norm_id: n for n in corrected_bundle.norm_inventory.norms}
    power = norms["AIA-NORM-A041-P1-ADOPT-COMMON-SPECIFICATIONS"]
    assert power.kind.value == "power"
    root = power.conditions
    assert root.operator == "all_of" and len(root.operands) == 4
    assert "Article 10(1)" in root.operands[0].text
    alternatives = root.operands[1]
    assert alternatives.operator == "any_of" and len(alternatives.operands) == 4
    assert "deadline" in alternatives.operands[1].text
    assert "fundamental rights" in alternatives.operands[2].text
    assert "no reference" in root.operands[2].text
    assert "no such reference is expected" in root.operands[3].text


def test_article_forty_three_preserves_routes_and_exceptions(corrected_bundle):
    norms = {n.norm_id: n for n in corrected_bundle.norm_inventory.norms}
    required = norms["AIA-NORM-A043-P1-REQUIRED-ANNEX-VII-ROUTE"].conditions
    assert required.operator == "all_of"
    assert "point 1 of Annex III" in required.operands[0].text
    assert required.operands[1].operator == "any_of"
    assert len(required.operands[1].operands) == 4
    assert "only on the part of the standard that was restricted" in (
        required.operands[1].operands[3].text
    )
    choice = norms["AIA-NORM-A043-P1-CHOOSE-NOTIFIED-BODY"]
    assert choice.kind.value == "permission"
    # The choice is enacted for the Annex VII procedure, which only point 1 of Annex III reaches.
    assert "procedure referred to in Annex VII" in choice.conditions[0].text
    assert "law enforcement, immigration or asylum" in choice.exceptions[0].text
    assert "Article 74(8) or (9)" in choice.exceptions[0].text
    choice_targets = corrected_bundle.norm_inventory.target_norm_ids_for(
        choice.norm_id, NormRelationKind.RELIES_ON_NORMS
    )
    assert choice_targets[0] == "AIA-NORM-A043-P1-AUTHORITY-AS-NOTIFIED-BODY"
    # The cited Annex VII procedure.
    assert all(t.startswith("AIA-NORM-ANNEX-VII-") for t in choice_targets[1:])
    assert len(choice_targets) > 1
