"""Uploaded PDF and DOCX files become input text: the extractor, and POST /api/extract."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from aiact.report_app.app import app
from aiact.report_app.uploads import (
    SUPPORTED_UPLOADS,
    UnreadableUpload,
    UnsupportedUpload,
    extract_upload,
)

# ---- hand-built files --------------------------------------------------------------------------
# Small enough to write byte by byte, so the tests depend on no authoring library.


def pdf_bytes(lines: list[str]) -> bytes:
    """A one-page PDF showing `lines` in Helvetica, with a correct cross-reference table."""
    stream = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({line}) Tj 0 -16 Td" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n{body}\nendobj\n".encode())
    start_xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{start_xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


_DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>TalentRank</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Human oversight</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">A panel reviews </w:t></w:r>
      <w:r><w:t>every recommendation.</w:t></w:r></w:p>
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>
      <w:r><w:t>Logs are kept.</w:t></w:r></w:p>
    <w:p/>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Role</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Provider</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:sectPr/>
  </w:body>
</w:document>
"""


def docx_bytes(document_xml: str = _DOCUMENT_XML) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types '
            'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr("word/document.xml", document_xml)
    return out.getvalue()


# ---- the extractor -----------------------------------------------------------------------------


def test_a_pdf_gives_up_its_text():
    text = extract_upload("card.pdf", pdf_bytes(["System card", "A panel reviews it."]))

    assert "System card" in text
    assert "A panel reviews it." in text


def test_a_docx_reads_as_markdown_flavoured_text():
    text = extract_upload("card.docx", docx_bytes())

    assert text.split("\n\n") == [
        "# TalentRank",
        "## Human oversight",
        "A panel reviews every recommendation.",
        "- Logs are kept.",
        "Role | Provider",
    ]


def test_the_extension_decides_whichever_way_the_browser_spells_the_path():
    assert "TalentRank" in extract_upload(r"C:\fakepath\Card.DOCX", docx_bytes())


def test_an_unknown_format_is_refused_as_unsupported():
    with pytest.raises(UnsupportedUpload, match="paste the text"):
        extract_upload("card.txt", b"plain text")


def test_a_file_that_is_not_what_its_name_says_is_refused():
    with pytest.raises(UnreadableUpload, match="does not look like a PDF"):
        extract_upload("card.pdf", docx_bytes())
    with pytest.raises(UnreadableUpload, match="save it as .docx"):
        extract_upload("card.docx", pdf_bytes(["hello"]))
    with pytest.raises(UnreadableUpload, match="save it as .docx"):
        extract_upload("card.docx", b"\xd0\xcf\x11\xe0 an old binary .doc")


def test_a_docx_with_no_text_is_refused():
    empty = '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/></w:body></w:document>'
    with pytest.raises(UnreadableUpload, match="No text could be read"):
        extract_upload("card.docx", docx_bytes(empty))


def test_a_damaged_pdf_is_refused_not_raised():
    with pytest.raises(UnreadableUpload, match="could not be read as a PDF"):
        extract_upload("card.pdf", pdf_bytes(["hello"])[:60])


# ---- the endpoint ------------------------------------------------------------------------------


def post(data: bytes, filename: str):
    return TestClient(app).post(
        f"/api/extract?filename={filename}",
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


def test_the_endpoint_returns_the_text_for_the_input_box():
    response = post(docx_bytes(), "card.docx")

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "card.docx"
    assert body["text"].startswith("# TalentRank")


def test_the_endpoint_reads_a_pdf_too():
    response = post(pdf_bytes(["Hello from a PDF"]), "card.pdf")

    assert response.status_code == 200
    assert "Hello from a PDF" in response.json()["text"]


def test_formats_the_page_reads_itself_are_415_here():
    response = post(b"plain text", "card.txt")

    assert response.status_code == 415
    for suffix in SUPPORTED_UPLOADS:
        assert suffix in response.json()["detail"]


def test_a_mislabelled_file_is_422_with_the_reason():
    response = post(b"not a zip at all", "card.docx")

    assert response.status_code == 422
    assert "could not be read as a Word document" in response.json()["detail"]


def test_an_empty_upload_is_422():
    assert post(b"", "card.pdf").status_code == 422


def test_an_oversized_upload_is_413_before_extraction(monkeypatch):
    monkeypatch.setattr("aiact.report_app.app.MAX_UPLOAD_BYTES", 10)

    response = post(docx_bytes(), "card.docx")

    assert response.status_code == 413
    assert "upload limit is 10" in response.json()["detail"]


def test_text_over_the_document_limit_is_413_like_the_review(monkeypatch):
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "10")

    response = post(docx_bytes(), "card.docx")

    assert response.status_code == 413
    assert "the limit is 10" in response.json()["detail"]


def test_the_limits_endpoint_names_the_upload_cap():
    limits = TestClient(app).get("/api/limits").json()

    assert limits["max_upload_bytes"] > 0


def test_a_list_paragraph_style_reads_as_a_list_item_too():
    xml = _DOCUMENT_XML.replace(
        '<w:pPr><w:pStyle w:val="Heading2"/></w:pPr>',
        '<w:pPr><w:pStyle w:val="ListBullet"/></w:pPr>',
    )

    assert "- Human oversight" in extract_upload("card.docx", docx_bytes(xml))


def test_an_upload_failure_is_reported_under_the_button_like_a_field_error():
    """Not in the page's error block below the form, out of sight: right under "Load a file", in
    the same `.field-error` style the model and key fields use."""
    client = TestClient(app)
    page = client.get("/").text
    upload = page.split('<div class="upload edit-only">')[1].split("</div>")[0]
    assert 'id="file"' in upload and 'aria-describedby="file-error"' in upload
    assert '<span class="field-error" id="file-error" role="alert" hidden></span>' in upload
    script = client.get("/static/report.js").text
    load_file = script.split("async function loadFile(file) {")[1].split("\n}\n")[0]
    assert 'setFieldError("file", err.message);' in load_file
    assert "showError(err.message)" not in load_file
    styles = client.get("/static/report.css").text
    assert ".upload:has(> .field-error:not([hidden])) { flex-basis: 100%; }" in styles
    # Drawn as a control, so the message under it cannot be read as part of its label; marked red
    # while the message shows, as an invalid input is.
    filebtn = styles.split(".filebtn {")[1].split("}")[0]
    assert "inline-flex" in filebtn and "border: 1px solid var(--line-strong)" in filebtn
    assert '.filebtn:has(input[aria-invalid="true"]) { border-color: var(--red); }' in styles
