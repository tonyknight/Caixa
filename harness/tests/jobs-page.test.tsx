// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { JobsPage } from '../src/client/pages/JobsPage.tsx'
import { ToastHost } from '../src/client/Toasts.tsx'
import { fail, job, ok } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const jobs = [
  job({ id: 3, status: 'running', stage: 'importing', message: 'chat.txt', result: null, finished_at: null }),
  job({ id: 2, status: 'failed', error: 'Nothing to import was found in there.', result: null, source: '/exports/empty' }),
  job({ id: 1 }),
]

describe('the jobs page', () => {
  it('says so when nothing has run', async () => {
    await renderWith(<JobsPage selected={undefined} onSelect={() => undefined} />)
    expect(screen.getByText('No imports have been run yet.')).toBeTruthy()
  })

  it('lists the jobs newest first, with collector names, sources, status and the running stage', async () => {
    await renderWith(<JobsPage selected={undefined} onSelect={() => undefined} />, (api) => { api.jobList = jobs })
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows.map(row => within(row).getAllByRole('cell')[0]!.textContent)).toEqual(['3', '2', '1'])
    expect(within(rows[0]!).getByText('Running')).toBeTruthy()
    expect(within(rows[0]!).getByText('Importing — chat.txt')).toBeTruthy()
    expect(within(rows[0]!).getAllByText(/WhatsApp/).length).toBeGreaterThan(0)
    expect(within(rows[1]!).getByText('Failed')).toBeTruthy()
    expect(within(rows[1]!).getByText('/exports/empty')).toBeTruthy()
    expect(within(rows[2]!).getByText('Done')).toBeTruthy()
  })

  it('offers to cancel only the jobs that can still be cancelled', async () => {
    const view = await renderWith(<JobsPage selected={undefined} onSelect={() => undefined} />, (api) => { api.jobList = jobs })
    expect(screen.getAllByRole('button', { name: 'Cancel' })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(view.api.calls).toContainEqual(['cancel', 3])
  })

  it('selects a job, shows its log, and says what went wrong', async () => {
    const onSelect = vi.fn()
    const view = await renderWith(<JobsPage selected={2} onSelect={onSelect} />, (api) => { api.jobList = jobs })
    const details = screen.getByRole('region', { name: 'Details of job 2' })
    expect(within(details).getByRole('alert').textContent).toContain('Nothing to import was found in there.')
    expect(within(details).getByText('hello from the collector', { exact: false })).toBeTruthy()
    expect(view.api.calls).toContainEqual(['jobLog', 2])
    fireEvent.click(screen.getAllByRole('button', { name: /Show details/ })[0]!)
    expect(onSelect).toHaveBeenCalledWith(3)
    fireEvent.click(screen.getAllByRole('button', { name: /Show details/ })[1]!)
    expect(onSelect).toHaveBeenLastCalledWith(undefined) // choosing the open one closes it
  })

  it('shows the result of a finished job and the options it ran with', async () => {
    await renderWith(<JobsPage selected={1} onSelect={() => undefined} />, (api) => { api.jobList = [job({ id: 1, options: { owner: 'Maria Costa' } })] })
    const details = screen.getByRole('region', { name: 'Details of job 1' })
    expect(within(details).getByText('7 new, 0 changed, 0 unchanged')).toBeTruthy()
    expect(within(details).getByText('owner: Maria Costa')).toBeTruthy()
  })

  it('handles an empty log and a cut one', async () => {
    const empty = await renderWith(<JobsPage selected={1} onSelect={() => undefined} />, (api) => {
      api.jobList = [job()]
      api.logReply = ok({ text: '', size: 0, truncated: false })
    })
    expect(screen.getByText('The log is empty.')).toBeTruthy()
    empty.unmount()
    await renderWith(<JobsPage selected={1} onSelect={() => undefined} />, (api) => {
      api.jobList = [job()]
      api.logReply = ok({ text: 'the last part', size: 999999, truncated: true })
    })
    expect(screen.getByText('Showing the end of the log.')).toBeTruthy()
    expect(screen.getByText('the last part')).toBeTruthy()
  })

  it('reads the log again when a running job moves on', async () => {
    const view = await renderWith(<JobsPage selected={3} onSelect={() => undefined} />, (api) => { api.jobList = jobs })
    const before = view.api.calls.filter(call => call[0] === 'jobLog').length
    await view.emit('job.progress', { job: 3, stage: 'rendering', current: 0, total: null, message: '' })
    expect(view.api.calls.filter(call => call[0] === 'jobLog').length).toBe(before + 1)
  })

  it('does not break when the log cannot be read', async () => {
    await renderWith(<JobsPage selected={1} onSelect={() => undefined} />, (api) => {
      api.jobList = [job()]
      api.jobLog = async () => fail('not_found', 'no log')
    })
    expect(screen.getByText('Reading the log…')).toBeTruthy()
  })
})

describe('the toasts', () => {
  const finished = (id: number, over = {}) => ({ ...job({ id, ...over }), job: id })

  it('announce a finished import with its count', async () => {
    const view = await renderWith(<ToastHost />)
    expect(screen.queryByRole('region')).toBeNull()
    await view.emit('job.finished', finished(5))
    expect(screen.getByRole('region', { name: 'Caixa notices' }).getAttribute('aria-live')).toBe('polite')
    expect(screen.getByText('WhatsApp: 7 new items imported.')).toBeTruthy()
  })

  it('announce a failure with its reason, a cancellation and an interruption', async () => {
    const view = await renderWith(<ToastHost />)
    await view.emit('job.finished', finished(6, { status: 'failed', error: 'Nothing to import', result: null }))
    await view.emit('job.finished', finished(7, { status: 'cancelled', result: null }))
    await view.emit('job.finished', finished(8, { status: 'interrupted', result: null }))
    expect(screen.getByText('WhatsApp import failed: Nothing to import')).toBeTruthy()
    expect(screen.getByText('WhatsApp import cancelled.')).toBeTruthy()
    expect(screen.getByText('WhatsApp import was interrupted.')).toBeTruthy()
  })

  it('go away when dismissed', async () => {
    const view = await renderWith(<ToastHost />)
    await view.emit('job.finished', finished(5))
    await view.emit('job.finished', finished(6))
    expect(screen.getAllByRole('button', { name: 'Dismiss' })).toHaveLength(2)
    fireEvent.click(screen.getAllByRole('button', { name: 'Dismiss' })[0]!)
    expect(screen.getAllByRole('button', { name: 'Dismiss' })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('region')).toBeNull()
  })

  it('announce failed page updates in their own words, not as an import', async () => {
    const view = await renderWith(<ToastHost />)
    await view.emit('job.finished', finished(9, { kind: 'refresh', collector: null, status: 'failed', error: 'disk full', result: null }))
    expect(screen.getByText('Updating the pages failed: disk full')).toBeTruthy()
  })

  it('speak Chinese when asked', async () => {
    const view = await renderWith(<ToastHost />, () => undefined, 'zh')
    await view.emit('job.finished', finished(5))
    expect(screen.getByText('WhatsApp：已导入 7 条新内容。')).toBeTruthy()
  })
})
