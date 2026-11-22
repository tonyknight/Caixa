---
id: 20261122-07-cleaning-is-optional
title: Cleaning is optional
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: Skip cleaning button in Clean mail.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Cleaning should be optional: the maintainer wants to go straight from a read mbox to sorting and importing.

## Acceptance criteria

- [x] Clean mail has a 'Skip cleaning: sort and import' button that opens Sort mail on the same mbox (no Cleaned copy written)
- [x] Sort mail and the import work on an mbox that was not cleaned (they already do; tested)

## Context

From the maintainer's first imports of older boxes (2026-11-22). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** a second pill beside Write in Clean mail's footer, a link to `/mail/sort?source=<id>` (the window Sort mail already opens from an address). Nothing changes on the worker: sorting and importing read any source in the index.

### T01: The Skip cleaning button

- `web/src/client/mail/CleanMail.tsx`, `locales.ts`, the built window.
- Tests (`web/tests/clean-mail.test.tsx`): the button is there and opens Sort mail on the same source; (`tests/test_mail_service.py`) an mbox that was read but not cleaned can be sorted and imported.
- Verify: `cd web && pnpm exec vitest run tests/clean-mail.test.tsx && pnpm exec tsc --noEmit`
- [x] done

## Completion report

- **Outcome:** Clean mail has a **Skip cleaning: sort and import** button that opens Sort mail on the same mbox, so cleaning is optional.
- **Files:** `web/src/client/mail/CleanMail.tsx`, `web/src/client/locales.ts`, `caixa/data/web/*`; tests `web/tests/clean-mail.test.tsx`.
- **Errors:** none.
- **Verify:** `pnpm exec vitest run tests/clean-mail.test.tsx` passed; `tsc` clean.

## Review

2026-11-22, in-session. **Verdict: clean.**

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: Clean mail's footer has 'Skip cleaning: sort and import', a link to /mail/sort?source=<id> (Sort mail on the same mbox, no Cleaned copy). Sorting and importing an uncleaned mbox were already covered by tests/test_mail_service.py (imports straight from a read mbox). RED then GREEN; window rebuilt.
