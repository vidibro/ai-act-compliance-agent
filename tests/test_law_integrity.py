"""The enacted-law store is tamper-evident.

Every article and annex file carries the sha256 of its body, written by scripts/fetch_articles.py.
That text is what the model is told is "the enacted text you must answer against", and what every
verdict cites — so a corrupted or hand-edited file is the worst silent failure in the project: the
model would reason against wording that was never enacted, and the citation would look perfect.

These tests pin that the check exists, covers the right bytes, and fires on tampering. The parallel
guarantee for non-binding Commission guidance lives in test_guidance.py; SECURITY.md documents both.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from aiact.graph.classify import _provision_text
from aiact.policy_loader import _read_article, verify_integrity

ROOT = Path(__file__).resolve().parents[1]
ARTICLES = ROOT / "data" / "policy" / "articles" / "2024-07-12"
ANNEXES = ROOT / "data" / "policy" / "annexes" / "2024-07-12"
_FRONT_SHA = re.compile(r"^sha256:\s*([0-9a-f]{64})\s*$", re.M)


def _stored_files() -> list[Path]:
    return sorted(ARTICLES.glob("*.md")) + sorted(ANNEXES.glob("*.md"))


def test_every_stored_provision_matches_its_hash():
    """The whole store, verified independently of the loader — if this fails, either a file was
    edited by hand or the fetch script's hashing span drifted from the loader's."""
    files = _stored_files()
    assert len(files) > 100, "expected the full Act store (113 articles + annexes)"
    for path in files:
        raw = path.read_text(encoding="utf-8")
        declared = _FRONT_SHA.search(raw)
        assert declared, f"{path.name} has no sha256 in its front matter"
        body = raw.partition("\n---\n\n")[2]
        actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert actual == declared.group(1), f"{path.name} does not match its stored sha256"


def test_a_tampered_article_is_refused(tmp_path):
    """The point of the whole exercise: altering the law text must raise, not classify."""
    original = (ARTICLES / "article-006.md").read_text(encoding="utf-8")
    tampered = original.replace("high-risk", "low-risk")
    assert tampered != original, "fixture must actually change the provision text"

    store = tmp_path / "2024-07-12"
    store.mkdir()
    (store / "article-006.md").write_text(tampered, encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its stored sha256"):
        _read_article(store, 6)


def test_a_tampered_annex_is_refused_on_the_prompt_path(tmp_path):
    """`_provision_text` feeds the model directly, so it is the highest-value check — Annex III IS
    the list of high-risk areas, and a doctored entry would be read as enacted law."""
    original = (ANNEXES / "annex-III.md").read_text(encoding="utf-8")
    tampered = original.replace("Employment", "Entertainment")
    assert tampered != original

    path = tmp_path / "annex-III.md"
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its stored sha256"):
        _provision_text(path)


def test_a_file_with_no_hash_is_refused(tmp_path):
    """Unverifiable text is not usable — an attacker (or a bad merge) must not be able to bypass the
    check simply by deleting the line that enables it."""
    original = (ARTICLES / "article-006.md").read_text(encoding="utf-8")
    stripped = _FRONT_SHA.sub("", original)

    store = tmp_path / "2024-07-12"
    store.mkdir()
    (store / "article-006.md").write_text(stripped, encoding="utf-8")

    with pytest.raises(ValueError, match="no sha256"):
        _read_article(store, 6)


def test_a_whitespace_only_edit_is_still_caught(tmp_path):
    """Hashing is byte-exact, so cosmetic edits fail too. That is deliberate: the store is
    machine-generated from the Official Journal and reproducible with one command, so ANY local
    divergence means the file is no longer the fetched text."""
    original = (ARTICLES / "article-006.md").read_text(encoding="utf-8")

    store = tmp_path / "2024-07-12"
    store.mkdir()
    (store / "article-006.md").write_text(original + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its stored sha256"):
        _read_article(store, 6)


def test_the_untampered_store_still_loads(tmp_path):
    """Guard against a check so strict nothing passes it — the real files must verify cleanly."""
    provisions, front = _read_article(ARTICLES, 6)
    assert "high-risk" in provisions
    assert front["sha256"]
    assert _provision_text(ANNEXES / "annex-III.md").startswith("ANNEX III")


def test_verify_integrity_accepts_a_matching_body():
    body = "some text\n"
    front = {"sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}
    verify_integrity(Path("x.md"), "---\n---\n\n" + body, front, body)  # must not raise
