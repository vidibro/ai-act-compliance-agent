"""Find the articles and annexes of this Regulation a norm cites, and the norms they resolve to.

A norm that cites another provision relies on it, so every such citation must be carried by a norm
relation. This module reads the citations from the enacted wording; the build fails while one has
no relation (see tests/test_norm_citations.py), and scripts/link_norm_citations.py adds the missing
ones.

Citations of other instruments ("Article 18 of Regulation (EU) 2019/1020", "Articles 101 and 102
TFEU") are not this Regulation's provisions and are skipped. References within the citing document
("paragraph 3", or its own article number) are out of scope.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from aiact.schemas.norm import NormativeCoverageBundle, NormInventory

_ARTICLE = re.compile(
    r"\bArticles? (?P<body>\d+[a-z]?(?:\(\d+[a-z]?\))*"
    r"(?:(?:, | and | or | to )(?:Article )?(?:\d+[a-z]?(?:\(\d+[a-z]?\))*|\(\d+[a-z]?\)))*)"
    r"(?P<points>(?:,? points? \([a-z]+\)(?:(?:,| and| or| to) \([a-z]+\))*)?)"
)
_ANNEX = re.compile(
    r"(?:(?:points? (?P<before>\d+(?:\([a-z]\))?(?: (?:to|and) \d+(?:\([a-z]\))?)?) of )?"
    r"(?:Section (?P<section>[A-C]) of ))?"
    r"(?:points? (?P<plain>\d+(?:\([a-z]\))?(?: (?:to|and) \d+(?:\([a-z]\))?)?) of )?"
    r"Annex(?:es)? (?P<annex>[IVX]+)\b"
    r"(?:,? Section (?P<section_after>[A-C])\b)?"
    r"(?P<after>,? points? \d+(?:\([a-z]\))?(?: (?:to|and) \d+(?:\([a-z]\))?)?)?"
)
# Text right after a citation that makes it another instrument's provision.
_OTHER_INSTRUMENT = re.compile(r"^,?\s*(?:(?:of|to) (?!this Regulation)|TFEU\b|TEU\b)")


@dataclass(frozen=True)
class Citation:
    kind: str  # "article" | "annex"
    document: str  # "10", "4a", "III"
    paragraph: str | None = None
    points: tuple[str, ...] = ()
    text: str = ""


def _article_citations(match: re.Match[str]) -> list[Citation]:
    parts = re.split(r"\s*(,|\band\b|\bor\b|\bto\b)\s*", match["body"])
    points = tuple(re.findall(r"\(([a-z]+)\)", match["points"] or ""))
    found: list[Citation] = []
    article: str | None = None
    ranged = False
    for part in parts:
        if part in {",", "and", "or", ""}:
            continue
        if part == "to":
            ranged = True
            continue
        item = re.fullmatch(r"(?:Article )?(\d+[a-z]?)?((?:\(\d+[a-z]?\))*)", part)
        if item is None:
            continue
        number = item.group(1) or article
        if number is None:
            continue
        paragraphs = re.findall(r"\((\d+[a-z]?)\)", item.group(2))
        paragraph = paragraphs[0] if paragraphs else None
        if ranged and found:
            last = found[-1]
            if item.group(1) and last.document.isdigit() and number.isdigit():
                for between in range(int(last.document) + 1, int(number)):
                    found.append(Citation("article", str(between)))
            elif paragraph and last.paragraph and last.paragraph.isdigit() and paragraph.isdigit():
                for between in range(int(last.paragraph) + 1, int(paragraph)):
                    found.append(Citation("article", number, str(between)))
        ranged = False
        found.append(Citation("article", number, paragraph))
        article = number
    if points and len(found) == 1:
        found = [Citation("article", found[0].document, found[0].paragraph, points)]
    return [Citation(c.kind, c.document, c.paragraph, c.points, match.group(0)) for c in found]


def _annex_points(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    items = re.findall(r"(\d+)(?:\(([a-z])\))?", text)
    if " to " in text and len(items) == 2:
        low, high = int(items[0][0]), int(items[1][0])
        return tuple(str(n) for n in range(low, high + 1))
    return tuple(number + letter.upper() for number, letter in items)


def cited_provisions(text: str) -> list[Citation]:
    """Every article and annex of this Regulation the text cites, in order."""
    citations: list[Citation] = []
    for match in _ARTICLE.finditer(text):
        if not _OTHER_INSTRUMENT.match(text[match.end() :]):
            citations.extend(_article_citations(match))
    for match in _ANNEX.finditer(text):
        if _OTHER_INSTRUMENT.match(text[match.end() :]):
            continue
        section = match["section"] or match["section_after"]
        points = _annex_points(match["before"] or match["plain"] or match["after"])
        citations.append(
            Citation("annex", match["annex"], section, points, match.group(0).strip(", "))
        )
    return citations


def _article_prefix(document: str) -> str:
    number = re.match(r"\d+", document)
    assert number is not None
    return f"AIA-NORM-A{int(number.group()):03d}{document[number.end() :].upper()}"


def resolve(citation: Citation, norm_ids: list[str]) -> list[str]:
    """The norms a citation points at, as precisely as the citation allows."""
    if citation.kind == "annex":
        prefix = f"AIA-NORM-ANNEX-{citation.document}-"
        members = [n for n in norm_ids if n.startswith(prefix)]
        items = [(n, n.removeprefix(prefix)) for n in members]
        if citation.document == "I" and citation.paragraph in {"A", "B"}:
            section = range(1, 13) if citation.paragraph == "A" else range(13, 22)
            return [n for n, item in items if item[:2].isdigit() and int(item[:2]) in section]
        if citation.document == "VIII" and citation.paragraph:
            return [n for n, item in items if item == citation.paragraph] or members
        if citation.document == "III" and citation.points:
            chosen = [
                n
                for n, item in items
                for point in citation.points
                if re.match(rf"{point}[A-Z]?-" if point.isdigit() else rf"{point}-", item)
            ]
            return chosen or members
        return members

    prefix = _article_prefix(citation.document)
    if citation.document == "3" and citation.paragraph:
        number = re.match(r"\d+", citation.paragraph)
        assert number is not None
        tail = citation.paragraph[number.end() :].upper()
        definition = f"AIA-NORM-A003-D{int(number.group()):03d}{tail}-"
        found = [n for n in norm_ids if n.startswith(definition)]
        if found:
            return found
    if citation.paragraph:
        paragraph = f"{prefix}-P{citation.paragraph.upper()}-"
        if citation.points:
            pointed = [
                n
                for n in norm_ids
                for point in citation.points
                if n.startswith(f"{paragraph}{point.upper()}-")
            ]
            if pointed:
                return pointed
        found = [n for n in norm_ids if n.startswith(paragraph)]
        if found:
            return found
    lead = next((n for n in norm_ids if n.startswith(f"{prefix}-")), None)
    return [lead] if lead else []


@dataclass(frozen=True)
class UnlinkedCitation:
    norm_id: str
    citation: str  # the cited words, e.g. "Articles 102 to 112"
    documents: tuple[tuple[str, str], ...]
    targets: tuple[str, ...]


def unlinked_citations(bundle: NormativeCoverageBundle) -> list[UnlinkedCitation]:
    """Citations whose documents a norm has no relation to, one per cited phrase."""
    inventory: NormInventory = bundle.norm_inventory
    sources = {segment.segment_id: segment.source for segment in bundle.text_review.segments}
    norm_ids = [norm.norm_id for norm in inventory.norms]
    documents = {
        norm.norm_id: (
            sources[norm.primary_spans[0]].kind.value,
            sources[norm.primary_spans[0]].document.lower(),
        )
        for norm in inventory.norms
    }
    linked: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for relation in inventory.relations:
        for target in relation.target_norm_ids:
            linked[relation.source_norm_id].add(documents[target])

    found: list[UnlinkedCitation] = []
    for norm in inventory.norms:
        grouped: dict[str, tuple[list[tuple[str, str]], list[str]]] = {}
        for citation in cited_provisions(norm.norm_text):
            document = (citation.kind, citation.document.lower())
            if document == documents[norm.norm_id] or document in linked[norm.norm_id]:
                continue
            cited, targets = grouped.setdefault(citation.text, ([], []))
            if document not in cited:
                cited.append(document)
            for target in resolve(citation, norm_ids):
                if target not in targets and target != norm.norm_id:
                    targets.append(target)
        found.extend(
            UnlinkedCitation(norm.norm_id, text, tuple(cited), tuple(targets))
            for text, (cited, targets) in grouped.items()
        )
    return found
