---
id: 20261120-11-the-person-page-s-entry-and-the-overlay
title: The person page's entry and the overlay
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-21
closed:
notes: ''
parent:
depends_on:
- 20261120-10-conversation-pages-and-attachments
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

One entry per conversation on every involved person's page, and the overlay that shows the
conversation page over it.

## Acceptance criteria

- [ ] The entry at the first mail's date: `@<Account>` pill, who began it, subject, summary (or the opening words), counts, Read the conversation
- [ ] Every box person in a conversation gets the entry, linking to the one page; unanswered owner mail appears as sent by the owner
- [ ] `conversation.js`: a dialog with the page in a frame, closing with Escape, the cross or a click beside it, and an open-in-its-own-window button
- [ ] Its hash joins the box pages' Content-Security-Policy; pages drawn with an older script get the current one (`caixa/web.py` PAGE_SCRIPTS)
- [ ] Works from `/box/` and from `file://` with no policy error (end-to-end test)
- [ ] The index page's Mail view and dashboard list mail by account

## Context

Phase 1.5 - Mbox Tasks Breakdown item 11. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds* (entry), *Components*; M11.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** Chattr draws the entry, since it draws the person pages; mail that came with an
account (ticket 09) gets the new entry, and mail without one (Chattr on its own) keeps Phase 1's
Mail list on the person page.

- **Who gets the entry:** every person in the conversation but the owner (its senders and
  recipients), each linking to the one page in the home person's folder. A person whose only
  contact is mail still gets a page of their own (only mail entries on it).
- **The entry** sits on the person's timeline at the first mail's date and time: the `@<Account>`
  pill (the badge), who began it (the owner, as "Me", for mail the owner sent first), the
  subject, the summary when there is one (ticket 12) or else the opening words of the first mail,
  the counts (mails, files), and Read the conversation (a plain link to the page). The calendar
  counts it as one item that day.
- **`conversation.js`** (inline, like `lightbox.js`): a click on Read the conversation opens a
  dialog with the page in a frame; Escape, the cross or a click beside it closes it; Open in its
  own window opens the page in a tab. Without script the link opens the page. The conversation
  page's back button opens the box's index over the whole window (`target="_top"`).
- **The policy:** `conversation.js` joins `PAGE_SCRIPTS` (its hash in the box policy, and an older
  copy in a page swapped for the current one); the box policy gains `frame-src 'self'` so the
  frame may show a box page.
- **The index:** its Mail view lists conversations under a heading per account (date, subject,
  home person, mails), and the dashboard's mail card says how many per account. Mail without an
  account stays in one list, as in Phase 1.

### T01: The entry on every person's page

- `tools/chattr/src/chattr/pages.py` (`_Relations`, `_message_page`, the entry), `render.py`
  (a page for a person only met in mail), `templates/page.html`.
- Tests (`tests/test_mail_pages.py`, Caixa's Mail collector on the noisy fixture with account
  Gmail): João's page has one entry per conversation with the pill, who began it, subject, opening
  words, counts and a link to the page; Ana, in Cc on a thread at João's, gets the entry linking to
  João's folder; Rui's lunch mail shows as sent by Me; Beatriz (mail only) has a page; the
  calendar has the day.
- Verify: `python -m pytest -q tests/test_mail_pages.py tests/test_mail_filing.py tools/chattr/tests`
- [x] done

### T02: The overlay, and the policy that lets it run

- `templates/conversation.js`, `templates/page.html`, `templates/conversation.html` (back button),
  `caixa/web.py` (`PAGE_SCRIPTS`, `frame-src 'self'`).
- Tests: the page carries `conversation.js` unchanged; its hash is in the box policy; an older copy
  is swapped; end to end (`web/tests/e2e-browse.test.ts`): from `/box/` and from `file://`, Read the
  conversation opens the dialog with the page in it, no policy error, Escape closes it.
- Verify: `python -m pytest -q tests/test_web_server.py tests/test_mail_pages.py && (cd web && pnpm exec vitest run tests/e2e-browse.test.ts)`
- [ ] done

### T03: The index's Mail view by account

- `pages.py` (`_index`, `_stats`), `templates/index.html`.
- Tests: the Mail view has a Gmail heading with its conversations (date, subject, person, mails);
  the dashboard says the count per account; Phase 1 mail without an account still listed.
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
T01: Renderer gives every account mail conversation an entry on the page of its home person and of every box person in it (a handle naming a person), making a person page for someone met only in mail (PageSpec.home, PageSpec.mail). The entry (page.html, k-conversation) sits at the first mail: @Account pill, who began it (Me for the owner), subject, opening words (40, before any quote) until summaries come, counts (mails, files without pixels and repeated signatures), Read the conversation. Calendar, totals and index tiles count the mails. Phase 1's Mail list stays for mail without an account. RED: 4 failing tests in tests/test_mail_pages.py, then GREEN.
