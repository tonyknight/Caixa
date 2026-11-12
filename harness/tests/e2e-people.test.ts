// The People section in a real browser, in the real DeepSeek Harness, against the real worker:
// name unnamed handles, rename and merge, and watch the generated pages follow on disk.
import { existsSync, readdirSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { buildFixtures, canRun, openCaixa, playwright, startHarness, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

const pages = (box: string, person: string) => {
  const folder = join(box, 'People', person)
  return existsSync(folder) ? readdirSync(folder).filter(name => /^\(\d{4}\) .*\.html$/.test(name)).sort() : []
}

run('the People section, in a browser', () => {
  let running: Running
  let box: string
  let fixtures: Record<string, string>

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
    fixtures = buildFixtures(mkdtempSync(join(tmpdir(), 'caixa-fixtures-')))
    box = join(running.work, 'Box')
    expect((await running.rpc('box.create', { path: box, name: 'People box', owner: 'Maria Costa' })).ok).toBe(true)
    await imported('whatsapp', join(fixtures.whatsapp!, 'WhatsApp Chat - Ana Costa', '_chat.txt'))
    await imported('imessage', fixtures.imessage!)
  }, 180_000)
  afterAll(async () => { await running?.stop() })

  it('names handles, renames and merges through the page, and the pages follow', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'People' }).click()
      await page.getByRole('heading', { name: /Not yet named/ }).waitFor()
      // The banner of the previous change stays until the next one replaces it, so wait for this change's
      // own message first, then for the pages to be redrawn.
      const upToDate = async (message: string) => {
        await page.getByText(message, { exact: false }).waitFor({ timeout: 60_000 })
        await page.getByText('The pages are up to date.').waitFor({ timeout: 60_000 })
      }

      // The queue shows what the imports could not name.
      await page.getByText('Ana Costa', { exact: true }).first().waitFor({ timeout: 30_000 }) // (wait: the list re-reads itself when a job ends)
      expect(pages(box, 'Ana Costa')).toEqual(['(2024) Ana Costa.html'])

      // Name the WhatsApp handle: the page moves to the new person's folder and the old one goes.
      await page.getByLabel('Name for Ana Costa').fill('Ana A')
      await page.getByRole('row', { name: /Ana Costa/ }).getByRole('button', { name: 'Link' }).click()
      await upToDate('Linked “Ana Costa” to Ana A.')
      expect(pages(box, 'Ana A')).toEqual(['(2024) Ana A.html'])
      expect(pages(box, 'Ana Costa')).toEqual([])
      await page.getByRole('heading', { name: 'People (2)' }).waitFor()

      // Name an iMessage handle for a second person.
      const handles = (await running.rpc('people.unresolved')).result.handles as { service: string; identifier: string }[]
      const digits = (text: string) => text.replace(/\D/g, '')
      const phone = handles.find(h => h.service === 'iMessage' && digits(h.identifier) === digits(fixtures.ana_phone!))!
      expect(phone, JSON.stringify(handles)).toBeDefined()
      await page.getByLabel(`Name for ${phone.identifier}`).fill('Ana B')
      await page.getByRole('row', { name: new RegExp(phone.identifier.replace(/[+()]/g, '\\$&')) }).getByRole('button', { name: 'Link' }).click()
      await upToDate(`Linked “${phone.identifier}” to Ana B.`)
      const afterLink = (await running.rpc('people.list')).result.people.map((p: { name: string }) => p.name)
      expect(afterLink).toEqual(expect.arrayContaining(['Ana A', 'Ana B']))
      expect(pages(box, 'Ana B').length).toBeGreaterThan(0)

      // Rename the first.
      await page.getByRole('button', { name: 'Rename Ana A' }).click()
      await page.getByLabel('New name for Ana A').fill('Ana Cruz')
      await page.getByRole('button', { name: 'Save' }).click()
      await upToDate('Renamed to Ana Cruz.')
      expect(pages(box, 'Ana Cruz')).toEqual(['(2024) Ana Cruz.html'])
      expect(pages(box, 'Ana A')).toEqual([])

      // Merge the second into the first, after the page says what will happen.
      const bYears = pages(box, 'Ana B').map(name => name.slice(0, 6))
      await page.getByRole('button', { name: 'Merge… Ana B' }).click()
      await page.getByLabel('Merge Ana B into').selectOption({ label: 'Ana Cruz' })
      await page.getByRole('button', { name: 'Merge…', exact: true }).click()
      await page.getByRole('alertdialog').getByText('Merge Ana B into Ana Cruz?', { exact: false }).waitFor()
      await page.getByRole('alertdialog').getByRole('button', { name: 'Merge', exact: true }).click()
      await upToDate('Merged into Ana Cruz.')
      const merged = (await running.rpc('people.list')).result.people.map((p: { name: string }) => p.name)
      expect(merged).not.toContain('Ana B')
      expect(pages(box, 'Ana B')).toEqual([])
      const cruz = pages(box, 'Ana Cruz').map(name => name.slice(0, 6))
      expect(cruz).toEqual(expect.arrayContaining(['(2024)', ...bYears]))

      // Nothing was lost: every item still links to a person who is in the box.
      const status = (await running.rpc('box.status')).result
      expect(status.items).toBe(14)
    } finally {
      await browser.close()
    }
  }, 300_000)
})
