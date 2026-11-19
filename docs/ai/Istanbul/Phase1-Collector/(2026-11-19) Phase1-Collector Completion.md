---
hierarchy:
- Istanbul
- Phase1-Collector
last_reviewed: 2026-11-19
status: complete
origin_branch: 2026-Istanbul/Phase1-Collector
execute_branch: 2026-Istanbul/Phase1-Collector
---

# Phase1-Collector Completion

Focus: Message collection: Chattr becomes Caixa's message converter, on top of Caixa's data architecture

Verify command (Requirements *Testing requirements*): **`python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`**

Released as **v0.5.0** on 2026-11-19 (project branch `2026-Istanbul/Phase1-Collector`, merged
into `working`, then `main`).

---

## Summary

Phase 1 set out to make Chattr Caixa's message converter, on top of Caixa's own data architecture,
with an interface a non-technical person can use. It is done: 66 tickets, all closed (27 from the
Requirements' Tasks Breakdown, 39 hot fixes and fix-ups that came out of the maintainer's testing
on real exports).

### What exists now

- **Six collectors**, each with a "how to export" card and its options: iMessage (`chat.db`, read
  only, on any recent macOS schema), WhatsApp (chat exports), Messenger and Instagram (Facebook's
  download), mail (`.mbox`), Google Voice (Takeout) and iPhone voicemail. Every import can be
  previewed, undone, and run again; re-importing adds only what is new.
- **The box**: a plain folder that stays complete when copied. One page per person
  (`People/<Person>/<Person>.html`) with every source together, a year bar and a calendar; group
  pages; mail pages; and `index.html` with people as tiles sorted into categories (Family, Friends,
  Business, Acquaintances, Unrecognized, Unassigned), a dashboard of sources, and the authoring
  tools (sort by drag or buttons, name a number with suggestions of people already in the box,
  remove people with their one-to-one conversations, open a page in its own window).
- **Files**: attachments filed beside the person, named by date and sender, stored once per
  content; pictures as dated JPEG, audio as `.m4a` that plays in any browser; a lightbox.
- **People**: Contacts (this Mac's, or a vCard), Facebook friends, names shown by WhatsApp,
  Google Voice and voicemail; one person across addresses and services; renames and merges; the
  owner's decisions kept in `.caixa/owner.json`, which survives a reset.
- **Rules against noise**: Facebook message requests and non-friends left out; group
  conversations only where the owner wrote, and only members who wrote; numbers from groups never
  listed to be named; Messages' junk tagged; messages without a chat in iMessage put back with
  their people.
- **Local speech-to-text** (whisper.cpp or faster-whisper, one run for many recordings) and
  **translation** through any OpenAI-compatible endpoint, local or paid.
- **Caixa's own window**: `caixa serve` runs the service layer and a small web server in one
  Python process, on this computer only, with a sign-in link. The window (React, in `web/`) is
  built into the package, so running Caixa needs neither Node.js nor DeepSeek Harness.
- **Command line** for everything (`caixa`), Chattr's own `chattr-cli` (and `chattr-cli serve`),
  `caixa doctor` for a report with no personal data in it, and `caixa reset`.

### Decisions made during the project (recorded in the Requirements)

- 2026-11-02: GPL-3.0-or-later for Chattr and Caixa; Chattr's command is `chattr-cli`.
- 2026-11-17: the collector leaves DeepSeek Harness for a service of its own, in Python, in the
  Nord theme; three modes (collection and authoring now; presentation and static later). The
  plugin was then removed and `harness/` renamed `web/`.
- 2026-11-17: no automatic pruning; the owner removes people by hand, remembered in
  `.caixa/owner.json`.

### Verified, and not verified

- **Verified by tests**: 1,290 Python tests (Caixa and Chattr) and 225 browser and unit tests of
  the window, 24 of them end-to-end against the real `caixa serve` in Chromium; black and mypy
  clean. Every source is tested against the synthetic fixture family; no real data is in the
  repository.
- **Tried by the maintainer on real exports**: iMessage, Messenger, Google Voice (with and without
  its HTML), iPhone voicemail, Mac Contacts, a local translation endpoint, sorting and naming a
  real box, reset.
- **Not yet tried on real data**: **mail (`.mbox`)**, WhatsApp, Instagram, a vCard file, the
  faster-whisper backend, Windows, and the Chattr mirror workflow (it needs the
  `CHATTR_MIRROR_TOKEN` secret; it runs on every push to `main`).
- **Open question carried over**: the "(no chat)" messages seen on 2026-11-18 did not come back in
  a fresh box; the maintainer judged them messages processed before the latest changes. The
  Google Voice forwarded-copy check (ticket `20261118-04`) rests on a premise the maintainer
  doubts; it only removes exact twins, and should be kept or removed once a full Google Voice
  import shows whether it finds any.

### Choices waiting for the maintainer's confirmation

Each is recorded in its ticket as "NEEDS MAINTAINER CONFIRMATION". The ones that shape what a person
sees:

- `.caixa/owner.json` as the preference file's name and place; removals remembered across imports.
- Deleting a person removes their one-to-one conversations and files; their messages in groups stay.
- The name field only on Unrecognized tiles; the open-page button (not the close box) in Unassigned;
  one reused window (`caixa-box`) for every box page.
- **Sent, recipient not recorded** (listed with the groups) for the owner's iMessages that name
  nobody and follow nothing; events of groups that no longer exist left out.
- The ten-minute, exact-words rule for Google Voice forwarded copies.
- The sign-in link valid until Caixa stops; the built window committed in `caixa/data/web/`.
- Pictures: the original HEIC/PNG not kept beside the JPEG. Voicemail audio at 16 kbit/s.
- Three undo snapshots kept (`undo.KEEP`).

### What comes next

1. A small project of interface tweaks.
2. Planning how mail (`.mbox`) is handled, starting from a first real import (see the mail
   section of `docs/Documentation/Collector.md` for what the current collector does).
3. Stage 1.5: requirements for photos, home videos, Obsidian vaults, PDFs, and quieter mail.
4. Then Stage 2 (a personal model) and Stage 3 (the harness that brings them together), and the
   presentation mode (read-only, its own port, possibly in Docker).

---

## Tickets

### 20261101-01-caixa-repository-foundations — Caixa repository foundations

- **Outcome:** `caixa` package skeleton with a `caixa` console script (`--version`); dev tooling
- **Files:** `pyproject.toml`, `caixa/__init__.py`, `caixa/__main__.py`, `caixa/cli.py`,
- **Errors:** none.
- **Verify:** `python -m pytest -q` → 2 passed; `python -m black --check .` → clean;

### 20261101-02-synthetic-fixture-family — Synthetic fixture family

- **Outcome:** a deterministic synthetic fixture family (standard library only) for all six
- **Files:** `tools/chattr/tests/` (`conftest.py`, `fixtures/` with `family.py`, `builders/`
- **Errors:** - **MBOX determinism bug:** random MIME boundaries and current-time From_ lines; fixed in T05.
- **Verify:** `python -m pytest -q` → 43 passed; `python -m black --check .` → clean;

### 20261101-03-chattr-import-and-licensing — Chattr import and licensing

- **Outcome:** - Chattr imported with its full history (8 commits, head `0152912`) at `tools/chattr`.
- **Files:** `tools/chattr/**` (import), `tools/chattr/LICENSE`, `tools/chattr/NOTICE`,
- **Errors:** none. One whole-history scan matched the ticket's own `grep` pattern for the key
- **Verify:** - history: `a09ccfa^2` = `0152912`, 8 commits; 0 `.db`/`.idea` files; 0 key-shaped strings;

### 20261101-04-chattr-stabilization — Chattr stabilization

- **Outcome:** Chattr is an installable package (`tools/chattr/src/chattr/`) with the
- **Files:** - `tools/chattr/pyproject.toml` (new), `requirements.txt`, `README.md`, `docs/*.md`
- **Errors:** - **Fixed real bugs:** six wrong configuration keys; the HTML crash on `sqlite3.Row`;
- **Verify:** `python -m pytest -q` → 84 passed; `python -m black --check .` → clean;

### 20261101-05-unified-schema-v0-chattr-sqlite — Unified schema v0 (chattr.sqlite)

- **Outcome:** Chattr's unified schema v0 and one `DatabaseManager` for all services.
- **Files:** `src/chattr/schema.py`, `records.py`, `importing.py` (new); `database_manager.py`
- **Errors:** none.
- **Verify:** `python -m pytest -q` → 105 passed; `python -m black --check .` → clean;

### 20261101-06-interactive-menu-and-command-line — Interactive menu and command line

- **Outcome:** Chattr's work now lives in prompt-free functions in `chattr.commands`:
- **Files:** - New: `tools/chattr/src/chattr/commands.py`, `tools/chattr/src/chattr/imessage_export.py`.
- **Errors:** found in review and fixed with tests:
- **Verify:** `python -m pytest -q` → 155 passed; `python -m black --check .` clean;

### 20261101-07-imessage-parser — iMessage parser

- **Outcome:** `chat.db` now converts into the central archive by default (`chattr-cli convert
- **Files:** - New: `typedstream.py`, `apple_time.py`, `chatdb.py`, `parsers/imessage_parser.py`.
- **Errors:** found and fixed, each with a test:
- **Verify:** `python -m pytest -q` → 223 passed; `python -m black --check .` clean;

### 20261101-08-whatsapp-parser — WhatsApp parser

- **Outcome:** `WhatsAppParser` reads iOS, Android and US-locale exports (day/month order decided
- **Files:** - New: `media_archive.py`.
- **Errors:** found and fixed, each with a test:
- **Verify:** `python -m pytest -q` → 252 passed; `python -m black --check .` clean;

### 20261101-09-messenger-and-instagram-parser — Messenger and Instagram parser

- **Outcome:** Messenger and Instagram exports convert into the central archive
- **Files:** - Rewritten: `parsers/messenger_parser.py` (plus `InstagramParser`).
- **Errors:** found and fixed, each with a test:
- **Verify:** `python -m pytest -q` → 282 passed; `python -m black --check .` clean;

### 20261101-10-mbox-email-parser — MBOX email parser

- **Outcome:** `chattr-cli convert mail <file.mbox>` imports an MBOX (Gmail Takeout or any
- **Files:** - New: `parsers/mbox_parser.py`, `parsers/batch.py`, `blobs.py`, `defaults/Services/Mail.json`.
- **Errors:** none in existing code. Decisions with consequences:
- **Verify:** `python -m pytest -q` → 327 passed; `python -m black --check .` clean;

### 20261101-11-google-voice-parser — Google Voice parser

- **Outcome:** `chattr-cli convert googlevoice <Takeout folder>` imports Google Voice into the central
- **Files:** - New: `parsers/google_voice_parser.py`.
- **Errors:** none in existing code. Notes:
- **Verify:** `python -m pytest -q` → 356 passed; `python -m black --check .` clean;

### 20261101-12-iphone-voicemail-and-local-speech-to-text — iPhone Voicemail and local speech-to-text

- **Outcome:** `chattr-cli convert voicemail <backup folder> [--transcribe] [--model PATH]
- **Files:** - New: `transcription.py`, `parsers/voicemail_parser.py`.
- **Errors:** none in existing code. **What was not verified:** no speech-to-text model or runtime
- **Verify:** `python -m pytest -q` → 399 passed; `python -m black --check .` clean;

### 20261101-13-one-attachment-pipeline — One attachment pipeline

- **Outcome:** `AttachmentManager` is the one attachment pipeline for the file-based services
- **Files:** - Rewritten: the `AttachmentManager` class in `attachment_manager.py`; `media_archive.py`
- **Errors:** found and fixed:
- **Verify:** `python -m pytest -q` → 423 passed; `python -m black --check .` clean;

### 20261101-14-people-roles-contacts-and-aliases — People: roles, contacts and aliases

- **Outcome:** handles (phone numbers, email addresses, usernames, names) resolve to people from the
- **Files:** - New: `people.py`.
- **Errors:** none in existing code. Behaviour changes to note:
- **Verify:** `python -m pytest -q` → 477 passed; `python -m black --check .` clean;

### 20261101-15-html-rendering-from-the-database — HTML rendering from the database

- **Outcome:** `chattr-cli html` (and `convert --html`) renders the archive as self-contained pages:
- **Files:** - New: `render.py` (page plan, data-island documents), `pages.py` (HTML), templates `base.html`,
- **Errors:** found and fixed by replacing the old generator:
- **Verify:** `python -m pytest -q` → 521 passed; `python -m black --check .` clean;

### 20261101-16-local-first-translation — Local-first translation

- **Outcome:** `chattr-cli translate [--endpoint URL] [--model NAME] [--service S] [--limit N]`
- **Files:** - New: `translation.py` (detection, rules, client, settings, `translate_archive`).
- **Errors:** none in existing code. The old defaults pointed at OpenRouter with a placeholder key
- **Verify:** `python -m pytest -q` → 616 passed; `python -m black --check .` clean;

### 20261101-17-rebuild-chattr-sqlite-from-html-data-islands — Rebuild chattr.sqlite from HTML data islands

- **Outcome:** `chattr-cli rebuild [--from DIR] [--db FILE]` recreates `chattr.sqlite` from the data
- **Files:** - New: `rebuild.py` (`rebuild_database`, `compare_databases`, `read_islands`).
- **Errors:** found while writing the oracle and fixed in the island: handles that only sent a
- **Verify:** `python -m pytest -q` → 541 passed; `python -m black --check .` clean;

### 20261101-18-caixa-master-schema-v0-and-messages-adapter — Caixa master schema v0 and messages adapter

- **Outcome:** Caixa has a master database (`caixa.sqlite`, ordered migrations) with people,
- **Files:** - New: `caixa/schema.py`, `caixa/master.py`, `caixa/collectors/__init__.py`,
- **Errors:** none in existing code. One slip of mine: a commit went in with a failing test; fixed
- **Verify:** `python -m pytest -q` → 655 passed; `python -m black --check .` clean;

### 20261101-19-chattr-mirror-workflow — Chattr mirror workflow

- **Outcome:** `.github/workflows/mirror-chattr.yml` mirrors `tools/chattr/` to Chattr's repository on
- **Files:** - New: `.github/workflows/mirror-chattr.yml`, `tools/mirror/mirror-chattr.sh`,
- **Errors:** none. Not verified: the workflow itself has not run on GitHub (no token, and Actions
- **Verify:** `python -m pytest -q` → 670 passed; `python -m black --check .` clean;

### 20261101-20-collector-contract-and-registry — Collector contract and registry

- **Outcome:** Chattr's six sources (iMessage, WhatsApp, Messenger and Instagram, Mail, Google
- **Files:** `caixa/collectors/{base,options,registry,inputs,chattr}.py`, `caixa/box.py`,
- **Errors:** two of my own test expectations were wrong (the WhatsApp fixture chats hold 7 + 4 + 7
- **Verify:** `python -m pytest -q` 728 passed; `black --check .` and `mypy caixa tools/chattr/src`

### 20261101-21-caixa-service-layer-and-caixa-worker — Caixa service layer and caixa worker

- **Outcome:** One `Service` holds everything the interface and the command line can do; `caixa
- **Files:** `caixa/{service,worker,jobs,settings,cli,box,master}.py`,
- **Errors:** two of my own test expectations (the renamed person's trailing dot is dropped by
- **Verify:** `python -m pytest -q` 831 passed; `black --check .` and `mypy caixa

### 20261101-22-harness-plugin-skeleton — Harness plugin skeleton

- **Outcome:** `harness/` is a DeepSeek Harness bundle. Its host half starts `caixa worker` through DSH's
- **Files:** `harness/{package.json,cordis.patch.yml,tsconfig.json,README.md,pnpm-lock.yaml}`,
- **Errors:** `pkill -f` matched my own shell once (the command was killed, nothing lost); the first
- **Verify:** `pnpm --dir harness test` 46 passed (including the end-to-end run); `check-types` clean;

### 20261101-23-caixa-serve-launcher — caixa serve launcher

- **Outcome:** `caixa serve [--box PATH] [--read-only] [--port N] [--no-browser] [--stop] [--node PATH]`
- **Files:** `caixa/serve.py`, `caixa/cli.py`, `README.md`, `tests/{test_serve,test_serve_launch,test_serve_real}.py`,
- **Errors:** running the real `dsh` found two things the fake could not: `--patch` must precede the
- **Verify:** `python -m pytest -q` (the real-harness tests run when Node 24.9+, pnpm and a built

### 20261101-24-import-wizard-and-jobs-pages — Import wizard and jobs pages

- **Outcome:** The Caixa page is now an application with Box, Import and Jobs sections. Box: create or
- **Files:** `harness/src/client/*` (store, api, pages, components, locales, CSS module),
- **Errors:** the first e2e run showed the Import tab does not reset a finished wizard (by design: the
- **Verify:** `pnpm --dir harness test` 114 passed (jsdom component tests for every step, store,

### 20261101-25-people-page — People page

- **Outcome:** A People section: the queue of handles no one is named for (service, number or name,
- **Files:** `harness/src/client/pages/PeoplePage.tsx`, `store.ts`, `api.ts`, `locales.ts`,
- **Errors:** the first end-to-end run raced on the previous change's "pages are up to date" banner
- **Verify:** `pnpm --dir harness test` all passing (jsdom tests for the section; the browser test);

### 20261101-26-browse-page-and-settings-section — Browse page and Settings section

- **Outcome:** Two more sections. **Browse:** the box's folders and files with a breadcrumb and a viewer:
- **Files:** `harness/src/host/box-files.ts`, `routes.ts`; `harness/src/client/pages/{Browse,Settings}Page.tsx`,
- **Errors:** after a reload DSH shows its first-run dialogs again, which covered the page in the e2e test
- **Verify:** `pnpm --dir harness test` 194 passed (including the four end-to-end files against real DSH);

### 20261101-27-chattr-serve-web-ui — chattr-cli serve web UI

- **Outcome:** `chattr-cli serve` opens a small local web page (standard-library HTTP server, Jinja2,
- **Files:** `tools/chattr/src/chattr/{web,cli}.py`, `templates/web/*.html`, `static/htmx.min.js`
- **Errors:** a refused POST left its body unread and the next request on the connection failed
- **Verify:** `python -m pytest -q` 873 passed; black and mypy clean.

### 20261112-01-hot-fix-messenger-import-slows-down-with-every — Hot fix: Messenger import slows down with every thread

- **Outcome:** A large Messenger export imports in time proportional to its size. 320 threads: 51 s before, 2.3 s after.
- **Files:** caixa/collectors/chattr.py, tools/chattr/src/chattr/commands.py, tools/chattr/src/chattr/schema.py, tests/test_messenger_scale.py, tools/chattr/tests/test_schema.py
- **Errors:** none
- **Verify:** `python -m pytest -q` 1038 passed, 6 skipped (the real-harness launcher tests, which need Node on PATH); black and mypy clean; scratch timing run at 20/80/320/3000 threads.

### 20261112-02-hot-fix-the-caixa-page-must-scroll-with-its — Hot fix: the Caixa page must scroll, with its buttons in reach

- **Outcome:** The page scrolls, the wizard's buttons are pinned to the bottom of the window, long lists are folded.
- **Files:** harness/src/client/caixa.module.css, CaixaPage.tsx, pages/ImportPage.tsx, locales.ts, harness/tests/e2e-layout.test.ts, e2e-support.ts
- **Errors:** none
- **Verify:** Harness suite: 240 passed in 23 files; tsc clean. Looked at a screenshot of the preview at 1100 by 560.

### 20261112-03-hot-fix-orange-dates-and-heat-map-and-a-date — Hot fix: orange dates and heat map, and a date click returns to the top

- **Outcome:** Orange heat map and dates; sent messages are a pale orange tint instead of green; dates jump to the top.
- **Files:** tools/chattr/src/chattr/templates/base.html, page.html, tools/chattr/tests/test_render_pages.py
- **Errors:** none
- **Verify:** Chattr suite: 687 passed.

### 20261112-04-hot-fix-people-first-box-layout-with-readable — Hot fix: people-first box layout with readable file names

- **Outcome:** A people-first box with readable names throughout; each person has an index of everything from them.
- **Files:** tools/chattr/src/chattr/{filing,render,pages,commands,database_manager}.py, templates/{person,page,index,base}.html, caixa/collectors/chattr.py, caixa/box.py, tests (Python and harness), docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1069 passed, 6 skipped; harness 240 passed; black, mypy, tsc clean. Imported the synthetic family by command line and looked at Ana's index and 2024 page in a browser; ran the documented check script (6 in the box, 3 recorded but not copied, 0 missing).

### 20261112-05-hot-fix-voicemail-audio-that-plays-in-a-browser — Hot fix: voicemail audio that plays in a browser

- **Outcome:** Voicemail plays on its page; the original AMR is kept beside an AAC copy of about the same size.
- **Files:** tools/chattr/src/chattr/filing.py, templates/page.html, pages.py, caixa/collectors/chattr.py, tests
- **Errors:** none
- **Verify:** Covered by the same runs as ticket 20261112-04. ffmpeg here decodes AMR-NB and encodes AAC; a 3-second generated AMR gives an 8 kHz mono AAC file that Chromium loads and reports as 3 s long.

### 20261112-06-hot-fix-progress-during-preview-and-import — Hot fix: progress during preview and import

- **Outcome:** A person can see what a preview or an import is doing, how far it is, and stop a preview.
- **Files:** caixa/service.py, caixa/collectors/{base,chattr}.py, harness/src/client/{api.ts,store.ts,locales.ts,caixa.module.css,components/Progress.tsx,pages/ImportPage.tsx}, tests/test_progress.py, harness/tests/{progress,import-page}.test.tsx, e2e-support.ts, e2e-people.test.ts
- **Errors:** none
- **Verify:** `python -m pytest -q` 1077 passed, 6 skipped; harness 248 passed, twice in a row; black, mypy, tsc clean.

### 20261112-07-hot-fix-undo-the-last-import-and-run-an-import — Hot fix: undo the last import and run an import again

- **Outcome:** Undo the last import and Run again, in the browser and on the command line.
- **Files:** caixa/undo.py, caixa/service.py, caixa/cli.py, caixa/collectors/{base,chattr}.py, harness/src/client/{api.ts,store.ts,locales.ts,pages/JobsPage.tsx}, tests/test_undo.py, tests/test_cli_commands.py, harness/tests/{jobs-page.test.tsx,e2e-voicemail.test.ts}, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1090 passed, 6 skipped; harness 255 passed; black, mypy, tsc clean.

### 20261112-08-hot-fix-unbrand-the-harness-window — Hot fix: unbrand the harness window

- **Outcome:** The window is Caixa's: name, mark, title and first page. Two harness controls remain.
- **Files:** caixa/serve.py, harness/src/host/{index,routes}.ts, harness/src/client/{index.tsx,api.ts}, harness/tests/{e2e-shell,host,build}.test.ts, tests/test_serve.py, tests/test_serve_real.py, README.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1091 passed, 6 skipped; with Node on PATH the 6 real-launcher tests pass; harness 257 passed; black, mypy, tsc clean. Looked at a screenshot of the first screen.

### 20261112-09-imessage-build-queries-from-the-columns-the — iMessage: build queries from the columns the database has

- **Outcome:** The reader adapts to whatever columns the database has.
- **Files:** tools/chattr/src/chattr/imessage_schema.py, parsers/imessage_database_parser.py, commands.py, imessage_tools.py, tools/chattr/tests/test_imessage_schema.py
- **Errors:** none
- **Verify:** Chattr suite 717 passed; whole Python suite passed; mypy clean.

### 20261112-10-imessage-group-handles-into-people-read-macos — iMessage: group handles into people, read macOS Contacts, merge split conversations

- **Outcome:** One folder per person and one conversation per conversation, named from the Mac's Contacts.
- **Files:** tools/chattr/src/chattr/{imessage_groups,people,schema,database_manager,commands,cli}.py, parsers/imessage_parser.py, caixa/collectors/chattr.py, tools/chattr/NOTICE, docs/Documentation/Collector.md, tools/chattr/tests/test_imessage_people.py
- **Errors:** none
- **Verify:** `python -m pytest -q` 1117 passed, 6 skipped; black and mypy clean.

### 20261112-11-imessage-copy-attachments-into-the-box-and-report — iMessage: copy attachments into the box, and report the ones missing from this Mac

- **Outcome:** iMessage attachments are in the box; what is still in iCloud is listed by conversation.
- **Files:** tools/chattr/src/chattr/{blobs,commands,cli,database_manager}.py, parsers/imessage_parser.py, caixa/collectors/chattr.py, tests, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1127 passed, 6 skipped; harness 257 passed; mypy clean; the documented check script on a fresh box of the six synthetic sources: 9 in the box, 0 not copied, 0 missing.

### 20261112-12-imessage-edited-and-unsent-messages-replies-group — iMessage: edited and unsent messages, replies, group events

- **Outcome:** Replies, edits, unsent messages and conversation events are read and shown.
- **Files:** tools/chattr/src/chattr/{imessage_events,render,pages}.py, parsers/{imessage_parser,imessage_database_parser}.py, templates/{page,base}.html, tools/chattr/tests/test_imessage_events.py, docs/Documentation/Collector.md, tools/chattr/NOTICE
- **Errors:** none
- **Verify:** Chattr suite 770 passed; whole Python suite passed; black and mypy clean.

### 20261112-13-imessage-recently-deleted-messages-and-apple-s — iMessage: recently deleted messages and Apple's filter categories

- **Outcome:** Deleted messages are back in their conversations; Messages' own categories are kept and shown.
- **Files:** tools/chattr/src/chattr/imessage_schema.py, parsers/imessage_parser.py, pages.py, templates/{page,base}.html, tools/chattr/tests/test_imessage_events.py
- **Errors:** none
- **Verify:** Chattr suite 775 passed; whole Python suite passed; mypy clean.

### 20261112-14-imessage-link-previews-and-app-messages — iMessage: link previews and app messages

- **Outcome:** Link previews, Apple Pay and app messages are no longer blank.
- **Files:** tools/chattr/src/chattr/imessage_payload.py, parsers/imessage_parser.py, pages.py, templates/page.html, tools/chattr/tests/test_imessage_payload.py, docs/Documentation/Collector.md, tools/chattr/NOTICE
- **Errors:** none
- **Verify:** `python -m pytest -q` 1168 passed, 6 skipped; harness 257 passed; black and mypy clean.

### 20261112-15-pictures-filed-as-dated-jpeg-heic-png-and-webp — Pictures filed as dated JPEG (HEIC, PNG and WebP converted)

- **Outcome:** Done at filing time in chattr/filing.py with Pillow and pillow-heif (already dependencies). DateTimeOriginal is written by Pillow, so exiftool is no longer needed except for a JPEG that has EXIF but no date. What was done is recorded in attachments.processing_info, which also stops a re-import from filing the staged original again.
- **Files:** tools/chattr/src/chattr/{filing,commands,database_manager}.py, caixa/collectors/chattr.py, tools/chattr/tests/test_filing.py, tests/test_chattr_collectors.py, tools/chattr/tests/test_imessage_attachments.py, docs/Documentation/Collector.md
- **Errors:** Three older tests expected the fixture PNGs to stay PNG; updated to the new behaviour.
- **Verify:** python -m pytest -q: 1182 passed, 6 skipped (Node not on PATH); black and mypy clean. Not run against real iPhone HEIC files: the tests use pictures made by pillow-heif. exiftool is not installed here, so the EXIF-but-no-date JPEG path is untested.

### 20261113-01-attachments-stored-once-audio-filed-as-m4a — Attachments stored once; audio filed as m4a

- **Outcome:** file_attachments now works in message-time order and gives each (checksum, mail-or-chat) one home row; other rows are pointed at the home's path with processing_info {shared: true}. Every filed row is marked in processing_info, which is what stops a re-import from re-filing it. Audio conversion happens at filing like pictures.
- **Files:** tools/chattr/src/chattr/filing.py, caixa/collectors/chattr.py, tools/chattr/tests/test_filing.py, tests/test_chattr_collectors.py, docs/Documentation/Collector.md
- **Errors:** A first version let a re-import move the copy to another person (the home row lost its place to a linked row); fixed by marking every filed row. Mail and chat sharing one staged file left the second without one; the staged file is now copied when both need it.
- **Verify:** python -m pytest -q: 1193 passed, 6 skipped (Node not on PATH); harness vitest: 257 passed; black and mypy clean. Not run on a real export: the first real import is the check, in particular WhatsApp .opus voice notes and how much space sharing saves.

### 20261113-02-translation-through-an-openai-compatible-endpoint — Translation through an OpenAI-compatible endpoint, with key and test

- **Outcome:** Translation works from Settings to page. Chattr's translator gained the guardrails and concurrency; Caixa adds caixa/translation.py (key store, checks, test), two service methods and a step in the import run between matching people and filing.
- **Files:** tools/chattr/src/chattr/translation.py, caixa/translation.py, caixa/settings.py, caixa/service.py, caixa/collectors/{base,chattr}.py, harness/src/client/{api,locales}.ts, harness/src/client/pages/{SettingsPage,ImportPage}.tsx, harness/src/client/components/Progress.tsx, tests/test_translation.py, tools/chattr/tests/test_translation_client.py, tools/chattr/tests/test_translate_archive.py, harness/tests/{settings-page,progress}.test.tsx, harness/tests/e2e-translation.test.ts, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1220 passed, 6 skipped (Node not on PATH); harness vitest: 264 passed, including a browser test of Settings against the real worker and a stand-in endpoint; tsc, black and mypy clean. NOT verified: any real endpoint. No request was made to OpenRouter, DeepSeek, Ollama or LM Studio; every test uses a stand-in server that speaks the same format.

### 20261114-01-test-round-fixes-stale-interface-google-voice — Test round fixes: stale interface, Google Voice, Contacts setting, speech-to-text progress

- **Outcome:** All four done. serve.ensure_built compares the newest of harness/src, scripts and package.json with lib/. The Google Voice parser reads pages in two passes so names can be matched to numbers. Contacts are box settings (contacts.mac, contacts.file, contacts.region) applied in one place for every source. TimedTranscriber wraps the engine; lines marked '[caixa] ' on the worker's error stream are echoed by `caixa serve`.
- **Files:** caixa/{serve,service,settings}.py, caixa/collectors/chattr.py, tools/chattr/src/chattr/{filing,commands,transcription}.py, tools/chattr/src/chattr/parsers/google_voice_parser.py, harness/scripts/preset.mjs, harness/src/client/{api,locales}.ts, harness/src/client/pages/SettingsPage.tsx, harness/src/client/components/Progress.tsx, tests (test_serve, test_serve_launch, test_contacts_setting, test_transcription_progress, test_chattr_collectors, fake_dsh), tools/chattr/tests/{test_google_voice_parser,test_filing}.py, harness/tests, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1250 passed, 6 skipped (Node not on PATH); harness vitest: 268 passed; tsc, black, mypy clean. The rebuild was run for real here (stale, rebuilt, current; new strings present in lib/client.js). NOT verified: a real Google Voice Takeout (the cases are written from the format as documented and the maintainer's examples); real Mac Contacts and the Full Disk Access message; a real speech model.

### 20261114-02-speech-to-text-all-recordings-in-one-whisper-cpp — Speech-to-text: all recordings in one whisper.cpp run

- **Outcome:** Done. transcribe_all asks the engine for transcribe_many when it has one. Results are found by watching for each recording's text file while the program runs.
- **Files:** tools/chattr/src/chattr/transcription.py, caixa/collectors/chattr.py, tools/chattr/tests/test_transcription.py, tests/test_transcription_progress.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q passes; black and mypy clean. NOT verified with the real whisper-cli: it is not installed here. The tests use a stand-in program that takes the same arguments; the argument handling was read from whisper.cpp's source, and a version that ignores -of is allowed for. The maintainer's first voicemail import with transcription on is the real check; the per-recording times in the terminal will show whether the model is loaded once.

### 20261114-03-google-voice-transcribe-voicemail-recordings-with — Google Voice: transcribe voicemail recordings with the local speech model

- **Outcome:** Done. The speech options and the engine set-up are now shared by the two sources.
- **Files:** tools/chattr/src/chattr/parsers/google_voice_parser.py, tools/chattr/src/chattr/commands.py, caixa/collectors/chattr.py, tools/chattr/tests/test_google_voice_parser.py, tests/test_transcription_progress.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1263 passed, 6 skipped; harness vitest: 268 passed; black and mypy clean. Not run with a real speech model or a real Takeout.

### 20261114-04-transcription-on-by-default-with-a-saved-model — Transcription on by default with a saved model; show which code is running

- **Outcome:** Done. caixa/revision.py reads the commit from .git without running git and compares source times with a start time.
- **Files:** caixa/{revision,worker,serve,service}.py, caixa/collectors/chattr.py, harness/src/client/{api,locales}.ts, harness/src/client/pages/SettingsPage.tsx, tests/{test_revision,test_transcription_progress,test_chattr_collectors}.py, harness/tests/{settings-page.test.tsx,e2e-voicemail.test.ts}, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q passes; harness vitest: 270 passed; tsc, black, mypy clean. The cause of the missing option is inferred from the code, not observed on the maintainer's machine: the commit line in Settings will confirm it.

### 20261116-01-messenger-keep-only-conversations-with-facebook — Messenger: keep only conversations with Facebook friends; name-only contacts

- **Outcome:** Done. chattr/meta_friends.py reads the lists; commands.convert takes keep=; the Messenger collector filters, reports and names friends via DatabaseManager.name_handles.
- **Files:** tools/chattr/src/chattr/{meta_friends,commands,database_manager,people}.py, caixa/collectors/chattr.py, tools/chattr/tests/{test_meta_friends,test_people,test_imessage_people}.py, tests/{test_messenger_friends,test_translation}.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1283 passed, 6 skipped; harness vitest: 270 passed; black and mypy clean. NOT verified against a real Facebook export: the file names and keys are written from known export layouts; if the maintainer's export uses another, the import will say no list was found.

### 20261116-02-naming-names-shown-by-whatsapp-and-google-voice — Naming: names shown by WhatsApp and Google Voice count; deactivated Facebook accounts kept

- **Outcome:** Done.
- **Files:** tools/chattr/src/chattr/parsers/messenger_parser.py, tools/chattr/src/chattr/meta_friends.py, caixa/collectors/chattr.py, tests/{test_messenger_friends,test_chattr_collectors,test_service_people,test_cli_commands,test_undo,test_worker_protocol}.py, harness/tests/e2e-people.test.ts, docs/Documentation/Collector.md
- **Errors:** Ten tests assumed WhatsApp 'Ana Costa' was unnamed; updated (link with move, or rename).
- **Verify:** python -m pytest -q: 1286 passed, 6 skipped; harness vitest: 270 passed. Not run on a real export.

### 20261116-03-one-page-per-person-fast-for-very-long-histories — One page per person, fast for very long histories

- **Outcome:** Done. render.py plans one PageSpec per person/group; pages.py draws it with the relations worked out once; the island is compacted on write and expanded on read.
- **Files:** tools/chattr/src/chattr/{render,pages,rebuild}.py, tools/chattr/src/chattr/templates/{base,page,index}.html (person.html removed), caixa/box.py, many tests under tests/ and tools/chattr/tests/, harness/tests/{e2e-browse,e2e-people}.test.ts, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1287 passed, 6 skipped; harness vitest: 270 passed (including the browse page opening a person's page and following the year bar inside Caixa's viewer). Performance measured in Chromium only; Safari 18+ and Firefox 125+ support content-visibility, but were not measured.

### 20261116-04-reset-a-box-s-data-keeping-its-settings — Reset a box's data, keeping its settings

- **Outcome:** Done.
- **Files:** caixa/{reset,service,cli}.py, harness/src/client/{api,locales}.ts, harness/src/client/pages/SettingsPage.tsx, tests/{test_reset,test_worker_protocol}.py, harness/tests/{settings-page.test.tsx,e2e-reset.test.ts,fake-api.ts}, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1293 passed, 6 skipped; harness vitest: 273 passed (including a browser reset against the real worker). black, mypy, tsc clean.

### 20261116-05-picture-lightbox-iphone-voicemail-callers-named — Picture lightbox; iPhone voicemail callers named; large pages in Caixa's viewer

- **Outcome:** Done.
- **Files:** tools/chattr/src/chattr/templates/{lightbox.js,page.html,base.html}, tools/chattr/src/chattr/pages.py, harness/src/host/{box-files,page-scripts}.ts, harness/src/client/pages/BrowsePage.tsx, caixa/collectors/chattr.py, tests and harness tests, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1297 passed, 6 skipped; harness vitest: 275 passed, including the lightbox opening and closing on a real page inside Caixa's viewer with no policy errors, and a 21 MB page rewritten as it is streamed.

### 20261116-06-facebook-noise-and-group-rules-requests-silent — Facebook noise and group rules: requests, silent members, numbers in groups

- **Outcome:** Done.
- **Files:** tools/chattr/src/chattr/{database_manager,commands,meta_friends}.py, caixa/collectors/{chattr,messages}.py, tests/{test_group_rules,test_messenger_friends,test_messenger_scale,test_chattr_collectors}.py, tools/chattr/tests/test_meta_friends.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1304 passed, 6 skipped; harness vitest: 275 passed; black and mypy clean. Not run on a real Facebook download.

### 20261116-07-index-page-categories-people-tiles-dashboard-nord — Index page: categories, people tiles, dashboard; Nord theme

- **Outcome:** Done.
- **Files:** caixa/{schema,master,service,reset}.py, caixa/collectors/chattr.py, tools/chattr/src/chattr/{pages,commands}.py, tools/chattr/src/chattr/templates/{index.html,index.js,base.html,page.html,mail.html}, harness/src/host/{box-files,page-scripts}.ts, tests/test_categories.py, tools/chattr/tests/{test_render_pages,test_render_mail}.py, harness/tests/{e2e-categories,e2e-browse,e2e-wizard}.test.ts, docs/Documentation/Collector.md
- **Errors:** The dashboard first showed a Python method instead of the item count (a template looking up 'items' on a dict); caught by the undo tests and fixed. The tooltip was clipped by the tiles' layout containment; removed.
- **Verify:** python -m pytest -q: 1313 passed, 6 skipped; harness vitest: 276 passed, including sorting three people in Caixa's viewer (selection, drag, footer button, saved categories, redrawn index). Looked at light, dark, narrow and tooltip renders.

### 20261117-01-owner-preference-file-and-removing-people-from-a — Owner preference file and removing people from a box

- **Outcome:** Owner file and removing people work end to end on the synthetic family; 1,326 tests pass.
- **Files:** caixa/owner.py, caixa/service.py, caixa/reset.py, caixa/master.py, caixa/schema.py, caixa/collectors/{chattr,messages}.py, tools/chattr/src/chattr/{database_manager,schema,commands}.py, tests/test_owner.py, tools/chattr/tests/test_remove_people.py
- **Errors:** An archive emptied by removal skipped rendering, leaving the old page and index; publish now redraws when a pages list exists.
- **Verify:** python -m pytest -q (1326 passed, 6 skipped); black; mypy clean

### 20261117-02-index-page-unassign-select-delete-open-in-new — Index page: unassign, select, delete, open in new window, name unrecognized

- **Outcome:** All four interactions work in Caixa's viewer; the redrawn index file reflects them.
- **Files:** tools/chattr/src/chattr/{pages.py,templates/index.html,templates/index.js}, harness/src/host/page-scripts.ts, harness/src/client/pages/BrowsePage.tsx, harness/tests/{e2e-categories.test.ts,browse-page.test.tsx}, tools/chattr/tests/test_render_pages.py, docs/Documentation/Collector.md
- **Errors:** A sandboxed frame never fires a form's submit event (no allow-forms), so Apply is a plain button with Enter handled by the script. The ↗ label kept the old name after naming; labels now follow.
- **Verify:** python -m pytest -q (1326 passed); vitest run (276 passed); tsc clean

### 20261117-03-people-page-select-and-delete-records-not-yet — People page: select and delete records not yet named

- **Outcome:** Records not yet named can be chosen and deleted from the People section.
- **Files:** harness/src/client/{api.ts,locales.ts,pages/PeoplePage.tsx}, harness/tests/{fake-api.ts,people-page.test.tsx,e2e-people.test.ts}, caixa/service.py, tests/test_owner.py
- **Errors:** The list reloaded straight after deleting and showed the records again until the redraw job ran; the service now leaves removed handles out at once.
- **Verify:** python -m pytest -q (1327 passed); vitest run (279 passed); tsc clean

### 20261117-04-collector-service-separate-from-the-deepseek — Collector service separate from the DeepSeek harness

- **Outcome:** Caixa runs as its own window; all 279 browser and unit tests and the Python suite pass against it.
- **Files:** caixa/web.py, caixa/serve.py, caixa/cli.py, caixa/diagnostics.py, caixa/data/web/*, harness/src/app/*, harness/scripts/build-app.mjs, harness/src/client/{caixa.module.css,store.ts,pages/SettingsPage.tsx}, harness/tests/*, tests/test_web_server.py, tests/test_serve.py, tools/chattr/src/chattr/templates/index.js, README.md, harness/README.md, docs/ai/Istanbul/Phase1-Collector/(2026-11-01) Phase1-Collector Requirements.md
- **Errors:** A refusal that left a request body unread spoiled the next request on the same connection (body now read first). Script hashes were off by the newline Jinja drops. Overlapping job-list refreshes answered out of order and an older answer hid the Undone mark (only the newest now counts). My first test file name clashed with Chattr's test_web.py.
- **Verify:** python -m pytest -q; black; mypy; vitest run (279 passed, including every end-to-end test against `caixa serve`); tsc clean

### 20261117-05-remove-the-deepseek-plugin-rename-harness-to-web — Remove the DeepSeek plugin, rename harness to web, box pages in their own window

- **Outcome:** Caixa has nothing of DeepSeek left; the index page has the whole window for sorting, naming and removing.
- **Files:** web/ (was harness/), caixa/web.py, caixa/worker.py, caixa/state.py, tools/chattr/src/chattr/templates/{index.html,index.js}, tools/chattr/tests/test_render_pages.py, tests/test_web_server.py, README.md, docs/Documentation/Collector.md, docs/ai/Istanbul/Phase1-Collector/(2026-11-01) Phase1-Collector Requirements.md
- **Errors:** One run of the categories browser test clicked a person's page while the redraw started by a removal was rewriting it; the test now waits for the redraw.
- **Verify:** python -m pytest -q; black; mypy; vitest run (225 passed, all end-to-end tests against `caixa serve`); tsc clean

### 20261117-06-index-page-categories-dead-on-pages-drawn-with-an — Index page categories dead on pages drawn with an older script

- **Outcome:** Index pages drawn by any earlier version work again in Caixa without being redrawn.
- **Files:** caixa/web.py, tests/test_web_server.py
- **Errors:** none
- **Verify:** python -m pytest -q (1281 passed); vitest run (225 passed); black; mypy

### 20261117-07-index-page-tools-only-on-hover-name-field-with — Index page tools only on hover; name field with suggestions of known people

- **Outcome:** Tiles are clean until hovered; naming an unrecognized number offers the people already in the box.
- **Files:** tools/chattr/src/chattr/templates/{index.js,index.html}, web/tests/e2e-categories.test.ts, docs/Documentation/Collector.md
- **Errors:** The field is hidden from screen readers until hovered, so the test finds it by element, not role. The tile's information pop-up covered the page while typing; hidden while the field has focus.
- **Verify:** python -m pytest -q (1281 passed); vitest run (225 passed)

### 20261118-01-unrecognized-sorted-busiest-first — Unrecognized sorted busiest first

- **Outcome:** Unrecognized is busiest first.
- **Files:** tools/chattr/src/chattr/{pages.py,templates/index.html,templates/index.js}, web/tests/e2e-categories.test.ts, docs/Documentation/Collector.md
- **Errors:** The template's p.items read as the dictionary's items method (the same trap as the dashboard once); the field is item_count.
- **Verify:** python -m pytest -q (1281 passed); vitest run (225 passed)

### 20261118-02-imessage-messages-without-a-chat-mixed-into-one — iMessage messages without a chat mixed into one (no chat) person

- **Outcome:** No more (no chat) person: those messages are with their people.
- **Files:** tools/chattr/src/chattr/{parsers/imessage_parser.py,database_manager.py,commands.py}, caixa/collectors/chattr.py, tools/chattr/tests/test_imessage_orphans.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q (1285 passed); vitest run (225 passed); black; mypy

### 20261118-03-owner-replies-in-deleted-imessage-chats-missing — Owner replies in deleted iMessage chats missing from their person

- **Outcome:** The owner's replies in deleted chats are back with the people they were written to, where Messages kept the thread.
- **Files:** tools/chattr/src/chattr/{imessage_schema.py,parsers/imessage_parser.py,commands.py}, tools/chattr/tests/test_imessage_orphans.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q (1287 passed); vitest run (225 passed); black; mypy

### 20261118-04-google-voice-texts-forwarded-to-the-phone — Google Voice texts forwarded to the phone duplicated as iMessage

- **Outcome:** Forwarded copies go; Google Voice's conversations, with both sides, are what the box shows.
- **Files:** tools/chattr/src/chattr/database_manager.py, caixa/collectors/chattr.py, tools/chattr/tests/test_forwarded_copies.py, tests/test_owner.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q (1290 passed); vitest run (225 passed); black; mypy

---

## Errors and deviations

- **20261101-01-caixa-repository-foundations**: none.
- **20261101-02-synthetic-fixture-family**: - **MBOX determinism bug:** random MIME boundaries and current-time From_ lines; fixed in T05.
- **20261101-03-chattr-import-and-licensing**: none. One whole-history scan matched the ticket's own `grep` pattern for the key
- **20261101-04-chattr-stabilization**: - **Fixed real bugs:** six wrong configuration keys; the HTML crash on `sqlite3.Row`;
- **20261101-05-unified-schema-v0-chattr-sqlite**: none.
- **20261101-06-interactive-menu-and-command-line**: found in review and fixed with tests:
- **20261101-07-imessage-parser**: found and fixed, each with a test:
- **20261101-08-whatsapp-parser**: found and fixed, each with a test:
- **20261101-09-messenger-and-instagram-parser**: found and fixed, each with a test:
- **20261101-10-mbox-email-parser**: none in existing code. Decisions with consequences:
- **20261101-11-google-voice-parser**: none in existing code. Notes:
- **20261101-12-iphone-voicemail-and-local-speech-to-text**: none in existing code. **What was not verified:** no speech-to-text model or runtime
- **20261101-13-one-attachment-pipeline**: found and fixed:
- **20261101-14-people-roles-contacts-and-aliases**: none in existing code. Behaviour changes to note:
- **20261101-15-html-rendering-from-the-database**: found and fixed by replacing the old generator:
- **20261101-16-local-first-translation**: none in existing code. The old defaults pointed at OpenRouter with a placeholder key
- **20261101-17-rebuild-chattr-sqlite-from-html-data-islands**: found while writing the oracle and fixed in the island: handles that only sent a
- **20261101-18-caixa-master-schema-v0-and-messages-adapter**: none in existing code. One slip of mine: a commit went in with a failing test; fixed
- **20261101-19-chattr-mirror-workflow**: none. Not verified: the workflow itself has not run on GitHub (no token, and Actions
- **20261101-20-collector-contract-and-registry**: two of my own test expectations were wrong (the WhatsApp fixture chats hold 7 + 4 + 7
- **20261101-21-caixa-service-layer-and-caixa-worker**: two of my own test expectations (the renamed person's trailing dot is dropped by
- **20261101-22-harness-plugin-skeleton**: `pkill -f` matched my own shell once (the command was killed, nothing lost); the first
- **20261101-23-caixa-serve-launcher**: running the real `dsh` found two things the fake could not: `--patch` must precede the
- **20261101-24-import-wizard-and-jobs-pages**: the first e2e run showed the Import tab does not reset a finished wizard (by design: the
- **20261101-25-people-page**: the first end-to-end run raced on the previous change's "pages are up to date" banner
- **20261101-26-browse-page-and-settings-section**: after a reload DSH shows its first-run dialogs again, which covered the page in the e2e test
- **20261101-27-chattr-serve-web-ui**: a refused POST left its body unread and the next request on the connection failed
- **20261112-15-pictures-filed-as-dated-jpeg-heic-png-and-webp**: Three older tests expected the fixture PNGs to stay PNG; updated to the new behaviour.
- **20261113-01-attachments-stored-once-audio-filed-as-m4a**: A first version let a re-import move the copy to another person (the home row lost its place to a linked row); fixed by marking every filed row. Mail and chat sharing one staged file left the second without one; the staged file is now copied when both need it.
- **20261116-02-naming-names-shown-by-whatsapp-and-google-voice**: Ten tests assumed WhatsApp 'Ana Costa' was unnamed; updated (link with move, or rename).
- **20261116-07-index-page-categories-people-tiles-dashboard-nord**: The dashboard first showed a Python method instead of the item count (a template looking up 'items' on a dict); caught by the undo tests and fixed. The tooltip was clipped by the tiles' layout containment; removed.
- **20261117-01-owner-preference-file-and-removing-people-from-a**: An archive emptied by removal skipped rendering, leaving the old page and index; publish now redraws when a pages list exists.
- **20261117-02-index-page-unassign-select-delete-open-in-new**: A sandboxed frame never fires a form's submit event (no allow-forms), so Apply is a plain button with Enter handled by the script. The ↗ label kept the old name after naming; labels now follow.
- **20261117-03-people-page-select-and-delete-records-not-yet**: The list reloaded straight after deleting and showed the records again until the redraw job ran; the service now leaves removed handles out at once.
- **20261117-04-collector-service-separate-from-the-deepseek**: A refusal that left a request body unread spoiled the next request on the same connection (body now read first). Script hashes were off by the newline Jinja drops. Overlapping job-list refreshes answered out of order and an older answer hid the Undone mark (only the newest now counts). My first test file name clashed with Chattr's test_web.py.
- **20261117-05-remove-the-deepseek-plugin-rename-harness-to-web**: One run of the categories browser test clicked a person's page while the redraw started by a removal was rewriting it; the test now waits for the redraw.
- **20261117-07-index-page-tools-only-on-hover-name-field-with**: The field is hidden from screen readers until hovered, so the test finds it by element, not role. The tile's information pop-up covered the page while typing; hidden while the field has focus.
- **20261118-01-unrecognized-sorted-busiest-first**: The template's p.items read as the dictionary's items method (the same trap as the dashboard once); the field is item_count.

---

## Testing guide for human testers

Run the verify command above first and confirm it passes. Then, with a box of your own
(`caixa serve`, Box, Create), the quickest way through the whole project is:

1. **Import** each source you have from the Import section: preview it, import it, and read what
   the import says (people found, groups left out, files missing). Undo one import from Jobs and
   run it again.
2. **Browse**, then **Open the box's index page**: it opens in a window of its own. Check the
   dashboard's numbers against what you expect, open a few people (every source on one page, the
   year bar, pictures full size, voicemails that play).
3. **Sort**: in Unassigned select people and drag them onto a category; in a category hover a
   tile and use its ×. In Unrecognized (busiest first) type a name under a number, pick a person
   already in the box from the suggestions, or a new name; remove a few with Delete.
4. **People**: name a number, rename someone, merge two; in "Not yet named" tick the box at the
   top, choose some records and Delete.
5. **Settings**: Contacts, translation (Test), speech-to-text; then **Start this box again** and
   import once more: your categories, names and removals come back.

The checks for each ticket follow; the ones under the later tickets are the most current.

### 20261101-01-caixa-repository-foundations — Caixa repository foundations

- Try: `pyproject.toml` defines the `caixa` package (Python >= 3.10) with a `caixa` console script
- Try: `python -m pytest -q` runs and passes (at least one smoke test)
- Try: `python -m black --check .` and `python -m mypy caixa` are clean
- Try: `.gitignore` covers Python build/test artifacts, generated boxes and databases

### 20261101-02-synthetic-fixture-family — Synthetic fixture family

- Try: A builder script creates a synthetic iMessage `chat.db` (long attributedBody messages, both epoch formats, same-second attachments, tapbacks on attachments, a group chat)
- Try: WhatsApp exports in iOS and Android formats with media and 'media omitted' lines
- Try: Messenger/Instagram JSON with mojibake text, shares and attachments
- Try: An MBOX with RFC 2047 headers, HTML-only mail, attachments and threads
- Try: A Google Voice Takeout sample (texts, calls, voicemails with audio) and iPhone voicemail audio + metadata
- Try: A vCard file linking the family's handles
- Try: Fixtures are generated deterministically and contain only fictional names and numbers

### 20261101-03-chattr-import-and-licensing — Chattr import and licensing

- Try: `git subtree add --prefix=tools/chattr` imports Chattr `main` (0152912) with full history
- Try: `src/parsers/imessage_database_parser.py` and `src/imessage_tools.py` are reviewed for code derived from imessage-exporter (GPL-3.0); findings recorded in this ticket's Notes and any derived parts flagged for rewrite
- Try: Chattr carries a GPL-3.0-or-later `LICENSE` and a `NOTICE` attributing the parts derived from imessage-exporter (decision 2026-11-02, replacing the original MIT plan)
- Try: No `.db`, key material or IDE files enter Caixa's history

### 20261101-04-chattr-stabilization — Chattr stabilization

- Try: The name is 'Chattr' everywhere (`~/.chattr.json`, `~/Documents/Chattr`, `chattr.sqlite`, `chattr-cli` command)
- Try: Preflight and configuration are wired: pointer → root → global `config.json` merged with `Services/<Service>.json`
- Try: iMessage configuration keys resolve (Quick/List/Diagnostics no longer fail)
- Try: Preflight repair keeps existing preferences and state; `--root` works without prompting
- Try: HTML generation no longer crashes and the template uses the database field names
- Try: Unused dependencies removed; stale docs consolidated

### 20261101-05-unified-schema-v0-chattr-sqlite — Unified schema v0 (chattr.sqlite)

- Try: Tables per the Requirements data model: conversations, handles, participants, messages, attachments, reactions, imports, schema_version
- Try: Ordered migrations; stable IDs; upserts make re-imports idempotent
- Try: `imports` and `Services/*.json` `state` updated on every run
- Try: Native per-service JSON export still available

### 20261101-06-interactive-menu-and-command-line — Interactive menu and command line

- Try: Waterfall menu: services → central DB or service folder → optional HTML, with overridable defaults
- Try: `chattr-cli convert <service> <export> [--root] [--db|--json] [--contacts] [--aliases] [--html]`
- Try: Restored iMessage flags: `--region`, `--attachment-root`, `--batch-size`, `--verbose`, `--attachment-workers`
- Try: Every menu action can be performed non-interactively

### 20261101-07-imessage-parser — iMessage parser

- Try: attributedBody is decoded with a real typedstream decoder; long messages are not truncated
- Try: Both seconds and nanoseconds epochs handled; UTC + offset stored
- Try: Spam filter runs on the parallel path and tags rather than drops
- Try: Tapbacks on attachments (`p:1/`, `bp:`) attach to their targets
- Try: All tools open `chat.db` read-only

### 20261101-08-whatsapp-parser — WhatsApp parser

- Try: iOS and Android/locale date formats parse
- Try: Continuation lines keep indentation; 'media omitted' kept as placeholders
- Try: Media renamed and dated via AttachmentManager

### 20261101-09-messenger-and-instagram-parser — Messenger and Instagram parser

- Try: Encoding fix applied to all text fields
- Try: Attachments recorded
- Try: Shared links stored, not folded into the body

### 20261101-10-mbox-email-parser — MBOX email parser

- Try: Threads by Message-ID / In-Reply-To / References and Gmail thread ID
- Try: RFC 2047 headers decoded; HTML and plain bodies kept
- Try: Attachments stored by hash

### 20261101-11-google-voice-parser — Google Voice parser

- Try: Texts, calls and voicemails become entries with correct content types
- Try: Voicemail audio kept as an attachment

### 20261101-12-iphone-voicemail-and-local-speech-to-text — iPhone Voicemail and local speech-to-text

- Try: A transcription interface with a local model backend and a test stub
- Try: Transcript stored with the entry; audio kept as an attachment
- Try: No network access during transcription

### 20261101-13-one-attachment-pipeline — One attachment pipeline

- Try: Archival `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>` names with no collisions
- Try: Originals kept; date written into standard metadata where supported
- Try: Per-person `Attachments/` folders

### 20261101-14-people-roles-contacts-and-aliases — People: roles, contacts and aliases

- Try: `--contacts` (vCard) and `--aliases` (JSON) inputs
- Try: Owner/author/sender derived, not duplicated
- Try: Unresolved-handle report

### 20261101-15-html-rendering-from-the-database — HTML rendering from the database

- Try: Date-named, self-contained pages merging all platforms with platform badges
- Try: Stable `id="m-<id>"` anchors and an embedded JSON data island
- Try: Escaped content; heatmap calendar; call/voicemail entries; mail pages by thread

### 20261101-16-local-first-translation — Local-first translation

- Try: Endpoint configurable; local default; key from environment only
- Try: Translation-skip heuristic restored from `60b276c`

### 20261101-17-rebuild-chattr-sqlite-from-html-data-islands — Rebuild chattr.sqlite from HTML data islands

- Try: Deleting `chattr.sqlite` and rebuilding from HTML gives identical IDs and counts

### 20261101-18-caixa-master-schema-v0-and-messages-adapter — Caixa master schema v0 and messages adapter

- Try: Migrations; items, people, aliases, item → person links with roles, imports, change log
- Try: Adapter ATTACHes `chattr.sqlite` and upserts by stable ID; appends change-log rows
- Try: `aliases.json` exported from the master
- Try: Re-syncing unchanged data writes zero change-log rows

### 20261101-19-chattr-mirror-workflow — Chattr mirror workflow

- Try: `.github/workflows/mirror-chattr.yml` pushes `git subtree split --prefix=tools/chattr` as a fast-forward
- Try: Write token documented as a repository secret (created by the maintainer)
- Try: 'Developed in Caixa' banner in Chattr's README

### 20261101-20-collector-contract-and-registry — Collector contract and registry

- Try: `caixa.collectors` entry-point discovery
- Try: Each collector declares inputs, 'how to export' instructions, an options JSON Schema, `preview` and `run`
- Try: Chattr's six sources registered

### 20261101-21-caixa-service-layer-and-caixa-worker — Caixa service layer and caixa worker

- Try: stdio JSON-RPC methods for box, collectors, import, jobs, people, browse, settings
- Try: SQLite jobs table with progress notifications; inbox folder watching
- Try: `--read-only` rejects every write method
- Try: CLI uses the same layer; worker-protocol pytest suite

### 20261101-22-harness-plugin-skeleton — Harness plugin skeleton

- Try: Pinned dsh version + `engines.dsh`; reproduced client build preset
- Try: Host service supervises `caixa worker`; owner-only `/api/caixa/*` routes plus a streaming progress route
- Try: Sidebar icon opens an empty Caixa page
- Try: `pnpm --dir harness test` passes

### 20261101-23-caixa-serve-launcher — caixa serve launcher

- Try: Node 24.9+ check with a clear message
- Try: Caixa's own DSH home; plugin installed; privacy patch disables session-log upload and telemetry
- Try: Sele's launch rules; reattach after a crash; token never logged

### 20261101-24-import-wizard-and-jobs-pages — Import wizard and jobs pages

- Try: Source list with 'how to export' cards; file picker and inbox
- Try: Options forms generated from collector schemas; preview; run with live progress; result report
- Try: Jobs and logs page; toasts on completion
- Try: Browser imports match CLI imports for every fixture

### 20261101-25-people-page — People page

- Try: Unresolved-handle queue; link, merge, rename
- Try: Affected pages re-rendered after a change

### 20261101-26-browse-page-and-settings-section — Browse page and Settings section

- Try: Generated pages served through `/api/caixa/box/*`
- Try: Settings: box location, local model endpoints, privacy defaults

### 20261101-27-chattr-serve-web-ui — chattr-cli serve web UI

- Try: Jinja2 + htmx; service, export, options, run with progress, open output
- Try: Works without Caixa, Node or DeepSeek Harness

### 20261112-01-hot-fix-messenger-import-slows-down-with-every — Hot fix: Messenger import slows down with every thread

- Try: The time per thread does not grow with the threads already read (measured: 20, 80, 320 and 3,000 threads all at 7 to 9 ms per thread; 3,000 threads preview in 24 s).
- Try: People are linked once per import, not once per thread.
- Try: Every top folder of a Facebook export is read, from the `messages` folder or from the export's root.
- Try: A thread with no messages is skipped and reported, instead of failing the whole export; an export where every thread is empty is still refused.
- Try: Progress names the thread's folder, not `message_1.json`.

### 20261112-02-hot-fix-the-caixa-page-must-scroll-with-its — Hot fix: the Caixa page must scroll, with its buttons in reach

- Try: Every section can be scrolled to its end with the mouse wheel in a short window (tested at 1100 by 560).
- Try: The wizard's Back and Continue/Import buttons stay in view however long the step is.
- Try: A long list of people in the preview shows the first 12 and a 'Show all N' button.

### 20261112-03-hot-fix-orange-dates-and-heat-map-and-a-date — Hot fix: orange dates and heat map, and a date click returns to the top

- Try: The heat map is four steps of orange, darker for busier days; #FA9237 is one of the steps.
- Try: Date headings are orange and still readable (contrast at least 4.5 to 1 against the page in light and dark).
- Try: No theme colour on the page is green (the WhatsApp badge keeps its own colour).
- Try: Every date heading is a link to the top of the page.

### 20261112-04-hot-fix-people-first-box-layout-with-readable — Hot fix: people-first box layout with readable file names

- Try: The box's top level is `People/`, `Groups/`, `Mail/`, `Inbox/`, `index.html`, `README.md`; there is no `Messages/` or `Audio/`.
- Try: Every person and group has an `index.html`: items by year and by source, the groups they are in, the mail they are in; year pages link back to it and the box's index links to it.
- Try: Every attachment is at `People/<Person>/<Source>/(date) time sender.ext` (groups under `Groups/`, mail under `Mail/<year>/Attachments/` with its own name kept). No visible file has a hash in its name (tested).
- Try: Naming or renaming a person moves their files with their pages; pages no longer wanted are removed, and only pages Caixa wrote.
- Try: Importing the same export again leaves one copy of each file.
- Try: The wizard and the command line still produce byte-identical boxes (e2e-wizard).

### 20261112-05-hot-fix-voicemail-audio-that-plays-in-a-browser — Hot fix: voicemail audio that plays in a browser

- Try: A voicemail's page plays in a browser (checked in Chromium: the `.m4a` loads with its duration and no error).
- Try: The original recording is kept, untouched, beside the playable copy and linked from the page.
- Try: Without ffmpeg the import finishes, the originals are filed, and the result says how many recordings have no playable copy and why; a file ffmpeg cannot convert is not blamed on a missing program.
- Try: The copy is made once and moves with its original when a person is renamed.

### 20261112-06-hot-fix-progress-during-preview-and-import — Hot fix: progress during preview and import

- Try: The preview shows its stages, 'N of M', what is being read, a bar and the time so far, and can be stopped (the worker stops counting).
- Try: The import shows all six stages with the current one marked, 'N of M', the time so far and, once there is enough to go on, roughly how long is left.
- Try: Reporting progress does not slow a large import: thousands of quick steps are announced at most a few times a second, always including each stage's first and last step.
- Try: A collector whose preview takes no progress callback still works.

### 20261112-07-hot-fix-undo-the-last-import-and-run-an-import — Hot fix: undo the last import and run an import again

- Try: Undoing an import leaves the box exactly as it was before it: the same visible files (by content) and the same rows in the master database (tested by comparing both).
- Try: Undo goes back one import at a time, newest first; the last 3 can be undone.
- Try: Naming people after the import is undone with it, their files go back to where they were, and the person is told how many such changes will go.
- Try: Undo is refused while an import runs and in a read-only box; it asks twice in the browser and once on the command line.
- Try: Any earlier import can be run again with the same source and options (`import.again`, `caixa again N`, Run again in Jobs).
- Try: The export is never touched.

### 20261112-08-hot-fix-unbrand-the-harness-window — Hot fix: unbrand the harness window

- Try: Started by `caixa serve`, the window is called Caixa: the sidebar's brand, and the browser tab's title (tested in the real harness).
- Try: It opens on the Caixa page with nothing to click first.
- Try: The harness's Plugins and Automation tasks entries are gone; no DeepSeek notice, sign-in prompt, name or mark is shown on the first screen.
- Try: Inside someone's own harness (not started by `caixa serve`) Caixa stays a guest: one more panel, nothing renamed.

### 20261112-09-imessage-build-queries-from-the-columns-the — iMessage: build queries from the columns the database has

- Try: The reader looks at the live schema once and asks only for columns that exist; missing ones read as empty.
- Try: An old database (seven message columns) imports with no fallback and no complaint; columns the reader does not know are ignored.
- Try: Paired and optional features are detected: filter categories (both columns), recently deleted, conversation lookup, person-centric IDs, replies, edits, tapbacks.
- Try: A database with no `message` table says it is not a Messages database.
- Try: `chattr-cli doctor` lists the schema's capabilities.

### 20261112-10-imessage-group-handles-into-people-read-macos — iMessage: group handles into people, read macOS Contacts, merge split conversations

- Try: Handle rows are one person when they share an address, a non-empty `person_centric_id`, or a Contacts card.
- Try: Chats with the same people and the same kind are one conversation (named ones only with the same name; unnamed ones join the earliest named); chats tied in `chat_lookup` are one; chats with nobody are left alone.
- Try: A split conversation is imported as one, with everyone's addresses as its participants.
- Try: Naming one address of a group names the others; two different names in a group are left alone.
- Try: People are named from the Mac's Contacts databases (every account under Sources/), read-only; the card marked 'me' gives the owner's addresses; a missing or unreadable database is skipped.
- Try: The Caixa iMessage source has a `mac_contacts` option (on by default); `chattr-cli convert imessage --mac-contacts`.

### 20261112-11-imessage-copy-attachments-into-the-box-and-report — iMessage: copy attachments into the box, and report the ones missing from this Mac

- Try: Attachments that are on the Mac are copied (the Mac's store is untouched) and filed at `People/<Person>/iMessage/(date) time sender.ext`.
- Try: A file that is not on the Mac is counted, its message says so, and the import's result says how many.
- Try: Importing again after the file has arrived brings it in, with no left-over 'missing' entry.
- Try: `chattr-cli missing [chat.db] [--list TEXT]` lists the conversations with missing files, the most data first, with first and last dates; the preview in Caixa says how many are missing and where the most are.
- Try: The documented walkthrough gives 9 attachments in the box, 0 not copied.

### 20261112-12-imessage-edited-and-unsent-messages-replies-group — iMessage: edited and unsent messages, replies, group events

- Try: A reply records what it answers and the page links to it with its first words (across year pages too).
- Try: An edited message shows its final text and keeps the earlier versions with their times, in an 'Edited' fold.
- Try: A wholly unsent message is a line saying who unsent it.
- Try: Rows with `item_type` other than 0 are sentences: added, removed, changed number, named, name removed, left, group photo, background, location sharing, kept audio, SOS transcript, emergency location; unknown ones are shown with their codes; an event with no actor names nobody.
- Try: The raw codes are kept with the message.

### 20261112-13-imessage-recently-deleted-messages-and-apple-s — iMessage: recently deleted messages and Apple's filter categories

- Try: A recently deleted message is read back into the conversation it was deleted from and marked.
- Try: Messages' category is kept with the message (`apple_filter`: junk, promotion, transaction); it reads only when both filter columns exist.
- Try: With spam filtering on, a message Messages called junk is tagged (never dropped); promotions and transactions are categories, not spam. With filtering off nothing is tagged.
- Try: The page marks deleted and categorised messages.
- Try: A conversation event is never also called spam.

### 20261112-14-imessage-link-previews-and-app-messages — iMessage: link previews and app messages

- Try: A link preview keeps its address, title, site and summary, and the page shows them; the address is not repeated as the message's text.
- Try: Apple Pay, Check In, Find My, Fitness, polls, Business Chat, handwriting and Digital Touch are named; an app's message shows the app's name and caption.
- Try: A message sent with an effect says which.
- Try: A payload that cannot be read leaves the message named by its kind, never an error.
- Try: Balloons are not tagged as spam.

### 20261112-15-pictures-filed-as-dated-jpeg-heic-png-and-webp — Pictures filed as dated JPEG (HEIC, PNG and WebP converted)

- Try: HEIC/HEIF, PNG and WebP attachments of chat messages are filed as .jpg at quality 85; only the JPEG is kept in the box and the source is untouched
- Try: A filed picture carries DateTimeOriginal: its own when it has one, else the local time of its message
- Try: A JPEG with no date is dated without being recompressed; a JPEG that has its date, GIF and video are byte-identical
- Try: Mail attachments are never converted
- Try: Importing the same export again files nothing twice and leaves nothing in staging
- Try: A picture that cannot be read is kept in its original format and the import says how many
- Try: The page shows the converted picture

### 20261113-01-attachments-stored-once-audio-filed-as-m4a — Attachments stored once; audio filed as m4a

- Try: The same content attached to several messages is one file on disk; every message's page shows it
- Try: The copy is filed for the earliest message; it does not move when filing is repeated, when older messages arrive later, or when the export is imported again
- Try: The one copy follows a renamed person and the pages that link it follow
- Try: A converted picture (HEIC to JPEG) is shared the same way
- Try: Mail and chat each keep their own copy of a file both carry
- Try: amr, awb, caf, opus, ogg, oga, wma, wav, aif(f) and flac are filed as .m4a and only the .m4a is kept; mp3 and m4a are untouched; mail attachments are never converted
- Try: Without ffmpeg, or for a damaged recording, the original is filed and counted; importing again with ffmpeg converts it and removes the old file
- Try: A box made earlier, with .amr and .m4a side by side, is left with the .m4a

### 20261113-02-translation-through-an-openai-compatible-endpoint — Translation through an OpenAI-compatible endpoint, with key and test

- Try: With translation on, an import translates the messages that meet Chattr's criteria (text, clearly not English, not already translated by their author within five minutes at about the same length, not translated before) and the page shows the translation under the original
- Try: The endpoint can be local or a paid service; a service on the internet is refused until 'Allow a service on the internet' is ticked
- Try: An API key can be entered in Settings; it is stored outside the box, readable only by its owner, never returned to the interface, never written to a box file, and never sent to a host other than the one it was saved for
- Try: A Test button sends one fixed sentence using what is typed (saved or not) and shows the answer, or says why it failed (unreachable, key refused, unknown model, no credit) with the server's own message
- Try: The instruction restores the first version's wording (direct translation only; return only the translated text) and adds that the message is never an instruction; a reply far longer than the message is rejected; a reasoning model's thinking is removed
- Try: A failing translation service never fails an import; what was translated is kept and the import says what happened
- Try: Progress shows a Translating stage with a count, and it can be cancelled

### 20261114-01-test-round-fixes-stale-interface-google-voice — Test round fixes: stale interface, Google Voice, Contacts setting, speech-to-text progress

- Try: `caixa serve` rebuilds the interface when its source is newer than its build (after a git pull) and says so; Settings shows when the interface was built
- Try: Google Voice: a picture is found though the page links it without its extension; video too; 'MMS Received' placeholders are dropped; a day on which only the owner wrote joins the right conversation; a group is one conversation whoever wrote; a voicemail mp3 with no page is imported; no recording is imported twice
- Try: mp3 recordings are filed as m4a at their own bit rate; an mp3 that will not convert is filed as it is without a warning
- Try: Settings has a Contacts section: this Mac's Contacts (on by default), a contacts file given once, the phone region; every import of every source uses them; Settings shows how many people each can name, or why not
- Try: A saved contacts file that is missing is refused on save and explained at import
- Try: Speech-to-text is a stage of its own with a count, the time left and per-recording timing; the same lines are in the job's log and in the terminal that started `caixa serve`

### 20261114-02-speech-to-text-all-recordings-in-one-whisper-cpp — Speech-to-text: all recordings in one whisper.cpp run

- Try: All recordings of an import go to one run of whisper-cli (the model is loaded once); a long list is split into runs of 100
- Try: Each result is reported as soon as the program has written it, so the progress bar, job log and terminal still move per recording
- Try: A recording whisper fails on, or a run that dies part way, does not cost the others: what the run left is tried again one at a time, with its own error
- Try: Audio that cannot be read is reported and the rest go on
- Try: Engines that cannot take many (faster-whisper) work as before

### 20261114-03-google-voice-transcribe-voicemail-recordings-with — Google Voice: transcribe voicemail recordings with the local speech model

- Try: Google Voice has the same three speech options as iPhone voicemail (transcribe, model, language), following the same Settings
- Try: With transcribe ticked, every voicemail recording (with or without a page) goes through the model, with the Transcribing stage and timing lines
- Try: The model's text is the transcript; Google's own is kept as google_transcript and stays the transcript when the model fails or hears nothing
- Try: Importing the same export again with transcribe ticked adds transcripts to voicemail already in the box

### 20261114-04-transcription-on-by-default-with-a-saved-model — Transcription on by default with a saved model; show which code is running

- Try: 'Transcribe on this computer' starts ticked, for iPhone voicemail and Google Voice, once a speech model is saved in Settings; unticked until then; unticking skips it for that import
- Try: An import started without mentioning the option (command line, Run again) follows the saved model
- Try: Settings shows the version, the commit and when the running Caixa started
- Try: When the code on disk is newer than the running process, Settings shows a restart notice and `caixa serve` (already running) says so
- Try: `caixa serve` prints the commit when it starts

### 20261116-01-messenger-keep-only-conversations-with-facebook — Messenger: keep only conversations with Facebook friends; name-only contacts

- Try: Messenger conversations with nobody on the friends or removed-friends list are left out; a group with at least one friend is kept; a thread that names nobody is kept
- Try: The import (and the preview) says how many were left out; the job's log lists who they were with, without the owner's own name
- Try: Friends and removed friends are named by their Facebook name, so they leave 'Not yet named'
- Try: The lists are found beside the messages in a folder or zip, in the three known layouts; friend requests are not friends; a separately downloaded list can be pointed at; a wrong path is an error
- Try: No list found: everything kept, and said so; 'Only conversations with Facebook friends' can be unticked; Instagram is never filtered
- Try: A contact with a name but no phone or email (vCard or Mac Contacts) now names a handle that is exactly that name

### 20261116-02-naming-names-shown-by-whatsapp-and-google-voice — Naming: names shown by WhatsApp and Google Voice count; deactivated Facebook accounts kept

- Try: A Messenger thread with a 'Facebook user' is kept by the friends filter
- Try: Each 'Facebook user' is a separate handle per thread ('Facebook user (<thread folder>)'), listed under Not yet named
- Try: WhatsApp and Google Voice handles shown by a name are named by that name after Contacts have had their say; numbers, email addresses, '~' self-given WhatsApp names and placeholders are not
- Try: The same name from WhatsApp, Google Voice, Contacts or Facebook is one person

### 20261116-03-one-page-per-person-fast-for-very-long-histories — One page per person, fast for very long histories

- Try: Each person and each group has one page, People/<Person>/<Person>.html, with every year and source; no index.html or year pages in their folders
- Try: The page starts with a summary (count, first and last date, sources, groups, mail), a year bar that stays at the top, and each year begins with its calendar
- Try: A 100,000-message page shows its first messages in well under a second and has fully arrived in a few seconds (measured in Chromium)
- Try: The page runs no script, so it works inside Caixa's viewer, where scripts are blocked
- Try: The data island leaves out empty fields (schema chattr-page-2); version 1 pages are still read; a database rebuilt from the pages renders identical pages
- Try: The box index links each person's page with their count and years

### 20261116-04-reset-a-box-s-data-keeping-its-settings — Reset a box's data, keeping its settings

- Try: Reset removes the pages, the files Caixa filed, index.html, the master's items and people, each collector's working data, undo copies, jobs and logs
- Try: It keeps box.yaml (all settings), the box name, the owner, README.md, Inbox and its contents
- Try: Names given by hand are kept and apply on the next import, unless 'forget names' is asked
- Try: Only files Caixa wrote are deleted; others are left and listed
- Try: Refused while an import runs and in read-only boxes; asks first in the browser and on the command line
- Try: Importing again after a reset gives the same box

### 20261116-05-picture-lightbox-iphone-voicemail-callers-named — Picture lightbox; iPhone voicemail callers named; large pages in Caixa's viewer

- Try: Clicking a picture on a person's page shows it full size over the page; arrows and arrow keys move between pictures; Escape, a click beside it or the cross closes it and returns to the picture
- Try: Without the script every picture is still a link to its file
- Try: Inside Caixa's viewer the lightbox runs: the policy admits exactly its SHA-256 and no other script; the frame sandbox allows scripts only under that policy
- Try: Chattr's tests fail if lightbox.js changes without its new hash being listed in harness/src/host/page-scripts.ts
- Try: Pages of any size have their links rewritten in the viewer (large ones as they are sent, cut only between tags)
- Try: Voicemail callers named in file names are named people; numbers still wait

### 20261116-06-facebook-noise-and-group-rules-requests-silent — Facebook noise and group rules: requests, silent members, numbers in groups

- Try: message_requests and filtered_threads are left out unless 'Include message requests and filtered messages' is ticked
- Try: Every group conversation (any source) the owner never wrote in is removed; only for a source whose owner is recognised, otherwise all its groups are kept and the import says so
- Try: In groups, members who never wrote lose their place, their reactions keep the emoji without the sender, and handles left with nothing are removed
- Try: A phone number that wrote only in groups is never listed under Not yet named (in the import result, the preview and the People page); a number with a direct conversation still is
- Try: The owner's own Facebook name (from the export's profile) is the owner on Messenger and Instagram
- Try: Each import says what was left out and why; the job's log names each
- Try: The documentation lists exactly which parts of a Facebook download are read

### 20261116-07-index-page-categories-people-tiles-dashboard-nord — Index page: categories, people tiles, dashboard; Nord theme

- Try: Categories are stored on the master's people (migration 2), follow renames and merges, survive a reset unless names are forgotten
- Try: people.categorize sorts people by id or name; unknown people and categories are refused; read-only refuses it; at most one redraw waits
- Try: The index shows the sidebar with counts, tiles with initials, counts and a source tooltip, groups and mail views, and the footer
- Try: People known only by a number, address or a nameless account are Unrecognized automatically and cannot be dragged
- Try: In Unassigned, click selects, Shift-click selects a range, drag onto a category or the footer buttons save it through Caixa and the tiles leave Unassigned; opened outside Caixa the page says sorting needs Caixa
- Try: The dashboard (under All only) counts items, conversations, files and their size per source, and the box's totals
- Try: Every person and mail page has an 'All people' button near the top; all pages use the Nord palette, keeping the orange heat map and dates
- Try: Caixa's viewer allows the index script by its hash and lets it call Caixa (connect-src 'self')

### 20261117-01-owner-preference-file-and-removing-people-from-a — Owner preference file and removing people from a box

- Try: `.caixa/owner.json` (0600) is written after every link, rename, merge, categorize and delete, and read when the box opens and at every import
- Try: Names and categories typed into the file while Caixa is closed are taken up
- Try: A reset keeps the file; forgetting names clears names and categories but keeps the removed list
- Try: Service `people.delete(people, handles)` removes people (by id or name) and unnamed handles; refuses the owner; the redraw job deletes their one-to-one conversations, files, pages and master items
- Try: Removed people stay out after the same export is imported again and after a reset
- Try: Group messages they wrote stay in the group

### 20261117-02-index-page-unassign-select-delete-open-in-new — Index page: unassign, select, delete, open in new window, name unrecognized

- Try: × on hover in assigned categories moves the person back to Unassigned (people.categorize with null)
- Try: Click and Shift-click select in Unassigned and Unrecognized
- Try: Delete/Backspace asks in an in-page dialog, then calls people.delete and removes the tiles
- Try: ↗ on hover opens the page in a new window; the selection is kept
- Try: Name field + Apply (or Enter) on Unrecognized tiles links every handle of the tile to the name; the tile moves to Unassigned
- Try: Works inside Caixa's viewer; opened from the folder, the page browses and says changes need Caixa

### 20261117-03-people-page-select-and-delete-records-not-yet — People page: select and delete records not yet named

- Try: The top box shows a box on every record; once shown, it chooses all or none
- Try: Delete (count) at the bottom is disabled until something is chosen; Cancel hides the boxes
- Try: Nothing is deleted before the confirmation
- Try: Deleted records leave the list at once (the service filters removed handles before the redraw job runs)
- Try: A refusal is shown in Caixa's own words
- Try: English and Chinese texts

### 20261117-04-collector-service-separate-from-the-deepseek — Collector service separate from the DeepSeek harness

- Try: `caixa serve` starts one Python process on 127.0.0.1 and opens a sign-in link; nothing answers without the session cookie
- Try: Host header checked (DNS rebinding); POSTs must be JSON and, when they say where from, from this window
- Try: The same /api/caixa/rpc, /events and /status contract as before, so the pages work unchanged
- Try: The box's pages served at /box/<path> under the pages' Content-Security-Policy, with Range for media; .caixa and anything outside the box refused; /api/caixa/box?path= redirects
- Try: Caixa's window: title Caixa, Nord colours, no DeepSeek name, strict CSP (no inline scripts or styles)
- Try: The built window is committed in caixa/data/web; a Python test fails if sources change without a rebuild
- Try: `caixa serve` run again opens the running window; `--stop` and Control-C stop it
- Try: Every end-to-end browser test runs against the real `caixa serve`

### 20261117-05-remove-the-deepseek-plugin-rename-harness-to-web — Remove the DeepSeek plugin, rename harness to web, box pages in their own window

- Try: No DeepSeek package, plugin host, plugin build or plugin test remains; `web/package.json` lists none
- Try: `harness/` is now `web/`, and every reference follows
- Try: Caixa's window and the index page scroll as one page: no inner scroll area; on the index the categories stay at the left and the footer at the bottom (sticky)
- Try: Browse opens the index page, and any page of the box, in one reused window named caixa-box, at /box/<path>; nothing is squeezed into a frame
- Try: Plain text still previews in a frame where nothing runs
- Try: The old /api/caixa/box address is gone

### 20261117-06-index-page-categories-dead-on-pages-drawn-with-an — Index page categories dead on pages drawn with an older script

- Try: A page drawn with an older version of Caixa's index or lightbox script is served with the current one, so it runs
- Try: Only a script that begins as one of Caixa's does is replaced; any other script, and message text, is sent unchanged
- Try: Only the end of a page is held in memory; Content-Length matches what is sent
- Try: No redraw of the box is needed

### 20261117-07-index-page-tools-only-on-hover-name-field-with — Index page tools only on hover; name field with suggestions of known people

- Try: Nothing on a tile until the pointer (or keyboard focus) is on it
- Try: Family, Friends, Business, Acquaintances: one close box, upper right
- Try: Unassigned and Unrecognized: one open-page button, upper right (the selection tick moves to the upper left)
- Try: Unrecognized: a name field on hover below the name and counts; it stays while typing
- Try: Apply appears to the right only once something is typed; Enter applies
- Try: As you type, the people already in the box are offered (prefix first, then word and substring), with their item counts; click, or arrows and Enter, to pick
- Try: Picking a known person links the number to them and removes its tile; a new name makes a new person in Unassigned
- Try: Works on pages drawn by earlier versions

### 20261118-01-unrecognized-sorted-busiest-first — Unrecognized sorted busiest first

- Try: Unrecognized lists the tiles with the most items first (ties in name order)
- Try: Every other view keeps name order, including a tile named from Unrecognized (it takes its new name's place)
- Try: Shift-click ranges follow the order on screen
- Try: Works on pages drawn before tiles carried their item count

### 20261118-02-imessage-messages-without-a-chat-mixed-into-one — iMessage messages without a chat mixed into one (no chat) person

- Try: A message without a chat goes to the person it was with (its handle, whoever sent it): their one-to-one conversation when one exists, through handle groups and merged chats
- Try: Otherwise a conversation of its own with them, named for them
- Try: Messages the owner sent with no recipient recorded: one conversation, Sent, recipient not recorded, listed with the groups
- Try: Events (item_type not 0) without a chat are left out
- Try: Importing the same chat.db again removes the old (no chat) conversation, its messages and its files; Caixa then drops the master items and the page

### 20261118-03-owner-replies-in-deleted-imessage-chats-missing — Owner replies in deleted iMessage chats missing from their person

- Try: A message the owner sent with no recipient goes into the conversation of the message it came after (`reply_to_guid`), or of the message that came after it
- Try: A run of such replies follows along the chain
- Try: Each message so placed says so (service_specific placed_by: reply_to)
- Try: Only those with nothing to follow stay in 'Sent, recipient not recorded'
- Try: A full import rebuilds that conversation, so a box imported before is not left with copies

### 20261118-04-google-voice-texts-forwarded-to-the-phone — Google Voice texts forwarded to the phone duplicated as iMessage

- Try: A message in iMessage's database is dropped when Google Voice has one from the same number (normalised), with the same words (spaces aside), within ten minutes
- Try: Google Voice's record stays; a conversation left with nothing goes; files only those copies showed are deleted from the box
- Try: Runs after every import and redraw, whichever source was imported first; safe to repeat
- Try: The import says how many it found
- Try: Nothing is dropped without a Google Voice twin: other people, other words, or hours apart

---

## Backlog

- **Slack** and other further sources (Google Chat/Hangouts, Telegram, …): a later project.
- Photos and media as their own domain (a separate tool, later project). Message attachments
  *are* in scope.
- Model, search index, knowledge distillation, training, and the heirs' "Ask" experience (later
  projects). This project only makes sure the master schema and the application serve them.
- **Heir mode** (`caixa serve --heir`, read-only) and the **Docker image**: a later project,
  together with the model and "Ask" work. Phase 1 lays the groundwork (`caixa worker --read-only`).
- A native desktop wrapper (a Sele-style window). The browser is the interface.
- A standalone `.eml` parser.
- Importing any other existing tool.


