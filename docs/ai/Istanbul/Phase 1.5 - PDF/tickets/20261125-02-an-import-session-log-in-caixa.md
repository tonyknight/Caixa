---
id: 20261125-02-an-import-session-log-in-caixa
title: An import session log in .caixa
type: feature
priority: high
status: done
created: 2026-11-25
updated: 2026-11-25
closed: 2026-11-25
notes: 'Done: session logs for every document job, documents log command, review fixed'
parent:
depends_on:
- 20261125-01-declare-numpy-and-check-every-import-is-declared
- 20261125-03-one-document-s-error-no-longer-ends-an-import
subtasks:
- id: T01
  title: The session log
  status: done
- id: T02
  title: Examining, OCR, validation and filing, logged
  status: done
- id: T03
  title: Reading, reconciliation, embedding and drawing, logged
  status: done
- id: T04
  title: Finding the log, documentation and the privacy test
  status: done
plan_status: done
---
## Description

The maintainer's first real import (about 150 PDFs, about an hour) ended with more than 70% of
documents in `Documents/PDF/Unrecognized/`, although most had a text layer. Nothing showed why.
The job log (`.caixa/logs/job-<N>.log`) holds only what a stage printed and a traceback. The
master database keeps runs and proposals, but they have to be read in SQL.

This ticket adds an **import session log**: one file per document job inside `.caixa`, written as
the job runs. It says what each stage decided about each document and why, so a run can be
understood afterwards, including one that stopped. It is also the evidence for the planned
bake-off between Apple Intelligence and the local Qwen model.

**What the log must answer, per document:**

- What did examination find? Pages by class, and whether each needs OCR.
- Did OCR run, how, and did validation pass?
- Where was it filed at import, and why? What the filename and the properties said; why it
  went to Unrecognized; duplicate, locked or unreadable.
- Did the model read it?
  - which provider and model, and why that one;
  - how much text it was given against the budget;
  - each attempt and what was wrong with it, and the time taken;
  - what it proposed, and whether each quote was found on its page.
- What did reconciliation decide, rule by rule?
  - the date: agrees, explained or conflicting;
  - the author: known, alias, verified or conflicting;
  - the type and the title;
  - confident and moved (from where to where), or To review with its reasons.
- Were its passages embedded? Were the pages drawn?

**Per session:**

- a header with Caixa's version, the Python running it (`sys.executable`), the package and tool
  versions, and the settings that steer decisions (provider and model, embedding model, workers,
  OCR on or off and its languages);
- a closing summary: counts per outcome, a tally of review reasons ("Unrecognized 104:
  `no_author` 41, `unverified_date` 30, `ai_unusable` 22, …"), time per stage, and any error
  with its stage, document and traceback.

**Out of scope (separate tickets, to plan):**

- surviving a failure partway through a long run (one document's or one stage's error ending
  the whole job);
- the Apple Intelligence and Qwen bake-off;
- changing any decision rule.

This ticket only makes the decisions visible.

## Decisions (maintainer, 2026-11-25)

1. **D26 privacy**, amended as proposed. The Requirements said: *"No page text or extracted value
   goes into a log."* A log that explains decisions needs extracted values (author, date,
   title), so D26 now reads:
   - **Always allowed** in the session log: extracted values (type, category, title, author,
     date and its kind, tags); review reasons; page numbers; whether each quote was verified;
     sizes, times and errors.
   - **Never:** page text, passages, or summaries.
   - **Opt-in only** (a setting, off by default, for the bake-off period): the evidence quotes
     and the model's raw replies.
   - The file is owner-only (0600, in an owner-only folder). The job log, the terminal and the
     job store keep D26 as it is: no page text and no extracted value.

   The master database already holds all of these values and quotes, in the same `.caixa`
   folder.
2. **Where it lives and what it is called**, as proposed:
   `.caixa/logs/sessions/<YYYY-MM-DD HH-MM-SS> <job kind> (job <N>).log`, for example
   `2026-11-25 00-20-14 PDF import (job 12).log`. A `.jsonl` twin with the same events, one JSON
   object per line, is there for scoring the bake-off. Sessions are kept until the owner deletes
   them; undoing an import leaves its log.

## Acceptance criteria

- [x] Every document job (PDF import, reprocess, enrich, embed) writes one session log, opened
      before its first stage, and closed with a summary even when the job fails or is
      cancelled. A failure is logged with its stage, the document when known, and its traceback.
- [x] The header names Caixa's version, `sys.executable`, the versions of numpy, PyMuPDF,
      pikepdf, OCRmyPDF and Tesseract (with its languages), and the deciding settings.
- [x] For each document the log says what examination, OCR, validation, filing, reading,
      reconciliation and embedding decided and why, as listed in the description. Each line
      names the document as `[n/total] <original filename>`.
- [x] A document left in `Unrecognized/` has a line saying why: at filing (what the filename and
      the properties lacked), and after reading (its reconciliation reasons, or why it was never
      read).
- [x] The closing summary counts documents per outcome, tallies review reasons, gives time per
      stage, and lists the errors.
- [x] The log is written line by line (readable while the job runs, with `tail -f`), and the file
      is owner-only.
- [x] The `.jsonl` twin holds the same events, one JSON object per line, with a stable `event`
      name and fields.
- [x] The end-of-import report (window and command line) names the session log.
      `caixa documents log [--job N]` prints a session (the latest by default).
- [x] The privacy test still finds no page text in job logs, the terminal or the job store; and
      no page text, passage or summary in the session log. It finds quotes and raw replies only
      when the opt-in setting is on (per decision 1).
- [x] D26 in the Requirements and the privacy section of `docs/Documentation/Collector.md` say
      what the session log holds.

## Context

- **Where jobs run:** `caixa/service.py`:
  - `_run_job` opens `job-<N>.log` and redirects stdout and stderr into it;
  - `_execute_job` handles `documents-reprocess`, `documents-enrich` and `documents-embed`;
  - the collector's `run` handles `import`.
  The window and `caixa import pdf` both start jobs here.
- **Stages:**
  - `caixa/collectors/pdfImport.py` (`examine` in spawned workers, `_examine_all`, `run`);
  - `caixa/documents/importing.py` (`import_examined`, `_record_evidence`);
  - `caixa/documents/pdf/process.py`, `ocr.py`, `validate.py`;
  - `caixa/documents/evidence.py` (`provisional_facts`), `archive.py` (`place`);
  - `caixa/documents/enrich.py` (`provider`, `prepare`, `ask`, `enrich_documents`);
  - `caixa/documents/reconcile.py` (`decide`, `apply_decision`);
  - `caixa/documents/embeddings.py`, `pages.py` (`draw_documents`).
- **Worker processes:** `examine` runs in other processes and cannot write to the parent's log.
  Its results already carry the inspection, OCR outcome and validation report. They gain their
  timings, and the parent logs them when it files each document.
- **Precedents:** `20261123-10` (each redraw step ends with a line saying what it did and how
  long it took); `20261124-23` (the privacy test and D26).
- **Requirements:** D26 (privacy), *Pipeline, statuses and failure*, *Enrichment, confidence and
  review*.

## Subtasks

- [x] T01 The session log
- [x] T02 Examining, OCR, validation and filing, logged
- [x] T03 Reading, reconciliation, embedding and drawing, logged
- [x] T04 Finding the log, documentation and the privacy test

## Implementation plan

Status: done
Current task: 

**Design:**

- **`caixa/session_log.py`** (generic, so mail and messages can use it later):
  - `SessionLog(box, job, kind)` writes the text file and its `.jsonl` twin, line-buffered, mode
    0600, in `.caixa/logs/sessions/` (0700).
  - `event(stage, name, document=None, **fields)` writes one human line and one JSON object.
  - `error(stage, exc, document=None)` writes the type, the message and the traceback.
  - `close(status)` writes the summary.
  - The open session is held in a `contextvars.ContextVar`. Stages call
    `session_log.current().event(…)` without new parameters, and get a no-op log when no session
    is open (tests, library use).
- **Privacy in one place:** fields are declared by kind:
  - *value*: allowed;
  - *quote* and *reply*: written only when the opt-in setting is on;
  - *text*: refused by `event` itself (a test fails if any caller passes page text).
- **A text line looks like this** (synthetic family):
  ```
  00:58:40 file    [17/212] scan_0042.pdf → Documents/PDF/Unrecognized/scan_0042.pdf · filename: nothing (a scanner's name) · properties: no author, no date
  01:02:11 read    [17/212] scan_0042.pdf · Apple Intelligence · 5,980 of 6,000 characters (pages 1, 2, 3) · attempt 1: not JSON · attempt 2: ok · 41.2 s
  01:02:11 propose [17/212] scan_0042.pdf · type bill · author "EDP Comercial" (quote found, p1) · date 2024-11-30 issue (quote not found)
  01:02:11 decide  [17/212] scan_0042.pdf · To review: unverified_date · stays in Unrecognized
  ```

### T01: The session log

- **Files:** `caixa/session_log.py` (new); `caixa/service.py` (`_run_job` opens a session for
  `import`, `documents-reprocess`, `documents-enrich` and `documents-embed`, and closes it in a
  `finally` with the job's status; an exception is logged with `error` before the job is marked
  failed); `caixa/settings.py` (the opt-in setting, if decision 1 keeps it);
  `tests/test_session_log.py` (new).
- **RED:**
  - a session writes its header (version, `sys.executable`, packages, settings);
  - lines appear before `close` (line-buffered);
  - the file and folder are owner-only;
  - the `.jsonl` twin parses line by line;
  - `event` refuses a *text* field; *quote* fields are dropped unless the setting is on;
  - a job that raises still gets a closed session with the error and its traceback;
  - `current()` outside a session is a no-op.
- **GREEN:** as designed.
- **Verify:** `python -m pytest -q tests/test_session_log.py`, then the project verify command.
- [x] done
### T02: Examining, OCR, validation and filing, logged

- **Files:** `caixa/collectors/pdfImport.py` (`Examined` gains `seconds` and OCR and validation
  timings; `run` logs the files found, then each stage's start and end with counts and time);
  `caixa/documents/importing.py` (`import_examined` logs, per document:
  - pages by class and how many need OCR;
  - OCR's mode, status and error;
  - validation passed or failed, with the failing checks;
  - what the filename and the properties said, and the facts it was filed by;
  - where it went, and why it went to Unrecognized;
  - duplicate, probable duplicate, locked or unreadable);
  `caixa/documents/reprocess.py` (the same lines for a reprocess); `tests/test_pdf_collector.py`
  or a new `tests/test_session_log_import.py`.
- **RED:** importing the synthetic family with the stand-in model off expects:
  - one `file` event per fixture;
  - a reason line for each fixture the known answers place in Unrecognized;
  - an `ocr` and a `validate` event for the scanned fixtures (when the OCR tools exist; skipped
    with a reason otherwise);
  - the damaged and locked fixtures named as such.
- **GREEN:** the events above, written by the parent as it files each document.
- **Verify:** `python -m pytest -q tests/test_session_log_import.py tests/test_pdf_collector.py
  tests/test_pdf_reprocess.py`, then the project verify command.
- [x] done
### T03: Reading, reconciliation, embedding and drawing, logged

- **Files:**
  - `caixa/documents/enrich.py`:
    - `provider` logs the choice and why (Automatic chose Apple; Apple unavailable and why; an
      endpoint refused as remote; reading off);
    - `ask` logs each attempt (characters sent against the budget, pages included, time, the
      problem found, and the raw reply when opted in);
    - `enrich_documents` logs each document's proposals with quote verification, and the stop
      after two failures in a row with both errors;
  - `caixa/documents/reconcile.py`: `decide` records each rule's outcome on the `Decision` (a
    `trail` list); `reconcile_document` logs the trail, then confident with the move, or review
    with its reasons;
  - `caixa/documents/embeddings.py`: the model, then documents, passages and failures per batch;
  - `caixa/documents/pages.py`: pages written;
  - tests: `tests/test_documents_enrich.py`, `tests/test_documents_reconcile.py`, or a new
    `tests/test_session_log_reading.py`.
- **RED:** with the stand-in model:
  - a descriptive fixture logs `read`, `propose` and `decide confident` with its move;
  - the misleading-filename fixture logs `conflict:date` or `conflict:author` with both values;
  - a stand-in that answers non-JSON logs two attempts and `ai_unusable`;
  - two provider failures log the stop and how many documents wait;
  - the closing summary's tally matches the review reasons in the master.
- **GREEN:** as listed. `Decision.trail` is the only change to `reconcile`; no rule changes.
- **Verify:** `python -m pytest -q tests/test_session_log_reading.py
  tests/test_documents_enrich.py tests/test_documents_reconcile.py tests/test_documents_semantic.py`,
  then the project verify command.
- [x] done
### T04: Finding the log, documentation and the privacy test

- **Files:**
  - `caixa/service.py`: the job's result carries `session_log`, its path relative to the box;
    the end-of-import report shows it;
  - `caixa/cli.py`: `caixa documents log [--job N] [--json]`;
  - `web/src/…`: the import report shows the path, and the opt-in setting appears in Settings,
    Documents, if decision 1 keeps it; the built window rebuilt;
  - `tests/test_documents_privacy.py`: extended to the session log;
  - `docs/Documentation/Collector.md` (privacy, and *Reading a session log*);
  - the Requirements: D26 amended as decided, with the date.
- **RED:**
  - the privacy test runs the full path, finds no page text, passage or summary in the session
    log, and finds quotes only with the setting on;
  - a CLI test prints the latest session;
  - a web test shows the path in the report.
- **GREEN:** as listed.
- **Verify:** `python -m pytest -q tests/test_documents_privacy.py`,
  `pnpm --dir web run build`, then the project verify command:
  `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`.
- [x] done
## Completion report

- **Outcome:**
  - Every PDF import and every documents `enrich`, `embed` and `reprocess` job writes an
    owner-only session log in `.caixa/logs/sessions/`, with a `.jsonl` twin. It is opened before
    the first stage and closed with a summary when the job is done, cancelled or failed.
  - The header gives the version, `sys.executable`, the packages, Tesseract with its languages,
    and the deciding settings. Each document gets a line per stage (`examine`, `ocr`,
    `validate`, `file`, `read`, `propose`, `decide`, `embed`), named `[n/total] filename`.
  - A document in Unrecognized says why at filing (`why: no_author`, …) and after reading (its
    review reasons). The summary counts outcomes, tallies reasons, times each stage and lists
    errors.
  - The job's result names the log; the command line's reports and the window's import report
    show it. `caixa documents log [--job N] [--json]` (and `documents.log`) prints it. A failed
    document job points to it.
  - On the synthetic family the log shows that most documents wait in Unrecognized at filing
    because their file names give no author; only the model's reading supplies one.
- **Files:** `caixa/session_log.py` (new); `caixa/service.py`; `caixa/cli.py`;
  `caixa/settings.py` (`documents.log_quotes`, off); `caixa/collectors/pdfImport.py`;
  `caixa/documents/importing.py`, `reprocess.py`, `enrich.py`, `reconcile.py` (`Decision.trail`),
  `embeddings.py`, `pages.py`, `evidence.py` (`lacking`), `pdf/process.py` (timings);
  `web/src/client/api.ts`, `locales.ts`, `pages/ImportPage.tsx`; the built window;
  `docs/Documentation/Collector.md`; the Requirements (D26 amended);
  `tests/test_session_log.py`, `test_session_log_import.py`, `test_session_log_reading.py` (new),
  `test_documents_privacy.py`, `test_documents_evidence.py`, `test_worker_protocol.py`,
  `web/tests/import-page.test.tsx`.
- **Errors:**
  - A type's own fields (amounts, account numbers) are logged by name and whether found, not by
    value: D26's always-allowed values are type, category, title, author, date and tags.
  - The privacy extension passed on first run (T01–T03 already met it); it stays as the guard.
  - Failed and cancelled jobs do not carry `session_log` in their result (the Jobs page reads
    any result as import counts); `caixa documents log --job N` finds their log.
  - Known limit: `examine` runs in worker processes; the parent logs its results, timings and
    errors as it files each document.
  - Review fixes (see *Review*): a log that cannot be written stops quietly; an error that ends
    the job names its stage and document, once; replies are logged without their summaries.
- **Verify:** project verify command after the review fixes: 2049 passed, 10 failed (the known
  Chattr failures); black only the known `tests/test_mail_sent_and_received.py`; mypy the 8 known
  errors; web 286 passed.

## Review

2026-11-25, a fresh reviewer on `716cf8e..862ae97`. Verdict before fixes: no Critical, three
Important, five Minor. The three Important findings are fixed (RED then GREEN, four new tests):

- *Important, fixed:* a write that failed (a full disk) would have raised into the stage. Now
  `SessionLog` stops writing, says once in the job log why, and the job goes on. The two files
  are closed even when the summary or the header fails.
- *Important, fixed:* an error that ended the job was logged as `in job:`. `stage()` and the new
  `on(document)` now remember where it left, and an error already logged where it happened is
  not logged twice.
- *Important, fixed:* with the opt-in on, a raw reply carried the model's summary. A reply that
  parses is logged without it; one that does not parse is kept as it came.
- *Minor, fixed:* `filename_conflicts` keeps only named words (year, type, author…) without the
  opt-in, anything longer becomes a quote. A failed `caixa import pdf` points to
  `caixa documents log --job N`. `contextlib.nullcontext` replaces `_no_session`.
- *Minor, left:* reading, deciding and embedding number documents within their own set, not the
  import's, and the `.jsonl` carries no item id. The standalone enrich, embed and reprocess jobs
  report `stages: none`. `evidence.lacking` repeats the rules of `provisional_facts`. Candidates
  for the bake-off ticket, which needs the item id to score by document.
- *Kept by design:* a field named for page text is refused with an error, not dropped: callers
  are fixed by the tests, which is the guard D26 asked for.

## Notes

Append-only running log. Each entry dated.

- 2026-11-25: Planned after the maintainer's first real import (about 150 PDFs, more than 70% in
  Unrecognized, stopped by a missing numpy). Waiting for the maintainer on D26 and the file name
  before code.
- 2026-11-25: Approved: D26 amended (values always; quotes and raw replies opt-in; never page
  text, passages or summaries) and the sessions folder as proposed. Runs after `20261125-03`, so
  the log records the failures that ticket catches.

### 2026-11-25
T01 done: caixa/session_log.py, opened by the service for PDF import and documents enrich/embed/reprocess jobs; documents.log_quotes setting (off). Files of the other jobs are named for their commands (documents enrich, …). Checked end to end on the synthetic family (header and summary; per-document lines come in T02 and T03).

### 2026-11-25
T02 done. On the synthetic family the log shows why files wait in Unrecognized at filing: most filenames give no author (why: no_author), which only the model's reading can supply. Outcomes are keyed by item id, so a later stage replaces a document's filing outcome.

### 2026-11-25
T03 done. A type's own fields (amounts, account and policy numbers) are logged by name and whether found, not by value: D26's always-allowed list names type, category, title, author, date and tags only. The privacy guard caught a field named passages (a count) in embedding; renamed passage_count.

### 2026-11-25
T04 done and reviewed: the job's result and reports name the session log; caixa documents log prints it; the privacy test covers session logs. Review: three Important findings fixed (unwritable log, job-level error context, summaries in opted-in replies).
