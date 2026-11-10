"""Numbered-paragraph text of a Commission guidance PDF, read by two independent engines.

Guidance exists only as a PDF, and PDF text extraction is lossy. So the stored text is derived,
never authoritative: pdfplumber (pdfminer, pure Python) reads the body, and PDFium (Chrome's
engine, C++) reads it again. Where both yield the same characters, spacing aside, the extraction of
that paragraph is trusted; where they differ, a person checks it against the page.

The body is what each document's `source.md` declares: its font sizes and the lowest point it
reaches on a page. That drops footnotes, footnote markers, the contents page and page numbers, which
would otherwise run into the paragraph they interrupt.

Both engines are imported only when a PDF is actually read. pypdfium2 is a development dependency,
like this check; pdfplumber is a runtime one, since the report app reads uploaded PDFs with it
(`aiact.report_app.uploads`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PARAGRAPH_START = re.compile(r"^\((\d+)\)\s")
_EMPTY_PARENS = re.compile(r"\(\s*\)")


@dataclass(frozen=True)
class GuidanceParagraph:
    number: int
    pages: tuple[int, ...]
    text: str


def _is_body(size: float, bottom: float, sizes: frozenset[float], bottom_limit: float) -> bool:
    return round(size, 1) in sizes and bottom <= bottom_limit


def _join(lines: list[str]) -> str:
    """One paragraph's lines as running text. A line ending in a hyphen continues the same word:
    the documents do not hyphenate automatically, so the hyphen is part of a compound."""
    text = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        text = f"{text}{line}" if not text or text.endswith("-") else f"{text} {line}"
    # A dropped footnote marker leaves its body-size parentheses, and the space before it, behind.
    text = re.sub(r" {2,}", " ", _EMPTY_PARENS.sub("", text))
    return re.sub(r" ([.,;:])", r"\1", text).strip()


def extract_paragraphs(
    pdf_path: Path, body_font_sizes: frozenset[float], body_bottom_limit: float
) -> list[GuidanceParagraph]:
    """The numbered paragraphs, in order. Text before paragraph (1) — cover, contents — is not a
    paragraph and is dropped. A paragraph runs until the next number in sequence, so the headings
    and example lists that follow it belong to it."""
    import pdfplumber

    paragraphs: list[GuidanceParagraph] = []
    number = 0
    pages: list[int] = []
    lines: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            body = page.filter(
                lambda obj: (
                    obj.get("object_type") != "char"
                    or _is_body(obj["size"], obj["bottom"], body_font_sizes, body_bottom_limit)
                )
            )
            for line in (body.extract_text() or "").split("\n"):
                start = _PARAGRAPH_START.match(line.strip())
                if start and int(start.group(1)) == number + 1:
                    if number:
                        paragraphs.append(GuidanceParagraph(number, tuple(pages), _join(lines)))
                    number, pages, lines = number + 1, [], []
                if number:
                    lines.append(line)
                    if page_number not in pages:
                        pages.append(page_number)
    if number:
        paragraphs.append(GuidanceParagraph(number, tuple(pages), _join(lines)))
    return paragraphs


def pdfium_body_text(
    pdf_path: Path, body_font_sizes: frozenset[float], body_bottom_limit: float
) -> str:
    """The same body, read by PDFium, as one comparable string for the whole document."""
    import ctypes

    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    chars: list[str] = []
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        for page in pdf:
            height = page.get_height()
            textpage = page.get_textpage()
            left, right, bottom, top = (ctypes.c_double() for _ in range(4))
            for index in range(textpage.count_chars()):
                size = pdfium_c.FPDFText_GetFontSize(textpage.raw, index)
                pdfium_c.FPDFText_GetCharBox(textpage.raw, index, left, right, bottom, top)
                # PDFium measures from the page's foot; the declared limit is from its head.
                if _is_body(size, height - bottom.value, body_font_sizes, body_bottom_limit):
                    chars.append(chr(pdfium_c.FPDFText_GetUnicode(textpage.raw, index)))
    finally:
        pdf.close()
    return comparable("".join(chars))


def comparable(text: str) -> str:
    """Text reduced to what two engines, or an engine and a hand transcription, must agree on.

    Spacing is where extractors differ, and list bullets and hyphens are re-typed by hand in a
    transcription, so all three are dropped, with PDFium's marker for a hyphen at a line end
    (U+0002); so are the parentheses a dropped footnote marker leaves behind. Every other character
    must match."""
    return re.sub(r"[\s•\-\x02]", "", _EMPTY_PARENS.sub("", text))
