---
id: 20261124-17-documents-view-on-the-index-page
title: Documents view on the index page
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-16-author-pages-and-the-unrecognized-page
subtasks: []
plan_status: in-progress
current_task: T03
---
## Description

Documents ▸ PDF on the index page: a heat map of document dates with a year range, years and author tiles, Unrecognized, To review, and an in-page card filter.

## Acceptance criteria

- [ ] The sidebar shows Documents ▸ PDF with its count
- [ ] Heat map and year range; years then author tiles; Unrecognized and To review
- [ ] The in-page filter narrows cards by their words, also from disk

## Context

Phase 1.5 - PDF Tasks Breakdown item 17. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Browser*; D20, D21.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T03

**Design:** the Documents ▸ PDF view is a page Caixa draws, `Documents/PDF/PDF.html` (named like
the other document pages: after its folder). The box's index reaches it from its sidebar. Chattr
stays free of documents: its index gains a generic slot, `links`, groups of plain sidebar links
(`[{group, links: [{label, href, count}]}]`). Caixa fills it with **Documents** ▸ **PDF (n)**.
Without links the index is as before, and the links are part of what the index is drawn from.

The view page, in the documents pages' style:
- a heat map of document dates: one calendar per year, the latest open, each day linking to its
  first card;
- a year range (from, to);
- the years, newest first, each with its authors as tiles (initials, count) linking to their
  pages;
- **Unrecognized** with its count;
- **To review**: each waiting document with its reasons in words, linking to its card;
- every document as a compact entry (date, title, author, type, tags, Open).

`documents-index.js`, a new page script (hash in the policy, refreshed like the others):
- the filter box narrows the entries and tiles to those holding every word typed (accents and
  case aside);
- the year range hides what is outside it.

Without the script everything shows. The page is drawn by `draw_documents` with the others.

### T01: The index's slot for links

- `tools/chattr/src/chattr/pages.py` and `templates/index.html`: `links` in `_index`,
  `render_index` and `render_pages`.
- `tools/chattr/src/chattr/commands.py`: `links` in `publish` and `publish_index`.
- `caixa/collectors/chattr.py`: passes `caixa.documents.view.index_links(box)`.
- Tests:
  - Chattr: links drawn in the sidebar under their group, none without;
  - Caixa: a box with documents gets **Documents** ▸ **PDF (n)** linking to
    `Documents/PDF/PDF.html`;
  - a box without documents gets none.
- Verify: `python -m pytest -q tools/chattr/tests/test_render_pages.py tests/test_documents_view.py`
- [x] done

### T02: The view page

- `caixa/documents/view.py` (`index_links`, `view_page`).
- `caixa/documents/templates/documents.html`, `caixa/documents/templates/documents-index.js`.
- `caixa/documents/pages.py` (draws it).
- `caixa/web.py` (`PAGE_SCRIPTS`).
- Tests (`tests/test_documents_view.py`):
  - the heat map's days link to cards;
  - years newest first with author tiles and counts linking to their pages;
  - Unrecognized with its count;
  - To review with reasons;
  - every document as an entry with Open;
  - links relative;
  - the script's hash in the policy.
- Verify: `python -m pytest -q tests/test_documents_view.py tests/test_documents_pages.py tests/test_web_server.py`
- [x] done

### T03: Filtering and the year range in a browser

- `web/tests/e2e-documents.test.ts`.
- Tests (Chromium, from disk):
  - typing words narrows the entries;
  - a year range hides other years;
  - the index's sidebar link opens the view.
- Verify: `cd web && pnpm exec vitest run tests/e2e-documents.test.ts && pnpm exec tsc --noEmit`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
