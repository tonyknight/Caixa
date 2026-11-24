---
id: 20261124-01-synthetic-pdf-fixtures
title: Synthetic PDF fixtures
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

The synthetic PDF family every later ticket tests against: deterministic builders (PyMuPDF, fixed seeds) that write digital, scanned, mixed, OCR'd (good and poor), broken-text, rotated and odd-sized PDFs for the synthetic family, with descriptive, uninformative and misleading filenames, missing and wrong properties, encrypted, corrupted, duplicate and same-text-different-bytes files, and a file of known answers (type, title, author, date and precision, key fields, words found only on scanned pages).

## Acceptance criteria

- [ ] A builder writes the whole family into a folder from a fixed seed; two builds are byte-identical where the format allows (or differ only in documented ways)
- [ ] Every case in *Testing requirements* (Fixtures) is present, in English and Portuguese, synthetic people and invented institutions only
- [ ] A known-answers file describes each fixture: expected page classes, type, title, author, naming date and precision, key fields, filename conflicts, search words
- [ ] Tests check the fixtures are what they claim (page counts, encryption, scanned pages without text, broken text layer garbled)

## Context

Phase 1.5 - PDF Tasks Breakdown item 1. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: Testing requirements (Fixtures).

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `tests/fixtures/pdf_family.py`. Caixa's own fixtures (PDFs are not Chattr's) go in this
folder, per its README. The conftest puts the folder on `sys.path` (the name `fixtures` is Chattr's)
and adds a session fixture `pdf_family`. `build_pdf_family(out_dir) -> PdfFamily` writes every PDF
with PyMuPDF and returns each one's `PdfFixture`: its path relative to the folder, kind, and known
answers. The known answers are the page classes, type, category, title, author, naming date with
precision and kind, key fields, filename conflicts, and words with the page they are on. They are
also written as `answers.json`.

How the cases are made:
- **Digital pages**: `insert_text` with base-14 fonts (WinAnsi, so plain hyphens).
- **Scanned pages**: a digital page rendered at 200 dpi in grey, with deterministic noise
  (`numpy` with a fixed seed), placed as the only image of a new page. There is no text, and
  Tesseract reads it back.
- **Existing OCR layer**: a scanned page plus the same words in render mode 3 (invisible). A poor
  layer carries garbled words instead.
- **Broken text**: a digital page whose font gets a `ToUnicode` map sending every code to the
  Private Use Area. It looks right, but extraction gives garbage.
- **Rotated, odd-sized and blank pages.**
- **Bytes**: fixed metadata dates and `no_new_id`, so builds are byte-identical. Encrypted files are
  the exception, because AES carries a random IV.

Every person is from the synthetic family; every institution is invented. PyMuPDF becomes a
dependency of Caixa (it is needed at run time from ticket 04 on), and OCRmyPDF an optional extra
(`caixa[ocr]`).

### T01: Builders for the page kinds and the known answers

- `tests/fixtures/pdf_family.py`: builders for digital, scanned, mixed, good and poor OCR layer,
  broken text, rotated, odd-sized and blank pages. The documents:
  - a bank statement;
  - a scanned water bill (uninformative name);
  - a scanned cheque;
  - a property-tax bill (the filename's year is a different date concept);
  - a letter from João Costa (`Document1.pdf`, Microsoft Word properties);
  - a mixed invoice and receipt (`download.pdf`);
  - an insurance renewal with a good OCR layer;
  - a rental agreement with a poor OCR layer;
  - a statement with broken text;
  - a misleading name (`2022 Car Insurance.pdf`, really a 2024 electricity bill);
  - a rotated narrow receipt;
  - Ana Costa's lab results.

  English and Portuguese. `answers.json`.
- `tests/conftest.py`: path and `pdf_family` session fixture. `pyproject.toml`: `pymupdf`
  dependency, `ocr = ["ocrmypdf"]` extra. `tests/fixtures/README.md`: the PDF family.
- Tests (`tests/test_pdf_family.py`):
  - page counts;
  - scanned pages have no text and one image;
  - OCR-layer pages' text is invisible (render mode 3);
  - broken-text pages extract to the Private Use Area but render like a digital page;
  - rotation and size;
  - every answer's words are on the page it names (digital pages) or rendered (scanned);
  - two builds are byte-identical.
- Verify: `python -m pytest -q tests/test_pdf_family.py`
- [x] done

### T02: The awkward files

- `pdf_family.py`:
  - encrypted with a user password;
  - encrypted with an owner password only (readable);
  - corrupted (truncated) and not-a-PDF;
  - an exact duplicate in a subfolder under another name;
  - the statement again with different metadata (same text, different bytes);
  - a non-PDF file;
  - nested folders;
  - `zip_family(folder, zip_path)` for zip imports.
- Tests: encryption states, a corrupted file fails to open, duplicate bytes equal, same-text pair
  differs in bytes but not in text, the zip holds the family.
- Verify: `python -m pytest -q tests/test_pdf_family.py && python -m black --check tests`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
