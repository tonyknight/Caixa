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
- **Nothing leaves your computer unless you say so.** Reading an export uses no network at all.
  Speech-to-text runs on your own computer. Translation is off by default; turned on, it talks only to
  the address you give, and an address on the internet (a paid service) needs a second, explicit yes
  because the text being translated is sent there. See [Translation](#translation).

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
caixa import whatsapp ~/Downloads/all-my-chats/ --box ~/Our\ Box    # a folder of chat zips
```

Put the chats' `.zip` files in one folder and choose the folder: every chat is imported in one go.
The folder can also hold chats already unzipped, each in its own folder; every `_chat.txt` (and every
`WhatsApp Chat….txt`) is found. A zip of that folder works too. Only the zips at the top of the folder
are opened: a zip deeper down is a file someone sent in a chat. A zip that can't be read stops the
import and is named, so nothing is left out unseen. (The same holds for every source that takes a
folder: a Google Takeout in several parts, for example.)

**What you get.** One page for each person (`People/Ana Costa/Ana Costa.html`), a group's page under
`Groups/<group name>/`, and the chat's photos, videos and voice
notes in the person's `WhatsApp` folder ([details](#attachments-in-detail)).

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

**What is read.** Text (including messages macOS stores only in its rich-text form), tapbacks, read and
delivered times, **replies** (each shows what it answers, with a link), **edited messages** (the page
shows the final text and keeps the earlier versions with their times under "Edited"), **unsent messages**
(a line saying who unsent it, instead of an empty bubble), and the **events of a conversation** as plain
sentences: someone added or removed, the conversation named, the group photo changed, someone left,
location sharing started or stopped, an audio message kept, Emergency SOS events. An event Caixa does not
recognise is still shown, with Messages' own code for it.

Messages that are not text are read too: a **link preview** keeps its address, title, site and summary; an
**Apple Pay** transfer, a **Check In**, a poll or a message from an app (a game move, a reservation) shows
the app's name and its caption; a message **sent with an effect** says which. Messages recently **deleted**
in the Messages app (kept there for 30 days) are imported in their conversation and marked, and the
**category** Messages itself gave a message (junk, promotion, transaction) is shown.

**One person, one conversation.** Messages keeps a separate entry for each address a person uses (their
phone number for iMessage, the same number for SMS, their email), and can split one conversation into
several. Caixa joins addresses that are the same person (the same address on two services, addresses
Messages itself ties together, addresses on one Contacts card) and imports a split conversation as one.
Naming one of a person's addresses names the others. The schema is read as it is: Caixa looks at which
columns your macOS version has and uses those (`chattr-cli doctor chat.db` lists what it found).

**Messages without a conversation.** Messages keeps some messages that belong to no conversation any
more: their conversation was deleted, but the messages were not. Each goes back to the person it was
with, into their conversation if they still have one, or a conversation of its own with them if not.
A message you sent often records no recipient there; Messages does keep, for each message, the one
it came after, so such a reply goes into the conversation of the message it answered (and a run of
replies follows along). Only those with nothing to follow are kept together under **Sent, recipient
not recorded**, listed with the group conversations. Events of a group that no longer exists (someone joined or
left) are left out. Earlier versions put all of these into one conversation called "(no chat)"; import
the same `chat.db` again and it is replaced.

**Texts Google Voice forwarded to your phone.** Google Voice can forward the texts people send you to
your phone as ordinary SMS, and Messages keeps them: the other person's side only (your replies went
through Google Voice), often with no conversation left in Messages. Once both iMessage and Google
Voice are imported, a message in Messages that Google Voice also has (the same number, the same
words, within ten minutes) is taken out, and the Google Voice record, with both sides, stays. The
import says how many it found.

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
| `mac_contacts` | `true` | Name people from the Contacts app on this Mac (read-only). Needs Full Disk Access for the app you start Caixa from, the same as Messages. A `contacts` file is used as well and wins on a clash. |
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

**What is read from a Facebook download, exactly.**

| Part of the download | Used? | What for |
| --- | --- | --- |
| `…/messages/inbox/<thread>/message_1.json` (and `message_2.json`, …) | yes | your conversations |
| `…/messages/archived_threads/…`, `…/messages/e2ee_cutover/…` | yes | conversations you archived; conversations from after Messenger's end-to-end encryption |
| `…/messages/message_requests/…` | no, unless asked | people who wrote to you and were never answered |
| `…/messages/filtered_threads/…` | no, unless asked | what Facebook set aside as spam |
| `connections/friends/your_friends.json`, `removed_friends.json` | yes | who to keep, and their names (nothing is imported from them) |
| `personal_information/profile_information/profile_information.json` | yes | your own Facebook name, to know your messages (nothing is imported from it) |
| Anything else (posts, comments, photos and albums, Marketplace listings, pages, events, …) | no | |

From each conversation: its participants, its title, and each message's sender, time, text, photos,
videos, voice notes, files, GIFs and stickers, shared links, reactions (with who reacted), calls (with
their length), whether it was unsent, and "added to the group" / "left the group" notices.

**Only friends.** A Messenger history is full of people the owner never knew: Marketplace buyers and
sellers, pages, strangers. Caixa keeps only the Messenger conversations in which someone is on your
**Facebook friends list or removed-friends list**, both read from the same export
(`connections/friends/your_friends.json` and `removed_friends.json`; older exports keep them in
`friends_and_followers/` or `friends/`). A group conversation is kept when at least one friend is in it.
Those friends are also **named**, by the name Facebook gives them, so they do not appear under "Not yet
named".

- The import says how many conversations were left out, and the job's log (Jobs → the job → Log) lists
  who they were with, so you can check nothing you wanted was dropped.
- To get the lists, include **Friends** (under Connections) when you download your information. If they
  came in a separate download, point **Facebook friends list** at that download's `connections/friends`
  folder.
- If no list is found, everything is kept and the import says so.
- A conversation with an account that was deleted or deactivated (Facebook shows it as "Facebook user")
  is kept: it may have been a friend. Each such person is listed separately under "Not yet named" as
  `Facebook user (<conversation>)`, so you can link each to who they were.
- Untick **Only conversations with Facebook friends** (`--option only_friends=false`) to keep everything.
- Instagram conversations are not affected: Instagram has follows, not friends.
- A conversation imported before this was in place stays in the box; reset the box and import again
  to drop them.

**Groups** follow the rules for every group conversation (see [Group conversations](#group-conversations)):
kept only if you wrote in them, and only the members who wrote are brought in. Your Facebook messages
are recognised by your name in the box and by the name in the download's own profile, so it works when
your Facebook name differs; that name is also taken to be you, not someone else.

Every import says how many conversations it left out and why, and the job's log lists them.

**Options.** `service` (`auto`, `messenger` or `instagram`) overrides the guess; leave it on `auto`.
`only_friends` (on), `include_requests` (off) and `friends_list` (empty: found beside the messages) are
described above.

**What you get.** Pages per person and year, reactions, shared links, and the photos of the thread in the
person's `Messenger` or `Instagram` folder.

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
and kept in `Mail/<year>/Attachments/`, named by date, sender and their own name, and linked from the page.

### Google Voice

*(`googlevoice`; takes a folder or a .zip)*

**Export.** In Google Takeout choose only **Voice** and download. The calls, texts and voicemail are in
`Takeout/Voice/Calls`.

**Import.**

```bash
caixa import googlevoice ~/Downloads/takeout-voice.zip --box ~/Our\ Box
caixa import googlevoice ~/Takeout/Voice/Calls --box ~/Our\ Box
```

**What is in the export.** Three kinds of file, all in one folder, named for who, what and when:

| File | Example | What Caixa does with it |
| --- | --- | --- |
| `.html` | `Adam Zell - Text - 2013-02-26T02_20_23Z.html` | The texts of one day with one person (or one group), one line per message with its time and sender. Also one page per call (`Placed`, `Received`, `Missed`) and per voicemail. Each message, call and voicemail becomes an item. |
| `.mp3` | `Mary Afraimi - Voicemail - 2021-01-06T18_05_49Z.mp3` | The recording of a voicemail. It is attached to its voicemail and filed as `.m4a`, like iPhone voicemail. Google's own transcript, when the page has one, is kept as the text. |
| `.jpg` (and video) | `Stella Ellis - Text - 2019-09-15T23_14_04Z-27-1.jpg` | A picture sent by text. It is attached to the message that carried it, shown in the thread, and filed like any other picture (JPEG, dated, named for its message). |

**How the days become conversations.** Google writes a page per day; Caixa joins them into one timeline
per person, with their calls and voicemail in the same place.

- **"Me"** is the owner of the box: those messages are shown as sent.
- A day on which only you wrote names nobody inside the page. Caixa takes the person from the file
  name and matches them to the number that name has on other days.
- A group's page lists its members; the group is one conversation whoever wrote that day.
- "MMS Received" and "MMS Sent" are Google's placeholders for a message that was only a picture; they
  are dropped when the picture is there.
- A voicemail `.mp3` whose page is missing is still imported, from its file name alone.

**What you get.** Calls (placed, received, missed), texts with their pictures, and voicemail as items on
the person's pages; recordings and pictures go into the person's `Google Voice` folder.

**Voicemail as text.** Google's own transcript, when the page has one, is shown as the voicemail's text.
To use your own speech model instead, save it in Settings (Speech-to-text model): **Transcribe on this
computer** is then ticked to begin with in the import's options, exactly as for iPhone voicemail. Untick
it to skip transcription for one import (`--option transcribe=false`). Every voicemail
recording is then put through the model, with the same progress and timing lines. Your model's text
replaces Google's on the page; Google's is kept in the data and stays the text for any recording the
model fails on or hears nothing in. Import the same export again with the box ticked to add transcripts
to voicemail that is already in the box.

**Many unnamed numbers.** A long Google Voice history is full of numbers that are not in your contacts
(deliveries, spam, one-off calls), and the preview lists them. They are imported under the number; name
the ones that matter afterwards, or set up Contacts in Settings first so the known ones arrive named.

### iPhone voicemail

*(`voicemail`; takes a folder or a .zip)*

**Export.** Voicemail comes in either of two forms. Point Caixa at a folder or a `.zip` of either:

- **Audio files named for the time and the caller**, as most export tools write them:
  `(2018-12-21) 15 02 31 - Diana Belenky.amr`. That is the date, the time, then a dash and the caller (a
  name or a phone number; the caller can be missing). The time can be written `15 02 31`, `15.02.31`,
  `15-02-31` or `15:02:31`, and the seconds can be left out. The audio can be `.amr`, `.m4a`, `.mp3`,
  `.wav`, `.aac`, `.caf`, `.qta`, `.3gp`, `.ogg`, `.opus` or `.flac`, and may sit in folders inside the zip.
  Files whose names do not start that way are not imported (a zip made on a Mac also holds `__MACOSX`
  and `._…` copies; those are ignored).
- **A device backup**: copy it out of a Finder or iTunes backup. The folder holds `voicemail.db` and the
  numbered `.amr` audio files (in a backup they are under `Library/Voicemail`). If a folder has both, the
  database is used.

The time in a file name has no time zone, so Caixa keeps it exactly as written and marks it as assumed;
the database form records an exact instant. The caller from a file name is a name or number to link to a
person in the People step, like a WhatsApp name.

**Import.**

```bash
caixa import voicemail ~/iphone-backup/Voicemail --box ~/Our\ Box
caixa import voicemail ~/iphone-backup/Voicemail --box ~/Our\ Box \
    --option transcribe=true --option model=$HOME/models/ggml-small.bin --option language=pt
```

**Options.**

| Option | Default | Meaning |
| --- | --- | --- |
| `transcribe` | on when a speech model is saved in Settings, else off | Turn each voicemail into text with a speech model on this computer. |
| `model` | *(empty)* | Path to a local speech model (a whisper.cpp model file, or a faster-whisper model folder). Caixa never downloads one. Empty uses **Speech-to-text model** in Settings. |
| `language` | *(empty)* | A language code such as `en` or `pt`. Empty uses **Speech language** in Settings, and if that is empty too, the model detects it. |

In the browser, the wizard's options step starts the model and language from Settings and has a **Browse
this computer** button for the model file. **Transcribe on this computer** starts ticked once a speech
model is saved in Settings, and unticked until then; untick it (or `transcribe=false`) to skip
transcription for one import.

**How long it takes.** Speech-to-text is the slow part of a voicemail import, so it has a stage of its
own, *Turning speech into text*, with a bar, "3 of 40", the time left, and for each recording how long it
took against how long it is: `12.amr: 4.1 s for 31 s of audio (7.6x real time); average 4.3 s each`. The
same lines are in the job's log (Jobs → the job → Log) and in the terminal you started `caixa serve`
from, so two models can be compared by running the same small export with each. With whisper.cpp all the
recordings of an import go to one run of the program, so the model is loaded once (the first recording's
time includes that) and not once per recording; a recording the run could not finish is tried again on
its own. A smaller model (`small`, `base`) is still usually several times faster than a large one.

**What you get.** Each voicemail as an item (who, when, how long), its audio in the caller's `Voicemail`
folder, and with transcription on, its text beside the player on the page. iPhone voicemail is recorded in
AMR, which most browsers cannot play, so Caixa files it as `.m4a`, which every browser plays (this needs
`ffmpeg`; without it the import says so and files the `.amr` as it is).

**Good to know.** Transcription needs `ffmpeg` and a model (see [Installation](../../README.md#installation)). It
runs with the network blocked for the process, so a speech engine that tried to fetch something would
fail rather than quietly phone home.

## When something does not work

**Read the message first.** When Caixa cannot find anything to import, it says what it opened and
what it was looking for, for example:

```
Nothing to import was found in /Users/you/Desktop/iPhone Voicemail.zip.
What Caixa saw: a zip with 40 files in 1 folder.
File types: 40 .amr.
Examples (letters shown as x, digits as 9): 'Xxxxx Xxxxxxxx 9999-99-99.amr'.
40 audio files were found, but none of their names start with a date and time like
'(2018-12-21) 15 02 31 - Jane Smith.amr', so Caixa cannot tell when each one came in.
Looking for: a folder with voicemail.db, or audio files named like '(2018-12-21) 15 02 31 - Jane Smith.amr'.
```

File names inside your export are shown as *shapes* (letters become `x`, digits become `9`), so the
message and any report show how your files are named without repeating anyone's name or number.
It also tells you when it opened a zip that holds another zip, when a file is not really a zip (and
how big it is), when your path does not exist (and whether its folder does), and how many hidden or
Mac system files (`__MACOSX`, `.DS_Store`) it ignored.

**Make a report.** In the browser, **Create a report** appears under a refused import and on the
**Settings** page. From the command line:

```bash
caixa doctor                                              # what is installed and set up
caixa doctor --box ~/Our\ Box                             # and the box, its recent imports
caixa doctor --collector voicemail --source ~/Desktop/"iPhone Voicemail.zip"   # and why a source will not import
```

The report lists Caixa's version, Python and your system, whether `ffmpeg`, `whisper-cli` and
`exiftool` are found, whether Caixa's window is running and was installed with it, the open
box's size, whether a speech model is set and its file is there, the last few imports with their
errors, and, for a source, what Caixa sees in it. It never contains a name, a number or message text,
and your home folder is shown as `~`. It changes nothing, and works with a box open read-only. Paste
it into your message when asking for help.

## Undoing an import, and running one again

Every import can be taken back. Before an import starts, Caixa keeps a copy of its databases and a list
of the box's files (in `.caixa/undo/`). **Undo** puts the databases back, removes every file the import
added, puts back any file that has moved since, and redraws the pages: the box is exactly as it was.
Your export is never touched, so you can import it again.

- In the browser: **Jobs**, **Undo the last import**. It asks twice. Each import in the list also has
  **Run again** (the same source, the same options).
- From the command line:

  ```bash
  caixa undo --box ~/Our\ Box          # says what it will undo and asks; --yes skips the question
  caixa jobs --box ~/Our\ Box          # the imports, with their numbers
  caixa again 4 --box ~/Our\ Box       # run import #4 again
  ```

Things to know:

- Undo works **newest first**: the last import, then the one before it. The last 3 imports can be undone.
- **Naming people is undone too** if you did it after that import (the names live in the same
  databases). Caixa tells you how many such changes will go before you confirm.
- An import that failed or was cancelled part-way can be undone the same way, to clean up after it.
- Undo is refused while an import is running, and in a box opened read-only.
- The copies take about as much room as Caixa's databases, three times over. They are inside `.caixa/`.

This is the loop for trying an improved importer: **undo**, update Caixa, **run again**.

### Starting a box again

To begin from scratch without setting anything up again, **reset** the box. It takes out everything
that was imported: the pages, the photos, recordings and attachments Caixa filed, the people, the list
of imports and their undo copies. It keeps:

- the box's settings (Contacts, translation, speech-to-text, privacy) and its name and owner;
- its `README.md`, its `Inbox/` and anything waiting there;
- the **owner's preference file**, `.caixa/owner.json` (see [Removing people and the preference
  file](#removing-people-and-the-preference-file)): the names you gave people (a number linked to a
  person, a rename, a merge) and their categories, which apply again on the next import unless you ask
  for them to go too, and the people you removed, who stay out either way;
- the translation key, which is not kept in the box anyway.

Only files Caixa wrote are deleted. A file you put in a person's folder yourself stays where it is, and
the reset lists it. The exports you imported from are never touched.

- In the browser: **Settings**, **Start this box again**. Tick **Also forget the names I gave people**
  to clear those too. It asks before doing anything.
- From the command line:

  ```bash
  caixa reset --box ~/Our\ Box                  # says what it will do and asks; --yes skips the question
  caixa reset --box ~/Our\ Box --forget-names   # the names you gave people go too
  ```

A reset is refused while an import is running, and in a box opened read-only. It cannot be undone.

## Picking up where you left off

Caixa remembers, in its own folder (`~/.local/share/caixa` on Linux, `~/Library/Application
Support/Caixa` on a Mac, or `$CAIXA_HOME`), in a file called `state.json` only you can read:

- **The boxes you opened lately** (the last ten). `caixa serve` with no `--box` reopens the newest one
  that is still there and says so. The **Box** section lists the others, with **Open**; one whose
  folder has gone is marked, and **Remove from list** takes it off.
- **Which section you were in** for each box (Box, Import, Jobs, …), so the page opens there.
- **An import you set up but have not started**: the source, the step you reached, the path you typed
  and the options you chose. It is put back, even after you leave the Import section for a moment, close
  the tab or stop Caixa. It is cleared when the import starts or you go back to the beginning. The preview is made
  again from your options rather than remembered.

Imports that were running when Caixa stopped are listed in **Jobs** as *interrupted*; running the same
import again is safe, since nothing is imported twice. If the worker restarts by itself while the page
is open, the page opens the box again.

None of this is kept inside a box, so a box on a read-only drive or opened read-only still remembers
where you were. Delete `state.json` to forget it all. It holds folder paths and your import choices,
not messages.

## Naming the people

Exports identify people by whatever the service uses: a phone number, an email address, a username, or a
display name. Until a handle is **named**, its pages go in a folder called after the handle
(`People/+15550101/…`). Naming a handle links it to a person, so **all of a person's messages, across
every app, live together** under that person's name.

**Who is named without being asked.**

- **Contacts** (Settings → Contacts) name a phone number, an email address or an exact name.
- **WhatsApp, Google Voice and iPhone voicemail exported as named files** show a sender by the name
  saved for them in your phone or in Google Contacts. A sender shown by a name is taken as that person; a sender shown only by a phone number
  waits for a name. On WhatsApp a name written after `~` is one people gave themselves, and is not
  taken.
- **Facebook friends** (and removed friends) are named by the name Facebook gives them.

The same name from two sources is one person: "Ana Costa" in WhatsApp, in your Contacts and on Facebook
all land on one page. A name that differs ("Jon Smith" here, "Jonathan Smith" there) makes two people,
which you can merge in the People section. Caixa never guesses that two different names are one person.
Everyone else (a number, an email address, a Messenger stranger in a group
with a friend, a deactivated Facebook account) is listed under "Not yet named" until you name them.

There are three ways to name people, and they combine:

1. **Contacts, set once.** In **Settings → Contacts** choose either or both:
   - **Use this Mac's Contacts** (on by default). Caixa reads the Contacts app's database, read-only.
     macOS allows that once the program you start Caixa from (Terminal) has **Full Disk Access** in
     System Settings → Privacy & Security; the web browser needs no permission. Settings shows how many
     people could be read, or what to do when none could.
   - **A contacts file** (`.vcf`, a vCard export of your address book). Give its path once; every
     import then uses it and none asks again. Where both know a number, the file wins.

   Every import of every source uses these. From the command line a file can still be given for one
   import with `--option contacts=$HOME/contacts.vcf`.
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

## The box's index page

`index.html` at the top of the box is where to start. All the box's pages share one look, the Nord
colours (light or dark, following your computer), with Caixa's orange for dates and the calendar.

- **On the left, the categories:** All, Family, Friends, Business, Acquaintances, Unrecognized and
  Unassigned, each with how many people it holds, then Groups and Mail.
- **On the right, the people as tiles:** each a square with their initials (their face, once photos are
  imported), their name, how many items and which years. Hover over a tile to see how much came from
  each source. Click it to open their page; every person's page has an **All people** button at the
  top to come back.
- **All** shows everyone except the unrecognized, with the box's numbers on top: items, people,
  groups, mail, files and their size, and a table of each source (items, conversations, files, size,
  first and last date). The numbers show only under All.
- **Unrecognized** holds whoever is known only by a phone number, an address or an account that no
  longer has a name ("Facebook user"); they move out when you name them. They are listed busiest first, the
  most items on top, so the ones that matter most come first; every other category is in name order. You can also put anyone there.
- **The footer** says how many people the category holds, and in Unassigned how many are selected.

**Sorting people.** Open **Unassigned**: everyone who has a name and no category yet. There a click
selects a tile instead of opening it; click more to select more, or Shift-click to select a range.
Drag the selection onto a category on the left, or use the **Move to** buttons in the footer. The
people leave Unassigned at once; Caixa saves their category in the box and redraws the pages. Escape
clears the selection.

Sorting works when the index is opened in Caixa: Browse, **Open the box's index page**. It opens in
a window of its own beside Caixa's (allow pop-ups for Caixa if your browser asks), and every page
of the box you open from Browse goes to that same window. Opened straight from the folder, in any browser, the page shows the
categories and works for browsing, but says that sorting needs Caixa. Categories are kept when you
rename or merge someone, and when you reset the box (unless you ask for the names you gave to be
forgotten).

**Back to Unassigned.** In Family, Friends, Business or Acquaintances, hover over a tile: a **×**
shows in its upper right corner. Choose it and the person goes back to Unassigned. Nothing shows on
a tile until the pointer is over it.

**Naming someone unrecognized.** In **Unrecognized**, hover over a tile and a **Name** field shows
under it. As you type, it offers the people already in the box: pick one (click it, or the arrow keys
and Enter) and the number or address joins that person, whose page is redrawn with everything from
it. Or type a new name. **Apply** shows beside the field once something is typed (Enter does the
same). A new name moves the person to Unassigned. Either way the name is kept in the preference file.

**Removing people.** In **Unassigned** or **Unrecognized**, select people and press **Delete** (or
Backspace). Caixa asks first; then their one-to-one conversations with you, and the photos, recordings
and files in them, are deleted from the box, and their pages go. What they wrote in group conversations
you took part in stays. Removed people stay out of later imports. It cannot be undone.

**Opening a page without losing the selection.** In Unassigned and Unrecognized a click selects, so
hover over a tile and choose the **↗** in its upper right corner to open that person's page in a new
window; the selection stays as it was.

## Removing people and the preference file

Imports bring in everyone an export holds. Two places take out the ones you do not want, with
everything that came only from them:

- the index page, in Unassigned or Unrecognized: select, then Delete (see above);
- the **People** section, under "Not yet named": the box at the top left of the first entry shows a
  box beside every entry; tick the ones to remove and choose **Delete** at the bottom of the list.

What you decide about people is kept in the **owner's preference file**, `.caixa/owner.json` in the
box. It survives a reset, and every import reads it first:

- `names`: who a number, an address or a name is (what you linked, renamed or merged). These come
  before Contacts and before the names a source gives;
- `categories`: the category each person is in;
- `removed`: the people and numbers you removed. Their conversations are not imported again.

Caixa writes the file whenever one of these changes. It is plain JSON, readable only by you (it holds
real names and numbers: keep it out of anything you share). You may edit it while Caixa is not
running: names and categories added there are taken up when the box is next opened, and deleting an
entry from `removed` lets that person be imported again. The box's settings are a different file,
`box.yaml`, beside it.

## Group conversations

The same rules apply to every group conversation, from every source (iMessage, WhatsApp, Messenger,
Instagram, Google Voice):

1. **A group is kept only if you wrote in it.** Groups someone added you to and you left, or never
   answered, are left out, messages and all. The import says how many, and the job's log names them.
   (If none of your own messages can be recognised in a source, its groups are all kept and the import
   says so: check **Your name** in the import's options.)
2. **Only the members who wrote are brought in.** Someone listed as a member who never wrote anything is
   not brought in at all: no name, no place in the group, and a reaction of theirs keeps its emoji but
   not who sent it.
3. **A phone number from a group is never brought in**, even if it wrote. Its messages stay on the
   group's page, shown with the number, but it is never listed under "Not yet named". If the number is in
   your Contacts, its messages are shown under that person's name, as anywhere else. A number you also
   have a conversation of your own with is listed as usual.

## Translation

Caixa can put an English translation under each message that is in another language. The original text
is never changed; the translation is stored beside it and shown under it on the page.

**Which messages are translated.** The rule is the one Chattr has always used:

- only text messages (not mail, not voicemail transcripts, not system notices);
- only when the language is clearly not English. Caixa recognises Portuguese, Spanish, French, German
  and Italian; a message too short to tell, or in a language it does not recognise, is left alone
  rather than guessed at;
- not when the author already translated it themselves: if the same person wrote an English message of
  about the same length (within 20%) within five minutes before or after, that is the translation and
  nothing is sent;
- never twice: a message that has a translation is not sent again.

**What does the translating.** Any service that speaks the OpenAI chat format. In **Settings →
Translation** give:

| Setting | A model on this computer | A paid service |
| --- | --- | --- |
| Translation endpoint | `http://localhost:11434/v1` (Ollama), `http://localhost:1234/v1` (LM Studio) | `https://openrouter.ai/api/v1`, `https://api.deepseek.com/v1` |
| Translation model | the model's name, such as `llama3.1` | such as `deepseek-chat`, or an OpenRouter model name |
| Allow a service on the internet | leave off | **tick it**: without it Caixa refuses the address |
| API key | leave empty | the key the service gave you |

**The key** is not kept in the box, because a box is copied, shared and backed up. It is kept in Caixa's
own folder on this computer (`keys.json`, readable only by you), it is never shown again once saved, and
it is remembered for one host: change the endpoint to another service and the key is not sent there.

**Test** sends one sample sentence (nothing from your box) using what is typed in the form, saved or not,
and shows what came back, or says why it failed: the address does not answer, the key was refused, the
model name is unknown, the account has no credit. Use it before the first import.

**When it runs.** With translation on, every import has a *Translating messages* step after people are
matched and before the pages are written. It considers every message in the box, so turning translation
on and importing anything (the same export again will do) also translates what was imported before. A
paid service is sent four messages at a time, a local model one. If the service fails, the import still
finishes, keeps what was translated, and says what went wrong; import again to translate the rest.

**What the model is told.** Each message is sent on its own, with an instruction to translate it and
do nothing else: the message is text to translate, never a request to act on, so a message that says
"ignore your instructions" is translated, not obeyed. A reply that is far longer than the message (a
model that started chatting) is thrown away, and a reasoning model's "thinking" is removed.

**Cost and privacy with a paid service.** The text of each message that needs translating is sent to
that service, one message per request, with no names, dates or attachments. The service will charge
for it; a large archive can be tens of thousands of messages. Nothing else leaves your computer.

From the command line the same translation is `chattr-cli translate` (see Chattr's README).

## Where the data is stored

Everything is inside the box folder.

```
Our Box/
  README.md                       plain-language note: what this folder is
  index.html                      start here: everyone, sorted into categories, and the box's numbers
  People/
    Ana Costa/
      Ana Costa.html              everything from Ana on one page: every year, every source
      WhatsApp/
        (2024-03-01) 14-05-09 Ana Costa.png
      Voicemail/
        (2018-12-21) 15-02-31 Ana Costa.m4a      the recording, in a format any browser plays
      Google Voice/
        (2018-09-08) 10-22-45 Ana Costa.m4a
    +15550101/                    a number nobody has named yet (it moves when you name it)
  Groups/
    Costa Family/
      Costa Family.html, WhatsApp/…
  Mail/
    2019/(2019-11-02) João Costa — Fotos de São Martinho.html
    2019/Attachments/(2019-11-02) 16-00-00 João Costa — familia.png
  Inbox/                          drop exports here to find them in the browser
  .caixa/                         Caixa's own working files (below)
```

The top level is **people**. Each person's folder has **one page**, named after them, that brings every
source and every year together in time order, and one folder per source holding the files that source
brought.

**One page, however long.** The page starts with a summary (how much, from when to when, from which
sources, the groups they are in and the mail they sent), then a bar of years that stays at the top while
you read. Each year begins with its calendar; a coloured day goes to that day, and a date's heading goes
back to the top. A page for someone you wrote to every day for years can hold a hundred thousand
messages; it still opens at once: the browser shows the top while the rest arrives, lays out only the
days on screen, and loads pictures, video and audio only when you scroll to them. (Measured on a page of
100,000 messages, 84 MB: the first messages show in about 0.2 seconds and the whole page has arrived in
about 2.5 seconds.) Click a picture to see it full size over the page; the arrows (or the arrow keys)
go to the pictures before and after it, and Escape closes it. That is the page's one script: without
it, in any browser, each picture is still a link to its file. Caixa's viewer lets pages run exactly
that script and nothing else.
Every file is named for its date, time and sender; nothing you can see is named by a code. You can also
keep your own notes or files in a person's folder: Caixa only ever removes pages it wrote itself.

**Everything above `.caixa/` is ordinary files** (HTML, images, audio). Open `index.html` in any web
browser, with or without Caixa, now or in fifty years. Each page also carries its own data, so it can be
read by a program as well as a person.

**Inside `.caixa/`:**

| Path | What it is |
| --- | --- |
| `caixa.sqlite` | The **master database**: one row per item (a message, a mail, a call, a voicemail), the people, their names (aliases), a record of every import, and an append-only **change log**. Each item says which page and anchor show it (`People/Ana Costa/(2024) Ana Costa.html#m-…`) and has a privacy level (`private` by default). |
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
5. **Draw the pages**: `People/<Person>/<Person>.html`, `Groups/…`, `Mail/<year>/…`, plus the box's
   `index.html`.
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

### One rule for every source

While an export is being read, its files wait in a working folder inside `.caixa/`. When the pages are
drawn, every file is **filed** beside the person it came from:

```
People/<Person>/<Source>/(YYYY-MM-DD) HH-MM-SS <sender>.<extension>
Groups/<Group>/<Source>/(YYYY-MM-DD) HH-MM-SS <sender>.<extension>
Mail/<YYYY>/Attachments/(YYYY-MM-DD) HH-MM-SS <sender> — <its own name>.<extension>
```

For example `People/Ana Costa/WhatsApp/(2024-03-01) 14-05-09 Ana Costa.png`. The pieces:

- **Person or group.** Whose conversation it is. A number nobody has named yet has a folder under its
  number; when you name it, its pages *and its files* move to the person's folder.
- **Source.** `iMessage`, `WhatsApp`, `Messenger`, `Instagram`, `Google Voice`, `Voicemail`.
- **Date and time.** The time of the message that carried the file, as shown on the page (local time when
  the export gives a time zone).
- **Sender.** Who sent it, made safe for a file name (characters such as `/ : * ? "` become `-`).
- **A number**, only when it is needed: ` 1`, ` 2`… when one message carried several files, and ` (2)` if
  two different files would otherwise get the same name. Names come out the same on every run.
- **Extension.** Kept as it was, in lower case.

The original export is never touched: files are copied out of it. Importing the same export again leaves
one copy of each file, and a file Caixa did not put there is never overwritten. The same picture sent in
two messages is kept twice, once beside each.

**Dates inside the file.** If ExifTool is installed and a picture has no capture date, Caixa writes the
message's date into the *copy* (the standard `DateTimeOriginal` field) so the date travels with the file.
Without ExifTool the copy is made unchanged.

**What is not changed.** Files are kept as they arrived: a photo stays in the format it was sent in. (A
file that cannot be copied is reported in the job's log and skipped; it never stops the import.) Apple's
proprietary "plugin payload" attachments are skipped as not suitable for archiving.

### Audio

Recordings are filed as **`.m4a`** (AAC), the one format every browser and phone plays. iPhone voicemail
(`.amr`), iMessage voice notes (`.caf`), WhatsApp voice notes (`.opus`), and `.ogg`, `.wav`, `.aiff`,
`.wma` and `.flac` files are converted when they are filed, at the recording's own sample rate and
channels (8 kHz mono for voicemail, at about the same size). `.mp3` (Google Voice voicemail) is converted
too, at its own bit rate, so that every recording in the box is one format. Only the `.m4a` is kept in
the box; the file in your export is never changed. `.m4a` is filed as it is.
**Mail attachments are never converted.**

The conversion uses `ffmpeg`. If it is not installed, or a recording is damaged, the import finishes,
files the recording in its original format, says how many there were, and the page links the file with a
note that it may not play. Install `ffmpeg` and import the same export again: those recordings are then
converted and the old files removed.

### One copy of each file

The same file often arrives many times: a sticker sent fifty times, a photo sent to three people, a
meme forwarded to a group. Caixa recognises identical files by their content (a SHA-256 checksum) and
**stores each one once**. It is filed for the earliest message that carried it, and every other message
shows that same file on its page. So:

- a person's folder holds a file only if it was first seen in a conversation with them; their pages still
  show everything they sent or received;
- importing the same export again never adds a second copy;
- the one copy follows its person if they are renamed or merged, and every page that shows it follows too;
- mail is kept apart: a file that came both by mail and in a chat is kept once for each, because mail
  attachments are never converted.

### Pictures

Pictures from messages are filed so that any device and any photo library can open and date them:

- **HEIC** (iPhone photos), **PNG** and **WebP** are filed as **JPEG at quality 85**. Only the JPEG is
  kept in the box; the file in your export or on your Mac is never changed. A picture with see-through
  parts gets a white background. The colour profile (iPhones use Display P3) is kept.
- Every filed picture carries the date it was taken (`DateTimeOriginal`). A picture that already knows
  its date keeps it. One that does not (screenshots, pictures that passed through WhatsApp or Messenger)
  is given the local date and time of the message that carried it. A JPEG is dated without being
  compressed again.
- The file is named after its message, like every attachment: `(2024-03-01) 14-05-09 Ana Costa.jpg`.
- JPEG that already has its date, GIF, moving pictures (animated stickers) and video are filed exactly
  as they are. **Mail attachments are
  never converted**: there the file itself is the record.
- A picture that cannot be read (damaged, or only partly downloaded) is filed in its original format and
  the import says how many there were.

Nothing extra needs installing: Caixa does this itself. `exiftool` is used only for the rare JPEG that has
camera data but no date; without it such a file is left as it is.

### iMessage attachments

Attachments are **copied** from the Mac's store (`~/Library/Messages/Attachments`, never changed) and
filed like every other source's: `People/<Person>/iMessage/(date) time sender.ext`.

**Files that are still in iCloud.** Messages fetches an attachment from iCloud only when its part of the
conversation has been shown on this Mac, so a database usually names files that are not on disk (often a
third or more). Caixa cannot fetch them. It tells you:

- The **preview** says how many attachments are missing, how much data, and which conversations hold the
  most.
- This lists every conversation with missing files, the most data first, with the first and last dates
  to scroll back to:

  ```bash
  chattr-cli missing ~/Library/Messages/chat.db
  chattr-cli missing ~/Library/Messages/chat.db --list "Ana"     # the files, for conversations matching
  ```

- Open those conversations in Messages, scroll back to those dates so the files load, and run it again
  until the number stops falling. Then import. Importing again later is safe and adds files that have
  arrived since; a message whose file is still missing says "file not in this archive".
- Attachments with "no file was ever recorded" have no file to fetch.

### How pages link to files

Pages use ordinary relative links (`WhatsApp/(2024-03-01) 14-05-09 Ana Costa.png`), so the box keeps
working if you move or copy the folder. A photo is shown inline, audio and video get a player, and any
other file is a link. If the file is not in the box the page says so rather than showing a broken link.

### Summary

| Source | Where the files go | Converted? |
| --- | --- | --- |
| WhatsApp, Messenger, Instagram | `People/<Person>/<Source>/` (or `Groups/<Group>/<Source>/`) | pictures to JPEG, voice notes to `.m4a` |
| Google Voice | `People/<Person>/Google Voice/` | voicemail `.mp3` to `.m4a`, pictures to JPEG |
| iPhone voicemail | `People/<Person>/Voicemail/` | `.amr` to `.m4a` |
| Mail | `Mail/<year>/Attachments/` | never |
| iMessage | `People/<Person>/iMessage/` | pictures to JPEG, `.caf` voice notes to `.m4a` |

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
| Voicemail | One item per voicemail: a row in `voicemail.db`, or an audio file named `(date) time - caller`. Each keeps its audio file. |

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
    elif (box / stored).is_file():   # the stored path is relative to the box
        good += 1
    else:
        missing += 1
        print(f"  MISSING: {service}: {stored}")
print(f"{good} attachments in the box, {unsaved} recorded but not copied, {missing} missing")
sys.exit(1 if missing else 0)
```

Success is **no `MISSING` lines**. Lines saying "not copied into the box" are iMessage attachments that
were not on the Mac when you imported (see [iMessage attachments](#imessage-attachments)). With the
synthetic data the result is `9 attachments in the box, 0 recorded but not copied, 0 missing`.

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
- In the browser interface, the **Browse** section lists the box's files and opens its pages in a window of their own.
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

- **iMessage attachments that are still in iCloud cannot be fetched.** Caixa copies the files that are
  on the Mac and tells you which conversations hold the rest (`chattr-cli missing`); loading them is
  done in Messages, by hand.
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
