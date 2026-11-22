---
id: 20261122-06-apple-intelligence-first-when-available
title: Apple Intelligence first, when available
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: Automatic (Apple Intelligence first) is the default for summaries and
  translation.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

The maintainer's benchmark found Apple Intelligence far better for both summaries and translations, and asked for a global rule: use it, when available, as the primary method for all such tasks.

## Acceptance criteria

- [x] Summaries and translations have a third choice, **Automatic** (Apple Intelligence when this Mac can use it, otherwise the endpoint), and it is the default for both
- [x] Boxes whose choice was "An endpoint" from before this (the old default) become Automatic once; a choice made after this is kept
- [x] With Automatic: Apple Intelligence is used whenever it is ready (also when no endpoint is set); otherwise the endpoint, and a missing endpoint is a problem only when Apple Intelligence cannot be used
- [x] The Settings page and Sort mail's switches know Automatic (a switch is set up when Apple Intelligence is ready or an endpoint is set)

## Context

Follows the benchmark (`20261122-05`) and tickets 19–20. `caixa/{settings,summaries,translation,apple_intelligence,service}.py`, `web/src/client/mail/SortMail.tsx`. Requirements: *Hot fixes*, Apple Intelligence; M19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `summaries.provider` and `translation.provider` gain `auto` ("Automatic: Apple
Intelligence when this Mac has it, otherwise the endpoint"), the new default. `apple(values)` (the
one place both modules decide) is true for `apple`, and for `auto` when
`apple_intelligence.available()`: its check (building the helper the first time), remembered for
ten minutes. Everything else (model name, budget, workers, client, Test, problems) follows from
it, so with Automatic a missing endpoint is only a problem when Apple Intelligence cannot be used.
`box.yaml` gains `settings_version: 2`; loading settings saved before it turns `endpoint` (the old
default) into `auto` once, and saving writes the version, so a choice made afterwards stays.
`settings.get` says whether Apple Intelligence is ready (`apple`), and Sort mail's switches count
Automatic as set up when it is, or when an endpoint is set.

### T01: Automatic, the default, and moving old boxes to it

- `caixa/{apple_intelligence,settings,summaries,translation,service}.py`, `web/src/client/mail/SortMail.tsx`,
  `web/src/client/api.ts`, the built window, `docs/Documentation/Collector.md`.
- Tests: the default is Automatic; with the stand-in ready, Automatic summarizes and translates
  through Apple Intelligence with no endpoint set; with it not ready, Automatic uses the endpoint;
  with neither, saving summaries on is refused saying both; an old box's `endpoint` reads as
  Automatic, a new explicit `endpoint` stays; `settings.get` carries `apple`; Sort mail counts
  Automatic as set up when Apple Intelligence is ready.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** Summaries and translations use Apple Intelligence whenever the Mac can, through a new default choice, Automatic, that falls back to the endpoint otherwise. Boxes still on the old default ("An endpoint") moved to Automatic once; choosing An endpoint or Apple Intelligence still works and is kept.
- **Files:** `caixa/{apple_intelligence,settings,summaries,translation,service}.py`, `web/src/client/{api.ts,mail/SortMail.tsx,pages/SettingsPage.tsx}`, `caixa/data/web/*`, `docs/Documentation/Collector.md`; tests `tests/{test_summaries,conftest}.py`, `web/tests/{sort-mail,settings-page}.test.tsx`.
- **Errors:** none beyond the expected change of an older test (it now chooses An endpoint explicitly).
- **Verify:** `python -m pytest -q` 1480 passed, 1 skipped; black and mypy clean; web `tsc` clean, vitest 267 passed.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: a box where someone had deliberately chosen An endpoint before today is moved to Automatic too (it cannot be told from the old default); choosing it again keeps it.
- Minor: whether Apple Intelligence can be used is remembered for ten minutes, so turning it on in macOS takes up to ten minutes (or a restart of `caixa serve`) to be noticed.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: providers gain 'auto' (Automatic), the default for both; summaries.apple()/translation.apple() are true for apple, and for auto when apple_intelligence.available() (check, building the helper the first time; remembered 10 minutes; forget() for tests via conftest). With Automatic a missing endpoint is a problem only when Apple Intelligence cannot be used (its own wording). box.yaml settings_version 2: settings saved before read 'endpoint' as 'auto' once; saving writes the version. settings.get carries apple {ready, message}; Sort mail counts Automatic as set up when it is ready or an endpoint is set; Settings' Test falls back to auto. Collector.md updated. RED: 5 Python and 1 web test, then GREEN; the old no-endpoint message test now chooses 'endpoint' explicitly. Full verify: pytest 1480 passed, vitest 267 passed.
