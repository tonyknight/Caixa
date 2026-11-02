---
id: 20261101-06-interactive-menu-and-command-line
title: Interactive menu and command line
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 6.
parent:
depends_on:
- 20261101-04-chattr-stabilization
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The step-by-step terminal menu plus an equivalent non-interactive command line for every action.

## Acceptance criteria

- [ ] Waterfall menu: services → central DB or service folder → optional HTML, with overridable defaults
- [ ] `chattr-cli convert <service> <export> [--root] [--db|--json] [--contacts] [--aliases] [--html]`
- [ ] Restored iMessage flags: `--region`, `--attachment-root`, `--batch-size`, `--verbose`, `--attachment-workers`
- [ ] Every menu action can be performed non-interactively

## Context

Phase1-Collector Tasks Breakdown item 6. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Key flows — Standalone Chattr; F12.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** today each menu action mixes `input()` prompts with the work. The work moves into
plain functions in `src/chattr/commands.py`. The step-by-step menu and the `chattr-cli`
subcommands both call those same functions, so every menu action has a non-interactive
equivalent by construction.

**Routes** (from Chattr's output strategy):
- **central archive** (default): `Database/chattr.sqlite`, with HTML in `Output/Chattr/`;
- **service folder**: JSON (and optional HTML) in `Output/<Service>/`, without touching the
  central archive.

iMessage writes its native JSON; iMessage import into the central archive is ticket 07.

### T01: Commands for WhatsApp and Messenger, and HTML

- `commands.convert(settings, service, export, route="central"|"service", html=False, owner=None, aliases=None)`
  parses the export and then, by route:
  - central: imports into the central archive;
  - service: imports into a temporary database and writes JSON to `Output/<Service>/`.

  Optionally it writes HTML.
- `commands.generate_html(settings, out=None, owner=None)` renders the central archive.
- `--aliases FILE` (identifier → person name) sets sender names; full people resolution is
  ticket 14.
- Tests: central route updates the database and state; service route writes JSON and leaves the
  central archive empty; HTML is written.
- Verify: `python -m pytest -q`
- [x] done

### T02: iMessage commands with the restored options

- `commands.convert_imessage(settings, db_path=None, out=None, contacts=None, region="US", attachment_root=None, batch_size=1000, attachment_workers=4, workers=None, spam_mode=None, chat=None, limit=None, verbose=False)`:
  native JSON to `Output/iMessage/`.
- `commands.list_chats(db_path)`; `commands.doctor(db_path, check="info"|"connection"|"spam")`.
- Defaults come from `services.imessage.preferences`.
- Tests against the synthetic `chat.db`: JSON written with messages; chats include
  "Costa Family"; every doctor check runs.
- Verify: `python -m pytest -q`
- [ ] done

### T03: Non-interactive subcommands

- `chattr-cli [--root DIR] convert <service> <export> [--db | --json] [--html] [--owner NAME] [--contacts FILE] [--aliases FILE]`.
- iMessage flags on `convert imessage`: `--region`, `--attachment-root`, `--batch-size`,
  `--verbose`, `--attachment-workers`, plus `--workers`, `--spam-mode`, `--chat`, `--limit`.
- Also `chattr-cli html [--out] [--owner]`, `chattr-cli chats [<chat.db>]` and
  `chattr-cli doctor [<chat.db>] [--check …]`. With no subcommand, the menu runs.
- Tests call `cli.main([...])` for each.
- Verify: `python -m pytest -q`
- [ ] done

### T04: Step-by-step menu on the same commands

- Main menu: convert an export / generate HTML from the archive / iMessage tools / exit.
- Convert: choose service → export path (iMessage defaults to its configured database) →
  destination (central archive or service folder) → HTML? → for iMessage, "use default settings?"
  (else spam mode, workers, contacts, chat, limit) → run.
- The old processing paths are removed; diagnostics live under iMessage tools.
- Tests drive the menu with scripted input and check the results match the subcommands.
- Verify: `python -m pytest -q`
- [ ] done

### T05: Preflight reports a new root as initialized

- Follow-up from ticket 05: when `--root` points at a folder with no `config.json`, say
  "initialized", not "repaired".
- Test captures the output.
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
Follow-up found while verifying ticket 05: run_preflight prints 'Chattr structure repaired' when it creates a brand-new root given via --root (first_time is only true for the prompt path). Report 'initialized' when config.json didn't exist before. Cosmetic; fix with a test here.
