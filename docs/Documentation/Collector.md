# Collectors

A **collector** turns one kind of export (a WhatsApp chat, an iMessage database, a Gmail download…)
into Caixa's archival form: pages you can read in any web browser, the photos and recordings they
refer to, and a database that keeps it all findable. This document explains how to use each collector,
where everything ends up, how the input is transformed (attachments especially), and how to tell that an
import worked.

It assumes Caixa is installed (see [Installation](../../README.md#installation)).

- [The short version](#the-short-version)
- [Before you start](#before-you-start)
- [The six collectors](#the-six-collectors): [WhatsApp](#whatsapp) · [iMessage](#imessage) ·
  [Messenger and Instagram](#messenger-and-instagram) · [Mail](#mail) · [Google Voice](#google-voice) ·
  [iPhone voicemail](#iphone-voicemail)
- [Naming the people](#naming-the-people)
- [Where the data is stored](#where-the-data-is-stored)
- [How the input is transformed](#how-the-input-is-transformed)
- [Attachments in detail](#attachments-in-detail)
- [How to measure success](#how-to-measure-success)
- [Trying the collectors with the synthetic data](#trying-the-collectors-with-the-synthetic-data)
- [Known limitations](#known-limitations)

## The short version

```bash
caixa box create ~/Our\ Box --name "Our box" --owner "Your Name"      # once
caixa collectors whatsapp                                             # how to export, and the options
caixa import whatsapp ~/Downloads/chat.zip --box ~/Our\ Box --preview # a dry run: counts, dates, people
caixa import whatsapp ~/Downloads/chat.zip --box ~/Our\ Box           # the real import
caixa people unresolved --box ~/Our\ Box                              # who is still only a number
```

Every step is also available in the browser (`caixa serve`): the **Import** section is a wizard that
does the same things in the same order. A browser import and a command-line import of the same export
give the same database rows, the same files and byte-identical pages.

Three things hold for every collector:

- **Your exports are never changed.** Caixa reads them and writes only inside the box. (Zips are
  unpacked into the box's own working folder first, safely: a zip containing a path that would escape
  that folder is refused.)
- **Running an import again is safe.** Every item has a stable identity, so a second run of the same
  export adds nothing and changes nothing. Import a newer export of the same chat and only what is new
  arrives.
- **Nothing leaves your computer.** There is no network access in a collector. Translation and
  speech-to-text are off by default and only ever talk to a model on your own computer.

## Before you start

**Make a box.** A box is a folder; Caixa creates it and the folders inside it.

```bash
caixa box create ~/Our\ Box --name "Our box" --owner "Your Name"
```

`--owner` matters: it says who "me" is, so your own messages are shown as sent by you. Set `CAIXA_BOX`
to the box's path (or run commands from inside the box) and you can leave out `--box`.

**Get the export.** Each collector below says how. Keep the export where it is; Caixa copies what it
needs.

**Point Caixa at it.** The source can be the `.zip` you downloaded, the folder you unzipped it into, or
(where it makes sense) the single file. Alternatively, drop the export into the box's `Inbox/` folder
and choose it from the list in the browser.

**Preview first.** `--preview` (or the wizard's preview step) reads the export in a scratch area and
reports what an import would bring in, without touching the box or the source:

```
$ caixa import whatsapp chat.zip --box ~/Our\ Box --preview
7 items in 1 conversation, 2024-03-01 to 2024-03-02
People: Ana Costa
Not yet named: Ana Costa
```

**Options.** Every collector has options; list them with `caixa collectors <id>`. Give one with
`--option name=value` (repeat for several). Two are common to all:

| Option | Meaning |
| --- | --- |
| `contacts` | Path to a vCard (`.vcf`) export of your address book. Used to put names to phone numbers and email addresses, so far fewer people are left unnamed. |
| `owner` | Who "me" is. Empty means the owner of the box, which is almost always what you want. |

## The six collectors

The id in brackets is what you give to `caixa import` and `caixa collectors`.

### WhatsApp

*(`whatsapp`; takes a file, a folder or a .zip)*

**Export.** In WhatsApp, open a chat, tap the contact or group name, then **Export chat**, and choose
**Attach Media** to keep photos and voice notes. Save the `.zip` it makes. Each chat is exported on its
own: repeat for each chat you want.

**Import.**

```bash
caixa import whatsapp ~/Downloads/WhatsApp\ Chat\ with\ Ana.zip --box ~/Our\ Box
caixa import whatsapp ~/Downloads/all-my-chats/ --box ~/Our\ Box    # a folder holding several chats
```

A folder is searched for every `_chat.txt` (and every `WhatsApp Chat….txt`), so you can unzip many chats
into one folder and import them together.

**What you get.** One page per year for each person (`Messages/Ana Costa/(2024) Ana Costa.html`), a
group's pages under `Messages/Groups/<group name>/`, and the chat's photos, videos and voice notes in
that person's `Attachments` folder ([details](#attachments-in-detail)).

**Good to know.** A WhatsApp export carries no time zone and sometimes an ambiguous date format (is
`03/04` the third of April or the fourth of March?). Caixa decides from the whole file and notes it when it
had to guess ("reading them month-first"); the times are kept exactly as exported and marked as having
an assumed zone.

### iMessage

*(`imessage`; takes the `chat.db` database file, or a folder containing it)*

**Export.** There is nothing to export: iMessage lives in `~/Library/Messages/chat.db` on your Mac. macOS
lets a program read it only after you give that program **Full Disk Access** (System Settings, Privacy &
Security). Caixa opens the database read-only and never changes it. You can also copy `chat.db` (and the
`Attachments` folder next to it) somewhere and import the copy.

**Import.**

```bash
caixa import imessage ~/Library/Messages/chat.db --box ~/Our\ Box --preview
caixa import imessage ~/Library/Messages/chat.db --box ~/Our\ Box \
    --option contacts=$HOME/contacts.vcf --option region=PT
```

**Options.**

| Option | Default | Meaning |
| --- | --- | --- |
| `region` | `US` | Two-letter country code, used to read local phone numbers. |
| `spam_mode` | `aggressive` | `aggressive`, `conservative` or `disabled`: how much machine-sent noise (RCS, unknown senders, system notices) to **tag**. Nothing is ever thrown away. |
| `workers` | `4` | How many parts of the database are read at once. |
| `limit` | `0` | Read only this many messages (0 reads everything). Useful for a first try on a huge library. |
| `attachment_root` | *(empty)* | Where macOS keeps attachments. Empty uses the `Attachments` folder next to `chat.db` when there is one. |

**What you get.** Messages with their tapback reactions, one page per year per person (or group). iMessage has no names of its own, only phone numbers and email addresses, so give `contacts` or
name people afterwards ([Naming the people](#naming-the-people)).

**Good to know.** Message text that macOS stores only in its binary form (`attributedBody`) is decoded.
**The files attached to iMessages are recorded but not yet copied into the box**; see
[Known limitations](#known-limitations).

For a closer look at a database before importing, Chattr has its own tools: `chattr-cli chats <chat.db>`
lists the conversations, and `chattr-cli doctor <chat.db>` checks the database and the spam filter.

### Messenger and Instagram

*(`messenger`; takes a file, a folder or a .zip. One collector handles both services.)*

**Export.** In Meta's Accounts Center choose **Your information and permissions**, then **Download your
information**. Pick Messenger and/or Instagram messages, set the format to **JSON**, and download. A
single download can hold both services.

**Import.**

```bash
caixa import messenger ~/Downloads/facebook-export.zip --box ~/Our\ Box
caixa import messenger .../inbox/joaocosta_1234567890/message_1.json --box ~/Our\ Box   # one conversation
```

Pointed at a zip or a folder, Caixa finds every conversation (`message_1.json` in each thread folder) and
imports Messenger and Instagram threads together; a thread is called Instagram when its path says so.
Pointed at one `message_1.json` it reads that whole conversation, including `message_2.json` and the
following files of a long thread.

**Options.** `service` (`auto`, `messenger` or `instagram`) overrides the guess; leave it on `auto`.

**What you get.** Pages per person and year, reactions, shared links, and the photos of the thread in the
person's `Attachments` folder.

**Good to know.** Meta writes every text twice-encoded (an accented letter arrives as two odd
characters) and lists messages newest first. Caixa repairs the encoding and reads the thread oldest
first, so names and text come out right.

### Mail

*(`mail`; takes an `.mbox` file, a folder or a .zip)*

**Export.** For Gmail, go to Google Takeout (takeout.google.com), choose only **Mail**, and download. Other
mail programs that export `.mbox` files work too.

**Import.**

```bash
caixa import mail ~/Downloads/takeout-20250101.zip --box ~/Our\ Box
caixa import mail "~/Takeout/Mail/All mail Including Spam and Trash.mbox" --box ~/Our\ Box
```

**What you get.** One page per mail conversation under `Mail/<year>/`, named by date, sender and subject
(`Mail/2019/(2019-11-02) João Costa — Fotos de São Martinho.html`). Attachments are taken out of the mail
and kept in `Mail/Attachments/`, linked from the page.

### Google Voice

*(`googlevoice`; takes a folder or a .zip)*

**Export.** In Google Takeout choose only **Voice** and download. The calls, texts and voicemail are in
`Takeout/Voice/Calls`.

**Import.**

```bash
caixa import googlevoice ~/Downloads/takeout-voice.zip --box ~/Our\ Box
caixa import googlevoice ~/Takeout/Voice/Calls --box ~/Our\ Box
```

**What you get.** Calls (placed, received, missed), texts and voicemail as items on the person's pages;
voicemail audio is copied into `Audio/GoogleVoice/`.

### iPhone voicemail

*(`voicemail`; takes a folder or a .zip)*

**Export.** Voicemail is not something an iPhone lets you browse, so copy it out of a Finder or iTunes
backup: the folder holds `voicemail.db` and the numbered `.amr` audio files (in a backup they are under
`Library/Voicemail`). Point Caixa at that folder.

**Import.**

```bash
caixa import voicemail ~/iphone-backup/Voicemail --box ~/Our\ Box
caixa import voicemail ~/iphone-backup/Voicemail --box ~/Our\ Box \
    --option transcribe=true --option model=$HOME/models/ggml-small.bin --option language=pt
```

**Options.**

| Option | Default | Meaning |
| --- | --- | --- |
| `transcribe` | `false` | Turn each voicemail into text with a speech model on this computer. |
| `model` | *(empty)* | Path to a local speech model (a whisper.cpp model file, or a faster-whisper model folder). Caixa never downloads one. |
| `language` | *(empty)* | A language code such as `en` or `pt`; empty lets the model detect it. |

**What you get.** Each voicemail as an item (who, when, how long), its audio in `Audio/Voicemail/`, and with
transcription on, its text beside the player on the page.

**Good to know.** Transcription needs `ffmpeg` and a model (see [Installation](../../README.md#installation)). It
runs with the network blocked for the process, so a speech engine that tried to fetch something would
fail rather than quietly phone home.

## Naming the people

Exports identify people by whatever the service uses: a phone number, an email address, a username, or a
display name. Until a handle is **named**, its pages go in a folder called after the handle
(`Messages/+15550101/…`). Naming a handle links it to a person, so **all of a person's messages, across
every app, live together** under that person's name.

There are three ways to name people, and they combine:

1. **A contacts file.** `--option contacts=$HOME/contacts.vcf` on any import. Phone numbers and emails in the
   export are matched against it.
2. **By hand**, one handle at a time:

   ```bash
   caixa people unresolved --box ~/Our\ Box
   caixa people link iMessage "+15550101" "Ana Costa" --box ~/Our\ Box
   ```

   Linking a **phone number or an email** names that address on every service; a **name or username** is
   linked for its own service only. Link to a name that is not in the box yet and a new person is made.
   If the address already names someone else the command says so; add `--move` to give it to the new person
   instead.
3. **In the browser:** the **People** section lists the unnamed handles (busiest first), offers the people
   already in the box as you type, and lets you rename a person or merge two who are really one.

Naming (or renaming, or merging) re-draws the affected pages: they move to the person's folder and the old
page is removed. The files already filed under the old name stay where they are and the new pages
link to them there.

## Where the data is stored

Everything is inside the box folder.

```
Our Box/
  README.md                       plain-language note: what this folder is
  index.html                      start here: every person and year, with counts
  Messages/
    Ana Costa/
      (2024) Ana Costa.html       one page per year, all services together
      Attachments/
        (2024-03-01) 14-05-09 Ana Costa 1.png
    Groups/Costa Family/(2024) Costa Family.html
    +15550101/(2023) +15550101.html     a handle nobody has named yet
    .attachments.json             remembers which file went where (see below)
  Mail/
    2019/(2019-11-02) João Costa — Fotos de São Martinho.html
    Attachments/f5/f5293be8….png        mail attachments, filed by content
  Audio/
    Voicemail/00/00e9f1b5….amr          voicemail recordings, filed by content
    GoogleVoice/2f/2f5b4d12….mp3        Google Voice recordings, filed by content
  Inbox/                          drop exports here to find them in the browser
  People/                         for notes about people
  .caixa/                         Caixa's own working files (below)
```

**Everything above `.caixa/` is ordinary files** (HTML, images, audio). Open `index.html` in any web
browser, with or without Caixa, now or in fifty years. Each page also carries its own data, so it can be
read by a program as well as a person.

**Inside `.caixa/`:**

| Path | What it is |
| --- | --- |
| `caixa.sqlite` | The **master database**: one row per item (a message, a mail, a call, a voicemail), the people, their names (aliases), a record of every import, and an append-only **change log**. Each item says which page and anchor show it (`Messages/Ana Costa/(2024) Ana Costa.html#m-…`) and has a privacy level (`private` by default). |
| `work/chattr/Database/chattr.sqlite` | Chattr's **message archive**: every conversation, handle, message, attachment (original name, content hash, mime type, where it was filed) and reaction. This is what the pages are drawn from. |
| `work/chattr/aliases.json` | The box's names, exported for Chattr each time (rewritten on every import). |
| `work/imports/` | Zips, unpacked once. |
| `jobs.sqlite` | The record of imports run from the browser or command line: status, progress, result. |
| `logs/job-N.log` | What each import printed, and the full error if it failed. |
| `box.yaml` | The box's name and settings (written as JSON, which is valid YAML). |

**What is safe to delete.** Your original exports are yours to keep or delete; the box does not need them
once imported. Do not edit `.caixa/` by hand.

**Keeping a box.** A box is a folder: copy it to a drive to back it up. The pages and files are complete
without `.caixa/`, which is what lets Caixa and the collectors be replaced without losing the archive.

## How the input is transformed

Every collector follows the same steps:

1. **Read** the export into a common shape: conversations, people (handles), messages with their time,
   attachments and reactions. This is the only part that differs between services.
2. **File the attachments** (see [Attachments in detail](#attachments-in-detail)).
3. **Store** the messages in Chattr's archive under a **stable identity**: an ID built from the service's
   own message ID where the export has one, and otherwise from the conversation, the time, the sender and
   the text, so the same message always gets the same ID.
4. **Match people**: handles are matched against the box's names and the contacts file; your own messages
   are marked as yours.
5. **Draw the pages**: `Messages/<Person>/(YYYY) <Person>.html` and `Mail/<year>/…`, plus `index.html`.
6. **Update the master database**, recording which page shows each item.

What follows from that:

- **Dates first.** Every item has an exact time. Where the export states a zone the time is stored in UTC
  with that offset (and shown in the local time of the message); WhatsApp has no zone, so its times are
  stored as written and marked as assumed. Pages are named by year, photos and mails by date.
- **Idempotent.** An item that is already in the box is recognised by its ID and its content hash. Same
  content: nothing happens. Changed content (an edited message): the item is updated and its version goes
  up. A message that is new: inserted. The master database's change log records each of these, and
  records *nothing* for an unchanged item, which is why a repeat import shows `0 new, 0 changed`.
- **Nothing is discarded.** Spam filtering tags; it does not delete. Reactions are kept, and each source
  keeps what its export contains (mail keeps which message replies to which). Odd items (system notices,
  calls, voicemail) have their own types (`text`, `media`, `call`, `voicemail`, `email`, `system`).
- **Text is repaired, not rewritten.** Meta's doubled encoding is undone; iMessage's binary text is
  decoded; WhatsApp's multi-line messages are put back together. The wording is untouched.
- **Translation and transcripts** are stored beside the original text, never instead of it, and only when
  you turn them on.

## Attachments in detail

Attachments are where a messaging export is hardest to use: the message points at a file by a name that
means nothing outside the app (`00000012-PHOTO-2024-03-01-14-05-09.png`, `IMG_0001.PNG`, a number in a
mail's MIME structure). Caixa gives every file a **durable, dated name**, puts it next to the person it
belongs to, and makes the page link to it.

### Chat attachments (WhatsApp, Messenger, Instagram)

Each file is **copied** (the original stays where it is) into the person's `Attachments` folder, or the
group's, and renamed:

```
Messages/<Person>/Attachments/(YYYY-MM-DD) HH-MM-SS <sender> <n>.<extension>
Messages/Groups/<Group name>/Attachments/…
```

For example `Messages/Ana Costa/Attachments/(2024-03-01) 14-05-09 Ana Costa 1.png`. The pieces:

- **Date and time.** The date the photo or video was *taken*, when the file records one and ExifTool is
  installed. Otherwise the time of the message that carried it. (A photo sent a week after it was taken
  is filed under the day it was taken.)
- **Sender.** Who sent it, made safe for a file name (characters such as `/ : * ? "` become `-`).
- **`<n>`.** A number starting at 1, so two files with the same second and sender never collide. Numbers
  are assigned in time order, so they come out the same every run.
- **Extension.** Kept as it was, in lower case.

Files are processed in a fixed order, so repeating an import gives the same names. A small file
`Messages/.attachments.json` remembers each filed name and the content hash of the original; on a repeat
import a file that is already there under its name is reused, never copied again, and a file the box does
not recognise is never overwritten.

**Dates inside the file.** If ExifTool is installed and a photo, picture or similar has no capture date,
Caixa writes the message's date into the *copy* (the standard `DateTimeOriginal` field) so the date
travels with the file wherever it goes. The original is never touched. Without ExifTool the copy is made
unchanged.

**What is not changed.** Caixa's collectors copy files as they are. Chattr can convert HEIC, PNG and WebP
pictures to JPEG and Apple's CAF audio to AAC while archiving, but that conversion is **off** in Caixa: a
photo arrives in the format it was sent in. (A file that cannot be copied is reported in the job's log and
skipped; it never stops the import.) Apple's proprietary "plugin payload" attachments are skipped as not
suitable for archiving.

### Mail attachments

Attachments are pulled out of the mail itself (they exist only inside the mailbox) and stored **by
content**:

```
Mail/Attachments/<first two hex digits of the SHA-256>/<full SHA-256>.<extension>
```

The same file attached to ten mails is stored once. The mail's page shows the attachment's original
name and links to the stored file. Because the name is the file's own fingerprint, nothing can collide
and a repeat import writes nothing new.

### Voicemail and Google Voice recordings

Recordings are stored by content in the same way:

```
Audio/Voicemail/<xx>/<sha256>.amr        iPhone voicemail
Audio/GoogleVoice/<xx>/<sha256>.mp3      Google Voice voicemail
```

The item records the recording's duration and, if you turned transcription on, its transcript. Audio is
not converted.

### iMessage attachments

The database records each attachment (original name, type, size, a fingerprint), and the page lists it,
but **the files are not copied into the box yet**; the page says "file not in this archive" beside it.
See [Known limitations](#known-limitations).

### How pages link to files

Pages use ordinary relative links (`Attachments/(2024-03-01) 14-05-09 Ana Costa 1.png`), so the box keeps
working if you move or copy the folder. A photo is shown inline, audio and video get a player, and any
other file is a link. If the file is not in the box the page says so rather than showing a broken link.

### Summary

| Source | Where the files go | How they are named | Converted? |
| --- | --- | --- | --- |
| WhatsApp | `Messages/<Person>/Attachments/` | `(date) time sender n.ext` | no |
| Messenger / Instagram | `Messages/<Person>/Attachments/` | `(date) time sender n.ext` | no |
| Mail | `Mail/Attachments/<xx>/` | content fingerprint | no |
| Google Voice | `Audio/GoogleVoice/<xx>/` | content fingerprint | no |
| iPhone voicemail | `Audio/Voicemail/<xx>/` | content fingerprint | no |
| iMessage | *(recorded; not copied yet)* | — | — |

## How to measure success

An import has **succeeded** when four things are true: it ran without error, it brought in about as much
as the export holds, nothing was lost on the way, and you can find and read what it brought in. Work down
this list; the first three steps are quick.

### 1. It ran, and said what it did

The command ends with a line of counts:

```
$ caixa import whatsapp chat.zip --box ~/Our\ Box
7 new, 0 changed, 0 unchanged; 1 page written.
1 handle still unnamed: WhatsApp: Ana Costa
Name them with 'caixa people link'.
```

Exit status 0 means it finished; an error is printed in plain words with exit status 1 (a missing file,
an empty folder, a wrong kind of file). In the browser the same result appears as the report at the end of
the wizard and as a toast. The record of every run is kept: `caixa jobs --box ~/Our\ Box`, or the **Jobs**
section, which also shows each job's log.

*Reading the counts.* **new** is what this import added; **changed** is items that already existed but
differ; **unchanged** counts items the box already had, **across the whole box**, not only this
source (a box that already holds 14 items from WhatsApp and iMessage and then receives 5 from Messenger
reports "5 new, 0 changed, 14 unchanged").

### 2. It brought in about what the export holds

Compare the **preview** with an independent count of the source. The preview and the real run should
agree exactly (same reader, same rules):

| Source | A quick independent count |
| --- | --- |
| Mail | `grep -c '^From ' file.mbox` is the number of mails (fixture: 4, preview: 4). |
| iMessage | `chattr-cli chats chat.db` lists conversations; `chattr-cli doctor chat.db` reports the database and how many messages the spam filter tags. |
| WhatsApp | Roughly the number of lines that begin with a date. System lines, multi-line messages and encryption notices make an exact match unlikely, so trust preview = run and check the first and last dates. |
| Messenger / Instagram | Each thread's `message_N.json` files hold a `"messages"` array; the preview's conversation count should equal the number of thread folders. |
| Google Voice | One item per `.html` file in `Calls/`. |
| Voicemail | One item per voicemail in `voicemail.db`, each with its `.amr` file. |

Also check the preview's **date range** against what you know ("from 2016 to last week"), and its
**people** against who you expect.

### 3. Nothing was lost

**It is safe to repeat.** Run the same import again. It must report `0 new, 0 changed`:

```
$ caixa import whatsapp chat.zip --box ~/Our\ Box
0 new, 0 changed, 31 unchanged; 12 pages written.
```

If a repeat adds items, something about the export is unstable (please report it).

**The box adds up.** `caixa box status` shows the box's totals by kind of item:

```
$ caixa box status --box ~/Our\ Box
Doc box  (/home/me/Our Box)
31 items, 1 person; owner Maria Costa
  call: 3
  email: 4
  media: 3
  system: 1
  text: 17
  voicemail: 3
```

The total must equal the sum of the previews' item counts. "People" counts only people who exist: handles
nobody has named yet are not people, which is why the count is low at first.

**Every attachment is a file in the box.** The database lists every attachment it saw; this script checks
each one against the box (it needs only Python):

```python
# check_attachments.py: python check_attachments.py ~/Our\ Box
import sqlite3, sys
from pathlib import Path

box = Path(sys.argv[1]).expanduser()
roots = {   # where each source's files live; the stored path is relative to this folder
    "WhatsApp": "Messages", "Messenger": "Messages", "Instagram": "Messages",
    "Mail": "Mail/Attachments", "Voicemail": "Audio/Voicemail", "Google Voice": "Audio/GoogleVoice",
}
db = sqlite3.connect(f"file:{box}/.caixa/work/chattr/Database/chattr.sqlite?mode=ro", uri=True)
rows = db.execute(
    "SELECT c.service, a.original_filename, a.storage_path FROM attachments a "
    "JOIN messages m ON m.id = a.message_id JOIN conversations c ON c.id = m.conversation_id"
).fetchall()
good = missing = unsaved = 0
for service, name, stored in rows:
    if not stored:
        unsaved += 1
        print(f"  not copied into the box: {service}: {name}")
    elif (box / roots.get(service, "Messages") / stored).is_file():
        good += 1
    else:
        missing += 1
        print(f"  MISSING: {service}: {stored}")
print(f"{good} attachments in the box, {unsaved} recorded but not copied, {missing} missing")
sys.exit(1 if missing else 0)
```

Success is **no `MISSING` lines**. Lines saying "not copied into the box" are the iMessage limitation
described below. With the synthetic data the result is `6 attachments in the box, 3 recorded but not
copied, 0 missing`.

**Failures are in the log.** Open `.caixa/logs/job-N.log` (or the job's log in the **Jobs** section). A file
that could not be copied is named there with the reason. For the chat sources (WhatsApp, Messenger,
Instagram) the log ends with attachment counts (`Successfully processed`, `Failed processing`, `Skipped
processing`); `Failed processing` should be 0.

**The source is untouched.** Caixa never writes to your export. If you want proof, take a checksum of the
export before and after (`shasum -a 256 chat.zip`).

### 4. You can find and read it

- Open `index.html` in a web browser: every person and year should be there, with message counts.
- Open a page you know: the first and last messages, a photo (it should display, not show "file not in
  this archive"), a voicemail (it should play), a mail with an attachment (the link should open).
- In the browser interface, the **Browse** section shows the same pages inside Caixa.
- **How many people are still just numbers?** `caixa people unresolved` lists them. A good result is
  *only* handles you do not care about (a short code, an unknown number). Import with `contacts=` and name
  the rest until the list is short.

### The checklist

| Check | How | Success |
| --- | --- | --- |
| It finished | exit status, `caixa jobs` | status `done`, no error |
| Right size | `--preview` against your count | preview = run; dates and people as expected |
| Repeatable | run the import again | `0 new, 0 changed` |
| Adds up | `caixa box status` | total = sum of the previews |
| Attachments present | the script above | no `MISSING` lines |
| No failures | the job log | `Failed processing: 0` |
| Readable | `index.html` and a few pages | text, photos and recordings all show |
| People named | `caixa people unresolved` | only handles you do not mind |

### Looking deeper (optional)

The databases are plain SQLite; use `sqlite3`, "DB Browser for SQLite", or Python. Some useful questions
(on `~/Our Box/.caixa/caixa.sqlite`, the master database):

```sql
-- what is in the box, by source and kind
SELECT service, type, COUNT(*) FROM items GROUP BY 1, 2;

-- every import, and what it did
SELECT id, collector, status, inserted, updated, unchanged, started_at FROM imports;

-- the change log: one 'insert' per new item, 'update' for changed ones, 'link' when a person was linked
SELECT operation, COUNT(*) FROM change_log GROUP BY 1;

-- which page shows a given item
SELECT file_path, anchor FROM items WHERE id = '…';
```

and on `.caixa/work/chattr/Database/chattr.sqlite`:

```sql
-- attachments that were not filed in the box (expected: iMessage only)
SELECT c.service, a.original_filename
FROM attachments a JOIN messages m ON m.id = a.message_id JOIN conversations c ON c.id = m.conversation_id
WHERE a.storage_path IS NULL;
```

## Trying the collectors with the synthetic data

The repository includes a fictional family's exports in every supported format (no real data), the same
ones the tests use. Build them and import all six into a throwaway box:

```bash
cd Caixa     # the repository
python - <<'EOF'
import sys, pathlib
sys.path.insert(0, 'tools/chattr/tests')
from fixtures import build_all
for name, path in build_all(pathlib.Path('/tmp/family')).paths.items():
    print(f'{name:18} {path}')
EOF

caixa box create /tmp/trybox --name "Try box" --owner "Maria Costa"
caixa import whatsapp    "/tmp/family/whatsapp/WhatsApp Chat - Ana Costa/_chat.txt" --box /tmp/trybox
caixa import imessage    /tmp/family/imessage/chat.db                               --box /tmp/trybox
caixa import messenger   /tmp/family/meta/meta-export/your_facebook_activity/messages/inbox/joaocosta_1234567890/message_1.json --box /tmp/trybox
caixa import mail        "/tmp/family/gmail/Takeout/Mail/All mail Including Spam and Trash.mbox" --box /tmp/trybox
caixa import googlevoice /tmp/family/google-voice/Takeout/Voice/Calls               --box /tmp/trybox
caixa import voicemail   /tmp/family/iphone/Voicemail                              --box /tmp/trybox
```

What each should bring in:

| Collector | Items | Notes |
| --- | ---: | --- |
| `whatsapp` | 7 | one photo; dates 2024-03-01 to 2024-03-02 |
| `imessage` | 7 | three attachments, recorded not copied |
| `messenger` (the one thread above) | 5 | a Messenger conversation with one photo |
| `mail` | 4 | one with a photo attachment |
| `googlevoice` | 6 | calls, texts, one voicemail recording |
| `voicemail` | 2 | two `.amr` recordings |

Point `messenger` at the whole Meta export folder instead (`/tmp/family/meta/meta-export`) and it
imports the Instagram thread as well: 7 items, in 2 conversations.

The six imports above together give **31 items**: `call: 3, email: 4, media: 3, system: 1, text: 17,
voicemail: 3`. Then open `/tmp/trybox/index.html`, run `caixa people unresolved --box /tmp/trybox`, name
one with `caixa people link`, and watch its pages move. Run any import a second time and it reports
`0 new, 0 changed`.

## Known limitations

These are known, and honest, as of this writing:

- **iMessage attachments are recorded but not copied.** The photos and files attached to iMessages
  appear in the database and on the page as "file not in this archive". The other five collectors copy
  or extract their files. (Chattr's older JSON export for iMessage can copy them with
  `chattr-cli convert imessage … --json --attachments-dir DIR`, outside the box.)
- **Real exports are not yet verified.** Every collector was built and tested against the synthetic
  fixtures, which follow each platform's documented format. A real export that does not read correctly
  is a bug worth reporting, with the first few lines of the file (and no private content).
- **No real speech model was run.** Transcription works through a stand-in in the tests and is wired
  to whisper.cpp and faster-whisper; it has not been tried with a real model.
- **WhatsApp has no time zone** in its exports, so its times are shown as exported.
- **ExifTool is optional**, but without it photos are filed by message time rather than capture time, and
  nothing is written into them.
- **The "unchanged" count covers the whole box**, so it can look larger than the export you just
  imported.
- **Unnamed handles get a folder named after the number** until you name them; renaming moves the
  pages but not the files already filed.
- **The privacy level** (`private`, `family`, `public`) is stored on every item and in the Settings, but
  nothing yet acts on it.
- **Windows** has not been tried; `caixa serve` refuses to start there.
