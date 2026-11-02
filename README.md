# Caixa

> *Caixa*: Portuguese for **box**.

A generation ago, a person's life survived as physical things: photo albums, letters, tapes,
paper records. Today a life is born digital. It lives in phones, cloud accounts and messaging
apps, and it can vanish with a lost device, a closed account, or a death nobody planned for.
Even carefully exported data becomes a pile that the next generation has to dig through to
understand their own family history.

**Caixa is an open-source digital-legacy system.** It turns a person's scattered digital life
into one durable box that their family can actually use.

## The three parts

1. **Collectors** transform personal data into an archival form. Most data arrives as
   takeout-style exports (Google, Facebook/Instagram, WhatsApp, Apple, Slack and others),
   organized for each platform's database rather than for people. Collectors rename, date,
   fix and organize that data, **dates first, people second**:
   - every transformed file is named `(YYYY-MM-DD) name.ext`;
   - wherever it makes sense, data is grouped by person, so all of your messages with one
     person, across every app, live together.
2. **A personal model**: a small, open, local AI that becomes the expert on the person. It
   answers from the archive and cites the original messages, photos and documents.
3. **A harness** runs the box locally in a web browser, so someone who inherits it can ask
   questions, read and browse.

## The box

```
<Box name>/
  Messages/  Mail/  Photos/  Documents/  People/  …   ← your data, in open formats, readable without Caixa
  .caixa/                                             ← Caixa's own working files (database, model, harness)
```

**Caixa is an enabler, not a requirement.** Everything at the top level of a box is ordinary
files: HTML pages, images with embedded dates, documents. You can open them in a web browser or
file manager, with or without Caixa.

## Installation

Caixa runs on your own computer; nothing is sent anywhere. It is developed and tested on Linux, and
macOS is the target for iMessage. Windows is untested (and `caixa serve` does not support it yet).

### What you need

| You need | For | Notes |
| --- | --- | --- |
| **Python 3.10 or newer** | everything | Required. Chattr's Python packages (Jinja2, vobject, phonenumbers, tqdm, python-dotenv, Pillow, pillow-heif, ffmpeg-python) are installed with it; that is the only time the network is needed. |
| **Disk space** | every import | A box keeps its own copy of photos and recordings (your exports are never changed), so allow at least the size of the exports you import, and more for a large iMessage library. |
| **ExifTool** | optional, recommended | Reads the date a photo was really taken, and writes the message date into photos that have none. Without it photos are dated by the message that carried them and nothing is written into them. Install with your package manager (`brew install exiftool`, `apt install libimage-exiftool-perl`). |
| **FFmpeg** | optional | Only for local speech-to-text (it prepares the audio) and for the optional format conversion, which is off. |
| **A local speech model** | optional | To transcribe voicemail: whisper.cpp's `whisper-cli` and a model file, or the `faster-whisper` package and a model folder. Caixa never downloads a model. |
| **A local translation model** | optional | Any OpenAI-compatible service on your own computer (for example Ollama at `http://localhost:11434/v1`). Off until you turn it on. |
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

## Status

Early development. The current work is the message collector and Caixa's data architecture. See
[`docs/ai/Istanbul/Phase1-Collector/`](docs/ai/Istanbul/Phase1-Collector/) for the project
briefing, requirements and status.

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
