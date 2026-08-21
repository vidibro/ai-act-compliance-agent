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
from aiact.provisions import Provision, all_provisions, annex_divisions, article_divisions

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
