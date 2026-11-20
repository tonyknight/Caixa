---
id: 20261120-15-retire-the-blind-mail-import-documentation
title: Retire the blind mail import; documentation
type: chore
priority: medium
status: done
created: 2026-11-20
updated: 2026-11-20
closed: 2026-11-20
notes: 'Done: whole-mbox import refused with directions; guide, README and first-mbox
  checklist.'
parent:
depends_on:
- 20261120-05-the-clean-mail-window
- 20261120-07-the-sort-mail-window
- 20261120-13-reduce
subtasks: []
plan_status: done
---
## Description

Retire Phase 1's blind mail import and document the new mail workflow.

## Acceptance criteria

- [ ] The import wizard's Mail card opens Clean mail / Sort mail; no collector imports a whole mbox
- [ ] `caixa import mail` replaced by `caixa mail read | clean | keep | senders | choose | ignore | import | reduce`; the worker protocol description lists the `mail.*` methods
- [ ] `docs/Documentation/Collector.md` (Mail) and `README.md` (box layout, collectors, status) describe the workflow
- [ ] A checklist for the maintainer's first real mbox (clean, sort, import, reduce, what to report)

## Context

Phase 1.5 - Mbox Tasks Breakdown item 15. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: M14; Tasks Breakdown item 15.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** the Mail collector stays (the wizard shows its card, which opens Clean mail, and the
`mail-import` job runs it on the chosen conversations), but nothing imports a whole mbox any more:
`import.preview` and `import.start` refuse the `mail` collector with a sentence that says what to
do instead (Clean mail and Sort mail, or `caixa mail …`), and so does `caixa import mail`. The
documentation describes the workflow as it is today: `docs/Documentation/Collector.md`'s Mail
section (read, clean, sort, import, reduce, sample; accounts; the Cleaned and Reduced files; what
is kept in `owner.json`; what comes later with the conversation pages and summaries), a checklist
for the first real mbox, and `README.md` (the collectors table, the command line, the worker's
methods, where the project is).

### T01: No whole-mbox import

- `caixa/service.py`, `caixa/cli.py`; `tests/test_service_jobs.py` (its progress test uses the
  WhatsApp fixture instead of mail).
- Tests (`tests/test_mail_service.py`): `import.preview` and `import.start` with `mail` are refused
  with the way to do it; `caixa import mail` says the same and imports nothing.
- Verify: `python -m pytest -q tests/test_mail_service.py tests/test_service_jobs.py tests/test_cli_commands.py`
- [x] done

### T02: The documentation and the checklist

- `docs/Documentation/Collector.md` (Mail, and the first-real-mbox checklist), `README.md`.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** no whole-mbox import any more: `import.preview`, `import.start` and `caixa import
  mail` refuse the mail collector and say what to do instead; the wizard's Mail card opens Clean mail
  (ticket 05). The guide's Mail section describes read, clean, sort, import and reduce with their
  commands, accounts, the Cleaned and Reduced files, what `owner.json` keeps, what comes next, and
  `caixa mail sample`, with a checklist for the first real mbox; the README's collectors table,
  command line and status table are brought up to date.
- **Files:** changed `caixa/service.py`, `docs/Documentation/Collector.md`, `README.md`, tests
  (`test_mail_service`, `test_service_jobs`, `test_cli_commands`, `e2e-browse`).
- **Errors:** three tests used the whole-mbox import only as a convenient source (progress order,
  command line against service, Browse); they use other sources or the mail workflow now.
- **Verify:** `python -m pytest -q` → 1396 passed, 1 skipped, 1 deselected; black, mypy, tsc clean;
  `vitest run` → 248 passed. The guide's synthetic-data mail commands were run by hand.

## Review

### 2026-11-20: eba934c..HEAD (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** the guide's "What you get, for now" describes Phase 1's mail pages; it must be rewritten
  with tickets 10 to 12 (the conversation pages, the overlay, summaries).
- **Minor:** `chattr-cli convert mail` still imports a whole mbox into Chattr on its own, as agreed
  (Chattr stands alone).
- **Spec:** M14 met.
- **TDD:** RED then GREEN for T01; T02 is documentation, verified by the suite and by hand.
- **Commits:** `{ticket-id} {task-id}: {title}`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: import.preview and import.start refuse the mail collector with directions (Clean mail from the Mail card, or caixa mail read|clean|senders|import); caixa import mail prints the same and imports nothing. The Mail collector stays for the mail-import job and the wizard's card. Two tests that used mail only as one source among others now use WhatsApp (progress order) and iPhone voicemail (command line against service).

### 2026-11-20
T02: docs/Documentation/Collector.md Mail section rewritten (the five steps with their commands, accounts, Cleaned and Reduced files, owner.json, what comes next, caixa mail sample) with a first-own-mbox checklist; the synthetic-data walkthrough uses mail read, choose, import (run by hand: 4 mails in 2 conversations). README: collectors table, the mail commands, the status table (Mail without the noise), the browser interface line. e2e-browse brought mail in with the old import; it now reads, chooses and imports through the mail workflow.
