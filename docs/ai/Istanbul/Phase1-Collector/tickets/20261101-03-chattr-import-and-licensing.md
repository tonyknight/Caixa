---
id: 20261101-03-chattr-import-and-licensing
title: Chattr import and licensing
type: chore
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 3.
parent: null
depends_on:
- 20261101-01-caixa-repository-foundations
subtasks: []
---

## Description

Bring Chattr into Caixa with its purged history and settle its license.

## Acceptance criteria

- [ ] `git subtree add --prefix=tools/chattr` imports Chattr `main` (0152912) with full history
- [ ] `src/parsers/imessage_database_parser.py` and `src/imessage_tools.py` are reviewed for code derived from imessage-exporter (GPL-3.0); findings recorded in this ticket's Notes and any derived parts flagged for rewrite
- [ ] Chattr carries an MIT `LICENSE`
- [ ] No `.db`, key material or IDE files enter Caixa's history

## Context

Phase1-Collector Tasks Breakdown item 3. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — Licensing; Components (Chattr).

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
