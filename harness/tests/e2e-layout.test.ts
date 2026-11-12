// The Caixa page in a short window, in the real harness: everything on a page must be reachable by
// scrolling, and the buttons that move an import forward must stay in view. (The other browser tests
// use a tall window, which is how a page that could not scroll went unnoticed.)
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, playwright, shot, startHarness, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

/** True when the element is inside the window (not merely in the document). */
const inView = (locator: any) => locator.evaluate((element: Element) => {
  const box = element.getBoundingClientRect()
  return box.top >= 0 && box.bottom <= window.innerHeight && box.height > 0
})

run('the Caixa page in a short window', () => {
  let running: Running
  let browser: any
  let page: any

  beforeAll(async () => {
    running = await startHarness({ caixaPatch: true })
    const box = join(running.work, 'Box')
    expect((await running.rpc('box.create', { path: box, name: 'Our box', owner: 'Maria Costa' })).ok).toBe(true)
    // an export with many people in it, so the preview is long
    const archive = join(running.work, 'Many Voicemails.zip')
    const code = [
      'import sys, zipfile',
      'z = zipfile.ZipFile(sys.argv[1], "w")',
      'for n in range(120): z.writestr(f"vm/(2019-01-{1 + n % 28:02d}) 10 {n % 60:02d} 00 - Caller Number {n}.amr", "a")',
      'z.close()',
    ].join('\n')
    execFileSync('python', ['-c', code, archive])
    browser = await playwright()!.chromium.launch()
    page = await browser.newPage({ viewport: { width: 1100, height: 560 } })
    await page.context().addCookies(running.cookie.split('; ').map(pair => {
      const [name, ...value] = pair.split('=')
      return { name, value: value.join('='), url: running.base }
    }))
    await page.goto(running.base, { waitUntil: 'networkidle' })
    await page.locator('[aria-label="Caixa"]').first().click({ timeout: 15_000 })
    await page.locator('[data-testid="caixa-page"]').waitFor({ timeout: 15_000 })
  }, 180_000)

  afterAll(async () => { await browser?.close(); await running?.stop() })

  it('scrolls to the bottom of a long page', async () => {
    await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click()
    const last = page.getByRole('button', { name: 'Create a report' })
    await last.waitFor()
    expect(await inView(last)).toBe(false) // it starts below the fold
    // Scroll as a person does, with the wheel. (scrollIntoView would also move a page that hides its
    // overflow, which no person can scroll.)
    await page.mouse.move(600, 300)
    for (let turn = 0; turn < 12 && !(await inView(last)); turn++) { await page.mouse.wheel(0, 400); await page.waitForTimeout(80) }
    expect(await inView(last), await page.evaluate(() => {
      const chain: string[] = []
      for (let node: Element | null = document.querySelector('[data-testid="caixa-page"]'); node; node = node.parentElement) {
        const style = getComputedStyle(node)
        chain.push(`${node.tagName}.${String(node.className).slice(0, 30)} overflow-y=${style.overflowY} h=${Math.round(node.getBoundingClientRect().height)} scroll=${node.scrollHeight}`)
      }
      return chain.join('\n')
    })).toBe(true)
  })

  it('keeps the wizard\'s buttons in view on a long preview, and the list of people short', async () => {
    await page.getByRole('navigation').getByRole('button', { name: 'Import', exact: true }).click()
    await page.getByRole('button', { name: /^iPhone voicemail/ }).click()
    await page.getByRole('button', { name: 'I have the export' }).click()
    await page.getByLabel('Path to the export').fill(join(running.work, 'Many Voicemails.zip'))
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.getByRole('button', { name: 'Preview' }).click()
    await page.getByText('120 items in', { exact: false }).waitFor({ timeout: 60_000 })
    const start = page.getByRole('button', { name: 'Import', exact: true }).last()
    expect(await inView(start)).toBe(true) // no scrolling needed to go on
    await shot(page, 'layout-preview')
    // 120 callers are not all listed at once
    expect(await page.getByText('Caller Number 119').count()).toBe(0)
    await page.getByRole('button', { name: /Show all 120/ }).first().click()
    expect(await page.getByText(/Caller Number 119/).count()).toBeGreaterThan(0)
    expect(await inView(start)).toBe(true)
  }, 120_000)

  it('scrolls the People section to its last row', async () => {
    await page.getByRole('navigation').getByRole('button', { name: 'Import', exact: true }).click()
    await page.getByRole('button', { name: 'Import', exact: true }).last().click()
    await page.getByRole('heading', { name: 'Import finished' }).waitFor({ timeout: 120_000 })
    await page.getByRole('navigation').getByRole('button', { name: 'People' }).click()
    const rows = page.getByRole('row')
    await rows.first().waitFor()
    const last = rows.last()
    await page.mouse.move(600, 300)
    for (let turn = 0; turn < 40 && !(await inView(last)); turn++) { await page.mouse.wheel(0, 400); await page.waitForTimeout(60) }
    expect(await inView(last)).toBe(true)
  }, 180_000)
})
