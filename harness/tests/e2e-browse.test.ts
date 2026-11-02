// The Browse and Settings sections in a real browser, in the real DeepSeek Harness, against the
// real worker: page, photo and links of an imported chat, the policy the pages are served under, and a
// setting that is saved and kept across a reload.
import { join } from 'node:path'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { buildFixtures, canRun, dismissDialogs, openCaixa, playwright, startHarness, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

run('Browse and Settings, in a browser', () => {
  let running: Running
  let box: string

  const imported = async (collector: string, source: string) => {
    const started = await running.rpc('import.start', { collector, source })
    expect(started.ok, JSON.stringify(started)).toBe(true)
    const end = Date.now() + 120_000
    while (Date.now() < end) {
      const job = (await running.rpc('jobs.get', { job: started.result.id })).result
      if (['done', 'failed', 'cancelled'].includes(job.status)) { expect(job.status, job.error).toBe('done'); return }
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    throw new Error('the import did not finish')
  }

  beforeAll(async () => {
    running = await startHarness()
    const fixtures = buildFixtures(mkdtempSync(join(tmpdir(), 'caixa-fixtures-')))
    box = join(running.work, 'Box')
    expect((await running.rpc('box.create', { path: box, name: 'Browse box', owner: 'Maria Costa' })).ok).toBe(true)
    await imported('whatsapp', join(fixtures.whatsapp!, 'WhatsApp Chat - Ana Costa', '_chat.txt'))
    await imported('mail', fixtures.mbox!)
  }, 180_000)
  afterAll(async () => { await running?.stop() })

  it('shows a generated page with its photo and links, safely', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Browse' }).click()

      // From the root to the page.
      await page.getByRole('button', { name: 'Messages/' }).click()
      await page.getByRole('button', { name: 'Ana Costa/' }).click()
      await page.getByRole('button', { name: 'Open (2024) Ana Costa.html' }).click()
      const frame = page.frameLocator('iframe[title^="The page"]')
      await frame.getByText('Que lindo! Buy two.').waitFor({ timeout: 30_000 })

      // Its photo comes through the box route (relative links were rewritten).
      const photo = frame.locator('img').first()
      await photo.waitFor()
      await expect.poll(() => photo.evaluate((image: HTMLImageElement) => image.naturalWidth), { timeout: 30_000 }).toBeGreaterThan(0)
      expect(await photo.getAttribute('src')).toMatch(/^\/api\/caixa\/box\?path=Messages%2FAna%20Costa%2FAttachments/)

      // The box's index page links on to the person's pages, inside the frame.
      await page.getByRole('navigation', { name: 'Where you are' }).getByRole('button', { name: 'Box' }).click()
      await page.getByRole('button', { name: "Open the box's index page" }).click()
      const index = page.frameLocator('iframe[title="The page index.html"]')
      await index.getByRole('link', { name: '2024' }).first().click()
      await index.getByText('Que lindo! Buy two.').waitFor({ timeout: 30_000 })

      // Served under a policy that forbids scripts, and nothing outside the box can be asked for.
      const served = await page.context().request.get(`${running.base}/api/caixa/box?path=${encodeURIComponent('Messages/Ana Costa/(2024) Ana Costa.html')}`)
      expect(served.status()).toBe(200)
      expect(served.headers()['content-security-policy']).toContain("default-src 'none'")
      expect(served.headers()['x-content-type-options']).toBe('nosniff')
      for (const path of ['../outside', '.caixa/caixa.sqlite', '/etc/passwd']) {
        const refused = await page.context().request.get(`${running.base}/api/caixa/box?path=${encodeURIComponent(path)}`)
        expect([403, 404], path).toContain(refused.status())
      }
      const noCookie = await fetch(`${running.base}/api/caixa/box?path=index.html`)
      expect(noCookie.status).toBe(401) // owner-only, like every Caixa route
    } finally {
      await browser.close()
    }
  }, 180_000)

  it('saves a setting and keeps it across a reload', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click()
      await page.getByText(`Location: ${box}`).waitFor()
      expect(await page.getByLabel('Who can see new items').inputValue()).toBe('private')
      await page.getByLabel('Who can see new items').selectOption('family')
      await page.getByRole('button', { name: 'Save settings' }).click()
      await page.getByText('Settings saved.').waitFor()
      expect((await running.rpc('settings.get')).result.values['privacy.default']).toBe('family')

      await page.reload({ waitUntil: 'networkidle' })
      await dismissDialogs(page)
      await page.locator('[aria-label="Caixa"]').first().click()
      await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click()
      await expect.poll(() => page.getByLabel('Who can see new items').inputValue()).toBe('family')
    } finally {
      await browser.close()
    }
  }, 180_000)
})
