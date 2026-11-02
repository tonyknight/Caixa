---
id: 20261101-10-mbox-email-parser
title: MBOX email parser
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 10.
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T01
---
## Description

Parse MBOX email (Gmail Takeout) into the unified schema.

## Acceptance criteria

- [ ] Threads by Message-ID / In-Reply-To / References and Gmail thread ID
- [ ] RFC 2047 headers decoded; HTML and plain bodies kept
- [ ] Attachments stored by hash

## Context

Phase1-Collector Tasks Breakdown item 10. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F1; F4.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

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
- [ ] done

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
- [ ] done

### T03: Import and `chattr-cli convert mail`

- `commands.convert(..., "mail", ...)` and `chattr-cli convert mail <file.mbox>`; central route
  (default) or `--json`; `--attachments-dir` (default `Output/Mail/Attachments`), `--owner` (name
  or address), `--aliases`, `--html`.
- `Mail` service defaults, output folder and state; menu entry.
- Tests: fixture import (conversations, offsets stored, attachment path, content type `email`),
  idempotent re-import, owner flag, subcommand, JSON route.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
NEEDS MAINTAINER CONFIRMATION: names not defined in the Requirements: service display name 'Mail', CLI key 'mail', output folder 'Output/Mail/', attachment store default 'Output/Mail/Attachments/<hh>/<sha256><ext>'. Chosen to match the box layout's 'Mail/' folder; trivial to rename.
