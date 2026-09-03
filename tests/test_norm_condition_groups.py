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
