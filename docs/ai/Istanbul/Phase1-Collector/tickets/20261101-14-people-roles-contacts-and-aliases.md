---
id: 20261101-14-people-roles-contacts-and-aliases
title: 'People: roles, contacts and aliases'
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 14.
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T01
---
## Description

Derive owner/author/sender and resolve handles to people.

## Acceptance criteria

- [ ] `--contacts` (vCard) and `--aliases` (JSON) inputs
- [ ] Owner/author/sender derived, not duplicated
- [ ] Unresolved-handle report

## Context

Phase1-Collector Tasks Breakdown item 14. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Data model — roles; F6.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

**Design:** a handle (a phone number, email address, username or name as a service shows it) is
resolved to a **person** by, in order: the aliases file, the contacts (vCard), then none. Roles are
derived, not stored twice: the *owner* is configuration (name and identifiers), the *sender* is the
message's handle → person, the *author* is the conversation's counterpart (its name or group). The
result lives in `handles.person` (and `participants.role = 'owner'`), and the legacy view shows
the person's name as the sender, so pages and exports use resolved names. Handles that match
nothing are reported for a human to link; linking is done by adding them to the aliases file.

### T01: Contacts, aliases and identifier matching (`people.py`)

- `normalize_identifier(raw, region)`: phone numbers to E.164 (region default US), emails lower
  case, anything else case-folded text.
- `Contacts.from_vcf(path, region)`: vCard (3.0/4.0, folded lines, several TEL/EMAIL per card)
  with lookup by phone, email or exact name.
- `Aliases.from_json(path)`: `{identifier or name: person}`; keys normalized like handles.
- `PeopleResolver(contacts, aliases, owner_name, owner_identifiers)`: `person_for(identifier,
  display_name)` (aliases win over contacts) and `is_owner(...)`.
- Tests: the fixture vCard, formatting variants of one number, folded and multi-value cards,
  malformed files.
- Verify: `python -m pytest -q tools/chattr/tests/test_people.py`
- [ ] done

### T02: Resolving handles in the database, and the unresolved report

- Migration 3: the legacy view's sender is the person when known.
- `DatabaseManager.resolve_people(resolver, service=None)`: sets `handles.person`; marks the
  owner's handles (`person` = owner, participant role `owner`, their messages `is_from_owner`);
  returns counts and the unresolved handles (service, identifier, display name, message count,
  first and last time).
- Re-resolving is idempotent and never overwrites a person already set unless the alias or
  contact now says otherwise.
- Tests: fixture import + the fixture contacts; owner derivation; unresolved list.
- Verify: `python -m pytest -q tools/chattr/tests/test_people_resolution.py`
- [ ] done

### T03: `--contacts`, `--aliases`, owner settings and `chattr-cli people`

- `--contacts` and `--region` apply to every service (iMessage keeps naming senders from them);
  every convert resolves people afterwards and prints how many handles are unresolved.
- Owner from `--owner` or `global.owner.name` / `.identifiers`.
- `chattr-cli people [--contacts F] [--aliases F] [--owner NAME] [--json]` re-resolves the
  archive and lists the unresolved handles.
- Tests: end-to-end per service, the report, the CLI.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
