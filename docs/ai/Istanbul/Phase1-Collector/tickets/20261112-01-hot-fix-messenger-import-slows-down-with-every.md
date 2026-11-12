---
id: 20261112-01-hot-fix-messenger-import-slows-down-with-every
title: 'Hot fix: Messenger import slows down with every thread'
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

The maintainer pointed the Messenger import at the `messages` folder of a real Facebook export (about 660 MB: `e2ee_cutover`, `inbox`, `e2ee_cutover_filtered`, `filtered_threads`, `archived_threads`, `message_requests`). Nothing seemed to happen and no error was shown. The search for threads was already recursive; the import was simply getting slower with every thread. Measured on a synthetic export: 20 threads 0.2 s, 80 threads 1.3 s, 320 threads 51 s.

## Acceptance criteria

- [x] The time per thread does not grow with the threads already read (measured: 20, 80, 320 and 3,000 threads all at 7 to 9 ms per thread; 3,000 threads preview in 24 s).
- [x] People are linked once per import, not once per thread.
- [x] Every top folder of a Facebook export is read, from the `messages` folder or from the export's root.
- [x] A thread with no messages is skipped and reported, instead of failing the whole export; an export where every thread is empty is still refused.
- [x] Progress names the thread's folder, not `message_1.json`.

## Context

Cause: `commands.convert` linked people after every conversation. `DatabaseManager.resolve_people` looks at every handle of the service, and `unresolved_handles` joined `messages` on `sender_handle_id`, which had no index, so each thread read every message already imported. A second fault surfaced while testing: one empty thread raised `CommandError` and aborted the whole export.

## Subtasks

- [x] Tests for a whole export under several top folders, the number of linking passes, empty threads and progress (tests/test_messenger_scale.py).
- [x] Chattr schema version 4: index `messages_by_sender`.
- [x] `commands.convert(resolve=False)` and `NothingFound`; the collectors convert without linking and link once at the end.
- [x] `_import_all` skips empty inputs, reports them as a note, and labels progress with the thread's folder.

## Implementation plan

Status: done
Current task:

### T01: Tests for a whole export under several top folders, the number of linking passes, empty threads and progress (tests/test_messenger_scale.py).
### T02: Chattr schema version 4: index `messages_by_sender`.
### T03: `commands.convert(resolve=False)` and `NothingFound`; the collectors convert without linking and link once at the end.
### T04: `_import_all` skips empty inputs, reports them as a note, and labels progress with the thread's folder.

## Completion report

- **Outcome:** A large Messenger export imports in time proportional to its size. 320 threads: 51 s before, 2.3 s after.
- **Files:** caixa/collectors/chattr.py, tools/chattr/src/chattr/commands.py, tools/chattr/src/chattr/schema.py, tests/test_messenger_scale.py, tools/chattr/tests/test_schema.py
- **Errors:** none
- **Verify:** `python -m pytest -q` 1038 passed, 6 skipped (the real-harness launcher tests, which need Node on PATH); black and mypy clean; scratch timing run at 20/80/320/3000 threads.

## Review

Clean. The fix is two independent changes (an index, and linking once), each of which removes the growth by itself; both are kept because Chattr's own command line still links per export. Not covered: a real Facebook export has not been run here (no real data in this repository), so media-heavy threads are measured only by the maintainer.

## Notes

- 2026-11-12: Reported by the maintainer after testing a real export. NEEDS MAINTAINER CONFIRMATION that the real `messages` folder now previews and imports in reasonable time.
- 2026-11-12: The preview still does the whole conversion (it is how it counts); progress for the preview is ticket 20261112-06.
