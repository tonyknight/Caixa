// Voicemail exported as a zip of audio files named for when they came in and who from, imported through
// the wizard in a real browser, against the real worker. The speech model field starts from Settings
// and offers to browse for the file.
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, startHarness, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

run('voicemail as named audio files, in a browser', () => {
  let running: Running
  let archive: string
  let box: string

  beforeAll(async () => {
    running = await startHarness()
    archive = join(running.work, 'iPhone Voicemail.zip')
    box = join(running.work, 'Voicemail box')
    const code = [
      'import sys, zipfile',
      'names = ["(2018-12-21) 15 02 31 - Ana Costa.amr", "(2019-01-03) 09 05 00 - João Costa.amr", "(2019-02-10) 18 30 12 - Ana Costa.amr"]',
      'z = zipfile.ZipFile(sys.argv[1], "w")',
      'for n in names: z.writestr("iPhone Voicemail/" + n, "audio of " + n)',
      'z.writestr("__MACOSX/iPhone Voicemail/._" + names[0], "apple double")',
      'z.close()',
    ].join('\n')
    execFileSync('python', ['-c', code, archive])
    const made = await running.rpc('box.create', { path: box, name: 'Voicemail box', owner: 'Maria Costa' })
    expect(made.ok, JSON.stringify(made)).toBe(true)
    expect((await running.rpc('settings.set', { values: { 'speech.model': '/models/ggml-saved.bin', 'speech.language': 'pt' } })).ok).toBe(true)
  }, 180_000)
  afterAll(async () => { await running?.stop() })
  // an import left half set up is remembered for the box, so each test starts from none
  afterEach(async () => { await running.rpc('session.set', { values: { draft: null, view: null } }) })

  it('explains a zip it cannot read, and makes a report that holds no names', async () => {
    const unnamed = join(running.work, 'Unnamed Voicemail.zip')
    const code = [
      'import sys, zipfile',
      'z = zipfile.ZipFile(sys.argv[1], "w")',
      'z.writestr("Voicemail/Diana Belenky 2018-12-21.amr", "a")',
      'z.writestr("Voicemail/notes.txt", "n")',
      'z.close()',
    ].join('\n')
    execFileSync('python', ['-c', code, unnamed])
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Import', exact: true }).click()
      await page.getByRole('button', { name: /^iPhone voicemail/ }).click()
      await page.getByRole('button', { name: 'I have the export' }).click()
      await page.getByLabel('Path to the export').fill(unnamed)
      await page.getByRole('button', { name: 'Continue' }).click()
      await page.getByRole('button', { name: 'Preview' }).click()
      const alert = page.getByRole('alert').first()
      await alert.waitFor({ timeout: 60_000 })
      const text = await alert.innerText()
      expect(text).toContain('This export cannot be imported')
      expect(text).toContain('Nothing to import was found')
      expect(text).toContain('What Caixa saw: a zip with 2 files')
      expect(text).toContain('none of their names start with a date')
      expect(text).toContain('Looking for:')
      expect(text).not.toContain('Diana')
      await page.getByRole('button', { name: 'Create a report' }).click()
      const report = await page.getByLabel('Report').inputValue()
      expect(report).toContain('Caixa diagnostic report')
      expect(report).toContain('== This source ==')
      expect(report).toContain('Cannot be imported')
      expect(report).not.toContain('Diana')
      expect(report).not.toContain('Belenky')
    } finally {
      await browser.close()
    }
  }, 240_000)

  it('previews and imports the zip, with the speech fields following Settings', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Import', exact: true }).click()
      await page.getByRole('button', { name: /^iPhone voicemail/ }).click()
      await page.getByRole('button', { name: 'I have the export' }).click()
      await page.getByLabel('Path to the export').fill(archive)
      await page.getByRole('button', { name: 'Continue' }).click()

      // the options step: the saved model and language are already there, transcribing is not on
      expect(await page.getByLabel('Speech model').inputValue()).toBe('/models/ggml-saved.bin')
      expect(await page.getByLabel('Language', { exact: true }).inputValue()).toBe('pt')
      expect(await page.getByLabel('Transcribe on this computer').isChecked()).toBe(false)
      await page.getByRole('button', { name: 'Browse this computer' }).click()
      await page.locator('[role="group"]').getByRole('button', { name: 'Up one level' }).waitFor({ timeout: 15_000 }).catch(() => undefined)

      await page.getByRole('button', { name: 'Preview' }).click()
      await page.getByText('3 items in 2 conversations', { exact: false }).waitFor({ timeout: 60_000 }).catch(async (error: Error) => {
        throw new Error(`The preview said: ${(await page.locator('[data-testid="caixa-page"]').innerText()).slice(0, 600)}\n${error.message}`)
      })
      await page.getByRole('button', { name: 'Import', exact: true }).last().click()
      await page.getByRole('heading', { name: 'Import finished' }).waitFor({ timeout: 120_000 })
      expect(await page.getByText(/\d+ new, \d+ changed, \d+ unchanged/).first().innerText()).toContain('3 new, 0 changed')
    } finally {
      await browser.close()
    }
    const listing = await running.rpc('browse.list', { path: 'People/Ana Costa/Voicemail' })
    expect(listing.ok, JSON.stringify(listing)).toBe(true)
  }, 240_000)
})
