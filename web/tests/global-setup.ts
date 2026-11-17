// Build Caixa's window before any test file runs (into caixa/data/web, which `caixa serve` serves to
// the end-to-end tests), so they always see the sources as they are.
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export default function setup(): void {
  const root = fileURLToPath(new URL('..', import.meta.url))
  execFileSync(process.execPath, [join(root, 'scripts', 'build-app.mjs')], { cwd: root, stdio: 'inherit' })
}
