---
id: 20261128-05-organized-names-in-the-import
title: Organized names in the import
type: feature
priority: high
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: 'organized option: owners'' names kept through filing, reading and corrections'
parent:
depends_on:
- 20261128-04-author-knowledge-in-the-import
- 20261128-01-organized-file-names
subtasks: []
plan_status: done
current_task: T03
---
## Description

The fourth part of folding `prepare` into the import (D31): organized file names (D30) as an
option of the PDF import, kept through filing, reading, reading again and corrections.

## Acceptance criteria

- [x] The PDF collector has an `organized` option: a checkbox in the import wizard and
      `--option organized=true`.
- [x] At filing, an organized name is kept under its year and author. A name with no author, or
      an impossible date, waits in `Unrecognized/` under its name. The owner's tags are Caixa's
      tags. The authors and tags learned are added to the whitelist.
- [x] At reading, the model adds the type, category, summary and its own tags. It never changes
      the file name, the subject, the author or the owner's tags.
- [x] Only an impossible date, or one the page contradicts, is replaced; only the date part of
      the name changes. "Contradicts" means the model's naming date has its quote found on the
      page, is not compatible with the name's date, and the name's date is nowhere on the page.
- [x] A name with no author takes the model's author (quote found, through author knowledge) for
      its folder; the name stays.
- [x] Reading again keeps the name. A correction of the date, subject or author rewrites that
      part of the owner's name, in the owner's pattern.
- [x] Without the option, organized names are imported as before.

## Context

Requirements: D31 (*Organized names in the import*), D30; Tasks Breakdown 30.

## Subtasks

## Implementation plan

Status: done
Current task: T03

**Design:**

- **The option** (`pdfImport.py`): `organized`, a boolean, default false, titled "My PDFs are
  named (date) Subject (Author) [Tag]". The wizard draws a boolean as a checkbox already.
- **At filing** (`importing.import_examined(…, organized=False)`): a matching name
  (`organized.read_organized`) is filed by `Facts(date, subject, author)`. The date is left out
  when impossible. The author is the owner's, never put through the lessons. The owner's file
  name is kept (`archive.place(…, filename=…)`).
  - The document gets a field `organized` (source `original_filename`, value the name).
  - The owner's tags go in as `user_verified` tags (`records.set_tags`), which a reading never
    takes away.
  - At the end, `author_knowledge.learn_organized` adds the names' authors and tags to the
    whitelist.
- **At reading and after** (`reconcile.decide`): a document with an `organized` field is decided
  by `_decide_organized`:
  - type and category: the owner's, else the model's;
  - title: the owner's, else the subject;
  - author: the owner's, else the name's, else the model's when verified (quote found or a known
    author) and through the lessons. That last one chooses the folder only;
  - date: the owner's, else the name's, replaced by the model's verified date only when the
    name's is impossible, or when the model's is not `compatible` and the name's is not
    `on_page`. An impossible date with no verified page date gives `no_date`;
  - the file name: the name with only its date replaced (`with_date`). A correction of the
    subject or the author rewrites the name in the owner's pattern (`organized.compose`); an
    author is added in brackets when the owner gives one to a name that had none;
  - the filename's own evidence fields do not conflict: the owner's name is the truth. An
    unusable reading does not block a name that is complete.

  `Decision.organized` carries the name. `apply_decision` files by it (`place(…, filename=…)`),
  and every step goes in the session log's trail.
- **Fixtures:** `organized_family.py` gains each model answer's quotes and a stand-in endpoint,
  `respond`, answering the import's schema from the fixtures' `apple` answers.

### T01: The option and filing at import

- `caixa/collectors/pdfImport.py`, `caixa/documents/importing.py`, `caixa/documents/archive.py`,
  `tests/fixtures/organized_family.py`, `tests/test_organized_import.py` (new).
- Tests:
  - the option is declared;
  - with no model, organized names are kept under year and author, a name with no author and an
    impossible date wait under their names;
  - the owner's tags are `user_verified` tags;
  - the whitelist learns;
  - a non-matching name is imported as before;
  - without the option, organized names get Caixa's naming as before.
- Verify: `python -m pytest -q tests/test_organized_import.py tests/test_pdf_collector.py`
- [x] done

### T02: Reading keeps the name: the decision, the date rule, corrections

- `caixa/documents/reconcile.py`, `caixa/documents/organized.py` (`compose`),
  `caixa/documents/corrections.py`, `tests/test_organized_import.py`,
  `tests/test_organized_names.py`.
- Tests, with the stand-in endpoint:
  - every fixture ends where its known answer says;
  - the model's type, category, summary and tags are added beside the owner's;
  - reading again keeps every name;
  - a correction of the subject, the author or the date rewrites that part of the name;
  - `compose`.
- Verify: `python -m pytest -q tests/test_organized_import.py tests/test_organized_names.py tests/test_documents_reconcile.py tests/test_documents_corrections.py`
- [x] done

### T03: The wizard and the documentation

- `web/tests/import-page.test.tsx`, `docs/Documentation/Collector.md`.
- Tests: the wizard shows the PDF collector's `organized` option as a checkbox, and sends it with
  the import.
- Verify: `pnpm --dir web exec vitest run tests/import-page.test.tsx && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
  - **The option:** the PDF collector's `organized` option, "My PDFs are named (date) Subject
    (Author) [Tag]", is a checkbox in the wizard and `--option organized=true` on the command line
    (tried on a scratch box).
  - **At filing:** a matching name is filed under its own name, in its year and author's folder.
    An impossible date, or no author, waits in `Unrecognized/` under the name. The document is
    marked with an `organized` field, and its tags are the owner's (`user_verified`, never taken
    away by a reading). The names' authors and tags join the whitelist.
  - **At reading and after:** `reconcile._decide_organized` decides such a document.
    - The model adds the type and the category, and the summary and its tags are recorded beside
      the owner's.
    - The title is the subject and the author is the name's.
    - The date is replaced only when it is impossible, or when the model's verified date is not
      compatible with it and the name's date is nowhere on the page. Only the date part of the
      name changes.
    - A name with no author takes the model's verified author (quote found or a known author,
      through the lessons) for its folder.
    - `apply_decision` files by the owner's name. Every step goes in the session log's trail.
  - **Corrections:** a correction of the subject or the author rewrites the name in the owner's
    pattern (`organized.compose`), and a correction of the date rewrites only the date. An author
    given to a name that had none is added in brackets. Reading again keeps every name.
  - Every fixture of the organized family ends in the import where its known answer says.
- **Files:**
  - new: `tests/test_organized_import.py`;
  - changed: `caixa/collectors/pdfImport.py`, `caixa/documents/importing.py`,
    `caixa/documents/archive.py` (`place(…, filename=…)`), `caixa/documents/reconcile.py`
    (`_decide_organized`, `Decision.organized`), `caixa/documents/organized.py` (`compose`),
    `tests/fixtures/organized_family.py` (quotes, `respond`), `tests/test_organized_names.py`,
    `web/tests/import-page.test.tsx`, `docs/Documentation/Collector.md`.
- **Errors:**
  - The T01 commit first went in with five new mypy errors: the check and the commit ran in one
    command. They were fixed and the unpushed commit amended. mypy now runs as its own step
    before each commit.
  - The wizard test passed at once: the wizard draws any yes/no option as a checkbox. It is kept
    as the guard on the real option.
  - `corrections.py` needed no change: corrections reach the organized decision through `decide`.
- **Verify:**
  - `python -m pytest -q` (with `PYTHONUNBUFFERED=1`): 2,208 passed.
  - vitest: 287 passed.
  - mypy: the 8 baseline errors.

## Review

### 2026-11-28: df7402d..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** `compose` writes single spaces between the parts, so a corrected name with unusual
  spacing comes back tidied. A date-only change uses `with_date` and leaves the rest exactly as
  written.
- **Minor:** a document imported without the option cannot become organized later. Importing it
  again with the option is "already in the box", so a later command would be needed.
- **Minor:** an organized document still waiting (no author, or an impossible date with no page
  date) keeps the model's type and summary off its record until it is filed, as any document
  waiting for review does.
- **Spec:** D31's *Organized names in the import* and D30 met; every acceptance criterion met;
  `corrections.py` named in the plan needed no change.
- **TDD:** RED (no option; a reading renaming organized files to Caixa's form; no `compose`)
  before each GREEN.
- **Commits:** `20261128-05 T01/T02/T03: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
