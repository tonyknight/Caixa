// Shared by the end-to-end tests: the real `caixa serve` (Caixa's own window, served by Python, in a
// throwaway Caixa home) and a browser when one is installed.
import { execFileSync, spawn, type ChildProcess } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const harness = fileURLToPath(new URL('..', import.meta.url))
export const repository = join(harness, '..')
export const caixaOk = (() => { try { execFileSync('caixa', ['--version'], { stdio: 'ignore' }); return true } catch { return false } })()
export const canRun = caixaOk

/** The Playwright browser library, or undefined when none is installed. */
export function playwright(): { chromium: { launch: () => Promise<any> } } | undefined {
  try { return createRequire(import.meta.url)('playwright') } catch { return undefined }
}

export interface Running {
  readonly base: string
  readonly link: string
  readonly cookie: string
  readonly work: string
  readonly stop: () => Promise<void>
  readonly rpc: (method: string, params?: Record<string, unknown>) => Promise<{ ok: boolean; result?: any; error?: any }>
}

/** Start `caixa serve` (no browser of its own) in a fresh Caixa home, and sign in. */
export async function startCaixa(options: { caixaHome?: string } = {}): Promise<Running> {
  const home = mkdtempSync(join(tmpdir(), 'caixa-home-'))
  const work = mkdtempSync(join(tmpdir(), 'caixa-work-'))
  // CAIXA_HOME: what Caixa remembers between runs (the last box) must not leak between tests, or into a real home
  const env = { ...process.env, CAIXA_HOME: options.caixaHome ?? join(home, 'caixa-home'), PYTHONUNBUFFERED: '1' }
  const server: ChildProcess = spawn('caixa', ['serve', '--no-browser', '--port', '0'], { env, cwd: work, stdio: ['ignore', 'pipe', 'inherit'] })
  const link = await new Promise<string>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('caixa serve did not print its link')), 60_000)
    let seen = ''
    server.stdout!.on('data', (chunk: Buffer) => {
      seen += chunk.toString()
      const found = /http:\/\/127\.0\.0\.1:\d+\/sign-in\?ticket=[\w-]+/.exec(seen)
      if (found) { clearTimeout(timer); resolve(found[0]) }
    })
    server.on('exit', code => { clearTimeout(timer); reject(new Error(`caixa serve stopped (exit ${code})`)) })
  })
  const base = new URL(link).origin
  const entry = await fetch(link, { redirect: 'manual' })
  const cookie = entry.headers.getSetCookie().map(c => c.split(';')[0]).join('; ')
  if (!cookie) throw new Error('no sign-in cookie')
  return {
    base, link, cookie, work,
    rpc: async (method, params = {}) => await (await fetch(`${base}/api/caixa/rpc`, {
      method: 'POST', headers: { cookie, 'content-type': 'application/json' }, body: JSON.stringify({ method, params }),
    })).json() as { ok: boolean; result?: any; error?: any },
    stop: async () => {
      const ended = new Promise(resolve => server.once('exit', resolve))
      server.kill('SIGTERM')
      await Promise.race([ended, new Promise(resolve => setTimeout(resolve, 10_000))])
      rmSync(home, { recursive: true, force: true })
      rmSync(work, { recursive: true, force: true })
    },
  }
}

/** Open Caixa's window in a browser, signed in. */
export async function openCaixa(browser: any, running: Running, viewport = { width: 1280, height: 1000 }): Promise<any> {
  const page = await browser.newPage({ viewport })
  await page.goto(running.link, { waitUntil: 'networkidle' })
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
