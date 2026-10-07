"""Segment ids read as the provisions a reader cites."""

from __future__ import annotations

from datetime import date

from aiact.report_app.citations import cite_segments, segment_citations
from aiact.schemas.norm import SegmentSource, SourceKind, TextReviewSegment


def segment(number: int, text: str, kind: SourceKind = SourceKind.ARTICLE, document: str = "9"):
    return TextReviewSegment.model_construct(
        segment_id=f"AIA-TEXT-X-P{number:03d}",
        source=SegmentSource(kind=kind, document=document, act_version_date=date(2026, 7, 27)),
        start=number,
        end=number + 1,
        text=text,
    )


def test_paragraphs_points_and_subparagraphs_cite_their_paragraph():
    cites = cite_segments(
        [
            segment(1, "Article 9\nRisk management\n"),
            segment(2, "1. A risk management system shall be established."),
            segment(3, "2. It shall comprise:"),
            segment(4, "    (a) the identification of risks;"),
            segment(5, "        (i) known risks;"),
            segment(6, "    (b) the estimation of risks;"),
            segment(7, "The second subparagraph."),
        ]
    )
    assert list(cites.values()) == [
        "Art. 9",
        "Art. 9(1)",
        "Art. 9(2)",
        "Art. 9(2)(a)",
        "Art. 9(2)(a)(i)",
        "Art. 9(2)(b)",
        "Art. 9(2)",
    ]


def test_a_point_i_after_h_is_a_letter():
    cites = cite_segments(
        [segment(1, "1. List:"), segment(2, "(h) eighth;"), segment(3, "(i) ninth;")]
    )
    assert cites["AIA-TEXT-X-P003"] == "Art. 9(1)(i)"


def test_an_annex_segment_cites_the_annex():
    cites = cite_segments([segment(1, "1. Anything", kind=SourceKind.ANNEX, document="XI")])
    assert cites["AIA-TEXT-X-P001"] == "Annex XI"


def test_the_real_text_resolves_known_segments():
    cites = segment_citations()
    assert cites["AIA-TEXT-A099-P003"] == "Art. 99(3)"
    assert cites["AIA-TEXT-A002-P022"] == "Art. 2(13)"
    assert cites["AIA-TEXT-A004A-P002"] == "Art. 4a(1)(a)"
