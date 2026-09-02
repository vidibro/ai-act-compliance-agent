"""Read-only granularity triage; signals are not findings or proof of completeness."""

from __future__ import annotations

import re
from dataclasses import dataclass

from aiact.schemas.norm import NormativeCoverageBundle

LIST_ITEM = re.compile(r"^[ \t]+(?:\([a-z]{1,3}\)|[0-9]+\.)[ \t]+", re.MULTILINE)
MODAL = re.compile(r"\b(?:shall|must|may\s+only|(?:is|are)\s+required\s+to)\b", re.IGNORECASE)


@dataclass(frozen=True)
class GranularityCandidate:
    segment_id: str
    source_sha256: str
    list_items: int
    modal_signals: int
    norm_ids: tuple[str, ...]
    signals: tuple[str, ...]


def granularity_signals(text: str, norm_count: int) -> tuple[int, int, tuple[str, ...]]:
    """Flag internal lists and multi-modal spans; deliberately make no legal decision.

    This does not detect every unnumbered list, implied duty, mixed actor, or missing qualifier.
    A compound content list may legitimately remain one norm. A modal in an exception may create
    a false positive. Unflagged source text still requires semantic review.
    """
    list_items = len(LIST_ITEM.findall(text))
    modals = len(MODAL.findall(text))
    signals = []
    if list_items >= 2:
        signals.append("internal_list")
    if modals >= 2 and norm_count <= 1:
        signals.append("multiple_modals_single_norm")
    return list_items, modals, tuple(signals)


def scan_granularity(bundle: NormativeCoverageBundle) -> list[GranularityCandidate]:
    """Scan the entire loaded partition, including already approved segments."""
    candidates = []
    for segment in bundle.text_review.segments:
        items, modals, signals = granularity_signals(segment.text, len(segment.norm_ids))
        if signals:
            candidates.append(
                GranularityCandidate(
                    segment_id=segment.segment_id,
                    source_sha256=segment.sha256,
                    list_items=items,
                    modal_signals=modals,
                    norm_ids=tuple(segment.norm_ids),
                    signals=signals,
                )
            )
    return candidates
