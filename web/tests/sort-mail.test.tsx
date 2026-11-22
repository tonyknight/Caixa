// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SortMail } from '../src/client/mail/SortMail.tsx'
import type { SortReply, SortRow } from '../src/client/mail/types.ts'
import { SETTINGS, job, ok, type FakeApi } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const job9 = job({ id: 9, kind: 'mail-import', collector: 'mail', source: '/exports/x.mbox', result: { inserted: 5, updated: 0, unchanged: 0, pages: 2, unresolved: [], warnings: [], mails: 5, conversations: 2, senders: 1 } as never })

const SOURCE = { id: 4, path: '/exports/(2026-11-20) All mail [Cleaned].mbox', member: '', kind: 'cleaned', account: 'Gmail', status: 'read', mails: 33, size: 20_000, parent_id: 1 }

const person = (name: string, address: string, mails: number, size: number, over: Partial<SortRow> = {}): SortRow =>
  ({ name, address, mails, size, known_by: null, person: null, owner_wrote: 0, chosen: false, ...over })

const ANA = person('Ana Costa', 'ana.costa@example.com', 4, 2_000, { known_by: 'address', person: 'Ana Costa', owner_wrote: 1, chosen: true })
const HOME = person('Rui Pereira', 'rui.home@example.net', 1, 400, { known_by: 'name', person: 'Rui Pereira' })
const BEATRIZ = person('Beatriz Lima', 'beatriz.lima@example.net', 3, 1_500, { owner_wrote: 1 })
const CARLOS = person('Carlos Mendes', 'carlos.mendes@example.net', 2, 900)
const INES = person('Inês Rocha', 'ines.rocha@example.net', 2, 700)

/** A stand-in for the service's sorting: decisions move people between the categories. */
function scripted(api: FakeApi, state = { chosen: new Set<string>(), ignored: new Set<string>(), linked: new Map<string, string>() }) {
  const reply = (): SortReply => {
    const everyone = [ANA, HOME, BEATRIZ, CARLOS, INES].map(r => {
      const linked = state.linked.get(r.address)
      return linked ? { ...r, known_by: 'address' as const, person: linked, chosen: true } : r
    })
    const live = everyone.filter(r => !state.ignored.has(r.address)).map(r => ({ ...r, chosen: r.chosen || state.chosen.has(r.address) }))
    const sum = (rows: SortRow[]) => ({ senders: rows.length, mails: rows.reduce((n, r) => n + r.mails, 0), size: rows.reduce((n, r) => n + r.size, 0), rows })
    const toImport = live.filter(r => r.chosen)
    return {
      source: { ...SOURCE, size: SOURCE.size },
      categories: [
        { key: 'known', label: 'Known', ...sum(live.filter(r => r.known_by)) },
        { key: 'to_sort', label: 'To sort', ...sum(live.filter(r => !r.known_by && !r.chosen)) },
        { key: 'to_import', label: 'To import', ...sum(toImport) },
        { key: 'ignored', label: 'Ignored', ...sum(everyone.filter(r => state.ignored.has(r.address))) },
        { key: 'imported', label: 'Imported', ...sum([]) },
      ],
      selection: { threads: toImport.length * 2, mails: toImport.reduce((n, r) => n + r.mails, 0) + 1, size: 9_000, senders: toImport.length },
    }
  }
  api.generic['mail.sources'] = () => ok({ sources: [SOURCE] })
  api.generic['mail.senders'] = () => ok(reply())
  api.generic['mail.choose'] = (params) => { (params.addresses as string[]).forEach(a => params.choose === false ? state.chosen.delete(a) : state.chosen.add(a)); return ok(reply()) }
  api.generic['mail.ignore'] = (params) => { (params.addresses as string[]).forEach(a => params.ignore === false ? state.ignored.delete(a) : state.ignored.add(a)); return ok(reply()) }
  api.generic['mail.owner'] = () => ok({ account: 'Gmail', confirmed: [], proposed: ['maria.costa@example.com'] })
  api.generic['mail.owner.set'] = () => ok({ account: 'Gmail', confirmed: ['maria.costa@example.com'], proposed: ['maria.costa@example.com'] })
  api.changeReply = (kind, args) => { if (kind === 'link') state.linked.set(String(args[1]), String(args[2])); return ok({ person: { id: 9, name: String(args[2]) }, refresh: null }) as never }
  return state
}

async function opened() {
  const view = await renderWith(<SortMail />, api => scripted(api))
  fireEvent.click(screen.getByRole('button', { name: /Sort \(2026-11-20\) All mail \[Cleaned\]\.mbox/ }))
  await view.flush()
  return view
}

const rows = () => screen.getAllByRole('row').slice(1)
const names = () => rows().map(r => within(r).getAllByRole('cell')[1]!.textContent)
const sidebar = () => screen.getByRole('navigation', { name: 'Groups' })
const go = (label: RegExp) => fireEvent.click(within(sidebar()).getByRole('link', { name: label }))

describe('the Sort mail window', () => {
  it('shows the categories with their counts, Known first, with notes under the names', async () => {
    await opened()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Known')
    expect(within(sidebar()).getByRole('link', { name: /To sort/ }).textContent).toContain('3 senders · 7 mails · 3.0 KB')
    expect(names()).toEqual(['Ana Costaknown · you wrote 1', 'Rui Pereiraby name: Rui Pereira?'])
    expect(screen.getByRole('contentinfo').textContent).toContain('Importing would bring 5 mails in 2 conversations')
  })

  it('chooses with the tool and the status bar, and ignores with Delete', async () => {
    const view = await opened()
    go(/To sort/)
    fireEvent.click(screen.getByRole('button', { name: 'Choose Beatriz Lima' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.choose', { source: 4, addresses: ['beatriz.lima@example.net'], choose: true }])
    expect(names()).not.toContain('Beatriz Limayou wrote 1')
    fireEvent.click(rows()[0]!)
    fireEvent.keyDown(document, { key: 'Delete' })
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.ignore', { source: 4, addresses: ['carlos.mendes@example.net'], ignore: true }])
    fireEvent.click(rows()[0]!)
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Choose' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.choose', { source: 4, addresses: ['ines.rocha@example.net'], choose: true }])
    go(/Ignored/)
    fireEvent.click(screen.getByRole('button', { name: 'Stop ignoring Carlos Mendes' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.ignore', { source: 4, addresses: ['carlos.mendes@example.net'], ignore: false }])
  })

  it('selects every sender at once, then lets a few be deselected', async () => {
    const view = await opened()
    go(/To sort/)
    const all = screen.getByRole('checkbox', { name: 'Select all' }) as HTMLInputElement
    fireEvent.click(all)
    expect(rows().every(r => r.getAttribute('aria-selected') === 'true')).toBe(true)
    expect(screen.getByRole('contentinfo').textContent).toContain('3 selected')
    expect(all.checked).toBe(true)
    fireEvent.click(rows()[0]!)  // Beatriz stays out
    expect(screen.getByRole('contentinfo').textContent).toContain('2 selected')
    expect(all.checked).toBe(false)
    expect(all.indeterminate).toBe(true)
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Choose' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.choose', { source: 4, addresses: ['carlos.mendes@example.net', 'ines.rocha@example.net'], choose: true }])
  })

  it('selects all with Ctrl-A, and not on the Imported list', async () => {
    await opened()
    go(/To sort/)
    fireEvent.keyDown(document, { key: 'a', ctrlKey: true })
    expect(screen.getByRole('contentinfo').textContent).toContain('3 selected')
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all' }))  // and off again
    expect(screen.getByRole('contentinfo').textContent).not.toContain('selected')
    go(/Imported/)
    expect(screen.queryByRole('checkbox', { name: 'Select all' })).toBeNull()
  })

  it('takes senders dropped on Ignored or To import', async () => {
    const view = await opened()
    go(/To sort/)
    fireEvent.click(rows()[1]!)
    fireEvent.dragStart(rows()[1]!, { dataTransfer: { setData: () => undefined } })
    const target = within(sidebar()).getByRole('link', { name: /To import/ })
    fireEvent.dragOver(target)
    fireEvent.drop(target)
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.choose', { source: 4, addresses: ['carlos.mendes@example.net'], choose: true }])
  })

  it('does not import someone from To import: a known person is ignored, a chosen one forgotten', async () => {
    const view = await opened()
    go(/To sort/)
    fireEvent.click(screen.getByRole('button', { name: 'Choose Beatriz Lima' }))
    await view.flush()
    go(/To import/)
    fireEvent.click(screen.getByRole('button', { name: "Don't import Beatriz Lima" }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.choose', { source: 4, addresses: ['beatriz.lima@example.net'], choose: false }])
    fireEvent.click(screen.getByRole('button', { name: "Don't import Ana Costa" }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.ignore', { source: 4, addresses: ['ana.costa@example.com'], ignore: true }])
  })

  it('confirms a match by name, and names a sender with the people of the box', async () => {
    const view = await opened()
    fireEvent.click(screen.getByRole('button', { name: "It's Rui Pereira: rui.home@example.net" }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['link', 'Mail', 'rui.home@example.net', 'Rui Pereira', undefined])
    go(/To sort/)
    fireEvent.click(screen.getByRole('button', { name: 'Name Inês Rocha' }))
    const field = screen.getByRole('combobox', { name: 'Name for ines.rocha@example.net' })
    expect([...document.querySelectorAll('datalist option')].map(o => (o as HTMLOptionElement).value)).toEqual(['Ana A', 'Rui Pereira'])
    fireEvent.change(field, { target: { value: 'Inês Rocha Costa' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['link', 'Mail', 'ines.rocha@example.net', 'Inês Rocha Costa', undefined])
  })

  it('confirms the owner’s addresses for the account', async () => {
    const view = await opened()
    const bar = screen.getByRole('region', { name: 'Your addresses' })
    expect(bar.textContent).toContain('maria.costa@example.com')
    fireEvent.click(within(bar).getByRole('button', { name: 'Confirm' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.owner.set', { source: 4, addresses: ['maria.costa@example.com'] }])
    expect(screen.queryByRole('region', { name: 'Your addresses' })).toBeNull()
  })

  it('imports what the chosen bring, after asking, and follows the job', async () => {
    const view = await opened()
    view.api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
    view.api.generic['mail.import'] = () => ok({ ...job9, status: 'queued', result: null })
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    const ask = screen.getByRole('dialog', { name: /Import 5 mails in 2 conversations/ })
    expect(ask.textContent).toContain('1 file')
    fireEvent.click(within(ask).getByRole('button', { name: 'Import them' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.import', { source: 4, translate: false, summarize: false }])
    const asked = view.api.calls.filter(c => c[1] === 'mail.senders').length
    await view.emit('job.finished', { ...job9, status: 'done', job: 9 })
    await view.flush()
    expect(within(screen.getByRole('main')).getByRole('status', { name: 'Imported' }).textContent).toContain('5 mails in 2 conversations')
    expect(view.api.calls.filter(c => c[1] === 'mail.senders').length).toBeGreaterThan(asked)
  })

  it('shows a meter beside Import from the click to the end of the job, and keeps it disabled', async () => {
    const view = await opened()
    let answer: (value: unknown) => void = () => undefined
    view.api.generic['mail.import.preview'] = () => new Promise(resolve => { answer = resolve }) as never
    view.api.generic['mail.import'] = () => ok({ ...job9, status: 'queued', result: null })
    const bar = () => screen.getByRole('contentinfo')
    const button = () => within(bar()).getByRole('button', { name: 'Import' }) as HTMLButtonElement
    fireEvent.click(button())
    await view.flush()
    expect(within(bar()).getByRole('status', { name: 'Import progress' }).textContent).toContain('Counting')
    expect(button().disabled).toBe(true)
    answer(ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 }))
    await view.flush()
    fireEvent.click(within(screen.getByRole('dialog', { name: /Import 5 mails/ })).getByRole('button', { name: 'Import them' }))
    await view.flush()
    // the window has not heard of the job yet: still busy, the meter says it is starting
    expect(button().disabled).toBe(true)
    expect(within(bar()).getByRole('status', { name: 'Import progress' }).textContent).toContain('Starting')
    view.api.jobList = [{ ...job9, status: 'running', stage: 'filing', current: 3, total: 12, result: null }]
    await view.emit('job.progress', { job: 9, stage: 'filing', current: 3, total: 12, message: '' })
    const meter = within(bar()).getByRole('status', { name: 'Import progress' })
    expect(meter.textContent).toContain('Filing')
    expect(meter.textContent).toContain('3 of 12')
    expect(button().disabled).toBe(true)
    await view.emit('job.finished', { ...job9, status: 'done', job: 9 })
    await view.flush()
    expect(within(bar()).queryByRole('status', { name: 'Import progress' })).toBeNull()
  })

  it('translates and summarizes this import as Settings say, or not, as chosen', async () => {
    const view = await renderWith(<SortMail />, api => {
      scripted(api)
      api.settingsReply = ok({ ...SETTINGS, values: { ...SETTINGS.values, 'translation.enabled': true, 'translation.endpoint': 'http://localhost:11434/v1', 'translation.model': 'llama', 'summaries.enabled': true } })
      api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
      api.generic['mail.import'] = () => ok({ ...job9, status: 'queued', result: null })
    })
    fireEvent.click(screen.getByRole('button', { name: /Sort \(2026-11-20\) All mail \[Cleaned\]\.mbox/ }))
    await view.flush()
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    const ask = screen.getByRole('dialog', { name: /Import 5 mails/ })
    const translate = within(ask).getByRole('checkbox', { name: 'Translate' }) as HTMLInputElement
    const summarize = within(ask).getByRole('checkbox', { name: 'Summarize' }) as HTMLInputElement
    expect(translate.checked && summarize.checked).toBe(true)  // as Settings say
    expect(translate.disabled || summarize.disabled).toBe(false)  // both set up (summaries use translation's)
    fireEvent.click(translate)
    fireEvent.click(within(ask).getByRole('button', { name: 'Import them' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.import', { source: 4, translate: false, summarize: true }])
  })

  it('counts Apple Intelligence as set up for the switches', async () => {
    const view = await renderWith(<SortMail />, api => {
      scripted(api)
      api.settingsReply = ok({ ...SETTINGS, values: { ...SETTINGS.values, 'summaries.enabled': true, 'summaries.provider': 'apple', 'translation.provider': 'apple' } })
      api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
    })
    fireEvent.click(screen.getByRole('button', { name: /Sort \(2026-11-20\) All mail \[Cleaned\]\.mbox/ }))
    await view.flush()
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    const ask = screen.getByRole('dialog', { name: /Import 5 mails/ })
    const summarize = within(ask).getByRole('checkbox', { name: 'Summarize' }) as HTMLInputElement
    expect(summarize.disabled).toBe(false)
    expect(summarize.checked).toBe(true)
    expect((within(ask).getByRole('checkbox', { name: 'Translate' }) as HTMLInputElement).disabled).toBe(false)
  })

  it('counts Automatic as set up when this Mac has Apple Intelligence, with no endpoint', async () => {
    const view = await renderWith(<SortMail />, api => {
      scripted(api)
      api.settingsReply = ok({ ...SETTINGS, apple: { ready: true, message: '' }, values: { ...SETTINGS.values, 'summaries.enabled': true, 'summaries.provider': 'auto', 'translation.provider': 'auto' } })
      api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
    })
    fireEvent.click(screen.getByRole('button', { name: /Sort \(2026-11-20\) All mail \[Cleaned\]\.mbox/ }))
    await view.flush()
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    const ask = screen.getByRole('dialog', { name: /Import 5 mails/ })
    expect((within(ask).getByRole('checkbox', { name: 'Summarize' }) as HTMLInputElement).disabled).toBe(false)
    expect((within(ask).getByRole('checkbox', { name: 'Translate' }) as HTMLInputElement).disabled).toBe(false)
  })

  it('cannot switch on work that is not set up, and says why no summaries were written', async () => {
    const view = await opened()
    view.api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
    view.api.generic['mail.import'] = () => ok({ ...job9, status: 'queued', result: null })
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    const ask = screen.getByRole('dialog', { name: /Import 5 mails/ })
    expect((within(ask).getByRole('checkbox', { name: 'Summarize' }) as HTMLInputElement).disabled).toBe(true)
    expect(ask.textContent).toContain('Set up in Settings')
    fireEvent.click(within(ask).getByRole('button', { name: 'Import them' }))
    await view.flush()
    await view.emit('job.finished', { ...job9, status: 'done', job: 9, result: { ...job9.result, summaries: { written: 0, left: 2, model: '', error: null, reason: 'off' } } })
    await view.flush()
    expect(within(screen.getByRole('main')).getByRole('status', { name: 'Imported' }).textContent).toContain('No summaries: they are off in Settings, Summaries.')
  })

  it('reports when the import is done, with ways back to the box', async () => {
    const view = await opened()
    view.api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
    view.api.generic['mail.import'] = () => ok({ ...job9, status: 'queued', result: null })
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    fireEvent.click(within(screen.getByRole('dialog', { name: /Import 5 mails/ })).getByRole('button', { name: 'Import them' }))
    await view.flush()
    const result = { inserted: 5, updated: 0, unchanged: 0, pages: 4, unresolved: [], files: 1, translated: 3, mails: 5, conversations: 2, senders: 1,
      summaries: { written: 2, left: 0, model: 'Apple Intelligence', error: null, reason: null }, warnings: ['1 conversation was declined by the safety filter.'] }
    await view.emit('job.finished', { ...job9, status: 'done', job: 9, result, started_at: '2026-11-22T10:00:00+00:00', finished_at: '2026-11-22T10:02:05+00:00' })
    await view.flush()
    const report = screen.getByRole('dialog', { name: 'The import is done' })
    for (const words of ['5 mails in 2 conversations', '1 sender', '5 new items', '2 summaries written by Apple Intelligence', '3 messages translated', '2 min 5 s', 'declined by the safety filter']) {
      expect(report.textContent).toContain(words)
    }
    // the box's people page, in the box window
    const opens: [string, string][] = []
    window.open = ((url: string, name: string) => { opens.push([url, name]); return null }) as typeof window.open
    fireEvent.click(within(report).getByRole('button', { name: "Open the box's people page" }))
    expect(opens[0]![0]).toMatch(/^\/box\/index\.html\?fresh=\d+$/)
    expect(opens[0]![1]).toBe('caixa-box')
    // back to Caixa's own window
    const focus = vi.fn(), close = vi.fn()
    Object.defineProperty(window, 'opener', { value: { focus, closed: false }, configurable: true })
    window.close = close
    fireEvent.click(within(report).getByRole('button', { name: 'Back to Caixa' }))
    expect(focus).toHaveBeenCalled()
    expect(close).toHaveBeenCalled()
    // and closing it leaves the Imported bar
    fireEvent.click(within(report).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog', { name: 'The import is done' })).toBeNull()
    expect(within(screen.getByRole('main')).getByRole('status', { name: 'Imported' })).toBeTruthy()
  })

  it('reports a failed import in the same place', async () => {
    const view = await opened()
    view.api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
    view.api.generic['mail.import'] = () => ok({ ...job9, status: 'queued', result: null })
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    fireEvent.click(within(screen.getByRole('dialog', { name: /Import 5 mails/ })).getByRole('button', { name: 'Import them' }))
    await view.flush()
    await view.emit('job.finished', { ...job9, status: 'failed', job: 9, result: null, error: 'The mbox could not be read.' })
    await view.flush()
    expect(screen.getByRole('dialog', { name: 'The import did not finish' }).textContent).toContain('The mbox could not be read.')
  })

  it('writes the reduced mbox after an import, after asking', async () => {
    const view = await opened()
    view.api.generic['mail.import.preview'] = () => ok({ senders: 1, conversations: 2, mails: 5, files: 1, size: 9_000 })
    view.api.generic['mail.import'] = () => ok({ ...job9, status: 'queued', result: null })
    view.api.generic['mail.reduce'] = () => ok(job({ id: 10, kind: 'mail-reduce', collector: null, status: 'queued', result: null }))
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Import' }))
    await view.flush()
    fireEvent.click(screen.getByRole('button', { name: 'Import them' }))
    await view.flush()
    await view.emit('job.finished', { ...job9, status: 'done', job: 9 })
    // (from the report that opens when the import is done)
    fireEvent.click(within(screen.getByRole('dialog', { name: 'The import is done' })).getByRole('button', { name: 'Write the reduced mbox' }))
    const ask = screen.getByRole('dialog', { name: 'Write the reduced mbox?' })
    expect(ask.textContent).toContain('is not changed')
    expect(ask.textContent).toContain('undo')
    fireEvent.click(within(ask).getByRole('button', { name: 'Write it' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.reduce', { source: 4 }])
    await view.emit('job.finished', { ...job({ id: 10, kind: 'mail-reduce', collector: null, status: 'done', result: { path: '/exports/(2026-11-20) All mail [Reduced].mbox', source_id: 15, mails: 28, size: 15_000, left_out: 5, left_out_size: 5_000 } as never }), job: 10 })
    const written = within(screen.getByRole('main')).getByRole('status', { name: 'Written' })
    expect(written.textContent).toContain('[Reduced].mbox')
    expect(within(written).getByRole('link', { name: 'Sort the reduced mbox' }).getAttribute('href')).toBe('/mail/sort?source=15')
  })

  it('opens the mbox named in its address', async () => {
    window.history.replaceState(null, '', '/mail/sort?source=4')
    const view = await renderWith(<SortMail />, api => scripted(api))
    await view.flush()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Known')
    window.history.replaceState(null, '', '/')
  })
})
