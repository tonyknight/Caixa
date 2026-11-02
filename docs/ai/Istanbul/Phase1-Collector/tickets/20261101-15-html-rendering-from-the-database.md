---
id: 20261101-15-html-rendering-from-the-database
title: HTML rendering from the database
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: page plan, person/group/mail pages, index, data island; old generator
  removed.'
parent:
depends_on:
- 20261101-13-one-attachment-pipeline
- 20261101-14-people-roles-contacts-and-aliases
subtasks: []
plan_status: done
---
## Description

Render per-person-per-year pages from `chattr.sqlite`.

## Acceptance criteria

- [x] Date-named, self-contained pages merging all platforms with platform badges
- [x] Stable `id="m-<id>"` anchors and an embedded JSON data island
- [x] Escaped content; heatmap calendar; call/voicemail entries; mail pages by thread

## Context

Phase1-Collector Tasks Breakdown item 15. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Organizing principles; Rebuild chain; F7.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T03: Mail pages by thread, and the index

- One page per mail thread under `Mail/<YYYY>/`, named by the first mail's local date, sender and
  subject; each mail with its headers, plain body (the HTML stays in the data island), attachments.
- `index.html` listing people, groups and mail threads.
- Tests: fixture threads; names; headers; no HTML injection from a mail body.
- Verify: `python -m pytest -q tools/chattr/tests/test_render_mail.py`
- [x] done

### T04: `chattr-cli render`, `--html`, and removing the old generator

- `commands.render(settings, out=None)`; `chattr-cli render [--out DIR]`; `convert --html` and
  `html` use it; the old `HTMLGenerator`, its template and its tests are removed.
- Tests: the commands and CLI; `--html` on the JSON route renders from the temporary database.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `chattr-cli html` (and `convert --html`) renders the archive as self-contained pages:
  `Messages/<Person>/(YYYY) <Person>.html` merging every platform, `Messages/Groups/<Group>/…`,
  `Mail/<YYYY>/(YYYY-MM-DD) <sender> — <subject>.html` per thread, and `index.html`. Each page has a
  platform badge per entry, stable `id="m-<id>"` anchors, the year's heatmap calendar, year
  navigation, call and voicemail entries (transcript and audio), standing reactions, escaped text,
  http-only links, links to attachment files only where they exist, and an escaped JSON data island
  holding every stored column of its messages. Dates and years are the event's local time.
- **Files:**
  - New: `render.py` (page plan, data-island documents), `pages.py` (HTML), templates `base.html`,
    `page.html`, `mail.html`, `index.html`.
  - Changed: `commands.py` (`generate_html`, `attachment_roots`, `--html` on every route),
    `cli.py` (`html --out DIR --attachments-dir DIR`), `database_manager.py` (`connection`).
  - Removed: `html_generator.py`, `templates/template.html`, `test_html_from_database.py`.
  - Tests: `test_render_plan`, `test_render_pages`, `test_render_mail`; the convert/menu/CLI HTML
    tests moved to the new layout; shared `full_archive` fixture in `conftest.py`.
- **Errors:** found and fixed by replacing the old generator:
  - It inserted message text unescaped (`| safe`), so a message containing HTML or script ran in the
    page.
  - Its calendar was always empty (placeholder data).
  - It wrote one page per conversation rather than per person per year, and without platform
    badges or anchors.
- **Verify:** `python -m pytest -q` → 521 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: cc95119..HEAD (T01–T04), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a two-person chat on a service where the owner is just another name (WhatsApp,
  Messenger) needs the owner configured, otherwise it lands under the chat's own name and doesn't merge
  with that person's other platforms. Say so in the README (the Chattr README still describes the
  pre-board state and needs a refresh).
- **Minor:** `convert --html` renders the whole archive each time; fine for a family archive, slow
  for a very large one (planning loads every message into memory).
- **Minor:** attachment links depend on the files being inside the known folders (`<out>/Messages`,
  `Output/*/Attachments`, or `--attachments-dir`); pages for iMessage imported on the central route
  show attachments by name only, because that route does not copy files.
- **Minor:** the per-person attachment folder (named at convert time from the chat) can differ from
  the page's person folder once people resolve; links still work, because they are computed from
  the stored path, but the two folders are not unified until the box is assembled (tickets 18, 21).
- **Minor:** the calendar levels are relative to the page's busiest day, and the page has no search
  or filtering (the old template had none either).
- **Minor:** HTML mail is kept in the data island only; it is never rendered.
- **Minor:** the index is a flat list; very many people make a long page.
- **Spec:** all three acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN for every task (collection errors, then passing; T04 moved 10 old HTML
  tests to the new layout).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: render.py: Renderer loads the archive once, plans PageSpecs and builds data-island documents (schema 'chattr-page-1': conversations incl. participants and roles, handles, messages with every stored column, attachments, reactions; senders referenced by (service, identifier)). Counterpart rule: non-owner person behind the conversation's handles (owner handles = handles that sent is_from_owner messages or have role owner), else the chat name (WhatsApp prefix stripped). Local time = UTC + stored offset. Mail: one page per thread by first mail's local date, sender and subject. Shared session fixture full_archive (every source fixture + contacts + owner + an alias for the Instagram username). DatabaseManager.connection added for readers.

### 2026-11-02
T02: pages.py + templates/page.html: self-contained page (inline CSS, light/dark, no external resources, one script element: the data island). Escaped everywhere (jinja autoescape; nl2br escapes before adding <br>); the island is JSON with < > & U+2028/9 escaped so a body containing </script> can't break out. Links only from http(s) addresses; attachment links only to files that exist inside the given roots (path traversal like ../../etc/x is refused and the file shows by name). Reactions: standing ones only (a later removal cancels). Time: local wall-clock at stored precision with its offset, 'UTC', or 'zone unknown'. Calendar levels are relative to the page's busiest day. The old template's unescaped '| safe' output is what this replaces (T04 removes it).

### 2026-11-02
T03: mail pages (templates/mail.html): per mail the headers (From/To/Cc/Subject/Labels with the sender's own offset), plain body escaped, a note that an HTML version is kept in the data island (not rendered: HTML mail is untrusted), attachments linked only if the file exists in a root. index.html lists people, groups and mail with per-year links and message counts. Shared base.html (CSS) for page/mail/index. Found: a Jinja dict key named 'items' collides with dict.items — keys renamed.

### 2026-11-02
T04: commands.generate_html now renders the whole archive (returns the index page; None when empty); convert --html renders the central archive into Output/Chattr (or, on the JSON route, the temporary database into the service folder); attachment links are looked up in --attachments-dir, <out>/Messages and Output/*/Attachments. CLI: html --out DIR --attachments-dir DIR (the old --owner is gone: the owner is derived from settings now). The old HTMLGenerator, its template and tests are removed. Menu 'Generate HTML' no longer asks for the owner.
