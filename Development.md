# Development

A rolling record of how Caixa is being built: the idea, the way we work, each project from first
plan to completion, what went wrong along the way and what we learned, and what is waiting. It is
updated at the end of every project. The detail of each project (briefing, Requirements, tickets
and completion report) lives under [`docs/ai/`](docs/ai/); this file is the story that ties them
together.

- [The idea](#the-idea)
- [How we work](#how-we-work)
- [Timeline](#timeline)
- [Phase 1: Collectors](#phase-1-collectors-2026-11-01-to-2026-11-19)
- [Phase 1.5: Mail without the noise](#phase-15-mail-without-the-noise-2026-11-19-to-2026-11-24)
- [Phase 1.5 - PDF: Documents](#phase-15---pdf-documents-2026-11-24-to-2026-11-28)
- [Issues we ran into, and what they taught us](#issues-we-ran-into-and-what-they-taught-us)
- [Where things stand](#where-things-stand)
- [Backlog](#backlog)
- [Next](#next)

---

## The idea

A generation ago a life survived as photo albums, letters, tapes and paper. Today it is born
digital, spread over phones, cloud accounts and messaging apps, and it can vanish with a lost
device, a closed account or a death nobody planned for. Even people who export their data carefully
are left with a pile organized for each platform's database, not for a person: opaque file names,
dates in sidecar files, UTC epochs, double-encoded text, one enormous file per thread.

**Caixa** (Portuguese for *box*) is an open-source digital-legacy system that turns that pile into
one durable box a family can use. From the first briefing it has had three parts:

1. **Collectors** turn platform exports into an archival form: plain folders, pages readable in any
   browser, people first and dates second, nothing proprietary.
2. **A personal model**: a small, open, local model that becomes the expert on the person, answering
   from the archive and citing it.
3. **A harness** that runs the box locally in a browser, so an heir can read, browse and ask.

The promises that shape every decision:

- **Local first.** No personal data leaves the computer unless the owner chooses a service.
- **Durable, open formats.** SQLite, HTML, JSON, standard image metadata.
- **Caixa is an enabler, not a requirement.** The box's files work without Caixa; Chattr (the
  message converter) runs without Caixa.
- **Import again safely.** Stable IDs: a newer export that overlaps an older one adds only what is new.
- **Everything the window does is also a `caixa` command.**

The work is staged: **Stage 1** collectors (messages), **Stage 1.5** quieter mail and further
sources (mail, PDFs, photos, home videos, Obsidian vaults), **Stage 2** the personal model,
**Stage 3** the harness and a read-only presentation mode.

## How we work

- **Bora.** Each project is a folder under `docs/ai/<Release train>/<Project>/` with a briefing,
  Requirements (agreed with the maintainer before any ticket), tickets created from the Requirements'
  Tasks Breakdown, an auto-generated `Status.md` and a completion report. Every ticket carries its
  own implementation plan, is built test-first (red, then green), verified, reviewed and closed with
  a completion note. Commit messages follow `{ticket-id} {task-id}: {title}`.
- **Release trains and branches.** The first train is **Istanbul**. Each project has a branch
  (`2026-Istanbul/Phase1-Collector`, `2026-Istanbul/Phase1.5-Mbox`) that merges into `working`, the
  integration branch, and from there into `main`, which is production only.
- **Hot fixes.** After each planned board, the maintainer tests on real exports. What that turns up
  becomes tickets in the same project ("hot fixes"), each with a plan, tests and a completion note.
  In both projects so far the hot fixes outnumbered or matched the planned tickets: real data is
  where the design is finished.
- **Synthetic data only.** Tests and fixtures use a synthetic family (Maria Costa, the owner; Ana,
  João, Rui, Beatriz…) and synthetic exports in every format. No real personal data is ever
  committed; real exports stay on the maintainer's machine.
- **Authorship.** Commits are authored by the maintainer, with AI assistance credited in a
  `Co-Authored-By:` trailer.
- **Naming.** Release trains, projects, branches, top-level folders and files meant for people are
  named by the maintainer, never invented.

## Timeline

| Date | What happened |
| --- | --- |
| 2026-11-01 | Phase 1 (Collectors) briefing and Requirements: Caixa's data architecture, Chattr carried in as the message converter. |
| 2026-11-02 | The repository's history begins (Phase 1 already well under way): the people, browse and settings pages; GPL-3.0-or-later for Caixa and Chattr; documentation of the collectors. |
| 2026-11-06 → 11-07 | `caixa serve` installs its harness from a lockfile; voicemail from named audio files; Caixa remembers where you were. |
| 2026-11-12 → 11-14 | First wave of hot fixes from real exports: Messenger speed, iMessage brought up to `imessage-exporter` 5.0.1, dated JPEGs, attachments stored once, undo and run-again, translation, speech-to-text in one run. |
| 2026-11-16 → 11-18 | One page per person; reset; the index page with categories and a dashboard (Nord theme); the owner's preference file; Caixa's own service replaces DeepSeek Harness. |
| 2026-11-19 | Phase 1 complete: 66 tickets, **release 0.5.0** merged to `working` and `main`. Phase 1.5 (Mail) scaffolded. |
| 2026-11-20 | Phase 1.5 Requirements approved; the mail workflow built (index, cleaning, sorting, import, Reduce). |
| 2026-11-21 | Conversation pages, the person-page entry and overlay, local summaries, Attachments folders. First real mbox: hot fixes 16–21, Apple Intelligence. |
| 2026-11-22 | Hot fixes from daily use: redraws on new templates, selection and nested categories, the AI benchmark, Apple Intelligence first, merge by drag, mail by account and folder, undecodable characters. |
| 2026-11-23 | Deleted people's mail, the calendar at the top, merging anywhere, an attachment race, the work bar, and the redraw made fast and batched. |
| 2026-11-24 | Phase 1.5 complete: 46 tickets, **release 0.5.1** merged to `working` and `main`. Next: PDF support. |
| 2026-11-24 | Phase 1.5 - PDF planned and built: 23 tickets on `2026-Istanbul/Phase1.5-PDF`, tested on synthetic PDFs; waiting for the maintainer's Mac. |
| 2026-11-25 | First real PDF imports on the Mac (about 150 PDFs): four hot fixes, among them the missing PDF card, numpy, errors that no longer end an import, and the session log. |
| 2026-11-27 | `caixa documents prepare` to compare Apple Intelligence with a local model on real PDFs (Gemma so far), and author knowledge learned from corrections. |
| 2026-11-28 | `prepare --organized`: owners' well-named PDFs keep their names, only a wrong date is replaced, and their authors and tags become the first whitelist. |
| 2026-11-28 | `prepare` folded into the import (D31, five tickets); `prepare` becomes its dry run, writing a preview at the box's root. |

---

## Phase 1: Collectors (2026-11-01 to 2026-11-19)

Project files: [`docs/ai/Istanbul/Phase1-Collector/`](docs/ai/Istanbul/Phase1-Collector/).

### What we set out to do

Define Caixa's data architecture (the box layout, the dates-and-people rules, a master database as
the source of truth, stable IDs) and build the first and most valuable collector: messages.
**Chattr**, an existing open tool that began as a WhatsApp-to-HTML script, was carried into Caixa
as the message converter, finished (unified schema, SQLite store) and kept usable on its own, with
changes flowing back to its own repository through a mirror.

### What was built

66 tickets: 27 from the Tasks Breakdown and 39 hot fixes from the maintainer's testing.

- **Six collectors**, each with a "how to export" card: iMessage (`chat.db`, read only, any recent
  macOS schema), WhatsApp, Messenger and Instagram, mail (`.mbox`), Google Voice and iPhone
  voicemail. Every import can be previewed, undone and run again.
- **The box**: a plain folder, complete when copied. One page per person with every source
  together, group pages, mail pages and an index of people as tiles in categories (Family, Friends,
  Business, Acquaintances, Unrecognized, Unassigned), with a dashboard and authoring tools.
- **Files**: attachments filed beside their person, named by date and sender, stored once;
  pictures as dated JPEG, audio as `.m4a`.
- **People**: Contacts (the Mac's or a vCard), Facebook friends, one person across addresses and
  services, renames and merges, the owner's decisions kept in `.caixa/owner.json` across resets.
- **Rules against noise**: message requests and non-friends left out, group conversations only
  where the owner wrote.
- **Local speech-to-text** and **translation** through any OpenAI-compatible endpoint.
- **Caixa's own window**: `caixa serve` runs the service and a small web server in one process,
  with the React window built into the package.
- **Command line** for everything, `caixa doctor` and `caixa reset`.

### Decisions

- GPL-3.0-or-later for Chattr and Caixa; Chattr's command is `chattr-cli` (2026-11-02).
- The collector left DeepSeek Harness for a service of its own, in Python; the plugin was removed
  and `harness/` renamed `web/` (2026-11-17).
- No automatic pruning: the owner removes people by hand, remembered in `owner.json` (2026-11-17).

### Issues along the way

- **The harness we started on.** Caixa first ran inside DeepSeek Harness. Its first-run dialogs,
  patches and process model kept getting in the way of tests and of the people using it, so the
  collector moved to its own Python service and window (tickets `20261117-04` and `-05`).
- **Chattr's v2 scaffolding** was more design than wiring: six wrong configuration keys, a crash on
  `sqlite3.Row` in the HTML output, and non-deterministic mbox fixtures (random MIME boundaries,
  current-time `From ` lines) were found and fixed while stabilizing it.
- **Real exports differ from documentation.** Messenger slowed down with every thread; iMessage's
  database changed columns across macOS versions (read by the columns it has, `20261112-09`);
  messages without a chat, owner replies in deleted chats and Google Voice texts duplicated as
  iMessage each needed their own rule.
- **Templates and dicts.** Twice a Jinja template read `items` on a dict as the dict's method, once
  on the dashboard and once on the Unrecognized sort; caught by tests.
- **Browser tests and redraws.** Several end-to-end tests raced with the redraw a change started;
  the tests learned to wait for it.

---

## Phase 1.5: Mail without the noise (2026-11-19 to 2026-11-24)

Project files: [`docs/ai/Istanbul/Phase 1.5 - Mbox/`](docs/ai/Istanbul/Phase%201.5%20-%20Mbox/),
including the [completion report](docs/ai/Istanbul/Phase%201.5%20-%20Mbox/(2026-11-24)%20Phase%201.5%20-%20Mbox%20Completion.md).

### What we set out to do

Phase 1 could import an mbox, but a real mailbox is mostly noise. The goal: read an mbox of any
size into an index without importing anything; clean it of junk without losing receipts or anyone
who matters; sort its senders in a window that works like the people page; import only the chosen
conversations; summarize each conversation on this computer; keep what was left out in a smaller,
Reduced mbox.

### The plan (tickets 01–15, built 2026-11-20 and 21)

- **Synthetic noisy mail**: a Gmail-shaped mbox and a second account with every case the rules
  name, plus a generator for multi-gigabyte scale tests.
- **The mail index** (`caixa/mail/index.py`): an mbox, a zip of mboxes or a folder read once into
  `.caixa/mail/index.sqlite`, split into ranges read by up to 12 worker processes (2 GB: 36.7 s
  with one worker, 9.9 s with four).
- **Cleaning** with a receipts guard and protections for people the owner wrote to, written as a
  Cleaned mbox beside the source (the export itself is never changed).
- **Sorting**: Known people chosen to begin with, everyone else to choose or ignore, with what each
  choice brings (threads, mails, size).
- **Import** of the chosen conversations, keyed by Message-ID so nothing is duplicated, recorded in
  the master (`mail`, `mail_threads`, accounts).
- **Conversation pages**: one page of cards per conversation, filed with its person, the mail's own
  HTML made safe (chosen by the maintainer after a trial on five real mails), an entry on every
  person's page and an overlay to read it in place.
- **Local summaries** of 30–50 words, in the conversation's language, marked as written by a model.
- **Reduce**: what was not imported, written to a Reduced mbox to sort again later.
- **Attachments folders** for every source, with existing boxes moved once on opening.

### Hot fixes (tickets 16–46, 2026-11-21 to 23)

The maintainer imported real mailboxes and used the people page every day. In order:

- **First real mbox (16–21):** Select all, a meter from the first click, Translate and Summarize
  switches per import, subcategories, and **Apple Intelligence** as a provider through a Swift
  helper (`tools/apple-intelligence/`), built on the maintainer's Mac with Xcode's Swift.
- **Daily use (22-01 to 22-13):** pages drawn by an older Caixa redrawn on opening and always loaded
  fresh; selecting within a category (⌘-click, Shift-⌘-click, a box); nested and flattened category
  views; an **AI benchmark** (`caixa benchmark`) that showed Apple Intelligence clearly ahead, so it
  became the first choice wherever available; cleaning made optional; a report when an import ends;
  dragging anyone onto any category; merging by dropping one person on another; mail by account,
  label and folder on the people page; quiet logs when the browser drops a connection; mail with
  characters its encoding cannot explain.
- **Larger mailboxes and a larger box (23-01 to 23-11):** deleted people no longer come back through
  their mail, which is kept under `People/Removed/`; the calendar moved to the top of person pages;
  merging works anywhere, named or not, several at once; an attachment race in parallel imports;
  received and sent mboxes of one account join; a work bar; and the redraw made fast (below).

### The redraw, from 12.8 s to about 2 s

With 48,000 pages in the maintainer's box, sorting one person had become painfully slow, because
every change redrew the whole box. Measured on a synthetic box of 3,000 mails with a picture each:

| Step | Redraw |
| --- | --- |
| Before | 12.8 s (filing 3.4 s, pages 9.2 s) |
| Data islands escaped in one pass; folders resolved once (`20261123-07`) | 7.4 s |
| Pages shared among the box's workers (`-08`) | 4.7 s with four workers |
| Only pages whose data or templates changed are written (`-09`) | 2.2 s when little changed |
| Changes batched behind **Update the pages**; sorting alone writes the people page only (`-11`) | one pass for many changes |

The terminal now ends each step of a redraw with what it did, the workers it used and how long it
took (`-10`), and the Workers setting is visible in Settings.

### Decisions (recorded in the Requirements)

- 2026-11-20: the categorized list with counts and sizes in both mail windows; Attachments folders
  for every source in this project; name-only matches not chosen until confirmed.
- 2026-11-21: mail bodies drawn as the mail's own HTML, made safe; the Apple helper built by Caixa on
  first use; subcategories two levels deep.
- 2026-11-22: Apple Intelligence first wherever it is available (Automatic, the default).
- 2026-11-23: removing someone ends them as a person, not their mail; merging by dropping anywhere,
  the one dropped on keeping their name; the work bar; changes wait for **Update the pages**.

---

## Phase 1.5 - PDF: Documents (2026-11-24 to 2026-11-28)

Project files: [`docs/ai/Istanbul/Phase 1.5 - PDF/`](docs/ai/Istanbul/Phase%201.5%20-%20PDF/),
with its completion report and testing guide.

### What we set out to do

Documents as a domain of the box, PDF first:

- import PDFs without touching the originals;
- give every archived copy a validated, searchable text layer;
- name and file each one by date and author, from evidence that a local model and the file name
  agree on;
- find documents again through search and card pages that open the PDF over the page.

The maintainer's draft had seven phases; phases 1–6 are this project, and the seventh (financial
transactions) went to the backlog.

### What was built (tickets 01–23)

- **The collector** `pdf` (`caixa/collectors/pdfImport.py`, named so other formats get their own).
  It takes a file, a folder or a zip, with preview, undo and run-again.
- **Inspection, OCR and validation:**
  - each page is classed (text, scan, old OCR layer, broken text);
  - OCRmyPDF is run on the scanned pages only;
  - broken-text pages are read by OCR from a render and left as they are;
  - the copy is checked by PyMuPDF and pikepdf, page by page, against renders of the original. A
    copy that fails is filed unchanged and can be retried.
- **Names and folders:** `(date) Title - Author.pdf` under `Documents/PDF/<year>/<author>/`, or
  `Unrecognized/`. The convention is set out in `docs/Archival names.md`, with `caixa/naming.py`.
- **Reading by a local model**, through the summaries' provider (Apple Intelligence first), never
  a remote one:
  - JSON schemas for classification and for eight types;
  - every quote verified against its page;
  - reconciliation and confidence decided by Caixa's rules, not the model's score;
  - summaries and tags from an extensible starter set;
  - a documents task in `caixa benchmark`.
- **Pages:** one per year and author, with cards and an overlay holding the browser's own PDF
  viewer, and `Documents/PDF/PDF.html` with a heat map, years, authors, Unrecognized and To review.
  The index links to it through a generic Chattr slot.
- **In the window:**
  - search by words, the first full-text index in Caixa (FTS5, accents aside), and by meaning
    (passages, an endpoint's embeddings, reciprocal rank fusion);
  - Ask, with checked citations;
  - corrections and tags, batched behind **Update the pages**.
- **People:** authors and people named are linked in `item_people`, and documents are listed on
  person pages through a second generic Chattr slot.

### Hot fixes after the first real imports (2026-11-25)

The maintainer's first import on the Mac, about 150 PDFs, found what the synthetic family had not:

- **`20261125-01` No PDF card in the wizard.** Collectors are found through entry points that pip
  records at install time, and an install from before the branch had none for `pdf`. Caixa's own
  collectors now load whatever the install recorded, and `caixa doctor` says when to install
  again.
- **`20261125-04` numpy.** The import stopped at once: numpy was used but never declared, and the
  container had it from other packages. It is now declared, a test fails on any import that is
  not, and the doctor and the import itself check the packages first. (This ticket was first
  numbered `-01` as well; two sessions had picked the same number.)
- **`20261125-03` One error, one document.** An hour in, a model answered an author's evidence with
  a list, and that one answer ended the job before embedding and drawing. Wrong shapes are now
  retried and reviewed. An unexpected error now stays with its document, or with its stage, which
  becomes a warning while the pages are still drawn.
- **`20261125-02` The session log.** More than 70% of documents ended in Unrecognized, and nothing
  said why. Every document job now writes an owner-only log in `.caixa/logs/sessions/`, with a
  `.jsonl` twin: what each stage decided about each document and why, then counts, reasons and
  times. `caixa documents log` shows it.

### Comparing the models (2026-11-27 and 28)

- **`20261127-01` `caixa documents prepare`.** On a real sample, a PDF's Author property was often
  the program that wrote it (`Brite:Bill`). Reading the page in order and taking the issuer from
  it filed 142 of 201. `prepare <folder> --out <path> --box <box>` does this beside the box,
  writing nothing to it.
  - Preprocessing runs once: reading order, OCR for a text layer that is not words, cover sheets
    skipped.
  - Apple Intelligence and the local model get the same pages and the same instructions.
  - Each model files into its own tree, and a report diffs the two.
- **`20261127-02` Author knowledge.** Gemma was careful: it named the real senders and left
  unreadable scans alone. Apple Intelligence filed almost everything, often under the customer or
  an invented name, and was not meaningfully faster. So corrections, renames and merges now write
  `.caixa/author-knowledge.json` (accepted authors, rejected names, and "use this instead"
  lessons), and `prepare` tells both models what it holds. The box's owner is never rejected.

### Organized file names (2026-11-28)

- **`20261128-01` `prepare --organized`.** Owners who already name their PDFs
  `(YYYY-MM-DD) Subject (Author) [Tag].pdf` keep their names. The name is read with no model, and
  only an impossible date, or one the page clearly contradicts, is replaced. The authors and tags
  in the names become the first whitelist in `.caixa/author-knowledge.json`. `prepare` was made a
  separate command to try PDFs without importing them; its logic is to be folded into the import.

### `prepare` folded into the import (2026-11-28)

`prepare` had been made separate only to try PDFs without importing them. Its logic now lives in
the import, in five tickets (`20261128-02` to `-06`):

- page text in reading order, and one rule for unreadable text;
- cover sheets left out for the model, and the bottom of the last page kept;
- no software names as authors, and a second look when the author or date is missing;
- author knowledge applied at filing and in reconciliation;
- organized names as an import option.

`prepare` itself became the import's dry run. It runs the real import in throwaway boxes, one per
model, and writes `(YYYY-MM-DD) PDF Import Preview.json` at the box's root.

### Decisions (recorded in the Requirements)

- Folders are year and author; category and type are views.
- Names carry no tags.
- A document is applied when confident, otherwise it goes to review.
- PyMuPDF is used, under the AGPL (stated in NOTICE).
- Every record is in the master.
- `Unrecognized/` sits at the root of the PDF folder.
- Author pages are named after the author alone.
- Names are cut after 110 characters.
- OCR is in English by default.
- D26 amended (2026-11-25): the session log may hold extracted values, review reasons and timings;
  evidence quotes and raw replies are opt-in; page text, passages and summaries never.
- D28 (2026-11-27): `prepare` beside the box. D29 (2026-11-27): author knowledge. D30
  (2026-11-28): organized file names, the date the only part ever replaced. D31 (2026-11-28):
  `prepare` folded into the import, and made its dry run.

## Issues we ran into, and what they taught us

### Phase 1.5 - PDF

| Issue | Cause | What we did |
| --- | --- | --- |
| Git's identity in the container was "Claude" again | The container's restart reset it, as in Phase 1.5 | Set to the maintainer before the first commit, and checked at each restart. |
| A failing model made every document wait out its retries | Each document retried on its own | Reading stops after two failures in a row; the rest wait. |
| Undo could not restore a file replaced in place by OCR | Undo followed moves, not rewrites | `undo.keep_file` keeps the earlier copy. |
| A natural question found nothing | Full text asks for every word, including "how" and "was" | Questions match any of their content words. |
| A search could hang for two minutes on a stalled model | The embedding call's timeout was meant for batches | Searches wait 10 seconds, then search by words alone. |
| The docs promised owner-only working copies that did not exist | A requirement with no test | Built, with a test; a privacy test also proves no page text reaches a log. |
| No PDF card in the wizard on the Mac | Entry points are recorded at install time, and the install predated `pdf` | Caixa's own collectors always load; the doctor says to install again. |
| `No module named 'numpy'` on the Mac | numpy used but never declared; the container had it from elsewhere | Declared; a test checks every import; packages checked before an import starts. |
| A real import died an hour in, leaving most documents in Unrecognized | A list where text was expected, and one document's error ended the whole job | Shapes checked; an error stays with its document or stage. |
| 70% of real PDFs in Unrecognized, with no way to see why | Decisions were visible only in the database | The session log. |
| Bills filed under `Brite:Bill` | The PDF's Author property names the program that wrote it | `prepare` takes the author from the page. |
| `prepare` asked Apple Intelligence twice | Automatic chooses Apple for reading | The second run uses the endpoint in Settings. |
| Two sessions gave two tickets the same number | Both picked the next free id on their own copy | One was renumbered (`20261125-04`). |
| A Chattr test passed or failed depending on the computer and the test order | The `missing` test followed the machine's own `~/.chattr.json`, and the rebuild tests wrote one pointing at a pytest folder | Each test has its own home and Chattr folder (merged from `claude/nifty-hawking-u8grqz`). |
| The test suite could hang | `chattr serve` prints its link without flushing, and a test reads it from a pipe | Run with `PYTHONUNBUFFERED=1`; the fix is in the backlog. |



### Phase 1.5, in the order they came up

| Issue | Cause | What we did |
| --- | --- | --- |
| The Apple helper would not build on the maintainer's Mac | An old Swift 5.0.3 toolchain selected by `TOOLCHAINS` | Build with `xcrun swift`, drop `TOOLCHAINS`, require Swift 6.2, say which version was found. |
| New index features (chevrons) did not appear | The browser cached the page; pages drawn by an older Caixa kept their old contents | Pages carry the fingerprint of what drew them and are redrawn on opening; each opening uses a fresh address. |
| A category change was sometimes undone | A redraw re-applied `owner.json` while people were being sorted, reading its previous version | Caixa no longer re-applies a version of the file it wrote itself, except when opening a box or resetting. |
| A larger mbox stopped with `UnicodeEncodeError … surrogates not allowed` | Bytes the mail's charset could not explain arrive as stand-in characters that UTF-8 refuses | Recover them (UTF-8, else Windows-1252), "�" only when nothing fits; headers read from their raw form; the database repairs any record. |
| Deleted people came back in Unrecognized | Removal left mail alone (a Phase 1 rule), so their threads were filed under their bare address | First fix deleted their mail; **that was the wrong rule** (the maintainer wants every mail kept) and was reverted before it reached the box. Now their mail stays under `People/Removed/Mail/<Account>/` and no tile comes back. |
| The calendar between years made long pages unusable | One calendar per year inside the messages | One calendar block at the top, a fold per year (a stopgap until person pages are redesigned). |
| Dropping one person on another did nothing in Safari | Their mail threads still named them as home, so the database refused to forget them (a foreign key); a drop on someone unnamed was refused | Mail threads follow a merge and let go on delete; `people.join` merges anywhere; failures shown in a dialog. |
| A mail import stopped with a voicemail error | Two workers storing the same attachment used one temporary file; Chattr blamed every missing file on voicemail | A temporary file per writer; the real file named in the message. |
| Changes could be made faster than Caixa drew them | Nothing showed the redraws running | A work bar that says what Caixa is doing and pauses changes; later replaced, for people changes, by batching. |
| The work bar unlocked too early, or let a second change in | A look at the queue begun before a change ended; a change chaining a step before its first request | Each change waits for its own job; a stale look is repeated; a change holds the lock from its first step. |
| Sorting one person took minutes on 48,000 pages | Every change redrew everything; the Workers setting was invisible | The redraw work above; batching; Workers in Settings. |
| Naming a number then deleting that person left the number | With batching, the name was never drawn into the archive before the delete | Deleting records the person's numbers and addresses too. |
| 17 commits were authored as "Claude" instead of the maintainer | A restart of the development container reset git's identity, and nobody checked it | Found at the release; the commits were re-authored as the maintainer (same contents and dates) and the branches force-pushed with the maintainer's agreement. |

### Patterns worth remembering

- **Real data finishes the design.** Both projects doubled their ticket count after the first real
  export. Plan for a hot-fix wave, and add every case real data shows to the synthetic fixtures.
- **Ask before changing what a person keeps.** The one revert of this project came from deciding
  what "delete" meant for mail without asking. When a change removes data, confirm the rule first.
- **Test the path the product uses.** Two bugs (the merge foreign key, the mail-only people) hid
  because tests built boxes a shortcut way that skipped the step that records mail homes. Tests now
  go through the same import the window uses.
- **Concurrency needs its own tests.** The attachment race and the work bar's polling races were
  found by forcing the interleaving in a test (a second writer finishing first; a check begun
  before a change ended).
- **Measure before optimizing.** The redraw's real costs (character-by-character escaping, path
  resolution) were not where intuition put them; profiling found them, and a benchmark script kept
  the numbers honest.
- **Check who is committing.** After any restart of the development environment, check
  `git config user.name` before the first commit: the authorship rule depends on it.
- **Browser-only behaviour needs a browser.** Safari's drag-and-drop could not be tested here
  (Chromium only); the maintainer's testing on Safari was the check.
- **Install the way the user does.** The development container hid two install bugs: numpy came
  with other packages, and a fresh `pip install -e` recorded the new entry points. Test the
  install script in a fresh environment, and run it again after every pull.
- **Make decisions visible before tuning them.** The session log turned "most documents are in
  Unrecognized" into reasons that could be counted, and `prepare` turned a hunch about the models
  into a diff.

---

## Where things stand

- **Version** 0.5.1 (Phase 1.5's release, tagged `v0.5.1`; Phase 1 was 0.5.0); Chattr 2.0.0.
  Phase 1.5 - PDF is built on its branch and not yet released.
- **Tests**: 2,208 Python tests at the last full run (before the dry run's ticket; the full suite
  is run at the end, when the maintainer asks), Caixa's and Chattr's, all passing (run with
  `PYTHONUNBUFFERED=1`); 286 tests of the window (unit and end-to-end against the real
  `caixa serve` in Chromium).
- **Tried on real data by the maintainer**: iMessage, Messenger, Google Voice, iPhone voicemail, Mac
  Contacts, a local translation endpoint, Apple Intelligence, and now mail: real mboxes of growing
  size, in a box of 48,000 pages. PDF documents: real imports of about 150 PDFs, and `prepare`
  comparing Apple Intelligence with Gemma.
- **Not yet tried on real data**: WhatsApp, Instagram, a vCard file, the faster-whisper backend,
  Windows, the Chattr mirror workflow, and parts of PDF documents (Safari's overlay, search by
  meaning, Ask, documents on person pages, with real data).

## Backlog

Items to plan into future projects. Each names where it came from.

### Next projects (Stage 1.5 and beyond)

- **PDF support**: built in Phase 1.5 - PDF, with hot fixes from the first real imports; release
  once the maintainer's trial on the Mac is done.
- **The bake-off** between Apple Intelligence and the local models, scored from `prepare`'s
  reports and the session log's `.jsonl`, which first needs each document's item id (Phase 1.5 -
  PDF, `20261125-02`). Then: vision, and a memory of past layouts, for `prepare`.
- **Tune the preprocessing on real PDFs** (Phase 1.5 - PDF, D31): the unreadable-text rule, the
  cover-sheet rule (a first page under 40 letters counts as a cover for the model), and the
  instructions, using the dry run's preview to compare.
- Financial transactions from statements and bills, cheques linked to bills (the PDF draft's phase
  7); other document formats, each with its own collector (Phase 1.5 - PDF).
- Photos and home videos as their own domain; Obsidian vaults (Stage 1.5).
- **Person page redesign**: the calendar at the top is a stopgap (Phase 1.5, `20261123-02`).
- Further message sources: Slack, Telegram, Google Chat (Phase 1).
- Stage 2: the search index, the personal model and the heirs' "Ask" experience.
- Stage 3: presentation mode (read-only, its own port) and a Docker image; Phase 1 laid the ground
  (`caixa worker --read-only`).
- Live mail accounts (IMAP, the Gmail API) and other mail formats (Maildir, PST, folders of `.eml`)
  were out of scope for Phase 1.5.

### Improvements carried forward

- From Phase 1.5 - PDF:
  - Apple Intelligence's guided generation (a JSON schema) and Apple's `NLContextualEmbedding` in
    the Swift helper;
  - whether Ghostscript is needed;
  - documents for box people who have no messages, and so no person page (with the person page
    redesign);
  - search across mail and messages, using the same `chunks` table (Stage 2);
  - `chattr serve` should flush the link it prints, so its test needs no `PYTHONUNBUFFERED`.

- **Names from the To line**: mail the owner sent to someone who never wrote back is filed under
  their address, though the To line names them (Phase 1.5, `20261123-05`).
- **Before Update, only categories show at once**: a merge or a new name appears on the people page
  after **Update the pages**; it could be shown at once, as categories are (`20261123-11`).
- **Redraws on very large boxes**: a full update still builds every page's data to see which
  changed, each worker loads the whole archive, and a people-page-only update loads it once. A
  record of which pages each change touches would let an update build only those (`-09`, `-11`).
- **Live updates instead of polling**: the people page asks for the job list every 0.7 s while busy;
  the service already sends events (`/api/caixa/events`) that could drive the bar.
- **Safari in the browser tests**: only Chromium runs here; WebKit would catch drag-and-drop
  differences (`20261123-03`).
- **Typing and lint**: `mypy` stops on a numpy stub in the development environment and keeps four
  older notes in `caixa/apple_intelligence.py`, `translation.py` and `summaries.py`; the project has
  no `ruff` configuration of its own, so its default rules flag older code.
- **A person named "Removed"** would share the `People/Removed/` folder name with the kept mail of
  removed people (their own page stays separate).
- **Signature images**: the size under which a repeated inline image counts as a signature is still
  to be set from real mail (Phase 1.5 open question).
- **Undo after Reduce** leaves the reduced mails only in the source they were reduced from (known,
  explained in the dialog).

### To confirm with the maintainer (from Phase 1)

- The Google Voice forwarded-copy rule (ten minutes, exact words): keep or remove once a full Google
  Voice import shows whether it finds any.
- Choices marked "NEEDS MAINTAINER CONFIRMATION" in Phase 1's tickets: `.caixa/owner.json` as the
  preference file; the open-page button in Unassigned; one reused window for box pages; "Sent,
  recipient not recorded" for iMessages that name nobody; the sign-in link valid until Caixa stops;
  original HEIC/PNG not kept beside the JPEG; voicemail audio at 16 kbit/s; three undo snapshots.
- Real-data trials still to do: WhatsApp, Instagram, a vCard, faster-whisper, Windows, and the
  Chattr mirror (it needs the `CHATTR_MIRROR_TOKEN` secret and runs on every push to `main`).

## Next

**Finish trying Phase 1.5 - PDF on the Mac**, following the testing guide in its completion report;
run `tools/install.sh` again after every pull. Then the bake-off, any further hot fixes, the merge
into `working`, and the release. After that, the next Stage 1.5 project: a briefing, then the
architecture conversation and Requirements, as for every project.
