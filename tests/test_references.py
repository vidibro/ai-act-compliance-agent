"""Cross-reference resolution — deterministic, so it is tested rather than evaluated.

Most tests here guard a way of getting it wrong that produces a false finding against COMPLIANT
documentation, which is the failure mode that makes a compliance tool unusable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.retrieval.store import DocumentIndex
from aiact.tools.references import references_in, resolve, resolve_all

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "golden_set" / "cases" / "pristine__untouched.md"
REMOVED = ROOT / "data" / "golden_set" / "cases" / "AIA-RULE-HR-A14__removed.md"
HELDOUT = ROOT / "data" / "golden_set" / "cases-heldout" / "pristine__untouched.md"

ROMAN_ANNEXES = """\
# Provider File

## Part A — Oversight
Panels review each case. Details in Annex II. Drawn up per Annex IV of the Regulation.

## Annex I — Model card
Feature list and training config.

## Annex II — Oversight procedure
Panel composition, escalation path, stop control.
"""


def _index(text: str) -> DocumentIndex:
    return DocumentIndex.build(text)


# --- the signal the judge actually needs -------------------------------------------------------
def test_a_deleted_section_is_reported_as_missing():
    """Art. 14's section is gone from this case, but the cross-reference to it survives elsewhere
    ("described in §7"). Unresolved, the judge reads that pointer as evidence the content exists."""
    text = REMOVED.read_text(encoding="utf-8")
    assert not resolve(_index(text), "§7", text).resolves


def test_a_present_section_resolves_with_its_content():
    text = DEV.read_text(encoding="utf-8")
    ref = resolve(_index(text), "§7", text)
    assert ref.resolves
    assert "Human oversight" in (ref.section or "")
    assert ref.chunks, "a resolved section must carry its content, so the judge can check it"


def test_lettered_parts_resolve_on_the_heldout_layout():
    """The two reference documents number their sections differently, so a resolver keyed to `§N`
    alone would do nothing on half the corpus."""
    text = HELDOUT.read_text(encoding="utf-8")
    assert resolve(_index(text), "Part C", text).resolves
    assert resolve(_index(text), "Part Z", text).resolves is False


# --- the three ways to invent a false finding ---------------------------------------------------
def test_an_annex_defined_as_a_list_item_is_not_dangling():
    """Annexes are often labelled items inside one "## Annexes" section rather than headings."""
    text = DEV.read_text(encoding="utf-8")
    for token in ("Annex A", "Annex D"):
        assert resolve(_index(text), token, text).resolves, f"{token} is defined in this document"


def test_a_citation_of_the_regulations_annex_is_not_an_internal_pointer():
    """A file citing "Annex IV" names the law it was drawn up against, not a section of itself."""
    text = DEV.read_text(encoding="utf-8")
    ref = resolve(_index(text), "Annex IV", text)
    assert not ref.resolves
    assert ref.cites_the_act, "must be reported as a citation, not as a dangling pointer"
    assert "Annex IV" not in [r.token for r in resolve_all(_index(text), text, text)]


def test_a_provider_may_number_their_own_annexes_with_roman_numerals():
    """A provider may number their own annexes I, II, III. Resolution therefore comes first, and
    the numeral shape only breaks a tie the document itself left open."""
    index = _index(ROMAN_ANNEXES)
    for token in ("Annex I", "Annex II"):
        ref = resolve(index, token, ROMAN_ANNEXES)
        assert ref.resolves, f"{token} is a section of THIS document"
        assert not ref.cites_the_act

    # …while the one it merely cites is still recognised as the law's.
    cited = resolve(index, "Annex IV", ROMAN_ANNEXES)
    assert not cited.resolves and cited.cites_the_act


def test_a_mention_is_not_a_definition():
    """The text fallback exists for annexes defined as list items, so it must not fire on a
    mid-sentence citation like "drawn up per Annex IV of the Regulation"."""
    index = _index(ROMAN_ANNEXES)
    assert "Annex IV of the Regulation" in ROMAN_ANNEXES
    assert not resolve(index, "Annex IV", ROMAN_ANNEXES).resolves


# --- extraction ---------------------------------------------------------------------------------
def test_references_are_extracted_in_order_without_duplicates():
    tokens = references_in("See §8 and §8 again, plus Part C, then Annex A.")
    assert tokens == ["§8", "Part C", "Annex A"]


@pytest.mark.parametrize("text", ["nothing to see", "", "the sections are numbered"])
def test_text_without_references_yields_none(text):
    """Note "section 8" is NOT here: it is a recognised reference, not prose."""
    assert references_in(text) == []


def test_resolution_is_capped():
    """Resolved sections go into the prompt; citing six would pull the document back in."""
    text = DEV.read_text(encoding="utf-8")
    assert len(resolve_all(_index(text), text, text, limit=2)) <= 2


# --- reference dialects -------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("described in §7", "§7"),
        ("in Section 7", "§7"),
        ("see section 7 below", "§7"),
        ("see Chapter 7", "§7"),
        ("cf. clause 7.2", "§7.2"),
        ("detailed in [Human oversight](#human-oversight)", "#human-oversight"),
        ("cf. Part C", "Part C"),
    ],
)
def test_the_common_reference_dialects_are_recognised(text, expected):
    """`§8` is one dialect among several; a document written any other ordinary way must still have
    its cross-references found."""
    assert references_in(text) == [expected]


def test_the_same_section_in_two_dialects_is_one_reference():
    assert references_in("see §7, as Section 7 explains") == ["§7"]


@pytest.mark.parametrize(
    "text",
    [
        "per Art. 14",
        "under Article 14",
        "accuracy of 7.2 percent",
        "version 4.2.1",
        "see 7.2 above",
    ],
)
def test_things_that_are_not_internal_references_are_not_matched(text):
    """`Art. 14` cites the Regulation, not the document. A bare number is not a reference at all —
    it collides with version numbers, metric values and dates."""
    assert references_in(text) == []


def test_a_markdown_anchor_resolves_to_its_heading():
    text = DEV.read_text(encoding="utf-8")
    assert resolve(_index(text), "#7-human-oversight", text).resolves


# --- 24 languages, no translation table --------------------------------------------------------
GERMAN = """\
# PathFinder Technische Dokumentation

## Abschnitt 1 — Allgemeine Beschreibung
Das System bewertet Bewerber.

## Abschnitt 3 — Menschliche Aufsicht
Jede Empfehlung wird geprueft. Details siehe Abschnitt 1 und Abschnitt 9.

## Anhang A — Modellkarte
Merkmalsliste.
"""

POLISH = """\
# Dokumentacja

## Rozdział 1 — Opis
Opis systemu.

## Rozdział 2 — Nadzór
Szczegóły w Rozdział 5. Zobacz Załącznik A.

## Załącznik A — Karta modelu
Lista cech.
"""


@pytest.mark.parametrize(
    ("document", "present", "missing"),
    [(GERMAN, "§1", "§9"), (POLISH, "§1", "§5")],
    ids=["german", "polish"],
)
def test_references_resolve_in_any_language(document, present, missing):
    """The Act is a 24-language instrument. The section vocabulary is read off the document's own
    headings, so this works for languages nobody listed and for a provider's own scheme."""
    index = _index(document)
    assert resolve(index, present, document).resolves
    assert not resolve(index, missing, document).resolves


def test_keyword_first_headings_resolve_numeric_references():
    """English numbers its headings "7. Human oversight"; most languages put the keyword first,
    "Abschnitt 7 — Aufsicht". A reference resolving to nothing is reported as a missing section, so
    missing this shape manufactures gaps against good documentation."""
    index = _index(GERMAN)
    assert resolve(index, "§3", GERMAN).section is not None
    assert "Menschliche Aufsicht" in (resolve(index, "§3", GERMAN).section or "")


def test_the_vocabulary_is_learned_from_the_documents_own_headings():
    from aiact.tools.references import section_keywords

    assert "rozdział" in section_keywords(_index(POLISH))
    assert "załącznik" in section_keywords(_index(POLISH))


def test_a_lettered_annex_keeps_its_keyword():
    """"Part C" and "Annex C" are different sections; normalising both to "§C" would merge them."""
    assert references_in("see Part C and Annex C") == ["Part C", "Annex C"]
