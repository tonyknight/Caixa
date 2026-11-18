// The box's index page inside Caixa: people as tiles, sorted into categories by selecting them in
// Unassigned and dragging them onto a category (or with the buttons in the footer), saved in the box.
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, shot, startCaixa, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

run('sorting people on the index page, in a browser', () => {
  let running: Running
  let box: string

  const imported = async (collector: string, source: string) => {
    const started = await running.rpc('import.start', { collector, source })
    expect(started.ok, JSON.stringify(started)).toBe(true)
    for (let i = 0; i < 600; i++) {
      const job = (await running.rpc('jobs.get', { job: started.result.id })).result
      if (job.status === 'done') return
      if (['failed', 'cancelled'].includes(job.status)) throw new Error(job.error)
      await new Promise(resolve => setTimeout(resolve, 200))
    }
  }
  const categories = async () => Object.fromEntries(
    ((await running.rpc('people.list')).result.people as { name: string; category: string | null }[]).map(p => [p.name, p.category]))

  beforeAll(async () => {
    running = await startCaixa()
    box = join(running.work, 'Box')
    expect((await running.rpc('box.create', { path: box, name: 'Sorting box', owner: 'Maria Costa' })).ok).toBe(true)
    const archive = join(mkdtempSync(join(tmpdir(), 'caixa-vm-')), 'Voicemail.zip')
    const code = [
      'import sys, zipfile',
      'z = zipfile.ZipFile(sys.argv[1], "w")',
      'for n, who in enumerate(["Pedro Dias", "Luisa Gomes", "Sara Lima"]): z.writestr(f"vm/(2019-01-0{n + 1}) 10 00 00 - {who}.amr", "a")',
      'z.writestr("vm/(2019-02-01) 10 00 00 - +15550000123.amr", "a")',
      'z.writestr("vm/(2019-02-02) 10 00 00 - +15550000456.amr", "a")',
      'z.writestr("vm/(2019-02-03) 10 00 00 - +15550000456.amr", "b")',  // the busier number: two calls
      'z.close()',
    ].join('\n')
    execFileSync('python', ['-c', code, archive])
    await imported('voicemail', archive)
  }, 180_000)
  afterAll(async () => { await running?.stop() })

  it('selects people in Unassigned and drags them onto a category', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Browse' }).click()
      // the index opens in a window of its own, with the whole screen for sorting
      const [index] = await Promise.all([page.waitForEvent('popup'), page.getByRole('button', { name: "Open the box's index page" }).click()])
      await index.setViewportSize({ width: 1280, height: 900 })
      // the window scrolls as a whole, with no scroll area of its own inside it
      await index.getByRole('heading', { name: 'All people' }).waitFor({ timeout: 30_000 })
      expect(await index.evaluate(() => ({
        body: getComputedStyle(document.body).overflowY,
        content: getComputedStyle(document.querySelector('.content')!).overflowY,
        sidebar: getComputedStyle(document.querySelector('.sidebar')!).position,
        footer: getComputedStyle(document.querySelector('.status')!).position,
      }))).toEqual({ body: 'visible', content: 'visible', sidebar: 'sticky', footer: 'sticky' })
      await index.getByRole('heading', { name: 'All people' }).waitFor({ timeout: 30_000 })
      // the dashboard shows on All; the number nobody named is in Unrecognized, not All
      await index.getByRole('region', { name: 'About this box' }).waitFor()
      expect(await index.locator('#people .tile:visible').count()).toBe(3)
      await expect.poll(() => index.locator('#count').textContent()).toBe('3 people')

      await index.locator('.sidebar a[data-view="unassigned"]').click()
      await index.getByRole('heading', { name: 'Unassigned' }).waitFor()
      expect(await index.getByRole('region', { name: 'About this box' }).isVisible()).toBe(false)
      const tiles = index.locator('#people .tile:visible')
      expect(await tiles.count()).toBe(3)
      await tiles.nth(0).click()
      await tiles.nth(1).click({ modifiers: ['Shift'] })
      await expect.poll(() => index.locator('#picked').textContent()).toBe('2 selected')
      await shot(index, 'categories-selected')
      // Drag the first selected tile onto Family. (The browser's own drag events are sent in the
      // order a person's drag makes them: Playwright's mouse cannot make a native drag here.)
      await tiles.nth(0).evaluate((tile: HTMLElement) => {
        const family = document.querySelector('.sidebar a[data-category="family"]')!
        const data = new DataTransfer()
        tile.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: data }))
        family.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: data }))
        family.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: data }))
        family.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: data }))
        tile.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true, dataTransfer: data }))
      })
      await index.getByText('2 people moved to Family.').waitFor({ timeout: 30_000 }).catch(async (error: Error) => {
        throw new Error(`footer said: ${await index.locator('#said').textContent()} / picked ${await index.locator('#picked').textContent()}\n${error.message}`)
      })
      expect(await index.locator('#people .tile:visible').count()).toBe(1)  // they left Unassigned
      expect(await index.locator('.sidebar a[data-view="family"] .n').textContent()).toBe('2')
      const saved = await categories()
      expect(['Luisa Gomes', 'Pedro Dias'].map(name => saved[name])).toEqual(['family', 'family'])

      // the last one with the footer's buttons
      await index.locator('#people .tile:visible').first().click()
      await index.locator('#actions').getByRole('button', { name: 'Friends' }).click()
      await index.getByText('1 person moved to Friends.').waitFor({ timeout: 30_000 })
      expect((await categories())['Sara Lima']).toBe('friends')

      // in a category, the close box on hover sends someone back to Unassigned
      await index.locator('.sidebar a[data-view="friends"]').click()
      const sara = index.locator('#people .cell:visible').first()
      // its buttons show only on hover: a close box in the corner, and nothing else
      await index.mouse.move(5, 5)
      const close = sara.getByRole('button', { name: 'Move Sara Lima back to Unassigned' })
      expect(await close.evaluate((b: HTMLElement) => getComputedStyle(b).opacity)).toBe('0')
      await sara.hover()
      await expect.poll(() => close.evaluate((b: HTMLElement) => getComputedStyle(b).opacity)).toBe('1')
      expect(await sara.getByRole('button', { name: /new window/ }).isVisible()).toBe(false)
      const corner = await close.boundingBox(), tileBox = await sara.locator('.tile').boundingBox()
      expect(corner!.x + corner!.width).toBeGreaterThan(tileBox!.x + tileBox!.width - 30)  // the upper right
      expect(corner!.y).toBeLessThan(tileBox!.y + 30)
      await sara.getByRole('button', { name: 'Move Sara Lima back to Unassigned' }).click()
      await index.getByText('Sara Lima moved back to Unassigned.').waitFor({ timeout: 30_000 })
      expect((await categories())['Sara Lima']).toBe(null)
      expect(await index.locator('#people .tile:visible').count()).toBe(0)

      // Unrecognized: the number nobody named gets a name, and is kept as a person
      await index.locator('.sidebar a[data-view="unrecognized"]').click()
      await index.getByRole('heading', { name: 'Unrecognized' }).waitFor()
      // busiest first: the number with two calls comes before the one with one, though it sorts after it
      expect(await index.locator('#people .cell:visible .name').allTextContents()).toEqual(['+15550000456', '+15550000123'])
      const unknown = index.locator('#people .cell:visible').first()
      const field = unknown.locator('.naming input')  // (hidden from everyone, even screen readers, until hovered)
      // nothing shows until the pointer is over the tile: then the name field, and the open button
      await index.mouse.move(5, 5)
      expect(await field.evaluate((f: HTMLElement) => getComputedStyle(f.parentElement!).visibility)).toBe('hidden')
      await unknown.hover()
      await expect.poll(() => field.evaluate((f: HTMLElement) => getComputedStyle(f.parentElement!).visibility)).toBe('visible')
      expect(await unknown.getByRole('button', { name: /back to Unassigned/ }).isVisible()).toBe(false)
      expect(await unknown.getByRole('button', { name: 'Apply' }).isVisible()).toBe(false)  // not before a name is typed
      // typing offers the people already in the box
      await field.fill('lu')
      await unknown.getByRole('option', { name: /Luisa Gomes/ }).waitFor()
      expect(await unknown.getByRole('button', { name: 'Apply' }).isVisible()).toBe(true)
      await shot(index, 'categories-naming')
      await field.press('Escape')
      expect(await unknown.getByRole('listbox').isVisible()).toBe(false)
      // a name nobody has: a new person
      await field.fill('Tio Rui')
      expect(await unknown.getByRole('option').count()).toBe(0)
      await unknown.getByRole('button', { name: 'Apply' }).click()
      await index.getByText('Tio Rui is kept as a person, in Unassigned.').waitFor({ timeout: 30_000 }).catch(async (error: Error) => {
        throw new Error(`footer said: ${await index.locator('#said').textContent()} / ${await unknown.locator('.tile').getAttribute('data-handles')}\n${error.message}`)
      })
      expect(Object.keys(await categories())).toContain('Tio Rui')

      // the other number joins someone already in the box, picked from the suggestions
      const other = index.locator('#people .cell:visible').first()
      await other.hover()
      const otherField = other.getByRole('combobox', { name: 'Name for this person' })
      await otherField.fill('sara')
      await other.getByRole('option', { name: /Sara Lima/ }).click()
      expect(await otherField.inputValue()).toBe('Sara Lima')
      await otherField.press('Enter')
      await index.getByText('Linked to Sara Lima.', { exact: false }).waitFor({ timeout: 30_000 })
      expect(await index.locator('#people .tile:visible').count()).toBe(0)  // its tile joined hers
      const people = (await running.rpc('people.list')).result.people as { name: string }[]
      expect(people.filter(p => p.name === 'Sara Lima')).toHaveLength(1)

      // Unassigned: the open-in-a-new-window button keeps the selection; Delete asks, then removes
      await index.locator('.sidebar a[data-view="unassigned"]').click()
      // back in name order outside Unrecognized
      const names = await index.locator('#people .cell:visible .name').allTextContents()
      expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)))
      const rui = index.locator('#people .cell:visible', { hasText: 'Tio Rui' })
      await rui.locator('.tile').click()
      await expect.poll(() => index.locator('#picked').textContent()).toBe('1 selected')
      await rui.hover()
      const [opened] = await Promise.all([
        page.context().waitForEvent('page'),
        rui.getByRole('button', { name: 'Open Tio Rui in a new window' }).click(),
      ])
      await opened.waitForLoadState()
      expect(decodeURIComponent(opened.url())).toContain('People/')  // (the page from before the redraw)
      await opened.close()
      expect(await index.locator('#picked').textContent()).toBe('1 selected')
      await rui.locator('.tile').press('Delete')
      const ask = index.getByRole('dialog', { name: 'Delete 1 person from this box?' })
      await ask.waitFor()
      await shot(index, 'categories-delete')
      await ask.getByRole('button', { name: 'Delete' }).click()
      await index.getByText('1 person deleted. The pages are being redrawn.').waitFor({ timeout: 30_000 })
      expect(Object.keys(await categories())).not.toContain('Tio Rui')
      expect(await index.locator('#people .tile', { hasText: 'Tio Rui' }).count()).toBe(0)

      // in a category, a click opens the person's page (once the redraw the removal started is done)
      for (let i = 0; i < 300; i++) {
        const jobs = (await running.rpc('jobs.list')).result as { status: string }[]
        if (!jobs.some(j => ['queued', 'running'].includes(j.status))) break
        await new Promise(resolve => setTimeout(resolve, 200))
      }
      await index.locator('.sidebar a[data-view="family"]').click()
      await index.locator('#people .tile:visible').first().click()
      await index.getByRole('link', { name: '← All people' }).waitFor({ timeout: 30_000 }).catch(async (error: Error) => {
        throw new Error(`at ${index.url()}: ${(await index.locator('body').innerText()).slice(0, 300)}\n${error.message}`)
      })
    } finally {
      await browser.close()
    }
    // the index file itself is redrawn with the categories, for opening without Caixa
    for (let i = 0; i < 300; i++) {
      const jobs = (await running.rpc('jobs.list')).result as { kind: string; status: string }[]
      if (!jobs.some(j => ['queued', 'running'].includes(j.status))) break
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    const html = readFileSync(join(box, 'index.html'), 'utf8')
    expect(html).toMatch(/data-category="family" data-items="\d+" data-name="Pedro Dias"/)
    expect(html).toMatch(/data-category="" data-items="2" data-name="Sara Lima"/)  // her call and the number that joined her
    expect(html).not.toContain('Tio Rui')
    expect(html).not.toContain('+15550000456')  // removed, not just renamed
  }, 240_000)
})
