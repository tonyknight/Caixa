---
id: 20261117-03-people-page-select-and-delete-records-not-yet
title: 'People page: select and delete records not yet named'
type: feature
priority: high
status: done
created: 2026-11-17
updated: 2026-11-17
closed: 2026-11-17
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

In the People section's "Not yet named" list, an empty selection box at the top left; clicking it shows a blank box at the left of every record. The owner ticks records and chooses Delete at the bottom of the list; after a confirmation, the records and the data that came only from them are deleted (through `people.delete`), and remembered in the owner's preference file.

## Acceptance criteria

- [x] The top box shows a box on every record; once shown, it chooses all or none
- [x] Delete (count) at the bottom is disabled until something is chosen; Cancel hides the boxes
- [x] Nothing is deleted before the confirmation
- [x] Deleted records leave the list at once (the service filters removed handles before the redraw job runs)
- [x] A refusal is shown in Caixa's own words
- [x] English and Chinese texts

## Context

Maintainer, 2026-11-17, collection-mode deletion method. Uses the service from 20261117-01.

## Subtasks

- [x] api.remove and the fake API
- [x] PeoplePage: reveal box, row boxes, Delete with confirmation
- [x] people.unresolved leaves out what was removed
- [x] Locales en + zh
- [x] Unit tests and the browser test

## Implementation plan

Status: done
Current task:

### T01: api.remove and the fake API
### T02: PeoplePage: reveal box, row boxes, Delete with confirmation
### T03: people.unresolved leaves out what was removed
### T04: Locales en + zh
### T05: Unit tests and the browser test

## Completion report

- **Outcome:** Records not yet named can be chosen and deleted from the People section.
- **Files:** harness/src/client/{api.ts,locales.ts,pages/PeoplePage.tsx}, harness/tests/{fake-api.ts,people-page.test.tsx,e2e-people.test.ts}, caixa/service.py, tests/test_owner.py
- **Errors:** The list reloaded straight after deleting and showed the records again until the redraw job ran; the service now leaves removed handles out at once.
- **Verify:** python -m pytest -q (1327 passed); vitest run (279 passed); tsc clean

## Review

Clean.

## Notes

- NEEDS MAINTAINER CONFIRMATION: the selection box sits in the list's header row, above the first record; once the boxes show, it also chooses all.
