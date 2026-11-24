---
id: 20261124-22-documents-and-people
title: Documents and people
type: feature
priority: medium
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: Authors and people named linked; documents on person pages
parent:
depends_on:
- 20261124-12-reconciliation-confidence-and-apply
- 20261124-16-author-pages-and-the-unrecognized-page
subtasks: []
plan_status: done
current_task: T02
---
## Description

Authors and people named in a document matched to the box's people, recorded in `item_people`, and documents shown on their person pages with Open.

## Acceptance criteria

- [x] An author that is a person of the box shows the document on their page
- [x] People named are linked as `mentioned`; the owner is not linked as recipient

## Context

Phase 1.5 - PDF Tasks Breakdown item 22. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (People links); D25.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: T02

**Design:**

- **Matching** (`caixa/documents/people.py`): a name matches a box person by the person's name,
  or by one of their `name` aliases, compared with case, spacing and accents aside. A name two
  people share matches neither.
- **Links** (`link_documents`): for every document, the author that is a person of the box is
  linked as `sender`, and each person the model found named in it (a `person` field) as
  `mentioned`.
  - The owner is never linked: every document is the owner's, so naming them as recipient says
    nothing.
  - A document's links (roles `sender` and `mentioned`) are brought up to date, and nothing else
    of `item_people` is touched.
  - This runs before the document pages are drawn (`draw_documents`), so imports, reading,
    corrections and author renames keep the links current.
  - When links change and the box has person pages, one change waits for **Update the pages**.
- **On person pages** (a generic Chattr slot): `publish` and `render_pages` gain `page_links`,
  `{page title: [{group, links: [{label, href, note}]}]}`, where hrefs are relative to the box.
  - A person page shows each group as a list ("Documents (n)"), each entry as its label, its note
    and a plain **Open** link to the file, relative to the page.
  - The slot is part of what a page is drawn from, so a change redraws it. It is also given to
    the worker processes.
  - Chattr's templates still know nothing of documents.
  - `person_links(box)` gives each linked person's documents, `(date) Title`, with the note "by
    them" or "names them", newest first. Caixa passes it on every publish.
- **Limitation:** a person of the box with no messages has no page to show documents on. That
  waits for Stage 2's person pages.

### T01: Matching and links

- `caixa/documents/people.py`, `caixa/documents/pages.py` (links before drawing).
- Tests (`tests/test_documents_people.py`):
  - the author João Costa, a person of the box, is linked as `sender`;
  - Rui Pereira, named in the lease, is linked as `mentioned`;
  - the owner, Maria Costa, is not linked;
  - an alias matches with accents aside;
  - a name two people share matches neither;
  - a correction of the author moves the link;
  - other roles of `item_people` are untouched;
  - a change of links waits for Update the pages when person pages exist.
- Verify: `python -m pytest -q tests/test_documents_people.py`
- [x] done

### T02: Documents on person pages

- `tools/chattr/src/chattr/pages.py`, `tools/chattr/src/chattr/commands.py`,
  `tools/chattr/src/chattr/templates/page.html`, `caixa/collectors/chattr.py`,
  `caixa/documents/people.py` (`person_links`).
- Tests:
  - Chattr: a page given `page_links` lists them with relative Open links, the other pages don't,
    and changing them redraws the page (`tools/chattr/tests/test_render_pages.py`);
  - Caixa: after a messages import and a documents import, João Costa's page lists "Carta de
    João Costa" with an Open link that reaches its PDF;
  - Update the pages draws a corrected link.
- Verify: `python -m pytest -q tests/test_documents_people.py tools/chattr/tests/test_render_pages.py tests/test_chattr_collectors.py tests/test_documents_pages.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
  - **Matching:** `caixa/documents/people.py` matches a name to a box person by their name or a
    `name` alias, with case, spacing and accents aside. A name two people share matches neither.
  - **Links:** `link_documents` records each document's author that is a box person as `sender`,
    and each person named in it as `mentioned` (not also as `mentioned` when they are its author).
    The owner is never linked. Only those two roles are brought up to date; others are left
    alone.
  - It runs before the document pages are drawn, so imports, reading, corrections and renamed
    authors keep the links current. When links change and the box has person pages, one change
    waits for **Update the pages**.
  - **On person pages:** Chattr's `publish` and `render_pages` take a generic `page_links` slot,
    `{page title: [{group, links: [{label, href, note}]}]}`. It is drawn as "Documents (n)" with
    each entry's label, note and a plain **Open** link relative to the page. Addresses outside
    the output folder are left out.
  - The slot is part of the page's fingerprint, so a change redraws the page, and it is given to
    worker processes. Chattr's templates still know nothing of documents.
  - Caixa passes `person_links(box)`: each person's documents, newest first, "by them" or "names
    them".
- **Files:**
  - new: `caixa/documents/people.py`, `tests/test_documents_people.py`;
  - changed: `caixa/documents/pages.py`, `caixa/collectors/chattr.py`,
    `tools/chattr/src/chattr/pages.py`, `tools/chattr/src/chattr/commands.py`,
    `tools/chattr/src/chattr/templates/page.html`, `tools/chattr/src/chattr/templates/base.html`,
    `tools/chattr/tests/test_render_pages.py`.
- **Errors:**
  - A first shared-name test was muddled (aliases are unique in the database). It was rewritten
    around two aliases that differ only by accents.
  - The new CSS class name appeared on every page, so the tests now look for the element.
- **Verify:**
  - `python -m pytest -q`: 1986 passed, 1 skipped.
  - Chattr's own suite: 916 passed.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 8768b52..49b9230 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a box person with no messages has no person page, so their documents show only on
  the document pages. That waits for Stage 2's person pages.
- **Minor:** person pages are matched by title. A Chattr page titled differently from the box
  person (an unresolved handle) shows nothing until the person is matched.
- **Minor:** the template change redraws every person page once, after this update.
- **Spec:** D25 met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.people`; `render_pages() got an unexpected
  keyword argument 'page_links'`; the person page without documents) before each GREEN.
- **Commits:** `20261124-22 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
