---
id: 20261120-02-mail-index-and-parallel-reading
title: "Mail index and parallel reading"
type: feature
priority: high
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-01-synthetic-mail-fixtures
subtasks: []
---

## Description

Read an `.mbox` (or each `.mbox` in a `.zip`) into `.caixa/mail/index.sqlite` without importing
anything: byte ranges, a SHA-256 of each mail's bytes, headers and thread keys, never bodies in
memory. Split at mail boundaries across up to 12 worker processes; a zip is one stream feeding the
workers. Sources remember their lineage and account.

## Acceptance criteria

- [ ] `index.sqlite` with `sources`, `mails` and `senders` as in *Data model*; readable only by the owner
- [ ] Plain and zipped mboxes, folders holding them, and Takeout zips with several `.mbox` are read with progress and cancel
- [ ] Reading again a file already read (same size, time and first-megabyte hash) is instant
- [ ] The **account** is a required name at read time; a Cleaned or Reduced file gets its parent's
- [ ] A box setting **Workers** (processor count, at most 12); 1 and 12 workers give the same index
- [ ] Memory stays under 500 MB on the generated multi-gigabyte mbox; 12 workers are faster than 1 (slow test)
- [ ] Service method(s) `mail.read`/`mail.status` and `caixa mail read <path> --account NAME`

## Context

Phase 1.5 - Mbox Tasks Breakdown item 2. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Components* (Mail index), *The mbox family*, *Data model*, *Workers*; M1–M3. Phase 1's `chattr/parsers/mbox_parser.py` has the header decoding and thread-key logic to reuse; it reads the whole file into memory, which this must not.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: draft
Current task:

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
