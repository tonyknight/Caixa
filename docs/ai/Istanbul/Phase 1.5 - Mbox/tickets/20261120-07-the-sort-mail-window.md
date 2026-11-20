---
id: 20261120-07-the-sort-mail-window
title: The Sort mail window
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ''
parent:
depends_on:
- 20261120-05-the-clean-mail-window
- 20261120-06-senders-known-and-what-a-choice-brings
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The Sort mail window: the same categorized list as Clean mail, for what an import would add.

## Acceptance criteria

- [ ] Categories Known, To sort, To import, Ignored, Imported, each with senders, mails and size; rows with name, address, mails, size
- [ ] Choose and ignore by selection, drag and hover tools; name-only Known marked and confirmable
- [ ] Typing a name under a sender, with suggestions of the box's people, links the address to that person (as on the index page)
- [ ] Preview of a sender's mails
- [ ] The status bar shows what an import would bring (senders, conversations, mails, size)
- [ ] Vitest and an end-to-end test; the built window rebuilt and committed

## Context

Phase 1.5 - Mbox Tasks Breakdown item 7. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Sorting rules*, *The list, in both windows*; M7.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** `web/src/client/mail/SortMail.tsx`, Caixa's page at `/mail/sort` (`?source=<id>`
opens an mbox directly), built on ticket 05's `MailList` and `Sources`. Categories Known, To sort,
To import, Ignored, Imported with senders, mails and size; rows with name, address, mails, size,
and a note under the name (`known`, `by name: Rui Pereira?`, `you wrote 3`). Tools and actions per
category, as on the index page:

- **To sort:** ✓ Choose, × Ignore, ✎ Name (a name field in the row with the box's people as
  suggestions; Apply links the address to that person, or to a new one, with `people.link`), ↗;
  status-bar Choose and Ignore; drag onto To import or Ignored; Delete or Backspace ignores.
- **Known:** × Ignore, ↗; a name-only match also has ✓ "It's <person>", which links the address.
- **To import:** × Don't import (ignores a known person; forgets the choice of anyone else), ↗.
- **Ignored:** ↶ Stop ignoring, ↗. **Imported:** ↗.
- The status bar adds up the category and the selection, and says what importing would bring
  ("Importing would bring 14 mails in 7 conversations"); the Import button itself is ticket 09's.
- Until the owner's addresses for the account are confirmed, a bar above the list shows the proposed
  ones with Confirm (`mail.owner.set`).
- Clean mail's "Written" notice gains **Sort the cleaned mbox**, which opens Sort mail on it.

### T01: The Sort mail window

- `caixa/web.py` already serves `/mail/sort`; `web/src/app/main.tsx` shows `SortMail` there;
  `MailList.tsx` (a row's note, per-row tools, a row's name field), `SortMail.tsx`,
  `CleanMail.tsx` (Sort the cleaned mbox), `types.ts` (`SortReply`), `locales.ts`.
- Tests (`web/tests/sort-mail.test.tsx`, fake API): categories and counts; notes; choose, ignore
  and stop ignoring by tool, pill, drag and Delete; a name-only match confirmed and a sender named
  with a suggestion (`people.link`); what importing would bring; the owner's addresses confirmed;
  opening `?source=`; Clean mail's link to Sort mail.
- Verify: `cd web && pnpm exec tsc --noEmit && pnpm exec vitest run tests/sort-mail.test.tsx tests/clean-mail.test.tsx`
- [x] done

### T02: In a real browser

- `web/tests/e2e-sort-mail.test.ts`: in Chromium against the real `caixa serve`, with Ana in the
  box: clean the noisy mbox, Sort the cleaned mbox, Ana under Known and To import, choose Beatriz,
  ignore Carlos with Delete, the count of what importing would bring; window rebuilt.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: SortMail.tsx on MailList (which gained a note under the name, per-row tools via 'show', a row's name field with a datalist of the box's people, and Delete/Backspace to ignore). Naming an address uses people.link with service 'Mail' (an email names that address on every service). 'Don't import' ignores a known-by-address person (they are imported unless ignored) and forgets anyone else's choice. Clean mail's Written notice links to /mail/sort?source=<cleaned id>.
