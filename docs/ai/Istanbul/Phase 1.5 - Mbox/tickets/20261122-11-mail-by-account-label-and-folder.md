---
id: 20261122-11-mail-by-account-label-and-folder
title: Mail by account, label and folder
type: feature
priority: medium
status: in-progress
created: 2026-11-22
updated: 2026-11-22
closed:
notes: ''
parent:
depends_on: []
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The box will hold many mailboxes: on the people page, Mail should fold open to each account (by the name given at import), and each account to the mail's own labels (Gmail) or folders (the mbox file's name, as Apple Mail and Thunderbird export one per folder).

## Acceptance criteria

- [ ] Mail on the people page has a chevron; unfolded, each account is listed by its name with its conversation count, and each account has a chevron of its own
- [ ] Under an account, its labels: Gmail's own labels on the mails (without Unread and Opened), else the folder the mail came from (the mbox file's name: Inbox, Sent, Family…), with conversation counts; a conversation with several labels is under each
- [ ] Clicking Mail shows every conversation; an account, only its conversations; a label, only that account's conversations with that label; the title and count follow
- [ ] The folder is kept with each mail at import (from the mbox the import read, or the one it was cleaned or reduced from)

## Context

From the maintainer's imports of older boxes (2026-11-22); the layout agreed in conversation (accounts, then labels and folders). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:**

- **Folders:** the mail import passes `folder` beside `account`: the name of the mbox it read (the original's, for a Cleaned or Reduced copy), from the zip member's, the Apple Mail `<name>.mbox` folder's or the file's name, without its date and `[Cleaned]`/`[Reduced]`. Chattr's mbox parser keeps it in `service_specific["folder"]`.
- **Labels of a conversation:** the union of its mails' labels: Gmail's `X-Gmail-Labels` (already kept, `mail_headers["labels"]`) without `Unread`, `Opened` and `IMAP_…`; a mail without Gmail labels has its folder (Gmail's own export, "All mail…", is never used as a folder when the mail has labels).
- **The index:** `Mail` becomes a row with a chevron (as the categories) and a nested list of accounts (each a chevron and a link `mail-a<n>`) with their labels (links `mail-a<n>-l<m>`), all with counts; the Mail view's items carry `data-account` and `data-labels`. The script shows the Mail section for these views and only the matching items; account headings with nothing shown hide. Folding is remembered as the categories' is. Mail without an account (Chattr on its own) stays in the Mail view only.

### T01: Folders kept with the mail

- `tools/chattr/src/chattr/parsers/mbox_parser.py`, `caixa/collectors/chattr.py`, `caixa/service.py` (`_mail_import`, the folder name).
- Tests: the parser keeps `folder`; an import from a mbox named `Family.mbox` keeps `Family` on its mails, and one from a Cleaned copy keeps the original's name.
- Verify: `python -m pytest -q tools/chattr/tests/test_mbox_accounts.py tests/test_mail_service.py`
- [x] done

### T02: Mail ▸ account ▸ label on the people page

- `tools/chattr/src/chattr/pages.py`, `templates/{index.html,index.js}`.
- Tests (`tests/test_mail_pages.py`): the sidebar has Mail ▸ Gmail ▸ its labels with counts, items carry account and labels; (`web/tests/e2e-browse.test.ts`) unfold Mail, click the account and a label: only those conversations show, the title and count follow.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: MboxParser takes folder (kept in service_specific['folder'], also through its worker processes); Caixa's mail collector passes it; the mail import derives it from the mbox it read, following a Cleaned or Reduced copy back to the original, from the zip member's, the Apple Mail <name>.mbox folder's or the file's name, without its date or [Cleaned]/[Reduced]. RED: 3 tests, then GREEN.
