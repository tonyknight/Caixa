// Builds the plugin: the host half (`lib/index.js`, an ES module run by DSH under Node) and the
// browser half (`lib/client.js`, in the form DSH's module system loads; see preset.mjs).
import { build } from 'esbuild'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { clientOptions } from './preset.mjs'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const manifest = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))

await build({
  bundle: true,
  sourcemap: true,
  logLevel: 'warning',
  absWorkingDir: root,
  entryPoints: ['src/host/index.ts'],
  outfile: 'lib/index.js',
  format: 'esm',
  platform: 'node',
  target: 'node24',
  packages: 'external',
})

await build(clientOptions(manifest, root))
