---
id: 20261120-10-conversation-pages-and-attachments
title: Conversation pages and attachments
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-21
closed:
notes: ''
parent:
depends_on:
- 20261120-08-how-mail-bodies-look
- 20261120-09-import-the-chosen-conversations
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

File each conversation as a page of cards in `People/<Person>/Mail/<Account>/` and its
attachments in `Attachments/`, and retire Phase 1's mail pages.

## Acceptance criteria

- [ ] One page per conversation, named `(YYYY-MM-DD) <subject>.html` (` (2)` on a clash), in its home person's folder
- [ ] Cards in date order: subject on the top border; date and time with offset; sender and recipients by name and address; the body drawn the way chosen in ticket 8; attachments; a closed All headers fold. Nord light and dark, no script, readable from disk
- [ ] Attachments in `Mail/<Account>/Attachments/` named `(YYYY-MM-DD) <original name>`; same content once; a different file of the same name that day numbered
- [ ] One-pixel images dropped; a small inline image repeated once by a sender (same name and pixel size) kept once and linked
- [ ] The top-level `Mail/` folder and the per-thread pages of Phase 1 gone; their tests updated

## Context

Phase 1.5 - Mbox Tasks Breakdown item 10. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds*; M10, N3.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

### T03: The conversation page, and the master's record of it

- `templates/conversation.html`, `pages.py` (account mail drawn as cards), `caixa/mail/records.py`
  (`page`, `home_person_id`).
- Tests: a conversation page's cards (subject label, date with offset, names and addresses, the
  framed HTML with its logo embedded, files, headers fold), no script, no remote reference; the
  master's thread rows point at their pages and people; through `mail.import` in Caixa.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: caixa/mail/render.py moved to chattr/mail_html.py (Chattr draws the pages; Chattr must not import Caixa); caixa.mail.render re-exports it. MboxParser keeps service_specific.content_ids (Content-ID → SHA-256, for the cid: pictures) and service_specific.headers (the top-level header block, up to 20,000 characters).
