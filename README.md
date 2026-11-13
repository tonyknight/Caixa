# Caixa

> *Caixa*: Portuguese for **box**.

A generation ago, a person's life survived as physical things: photo albums, letters, tapes,
paper records. Whoever inherited them could pick them up and understand them. Today a life is
born digital. It lives in phones, cloud accounts and messaging apps, and it can vanish with a
lost device, a closed account, or a death nobody planned for. Even carefully exported data
becomes a pile that the next generation has to dig through to understand their own family
history.

**Caixa is an open-source digital-legacy system.** It turns a person's scattered digital life
into one durable box that their family can actually use: files they can read in any web browser
today and in decades, a way to ask questions of them, and nothing that depends on a company, a
cloud account or even on Caixa itself.

- [How Caixa works](#how-caixa-works)
- [How we think about it](#how-we-think-about-it)
- [Part 1: Collectors](#part-1-collectors) · [Part 2: A personal model](#part-2-a-personal-model) ·
  [Part 3: The harness](#part-3-the-harness)
- [Where the project is](#where-the-project-is)
- [Installation](#installation) · [Using Caixa from the command line](#using-caixa-from-the-command-line) ·
  [The browser interface](#the-browser-interface)

## How Caixa works

```
 your exports ──► COLLECTORS ──► THE BOX ──► PERSONAL MODEL ──► HARNESS
 (WhatsApp, iMessage,  transform and   durable files    answers from the     runs all of it in a
  mail, voicemail …)   organize them   + databases      box, citing it       web browser, locally
                                                         (planned)
```

1. **Collectors** transform personal data into an archival form. Most data arrives as
   takeout-style exports (Google, Facebook/Instagram, WhatsApp, Apple and others), organized for
   each platform's database rather than for people. Collectors rename, date, fix and organize
   that data, **dates first, people second**.
2. **The box** is where the result lives: a folder of ordinary files (pages, photos, recordings)
   with a database beside it that keeps everything findable and connected.
3. **A personal model** is a small, open, local AI that becomes the expert on that person. It
   answers from the box and cites the original messages, photos and documents. *(Planned.)*
4. **A harness** runs the whole thing on your own computer, in a web browser, so a person can
   build their box, and someone who inherits it can read, browse and ask, with no technical
   knowledge. It is built to be updated for years without touching the data.

## How we think about it

**Normalize for people, not platforms.** An export is organized for a platform's database: opaque
file names, dates kept in side files, times as UTC counters, text encoded twice, one enormous file
per conversation. Caixa transforms a *copy* into something a person can use: files renamed with
their dates, dates written into the files' own metadata (when ExifTool is installed), text repaired, times kept with their
local offset, everything grouped by person and by date. Your original exports (and anything a
live app still uses) are never changed.

**Dates first, people second.** Dates are the backbone: every transformed file is named
`(YYYY-MM-DD) name.ext`, with honest precision (`(2019-07) …` or `(2019) …` when only the month or
year is known; a day is never invented). People are the second axis: all of your messages with one
person, across every app, live together in one place.

**Local first.** Nothing leaves your computer unless you say so. There is no cloud service in the path;
speech-to-text runs on your own machine, and translation, when you turn it on, talks only to the address
you give. A paid translation service on the internet needs a second, explicit yes.

**Open, durable formats, and Caixa is an enabler, not a requirement.** The box is SQLite, HTML,
JSON and standard image metadata. Everything at its top level is ordinary files you can open with a
web browser or a file manager, with or without Caixa. Chattr, the message converter at the heart of
Phase 1, runs on its own without Caixa installed.

**Import again, safely.** Every item gets a stable identity, so importing a newer export that
overlaps an older one adds only what is new and changes nothing else. Every change is recorded in an
append-only log. That is what keeps a box current for years, and what lets later stages (search,
the model) catch up incrementally instead of starting over.

**Facts come from records, not from memory.** When a model answers a question about a person's life, the
facts must come from the box and be cited, never from what the model "remembers" (more in
[Part 2](#part-2-a-personal-model)).

## Part 1: Collectors

A **collector** is how one kind of export enters a box. Each one declares what it accepts, the plain
steps to export from that platform, and an options schema; it can **preview** an import (a dry run: counts,
date range, people, what is not yet named) and **run** it, reporting progress. The command line and the
browser are built from those declarations, so **a new collector appears in both with no interface
work**. Collectors are found through a Python entry-point group (`caixa.collectors`), so a new source can
ship as its own package.

Phase 1 delivers the **messages** collectors. **[Chattr](tools/chattr/)**, an existing open tool, is
carried into Caixa as the converter for every conversation-like source:

| Source | Takes | Notable details |
| --- | --- | --- |
| iMessage | the macOS `chat.db` | read-only, tapbacks, spam tagged (never dropped) |
| WhatsApp | an exported chat (`.zip` or folder) | media filed with the person, ambiguous dates resolved |
| Facebook Messenger / Instagram | "Download your information" JSON | doubled text encoding repaired |
| Mail | `.mbox` (a Gmail Takeout) | threaded, attachments filed by date and sender |
| Google Voice | a Takeout folder | calls, texts and voicemail audio |
| iPhone voicemail | a backup's voicemail folder | optional transcription on your own computer |

What happens to an export: it is **read** into a common shape (conversations, people, messages,
attachments, reactions); its **attachments are filed** under dated names next to the person; messages are
**stored under stable IDs**; handles (phone numbers, addresses, usernames) are **matched to people**;
**pages are drawn**, one per person and year; and the **master database** is updated to say which page
shows each item. How each step works, and what happens to attachments in particular, is described in
[`docs/Documentation/Collector.md`](docs/Documentation/Collector.md).

**Two databases, on purpose.** Chattr keeps its own working store (`chattr.sqlite`), so it can run
standalone and iterate quickly. Caixa's **master database** (`caixa.sqlite`) is the source of truth: one
row per item (a message, a mail, a call, a voicemail), the people, their names, a record of every
import, and the append-only change log. The master sees every kind of data and resolves identities
across all of them, which no single collector can. Collectors hand over to it through a read-only
attachment of their own database, never by writing into each other.

**What a box looks like today:**

```
<Box name>/
  README.md        plain language: what this folder is
  index.html       start here: every person and year
  People/          <Person>/index.html, (YYYY) <Person>.html, <Source>/(date) time sender.ext
  Groups/          <Group>/  the same, for group conversations
  Mail/            <YYYY>/(YYYY-MM-DD) Sender — Subject.html  +  Attachments/
  Inbox/           drop exports here
  .caixa/          Caixa's own working files: the databases, logs, working copies
```

Photos, video and documents will be their own domain with their own tool: a later project.

## Part 2: A personal model

*This part is planned, not built. Phase 1 builds the foundation it stands on.*

The idea: a small, open AI model that runs on your own computer and becomes the **expert on one person**,
able to answer "what did Grandma say about the move to Lisbon?" the way a good archivist would: from the
records, with the sources shown.

**The decision that shapes everything: facts are retrieved and cited, never stored in the model's
weights.** A fact held in weights has no provenance, blurs similar events together, cannot say "the
record is silent on that", cannot be corrected cleanly, and can leak private data. So the model looks
things up in the box and cites the records it used, and the design follows from that:

- **Training is for skill, not for facts.** What the model learns is how to use *this* box: how to query
  its schema, to cite record IDs, to decline when the record does not say, and who the cast of characters
  is. The method is retrieval-augmented fine-tuning on question-and-answer examples generated from the
  database itself, with sealed and private items left out.
- **Citations are checked.** A deterministic verifier checks every citation the model gives against the
  database. An answer that cites something that is not there does not pass.
- **It stays current without starting over.** Each stage of the pipeline remembers the last change number
  it processed in the master's change log. Conversations are cut into sessions, a mail is one chunk, a call
  or voicemail transcript is one chunk; summaries are recomputed only where new items arrived; adapters are
  retrained now and then, gated by an evaluation.
- **It speaks as an archivist, with citations.** A first-person persona exists only if the person it is
  about turned it on.

**What Phase 1 already does for it:** stable IDs for every item and links from every item to every person
involved; an append-only change log to catch up from; a privacy level on every item; transcripts and
translations kept beside the original text, never instead of it; and local-only speech-to-text and
translation. The design reserves places in the box for the later search index and knowledge stores.

## Part 3: The harness

Most people who will use a box are not technical: the person building it, and above all the family who
inherits it years later. The interface has to be a **web browser**, ask as little of the computer as
possible, and keep working for years while its parts change.

**Built on an open harness.** Caixa's interface is a plugin for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
(`dsh web`, MIT-licensed): an open agent harness with a web interface and a plugin system. Using it means
we write the Caixa pages and the data code, not a web application and an agent runtime from scratch, and
it is also where the personal model is meant to run.

```
 browser ──► DeepSeek Harness ──► Caixa plugin ──► caixa worker ──► collectors, master database, box
           (sign-in, Host/Origin  /api/caixa/*     (Python; JSON-RPC
            checks, loopback only) owner-only       over stdio, no
                                                    network listener)
```

All data work stays in Python (`caixa worker`); the plugin only runs it and exposes owner-only routes to
the pages. The worker is never reachable except through the harness's own authentication.

**Platform independent.** There is no native app. The interface is a browser page served from your own
computer (`127.0.0.1` only), so it looks and behaves the same wherever Python and Node run: developed and
tested on Linux, with macOS as the target (it has to be, for iMessage), and other systems to follow. The
box itself is a folder: copy it to a drive, a NAS or a USB stick and it is still complete. A Docker image
is planned.

**Built to be updated.** Four decisions keep the interface replaceable and the data safe:

- **The worker's protocol is the seam.** The command line and the browser both go through one service
  layer, and the browser reaches it only through a small, documented JSON-RPC protocol. The interface can
  be rebuilt or upgraded without touching the data code, and the data code without touching the interface.
- **The harness version is pinned.** DeepSeek Harness is a young project whose plugin interfaces still
  change. Caixa pins one exact version and the plugin declares which it supports; upgrading is a deliberate
  step that follows the harness's upgrade guide, checked by tests that run the real pinned harness in a
  real browser. Caixa keeps its own copy in its own folder and never touches yours.
- **New sources need no interface work.** A collector installed as a package appears in the import wizard
  with its form and its "how to export" card.
- **Updating a box is just importing.** Importing a newer export adds only what is new, and the pages are
  redrawn; there is no "upgrade the archive" step.

**Privacy of the harness itself.** Its session logging and telemetry are switched off in Caixa's copy,
the sign-in link carries a one-time token that is never printed or logged, and a read-only mode
(`caixa worker --read-only`) already exists as the groundwork for an **heir mode**: a box opened for
reading and asking, in which nothing can be changed.

## Where the project is

Caixa is in early development. This is what exists today, and what does not.

| | Status |
| --- | --- |
| **Message collectors** (iMessage, WhatsApp, Messenger/Instagram, mail, Google Voice, voicemail) | Built and tested against synthetic exports in every format; not yet verified against real exports |
| **The box and the master database** | Built |
| **Command line** (`caixa`, and Chattr's own `chattr-cli`) | Built |
| **Browser interface**: create a box, import wizard, jobs, people, browse, settings | Built, and tested in a real browser against the real harness |
| **Chattr's own browser page** (`chattr-cli serve`) | Built |
| **Search index, personal model, the heirs' "Ask" experience** | Planned |
| **Heir mode, Docker image** | Planned (read-only worker exists) |
| **More sources** (Slack, Telegram, Google Chat, photos, documents) | Planned |
| **Windows** | Untested; `caixa serve` refuses to start there |

The known gaps of the collectors (for example, that iMessage attachments still in iCloud cannot be
fetched) are listed in [`docs/Documentation/Collector.md`](docs/Documentation/Collector.md#known-limitations).
The project's briefing, requirements and ticket history are in
[`docs/ai/Istanbul/Phase1-Collector/`](docs/ai/Istanbul/Phase1-Collector/).

## Installation

Caixa runs on your own computer; nothing is sent anywhere. It is developed and tested on Linux, and
macOS is the target for iMessage. Windows is untested (and `caixa serve` does not support it yet).

### What you need

| You need | For | Notes |
| --- | --- | --- |
| **Python 3.10 or newer** | everything | Required. Chattr's Python packages (Jinja2, vobject, phonenumbers, tqdm, python-dotenv, Pillow, pillow-heif, ffmpeg-python) are installed with it; that is the only time the network is needed. |
| **Disk space** | every import | A box keeps its own copy of photos and recordings (your exports are never changed), so allow at least the size of the exports you import, and more for a large iMessage library. |
| **ExifTool** | optional, recommended | Reads the date a photo was really taken, and writes the message date into photos that have none. Without it photos are dated by the message that carried them and nothing is written into them. Install with your package manager (`brew install exiftool`, `apt install libimage-exiftool-perl`). |
| **FFmpeg** | recommended | Files recordings (voicemail, voice notes) as `.m4a`, which every browser plays; without it they are kept in their original format. Also prepares audio for local speech-to-text. |
| **A local speech model** | optional | To transcribe voicemail: whisper.cpp's `whisper-cli` and a model file, or the `faster-whisper` package and a model folder. Caixa never downloads a model. |
| **A translation model** | optional | Any OpenAI-compatible service: one on your own computer (for example Ollama at `http://localhost:11434/v1`) or a paid one (OpenRouter, DeepSeek) with your API key. Off until you turn it on; set it up and test it in Settings. |
| **macOS "Full Disk Access"** | iMessage only | macOS lets a program read `~/Library/Messages/chat.db` only after you allow it in System Settings, Privacy & Security. Caixa opens the database read-only. |
| **Node.js 24.9 or newer, and pnpm** | the browser interface only | `caixa serve` runs DeepSeek Harness, which needs Node 24.9+. `pnpm` is installed with `npm install -g pnpm` (or `corepack enable`). The first run downloads the pinned DeepSeek Harness once. |

The command-line collectors need only Python. Everything in the table marked optional can be added
later.

### Install

From a checkout of this repository:

```bash
git clone https://github.com/tonyknight/Caixa.git
cd Caixa
python3 -m venv .venv && source .venv/bin/activate
pip install -e tools/chattr -e .
```

Both packages go in one command, **Chattr first**: Caixa depends on Chattr by name, and an
unrelated project of that name exists on PyPI, so Chattr must come from `tools/chattr`. This also
installs `chattr-cli`, Chattr's own command, which works without Caixa.

Check it worked:

```bash
caixa --version         # caixa 0.1.0
caixa collectors        # lists the six collectors (iMessage, WhatsApp, Messenger, mail, Google Voice, voicemail)
```

For the browser interface, build the plugin once, then start it:

```bash
pnpm --dir harness install && pnpm --dir harness build
caixa serve --box ~/Our\ Box
```

To work on Caixa itself, add the development tools and run the tests:

```bash
pip install -e "tools/chattr[dev]" -e ".[dev]"
python -m pytest -q          # tests use only synthetic, fictional data
python -m black --check . && python -m mypy caixa tools/chattr/src
```

**Next:** [`docs/Documentation/Collector.md`](docs/Documentation/Collector.md) explains how to use each
collector, where the data goes, and how to tell that an import worked.

## Using Caixa from the command line

Everything the browser interface does is also a command, and gives the same result:

```bash
caixa box create ~/Our\ Box --name "Our box" --owner "Your Name"
caixa collectors whatsapp                      # how to export from WhatsApp, and its options
caixa import whatsapp ~/Downloads/chat.zip --box ~/Our\ Box --preview
caixa import whatsapp ~/Downloads/chat.zip --box ~/Our\ Box
caixa people unresolved --box ~/Our\ Box        # numbers and names no one is called yet
caixa people link WhatsApp "Ana Costa" "Ana" --box ~/Our\ Box
```

Set `CAIXA_BOX` (or run inside the box) to leave out `--box`. Drop exports into the box's `Inbox/`
folder if you prefer; it is listed in the interface.

`caixa worker [--box PATH] [--read-only]` serves the same operations over standard input and
output as JSON-RPC 2.0, one JSON object per line. That is how the browser interface talks to
Python; it is not a network service. Its methods (`box.*`, `collectors.list`, `import.*`,
`jobs.*`, `people.*`, `browse.*`, `files.list`, `inbox.list`, `settings.*`), notifications
(`job.progress`, `job.finished`, `inbox.changed`) and error codes are described at the top of
[`caixa/worker.py`](caixa/worker.py). With `--read-only`, every method that would change the box is
refused, and nothing is written.

## The browser interface

The browser interface is a plugin for DeepSeek Harness, kept in [`harness/`](harness/). It runs
`caixa worker` and adds the Caixa pages to `dsh web`. See [`harness/README.md`](harness/README.md)
for how it fits together, the pinned DeepSeek Harness version and how to develop it. It needs Node
24.9 or newer; everything else, including `chattr-cli serve`, needs only Python.

```bash
pnpm --dir harness install && pnpm --dir harness build   # once, from a checkout
caixa serve --box ~/Our\ Box     # starts everything and opens your browser
caixa serve --stop               # stops it
```

`caixa serve` checks Node first and says plainly what is missing. It keeps DeepSeek Harness in Caixa's
own folder (`~/.local/share/caixa`, or `~/Library/Application Support/Caixa` on a Mac; never your own
`~/.dsh`), installs the pinned version there on first run (that needs the network once), turns off
its session logs and telemetry, and listens on `127.0.0.1` only. The link it opens carries a sign-in
token; it is never printed (unless you pass `--no-browser`) or logged. If you close the terminal
abruptly, the next `caixa serve` finds the running instance again instead of starting another.

**What you should see.** The browser opens straight onto the Caixa page, in a window called Caixa:
create or open a box, then Import, Jobs, People, Browse and Settings. There is no sign-in prompt and no
welcome notice. Caixa runs inside DeepSeek Harness, and two of the harness's own controls are still in
the left-hand column, **New Session** and the **Workspaces** list (its chat); they cannot be switched off
yet without breaking it. They are not needed for anything Caixa does today. The harness's plugin browser
and automation list are switched off.

**Picking up where you left off.** Caixa remembers the box you had open, the section you were in and
an import you had set up but not started, in its own folder (never inside a box). Stop it and start it
again and you land where you were; `caixa serve` reopens your last box (or pass `--box`).
**When something does not work**, an import that finds nothing now says what it saw and what it
wanted, and `caixa doctor` (or **Create a report** in the browser) makes a report you can paste, with
no names, numbers or messages in it. Details are in
[`docs/Documentation/Collector.md`](docs/Documentation/Collector.md#when-something-does-not-work).

**If an earlier `caixa serve` showed a "Preview Notice" you could not dismiss** ("The
acknowledgement could not be saved"), update Caixa and run `caixa serve --stop`, then `caixa serve`
again. The first run after updating replaces the harness with the exact build Caixa is tested with
(about a minute, with the network). The cause and how it is pinned are in
[`caixa/data/dsh/README.md`](caixa/data/dsh/README.md).

## Chattr and its mirror

Chattr lives in `tools/chattr/` and is mirrored to its own repository by
`.github/workflows/mirror-chattr.yml` (a fast-forward of `git subtree split`, never forced). The
workflow needs a write token for Chattr's repository, stored as the repository secret
`CHATTR_MIRROR_TOKEN`. The maintainer creates it once; the steps are in
[`tools/mirror/README.md`](tools/mirror/README.md).

## Contributing

Work is organized into release trains and projects with
[Bora](https://github.com/tonyknight/Bora). Start with [`AGENTS.md`](AGENTS.md) and the
project's briefing and requirements. Tests use synthetic data only: never commit real personal
data.

## License

Caixa is free software, licensed under the **GNU General Public License, version 3 or later
(GPL-3.0-or-later)**. See [`LICENSE`](LICENSE) for the full text and [`NOTICE`](NOTICE) for
copyright and included components.
