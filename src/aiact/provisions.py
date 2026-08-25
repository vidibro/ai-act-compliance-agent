"""One address for every piece of the enacted text, derived from the stored files.

WHY THIS EXISTS. Every coverage claim this project makes has to be checkable against the law rather
than against something someone typed. A test that asserts "the Annex lists twenty instruments"
compares the code to a number and passes whatever the Annex says; a test that counts the Annex
cannot.

So nothing here accepts a count or a list as input. The enumerator reads the files and produces the
addresses; every partition, ledger and budget elsewhere is a claim ABOUT that output.

THE UNIT IS THE DIVISION, and the coarsest ruling allowed anywhere is one per division:

    Article 6(1a)        a numbered paragraph
    Article 16(b)        a lettered point, where the article has no numbered paragraphs
    Article 3(63)        a numbered point, likewise — Art. 3 lists 68 definitions this way
    Annex III(5)         a numbered item
    Annex VIII(A)(1)     a numbered item inside a lettered Section, whose numbering restarts

Below a division sit sub-points — Art. 27(1)(a)-(f), Annex III(5)(b) — which elaborate the division
they hang from rather than standing alone. A ruling on the division covers them. Above a division
sits the whole article or annex, and a ruling THERE is what this module exists to make impossible
to mistake for coverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from aiact.policy_loader import (
    _POINT_LABEL,
    article_filename,
    provision_labels,
    provision_text,
)

# The Annexes are rendered inconsistently by the Official Journal's own XML, and the fetcher
# preserves what it is given rather than tidying it. Both shapes are real and both are here:
#
#   line-anchored   "    1. Biometrics, in so far as ..."        (Annexes III, IV, V, VI, VIII, IX)
#   run together    "Section A. ... 1.Directive 2006/42/EC ..."  (Annexes I and VII)
#
# So an item marker is `N.` followed by a space, a capital, or an opening bracket, at a line start
# or after whitespace. Requiring a line start would miss every instrument in Annex I.
_ANNEX_ITEM = re.compile(r"(?:^|(?<=\s))(\d{1,2})\.(?=[ \t]*[A-Z(‘])", re.M)

# Annexes I, VIII and XI restart their numbering inside Sections, so an item number alone is not an
# address: Annex VIII has three different point 1s. Sections are lettered in some annexes and
# numbered in others, and both punctuations occur.
_ANNEX_SECTION = re.compile(r"^Section (\d+|[A-Z])\s*[.:—-]?\s*(?=[A-Z])", re.M)


@dataclass(frozen=True)
class Provision:
    """One addressable piece of the Act, as the stored text divides it."""

    kind: str  # "article" | "annex"
    document: str  # "6", "75a", "III"
    division: str | None  # "1a", "b", "A/1"; None where the document has no divisions

    def __str__(self) -> str:
        label = f"Art. {self.document}" if self.kind == "article" else f"Annex {self.document}"
        if self.division is None:
            return label
        parts = "".join(f"({p})" for p in self.division.split("/"))
        return f"{label}{parts}"


def _annex_body(annexes_dir: Path, roman: str) -> str:
    """The annex's text with its heading block removed, verified against its stored hash."""
    path = annexes_dir / f"annex-{roman}.md"
    if not path.is_file():
        raise FileNotFoundError(f"No annex file for Annex {roman} at {path}")
    body = provision_text(path)
    # body = "ANNEX <roman>\n<title>\n\n<content>"; drop the heading block.
    _, _, content = body.partition("\n\n")
    return content or body


def annex_divisions(annexes_dir: Path, roman: str) -> tuple[str, ...]:
    """Every separately citable item of one annex, in the order the Annex writes them.

    Numbered items, prefixed by their Section where the annex has Sections — `A/1`, `B/1` — because
    the numbering restarts and a bare `1` would name three different provisions in Annex VIII.

    An annex that enumerates nothing returns empty, and that is a real answer rather than a failure:
    Annex II is a bare list of offence names with no numbering, so the annex IS the unit.
    """
    content = _annex_body(annexes_dir, roman)
    sections = list(_ANNEX_SECTION.finditer(content))

    def section_of(pos: int) -> str | None:
        name = None
        for section in sections:
            if section.start() < pos:
                name = section.group(1)
            else:
                break
        return name

    # KEPT ONLY IF IT CONTINUES THE SEQUENCE. Where an annex is run together on one line, a
    # cross-reference reads exactly like an item marker: "points 2 to 5. Article 17 ..." offers a
    # `5.` and a `17.` that begin nothing. Sequence position separates the two, and it is structure
    # the text carries rather than a list of exceptions someone maintains.
    #
    # A Section may restart the count or carry it on, and both occur: Annex VIII starts each Section
    # at 1, Annex I runs 1-12 through Section A and 13-21 through Section B. So the next number is
    # accepted, and so is a 1 that opens a Section — nothing else.
    divisions: list[str] = []
    nxt, current = 1, object()
    for item in _ANNEX_ITEM.finditer(content):
        section = section_of(item.start())
        number = int(item.group(1))
        opens_section = section != current and number == 1
        if number != nxt and not opens_section:
            continue
        current, nxt = section, number + 1
        divisions.append(f"{section}/{number}" if section else str(number))
    if divisions:
        return tuple(divisions)

    # No numbered list. Some annexes enumerate with letters instead — Annex XIII's criteria.
    letters = list(_POINT_LABEL.finditer(content))
    if letters:
        top = min(len(m.group("indent")) for m in letters)
        return tuple(m.group("label") for m in letters if len(m.group("indent")) == top)
    return ()


# The article half already lives beside the text loader, which owns the file read and its
# integrity check. Re-exported rather than reimplemented: two copies of "what counts as a
# division" would drift, and one answer is the whole point of this module.
article_divisions = provision_labels

# An OJ citation of a Union act — "Directive 2006/42/EC", "Regulation (EU) No 168/2013". The
# optional "No" and the trailing "/EC" both vary by era and by act type.
_INSTRUMENT = re.compile(
    r"(?:Regulation|Directive)\s+(?:\((?:EU|EC|EEC)\)\s+)?(?:No\s+)?\d{1,4}/\d{2,4}"
    r"(?:/(?:EC|EU|EEC))?"
)


def annex_instruments(annexes_dir: Path, roman: str) -> dict[str, str]:
    """The Union act each item of an annex names, keyed by the same division label as above.

    For the annexes that ARE lists of legislation — Annex I's harmonisation instruments, Annex X's
    large-scale IT systems — the item is a citation and the citation is the content. The FIRST one
    inside an item is the act that item enacts; later ones are the acts it amends or repeals, which
    is why this takes the first rather than collecting them all.

    Exists so that anything naming an instrument — the ledger's rulings, the `legislation` strings
    the classification cascade offers the model as answer options — can be checked against the
    Annex rather than against whoever typed it. Annex I lists machinery twice, under instruments
    in different Sections, so a transposed pair there decides whether Chapter III applies at all.
    """
    content = _annex_body(annexes_dir, roman)
    positions: list[tuple[str, int]] = []
    for division in annex_divisions(annexes_dir, roman):
        number = division.rpartition("/")[2]
        marker = re.compile(rf"(?:^|(?<=\s)){re.escape(number)}\.(?=[ \t]*[A-Z(‘])", re.M)
        start = positions[-1][1] if positions else 0
        found = marker.search(content, start)
        if found:
            positions.append((division, found.end()))

    instruments: dict[str, str] = {}
    for index, (division, start) in enumerate(positions):
        end = positions[index + 1][1] if index + 1 < len(positions) else len(content)
        found = _INSTRUMENT.search(content, start, end)
        if found:
            instruments[division] = found.group(0)
    return instruments


def points_within(articles_dir: Path, article: str, paragraph: str) -> tuple[str, ...]:
    """The top-level lettered points of one numbered paragraph.

    A LEVEL BELOW the division, and needed where a paragraph's points are the substance rather than
    an elaboration of it. Art. 5(1) is the case: the paragraph is a chapeau and the prohibited
    practices are its points, so "every practice the Act bans" is this list and not Art. 5's
    paragraphs. Labels may be two letters — 5(1)(ba) and 5(1)(bb) were inserted between (b) and (c)
    without renumbering what followed.
    """
    from aiact.policy_loader import _extract_paragraph, _read_article

    provisions, _ = _read_article(articles_dir, article)
    text = _extract_paragraph(provisions, paragraph, article)
    labels = list(_POINT_LABEL.finditer(text))
    if not labels:
        return ()
    top = min(len(m.group("indent")) for m in labels)
    return tuple(m.group("label") for m in labels if len(m.group("indent")) == top)


def _article_key(name: str) -> tuple[int, str]:
    match = re.match(r"(\d+)([a-z]*)", name)
    assert match is not None
    return int(match.group(1)), match.group(2)


_ANNEX_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII",
                "XIII", "XIV", "XV", "XVI"]


def _with_unnumbered(
    articles_dir: Path, article: str, divisions: tuple[str, ...]
) -> tuple[str, ...]:
    """`divisions`, plus an address for enacted text they leave outside.

    ONLY FOR THE POINT SHAPE, and that restriction is what makes it correct. An article divided into
    numbered PARAGRAPHS starts at paragraph 1 and every later subparagraph belongs to the paragraph
    above it — Art. 26(5) runs to two subparagraphs and both are 26(5). An article divided into
    POINTS is built the other way: a chapeau introduces the list, the points hang off it, and a
    closing paragraph after the last point is outside all of them. The Act writes points in
    brackets, `(a)` or `(1)`, and paragraphs without, which is how the two are told apart here.

    Art. 113 is why it matters. Its second sentence — "It shall apply from 2 August 2026" — sits
    before point (a) and is the general application date every rule's `effective_date` is read from.
    Art. 75b's closing paragraph, after point (c), is what happens when the AI Office rejects the
    commitments an operator offered. Neither is a point, and without an address neither is in the
    denominator that `unaccounted 0` is measured against.

    `chapeau` and `closing` are not citable divisions in the Act's own sense — no rule cites
    Art. 113(chapeau). They exist so the partition has somewhere to put the words, which forces the
    ledger to rule on them rather than letting them fall out of the count unnoticed. A chapeau that
    only introduces its list is still an address, and the ledger dismisses it in one line; that is
    cheaper than deciding per article which chapeaux are worth keeping."""
    body = provision_text(articles_dir / article_filename(article))
    lines = body.split("\n")
    body = "\n".join(lines[2:]) if len(lines) > 2 else body
    first, last = divisions[0], divisions[-1]
    head = re.search(rf"^\s*\({re.escape(first)}\)", body, re.M)
    if head is None:
        return divisions  # numbered paragraphs: nothing sits outside them
    out = list(divisions)
    if len(body[: head.start()].strip()) > _UNNUMBERED_MIN:
        out.insert(0, "chapeau")
    # The LAST occurrence of the last point's label: a point may be quoted before it is enacted.
    marks = list(re.finditer(rf"^\s*\({re.escape(last)}\)", body, re.M))
    if marks and len(body[marks[-1].end() :].partition("\n")[2].strip()) > _UNNUMBERED_MIN:
        out.append("closing")
    return tuple(out)


# Long enough to be a sentence rather than a stray label or a line break. Art. 16's chapeau is
# "Providers of high-risk AI systems shall:" at 40 characters and IS enacted text that binds; a
# shorter fragment is punctuation.
_UNNUMBERED_MIN = 35


def all_provisions(articles_dir: Path, annexes_dir: Path) -> list[Provision]:
    """Every addressable piece of the stored Act, articles then annexes, in the Act's own order.

    A document with no divisions contributes ONE provision addressing the whole of it, so the
    output is never silently short: an annex the parser cannot break down still has to be ruled on,
    it just gets ruled on whole and the ledger says so.

    AND A DOCUMENT WITH DIVISIONS THAT DO NOT COVER IT contributes an address for what they leave
    out. An article built as a chapeau plus lettered points has enacted text before the first point
    and sometimes after the last, and neither is a point — Art. 113's "It shall apply from 2 August
    2026" is the general application date every rule's `effective_date` is read from, and it sits
    outside (a) to (d). Without `chapeau` and `closing` those words have no address, so the
    denominator every coverage claim is measured against shrinks with no counter moving. That is the
    one failure this module cannot be allowed to have.
    """
    found: list[Provision] = []
    names = sorted(
        (p.stem.removeprefix("article-").lstrip("0") for p in articles_dir.glob("article-*.md")),
        key=_article_key,
    )
    for name in names:
        divisions = article_divisions(articles_dir, name)
        if divisions:
            found += [Provision("article", name, d) for d in _with_unnumbered(
                articles_dir, name, divisions
            )]
        else:
            found.append(Provision("article", name, None))

    stored = {p.stem.removeprefix("annex-") for p in annexes_dir.glob("annex-*.md")}
    for roman in [r for r in _ANNEX_ORDER if r in stored] + sorted(stored - set(_ANNEX_ORDER)):
        divisions = annex_divisions(annexes_dir, roman)
        if divisions:
            found += [Provision("annex", roman, d) for d in divisions]
        else:
            found.append(Provision("annex", roman, None))
    return found
