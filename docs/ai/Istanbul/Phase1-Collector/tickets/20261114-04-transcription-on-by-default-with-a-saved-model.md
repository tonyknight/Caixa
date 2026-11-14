---
id: 20261114-04-transcription-on-by-default-with-a-saved-model
title: Transcription on by default with a saved model; show which code is running
type: feature
priority: medium
status: done
created: 2026-11-14
updated: 2026-11-14
closed: 2026-11-14
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Two things from the maintainer's test of 2026-11-14. (1) Decision: transcription should be on by default once a speech model is saved in Settings. (2) Report: after ticket 20261114-03 the Google Voice import still showed no transcription option and its log showed no transcribing stage. The option is in the code (the collector's schema lists transcribe, model and language), so the Caixa that ran the import was older than that commit: either not pulled, or still running from before the pull. Nothing in Caixa said which.

## Acceptance criteria

- [x] 'Transcribe on this computer' starts ticked, for iPhone voicemail and Google Voice, once a speech model is saved in Settings; unticked until then; unticking skips it for that import
- [x] An import started without mentioning the option (command line, Run again) follows the saved model
- [x] Settings shows the version, the commit and when the running Caixa started
- [x] When the code on disk is newer than the running process, Settings shows a restart notice and `caixa serve` (already running) says so
- [x] `caixa serve` prints the commit when it starts

## Context

A running worker keeps the Python it loaded; ticket 20261114-01 handled the browser half (rebuilt when stale) but not this. The check compares the newest modification time of the Python sources with the process start time. NEEDS MAINTAINER CONFIRMATION: none.

## Subtasks

- [x] Transcribe follows the saved speech model unless said otherwise
- [x] Commit, start time and restart notice in worker.info, Settings and caixa serve; documentation

## Implementation plan

Status: done
Current task:

### T01: Transcribe follows the saved speech model unless said otherwise
### T02: Commit, start time and restart notice in worker.info, Settings and caixa serve; documentation

## Completion report

- **Outcome:** Done. caixa/revision.py reads the commit from .git without running git and compares source times with a start time.
- **Files:** caixa/{revision,worker,serve,service}.py, caixa/collectors/chattr.py, harness/src/client/{api,locales}.ts, harness/src/client/pages/SettingsPage.tsx, tests/{test_revision,test_transcription_progress,test_chattr_collectors}.py, harness/tests/{settings-page.test.tsx,e2e-voicemail.test.ts}, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q passes; harness vitest: 270 passed; tsc, black, mypy clean. The cause of the missing option is inferred from the code, not observed on the maintainer's machine: the commit line in Settings will confirm it.

## Review

Self-review, clean. Checked: the restart notice cannot appear for a freshly started worker (source times precede its start); a checkout without .git shows an unknown commit rather than failing.

## Notes

- 2026-11-14: done.
