---
id: 20261120-05-the-clean-mail-window
title: The Clean mail window
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ''
parent:
depends_on:
- 20261120-03-junk-classifier-and-the-receipts-guard
- 20261120-04-the-mbox-writer
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The Clean mail window: React in `web/src`, opened in its own window from the Mail card in
Import, showing the categorized list of what cleaning would delete, with Keep, preview and writing
the Cleaned mbox. Its service methods and commands.

## Acceptance criteria

- [ ] Categories on the left with senders, mails and size each; rows with sender name, address, number of mails and size
- [ ] Select, Shift-select, drag onto Keep, Keep from the hover tools; the status bar adds up the selection
- [ ] A preview shows a sender's mails (read from the mbox by byte range, drawn safely)
- [ ] Writing asks for confirmation (how many mails and how much space are left out) and runs as a job with progress
- [ ] Keeps are remembered in `owner.json` (`mail` section)
- [ ] `mail.*` methods for cleaning and `caixa mail clean | keep`
- [ ] Vitest with the fake API, and an end-to-end test in Chromium against the real `caixa serve`; the built window rebuilt and committed
- [ ] After this ticket the maintainer can clean a real mbox

## Context

Phase 1.5 - Mbox Tasks Breakdown item 5. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Components* (windows), *Cleaning rules*, *The list, in both windows*; M5, M8. Design language: the box index page (`tools/chattr/src/chattr/templates/index.html`, `index.js`).

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** the window is a second page of Caixa's React app, served at `/mail/clean` (the same
built `index.html`; `main.tsx` picks the page by its address) and opened in a window of its own
(`caixa-mail`) from the Mail card of the import wizard. Its layout is the box index page's: a
sidebar of categories with counts on the left, a list in the middle, a status bar at the bottom
with the counts, the selection and the actions, and a confirmation before anything is written;
the Nord colours. Unlike the index page the items are rows (sender name, address, number of mails,
size), as agreed. Its parts live in `web/src/client/mail/` so Sort mail (ticket 07) reuses the list.

The service does the work, so the command line does the same:

- `mail.clean` (source): classifies the source (the owner's addresses from the box's owner aliases
  and the mail labelled Sent; the box's people's addresses and names; the senders kept in
  `owner.json`) and returns its groups with rows, and the totals of what writing would leave out;
- `mail.keep` (addresses, keep): adds to or takes from the kept senders in `owner.json`'s new
  `mail` section (which `owner.load` now keeps) and classifies again;
- `mail.preview` (source, address): the sender's mails, latest first (date, subject, recipients
  and a snippet), and `mail.message` (source, position): one mail's headers and text, read from the
  mbox; drawn as text, never as HTML;
- `mail.clean.write` (source): a `mail-clean` job that writes the Cleaned mbox (ticket 04's
  writer) with every mail that is not junk, using the Workers setting.

The index keeps a short snippet of each mail's text (its first 200 characters) so a sender's mails
can be listed without reading the mbox again (index schema 3).

### T01: The service and the command line for cleaning

- `caixa/mail/index.py`: `snippet` column (schema 3), filled in `parse`.
- `caixa/owner.py`: a `mail` section (`kept`, `ignored`, `accounts`) kept by `load`, with
  `mail_kept`/`set_mail_kept` helpers.
- `caixa/service.py`: `mail.clean`, `mail.keep` (write), `mail.preview`, `mail.message`,
  `mail.clean.write` (write; a `mail-clean` job); `caixa/cli.py`: `caixa mail clean PATH
  [--account NAME] [--write]` and `caixa mail keep ADDRESS… [--forget]`; the protocol list and
  README.
- Tests (`tests/test_mail_service.py`): groups and totals for the fixture's Gmail mbox through the
  service; a box person's address protects their mail; keeping a sender takes its mails out of the
  groups and survives a reset; the preview's mails and snippets; one mail's text; writing the Cleaned
  mbox as a job (the file beside the source, the right mails, the result's counts); the commands.
- Verify: `python -m pytest -q tests/test_mail_service.py tests/test_mail_index.py tests/test_owner.py`
- [x] done

### T02: The Clean mail window

- `caixa/web.py`: `/mail/clean` serves Caixa's page.
- `web/src/app/main.tsx`: the page by address; `web/src/client/mail/CleanMail.tsx`,
  `MailList.tsx` (sidebar, rows, selection, tools, status bar), `Preview.tsx` (the overlay),
  `mail.module.css` (the index page's look); `api.ts` types; `locales.ts` (English and Chinese).
- The window: choose a source (a source already read, or an mbox and its account to read, with
  progress), then the groups; click and Shift-click to select, drag onto Keep or the Keep button,
  the ✓ and ↗ tools on hover, Escape to clear; the status bar adds up the view and the selection;
  Write the cleaned mbox asks first (how many mails and how much space are left out, where the
  file goes, that the original is not changed), then shows progress and the new file.
- Tests (`web/tests/clean-mail.test.tsx`, vitest with the fake API).
- Verify: `cd web && pnpm exec tsc --noEmit && pnpm exec vitest run tests/clean-mail.test.tsx`
- [ ] done

### T03: From the import wizard, in a real browser

- `ImportPage.tsx`: the Mail card says mail is cleaned and sorted first and opens Clean mail in its
  own window; the Jobs page names `mail-clean` jobs and their results; window rebuilt.
- `web/tests/e2e-clean-mail.test.ts`: in Chromium against the real `caixa serve`: read the noisy
  mbox, see the groups, keep a sender, write the cleaned mbox, find it beside the source.
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
T01: service mail.clean (classify with the box's people and owner aliases, owner.json keeps; groups, left_out and kept totals, kept senders), mail.keep, mail.preview (from the index's snippets, schema 3), mail.message (reads the mail; text only), mail.clean.write (a mail-clean job: everything but the junk, ticket 04's writer). mail.clean is a write method because classifying writes the index. CLI: 'caixa mail clean PATH [--account] [--write]', 'caixa mail keep ADDRESS... [--forget]'. owner.json gains 'mail' {kept, ignored, accounts}; test_owner's empty-file expectation updated for it. Note for tests: every box person in the fixture is also someone the owner wrote to, so box-person protection is tested with an extra person.
