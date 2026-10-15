"""Resolve a cross-reference inside a provider's document.

The judge sees only the retrieved excerpts, so "the oversight measures are described in §7" is
ambiguous to it: §7 may exist and simply not have been retrieved, or may not exist at all. Those
imply opposite verdicts, so the lookup is done here and the answer given to the judge as a fact.

Three kinds of reference, told apart by whether the DOCUMENT defines them — never by the shape of
the label, since a provider may number their own annexes I, II, III:

    §8, Part C   internal, resolves against a heading
    Annex A      internal, but often a labelled item inside a section rather than a heading
    Annex IV     the Regulation's annex; the document is citing the law, not itself

Section keywords are learned from the document's own headings, so this works in any of the Act's
24 languages without a translation table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from aiact.retrieval.chunking import Chunk
from aiact.retrieval.store import DocumentIndex

# Forms that need no section vocabulary: the section sign and a markdown anchor.
_UNIVERSAL = re.compile(r"§\s*(?P<sec>\d+(?:\.\d+)*)|\]\(#(?P<anchor>[a-z0-9][a-z0-9-]*)\)")

# Used in addition to the vocabulary learned from the document, for files whose headings carry no
# keyword ("## 7. Human oversight") but whose prose says "Section 7". Not a full 24-language table:
# unverifiable entries would be guesses, and the learned vocabulary covers the rest.
_SEED_KEYWORDS = frozenset(
    {
        "section",
        "clause",
        "chapter",
        "part",
        "annex",
        "appendix",  # EN
        "abschnitt",
        "kapitel",
        "teil",
        "anhang",  # DE
        "chapitre",
        "partie",
        "annexe",  # FR
        "sección",
        "seccion",
        "capítulo",
        "capitulo",
        "parte",
        "anexo",  # ES
        "sezione",
        "capitolo",
        "allegato",  # IT
    }
)

# Bare numbers ("see 7.2 above") are never matched — they collide with version numbers, metric
# values and dates. `Art. 14` is likewise absent: it cites the Regulation, not the document.
_KEYWORD_REF = r"\b(?P<kw>{words})\s*\.?\s+(?P<label>\d+(?:\.\d+)*|[A-Z]+(?:\.\d+)*)\b"

# A heading that labels itself: "Abschnitt 3 — …", "Part C — …", "7. Human oversight".
_LABELLED_HEADING = re.compile(r"^(?P<kw>[^\W\d_]+)\s*\.?\s+(?P<label>\d+|[A-Z]+)\b")

# The Regulation's annexes. Consulted only for a reference the document does not define, to tell a
# citation of the law from a pointer to nothing. Never applied before resolution.
_ACT_ANNEXES = frozenset("I II III IV V VI VII VIII IX X XI XII XIII".split())


def _defines(body: str, token: str) -> bool:
    """Whether the document DEFINES `token`, as opposed to merely mentioning it.

    A definition starts its line and is followed by a separator — "- **Annex A** — model card". A
    citation sits mid-sentence ("drawn up per Annex IV of the Regulation") and does not count.
    """
    label = re.escape(token)
    return bool(re.search(rf"^[\s\-*>|]*\**\s*{label}\b\**\s*[—–\-:.]", body, re.M | re.I))


@dataclass(frozen=True)
class Reference:
    """One cross-reference found in a document, and what it points at."""

    token: str
    """As written: "§8", "Part C", "Annex A"."""

    section: str | None
    """Heading path it resolves to, or None when nothing in the document answers to it."""

    chunks: tuple[Chunk, ...] = ()
    """The referenced section's content, when it resolved to a section."""

    cites_the_act: bool = False
    """The document does not define this label and it names an annex of the Regulation, so the
    reference cites the law rather than pointing at a missing section."""

    @property
    def resolves(self) -> bool:
        return self.section is not None


def section_keywords(index: DocumentIndex) -> frozenset[str]:
    """The words this document uses to label its sections, read off its own headings.

    "Abschnitt 3 — Risikomanagement" teaches that `Abschnitt` labels a section here. Nothing is
    translated and no language is detected; the document is the authority on its own vocabulary.
    """
    learned = {
        match.group("kw").lower()
        for path in {c.heading_path for c in index.chunks.values()}
        for leaf in [path.split(" > ")[-1].strip()]
        if (match := _LABELLED_HEADING.match(leaf))
    }
    return frozenset(learned | _SEED_KEYWORDS)


def references_in(text: str, keywords: frozenset[str] | None = None) -> list[str]:
    """Internal cross-references in `text`, in order, deduplicated.

    `keywords` is the section vocabulary — pass the document's own (see `section_keywords`) so
    non-English files are read properly. Defaults to the seed list alone.
    """
    words = keywords if keywords is not None else _SEED_KEYWORDS
    pattern = re.compile(
        _UNIVERSAL.pattern
        + "|"
        + _KEYWORD_REF.format(words="|".join(sorted(map(re.escape, words), key=len, reverse=True))),
        re.IGNORECASE,
    )

    found: dict[str, None] = {}
    for match in pattern.finditer(text):
        if number := match.group("sec"):
            found.setdefault(f"§{number}", None)
        elif anchor := match.group("anchor"):
            found.setdefault(f"#{anchor}", None)
        elif label := match.group("label"):
            keyword = match.group("kw").lower()
            # Numeric labels normalise to `§N` so "§7", "Section 7" and "Abschnitt 7" are one
            # reference. Lettered ones keep the keyword: "Part C" and "Annex C" differ.
            if label[0].isdigit():
                found.setdefault(f"§{label}", None)
            else:
                found.setdefault(f"{keyword.title()} {label}", None)
    return list(found)


def _slug(text: str) -> str:
    """GitHub-style anchor slug, so `](#human-oversight)` can find "## Human oversight"."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _matches(heading: str, token: str) -> bool:
    """Whether a section heading answers to a reference token.

    Headings label themselves in two shapes and both must work: "7. Human oversight" (number first)
    and "Abschnitt 7 — Aufsicht" (keyword first, as most languages write it).
    """
    leaf = heading.split(" > ")[-1].strip()
    if token.startswith("#"):
        return _slug(leaf) == token[1:]

    labelled = _LABELLED_HEADING.match(leaf)
    if token.startswith("§"):
        number = token[1:].strip()
        # The boundary keeps "8" from matching "80. ...".
        if re.match(rf"{re.escape(number)}[.\s]", leaf):
            return True
        return bool(labelled and labelled.group("label") == number)

    keyword, _, label = token.partition(" ")
    return bool(
        labelled
        and labelled.group("kw").lower() == keyword.lower()
        and labelled.group("label").lower() == label.lower()
    )


def resolve(index: DocumentIndex, token: str, document: str = "") -> Reference:
    """Resolve one cross-reference against a document.

    Headings first, then a definition in the body (an annex may be a labelled item rather than a
    heading). Only when both fail is the reference unanswered.
    """
    for chunk in index.chunks.values():
        if chunk.heading_path and _matches(chunk.heading_path, token):
            section = chunk.heading_path
            return Reference(
                token=token,
                section=section,
                chunks=tuple(c for c in index.chunks.values() if c.heading_path == section),
            )

    body = document or "\n\n".join(c.body for c in index.chunks.values())
    if not token.startswith("§") and _defines(body, token):
        return Reference(token=token, section=f"(defined in the text: {token})")

    # Undefined by the document: only now does the numeral shape decide law-citation vs dangling.
    kind, _, label = token.partition(" ")
    if kind == "Annex" and label in _ACT_ANNEXES:
        return Reference(token=token, section=None, cites_the_act=True)

    return Reference(token=token, section=None)


def resolve_all(
    index: DocumentIndex, text: str, document: str = "", limit: int = 3
) -> list[Reference]:
    """Every internal cross-reference in `text`, resolved, up to `limit`.

    Capped because resolved sections go into the prompt; citing six of them would pull most of the
    document back in.
    """
    resolved = (
        resolve(index, token, document) for token in references_in(text, section_keywords(index))
    )
    # Dropped here rather than earlier: resolution is what proves they are not the document's own.
    return [ref for ref in resolved if not ref.cites_the_act][:limit]
