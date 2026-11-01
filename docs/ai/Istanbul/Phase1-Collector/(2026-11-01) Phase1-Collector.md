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
focus: "Message collection: Chattr becomes Caixa's message converter, on top of Caixa's data architecture"
---

# Project

## Background

A generation ago, a person's life survived as physical things: photo albums, letters, tapes,
paper records. Whoever inherited them could pick them up and understand them. Today a life is
born digital. It lives in phones, cloud accounts and messaging apps, and it disappears with a
lost device, a closed account, or a death nobody planned for. Even people who carefully export
their data end up with an organized but impenetrable pile. Their heirs would have to dig through
it to understand their own family history.

**Caixa** (Portuguese for *box*) is an open-source digital-legacy system. It turns a person's
scattered digital life into one durable box that the next generation can actually use. It has
three parts:

1. **Collectors**: transform personal data from platform exports into an archival form.
2. **A personal model**: a small, open, local AI that becomes the expert on that person,
   answering from the archive and citing it.
3. **A harness**: runs the box locally in a web browser, so an heir can ask questions, read and
   browse.

Most personal data arrives as takeout-style exports (Google Takeout, Facebook/Instagram
"Download Your Information", WhatsApp chat exports, Apple's privacy export) or as local stores
such as the iMessage database. These exports are organized for the platform's database, not for
a person:
- opaque filenames;
- dates kept in sidecar files;
- timestamps in UTC epochs;
- double-encoded text;
- one enormous file per thread.

Caixa's job is **transformation and normalization for people**.

**Phase1-Collector** is the first project on the Istanbul release train. It establishes Caixa's
data architecture and builds the first, most valuable collector: **messages**. An existing open
tool, **Chattr**, is carried into Caixa as the message converter.

Chattr began as a WhatsApp-to-HTML script and grew into a multi-service "Swiss Army knife" for
message archives. It has:
- one parser per platform;
- a direct iMessage database reader;
- a settings design with per-service import state for repeated, incremental updates;
- styled HTML output.

Much of its v2 design is scaffolding that still needs wiring. Its own plan names the next step:
a **unified schema**, then the **unified SQLite database**. Changes made to Chattr inside Caixa
flow back to Chattr's own repository, so it stays usable on its own.

## Goals

- Define Caixa's **data architecture**:
  - the box layout;
  - the date and people organizing rules;
  - the master database as the source of truth;
  - how collector databases hand off to it;
  - stable IDs so repeated imports never duplicate.
- Make **Chattr** a standalone, well-tested converter. It finishes its unified schema and SQLite
  milestone, and turns six sources into:
  - a SQLite domain store, plus each service's native JSON export;
  - styled, self-contained HTML pages organized **by person** and named **by date**.

  The six sources: iMessage, WhatsApp, Facebook Messenger/Instagram, email (MBOX), Google Voice,
  and iPhone Voicemail (transcribed locally).
- Create **Caixa's master database (schema v0)** and the messages adapter that brings Chattr's
  output into it, linking every message to the people involved.
- Set up the **mirror** so Chattr changes made in Caixa reach Chattr's repository automatically.
- Give people a **browser-based way to build their box**. `caixa serve` opens Caixa's authoring
  pages inside DeepSeek Harness, with all conversion done in Python. New export sources appear in
  the import wizard automatically as collectors are added. Chattr gets its own small web UI
  (`chattr serve`) for standalone use.

## Non-goals

- Slack and other further message sources (Google Chat/Hangouts, Telegram, …): a later project.
- Photos and other media as their own domain. These are handled by a separate kind of tool in a
  later project. Message attachments are in scope.
- The personal model, the search index, knowledge distillation, training, and the heirs' "Ask"
  experience. Later projects on the Istanbul train; this project only shapes the data and the
  application they need.
- Heir mode (a read-only `caixa serve`) and a Docker image: a later project, together with the
  model and "Ask" work.
- A native desktop app wrapper. The browser is the interface.
- A standalone `.eml` email parser. MBOX first; `.eml` only if needed later.
- Bringing any other existing tools into Caixa.

## Target users

- **People preserving their own digital life**: they run collectors on their exports and want a
  clean, durable, human-readable result.
- **Heirs and family members**: they open the box years later. They need something they can read
  in a browser and browse in a file manager, with no technical knowledge and no specific app.
- **Contributors**: developers adding collectors, fixing parsers and improving output. They need
  clear contracts, fixtures and tests.

## User stories

- As a person preserving my life, I want to convert my iMessage, WhatsApp and Messenger history
  with a friend into **one** chronological page set for that friend, so I can read our whole
  relationship in one place regardless of which app we used.
- As a person preserving my life, I want message photos renamed to `(YYYY-MM-DD) …` with the date
  embedded in the image, so they sort correctly anywhere.
- As a person preserving my life, I want to import a newer export that overlaps an older one
  without getting duplicates.
- As a person preserving my life, I want old voicemails transcribed on my own computer, so the
  words are searchable and readable while the original audio is kept.
- As an heir, I want to open a folder named after my grandmother and find every conversation
  with her as pages I can read in any browser.
- As a person preserving my life, I want to build my box in a web browser, picking a source,
  following its "how to export" steps, previewing what will be imported and watching it run,
  without using a terminal.
- As a person preserving my life, I want to link the phone numbers, emails and usernames that
  belong to the same person, so all our conversations end up together.
- As a user who doesn't need Caixa, I want to run Chattr on its own, from a terminal or a simple
  browser page, to turn a chat export into readable offline HTML.
- As a contributor, I want a synthetic test corpus for every supported platform, so I can change
  a parser safely.

## Constraints

- **Durable, open formats**: SQLite, HTML, JSON, standard image metadata (EXIF/XMP). No
  proprietary formats.
- **Local-first**: no personal data is sent to cloud services by default.
- **Caixa is an enabler, not a requirement**: the box's top-level files must be usable without
  Caixa. Chattr must run without Caixa installed.
- **No Caixa-specific metadata written into user files**: photos are referenced by path, and
  identified by a hash of their image data.
- **Open source, MIT license.** Nothing in the repository is personalized to any individual.
  Tests use synthetic data only; real personal data never enters the repository.
- **Python** for collectors (Chattr's existing language).
- **Browser UI on DeepSeek Harness**, which is a pre-stable developer preview. Caixa pins an exact
  version, keeps its own harness home, and disables the harness's session-log upload and
  telemetry. Native installs need Node 24.9+.
- **Local only**: the application listens on `127.0.0.1` and is reached through a browser on the
  same computer.
- **The tool's name is "Chattr" everywhere** (files, folders, commands, docs).

## Success criteria

- The Requirements for this project are approved, and every ticket in its Tasks Breakdown is
  done.
- Chattr converts the synthetic fixtures for every supported platform:
  - no dropped or truncated messages;
  - unique, date-named attachments;
  - correct local times;
  - per-person pages merging several platforms.
- Re-importing an overlapping export adds zero messages.
- Chattr's database can be rebuilt from its own HTML output.
- The messages adapter fills the master database with items linked to people, and re-running it
  on unchanged data changes nothing.
- An edit to Chattr inside Caixa appears in Chattr's repository through the mirror.
- A person can create a box and import each supported source entirely in the browser, with the
  same result as the command line.
- `chattr serve` converts an export in a browser without Caixa, Node or DeepSeek Harness
  installed.
