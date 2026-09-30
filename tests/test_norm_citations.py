from __future__ import annotations

import pytest

from aiact.norm_citations import cited_provisions, unlinked_citations
from aiact.norm_loader import load_normative_coverage


def _cited(text: str) -> list[tuple[str, str, str | None, tuple[str, ...]]]:
    return [(c.kind, c.document, c.paragraph, c.points) for c in cited_provisions(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Article 10(2), points (f) and (g)", [("article", "10", "2", ("f", "g"))]),
        ("Article 99(3) to (5)", [("article", "99", p, ()) for p in ("3", "4", "5")]),
        ("Articles 9 to 11", [("article", n, None, ()) for n in ("9", "10", "11")]),
        (
            "Article 49(4) and Article 60(4)",
            [("article", "49", "4", ()), ("article", "60", "4", ())],
        ),
        ("points 2 to 4 of Annex III", [("annex", "III", None, ("2", "3", "4"))]),
        ("Annex III, point 1(a)", [("annex", "III", None, ("1A",))]),
        ("listed in Section A of Annex I", [("annex", "I", "A", ())]),
        ("Annex I, Section B", [("annex", "I", "B", ())]),
        ("point 3 of Section A of Annex VIII", [("annex", "VIII", "A", ("3",))]),
    ],
)
def test_citations_of_this_regulation_are_read(text: str, expected: list[object]) -> None:
    assert _cited(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Article 18 of Regulation (EU) 2019/1020",
        "Articles 101 and 102 TFEU",
        "Article 2 of the Annex to Recommendation 2003/361/EC",
        "Annex I to Regulation (EU) 2019/1020",
    ],
)
def test_citations_of_other_instruments_are_skipped(text: str) -> None:
    assert cited_provisions(text) == []


def test_every_cited_provision_is_carried_by_a_relation() -> None:
    """A norm that cites another article or annex relies on it; the relation must say so."""
    unlinked = unlinked_citations(load_normative_coverage())

    assert [(u.norm_id, u.citation) for u in unlinked] == [], (
        "run scripts/link_norm_citations.py, then rebuild the normative coverage"
    )
