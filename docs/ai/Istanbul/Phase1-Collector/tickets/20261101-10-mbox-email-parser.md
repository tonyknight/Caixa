---
id: 20261101-10-mbox-email-parser
title: MBOX email parser
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: threads, headers, bodies, attachments by hash; names need confirmation.'
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Parse MBOX email (Gmail Takeout) into the unified schema.

## Acceptance criteria

- [x] Threads by Message-ID / In-Reply-To / References and Gmail thread ID
- [x] RFC 2047 headers decoded; HTML and plain bodies kept
- [x] Attachments stored by hash

## Context

Phase1-Collector Tasks Breakdown item 10. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F1; F4.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `MboxParser(BaseParser)` reads an MBOX with the standard library `mailbox` and
`email` (default policy, so RFC 2047 headers and charsets decode themselves) and returns
`ConversationBatch`es: one conversation per mail thread. `ConversationBatch` moves to a shared
`parsers/batch.py` (the iMessage parser re-exports it), the shape ticket 20's collector contract
will generalize. The sender's own UTC offset from the `Date` header is kept (aware datetime), so
the stored time carries it. Attachments are stored by content hash.

**Names to confirm with the maintainer** (not defined in the Requirements): the service is
displayed as `Mail`, its CLI key is `mail`, its folder `Output/Mail/`. Recorded in the ticket
Notes.

### T01: Messages: headers, dates, bodies

- RFC 2047 headers decoded (From, To, Cc, Subject); sender address and display name kept apart.
- Plain and HTML bodies both kept: `body` is the plain text (derived from the HTML when the mail
  is HTML-only), the HTML stays in `service_specific.body_html`.
- `Date` keeps the sender's offset; an unparseable or missing date falls back to the mbox `From `
  line (UTC) and is marked assumed.
- `source_id` is the normalized Message-ID (a hash of the headers when it is missing); duplicate
  Message-IDs collapse, merging Gmail labels.
- Headers kept in `mail_headers`: message id, in-reply-to, references, Gmail thread id, labels,
  subject, to, cc, bcc.
- Tests: the fixture mbox, plus generated edge cases.
- Verify: `python -m pytest -q tools/chattr/tests/test_mbox_parser.py`
- [x] done

### T02: Threads and attachments by hash

- Threads: Gmail `X-GM-THRID` when present, else the root of the `References`/`In-Reply-To` chain
  (stable even when the root mail isn't in the file). Conversation named by the subject without
  `Re:`/`Fwd:`; more than two participants make a group; participants are the addresses on the
  mails.
- Attachments (and inline files, forwarded mails) are written to `<store>/<hh>/<sha256><ext>` once
  per content (`blobs.store_by_hash`), recorded with filename, type, size and path.
- Tests: Gmail threads, header-only threads (missing root), unrelated mail, attachment bytes
  intact and stored once.
- Verify: `python -m pytest -q tools/chattr/tests/test_mbox_threads.py`
- [x] done

### T03: Import and `chattr-cli convert mail`

- `commands.convert(..., "mail", ...)` and `chattr-cli convert mail <file.mbox>`; central route
  (default) or `--json`; `--attachments-dir` (default `Output/Mail/Attachments`), `--owner` (name
  or address), `--aliases`, `--html`.
- `Mail` service defaults, output folder and state; menu entry.
- Tests: fixture import (conversations, offsets stored, attachment path, content type `email`),
  idempotent re-import, owner flag, subcommand, JSON route.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `chattr-cli convert mail <file.mbox>` imports an MBOX (Gmail Takeout or any
  other) into the central archive: one conversation per mail thread (Gmail thread id, else the root
  of the References chain), each mail an `email` message with decoded headers, plain and HTML
  bodies, the sender's own UTC offset, Message-ID based stable ids, and attachments stored once
  under their content hash (default `Output/Mail/Attachments/`). Re-importing changes nothing.
- **Files:**
  - New: `parsers/mbox_parser.py`, `parsers/batch.py`, `blobs.py`, `defaults/Services/Mail.json`.
  - Changed: `commands.py` (`_convert_mail`, shared page writer), `cli.py`, `preflight.py`,
    `importing.py`, `parsers/imessage_parser.py` (shared `ConversationBatch`).
  - Tests: `test_mbox_parser`, `test_mbox_threads`, `test_mbox_import`, plus the menu.
- **Errors:** none in existing code. Decisions with consequences:
  - Names the Requirements don't define (service "Mail", key `mail`, folder `Output/Mail/`)
    need the maintainer's confirmation.
  - A mail with no Message-ID gets `nomid-<hash>`, stable for identical content only.
- **Verify:** `python -m pytest -q` → 327 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: 04d9d69..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** the fixture mbox is synthetic; Gmail Takeout details (`X-GM-THRID`, `X-Gmail-Labels`,
  `From ` line quoting, very large files) are from the format's documentation, not from a real
  export. Check against a real Takeout.
- **Minor:** a thread's key can change between exports (a later export gains the Gmail thread id,
  or the missing root mail), which would file the same mails under a new conversation; message ids
  include the conversation id. The Caixa master (ticket 18) should key mail by Message-ID alone.
- **Minor:** `is_from_owner` is true only when the owner is the sender; recipients are not
  linked to people yet (ticket 14).
- **Minor:** HTML is stored as given (not sanitised) in `service_specific.body_html`; the
  renderer (ticket 15) must escape or sandbox it.
- **Minor:** an mbox's `Status`/`X-Status` flags (read, starred) and other mail clients' labels are
  not recorded; only Gmail's `X-Gmail-Labels` are.
- **Minor:** two threads with the same subject and date span would write the same HTML page name
  (the second overwrites the first).
- **Minor:** the whole mbox is read message by message (`mailbox` keeps an index in memory); a
  50 GB Takeout may need a streaming pass.
- **Spec:** all three acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN for every task (collection errors, then passing).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
NEEDS MAINTAINER CONFIRMATION: names not defined in the Requirements: service display name 'Mail', CLI key 'mail', output folder 'Output/Mail/', attachment store default 'Output/Mail/Attachments/<hh>/<sha256><ext>'. Chosen to match the box layout's 'Mail/' folder; trivial to rename.

### 2026-11-02
T01: MboxParser reads the mbox with mailbox + the default email policy (decoded headers and charsets). The sender's own UTC offset from the Date header is kept (aware datetime) so it reaches tz_offset_minutes. A '-0000' date (zone unknown) or a missing/unparseable date is marked tz_assumed; the latter falls back to the mbox From_ line. Message-ID is normalized (no brackets, lower case); a mail without one gets 'nomid-<hash>' of sender/time/subject/body. Duplicate Message-IDs collapse with labels merged. ConversationBatch moved to parsers/batch.py. Until T02 the whole file is one batch.

### 2026-11-02
T02: threads: Gmail X-GM-THRID when present ('gmail:<id>'), else the root of the References/In-Reply-To chain ('msgid:<root>'; stable when the first mail is missing from the file; reference cycles stop). Subject prefixes (Re/Fwd/Aw/Sv/…) stripped for the thread name; >2 addresses on From/To/Cc make a group. Known limitation: a thread key can change if a later export adds a Gmail thread id or the missing root, which would re-file mails (message ids include the conversation id). New blobs.store_by_hash (<hh>/<sha256><ext>, written atomically, suffix sanitised) keeps attachments, inline files and forwarded mails exactly once; without an attachments_dir they are hashed but not kept.

### 2026-11-02
T03: convert mail wired (central default, --json, --html per thread, --attachments-dir default Output/Mail/Attachments, --owner by address or name, --aliases). Mail service defaults, Output/Mail and state added; the menu offers 'Mail (MBOX)' as choice 5 (iMessage stays 4). The per-thread HTML writer is shared with iMessage.
