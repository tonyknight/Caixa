---
id: 20261119-01-a-folder-of-chat-zips-imports-every-chat
title: A folder of chat zips imports every chat
type: feature
priority: medium
status: done
created: 2026-11-19
updated: 2026-11-19
closed: 2026-11-19
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-19 (after v0.5.0): WhatsApp exports one chat at a time, each as a zip; choosing a folder of those zips found nothing, because only a zip chosen directly was opened. Asked to do this now, ahead of the interface-tweaks project.

## Acceptance criteria

- [x] A folder of WhatsApp chat zips imports every chat in one job
- [x] Zips and unzipped chat folders mixed in one folder are all read
- [x] A zip of such a folder works (it unpacks into one folder holding the zips)
- [x] A zip further down (a file sent in a chat) stays closed
- [x] A zip that cannot be read stops the import and is named
- [x] Applies to every source that takes a folder (a Takeout in parts, for example)

## Context

Post-release fix on the closed Phase 1 board, on the project branch, so no new project or branch had to be named.

## Subtasks

- [x] Tests: folder of zips, mixed folder, zip of zips, deep zip left closed, unreadable zip named; the diagnostics tests follow
- [x] inputs.resolve opens the zips at the top of a folder (and inside the single folder an unpacked zip holds)
- [x] WhatsApp's how-to-export text and the guide

## Implementation plan

Status: done
Current task:

### T01: Tests: folder of zips, mixed folder, zip of zips, deep zip left closed, unreadable zip named; the diagnostics tests follow
### T02: inputs.resolve opens the zips at the top of a folder (and inside the single folder an unpacked zip holds)
### T03: WhatsApp's how-to-export text and the guide

## Completion report

- **Outcome:** Point Caixa at the folder of WhatsApp zips and every chat comes in at once.
- **Files:** caixa/collectors/inputs.py, caixa/collectors/chattr.py, tests/test_chattr_collectors.py, tests/test_input_diagnostics.py, docs/Documentation/Collector.md
- **Errors:** A first version also stepped into the single folder of a plain folder, which opened a zip sent inside a chat's folder; that step is now only for an unpacked zip.
- **Verify:** python -m pytest -q (1296 passed); vitest run (225 passed); black; mypy

## Review

Clean.

## Notes

- NEEDS MAINTAINER CONFIRMATION: an unreadable zip among good ones stops the whole import (named) rather than being skipped with a warning.
