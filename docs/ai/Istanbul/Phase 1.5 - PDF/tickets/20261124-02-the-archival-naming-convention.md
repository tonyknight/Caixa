---
id: 20261124-02-the-archival-naming-convention
title: The archival naming convention
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: caixa/naming.py and docs/Archival names.md, examples checked by tests.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Caixa's archival naming convention, as a document (`docs/Archival names.md`) and as code (`caixa/naming.py`) future file collectors can reuse: dates at their precision, which date names each type, title and author cleaning, characters, a cut after 110 characters, clashes with ` (2)`.

## Acceptance criteria

- [x] `docs/Archival names.md` documents the convention with examples and edge cases, linked from the README
- [x] `caixa/naming.py` builds `(DATE) Title - Author.ext` with `(YYYY-MM-DD)`, `(YYYY-MM)`, `(YYYY)`; no author omits ` - Author`; no date is not named (Unrecognized keeps the original name)
- [x] Unsafe characters, control characters, leading/trailing dots and spaces, runs of spaces, capitals and NFC are handled; names are cut after 110 characters at a word
- [x] A different file of the same name in a folder gets ` (2)`, ` (3)`; the same file is recognised
- [x] Every example in the document is a test

## Context

Phase 1.5 - PDF Tasks Breakdown item 2. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Naming convention*; D9.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/naming.py`, with no dependencies on documents, so a future photo or video
collector can use it. Chattr's attachment names (`safe_name`, `_free_name`) stay as they are; this
module is the general convention they already follow.

- `NamingDate.parse("2024" | "2024-11" | "2024-11-30")` holds a value and a precision
  (`year` | `month` | `day`), refusing anything else and impossible dates. `.prefix` is
  `(2024-11-30)`.
- `clean(text)`:
  - NFC;
  - control characters out;
  - `/ \ |` → `-`, `:` → ` - `, `* ? < >` out, `"` → `'`;
  - spaces collapsed;
  - leading and trailing dots, spaces and dashes trimmed;
  - a part written all in capitals (more than five letters) becomes title case, with short
    joining words (`de, da, do, dos, das, e, of, the, and, a, o, for`) kept lower case after the
    first word.
- `archival_name(date, title, author=None, extension=".pdf")` gives
  `(DATE) Title - Author.ext`:
  - the author, a leading date and a leading or trailing ` - Author` are taken out of the title
    when something is left;
  - no author means no ` - Author`;
  - a missing date or title raises `NamingError`.
- `original_name(filename)` is the original name made safe, used in `Unrecognized/`.
- **Length**: the stem is at most `LIMIT = 110` characters. The title is shortened at a word first
  (the date and author kept); if the stem is still too long, it is cut at a word, else at 110.
- `folder_name(text)` cleans a folder name (an author) the same way and within the limit.
- `free_path(folder, name, sha256=None)`: `name`, or the first ` (2)`, ` (3)`… free name. A file
  already holding the same SHA-256 is returned as it is (the same file).
- `docs/Archival names.md`: the convention with examples and edge cases, linked from the README. Its
  examples table (between `<!-- examples -->` markers) is read by the tests and checked against
  `archival_name`, so the document and the code cannot drift.

### T01: Dates, cleaning, names and length

- `caixa/naming.py`: `NamingDate`, `NamingError`, `clean`, `archival_name`, `original_name`,
  `folder_name`, `free_path`, `LIMIT`. (`free_path` was moved here from T02: its tests share the
  file.)
- Tests (`tests/test_naming.py`):
  - the three precisions and refusals;
  - unsafe characters, controls, NFC, shouting titles, joining words;
  - author and date repeated in the title;
  - no author;
  - 110 characters (title shortened first, at a word);
  - a long author;
  - the original name kept safe;
  - ` (2)` and ` (3)`, and the same content recognised.
- Verify: `python -m pytest -q tests/test_naming.py && python -m mypy caixa`
- [x] done

### T02: Clashes and the convention document

- `docs/Archival names.md` with the convention, the naming date per type, Unrecognized, folders and
  the examples table. README link.
- Tests: every row of the document's examples table gives its name.
- Verify: `python -m pytest -q tests/test_naming.py && python -m black --check caixa tests/test_naming.py && python -m mypy caixa`
- [x] done

## Completion report

- **Outcome:** `caixa/naming.py` names files by the convention:
  - `NamingDate` at day, month or year precision;
  - `clean`: safe characters, NFC, capitals calmed;
  - `archival_name`: `(DATE) Title - Author.ext`, with the date and author taken out of the
    title, and cut after 110 characters (the title shortened first, at a word);
  - `original_name` for Unrecognized;
  - `folder_name`;
  - `free_path`: ` (2)`, ` (3)`, with the same content recognised by SHA-256.

  `docs/Archival names.md` documents the convention (the naming date per type, characters,
  length, clashes, folders, Unrecognized), and its examples table is checked by the tests. Linked
  from the README.
- **Files:**
  - new: `caixa/naming.py`, `tests/test_naming.py`, `docs/Archival names.md`;
  - changed: `README.md`.
- **Errors:** none. `free_path` moved from T02 to T01, because its tests share the file.
- **Verify:**
  - `python -m pytest -q`: 1610 passed, 1 skipped.
  - `python -m mypy --python-version 3.12 caixa`: only the 8 baseline errors, none in
    `naming.py`.
  - black: clean for the changed files.

## Review

### 2026-11-24: 201a2be..9399499 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** the joining-word list (`JOINING`) covers English and Portuguese only. Other
  languages' articles get capitals when a shouting title is calmed.
- **Minor:** `original_name` raises on a name with nothing usable in it (`???.pdf`). The collector
  (ticket 04) must decide what such a file is called.
- **Spec:** D9 met; every acceptance criterion met. The 110-character limit and the Unrecognized
  rule match the 2026-11-24 decisions.
- **TDD:** RED (`ModuleNotFoundError: caixa.naming`; then the missing document) before each GREEN.
- **Commits:** `20261124-02 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
