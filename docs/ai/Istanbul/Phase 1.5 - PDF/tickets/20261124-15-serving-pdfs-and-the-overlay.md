---
id: 20261124-15-serving-pdfs-and-the-overlay
title: "Serving PDFs and the overlay"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-04-the-pdf-collector
subtasks: []
---

## Description

PDFs served inline by `caixa serve` under a policy the browser's viewer accepts in a frame; `document.js` overlay with page jumps; from `/box/` and `file://`.

## Acceptance criteria

- [ ] `application/pdf` is served inline with ranges
- [ ] Open shows the PDF in an overlay, `#page=N` jumps; Escape, cross and outside click close; Open in its own window
- [ ] Its hash joins the box CSP; works from `/box/` and `file://` (Chromium end-to-end)

## Context

Phase 1.5 - PDF Tasks Breakdown item 15. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Overlay, Serving PDFs); D19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: draft
Current task:

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
