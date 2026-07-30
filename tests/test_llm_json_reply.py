"""Both layers parse JSON out of a model reply, and both used to carry their own copy of this.

`response_format={"type": "json_object"}` is advisory rather than enforced on several providers, so
a reply can arrive wrapped in a markdown fence and json.loads dies on the first backtick. One
implementation, tested once — a provider quirk should not be fixed twice.
"""

import json

import pytest

from aiact.llm import unfence


@pytest.mark.parametrize(
    "raw",
    [
        '{"verdict": "pass"}',
        '```json\n{"verdict": "pass"}\n```',
        '```\n{"verdict": "pass"}\n```',
        '   ```json\n{"verdict": "pass"}\n```   ',
        '```json{"verdict": "pass"}```',
    ],
)
def test_a_fenced_reply_parses_as_json(raw):
    assert json.loads(unfence(raw)) == {"verdict": "pass"}


def test_unfencing_does_not_rescue_garbage():
    """Stripping the fence must not turn an unreadable reply into a confident one — what comes out
    still has to survive json.loads, and here it must not."""
    with pytest.raises(json.JSONDecodeError):
        json.loads(unfence("```json\nnot actually json\n```"))


def test_backticks_inside_the_payload_survive():
    """A quoted backtick belongs to the value, not to a fence."""
    assert json.loads(unfence('{"reasoning": "the doc says ``TODO``"}')) == {
        "reasoning": "the doc says ``TODO``"
    }
