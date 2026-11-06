# The harness Caixa runs

`caixa serve` installs DeepSeek Harness from these two files with `npm ci`, so every computer gets
exactly the same build: the one Caixa's plugin is tested against.

A plain `npm install @deepseek-ai/dsh@<version>` is not enough. The harness depends on its own
pre-release packages, and npm picks the newest of them. Caixa found that one newer build
(`@deepseek-ai/cordis` 4.0.6-alpha.2) cannot save the harness's settings, which left the first-run
notice impossible to dismiss. `package.json` pins those packages in `overrides`, and
`package-lock.json` records everything else.

To move to a new harness version, change `DSH_VERSION` in `caixa/serve.py`, `harness/package.json`
and `dependencies` here, run `npm install --package-lock-only` in this folder, and run the harness
end-to-end tests (`pnpm --dir harness test`). A test checks that these files and `DSH_VERSION`
agree.
