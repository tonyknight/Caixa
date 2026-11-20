---
id: 20261120-05-the-clean-mail-window
title: The Clean mail window
type: feature
priority: high
status: done
created: 2026-11-20
updated: 2026-11-20
closed: 2026-11-20
notes: 'Done: Clean mail window (groups, keep, preview, write), service and CLI; opened
  from the wizard''s Mail card.'
parent:
depends_on:
- 20261120-03-junk-classifier-and-the-receipts-guard
- 20261120-04-the-mbox-writer
subtasks: []
plan_status: done
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

Status: done
Current task: 

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
- [x] done

### T03: From the import wizard, in a real browser

- `ImportPage.tsx`: the Mail card says mail is cleaned and sorted first and opens Clean mail in its
  own window; the Jobs page names `mail-clean` jobs and their results; window rebuilt.
- `web/tests/e2e-clean-mail.test.ts`: in Chromium against the real `caixa serve`: read the noisy
  mbox, see the groups, keep a sender, write the cleaned mbox, find it beside the source.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** the Clean mail window: Caixa's page at `/mail/clean`, opened in its own window from
  the import wizard's Mail card (which no longer starts a blind import). It starts from the mboxes
  already read, or reads another with its account (a job, with progress). Then, in the index page's
  way of working: the groups on the left with senders, mails and size; senders as rows (name,
  address, mails, size); click and Shift-click to select, drag onto Kept, Keep and Stop keeping from
  the status bar or a row's hover tools; a sender's mail in an overlay (as text) and one mail in
  full; Escape clears or closes. Write the cleaned mbox asks first (mails, size, senders left out;
  the source is not changed), runs as a job and shows the new file. Service methods `mail.clean`,
  `mail.keep`, `mail.preview`, `mail.message`, `mail.clean.write`; `caixa mail clean` and
  `caixa mail keep`; kept senders in `owner.json` (`mail.kept`), surviving a reset.
- **Files:** new `web/src/client/mail/{types.ts,MailList.tsx,Preview.tsx,Sources.tsx,CleanMail.tsx,
  mail.module.css}`, `web/tests/{clean-mail.test.tsx,e2e-clean-mail.test.ts}`; changed
  `caixa/{service,cli,owner,web}.py`, `caixa/mail/{index,clean}.py` (snippets, schema 3),
  `web/src/app/main.tsx`, `web/src/client/{locales.ts,Toasts.tsx,pages/ImportPage.tsx,
  pages/JobsPage.tsx}`, `caixa/data/web/*` (rebuilt), tests (`test_mail_service`, `test_owner`,
  `test_web_server`, `test_worker_protocol`, `import-page`, `jobs-page`, `e2e-wizard`).
- **Errors:** none in existing code. `e2e-wizard` imported mail through the wizard card that now
  opens Clean mail; mail left its list (its item total drops by 4).
- **Verify:** `python -m pytest -q` → 1354 passed, 1 skipped, 1 deselected; black and mypy clean;
  `tsc` clean; `vitest run` → 238 passed, including Clean mail end to end in Chromium against the
  real `caixa serve` with no console errors.

## Review

### 2026-11-20: e906574..HEAD (T01–T03), reviewed in-session, with screenshots

**Verdict:** clean after two fixes; Minor items only.

- **Fixed (Minor, seen in the screenshots):** the sidebar's first number had no word ("5 · 11
  mails"); it now says "5 senders · 11 mails". The "Written" notice sat above the whole window and
  pushed it down; it is now a card at the top of the list.
- **Minor:** previewing one mail of an mbox inside a zip unzips forward to it (slow for a mail deep
  in a large zip); the list of a sender's mails is instant (snippets in the index). After cleaning,
  the Cleaned mbox is a plain file, so sorting never meets this.
- **Minor:** the blind import is gone from the wizard but still exists as `caixa import mail` until
  ticket 15 (as planned).
- **Minor:** the window's hover tools are hidden until hover, as on the index page; keyboard users
  reach them by Tab (they show on focus).
- **Spec:** M5 and M8 (keeps) met; every acceptance criterion met.
- **TDD:** RED then GREEN for each task (service tests, window tests, server route, Mail card, Jobs
  page, toasts).
- **Commits:** `{ticket-id} {task-id}: {title}`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: service mail.clean (classify with the box's people and owner aliases, owner.json keeps; groups, left_out and kept totals, kept senders), mail.keep, mail.preview (from the index's snippets, schema 3), mail.message (reads the mail; text only), mail.clean.write (a mail-clean job: everything but the junk, ticket 04's writer). mail.clean is a write method because classifying writes the index. CLI: 'caixa mail clean PATH [--account] [--write]', 'caixa mail keep ADDRESS... [--forget]'. owner.json gains 'mail' {kept, ignored, accounts}; test_owner's empty-file expectation updated for it. Note for tests: every box person in the fixture is also someone the owner wrote to, so box-person protection is tested with an extra person.

### 2026-11-20
T02: web/src/client/mail/ (types, MailList: categories with counts, rows, click/Shift-click, drag onto a drop target, hover tools, status bar; Preview overlay as text only; Sources: mboxes read and reading another with its account; CleanMail). /mail/clean and /mail/sort serve Caixa's page (main.tsx shows CleanMail at /mail/clean; Sort mail is ticket 07). The Jobs page's mail-clean label and result moved here from T03 (the locale test refuses an unused key). Selection colour is the index page's Frost blue, not the window's orange accent.

### 2026-11-20
T03: the wizard's Mail card opens Clean mail in its own window (caixa-mail) instead of the blind import; e2e-clean-mail.test.ts runs it in Chromium against the real caixa serve (read, groups, keep, write, file beside the source, no console errors). e2e-wizard.test.ts no longer imports mail through the wizard (its card is gone); its item total drops by the fixture mbox's 4. Added: failed mail-read / mail-clean jobs toast in their own words (they toasted 'Updating the pages failed').
