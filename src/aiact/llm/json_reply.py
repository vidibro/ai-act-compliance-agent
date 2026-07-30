"""Recovering JSON from a model that was asked for JSON."""

from __future__ import annotations

import re

# Models very often wrap JSON in a markdown fence, even when told to reply with JSON and nothing
# else, and even with response_format={"type": "json_object"} set — that flag is advisory rather
# than enforced on several providers. json.loads then fails at char 0 on the backtick. Stripping
# the fence is provider-agnostic: it costs nothing where the reply is already bare JSON, and it is
# the difference between an answer and an abstention where it is not.
_FENCED_JSON = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def unfence(raw: str) -> str:
    """Strip a surrounding ```json fence, if there is one."""
    match = _FENCED_JSON.match(raw)
    return match.group(1) if match else raw
