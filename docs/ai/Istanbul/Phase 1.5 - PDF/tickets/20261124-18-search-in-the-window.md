---
id: 20261124-18-search-in-the-window
title: Search in the window
type: feature
priority: medium
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-08-page-text-and-full-text-index
- 20261124-17-documents-view-on-the-index-page
subtasks: []
plan_status: done
---
## Description

Search in the served Documents view: a search box and filters, results with snippets and pages that open the overlay at the page.

## Acceptance criteria

- [ ] Searching from the view finds scanned-page words; results open the PDF at the page
- [ ] Filters narrow results; the view degrades to the in-page filter from disk

## Context

Phase 1.5 - PDF Tasks Breakdown item 18. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Search and Ask*; D21.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** the view page (`Documents/PDF/PDF.html`) carries a search form, hidden until its
script finds the page served by Caixa (`/box/` over http). It then searches every page's words
through the service (`documents.search` over `/api/caixa/rpc`; the box pages' policy already
allows `connect-src 'self'`).

- **The form:** the words, a type (the types the box's documents have), and the view's year
  range as the date range.
- **The hits**, best first, one per page:
  - the document's title (or file name), author and date;
  - the page, and *read by OCR* when it was;
  - the snippet, with the words marked (built as text: the `[ ]` marks become `<mark>`, nothing
    from the box is read as HTML);
  - **Open**, which shows the PDF in the overlay at that page;
  - a link to its card.
- **Messages:** "Nothing found" when there are no hits, and a message when Caixa cannot be
  reached.
- **From disk:** the form stays hidden and the view's in-page filter is what narrows (ticket 17).

Both live in `documents.html` and `documents-index.js` (its hash in the policy, as before).

### T01: The search form and its results

- `caixa/documents/templates/documents.html`, `caixa/documents/templates/documents-index.js`,
  `caixa/documents/view.py` (the types offered).
- Tests (`tests/test_documents_view.py`): the form is drawn hidden with the box's types, and
  the script names the service method.
- Verify: `python -m pytest -q tests/test_documents_view.py tests/test_web_server.py`
- [x] done

### T02: Searching in a browser

- `web/tests/e2e-documents.test.ts`.
- Tests (Chromium, the real `caixa serve` with the stand-in-read box):
  - "Supermercado" finds the statement's page 2 with the word marked, and Open shows the PDF at
    `#page=2`;
  - a type filter narrows;
  - a search finding nothing says so;
  - from disk the form stays hidden.
- Verify: `cd web && pnpm exec vitest run tests/e2e-documents.test.ts && pnpm exec tsc --noEmit`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
