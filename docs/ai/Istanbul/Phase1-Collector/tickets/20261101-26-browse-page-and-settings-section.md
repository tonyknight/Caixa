---
id: 20261101-26-browse-page-and-settings-section
title: Browse page and Settings section
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 26.
parent:
depends_on:
- 20261101-24-import-wizard-and-jobs-pages
subtasks: []
current_task: T03
plan_status: in-progress
---
## Description

View the box and configure Caixa in the browser.

## Acceptance criteria

- [ ] Generated pages served through `/api/caixa/box/*`
- [ ] Settings: box location, local model endpoints, privacy defaults

## Context

Phase1-Collector Tasks Breakdown item 26. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Authoring pages; F19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T03

**Design:** two more sections, Browse and Settings.

- **Serving the box's pages:** the Requirements say `/api/caixa/box/*`, but DSH's fetch routes are exact
  paths, not prefixes (checked in its connection package), so the route is `GET|HEAD /api/caixa/box?path=<relative path>`.
  The host asks the worker (`browse.file`) to validate the path (it refuses anything outside the box and
  anything under `.caixa/`) and then streams the file from disk. Generated pages link to each other and to
  their photos with relative URLs, which would break under a query-string route, so served HTML has its
  relative `href`/`src`/`poster` links rewritten to the same route. Every response carries a strict
  Content-Security-Policy (no scripts, own-origin images and media only), `nosniff`, and files that are
  not pages or media are sent as attachments. Audio and video honour `Range` requests so they can seek.
- **The Browse section:** the box's folders and files (`browse.list`), a breadcrumb, and a viewer: pages in
  a sandboxed frame (plus "open in a new tab"), images, audio and video inline, anything else as a
  download link. Hidden: `.caixa/`.
- **The Settings section:** the box's location, and a form drawn from the settings schema the worker
  publishes (`settings.get`): privacy default, translation (off by default, local endpoint and model) and
  speech-to-text model. Saved with `settings.set`; the worker's own validation errors are shown beside the
  form; read-only boxes show the values but cannot change them.
- **Names to confirm with the maintainer:** the route `/api/caixa/box?path=` instead of `/api/caixa/box/*`;
  the sections "Browse" and "Settings"; no separate DSH `settings.section` entry (the settings live in the
  Caixa page).

### T01: Serving the box's files

- `src/host/box-files.ts` and its route; link rewriting; CSP and attachment rules; `Range`.
- Tests: unit tests against a temp box: pages with rewritten links, photos and audio (with ranges),
  containment (`..`, absolute paths, `.caixa`, links out), headers, errors; the route table.
- Verify: `pnpm --dir harness test`
- [x] done

### T02: The Browse and Settings sections

- API wrappers; `BrowsePage`, `SettingsPage`; the settings form model against the current values; locales
  (English, Chinese); navigation.
- Tests: jsdom for both sections, and the form model.
- Verify: `pnpm --dir harness test`
- [x] done

### T03: In the real browser

- End to end: browse from the root to a page and see it (text, its photo, a link to another page);
  change a setting and see it saved and kept across a reload; the worker's validation errors show.
- Verify: `pnpm --dir harness test` (with Node 24.9+)
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
