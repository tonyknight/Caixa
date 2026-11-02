# Caixa's plugin for DeepSeek Harness

The browser interface for Caixa is a plugin for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
(`dsh web`, MIT). All the work on your archive happens in Python (`caixa worker`); this plugin
runs it, opens it to the browser, and adds the Caixa pages.

```
browser  ──►  DSH (sign-in, Host and Origin checks)  ──►  /api/caixa/*  ──►  caixa worker  (stdio JSON-RPC)
  Caixa pages (React)                  host half of this plugin               Python; no network listener
```

## What is here

| Path | What it is |
| --- | --- |
| `src/host/worker-client.ts` | Talks to `caixa worker` (JSON-RPC, one JSON object per line); matches answers to requests, passes notifications on, restarts the worker with a growing pause and reopens the same box. |
| `src/host/routes.ts` | The owner-only routes: `POST /api/caixa/rpc`, `GET /api/caixa/events` (a stream of the worker's notifications), `GET /api/caixa/status`. |
| `src/host/index.ts` | The plugin DSH loads: starts the worker through DSH's subprocess service and registers the routes. Settings: `command`, `box`, `readOnly`, `roots`, `cwd`. |
| `src/client/` | The browser half: a sidebar icon and the Caixa page. All text is in `locales.ts` (English and Chinese). |
| `scripts/preset.mjs`, `scripts/build.mjs` | The build. DSH builds its own plugins with a preset that is not published, so this reproduces its contract (see the comments in `preset.mjs`). |
| `cordis.patch.yml` | The layer that adds the plugin to a DSH profile. |

## Versions

DSH is a developer preview and its plugin interfaces change. This plugin is pinned to one exact
version: `@deepseek-ai/dsh` **0.2.2-alpha.2** (in `devDependencies`) and `engines.dsh` in
`package.json`. DSH refuses to install it on another version. Upgrade deliberately, following DSH's
`docs/upgrade-guide/`, and run the end-to-end test before changing the pin. DSH needs
**Node 24.9 or newer**.

## Develop

```bash
pnpm --dir harness install
pnpm --dir harness build         # lib/index.js (host) and lib/client.js (browser)
pnpm --dir harness check-types
pnpm --dir harness test          # unit tests, and an end-to-end run against the real dsh
```

The end-to-end test (`tests/e2e.test.ts`) installs this plugin into a throwaway DSH home, starts
`dsh web`, signs in, and checks the routes, an import's progress stream and the page in a browser.
It skips itself when Node is older than 24.9, `caixa` is not on the path, or no browser is
installed. It never touches your own `~/.dsh`.

Tests use only the synthetic fixtures; nothing here sends anything off your computer.
