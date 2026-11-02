---
id: 20261101-15-html-rendering-from-the-database
title: HTML rendering from the database
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 15.
parent:
depends_on:
- 20261101-13-one-attachment-pipeline
- 20261101-14-people-roles-contacts-and-aliases
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

Render per-person-per-year pages from `chattr.sqlite`.

## Acceptance criteria

- [ ] Date-named, self-contained pages merging all platforms with platform badges
- [ ] Stable `id="m-<id>"` anchors and an embedded JSON data island
- [ ] Escaped content; heatmap calendar; call/voicemail entries; mail pages by thread

## Context

Phase1-Collector Tasks Breakdown item 15. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Organizing principles; Rebuild chain; F7.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** a new renderer (`render.py`) replaces the old `HTMLGenerator` and its template. The old
template put message text into the page unescaped (`| safe`), left the calendar empty, and wrote one
page per conversation; the Requirements ask for escaped text, a working heatmap, and pages per
person per year across all platforms.

Layout under the output folder (standalone: `<root>/Output/Chattr/`):

```
Messages/<Person>/(YYYY) <Person>.html          every platform, one page per year
Messages/Groups/<Group>/(YYYY) <Group>.html
Mail/<YYYY>/(YYYY-MM-DD) <sender> — <subject>.html     one page per thread
index.html
```

A page belongs to the conversation's *counterpart*: the non-owner person behind its handles (the
handle itself while unresolved), so a person's iMessage, WhatsApp, Google Voice, voicemail and
Messenger history land in one page set. Group conversations go under `Groups/`. Years and dates use
the event's **local** time (UTC + the stored offset). Every page is self-contained (inline CSS, no
scripts needed), shows a platform badge per entry, has `id="m-<id>"` anchors, and embeds a JSON data
island with everything needed to rebuild the database rows (ticket 17).

Two-person chats need the owner configured (`global.owner` or `--owner`) so the counterpart can be
told from the owner on services where the owner is just another name (WhatsApp, Messenger).

### T01: Page plan and the data island document

- `render.plan_pages(db)`: one `PageSpec` per page (kind, title, folder, file name, year, the
  conversations and messages it holds), grouped as above; local dates; safe file names.
- `render.page_document(db, spec)`: the data island: conversations, handles, messages (every
  stored column incl. mail headers and service-specific data), attachments, reactions.
- Shared fixture `full_archive`: every source fixture imported with contacts and owner.
- Tests: Ana's pages merge iMessage, WhatsApp, Google Voice and voicemail; the group is under
  `Groups`; an unresolved handle gets its own folder; years follow local time; document contents.
- Verify: `python -m pytest -q tools/chattr/tests/test_render_plan.py`
- [x] done

### T02: Person and group pages

- `templates/page.html`: inline CSS (light and dark), year navigation, heatmap calendar (a month
  grid per month, days link to their date), date separators, entries with platform badge, sender,
  local time shown with its offset or "UTC", honest precision, `id="m-<id>"`.
- Entries for text (escaped, line breaks kept), media (image, video, audio, link), calls,
  voicemail (transcript + audio), reactions, shared links, system notices.
- The data island embedded safely (`</script>` and U+2028 can't break out).
- Tests: HTML and script in messages render as text; anchors; badges; calendar counts; entry kinds;
  attachment links resolve; island parses and matches.
- Verify: `python -m pytest -q tools/chattr/tests/test_render_pages.py`
- [ ] done

### T03: Mail pages by thread, and the index

- One page per mail thread under `Mail/<YYYY>/`, named by the first mail's local date, sender and
  subject; each mail with its headers, plain body (the HTML stays in the data island), attachments.
- `index.html` listing people, groups and mail threads.
- Tests: fixture threads; names; headers; no HTML injection from a mail body.
- Verify: `python -m pytest -q tools/chattr/tests/test_render_mail.py`
- [ ] done

### T04: `chattr-cli render`, `--html`, and removing the old generator

- `commands.render(settings, out=None)`; `chattr-cli render [--out DIR]`; `convert --html` and
  `html` use it; the old `HTMLGenerator`, its template and its tests are removed.
- Tests: the commands and CLI; `--html` on the JSON route renders from the temporary database.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: render.py: Renderer loads the archive once, plans PageSpecs and builds data-island documents (schema 'chattr-page-1': conversations incl. participants and roles, handles, messages with every stored column, attachments, reactions; senders referenced by (service, identifier)). Counterpart rule: non-owner person behind the conversation's handles (owner handles = handles that sent is_from_owner messages or have role owner), else the chat name (WhatsApp prefix stripped). Local time = UTC + stored offset. Mail: one page per thread by first mail's local date, sender and subject. Shared session fixture full_archive (every source fixture + contacts + owner + an alias for the Instagram username). DatabaseManager.connection added for readers.
