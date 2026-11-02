---
id: 20261101-07-imessage-parser
title: iMessage parser
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 7.
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T01
---
## Description

Move the working iMessage reader behind `BaseParser` and into the database, with the review fixes.

## Acceptance criteria

- [ ] attributedBody is decoded with a real typedstream decoder; long messages are not truncated
- [ ] Both seconds and nanoseconds epochs handled; UTC + offset stored
- [ ] Spam filter runs on the parallel path and tags rather than drops
- [ ] Tapbacks on attachments (`p:1/`, `bp:`) attach to their targets
- [ ] All tools open `chat.db` read-only

## Context

Phase1-Collector Tasks Breakdown item 7. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — Carry forward / Fix; F1–F3.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

**Design:** the existing reader (`parsers/imessage_database_parser.py`) is kept and fixed, not
rewritten. A new `IMessageParser(BaseParser)` sits on top: `parse(chat.db)` returns normalized
`MessageRecord`s grouped by conversation, which `commands.convert_imessage` imports into the
central archive (default route) or writes as native JSON (`--json`). Fixes are made in the
reader so the native-JSON path benefits too.

**Decisions (open question "typedstream decoder"):** a small purpose-built decoder in
`chattr/typedstream.py` rather than a new dependency. It only needs the `NSString` payload of an
`NSAttributedString`, and the fixture family exercises the length encodings. The old heuristic
stays as a fallback for blobs the decoder rejects. To be confirmed against a real export.

### T01: Typedstream decoder for attributedBody

- `typedstream.attributed_text(blob) -> str | None`: reads the stream header, finds the
  `NSString` object and decodes its length-prefixed UTF-8 payload (1-byte length, `0x81` +
  2 bytes LE, `0x82` + 4 bytes LE). Returns None for anything that isn't a valid stream.
- `_extract_text_from_attributed_body` tries the decoder first, then the old heuristics.
- Tests: the fixture's long message (over 255 bytes) is complete; multi-byte characters; emoji;
  a truncated blob returns None; the parser returns the full long message from `chat.db`.
- Verify: `python -m pytest -q tools/chattr/tests/test_typedstream.py`
- [ ] done

### T02: Epochs, UTC and offset

- `apple_timestamp_to_datetime(value)`: seconds when the value is below 1e11, nanoseconds
  otherwise; returns timezone-aware UTC. 0/None → no time.
- Messages carry `timestamp` (aware UTC). The unified record stores `timestamp_utc`,
  `time_precision="second"`, and no offset (the database doesn't record one); `tz_assumed` is
  false because Apple stores UTC.
- Tests: the fixture's 2016 messages (seconds) land in 2016, 2023+ (nanoseconds) in the right
  hour; both epochs convert to the same UTC instant; native JSON timestamps are unchanged in
  shape.
- Verify: `python -m pytest -q tools/chattr/tests/test_imessage_time.py`
- [ ] done

### T03: Spam filter on every path, tagging instead of dropping

- One `_row_to_message` shared by the single-threaded and parallel paths; the filter result is
  stored on the message as `spam_reason` (None when kept) instead of skipping it. Stats are
  counted under a lock.
- Native JSON and records carry `spam_reason`; `--spam-mode disabled` leaves it empty.
- Tests: the fixture's "package could not be delivered" message from an unknown number is tagged
  on both paths with identical stats; nothing is dropped; disabled mode tags nothing.
- Verify: `python -m pytest -q tools/chattr/tests/test_imessage_spam.py`
- [ ] done

### T04: Tapbacks attach to their targets

- `get_tapbacks_for_message` matches `p:<n>/<guid>`, `bp:<guid>` and bare GUIDs; the component
  index (`p:<n>`) selects the target part. Parts are the message text (when present) followed by
  its attachments in order.
- Native JSON puts attachment tapbacks on the attachment they target; records carry
  `ReactionRecord(target_part=…)`. Removed tapbacks (3000-series) are recorded as removals.
- Tests: the fixture's `p:0/`, `p:1/` (attachment), removed like and legacy `bp:` forms.
- Verify: `python -m pytest -q tools/chattr/tests/test_imessage_tapbacks.py`
- [ ] done

### T05: IMessageParser behind BaseParser, into the database

- `IMessageParser(BaseParser)`: `parse(path)` returns `list[ConversationBatch]` (conversation
  record + message records); a `records()` helper does the grouping per chat.
- `commands.convert_imessage(..., route="central"|"service")`: central imports per conversation
  with stable ids (the iMessage GUID), re-import is idempotent; service route writes native JSON
  as before. `chattr-cli convert imessage` accepts `--db`/`--json`; the menu asks the
  destination.
- Tests: central import of the fixture; second run inserts nothing; group chat typed `group`
  with its name; owner messages flagged; state file updated.
- Verify: `python -m pytest -q`
- [ ] done

### T06: Every tool opens chat.db read-only

- The four read-write `sqlite3.connect` calls in `imessage_tools.py` use `mode=ro` URIs.
- Tests: a static scan that no iMessage module opens a connection without `mode=ro`; a
  behavioural check that the diagnostics run on a read-only copy and leave the file's bytes
  unchanged.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
