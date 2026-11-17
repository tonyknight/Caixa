# Caixa's window

The browser interface `caixa serve` opens. `caixa serve` (Python, see `caixa/web.py`) runs Caixa's
service layer and a small web server in one process; this folder holds the pages it serves, written
in React and built into the Python package (`caixa/data/web/`, committed), so running Caixa needs no
Node.js.

```
browser  ──►  caixa serve (127.0.0.1 only: sign-in link, session cookie, Host/Origin checks)
  Caixa's window (this folder)        /api/caixa/rpc, /api/caixa/events, /api/caixa/status
  the box's pages, in a window        /box/<path>
  of their own
```

## What is here

| Path | What it is |
| --- | --- |
| `src/app/main.tsx` | The entry: mounts the Caixa page, with its translator (English or Chinese, from the browser's language). |
| `src/app/app.css` | The Nord colours, the same the box's pages use; `src/client/caixa.module.css` reads them. |
| `src/client/` | The pages (Box, Import, Jobs, People, Browse, Settings), the store and the calls to `caixa serve` (`api.ts`). All text is in `locales.ts`. |
| `scripts/build-app.mjs` | The build, into `../caixa/data/web/`. It records the digest of the sources in `build.json`; a Python test fails when they change without a rebuild. |
| `tests/` | Unit tests (jsdom) and end-to-end tests that start the real `caixa serve` and drive it in Chromium. |

## Working on it

Node.js 24.9 or newer and pnpm, only to change the window:

```bash
pnpm install          # once
pnpm run build        # after any change under src/ (commit caixa/data/web/ with it)
pnpm run check-types
pnpm test             # unit tests, and the end-to-end tests when `caixa` and Playwright are installed
```

The box's pages themselves (the index page and everyone's page) are made by Chattr
(`tools/chattr/src/chattr/templates/`), not here. Browse opens them in a window of their own,
named `caixa-box`, reused for every page opened from Caixa.
