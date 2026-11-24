---
id: 20261124-16-author-pages-and-the-unrecognized-page
title: Author pages and the Unrecognized page
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-12-reconciliation-confidence-and-apply
- 20261124-15-serving-pdfs-and-the-overlay
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

Caixa draws the author pages (`<YYYY>/<Author>/<Author>.html`) and the Unrecognized page with cards in date order, on Chattr's base and Nord palette, through a generic slot in Chattr's templates; redraws batched.

## Acceptance criteria

- [ ] Each card shows archival name, title, date at its precision, author, type, category, tags, original filename, summary (marked), statuses and Open
- [ ] Pages open from disk without a script; Chattr's templates know nothing of documents
- [ ] Pages are redrawn when their documents change, behind Update the pages

## Context

Phase 1.5 - PDF Tasks Breakdown item 16. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Pages); D20.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
