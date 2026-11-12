// Shared by the end-to-end tests: the real DeepSeek Harness (the pinned version, in a throwaway DSH
// home) with Caixa's plugin and the real `caixa worker`, and a browser when one is installed.
import { execFileSync, spawn, type ChildProcess } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const harness = fileURLToPath(new URL('..', import.meta.url))
export const repository = join(harness, '..')
const [major = 0, minor = 0] = process.versions.node.split('.').map(Number)
export const nodeOk = major > 24 || (major === 24 && minor >= 9)
export const caixaOk = (() => { try { execFileSync('caixa', ['--version'], { stdio: 'ignore' }); return true } catch { return false } })()
export const canRun = nodeOk && caixaOk
const dsh = join(harness, 'node_modules/.bin/dsh')

/** The Playwright browser library, or undefined when none is installed. */
export function playwright(): { chromium: { launch: () => Promise<any> } } | undefined {
  try { return createRequire(import.meta.url)('playwright') } catch { return undefined }
}

export interface Running {
  readonly base: string
  readonly cookie: string
  readonly work: string
  readonly stop: () => Promise<void>
  readonly rpc: (method: string, params?: Record<string, unknown>) => Promise<{ ok: boolean; result?: any; error?: any }>
}

/** Install the plugin into a fresh DSH home, start `dsh web`, sign in. */
export async function startHarness(options: { caixaPatch?: boolean; caixaHome?: string } = {}): Promise<Running> {
  const home = mkdtempSync(join(tmpdir(), 'caixa-dsh-home-'))
  const work = mkdtempSync(join(tmpdir(), 'caixa-dsh-work-'))
  // CAIXA_HOME: what Caixa remembers between runs (the last box) must not leak between tests, or into a real home
  const env = { ...process.env, DSH_HOME: home, CAIXA_HOME: options.caixaHome ?? join(home, 'caixa-home'), DSH_TELEMETRY_DISABLED: '1' }
  // (lib/ is built once by tests/global-setup.ts: rebuilding here would hot-reload other files' DSH)
  execFileSync(dsh, ['plugin', '--profile', 'web', 'add', harness], { env, stdio: 'ignore', timeout: 180_000 })
  // `caixaPatch`: the configuration layer `caixa serve` really writes, so a test sees what a user sees.
  const patch = options.caixaPatch ? join(work, 'caixa.patch.yml') : undefined
  if (patch) {
    const code = 'import sys; from caixa.serve import write_patch; from pathlib import Path; write_patch(Path(sys.argv[1]), None, False, sys.executable)'
    execFileSync('python', ['-c', code, work], { cwd: repository })
  }
  const server: ChildProcess = spawn(dsh, [...(patch ? ['--patch', patch] : []), '--profile', 'web', '--no-open', '--port', '0'], { env, cwd: work, stdio: ['ignore', 'pipe', 'inherit'] })
  const link = await new Promise<string>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('dsh web did not print its link')), 60_000)
    server.stdout!.on('data', (chunk: Buffer) => {
      const found = /http:\/\/127\.0\.0\.1:\d+\/\?token=[\w-]+/.exec(chunk.toString())
      if (found) { clearTimeout(timer); resolve(found[0]) }
    })
  })
  const base = new URL(link).origin
  const entry = await fetch(link, { redirect: 'manual' })
  const cookie = entry.headers.getSetCookie().map(c => c.split(';')[0]).join('; ')
  if (!cookie) throw new Error('no sign-in cookie')
  // The harness answers before every plugin's routes are mounted: wait for Caixa's own, so a test's
  // first call is never answered "not found".
  for (let attempt = 0; ; attempt++) {
    const ready = await fetch(`${base}/api/caixa/status`, { headers: { cookie } }).then(r => r.status === 200, () => false)
    if (ready) break
    if (attempt > 150) throw new Error('the Caixa routes never came up')
    await new Promise(resolve => setTimeout(resolve, 200))
  }
  return {
    base, cookie, work,
    rpc: async (method, params = {}) => await (await fetch(`${base}/api/caixa/rpc`, {
      method: 'POST', headers: { cookie }, body: JSON.stringify({ method, params }),
    })).json() as { ok: boolean; result?: any; error?: any },
    stop: async () => {
      server.kill('SIGTERM')
      await new Promise(resolve => setTimeout(resolve, 500))
      rmSync(home, { recursive: true, force: true })
      rmSync(work, { recursive: true, force: true })
    },
  }
}

/**
 * DSH's own first-run dialogs ("Preview Notice", "Get started") cover the page on every fresh load, and
 * on a busy machine they can appear well after the page does. So instead of dismissing them once, a
 * handler dismisses them whenever one shows up, for the life of the page, and the first sweep waits
 * until none is left.
 */
export async function dismissDialogs(page: any): Promise<void> {
  if (!page.__caixaHandlers) {
    page.__caixaHandlers = true
    for (const name of ['Continue', 'Close']) {
      // only inside DSH's modal root: the Caixa wizard has a "Continue" button of its own
      const button = page.locator('[role="presentation"]').getByRole('button', { name, exact: true })
      await page.addLocatorHandler(button, async (found: any) => { await found.first().click({ timeout: 5000 }).catch(() => undefined) })
    }
  }
  // Give them time to come, then make sure none is still covering the page.
  const quiet = Date.now() + 4000
  while (Date.now() < quiet) {
    if (await page.locator('[class*="_mask_"]').count() > 0) { await page.waitForTimeout(300); continue }
    await page.waitForTimeout(300)
  }
  await page.waitForFunction(() => document.querySelectorAll('[class*="_mask_"]').length === 0, undefined, { timeout: 20_000 }).catch(() => undefined)
}

/** Open DSH in a browser, signed in, past its first-run dialogs, on the Caixa page. */
export async function openCaixa(browser: any, running: Running): Promise<any> {
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } })
  await page.context().addCookies(running.cookie.split('; ').map(pair => {
    const [name, ...value] = pair.split('=')
    return { name, value: value.join('='), url: running.base }
  }))
  await page.goto(running.base, { waitUntil: 'networkidle' })
  await dismissDialogs(page)
  await page.locator('[aria-label="Caixa"]').first().click({ timeout: 15_000 })
  await page.locator('[data-testid="caixa-page"]').waitFor({ timeout: 15_000 })
  return page
}

/** The synthetic fixture family (the same one the Python tests use), built into a new folder. */
export function buildFixtures(into: string): Record<string, string> {
  const code = [
    'import json, sys',
    "sys.path.insert(0, 'tools/chattr/tests')",
    'from pathlib import Path',
    'from fixtures import build_all, family',
    'paths = {k: str(v) for k, v in build_all(Path(sys.argv[1])).paths.items()}',
    "paths['ana_phone'] = family.ANA.phones[0]  # a number the family's daughter texts from",
    'print(json.dumps(paths))',
  ].join('\n')
  return JSON.parse(execFileSync('python', ['-c', code, into], { cwd: repository, encoding: 'utf8' }).trim().split('\n').pop()!)
}

/** Save a picture of the page when `CAIXA_SHOTS` names a folder (for looking at a change by eye). */
export async function shot(page: any, name: string): Promise<void> {
  const folder = process.env.CAIXA_SHOTS
  if (folder) await page.screenshot({ path: join(folder, `${name}.png`) })
}
