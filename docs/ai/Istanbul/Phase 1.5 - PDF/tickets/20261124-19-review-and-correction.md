---
id: 20261124-19-review-and-correction
title: Review and correction
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: owner corrections (user_verified), review with candidates, editing on
  served cards.'
parent:
depends_on:
- 20261124-12-reconciliation-confidence-and-apply
- 20261124-17-documents-view-on-the-index-page
subtasks: []
plan_status: done
---
## Description

Authoring mode for documents: an Unrecognized card has Author and Date fields and Apply; any document's author, title, date, type and tags can be corrected; corrections are `user_verified`, move files, and are batched behind Update the pages; the To review list shows reasons and candidates.

## Acceptance criteria

- [x] Typing author and date on an Unrecognized card and Apply moves it to `<YYYY>/<Author>/` under its archival name
- [x] Corrections are `user_verified` and never overwritten by enrichment
- [x] To review lists reasons and candidates with sources; choosing one applies it
- [x] Every action is also `documents.update` and a `caixa documents` command

## Context

Phase 1.5 - PDF Tasks Breakdown item 19. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment, confidence and review* (Corrections), *Key flows* (Review); D14, D22.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:**
  - **Corrections:** `caixa/documents/corrections.py` records the owner's author, date, title or
    type as `user_verified` (replacing an earlier correction) and checks each value first. With
    an author and a date from the owner, an Unrecognized document is filed at once under the best
    known title, or its file name. Corrections survive reading again.
  - **Moves and pages:** files move at once (noted for undo). In the window the pages wait for
    **Update the pages**; from the command line they are drawn at once.
  - **Candidates and review:** `candidates` lists each fact's values with their sources in words.
    Also the `documents.update` and `documents.review` methods, and `caixa documents update` and
    `review`.
  - **On the pages:** `document-edit.js`, a page script whose hash is in the policy, works only
    when served by Caixa. An Unrecognized card shows **Author**, **Date** and **Apply**; other
    cards have **Correct** (author, title, date, type). Fields offer the card's candidates labelled
    by source, and Apply says where the document was filed. From disk the pages are for reading
    only.
- **Files:**
  - new: `caixa/documents/corrections.py`, `caixa/documents/templates/document-edit.js`,
    `tests/test_documents_corrections.py`;
  - changed: `caixa/documents/reconcile.py`, `caixa/documents/pages.py`,
    `caixa/documents/templates/author.html`, `caixa/service.py`, `caixa/cli.py`, `caixa/web.py`,
    `tests/test_web_server.py`, `tests/test_documents_view.py`, `tests/test_worker_protocol.py`,
    `web/tests/e2e-documents.test.ts`.
- **Errors:**
  - A patch script stopped on text black had rewrapped; reapplied.
  - The author page lacked a `[hidden]` rule, so its forms showed from disk; added.
  - Running black over all of `tests/` touched an unrelated file, which was reverted.
- **Verify:**
  - `python -m pytest -q`: 1943 passed, 1 skipped.
  - vitest: 284 passed (seven document end-to-end tests).
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: f0fb7a7..6df785e (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** after Apply the card stays where it was until **Update the pages**; its message says
  where the document went.
- **Minor:** candidates are shown as suggestions in the fields (a `datalist`), not as a separate
  side-by-side table; choosing one fills the field, and Apply applies it.
- **Spec:** D14 and D22 met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.corrections`; the end-to-end test) before each
  GREEN.
- **Commits:** `20261124-19 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
