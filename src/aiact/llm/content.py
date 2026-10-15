"""Flattening a user turn back to plain text.

Both layers build their user turn in one of two shapes: a plain string, or a list of content blocks
when the provider takes an inline cache breakpoint. Which one you get depends on the model, so any
code that wants to READ a prompt rather than send it has to handle both.

Used for recording what a model was shown, so that anything grading its answer can be given the
same text rather than a reconstruction of it.
"""

from __future__ import annotations

from typing import Any


def flatten(content: Any) -> str:
    """The text of a user turn, whichever shape it was built in."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if isinstance(block, dict))
    return str(content)
