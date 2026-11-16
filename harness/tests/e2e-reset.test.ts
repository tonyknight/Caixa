// Starting a box again from Settings, in a real browser against the real worker: what was imported
// goes, the settings stay.
import { existsSync, mkdtempSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { buildFixtures, canRun, openCaixa, playwright, startHarness, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

run('starting a box again, in a browser', () => {
  let running: Running
  let box: string

  beforeAll(async () => {
    running = await startHarness()
    const fixtures = buildFixtures(mkdtempSync(join(tmpdir(), 'caixa-fixtures-')))
    box = join(running.work, 'Box')
    expect((await running.rpc('box.create', { path: box, name: 'Reset box', owner: 'Maria Costa' })).ok).toBe(true)
    expect((await running.rpc('settings.set', { values: { 'speech.language': 'pt' } })).ok).toBe(true)
    const started = await running.rpc('import.start', { collector: 'whatsapp', source: join(fixtures.whatsapp!, 'WhatsApp Chat - Ana Costa', '_chat.txt') })
    expect(started.ok, JSON.stringify(started)).toBe(true)
    for (let i = 0; i < 600; i++) {
      const job = (await running.rpc('jobs.get', { job: started.result.id })).result
      if (job.status === 'done') break
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    expect((await running.rpc('box.status')).result.items).toBe(7)
  }, 180_000)
  afterAll(async () => { await running?.stop() })

  it('clears the imported data and keeps the settings', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click()
      const card = page.getByRole('region', { name: 'Start this box again' })
      await card.getByRole('button', { name: 'Start again…' }).click()
      await card.getByRole('alertdialog').getByRole('button', { name: 'Start again', exact: true }).click()
      await page.getByTestId('reset-result').getByText('The box is empty again', { exact: false }).waitFor({ timeout: 60_000 })
    } finally {
      await browser.close()
    }
    const status = (await running.rpc('box.status')).result
    expect(status.items).toBe(0)
    expect(status.owner).toBe('Maria Costa')
    expect((await running.rpc('settings.get')).result.values['speech.language']).toBe('pt')
    expect(existsSync(join(box, 'People')) ? readdirSync(join(box, 'People')) : []).toEqual([])
    expect(existsSync(join(box, 'index.html'))).toBe(false)
  }, 180_000)
})
