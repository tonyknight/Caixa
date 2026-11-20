---
id: 20261120-08-how-mail-bodies-look
title: How mail bodies look
type: spike
priority: high
status: blocked
created: 2026-11-20
updated: 2026-11-20
closed:
notes: 'Waiting for the maintainer: run ''caixa mail sample'' on a small real mbox
  and choose plain, tidied or original.'
parent:
depends_on:
- 20261120-02-mail-index-and-parallel-reading
subtasks: []
plan_status: blocked
current_task: T03
---
## Description

Spike: decide how mail bodies are drawn on the conversation page. `caixa mail sample <mbox>`
draws a few conversations of a small real mbox three ways (plain text; tidied HTML; the mail's own
HTML with its styling kept and scripts, event handlers and remote content removed) for the
maintainer to compare on their own computer.

## Acceptance criteria

- [ ] `caixa mail sample` writes the three versions of each sampled conversation to a folder the maintainer chooses (outside the repository)
- [ ] Every version holds no script, event handler or remote reference (tested on the fixtures)
- [ ] The maintainer's choice is recorded in the Requirements (*What the box holds*) and in this ticket's notes
- [ ] No real mail is committed

## Context

Phase 1.5 - Mbox Tasks Breakdown item 8. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds* (conversation page), N3, Open questions. Blocks ticket 10.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: blocked
Current task: T03

**Design (spike):** `caixa/mail/render.py` draws a mail's body three ways, with the standard
library's HTML parser, and `caixa mail sample` lays a few conversations of a real mbox out as pages
of cards in each way, for the maintainer to compare on their own computer:

1. **plain:** the mail's text (its plain part, or its HTML as text), as written;
2. **tidied:** the HTML kept to a small set of tags (paragraphs, breaks, emphasis, links, lists,
   quotes, headings, tables, images), every attribute dropped but a link's address and an image's
   source and description, styles dropped, and earlier replies quoted in the mail folded away;
3. **original:** the mail's own HTML with its styles kept, but with scripts, event handlers,
   `javascript:` addresses, frames, objects, forms and every remote reference (images, style sheets,
   `url(...)` in styles) taken out, shown inside its card in a frame that runs nothing
   (`<iframe sandbox srcdoc=…>`), so its styles stay in the card.

In every way, pictures sent inside the mail (`cid:`) are written beside the page and shown; remote
pictures are not fetched. Each card: the subject on the top border; the date, the sender's name and
address, the recipients' names and addresses; the body; the files; a closed **All headers** fold.
The sample folder holds `plain/`, `tidied/` and `original/`, one page per conversation in each, and an
`index.html` linking them side by side. The choice is recorded in the Requirements and in ticket 10.

### T01: Three ways to draw a body, safely

- `caixa/mail/render.py`: `plain(text)`, `tidied(html, images)`, `original(html, images)`.
- Tests (`tests/test_mail_render.py`): on the fixture's unsafe HTML and on hand-made cases, no
  `<script`, no `on…=` handler, no `javascript:`, no `http(s)://` source or `url()` in any output;
  `cid:` pictures point at their files; links keep their address; quoted replies folded in tidied;
  styles kept (and remote ones removed) in original.
- Verify: `python -m pytest -q tests/test_mail_render.py`
- [x] done

### T02: `caixa mail sample`

- `caixa/mail/sample.py` and `caixa mail sample SOURCE --out FOLDER [--account NAME]
  [--conversations N]`: the conversations with the most mails, HTML ones first; pages of cards in
  each way; pictures beside them; `index.html`.
- Tests: the fixture sampled into a folder: three versions of each conversation, the index, the
  pictures, and no script, handler or remote reference in any page.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

### T03: The maintainer's choice

- The maintainer runs `caixa mail sample` on a small real mbox and chooses; the choice goes into the
  Requirements (*What the box holds*) and ticket 10. **Waits for the maintainer.**
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T02: 'caixa mail sample SOURCE --out FOLDER [--account] [--conversations N]' writes plain/, tidied/, original/, files/ and index.html. Seen in a browser from disk: a frame that runs nothing (sandbox, no allow-same-origin) cannot load pictures from disk, so the original's pictures travel inside it as data: addresses; it also cannot size itself, so its height is estimated from the mail (words, blocks, pictures; 4 to 60 rem, and it can be resized by hand). Links inside the original's frame open in the frame. These are the original style's trade-offs for the maintainer to weigh.

### 2026-11-20
Blocked on T03: the maintainer's choice of body style (run caixa mail sample on a small real mbox). Tickets 10, 11, 12 and 14 wait on it; 09, 13 and 15 go on.
