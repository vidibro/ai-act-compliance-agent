"""Every paragraph of every stored guidance document has a decision, read from the pinned PDF.

The stored `paragraphs.yaml` is a machine extraction, so it is regenerated here and must match byte
for byte; the rest of the tests break the store on purpose and require the check to say so.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
import yaml

from aiact.guidance_coverage import (
    PARAGRAPHS_FILE,
    guidance_coverage_errors,
    parse_ranges,
    render_paragraphs,
)
from aiact.norm_loader import load_normative_coverage

ROOT = Path(__file__).resolve().parents[1] / "data" / "policy" / "guidance"
DOCUMENTS = ("C-2025-5052", "C-2026-5054")


@pytest.fixture(scope="module")
def consumed() -> set[str]:
    bundle = load_normative_coverage()
    return {ref for link in bundle.norm_inventory.interpretations for ref in link.snippet_refs}


@pytest.fixture
def store(tmp_path) -> Path:
    copy = tmp_path / "guidance"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("*.pdf"))
    return copy


def _paragraphs(doc: str) -> list[dict]:
    return yaml.safe_load((ROOT / doc / PARAGRAPHS_FILE).read_text(encoding="utf-8"))["paragraphs"]


@pytest.mark.parametrize("doc", DOCUMENTS)
def test_the_stored_paragraphs_are_what_the_pdf_yields(doc):
    """Regenerated from the hash-pinned PDF, the extraction must not differ by a byte."""
    stored = (ROOT / doc / PARAGRAPHS_FILE).read_text(encoding="utf-8")
    assert render_paragraphs(ROOT / doc) == stored, (
        f"{doc}/{PARAGRAPHS_FILE} is stale: run scripts/extract_guidance_paragraphs.py"
    )


@pytest.mark.parametrize(
    ("doc", "count", "disagreeing"),
    [
        ("C-2025-5052", 433, [9]),
        ("C-2026-5054", 155, [6]),
    ],
)
def test_the_engines_disagree_only_on_the_overview_tables(doc, count, disagreeing):
    """Both documents open with a table summarising the provisions, whose cells the two engines
    read in different orders. Everything else they read identically."""
    paragraphs = _paragraphs(doc)
    assert [item["number"] for item in paragraphs] == list(range(1, count + 1))
    assert [item["number"] for item in paragraphs if not item["engines_agree"]] == disagreeing


def test_the_store_has_no_coverage_defect(consumed):
    assert guidance_coverage_errors(ROOT, consumed) == []


@pytest.mark.parametrize(("doc", "awaiting"), [("C-2025-5052", 194), ("C-2026-5054", 0)])
def test_paragraphs_awaiting_review_only_shrink(doc, awaiting):
    """Declared debt. Reading a paragraph moves it into `decisions`; lower the number with it."""
    coverage = yaml.safe_load((ROOT / doc / "coverage.yaml").read_text(encoding="utf-8"))
    assert len(parse_ranges(coverage["awaiting_review"])) == awaiting


def _edit_coverage(store: Path, doc: str, edit) -> None:
    path = store / doc / "coverage.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_a_paragraph_nobody_decided_fails(store, consumed):
    _edit_coverage(store, "C-2025-5052", lambda data: data["decisions"].pop(1))

    assert "C-2025-5052 ¶1 has no decision and is not listed as awaiting review" in (
        guidance_coverage_errors(store, consumed)
    )


def test_a_quote_that_drifted_from_the_pdf_fails(store, consumed):
    """The snippet's own sha256 is updated with the edit, so only the PDF text catches it."""
    path = store / "C-2026-5054" / "snippets" / "substantive-human-review.md"
    raw = path.read_text(encoding="utf-8")
    front, _, body = raw.partition("\n---\n")
    body = body.replace("cannot fulfil", "can fulfil")
    old_sha = hashlib.sha256(body.replace("can fulfil", "cannot fulfil").lstrip("\n").encode())
    new_sha = hashlib.sha256(body.lstrip("\n").encode())
    path.write_text(
        front.replace(old_sha.hexdigest(), new_sha.hexdigest()) + "\n---\n" + body,
        encoding="utf-8",
    )

    errors = guidance_coverage_errors(store, consumed)

    assert any(
        e.startswith("C-2026-5054/substantive-human-review quote does not match") for e in errors
    )


def test_a_decision_on_a_paragraph_the_engines_read_differently_needs_a_visual_check(
    store, consumed
):
    """The overview table's cells come out in different orders, so its decision stands only on a
    person having compared the page."""
    assert not any("¶9" in e for e in guidance_coverage_errors(store, consumed))

    _edit_coverage(store, "C-2025-5052", lambda data: data.pop("visually_checked"))

    assert (
        "C-2025-5052 ¶9 is decided, but the two engines read it differently and no one has "
        "checked it against the page"
    ) in guidance_coverage_errors(store, consumed)


def test_a_followed_passage_must_be_handed_to_something(store, consumed):
    """A `used` paragraph whose snippet no question or rule receives is an interpretation on paper
    only; the reverse is a `not_followed` one that quietly steers an answer."""
    errors = guidance_coverage_errors(
        store, consumed - {"C-2026-5054/agent-assist-is-not-direct-interaction"}
    )
    assert any(e.startswith("C-2026-5054 ¶30 is quoted by") for e in errors)

    errors = guidance_coverage_errors(store, consumed | {"C-2026-5054/industrial-b2b-no-marking"})
    assert any(e.startswith("C-2026-5054 ¶87 is quoted by") for e in errors)


def test_a_decision_without_a_quote_or_reason_is_refused(store, consumed):
    _edit_coverage(
        store, "C-2025-5052", lambda data: data["decisions"].update({1: {"decision": "used"}})
    )
    assert "C-2025-5052 ¶1 is used but no snippet quotes it" in guidance_coverage_errors(
        store, consumed
    )

    _edit_coverage(
        store, "C-2025-5052", lambda data: data["decisions"].update({1: {"decision": "no_effect"}})
    )
    with pytest.raises(ValueError, match="no_effect requires a reason"):
        guidance_coverage_errors(store, consumed)
