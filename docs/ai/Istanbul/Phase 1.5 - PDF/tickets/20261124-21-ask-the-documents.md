---
id: 20261124-21-ask-the-documents
title: Ask the documents
type: feature
priority: medium
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: Ask with checked citations; Ask box in the served view
parent:
depends_on:
- 20261124-20-passages-embeddings-and-hybrid-search
- 20261124-18-search-in-the-window
subtasks: []
plan_status: done
current_task: T02
---
## Description

Ask the documents: a question answered by the local model from retrieved passages, citing document and page, citations checked; the Ask box in the served view.

## Acceptance criteria

- [x] A fixture question is answered citing the right document and page
- [x] An answer citing a passage it was not given is refused
- [x] The answer is marked as a model's; each citation opens the PDF at its page

## Context

Phase 1.5 - PDF Tasks Breakdown item 21. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Search and Ask* (Ask); D24.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: T02

**Design:**

- **Retrieval** (`caixa/documents/ask.py`):
  - A question is searched with *any* of its words: `search.search` gains `match="any"`, which
    joins the question's content words with OR and leaves out short and common words in English
    and Portuguese. Otherwise a natural question ("How much was…") matches nothing, because full
    text asks for every word.
  - When an embedding model is set, the search is hybrid (ticket 20).
  - The best pages give the passages: about four for Apple Intelligence, eight for an endpoint.
    Each page gives one passage, the one sharing the most of the question's words, or the closest
    in meaning when its vectors exist.
- **The answer:**
  - The model gets the numbered passages, `[1] Title, Author, date, page N`, then the text, within
    the provider's budget.
  - It answers with a JSON object `{found, answer}`, where `answer` cites passages as `[n]`. This
    goes through `enrich.ask`: the schema is sent as `response_format` to an endpoint, or written
    into the instructions for Apple, with one retry naming what was wrong.
  - The check: if `found` is true, the answer must cite at least one passage, and every `[n]` must
    be a passage it was given. Otherwise the answer is refused and not shown, with the reason.
  - When `found` is false, the answer says the passages don't hold it.
- **Result:** `{question, found, answer, written_by: {provider, model}, citations: [{n, item_id,
  title, author, date, page, source, file_path, passage}], refused?, message?}`, holding only the
  passages the answer cites.
- **Provider:** `enrich.provider(values, reading=False)`. The local-only rule still applies. The
  `documents.enrich` switch (reading at import) does not turn Ask off.
- **Where:**
  - `documents.ask` is a read method. It answers directly, since the server is threaded.
  - `caixa documents ask "question"` prints the answer, then each citation with its file and page,
    then "Written by <model>".
  - The served view has an **Ask** box under the search. Its answer is labelled as a model's, each
    `[n]` links to its passage, and each passage opens the PDF at its page in the overlay. Opened
    from disk, the box is hidden.
- **Privacy:** no question, passage or answer goes into a log.

### T01: Retrieval, the answer and its check

- `caixa/documents/ask.py`, `caixa/documents/search.py` (`match`), `caixa/documents/enrich.py`
  (`reading`, the schema's name), `tests/fixtures/stand_in_documents.py` (answers questions, with
  a misbehaving mode that cites a passage it was not given).
- Tests (`tests/test_documents_ask.py`):
  - "How much was the electricity bill for December 2023?" is answered citing
    `2022 Car Insurance.pdf`, page 1;
  - any-word matching finds pages that every-word matching misses;
  - Apple gets four passages and an endpoint eight;
  - a citation the model was not given is refused;
  - an answer that is not found carries no citations;
  - a remote endpoint is refused;
  - nothing is logged.
- Verify: `python -m pytest -q tests/test_documents_ask.py tests/test_documents_search.py`
- [x] done

### T02: The method, the command and the Ask box

- `caixa/service.py`, `caixa/cli.py`, `caixa/documents/templates/documents.html`,
  `caixa/documents/templates/documents-index.js`, `tests/test_worker_protocol.py`,
  `web/tests/e2e-documents.test.ts`.
- Tests:
  - `documents.ask` answers through the service;
  - the command prints the answer and its citations;
  - end to end: the Ask box shows a routed answer marked as a model's, and a citation opens the
    overlay at its page;
  - from disk the box is hidden.
- Verify: `python -m pytest -q tests/test_documents_ask.py tests/test_worker_protocol.py && pnpm --dir web exec vitest run tests/e2e-documents.test.ts && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
  - **Retrieval:** `caixa/documents/ask.py` searches a question with any of its content words
    (`search(match="any")`, common English and Portuguese words left out), by meaning too when an
    embedding model is set. It takes one passage from each of the best pages, the one sharing the
    most words with the question or closest in meaning: four for Apple Intelligence, eight for an
    endpoint.
  - **The answer:** the model reads the numbered passages within its budget and answers with
    `{found, answer}`, citing `[n]`. This goes through `enrich.ask` (the schema as
    `response_format` for an endpoint, in the instructions for Apple), with one retry.
  - **The check:** a citation of a passage it was not given, or a found answer that cites
    nothing, is refused and not shown, with the reason. The result carries only the cited
    passages, each with its document, page and file, and `written_by` (provider and model).
  - **Where:** `documents.ask`; `caixa documents ask "…"`; the **Ask** box in the served
    Documents view, whose answer is marked "Written by a model (…)". Each `[n]` links to its
    passage, and each passage opens its PDF at its page in the overlay. The box is hidden when
    the view is opened from disk.
  - Reading at import turned off does not turn Ask off; a model on the internet is refused.
    Nothing asked or answered is logged.
- **Files:**
  - new: `caixa/documents/ask.py`, `tests/test_documents_ask.py`;
  - changed: `caixa/documents/search.py`, `caixa/documents/enrich.py`, `caixa/service.py`,
    `caixa/cli.py`, `caixa/documents/templates/documents.html`,
    `caixa/documents/templates/documents-index.js`, `tests/fixtures/stand_in_documents.py`,
    `tests/test_worker_protocol.py`, `web/tests/e2e-documents.test.ts`.
- **Errors:**
  - The T01 commit first carried a mypy annotation error, because `tail` had hidden mypy's exit
    status. Fixed, and the unpushed commit amended.
  - An ambiguous end-to-end locator was narrowed.
- **Verify:**
  - `python -m pytest -q`: 1971 passed, 1 skipped.
  - vitest: 285 passed (eight document end-to-end tests).
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 64b5887..95463f3 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a citation written as `[1, 2]` is not read as two citations. A found answer citing
  only that way is retried once, then refused. The instruction asks for `[n]` each.
- **Minor:** the end-to-end test routes `documents.ask` to a fixed answer, because the stand-in
  model is not running while `caixa serve` is. The method itself is tested against the stand-in
  in Python.
- **Minor:** the prompt is cut at the budget as a last guard, which can cut the last passage
  short; each passage is first sized to its share.
- **Spec:** D24 met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.ask`; no method `documents.ask`; no `ask`
  command) before each GREEN.
- **Commits:** `20261124-21 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
