---
id: 20261125-03-one-document-s-error-no-longer-ends-an-import
title: One document's error no longer ends an import
type: bug
priority: high
status: in-progress
created: 2026-11-25
updated: 2026-11-25
closed:
notes: 'Hot fix: a model''s list-shaped evidence crashed an hour-long import at the
  reading stage'
parent:
depends_on:
- 20261125-01-declare-numpy-and-check-every-import-is-declared
subtasks:
- id: T01
  title: An answer of the wrong shape is a problem, not a crash
  status: done
- id: T02
  title: One document, or one stage, cannot end the import
  status: todo
plan_status: approved
current_task: T02
---
## Description

The maintainer's first real import (about 150 PDFs, about an hour) stopped in the reading stage
with:

```
File "caixa/documents/enrich.py", line 365, in _checked
    author["verified"], author["page"] = verify_quote(author.get("evidence"), …)
File "caixa/documents/enrich.py", line 275, in _plain
    decomposed = unicodedata.normalize("NFKD", text or "")
TypeError: normalize() argument 2 must be str, not list
```

**Causes:**

1. **An answer of the wrong shape got through.** A model answered an author's `evidence` with a
   list. `problems()` checks that `author` is an object with a string `name`, but not the types
   of `evidence` and `page`. The same gap exists for `date`, each of `other_dates`, and the
   type fields (`types.type_problems`). So the answer was passed as usable, and quote
   verification failed on it.
2. **One document's error ended the whole job.** `enrich_documents` catches only provider errors
   (`TranslationError`) around each document. Any other exception left the loop. It then left
   `PdfCollector.run` before embedding and drawing, so nothing was drawn, and the documents not
   yet read stayed where filing had put them, mostly in `Unrecognized/`. The same holds for the
   examining stage: an exception in one worker ends `pool.map`, and with it every file's
   examination.

**This ticket:** a wrong-shaped answer is treated like any other unusable answer (retried once
with what was wrong, then To review as `ai_unusable`). An unexpected error in one document is
recorded against that document while the run carries on. An unexpected error in a later stage
(reading, embedding) becomes a warning, and the pages are still drawn.

## Acceptance criteria

- [x] `problems()` reports an `evidence` that is not text or null, and a `page` that is not a
      whole number or null, for `author` and `date`. `type_problems` does the same for each type
      field. A model that answers so is asked again, naming the fault. A supporting date in
      `other_dates` of the wrong shape is left out, as non-objects already were: it decides
      nothing, so it does not cost the whole answer.
- [x] `verify_quote` never raises on a value that is not text; it reports it as not verified.
- [ ] An unexpected exception while reading one document marks that document `failed`. Its
      `enrich` run records the error's type and message, the traceback goes to the job log, and
      the next document is read. Two failures in a row still stop the stage as today, without
      ending the job.
- [ ] An unexpected exception in one file's examination reports that file as unreadable (named
      in the warnings with the error) and the other files are examined and filed.
- [ ] If the reading or embedding stage raises, the import still ends `done`: a warning says
      which stage stopped and how to carry on (`caixa documents enrich` or `embed`), and the
      document pages are drawn.
- [ ] Every test uses the synthetic family and the stand-in models.

## Context

- `caixa/documents/enrich.py` (`problems`, `verify_quote`, `_checked`, `classify_type`,
  `enrich_documents`); `caixa/documents/types.py` (`type_problems`);
  `caixa/collectors/pdfImport.py` (`examine`, `_examine_all`, `run`).
- Requirements: *Pipeline, statuses and failure*; *Enrichment, confidence and review* ("Validates
  each answer against its schema (one retry, then To review)").
- Precedent: `20261124-20` (a stalled embedding model no longer holds up a search).
- Found in the maintainer's first real import (2026-11-25); the job log's traceback is quoted
  above.

## Subtasks

- [x] T01 An answer of the wrong shape is a problem, not a crash
- [ ] T02 One document, or one stage, cannot end the import

## Implementation plan

Status: approved
Current task: T02

### T01: An answer of the wrong shape is a problem, not a crash

- **Files:** `caixa/documents/enrich.py`; `caixa/documents/types.py`;
  `tests/test_documents_enrich.py`; `tests/test_documents_types.py`.
- **RED:**
  - `problems()` on an answer whose `author.evidence` is a list, whose `date.page` is `"1"`,
    or whose `other_dates` holds a non-object, names each fault;
  - `type_problems` on a field whose `evidence` is a list names it;
  - `verify_quote(["a", "b"], 1, pages)` returns not verified instead of raising;
  - `classify` with a stand-in that first answers list-shaped evidence and then a good answer
    succeeds on the second attempt.
- **GREEN:** a small `_quote_problems(name, value)` shared by `problems` (author, date, each
  other date) and `type_problems` (each field): `evidence` must be a string or null, `page` an
  integer or null. `verify_quote` returns `(False, None)` for a quote that is not a string.
- **Verify:** `python -m pytest -q tests/test_documents_enrich.py tests/test_documents_types.py`,
  then the project verify command.

### T02: One document, or one stage, cannot end the import

- **Files:** `caixa/documents/enrich.py` (`enrich_documents`); `caixa/collectors/pdfImport.py`
  (`examine`, `run`); `tests/test_documents_enrich.py`; `tests/test_pdf_collector.py`.
- **RED:**
  - with `classify` patched to raise `TypeError` for the first document only, every other
    document is read, the first is `failed` with an `enrich` run naming `TypeError`, and the
    stage does not raise;
  - with `inspect_pdf` patched to raise for one fixture (one worker, so the patch applies), that
    file is named in the warnings and the rest are filed;
  - with `enrich_documents` patched to raise, the import returns a warning naming the reading
    stage, and the document pages are drawn;
  - the same for `embed_documents`.
- **GREEN:**
  - `enrich_documents`: each document's work in `try … except Exception`; the traceback is
    printed (it goes to the job log); status `failed` with `{"error": "<Type>: <message>"}` in
    the run; it counts towards the failures in a row.
  - `examine`: everything after the hash in `try … except Exception`, returning
    `Examined(…, error=f"it could not be examined ({Type}: {message})")`.
  - `run`: reading and embedding each in `try … except Exception` that prints the traceback and
    adds a warning; drawing always runs. `JobCancelled` still passes through (it is caught
    first and re-raised).
- **Verify:** `python -m pytest -q tests/test_documents_enrich.py tests/test_pdf_collector.py`,
  then the project verify command:
  `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`.

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

- 2026-11-25: Planned from the job log of the maintainer's first real import, under the
  maintainer's direction that long imports must fail gracefully.
- 2026-11-25: T01 done. RED reproduced the maintainer's `TypeError` through the stand-in
  (`list_evidence`). Changed from the plan: a malformed supporting date is dropped, not
  retried, because it decides nothing.
