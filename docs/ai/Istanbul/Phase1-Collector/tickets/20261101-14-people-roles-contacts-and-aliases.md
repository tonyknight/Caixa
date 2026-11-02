---
id: 20261101-14-people-roles-contacts-and-aliases
title: 'People: roles, contacts and aliases'
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: contacts, aliases, owner, unresolved report; people command.'
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Derive owner/author/sender and resolve handles to people.

## Acceptance criteria

- [x] `--contacts` (vCard) and `--aliases` (JSON) inputs
- [x] Owner/author/sender derived, not duplicated
- [x] Unresolved-handle report

## Context

Phase1-Collector Tasks Breakdown item 14. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Data model — roles; F6.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

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
- [x] done

### T03: `--contacts`, `--aliases`, owner settings and `chattr-cli people`

- `--contacts` and `--region` apply to every service (iMessage keeps naming senders from them);
  every convert resolves people afterwards and prints how many handles are unresolved.
- Owner from `--owner` or `global.owner.name` / `.identifiers`.
- `chattr-cli people [--contacts F] [--aliases F] [--owner NAME] [--json]` re-resolves the
  archive and lists the unresolved handles.
- Tests: end-to-end per service, the report, the CLI.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** handles (phone numbers, email addresses, usernames, names) resolve to people from the
  aliases file, then a vCard, with phone numbers compared as E.164. `--contacts`, `--aliases`,
  `--region` and `--owner` (or `global.owner` / `global.contacts` in the settings) apply to every
  service; after each conversion the service's handles are linked and the unnamed ones counted.
  The owner is derived (`handles.person`, participant role `owner`, `is_from_owner` on their
  messages), the legacy view and the JSON export show the person, and `chattr-cli people` re-links
  the whole archive and lists the handles still unnamed (busiest first, `--json` available).
- **Files:**
  - New: `people.py`.
  - Changed: `database_manager.py` (`resolve_people`, `unresolved_handles`, `person` in the JSON),
    `schema.py` (migration 3), `commands.py` (`make_resolver`, `people`, `ConvertResult.unresolved`),
    `cli.py` (`people` command, general `--contacts` / `--region`),
    `defaults/config.json` (`global.owner`).
  - Tests: `test_people`, `test_people_resolution`, `test_people_commands`, `test_schema`.
- **Errors:** none in existing code. Behaviour changes to note:
  - `--contacts` and `--region` are no longer iMessage-only, so the two usage-error cases that said
    so were replaced.
  - The unresolved report is how a human finds handles to link; linking itself is editing the
    aliases file (the People page of Caixa, ticket 25, will do it from the browser).
- **Verify:** `python -m pytest -q` → 477 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: 1af573b..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** matching a handle by name (a WhatsApp author "Ana Costa" against a card named "Ana Costa")
  can't tell two people with the same name apart.
- **Minor:** nothing separates two services' handles for one person yet: Ana's iMessage number,
  WhatsApp name and email all resolve to the person *name* "Ana Costa", but the person is only a
  string on each handle. Caixa's master (ticket 18) owns real person records and merging.
- **Minor:** the person string isn't unset when an alias or contact is later removed (resolution
  only ever adds or replaces).
- **Minor:** `is_from_owner` is only ever raised by resolution, never cleared if the owner setting
  changes; re-importing into a fresh archive fixes it.
- **Minor:** the "author" role (the conversation's counterpart) is derivable from the conversation and
  the group flag but there is no column or API for it yet; the renderer (ticket 15) needs it.
- **Minor:** vCard parsing relies on `vobject`; photos, groups and the owner's own card in the file are
  ignored. A card with no name or no phone/email is skipped silently.
- **Minor:** E.164 matching assumes one default region unless the number has a country code; a
  contacts file mixing regions without `+` prefixes will mismatch.
- **Spec:** all three acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN for every task (collection error, 10 failing, then the end-to-end set).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: people.py: normalize_identifier (E.164 via phonenumbers incl. numbers written with the country code but no '+', short codes (<7 digits) stay text; emails lower; names case-folded), Contacts.from_vcf (vobject; FN else N; a name also resolves as a handle, which is how WhatsApp/Messenger senders match), Aliases.from_json (the human's word beats contacts), PeopleResolver (owner by name or identifiers). Cards with no name or no handle are skipped; a file without vCards is an error.

### 2026-11-02
T02: DatabaseManager.resolve_people(resolver, service=None) sets handles.person (aliases, then contacts; an existing person is kept unless something now names someone else), derives the owner (person = owner name, participants.role = 'owner', their messages is_from_owner = 1 — never unset), and returns PeopleResult(newly_resolved, owner_handles, unresolved[]). unresolved_handles() lists handles with no person, busiest first (service, identifier, display name, message count, first/last seen). Schema migration 3: the legacy view's sender is COALESCE(person, display_name, identifier), so resolved names reach pages and JSON. Owner derivation reads config each time; the DB only stores the resolved result.

### 2026-11-02
T03: make_resolver builds the resolver from --contacts/--aliases/--owner/--region, falling back to global.contacts and the new global.owner {name, identifiers}; a bad contacts or aliases file stops the run before anything is imported (CommandError). convert resolves the imported service's handles inside the same database session, before pages/JSON are written. New 'chattr-cli people' (re-resolve everything; list unresolved; --json). Parser-time alias renaming is kept (service-route JSON needs names); the JSON export now also carries each message's person.
