---
id: 20261101-03-chattr-import-and-licensing
title: Chattr import and licensing
type: chore
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 3.
parent:
depends_on:
- 20261101-01-caixa-repository-foundations
subtasks: []
plan_status: done
---
## Description

Bring Chattr into Caixa with its purged history and settle its license.

## Acceptance criteria

- [ ] `git subtree add --prefix=tools/chattr` imports Chattr `main` (0152912) with full history
- [ ] `src/parsers/imessage_database_parser.py` and `src/imessage_tools.py` are reviewed for code derived from imessage-exporter (GPL-3.0); findings recorded in this ticket's Notes and any derived parts flagged for rewrite
- [ ] Chattr carries a GPL-3.0-or-later `LICENSE` and a `NOTICE` attributing the parts derived from imessage-exporter (decision 2026-11-02, replacing the original MIT plan)
- [ ] No `.db`, key material or IDE files enter Caixa's history

## Context

Phase1-Collector Tasks Breakdown item 3. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — Licensing; Components (Chattr).

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

This ticket is import, review and licensing work, with no new production code. Per bora-tdd's
config/docs exception, each task's Verify command is the gate.

### T01: Import Chattr with its purged history

- `git subtree add --prefix=tools/chattr https://github.com/tonyknight/chattr main` (no
  `--squash`), with a ticket-format merge message.
- `pyproject.toml`: add `extend-exclude = "tools/chattr"` under `[tool.black]` until ticket 04
  formats Chattr (ticket 04 removes it).
- Verify: `test -f tools/chattr/main.py && git log --oneline -- tools/chattr | grep -c . && test "$(git log -p -- tools/chattr | grep -c 'sk-or-v1-')" = 0 && test "$(git log --name-only --format= -- tools/chattr | grep -cE '\.db$|/\.idea/')" = 0 && python -m pytest -q && python -m black --check .`
- [x] done

### T02: Review Chattr's iMessage code for imessage-exporter (GPL-3.0) derivation

- Compare `tools/chattr/src/parsers/imessage_database_parser.py` and
  `tools/chattr/src/imessage_tools.py` with imessage-exporter's source (read-only clone in the
  session scratchpad): structure, naming, algorithms and output formats beyond public
  database-schema facts.
- Record findings per file and function in this ticket's Notes. Flag every part that looks
  derived, and its replacement path (ticket 07 rewrites the iMessage reader).
- Verify: the Notes contain a dated "License review" entry covering both files, with a verdict
  per flagged part.
- [x] done

### T03: GPL-3.0-or-later license and attribution for Chattr

Rewritten 2026-11-02 after T02 found derived code and the maintainer chose GPL-3.0-or-later for
Chattr and Caixa (the original MIT plan is replaced).
- `tools/chattr/LICENSE`: the verbatim GNU GPL v3 text (from imessage-exporter's `LICENSE`, which
  is the FSF text).
- `tools/chattr/NOTICE`: Chattr's copyright (© 2025-2026 Tony Knight), licensed
  GPL-3.0-or-later; attribution of the derived parts (diagnostics tool, message-query structure,
  tapback GUID parsing, one comment) to imessage-exporter, © Christopher Sardegna,
  GPL-3.0-or-later; other schema knowledge learned from studying it.
- Correct the "port" wording to say accurately what was derived and what was learned:
  `docs/MIGRATION_SUMMARY.md`, `docs/iMessageConversionReadMe.md`, and the docstrings in
  `src/parsers/imessage_database_parser.py` and `src/imessage_tools.py`.
- Chattr `README.md`: a License section (GPL-3.0-or-later, pointing to `NOTICE`).
- Verify: `grep -q "GNU GENERAL PUBLIC LICENSE" tools/chattr/LICENSE && grep -q imessage-exporter tools/chattr/NOTICE && ! grep -rniE "port of the rust|convert rust" tools/chattr/docs tools/chattr/src && grep -q "GPL-3.0-or-later" tools/chattr/README.md && python -m pytest -q && python -m black --check .`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-01
T01 verified. Path-limited 'git log -- tools/chattr' only shows the merge commit (Chattr's commits touched paths at its own root), so history was checked on the merge's second parent: a09ccfa^2 = 0152912 with all 8 Chattr commits. Whole-history scans: 0 .db/.idea files; the only 'sk-or-v1-' match is this ticket's own grep pattern (no key). pytest 2 passed; black clean with tools/chattr excluded.

### 2026-11-02
License review (T02). Compared tools/chattr against imessage-exporter (GPL-3.0-or-later, Christopher Sardegna) at tags 2.8.0, 3.1.0 and HEAD 47b7514; the diagnostics output matches 2.x specifically ([1/4] cache steps), so the translation came from a 2.x checkout. Engineering assessment, not legal advice. DERIVED (C): src/imessage_tools.py:126-386 DatabaseDiagnostics (banners, section order, ~15 output lines verbatim, copied COUNT(DISTINCT person_centric_id) quirk, converter check order; includes _resolve_attachment_path :361-374); src/parsers/imessage_database_parser.py:728-784 and :953-964 (message query structure, aliases, column order, newest-schema-first fallback); :1064-1075, :1250-1267, :1311-1322 (p:N/GUID tapback parsing); :440 (copied comment). INFLUENCED (B): dataclass field order :197-265; TAPBACK_TYPES :272-281 and Tapback action/index; attributedBody heuristic :564-667; _generate_chat_name :508-555; _get_sender_name :678-689; _format_file_size imessage_tools.py:376-386. INDEPENDENT (A): timestamps, group detection :453-506, vCard/phonenumbers contacts, MessageSpamFilter, batch/parallel processing, tapback SQL, other imessage_tools.py utilities and the attachment report. Chattr's docs describe it as a port (MIGRATION_SUMMARY.md:10/17/94, iMessageConversionReadMe.md:252-262; docstrings parser:509, tools:135,160). CONCLUSION: Chattr contains code derived from GPL-3.0-or-later work, so it must be distributed under the GPL. Maintainer decision 2026-11-02: Chattr and Caixa both become GPL-3.0-or-later; keep the code; keep the full-history import.
