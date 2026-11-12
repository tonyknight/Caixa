---
id: 20261112-04-hot-fix-people-first-box-layout-with-readable
title: 'Hot fix: people-first box layout with readable file names'
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

The box was organised by kind of file: `Messages/`, `Audio/Voicemail/`, `Audio/GoogleVoice/`, `Mail/Attachments/`, with voicemail, Google Voice and mail files stored under their content hash (`Audio/Voicemail/00/00e9f1b5….amr`). The maintainer asked for people at the top level: a folder per person with an index page that reflects everything imported from them, and a folder per source beneath it; nothing a casual user sees may be named like a database.

## Acceptance criteria

- [x] The box's top level is `People/`, `Groups/`, `Mail/`, `Inbox/`, `index.html`, `README.md`; there is no `Messages/` or `Audio/`.
- [x] Every person and group has an `index.html`: items by year and by source, the groups they are in, the mail they are in; year pages link back to it and the box's index links to it.
- [x] Every attachment is at `People/<Person>/<Source>/(date) time sender.ext` (groups under `Groups/`, mail under `Mail/<year>/Attachments/` with its own name kept). No visible file has a hash in its name (tested).
- [x] Naming or renaming a person moves their files with their pages; pages no longer wanted are removed, and only pages Caixa wrote.
- [x] Importing the same export again leaves one copy of each file.
- [x] The wizard and the command line still produce byte-identical boxes (e2e-wizard).

## Context

Design: where a file lives is now part of drawing the pages, not of importing. Importers stage files in `.caixa/work/incoming/<kind>/`; `chattr.filing.file_attachments` moves each to its place under the output folder using the renderer's own plan (which page a message is on), records the place in `attachments.storage_path` relative to the output folder, and reports what it created and moved. `render_pages` keeps a list of the pages it wrote and deletes ones it no longer writes. Year pages still bring every source together (the Requirements' 'organised for people, not platforms'); the per-source folders hold the files.

## Subtasks

- [x] Tests for filing (tools/chattr/tests/test_filing.py) and for the person and group index pages and stale pages (test_render_pages.py).
- [x] `render.py`: `People/<Person>` and `Groups/<Group>`; `page_of`, `label`.
- [x] `filing.py`: file, rename, de-duplicate, follow a renamed person, tidy empty folders.
- [x] `pages.py`: links relative to the output folder; `person.html` index pages; the list of written pages and removal of stale ones.
- [x] `commands.publish`; attachment rows take a later import's path.
- [x] Caixa: staging folders, `_publish` through `commands.publish`, box folders and README, a 'filing' progress stage.
- [x] Tests and browser tests moved to the new layout; Collector.md and README rewritten for it.

## Implementation plan

Status: done
Current task:

### T01: Tests for filing (tools/chattr/tests/test_filing.py) and for the person and group index pages and stale pages (test_render_pages.py).
### T02: `render.py`: `People/<Person>` and `Groups/<Group>`; `page_of`, `label`.
### T03: `filing.py`: file, rename, de-duplicate, follow a renamed person, tidy empty folders.
### T04: `pages.py`: links relative to the output folder; `person.html` index pages; the list of written pages and removal of stale ones.
### T05: `commands.publish`; attachment rows take a later import's path.
### T06: Caixa: staging folders, `_publish` through `commands.publish`, box folders and README, a 'filing' progress stage.
### T07: Tests and browser tests moved to the new layout; Collector.md and README rewritten for it.

## Completion report

- **Outcome:** A people-first box with readable names throughout; each person has an index of everything from them.
- **Files:** tools/chattr/src/chattr/{filing,render,pages,commands,database_manager}.py, templates/{person,page,index,base}.html, caixa/collectors/chattr.py, caixa/box.py, tests (Python and harness), docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1069 passed, 6 skipped; harness 240 passed; black, mypy, tsc clean. Imported the synthetic family by command line and looked at Ana's index and 2024 page in a browser; ran the documented check script (6 in the box, 3 recorded but not copied, 0 missing).

## Review

Minors only. (1) NEEDS MAINTAINER CONFIRMATION: year pages stay combined across sources at the person level and only the files are in per-source folders; the tree shown to the maintainer had the pages inside the source folders. Combined pages are the approved Requirements behaviour and what makes one timeline per person, so they were kept; splitting them is a planner change if wanted. (2) NEEDS MAINTAINER CONFIRMATION: the names `Groups/` (top level) and `Mail/<year>/Attachments/`. (3) The same picture sent in two messages is now two files (it was stored once by hash). (4) Files are named by the message's time, no longer by a photo's capture date. (5) Existing boxes are not migrated: rebuild them (agreed with the maintainer).

## Notes

- 2026-11-12: The maintainer confirmed boxes can be rebuilt from scratch, so no migration was written.
- 2026-11-12: iMessage attachments are still recorded but not copied (unchanged, a known limitation).
