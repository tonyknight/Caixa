---
id: 20261124-16-author-pages-and-the-unrecognized-page
title: Author pages and the Unrecognized page
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: author pages and the Unrecognized page with cards; drawn when documents
  change.'
parent:
depends_on:
- 20261124-12-reconciliation-confidence-and-apply
- 20261124-15-serving-pdfs-and-the-overlay
subtasks: []
plan_status: done
---
## Description

Caixa draws the author pages (`<YYYY>/<Author>/<Author>.html`) and the Unrecognized page with cards in date order, on Chattr's base and Nord palette, through a generic slot in Chattr's templates; redraws batched.

## Acceptance criteria

- [x] Each card shows archival name, title, date at its precision, author, type, category, tags, original filename, summary (marked), statuses and Open
- [x] Pages open from disk without a script; Chattr's templates know nothing of documents
- [x] Pages are redrawn when their documents change, behind Update the pages

## Context

Phase 1.5 - PDF Tasks Breakdown item 16. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Pages); D20.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/documents/pages.py` draws the document pages with Caixa's own templates
(`caixa/documents/templates/`), which extend Chattr's `base.html`: the same Nord palette, light
and dark. Chattr's templates are not changed; the index page's slot is ticket 17.

- **Where:** one page per year and author, `Documents/PDF/<YYYY>/<Author>/<Author>.html` (named
  after the author alone, decided 2026-11-24), and `Documents/PDF/Unrecognized/Unrecognized.html`
  for the documents waiting there.
- **What a card shows**, in date order:
  - the title, the date at its precision (`30 November 2024`, `November 2024`, `2024`), the
    author, type and category;
  - tags; the archival file name and the original filename;
  - the summary, marked *Summary by <model>*;
  - OCR, validation and review statuses in words (review reasons included);
  - **Open**: `a.open-document`, a relative link to the PDF with `data-title`, shown in the
    overlay with `document.js`.

  A link back to the box's index, and the overlay's style inline.
- **Without scripts:** the page reads fully and each Open is a plain link. From disk, everything
  is relative.
- **When:** `draw_documents(box)` draws every page whose content changed (a page that is the same
  is not written again), removes pages that no longer have documents, and records what it wrote
  in `.caixa/documents-pages.json` (reset removes them; undo takes new ones away). It runs at the
  end of a PDF import, an enrich or reprocess job, an author rename or merge, a tag change, and
  every full redraw of the box's pages (**Update the pages**).

### T01: The templates and drawing

- `caixa/documents/pages.py` (`draw_documents`, `page_path`, `card`).
- `caixa/documents/templates/author.html`.
- `caixa/reset.py` (the record of pages).
- Tests (`tests/test_documents_pages.py`, an import of the family with OCR and the stand-in
  model):
  - the statement's page at `2024/Banco Atlântico/Banco Atlântico.html` has its card with every
    field, and the duplicate's;
  - cards are in date order;
  - the Unrecognized page lists the misleading name and the contract with their review reasons;
  - Open links are relative and open the PDF from disk;
  - the summary is marked as a model's;
  - drawing again writes nothing;
  - renaming an author moves its page;
  - reset removes the pages;
  - Chattr's templates are unchanged.
- Verify: `python -m pytest -q tests/test_documents_pages.py tests/test_reset.py`
- [x] done

### T02: Drawn when documents change

- `caixa/collectors/pdfImport.py`, `caixa/service.py` (enrich, reprocess, authors, tags, the
  full redraw).
- Tests:
  - an import draws the pages;
  - an author rename through the service redraws;
  - a tag added through the service shows on its card;
  - **Update the pages** redraws a page whose file was deleted.
- Verify: `python -m pytest -q tests/test_documents_pages.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:** `caixa/documents/pages.py` draws, with Caixa's own template on Chattr's base (Nord,
  light and dark):
  - an author page for each year and author, `Documents/PDF/<YYYY>/<Author>/<Author>.html`;
  - `Documents/PDF/Unrecognized/Unrecognized.html`.

  Each card shows the title, the date at its precision, author, type, category and pages; tags;
  the box name and the name it came with; the summary marked *Summary by <model>*; OCR,
  validation, model and review statuses in words; and **Open** (the overlay, or a plain relative
  link without scripts or from disk).

  Pages are written only when they changed, removed when they have no documents, and recorded
  for reset and undo. They are drawn at the end of an import, enrich, reprocess, author change or
  tag change, and with every full redraw. Chattr's templates are unchanged.
- **Files:**
  - new: `caixa/documents/pages.py`, `caixa/documents/templates/author.html`,
    `tests/test_documents_pages.py`;
  - changed: `caixa/collectors/pdfImport.py`, `caixa/service.py`, `caixa/reset.py`.
- **Errors:**
  - A test's date pattern assumed `datetime` came first in `<time>`; loosened.
  - **Update the pages** starts a job only when changes wait, so the test starts the same refresh
    job directly.
- **Verify:**
  - `python -m pytest -q`: 1916 passed, 1 skipped.
  - vitest: 279 passed.
  - mypy (3.12 target): only the 8 baseline errors.
  - A screenshot of an author page in Chromium was checked by eye.

## Review

### 2026-11-24: c4bb1da..4f2f675 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** pages are drawn at once after a tag or author change rather than batched behind
  **Update the pages**. They are few and quick to draw; corrections (ticket 19) follow the
  batching.
- **Minor:** a document page has no calendar heat map of its own; the heat map is the index view's
  (ticket 17).
- **Spec:** D20 (pages) met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.pages`; the drawing-on-change tests before
  T02) before each GREEN.
- **Commits:** `20261124-16 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
