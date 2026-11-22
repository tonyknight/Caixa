// The box's index page inside Caixa: people as tiles, sorted into categories by selecting them in
// Unassigned and dragging them onto a category (or with the buttons in the footer), saved in the box.
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
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

  it('selects people within a category with Cmd-click, Shift-Cmd-click or a box, and moves them', async () => {
    const cousins = (await running.rpc('people.subcategory.add', { category: 'family', name: 'Cousins' })).result.id as number
    for (let i = 0; i < 300; i++) {  // (the redraw that adding it started)
      const jobs = (await running.rpc('jobs.list')).result as { status: string }[]
      if (!jobs.some(j => ['queued', 'running'].includes(j.status))) break
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Browse' }).click()
      const [index] = await Promise.all([page.waitForEvent('popup'), page.getByRole('button', { name: "Open the box's index page" }).click()])
      await index.setViewportSize({ width: 1280, height: 900 })
      await index.getByRole('heading', { name: 'All people' }).waitFor({ timeout: 30_000 })
      await index.locator('.sidebar a[data-view="family"]').click()
      expect(await index.getByText('⌘-click', { exact: false }).isVisible()).toBe(true)  // the page says how
      const tiles = index.locator('#people .tile:visible')
      expect(await tiles.count()).toBe(2)
      const at = index.url()
      // Cmd-click selects in place: no page opens
      await tiles.nth(0).click({ modifiers: ['Meta'] })
      await tiles.nth(1).click({ modifiers: ['Meta'] })
      expect(index.url()).toBe(at)
      await expect.poll(() => index.locator('#picked').textContent()).toBe('2 selected')
      await shot(index, 'category-selected')
      // dragging one of them moves both
      await tiles.nth(0).evaluate((tile: HTMLElement, id: number) => {
        const goal = document.querySelector(`.sidebar a[data-sub="${id}"]`)!
        const data = new DataTransfer()
        tile.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: data }))
        goal.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: data }))
        goal.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: data }))
        tile.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true, dataTransfer: data }))
      }, cousins)
      await index.getByText('2 people moved to Cousins.').waitFor({ timeout: 30_000 })
      const listed = (await running.rpc('people.list')).result.people as { name: string; subcategory: number | null }[]
      expect(listed.filter(p => p.subcategory === cousins).map(p => p.name).sort()).toEqual(['Luisa Gomes', 'Pedro Dias'])

      // in the subcategory: Cmd-click one, Shift-Cmd-click the other selects the range
      await index.getByRole('button', { name: 'Subcategories of Family' }).click()
      await index.locator(`.sidebar a[data-sub="${cousins}"]`).click()
      await expect.poll(() => tiles.count()).toBe(2)
      await tiles.nth(0).click({ modifiers: ['Meta'] })
      await tiles.nth(1).click({ modifiers: ['Meta', 'Shift'] })
      await expect.poll(() => index.locator('#picked').textContent()).toBe('2 selected')
      await index.keyboard.press('Escape')
      await expect.poll(() => index.locator('#picked').textContent()).toBe('0 selected')

      // a box drawn from the empty space across the tiles selects them; a press there clears
      const first = (await tiles.nth(0).boundingBox())!, last = (await tiles.nth(1).boundingBox())!
      const content = (await index.locator('#people').boundingBox())!
      const start = { x: content.x + content.width - 5, y: first.y - 8 }
      await index.mouse.move(start.x, start.y)
      await index.mouse.down()
      await index.mouse.move(first.x + 10, last.y + last.height - 10, { steps: 8 })
      expect(await index.locator('.marquee').isVisible()).toBe(true)
      await index.mouse.up()
      await expect.poll(() => index.locator('#picked').textContent()).toBe('2 selected')
      expect(await index.locator('.marquee').count()).toBe(0)
      await index.mouse.click(start.x, start.y)
      await expect.poll(() => index.locator('#picked').textContent()).toBe('0 selected')

      // and a plain click still opens the person's page
      await tiles.nth(0).click()
      await index.getByRole('link', { name: '← All people' }).waitFor({ timeout: 30_000 })
    } finally {
      await browser.close()
    }
    await running.rpc('people.subcategory.delete', { id: cousins })  // (as the next test expects)
    for (let i = 0; i < 300; i++) {
      const jobs = (await running.rpc('jobs.list')).result as { status: string }[]
      if (!jobs.some(j => ['queued', 'running'].includes(j.status))) break
      await new Promise(resolve => setTimeout(resolve, 200))
    }
  }, 240_000)

  it('makes subcategories, sorts someone into one, renames and deletes it; from disk they only show', async () => {
    const idle = async () => {
      for (let i = 0; i < 300; i++) {
        const jobs = (await running.rpc('jobs.list')).result as { status: string }[]
        if (!jobs.some(j => ['queued', 'running'].includes(j.status))) return
        await new Promise(resolve => setTimeout(resolve, 200))
      }
    }
    const tree = async () => (await running.rpc('people.subcategories')).result.subcategories as { id: number; name: string; parent_id: number | null; people: number }[]
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Browse' }).click()
      const [index] = await Promise.all([page.waitForEvent('popup'), page.getByRole('button', { name: "Open the box's index page" }).click()])
      await index.setViewportSize({ width: 1280, height: 900 })
      await index.getByRole('heading', { name: 'All people' }).waitFor({ timeout: 30_000 })
      // Sara into Friends first
      await index.locator('.sidebar a[data-view="unassigned"]').click()
      await index.locator('#people .tile:visible', { hasText: 'Sara Lima' }).click()
      await index.locator('#actions').getByRole('button', { name: 'Friends' }).click()
      await index.getByText('1 person moved to Friends.').waitFor({ timeout: 30_000 })

      // folded to begin with; the chevron unfolds Friends, with a + at the bottom of its list
      const fold = index.getByRole('button', { name: 'Subcategories of Friends' })
      expect(await fold.getAttribute('aria-expanded')).toBe('false')
      expect(await index.locator('.subs[data-for="friends"]').isVisible()).toBe(false)
      await fold.click()
      expect(await fold.getAttribute('aria-expanded')).toBe('true')
      await index.getByRole('button', { name: 'Add a subcategory to Friends' }).click()
      await index.getByRole('textbox', { name: 'New subcategory of Friends' }).fill('School')
      await index.getByRole('textbox', { name: 'New subcategory of Friends' }).press('Enter')
      const school = index.locator('.sidebar a[data-sub]', { hasText: 'School' })
      await school.waitFor({ timeout: 30_000 })
      // and one under it, which cannot have its own
      await index.getByRole('button', { name: 'Subcategories of School' }).click()
      await index.getByRole('button', { name: 'Add a subcategory to School' }).click()
      await index.getByRole('textbox', { name: 'New subcategory of School' }).fill('Class of 98')
      await index.getByRole('textbox', { name: 'New subcategory of School' }).press('Enter')
      const year = index.locator('.sidebar a[data-sub]', { hasText: 'Class of 98' })
      await year.waitFor({ timeout: 30_000 })
      expect(await index.getByRole('button', { name: 'Add a subcategory to Class of 98' }).count()).toBe(0)
      await shot(index, 'subcategories')
      // a double click renames it
      await year.dblclick()
      const rename = index.getByRole('textbox', { name: 'Rename Class of 98' })
      await rename.fill("Class of '98")
      await rename.press('Enter')
      await index.locator('.sidebar a[data-sub]', { hasText: "Class of '98" }).waitFor({ timeout: 30_000 })
      expect((await tree()).map(s => s.name)).toEqual(['School', "Class of '98"])

      // Sara, dragged from Friends onto it
      await index.locator('.sidebar a[data-view="friends"]').click()
      const target = await index.locator('.sidebar a[data-sub]', { hasText: "Class of '98" }).getAttribute('data-sub')
      await index.locator('#people .tile:visible', { hasText: 'Sara Lima' }).evaluate((tile: HTMLElement, id: string) => {
        const goal = document.querySelector(`.sidebar a[data-sub="${id}"]`)!
        const data = new DataTransfer()
        tile.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: data }))
        goal.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: data }))
        goal.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: data }))
        tile.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true, dataTransfer: data }))
      }, target!)
      await index.getByText("1 person moved to Class of '98.").waitFor({ timeout: 30_000 })
      // like folders: each label holds only its own people
      const count = (view: string) => index.locator(`.sidebar a[data-view="${view}"] .n`).textContent()
      const shownNames = () => index.locator('#people .tile:visible .name').allTextContents()
      expect(await count(`sub-${target}`)).toBe('1')
      expect(await count('friends')).toBe('0')
      expect(await shownNames()).toEqual([])  // (Friends is still the view: Sara left it)
      await school.click()
      expect(await shownNames()).toEqual([])
      expect((await tree()).map(s => s.people)).toEqual([1, 1])
      // ⌘-click flattens a label: everyone beneath it, counted, and its label blue
      const friends = index.locator('.sidebar a[data-view="friends"]')
      await friends.click({ modifiers: ['Meta'] })
      await expect.poll(() => count('friends')).toBe('1')
      expect(await shownNames()).toEqual(['Sara Lima'])
      expect(await friends.evaluate((a: HTMLElement) => a.classList.contains('flat'))).toBe(true)
      expect(await index.getByRole('heading', { level: 1 }).textContent()).toBe('Friends, with its subcategories')
      const blue = await friends.evaluate((a: HTMLElement) => getComputedStyle(a).color)
      const accent = await friends.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim())
      expect(blue).toBe(await friends.evaluate((_a: HTMLElement, c: string) => { const probe = document.createElement('span'); probe.style.color = c; document.body.appendChild(probe); const v = getComputedStyle(probe).color; probe.remove(); return v }, accent))
      await shot(index, 'flattened')
      const schoolId = await school.getAttribute('data-sub')
      await school.click({ modifiers: ['Meta'] })
      await expect.poll(() => count(`sub-${schoolId}`)).toBe('1')
      expect(await shownNames()).toEqual(['Sara Lima'])
      // a plain click on a flattened label keeps it flattened; ⌘-click again nests it
      await friends.click()
      expect(await shownNames()).toEqual(['Sara Lima'])
      await friends.click({ modifiers: ['Meta'] })
      await expect.poll(() => count('friends')).toBe('0')
      expect(await shownNames()).toEqual([])
      expect(await friends.evaluate((a: HTMLElement) => a.classList.contains('flat'))).toBe(false)
      await school.click({ modifiers: ['Meta'] })  // (School back to nested for what follows)

      // deleting School asks, then takes its own with it; Sara stays in Friends
      await school.hover()
      await index.getByRole('button', { name: 'Delete School' }).click()
      const ask = index.getByRole('dialog', { name: 'Delete the subcategory School?' })
      await ask.waitFor()
      await ask.getByRole('button', { name: 'Delete' }).click()
      await index.getByText('School deleted.', { exact: false }).waitFor({ timeout: 30_000 })
      expect(await index.locator('.sidebar a[data-sub]').count()).toBe(0)
      expect(await tree()).toEqual([])
      expect(await index.getByRole('heading', { level: 1 }).textContent()).toBe('Friends')
      expect(await index.locator('#people .tile:visible .name').allTextContents()).toEqual(['Sara Lima'])
    } finally {
      await browser.close()
    }

    // From disk: the subcategories show and filter, but cannot be changed
    const made = (await running.rpc('people.subcategory.add', { category: 'friends', name: 'Climbing' })).result
    await running.rpc('people.categorize', { people: ['Sara Lima'], category: 'friends', subcategory: made.id })
    await idle()
    const offline = await playwright()!.chromium.launch()
    try {
      const disk = await offline.newPage({ viewport: { width: 1280, height: 900 } })
      await disk.goto(pathToFileURL(join(box, 'index.html')).href)
      await disk.getByRole('heading', { name: 'All people' }).waitFor()
      await disk.getByRole('button', { name: 'Subcategories of Friends' }).click()
      await disk.locator('.sidebar a[data-sub]', { hasText: 'Climbing' }).click()
      expect(await disk.locator('#people .tile:visible .name').allTextContents()).toEqual(['Sara Lima'])
      expect(await disk.getByRole('button', { name: 'Add a subcategory to Friends' }).isVisible()).toBe(false)
      expect(await disk.locator('#people .tile:visible').first().getAttribute('draggable')).not.toBe('true')
      expect(await disk.getByRole('button', { name: 'Delete Climbing' }).count()).toBe(0)
    } finally {
      await offline.close()
    }
  }, 240_000)
})
