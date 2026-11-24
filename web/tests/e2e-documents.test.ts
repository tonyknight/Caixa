// Documents in a real browser, served by the real `caixa serve`: a PDF of the box opened in the
// overlay over a page (the browser's own viewer, in a frame), from the box and from disk.
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { buildDocumentsBox, buildPdfFamily, canRun, openCaixa, playwright, repository, startCaixa, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip
const SCRIPT = readFileSync(join(repository, 'caixa', 'documents', 'templates', 'document.js'), 'utf8').replace(/\n$/, '')
const STYLE = readFileSync(join(repository, 'caixa', 'documents', 'templates', 'document.css'), 'utf8')

run('Documents, in a browser', () => {
  let running: Running
  let box: string
  let pdf: string

  const finished = async (started: { ok: boolean; result?: any }) => {
    expect(started.ok, JSON.stringify(started)).toBe(true)
    const end = Date.now() + 120_000
    while (Date.now() < end) {
      const job = (await running.rpc('jobs.get', { job: started.result.id })).result
      if (['done', 'failed', 'cancelled'].includes(job.status)) { expect(job.status, job.error).toBe('done'); return job }
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    throw new Error('the job did not finish')
  }

  beforeAll(async () => {
    running = await startCaixa()
    const family = buildPdfFamily(mkdtempSync(join(tmpdir(), 'caixa-pdfs-')))
    const source = mkdtempSync(join(tmpdir(), 'caixa-statement-'))
    copyFileSync(join(family, '2024-11 Banco Atlântico Checking Statement.pdf'), join(source, '2024-11 Banco Atlântico Checking Statement.pdf'))
    box = join(running.work, 'Box')
    expect((await running.rpc('box.create', { path: box, name: 'Documents box', owner: 'Maria Costa' })).ok).toBe(true)
    expect((await running.rpc('settings.set', { values: { 'documents.ocr': false, 'documents.enrich': false } })).ok).toBe(true)
    await finished(await running.rpc('import.start', { collector: 'pdf', source }))
    pdf = (await running.rpc('documents.list', {})).result.documents[0].file_path
    // a page of the box with a card's link, as the document pages carry it
    mkdirSync(join(box, 'Documents', 'PDF'), { recursive: true })
    const href = encodeURI(pdf.replace(/^Documents\/PDF\//, '')) + '#page=2'
    writeFileSync(join(box, 'Documents', 'PDF', 'Cards.html'),
      `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Cards</title><style>${STYLE}</style></head><body>` +
      `<a class="open-document" data-title="Checking Statement" href="${href}">Open</a>` +
      `<script>${SCRIPT}</script></body></html>`, 'utf8')
  }, 180_000)
  afterAll(async () => { await running?.stop() })

  it('opens a PDF over the page, at its page, and closes it', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      const errors: string[] = []
      page.on('console', (message: any) => { if (message.type() === 'error') errors.push(message.text()) })
      await page.goto(`${running.base}/box/Documents/PDF/Cards.html`, { waitUntil: 'networkidle' })
      await page.getByRole('link', { name: 'Open' }).click()
      const overlay = page.getByRole('dialog', { name: 'Document' })
      await overlay.waitFor()
      const src = await page.locator('.document-overlay iframe').getAttribute('src')
      expect(decodeURI(new URL(src!, page.url()).pathname)).toBe(`/box/${pdf}`)
      expect(src!.endsWith('#page=2')).toBe(true)
      expect(await overlay.getByRole('link', { name: 'Open in its own window' }).getAttribute('href')).toBe(src)
      expect(await overlay.locator('.do-title').textContent()).toBe('Checking Statement')
      await page.keyboard.press('Escape')
      await overlay.waitFor({ state: 'hidden' })
      await page.getByRole('link', { name: 'Open' }).click()
      await overlay.waitFor()
      await overlay.getByRole('button', { name: 'Close' }).click()
      await overlay.waitFor({ state: 'hidden' })
      expect(errors.filter(e => /Content Security Policy/.test(e))).toEqual([])  // the script ran under the policy
      // the PDF itself is shown, not downloaded
      const reply = await page.request.get(`${running.base}/box/${encodeURI(pdf)}`)
      expect(reply.headers()['content-type']).toBe('application/pdf')
      expect(reply.headers()['content-disposition']).toBeUndefined()
    } finally {
      await browser.close()
    }
  }, 120_000)

  it('opens it from disk too', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await browser.newPage()
      await page.goto(pathToFileURL(join(box, 'Documents', 'PDF', 'Cards.html')).href)
      await page.getByRole('link', { name: 'Open' }).click()
      await page.getByRole('dialog', { name: 'Document' }).waitFor()
      const src = await page.locator('.document-overlay iframe').getAttribute('src')
      expect(new URL(src!, page.url()).protocol).toBe('file:')
      expect(decodeURI(new URL(src!, page.url()).pathname).endsWith(pdf)).toBe(true)
    } finally {
      await browser.close()
    }
  }, 120_000)
})

run('The documents view, from disk', () => {
  let box: string
  beforeAll(() => { box = buildDocumentsBox(mkdtempSync(join(tmpdir(), 'caixa-documents-box-'))) }, 300_000)

  it('narrows the documents by their words and by years', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await browser.newPage()
      await page.goto(pathToFileURL(join(box, 'Documents', 'PDF', 'PDF.html')).href)
      const entries = page.locator('li.entry-doc')
      const visible = async () => await entries.evaluateAll((items: HTMLElement[]) => items.filter(i => !i.hidden).length)
      expect(await entries.count()).toBe(15)
      expect(await visible()).toBe(15)
      await page.getByLabel('Find documents by their words').fill('atlantico checking')
      expect(await visible()).toBe(2)  // the statement and its copy: accents and case aside
      await page.getByLabel('Find documents by their words').fill('')
      await page.getByLabel('From the year').selectOption('2024')
      const years = await page.locator('section.year-block').evaluateAll((blocks: HTMLElement[]) =>
        blocks.filter(b => !b.hidden).map(b => b.getAttribute('data-year-block')))
      expect(years).toEqual(['2024'])
      const shown = await entries.evaluateAll((items: HTMLElement[]) =>
        items.filter(i => !i.hidden).map(i => i.getAttribute('data-year')))
      expect(shown.every((year: string | null) => !year || year >= '2024')).toBe(true)
    } finally {
      await browser.close()
    }
  }, 120_000)

  it('is reached from the box', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await browser.newPage()
      await page.goto(pathToFileURL(join(box, 'index.html')).href)
      await page.getByRole('link', { name: 'Documents ▸ PDF' }).click()
      await page.getByRole('heading', { name: 'PDF documents' }).waitFor()
      await page.getByRole('link', { name: /Banco Atlântico/ }).first().click()
      await page.getByRole('heading', { name: /Banco Atlântico · 2024/ }).waitFor()
    } finally {
      await browser.close()
    }
  }, 120_000)
})

run('Searching documents in Caixa', () => {
  let running: Running
  beforeAll(async () => {
    running = await startCaixa()
    const box = buildDocumentsBox(running.work)
    expect((await running.rpc('box.open', { path: box })).ok).toBe(true)
  }, 300_000)
  afterAll(async () => { await running?.stop() })

  it('finds pages by their words and opens them at the page', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.goto(`${running.base}/box/Documents/PDF/PDF.html`, { waitUntil: 'networkidle' })
      const search = page.getByRole('searchbox', { name: 'Search every page' })
      await search.fill('Supermercado')
      await page.getByRole('button', { name: 'Search' }).click()
      const hit = page.locator('ol.hits li').first()
      await hit.locator('mark').first().waitFor()
      expect(await hit.locator('mark').first().textContent()).toBe('Supermercado')
      expect(await hit.textContent()).toContain('page 2')
      await hit.getByRole('link', { name: 'Open at page 2' }).click()
      await page.getByRole('dialog', { name: 'Document' }).waitFor()
      expect((await page.locator('.document-overlay iframe').getAttribute('src'))!.endsWith('#page=2')).toBe(true)
      await page.getByRole('dialog', { name: 'Document' }).getByRole('button', { name: 'Close' }).click()
      await page.getByRole('dialog', { name: 'Document' }).waitFor({ state: 'hidden' })

      await search.fill('Maria')
      await page.getByRole('combobox', { name: 'Of the type' }).selectOption('statement')
      await page.getByRole('button', { name: 'Search' }).click()
      await page.waitForFunction(() => !document.querySelector('ol.hits')?.textContent?.includes('Searching'))
      const titles = await page.locator('ol.hits li strong').allTextContents()
      expect(titles.length).toBeGreaterThan(0)
      expect(titles.every((t: string) => /Statement|Extrato/i.test(t))).toBe(true)

      await search.fill('nowhere-to-be-found')
      await page.getByRole('combobox', { name: 'Of the type' }).selectOption('')
      await page.getByRole('button', { name: 'Search' }).click()
      await page.getByText('Nothing found.').waitFor()
    } finally {
      await browser.close()
    }
  }, 120_000)

  it('keeps the search hidden from disk', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await browser.newPage()
      const box = join(running.work, 'Box')
      await page.goto(pathToFileURL(join(box, 'Documents', 'PDF', 'PDF.html')).href)
      expect(await page.locator('form.search').isHidden()).toBe(true)
      expect(await page.getByLabel('Find documents by their words').isVisible()).toBe(true)
    } finally {
      await browser.close()
    }
  }, 120_000)
})

