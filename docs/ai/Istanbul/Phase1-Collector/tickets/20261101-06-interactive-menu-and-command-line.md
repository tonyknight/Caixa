---
id: 20261101-06-interactive-menu-and-command-line
title: Interactive menu and command line
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: commands layer, chattr-cli subcommands, menu on the same commands.'
parent:
depends_on:
- 20261101-04-chattr-stabilization
subtasks: []
plan_status: done
---
## Description

The step-by-step terminal menu plus an equivalent non-interactive command line for every action.

## Acceptance criteria

- [x] Waterfall menu: services → central DB or service folder → optional HTML, with overridable defaults
- [x] `chattr-cli convert <service> <export> [--root] [--db|--json] [--contacts] [--aliases] [--html]`
  (`--contacts` applies to iMessage for now; WhatsApp and Messenger get it with ticket 14)
- [x] Restored iMessage flags: `--region`, `--attachment-root`, `--batch-size`, `--verbose`, `--attachment-workers`
- [x] Every menu action can be performed non-interactively

## Context

Phase1-Collector Tasks Breakdown item 6. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Key flows — Standalone Chattr; F12.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T03: Non-interactive subcommands

- `chattr-cli [--root DIR] convert <service> <export> [--db | --json] [--html] [--owner NAME] [--contacts FILE] [--aliases FILE]`.
- iMessage flags on `convert imessage`: `--region`, `--attachment-root`, `--batch-size`,
  `--verbose`, `--attachment-workers`, plus `--workers`, `--spam-mode`, `--chat`, `--limit`.
- Also `chattr-cli html [--out] [--owner]`, `chattr-cli chats [<chat.db>]` and
  `chattr-cli doctor [<chat.db>] [--check …]`. With no subcommand, the menu runs.
- Tests call `cli.main([...])` for each.
- Verify: `python -m pytest -q`
- [x] done

### T04: Step-by-step menu on the same commands

- Main menu: convert an export / generate HTML from the archive / iMessage tools / exit.
- Convert: choose service → export path (iMessage defaults to its configured database) →
  destination (central archive or service folder) → HTML? → for iMessage, "use default settings?"
  (else spam mode, workers, contacts, chat, limit) → run.
- The old processing paths are removed; diagnostics live under iMessage tools.
- Tests drive the menu with scripted input and check the results match the subcommands.
- Verify: `python -m pytest -q`
- [x] done

### T05: Preflight reports a new root as initialized

- Follow-up from ticket 05: when `--root` points at a folder with no `config.json`, say
  "initialized", not "repaired".
- Test captures the output.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** Chattr's work now lives in prompt-free functions in `chattr.commands`:
  - `convert` (WhatsApp and Messenger, into the central archive or a service folder, with
    optional HTML and aliases);
  - `generate_html`;
  - `convert_imessage` (native JSON with the restored options, plus archival attachment copies);
  - `list_chats` and `doctor`.

  `chattr-cli` gains the `convert`, `html`, `chats` and `doctor` subcommands. The step-by-step
  menu (convert / generate HTML / iMessage tools / exit) runs the same functions, so every menu
  action has a subcommand. Preflight reports a new root as "initialized".
- **Files:**
  - New: `tools/chattr/src/chattr/commands.py`, `tools/chattr/src/chattr/imessage_export.py`.
  - Changed: `cli.py` (rewritten; 716 → about 400 lines), `attachment_manager.py`
    (iMessage paths re-rooted; numbered names on collision), `database_manager.py`
    (`get_messages_for_conversation`), `preflight.py`.
  - Tests: `test_commands.py`, `test_imessage_commands.py`, `test_cli_subcommands.py`,
    `test_cli_menu.py`, plus updates to `test_cli_config_keys.py`, `test_importing.py`,
    `test_json_export.py`, `test_preflight.py` and `conftest.py` (`chattr_root` fixture).
- **Errors:** found in review and fixed with tests:
  - `--attachment-root` and `--attachment-workers` had no effect: iMessage attachment paths
    were expanded against the current home, and the CLI never asked for archival copies.
  - Turning archiving on exposed silent overwriting of different attachments that share a
    timestamp.
  - Full Disk Access refusals, files that aren't SQLite, and unreadable aliases files crashed
    with a traceback.
- **Verify:** `python -m pytest -q` → 155 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean; `chattr-cli --version` → `chattr 2.0.0`.

## Review

### 2026-11-02: e119138..12fe4ed (T01–T05 and review fixes), reviewed in-session

**Verdict:** two Important findings, both fixed with tests before marking done. Minor items
are listed below and carried forward.

- **Important (fixed):** `--attachment-root` and `--attachment-workers` were inert.
  - Root cause: `create_attachment_info_from_message_attachment` expanded
    `~/Library/Messages/Attachments/…` against the current home, ignoring the source folder.
  - The parser stores `attachment_root` but never uses it.
  - The CLI never requested archival copies.
  - Fix: those paths are re-rooted under the source folder, and `convert imessage` takes
    `--attachments-dir`, Chattr's earlier flag name for the archive folder.
  - Enabling archiving showed that two different attachments with the same timestamp
    overwrote each other. Within a run they are now numbered " 2", " 3", as a stopgap.
    Ticket 13 owns full collision-free naming.
- **Important (fixed):** failures other than `CommandError` crashed the menu and the
  subcommands with a traceback. The cases: macOS Full Disk Access (`PermissionError`), a file
  that isn't SQLite, and an unreadable aliases file. They are now command errors, and the
  parser's Full Disk Access advice is kept.
- **Minor:** `--contacts` applies to iMessage only until ticket 14.
- **Minor:** `load_dotenv("API_Key.env")` in `cli.main` is dead code, since nothing reads
  environment variables. Remove it when translation is revisited.
- **Minor:** every iMessage conversion writes `Output/iMessage/imessage_export.json`, so a
  `--chat` export replaces a full one. Revisit with ticket 07.
- **Minor:** spam filtering doesn't apply on the parallel path (no `--limit`). This is the
  parser's existing limitation.
- **Minor:** the HTML path is printed twice, because `HTMLGenerator` prints its own line.
  Ctrl-C during a subcommand prints a traceback.
- **Spec:** all acceptance criteria are met (`--contacts` as noted). The plan named
  `commands.py`. The helpers moved into `imessage_export.py`, and `database_manager.py` and
  `attachment_manager.py` changed for T01 and the review fixes.
- **TDD:** RED was seen before GREEN for every task:
  - T02: the command functions were missing;
  - T03: 11 failing;
  - T04: 10 failing;
  - T05: 1 failing;
  - review fixes: 6, then 1 failing.
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
Follow-up found while verifying ticket 05: run_preflight prints 'Chattr structure repaired' when it creates a brand-new root given via --root (first_time is only true for the prompt path). Report 'initialized' when config.json didn't exist before. Cosmetic; fix with a test here.
T02: `convert_imessage` also takes `attachments_dir` (the name `export_to_json` already uses). Archival copies of attachments are written only when it's given, which matches the old advanced menu's default of "no". The parallel fetch path (no `--limit`) doesn't apply spam filtering. That's a known limitation documented in the parser, and it's unchanged here. `--limit` uses the filtered single-threaded path.
T03: `--contacts` is accepted for iMessage, where the parser uses it. For WhatsApp and Messenger it's a usage error ("applies to iMessage only") until people resolution (ticket 14) gives those services a contacts step. `--aliases` covers sender naming for them meanwhile. Options that don't apply to the chosen service are rejected before anything runs (exit 2): `--db/--json`, `--html`, `--aliases` and `--owner` with iMessage; the iMessage flags with the others. `--root` works before or after the command. `doctor` runs every check unless `--check` is given (repeatable). With iMessage, `batch_size` and `attachment_workers` also fall back to `services.imessage.preferences` (`performance.batch_size`, `attachments.general.max_attachment_workers`). The config-key scan now covers `commands.py` too.
T04: the menu is now Convert / Generate HTML / iMessage tools / Exit, built on `commands`. `cli.py` is down from 716 to 393 lines. Removed: `main_menu`, `process_and_import`, the iMessage quick/advanced paths, the diagnostics submenu functions, `generate_html_submenu`, and the `imessage_export` re-exports.
- The menu also asks for the archive owner's name (Enter skips); without it, sent messages can't be marked.
- A missing export file is reported right after the path is entered, before the remaining questions.
- Quoted and drag-and-dropped (backslash-escaped) paths are accepted.
- End of input exits with 0; Ctrl-C exits with 130.
- iMessage `contacts` and `region` now default to `global.contacts.vcf_file_path` and `global.contacts.phone_region`.
- The start-up no longer creates an empty `chattr.sqlite`. The installed-command test now runs the menu's Exit and a real `convert` subcommand.
- Cosmetic: `HTMLGenerator` prints its own "HTML file generated at" line, so the path shows twice.

### 2026-11-02
Review: two Important findings, fixed (attachment root and archive flags; error handling). Minors recorded in the Review section.
