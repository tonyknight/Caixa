// Builds Caixa's own browser interface (src/app) into the Python package, `caixa/data/web/`, where
// `caixa serve` serves it. The result is committed, so running Caixa needs no Node.js: only someone
// changing the interface runs this (`pnpm run build:app`). React is bundled in; the styles go to
// one stylesheet (the CSS modules included), so the page needs no inline styles or scripts.
//
// The output depends only on the sources: `build.json` records their digest, and a Python test
// fails when the sources change without a rebuild.
import { build } from 'esbuild'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, statSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const out = join(root, '..', 'caixa', 'data', 'web')

/** The digest of every source the bundle is made from (src/app and src/client), path and text. */
export function sourceDigest() {
  const hash = createHash('sha256')
  const walk = (folder) => readdirSync(folder).sort().forEach((name) => {
    const path = join(folder, name)
    if (statSync(path).isDirectory()) return walk(path)
    hash.update(relative(root, path).split('\\').join('/')).update('\0').update(readFileSync(path)).update('\0')
  })
  walk(join(root, 'src', 'app'))
  walk(join(root, 'src', 'client'))
  return hash.digest('hex')
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  mkdirSync(out, { recursive: true })
  await build({
    bundle: true,
    minify: true,
    legalComments: 'none',
    logLevel: 'warning',
    absWorkingDir: root,
    entryPoints: { app: 'src/app/main.tsx' },
    outdir: out,
    format: 'iife',
    platform: 'browser',
    target: 'es2022',
    jsx: 'automatic',
    loader: { '.module.css': 'local-css' },
    define: { 'process.env.NODE_ENV': '"production"' },
  })
  writeFileSync(join(out, 'build.json'), JSON.stringify({ sources: sourceDigest() }, null, 2) + '\n')
}
