"""The enumerator: one address for every piece of the enacted text.

Everything the coverage machinery claims is a claim ABOUT this module's output, so a silent failure
here weakens every guarantee above it without failing anything. An annex the parser cannot break
down looks exactly like an annex with nothing in it, and a partition over an empty list passes.

So these tests check the enumerator against the FILES, never against counts written down here. Where
a count is unavoidable it is derived from the text on both sides, so neither side can go stale.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from aiact.config import get_settings
from aiact.policy_loader import article_filename, provision_text
from aiact.provisions import (
    _ANNEX_SECTION,
    Provision,
    _annex_body,
    all_provisions,
    annex_divisions,
    article_divisions,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = get_settings().act_version_date.isoformat()
ARTICLES_DIR = ROOT / "data" / "policy" / "articles" / VERSION
ANNEXES_DIR = ROOT / "data" / "policy" / "annexes" / VERSION

ARTICLE_FILES = sorted(ARTICLES_DIR.glob("article-*.md"))
ANNEX_NAMES = sorted(p.stem.removeprefix("annex-") for p in ANNEXES_DIR.glob("annex-*.md"))


def test_every_stored_document_yields_at_least_one_address():
    """Nothing may contribute zero provisions, because zero is indistinguishable from "not read".

    An annex whose shape the parser does not recognise would enumerate empty, every partition over
    it would pass vacuously, and the ledger would show it as handled. `all_provisions` therefore
    emits one whole-document address rather than nothing, and this pins that."""
    provisions = all_provisions(ARTICLES_DIR, ANNEXES_DIR)
    documents = {(p.kind, p.document) for p in provisions}
    expected = {("article", f.stem.removeprefix("article-").lstrip("0")) for f in ARTICLE_FILES}
    expected |= {("annex", name) for name in ANNEX_NAMES}
    assert documents == expected, "every stored file contributes at least one provision"


def test_no_piece_of_the_act_is_addressed_twice():
    """A duplicate address means two different provisions share one ruling.

    The way it happens is a parser that misses an article's real shape and falls through to a deeper
    one, scraping sub-points out of unrelated divisions: labels that repeat, identify nothing, and
    leave a ledger looking complete while it rules on fiction."""
    provisions = all_provisions(ARTICLES_DIR, ANNEXES_DIR)
    seen = [(p.kind, p.document, p.division) for p in provisions]
    duplicates = {a for a in seen if seen.count(a) > 1}
    assert not duplicates, f"the same address is emitted more than once: {sorted(duplicates)}"


@pytest.mark.parametrize("name", ANNEX_NAMES)
def test_annex_items_run_without_gaps(name):
    """Within a Section, numbered items must run 1, 2, 3 … with nothing skipped.

    This is what catches a DROPPED item, which is the failure that matters: the parser filters
    candidates that do not continue the sequence, so anything it wrongly rejects leaves a hole. A
    hole here is a provision with no address, and a provision with no address is one nothing can
    require a ruling for."""
    divisions = annex_divisions(ANNEXES_DIR, name)
    if not divisions:
        return  # Annex II numbers nothing; the annex is the unit, checked in the test above
    by_section: dict[str | None, list[int]] = {}
    for division in divisions:
        section, _, number = division.rpartition("/")
        if not number.isdigit():
            return  # a lettered annex, e.g. Annex XIII
        by_section.setdefault(section or None, []).append(int(number))
    for section, numbers in by_section.items():
        assert numbers == list(range(numbers[0], numbers[0] + len(numbers))), (
            f"Annex {name} section {section}: items {numbers} skip a number"
        )


@pytest.mark.parametrize("path", ARTICLE_FILES, ids=lambda p: p.stem)
def test_every_article_address_is_findable_in_its_own_text(path):
    """An address must name text that is really there — otherwise the ledger rules on fiction."""
    name = path.stem.removeprefix("article-").lstrip("0")
    body = path.read_text(encoding="utf-8")
    for division in article_divisions(ARTICLES_DIR, name):
        assert re.search(rf"^\s*\(?{re.escape(division)}[).]", body, re.M), (
            f"Art. {name}({division}) is not a label that appears in the article"
        )


def test_annex_i_is_counted_from_the_annex_and_not_from_memory():
    """Both sides of this comparison come from the Annex, and that is the point of it.

    Annex I decides which products reach Art. 6(1), so its length is load-bearing. A test asserting
    that length as a literal checks the code against a number and keeps passing when the Annex gains
    an instrument. Counting the OJ citations instead measures the same thing from the text, by a
    route independent of how the items are numbered or punctuated, so the two can only agree when
    the enumerator is right."""
    body = (ANNEXES_DIR / "annex-I.md").read_text(encoding="utf-8")
    # Every Annex I item ends with the Official Journal reference for the instrument it lists.
    # Counting those is independent of how the items themselves are numbered or punctuated.
    cited = body.count("OJ L")
    divisions = annex_divisions(ANNEXES_DIR, "I")
    assert len(divisions) == cited, (
        f"Annex I enumerates {len(divisions)} items but cites {cited} instruments"
    )


def test_an_address_renders_the_way_the_act_writes_it():
    """The address is the thing a reviewer matches against the Official Journal, so it has to read
    like a citation rather than like a key."""
    assert str(Provision("article", "6", "1a")) == "Art. 6(1a)"
    assert str(Provision("annex", "VIII", "A/1")) == "Annex VIII(A)(1)"
    assert str(Provision("annex", "II", None)) == "Annex II"


def test_no_enacted_text_sits_outside_every_address():
    """THE DENOMINATOR CANNOT SHRINK WITHOUT A COUNTER MOVING, which is the one failure this module
    is not allowed to have.

    Every number this project reports — the provision count, `unaccounted 0`, `owed 0` — is a claim
    ABOUT the enumerator's output, never about the Act directly. If the enumerator stops seeing part
    of the Act, the partition stays complete over what is left and says so in a reassuring number
    that nothing contradicts.

    An article built as a chapeau plus points is where the text escapes: the labels name the points
    and nothing names the words before the first or after the last. Art. 113's "It shall apply from
    2 August 2026" is the general application date most rules' timing entries carry, and
    it sits before point (a).

    So the attribution below is BUILT FROM THE LAYOUT OF THE FILES rather than from the enumerator:
    it walks the lines, opens an address on each label line, and gives a flush-left line that opens
    no label its own `chapeau` or `closing`. It shares no regex, no threshold and no filename rule
    with `_with_unnumbered`, which is the point — a check that re-runs the code it checks agrees
    with that code however either one is changed.

    An article with no labels at all is one provision with `division=None` covering its whole body,
    so those are skipped rather than read as one long chapeau.

    ARTICLES ONLY — the annexes are checked by `test_no_annex_text_sits_outside_every_address`,
    which cannot share this attribution: an annex runs its heading and its first item together on
    one line, so nothing here about flush-left lines applies to it."""
    articles = ARTICLES_DIR
    provisions = all_provisions(articles, ANNEXES_DIR)
    addressed = {(p.document, p.division) for p in provisions if p.kind == "article"}
    orphaned: list[str] = []
    for document in sorted({p.document for p in provisions if p.kind == "article"}):
        if (document, None) in addressed:
            continue
        body = provision_text(articles / article_filename(document)).split("\n")
        current: str | None = None
        labelled = False
        for line in body[2:]:
            if not line.strip():
                continue
            paragraph = re.match(r"(\d+[a-z]*)\.\s", line)
            point = re.match(r"\s+\(([^)]+)\)\s", line)
            if paragraph and not line[0].isspace():
                current, labelled = paragraph.group(1), True
            elif point and not labelled:
                # A point at the TOP level: this article is a chapeau plus points, not paragraphs.
                current, labelled = point.group(1), True
            elif not line[0].isspace() and not paragraph:
                current = "closing" if labelled else "chapeau"
            if len(line.strip()) > _SENTENCE and (document, current) not in addressed:
                orphaned.append(f"Art. {document}({current})")
    assert not orphaned, (
        f"enacted text with no address in the partition: {sorted(set(orphaned))}. Every coverage "
        f"count is a claim about this enumerator's output, so text it cannot see is text that "
        f"reads as covered."
    )


# This test's own floor, deliberately not the module's: a line longer than this carries a duty, and
# a shorter one is a label or a stray fragment. Sharing the module's constant would let one change
# move both sides of the comparison at once.
_SENTENCE = 35


def test_no_annex_text_sits_outside_every_address():
    """THE SAME INVARIANT AS ABOVE, on the half of the Act the article check cannot see.

    `annex_divisions` finds the numbered items and nothing else, so the sentence that introduces
    them has no address of its own. Annex IV's is "The technical documentation referred to in
    Article 11(1) shall contain at least the following information, AS APPLICABLE TO THE RELEVANT
    AI SYSTEM" — a floor and a limb narrowing it, governing all nine elements and part of none of
    them. Annex VIII's three Section headings are the only place the Act says which party submits
    which block.

    Derived from the files: for every annex item that OPENS a section — or the annex, where it has
    no sections — the text before it must be short enough to be a label, or an address must exist.

    THE MARKER IS FOUND BY A STRICTER TEST THAN THE MODULE'S, and it has to be, because a guard
    whose search matches everything the module's matches can never complain: it would find the
    first item at or before the module does, measure a prefix at or shorter than the module's, and
    stay silent wherever the module stayed silent. So this one asks what the module does not — what
    PRECEDES the marker. An item opens after a sentence ends or a heading does; a number that
    reads like an item marker in the middle of a sentence is a CROSS-REFERENCE, and "as set out in
    point 1." is the shape that fools a forward scan for `1.` into placing the annex's first item
    inside its own chapeau. Where that happens the module emits no address and the words it should
    have addressed leave the partition with `unaccounted` still reading zero, which is the one
    failure the count cannot show. This test is what sees it."""
    provisions = all_provisions(ARTICLES_DIR, ANNEXES_DIR)
    addressed = {(p.document, p.division) for p in provisions if p.kind == "annex"}
    orphaned: list[str] = []
    for annex in {p.document for p in provisions if p.kind == "annex"}:
        divisions = [d for d in annex_divisions(ANNEXES_DIR, annex) if not d.endswith("chapeau")]
        if not divisions:
            continue
        body = _annex_body(ANNEXES_DIR, annex)
        sections = {m.group(1): m.start() for m in _ANNEX_SECTION.finditer(body)}
        opened: set[str | None] = set()
        for division in divisions:
            section, _, item = division.rpartition("/")
            section = section or None
            if section in opened:
                continue
            opened.add(section)
            start = sections.get(section, 0) if section else 0
            marker = re.search(
                rf"(?:^|(?<=[.:;)—]\s)|(?<=\n)){re.escape(item)}[.)]", body[start:], re.M
            )
            if marker is None:
                continue
            head = body[start : start + marker.start()].strip()
            address = f"{section}/chapeau" if section else "chapeau"
            if len(head) > _SENTENCE and (annex, address) not in addressed:
                orphaned.append(f"Annex {annex}({address})")
    assert not orphaned, (
        f"annex text with no address in the partition: {sorted(orphaned)}. A chapeau states what "
        f"its whole list is qualified by, and text the enumerator cannot see is text that reads "
        f"as covered."
    )
