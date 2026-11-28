---
id: 20261127-02-author-knowledge-in-the-box
title: Author knowledge in the box
type: feature
priority: high
status: done
created: 2026-11-27
updated: 2026-11-27
closed: 2026-11-27
notes: Agreed 2026-11-27. Corrections teach the next prepare run, in .caixa/author-knowledge.json.
parent:
depends_on:
- 20261124-12-reconciliation-confidence-and-apply
- 20261127-01-prepare-pdfs-beside-the-box-and-compare-the-two
subtasks:
- id: T01
  title: The author-knowledge file
  status: done
- id: T02
  title: Corrections, renames and merges write it
  status: done
- id: T03
  title: Prepare reads it
  status: done
plan_status: done
---
## Description

The Gemma comparison showed the models will not categorize perfectly. Gemma was the careful one:
it named PG&E, T-Mobile and PayPal, and left unreadable scans unrecognized. Apple Intelligence
filed almost everything, often under the customer, and sometimes under an invented name (`City of
Springfield`, the year `2025`, `null`). Apple was not meaningfully faster.

The owner already corrects people by renaming and merging them. Document authors already rename
and merge (`caixa/documents/authors.py`) and a document's author can be corrected by hand
(`caixa/documents/corrections.py`). This ticket keeps what those corrections teach, in the box, and
feeds it to the next `prepare` run.

The file is `.caixa/author-knowledge.json`, readable by the owner alone (mode `0600`). It holds
three lists and nothing from the page:

- **accepted.** Authors the owner has confirmed: the name they corrected to, the name kept in a
  merge, the name given in a rename.
- **rejected.** Names that are not authors in this archive: an invented city, a software name, the
  word `null`, a bare year. A rejected name is never filed. The box's owner is never rejected,
  because they do author some documents (a resume, a letter they wrote).
- **instead.** A name a model said, the author to use instead, and the document's kind when the
  lesson came from correcting one document (`bill`, `statement`, …). A rename or a merge has no
  kind: that old name means the kept author on every document.

```json
{
  "accepted": ["PG&E", "T-Mobile"],
  "rejected": ["City of Springfield", "Brite:Bill", "null"],
  "instead": [{"said": "Anthony D. Knight", "use": "T-Mobile", "kind": "bill"}]
}
```

`caixa documents prepare` reads the file from the box given with `--box` (still not written by
prepare). Both models are told the accepted names, and told never to use a rejected one. After an
answer comes back:

- a rejected author is dropped;
- an `instead` whose `said` matches, and whose `kind` matches or is absent, supplies the author;
- otherwise a rejected author with no lesson leaves the file in `Unrecognized`.

Correcting an author, renaming one, or merging two updates the file in the same action. The
database of authors and aliases stays as it is; this file is what a run outside the box can read.

## Acceptance criteria

- [x] Correcting a document's author from a name that is not the box's owner to another name adds
      the new name to `accepted`, the old name to `rejected` when it is not already accepted, and
      an `instead` that names the document's kind.
- [x] Renaming an author, or merging one into another, records an `instead` with no kind, and the
      kept name as accepted. The old name is not rejected when it is the box's owner.
- [x] The box's owner is never written to `rejected`, including when a bill of theirs is corrected
      to the company that sent it.
- [x] The file is `.caixa/author-knowledge.json`, mode `0600`, and a test finds no page text in it.
- [x] `prepare`, given that box, does not file a rejected name. It files under the `instead` author
      when one matches. The instruction shown to both models names the accepted authors and the
      rejected names.
- [x] A box with no such file prepares as it does today.

## Context

- **Requirements:** D29. Author rename and merge are D15 (`caixa/documents/authors.py`). A
  hand correction is D22 (`caixa/documents/corrections.py`). `prepare` is D28
  (`caixa/documents/prepare.py`).
- **Why the owner is not rejected.** On the sample, the customer was the right author of a resume
  and the wrong author of the utility bills. A global ban on that name would misfile the resume.
  The lesson from one bill is stored with its kind.
- **Why a file, not only the database.** `prepare` does not write the box and must be able to read
  the lessons without opening the master for decisions. The author tables remain the record of who
  is filed in the box.
- **Not in this ticket:** vision, a longer pass for low-confidence files, choosing Gemma over
  Apple. This is only the memory the next run can be shown.

## Subtasks

- [x] T01 The author-knowledge file
- [x] T02 Corrections, renames and merges write it
- [x] T03 Prepare reads it

## Implementation plan

Status: done
Current task: 

### T01: The author-knowledge file

- **Files:** `caixa/documents/author_knowledge.py` (new); `tests/test_author_knowledge.py` (new).
- **RED:** a new file accepts an author, rejects a name, and records an instead with a kind. The
  owner passed to it is refused as a rejected name. The file is mode `0600`. Reading a missing
  file is three empty lists. Round-trip keeps the three lists and no other keys.
- **GREEN:** load and save under `.caixa/author-knowledge.json`.
- **Verify:** `python -m pytest -q tests/test_author_knowledge.py`
- [x] done

### T02: Corrections, renames and merges write it

- **Files:** `caixa/documents/corrections.py`; `caixa/documents/authors.py`;
  `tests/test_author_knowledge.py` and the existing correction and author tests if they construct
  a box.
- **RED:** correcting one document's author writes `accepted`, `rejected` and an `instead` with
  that document's kind, and does not reject the owner. Renaming writes an `instead` with no kind.
  Merging writes an `instead` from the name that went away to the name that stayed.
- **GREEN:** each of those three actions updates the file after the database change succeeds.
- **Verify:** `python -m pytest -q tests/test_author_knowledge.py tests/test_documents_corrections.py tests/test_documents_authors.py`
- [x] done
### T03: Prepare reads it

- **Files:** `caixa/documents/prepare.py`; `tests/test_documents_prepare.py`.
- **RED:** with a rejected name, a stand-in that answers that name does not file under it. With
  an `instead` for that name and kind, the file lands under the kept author. The text sent to the
  stand-in contains an accepted name and a rejected name. A box with no file is unchanged.
- **GREEN:** `prepare` loads the box's file when `--box` is set, adds the lists to the
  instruction, and applies `instead` before filing.
- **Verify:** `python -m pytest -q tests/test_documents_prepare.py tests/test_author_knowledge.py`,
  then the project verify command:
  `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`.
- [x] done
## Completion report

- **Outcome:** Corrections, renames, and merges write `.caixa/author-knowledge.json`.
  `caixa documents prepare --box` reads it: both models are told the accepted authors and
  the rejected names, an `instead` for that kind supplies the author, and a rejected name
  with no lesson stays in `Unrecognized`. The owner's name is never rejected. A lesson for
  one kind wins over a lesson for every kind.
- **Files:** `caixa/documents/author_knowledge.py`; `caixa/documents/corrections.py`;
  `caixa/documents/authors.py`; `caixa/documents/prepare.py`; `tests/test_author_knowledge.py`;
  `tests/test_documents_prepare.py`.
- **Errors:** A rejected first answer is treated as a missing author, so the second look still
  runs and can supply a different name. The project pytest command deadlocked once on
  `test_the_real_command_serves_a_page_and_stops_on_control_c` (the child's stdout is
  block-buffered). The same command with `PYTHONUNBUFFERED=1` finished.
- **Verify:** `tests/test_documents_prepare.py` and `tests/test_author_knowledge.py`: 21 passed.
  With corrections: 35 passed. Project suite, unbuffered: 2078 passed, 7 failed (the known
  Chattr web-convert failures), 1 deselected. black only the known
  `tests/test_mail_sent_and_received.py`. mypy the 8 known errors, none in these modules.
  Web `tsc` clean; vitest 249 passed, 37 skipped (Playwright is not installed here).

## Review

2026-11-27, on `b2786f3..15aea07`. No Critical or Important findings. The file matches D29:
accepted, rejected, and instead; the owner is never rejected; a one-document correction keeps
its kind; a rename or merge does not. `prepare` reads the file and does not write the box.
One minor, recorded under Errors: a rejected author still gets the second look.

## Notes

Append-only running log. Each entry dated.

- 2026-11-27: Agreed after the Gemma run. Gemma was careful and Apple was not faster. The owner
  corrects authors the way they correct people. The lessons live in
  `.caixa/author-knowledge.json` and are shown to the next prepare run. The owner's own name is
  never rejected.

### 2026-11-28
T02: correcting, renaming, and merging an author now writes .caixa/author-knowledge.json after the database change.

### 2026-11-27
T03 done. prepare reads the file. A lesson for one kind wins over a lesson for every kind. Ticket done.
