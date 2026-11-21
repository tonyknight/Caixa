---
id: 20261120-14-attachments-folders-for-every-source
title: Attachments folders for every source
type: feature
priority: medium
status: in-progress
created: 2026-11-20
updated: 2026-11-21
closed:
notes: ''
parent:
depends_on:
- 20261120-10-conversation-pages-and-attachments
subtasks: []
plan_status: done
---
## Description

Every source files attachments in an `Attachments/` folder: `People/<Person>/<Source>/Attachments/`
(and the same under `Groups/`). Boxes already built are moved once.

## Acceptance criteria

- [ ] iMessage, WhatsApp, Messenger, Instagram, Google Voice and voicemail file new attachments in `<Source>/Attachments/`
- [ ] Opening a box built before this moves its files once; the move can be stopped and restarted without loss
- [ ] Paths in `chattr.sqlite` and `caixa.sqlite` updated; pages redrawn; a test checks every link on every page resolves
- [ ] Undo snapshots and re-imports keep working after the move
- [ ] `docs/Documentation/Collector.md` (Attachments in detail) updated

## Context

Phase 1.5 - Mbox Tasks Breakdown item 14. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds* (Attachments folders); M15. Filing code: `tools/chattr/src/chattr/filing.py`.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** filing already moves a filed file when its place changes (that is how a renamed person's
files follow them) and records the new place in `chattr.sqlite`, and Caixa notes every move for
undo. So the folder rule changes in one place, and a box built before is moved by drawing its pages
again.

- **Where:** `People/<Person>/<Source>/Attachments/(YYYY-MM-DD) HH-MM-SS <sender>.<ext>` (and the
  same under `Groups/`); mail stays as ticket 10 left it (`Mail/<Account>/Attachments/`, and Phase
  1's `Mail/<year>/Attachments/` for mail without an account). Pages link the new places.
- **Stopped and restarted:** filing commits its records as it goes (every 200 files), and a file
  whose move was not recorded (the run stopped between the two) is found again in its new folder
  by its name and content, so a second run finishes the move and loses nothing.
- **Boxes built before:** `box.yaml` gains `layout` (2 for boxes made now; a box without it is 1).
  Opening a layout-1 box (not read-only) that has pages starts one Redraw job, "Moving files into
  Attachments folders"; when it finishes the box is marked layout 2. Stopped or failed, the box
  stays at 1 and the next opening starts it again. A box with nothing imported is marked at once.
- **Caixa's database** holds page paths, not attachment paths; it is brought up to date by the
  redraw as always. Moves are noted on the newest undo snapshot, so undoing an import made before
  the move puts files back and the redraw files them again.

### T01: Every source files into Attachments/, and a move can be repeated

- `tools/chattr/src/chattr/filing.py` (`_folder`, periodic commits, finding an unrecorded move);
  tests that name the old places.
- Tests (`tools/chattr/tests/test_filing.py`): WhatsApp and iMessage files land in
  `<Source>/Attachments/`; files filed the old way move on the next drawing and the pages link the
  new places; a drawing stopped part-way (files moved, records not saved) is finished by the next
  one with every file present once and every link resolving.
- Verify: `python -m pytest -q tools/chattr/tests`
- [x] done

### T02: Boxes built before are moved once

- `caixa/box.py` (`layout`), `caixa/service.py` (the move on opening, marking it done),
  `docs/Documentation/Collector.md` (Attachments in detail).
- Tests (`tests/test_attachments_move.py`): a box imported the old way, opened, is moved by one job
  and marked; every link on every page resolves; opening again starts nothing; a stopped move is
  started again on the next opening and finishes; an import made before the move can still be
  undone (links resolve after), and importing again after the move adds nothing.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: filing._folder puts every chat source's files in <Source>/Attachments/ (mail unchanged). Filing commits its records every 200 files, and a filed file whose move was not recorded (stopped between the two) is recovered from its new folder by name, extension and content (any content when it was converted at first filing), then recorded. Files filed the old way move on the next drawing (the existing rename mechanism). Tests: 3 new in test_filing.py (new folders; old layout moves, links resolve; a drawing interrupted after two moves is finished by the next with every file once and every link resolving), RED then GREEN; old-path expectations in test_filing.py, test_imessage_attachments.py and tests/test_chattr_collectors.py updated. Full suite 1431 passed.

### 2026-11-21
T02: box.yaml gains layout (Box.LAYOUT = 2 for new boxes; missing = 1; Box.layout, Box.mark_layout). Opening a layout-1 box (not read-only) enqueues one refresh job with options {layout: 2} ('Moving files into Attachments folders'), which marks the box when it finishes; stopped or failed, the next opening starts it again; a box with no Chattr store is marked at once. tests/test_attachments_move.py (5): new boxes marked; an old box (imported with the old folder rule) is moved by one job, links resolve, opening again starts nothing; an empty box is marked; a cancelled move restarts and finishes; re-import adds nothing and every import (from before the move too) can be undone with links resolving. RED (LAYOUT missing) then GREEN. Collector.md: the box tree, the filing rule, older boxes, iMessage path, links and the summary table.
