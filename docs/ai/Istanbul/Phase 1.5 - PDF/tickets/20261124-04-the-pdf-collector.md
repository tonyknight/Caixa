---
id: 20261124-04-the-pdf-collector
title: The PDF collector
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: pdf collector, byte-for-byte archive into Documents/PDF, sources, undo,
  reset.'
parent:
depends_on:
- 20261124-02-the-archival-naming-convention
- 20261124-03-migration-6-and-document-records
subtasks: []
plan_status: done
---
## Description

The `pdf` collector in `caixa/collectors/pdfImport.py`, registered by entry point: preview and import of files, folders (recursive) and zips; identity by SHA-256; working copies; byte-for-byte archive into `<YYYY>/<Author>/` or `Unrecognized/`; sources; undo; workers; the wizard card. No OCR or enrichment yet (later tickets plug into its pipeline).

## Acceptance criteria

- [x] Registered as `pdf = "caixa.collectors.pdfImport:collectors"`; appears in `collectors.list` with a how-to card and options
- [x] Preview counts PDFs, already in the box, duplicates within the source, encrypted, unreadable, pages, size, and writes nothing
- [x] Run archives each new PDF byte for byte; a source's bytes and modification time are unchanged; a second run adds only source rows
- [x] Filed into `<YYYY>/<Author>/` when a date and author are known (`caixa.documents.archive.place` takes them; ticket 09 supplies them from the filename and properties), else `Documents/PDF/Unrecognized/` under its original name
- [x] Undo removes what the import added; progress, cancel and run-again work; up to the Workers setting processes
- [x] The box README mentions `Documents/`

## Context

Phase 1.5 - PDF Tasks Breakdown item 4. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (PDF collector, Archive), *The box*, *Pipeline*; D1–D3, D8.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:** the `pdf` collector (`caixa/collectors/pdfImport.py`), registered by entry
  point, appears in the import wizard with its card.
  - It finds every PDF in a file, a folder (recursive) or a zip, and examines each in up to the
    Workers setting processes: hash, size, time, pages, password, properties, or why it cannot be
    used.
  - Preview counts new documents, those already in the box, copies, locked and unreadable files
    (named), pages and size, and writes nothing.
  - An import copies each new PDF byte for byte through a checked `.part` file into
    `Documents/PDF/Unrecognized/` under its own name. `archive.place` files by year and author when
    facts are given; ticket 09 gives them. Each document is recorded with its sources and an
    `import` run, and committed one by one.
  - Known files only gain a source row; locked files wait for review; unreadable ones are named
    and left alone.
  - Undo and reset take the documents out, and reset keeps the owner's own files. The box README
    describes `Documents/`.
- **Files:**
  - new: `caixa/collectors/pdfImport.py`, `caixa/documents/archive.py`,
    `caixa/documents/importing.py`, `tests/test_pdf_collector.py`;
  - changed: `pyproject.toml` (entry point; mypy treats PyMuPDF, OCRmyPDF and pikepdf as
    untyped), `caixa/reset.py`, `caixa/box.py`;
  - two older tests corrected: `tests/test_chattr_collectors.py` compared lists with `>=`, and
    `tests/test_contacts_setting.py` assumed every collector reads contacts.
- **Errors:** opening the master read-only makes SQLite's `-wal`/`-shm` files, and the preview
  test now ignores them. Adding a seventh collector exposed the two older test assumptions above.
- **Verify:**
  - `python -m pytest -q`: 1651 passed plus the corrected contacts test (8 passed), 1 skipped.
  - vitest: 277 passed.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: abf68b5..11974e2 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a file from a zip is recorded as found at `<zip>!/<member>`. For a zip inside a
  chosen folder this names the folder, not the zip; good enough to find it again.
- **Minor:** preview's counts are carried in `Preview.warnings`, since the contract has no fields
  for them. The wizard shows them as lines.
- **Minor:** a file whose name has nothing usable is filed under the first 12 characters of its
  SHA-256 (rare; such files can be renamed in review).
- **Spec:** D1–D3 and D8 met; every acceptance criterion met. The provisional filing rule's facts
  come in ticket 09, through `import_examined(facts=…)`.
- **TDD:** RED (`ModuleNotFoundError: caixa.collectors.pdfImport`; the run tests failing before
  `importing.py`) before each GREEN.
- **Commits:** `20261124-04 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
