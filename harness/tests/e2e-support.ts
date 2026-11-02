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
export async function startHarness(): Promise<Running> {
  const home = mkdtempSync(join(tmpdir(), 'caixa-dsh-home-'))
  const work = mkdtempSync(join(tmpdir(), 'caixa-dsh-work-'))
  const env = { ...process.env, DSH_HOME: home, DSH_TELEMETRY_DISABLED: '1' }
  // Linking does not rebuild, so build what the browser will load from the current sources.
  execFileSync(process.execPath, [join(harness, 'scripts', 'build.mjs')], { cwd: harness, stdio: 'ignore' })
  execFileSync(dsh, ['plugin', '--profile', 'web', 'add', harness], { env, stdio: 'ignore', timeout: 180_000 })
  const server: ChildProcess = spawn(dsh, ['--profile', 'web', '--no-open', '--port', '0'], { env, cwd: work, stdio: ['ignore', 'pipe', 'inherit'] })
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

/** DSH's own first-run dialogs ("Preview Notice", "Get started") cover the page on every fresh load. */
export async function dismissDialogs(page: any): Promise<void> {
  await page.waitForTimeout(1500)
  for (const name of ['Continue', 'Close']) {
    await page.getByRole('button', { name }).first().click({ timeout: 3000 }).catch(() => undefined)
    await page.waitForTimeout(500)
  }
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
