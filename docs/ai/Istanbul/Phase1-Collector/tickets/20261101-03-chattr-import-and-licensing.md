---
id: 20261101-03-chattr-import-and-licensing
title: Chattr import and licensing
type: chore
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-01
closed:
notes: Breakdown item 3.
parent:
depends_on:
- 20261101-01-caixa-repository-foundations
subtasks: []
plan_status: in-progress
current_task: T01
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

Status: in-progress
Current task: T01

This ticket is import, review and licensing work, with no new production code. Per bora-tdd's
config/docs exception, each task's Verify command is the gate.

### T01: Import Chattr with its purged history

- `git subtree add --prefix=tools/chattr https://github.com/tonyknight/chattr main` (no
  `--squash`), with a ticket-format merge message.
- `pyproject.toml`: add `extend-exclude = "tools/chattr"` under `[tool.black]` until ticket 04
  formats Chattr (ticket 04 removes it).
- Verify: `test -f tools/chattr/main.py && git log --oneline -- tools/chattr | grep -c . && test "$(git log -p -- tools/chattr | grep -c 'sk-or-v1-')" = 0 && test "$(git log --name-only --format= -- tools/chattr | grep -cE '\.db$|/\.idea/')" = 0 && python -m pytest -q && python -m black --check .`
- [ ] done

### T02: Review Chattr's iMessage code for imessage-exporter (GPL-3.0) derivation

- Compare `tools/chattr/src/parsers/imessage_database_parser.py` and
  `tools/chattr/src/imessage_tools.py` with imessage-exporter's source (read-only clone in the
  session scratchpad): structure, naming, algorithms and output formats beyond public
  database-schema facts.
- Record findings per file and function in this ticket's Notes. Flag every part that looks
  derived, and its replacement path (ticket 07 rewrites the iMessage reader).
- Verify: the Notes contain a dated "License review" entry covering both files, with a verdict
  per flagged part.
- [ ] done

### T03: MIT license for Chattr

- `tools/chattr/LICENSE`: MIT, "Copyright (c) 2025-2026 Tony Knight". If T02 found derived
  code, add `tools/chattr/NOTICE` naming the affected files and their pending rewrite (ticket 07)
  so the license status is honest until then.
- Chattr `README.md`: a License section.
- Verify: `grep -q "MIT License" tools/chattr/LICENSE && grep -qi "license" tools/chattr/README.md`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
