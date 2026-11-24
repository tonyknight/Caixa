---
id: 20261124-18-search-in-the-window
title: Search in the window
type: feature
priority: medium
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: search form in the served view, hits with marked snippets opening at
  their page.'
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

- [x] Searching from the view finds scanned-page words; results open the PDF at the page
- [x] Filters narrow results; the view degrades to the in-page filter from disk

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

- **Outcome:** the view page has a search form, hidden until its script finds the page served by
  Caixa. It searches every page's words through `documents.search`, with a type and the view's
  year range as filters. Each hit shows its title, author, date and page (*read by OCR* when it
  was), a snippet with the words marked (built as text, never HTML from the box), and **Open at
  page N** in the overlay. "Nothing found" and a reach failure are said. From disk the form stays
  hidden and the in-page filter is what narrows. Chromium end-to-end tests against the real
  `caixa serve` cover these.
- **Files:**
  - changed: `caixa/documents/templates/documents.html`,
    `caixa/documents/templates/documents-index.js`, `caixa/documents/view.py` (types),
    `tests/test_documents_view.py`, `web/tests/e2e-documents.test.ts`.
- **Errors:**
  - The end-to-end test chose a type the box did not have (with OCR off no bill was confident),
    and Playwright waited for an option that never came; it now filters statements.
  - Closing the overlay by Escape is left to its own test, since a PDF frame can hold the focus.
- **Verify:**
  - `python -m pytest -q`: 1930 passed, 1 skipped.
  - vitest: 283 passed (six document end-to-end tests).
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 2271eb1..2c5c133 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** search is on the view page only; an author page has its in-page cards but no search
  form.
- **Minor:** hits are pages, not documents, so a document matching on many pages shows many times
  (as in the service).
- **Spec:** D21 met; every acceptance criterion met.
- **TDD:** RED (the form test; the end-to-end search) before each GREEN.
- **Commits:** `20261124-18 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
