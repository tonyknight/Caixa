---
id: 20261120-01-synthetic-mail-fixtures
title: Synthetic mail fixtures
type: chore
priority: high
status: done
created: 2026-11-20
updated: 2026-11-20
closed: 2026-11-20
notes: 'Done: noisy mailbox fixture (2 accounts, zips, catalogue), large-mbox generator,
  slow marker.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

The synthetic mail every test of this project uses: a noisy mbox (plain and zipped) and a
generator for a multi-gigabyte mbox for the scale test. Built by the fixture family's builders, in
the style of `tools/chattr/tests/fixtures/builders/mbox.py`; deterministic (fixed boundaries and
`From ` lines).

## Acceptance criteria

- [ ] The noisy mbox holds: family and friends who are people in the fixture box; the owner's sent mail, including mail never answered; strangers; newsletters, notifications, mailing lists and no-reply senders; mail with unsubscribe links (English, Portuguese, Spanish); receipts and orders in the same languages, some from no-reply senders with unsubscribe links
- [ ] Gmail labels including Sent, Spam, Trash and the Promotions, Updates, Social and Forums categories; Gmail thread ids on some threads and References-only threads on others; a thread across years; a mailing-list thread in which a box person posted
- [ ] Edge cases: mail without a Message-ID, the same mail in two accounts, odd charsets and RFC 2047 headers, HTML-only mail, `From ` lines escaped in bodies, signature images repeated with slightly different bytes, one-pixel tracking images, `image001.png` from different mails on the same day
- [ ] A zipped copy, and a Takeout-shaped zip holding more than one `.mbox`
- [ ] A generator writes an mbox of a requested size into a temporary folder (never committed) for the slow scale test
- [ ] The same input always gives byte-identical files; a test checks it
- [ ] Each case is documented in the builder so later tickets can find what they need

## Context

Phase 1.5 - Mbox Tasks Breakdown item 1. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Testing requirements* (Fixtures, Scale). Tasks Breakdown item 1.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** a new builder, `tools/chattr/tests/fixtures/builders/noisy_mbox.py`, beside Phase 1's
`mbox.py` (which stays as it is for the existing tests). Mails are declared as data (`Mail`
specs: sender, recipients, subject, time, bodies, labels, thread, extra headers, attachments) and
each carries what later tickets must find: its cleaning outcome (`junk:<group>` with the group
slugs `lists`, `notices`, `unsubscribe`, `spam_trash`; `kept:receipt`; `kept:protected`; or
`clean`) and the case names it illustrates. `build_noisy_mbox(out_dir)` writes the Gmail account's
mbox, a second account's mbox (the "Work" account, sharing one mail with the first), a zip of the
first and a Takeout-shaped zip holding both, and returns their paths with the catalogue. Every MIME
boundary and `From ` line is fixed, so builds are byte-identical. People are the fixture family
(Ana, João and Rui are people in the box); strangers, shops and lists use reserved `example.*`
domains. A generator, `write_large_mbox(path, size)`, renders the catalogue's mails once and
writes numbered copies (new Message-IDs and thread ids per copy) straight to disk until the size is
reached, for the slow scale test.

### T01: The noisy mbox, its second account, the zips and the catalogue

- `noisy_mbox.py`: `Mail` spec, `MAILS`, `OWNER_WORK` address, `NoisyMail` result
  (`gmail`, `work`, `zip`, `takeout_zip`, `catalogue`), `build_noisy_mbox(out_dir)`.
- Cases: family threads (Gmail thread id; References only; across years), the owner's unanswered
  mail, strangers the owner wrote to and did not, a name-only match, newsletters, a mailing list
  (with a post by a box person, replies by strangers and the owner), notifications, no-reply,
  bounce, Feedback-ID, unsubscribe links in English, Portuguese and Spanish, Gmail Spam, Trash and
  categories, receipts and orders in the three languages (from no-reply senders with unsubscribe
  links), a box person forwarding a newsletter, a list the owner answered, no Message-ID, the
  same mail in both accounts, ISO-8859-1 and windows-1252, HTML-only mail with a script, an event
  handler and a remote image, signature images repeated with different bytes, tracking pixels,
  `image001.png` from two mails on one day, a body line beginning `From `.
- Documented in `tools/chattr/tests/fixtures/README.md`.
- Tests (`tools/chattr/tests/test_noisy_mbox.py`): byte-identical builds; every mail parses and
  the counts match the catalogue; each case is present (escaped `>From `, no Message-ID, the shared
  Message-ID in both accounts, labels, attachments); the zips hold the right members.
- Verify: `python -m pytest -q tools/chattr/tests/test_noisy_mbox.py`
- [x] done

### T02: The large mbox generator and the slow marker

- `write_large_mbox(path, size_bytes)` in `noisy_mbox.py`: numbered copies of the catalogue,
  streamed to disk, deterministic; returns the number of mails written.
- `pyproject.toml`: register a `slow` marker and leave slow tests out of the default run
  (`-m "not slow"` in `addopts`), so `python -m pytest -q -m slow …` runs them.
- Tests: a few-megabyte file is a valid mbox with the expected count and unique Message-IDs, is
  identical on a second run, and is at least the size asked for.
- Verify: `python -m pytest -q tools/chattr/tests/test_noisy_mbox.py && python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** a noisy mailbox fixture: 56 Gmail mails and 4 Work mails (one shared), each declared
  with its cleaning outcome and the cases it shows, written byte-identically as two mboxes, a zip
  and a Takeout-shaped zip; a generator for a multi-gigabyte copy; a `slow` pytest marker kept out
  of the default run.
- **Files:** new `tools/chattr/tests/fixtures/builders/noisy_mbox.py`,
  `tools/chattr/tests/test_noisy_mbox.py`; changed `tools/chattr/tests/fixtures/README.md`,
  `pyproject.toml`.
- **Errors:** none in existing code. Review found Gmail's Forums category missing; fixed before
  closing. Baseline note: in this container `test_the_command_line_prints_the_report` fails only
  when the whole suite runs with the system Python (an environment variable leaks between tests;
  it passes alone and in a clean virtual environment), and mypy trips over a preinstalled numpy
  stub; both are the container's, and verification runs in a clean virtual environment.
- **Verify:** `python -m pytest -q` → 1304 passed, 1 skipped; `black --check` clean; `mypy` clean.

## Review

### 2026-11-20: 95431f3..HEAD (T01–T02), reviewed in-session

**Verdict:** clean after one fix; Minor items only.

- **Fixed (Important):** the acceptance criteria name Gmail's Forums category; no mail had it. The
  list thread without the owner is now labelled `Category Forums`, and the test checks Social and
  Forums too.
- **Minor:** cleaning outcomes encode decisions ticket 03 must follow (Feedback-ID → lists,
  Auto-Submitted → notices, list posts in a thread the owner wrote in → kept); recorded in Notes.
- **Minor:** List headers, `Auto-Submitted`, receipt wording and Gmail category labels follow
  documentation, not a real export (said in the fixtures README).
- **Spec:** every acceptance criterion met; files match the plan.
- **TDD:** RED (collection error; then the generator test failing; then the Forums check) before
  GREEN for each change.
- **Commits:** `{ticket-id} {task-id}: {title}`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: noisy_mbox.py declares 56 Gmail mails and 4 Work mails (one shared) as data, each with its cleaning outcome and cases; builds are byte-identical (fixed boundaries, From lines, zip entries). Group slugs chosen: lists, notices, unsubscribe, spam_trash. Feedback-ID (bulk mail service) is expected under lists, Auto-Submitted under notices. Mailing-list posts in a thread the owner wrote in are expected kept:protected (cleaning rule: owner wrote in its thread); the list rule for import is ticket 06's.

### 2026-11-20
T02: write_large_mbox renders the Gmail mails once with a copy token in Message-IDs and thread ids and streams numbered copies; a 3 MB file is valid, deterministic, with unique ids. pyproject: 'slow' marker, left out by default (-m 'not slow' in addopts; a later -m slow wins).
