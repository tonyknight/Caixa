// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BoxPage } from '../src/client/pages/BoxPage.tsx'
import { fail, ok, BOX } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const RECENT = [
  { path: '/boxes/Our box', name: 'Our box', opened: '2024-05-01T10:00:00+00:00', exists: true },
  { path: '/boxes/Gone', name: 'Old box', opened: '2024-04-01T10:00:00+00:00', exists: false },
]

describe('the boxes opened lately', () => {
  const withRecent = (api: any) => { api.box = fail('no_box', 'You need to open a box first'); api.sessionReply = ok({ recent: RECENT, last_box: '/boxes/Our box', box: null, view: null, draft: null }) }

  it('are listed, so the last one is one click away', async () => {
    await renderWith(<BoxPage onImport={() => undefined} />, withRecent)
    const list = screen.getByRole('list', { name: 'Boxes you opened lately' })
    expect(within(list).getAllByRole('listitem').map(item => item.textContent)).toEqual([
      expect.stringContaining('Our box'),
      expect.stringContaining('Old box'),
    ])
  })

  it('open from the list', async () => {
    const view = await renderWith(<BoxPage onImport={() => undefined} />, withRecent)
    view.api.box = ok(BOX)
    fireEvent.click(screen.getByRole('button', { name: 'Open Our box' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['boxOpen', '/boxes/Our box'])
    expect(screen.getByRole('heading', { name: 'Our box' })).toBeTruthy()
  })

  it('say when a folder has gone, and can be taken off the list', async () => {
    const view = await renderWith(<BoxPage onImport={() => undefined} />, withRecent)
    expect(screen.queryByRole('button', { name: 'Open Old box' })).toBeNull()
    expect(screen.getByText('Not found: the folder has moved or been deleted.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Remove Old box from this list' }))
    await view.flush()
    expect(view.api.forgotten).toEqual(['/boxes/Gone'])
    expect(screen.queryByText('Old box')).toBeNull()
  })

  it('are not shown when there are none', async () => {
    await renderWith(<BoxPage onImport={() => undefined} />, ((api: any) => { api.box = fail('no_box', 'x') }) as never)
    expect(screen.queryByRole('list', { name: 'Boxes you opened lately' })).toBeNull()
  })

  it('are offered again when choosing another box', async () => {
    await renderWith(<BoxPage onImport={() => undefined} />, (api) => { api.sessionReply = ok({ recent: RECENT, last_box: null, box: '/boxes/Our box', view: null, draft: null }) })
    fireEvent.click(screen.getByRole('button', { name: 'Open another box' }))
    expect(screen.getByRole('list', { name: 'Boxes you opened lately' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Open Our box' })).toBeNull() // that one is open already
  })
})

describe('with no box open', () => {
  const noBox = (api: { box: unknown }) => { api.box = fail('no_box', 'You need to open a box first') }

  it('offers to create one or open one', async () => {
    await renderWith(<BoxPage onImport={() => undefined} />, noBox as never)
    expect(screen.getByRole('heading', { name: 'Create or open a box' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Create a new box' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Open an existing box' })).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Create box' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('creates a box from the trimmed form and shows it', async () => {
    const view = await renderWith(<BoxPage onImport={() => undefined} />, noBox as never)
    const [folder, name, owner] = screen.getAllByRole('textbox') as HTMLInputElement[]
    fireEvent.change(folder!, { target: { value: '  /boxes/Our box ' } })
    fireEvent.change(name!, { target: { value: ' Our box ' } })
    fireEvent.change(owner!, { target: { value: 'Maria Costa' } })
    view.api.box = { ok: true, result: BOX }
    fireEvent.click(screen.getByRole('button', { name: 'Create box' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['boxCreate', '/boxes/Our box', 'Our box', 'Maria Costa'])
    expect(screen.getByRole('heading', { name: 'Our box' })).toBeTruthy()
  })

  it('shows the worker\'s plain error and keeps the form', async () => {
    const view = await renderWith(<BoxPage onImport={() => undefined} />, noBox as never)
    const [folder] = screen.getAllByRole('textbox') as HTMLInputElement[]
    fireEvent.change(folder!, { target: { value: '/boxes/Taken' } })
    view.api.box = fail('conflict', '/boxes/Taken is already a Caixa box.')
    fireEvent.click(screen.getByRole('button', { name: 'Create box' }))
    await view.flush()
    expect(screen.getByRole('alert').textContent).toBe('/boxes/Taken is already a Caixa box.')
    expect((screen.getAllByRole('textbox')[0] as HTMLInputElement).value).toBe('/boxes/Taken')
  })

  it('opens an existing box', async () => {
    const view = await renderWith(<BoxPage onImport={() => undefined} />, noBox as never)
    const inputs = screen.getAllByRole('textbox') as HTMLInputElement[]
    fireEvent.change(inputs[3]!, { target: { value: '/boxes/Our box' } })
    view.api.box = { ok: true, result: BOX }
    fireEvent.click(screen.getByRole('button', { name: 'Open box' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['boxOpen', '/boxes/Our box'])
  })

  it('lets the folder be picked from this computer', async () => {
    const view = await renderWith(<BoxPage onImport={() => undefined} />, noBox as never)
    fireEvent.click(screen.getAllByRole('button', { name: 'Browse this computer' })[0]!)
    await view.flush()
    expect(screen.getByText('/home/me')).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button', { name: 'Choose this folder' })[0]!)
    expect((screen.getAllByRole('textbox')[0] as HTMLInputElement).value).toBe('/home/me/Exports')
  })
})

describe('with a box open', () => {
  it('shows what is in it', async () => {
    await renderWith(<BoxPage onImport={() => undefined} />)
    expect(screen.getByRole('heading', { name: 'Our box' })).toBeTruthy()
    expect(screen.getByText('Location: /boxes/Our box')).toBeTruthy()
    expect(screen.getByText('Owner: Maria Costa')).toBeTruthy()
    expect(screen.getByText('Messages: 9')).toBeTruthy()
    expect(screen.getByText('Mail: 3')).toBeTruthy()
    const recent = screen.getByRole('table')
    expect(within(recent).getByText('chattr')).toBeTruthy()
    expect(within(recent).getByText('12 new, 0 changed, 0 unchanged')).toBeTruthy()
  })

  it('says what is missing in an empty box', async () => {
    await renderWith(<BoxPage onImport={() => undefined} />, (api) => {
      api.box = { ok: true, result: { ...BOX, items: 0, by_type: {}, imports: [], owner: null } }
    })
    expect(screen.getByText('The box is empty. Import an export to fill it.')).toBeTruthy()
    expect(screen.getByText('Nothing has been imported yet.')).toBeTruthy()
    expect(screen.getByText('No owner is set yet.')).toBeTruthy()
  })

  it('goes to the import wizard, or to another box', async () => {
    const onImport = vi.fn()
    await renderWith(<BoxPage onImport={onImport} />)
    fireEvent.click(screen.getByRole('button', { name: 'Import data' }))
    expect(onImport).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: 'Open another box' }))
    expect(screen.getByRole('heading', { name: 'Open an existing box' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByRole('heading', { name: 'Our box' })).toBeTruthy()
  })

  it('shows an unknown kind of item by its own name', async () => {
    await renderWith(<BoxPage onImport={() => undefined} />, (api) => {
      api.box = { ok: true, result: { ...BOX, by_type: { sticker: 2 } } }
    })
    expect(screen.getByText('sticker: 2')).toBeTruthy()
  })
})
