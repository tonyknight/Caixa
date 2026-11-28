---
id: 20261128-06-prepare-as-the-dry-run
title: Prepare as the dry run
type: feature
priority: high
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: 'prepare is the import''s dry run: the preview at the box''s root'
parent:
depends_on:
- 20261128-02-reading-order-and-one-unreadable-text-rule
- 20261128-03-what-the-model-reads-and-is-told
- 20261128-04-author-knowledge-in-the-import
- 20261128-05-organized-names-in-the-import
subtasks: []
plan_status: done
current_task: T02
---
## Description

The last part of folding `prepare` into the import (D31): `caixa documents prepare` becomes the
import's dry run. It runs the import's own steps for both models, copies nothing, and writes
`(YYYY-MM-DD) PDF Import Preview.json` at the box's root, with both trees and the report.

## Acceptance criteria

- [x] `prepare <folder> --box <box> [--organized]` copies nothing; `--out` is gone and `--box` is
      required.
- [x] It uses the import's own steps (preprocessing, instructions, schema, quote checks, second
      look, author knowledge, organized names, filing rules) for Apple Intelligence and the
      endpoint in Settings. A model that cannot run is "not run". `prepare`'s own question and
      rules are removed.
- [x] It writes `(YYYY-MM-DD) PDF Import Preview.json` at the box's root, replacing that day's. It
      holds the two trees (`apple`, `local`), each file as `{from, name, why}`, and a `report`:
      the trees compared, the times, each file's preprocessing, the organized names, and what
      was learned. The command prints the readable report.
- [x] It writes nothing else into the box but the author-knowledge file with `--organized`; the
      sources are unchanged; nothing it made is left behind; the preview holds no page text.
- [x] A file already in the box shows where it is, "already in the box".

## Context

Requirements: D31 (*`prepare` is the import's dry run*), D28 and D30 (amended); Tasks Breakdown
31.

## Subtasks

## Implementation plan

Status: done
Current task: T02

**Design** (`caixa/documents/prepare.py`, rewritten):

- **One code path: the import itself.** For each model, `prepare` makes a throwaway box in a
  temporary folder, outside the real box, and seeds it from the real box:
  - a copy of its master database, taken with SQLite's backup, so a running Caixa is not
    disturbed;
  - its settings, with the run's model, and embedding left off;
  - its `author-knowledge.json`.

  Then it runs the PDF collector's own `run` on the folder (with `organized` when asked) inside a
  session log, and reads where each file went. The throwaway box is deleted in all cases. So the
  dry run is the import, rule for rule, and a file the box already has comes out "already in the
  box", at its place.
- **The models:** `models_for(box)` gives `apple`, the summaries' Apple Intelligence when it is
  available, and `local`, the endpoint and model in Settings when local. Either can be "not run".
  Tests pass `models={label: settings or None}`.
- **What each file says**, read from the throwaway box after the run:
  - its place, and `from` (its path relative to the folder);
  - `why`: the review's reasons in words, or "already in the box";
  - with `--organized`, `name`: `kept`, `date replaced` (with `from_date`, `to_date`), `no author`,
    `waiting` or `not organized`;
  - its preprocessing: the pages read by OCR (stored `ocr`), a cover sheet left out for the model
    (`enrich.is_cover`), and the look that found a fact (the session log's `propose` events).
- **The preview:** `(YYYY-MM-DD) PDF Import Preview.json` at the box's root:
  `{"apple": tree | null, "local": tree | null, "report": {…}}`. A tree nests folders as objects,
  down to each file's record. The report holds the run states and times, the same / different /
  filed-by-one comparison with each file's record, the organized counts, and what was learned.
  `report_text` gives the readable report, which the command prints.
- **The whitelist:** with `--organized`, the names' authors and tags are learned into the real
  box's `author-knowledge.json`, as before.
- **Removed:** `--out`, the two copied trees, `report.txt` and `report.jsonl`, and `prepare`'s own
  `INSTRUCTION`, `read_document`, `_decide`, filing and second look. Their tests are replaced by
  tests of the dry run; the import's own tests cover those rules.

### T01: The dry run, through the import

- `caixa/documents/prepare.py`, `tests/test_documents_prepare.py` (rewritten).
- Tests:
  - the sources and the box are unchanged but for the preview, and the throwaway boxes are gone;
  - two stand-in models that disagree give two places, and agreeing ones the same;
  - a model that cannot run is "not run", with a null tree;
  - a file already in the box is "already in the box", at its place;
  - each organized fixture is where its known answer says, in both trees;
  - a scanned page is reported as read by OCR, a cover sheet as left out, and an author found on
    the second look as such.
- Verify: `python -m pytest -q tests/test_documents_prepare.py`
- [x] done

### T02: The preview file, the report, the command and the documentation

- `caixa/documents/prepare.py`, `caixa/cli.py`, `tests/test_documents_prepare.py`,
  `docs/Documentation/Collector.md`.
- Tests:
  - the preview's name, place, shape and report;
  - a second run that day replaces it;
  - no page text in it;
  - `--organized` learns into the real box, and without it the knowledge is unchanged;
  - the command takes `--box` (required), no `--out`, and prints the report.
- Verify: `python -m pytest -q tests/test_documents_prepare.py tests/test_author_knowledge.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
  - **One code path:** `caixa documents prepare <folder> --box <box> [--organized]` is the PDF
    import's dry run. For each model it makes a throwaway box in a temporary folder, seeded from
    the real box:
    - its master, copied with SQLite's backup;
    - its settings with that model, and embedding off;
    - its author knowledge.

    It runs the PDF collector's own `run` there (with `organized` when asked), inside a session
    log, then reads each file's place, its reasons in words, its organized outcome, its OCR pages,
    whether its cover sheet was left out, and which look found its facts. The throwaway box is
    always deleted. A file the box already has shows where it is, "already in the box". A model
    that cannot run is "not run".
  - **The preview:** `(YYYY-MM-DD) PDF Import Preview.json` at the box's root, replaced by a
    second run that day. It holds the `apple` and `local` trees (folders nested, each file as
    `{from, name, why}`) and the `report`: run states, models and times, the same / different /
    filed-by-one comparison with every file's record, the organized counts, and what was learned.
    The command prints `report_text` and the preview's path.
  - **What it writes into the box:** the preview, and with `--organized` the whitelist in
    `.caixa/author-knowledge.json`. Nothing else.
  - **Removed:** `--out`, the copied trees, `report.txt` and `report.jsonl`, and `prepare`'s own
    instruction, reading, second look and filing.
- **Files:** `caixa/documents/prepare.py` (rewritten), `caixa/cli.py`,
  `tests/test_documents_prepare.py` (rewritten), `docs/Documentation/Collector.md`.
- **Errors:**
  - The command's call moved into the T01 commit, so no commit had a broken command or a mypy
    error.
  - Reading the real box's master read-only leaves SQLite's `-wal`/`-shm` side files, as the
    import's own preview does. The test ignores them, following ticket 04's precedent. Deleting
    them while a running Caixa may hold the database would be unsafe.
  - T02's tests passed at once: the preview and the whitelist were built in T01 along with the
    dry run. They are kept as the guard.
  - A first rewrite of the module was refused because black had touched the file; it was read
    again and written.
  - The old `prepare` tests checked behaviour this ticket removes; the rules they also covered
    are tested by the import's own tests.
- **Verify:**
  - `python -m pytest -q tests/test_documents_prepare.py tests/test_author_knowledge.py`:
    31 passed.
  - mypy: the 8 baseline errors.
  - The full suite was not run: the maintainer asked on 2026-11-28 that it run only when they say
    so. It is pending.

## Review

### 2026-11-28: 1c1c911..HEAD (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** each model's run repeats the whole import, OCR and drawing the document pages
  included, so a dry run takes about twice an import's time. That is the price of one code path.
  Drawing could be skipped in a throwaway box later.
- **Minor:** only the stand-in endpoints have run the dry run here. The Apple Intelligence run
  waits for the Mac.
- **Minor:** SQLite's side files in the real box, as above.
- **Spec:** D31's *`prepare` is the import's dry run* met, with D28 and D30 as amended; every
  acceptance criterion met.
- **TDD:** RED (`prepare() got an unexpected keyword argument 'models'`, all 16 T01 tests) before
  GREEN; T02's tests guard what T01 built.
- **Commits:** `20261128-06 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
