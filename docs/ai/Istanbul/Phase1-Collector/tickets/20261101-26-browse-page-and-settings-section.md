---
id: 20261101-26-browse-page-and-settings-section
title: Browse page and Settings section
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: Breakdown item 26.
parent:
depends_on:
- 20261101-24-import-wizard-and-jobs-pages
subtasks: []
plan_status: done
---
## Description

View the box and configure Caixa in the browser.

## Acceptance criteria

- [x] Generated pages served through `/api/caixa/box/*`
- [x] Settings: box location, local model endpoints, privacy defaults

## Context

Phase1-Collector Tasks Breakdown item 26. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Authoring pages; F19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:** Two more sections. **Browse:** the box's folders and files with a breadcrumb and a viewer:
  generated pages in a frame that cannot run scripts (with "open in a new tab"), photos, audio and video
  inline, anything else as a download; a shortcut to the box's index page; `.caixa/` is never shown.
  **Settings:** the box's location and a form drawn from the schema the worker publishes (privacy default,
  local translation endpoint and model, speech-to-text model and language), saved as changes against what
  is stored (so a setting put back to its default is still saved), with the worker's validation errors
  listed; read-only boxes show the values and cannot change them. The host serves the box's files at
  `GET|HEAD /api/caixa/box?path=…` (owner-only like every Caixa route): the worker validates the path, the
  host streams the file; generated pages have their relative links rewritten to the route; every response
  carries a strict Content-Security-Policy (no scripts), `nosniff`, and anything but pages, text, common
  images, audio and video is sent as an attachment; audio and video honour byte ranges.
- **Deviation from the Requirements:** the route is `/api/caixa/box?path=` rather than `/api/caixa/box/*`
  because DSH's fetch routes match exact paths only (checked in its connection package), so a prefix cannot
  be registered; the link rewriting is what that costs.
- **Verified in a real browser against the real DSH and worker:** after importing a chat and a mailbox, the
  page opens from the folder tree with its text and its photo (the photo loads through the route), the
  index page's links work inside the frame, the response policy is as stated, paths out of the box
  (`../`, `.caixa/`, absolute) and requests without the sign-in cookie are refused, and a changed setting
  is saved and kept across a reload.
- **Files:** `harness/src/host/box-files.ts`, `routes.ts`; `harness/src/client/pages/{Browse,Settings}Page.tsx`,
  `options-form.ts`, `api.ts`, `locales.ts`, `CaixaPage.tsx`, `caixa.module.css`; `harness/tests/*`.
- **Errors:** after a reload DSH shows its first-run dialogs again, which covered the page in the e2e test
  (the dialog dismissal is now a helper used on every load); otherwise the unit and browser tests passed on
  their first runs.
- **Verify:** `pnpm --dir harness test` 194 passed (including the four end-to-end files against real DSH);
  `check-types` clean; Python suite, black and mypy clean.

## Review

Reviewed in-session. Accepted: DSH's own `settings.section` slot is not used (the settings live in the
Caixa page; registering there too is a small later addition); the page frame relies on `sandbox` plus the
policy rather than serving pages from a separate origin; HEIC photos and PDFs are downloads, not previews;
a very large box lists a whole folder at once (no paging yet); the privacy default is stored and shown but
not yet applied to newly imported items (ticket 21's known gap). No blockers.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01-T03 done. NEEDS MAINTAINER CONFIRMATION: the route `/api/caixa/box?path=` instead of `/api/caixa/box/*` (DSH limitation); the sections "Browse" and "Settings"; no separate DSH `settings.section` entry; the response policy (no scripts at all in served pages).
