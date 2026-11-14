"""The Act's own words for a row of the report, and the provisions those words point at.

Every row opens to the paragraph it comes from — a duty's resolved requirement, or the paragraph
around a permission, right or effect — so the reader has the context a one-line summary leaves out.
Where that paragraph cites another article or annex of this Regulation ("commitments in accordance
with Article 75b"), the row names it with its title, and the page fetches its text on request.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from aiact.config import get_settings
from aiact.norm_citations import cited_provisions
from aiact.policy_loader import article_filename, articles_dir_for, provision_text
from aiact.report_app.citations import ordered_segments, segment_citations

_TITLE = re.compile(r"^title:\s*(.+)$", re.MULTILINE)
_ANNEX_ID = re.compile(r"[IVX]+")
_HEADING = re.compile(r"^(?:Article|ANNEX|Annex) [0-9A-Za-z]+\n[^\n]*\n+")


class Provision(BaseModel):
    key: str
    """"75b" for an article, "IV" for an annex — the id the page asks for its text by."""
    citation: str
    """"Art. 75b" or "Annex IV"."""
    title: str


class ProvisionText(Provision):
    text: str


def _path(key: str) -> Path:
    version = str(get_settings().act_version_date)
    if _ANNEX_ID.fullmatch(key):
        return Path(get_settings().policy_annexes_path) / version / f"annex-{key}.md"
    return articles_dir_for(version) / article_filename(key)


@lru_cache(maxsize=256)
def provision(key: str) -> ProvisionText | None:
    """An article or annex of the pinned Act, with its title and text; None if there is none."""
    try:
        path = _path(key)
    except ValueError:
        return None
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    title = _TITLE.search(raw)
    citation = f"Annex {key}" if _ANNEX_ID.fullmatch(key) else f"Art. {key}"
    return ProvisionText(
        key=key,
        citation=citation,
        title=title.group(1).strip() if title else "",
        # The heading ("Article 75b", "Commitments") is what `citation` and `title` already say.
        text=_HEADING.sub("", provision_text(path), count=1),
    )


def references(text: str, own: str | None = None) -> list[Provision]:
    """The other articles and annexes of this Regulation `text` cites, once each, in order.
    Citations of other instruments are skipped, as is the provision the text belongs to."""
    keys = dict.fromkeys(c.document for c in cited_provisions(text) if c.document != own)
    found = (provision(key) for key in keys)
    return [Provision(key=p.key, citation=p.citation, title=p.title) for p in found if p]


_CITED_AS = re.compile(r"Art\. (\d+[a-z]?)\b|Annex ([IVX]+)\b")


def provision_cited_as(citation: str) -> Provision | None:
    """The article or annex a citation such as "Art. 21(3)" sits in, under that citation."""
    match = _CITED_AS.match(citation)
    found = provision(match.group(1) or match.group(2)) if match else None
    return Provision(key=found.key, citation=citation, title=found.title) if found else None


@lru_cache(maxsize=1)
def _segments() -> tuple[dict[str, list[tuple[str, str]]], dict[str, tuple[str, str, str]]]:
    """Each source document's segments in order as (citation, text), and each segment id's
    (document, citation, text)."""
    citations = segment_citations()
    by_document: dict[str, list[tuple[str, str]]] = {}
    by_id: dict[str, tuple[str, str, str]] = {}
    for segment in ordered_segments():
        document = f"{segment.source.kind.value}:{segment.source.document}"
        citation = citations.get(segment.segment_id, "")
        text = segment.text.strip()
        by_document.setdefault(document, []).append((citation, text))
        by_id[segment.segment_id] = (document, citation, text)
    return by_document, by_id


def paragraph_text(span: str) -> str:
    """The whole paragraph a source segment belongs to — "Art. 75c(3)" and its points — or, for an
    annex or an unnumbered article, the segment alone."""
    by_document, by_id = _segments()
    if span not in by_id:
        return ""
    document, citation, own = by_id[span]
    paragraph = re.match(r"Art\. [0-9a-z]+\([0-9a-z]+\)", citation)
    if paragraph is None:
        return own
    head = paragraph.group(0)
    return "\n".join(
        text for cite, text in by_document[document] if cite == head or cite.startswith(head + "(")
    )


def article_of(spans: list[str]) -> str | None:
    """The article a norm's first source span sits in, e.g. "75c" for AIA-TEXT-A075C-P003."""
    match = re.match(r"AIA-TEXT-A0*(\d+)([A-Z]?)-", spans[0]) if spans else None
    return f"{match.group(1)}{match.group(2).lower()}" if match else None


_DEFINITION_CITED = re.compile(
    r"Article 3,? points? \((\d+)\)|points? \((\d+)\)(?:\([a-z]\))? of Article 3\b"
)
_DEFINITION = re.compile(r"^\s*\((\d+[a-z]?)\) ", re.MULTILINE)


@lru_cache(maxsize=1)
def _definitions() -> dict[str, str]:
    """Article 3's definitions by point number, each in full with its sub-points."""
    found = provision("3")
    text = found.text if found else ""
    marks = list(_DEFINITION.finditer(text))
    ends = [m.start() for m in marks[1:]] + [len(text)]
    return {
        m.group(1): " ".join(
            line.strip() for line in text[m.start() : end].splitlines() if line.strip()
        )
        for m, end in zip(marks, ends, strict=True)
    }


def cited_definitions(text: str) -> list[str]:
    """The Article 3 definitions `text` cites by point ("Article 3, point (49)(c)"), in full."""
    numbers = dict.fromkeys(a or b for a, b in _DEFINITION_CITED.findall(text))
    return [definition for n in numbers if (definition := _definitions().get(n))]
