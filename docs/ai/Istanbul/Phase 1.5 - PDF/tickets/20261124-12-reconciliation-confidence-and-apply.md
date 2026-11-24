---
id: 20261124-12-reconciliation-confidence-and-apply
title: Reconciliation, confidence and apply
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-10-ai-classification
subtasks: []
plan_status: in-progress
current_task: T03
---
## Description

Reconciliation of every field's candidates, provenance, conflicts, the confidence rule, apply (rename and move recorded for undo) or To review, re-enrichment without duplicates, authors with aliases (rename, merge, folders follow).

## Acceptance criteria

- [ ] Descriptive fixtures are applied: renamed and moved to `<YYYY>/<Author>/`
- [ ] A misleading filename produces a conflict and To review; no filename fact is dropped without contradicting evidence
- [ ] Date kinds stay separate; re-enriching creates no duplicate and keeps `user_verified`
- [ ] Undo puts moved files back; authors can be renamed and merged with folders following

## Context

Phase 1.5 - PDF Tasks Breakdown item 12. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment, confidence and review*, *Authors*; D13–D15.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T03

**Design:** `caixa/documents/reconcile.py` decides by Caixa's own rules, from a document's fields.
The sources are the filename, the properties, the text's dates, the model and the owner.

- **The owner's word wins:** a `user_verified` value is never replaced.
- **Date:**
  - The naming date is the model's, when given.
  - The filename's date agrees when one is a prefix of the other (`2024-11` and `2024-11-30`;
    the more precise is kept and both sources are listed).
  - A different filename date is *explained* when it matches another date written in the
    document (a text date or one of the model's other dates). It then describes another date
    (the property tax bill's `2023` is its issue year), is kept as that kind, and is not a
    conflict.
  - Otherwise it contradicts: a `date` conflict.
- **Type:** the filename's type words conflict only when none of them is the model's type.
- **Author:** the model's author matched to a known author (the same name or alias, or one
  containing the other as words) takes that author's name, and gains an alias. A filename author
  that is a different organization is an `author` conflict. A properties author never conflicts:
  properties are often wrong.
- **Confident** when all of these hold:
  - the model's answer was valid;
  - type, title and date are present;
  - the date's evidence was verified;
  - the author is a known author, or its evidence was verified;
  - there is no conflict.
- **Confident means applied:** title, author, date (precision and kind), type and category are
  set and their fields marked `applied`. The file is renamed and moved to
  `<YYYY>/<Author>/<archival name>`, and each move is returned for undo. Other review reasons
  (locked, `ocr_failed`, `probable_duplicate`) stay.
- **Otherwise review:** the reasons are added: `conflict:date`, `conflict:type`,
  `conflict:author`, `unverified_date`, `unverified_author`, `no_date`, `no_author`,
  `ai_unusable`. The conflicting fields are marked `conflict`, and the document stays where it is.
  A model's claimed conflicts (`filename_conflict` fields) are kept as information.

`enrich_documents` reconciles every document it reads. Moves go to the import's `RunResult.moved`,
or are noted on the enrich job's undo snapshot.

`caixa/documents/authors.py` renames and merges authors, and the folders and archival names
follow: each document's file moves, and its aliases are kept. Also `documents.authors`,
`documents.authors.rename`, `documents.authors.merge`, and
`caixa documents authors [list|rename|merge]`.

### T01: The rules

- `caixa/documents/reconcile.py` (`Decision`, `decide`).
- Tests (`tests/test_documents_reconcile.py`, on hand-made field sets):
  - agreeing and more precise dates;
  - an explained filename date (the property tax bill);
  - a contradicting one (`2022 Car Insurance.pdf`);
  - type conflicts and agreement;
  - author matching to a known author and alias;
  - a different filename author;
  - the owner's values winning;
  - each review reason;
  - confident with every condition met.
- Verify: `python -m pytest -q tests/test_documents_reconcile.py`
- [x] done

### T02: Applying, moving and undo

- `caixa/documents/reconcile.py` (`apply_decision`).
- `caixa/documents/enrich.py` (reconcile after reading; moves).
- `caixa/collectors/pdfImport.py` (`moved`).
- `caixa/service.py` (moves noted for the enrich job).
- Tests (import of the family with OCR and the stand-in model):
  - the statement moves to `2024/Banco Atlântico/(2024-11-30) Checking Statement - Banco
    Atlântico.pdf`;
  - the scan to `2024/Águas do Vale/…`;
  - the tax bill to `2022/Câmara Municipal de Vila Nova/(2022) Property Tax Bill - …`, its
    filename's 2023 kept as an issue date;
  - the renewal from `(2024-06-15)` to `(2024-07-01)`;
  - the misleading name in review with `conflict:date` and `conflict:type` in Unrecognized;
  - the rental agreement with `no_author`;
  - the probable duplicate applied but still in review;
  - fields marked `applied`/`conflict`;
  - undoing the import or the enrich job puts files back;
  - reading again changes nothing more.
- Verify: `python -m pytest -q tests/test_documents_reconcile.py tests/test_documents_enrich.py tests/test_pdf_collector.py`
- [x] done

### T03: Authors renamed and merged

- `caixa/documents/authors.py`.
- `caixa/service.py`, `caixa/cli.py`.
- `tests/test_worker_protocol.py`.
- Tests:
  - renaming an author moves its folders and renames its files, and keeps the old name as an
    alias;
  - merging two moves the documents to the one kept and joins the aliases;
  - a name already taken is refused;
  - the service and the commands.
- Verify: `python -m pytest -q tests/test_documents_reconcile.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
