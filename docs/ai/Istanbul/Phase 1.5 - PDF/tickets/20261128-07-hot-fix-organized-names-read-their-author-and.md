---
id: 20261128-07-hot-fix-organized-names-read-their-author-and
title: 'Hot fix: organized names read their author and tags wherever they are'
type: bug
priority: high
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: Author and tags read wherever the name holds them; corrections in place
parent:
depends_on:
- 20261128-05-organized-names-in-the-import
subtasks: []
plan_status: done
current_task: T01
---
## Description

The maintainer's first organized import put 493 well-named PDFs in `Unrecognized/`. Their names
hold an author and tags, but in forms the reader did not take: `Subject - (Author) - [Tag]`
(349), `(Author) Subject` (67), `Subject (Author) - [Tag]` (16), a bare copy number (16), the
author followed by more `[ … ]` (23). The reader took an author only from the last brackets right
before the tags, a rule narrower than the maintainer's description. Run over the maintainer's
list, the rule below finds an author in 471 of the 493 and no case of two different authors; the
22 left have no `( … )` at all. (The list was only read in the session; nothing of it is in the
repository. The tests use synthetic names in the same forms.)

The import that brought them stopped during filing (the copy error, a separate hot fix), so the
model never read them either. They are marked organized, so once the reader is fixed, reading
them (`caixa documents enrich`) re-decides and files each under its author, its name unchanged.

## Acceptance criteria

- [x] Every `( … )` after the date names the author, except a month name, a number or a copy
      number. The same name twice is one author; of two different names the last is the author.
- [x] Every `[ … ]` is a tag, `[(Name)]` being `Name`, in order, the same tag once.
- [x] ` - ` is a separator; a trailing ` 2` or ` - 2` is a copy number.
- [x] The subject is what is left: an author at its start or end taken out, one inside it kept as
      its words; no stray separators or brackets.
- [x] The forms of the maintainer's names (in synthetic names) each give their author, tags and
      subject.
- [x] A correction rewrites the author's brackets, or the subject, in place; the date as before.
- [x] The organized fixtures, the import and the dry run end as their known answers say.

## Context

Requirements: D30 (amended 2026-11-28 by the maintainer), D31.

## Subtasks

## Implementation plan

Status: done
Current task: T01

**Design** (`caixa/documents/organized.py`):

- `read_organized` takes the date and the rest as now. Then:
  - **tags:** every `[ … ]` in the rest, its text with any brackets of its own taken off, kept
    once each (case aside), in order;
  - **authors:** every `( … )` outside the tags, less month names, numbers and copy numbers. The
    distinct names (case and spacing aside) give `authors`, and the last is `author`;
  - **copy number:** a trailing `(n)`, or a trailing ` n` or ` - n`, of one or two digits;
  - **subject:** the rest without the copy number. Then the trailing tags and separators are
    taken off, the author's brackets are taken off where they start or end it, and kept as their
    words inside it. A run of separators becomes one, and stray `[` `]` `(` `)` and separators at
    either end go.
- `OrganizedName` gains `authors`. `compose` stays the fallback.
- `rewrite(name, date=, subject=, author=)` rewrites in place:
  - the date: `with_date`;
  - the author: each `(old)` becomes `(new)`, or ` (new)` is put after the subject when the name
    had none;
  - the subject: its words replaced where they are written, else `compose`.

  `reconcile._decide_organized` uses `rewrite`.

### T01: Reading the author and tags wherever they are

- `caixa/documents/organized.py`, `caixa/documents/reconcile.py`, `tests/test_organized_names.py`.
- Tests:
  - each form, in synthetic names: `Subject - (Author) - [Tag]`; `(Author) Subject`;
    `Subject (Author) - [Tag]`; `… - (Author) - 2`; `… (Author) [Tag] - [Tag]`;
    `[Tag] Subject - (Author) - [Tag]`; `Name (Author)'s words`; an author inside the subject;
    the same author twice; two different authors; `[(Name)]`; no author; several tags;
  - a correction in place;
  - the earlier forms still read as before.
- Verify: `python -m pytest -q tests/test_organized_names.py tests/test_organized_import.py tests/test_documents_prepare.py`
- [x] done

## Completion report

- **Outcome:**
  - **Reading:** `read_organized` reads the author and tags wherever the name holds them.
    - Every `( … )` after the date names the author, except a month name, a number or a copy
      number. The same name twice is one author, and of two different names the last is the
      author (`OrganizedName.authors` keeps them all).
    - Every `[ … ]` is a tag, `[(Name)]` being `Name`, each once.
    - A trailing ` (2)`, ` 2` or ` - 2` is a copy number.
    - The subject is what is left. An author at its start or end is taken out, a stray letter
      glued to it included (`I(Kaiser)]`, `(…)a`); one inside it is kept as its words.
  - **Corrections:** `rewrite` changes one part of a name where it is written: the author's
    brackets, the subject's words, or the date. An author given to a name without one goes after
    the subject. `reconcile._decide_organized` uses it.
  - **On the maintainer's list,** read in the session only: 471 of 493 names give an author, 412
    give tags, all give a subject, and none gives two different authors. The 22 without any
    `( … )` go to the model, then `Unrecognized/`, as decided.
- **Files:** `caixa/documents/organized.py`, `caixa/documents/reconcile.py`,
  `tests/test_organized_names.py`; D30 amended in the Requirements.
- **Errors:** the first version left two untidy subjects on the real list (a tag left at the end
  once a stray author was taken off, and a letter glued after the author). Both were fixed with
  tests, in synthetic names.
- **Verify:**
  - `python -m pytest -q tests/test_organized_names.py tests/test_organized_import.py tests/test_documents_prepare.py`:
    105 passed.
  - mypy: the 8 baseline errors.
  - The full suite is not run, per the maintainer's instruction; it runs at the end.

## Review

### 2026-11-28: reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a `[ … ]` inside the subject (`[Quartz] 2.1 Notes`) is both a tag and kept in the
  subject as written.
- **Minor:** a subject that ends in a one- or two-digit number written after a space
  (`Section 2`) is read as a copy number. Not seen on the real list.
- **Spec:** D30 as amended met; every acceptance criterion met.
- **TDD:** RED (16 failing reader tests; the untidy endings) before GREEN.

## Notes

Append-only running log. Each entry dated.
