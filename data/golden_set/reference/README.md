# The two `.md` references, and six upload fixtures

The two Markdown files — `hr-candidate-scoring.md`, `internal-mobility.md` — are the golden set's
actual reference documents: the synthetic, complete, COMPLIANT baselines that
`scripts/make_golden_set.py` degrades to generate every scored case (see the comment at the top of
each file). They are named explicitly in `data/golden_set/ablations*.yaml`; nothing here reads this
directory by listing it, so the files below sit alongside them without joining that pipeline.

The other six files are **not golden-set references**. They exist to exercise "Load a file" in the
report app (`POST /api/extract`, `aiact.report_app.uploads`) against real PDF, DOCX and legacy
`.doc` bytes instead of hand-built test fixtures — something to drag onto the page, or to `curl`,
while checking the upload path by hand. `tests/test_upload_fixtures.py` runs every one of them
through the extractor so a change to `aiact.report_app.uploads` that breaks one of these shapes
fails a test, not a manual check.

| file | format | what it is | what "Load a file" should do |
|---|---|---|---|
| `hr-candidate-scoring.docx` | DOCX | `hr-candidate-scoring.md`, comments stripped, converted with `pandoc` | read the text in (headings, bold, lists and tables intact) and run a normal review |
| `hr-candidate-scoring.pdf` | PDF | the same text, converted with `pandoc --pdf-engine=wkhtmltopdf` | read the text in and run a normal review |
| `hr-candidate-scoring.doc` | legacy binary `.doc` | the DOCX above, saved down by LibreOffice | refused — this module reads `.pdf` and `.docx` only, not the pre-2007 binary format (415) |
| `scanned-system-card.pdf` | PDF, no text layer | a page of text rendered to an image, then wrapped in a PDF (ImageMagick) — no fonts, nothing pdfplumber can extract | refused as unreadable: looks exactly like a scan a reader might actually try (422) |
| `mislabelled-system-card.docx` | plain text | the stripped Markdown saved with a `.docx` name — not a zip at all | refused as unreadable: not what its name says (422) |
| `mislabelled-system-card.pdf` | DOCX bytes | `hr-candidate-scoring.docx` saved with a `.pdf` name | refused as unreadable: fails the `%PDF-` signature check before any parser runs (422) |

None of the six carry author metadata (checked with `unzip -p … docProps/core.xml` and `strings`
for the PDFs) — they are generated from the existing reference text, not authored fresh, so there
is nothing of anyone's to scrub, but it is worth checking again if they are ever regenerated.

To regenerate: strip the reference comments the way `aiact.report_app.samples._read` does, then

```bash
pandoc hr-candidate-scoring.stripped.md -o hr-candidate-scoring.docx
pandoc hr-candidate-scoring.stripped.md --pdf-engine=wkhtmltopdf -o hr-candidate-scoring.pdf
libreoffice --headless --convert-to doc hr-candidate-scoring.docx
```
