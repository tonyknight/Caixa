---
id: 20261101-02-synthetic-fixture-family
title: Synthetic fixture family
type: feature
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 2.
parent: null
depends_on:
- 20261101-01-caixa-repository-foundations
subtasks: []
---

## Description

Build a fictional family's synthetic exports for every Phase 1 source, used by all tests. No real data, ever.

## Acceptance criteria

- [ ] A builder script creates a synthetic iMessage `chat.db` (long attributedBody messages, both epoch formats, same-second attachments, tapbacks on attachments, a group chat)
- [ ] WhatsApp exports in iOS and Android formats with media and 'media omitted' lines
- [ ] Messenger/Instagram JSON with mojibake text, shares and attachments
- [ ] An MBOX with RFC 2047 headers, HTML-only mail, attachments and threads
- [ ] A Google Voice Takeout sample (texts, calls, voicemails with audio) and iPhone voicemail audio + metadata
- [ ] A vCard file linking the family's handles
- [ ] Fixtures are generated deterministically and contain only fictional names and numbers

## Context

Phase1-Collector Tasks Breakdown item 2. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Acceptance criteria; Testing requirements.

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
