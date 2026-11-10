"""The real PDF/DOCX/.doc files under data/golden_set/reference/ (see the README there) read —
or are refused — the way "Load a file" promises. Unlike test_report_uploads.py, which builds
minimal bytes by hand to pin the extractor's logic, this module is the fixtures' own regression
test: a change to aiact.report_app.uploads that stops reading real pandoc/LibreOffice/ImageMagick
output, or starts accepting what should be refused, fails here."""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.report_app.uploads import UnreadableUpload, UnsupportedUpload, extract_upload

REFERENCE = Path(__file__).resolve().parents[1] / "data" / "golden_set" / "reference"


def fixture(name: str) -> bytes:
    return (REFERENCE / name).read_bytes()


@pytest.mark.parametrize("name", ["hr-candidate-scoring.docx", "hr-candidate-scoring.pdf"])
def test_the_readable_fixtures_give_back_the_reference_text(name):
    text = extract_upload(name, fixture(name))

    # What a reader would expect to see in the input box and then run a review on — the document's
    # own title, a named section, and enough of it to be the whole thing, not a truncated read.
    assert "TalentRank" in text
    assert "Risk management system" in text
    assert len(text) > 10_000


def test_the_legacy_doc_format_is_refused_as_unsupported():
    with pytest.raises(UnsupportedUpload, match=r"\.doc"):
        extract_upload("hr-candidate-scoring.doc", fixture("hr-candidate-scoring.doc"))


def test_the_scanned_pdf_is_refused_for_holding_no_text():
    with pytest.raises(UnreadableUpload, match="No text could be read"):
        extract_upload("scanned-system-card.pdf", fixture("scanned-system-card.pdf"))


def test_the_mislabelled_docx_is_refused_as_not_a_word_document():
    with pytest.raises(UnreadableUpload, match="could not be read as a Word document"):
        extract_upload("mislabelled-system-card.docx", fixture("mislabelled-system-card.docx"))


def test_the_mislabelled_pdf_is_refused_for_failing_the_signature_check():
    with pytest.raises(UnreadableUpload, match="does not look like a PDF"):
        extract_upload("mislabelled-system-card.pdf", fixture("mislabelled-system-card.pdf"))


def test_every_fixture_named_in_the_readme_exists():
    named = {
        "hr-candidate-scoring.docx",
        "hr-candidate-scoring.pdf",
        "hr-candidate-scoring.doc",
        "scanned-system-card.pdf",
        "mislabelled-system-card.docx",
        "mislabelled-system-card.pdf",
    }
    assert named <= {path.name for path in REFERENCE.iterdir()}
