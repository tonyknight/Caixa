---
id: 20261124-04-the-pdf-collector
title: "The PDF collector"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-02-the-archival-naming-convention
- 20261124-03-migration-6-and-document-records
subtasks: []
---

## Description

The `pdf` collector in `caixa/collectors/pdfImport.py`, registered by entry point: preview and import of files, folders (recursive) and zips; identity by SHA-256; working copies; byte-for-byte archive into `<YYYY>/<Author>/` or `Unrecognized/`; sources; undo; workers; the wizard card. No OCR or enrichment yet (later tickets plug into its pipeline).

## Acceptance criteria

- [ ] Registered as `pdf = "caixa.collectors.pdfImport:collectors"`; appears in `collectors.list` with a how-to card and options
- [ ] Preview counts PDFs, already in the box, duplicates within the source, encrypted, unreadable, pages, size, and writes nothing
- [ ] Run archives each new PDF byte for byte; a source's bytes and modification time are unchanged; a second run adds only source rows
- [ ] Filed by date and author when the filename or properties give both (provisional rule until ticket 09), else `Documents/PDF/Unrecognized/` under its original name
- [ ] Undo removes what the import added; progress, cancel and run-again work; up to the Workers setting processes
- [ ] The box README mentions `Documents/`

## Context

Phase 1.5 - PDF Tasks Breakdown item 4. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (PDF collector, Archive), *The box*, *Pipeline*; D1–D3, D8.

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
