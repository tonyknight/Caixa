---
id: 20261128-01-organized-file-names
title: Organized file names
type: feature
priority: high
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: 'prepare --organized: owners'' names kept, only wrong dates replaced, authors
  and tags learned'
parent:
depends_on:
- 20261127-01-prepare-pdfs-beside-the-box-and-compare-the-two
- 20261127-02-author-knowledge-in-the-box
subtasks: []
plan_status: done
current_task: T03
---
## Description

Some owners have already named their PDFs well, as `(YYYY-MM-DD) Subject (Author) [Tag].pdf`.
With `--organized`, `caixa documents prepare` trusts such names, overrides only a date it is sure
is wrong, files the copy under the owner's own name, and learns a whitelist of authors and tags
into `.caixa/author-knowledge.json`, the baseline for the PDF import once `prepare` is folded
into it. Today's filename reader does not know this pattern: it reads no author or tag, and trims
an impossible `2024-02-30` to February. Requirements: D30, D28 (amended), task 26.

## Acceptance criteria

- [x] `prepare --organized` reads `(YYYY-MM-DD) Subject (Author) [Tag].pdf` and its partial
      forms: a month or a year; no author; no tag; several tags; brackets inside the subject; a
      copy number. A month name or a number in the last brackets is not an author.
- [x] A matching file keeps its name and is filed under its year and author.
- [x] An impossible date, and a date the page clearly contradicts, are replaced, and nothing else
      in the name changes. A date that is among the page's other dates, or coarser or finer than
      the page's, is kept.
- [x] A name with no author is filed under the author the models agree on, keeping its name;
      otherwise it waits in `Unrecognized/` under its name.
- [x] A name that does not match is prepared as before.
- [x] The authors and tags read are added to `accepted` and `tags` in
      `.caixa/author-knowledge.json`, and a rejected name the owner used moves to `accepted`.
      Nothing else in the box is written, and without `--organized` the box is only read.
- [x] The report says what happened to each name (kept, date replaced from/to/why, no author,
      not organized), counts and lists the authors and tags learned, and records each file's OCR
      pages, cover sheet and look (D28). It holds no page text.

## Context

Requirements: D30 *Organized file names*, D28 *Prepare, beside the box* (amended 2026-11-28), D29
*Author knowledge*; Tasks Breakdown 26. Folding `prepare` into the import is a later task.

## Subtasks

## Implementation plan

Status: done
Current task: T03

**Design:**

- **`caixa/documents/organized.py` (new):**
  - `read_organized(name) -> Optional[OrganizedName]`: the date (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`),
    whether it is impossible, the subject, the author (the last `( … )` before the tags, never a
    month name, a number or a copy number), the tags, and a copy number `(2)` kept apart. `None`
    when the name does not fit.
  - `with_date(name, date)`: the same name with only its date replaced.
  - `on_page(date, pages)`: whether a date appears on the pages at its own precision. A full date
    must be among `evidence.text_dates`. A month or year counts when any full date falls in it,
    or when the month and year, or the year alone, are written.
  - `compatible(a, b)`: one date is the other, or a coarser form of it (`2024-03` and
    `2024-03-12`).
- **The decision, shared by both trees** (`prepare.py`), for a matching name:
  - **Agreed page date:** the date the models that ran give, when they agree and it is
    `on_page`. With one model available, its date alone.
  - **Impossible date:** replaced by the agreed page date. Without one, the copy waits in
    `Unrecognized/` under its name ("impossible date, no page date").
  - **Contradicted date:** replaced when there is an agreed page date, it is not `compatible`
    with the name's date, and the name's date is not `on_page`. Otherwise the name is kept.
  - "The quote is found on the page" is checked by `on_page` on the models' date: the page
    states that date. That check is deterministic; `prepare`'s answers carry no quote.
  - **Author:** the name's. With none, the models' agreed author (after author knowledge, D29),
    used for the folder only. Without agreement, the copy waits in `Unrecognized/`.
  - **Filing:** `Documents/PDF/<year>/<author>/<the owner's name>` (date replaced if it was),
    using `free_path`. The owner's author is never put through `rejected` or `instead`.
  - **Tags:** recorded on the file's report record. A document record (and Caixa's tags) comes
    with the import, once `prepare` is folded in.
- **Whitelist** (`author_knowledge.py`): `Knowledge.tags`; `learn_organized(known, authors,
  tags)` adds the authors to `accepted` (moving any from `rejected`) and the tags to `tags`. The
  key `tags` is written only when it holds something, so existing files are unchanged.
  `prepare(organized=True, box=…)` saves the file at the end; it is the only box write.
- **Report:** per file `ocr_pages`, `cover` and `look` (D28, the two reopened criteria of
  `20261127-01`); with `--organized`, `name`, which is one of `kept`, `date replaced`, `no author`,
  `waiting` or `not organized`, plus `from`, `to`, `why` and the tags. `report.txt` gains an
  *Organized names* section: the counts, each replaced date, and every author and tag learned.
- **Command:** `caixa documents prepare … --organized`.

### T01: Reading organized names

- `caixa/documents/organized.py`, `tests/test_organized_names.py` (new).
- Tests:
  - the full form;
  - month and year dates;
  - no author;
  - no tag, and several tags;
  - brackets inside the subject;
  - a copy number;
  - a month name or a number in the last brackets is not an author;
  - an impossible date is flagged, not trimmed;
  - a non-matching name gives `None`;
  - `with_date` changes only the date;
  - `on_page` at each precision, including dates written in Portuguese and as `03/2024`;
  - `compatible`.
- Verify: `python -m pytest -q tests/test_organized_names.py`
- [x] done

### T02: Prepare --organized: the date decision, filing and the report

- `tests/fixtures/organized_family.py` (new: synthetic organized-name PDFs with known answers),
  `caixa/documents/prepare.py`, `caixa/cli.py`, `tests/test_documents_prepare.py`.
- Tests:
  - a matching file is kept under its year and author in both trees;
  - an impossible date is replaced from the page;
  - an impossible date with no page date waits in Unrecognized;
  - a contradicted date is replaced, and the rest of the name is unchanged;
  - a date among the page's other dates is kept;
  - a coarser name date is kept;
  - a name with no author takes the agreed author, and waits when the models disagree;
  - a non-matching name is prepared as before;
  - a rejected name the owner used is still the folder;
  - the report's per-file records (name, OCR, cover, look), with no page text;
  - the CLI flag.
- Verify: `python -m pytest -q tests/test_documents_prepare.py tests/test_organized_names.py`
- [x] done

### T03: The whitelist and the documentation

- `caixa/documents/author_knowledge.py`, `caixa/documents/prepare.py`,
  `tests/test_author_knowledge.py`, `tests/test_documents_prepare.py`,
  `docs/Documentation/Collector.md`.
- Tests:
  - authors and tags learned into `accepted` and `tags`;
  - a rejected name moves to `accepted`;
  - an existing file without tags keeps its form;
  - `--organized` writes only `.caixa/author-knowledge.json` (the box's files are otherwise
    unchanged), and without the flag nothing in the box is written;
  - the report lists what was learned;
  - the file stays 0600 and holds no page text.
- Verify: `python -m pytest -q tests/test_author_knowledge.py tests/test_documents_prepare.py tests/test_organized_names.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
  - **Reading the name:** `caixa/documents/organized.py` reads
    `(YYYY-MM-DD) Subject (Author) [Tag].pdf` and its partial forms with no model.
    - The author is the last brackets before the tags, never a month name or a number.
    - A copy number is kept apart.
    - An impossible date is flagged, not trimmed.
    - A date and a subject alone are enough, so Caixa's own `(date) Title - Author` form is read
      as a subject with no author.
  - **`prepare --organized`:** a matching file keeps the owner's name under its year and author,
    in both trees.
    - Only the date is ever replaced: when it is impossible (by the date the page gives), or when
      the page clearly contradicts it. "Clearly" means the models that ran agree on a date, the
      page states it, and the name's date is nowhere on the page.
    - A name with no author takes the author the models agree on, for the folder only.
    - An impossible date with no page date, or a missing author the models do not agree on,
      waits in `Unrecognized/` under the owner's name.
    - The owner's author never goes through `rejected` or `instead`.
    - Names that do not match are prepared as before.
  - **The whitelist:** the authors and tags read go into `.caixa/author-knowledge.json`, as
    `accepted` (a rejected name moves out of `rejected`) and a new `tags` list. That is the only
    box write; without the flag the box is only read.
  - **The report:** every record now carries `ocr_pages`, `cover` and `look`, which meets the two
    criteria reopened on `20261127-01`. `report.txt` gains *preprocessing* and *organized names*
    sections: counts, each replaced date with why, each waiting file, and what was learned.
  - **Documentation:** a section on `--organized` in `docs/Documentation/Collector.md`.
- **Files:**
  - new: `caixa/documents/organized.py`, `tests/fixtures/organized_family.py`,
    `tests/test_organized_names.py`;
  - changed: `caixa/documents/prepare.py`, `caixa/documents/author_knowledge.py`, `caixa/cli.py`,
    `tests/test_documents_prepare.py`, `tests/test_author_knowledge.py`,
    `docs/Documentation/Collector.md`.
- **Errors:**
  - "The quote is found on the page" (D30) is checked deterministically. The models' date must be
    written on the page (`on_page`), because `prepare`'s answers carry no quote.
  - Tags are recorded on each file's report record. They become Caixa's document tags once
    `prepare` is folded into the import.
  - Two expected orders in the T03 tests were wrong (files are read in name order); corrected
    before GREEN.
  - Noticed while testing, not changed here: the "not words" test sends any page with fewer than
    20 letters to OCR, so a short page of real text is OCR'd (the fixture's two-line receipt).
    It is a preprocessing threshold for the tuning work.
- **Verify:**
  - `python -m pytest -q` (with `PYTHONUNBUFFERED=1`): 2,146 passed before the review fix; the
    ticket's suites after it: 83 passed.
  - vitest: 286 passed.
  - mypy: the 8 baseline errors.
  - black: only the untouched `tests/test_mail_sent_and_received.py`.

## Review

### 2026-11-28: 7640b3d..HEAD (T01–T03), reviewed in-session

**Verdict:** clean after one fix; Minor items only.

- **Fixed:** a name whose date was replaced but which then waited for an author was counted only
  as "no author", and the report did not list its date change. It now says both, with a test.
- **Minor:** in a box with author knowledge, the models are not yet told the authors and tags the
  same run is learning; a second run benefits from them.
- **Minor:** `organized.py` uses three of `evidence.py`'s private helpers (`_MONTH`, `_plain`,
  `_valid`); they could be made public when the import takes this over.
- **Spec:** D30 and the D28 amendment met; every acceptance criterion met; the files touched match
  the plan.
- **TDD:** RED before each GREEN: `ModuleNotFoundError: caixa.documents.organized`; 14 failing
  prepare tests; 5 failing whitelist tests; the review fix's test.
- **Commits:** `20261128-01 T01/T02/T03: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
