---
id: 20261122-08-a-report-when-the-mail-import-ends
title: A report when the mail import ends
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: a report when the mail import ends, with ways back to the box.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

The mail import ends unceremoniously: the maintainer wants a short report when it is done, and a way back to the box's main page from there.

## Acceptance criteria

- [x] When an import Sort mail started finishes, a report shows: mails and conversations brought in, senders, new items, files, summaries written (or why none), translations, how long it took, and any warnings
- [x] From the report: open the box's people page (its index), go back to Caixa's window, write the reduced mbox, or close it
- [x] A failed import shows its error in the same place

## Context

From the maintainer's first imports of older boxes (2026-11-22). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** in Sort mail, when the import job it started ends, a dialog ("The import is done") with the job's result: mails and conversations, senders, new items, files, summaries (written, or the reason), translations, the time from the click, and warnings. Buttons: **Open the box's people page** (the box window, `index.html`, fresh), **Back to Caixa** (the window that opened this one, else Caixa's main page), **Write the reduced mbox**, **Close**. The Imported bar stays under it.

### T01: The report and its way out

- `web/src/client/mail/SortMail.tsx`, `mail.module.css`, `locales.ts`, the built window.
- Tests (`web/tests/sort-mail.test.tsx`): after the job finishes the dialog shows the counts, summaries and time; its buttons open the index in the box window, return to Caixa, start the reduced mbox and close.
- Verify: `cd web && pnpm exec vitest run tests/sort-mail.test.tsx && pnpm exec tsc --noEmit`
- [x] done

## Completion report

- **Outcome:** When an import started from Sort mail ends, a report opens: what came in (mails, conversations, senders, new items, files), summaries and translations, how long it took and any warnings, or the error if it failed. From it: open the box's people page, go back to Caixa, write the reduced mbox, or close it.
- **Files:** `web/src/client/mail/{SortMail.tsx,mail.module.css}`, `web/src/client/locales.ts`, `caixa/data/web/*`; tests `web/tests/{sort-mail.test.tsx,e2e-sort-mail.test.ts}`.
- **Errors:** a variable named like an imported helper (renamed); two tests clicked what the report now covers (they go through it).
- **Verify:** Sort mail tests and the real-browser Sort mail test passed; `tsc` clean.

## Review

2026-11-22, in-session. **Verdict: clean.**

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: Sort mail shows a dialog when the import it started ends: 'The import is done' (mails and conversations, senders, new items, files, summaries written and by whom or why none, translations, time from started_at to finished_at, warnings) or 'The import did not finish' (its error). Buttons: Close, Back to Caixa (the opener's window, else /), Write the reduced mbox, Open the box's people page (box window, fresh). RED: 2 new tests, then GREEN; the older reduced-mbox test and the real-browser Sort mail test now go through the report. Screenshot: buttons wrapped, dialog widened.
