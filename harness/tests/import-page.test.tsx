// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ImportPage } from '../src/client/pages/ImportPage.tsx'
import { BOX, fail, job, ok } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const wizard = (onShowJob = vi.fn(), onShowPeople = vi.fn()) => renderWith(<ImportPage onShowJob={onShowJob} onShowPeople={onShowPeople} />)
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))
const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })
const currentStep = () => screen.getByRole('list', { name: 'Steps' }).querySelector('[aria-current="step"]')!.textContent

/** Walk the wizard to the preview of the WhatsApp chat. */
async function toPreview(view: Awaited<ReturnType<typeof wizard>>, path = '/exports/chat.txt') {
  click(/WhatsApp/)
  click('I have the export')
  type(/Path to the export/, path)
  click('Continue')
  click('Preview')
  await view.flush()
}

const VOICEMAIL = {
  id: 'voicemail', name: 'iPhone voicemail', platform: 'iPhone', inputs: ['folder', 'zip'], source: 'chattr',
  how_to_export: 'Point Caixa at a folder or a .zip of voicemail.',
  options_schema: { type: 'object', properties: {
    transcribe: { type: 'boolean', default: false, title: 'Transcribe on this computer' },
    model: { type: 'string', default: '/models/saved.bin', title: 'Speech model', 'x-setting': 'speech.model', 'x-picker': 'file' },
    language: { type: 'string', default: 'pt', title: 'Language', 'x-setting': 'speech.language' },
  } },
} as const

describe('the speech model on the options step', () => {
  const toOptions = async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.collectorList = [VOICEMAIL as never] })
    click(/iPhone voicemail/)
    click('I have the export')
    type(/Path to the export/, '/exports/iPhone Voicemail.zip')
    click('Continue')
    return view
  }

  it('starts from what Settings says', async () => {
    await toOptions()
    expect((screen.getByLabelText('Speech model') as HTMLInputElement).value).toBe('/models/saved.bin')
    expect((screen.getByLabelText('Language') as HTMLInputElement).value).toBe('pt')
    expect((screen.getByLabelText('Transcribe on this computer') as HTMLInputElement).checked).toBe(false)
  })

  it('browses for the model file and puts its path in the field', async () => {
    const view = await toOptions()
    click('Browse this computer')
    await view.flush()
    fireEvent.click(within(screen.getByText('chat.zip').parentElement!).getByRole('button', { name: 'Choose' }))
    expect((screen.getByLabelText('Speech model') as HTMLInputElement).value).toBe('/home/me/chat.zip')
    expect(screen.queryByText('Up one level')).toBeNull() // the picker closed
  })

  it('sends only what was changed: ticking transcribe leaves the saved model to the worker', async () => {
    const view = await toOptions()
    fireEvent.click(screen.getByLabelText('Transcribe on this computer'))
    click('Preview')
    await view.flush()
    expect(view.api.calls).toContainEqual(['preview', 'voicemail', '/exports/iPhone Voicemail.zip', { transcribe: true }])
  })
})

describe('an import that was not finished', () => {
  const DRAFT = { collector: 'voicemail', step: 'options', source: '/exports/iPhone Voicemail.zip', values: { transcribe: true, model: '/models/chosen.bin', language: 'en' } }
  const remembered = (draft: unknown) => (api: any) => {
    api.collectorList = [VOICEMAIL as never]
    api.sessionReply = ok({ recent: [], last_box: null, box: '/boxes/Our box', view: 'import', draft })
  }

  it('is put back where it was, with what was typed and chosen', async () => {
    await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, remembered(DRAFT))
    expect(currentStep()).toBe('Options')
    expect((screen.getByLabelText('Speech model') as HTMLInputElement).value).toBe('/models/chosen.bin')
    expect((screen.getByLabelText('Transcribe on this computer') as HTMLInputElement).checked).toBe(true)
    click('Back')
    expect((screen.getByLabelText(/Path to the export/) as HTMLInputElement).value).toBe('/exports/iPhone Voicemail.zip')
  })

  it('says it was put back, and can be thrown away with Start over', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, remembered(DRAFT))
    expect(screen.getByRole('status').textContent).toContain('Picked up where you left off')
    click('Start over')
    expect(currentStep()).toBe('Source')
    expect(screen.queryByText(/Picked up where you left off/)).toBeNull()
    expect(view.store.getState().draft).toBeNull()
  })

  it('says nothing about it when there was nothing to put back', async () => {
    await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.collectorList = [VOICEMAIL as never] })
    expect(screen.queryByText(/Picked up where you left off/)).toBeNull()
  })

  it('is ignored when its source is no longer there to choose', async () => {
    await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, remembered({ ...DRAFT, collector: 'gone' }))
    expect(currentStep()).toBe('Source')
  })

  it('is kept as each step is taken', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.collectorList = [VOICEMAIL as never] })
    expect(view.store.getState().draft).toBeNull()
    click(/iPhone voicemail/)
    click('I have the export')
    type(/Path to the export/, '/exports/iPhone Voicemail.zip')
    click('Continue')
    expect(view.store.getState().draft).toMatchObject({ collector: 'voicemail', step: 'options', source: '/exports/iPhone Voicemail.zip' })
    fireEvent.click(screen.getByLabelText('Transcribe on this computer'))
    expect(view.store.getState().draft?.values).toMatchObject({ transcribe: true })
  })

  it('is let go of when the import starts', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, remembered(DRAFT))
    expect(view.store.getState().draft).not.toBeNull()
    click('Preview')
    await view.flush()
    click('Import')
    await view.flush()
    expect(view.store.getState().draft).toBeNull()
  })

  it('is let go of when you go back to the start', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, remembered(DRAFT))
    click('Back'); click('Back'); click('Back')
    expect(currentStep()).toBe('Source')
    expect(view.store.getState().draft).toBeNull()
  })

  it('survives a trip to another section and back', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.collectorList = [VOICEMAIL as never] })
    click(/iPhone voicemail/)
    click('I have the export')
    type(/Path to the export/, '/exports/iPhone Voicemail.zip')
    view.unmount()
    const back = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.collectorList = [VOICEMAIL as never]; api.sessionReply = ok({ recent: [], last_box: null, box: '/boxes/Our box', view: 'import', draft: view.store.getState().draft }) })
    expect(currentStep()).toBe('Choose') // the step it was left at, with the path already typed
    expect((screen.getByLabelText(/Path to the export/) as HTMLInputElement).value).toBe('/exports/iPhone Voicemail.zip')
    expect(back.store.getState().draft?.collector).toBe('voicemail')
  })
})

describe('when an export cannot be imported', () => {
  const refusal = (api: any) => {
    api.previewReply = { ok: false, error: { code: -32000, kind: 'input', message: 'Nothing to import was found in /exports/chat.zip.\nWhat Caixa saw: a zip with 4 files.\nLooking for: a WhatsApp export.', data: { details: ['What Caixa saw: a zip with 4 files.', 'Looking for: a WhatsApp export.'] } } }
  }

  it('says what was found and what was wanted, one line each', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, refusal)
    await toPreview(view)
    const alert = screen.getByRole('alert')
    expect(within(alert).getByText('This export cannot be imported')).toBeTruthy()
    expect(within(alert).getByText('Nothing to import was found in /exports/chat.zip.')).toBeTruthy()
    expect(within(alert).getAllByRole('listitem').map(item => item.textContent)).toEqual(['What Caixa saw: a zip with 4 files.', 'Looking for: a WhatsApp export.'])
  })

  it('offers a report about this source, to copy', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, refusal)
    await toPreview(view)
    fireEvent.click(screen.getByRole('button', { name: 'Create a report' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['diagnostics', 'whatsapp', '/exports/chat.txt'])
    expect((screen.getByLabelText('Report') as HTMLTextAreaElement).value).toContain('Caixa diagnostic report')
    expect(screen.getByRole('button', { name: 'Copy the report' })).toBeTruthy()
  })

  it('still shows a plain message when there are no details', async () => {
    const view = await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.previewReply = fail('input', 'Not found: /exports/chat.txt') })
    await toPreview(view)
    expect(within(screen.getByRole('alert')).getByText('Not found: /exports/chat.txt')).toBeTruthy()
    expect(within(screen.getByRole('alert')).queryAllByRole('listitem')).toEqual([])
  })
})

describe('while a preview is being counted', () => {
  const counting = async () => {
    const view = await wizard()
    view.api.holdPreview = true
    click(/WhatsApp/)
    click('I have the export')
    type(/Path to the export/, '/exports/messages')
    click('Continue')
    click('Preview')
    await view.flush()
    return view
  }

  it('shows the stages, how many of how many, and what is being read', async () => {
    const view = await counting()
    const token = view.api.previewTokens.at(-1)!
    expect(token).toBeTruthy()
    await view.emit('preview.progress', { token, stage: 'importing', current: 320, total: 4812, message: 'friend_1042' })
    const status = screen.getByRole('status')
    expect(within(status).getByText('320 of 4,812', { exact: false })).toBeTruthy()
    expect(within(status).getByText('friend_1042')).toBeTruthy()
    const stages = within(status).getByRole('list', { name: 'Steps of the import' })
    expect(Array.from(stages.querySelectorAll('li')).map(li => li.textContent)).toEqual(['Reading the export', 'Importing', 'Matching people'])
    expect(stages.querySelector('[aria-current="step"]')!.textContent).toBe('Importing')
    expect((status.querySelector('progress') as HTMLProgressElement).value).toBe(320)
    expect(within(status).getByText(/So far: \d+ s/)).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Import' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('ignores the progress of some other preview', async () => {
    const view = await counting()
    await view.emit('preview.progress', { token: 'someone-else', stage: 'importing', current: 9, total: 10, message: 'x' })
    expect(screen.queryByText('9 of 10', { exact: false })).toBeNull()
  })

  it('can be stopped: going back tells the worker to stop counting', async () => {
    const view = await counting()
    const token = view.api.previewTokens.at(-1)!
    click('Stop and go back')
    await view.flush()
    expect(view.api.cancelledPreviews).toEqual([token])
    expect(currentStep()).toBe('Options')
  })

  it('shows the result when it arrives, and stops nothing', async () => {
    const view = await counting()
    view.api.releasePreview()
    await view.flush()
    expect(screen.getByText('7 items in 1 conversations')).toBeTruthy()
    expect(view.api.cancelledPreviews).toEqual([])
    expect(screen.getByRole('button', { name: 'Back' })).toBeTruthy()
  })
})

describe('while an import runs', () => {
  it('shows every stage, the count and the time so far', async () => {
    const view = await wizard()
    await toPreview(view)
    click('Import')
    await view.flush()
    view.api.jobList = [job({ id: 5, status: 'running', stage: 'preparing', result: null, finished_at: null })]
    await view.store.refreshJobs()
    await view.emit('job.progress', { job: 5, stage: 'filing', current: 40, total: 200, message: 'photos' })
    const status = screen.getByRole('status')
    const stages = within(status).getByRole('list', { name: 'Steps of the import' })
    expect(Array.from(stages.querySelectorAll('li')).map(li => li.textContent)).toEqual(
      ['Reading the export', 'Importing', 'Matching people', 'Filing photos, audio and other files', 'Writing the pages', 'Updating the box'])
    expect(stages.querySelector('[aria-current="step"]')!.textContent).toBe('Filing photos, audio and other files')
    expect(within(status).getByText('40 of 200', { exact: false })).toBeTruthy()
    expect(within(status).getByText(/So far:/)).toBeTruthy()
  })
})

describe('before a box is open', () => {
  it('says to open one first', async () => {
    await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.box = fail('no_box', 'x') })
    expect(screen.getByText('Open or create a box first (see the Box section).')).toBeTruthy()
  })
})

describe('a read-only box', () => {
  it('cannot import, and says so', async () => {
    await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.readOnly = true })
    expect(screen.getByText('This box is open read-only, so nothing can be imported.')).toBeTruthy()
    expect(screen.queryByText('Where do your messages come from?')).toBeNull()
  })
})

describe('step 1: the source', () => {
  it('lists every collector with what it takes', async () => {
    await wizard()
    expect(currentStep()).toBe('Source')
    expect(screen.getByText('Where do your messages come from?')).toBeTruthy()
    const whatsapp = screen.getByRole('button', { name: /WhatsApp/ })
    expect(whatsapp.textContent).toContain('Takes a file, a folder, a .zip')
    expect(screen.getByRole('button', { name: /iMessage/ }).textContent).toContain('a database file')
  })

  it('says when nothing is installed', async () => {
    await renderWith(<ImportPage onShowJob={() => undefined} onShowPeople={() => undefined} />, (api) => { api.collectorList = [] })
    expect(screen.getByText('No sources are installed.')).toBeTruthy()
  })
})

describe('step 2: how to export', () => {
  it('shows the collector\'s own instructions, and goes back', async () => {
    await wizard()
    click(/WhatsApp/)
    expect(currentStep()).toBe('Export')
    expect(screen.getByRole('heading', { name: 'How to export from WhatsApp' })).toBeTruthy()
    expect(screen.getByText('In WhatsApp, open a chat, then Export chat.')).toBeTruthy()
    click('Back')
    expect(currentStep()).toBe('Source')
  })
})

describe('step 3: choosing the export', () => {
  it('needs a path before it goes on', async () => {
    await wizard()
    click(/WhatsApp/)
    click('I have the export')
    expect(currentStep()).toBe('Choose')
    expect((screen.getByRole('button', { name: 'Continue' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('Choose an export, or type its path.')).toBeTruthy()
    type(/Path to the export/, '/exports/chat.txt')
    expect(screen.getByText('Chosen: /exports/chat.txt')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Continue' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('browses the computer: into a folder, up again, and picks a file', async () => {
    const view = await wizard()
    click(/WhatsApp/)
    click('I have the export')
    click('Browse this computer')
    await view.flush()
    expect(screen.getByText('/home/me')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Exports/' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['files', '/home/me/Exports', undefined])
    fireEvent.click(screen.getByRole('button', { name: 'Up one level' }))
    await view.flush()
    fireEvent.click(within(screen.getByText('chat.zip').parentElement!).getByRole('button', { name: 'Choose' }))
    expect((screen.getByLabelText(/Path to the export/) as HTMLInputElement).value).toBe('/home/me/chat.zip')
    expect(screen.queryByText('Up one level')).toBeNull() // the picker closed
  })

  it('explains a folder it may not show', async () => {
    const view = await wizard()
    click(/WhatsApp/)
    click('I have the export')
    view.api.filesReply = () => fail('outside_roots', '/etc is outside the folders Caixa may show.')
    click('Browse this computer')
    await view.flush()
    expect(screen.getByRole('alert').textContent).toBe('Something went wrong: /etc is outside the folders Caixa may show.')
  })

  it('lists the inbox, says when it is empty, and picks from it', async () => {
    const view = await wizard()
    click(/WhatsApp/)
    click('I have the export')
    await view.flush()
    expect(screen.getByText('The Inbox is empty. Drop an export into /boxes/Our box/Inbox and it will appear here.')).toBeTruthy()
    view.api.inboxReply = ok({ path: '/boxes/Our box/Inbox', entries: [
      { name: 'chat.zip', path: 'chat.zip', kind: 'file', size: 10, modified: '2024-01-01T00:00:00+00:00', absolute: '/boxes/Our box/Inbox/chat.zip' },
    ] })
    await view.emit('inbox.changed', { entries: [] }) // the worker noticed a new file: the list reloads
    fireEvent.click(within(screen.getByText('chat.zip').parentElement!).getByRole('button', { name: 'Choose' }))
    expect((screen.getByLabelText(/Path to the export/) as HTMLInputElement).value).toBe('/boxes/Our box/Inbox/chat.zip')
  })
})

describe('step 4: options', () => {
  it('draws the form from the schema, with its titles and help', async () => {
    const view = await wizard()
    click(/WhatsApp/)
    click('I have the export')
    type(/Path to the export/, '/x')
    click('Continue')
    expect(currentStep()).toBe('Options')
    expect(screen.getByLabelText('Contacts file (.vcf)')).toBeTruthy()
    expect(screen.getByText('A vCard export.')).toBeTruthy()
    expect(screen.getByLabelText('Your name')).toBeTruthy()
    await view.flush()
  })

  it('draws selects, whole numbers and checkboxes from other schemas', async () => {
    await wizard()
    click(/iMessage/)
    click('I have the export')
    type(/Path to the export/, '/chat.db')
    click('Continue')
    const select = screen.getByLabelText('Spam filtering') as HTMLSelectElement
    expect(Array.from(select.options).map(o => o.value)).toEqual(['aggressive', 'conservative', 'disabled'])
    expect(select.value).toBe('aggressive')
    const workers = screen.getByLabelText('Workers') as HTMLInputElement
    expect(workers).toMatchObject({ type: 'number', value: '4', min: '1', max: '8' })
    expect((screen.getByLabelText('Transcribe') as HTMLInputElement).type).toBe('checkbox')
  })

  it('shows what is wrong beside the field and does not go on', async () => {
    await wizard()
    click(/iMessage/)
    click('I have the export')
    type(/Path to the export/, '/chat.db')
    click('Continue')
    type('Workers', '0')
    click('Preview')
    expect(screen.getByRole('alert').textContent).toBe('Workers must be at least 1.')
    expect(currentStep()).toBe('Options')
    type('Workers', '2')
    click('Preview')
    expect(currentStep()).toBe('Preview')
  })
})

describe('step 5: the preview', () => {
  it('asks the worker for a dry run with only the options that were changed', async () => {
    const view = await wizard()
    click(/WhatsApp/)
    click('I have the export')
    type(/Path to the export/, '/exports/chat.txt')
    click('Continue')
    type('Your name', 'Maria Costa')
    click('Preview')
    expect(screen.getByText(/Looking at the export…/)).toBeTruthy()
    await view.flush()
    expect(view.api.calls).toContainEqual(['preview', 'whatsapp', '/exports/chat.txt', { owner: 'Maria Costa' }])
    expect(screen.getByText('7 items in 1 conversations')).toBeTruthy()
    expect(screen.getByText('From 2024-03-01 to 2024-03-05')).toBeTruthy()
    expect(screen.getAllByText('Ana Costa')).toHaveLength(2) // as a person, and as not yet named
    expect(screen.getByRole('heading', { name: 'Not yet named (1)' })).toBeTruthy()
  })

  it('explains a source that cannot be imported, in the worker\'s words', async () => {
    const view = await wizard()
    view.api.previewReply = fail('input', 'Not found: /exports/chat.txt')
    await toPreview(view)
    expect(screen.getByRole('alert').textContent).toContain('This export cannot be imported')
    expect(screen.getByRole('alert').textContent).toContain('Not found: /exports/chat.txt')
    expect((screen.getByRole('button', { name: 'Import' }) as HTMLButtonElement).disabled).toBe(true)
    click('Back')
    expect(currentStep()).toBe('Options')
  })

  it('does not offer to import an export with nothing in it', async () => {
    const view = await wizard()
    view.api.previewReply = ok({ items: 0, conversations: 0, first: null, last: null, participants: [], unresolved: [], warnings: ['It was empty'] })
    await toPreview(view)
    expect(screen.getByText('Nothing was found to import in this export.')).toBeTruthy()
    expect(screen.getByText('It was empty')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Import' }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('step 6: running and the report', () => {
  it('starts the import with the same options, follows its progress and reports the result', async () => {
    const view = await wizard()
    await toPreview(view)
    click('Import')
    await view.flush()
    expect(view.api.calls).toContainEqual(['startImport', 'whatsapp', '/exports/chat.txt', {}])
    expect(currentStep()).toBe('Import')
    expect(screen.getByText('Waiting for the earlier import to finish…')).toBeTruthy()

    view.api.jobList = [job({ id: 5, status: 'running', stage: 'preparing', result: null })]
    await view.store.refreshJobs()
    await view.emit('job.progress', { job: 5, stage: 'importing', current: 1, total: 4, message: 'chat.txt' })
    expect(screen.getByText('Importing from WhatsApp…')).toBeTruthy()
    expect(screen.getByText('1 of 4', { exact: false })).toBeTruthy()
    expect(screen.getByText('chat.txt')).toBeTruthy()
    const bar = screen.getByRole('status').querySelector('progress')!
    expect(bar).toMatchObject({ max: 4, value: 1 })

    await view.emit('job.finished', { ...job({ id: 5, result: { inserted: 7, updated: 1, unchanged: 2, pages: 3, unresolved: ['Ana Costa'], warnings: ['One photo was missing'] } }), job: 5 })
    expect(screen.getByRole('heading', { name: 'Import finished' })).toBeTruthy()
    expect(screen.getByText('7 new, 1 changed, 2 unchanged')).toBeTruthy()
    expect(screen.getByText('3 pages written')).toBeTruthy()
    expect(screen.getByText('1 handles still need a name.')).toBeTruthy()
    expect(screen.getByText('One photo was missing')).toBeTruthy()
  })

  it('can be cancelled while it runs', async () => {
    const view = await wizard()
    await toPreview(view)
    click('Import')
    await view.flush()
    click('Cancel the import')
    expect(view.api.calls).toContainEqual(['cancel', 5])
    await view.emit('job.finished', { ...job({ id: 5, status: 'cancelled', result: null }), job: 5 })
    expect(screen.getByText('The import was cancelled.')).toBeTruthy()
  })

  it('reports a failure in plain words', async () => {
    const view = await wizard()
    await toPreview(view)
    click('Import')
    await view.flush()
    await view.emit('job.finished', { ...job({ id: 5, status: 'failed', error: 'Nothing to import was found in there.', result: null }), job: 5 })
    expect(screen.getByRole('alert').textContent).toContain('The import did not finish')
    expect(screen.getByRole('alert').textContent).toContain('Nothing to import was found in there.')
  })

  it('says so when Caixa stopped before the import finished', async () => {
    const view = await wizard()
    await toPreview(view)
    click('Import')
    await view.flush()
    await view.emit('job.finished', { ...job({ id: 5, status: 'interrupted', result: null }), job: 5 })
    expect(screen.getByText('Caixa stopped before the import finished. Run it again to continue.')).toBeTruthy()
  })

  it('leads from the unnamed handles to the People section', async () => {
    const onShowPeople = vi.fn()
    const view = await wizard(vi.fn(), onShowPeople)
    await toPreview(view)
    click('Import')
    await view.flush()
    await view.emit('job.finished', { ...job({ id: 5, result: { inserted: 7, updated: 0, unchanged: 0, pages: 2, unresolved: ['Ana Costa', 'Rui'], warnings: [] } }), job: 5 })
    expect(screen.getByText(/2 handles still need a name/)).toBeTruthy()
    click('Name them')
    expect(onShowPeople).toHaveBeenCalledOnce()
  })

  it('goes to the job, or starts over', async () => {
    const onShowJob = vi.fn()
    const view = await wizard(onShowJob)
    await toPreview(view)
    click('Import')
    await view.flush()
    await view.emit('job.finished', { ...job({ id: 5 }), job: 5 })
    click('See the job and its log')
    expect(onShowJob).toHaveBeenCalledWith(5)
    click('Import another')
    expect(currentStep()).toBe('Source')
  })

  it('shows a refusal to start, and stays on the preview', async () => {
    const view = await wizard()
    await toPreview(view)
    view.api.startReply = fail('invalid_params', 'The box is read-only.')
    click('Import')
    await view.flush()
    expect(screen.getByRole('alert').textContent).toContain('The box is read-only.')
    expect(currentStep()).toBe('Preview')
  })
})

describe('the steps', () => {
  it('mark where you are and what is done', async () => {
    const view = await wizard()
    click(/WhatsApp/)
    click('I have the export')
    const items = Array.from(screen.getByRole('list', { name: 'Steps' }).querySelectorAll('li')).map(li => li.textContent)
    expect(items).toEqual(['Source', 'Export', 'Choose', 'Options', 'Preview', 'Import'])
    expect(currentStep()).toBe('Choose')
    expect(BOX.name).toBe('Our box')
    await view.flush()
  })
})
