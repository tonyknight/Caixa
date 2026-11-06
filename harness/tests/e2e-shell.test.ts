// What a person sees the first time `caixa serve` opens: the Caixa page, with none of DeepSeek's own
// first-run messages in the way and none of its name. Runs the real harness with the same patch
// `caixa serve` writes. Skipped when this computer cannot run it (Node older than 24.9, no browser).
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, playwright, startHarness, type Running } from './e2e-support.ts'

const pw = playwright()
const run = canRun && pw ? describe : describe.skip

run('the first run, as `caixa serve` starts it', () => {
  let running: Running
  let browser: any
  let page: any

  beforeAll(async () => {
    running = await startHarness({ caixaPatch: true })
    browser = await pw!.chromium.launch()
    page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
    await page.context().addCookies(running.cookie.split('; ').map(pair => {
      const [name, ...value] = pair.split('=')
      return { name, value: value.join('='), url: running.base }
    }))
    await page.goto(running.base, { waitUntil: 'networkidle' })
    await page.waitForTimeout(4000) // DSH's own dialogs come a moment after the page, when they come
  }, 120_000)

  afterAll(async () => { await browser?.close(); await running?.stop() })

  it('shows no preview notice, sign-in prompt or other dialog', async () => {
    expect(await page.locator('[role="presentation"] [role="dialog"], [role="dialog"]').count()).toBe(0)
    const text = await page.locator('body').innerText()
    expect(text).not.toMatch(/Preview Notice|Get started|Sign in to your DeepSeek/)
  })

  it('leaves Caixa one click away, with nothing covering it', async () => {
    await page.locator('[aria-label="Caixa"]').first().click({ timeout: 10_000 })
    await page.locator('[data-testid="caixa-page"]').waitFor({ timeout: 15_000 })
  })

  it('does not carry the DeepSeek name in the sidebar', async () => {
    const sidebar = await page.locator('body').innerText()
    expect(sidebar).not.toMatch(/deepseek harness/i)
  })
})
