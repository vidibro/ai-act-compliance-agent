"""The input: the AI system's documentation, as ingested and chunked for retrieval."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    """A retrievable span of the source document. char_start/char_end index into raw_text,
    so any evidence_chunk_id in a verdict can be resolved back to the exact source location."""

    chunk_id: str
    text: str
    section: str | None = None
    char_start: int
    char_end: int


class SystemUnderReview(BaseModel):
    """One AI system's documentation submitted for compliance review."""

    system_id: str
    source_type: Literal[
        "technical_documentation",
        "system_card",
        "vendor_description",
        "bias_audit",
        "synthetic",
    ]
    source_url: str | None = None
    retrieved_at: date | None = None
    raw_text: str
    chunks: list[DocumentChunk] = []
