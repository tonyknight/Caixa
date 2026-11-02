---
id: 20261101-22-harness-plugin-skeleton
title: Harness plugin skeleton
type: feature
priority: high
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: Breakdown item 22.
parent:
depends_on:
- 20261101-21-caixa-service-layer-and-caixa-worker
subtasks: []
plan_status: done
---
## Description

The Caixa plugin for DeepSeek Harness in `harness/`.

## Acceptance criteria

- [x] Pinned dsh version + `engines.dsh`; reproduced client build preset
- [x] Host service supervises `caixa worker`; owner-only `/api/caixa/*` routes plus a streaming progress route
- [x] Sidebar icon opens an empty Caixa page
- [x] `pnpm --dir harness test` passes

## Context

Phase1-Collector Tasks Breakdown item 22. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application; F18; N6; N8.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** the plugin has two halves. The *host half* runs in DSH under Node: it starts `caixa worker`
through DSH's subprocess service, keeps it alive, and registers owner-only `/api/caixa/*` routes on
DSH's connection (so DSH's token, signed cookie and Host/Origin checks apply and the worker has no
network listener). The *browser half* registers a sidebar icon and a page in DSH's slots and talks to
Python only through those routes. Node 24.9+ and the pinned `@deepseek-ai/dsh@0.2.2-alpha.2` install
in this environment, so everything is also exercised against the real `dsh web`.

- **Build:** DSH's client build preset is not published, so `scripts/preset.mjs` reproduces its
  contract with esbuild (the `window.__ModuleLoader__.load({id, factory})` wrapper; DSH-shared modules
  stay `require()`s; any other `@deepseek-ai/*` value import is a build error).
- **Pin:** `devDependencies` and `engines.dsh` carry the exact version.
- **Names to confirm with the maintainer:** the package name `caixa-dsh-plugin` and plugin id `caixa`;
  the route paths `/api/caixa/rpc|events|status`; the plugin settings (`command`, `box`, `readOnly`,
  `roots`, `cwd`); the sidebar panel id `caixa`.

### T01: The host half

- `src/host/worker-client.ts` (JSON-RPC over stdio, restarts, reopens the box), `src/host/routes.ts`
  (rpc, events stream, status), `src/host/index.ts` (the plugin and its config).
- Tests: against a fake worker and the real `caixa worker`: matching, errors by kind, junk lines,
  notifications, death and restart, giving up, close; each route's answers; the config.
- Verify: `pnpm --dir harness test`
- [x] done

### T02: The browser half and the build

- `src/client/` (sidebar icon, Caixa page, API helpers, English and Chinese text), `scripts/`, the
  package manifest (`dsh.bundle`, `dsh.client`, pin, `engines.dsh`), `cordis.patch.yml`.
- Tests: the bundle's contract (wrapper, only shared requires, runs against a fake loader, the
  purity gate rejects an unshared DSH package); the helpers and the page (jsdom); both dictionaries
  match.
- Verify: `pnpm --dir harness test && pnpm --dir harness check-types`
- [x] done

### T03: End to end in the real DeepSeek Harness

- `tests/e2e.test.ts`: a throwaway DSH home, `dsh plugin add`, `dsh web`, sign in; owner-only checks
  (401 without the cookie, 403 for a foreign Host or Origin); worker methods; an import's progress
  stream; the page in a browser. `harness/README.md` and the root README section.
- Verify: `pnpm --dir harness test`
- [x] done

## Completion report

- **Outcome:** `harness/` is a DeepSeek Harness bundle. Its host half starts `caixa worker` through DSH's
  subprocess service, supervises it (answers waiting requests with a plain error if it dies, restarts
  it with a growing pause, reopens the same box) and registers owner-only `POST /api/caixa/rpc`,
  streaming `GET /api/caixa/events` and `GET /api/caixa/status`. Its browser half adds a sidebar icon
  and an empty Caixa page (it shows whether the worker is running). Verified against the real `dsh web`
  0.2.2-alpha.2 under Node 24: 401 without the cookie, 403 for a foreign Origin or Host, an import's
  `job.progress`/`job.finished` events over the stream, and the page opened from the sidebar in a
  browser.
- **Files:** `harness/{package.json,cordis.patch.yml,tsconfig.json,README.md,pnpm-lock.yaml}`,
  `harness/src/host/*`, `harness/src/client/*`, `harness/scripts/*`, `harness/tests/*`, root `README.md`.
- **Errors:** `pkill -f` matched my own shell once (the command was killed, nothing lost); the first
  browser check hit DSH's first-run dialogs ("Preview Notice", "Get started"), which the end-to-end
  test dismisses; an ESM `import('playwright')` ignored NODE_PATH and made the browser test skip
  silently, so it now uses `require` and skips explicitly.
- **Verify:** `pnpm --dir harness test` 46 passed (including the end-to-end run); `check-types` clean;
  Python suite, black and mypy unchanged and clean.

## Review

Reviewed in-session. Accepted: the browser build is a reproduction of DSH's unpublished preset (esbuild
instead of tsdown), checked by the bundle contract tests and the live run, but a future DSH version may
change the loader contract, which is why the version is pinned; the client casts DSH's slot typing with
`as never` in three places (commented; the live run covers what the types would); the page shows
only worker status for now (the wizard, people and browse pages are tickets 24-26); the first-run
dialogs of DSH itself are DSH's, not suppressed here (the launcher in ticket 23 may seed them).
No blockers.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01-T03 done. NEEDS MAINTAINER CONFIRMATION: package/plugin names (`caixa-dsh-plugin`, id `caixa`), route paths, plugin settings, panel id; the exact DSH pin `0.2.2-alpha.2` was chosen because it is the version the Requirements named and the only 0.2.2 release on npm. DSH and Node 24 are available in the build environment (Node via the npm `node` package), so these tickets were verified live, not against stubs.
