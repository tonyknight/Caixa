// Clean mail in a browser, against the real `caixa serve`: from the import wizard's Mail card to a
// Cleaned mbox beside the source, through reading, the groups, keeping a sender and writing.
import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, repository, shot, startCaixa, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

run('cleaning an mbox, in a browser', () => {
  let running: Running
  let gmail: string

  beforeAll(async () => {
    running = await startCaixa()
    expect((await running.rpc('box.create', { path: join(running.work, 'Box'), name: 'Mail box', owner: 'Maria Costa' })).ok).toBe(true)
    const code = [
      'import sys',
      "sys.path.insert(0, 'tools/chattr/tests')",
      'from pathlib import Path',
      'from fixtures.builders.noisy_mbox import build_noisy_mbox',
      'print(build_noisy_mbox(Path(sys.argv[1])).gmail)',
    ].join('\n')
    const folder = mkdtempSync(join(tmpdir(), 'caixa-mail-'))
    gmail = execFileSync('python', ['-c', code, folder], { cwd: repository, encoding: 'utf8' }).trim().split('\n').pop()!
  }, 120_000)
  afterAll(async () => { await running?.stop() })

  it('reads the mbox, shows the junk by group, keeps a sender and writes the cleaned mbox', async () => {
    const browser = await playwright()!.chromium.launch()
    const problems: string[] = []
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Import' }).click()
      const [mail] = await Promise.all([
        page.waitForEvent('popup'),
        page.getByRole('button', { name: /Mail \(Gmail and other mbox\)/ }).click(),
      ])
      mail.on('console', (message: any) => { if (message.type() === 'error') problems.push(message.text()) })
      await mail.setViewportSize({ width: 1280, height: 900 })
      expect(new URL(mail.url()).pathname).toBe('/mail/clean')
      await mail.getByRole('heading', { name: 'Clean mail' }).waitFor({ timeout: 15_000 })
      await mail.getByLabel('The mbox').fill(gmail)
      await mail.getByLabel('Account').fill('Gmail')
      await mail.getByRole('button', { name: 'Read it' }).click()
      await mail.getByRole('heading', { level: 1, name: 'Lists and newsletters' }).waitFor({ timeout: 60_000 })
      const groups = mail.getByRole('navigation', { name: 'Groups' })
      expect(await groups.getByRole('link', { name: /Lists and newsletters/ }).textContent()).toContain('5 senders · 11 mails')
      await shot(mail, 'clean-mail-groups')

      const fold = mail.getByRole('row', { name: /The Daily Fold/ })
      await fold.hover()
      await mail.getByRole('button', { name: 'Keep The Daily Fold' }).click()
      await fold.waitFor({ state: 'detached', timeout: 15_000 })
      expect(await groups.getByRole('link', { name: /Kept/ }).textContent()).toContain('1 sender · 6 mails')

      await mail.getByRole('button', { name: 'Write the cleaned mbox' }).click()
      const ask = mail.getByRole('dialog', { name: /Leave out \d+ mails/ })
      await ask.getByRole('button', { name: 'Write it' }).click()
      const written = mail.getByRole('status', { name: 'Written' })
      await written.waitFor({ timeout: 60_000 })
      const path = (await written.locator('code').textContent())!
      expect(path).toMatch(/\[Cleaned\]\.mbox$/)
      expect(existsSync(path)).toBe(true)
      await shot(mail, 'clean-mail-written')
      expect(problems).toEqual([])
    } finally {
      await browser.close()
    }
  }, 180_000)
})
