---
id: 20261122-08-a-report-when-the-mail-import-ends
title: "A report when the mail import ends"
type: feature
priority: medium
status: todo
created: 2026-11-22
updated: 2026-11-22
closed:
notes: ""
parent:
depends_on: []
subtasks: []
---

## Description

The mail import ends unceremoniously: the maintainer wants a short report when it is done, and a way back to the box's main page from there.

## Acceptance criteria

- [ ] When an import Sort mail started finishes, a report shows: mails and conversations brought in, senders, new items, files, summaries written (or why none), translations, how long it took, and any warnings
- [ ] From the report: open the box's people page (its index), go back to Caixa's window, write the reduced mbox, or close it
- [ ] A failed import shows its error in the same place

## Context

From the maintainer's first imports of older boxes (2026-11-22). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: approved
Current task: T01

**Design:** in Sort mail, when the import job it started ends, a dialog ("The import is done") with the job's result: mails and conversations, senders, new items, files, summaries (written, or the reason), translations, the time from the click, and warnings. Buttons: **Open the box's people page** (the box window, `index.html`, fresh), **Back to Caixa** (the window that opened this one, else Caixa's main page), **Write the reduced mbox**, **Close**. The Imported bar stays under it.

### T01: The report and its way out

- `web/src/client/mail/SortMail.tsx`, `mail.module.css`, `locales.ts`, the built window.
- Tests (`web/tests/sort-mail.test.tsx`): after the job finishes the dialog shows the counts, summaries and time; its buttons open the index in the box window, return to Caixa, start the reduced mbox and close.
- Verify: `cd web && pnpm exec vitest run tests/sort-mail.test.tsx && pnpm exec tsc --noEmit`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
