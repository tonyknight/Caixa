---
id: 20261120-10-conversation-pages-and-attachments
title: Conversation pages and attachments
type: feature
priority: high
status: done
created: 2026-11-20
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: conversation pages as cards with their person, attachments dated, master
  knows page and home.'
parent:
depends_on:
- 20261120-08-how-mail-bodies-look
- 20261120-09-import-the-chosen-conversations
subtasks: []
plan_status: done
---
## Description

File each conversation as a page of cards in `People/<Person>/Mail/<Account>/` and its
attachments in `Attachments/`, and retire Phase 1's mail pages.

## Acceptance criteria

- [x] One page per conversation, named `(YYYY-MM-DD) <subject>.html` (` (2)` on a clash), in its home person's folder
- [x] Cards in date order: subject on the top border; date and time with offset; sender and recipients by name and address; the body drawn the way chosen in ticket 8; attachments; a closed All headers fold. Nord light and dark, no script, readable from disk
- [x] Attachments in `Mail/<Account>/Attachments/` named `(YYYY-MM-DD) <original name>`; same content once; a different file of the same name that day numbered
- [x] One-pixel images dropped; a small inline image repeated once by a sender (same name and pixel size) kept once and linked
- [x] The top-level `Mail/` folder and the per-thread pages of Phase 1 gone; their tests updated

## Context

Phase 1.5 - Mbox Tasks Breakdown item 10. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds*; M10, N3.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** mail that came through the mail workflow carries its account (ticket 09); Chattr draws
and files it the new way, and mail without an account (Chattr on its own) keeps Phase 1's
`Mail/<year>/` pages, so Chattr standalone is unchanged.

- **Safe HTML moves into Chattr** (`chattr/mail_html.py`), since Chattr draws the pages; Caixa's
  `caixa.mail.render` re-exports it. The parser keeps what the page needs and Chattr did not keep:
  each inline file's Content-ID (`service_specific.content_ids`: Content-ID → SHA-256) and the mail's
  header block (`service_specific.headers`, for the All headers fold).
- **Where:** a conversation's home is its person: the non-owner person with the most mails in it
  (the first, on a tie), or, for the owner's unanswered mail, the person it was sent to.
  `People/<Person>/Mail/<Account>/(YYYY-MM-DD) <subject>.html` (` (2)` on a clash); attachments in
  `People/<Person>/Mail/<Account>/Attachments/(YYYY-MM-DD) <original name>` by the date of the mail
  that carried them (the same content once; a different file of the same name that day numbered).
- **Noise in attachments:** a one-pixel image is not filed (a tracking pixel); a small inline image
  (at most 40 KB, provisional until the first real mbox) that the same sender sends again with the
  same name and pixel size is a signature: filed once, every later copy linked to it.
- **The page:** cards in date order: the subject on the top border; date and time with the offset;
  sender and recipients by name and address; the body as the mail's own HTML made safe (pictures
  sent inside it embedded), or its text when it has no HTML; its files (pictures shown, other files
  as links); a closed All headers fold. Nord, light and dark; no script; readable from disk; the
  island keeps the page's data as on every page.
- **The master:** `mail_threads.page` and `home_person_id` are filled from the pages drawn.

### T01: Safe HTML in Chattr, and what the parser keeps for the page

- `tools/chattr/src/chattr/mail_html.py` (moved from `caixa/mail/render.py`, which re-exports it);
  `parsers/mbox_parser.py` (`content_ids`, `headers`).
- Tests: the render tests run against both names; the parser keeps the Content-IDs and headers.
- Verify: `python -m pytest -q tests/test_mail_render.py tests/test_mail_sample.py tools/chattr/tests/test_mbox_parser.py tools/chattr/tests/test_mbox_accounts.py`
- [x] done

### T02: Where conversations and their files go

- `render.py` (`_mail_page`: the home person, the account folder, clashes), `filing.py` (the
  date and original name, tracking pixels, signatures).
- Tests (`tools/chattr/tests/test_mail_filing.py`, the noisy fixture with an account): pages under
  each home person's `Mail/Gmail/`; Rui's lunch mail with Rui; `image001.png` twice on one day,
  numbered; Beatriz's three logos filed once; the tracking pixels not filed; mail without an
  account still under `Mail/<year>/`.
- Verify: `python -m pytest -q tools/chattr/tests/test_mail_filing.py tools/chattr/tests/test_render_mail.py tools/chattr/tests/test_filing.py`
- [x] done

### T03: The conversation page, and the master's record of it

- `templates/conversation.html`, `pages.py` (account mail drawn as cards), `caixa/mail/records.py`
  (`page`, `home_person_id`).
- Tests: a conversation page's cards (subject label, date with offset, names and addresses, the
  framed HTML with its logo embedded, files, headers fold), no script, no remote reference; the
  master's thread rows point at their pages and people; through `mail.import` in Caixa.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** Mail imported through the mail workflow is filed with its person: one page per conversation at `People/<Person>/Mail/<Account>/(YYYY-MM-DD) <subject>.html`, drawn as cards (subject on the top border, names and addresses, date and offset, the mail's own HTML made safe in a frame that runs nothing with its inline pictures embedded, files, a closed All headers fold), attachments in `Attachments/` as `(YYYY-MM-DD) <original name>`, tracking pixels dropped, repeated signature pictures kept once. The master's `mail_threads` rows know their page and home person. New boxes have no top-level `Mail/`; mail without an account (Chattr on its own) keeps Phase 1's pages.
- **Files:** `tools/chattr/src/chattr/{mail_html.py,render.py,filing.py,pages.py,parsers/mbox_parser.py,templates/conversation.html}`, `caixa/mail/{render.py,records.py}`, `caixa/box.py`, `caixa/undo.py`; tests `tests/test_mail_{filing,records,render}.py`, `tests/test_collector_contract.py`, `tools/chattr/tests/test_mbox_accounts.py`.
- **Errors:** mypy refused `safe_name` through `chattr.filing` (not re-exported); imported from `chattr.attachment_manager`. The offset test used an ASCII hyphen; the pages use the minus sign (U+2212), as Phase 1's do.
- **Verify:** `python -m pytest -q` 1405 passed, 1 skipped; black clean; mypy clean (76 files); web `tsc` clean, vitest 248 passed.

## Review

2026-11-21, in-session. **Verdict: clean (minors only).**

- Minor: times on mail cards show seconds (`19:00:00`), as Phase 1's mail pages do; minutes would read better for mail.
- Minor: a picture sent inline but larger than 4 MB is listed with the files rather than shown in the mail's frame (by design; noted for the first real mbox).
- Spec: files touched match the plan; acceptance criteria met; RED then GREEN recorded per task (the T03 tests failed on the missing cards and the empty `page` before the code).

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: caixa/mail/render.py moved to chattr/mail_html.py (Chattr draws the pages; Chattr must not import Caixa); caixa.mail.render re-exports it. MboxParser keeps service_specific.content_ids (Content-ID → SHA-256, for the cid: pictures) and service_specific.headers (the top-level header block, up to 20,000 characters).

### 2026-11-21
T02: mail with an account is planned at People/<home>/Mail/<Account>/(date) subject.html (home: the non-owner who wrote most, else the person written to; ' (2)' on a clash), its files at .../Attachments/(date) <own name> (filing's free-name rule numbers clashes; one copy per content). Filing pre-pass for Caixa's mail: one-pixel pictures are not filed (processing_info dropped: tracking pixel); a picture of at most 40 KB that a sender repeats with the same name and pixel size is filed once and later copies linked (signature). New boxes have no top-level Mail/ folder (box.FOLDERS, undo's always-there folders); the contract test updated. Tests moved to tests/test_mail_filing.py (they need Caixa's collector). Mail without an account is still drawn the Phase 1 way.

### 2026-11-21
T03: account mail is drawn by chattr/templates/conversation.html: cards in date order, subject on the top border, sender and To/Cc by name and address, date/time with offset, the mail's own HTML via mail_html.original (Content-ID pictures embedded as data: addresses, up to 4 MB each; larger ones listed), plain text otherwise, files beneath (pictures shown, others linked; dropped pixels and inline pictures not repeated), a closed All headers fold; no script but the data island. record_mail fills mail_threads.page (from items.file_path) and home_person_id (the person whose People/ folder holds the page).
