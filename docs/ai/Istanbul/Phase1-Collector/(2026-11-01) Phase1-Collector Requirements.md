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
focus: "DRAFT: awaiting maintainer approval. No tickets until approved."
---


# Phase1-Collector Requirements

> **Status: DRAFT.** This file records the architecture agreed in design discussion. Tickets are
> created from the Tasks Breakdown only after the maintainer approves it.

## Overview

Phase1-Collector establishes Caixa's data architecture and delivers the message collector.
Chattr, an existing open tool, becomes Caixa's converter for every conversation-like source
(iMessage, WhatsApp, email from MBOX, Facebook Messenger/Instagram, Slack). It writes a SQLite
domain store and styled HTML pages organized by person and named by date. A messages adapter
loads that output into Caixa's master database, the system's source of truth. Chattr lives in
Caixa and is mirrored back to its own repository.

## Goals

1. Agree and document the data architecture: box layout, organizing rules, databases and
   ownership, handoff contract, stable IDs, rebuild chain.
2. Chattr: a standalone, tested converter for five sources, writing `chattr.sqlite` and
   date-named, per-person HTML.
3. Caixa master database schema v0 plus the messages adapter.
4. A working mirror of Chattr from Caixa to Chattr's repository.

## Non-goals

- Photos and media (separate tool, later project).
- Model, search index, knowledge distillation, training, harness (later projects). This project
  only makes sure the master schema serves them (change log, item abstraction, people links).
- A standalone `.eml` parser.
- Importing any other existing tool.
- A graphical interface for imports.

## Architecture

### Guiding principle: normalize for people, not platforms

Exports are organized for each platform's database. Caixa **transforms** them into an archive
organized for people:
- rename to archival names;
- embed dates and standard metadata into files;
- fix text encoding;
- record local time with its offset;
- organize by person, date and conversation.

We are transforming an archive copy, not modifying data that live applications use. Keeping the
raw export is optional at import time. Provenance (which export, when, its hash) is always
recorded.

Correctness still matters wherever it changes meaning:
- no dropped or garbled messages;
- no attachment overwriting another;
- correct times;
- re-importing an overlapping export adds nothing twice.

### Organizing principles: dates first, people second

**Dates are the backbone.**
- Every file Caixa or Chattr transforms is named `(YYYY-MM-DD) <name>.<ext>`.
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
    (YYYY) <Person>.html      ← every message to/from this person across all platforms,
                                 merged chronologically, platform badge per message, one page per year
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
| **Chattr** | `tools/chattr/` (subtree, mirrored to Chattr's repository) | Standalone message converter: parsers → `chattr.sqlite` → HTML. Never imports Caixa. |
| **Caixa core** | `caixa/` | Master database (schema, migrations, change log), collector adapters, CLI. |
| **Messages adapter** | `caixa/collectors/messages.py` | Runs Chattr into `.caixa/work/chattr/`, `ATTACH`es `chattr.sqlite`, upserts into the master, exports `aliases.json`. |
| **Mirror workflow** | `.github/workflows/mirror-chattr.yml` | On push to the default branch: `git subtree split --prefix=tools/chattr` → push to Chattr's repository (fast-forward). |
| **Fixtures** | `tests/fixtures/` | Synthetic fixture family: no real data, ever. |

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
    work/chattr/chattr.sqlite      ← Chattr's domain store
    box.yaml  model/  harness/  imports/ (optional raw-export retention)  logs/
```

**Two data patterns:**
- **Render** (messages, mail): export → collector database → generated HTML. The database is
  the working store the files are generated from. JSON is only an interchange format.
- **Index** (photos, media, documents; later projects): normalize the files → scan them into a
  catalog database, which acts as a fast-search cache over metadata stored in the files.

**Database inventory and ownership.** Caixa's master is separate from each collector's database
because:
- Chattr must run standalone;
- lifecycles differ (fast-iterating conversion state vs. decades of curated history);
- only the master sees every domain and can resolve identities across them.

| Store | Owner | Holds |
| --- | --- | --- |
| `chattr.sqlite` | Chattr | sources/import runs, threads, participants/handles, messages (+ optional mail headers: Message-ID, In-Reply-To/References, Gmail thread ID, labels, cc/bcc), reactions, attachments (by hash) |
| `caixa.sqlite` | Caixa | items (one per message/email/photo/document: stable ID, type, time + offset + precision, text, file path + anchor, privacy, content hash, version), people, aliases, item → person links with role (sender, recipient, participant, depicted, mentioned), imports/provenance, change log, human curation |

**Handoff contract**: the adapter `ATTACH`es the collector database and upserts by stable ID in
SQL. Each insert or update appends a change-log row: change number (monotonic), item ID,
operation, version, import ID.

**Stable IDs:**
- chat: source thread ID + source message ID, or else a hash of (service, thread, time, sender,
  body);
- email: normalized Message-ID, or else a hash of the headers;
- (later) photos/media: a hash of the image data only, located by path relative to the box root.

**Rebuild chain**: top-level files → domain stores → master → (later) index/knowledge.
- Each rendered HTML page embeds its messages as a JSON data island
  (`<script type="application/json">`) and gives every message an `id="m-<id>"` anchor. So
  `chattr.sqlite` can be rebuilt from the HTML, and citations deep-link to exact messages.
- No Caixa-specific metadata is written into user files. Only Caixa-generated files (HTML) carry
  Caixa IDs.
- Human curation (people, relationships, corrections) is also written to the top level
  (`People/`), so losing `.caixa/` loses nothing irreplaceable.

### Key flows

**Standalone Chattr:**
`chattr convert <source> <export> --out <dir> [--contacts file.vcf] [--aliases aliases.json]`
→ parse → upsert into `<dir>/chattr.sqlite` (deduplicated by stable ID) → re-render only the
changed person and group pages → report handles it couldn't resolve.

**Inside Caixa (an import or update):**
1. The adapter writes `aliases.json` from the master's people/aliases.
2. It runs Chattr into `.caixa/work/chattr/` and renders into the box's `Messages/` and `Mail/`.
3. It `ATTACH`es `chattr.sqlite` and upserts items, item → person links and provenance.
4. It appends to the change log.
5. It reports unresolved handles for a human to link.
6. Linking a handle re-runs rendering for the affected pages.

### Chattr: decision and code-review findings

Chattr's history already trends toward this design:
- a working WhatsApp → HTML converter (`3644cd1`, `main.py`);
- iMessage support (`455b15a`);
- a SQLite store (`e160fe4`);
- a unified parser skeleton (`1a2c4a3`: `src/parsers/base_parser.py`,
  `src/database_manager.py`).

Phase 1 finishes that design. In the line references below, **Ref** means a file and line in
Chattr at commit `1a2c4a3`.

**Carry forward:**

| What | Ref |
| --- | --- |
| read-only `chat.db` connect and its Full Disk Access message | `iMessageDatabase.py:304-324` |
| chat, participant and group-name logic | `iMessageDatabase.py:453-555` |
| phone/email normalization and vCard lookup | `iMessageDatabase.py:369-432`, `iMessageDatabase.py:691-712` |
| tapback table | `iMessageDatabase.py:272-281` |
| bulk tapback query | `iMessageDatabase.py:1179-1286` |
| diagnostics, which become a `doctor` command | `iMessageTools.py:126-386` |
| sha256 helper | `AttachmentManager.py:140` |
| Facebook encoding fix | `src/parsers/messenger_parser.py:5` |
| WhatsApp message and attachment regexes, attachment-date logic, gallery grouping idea | `3644cd1:main.py` |
| HTML template design (theme, calendar, lightbox) | Chattr's `templates/template.html` |

**Fix:**
- **attributedBody** is byte-scanned rather than decoded. Messages over 255 characters can shrink
  to one character (`iMessageDatabase.py:564-667`). Use a real typedstream decoder.
- **Dates**: handle both seconds and nanoseconds `chat.db` epochs; store UTC + offset
  (`iMessageDatabase.py:669-676`).
- **Attachment names** made only from a timestamp collide, and same-second photos overwrite each
  other (`AttachmentManager.py:327-357`). Archival names need a counter.
- **Tapbacks** on attachments (`p:1/`, `bp:`) are not matched (`iMessageDatabase.py:1221`). The
  spam filter must tag messages, not drop them.
- **WhatsApp**: support Android and locale date formats; keep indentation on continuation lines;
  keep "media omitted" placeholder messages.
- **HTML**: autoescaping is off and `|safe` is used (`templates/template.html:407`). Turn
  escaping on.
- **Tools** open `chat.db` read-write (`iMessageTools.py:137`). Open it read-only.

**Drop or change:**
- Cloud translation (OpenRouter) becomes optional local-LLM enrichment, in a later project.
- Interactive `input()` menus give way to a real CLI.
- The stub iMessage parser is replaced by the working reader behind `BaseParser`.

**Licensing:**
- Chattr receives the MIT license.
- First, review `iMessageDatabase.py` and `iMessageTools.py` for code derived from
  imessage-exporter (GPL-3.0). A docstring cites "the Rust implementation", and the diagnostics
  mirror its output. Rewrite any derived parts.

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
  Chunks are conversation sessions, single emails, or photo captions. Summaries are recomputed
  only where new items land. Adapters are retrained periodically, gated by an evaluation.
- **The AI speaks as an archivist** with citations. A first-person persona mode exists only if
  the subject enabled it.

## Requirements

**Functional:**
- **F1:** Chattr parses iMessage (`chat.db`), WhatsApp (iOS and Android `_chat.txt` + media),
  MBOX, Facebook Messenger/Instagram (Download Your Information JSON), and Slack (workspace export
  JSON).
- **F2:** every parser emits the standard record through `BaseParser`. Records are upserted into
  `chattr.sqlite` by stable ID.
- **F3:** reactions attach to their target message, including attachment targets.
- **F4:** email threads by Message-ID / In-Reply-To / References, and by Gmail thread ID when
  present.
- **F5:** people input via `--contacts` (vCard) and `--aliases` (JSON). Unresolved handles are
  reported.
- **F6:** rendering:
  - one self-contained HTML page per person (or group) per year, merging all platforms
    chronologically;
  - date-named files;
  - a platform badge per message;
  - stable message anchors;
  - an embedded JSON data island;
  - escaped content.
- **F7:** attachments are copied with archival `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>` names,
  with no collisions, and the date written into standard metadata where supported.
- **F8:** `chattr.sqlite` can be rebuilt from rendered HTML data islands.
- **F9:** the Caixa master schema v0 provides items, people, aliases, item → person links with
  roles, imports, and an append-only change log with monotonic change numbers. Migrations are
  versioned.
- **F10:** the messages adapter performs the import/update flow above and exports `aliases.json`.
- **F11:** the mirror workflow pushes `tools/chattr` history to Chattr's repository as a
  fast-forward.

**Non-functional:**
- **N1:** Chattr runs without Caixa installed.
- **N2:** no network access during conversion. Nothing is sent to external services.
- **N3:** imports are idempotent, so an overlapping re-import adds zero rows.
- **N4:** no real personal data in the repository. Fixtures are synthetic.
- **N5:** all times are stored as UTC + offset + precision.

## Acceptance criteria

- For each source fixture:
  - every message is present and untruncated, including iMessage attributedBody messages over 255
    characters;
  - times are correct in local time with an offset;
  - attachments are unique and date-named.
- A fixture person with both iMessage and WhatsApp history renders as **one**
  `Messages/<Person>/` page set with one attachments folder.
- A group chat renders under `Messages/Groups/`.
- A second, overlapping import adds zero messages to `chattr.sqlite` and zero change-log rows to
  `caixa.sqlite`.
- Deleting `chattr.sqlite` and rebuilding it from the HTML gives identical message IDs and counts.
- Every transformed filename matches `^\(\d{4}(-\d{2}(-\d{2})?)?\) `.
- Message text containing HTML or script renders as text.
- The standalone `chattr` CLI works in an environment without Caixa.
- An edit under `tools/chattr/` appears in Chattr's repository through the mirror, as a
  fast-forward commit.

## Testing requirements

- **Project suite:** `python -m pytest -q`, run from the repository root (covers `caixa/` and
  `tools/chattr/`).
- **Chattr alone:** `python -m pytest tools/chattr/tests -q`, in an environment where only Chattr
  is installed.
- Tests run only against the synthetic fixtures in `tests/fixtures/` and
  `tools/chattr/tests/fixtures/`. They never touch real data.
- macOS-only access (a live `~/Library/Messages/chat.db`) is never needed by tests. iMessage
  tests use a synthetic `chat.db` built by a fixture script.

## Commit criteria

Before marking a ticket or subtask done, and before any git commit:

- [ ] Plan-task verification command passed (RED then GREEN)
- [ ] The change meets the matching requirement and acceptance criteria
- [ ] Project suite passes: `python -m pytest -q`
- [ ] The commit's author and committer are a real person (repo-local identity), never a
      fictitious or agent identity. AI assistance is credited with a `Co-Authored-By` trailer.
- [ ] No documentation was placed only in an agent-specific location (for example `.claude/`)
- Commit message format: `{ticket-id} {task-id}: {title}`
- **Branches:**
  - completed tickets are committed on `2026-Istanbul/Phase1-Collector`;
  - the project branch is merged into `working` when the project is done;
  - `main` is production only.

## Tasks Breakdown

Proposed. Each item becomes a ticket after approval; dependencies are in brackets.

1. **Repository foundations**: Python project skeleton for `caixa/`, the test setup, and the
   `LICENSE` header policy.
2. **Synthetic fixture family**: a fictional family with:
   - a builder script for a synthetic iMessage `chat.db`;
   - WhatsApp iOS and Android exports;
   - Messenger/Instagram JSON with mojibake;
   - a Slack export;
   - an MBOX (encoded headers, HTML-only mail, attachments, threads);
   - a vCard file.

   [1]
3. **Chattr import + licensing**: `git subtree add --prefix=tools/chattr` with full history;
   review the imessage-exporter derivation; add the MIT license to Chattr. [1]
4. **Chattr restructure**: installable package, CLI (`chattr convert …`, `chattr doctor`),
   `BaseParser` standard record, `chattr.sqlite` schema v0 for chat + mail with stable IDs and
   upserts. [3]
5. **iMessage parser**: port the working reader behind `BaseParser` with the fixes listed above.
   [2, 4]
6. **WhatsApp parser**: restore from `3644cd1`, add Android and locale formats and the other
   fixes. [2, 4]
7. **MBOX parser**: threading, encoded headers, HTML and plain bodies, attachments by hash. [2, 4]
8. **Messenger/Instagram parser**: complete the skeleton, including the encoding fix. [2, 4]
9. **Slack parser**: channels, DMs, threads, files. [2, 4]
10. **People input and grouping**: `--contacts`, `--aliases`, unresolved-handle report,
    person/group assignment. [4]
11. **HTML renderer**: per-person-per-year date-named pages, platform badges, anchors, data
    island, escaping, archival attachment naming and date metadata, mail pages. [4, 10]
12. **Rebuild from HTML**: re-create `chattr.sqlite` from data islands. [11]
13. **Caixa master schema v0 + messages adapter**: migrations; items, people, aliases, links,
    imports, change log; the `ATTACH`/upsert adapter; `aliases.json` export. [4, 10]
14. **Mirror workflow**: `.github/workflows/mirror-chattr.yml`, the write-token secret, and the
    "Developed in Caixa" banner in Chattr's README. [3]

## Risks and assumptions

- **iMessage `attributedBody`** requires a correct typedstream decoder. A suitable library must
  be found or written.
- **Export formats change without notice** (WhatsApp locales, Meta's JSON layout, Slack). The
  fixtures and parsers need to be versioned.
- **Identity resolution is partly manual.** Pages for unresolved handles will move once they are
  linked.
- **The mirror needs a write token** for Chattr's repository, stored as a GitHub secret. The
  maintainer must create it.
- **Assumption:** email arrives as MBOX (Gmail Takeout).

## Open questions

- Which typedstream decoder to use for iMessage `attributedBody` (existing library vs. a minimal
  in-house one, with licenses checked).
- Minimum Python version (proposal: 3.10).
- Linter/formatter choice for the repository.
- For the later photo tool:
  - which XMP/MWG fields carry people and dates;
  - verifying exiftool's `ImageDataHash` as the identity of media files.
- Names of later projects on the Istanbul release train (the maintainer decides).
