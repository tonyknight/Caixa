---
release_train: Istanbul
project: Phase1-Collector
tags:
- Release Train
- Project
hierarchy:
- Istanbul
- Phase1-Collector
last_reviewed: 2026-11-01
focus: "DRAFT (rev 3, adds the browser application on DeepSeek Harness): awaiting maintainer approval. No tickets until approved."
---


# Phase1-Collector Requirements

> **Status: DRAFT, revision 3.** This file records the architecture agreed in design discussion.
> Revision 2 recast Chattr from its full history, including the previously uncommitted v2 work
> (`9a42781`). Revision 3 adds how people run Caixa: a browser application built on DeepSeek
> Harness, with all conversion in Python. Tickets are created from the Tasks Breakdown only after
> the maintainer approves this file.

## Overview

Phase1-Collector establishes Caixa's data architecture and delivers the message collector.
**Chattr**, an existing open tool, becomes Caixa's converter for every conversation-like source.
It writes a SQLite domain store (`chattr.sqlite`) and styled HTML pages organized by person and
named by date. Phase 1 covers six sources:
- iMessage
- WhatsApp
- Facebook Messenger/Instagram
- email from MBOX
- Google Voice
- iPhone Voicemail, with local speech-to-text

A messages adapter loads Chattr's output into Caixa's master database, the system's source of
truth. Chattr lives in Caixa and is mirrored back to its own repository.

Chattr's own plan already named the next step: define a **unified schema**, then build the
**unified SQLite database** (Chattr `docs/database_schema_plan.md`, "Migration Strategy", phases
2–3). Phase 1 completes that step in the shape Caixa needs.

People run Caixa in a **web browser on their own computer**. `caixa serve` starts DeepSeek
Harness (`dsh web`) with a Caixa plugin that adds the authoring pages: box, import wizard, jobs,
people, browse, settings. All conversion and data work happens in Python (`caixa worker`), which
the plugin runs and talks to directly. Chattr also gets a small Python-only web UI
(`chattr serve`) for people who use it without Caixa.

## Goals

1. Agree and document the data architecture: box layout, organizing rules, databases and
   ownership, handoff contract, stable IDs, rebuild chain.
2. Stabilize Chattr's v2 scaffolding and complete its **unified schema → SQLite** milestone.
3. Chattr converts the six Phase 1 sources into `chattr.sqlite`, per-service JSON exports, and
   date-named, per-person HTML.
4. Caixa master database schema v0, plus the messages adapter.
5. A working mirror of Chattr from Caixa to Chattr's repository.
6. A browser-based authoring application: `caixa serve` + a Caixa plugin for DeepSeek Harness +
   `caixa worker`, with collectors that register themselves, so new export sources appear without
   UI work. Plus `chattr serve` for standalone Chattr users.

## Non-goals

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

## Architecture

### Guiding principle: normalize for people, not platforms

Exports are organized for each platform's database. Caixa and Chattr **transform** them into an
archive organized for people:
- rename to archival names;
- embed dates and standard metadata into files;
- fix text encoding;
- record local time with its offset;
- organize by person, date and conversation.

We transform an archive copy, never data that live applications use. Keeping the raw export is
optional at import time. Provenance (which export, when, its hash) is always recorded.

Correctness still matters wherever it changes meaning:
- no dropped or garbled messages;
- no attachment overwriting another;
- correct times;
- re-importing an overlapping export adds nothing twice.

### Organizing principles: dates first, people second

**Dates are the backbone.**
- Every transformed file is named `(YYYY-MM-DD) <name>.<ext>`.
- **Honest precision**: `(YYYY-MM) …` or `(YYYY) …` when only the month or year is known. Never
  invent a day.
- **Same-day collisions** add a time, then a counter: `(YYYY-MM-DD) HH-MM-SS <name> 2.<ext>`.
- **The name uses the local date of the event.** Databases store UTC + offset + precision.
- **The date is also written into standard metadata** where the format allows it (EXIF/XMP
  `DateTimeOriginal` on images).

**People are the second axis.** Wherever it makes sense, data is organized by person:

```
Messages/
  <Person>/
    (YYYY) <Person>.html      ← every message, call and voicemail with this person across all platforms,
                                 merged chronologically, platform badge per entry, one page per year
    Attachments/
      (YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>
  Groups/
    <Group name>/             ← same shape; group chats don't belong to one person
Mail/
  <YYYY>/
    (YYYY-MM-DD) <sender> — <subject>.html   (+ attachments; threaded by Message-ID/References)
```

- Mail is organized by date and thread, not by person.
- Handles not yet linked to a person render under the handle (for example `Messages/+1 555…/`)
  until someone links them. Pages are then re-rendered under the person's name.
- Duplicate person names get a suffix when the person is created. The canonical name is set by
  the curator.
- The **master database links every item to every person involved, across all data types**.

### Components

| Component | Location | Role |
| --- | --- | --- |
| **Chattr** | `tools/chattr/` (subtree, mirrored to Chattr's repository) | Standalone message converter: parsers → `chattr.sqlite` (+ per-service JSON) → HTML. Never imports Caixa. |
| **Caixa core** | `caixa/` | Master database (schema, migrations, change log), collector adapters, CLI. |
| **Messages adapter** | `caixa/collectors/messages.py` | Runs Chattr into `.caixa/work/chattr/`, `ATTACH`es `chattr.sqlite`, upserts into the master, exports `aliases.json`. Registers Chattr's six sources as collectors. |
| **Collector registry** | `caixa/collectors/` | The collector contract; discovery through the `caixa.collectors` Python entry-point group. |
| **Caixa worker** | `caixa/` (`caixa worker`) | The Python service layer behind the UI and the CLI: JSON-RPC over stdio; box, collectors, imports, jobs, people, browse, settings; `--read-only`. |
| **Caixa harness plugin** | `harness/` | A DeepSeek Harness bundle (TypeScript, React 18). Its host half supervises `caixa worker` and exposes owner-only `/api/caixa/*` routes; its browser half provides the authoring pages. |
| **Launcher** | `caixa/` (`caixa serve`) | Checks Node, prepares Caixa's own DeepSeek Harness home with a pinned version and a privacy patch, starts `dsh web`, opens the browser. |
| **Chattr web UI** | `tools/chattr/` (`chattr serve`) | Small Python-only browser UI for standalone Chattr users (Jinja2 + htmx). |
| **Mirror workflow** | `.github/workflows/mirror-chattr.yml` | On push to the default branch: `git subtree split --prefix=tools/chattr` → push to Chattr's repository (fast-forward). |
| **Fixtures** | `tests/fixtures/`, `tools/chattr/tests/fixtures/` | Synthetic fixture family: no real data, ever. |

### Data model

**The box** (what a user's archive looks like on disk):

```
<Box name>/
  README.md                ← plain language: what this is; how to use it with or without Caixa
  Messages/  Mail/  Photos/  Video/  Audio/  Documents/  PDFs/  Contacts/  Calendar/  People/  …
  .caixa/
    caixa.sqlite           ← master database (source of truth)
    index.sqlite           ← later project: full-text search + vectors over chunks
    knowledge.sqlite       ← later project: summaries, claims→citations, training sets, model registry
    work/chattr/           ← Chattr's root when run by Caixa (chattr.sqlite, Services/*.json state)
    box.yaml  model/  harness/  imports/ (optional raw-export retention)  logs/
```

**Two data patterns:**
- **Render** (messages, calls, voicemail, mail): export → collector database → generated HTML.
  The database is the working store the files are generated from. JSON is an interchange and
  export format.
- **Index** (photos, media, documents; later projects): normalize the files → scan them into a
  catalog database, which acts as a fast-search cache over metadata stored in the files.

**Database inventory and ownership.** Caixa's master is separate from each collector's database
because:
- Chattr must run standalone;
- lifecycles differ (fast-iterating conversion state vs. decades of curated history);
- only the master sees every domain and can resolve identities across them.

| Store | Owner | Holds |
| --- | --- | --- |
| `chattr.sqlite` | Chattr | the unified message schema v0 (below) |
| `caixa.sqlite` | Caixa | items (one per message/email/call/voicemail/photo/document: stable ID, type, time + offset + precision, text, file path + anchor, privacy, content hash, version), people, aliases, item → person links with role (sender, recipient, participant, depicted, mentioned), imports/provenance, change log, human curation |

**Chattr unified schema v0 (`chattr.sqlite`).** It combines three sources: Chattr's JSON message
model (`docs/database_schema_plan.md`), Chattr's owner/author/sender roles (Chattr.md Phase 3),
and Caixa's stable IDs and time precision.
- `conversations`: stable id, service, type (`individual` | `group`), name, `service_specific`
  (JSON).
- `handles`: service, raw identifier (phone, email, username), normalized form, display name,
  resolved person (from `--contacts` vCard / `--aliases`).
- `participants`: conversation ↔ handle, role.
- `messages`:
  - identity: stable id, conversation, source id;
  - time: `timestamp_utc`, `tz_offset`, `precision`;
  - sender: sender handle, `is_from_owner`;
  - content: `content_type` (`text` | `media` | `system` | `reaction` | `call` | `voicemail` |
    `email`), body, language, translation, transcript (voicemail);
  - metadata: reply_to, edit history, forwarded_from, delivery/read status;
  - mail headers (Message-ID, In-Reply-To, References, Gmail thread ID, labels, cc/bcc);
  - provenance: `service_specific` (JSON), import id, content hash.
- `attachments`: sha256 id, message, original filename, archival filename, mime type, size,
  storage path, `processing_info` (converted, from/to format, duplicate).
- `reactions`: target message (including attachment targets), sender handle, type, emoji,
  timestamp, action (`added` | `removed`).
- `imports`: service, source path and hash, started/finished, counts, last source cursor (for
  example the iMessage ROWID). `Services/<Service>.json` → `state` mirrors this for standalone
  use.
- `schema_version` + ordered migrations.
- **Roles are derived, not duplicated:**
  - *owner* = the archive owner (configuration);
  - *author* = the conversation's counterpart person or group, which maps to
    `Messages/<Person>/` or `Groups/<Group>/`;
  - *sender* = the handle → person.
- **Per-service JSON exports remain** in each service's native format, as Chattr's schema plan
  recommends, alongside the central database.

**Handoff contract**: the adapter `ATTACH`es `chattr.sqlite` and upserts by stable ID in SQL.
Each insert or update appends a change-log row: change number (monotonic), item ID, operation,
version, import ID.

**Stable IDs:**
- chat: source thread ID + source message ID, or else a hash of (service, thread, time, sender,
  body);
- email: normalized Message-ID, or else a hash of the headers;
- Google Voice and Voicemail: source record ID, or else a hash of (service, counterpart, time,
  duration);
- (later) photos/media: a hash of the image data only, located by path relative to the box root.

**Rebuild chain**: top-level files → domain stores → master → (later) index/knowledge.
- Each rendered HTML page embeds its entries as a JSON data island
  (`<script type="application/json">`) and gives every entry an `id="m-<id>"` anchor. So
  `chattr.sqlite` can be rebuilt from the HTML, and citations deep-link to exact messages.
- No Caixa-specific metadata is written into user files. Only Caixa- and Chattr-generated files
  (HTML) carry IDs.
- Human curation (people, relationships, corrections) is also written to the top level
  (`People/`), so losing `.caixa/` loses nothing irreplaceable.

### Key flows

**Standalone Chattr:**
- **Preflight:** `~/.chattr.json` → Chattr root (default `~/Documents/Chattr`; `--root` overrides
  without prompting). It creates `Database/`, `Output/{Chattr,<Service>…}`, `Services/` and
  `temp/`, and copies `Defaults/` without overwriting existing preferences or state.
- **Interactive menu:** choose service(s) → route to the central database or to the service's own
  folder → optionally generate HTML. Defaults come from `config.json` +
  `Services/<Service>.json`, overridable while drilling down.
- **Equivalent non-interactive command line:**
  `chattr convert <service> <export> [--root DIR] [--db | --json] [--contacts file.vcf] [--aliases aliases.json] [--html]`.
  It also restores the dropped iMessage flags: `--region`, `--attachment-root`, `--batch-size`,
  `--verbose`, `--attachment-workers`.
- **Per run:** parse → upsert by stable ID → update `imports` and `state` → re-render only the
  changed person and group pages → report handles it couldn't resolve.

**Inside Caixa (an import or update):**
1. The adapter writes `aliases.json` from the master's people/aliases.
2. It runs `chattr convert … --root .caixa/work/chattr` and renders into the box's `Messages/`
   and `Mail/`.
3. It `ATTACH`es `chattr.sqlite` and upserts items, item → person links and provenance.
4. It appends to the change log.
5. It reports unresolved handles for a human to link.
6. Linking a handle re-runs rendering for the affected pages.

### Application: how people run Caixa

People author their box in a **web browser on their own computer**. The interface is built on
**DeepSeek Harness** (`dsh web`; MIT; plugin-based). All conversion and data work stays in
**Python**.

```
caixa serve  (Python launcher)
 ├─ starts: dsh web --host 127.0.0.1 --port N --patch caixa.patch.yml   (Caixa's own DSH home, pinned dsh)
 │    └─ Caixa harness plugin (harness/, TypeScript)
 │         ├─ host half:    runs `caixa worker` (Python) and talks to it over stdio JSON-RPC
 │         │                registers owner-only routes /api/caixa/* (+ streaming job progress)
 │         └─ browser half: sidebar icon → Caixa pages; a Settings section; toasts
 └─ opens the browser at the 127.0.0.1 token URL
caixa worker (Python): collectors (Chattr …), master DB, jobs, people, box operations
```

**What DeepSeek Harness provides.** Findings from its source, commit `ce7073d`, version
`0.2.2-alpha.2`:
- **Full pages from a plugin.** A React 18 component goes in the `main` slot, with a
  `sidebar.panellist` icon. This is how the built-in Schedule page works
  (`packages/client/ui-schedule/src/client/index.ts`).
- **Other UI slots:** `settings.section` (Settings pages), `sidebar.right.pane.tab` (right-hand
  panels), `shell.overlay` (toasts).
- **How plugin UI is loaded:** declared with `"dsh": {"client": {...}}` and an exported
  `./client`, and loaded live by `ctx.clientModules`.
- **Running Python from a plugin.** A plugin's host side can run a child process with
  `ctx.subprocess.spawn` and talk to it over stdio, with no extra network port. It exposes that
  to the browser through **owner-only routes**, `ctx.connection.fetch.register({ path: '/api/caixa/...' })`,
  protected by DSH's launch token, signed cookie, and `Host`/`Origin` checks. Streaming responses
  carry job progress.
- **Pieces for later "Ask" work:** agent tools (`ctx.tools.register`), tool policies
  (`tools/pre-execute`), and local OpenAI-compatible models (the `llm-pi-ai` custom provider).
- **Templates to learn from:**
  - the `dsh-chat-import` plugin (MIT): an importer with pure converters, host routes, agent
    tools and client UI;
  - Sele: the rules for launching and supervising `dsh web`;
  - `dsh-vscode-plugin`: bundling dsh, a dedicated DSH home, patch YAML, and a gateway client.
    MIT; reuse needs both copyright lines.

**Caixa worker (Python).**
- One service layer, shared by the CLI (`caixa import …`) and the worker, so everything the UI
  does can be scripted.
- JSON-RPC over stdio. Methods:
  - `box.create`, `box.open`, `box.status`
  - `collectors.list`
  - `import.preview`, `import.start`, `import.cancel`
  - `jobs.list`, plus progress notifications
  - `people.unresolved`, `people.link`, `people.merge`, `people.rename`
  - `browse.list`, `browse.file`
  - `settings.get`, `settings.set`
- Jobs are kept in a SQLite table in `.caixa/`, so long imports survive restarts.
- `--read-only` refuses every write method. This is the groundwork for heir mode.

**Collector contract.** New export sources appear in the UI without UI code.
- **Discovery:** the `caixa.collectors` Python entry-point group. Chattr's adapter registers six
  collectors.
- **Each collector declares:**
  - id, display name, platform;
  - accepted inputs (zip, folder, file, local database);
  - **"How to export" instructions** for the platform;
  - an **options JSON Schema**, seeded from Chattr's `Defaults/Services/*.json` preferences,
    which the UI renders as a form;
  - `preview(input, options)`: counts, date range, participants, unresolved handles;
  - `run(input, options, progress)`.

**Authoring pages** (React 18, following DSH's UI rules: CSS Modules, no Tailwind or component
libraries, all text in locale files), behind one sidebar icon:
1. **Box**: create or open a box; dashboard of counts by type, person and year; last imports.
2. **Import wizard**:
   1. choose a source;
   2. read its "how to export" card;
   3. pick the export with a server-side file picker limited to the user's folders, or drop it in
      the **inbox folder** the worker watches;
   4. options form generated from the schema;
   5. **preview** (dry run);
   6. run, with live progress;
   7. result report.
3. **Jobs and logs**: running and finished imports; cancel; errors; a toast on completion.
4. **People**: queue of unresolved handles; link, merge, set the canonical name. Changes
   re-render the affected pages.
5. **Browse**: the box's generated pages, served through `/api/caixa/box/*`.
6. **Settings section**: box location, local model endpoints (translation, speech-to-text),
   privacy defaults.

**Launcher (`caixa serve`).**
- **Checks Node 24.9+ first**, and explains how to install it if it's missing or too old.
- **Prepares Caixa's own DeepSeek Harness home**, never the user's `~/.dsh`. It installs the
  **pinned** dsh version and the Caixa plugin into its `web` profile.
- **Writes `caixa.patch.yml`:**
  - **disables `session-log-deepseek` and telemetry upload**;
  - configures a local OpenAI-compatible provider placeholder;
  - sets permission defaults.

  It also sets `DSH_TELEMETRY_DISABLED=1`.
- **Starts `dsh web` following Sele's rules:**
  - own process group, terminated as a group;
  - `127.0.0.1` only, ports 3082+ or OS-assigned, never 3080/3081;
  - reads the token line from stdout, then checks readiness;
  - saves `{pid, port, tokenURL}` so it can reattach after a crash;
  - never logs the token URL.
- **Opens the browser** at the `127.0.0.1` token URL.

**Where it runs (Phase 1):** a native install (`pipx` / `uv tool install`) with Node 24.9+ on the
system. Native is also what macOS iMessage needs (Full Disk Access to `chat.db`), and what fast
local speech-to-text needs (Apple GPU acceleration isn't available inside Docker on macOS). Heir
mode and a Docker image come in a later project.

**Chattr's own web UI (`chattr serve`).** Python only (Jinja2 + htmx), reusing Chattr's templates
and Nord theme; no Node or DeepSeek Harness. Screens: choose a service, point to the export, set
options (from `Services/*.json`), run with progress, open the output. It calls the same Chattr
library functions as the CLI, the terminal menu and the Caixa worker.

**Constraints and safeguards:**
- **Pre-stable plugin interfaces.** DSH warns of "compatibility-breaking changes", and slots can
  be renamed without aliases. Pin an exact dsh version plus `engines.dsh`, and upgrade
  deliberately using DSH's `docs/upgrade-guide/`.
- **The client build preset isn't published.** The plugin's browser bundle needs a "lazy-CJS
  factory" format whose build preset (`packages/client/tsdown.client.ts`) isn't published, so
  `harness/` reproduces it.
- **One owner, no roles in DSH.** Read-only access for heirs, later, must be enforced in
  `caixa worker`, not by DSH's agent permission presets.
- **The Python worker is never exposed to the browser directly.** It is reachable only through
  `/api/caixa/*`, so DSH's authentication and `Origin` checks apply.

### Chattr: history, current state and decisions

The commit hashes below are those of Chattr's history **after the 2026-11-01 privacy purge**,
which removed a committed chat database, an exported AI-assistant transcript containing an API
key, and IDE files. A line reference means file and line at Chattr `0152912` unless noted.

**History:**

| Commit | Date | Change |
| --- | --- | --- |
| `d7ee0de` | 2025-09-01 | First working version: WhatsApp → single HTML page (translation, EXIF dating, galleries, lightbox, calendar). |
| `c2c0e48` | 2025-09-12 | Messenger (encoding fix, shared links, translation-skip heuristic); iMessage via imessage-exporter HTML (BeautifulSoup); heatmap calendar; interactive menu. |
| `60b276c` | 2025-09-17 | First SQLite (`message_owner` / `message_author` / `message_sender`, vCard enrichment). **High-water mark of working features** (`main.py`). |
| `9b960f2` | 2025-09-28 | Object-oriented skeleton (`src/parsers/`, `BaseParser`, `DatabaseManager`, `HTMLGenerator`), plus the separate "iMessage Database Tool" (a direct `chat.db` reader) merged in. Much of `main.py` was dropped, not ported. |
| `9a42781` | 2025-10 (pushed 2026-10-31) | **v2 "multi-function" scaffolding**: `src/preflight.py`, `src/config.py`, `Defaults/config.json` + `Defaults/Services/{iMessage,WhatsApp,Messenger,GoogleVoice,Voicemail}.json` (preferences + state), iMessage tool integrated (`src/parsers/imessage_database_parser.py`, `src/attachment_manager.py`, `src/imessage_tools.py`), unified `requirements.txt`, design docs. |
| `0152912` | 2026-11-01 | `.gitignore` for output, databases, secrets and IDE files. |

**What works at `0152912`:**
- **WhatsApp → DB:** only 6 columns are filled, and "image omitted" lines are dropped.
- **Messenger → DB:** one file at a time; the attachment path is dropped.
- **iMessage:** produces JSON only, and only in Advanced mode with a hand-typed path. Quick, List
  and Diagnostics fail because `main.py` reads configuration keys that no loaded file contains
  (`main.py:314-315`, `main.py:406`). It never reaches the database.
- **Google Voice, Voicemail:** configuration and folders only.
- **HTML generation crashes:** `src/html_generator.py:30` assigns into a `sqlite3.Row`, and the
  template expects `author`/`message` while the database has `message_author`/`body`.

**What is scaffolding only:**
- **Configuration is never loaded from the setup step:** `src/config.py` loads `./config.json`
  only, never `~/.chatter.json`, the root, or `Services/*.json`.
- **Import-progress fields are dead:** `state.*` is never read or written.
- **No duplicate protection:** re-importing duplicates rows.
- **"Repair" wipes settings:** preflight's repair overwrites user preferences and state.
- **The menu is still flat:** the step-by-step "waterfall" menu isn't built.
- **The spam filter is skipped in parallel mode:** it doesn't run on the iMessage parallel path
  (`src/parsers/imessage_database_parser.py:941`).

**Still missing from `60b276c:main.py`:**
- translation and the translation-skip heuristic;
- the heatmap calendar;
- WhatsApp/Messenger media renaming + EXIF;
- shared links;
- DB → HTML.

**Decisions to preserve:**
- SQLite is the canonical store (Chattr.md Phase 3).
- Owner/author/sender roles (Chattr.md Phase 3).
- Native per-service JSON exports kept after unification (schema plan, "Recommendations").
- One attachment pipeline for all services: the parser identifies attachments, AttachmentManager
  transforms and stores them; sha256 dedupe.
- The pointer → root → `Defaults/` → `Services/*.json` (preferences + state) design.
- Translation as a global backend + per-service rules, with the key from the environment only.
- `BaseParser` per service, with `main.py` only orchestrating.
- iMessage opened read-only, with the spam filter.

**Carry forward:**

| What | Ref |
| --- | --- |
| read-only `chat.db` connect | `src/parsers/imessage_database_parser.py:306` |
| chat, participant and group-name logic | `src/parsers/imessage_database_parser.py:447-555` |
| phone normalization | `src/parsers/imessage_database_parser.py:369` |
| vCard contacts | `src/parsers/imessage_database_parser.py:381` |
| tapback table | `src/parsers/imessage_database_parser.py:272` |
| tapback queries | `src/parsers/imessage_database_parser.py:1046-1310` |
| diagnostics, which become `chattr doctor` | `src/imessage_tools.py:126` |
| sha256 helper | `src/attachment_manager.py:140` |
| EXIF date parsing | `src/attachment_manager.py:169` |
| Facebook encoding fix | `src/parsers/messenger_parser.py:5` |
| WhatsApp regexes, translation, skip heuristic, heatmap, media dating | `60b276c:main.py` |
| HTML design (theme, calendar, lightbox) | `templates/template.html` |
| per-service preferences and state | `Defaults/Services/*.json` |

**Fix:**
- **attributedBody** is pattern-matched, not decoded (`src/parsers/imessage_database_parser.py:564-667`).
  Long messages can be truncated. Use a real typedstream decoder.
- **Dates:** handle both seconds and nanoseconds `chat.db` epochs; store UTC + offset
  (`src/parsers/imessage_database_parser.py:669`).
- **Attachment names collide**, and same-second files overwrite each other; archival names need
  a counter. Conversion to JPEG must keep the original.
- **Tapbacks** on attachments (`p:1/`, `bp:`) aren't matched; the spam filter must tag messages,
  not drop them.
- **WhatsApp:** support Android and locale formats; keep indentation on continuation lines; keep
  "media omitted" placeholders.
- **HTML:** `templates/template.html:407` uses `| safe` on message text. Escape it.
- **`src/imessage_tools.py`** opens `chat.db` read-write (`:137`, `:596`, `:750`, `:949`). Open
  it read-only.

**Contradictions to resolve:**
- **Three names**: Chat2HTML, Chatter, Chattr. **Decision: "Chattr" everywhere**, for example
  `~/.chattr.json`, `chattr.sqlite`, `~/Documents/Chattr`, the `chattr` command.
- **Two database paths:** `./output/chat_archive.db` vs `{root}/Database/…`. Resolve to the
  Chattr root.
- **Two configuration designs:** a single `config.json` with `services.*` vs global + per-service
  files. Resolve to global + per-service.
- **The service enum** lists 3 services while there are 5 Defaults files. Resolve to the six
  Phase 1 sources.
- **Attachment naming and folders differ across docs.** Resolve to Caixa's date naming rule.
- **Stale docs**, such as `docs/iMessageConversionReadMe.md`.

**Licensing:**
- Chattr receives the MIT license.
- First, review `src/parsers/imessage_database_parser.py` and `src/imessage_tools.py` for code
  derived from imessage-exporter (GPL-3.0). `docs/MIGRATION_SUMMARY.md` calls the tool "a Python
  port" of it. Rewrite any derived parts.

### Context for later projects: model strategy

Not built in this project, but the master schema must support it:
- **Facts are retrieved from the database and cited, never stored in model weights.** Facts held
  in weights have no provenance, conflate similar events, can't say "the record doesn't say",
  can't be corrected cleanly, and can leak private data.
- **Training is for skill, familiarity and optional voice.** That means tool use against this
  box's schema, citing record IDs, refusing when the record is silent, and knowing the cast of
  characters. The method is retrieval-augmented fine-tuning on question-and-answer examples
  generated from the database, with sealed and private items excluded.
- **A deterministic verifier** checks every citation against the database.
- **Updates are incremental.** Pipeline stages track the last change number they processed.
  Chunks are conversation sessions, single emails, or call/voicemail transcripts. Summaries are
  recomputed only where new items land. Adapters are retrained periodically, gated by an
  evaluation.
- **The AI speaks as an archivist** with citations. A first-person persona mode exists only if
  the subject enabled it.

## Requirements

**Functional:**
- **F1:** Chattr parses:
  - iMessage (`chat.db`);
  - WhatsApp (iOS and Android `_chat.txt` + media);
  - Facebook Messenger/Instagram (Download Your Information JSON);
  - MBOX email;
  - Google Voice (Takeout: texts, calls, voicemails with audio);
  - iPhone Voicemail (audio + metadata).
- **F2:** every parser emits records through `BaseParser`. Records are upserted into
  `chattr.sqlite` (schema v0) by stable ID. Native per-service JSON export is available for each
  service.
- **F3:** reactions attach to their target message, including attachment targets.
- **F4:** email threads by Message-ID / In-Reply-To / References, and by Gmail thread ID when
  present.
- **F5:** voicemail audio is transcribed by a **local** speech-to-text model (no network). The
  transcript is stored with the entry, and the audio is kept as an attachment.
- **F6:** people input via `--contacts` (vCard) and `--aliases` (JSON); owner/author/sender
  derived; unresolved handles reported.
- **F7:** rendering:
  - one self-contained HTML page per person (or group) per year, merging all platforms
    chronologically;
  - date-named files;
  - a platform badge per entry;
  - stable anchors;
  - an embedded JSON data island;
  - escaped content;
  - the heatmap calendar;
  - mail pages per thread.
- **F8:** attachments are copied with archival `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>` names,
  with no collisions, the original kept, and the date written into standard metadata where
  supported.
- **F9:** optional translation through an OpenAI-compatible endpoint (local by default), with the
  translation-skip heuristic restored.
- **F10:** `chattr.sqlite` can be rebuilt from rendered HTML data islands.
- **F11:** preflight and configuration:
  - `~/.chattr.json` → root;
  - `--root` without prompting;
  - global `config.json` merged with `Services/<Service>.json`;
  - non-destructive repair;
  - `state` and `imports` updated on every run.
- **F12:** an interactive menu and an equivalent non-interactive command line for every action.
- **F13:** the Caixa master schema v0 provides items, people, aliases, item → person links with
  roles, imports, and an append-only change log with monotonic change numbers. Migrations are
  versioned.
- **F14:** the messages adapter performs the Caixa import/update flow and exports `aliases.json`.
- **F15:** the mirror workflow pushes `tools/chattr` history to Chattr's repository as a
  fast-forward.
- **F16:** collector contract and registry: collectors are discovered through the
  `caixa.collectors` entry-point group, and each declares inputs, "how to export" instructions,
  an options JSON Schema, `preview` and `run`.
- **F17:** `caixa worker` exposes the service layer over stdio JSON-RPC (box, collectors, import,
  jobs, people, browse, settings), with progress notifications. `--read-only` refuses every
  write.
- **F18:** the Caixa harness plugin (`harness/`) supervises `caixa worker` and registers
  owner-only `/api/caixa/*` routes, including a streaming route for job progress.
- **F19:** authoring pages in DeepSeek Harness: box dashboard; import wizard (source → "how to
  export" → input via file picker or inbox → options form → preview → run → report); jobs and
  logs; people; browse; a Settings section.
- **F20:** `caixa serve`:
  - checks Node 24.9+;
  - prepares Caixa's own DSH home with the pinned dsh and the plugin;
  - writes the privacy patch;
  - starts and supervises `dsh web` by Sele's rules, and reattaches after a crash;
  - opens the browser.
- **F21:** the CLI and the browser use the same service layer; every UI action has a CLI
  equivalent.
- **F22:** `chattr serve`: Chattr's small Python-only web UI (service, export, options, run with
  progress, open the output).

**Non-functional:**
- **N1:** Chattr runs without Caixa installed.
- **N2:** no network access during conversion. Speech-to-text and translation default to local
  models; a cloud endpoint is used only when explicitly configured. Keys come from the
  environment only, never from files in the repository.
- **N3:** imports are idempotent, so an overlapping re-import adds zero rows.
- **N4:** no real personal data or secrets in either repository. Fixtures are synthetic, and
  `.gitignore` covers output, databases, secrets and IDE files.
- **N5:** all times are stored as UTC + offset + precision.
- **N6:** the application listens on `127.0.0.1` only. The Python worker has no network listener
  and is reachable only through DSH's authenticated `/api/caixa/*` routes.
- **N7:** DeepSeek Harness's session-log upload and telemetry are disabled in Caixa's profile.
  Archive content never leaves the machine through the harness.
- **N8:** an exact DeepSeek Harness version is pinned (plus `engines.dsh` in the plugin), and
  upgrades are deliberate.
- **N9:** native installs require Node 24.9+ on the system; `caixa serve` checks it.

## Acceptance criteria

- For each of the six source fixtures:
  - every entry is present and untruncated, including iMessage attributedBody messages over 255
    characters;
  - times are correct in local time with an offset;
  - attachments are unique and date-named, with originals kept.
- A fixture person with iMessage, WhatsApp and Google Voice history renders as **one**
  `Messages/<Person>/` page set with one attachments folder.
- A group chat renders under `Messages/Groups/`.
- Mail renders under `Mail/<YYYY>/`, threaded.
- A fixture voicemail is transcribed locally with the network disabled. The transcript appears on
  the person's page, and the audio is kept.
- A second, overlapping import adds zero rows to `chattr.sqlite` and zero change-log rows to
  `caixa.sqlite`.
- Deleting `chattr.sqlite` and rebuilding it from the HTML gives identical IDs and counts.
- Every transformed filename matches `^\(\d{4}(-\d{2}(-\d{2})?)?\) `.
- Message text containing HTML or script renders as text.
- Every interactive menu action can be performed non-interactively.
- Preflight repair keeps existing preferences and state.
- The standalone `chattr` command works in an environment without Caixa.
- An edit under `tools/chattr/` appears in Chattr's repository through the mirror, as a
  fast-forward commit.
- Importing each source fixture through the browser wizard gives the same database rows and
  files as importing it with the CLI.
- A new collector package, once installed, appears in the import wizard with its form and "how to
  export" card, with no UI change.
- `caixa worker --read-only` rejects every write method.
- Requests to `/api/caixa/*` without DSH's session cookie, or with a foreign `Origin`, are
  rejected.
- With outbound network blocked, a full import through the browser completes, and no request
  leaves the machine.
- `caixa serve` refuses to start with a clear message when Node is older than 24.9, and
  reattaches to its running harness after its own process is killed.
- `chattr serve` converts a fixture in a browser, in an environment without Caixa, Node or
  DeepSeek Harness.

## Testing requirements

- **Project suite:** `python -m pytest -q`, run from the repository root (covers `caixa/` and
  `tools/chattr/`).
- **Chattr alone:** `python -m pytest tools/chattr/tests -q`, in an environment where only Chattr
  is installed.
- **Format and type checks:** `python -m black --check .` and `python -m mypy caixa tools/chattr/src`.
  These are the development tools already listed by Chattr's iMessage tool.
- Tests run only against the synthetic fixtures in `tests/fixtures/` and
  `tools/chattr/tests/fixtures/`. They never touch real data or the network.
- macOS-only access (a live `~/Library/Messages/chat.db`) is never needed by tests. iMessage
  tests use a synthetic `chat.db` built by a fixture script. Speech-to-text tests use a tiny local
  model or a stub behind the same interface.
- **Harness plugin:** `pnpm --dir harness test` (vitest, matching DeepSeek Harness's own
  tooling).
- **Worker protocol:** a pytest suite drives `caixa worker` over stdio (including `--read-only`)
  without a browser.

## Commit criteria

Before marking a ticket or subtask done, and before any git commit:

- [ ] Plan-task verification command passed (RED then GREEN)
- [ ] The change meets the matching requirement and acceptance criteria
- [ ] Project suite passes: `python -m pytest -q`; `black --check` and `mypy` are clean for
      touched code
- [ ] The commit's author and committer are a real person (repo-local identity), never a
      fictitious or agent identity. AI assistance is credited with a `Co-Authored-By` trailer.
- [ ] No documentation was placed only in an agent-specific location (for example `.claude/`)
- [ ] No personal data, secrets or generated databases are staged
- Commit message format: `{ticket-id} {task-id}: {title}`
- **Branches:**
  - completed tickets are committed on `2026-Istanbul/Phase1-Collector`;
  - the project branch is merged into `working` when the project is done;
  - `main` is production only.

## Tasks Breakdown

Proposed. Each item becomes a ticket after approval; dependencies are in brackets.

**Prerequisites:**
- ~~Purge Chattr's history (chat database, transcript with API key, IDE files) and add
  `.gitignore`~~. Done 2026-11-01; Chattr `main` is at `0152912`.
- The maintainer revokes the exposed OpenRouter key (outside the repository).

**Foundations:**
1. **Caixa repository foundations**: Python project skeleton for `caixa/`; `pytest`, `black`,
   `mypy` setup.
2. **Synthetic fixture family**: a fictional family with:
   - a builder script for a synthetic iMessage `chat.db`;
   - WhatsApp iOS and Android exports;
   - Messenger/Instagram JSON with mojibake;
   - an MBOX (encoded headers, HTML-only mail, attachments, threads);
   - a Google Voice Takeout sample (texts, calls, voicemails with audio);
   - iPhone voicemail audio + metadata;
   - a vCard file.

   [1]
3. **Chattr import + licensing**: `git subtree add --prefix=tools/chattr` with the purged
   history; review the imessage-exporter derivation; add the MIT license to Chattr. [1]

**Chattr core:**

4. **Chattr stabilization**:
   - rename to "Chattr" everywhere;
   - wire preflight ↔ configuration (pointer → root → global + per-service merge);
   - fix the iMessage configuration keys;
   - make repair non-destructive;
   - add `--root`;
   - fix the HTML crash and the template field names;
   - prune unused dependencies;
   - consolidate the docs.

   [3]
5. **Unified schema v0** (`chattr.sqlite`): the tables above, migrations, stable IDs, one
   `DatabaseManager` for all services, `imports`/`state` wiring, per-service JSON export kept.
   [4]
6. **Interactive menu + command line**: the waterfall menu; non-interactive equivalents,
   including the restored iMessage flags. [4]

**Sources:**

7. **iMessage**: behind `BaseParser`, into the database; attributedBody decoding, epochs, spam
   filter on the parallel path, read-only tools. [2, 5]
8. **WhatsApp**: restore from `60b276c` (media placeholders, renaming/EXIF via
   AttachmentManager) + Android/locale formats. [2, 5]
9. **Messenger/Instagram**: attachments, shared links. [2, 5]
10. **MBOX email**: threading, encoded headers, HTML and plain bodies, attachments by hash. [2, 5]
11. **Google Voice**: texts, calls, voicemails with audio. [2, 5]
12. **iPhone Voicemail + local speech-to-text**: transcription interface, local model, transcript
    storage. [2, 5]

**Shared pipeline:**

13. **One attachment pipeline**: AttachmentManager generalized for all services; date naming,
    per-person `Attachments/`, no collisions, originals kept. [5]
14. **People**: owner/author/sender derivation, `--contacts`, `--aliases`, unresolved-handle
    report. [5]
15. **HTML from the database**: per-person-per-year pages, the heatmap calendar, data island,
    anchors, escaping, call/voicemail entries, mail pages. [13, 14]
16. **Translation**: OpenAI-compatible endpoint (local by default) + the skip heuristic. [5]
17. **Rebuild `chattr.sqlite` from the HTML data islands.** [15]

**Caixa integration:**

18. **Caixa master schema v0 + messages adapter**: migrations; items, people, aliases, links,
    imports, change log; the `ATTACH`/upsert adapter; `aliases.json` export. [5, 14]
19. **Mirror workflow**: `.github/workflows/mirror-chattr.yml`, the write-token secret, the
    "Developed in Caixa" banner in Chattr's README. [3]

**Application:**

20. **Collector contract + registry**: entry-point discovery, metadata, "how to export"
    instructions, options JSON Schema (seeded from Chattr's `Defaults/Services/*.json`),
    `preview`/`run`; Chattr's six sources registered. [5, 18]
21. **Caixa service layer + `caixa worker`**: stdio JSON-RPC, SQLite jobs table with progress
    notifications, inbox folder watching, `--read-only`; the CLI on the same layer; the
    worker-protocol test suite. [20]
22. **Harness plugin skeleton** (`harness/`):
    - pinned dsh + `engines.dsh`;
    - reproduced client build preset;
    - host service supervising `caixa worker`;
    - owner-only `/api/caixa/*` routes + a streaming progress route;
    - sidebar icon with an empty Caixa page;
    - vitest.

    [21]
23. **`caixa serve` launcher**: Node 24.9+ check, Caixa's own DSH home, plugin install, privacy
    patch (session-log upload and telemetry off), Sele's launch rules, reattach. [22]
24. **Import wizard + jobs pages**: source list, "how to export" cards, file picker and inbox,
    generated options forms, preview, run with live progress, result report, jobs and logs,
    toasts. [22, 23]
25. **People page**: unresolved handles; link, merge, rename; re-render the affected pages.
    [14, 24]
26. **Browse page + Settings section**: generated pages served through `/api/caixa/box/*`; box
    location, local model endpoints, privacy defaults. [24]
27. **`chattr serve`**: Chattr's Python-only web UI (Jinja2 + htmx). [6, 15]

## Risks and assumptions

- **The exposed OpenRouter key** must be revoked. Purging the history doesn't un-leak it, and
  GitHub may serve the old commit by its hash until garbage collection.
- **iMessage `attributedBody`** requires a correct typedstream decoder. A suitable library must
  be found or written.
- **Local speech-to-text** needs a model the maintainer can run locally. Model size vs. accuracy
  needs a choice, and tests must not download models.
- **Export formats change without notice** (WhatsApp locales, Meta's JSON layout, Google
  Takeout). The fixtures and parsers need to be versioned.
- **Identity resolution is partly manual.** Pages for unresolved handles will move once they are
  linked.
- **The mirror needs a write token** for Chattr's repository, stored as a GitHub secret. The
  maintainer must create it.
- **The privacy purge rewrote Chattr's history.** Existing clones must be re-cloned.
- **DeepSeek Harness is a pre-stable developer preview.** Plugin interfaces and slot names change
  without aliases; pinning and deliberate upgrades limit the damage, but each upgrade can cost
  rework in `harness/`.
- **DSH's client build preset is unpublished.** Reproducing the bundle format outside its
  monorepo may break when DSH changes it.
- **DSH's defaults upload session logs and telemetry.** Caixa's patch must disable them, and the
  no-network acceptance test guards against regressions.
- **DSH has a single owner and no roles.** Heir read-only access must be enforced by Caixa, in
  a later project.
- **Python environment management is Caixa's job.** DSH doesn't manage Python; `caixa serve`
  must find and run the right interpreter.
- **Node 24.9+** is an extra install for native users.
- **Assumption:** email arrives as MBOX (Gmail Takeout).

## Open questions

- Which typedstream decoder to use for iMessage `attributedBody` (existing library vs. a minimal
  in-house one, with licenses checked).
- Which local speech-to-text runtime and model size to use as the default for Voicemail.
- Minimum Python version (proposal: 3.10, matching Chattr's development interpreter).
- For the later photo tool:
  - which XMP/MWG fields carry people and dates;
  - verifying exiftool's `ImageDataHash` as the identity of media files.
- Names of later projects on the Istanbul release train (the maintainer decides).
- Where Caixa's own DeepSeek Harness home lives: inside the box (`.caixa/harness/`) or in a
  per-user application folder (the maintainer decides the name and location).
- The inbox folder's name and location (the maintainer decides).
- Which exact DeepSeek Harness version to pin when ticket 22 starts.
- Windows support for `caixa serve` (process-tree termination differs; see Sele and
  `dsh-vscode-plugin`).
