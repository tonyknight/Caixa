// Stopping Caixa and starting it again, in the real harness with the real worker: the box that was
// open is open again, the section you were in is where you land, and an import you had set up but
// not started is put back with what you had typed and chosen.
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, startHarness, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

run('stopping and starting Caixa again', () => {
  let remembered: string
  let box: string
  let first: Running | undefined
  let second: Running | undefined

  beforeAll(async () => {
    remembered = mkdtempSync(join(tmpdir(), 'caixa-remembered-'))
    box = join(remembered, 'Our Box')
    first = await startHarness({ caixaHome: join(remembered, 'home') })
    const made = await first.rpc('box.create', { path: box, name: 'Our box', owner: 'Maria Costa' })
    expect(made.ok, JSON.stringify(made)).toBe(true)
    const kept = await first.rpc('session.set', { values: {
      view: 'import',
      draft: { collector: 'voicemail', step: 'options', source: '/exports/iPhone Voicemail.zip', values: { transcribe: true, model: '/models/ggml-small.bin', language: 'pt' } },
    } })
    expect(kept.ok, JSON.stringify(kept)).toBe(true)
    await first.stop() // Caixa is stopped: nothing but the folder of remembered things survives
    first = undefined
    second = await startHarness({ caixaHome: join(remembered, 'home') })
  }, 240_000)

  afterAll(async () => {
    await first?.stop()
    await second?.stop()
    rmSync(remembered, { recursive: true, force: true })
  })

  it('has the same box open without being told which', async () => {
    const status = await second!.rpc('box.status')
    expect(status.ok, JSON.stringify(status)).toBe(true)
    expect(status.result.name).toBe('Our box')
    const session = await second!.rpc('session.get')
    expect(session.result.recent.map((b: { name: string }) => b.name)).toEqual(['Our box'])
  })

  it('lands on the section you were in, with the import put back as you left it', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, second!)
      await page.getByRole('heading', { name: 'Where do your messages come from?' }).or(page.getByRole('list', { name: 'Steps' })).first().waitFor({ timeout: 20_000 })
      expect(await page.getByLabel('Speech model').inputValue()).toBe('/models/ggml-small.bin')
      expect(await page.getByLabel('Language', { exact: true }).inputValue()).toBe('pt')
      expect(await page.getByLabel('Transcribe on this computer').isChecked()).toBe(true)
      await page.getByRole('button', { name: 'Back' }).click()
      expect(await page.getByLabel('Path to the export').inputValue()).toBe('/exports/iPhone Voicemail.zip')
    } finally {
      await browser.close()
    }
  }, 120_000)
})
