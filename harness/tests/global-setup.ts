// Build the plugin once, before any test file runs. The end-to-end tests link `harness/` into DSH
// homes of their own and DSH hot-reloads a linked plugin when its files change, so a test file that
// rebuilt `lib/` while another file's DSH was running would remount that file's page mid-test.
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export default function setup(): void {
  const root = fileURLToPath(new URL('..', import.meta.url))
  execFileSync(process.execPath, [join(root, 'scripts', 'build.mjs')], { cwd: root, stdio: 'ignore' })
}
