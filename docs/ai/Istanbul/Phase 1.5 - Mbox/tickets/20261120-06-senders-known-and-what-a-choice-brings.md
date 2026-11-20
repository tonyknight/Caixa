---
id: 20261120-06-senders-known-and-what-a-choice-brings
title: Senders, Known and what a choice brings
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ''
parent:
depends_on:
- 20261120-02-mail-index-and-parallel-reading
subtasks: []
plan_status: done
---
## Description

The sorting logic behind Sort mail: the owner's addresses per account, Known matching, the
threads a chosen sender brings, and the owner's decisions.

## Acceptance criteria

- [ ] The owner's addresses proposed from mail labelled Sent (and the most frequent From otherwise) and confirmed with the account
- [ ] Known by address (chosen to begin with) and by name only (shown as such, not chosen until confirmed)
- [ ] To sort ordered with the owner's correspondents first, then the busiest
- [ ] A chosen sender brings every thread they wrote in, whole, and every thread in which the owner wrote to them, even unanswered; in a mailing-list thread only the mails of box people and the owner
- [ ] Choices and ignores remembered in `owner.json` and restored when a Cleaned or Reduced mbox is read, and after a reset
- [ ] `caixa mail senders | choose | ignore`

## Context

Phase 1.5 - Mbox Tasks Breakdown item 6. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Sorting rules*, *Data model* (owner.json); M2, M8.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/mail/senders.py` works from the index, plain sets and the owner's decisions,
like the classifier, so it is tested without a box; the service fills it from the box.

- **Who is listed:** every sender of the source except the owner, and every address the owner wrote
  to that never wrote back (no mails of its own, "you wrote N"): a person the owner wrote to is
  someone a choice must be able to reach, so the owner's unanswered mail reaches their page.
- **Known:** an address that is an alias of a box person (`by: address`, chosen to begin with), or a
  sender who used a box person's name (`by: name`, shown as such, chosen only when the owner says so).
- **Decisions** in `owner.json`'s `mail` section: `chosen` and `ignored` addresses (an explicit
  choice wins over the default; ignoring wins over choosing), restored for any source, after a
  reset. `accounts[<name>].owner` holds the owner's confirmed addresses for an account.
- **Categories:** Known, To sort (the owner's correspondents first, then the busiest), To import
  (every chosen sender), Ignored, Imported (senders already imported: given by the master once
  ticket 09 records mail; empty until then). Each with senders, mails and size; rows with name,
  address, mails, size, how they are known and how often the owner wrote to them.
- **What a choice brings:** every thread a chosen sender wrote in, whole; every thread in which the
  owner wrote to a chosen address, even unanswered; but in a mailing-list thread (a mail in it has
  `List-Id` or `List-Post`) only the mails of the owner, of box people and of chosen senders.
  `selection()` returns the threads and mails (positions), with the counts and size.
- **The owner's addresses** for an account: proposed from the master's owner aliases and the
  source's mail labelled `Sent` (else the commonest `From`), confirmed with `mail.owner.set`;
  cleaning and sorting use the confirmed ones when there are any.

### T01: Known, categories and decisions

- `caixa/mail/senders.py`: `Row`, `Category`, `listing(index, source, owner, known, names,
  chosen, ignored, imported)`; `caixa/owner.py`: `chosen`, owner addresses per account,
  `set_mail_decision`.
- Tests (`tests/test_mail_senders.py`, noisy fixture): owner addresses not listed; Ana and João
  known by address and chosen, the name-only Rui known by name and not chosen, Rui himself listed
  from the owner's unanswered mail; To sort starts with the owner's correspondents; choosing,
  ignoring and their order of precedence; counts add up.
- Verify: `python -m pytest -q tests/test_mail_senders.py tests/test_owner.py`
- [x] done

### T02: What a choice brings

- `selection(index, source, chosen, owner, people)` → threads and positions, with counts and size.
- Tests: Beatriz brings both book-club threads (four mails); Rui brings the owner's unanswered
  lunch mail; João brings his two threads and, from the hikers' list thread, only his mail and the
  owner's; nothing else.
- Verify: `python -m pytest -q tests/test_mail_senders.py`
- [x] done

### T03: Through the service and the command line

- `caixa/service.py`: `mail.senders`, `mail.choose`, `mail.ignore` (write), `mail.owner`,
  `mail.owner.set` (write), `mail.selection`; cleaning uses the confirmed owner addresses;
  `caixa/cli.py`: `caixa mail senders PATH [--account]`, `caixa mail choose ADDRESS… [--forget]`,
  `caixa mail ignore ADDRESS… [--forget]`; protocol list.
- Tests (`tests/test_mail_service.py`): the categories through the service with the box's people;
  decisions remembered across a reset and for a Cleaned child; the owner's addresses proposed and
  confirmed; the selection's counts; the commands.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: senders.listing lists every sender but the owner plus the owner's correspondents who never wrote back (decided while planning: otherwise a known person the owner wrote to but who never answered could not be chosen, and the owner's unanswered mail would never reach their page). A known-by-address sender is in Known and To import; an unknown chosen one only in To import. owner.json mail: chosen, ignored (exclusive), accounts[name].owner.

### 2026-11-20
T03: mail.senders (categories + what the chosen would bring), mail.choose, mail.ignore, mail.selection, mail.owner (confirmed and proposed: master owner aliases, Sent mail's From; failing both, the commonest sender), mail.owner.set; cleaning now uses the confirmed owner addresses when there are any. 'Imported' is empty until ticket 09 records imported mail (_mail_imported). CLI: caixa mail senders|choose|ignore.
