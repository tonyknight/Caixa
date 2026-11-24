---
id: 20261124-04-the-pdf-collector
title: The PDF collector
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-02-the-archival-naming-convention
- 20261124-03-migration-6-and-document-records
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The `pdf` collector in `caixa/collectors/pdfImport.py`, registered by entry point: preview and import of files, folders (recursive) and zips; identity by SHA-256; working copies; byte-for-byte archive into `<YYYY>/<Author>/` or `Unrecognized/`; sources; undo; workers; the wizard card. No OCR or enrichment yet (later tickets plug into its pipeline).

## Acceptance criteria

- [ ] Registered as `pdf = "caixa.collectors.pdfImport:collectors"`; appears in `collectors.list` with a how-to card and options
- [ ] Preview counts PDFs, already in the box, duplicates within the source, encrypted, unreadable, pages, size, and writes nothing
- [ ] Run archives each new PDF byte for byte; a source's bytes and modification time are unchanged; a second run adds only source rows
- [ ] Filed into `<YYYY>/<Author>/` when a date and author are known (`caixa.documents.archive.place` takes them; ticket 09 supplies them from the filename and properties), else `Documents/PDF/Unrecognized/` under its original name
- [ ] Undo removes what the import added; progress, cancel and run-again work; up to the Workers setting processes
- [ ] The box README mentions `Documents/`

## Context

Phase 1.5 - PDF Tasks Breakdown item 4. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (PDF collector, Archive), *The box*, *Pipeline*; D1–D3, D8.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:**

- `caixa/collectors/pdfImport.py`: `PdfCollector` (id `pdf`, "PDF documents", inputs file,
  folder, zip) and `collectors()`, registered in `pyproject.toml`
  (`pdf = "caixa.collectors.pdfImport:collectors"`).
  - `locate` uses `inputs.resolve` with every `*.pdf` (any case) outside system folders; zips are
    unpacked into the collector's work folder, and zips at a folder's top are read too.
  - `examine(path)` is module level, so worker processes can run it (spawn, as mail does). It
    returns `Examined`: path, SHA-256, size, modification time, pages, whether a password is
    needed, properties, and an error. The error is set for a file that is not a PDF, or one MuPDF
    could only rebuild into empty pages (damaged).
  - `preview` examines and counts, writing nothing: new, already in the box, copies within the
    source, locked, unreadable (named), pages, size.
  - `run`:
    1. examine in up to the Workers setting processes;
    2. one writer then records every file in order: known file → a new source row only; a copy
       within the source → the same; unreadable → a warning naming it, left alone; new → copied
       byte for byte, checked against its SHA-256, placed, recorded (`save_document`,
       `add_source`, an `import` run) and counted;
    3. the import record is finished with the counts.
- `caixa/documents/archive.py`:
  - `place(box, source_name, sha256, facts=None)`: the box-relative path in
    `Documents/PDF/<YYYY>/<Author>/` with its archival name when `facts` give a date, an author and
    a title; else `Documents/PDF/Unrecognized/<original name>`. Uses `caixa.naming`, with
    `free_path` for clashes.
  - `copy_into(box, source, relative, sha256)`: copies through a `.part` file, checks the hash,
    then renames.
  - Ticket 09 supplies `facts`.
- Locked files are archived and marked `needs_review` (`locked`).
- `caixa/reset.py`: files of documents (from the master) are written files, and `Documents/` is
  tidied on reset (not re-created).
- `caixa/box.py`: the README mentions `Documents/`.
- The service's import job already gives undo (snapshot, new files removed).

### T01: The collector, locating and preview

- `caixa/collectors/pdfImport.py` (`PdfCollector`, `collectors`, `examine`, `Examined`, `locate`,
  `preview`).
- `pyproject.toml`: entry point (`pip install -e .` again to register it).
- Tests (`tests/test_pdf_collector.py`):
  - registered and described, with a how-to card;
  - finds the family recursively, from a folder, a zip and a single file;
  - examines a locked file, a damaged one and a false `.pdf`;
  - preview counts new, already there, copies, locked, unreadable (named) and pages, and writes
    nothing.
- Verify: `python -m pytest -q tests/test_pdf_collector.py tests/test_collector_contract.py`
- [x] done

### T02: Importing: copies, records, undo and reset

- `caixa/documents/archive.py` (`place`, `copy_into`).
- `PdfCollector.run`, with workers.
- `caixa/reset.py`, and `caixa/box.py` README.
- Tests:
  - every readable PDF archived byte for byte under `Documents/PDF/Unrecognized/` with its
    original name, sources' bytes and times unchanged;
  - `place` with facts gives `<YYYY>/<Author>/(date) Title - Author.pdf`;
  - a second run adds only source rows (copies and the duplicate counted unchanged);
  - the locked file is `needs_review`;
  - unreadable files are named in warnings and not archived;
  - a clash gets ` (2)`;
  - 1 and 4 workers give the same box;
  - undo through the service empties `Documents/`;
  - reset removes the archived files and keeps a file the owner put there.
- Verify: `python -m pytest -q tests/test_pdf_collector.py tests/test_reset.py tests/test_undo.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
