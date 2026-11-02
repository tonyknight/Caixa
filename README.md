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
