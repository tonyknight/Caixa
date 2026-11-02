// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SettingsPage } from '../src/client/pages/SettingsPage.tsx'
import { SETTINGS, fail, ok } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const page = (onChangeBox = vi.fn(), setup?: Parameters<typeof renderWith>[1]) => renderWith(<SettingsPage onChangeBox={onChangeBox} />, setup)
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

describe('the settings form', () => {
  it('shows the box, a plain statement that nothing leaves the computer, and each group', async () => {
    await page()
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeTruthy()
    expect(screen.getByText('Location: /boxes/Our box')).toBeTruthy()
    expect(screen.getByText(/Nothing here sends your archive anywhere/)).toBeTruthy()
    for (const legend of ['Privacy', 'Translation (local model)', 'Speech-to-text (local model)']) {
      expect(screen.getByRole('group', { name: legend })).toBeTruthy()
    }
  })

  it('draws every field from the schema with its saved value', async () => {
    await page(vi.fn(), (api) => {
      api.settingsReply = ok({ ...SETTINGS, values: { ...SETTINGS.values, 'privacy.default': 'family', 'translation.enabled': true, 'translation.endpoint': 'http://localhost:11434/v1' } })
    })
    expect((screen.getByLabelText('Who can see new items') as HTMLSelectElement).value).toBe('family')
    expect(Array.from((screen.getByLabelText('Who can see new items') as HTMLSelectElement).options).map(o => o.value)).toEqual(['private', 'family', 'public'])
    expect((screen.getByLabelText('Translate with a local model') as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText('Translation endpoint') as HTMLInputElement).value).toBe('http://localhost:11434/v1')
    expect(screen.getByText('Off by default.')).toBeTruthy()
  })

  it('can do nothing until something changes, then saves only the changes', async () => {
    const view = await page()
    const save = screen.getByRole('button', { name: 'Save settings' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    change('Who can see new items', 'family')
    change('Translation endpoint', ' http://localhost:1/v1 ')
    expect(save.disabled).toBe(false)
    expect(screen.getByText('You have changes that are not saved yet.')).toBeTruthy()
    fireEvent.click(save)
    await view.flush()
    expect(view.api.savedSettings).toEqual([{ 'privacy.default': 'family', 'translation.endpoint': 'http://localhost:1/v1' }])
    expect(screen.getByRole('status').textContent).toBe('Settings saved.')
    expect(save.disabled).toBe(true)
  })

  it('sends a setting that is put back to its default', async () => {
    const view = await page(vi.fn(), (api) => { api.settingsReply = ok({ ...SETTINGS, values: { ...SETTINGS.values, 'privacy.default': 'family' } }) })
    change('Who can see new items', 'private')
    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await view.flush()
    expect(view.api.savedSettings).toEqual([{ 'privacy.default': 'private' }])
  })

  it('saves a checkbox', async () => {
    const view = await page()
    fireEvent.click(screen.getByLabelText('Translate with a local model'))
    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await view.flush()
    expect(view.api.savedSettings).toEqual([{ 'translation.enabled': true }])
  })

  it('undoes unsaved changes', async () => {
    await page()
    change('Speech language', 'pt')
    fireEvent.click(screen.getByRole('button', { name: 'Undo changes' }))
    expect((screen.getByLabelText('Speech language') as HTMLInputElement).value).toBe('')
    expect((screen.getByRole('button', { name: 'Save settings' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('lists every problem the worker found, and keeps what was typed', async () => {
    const view = await page(vi.fn(), (api) => {
      api.saveReply = () => ({ ok: false, error: { code: -32602, message: 'two problems', kind: 'invalid_params', data: { errors: ["'privacy.default' must be one of private, family, public.", "'colour' is not an option of the settings."] } } })
    })
    change('Speech language', 'pt')
    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await view.flush()
    const alert = screen.getByRole('alert')
    expect(within(alert).getByText('The settings were not saved:')).toBeTruthy()
    expect(within(alert).getAllByRole('listitem').map(li => li.textContent)).toEqual(["'privacy.default' must be one of private, family, public.", "'colour' is not an option of the settings."])
    expect((screen.getByLabelText('Speech language') as HTMLInputElement).value).toBe('pt')
  })

  it('shows any other failure in plain words', async () => {
    const view = await page(vi.fn(), (api) => { api.saveReply = () => fail('read_only', "This box is open read-only, so 'settings.set' is not allowed.") })
    change('Speech language', 'pt')
    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await view.flush()
    expect(screen.getByRole('alert').textContent).toContain('open read-only')
  })

  it('leads to choosing another box', async () => {
    const onChangeBox = vi.fn()
    await page(onChangeBox)
    fireEvent.click(screen.getByRole('button', { name: 'Open another box' }))
    expect(onChangeBox).toHaveBeenCalledOnce()
  })

  it('shows the values of a read-only box but changes nothing', async () => {
    await page(vi.fn(), (api) => { api.readOnly = true })
    expect(screen.getByText('This box is open read-only, so settings cannot be changed.')).toBeTruthy()
    expect(screen.getByRole('group', { name: 'Privacy' }).hasAttribute('disabled')).toBe(true)
    expect((screen.getByRole('button', { name: 'Save settings' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('needs a box, and reports settings it cannot read', async () => {
    await page(vi.fn(), (api) => { api.box = fail('no_box', 'x') })
    expect(screen.getByText('Open or create a box first (see the Box section).')).toBeTruthy()
    cleanup()
    await page(vi.fn(), (api) => { api.settingsReply = fail('not_found', 'no settings') })
    expect(screen.getByRole('alert').textContent).toBe('Something went wrong: no settings')
  })
})
