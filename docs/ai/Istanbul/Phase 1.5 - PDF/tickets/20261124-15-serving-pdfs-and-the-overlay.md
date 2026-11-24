---
id: 20261124-15-serving-pdfs-and-the-overlay
title: Serving PDFs and the overlay
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: PDFs inline under their own policy; document.js overlay with page jumps,
  from the box and from disk.'
parent:
depends_on:
- 20261124-04-the-pdf-collector
subtasks: []
plan_status: done
---
## Description

PDFs served inline by `caixa serve` under a policy the browser's viewer accepts in a frame; `document.js` overlay with page jumps; from `/box/` and `file://`.

## Acceptance criteria

- [x] `application/pdf` is served inline with ranges
- [x] Open shows the PDF in an overlay, `#page=N` jumps; Escape, cross and outside click close; Open in its own window
- [x] Its hash joins the box CSP; works from `/box/` and `file://` (Chromium end-to-end)

## Context

Phase 1.5 - PDF Tasks Breakdown item 15. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Overlay, Serving PDFs); D19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:**

- **Serving:** `caixa/web.py` serves `application/pdf` inline, with ranges, so the browser's own
  viewer shows it. A PDF is not one of the box's pages, so it is sent under its own policy:
  `frame-ancestors 'self'`, meaning only the box's pages may show it in a frame, with `nosniff`.
  The pages' policy, with its script hashes and `default-src 'none'`, would stop some browsers'
  PDF viewers.
- **The overlay script:** `caixa/documents/templates/document.js`, Caixa's own page script
  beside Chattr's:
  - a link `a.open-document` opens its PDF in a dialog over the page, in a frame drawn by the
    browser's viewer, with `#page=N` kept;
  - Escape, the cross or a click beside it closes the dialog;
  - **Open in its own window** shows the PDF in a tab;
  - modifier clicks open as links do;
  - without the script each card is a plain link to its PDF.

  Its hash joins the box pages' policy. `web.PAGE_SCRIPTS` names each script's folder (Chattr's
  templates or Caixa's), and pages drawn with an older version get the current one, as for the
  other scripts.
- **The overlay's look:** `caixa/documents/templates/document.css`, the same Nord panel as the
  conversation overlay, included by the document pages (ticket 16).
- **End to end:** a box with an imported PDF and a small test page carrying the script. The
  overlay opens from `/box/` and from `file://` in Chromium, at the right page. Safari is for the
  maintainer.

### T01: PDFs served inline, and the script's place in the policy

- `caixa/web.py`.
- `caixa/documents/templates/document.js`, `caixa/documents/templates/document.css`.
- `pyproject.toml` (package data).
- Tests (`tests/test_web_server.py`):
  - a PDF of the box is served inline as `application/pdf` with ranges under the PDF policy and
    without `Content-Disposition`;
  - a page's policy lists `document.js`'s hash;
  - an older copy of the script in a page is replaced by the current one;
  - the script's text begins as `PAGE_SCRIPTS` says.
- Verify: `python -m pytest -q tests/test_web_server.py`
- [x] done

### T02: The overlay in a browser

- `web/tests/e2e-documents.test.ts`.
- `web/tests/e2e-support.ts` (`buildPdfFamily`).
- Tests (Chromium, the real `caixa serve`):
  - clicking **Open** shows the dialog with the PDF in a frame at `#page=2`;
  - Escape and the cross close it;
  - **Open in its own window** points at the PDF;
  - the same from `file://`.
- Verify: `cd web && pnpm exec vitest run tests/e2e-documents.test.ts && pnpm exec tsc --noEmit`
- [x] done

## Completion report

- **Outcome:** `caixa serve` shows PDFs inline (`application/pdf`, ranges, no
  `Content-Disposition`) under their own policy, `frame-ancestors 'self'`, so the browser's viewer
  works in the overlay and nothing else can frame them. `caixa/documents/templates/document.js`
  is Caixa's own page script:
  - **Open** (`a.open-document`) shows the PDF over the page at `#page=N`;
  - Escape, the cross or a click beside it closes it;
  - **Open in its own window** shows it in a tab.

  Its hash is in the box pages' policy. `PAGE_SCRIPTS` now names each script's folder, and
  older copies in pages are replaced. `document.css` gives the Nord panel. Chromium end-to-end
  tests open the overlay from `/box/` and from `file://`.
- **Files:**
  - new: `caixa/documents/templates/document.js`, `caixa/documents/templates/document.css`,
    `web/tests/e2e-documents.test.ts`;
  - changed: `caixa/web.py`, `pyproject.toml` (package data), `tests/test_web_server.py`,
    `web/tests/e2e-support.ts` (`buildPdfFamily`).
- **Errors:** the first end-to-end test page lacked the overlay's style, so the closed dialog
  stayed visible; the page now carries `document.css`, as document pages will.
- **Verify:**
  - `python -m pytest -q`: 1901 passed, 1 skipped.
  - vitest: 279 passed (with the new end-to-end tests); tsc clean.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 890be88..e9b55c6 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only (one for the Mac).

- **Minor (for the Mac):** headless Chromium does not draw PDFs, so the tests check the frame's
  address and the PDF's headers, not the viewer itself. Safari's viewer in the overlay, from
  `/box/` and from disk, is the maintainer's check.
- **Minor:** unlike `conversation.js`, the overlay does not hand Escape to the PDF frame (a
  browser's PDF viewer keeps its own keys); the cross and a click beside it always work.
- **Spec:** D19 met; every acceptance criterion met.
- **TDD:** RED (4 failing web tests; the end-to-end test failing on its first page) before each
  GREEN.
- **Commits:** `20261124-15 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
