---
id: 20261122-12-quiet-when-the-browser-closes-a-connection
title: Quiet when the browser closes a connection
type: bug
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: closed connections are not printed.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

After an undo the terminal printed a `ConnectionResetError` traceback: the browser had closed an idle connection, and the web server reported it as an error. Nothing went wrong; it should not be printed.

## Acceptance criteria

- [x] A connection the browser resets or closes (reset, broken pipe, timeout) is not printed
- [x] Any other error while handling a request is still printed

## Context

From the maintainer's imports of older boxes (2026-11-22); the layout agreed in conversation (accounts, then labels and folders). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `CaixaServer.handle_error` returns quietly when the exception being handled is a `ConnectionResetError`, `BrokenPipeError`, `ConnectionAbortedError` or `TimeoutError`, and otherwise does what `socketserver` does.

### T01: Ignore connections the browser closes

- `caixa/web.py`.
- Tests (`tests/test_web_server.py`): handling a reset connection prints nothing; another error is still printed.
- Verify: `python -m pytest -q tests/test_web_server.py && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** A browser closing a connection no longer prints a traceback in the terminal; other errors still do.
- **Files:** `caixa/web.py`; tests `tests/test_web_server.py`.
- **Errors:** none.
- **Verify:** `tests/test_web_server.py` 16 passed; mypy clean.

## Review

2026-11-22, in-session. **Verdict: clean.** (The traceback the maintainer saw was this: unrelated to the undo, which had finished.)

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: CaixaServer.handle_error returns quietly for ConnectionResetError, BrokenPipeError, ConnectionAbortedError and TimeoutError (a browser closing a connection) and otherwise reports as socketserver does. RED then GREEN.
