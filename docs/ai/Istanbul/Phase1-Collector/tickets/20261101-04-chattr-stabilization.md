---
id: 20261101-04-chattr-stabilization
title: Chattr stabilization
type: feature
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 4.
parent:
depends_on:
- 20261101-03-chattr-import-and-licensing
subtasks: []
plan_status: in-progress
current_task: T07
---
## Description

Make Chattr's v2 scaffolding actually work and remove its contradictions.

## Acceptance criteria

- [ ] The name is 'Chattr' everywhere (`~/.chattr.json`, `~/Documents/Chattr`, `chattr.sqlite`, `chattr-cli` command)
- [ ] Preflight and configuration are wired: pointer → root → global `config.json` merged with `Services/<Service>.json`
- [ ] iMessage configuration keys resolve (Quick/List/Diagnostics no longer fail)
- [ ] Preflight repair keeps existing preferences and state; `--root` works without prompting
- [ ] HTML generation no longer crashes and the template uses the database field names
- [ ] Unused dependencies removed; stale docs consolidated

## Context

Phase1-Collector Tasks Breakdown item 4. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — What works / Scaffolding / Contradictions; F11.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T07

Chattr's modules import each other as `src.…`. The `chattr-cli` command and the Requirements' type
check (`mypy … tools/chattr/src`) call for an installable `chattr` package in a src layout:
`tools/chattr/src/chattr/`. All test work uses the synthetic family and a temporary HOME; nothing
touches the real home folder.

### T01: Installable `chattr` package and command

- Move modules into `src/chattr/` (`parsers/` included). `main.py` → `src/chattr/cli.py` with
  `main(argv)` (`--version`, `--root DIR`, then the existing menu); add `src/chattr/__main__.py`.
- `templates/` → `src/chattr/templates/`; `Defaults/` → `src/chattr/defaults/`, located via the
  package path rather than the working directory.
- `tools/chattr/pyproject.toml`: name `chattr`, GPL-3.0-or-later, Python ≥ 3.10, console script
  `chattr-cli = "chattr.cli:main"`, package data.
- Remove the stale top-level `config.json` (a development leftover with `./output` paths).
- Tests (`tests/test_package.py`): every module imports; `python -m chattr --version` and the
  `chattr-cli` command print the version.
- Verify: `python -m pip install -e tools/chattr -q && python -m pytest -q`
- [x] done

### T02: "Chattr" everywhere

- Rename in code, defaults and user-facing text:
  - `~/.chatter.json` → `~/.chattr.json`;
  - `chatter_root` → `chattr_root`;
  - `~/Documents/Chatter` → `~/Documents/Chattr`;
  - `Output/Chatter` → `Output/Chattr`;
  - `chatter.sqlite` → `chattr.sqlite`;
  - `{CHATTER_ROOT}` → `{CHATTR_ROOT}`;
  - "Chat2HTML", "Chatter" and "Chat Archiver" → "Chattr".
- Historical docs keep old names only where they describe the past.
- Test: no old names in `src/chattr/` or its defaults.
- Verify: `python -m pytest -q`
- [x] done

### T03: Configuration wired to the Chattr root

- `Settings` resolves the root in this order: `--root` → `CHATTR_ROOT` environment variable →
  `~/.chattr.json`.
- It loads global `config.json` plus every `Services/<Service>.json` (preferences and state) into
  one view: `global.…` and `services.<service>.preferences/state.…`.
- `{CHATTR_ROOT}` is substituted at load time, which removes the JSON-breaking text replacement.
- State can be saved back per service.
- Tests: merge, precedence, placeholder substitution, state round-trip.
- Verify: `python -m pytest -q`
- [x] done

### T04: Non-interactive, non-destructive preflight

- `run_preflight(root=None, interactive=…)`: never prompts when a root is given or when stdin
  isn't a TTY.
- Creates the tree; copies defaults only when missing; adds missing default keys into existing
  JSON files **without overwriting** user preferences or state; writes the pointer.
- Tests: first run creates everything; a second run changes nothing; a user-edited preference and
  state survive a repair; a missing service file is restored.
- Verify: `python -m pytest -q`
- [x] done

### T05: CLI uses the real configuration keys and paths

- The CLI reads output and database paths from `Settings` (`{root}/Database/chattr.sqlite`), and
  iMessage options from `services.imessage.preferences.…`.
- Test: every configuration key the CLI reads resolves in a freshly prepared root (a static scan
  of `cli.py`, so mismatched keys can't return).
- Verify: `python -m pytest -q`
- [x] done

### T06: HTML generation works from the database

- `HTMLGenerator` converts rows to plain dicts and maps database fields (`message_author`,
  `message_sender`, `body`, …) to what the template uses.
- Test: the synthetic iOS WhatsApp export → `WhatsAppParser` → `DatabaseManager` → HTML file
  containing the messages.
- Verify: `python -m pytest -q`
- [x] done

### T07: Dependencies and documentation

- Remove unused dependencies (check imports: `beautifulsoup4`, `langdetect`, `requests`); keep
  `requirements.txt` and `pyproject.toml` in step.
- README rewritten for the current state (install, `chattr-cli` command, root layout, settings,
  services, license).
- Superseded docs (`config_structure_v2.md`, `configuration_guide.md`,
  `iMessageConversionReadMe.md`, `MIGRATION_SUMMARY.md`) get a "superseded" header pointing to
  the README.
- Verify: `python -m pytest -q && ! grep -rqE "^(beautifulsoup4|langdetect|requests)" tools/chattr/requirements.txt`
- [ ] done

### T08: Formatting and type-check baseline

- Black-format Chattr and remove the root `extend-exclude` for `tools/chattr`.
- Type-check Chattr with a baseline configuration that passes, fixing real errors found.
  Strictness for legacy Chattr code ratchets up in later tickets; new Caixa code stays strict.
  The decision is recorded in Notes.
- Verify: `python -m black --check . && python -m mypy caixa tools/chattr/src && python -m pytest -q`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01 debug: 'pip install -e tools/chattr' failed building langdetect (sdist-only; egg_info subprocess error in this environment). Root cause for us: langdetect, requests and beautifulsoup4 are declared but never imported by Chattr (grep confirms). Fix: removed all three from pyproject.toml and requirements.txt now (pulled forward from T07). Separately found: /usr/bin/chattr is the e2fsprogs file-attribute tool, so a 'chattr' console script would shadow a standard Linux command; command name raised with the maintainer.

### 2026-11-02
T01 done. Maintainer decision 2026-11-02: the terminal command is 'chattr-cli' (not 'chattr', which would shadow Linux's e2fsprogs /usr/bin/chattr). Package and import name stay 'chattr'; 'python -m chattr' works; a test asserts no bare 'chattr' console script is installed.

### 2026-11-02
T05: the static key-scan test failed on six keys cli.py read (global.output_directory, services.imessage.* without .preferences, imessage.*), confirming the review. Fixed. Debug: the new end-to-end test first failed with 'No module named jinja2' because it isolates HOME and Python derives the per-user site folder from HOME; fixed in the test by passing PYTHONUSERBASE (not a product bug).
