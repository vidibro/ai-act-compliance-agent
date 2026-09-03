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
