"""Explicit condition grouping survives authoring, generation and loading."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from aiact.norm_loader import load_normative_coverage
from aiact.schemas.norm import ConditionGroup


@pytest.mark.parametrize(
    "value",
    [
        {"operator": "xor", "operands": ["a", "b"]},
        {"operator": "all_of", "operands": []},
        {"operator": "any_of", "operands": ["a"]},
        {"operator": "all_of", "operands": ["a", " "]},
        {"operator": "all_of", "operands": ["a", "b"], "typo": True},
        {"operator": "any_of", "operands": ["a", {"operator": "all_of", "operands": []}]},
    ],
)
def test_condition_groups_reject_ambiguous_or_empty_structure(value):
    with pytest.raises(ValidationError):
        ConditionGroup.model_validate(value)


def test_nested_condition_groups_round_trip():
    value = {
        "operator": "all_of",
        "operands": [
            "shared premise",
            {"operator": "any_of", "operands": ["alternative a", "alternative b"]},
        ],
    }
    assert ConditionGroup.model_validate(value).model_dump(mode="json") == value


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
    root = norm.conditions[0]
    assert isinstance(root, ConditionGroup) and root.operator == "all_of"
    assert "contrary to Union law" in root.operands[0]
    routes = root.operands[1]
    assert isinstance(routes, ConditionGroup) and routes.operator == "any_of"
    assert len(routes.operands) == 2
    connections, concurrent = routes.operands
    assert connections.operator == "any_of" and len(connections.operands) == 3
    assert all("at least two Member States other than" in item for item in connections.operands)
    assert "originated or took place" in connections.operands[0]
    assert "authorised representative" in connections.operands[1]
    assert "when the infringement is committed by the deployer" in connections.operands[2]
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
    assert "profiling of natural persons is always high-risk" in norm.exceptions[0]
    assert "AIA-TEXT-A006-P014" in norm.qualifier_spans
    assert norm.review.status.value == "proposed"
    # Existing independent source approvals are not new norm approvals.
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
    assert len(norms) == 19
    assert norms["P7-CONFIDENTIALITY-AND-SECRECY"].exceptions == ["disclosure required by law"]
    staff = norms["P7-STAFF-PROFESSIONAL-SECRECY"]
    assert staff.subjects[0].subject_ref == "notified_body_staff"
    assert "notifying authorities of the Member State" in staff.exceptions[0]
    assert "disclosure required by law" not in staff.exceptions
    for suffix in (
        "P5-DIRECT-INVOLVEMENT-PROHIBITED",
        "P5-PARTY-REPRESENTATION-PROHIBITED",
        "P5-CONFLICTING-ACTIVITIES-PROHIBITED",
    ):
        assert norms[suffix].kind.value == "prohibition"
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
    assert all(n.review.status.value == "proposed" for n in norms.values())
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
