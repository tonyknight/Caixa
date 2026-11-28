---
id: 20261128-03-what-the-model-reads-and-is-told
title: What the model reads and is told
type: feature
priority: high
status: in-progress
created: 2026-11-28
updated: 2026-11-28
closed:
notes: ''
parent:
depends_on:
- 20261128-02-reading-order-and-one-unreadable-text-rule
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The second part of folding `prepare` into the import (D31): what the import's model reads, what
it is told, and a second look when the author or the date is missing.

## Acceptance criteria

- [ ] A cover sheet is skipped for the model only: it reads the first two real pages and the
      last. The cover stays in the archive and in search.
- [ ] The top of the first page and the bottom of the last are never cut to fit the budget.
- [ ] The instruction says the author is who the page names as the sender, never a software
      name such as `Brite:Bill`. A program name is filtered from the model's answer.
- [ ] When the answer has no author or no naming date, the model is asked once more with the
      bottom of the last page, with the same schema and quote check. What is still missing goes
      to `Unrecognized/`.
- [ ] The session log says which look found each fact.

## Context

Requirements: D31 (*What the model reads and is told*); Tasks Breakdown 28.

## Subtasks

## Implementation plan

Status: in-progress
Current task: T02

**Design** (`caixa/documents/enrich.py`, `caixa/documents/evidence.py`):

- **Cover sheet:** `is_cover(text)`, the rule `prepare` uses (a fax, transmission or scan cover,
  or fewer than 40 letters), applies to page 1 of a document of two pages or more.
  `pages_sent` then gives the first two real pages and the last. The header says the cover was
  left out. The pages are stored and searched as before, and quotes are checked against every
  page.
- **Top and bottom:** each sent page is cut to its share of the budget. The first page keeps its
  start, as now. The last page keeps its end: when it is too long, its start is cut and its last
  part (up to 600 characters) is kept whole. A one-page document keeps both its top and bottom.
- **Software names** (one list, `evidence.PROGRAM_NAMES`): whole program names (`Brite:Bill`,
  `Brite`, `Pro API`, `Pro Document`, `Adobe Acrobat`, `Acrobat Distiller`, `Microsoft Word`,
  `Microsoft Excel`, `LibreOffice`, `OpenOffice`, `Ghostscript`, `Quartz PDFContext`, `ScanSnap`,
  `Epson Scan`, `PDF Printer` and the like). `evidence.is_program(name)` is a whole-name match.
  - The PDF's properties are filtered by it as well as by today's broader word test.
  - The model's author is dropped only on a whole-name match, so a real sender such as
    "Microsoft", on a Microsoft invoice, is kept.
  - `prepare._software` uses the same list.
  - The instruction adds: "The author is who the page names as the sender; never the program
    that made the PDF, such as Brite:Bill."
- **Second look:** `read(client, document, budget)` is `classify` and, when the answer has no
  author name or no date value, one more `ask` with the same instruction, schema and checks. Its
  prompt is the header plus the bottom of the last page ("Second look: only the bottom of the
  last page is given."). What it finds fills only what is missing, its quotes verified against
  the pages. `Classified.looks` says `first` or `bottom` per fact. `_read_one` calls `read`.
- **Session log:** the `read` event carries every attempt, including the second look's. The
  `propose` event gains `author_look` and `date_look`.

### T01: What the model reads and is told

- `caixa/documents/enrich.py`, `caixa/documents/evidence.py`, `caixa/documents/prepare.py`,
  `tests/test_documents_enrich.py`, `tests/test_documents_evidence.py`.
- Tests:
  - a cover sheet is left out of what is sent and the header says so; a one-page document is
    sent whole;
  - the bottom of a long last page is kept within the budget;
  - the instruction names software;
  - `is_program`: whole names only ("Brite:Bill" yes, "Microsoft" no);
  - a property author "Brite:Bill" is filtered;
  - a model author "Brite:Bill" is dropped and "Microsoft" kept.
- Verify: `python -m pytest -q tests/test_documents_enrich.py tests/test_documents_evidence.py tests/test_documents_prepare.py`
- [x] done

### T02: The second look

- `caixa/documents/enrich.py`, `tests/test_documents_enrich.py`.
- Tests:
  - an author written only at the bottom of the last page is found on the second look;
  - a complete first answer asks no second time;
  - what the second look finds fills only what is missing;
  - what is still missing leaves the document in `Unrecognized/`;
  - the session log names the looks;
  - an import with the stand-in model reads as before.
- Verify: `python -m pytest -q tests/test_documents_enrich.py tests/test_session_log_reading.py tests/test_documents_reconcile.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
