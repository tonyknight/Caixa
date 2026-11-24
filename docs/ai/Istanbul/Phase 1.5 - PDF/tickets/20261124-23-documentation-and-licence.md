---
id: 20261124-23-documentation-and-licence
title: Documentation and licence
type: feature
priority: low
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: Docs, NOTICE, logs checked for page text, owner-only work folder
parent:
depends_on:
- 20261124-02-the-archival-naming-convention
- 20261124-07-validation-and-failure-handling
- 20261124-21-ask-the-documents
subtasks: []
plan_status: done
current_task: T02
---
## Description

Documentation and licence: README (documents, tools to install), NOTICE with PyMuPDF's AGPL-3.0, the box README's `Documents/` line, the naming convention linked, a check that logs carry no page text.

## Acceptance criteria

- [x] README and NOTICE updated; `docs/Archival names.md` linked
- [x] A test imports the fixtures and finds no page text in job logs

## Context

Phase 1.5 - PDF Tasks Breakdown item 23. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Constraints*; D26, D27.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: T02

**Design:**

- **Logs carry no page text (D26):** a job's log is whatever it prints (its stdout and stderr,
  tracebacks included). The terminal is also told each job's stages, and the job store keeps the
  latest progress message.
  - A test runs the whole path through the service: a PDF import with OCR (where the tools exist),
    reading by the stand-in model, embedding, then Ask and search.
  - It reads every job log, the terminal's output and every job's stored message, and finds none
    of the fixtures' page words (amounts, account numbers, words only on the pages) and no
    passage.
  - Anything that leaks is fixed where it is printed.
- **Documentation (D27):**
  - **README:**
    - PDF documents in *Part 1* (the collector, what happens to a PDF);
    - the box layout with `Documents/`;
    - *Where the project is* (PDF documents, search and Ask for documents);
    - *What you need*: PyMuPDF, installed with Caixa; OCRmyPDF, Tesseract with its languages and
      Ghostscript for scans; a local model for reading and Ask, and an embedding model for search
      by meaning;
    - the command-line examples (`caixa import pdf`, `caixa documents …`);
    - the worker's `documents.*` methods;
    - the project's folder.
  - **NOTICE:** the libraries and programs Caixa uses for PDFs, with their licences. PyMuPDF is
    AGPL-3.0, so a Caixa installed with it is used under the AGPL's terms, section 13 included.
    OCRmyPDF and pikepdf are MPL-2.0, Tesseract is Apache-2.0, and Ghostscript is AGPL-3.0 (run
    as a separate program).
  - **`docs/Documentation/Collector.md`:** a *PDF documents* section covering:
    - what it takes;
    - inspection, OCR, validation and archiving;
    - names and folders (linking `docs/Archival names.md`);
    - reading by a model and when a document waits for review;
    - corrections, tags and authors;
    - search, meaning and Ask;
    - people;
    - the settings;
    - privacy;
    - `caixa documents` and its subcommands;
    - known limitations.
  - The box README already has the `Documents/` line (ticket 04). A test checks the documents
    link to the naming convention.

### T01: No page text in the logs

- `tests/test_documents_privacy.py`; fixes where a leak is found.
- Verify: `python -m pytest -q tests/test_documents_privacy.py`
- [x] done

### T02: README, NOTICE and the collector's documentation

- `README.md`, `NOTICE`, `docs/Documentation/Collector.md`; `tests/test_naming.py` (the README
  and Collector.md link the naming convention; NOTICE names PyMuPDF's AGPL).
- Verify: `python -m pytest -q tests/test_naming.py tests/test_documents_privacy.py`
- [x] done

## Completion report

- **Outcome:**
  - **No page text in the logs:** a test runs the whole path through the service: an import with
    OCR, reading by the stand-in model, embedding, Ask and search. It finds none of the fixtures'
    page words in any job log, in the terminal's output, in the jobs' stored messages or in
    Python's logging. Planting a leak (printing each passage while embedding) makes it fail.
  - **Owner-only working copies (D26):** this had not been built. `Box.work_dir("documents")` is
    now made, or set again, as 0700, with a test.
  - **README:**
    - PDF documents in Part 1;
    - `Documents/` in the box layout;
    - *Where the project is*, with PDF documents and search and Ask for documents;
    - *What you need*: PyMuPDF and its licence, OCRmyPDF, Tesseract and Ghostscript, a local
      model and an embedding model;
    - command examples, the `documents.*` methods, and the project's folder.
  - **NOTICE:** PyMuPDF's AGPL-3.0 and what it means for a Caixa installed with it (section 13),
    and the licences of OCRmyPDF, pikepdf, Tesseract and Ghostscript.
  - **Collector.md:** a *PDF documents* section and two known limitations. It covers what the
    collector takes, each step, names and folders (linking `Archival names.md`), reading by a model
    and review, corrections, tags and authors, search, meaning and Ask, people, settings, privacy,
    and every `caixa documents` command.
  - The box README already had its `Documents/` line (ticket 04).
- **Files:**
  - new: `tests/test_documents_privacy.py`;
  - changed: `README.md`, `NOTICE`, `docs/Documentation/Collector.md`, `caixa/box.py`,
    `tests/test_naming.py`.
- **Errors:**
  - The privacy test first used the wrong shapes for `import.start` and `jobs.list`; corrected.
  - The documents promised owner-only working copies that did not exist yet; built.
- **Verify:**
  - `python -m pytest -q`: 1991 passed, 1 skipped.
  - Chattr: 916 passed.
  - vitest: 285 passed.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: ac28f0f..6e4ccd3 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** only the documents' working folder is owner-only. Other collectors' working folders
  keep their earlier permissions; that is outside this project.
- **Minor:** the licence notes in NOTICE describe the libraries' published licences. They are not
  legal advice; the maintainer may want to confirm them before a release.
- **Spec:** D26 and D27 met; every acceptance criterion met.
- **TDD:** the privacy test passed at once (it checks a property). It was proven able to fail by
  a planted leak. The permissions test was RED before GREEN.
- **Commits:** `20261124-23 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
