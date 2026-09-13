"""Input size guard: the document is checked before anything is spent on it."""

from __future__ import annotations

from aiact.config import get_settings

_CHARS_PER_TOKEN = 4

FULL_DOCUMENT_CALLS = 17
"""Cascade nodes plus gap role questions — each is sent the whole document. Not the judge, which
sees only excerpts."""


class DocumentTooLarge(ValueError):
    """The document is longer than the configured limit."""


def check_size(document: str, limit: int | None = None) -> str:
    """`document` unchanged, or raise before any model call. A limit of 0 disables the check."""
    cap = get_settings().max_document_chars if limit is None else limit
    if cap <= 0 or len(document) <= cap:
        return document
    # Size and limit only. Anything about the internals is the operator's, not the sender's.
    raise DocumentTooLarge(
        f"The document is {len(document):,} characters; the limit is {cap:,} "
        f"(about {cap // _CHARS_PER_TOKEN:,} tokens)."
    )
