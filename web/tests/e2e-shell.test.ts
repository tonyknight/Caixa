// What a person sees the first time `caixa serve` opens: Caixa's own window, with nothing of DeepSeek
// Harness in it, and nothing to see without the link `caixa serve` printed.
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, shot, startCaixa, type Running } from './e2e-support.ts'

const pw = playwright()
const run = canRun && pw ? describe : describe.skip

run('the first run, as `caixa serve` starts it', () => {
  let running: Running
  let browser: any
  let page: any

  beforeAll(async () => {
    running = await startCaixa()
    browser = await pw!.chromium.launch()
    page = await openCaixa(browser, running, { width: 1280, height: 900 })
  }, 120_000)

  afterAll(async () => { await browser?.close(); await running?.stop() })

  it('opens on the Caixa page, with nothing to click first and no dialog in the way', async () => {
    await page.goto(running.base, { waitUntil: 'networkidle' })
    await page.locator('[data-testid="caixa-page"]').waitFor({ timeout: 20_000 })
    expect(await page.locator('[role="dialog"]').count()).toBe(0)
    await shot(page, 'shell-first')
  })

  it('is called Caixa, and carries no DeepSeek name anywhere', async () => {
    expect(await page.title()).toBe('Caixa')
    const text = await page.locator('body').innerText()
    expect(text).not.toMatch(/DeepSeek|DSH|harness/i)
    expect(await page.getByRole('heading', { level: 1 }).textContent()).toBe('Caixa')
  })

  it('uses the Nord colours', async () => {
    const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
    expect(['rgb(236, 239, 244)', 'rgb(46, 52, 64)']).toContain(background)
  })

  it('shows nothing to a browser that did not use the link', async () => {
    const stranger = await browser.newPage()
    const answer = await stranger.goto(running.base)
    expect(answer.status()).toBe(401)
    expect(await stranger.locator('body').innerText()).toContain('caixa serve')
    await stranger.close()
  })
})
