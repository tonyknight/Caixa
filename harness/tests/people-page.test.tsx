// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { PeoplePage } from '../src/client/pages/PeoplePage.tsx'
import { HANDLES, PEOPLE, fail, job, ok } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const page = () => renderWith(<PeoplePage />)
const refreshJob = (status: string, extra = {}) => job({ id: 9, kind: 'refresh', collector: null, source: null, status: status as never, stage: null, result: null, ...extra })

describe('the queue of unnamed handles', () => {
  it('lists each handle busiest first, with its source, name and message count', async () => {
    await page()
    expect(screen.getByRole('heading', { name: 'Not yet named (2)' })).toBeTruthy()
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]!).getByText('WhatsApp')).toBeTruthy()
    expect(within(rows[0]!).getByText('Ana Costa')).toBeTruthy()
    expect(within(rows[0]!).getByText('7')).toBeTruthy()
    expect(within(rows[1]!).getByText('+1 555 0102')).toBeTruthy()
    expect(within(rows[1]!).getByText('Unknown')).toBeTruthy()
  })

  it('says when everyone is named', async () => {
    await renderWith(<PeoplePage />, (api) => { api.handleList = [] })
    expect(screen.getByText('Everyone is named.')).toBeTruthy()
  })

  it('needs a box', async () => {
    const { fail: failure } = await import('./fake-api.ts')
    await renderWith(<PeoplePage />, (api) => { api.box = failure('no_box', 'x') })
    expect(screen.getByText('Open or create a box first (see the Box section).')).toBeTruthy()
  })
})

describe('naming a handle', () => {
  it('links it to a new person by the name typed, then shows the pages being redrawn and done', async () => {
    const view = await page()
    fireEvent.change(screen.getByLabelText('Name for Ana Costa'), { target: { value: '  Ana (daughter) ' } })
    fireEvent.click(within(screen.getAllByRole('row')[1]!).getByRole('button', { name: 'Link' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['link', 'WhatsApp', 'Ana Costa', 'Ana (daughter)', false])
    expect(screen.getByRole('status').textContent).toContain('Linked “Ana Costa” to Ana A.')
    expect(screen.getByRole('status').textContent).toContain('Redrawing the pages…')
    view.api.jobList = [refreshJob('running')]
    await view.store.refreshJobs()
    await view.emit('job.finished', { ...refreshJob('done'), job: 9 })
    expect(screen.getByRole('status').textContent).toContain('The pages are up to date.')
  })

  it('links to an existing person by id when the name is theirs, whatever the case', async () => {
    const view = await page()
    fireEvent.change(screen.getByLabelText('Name for +1 555 0102'), { target: { value: 'rui pereira' } })
    fireEvent.click(within(screen.getAllByRole('row')[2]!).getByRole('button', { name: 'Link' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['link', 'iMessage', '+1 555 0102', 2, false])
  })

  it('offers the people already in the box while typing', async () => {
    await page()
    const list = document.getElementById(screen.getByLabelText('Name for Ana Costa').getAttribute('list')!)!
    expect(Array.from(list.querySelectorAll('option')).map(option => option.getAttribute('value'))).toEqual(['Maria Costa', 'Rui Pereira', 'Ana A'])
  })

  it('does not link a blank name', async () => {
    await page()
    expect((within(screen.getAllByRole('row')[1]!).getByRole('button', { name: 'Link' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('explains a handle that already names someone else, and can move it', async () => {
    const view = await page()
    view.api.changeReply = (kind, args) => (args[3] === true
      ? ok({ person: PEOPLE[2]!, job: null })
      : fail('conflict', "'Ana Costa' already names Rui Pereira. Use move to give it to this person."))
    fireEvent.change(screen.getByLabelText('Name for Ana Costa'), { target: { value: 'Ana A' } })
    fireEvent.click(within(screen.getAllByRole('row')[1]!).getByRole('button', { name: 'Link' }))
    await view.flush()
    expect(screen.getByRole('alert').textContent).toBe("'Ana Costa' already names Rui Pereira.")
    fireEvent.click(screen.getByRole('button', { name: 'Give it to Ana A instead' }))
    await view.flush()
    expect(view.api.calls.filter(call => call[0] === 'link').map(call => call[4])).toEqual([false, true])
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows any other refusal in the worker\'s own words', async () => {
    const view = await page()
    view.api.changeReply = () => fail('read_only', "This box is open read-only, so 'people.link' is not allowed.")
    fireEvent.change(screen.getByLabelText('Name for Ana Costa'), { target: { value: 'Ana' } })
    fireEvent.click(within(screen.getAllByRole('row')[1]!).getByRole('button', { name: 'Link' }))
    await view.flush()
    expect(screen.getByRole('alert').textContent).toContain('open read-only')
  })

  it('reports pages that could not be redrawn', async () => {
    const view = await page()
    fireEvent.change(screen.getByLabelText('Name for Ana Costa'), { target: { value: 'Ana' } })
    fireEvent.click(within(screen.getAllByRole('row')[1]!).getByRole('button', { name: 'Link' }))
    await view.flush()
    await view.emit('job.finished', { ...refreshJob('failed', { error: 'disk full' }), job: 9 })
    expect(screen.getByRole('status').textContent).toContain('The pages could not be redrawn: disk full')
  })

  it('reads the queue and the people again afterwards', async () => {
    const view = await page()
    const before = view.api.calls.filter(call => call[0] === 'unresolved').length
    fireEvent.change(screen.getByLabelText('Name for Ana Costa'), { target: { value: 'Ana' } })
    fireEvent.click(within(screen.getAllByRole('row')[1]!).getByRole('button', { name: 'Link' }))
    view.api.handleList = [HANDLES[1]!]
    await view.flush()
    expect(view.api.calls.filter(call => call[0] === 'unresolved').length).toBeGreaterThan(before)
    expect(screen.getByRole('heading', { name: 'Not yet named (1)' })).toBeTruthy()
  })
})

describe('the people', () => {
  it('lists each with their items and names, and marks the owner', async () => {
    await page()
    expect(screen.getByRole('heading', { name: 'People (3)' })).toBeTruthy()
    const owner = screen.getByText('Maria Costa').closest('div')!
    expect(within(owner).getByText('owner')).toBeTruthy()
    expect(owner.textContent).toContain('9 items · 2 names')
  })

  it('renames in place, and leaves it alone on cancel', async () => {
    const view = await page()
    fireEvent.click(screen.getByRole('button', { name: 'Rename Rui Pereira' }))
    const field = screen.getByLabelText('New name for Rui Pereira') as HTMLInputElement
    expect(field.value).toBe('Rui Pereira')
    expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true) // unchanged
    fireEvent.change(field, { target: { value: ' Rui P. ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['rename', 2, 'Rui P.'])
    expect(screen.getByRole('status').textContent).toContain('Renamed to Ana A.') // the worker's reply names the person
    fireEvent.click(screen.getByRole('button', { name: 'Rename Ana A' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByLabelText('New name for Ana A')).toBeNull()
  })

  it('shows a name already in use, with the way out the worker gives', async () => {
    const view = await page()
    view.api.changeReply = () => fail('conflict', "Someone named 'Ana A' is already in the box; merge the two people instead.")
    fireEvent.click(screen.getByRole('button', { name: 'Rename Rui Pereira' }))
    fireEvent.change(screen.getByLabelText('New name for Rui Pereira'), { target: { value: 'Ana A' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await view.flush()
    expect(screen.getByRole('alert').textContent).toContain('merge the two people instead')
    expect(screen.getByLabelText('New name for Rui Pereira')).toBeTruthy() // still editing
  })

  it('merges only after being told exactly what will happen and agreeing', async () => {
    const view = await page()
    fireEvent.click(screen.getByRole('button', { name: 'Merge… Rui Pereira' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    fireEvent.change(screen.getByLabelText('Merge Rui Pereira into'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Merge…' }))
    const confirm = screen.getByRole('alertdialog')
    expect(confirm.textContent).toContain('Merge Rui Pereira into Ana A? Rui Pereira will disappear')
    expect(view.api.calls.some(call => call[0] === 'merge')).toBe(false)
    fireEvent.click(within(confirm).getByRole('button', { name: 'Merge' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['merge', 2, 3])
    expect(screen.getByRole('status').textContent).toContain('Merged into Ana A.')
  })

  it('does not offer the owner to be merged away, nor a lone person anything to merge into', async () => {
    await page()
    expect(screen.queryByRole('button', { name: 'Merge… Maria Costa' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Rename Maria Costa' })).toBeTruthy() // the owner can be renamed
    cleanup()
    await renderWith(<PeoplePage />, (api) => { api.peopleList = [PEOPLE[1]!] })
    expect(screen.queryByRole('button', { name: /Merge…/ })).toBeNull()
  })

  it('says when the box has nobody yet', async () => {
    await renderWith(<PeoplePage />, (api) => { api.peopleList = []; api.handleList = [] })
    expect(screen.getByText('There is nobody in the box yet.')).toBeTruthy()
  })
})

describe('a read-only box', () => {
  it('shows who is there but changes nothing', async () => {
    await renderWith(<PeoplePage />, (api) => { api.readOnly = true })
    expect(screen.getByText('This box is open read-only, so names cannot be changed.')).toBeTruthy()
    expect((screen.getByLabelText('Name for Ana Costa') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Rename Rui Pereira' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Merge… Rui Pereira' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
