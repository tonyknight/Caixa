// Sort mail in a browser, against the real `caixa serve`: clean the noisy mbox, go on to sort the
// cleaned one, and choose and ignore senders the way the index page sorts people.
import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, repository, shot, startCaixa, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

run('sorting an mbox, in a browser', () => {
  let running: Running
  let gmail: string

  beforeAll(async () => {
    running = await startCaixa()
    expect((await running.rpc('box.create', { path: join(running.work, 'Box'), name: 'Mail box', owner: 'Maria Costa' })).ok).toBe(true)
    expect((await running.rpc('people.link', { service: 'Mail', identifier: 'ana.costa@example.com', person: 'Ana Costa' })).ok).toBe(true)
    const code = [
      'import sys',
      "sys.path.insert(0, 'tools/chattr/tests')",
      'from pathlib import Path',
      'from fixtures.builders.noisy_mbox import build_noisy_mbox',
      'print(build_noisy_mbox(Path(sys.argv[1])).gmail)',
    ].join('\n')
    gmail = execFileSync('python', ['-c', code, mkdtempSync(join(tmpdir(), 'caixa-mail-'))], { cwd: repository, encoding: 'utf8' }).trim().split('\n').pop()!
  }, 120_000)
  afterAll(async () => { await running?.stop() })

  it('cleans, then sorts the cleaned mbox: known people chosen, a stranger chosen, one ignored', async () => {
    const browser = await playwright()!.chromium.launch()
    const problems: string[] = []
    try {
      const page = await openCaixa(browser, running)
      page.on('console', (message: any) => { if (message.type() === 'error') problems.push(message.text()) })
      await page.goto(`${running.base}/mail/clean`)
      await page.getByLabel('The mbox').fill(gmail)
      await page.getByLabel('Account').fill('Gmail')
      await page.getByRole('button', { name: 'Read it' }).click()
      await page.getByRole('button', { name: 'Write the cleaned mbox' }).click({ timeout: 60_000 })
      await page.getByRole('dialog').getByRole('button', { name: 'Write it' }).click()
      await page.getByRole('link', { name: 'Sort the cleaned mbox' }).click({ timeout: 60_000 })

      await page.getByRole('heading', { level: 1, name: 'Known' }).waitFor({ timeout: 30_000 })
      expect(new URL(page.url()).pathname).toBe('/mail/sort')
      expect(await page.getByRole('row', { name: /Ana Costa/ }).textContent()).toContain('known · you wrote 1')
      const groups = page.getByRole('navigation', { name: 'Groups' })
      const footer = page.getByRole('contentinfo')
      expect(await footer.textContent()).toContain('Importing would bring 4 mails in 3 conversations')

      await groups.getByRole('link', { name: /To sort/ }).click()
      const beatriz = page.getByRole('row', { name: /Beatriz Lima/ })
      await beatriz.hover()
      await page.getByRole('button', { name: 'Choose Beatriz Lima' }).click()
      await beatriz.waitFor({ state: 'detached', timeout: 15_000 })
      await page.getByRole('row', { name: /Carlos Mendes/ }).click()
      await page.keyboard.press('Delete')
      await page.getByRole('row', { name: /Carlos Mendes/ }).waitFor({ state: 'detached', timeout: 15_000 })
      await page.waitForFunction(() => document.querySelector('footer')?.textContent?.includes('8 mails in 5 conversations'), null, { timeout: 15_000 })
      await groups.getByRole('link', { name: /Ignored/ }).click()
      expect(await page.getByRole('row', { name: /Carlos Mendes/ }).count()).toBe(1)
      await shot(page, 'sort-mail-ignored')

      await footer.getByRole('button', { name: 'Import' }).click()
      await page.getByRole('dialog', { name: /Import 8 mails in 5 conversations/ }).getByRole('button', { name: 'Import them' }).click()
      const imported = page.getByRole('status', { name: 'Imported' })
      await imported.waitFor({ timeout: 120_000 })
      expect(await imported.textContent()).toContain('8 mails in 5 conversations')
      // a report says what came in, with ways back to the box; closing it leaves the window as it was
      const report = page.getByRole('dialog', { name: 'The import is done' })
      expect(await report.textContent()).toContain('8 mails in 5 conversations came into the box.')
      expect(await report.getByRole('button', { name: "Open the box's people page" }).isVisible()).toBe(true)
      await shot(page, 'sort-mail-report')
      await report.getByRole('button', { name: 'Close' }).click()
      await groups.getByRole('link', { name: /Imported/ }).click()
      await page.getByRole('row', { name: /Beatriz Lima/ }).waitFor({ timeout: 15_000 })

      await imported.getByRole('button', { name: 'Write the reduced mbox' }).click()
      await page.getByRole('dialog', { name: 'Write the reduced mbox?' }).getByRole('button', { name: 'Write it' }).click()
      const written = page.getByRole('status', { name: 'Written' })
      await written.waitFor({ timeout: 60_000 })
      const reduced = (await written.locator('code').textContent())!
      expect(reduced).toMatch(/\[Reduced\]\.mbox$/)
      expect(existsSync(reduced)).toBe(true)
      await shot(page, 'sort-mail-reduced')
      expect(problems).toEqual([])
    } finally {
      await browser.close()
    }
  }, 300_000)
})
