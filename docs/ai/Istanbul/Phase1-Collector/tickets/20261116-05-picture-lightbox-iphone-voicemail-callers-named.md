---
id: 20261116-05-picture-lightbox-iphone-voicemail-callers-named
title: Picture lightbox; iPhone voicemail callers named; large pages in Caixa's viewer
type: feature
priority: medium
status: done
created: 2026-11-16
updated: 2026-11-16
closed: 2026-11-16
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-16: bring back old Chattr's picture lightbox; take iPhone voicemail callers named in file names as people. Found while doing it: Caixa's viewer served pages over 20 MB without rewriting their links, so on a long single page pictures and links would not work inside Caixa.

## Acceptance criteria

- [x] Clicking a picture on a person's page shows it full size over the page; arrows and arrow keys move between pictures; Escape, a click beside it or the cross closes it and returns to the picture
- [x] Without the script every picture is still a link to its file
- [x] Inside Caixa's viewer the lightbox runs: the policy admits exactly its SHA-256 and no other script; the frame sandbox allows scripts only under that policy
- [x] Chattr's tests fail if lightbox.js changes without its new hash being listed in harness/src/host/page-scripts.ts
- [x] Pages of any size have their links rewritten in the viewer (large ones as they are sent, cut only between tags)
- [x] Voicemail callers named in file names are named people; numbers still wait

## Context

The previous rule (no script may ever run in the viewer's frame) is replaced by: only the listed hashes may run. Inline event handlers stay blocked (no 'unsafe-inline'/'unsafe-hashes'). With scripts allowed, browsers also lazy-load pictures inside the frame, which they did not before. NEEDS MAINTAINER CONFIRMATION: none.

## Subtasks

- [x] lightbox.js in person pages; styles
- [x] Viewer: script-src by hash, frame sandbox, streamed link rewriting for large pages
- [x] Voicemail in the services shown by their own names; tests; documentation

## Implementation plan

Status: done
Current task:

### T01: lightbox.js in person pages; styles
### T02: Viewer: script-src by hash, frame sandbox, streamed link rewriting for large pages
### T03: Voicemail in the services shown by their own names; tests; documentation

## Completion report

- **Outcome:** Done.
- **Files:** tools/chattr/src/chattr/templates/{lightbox.js,page.html,base.html}, tools/chattr/src/chattr/pages.py, harness/src/host/{box-files,page-scripts}.ts, harness/src/client/pages/BrowsePage.tsx, caixa/collectors/chattr.py, tests and harness tests, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1297 passed, 6 skipped; harness vitest: 275 passed, including the lightbox opening and closing on a real page inside Caixa's viewer with no policy errors, and a 21 MB page rewritten as it is streamed.

## Review

Self-review, minors only. Checked: the hash is computed from a rendered page, so template whitespace cannot drift from it unnoticed.

## Notes

- 2026-11-16: done.
