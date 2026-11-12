---
id: 20261112-07-hot-fix-undo-the-last-import-and-run-an-import
title: 'Hot fix: undo the last import and run an import again'
type: feature
priority: medium
status: done
created: 2026-11-12
updated: 2026-11-12
closed: 2026-11-12
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

While the importers are still being improved, the maintainer wants to take an import back and run it again with the new code, and asked for ideas. Built: undo the last import, and run any earlier import again.

## Acceptance criteria

- [x] Undoing an import leaves the box exactly as it was before it: the same visible files (by content) and the same rows in the master database (tested by comparing both).
- [x] Undo goes back one import at a time, newest first; the last 3 can be undone.
- [x] Naming people after the import is undone with it, their files go back to where they were, and the person is told how many such changes will go.
- [x] Undo is refused while an import runs and in a read-only box; it asks twice in the browser and once on the command line.
- [x] Any earlier import can be run again with the same source and options (`import.again`, `caixa again N`, Run again in Jobs).
- [x] The export is never touched.

## Context

caixa/undo.py. Before an import the service copies Caixa's state (the master database, the list of pages, each collector's databases and settings; SQLite's backup API, so the copy is consistent) into `.caixa/undo/<job>/` and lists the box's visible files. Every later move of a file (reported by a collector in `RunResult.moved`) is noted on the newest snapshot. Undo runs as a job: put moved files back, delete files that were not there before, restore the state, redraw the pages. The append-only change log is restored with the database, so an undone import leaves no trace in it; nothing reads the log yet. When the personal-model work starts reading it, undo will need to write a 'removed' entry instead.

## Subtasks

- [x] Tests (tests/test_undo.py): one import, two imports, people named in between, run again, refusals, retention.
- [x] `caixa/undo.py`: begin, finish, note_moves, note_people_change, latest, restore.
- [x] Service: snapshots around import jobs, the `undo` job kind, `import.undo.info`, `import.undo`, `import.again`; `RunResult.moved`.
- [x] `caixa undo` and `caixa again`.
- [x] Browser: the Undo card and Run again in Jobs; an 'Undone' mark; tests and a browser test.
- [x] Collector.md: 'Undoing an import, and running one again'.

## Implementation plan

Status: done
Current task:

### T01: Tests (tests/test_undo.py): one import, two imports, people named in between, run again, refusals, retention.
### T02: `caixa/undo.py`: begin, finish, note_moves, note_people_change, latest, restore.
### T03: Service: snapshots around import jobs, the `undo` job kind, `import.undo.info`, `import.undo`, `import.again`; `RunResult.moved`.
### T04: `caixa undo` and `caixa again`.
### T05: Browser: the Undo card and Run again in Jobs; an 'Undone' mark; tests and a browser test.
### T06: Collector.md: 'Undoing an import, and running one again'.

## Completion report

- **Outcome:** Undo the last import and Run again, in the browser and on the command line.
- **Files:** caixa/undo.py, caixa/service.py, caixa/cli.py, caixa/collectors/{base,chattr}.py, harness/src/client/{api.ts,store.ts,locales.ts,pages/JobsPage.tsx}, tests/test_undo.py, tests/test_cli_commands.py, harness/tests/{jobs-page.test.tsx,e2e-voicemail.test.ts}, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1090 passed, 6 skipped; harness 255 passed; black, mypy, tsc clean.

## Review

Minors. (1) A snapshot copies Caixa's databases, so three snapshots of a very large archive take real disk space and some seconds each; the number kept (3) is a constant, `undo.KEEP`. NEEDS MAINTAINER CONFIRMATION of that number. (2) An import that fails part-way is offered for undo like any other, but that path has no test of its own. (3) Undo removes the import from the change log (see Context).

## Notes

- 2026-11-12: Other approaches considered and left: rebuilding the whole box by replaying every recorded import (needs every source to still be where it was), and removing one source's data across imports (cannot restore items a later import changed).
