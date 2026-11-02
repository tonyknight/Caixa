// End to end against the real DeepSeek Harness (the pinned version, in a throwaway DSH home) and the
// real `caixa worker`: the owner-only routes, the progress stream, and the page in a browser.
// Skipped when this computer cannot run it (Node older than 24.9, no `caixa`, no browser).
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, startHarness, type Running } from './e2e-support.ts'

const run = canRun ? describe : describe.skip

run('Caixa inside the real DeepSeek Harness', () => {
  let running: Running
  let base = ''
  let cookie = ''
  const work = () => running.work

  const get = (path: string, init: RequestInit = {}) =>
    fetch(`${base}${path}`, { ...init, headers: { cookie, ...(init.headers as Record<string, string>) } })
  const rpc = (method: string, params: Record<string, unknown> = {}) => running.rpc(method, params)

  beforeAll(async () => {
    running = await startHarness()
    base = running.base
    cookie = running.cookie
  }, 120_000)

  afterAll(async () => { await running?.stop() })

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
    const made = await rpc('box.create', { path: join(work(), 'Box'), name: 'Test box', owner: 'Maria Costa' })
    expect(made.result.owner).toBe('Maria Costa')
  })

  it('streams an import\'s progress and its end', async () => {
    const chat = join(work(), 'chat', '_chat.txt')
    mkdirSync(join(work(), 'chat'), { recursive: true })
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
    const library = playwright()
    if (!library) return context.skip()
    const browser = await library.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      const text = await page.locator('[data-testid="caixa-page"]').innerText({ timeout: 15_000 })
      expect(text).toContain('Collect, preserve and pass on a digital life.')
      expect(text).toContain('Test box') // the box the earlier steps made is open
      expect(text).toContain('Messages: 2')
    } finally {
      await browser.close()
    }
  }, 120_000)
})
