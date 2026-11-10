"""Text out of an uploaded PDF or DOCX, for the report app's input box.

The review reads plain text or Markdown, and the page reads `.txt` and `.md` files itself. A PDF
or DOCX cannot be read in the browser, so its bytes come to the server (`POST /api/extract`),
the text is pulled out here — no model call, nothing stored — and goes back to the input box,
where the reader sees exactly what the review will read before running it.

PDF text comes from pdfplumber, the engine the guidance pipeline already reads the Commission's
PDFs with (`aiact.guidance_text`). PDF extraction is lossy by nature; here the reader checks the
result on screen, so one engine serves where the stored guidance text needed two. A PDF that
yields no text — a scan — is refused with a message rather than reviewed empty.

DOCX is a zip of XML, read with the standard library alone: each paragraph's runs in document
order, tabs and line breaks kept, table rows one per line with `|` between cells. A `Heading N`
(or `Title`) style becomes a Markdown heading and a numbered or bulleted paragraph a list item, so
a Word-authored system card keeps the structure the classifier and the judge read Markdown for.
The old binary `.doc` is not a zip and is refused up front, not mangled.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterator
from pathlib import PurePosixPath, PureWindowsPath
from xml.etree import ElementTree

SUPPORTED_UPLOADS = (".pdf", ".docx")
"""What `extract_upload` can read. The page sends every other format as text, client-side."""


class UnsupportedUpload(ValueError):
    """A format this module does not read (415 on the endpoint)."""


class UnreadableUpload(ValueError):
    """A file that is not what its name says, or holds no text (422 on the endpoint)."""


def extract_upload(filename: str, data: bytes) -> str:
    """The text of the file, or a refusal a reader can act on.

    Dispatch is by the filename's extension — the one fact the reader chose — with the bytes
    checked against it before a parser runs, so a mislabelled file gets a straight answer instead
    of a parser traceback."""
    suffix = _suffix(filename)
    if suffix == ".pdf":
        text = _pdf_text(filename, data)
    elif suffix == ".docx":
        text = _docx_text(filename, data)
    else:
        named = f"{suffix!r} files" if suffix else "a file with no extension"
        readable = " or ".join(SUPPORTED_UPLOADS)
        raise UnsupportedUpload(f"Cannot read {named} here — upload {readable}, or paste the text.")
    if not text.strip():
        raise UnreadableUpload(
            f"No text could be read from {filename!r}. A scanned PDF holds images, not text — "
            "it needs OCR first; otherwise, paste the document's text."
        )
    return text


def _suffix(filename: str) -> str:
    """The extension, whichever way the browser spelt the path."""
    return PurePosixPath(PureWindowsPath(filename).name).suffix.lower()


# ---- PDF ---------------------------------------------------------------------------------------


def _pdf_text(filename: str, data: bytes) -> str:
    """Every page's text, pages separated by a blank line."""
    # The header may sit behind a few bytes of junk in the wild; pdfminer tolerates up to a
    # kilobyte, and so does this check.
    if b"%PDF-" not in data[:1024]:
        raise UnreadableUpload(f"{filename!r} does not look like a PDF inside.")
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [(page.extract_text() or "").strip() for page in pdf.pages]
    except Exception as exc:  # damaged, truncated, password-protected — pdfminer's zoo of errors
        raise UnreadableUpload(
            f"{filename!r} could not be read as a PDF: {_first_line(exc)}"
        ) from exc
    return "\n\n".join(page for page in pages if page)


def _first_line(exc: Exception) -> str:
    text = str(exc).strip()
    return (text.splitlines()[0][:200] if text else type(exc).__name__).rstrip(".") + "."


# ---- DOCX --------------------------------------------------------------------------------------

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING_STYLE = re.compile(r"^heading\s*([1-6])$", re.IGNORECASE)
# Word marks a list item with numbering properties (`w:numPr`); some writers reach for a list
# paragraph style instead. Either way it reads as a Markdown list item.
_LIST_STYLE = re.compile(r"^list\s*(bullet|number|paragraph)", re.IGNORECASE)


def _docx_text(filename: str, data: bytes) -> str:
    """The document body as Markdown-flavoured text, blocks separated by a blank line."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive, archive.open("word/document.xml") as doc:
            root = ElementTree.parse(doc).getroot()
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise UnreadableUpload(
            f"{filename!r} could not be read as a Word document (.docx). If it is an old "
            "binary .doc, save it as .docx first."
        ) from exc
    body = root.find(f"{_W}body")
    if body is None:
        raise UnreadableUpload(f"{filename!r} has no document body to read.")
    return "\n\n".join(block for block in _blocks(body) if block)


def _blocks(body: ElementTree.Element) -> Iterator[str]:
    """One string per paragraph or table row, in document order."""
    for child in body:
        if child.tag == f"{_W}p":
            yield _paragraph(child)
        elif child.tag == f"{_W}tbl":
            for row in child.findall(f"{_W}tr"):
                cells = [
                    " ".join(filter(None, (_paragraph(p) for p in cell.iter(f"{_W}p"))))
                    for cell in row.findall(f"{_W}tc")
                ]
                yield " | ".join(cells).strip()


def _paragraph(paragraph: ElementTree.Element) -> str:
    """A paragraph's text, with its Word structure spelt the way the review reads Markdown."""
    pieces: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_W}t":
            pieces.append(node.text or "")
        elif node.tag == f"{_W}tab":
            pieces.append("\t")
        elif node.tag in (f"{_W}br", f"{_W}cr"):
            pieces.append("\n")
    text = "".join(pieces).strip()
    if not text:
        return ""
    properties = paragraph.find(f"{_W}pPr")
    style = "" if properties is None else _style_id(properties)
    heading = _HEADING_STYLE.match(style)
    if heading:
        return f"{'#' * int(heading.group(1))} {text}"
    if style.lower() == "title":
        return f"# {text}"
    listed = properties is not None and properties.find(f"{_W}numPr") is not None
    if listed or _LIST_STYLE.match(style):
        return f"- {text}"  # a numbered or bulleted list item
    return text


def _style_id(properties: ElementTree.Element) -> str:
    style = properties.find(f"{_W}pStyle")
    return style.get(f"{_W}val", "") if style is not None else ""
