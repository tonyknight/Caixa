---
id: 20261114-01-test-round-fixes-stale-interface-google-voice
title: 'Test round fixes: stale interface, Google Voice, Contacts setting, speech-to-text
  progress'
type: feature
priority: medium
status: done
created: 2026-11-14
updated: 2026-11-14
closed: 2026-11-14
notes: Done; four choices need maintainer confirmation
parent:
depends_on: []
subtasks: []
---
## Description

The maintainer's test of 2026-11-13 found: no Test button for translation and no change to the page that would not scroll; a large Google Voice preview overflowing; a question whether Google Voice's three kinds of file (mp3, html, jpg) are all handled, with a request to file its mp3 as m4a; no Contacts section in Settings and a vCard asked for at every import; and no feedback while speech-to-text runs.

## Acceptance criteria

- [x] `caixa serve` rebuilds the interface when its source is newer than its build (after a git pull) and says so; Settings shows when the interface was built
- [x] Google Voice: a picture is found though the page links it without its extension; video too; 'MMS Received' placeholders are dropped; a day on which only the owner wrote joins the right conversation; a group is one conversation whoever wrote; a voicemail mp3 with no page is imported; no recording is imported twice
- [x] mp3 recordings are filed as m4a at their own bit rate; an mp3 that will not convert is filed as it is without a warning
- [x] Settings has a Contacts section: this Mac's Contacts (on by default), a contacts file given once, the phone region; every import of every source uses them; Settings shows how many people each can name, or why not
- [x] A saved contacts file that is missing is refused on save and explained at import
- [x] Speech-to-text is a stage of its own with a count, the time left and per-recording timing; the same lines are in the job's log and in the terminal that started `caixa serve`

## Context

ROOT CAUSE of 'no visible change': harness/lib/ is not kept in git and `caixa serve` only checked that it existed, so after every pull the browser kept the interface from the first build while the Python side was new. The scroll fix (ticket 20261112-02) and the Test button (20261113-02) were in the source and passing in a real browser; they never reached the maintainer's browser. The harness addresses plugin bundles by content hash, so browser caching was not the cause. NEEDS MAINTAINER CONFIRMATION: (1) the per-import 'Contacts file' option stays in the wizard, pre-filled from Settings, rather than being removed; (2) 'Use this Mac's Contacts' defaults to on; (3) mp3 is converted for every chat source, not only Google Voice; (4) whisper.cpp is still started once per recording (the model is loaded each time): batching recordings into one run would be faster and is not done here.

## Subtasks

- [x] Rebuild the interface when stale; build time in Settings
- [x] Google Voice: real Takeout cases; mp3 to m4a
- [x] Contacts as a box setting used by every import, with a check
- [x] Speech-to-text progress: stage, timing, job log, terminal

## Implementation plan

Status: done
Current task:

### T01: Rebuild the interface when stale; build time in Settings
### T02: Google Voice: real Takeout cases; mp3 to m4a
### T03: Contacts as a box setting used by every import, with a check
### T04: Speech-to-text progress: stage, timing, job log, terminal

## Completion report

- **Outcome:** All four done. serve.ensure_built compares the newest of harness/src, scripts and package.json with lib/. The Google Voice parser reads pages in two passes so names can be matched to numbers. Contacts are box settings (contacts.mac, contacts.file, contacts.region) applied in one place for every source. TimedTranscriber wraps the engine; lines marked '[caixa] ' on the worker's error stream are echoed by `caixa serve`.
- **Files:** caixa/{serve,service,settings}.py, caixa/collectors/chattr.py, tools/chattr/src/chattr/{filing,commands,transcription}.py, tools/chattr/src/chattr/parsers/google_voice_parser.py, harness/scripts/preset.mjs, harness/src/client/{api,locales}.ts, harness/src/client/pages/SettingsPage.tsx, harness/src/client/components/Progress.tsx, tests (test_serve, test_serve_launch, test_contacts_setting, test_transcription_progress, test_chattr_collectors, fake_dsh), tools/chattr/tests/{test_google_voice_parser,test_filing}.py, harness/tests, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1250 passed, 6 skipped (Node not on PATH); harness vitest: 268 passed; tsc, black, mypy clean. The rebuild was run for real here (stale, rebuilt, current; new strings present in lib/client.js). NOT verified: a real Google Voice Takeout (the cases are written from the format as documented and the maintainer's examples); real Mac Contacts and the Full Disk Access message; a real speech model.

## Review

Self-review, minors only. Checked: only lines carrying the mark reach the terminal, and they pass through the same redaction as the log; the progress callback travels in a private options key that never reaches validation or the saved job options; without a box nobody's Contacts are read (previews in tests).

## Notes

- 2026-11-14: done; four choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
