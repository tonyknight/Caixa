---
id: 20261124-19-review-and-correction
title: Review and correction
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-12-reconciliation-confidence-and-apply
- 20261124-17-documents-view-on-the-index-page
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

Authoring mode for documents: an Unrecognized card has Author and Date fields and Apply; any document's author, title, date, type and tags can be corrected; corrections are `user_verified`, move files, and are batched behind Update the pages; the To review list shows reasons and candidates.

## Acceptance criteria

- [ ] Typing author and date on an Unrecognized card and Apply moves it to `<YYYY>/<Author>/` under its archival name
- [ ] Corrections are `user_verified` and never overwritten by enrichment
- [ ] To review lists reasons and candidates with sources; choosing one applies it
- [ ] Every action is also `documents.update` and a `caixa documents` command

## Context

Phase 1.5 - PDF Tasks Breakdown item 19. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment, confidence and review* (Corrections), *Key flows* (Review); D14, D22.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** `caixa/documents/corrections.py`.

- `correct(box, master, item_id, author=, date=, title=, type=)` records each value given as the
  owner's (`user_verified`, replacing an earlier correction of that field), then reconciles and
  applies.
  - The owner's word wins: with a date and an author from the owner, the document is filed even
    without a model's reading. Its title is then the best known one, or its file's own name.
  - A date is checked (`YYYY`, `YYYY-MM` or `YYYY-MM-DD`) and an author cleaned before anything is
    recorded; a value that cannot be used is refused, naming why.
  - The file is moved at once (each move noted for undo); the pages wait for **Update the pages**
    in Caixa's window (`box.add_pending("pages")`), or are drawn at once from the command line.
- `candidates(master, item_id)` lists each fact's candidate values with where each came from
  (filename, properties, text, model, owner), its evidence and page. This is what the owner
  chooses from.
- Also `documents.update`, `documents.review` (the documents waiting, with their reasons and
  candidates), and `caixa documents update ITEM [--author] [--date] [--title] [--type]` and
  `caixa documents review`.
- `reconcile.decide` takes a fallback title and, with the owner's date and author, drops every
  reason but the owner's own conflicts.

On the pages (T02), a new page script `document-edit.js` (hash in the policy) works only when the
page is served by Caixa:
- an Unrecognized card shows **Author** and **Date** fields and **Apply**;
- every other card has **Correct**, which shows author, title, date and type fields;
- each field offers the card's candidates (`data-candidates`, labelled by source);
- **Apply** sends `documents.update` and says where the document was filed, and that the pages
  show it after **Update the pages**.

### T01: Corrections and review in the service

- `caixa/documents/corrections.py`, `caixa/documents/reconcile.py`, `caixa/service.py`,
  `caixa/cli.py`, `tests/test_worker_protocol.py`.
- Tests (`tests/test_documents_corrections.py`):
  - typing an author and date for an Unrecognized document files it under
    `<YYYY>/<Author>/(date) Title - Author.pdf` and leaves review;
  - corrections are `user_verified` and survive reading again;
  - a correction of the title renames the file;
  - a bad date is refused;
  - in the window the pages wait, and Update draws them;
  - candidates come with their sources;
  - `documents.review` lists waiting documents with reasons;
  - the commands.
- Verify: `python -m pytest -q tests/test_documents_corrections.py tests/test_documents_reconcile.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [x] done

### T02: Correcting on the pages

- `caixa/documents/templates/document-edit.js`, `author.html`.
- `caixa/documents/pages.py` (candidates on cards).
- `caixa/web.py` (`PAGE_SCRIPTS`).
- `web/tests/e2e-documents.test.ts`.
- Tests:
  - from disk the fields are hidden;
  - served, an Unrecognized card's Author and Date, then Apply, file the document (the service
    lists it under its new path) and say so;
  - Correct on a filed card shows its candidates.
- Verify: `python -m pytest -q tests/test_documents_pages.py tests/test_web_server.py && cd web && pnpm exec vitest run tests/e2e-documents.test.ts && pnpm exec tsc --noEmit`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
