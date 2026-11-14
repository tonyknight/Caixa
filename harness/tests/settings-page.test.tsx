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
    for (const legend of ['Privacy', 'Contacts', 'Translation', 'Speech-to-text (local model)']) {
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

  it('browses for the speech model file and saves the path it picked', async () => {
    const view = await page()
    fireEvent.click(within(screen.getByRole('group', { name: 'Speech-to-text (local model)' })).getByRole('button', { name: 'Browse this computer' }))
    await view.flush()
    fireEvent.click(within(screen.getByText('chat.zip').parentElement!).getByRole('button', { name: 'Choose' }))
    expect((screen.getByLabelText('Speech-to-text model') as HTMLInputElement).value).toBe('/home/me/chat.zip')
    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await view.flush()
    expect(view.api.savedSettings).toEqual([{ 'speech.model': '/home/me/chat.zip' }])
  })

  it('has a place to create a report for when something does not work', async () => {
    const view = await page()
    expect(screen.getByRole('heading', { name: 'Something not working?' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Create a report' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['diagnostics', undefined, undefined])
    expect((screen.getByLabelText('Report') as HTMLTextAreaElement).value).toContain('== Caixa ==')
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

describe('translation: the key and the test', () => {
  it('saves a typed key apart from the settings, and never shows a saved one', async () => {
    const view = await page()
    expect(screen.getByText(/No key is saved for this endpoint/)).toBeTruthy()
    change('Translation endpoint', 'https://openrouter.ai/api/v1')
    const field = screen.getByLabelText('API key') as HTMLInputElement
    expect(field.type).toBe('password')
    fireEvent.change(field, { target: { value: ' sk-secret-123 ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await screen.findByText('Settings saved.')
    expect(view.api.keySaves).toEqual([['https://openrouter.ai/api/v1', 'sk-secret-123']])
    expect(view.api.savedSettings.every(values => !JSON.stringify(values).includes('sk-secret'))).toBe(true)
    expect((screen.getByLabelText('API key') as HTMLInputElement).value).toBe('')
    expect(screen.getByText(/A key is saved for this endpoint/)).toBeTruthy()
  })

  it('forgets a saved key when asked', async () => {
    const view = await page(vi.fn(), (api) => {
      api.settingsReply = ok({ ...SETTINGS, values: { ...SETTINGS.values, 'translation.endpoint': 'https://api.deepseek.com/v1' }, translation: { key_saved: true } })
    })
    fireEvent.click(screen.getByRole('button', { name: 'Forget the saved key' }))
    await screen.findByText(/No key is saved for this endpoint/)
    expect(view.api.keySaves).toEqual([['https://api.deepseek.com/v1', '']])
  })

  it('tests what is typed, saved or not, and shows the sample and what came back', async () => {
    const view = await page()
    change('Translation endpoint', 'http://localhost:11434/v1')
    change('Translation model', 'llama3.1')
    fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'sk-typed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Test' }))
    const result = await screen.findByTestId('translation-test-result')
    expect(result.textContent).toContain('It works')
    expect(result.textContent).toContain('Bom dia!')
    expect(result.textContent).toContain('Good morning!')
    expect(view.api.tests).toEqual([[{ 'translation.endpoint': 'http://localhost:11434/v1', 'translation.model': 'llama3.1' }, 'sk-typed']])
    expect(view.api.savedSettings).toEqual([])  // testing saves nothing
  })

  it('says why a test failed', async () => {
    await page(vi.fn(), (api) => { api.testReply = ok({ ok: false, message: 'The server refused the key (HTTP 401): No auth credentials found' }) })
    fireEvent.click(screen.getByRole('button', { name: 'Test' }))
    const result = await screen.findByTestId('translation-test-result')
    expect(result.getAttribute('role')).toBe('alert')
    expect(result.textContent).toContain('The test failed. The server refused the key (HTTP 401)')
  })
})

describe('contacts', () => {
  it('says how many people this Mac\u2019s Contacts can name', async () => {
    await page()
    const status = await screen.findByTestId('contacts-check')
    expect(status.textContent).toContain('This Mac\u2019s Contacts can be read: 412 people')
  })

  it('says what to do when macOS will not let them be read, and counts a contacts file', async () => {
    await page(vi.fn(), (api) => {
      api.contactsReply = ok({ mac: { on: true, people: 0, problem: 'no_access' }, file: { on: true, people: 87, problem: '' } })
    })
    const status = await screen.findByTestId('contacts-check')
    expect(status.textContent).toContain('Full Disk Access')
    expect(status.textContent).toContain('The contacts file can be read: 87 people')
    expect(status.textContent).toContain('you will not be asked again')
  })

  it('offers to browse for the contacts file and checks again after saving', async () => {
    const view = await page()
    await screen.findByTestId('contacts-check')
    change('Contacts file (.vcf)', '/home/maria/contacts.vcf')
    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
    await screen.findByText('Settings saved.')
    expect(view.api.savedSettings).toEqual([{ 'contacts.file': '/home/maria/contacts.vcf' }])
    expect(view.api.calls.filter(call => call[0] === 'checkContacts').length).toBe(2)
  })
})
