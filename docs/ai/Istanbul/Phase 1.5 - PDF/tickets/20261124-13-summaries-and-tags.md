---
id: 20261124-13-summaries-and-tags
title: Summaries and tags
type: feature
priority: medium
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-10-ai-classification
subtasks: []
plan_status: done
---
## Description

A 30–50-word summary in the document's language, marked as a model's, and up to four tags written with it (the starter set when one fits); the owner adds and removes tags and extends or trims the starter set.

## Acceptance criteria

- [ ] Fixtures get summaries within 30–50 words and up to four tags
- [ ] A starter tag is used when it fits; tags can be added and removed (`documents.tags`), the starter set extended or trimmed

## Context

Phase 1.5 - PDF Tasks Breakdown item 13. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Summaries and tags); D16.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** the classification answer already carries a summary and tags (ticket 10). This
ticket makes them right and puts them on the document.

- **Summary:** asked for in 30 to 50 words in the document's language. A longer answer is cut at
  the last sentence within 50 words (`summaries`' rule), and a shorter one is kept, as for mail.
  Stored on the document with the model's name (`summary`, `summary_model`) whether or not the
  document is confident: the summary is always marked as a model's, so it is safe to show.
- **Tags:**
  - The prompt names the starter set (the `tags` table's `starter` rows) and asks for one of them
    when it fits.
  - Answers are normalized: lower case, single spaces, and a word that is a starter tag but for
    its accents, case or a final `s` becomes that tag.
  - Duplicates go, and at most four are kept.
  - They are applied whether or not the document is confident (`set_tags`, source
    `ai_inference`).
- **The owner's tags:**
  - `documents.tags(item_id, add, remove)` adds tags (`user_verified`) and removes any.
  - A tag the owner removed is remembered (a `user_verified` `tag` field marked `rejected`), so
    reading the document again does not bring it back.
  - `documents.tags.starter(add, remove)` extends or trims the starter set.
  - Command: `caixa documents tags [ITEM] [--add T…] [--remove T…] [--starter]`.

### T01: Summaries and tags from the model

- `caixa/documents/tags.py` (`normalize_tags`, `starter_tags`).
- `caixa/documents/enrich.py`: the starter set in the prompt; the summary cut and stored; tags
  applied.
- `tests/fixtures/stand_in_documents.py`: tags in its answers.
- Tests (`tests/test_documents_tags.py`):
  - plural, capitals and accents meet their starter tag;
  - four at most, no duplicates;
  - the prompt names the starter set;
  - imported documents get a summary of 30–50 words with the model's name, and their tags;
  - a summary of 70 words is cut at a sentence;
  - a non-confident document still gets both.
- Verify: `python -m pytest -q tests/test_documents_tags.py tests/test_documents_enrich.py`
- [x] done

### T02: The owner's tags and the starter set

- `caixa/documents/tags.py` (`change_tags`, `change_starter`).
- `caixa/documents/records.py`: rejected tags kept out.
- `caixa/service.py`, `caixa/cli.py`, `tests/test_worker_protocol.py`.
- Tests:
  - adding and removing tags;
  - a removed model tag stays removed after reading again;
  - extending and trimming the starter set;
  - the service and the command.
- Verify: `python -m pytest -q tests/test_documents_tags.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
