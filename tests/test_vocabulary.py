"""THE CLASSIFICATION SIDE OF THE PARTITION: every case the Act enumerates has a name in the code.

`tests/test_coverage.py` accounts for every provision that creates a DUTY. This file does the same
for the ones that decide what a system IS — the Annex I instruments, the Annex III areas, the
Art. 5 prohibitions, the Art. 50 duties, the Art. 2 exclusions. Those live in enums, and an enum is
a hand-written list: nothing about writing one makes it agree with the Annex it stands for.

So each test here derives the cases from the stored text and requires the enum to cover them, or a
declaration below to say why a case is deliberately absent. No test in this file may assert a count.

WHAT THIS DOES NOT CHECK is whether the cascade ASKS about a member it holds. An enum can be
complete while a node ignores half of it — Art. 6(1c) is in the stored text, is supplied to the
model as context, and no node applies it. That is a separate guarantee and it is not built yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.config import get_settings
from aiact.provisions import (
    annex_divisions,
    annex_instruments,
    article_divisions,
    points_within,
)
from aiact.schemas.enums import (
    AnnexIIIArea,
    AnnexIProduct,
    ProhibitedPractice,
    ScopeExclusion,
    TransparencyDuty,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = get_settings().act_version_date.isoformat()
ARTICLES_DIR = ROOT / "data" / "policy" / "articles" / VERSION
ANNEXES_DIR = ROOT / "data" / "policy" / "annexes" / VERSION


def _assert_covers(cases: tuple[str, ...], claimed: set[str], declared: dict[str, str], what: str):
    """Every case the text enumerates is claimed by a member, or declared with a reason."""
    missing = [c for c in cases if c not in claimed and c not in declared]
    assert not missing, (
        f"{what}: the text enumerates {missing} and nothing in the code names them. Add a member, "
        f"or declare why the case is absent."
    )
    invented = claimed - set(cases)
    assert not invented, f"{what}: the code names {sorted(invented)}, which the text does not list."
    stale = set(declared) - set(cases)
    assert not stale, f"{what}: declared absent but no longer in the text: {sorted(stale)}"
    for case, reason in declared.items():
        assert len(reason.strip()) > 15, f"{what}: {case} is declared absent without a reason"


# --- Annex I: which product legislation reaches Art. 6(1) ----------------------------------------
ANNEX_I_NOT_MODELLED: dict[str, str] = {}
"""Empty, and it should stay that way: every Annex I instrument can make a system high-risk."""


def test_every_annex_i_instrument_has_a_name_in_the_code():
    """Annex I decides which regulated products reach Art. 6(1), so a missing instrument is a system
    the cascade cannot classify at all — it has no value to answer with."""
    _assert_covers(
        annex_divisions(ANNEXES_DIR, "I"),
        {p.annex_item for p in AnnexIProduct},
        ANNEX_I_NOT_MODELLED,
        "Annex I",
    )


# --- Annex III: the high-risk areas --------------------------------------------------------------
ANNEX_III_NOT_MODELLED: dict[str, str] = {}
"""Empty. Art. 7 lets the Commission add areas, which is exactly why this is derived."""


def test_every_annex_iii_area_has_a_name_in_the_code():
    _assert_covers(
        annex_divisions(ANNEXES_DIR, "III"),
        {a.annex_item for a in AnnexIIIArea},
        ANNEX_III_NOT_MODELLED,
        "Annex III",
    )


# --- Art. 5(1): the prohibited practices ---------------------------------------------------------
PROHIBITED_NOT_MODELLED: dict[str, str] = {}
"""Empty. A practice the Act bans and the cascade cannot name would be reported as some lesser
tier, which is the worst answer this tool can give."""


def test_every_prohibited_practice_has_a_name_in_the_code():
    """The points of Art. 5(1), not the paragraphs of Art. 5. The paragraph is a chapeau and the
    bans are its points, so 5(1a) and 5(1b) — which qualify two of them — are not themselves
    practices and must not be counted as missing ones."""
    _assert_covers(
        points_within(ARTICLES_DIR, "5", "1"),
        {p.point for p in ProhibitedPractice},
        PROHIBITED_NOT_MODELLED,
        "Art. 5(1)",
    )


# --- Art. 50: the transparency duties ------------------------------------------------------------
TRANSPARENCY_NOT_A_DUTY: dict[str, str] = {
    "5": "The manner and timing of the 50(1)-(4) information. Qualifies all four duties rather "
    "than adding a fifth; owed a rule, see articles_awaiting_rules.",
    "6": "Art. 50(1)-(4) do not affect Chapter III. A saving clause, and modelled structurally: "
    "an Art. 50 duty is added to a tier's obligations rather than replacing them.",
    "7": "Commission duty to facilitate codes of practice on marking and labelling. Institutional.",
}


def test_every_art_50_paragraph_that_creates_a_duty_has_a_name_in_the_code():
    """Art. 50 cuts across the risk tiers in both directions, so a duty with no name is one no
    system can be found to owe — whatever tier it lands in."""
    _assert_covers(
        article_divisions(ARTICLES_DIR, "50"),
        {str(d.paragraph) for d in TransparencyDuty},
        TRANSPARENCY_NOT_A_DUTY,
        "Art. 50",
    )


# --- Art. 2: the scope exclusions ----------------------------------------------------------------
SCOPE_NOT_AN_EXCLUSION: dict[str, str] = {
    "1": "Who the Regulation applies to, points (a)-(g). The positive limb, answered by the "
    "`territorial` node into TerritorialLink rather than into an exclusion.",
    "2": "A LIMIT on what a Section B Annex I system owes, not an exclusion. Carried by "
    "AnnexIProduct.chapter_iii_applies and the Section B branch of select_rules.",
    "5": "Preserves the Digital Services Act's liability rules. A saving clause.",
    "7": "Union data protection law continues to apply. A saving clause.",
    "9": "Consumer protection and product safety law unaffected. A saving clause.",
    "11": "Member States may keep law more favourable to workers. A power that can only add to "
    "what a deployer owes, never subtract.",
    "13": "Arts. 9-15 and 17-25 MAY BE LIMITED for an Art. 6(1) system. Not operative: it works "
    "through delegated acts the Commission must adopt by 2 August 2027.",
}


def test_every_art_2_paragraph_that_withholds_the_regulation_has_a_name_in_the_code():
    """An exclusion the cascade cannot name is a system it will govern anyway — over-inclusive, so
    not the dangerous direction, but it means telling someone they owe duties the legislator
    expressly withheld."""
    _assert_covers(
        article_divisions(ARTICLES_DIR, "2"),
        {str(e.paragraph) for e in ScopeExclusion},
        SCOPE_NOT_AN_EXCLUSION,
        "Art. 2",
    )


@pytest.mark.parametrize(
    "declared",
    [ANNEX_I_NOT_MODELLED, ANNEX_III_NOT_MODELLED, PROHIBITED_NOT_MODELLED],
    ids=["annex_i", "annex_iii", "prohibited"],
)
def test_the_lists_that_must_stay_complete_are_complete(declared):
    """Three vocabularies admit no absences, and saying so here is what stops one being added
    quietly with a plausible reason. An unmodelled Annex I instrument, Annex III area or Art. 5
    practice each ends in a system being classified into a tier below the one it belongs to."""
    assert declared == {}, (
        f"a case was declared absent from a list that must stay exhaustive: {declared}"
    )


def test_every_annex_i_option_names_the_instrument_the_annex_puts_at_that_item():
    """THE ANSWER OPTIONS THE MODEL PICKS FROM, checked against the Annex rather than against
    whoever typed them.

    `_answer_instructions` renders each AnnexIProduct as `<value> = <legislation>`, and the
    legislation string is what separates two options whose identifiers do not: Annex I lists
    machinery twice, as Directive 2006/42/EC at A/1 and Regulation (EU) 2023/1230 at B/21. The two
    sit in different Sections, so Art. 2(2) withholds Chapter III from one and not the other, and
    `machinery_regulation` returns an EMPTY obligation set for every role. B/14 and B/15 are a
    second adjacent pair — two vehicle Regulations whose numbers differ by one digit.

    The member-to-item map is checked above; this checks the prose beside it, which is the half a
    reader believes and no address comparison can see."""
    instruments = annex_instruments(ANNEXES_DIR, "I")
    assert instruments, "no instrument parsed out of Annex I — re-derive this test"

    wrong = {
        product.annex_item: (instruments[product.annex_item], product.legislation)
        for product in AnnexIProduct
        if product.annex_item in instruments
        and instruments[product.annex_item] not in product.legislation
    }
    assert not wrong, (
        f"AnnexIProduct.legislation naming an act the Annex does not put at that item: "
        f"{ {k: f'annex says {v[0]}, code says {v[1]}' for k, v in wrong.items()} }"
    )

    unmatched = {p.annex_item for p in AnnexIProduct} - set(instruments)
    assert not unmatched, f"items with no instrument derived from the Annex: {sorted(unmatched)}"
