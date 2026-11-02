---
id: 20261101-02-synthetic-fixture-family
title: Synthetic fixture family
type: feature
priority: high
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: deterministic synthetic family for all six sources + vCard; build_all
  and fixture_family fixture.'
parent:
depends_on:
- 20261101-01-caixa-repository-foundations
- 20261101-03-chattr-import-and-licensing
subtasks: []
plan_status: done
---
## Description

Build a fictional family's synthetic exports for every Phase 1 source, used by all tests. No real data, ever.

## Acceptance criteria

- [x] A builder script creates a synthetic iMessage `chat.db` (long attributedBody messages, both epoch formats, same-second attachments, tapbacks on attachments, a group chat)
- [x] WhatsApp exports in iOS and Android formats with media and 'media omitted' lines
- [x] Messenger/Instagram JSON with mojibake text, shares and attachments
- [x] An MBOX with RFC 2047 headers, HTML-only mail, attachments and threads
- [x] A Google Voice Takeout sample (texts, calls, voicemails with audio) and iPhone voicemail audio + metadata
- [x] A vCard file linking the family's handles
- [x] Fixtures are generated deterministically and contain only fictional names and numbers

## Context

Phase1-Collector Tasks Breakdown item 2. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Acceptance criteria; Testing requirements.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design**
- One data definition of a fictional family drives builders that write each export format into a
  target folder.
- Builders use the Python standard library only, so they don't depend on Chattr's code, which
  ticket 04 restructures.
- Location: `tools/chattr/tests/fixtures/`, so Chattr can run its own tests after mirroring;
  Caixa's tests reuse it. Tests go in `tools/chattr/tests/`.
- Fictional data only:
  - US phone numbers in the 555-0100…0199 range reserved for fiction;
  - email addresses at `example.com`/`example.org`;
  - invented names.
- **Cast:** owner Maria Costa; daughter Ana Costa (iMessage, WhatsApp, Google Voice, for the
  cross-platform merge); brother João Costa (Messenger, MBOX); friend Rui Pereira (WhatsApp
  Android, Instagram); the group "Costa Family" (iMessage); one unknown handle, 555-0199, for the
  unresolved-handle test.
- **Format assumptions** (which tables, file names and HTML classes each export uses) are
  recorded in `tools/chattr/tests/fixtures/README.md`, to be checked against real exports before
  release.
- Root pytest gains `tools/chattr/tests` in `testpaths` and `--import-mode=importlib`, so both
  suites run from the root.

### T01: Family definition and vCard

- Files: `tools/chattr/tests/fixtures/family.py` (people, handles, conversations, fixed
  timestamps), `tools/chattr/tests/fixtures/builders/vcard.py`, `tools/chattr/tests/conftest.py`,
  `tools/chattr/tests/test_fixture_vcard.py`; root `pyproject.toml` (`testpaths`, import mode).
- Tests:
  - every known handle appears in the vCard;
  - all numbers are in 555-01xx and all emails are at example domains;
  - the unknown handle is absent;
  - two builds are byte-identical.
- Verify: `python -m pytest tools/chattr/tests -q`
- [x] done

### T02: Synthetic iMessage `chat.db`

- Files: `builders/imessage.py`, `tests/test_fixture_imessage.py`.
- Tables: `handle`, `chat` (style 43 group / 45 single), `chat_handle_join`, `message`,
  `chat_message_join`, `attachment`, `message_attachment_join`, with the columns Chattr reads.
  Attachment files go under `Attachments/`, referenced as `~/Library/Messages/Attachments/…`.
- Cases:
  - a message over 255 characters stored **only** in `attributedBody`, as an NSAttributedString
    typedstream with the `0x81` two-byte length form;
  - both seconds and nanoseconds `date` epochs;
  - two attachments with the same timestamp in one message;
  - tapbacks on text (`p:0/`), on an attachment (`p:1/`) and with `bp:`, plus a removal (3000s);
  - a three-person group chat;
  - a message from the unknown handle.
- Tests assert each case through SQL and on disk.
- Verify: `python -m pytest tools/chattr/tests -q`
- [x] done

### T03: WhatsApp exports (iOS, Android, US locale)

- Files: `builders/whatsapp.py`, `tests/test_fixture_whatsapp.py`.
- Three `_chat.txt` variants:
  - iOS: `[YYYY-MM-DD, HH:MM:SS] Name: …` with U+200E marks, `<attached: …>`, `image omitted`;
  - Android: `DD/MM/YYYY, HH:MM - Name: …`, `(file attached)`, `<Media omitted>`;
  - US: `M/D/YY, H:MM AM - …`.
- Each has multi-line messages with indentation and real media files (PNG/GIF).
- Verify: `python -m pytest tools/chattr/tests -q`
- [x] done

### T04: Messenger and Instagram JSON

- Files: `builders/meta.py`, `tests/test_fixture_meta.py`.
- Download Your Information layout: `messages/inbox/<thread>/message_1.json`, plus the Instagram
  equivalent.
- Messages newest first, `timestamp_ms`, photos with `uri`, a `share`, reactions.
- All text double-encoded the way Facebook does it (UTF-8 bytes read as latin-1). A test proves
  the encoding fix recovers the original.
- Verify: `python -m pytest tools/chattr/tests -q`
- [x] done

### T05: MBOX email

- Files: `builders/mbox.py`, `tests/test_fixture_mbox.py`.
- Built with the standard `email`/`mailbox` modules:
  - RFC 2047 encoded `Subject`/`From`;
  - an HTML-only message;
  - a multipart/alternative message;
  - a PNG attachment;
  - a thread linked by `Message-ID`/`In-Reply-To`/`References`;
  - `X-GM-THRID` and `X-Gmail-Labels` headers;
  - dates with different offsets.
- Verify: `python -m pytest tools/chattr/tests -q`
- [x] done

### T06: Google Voice Takeout and iPhone voicemail

- Files: `builders/voice.py`, `tests/test_fixture_voice.py`.
- **Google Voice**: `Takeout/Voice/Calls/<Name> - <Kind> - <timestamp>.html` for texts, received,
  placed and missed calls, and voicemails. Pages use the hAtom/hCard-style classes. Each
  voicemail has an audio file and a transcript.
- **iPhone**: `voicemail.db` (table `voicemail`) plus one audio file per row.
- Audio payloads are short PCM WAV data whatever the extension, because the standard library
  can't encode MP3/AMR. Parsers must not trust extensions, and speech-to-text tests use a stub.
- Verify: `python -m pytest tools/chattr/tests -q`
- [x] done

### T07: `build_all`, determinism and documentation

- Files: `tools/chattr/tests/fixtures/__init__.py` (`build_all(out_dir)`), a session-scoped
  `fixture_family` pytest fixture in `conftest.py`, `tests/test_fixture_family.py`,
  `tools/chattr/tests/fixtures/README.md`, `tests/fixtures/README.md` (Caixa side, pointing to
  Chattr's builders).
- Tests:
  - `build_all` creates every source;
  - two builds are identical: byte-identical text and media files, and identical logical dumps
    for SQLite files.
- Verify: `python -m pytest -q` (root, both suites) `&& python -m black --check . && python -m mypy caixa`
- [x] done

## Review

2026-11-02. Commits `5c531d4` (T01), `8f0f07c` (T02), `dfac30a` (T03), `cabb0e9` (T04),
`5a19e94` (T05), `23c3f69` (T06), `e7ce69e` (T07). **Verdict: clean, minors only.**
- **Spec:** all seven acceptance criteria met. Each export has tests for its specific cases
  (41 fixture tests), plus a whole-family determinism test.
- **TDD:** every task went RED (missing module) and then GREEN. T05 added a determinism test
  that went RED for a real bug before the fix. T04's single failure was a test path error,
  recorded in Notes.
- **Data:** a scan found only 555-01xx phone numbers and example.com/org email addresses. Only
  source and docs are committed (no caches or databases).
- **Commits** are authored by Tony Knight.
- **Minor:** format assumptions (Google Voice HTML classes, iPhone `voicemail.db` columns, Meta
  folder names) come from public descriptions, not real exports. They are recorded in
  `tools/chattr/tests/fixtures/README.md` to verify before release.
- **Minor:** audio is WAV whatever the extension, and there's no HEIC sample (standard-library
  limits). Both are documented; ticket 13 needs its own HEIC asset.
- **Minor:** `tools/chattr` stays excluded from `black --check` until ticket 04. The new fixture
  code was formatted with black anyway.

## Completion report

- **Outcome:** a deterministic synthetic fixture family (standard library only) for all six
  Phase 1 sources plus contacts, with `build_all()` and a session-scoped `fixture_family` pytest
  fixture. Root `pytest` runs Caixa's and Chattr's suites together.
- **Files:** `tools/chattr/tests/` (`conftest.py`, `fixtures/` with `family.py`, `builders/`
  for vcard, imessage, whatsapp, meta, mbox, voice, media, plus `README.md`, and seven
  `test_fixture_*.py` files); `tests/fixtures/README.md`; `pyproject.toml` (pytest `testpaths`,
  importlib mode).
- **Errors:**
  - **MBOX determinism bug:** random MIME boundaries and current-time From_ lines; fixed in T05.
  - **Test path error in T04:** fixed.
- **Verify:** `python -m pytest -q` → 43 passed; `python -m black --check .` → clean;
  `python -m mypy caixa` → no issues.

## Notes

Append-only running log. Each entry dated.

### 2026-11-01
Now depends on ticket 03: the message-source fixture builders live in Chattr's test tree (tools/chattr/tests/fixtures/, a location named in the Requirements), so standalone Chattr can run its own tests after mirroring; Caixa's tests reuse them. That folder exists only after the Chattr subtree import.

### 2026-11-02
T04: first GREEN run failed one test because the test computed the export root as path.parents[3] (one level short); the builder was right. Fixed the test (parents[4]) and documented the folder chain.

### 2026-11-02
T05: the first MBOX build was not deterministic (random MIME boundaries from the email package; mailbox stamps the current time on From_ lines). Added a byte-identity test (RED), then fixed boundaries and derived From_ lines from each message's Date (GREEN).
