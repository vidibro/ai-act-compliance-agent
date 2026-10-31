"""Readable citations for source-text segments: AIA-TEXT-A099-P003 is "Art. 99(3)".

A segment id numbers segments in order, not paragraphs, so the citation is read from the text: a
segment opens with its paragraph number ("3. ...") or point marker ("(a) ..."), and a point or an
unnumbered subparagraph belongs to the paragraph before it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from functools import lru_cache

from aiact.norm_loader import load_normative_coverage
from aiact.schemas.norm import SourceKind, TextReviewSegment

_PARAGRAPH = re.compile(r"(\d+[a-z]?)\.\s")
_POINT = re.compile(r"\(([a-z]+)\)\s")
_ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"}
# A letter that also reads as a roman numeral is a letter when it follows the letter before it.
_LETTER_BEFORE = {"i": "h", "v": "u", "x": "w"}


def cite_segments(segments: Sequence[TextReviewSegment]) -> dict[str, str]:
    """Citation per segment id, for segments given in document order."""
    citations: dict[str, str] = {}
    current: tuple[SourceKind, str] | None = None
    paragraph: str | None = None
    letter: str | None = None
    for segment in segments:
        source = (segment.source.kind, segment.source.document)
        if source != current:
            current, paragraph, letter = source, None, None
        if segment.source.kind is not SourceKind.ARTICLE:
            citations[segment.segment_id] = f"Annex {segment.source.document}"
            continue
        text = segment.text.lstrip()
        parts: list[str] = []
        if match := _PARAGRAPH.match(text):
            paragraph, letter = match.group(1), None
            parts = [paragraph]
        elif match := _POINT.match(text):
            marker = match.group(1)
            nested = (
                marker in _ROMAN and letter is not None and _LETTER_BEFORE.get(marker) != letter
            )
            if not nested:
                letter = marker
            parts = [p for p in (paragraph, letter, marker if nested else None) if p]
        elif paragraph:
            parts = [paragraph]
        suffix = "".join(f"({part})" for part in parts)
        citations[segment.segment_id] = f"Art. {segment.source.document}{suffix}"
    return citations


@lru_cache(maxsize=1)
def ordered_segments() -> tuple[TextReviewSegment, ...]:
    """The normative coverage's text segments in document order, loaded ONCE for the app's
    lifetime. The load reads a few hundred YAML shards and takes seconds, and both this module
    and `law` need the same segments — so they share one load rather than each paying for it."""
    segments = load_normative_coverage().text_review.segments
    return tuple(sorted(segments, key=lambda s: (s.source.kind.value, s.source.document, s.start)))


@lru_cache(maxsize=1)
def segment_citations() -> dict[str, str]:
    return cite_segments(ordered_segments())
