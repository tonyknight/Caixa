# Caixa test fixtures

Caixa's tests use the same synthetic fixture family as Chattr. The builders live with Chattr, so
Chattr can run its own tests on its own:

- **Builders and documentation:** [`tools/chattr/tests/fixtures/`](../../tools/chattr/tests/fixtures/README.md)
- **Entry point:** `fixtures.build_all(out_dir)` (also available as the `fixture_family` pytest
  fixture in `tools/chattr/tests/conftest.py`)

Caixa-specific fixtures, such as master-database scenarios, go in this folder as later tickets
need them. Never add real personal data.

## The PDF family

PDFs are Caixa's own domain, so their builders live here: [`pdf_family.py`](pdf_family.py).
`build_pdf_family(out_dir)` (the `pdf_family` pytest fixture) writes every PDF with PyMuPDF and
an `answers.json` with what is known about each: the class of every page (`text`, `needs_ocr`,
`ocr_layer`, `broken_text`, `blank`), the document's type, title, author and naming date, its key
fields, the words a search must find and where, and whether its filename contradicts it.

- Digital, scanned (pictures at 200 dpi without text), mixed, a good and a poor OCR layer, a page
  whose text extracts to garbage, a rotated narrow receipt and a blank page; English and
  Portuguese.
- Descriptive (`2024-11 Banco Atlântico Checking Statement.pdf`), uninformative (`scan_00482.pdf`,
  `Document1.pdf`, `download.pdf`) and misleading (`2022 Car Insurance.pdf`, really a 2024
  electricity bill) filenames; wrong properties (`2023 Property Tax Bill.pdf`).
- Files an import must survive: a password-locked statement (`PASSWORD`), a policy with only an
  owner password, a damaged scan (MuPDF repairs it into an empty page), a text file named `.pdf`,
  an exact copy in `Arquivo/2024/`, the same statement saved again with different bytes, and a
  `notes.txt`. `zip_family(folder, zip_path)` zips the folder.

People are the synthetic family's; institutions are invented. Two builds are byte-identical except
the encrypted files.
