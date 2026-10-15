"""A Formex zip may only overwrite the version it actually is."""

from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fetch_articles", ROOT / "scripts/fetch_articles.py")
fetch = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fetch)

CONSOLIDATED = fetch.VERSIONS["2026-07-27"]
OFFICIAL_JOURNAL = fetch.VERSIONS["2024-07-12"]


def _article(number: str) -> str:
    return (
        f"<ARTICLE><TI.ART>Article {number}</TI.ART><STI.ART>Test</STI.ART>"
        f"<ALINEA><P>Body of Article {number}.</P></ALINEA></ARTICLE>"
    )


def _zip(articles: list[str], *, consolidated: bool, annexes: tuple[str, ...] = ("I",)) -> bytes:
    annex_tag = "CONS.ANNEX" if consolidated else "ANNEX"
    body = (
        "<ACT><ENACTING.TERMS>"
        + "".join(_article(n) for n in articles)
        + "</ENACTING.TERMS>"
        + "".join(
            f"<{annex_tag}><TITLE><TI>ANNEX {roman}</TI><STI>Test</STI></TITLE>"
            f"<CONTENTS><P>Annex body.</P></CONTENTS></{annex_tag}>"
            for roman in annexes
        )
        + "</ACT>"
    )
    buffer = io.BytesIO()
    name = "CL_02024R1689EN.xml" if consolidated else "L_202401689EN.000101.fmx.xml"
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(name, body)
    return buffer.getvalue()


@pytest.fixture
def store(tmp_path: Path) -> tuple[Path, Path]:
    articles, annexes = tmp_path / "articles", tmp_path / "annexes"
    articles.mkdir()
    annexes.mkdir()
    for name in ("article-004.md", "article-004a.md", "article-060a.md"):
        (articles / name).write_text("stub", encoding="utf-8")
    (annexes / "annex-I.md").write_text("stub", encoding="utf-8")
    (annexes / "annex-XIV.md").write_text("stub", encoding="utf-8")
    return articles, annexes


def test_layout_mismatch_is_refused(store):
    """The real failure that prompted this: an OJ zip offered for a consolidated version."""
    articles, annexes = store
    with pytest.raises(SystemExit) as excinfo:
        fetch.verify_manifestation(
            _zip(["4", "4a", "60a"], consolidated=False),
            CONSOLIDATED,
            "2026-07-27",
            articles,
            annexes,
        )
    message = str(excinfo.value)
    assert "official-journal" in message and "consolidated" in message
    assert CONSOLIDATED.zip_url in message


def test_a_zip_missing_stored_articles_is_refused(store):
    """Right layout, wrong content: the amending act's lettered articles are absent."""
    articles, annexes = store
    with pytest.raises(SystemExit) as excinfo:
        fetch.verify_manifestation(
            _zip(["4"], consolidated=True, annexes=("I", "XIV")),
            CONSOLIDATED,
            "2026-07-27",
            articles,
            annexes,
        )
    message = str(excinfo.value)
    assert "4a" in message and "60a" in message
    assert "not 02024R1689-20260727" in message


def test_a_zip_missing_stored_annexes_is_refused(store):
    articles, annexes = store
    with pytest.raises(SystemExit) as excinfo:
        fetch.verify_manifestation(
            _zip(["4", "4a", "60a"], consolidated=True, annexes=("I",)),
            CONSOLIDATED,
            "2026-07-27",
            articles,
            annexes,
        )
    assert "XIV" in str(excinfo.value)


def test_the_matching_manifestation_is_accepted(store):
    """A superset is fine — the guard blocks regression, it does not pin an exact article list."""
    articles, annexes = store
    fetch.verify_manifestation(
        _zip(["4", "4a", "60a", "75a"], consolidated=True, annexes=("I", "XIV")),
        CONSOLIDATED,
        "2026-07-27",
        articles,
        annexes,
    )


def test_an_empty_store_accepts_a_first_fetch(tmp_path: Path):
    """Nothing stored yet, so there is nothing to regress against."""
    articles, annexes = tmp_path / "articles", tmp_path / "annexes"
    fetch.verify_manifestation(
        _zip(["1"], consolidated=False),
        OFFICIAL_JOURNAL,
        "2024-07-12",
        articles,
        annexes,
    )
