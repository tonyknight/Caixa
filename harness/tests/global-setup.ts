// Build before any test file runs: Caixa's own window (into caixa/data/web, which `caixa serve`
// serves to the end-to-end tests) and the DeepSeek Harness plugin (whose host tests read lib/).
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export default function setup(): void {
  const root = fileURLToPath(new URL('..', import.meta.url))
  execFileSync(process.execPath, [join(root, 'scripts', 'build-app.mjs')], { cwd: root, stdio: 'inherit' })
  execFileSync(process.execPath, [join(root, 'scripts', 'build.mjs')], { cwd: root, stdio: 'ignore' })
}
