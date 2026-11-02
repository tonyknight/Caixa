// End to end against the real DeepSeek Harness (the pinned version, in a throwaway DSH home) and the
// real `caixa worker`: the owner-only routes, the progress stream, and the page in a browser.
// Skipped when this computer cannot run it (Node older than 24.9, no `caixa`, no browser).
import { execFileSync, spawn, type ChildProcess } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

const harness = fileURLToPath(new URL('..', import.meta.url))
const [major = 0, minor = 0] = process.versions.node.split('.').map(Number)
const nodeOk = major > 24 || (major === 24 && minor >= 9)
const caixaOk = (() => { try { execFileSync('caixa', ['--version'], { stdio: 'ignore' }); return true } catch { return false } })()
const dsh = join(harness, 'node_modules/.bin/dsh')

const run = nodeOk && caixaOk ? describe : describe.skip

run('Caixa inside the real DeepSeek Harness', () => {
  let home: string
  let work: string
  let server: ChildProcess
  let base = ''
  let cookie = ''
  const environment = () => ({ ...process.env, DSH_HOME: home, DSH_TELEMETRY_DISABLED: '1' })

  const get = (path: string, init: RequestInit = {}) =>
    fetch(`${base}${path}`, { ...init, headers: { cookie, ...(init.headers as Record<string, string>) } })
  const rpc = async (method: string, params: Record<string, unknown> = {}) =>
    await (await get('/api/caixa/rpc', { method: 'POST', body: JSON.stringify({ method, params }) })).json() as
      { ok: boolean; result?: any; error?: any }

  beforeAll(async () => {
    home = mkdtempSync(join(tmpdir(), 'caixa-dsh-home-'))
    work = mkdtempSync(join(tmpdir(), 'caixa-dsh-work-'))
    execFileSync(dsh, ['plugin', '--profile', 'web', 'add', harness], { env: environment(), stdio: 'ignore', timeout: 180_000 })
    server = spawn(dsh, ['--profile', 'web', '--no-open', '--port', '0'], { env: environment(), cwd: work, stdio: ['ignore', 'pipe', 'inherit'] })
    const link = await new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('dsh web did not print its link')), 60_000)
      server.stdout!.on('data', (chunk: Buffer) => {
        const found = /http:\/\/127\.0\.0\.1:\d+\/\?token=[\w-]+/.exec(chunk.toString())
        if (found) { clearTimeout(timer); resolve(found[0]) }
      })
    })
    base = new URL(link).origin
    const entry = await fetch(link, { redirect: 'manual' })
    cookie = entry.headers.getSetCookie().map(c => c.split(';')[0]).join('; ')
    expect(cookie).not.toBe('')
  }, 120_000)

  afterAll(async () => {
    server?.kill('SIGTERM')
    await new Promise(resolve => setTimeout(resolve, 500))
    rmSync(home, { recursive: true, force: true })
    rmSync(work, { recursive: true, force: true })
  })

  it('serves the routes only to the signed-in owner on this computer', async () => {
    expect((await fetch(`${base}/api/caixa/status`)).status).toBe(401)
    expect((await get('/api/caixa/status', { headers: { origin: 'http://evil.example' } })).status).toBe(403)
    const status = await get('/api/caixa/status')
    expect(status.status).toBe(200)
    expect(await status.json()).toEqual({ worker: 'running' })
  })

  it('refuses a foreign Origin on the call route too', async () => {
    const response = await get('/api/caixa/rpc', {
      method: 'POST',
      body: JSON.stringify({ method: 'worker.info' }),
      headers: { origin: 'http://evil.example' },
    })
    expect(response.status).toBe(403)
  })

  it('runs worker methods and reports its errors by kind', async () => {
    expect((await rpc('worker.info')).result.protocol).toBe(1)
    expect((await rpc('box.status')).error.kind).toBe('no_box')
    const made = await rpc('box.create', { path: join(work, 'Box'), name: 'Test box', owner: 'Maria Costa' })
    expect(made.result.owner).toBe('Maria Costa')
  })

  it('streams an import\'s progress and its end', async () => {
    const chat = join(work, 'chat', '_chat.txt')
    mkdirSync(join(work, 'chat'), { recursive: true })
    writeFileSync(chat, '01/03/2024, 10:00 - Ana Costa: Olá!\n01/03/2024, 10:01 - Maria Costa: Olá, Ana.\n')
    const events = await get('/api/caixa/events')
    expect(events.headers.get('content-type')).toContain('text/event-stream')
    const reader = events.body!.getReader()
    const started = await rpc('import.start', { collector: 'whatsapp', source: chat })
    expect(started.ok).toBe(true)
    const decoder = new TextDecoder()
    let text = ''
    const end = Date.now() + 60_000
    while (!text.includes('event: job.finished') && Date.now() < end) {
      const { value, done } = await reader.read()
      if (done) break
      text += decoder.decode(value)
    }
    await reader.cancel()
    expect(text).toContain('event: job.progress')
    expect(text).toContain('event: job.finished')
    expect(text).toMatch(/"status":"done"/)
    expect((await rpc('box.status')).result.items).toBe(2)
  }, 90_000)

  it('shows the Caixa page from the sidebar in a browser', async (context) => {
    let chromium: { launch: () => Promise<any> }
    try { ({ chromium } = createRequire(import.meta.url)('playwright')) } catch { return context.skip() }
    const browser = await chromium.launch()
    try {
      const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
      await page.context().addCookies(cookie.split('; ').map(pair => {
        const [name, ...value] = pair.split('=')
        return { name, value: value.join('='), url: base }
      }))
      await page.goto(base, { waitUntil: 'networkidle' })
      await page.waitForTimeout(1500)
      for (const name of ['Continue', 'Close']) {
        await page.getByRole('button', { name }).first().click({ timeout: 3000 }).catch(() => undefined)
        await page.waitForTimeout(500)
      }
      await page.locator('[aria-label="Caixa"]').first().click({ timeout: 15_000 })
      const text = await page.locator('[data-testid="caixa-page"]').innerText({ timeout: 15_000 })
      expect(text).toContain('Collect, preserve and pass on a digital life.')
      expect(text).toContain('The Caixa worker is running')
    } finally {
      await browser.close()
    }
  }, 120_000)
})
