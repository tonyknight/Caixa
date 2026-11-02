// The import wizard in a real browser, in the real DeepSeek Harness, against the real worker: every
// fixture of the synthetic family is imported through the pages, then the same fixtures through the
// command line into a second box, and the two boxes must hold the same rows, people and files.
import { execFileSync } from 'node:child_process'
import { readdirSync, statSync, readFileSync } from 'node:fs'
import { DatabaseSync } from 'node:sqlite'
import { join, relative } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { buildFixtures, canRun, openCaixa, playwright, startHarness, type Running } from './e2e-support.ts'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'

const run = canRun && playwright() ? describe : describe.skip

/** [collector id, the card's name in the wizard, where the fixture is, items it holds]. */
const SOURCES = (paths: Record<string, string>): [string, RegExp, string, number][] => [
  ['whatsapp', /^WhatsApp/, join(paths.whatsapp!, 'WhatsApp Chat - Ana Costa', '_chat.txt'), 7],
  ['imessage', /^iMessage/, paths.imessage!, 7],
  ['messenger', /^Messenger/, paths.messenger!, 5],
  ['mail', /^Mail/, paths.mbox!, 4],
  ['googlevoice', /^Google Voice/, paths.google_voice!, 6],
  ['voicemail', /^iPhone voicemail/, paths.iphone_voicemail!, 2],
]

function snapshot(box: string) {
  const db = new DatabaseSync(join(box, '.caixa', 'caixa.sqlite'), { readOnly: true })
  const rows = db.prepare('SELECT id, type, collector, service, conversation, timestamp_utc, text, file_path, anchor, content_hash FROM items ORDER BY id').all()
  const people = db.prepare('SELECT name, is_owner FROM people ORDER BY name').all()
  const links = db.prepare('SELECT item_id, person_id, role FROM item_people ORDER BY item_id, role, person_id').all().length
  db.close()
  const files: string[] = []
  const walk = (folder: string) => readdirSync(folder).forEach((name) => {
    if (folder === box && name === '.caixa') return
    const path = join(folder, name)
    statSync(path).isDirectory() ? walk(path) : files.push(relative(box, path))
  })
  walk(box)
  return { rows, people: people.map(p => ({ ...p })), links, files: files.sort() }
}

run('the import wizard, in a browser', () => {
  let running: Running
  let fixtures: Record<string, string>
  let cliBox: string
  let browserBox: string

  beforeAll(async () => {
    running = await startHarness()
    fixtures = buildFixtures(mkdtempSync(join(tmpdir(), 'caixa-fixtures-')))
    browserBox = join(running.work, 'Browser box')
    cliBox = join(running.work, 'CLI box')
  }, 180_000)
  afterAll(async () => { await running?.stop() })

  it('imports every fixture through the pages, and the same fixtures by command line give the same box', async () => {
    const library = playwright()!
    const browser = await library.chromium.launch()
    try {
      const page = await openCaixa(browser, running)

      // Make the box in the browser.
      await page.getByLabel('Folder for the new box').fill(browserBox)
      await page.getByLabel('Name', { exact: true }).fill('Browser box')
      await page.getByLabel('Your name').fill('Maria Costa')
      await page.getByRole('button', { name: 'Create box' }).click()
      await page.getByRole('heading', { name: 'Browser box' }).waitFor()

      let jobs = 0
      for (const [id, card, source, items] of SOURCES(fixtures)) {
        if (jobs === 0) await page.getByRole('navigation').getByRole('button', { name: 'Import', exact: true }).click()
        else await page.getByRole('button', { name: 'Import another' }).click()
        await page.getByRole('button', { name: card }).click()
        await page.getByRole('button', { name: 'I have the export' }).click()
        await page.getByLabel('Path to the export').fill(source)
        await page.getByRole('button', { name: 'Continue' }).click({ timeout: 10_000 }).catch(async (error: Error) => {
          const text = await page.locator('[data-testid="caixa-page"]').innerText()
          const typed = await page.getByLabel('Path to the export').inputValue().catch(() => '(no field)')
          throw new Error(`${id}: could not continue. Field holds ${JSON.stringify(typed)} (wanted ${JSON.stringify(source)}). Page: ${text.slice(0, 500)}\n${error.message.slice(0, 200)}`)
        })
        await page.getByRole('button', { name: 'Preview' }).click()
        await page.getByText(`${items} items in`, { exact: false }).waitFor({ timeout: 60_000 }).catch(async (error: Error) => {
          // say what the page showed, not just that something was missing
          throw new Error(`${id}: no "${items} items in" in the preview. The page said: ${(await page.locator('[data-testid="caixa-page"]').innerText()).slice(0, 600)}\n${error.message}`)
        })
        await page.getByRole('button', { name: 'Import', exact: true }).last().click()
        await page.getByRole('heading', { name: 'Import finished' }).waitFor({ timeout: 120_000 }).catch(async (error: Error) => {
          const jobs = (await running.rpc('jobs.list', { limit: 3 })).result as { id: number; status: string; stage: string; error: string | null; log: string }[]
          const log = jobs[0] ? (await running.rpc('jobs.log', { job: jobs[0].id })).result?.text?.slice(-800) : ''
          throw new Error(`${id}: the import did not finish. Jobs: ${JSON.stringify(jobs.map(j => [j.id, j.status, j.stage, j.error]))}\nLog tail: ${log}\n${error.message}`)
        })
        const report = await page.getByText(/\d+ new, \d+ changed, \d+ unchanged/).first().innerText()
        expect(report, id).toContain(`${items} new, 0 changed`) // this import's own items; "unchanged" counts the rest of the box
        jobs += 1
        if (id === 'whatsapp') {
          // The toast is in DSH's own overlay: it says the same thing wherever you are.
          await page.getByText('WhatsApp: 7 new items imported.').first().waitFor({ timeout: 15_000 })
        }
      }

      // Jobs: one row per import, each with a log.
      await page.getByRole('navigation').getByRole('button', { name: 'Jobs' }).click()
      await page.getByRole('table').waitFor()
      expect(await page.getByRole('row').count()).toBe(jobs + 1)
      await page.getByRole('button', { name: /Show details/ }).first().click()
      await page.getByRole('region', { name: /Details of job/ }).waitFor()
      await page.getByRole('heading', { name: 'Log' }).waitFor()

      // The Box section counts what arrived.
      await page.getByRole('navigation').getByRole('button', { name: 'Box' }).click()
      await page.getByText('Messages: ', { exact: false }).waitFor()
    } finally {
      await browser.close()
    }

    // The same sources, the same order, by command line.
    execFileSync('caixa', ['box', 'create', cliBox, '--name', 'CLI box', '--owner', 'Maria Costa'], { stdio: 'ignore' })
    for (const [id, , source] of SOURCES(fixtures)) {
      execFileSync('caixa', ['import', id, source, '--box', cliBox], { stdio: 'ignore', timeout: 180_000 })
    }

    const fromBrowser = snapshot(browserBox)
    const fromCommandLine = snapshot(cliBox)
    expect(fromBrowser.rows.length).toBe(7 + 7 + 5 + 4 + 6 + 2)
    expect(fromBrowser.rows).toEqual(fromCommandLine.rows)
    expect(fromBrowser.people).toEqual(fromCommandLine.people)
    expect(fromBrowser.links).toBe(fromCommandLine.links)
    expect(fromBrowser.files).toEqual(fromCommandLine.files)
    expect(fromBrowser.files.some(file => file.startsWith('Messages/'))).toBe(true)
    // (the pages themselves are compared by content: same text, same links)
    for (const file of fromBrowser.files.filter(f => f.endsWith('.html'))) {
      expect(readFileSync(join(browserBox, file), 'utf8'), file).toBe(readFileSync(join(cliBox, file), 'utf8'))
    }
  }, 600_000)
})
