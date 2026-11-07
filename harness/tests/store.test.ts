import { describe, expect, it } from 'vitest'
import { Store } from '../src/client/store.ts'
import { BOX, FakeApi, fail, job, ok, settle } from './fake-api.ts'

const make = (options = {}) => {
  const api = new FakeApi()
  const timers: (() => void)[] = []
  const saves: (() => void)[] = []
  const memory = { value: null as string | null, get() { return this.value }, set(path: string | null) { this.value = path } }
  const store = new Store(api, { toastMs: 5000, memory, setTimer: (callback) => { timers.push(callback); return 0 }, debounce: (callback) => { saves.push(callback); return saves.length }, ...options })
  return { api, store, memory, timers, saves }
}

describe('starting', () => {
  it('opens the event stream once and reads the box and the jobs', async () => {
    const { api, store } = make()
    api.jobList = [job()]
    await store.start()
    await store.start()
    expect(api.followed).toBe(1)
    const state = store.getState()
    expect(state.box).toEqual(BOX)
    expect(state.jobs).toHaveLength(1)
    expect(state.ready).toBe(true)
  })

  it('reopens the box it remembers when the worker has none open', async () => {
    const { api, store, memory } = make()
    memory.value = '/boxes/Our box'
    api.box = fail('no_box', 'open a box first')
    const opened = { ...BOX, name: 'Remembered' }
    api.boxOpen = async (path: string) => { api.calls.push(['boxOpen', path]); return ok(opened) }
    await store.start()
    expect(store.getState().box).toEqual(opened)
    expect(api.calls).toContainEqual(['boxOpen', '/boxes/Our box'])
  })

  it('forgets a remembered box that cannot be opened any more', async () => {
    const { api, store, memory } = make()
    memory.value = '/gone'
    api.box = fail('no_box', 'x')
    api.boxOpen = async () => fail('not_found', 'not a Caixa box')
    await store.start()
    expect(store.getState().box).toBeNull()
    expect(memory.value).toBeNull()
    expect(store.getState().ready).toBe(true)
  })

  it('stops following when stopped', async () => {
    const { api, store } = make()
    await store.start()
    store.stop()
    expect(api.stopped).toBe(1)
  })
})

describe('boxes', () => {
  it('creating or opening a box makes it the current one and remembers it', async () => {
    const { api, store, memory } = make()
    await store.start()
    expect(await store.createBox('/b', 'B', 'Me')).toBeUndefined()
    expect(api.calls).toContainEqual(['boxCreate', '/b', 'B', 'Me'])
    expect(memory.value).toBe(BOX.root)
    memory.value = null
    expect(await store.openBox('/b')).toBeUndefined()
    expect(memory.value).toBe(BOX.root)
  })

  it('returns the worker\'s error and keeps what was there', async () => {
    const { api, store } = make()
    await store.start()
    api.box = fail('conflict', 'already a box')
    expect(await store.createBox('/b', 'B', 'Me')).toMatchObject({ kind: 'conflict', message: 'already a box' })
    expect(store.getState().box).toEqual(BOX)
  })
})

describe('the event stream', () => {
  it('moves a job along as progress arrives', async () => {
    const { api, store } = make()
    api.jobList = [job({ id: 5, status: 'queued', stage: null, result: null })]
    await store.start()
    api.emit('job.progress', { job: 5, stage: 'importing', current: 1, total: 4, message: 'chat.txt' })
    expect(store.job(5)).toMatchObject({ status: 'running', stage: 'importing', current: 1, total: 4, message: 'chat.txt' })
  })

  it('reads the jobs again when progress names one it does not know', async () => {
    const { api, store } = make()
    await store.start()
    api.jobList = [job({ id: 9, status: 'running' })]
    api.emit('job.progress', { job: 9, stage: 'preparing', current: 0, total: null, message: '' })
    await settle()
    expect(store.job(9)).toBeDefined()
  })

  it('records a finished job, announces it once and refreshes the box counts', async () => {
    const { api, store } = make()
    api.jobList = [job({ id: 5, status: 'running', result: null })]
    await store.start()
    api.emit('job.finished', { ...job({ id: 5 }), job: 5 })
    await settle()
    expect(store.job(5)).toMatchObject({ status: 'done', result: { inserted: 7 } })
    expect(store.getState().toasts).toEqual([
      { id: 1, job: 5, outcome: 'done', kind: 'import', collector: 'WhatsApp', inserted: 7, error: null },
    ])
    expect(api.calls.filter(call => call[0] === 'boxStatus').length).toBeGreaterThan(1)
  })

  it('announces failures and cancellations too, with the plain error', async () => {
    const { api, store } = make()
    await store.start()
    api.emit('job.finished', { ...job({ id: 6, status: 'failed', error: 'Nothing to import', result: null }), job: 6 })
    api.emit('job.finished', { ...job({ id: 7, status: 'cancelled', result: null }), job: 7 })
    await settle()
    expect(store.getState().toasts.map(t => [t.job, t.outcome, t.error])).toEqual([[6, 'failed', 'Nothing to import'], [7, 'cancelled', null]])
  })

  it('removes a toast when dismissed and when its time is up', async () => {
    const { api, store, timers } = make()
    await store.start()
    api.emit('job.finished', { ...job({ id: 5 }), job: 5 })
    api.emit('job.finished', { ...job({ id: 6 }), job: 6 })
    await settle()
    expect(store.getState().toasts).toHaveLength(2)
    store.dismissToast(1)
    expect(store.getState().toasts.map(t => t.id)).toEqual([2])
    timers.forEach(run => run())
    expect(store.getState().toasts).toEqual([])
    store.dismissToast(99) // unknown: nothing happens
  })

  it('notes inbox changes and a worker that came back', async () => {
    const { api, store } = make()
    await store.start()
    api.emit('inbox.changed', { entries: [] })
    expect(store.getState().inboxVersion).toBe(1)
    api.emit('worker.state', { state: 'restarting' })
    expect(store.getState().worker).toBe('restarting')
    const before = api.calls.length
    api.emit('worker.state', { state: 'running' })
    await settle()
    expect(store.getState().worker).toBe('running')
    expect(api.calls.length).toBeGreaterThan(before) // it read the box and the jobs again
  })

  it('tells subscribers about every change, until they leave', async () => {
    const { api, store } = make()
    let heard = 0
    const leave = store.subscribe(() => { heard += 1 })
    await store.start()
    const afterStart = heard
    expect(afterStart).toBeGreaterThan(0)
    leave()
    api.emit('inbox.changed', {})
    expect(heard).toBe(afterStart)
  })
})

describe('read-only and the pages-redrawn jobs', () => {
  it('learns from the worker whether it refuses changes', async () => {
    const { api, store } = make()
    api.readOnly = true
    await store.start()
    expect(store.getState().readOnly).toBe(true)
    const writable = make()
    await writable.store.start()
    expect(writable.store.getState().readOnly).toBe(false)
  })

  it('says nothing when the pages were redrawn, but tells lists to re-read', async () => {
    const { api, store } = make()
    await store.start()
    const before = store.getState().boxVersion
    api.emit('job.finished', { ...job({ id: 9, kind: 'refresh', collector: null, result: null }), job: 9 })
    await settle()
    expect(store.getState().toasts).toEqual([])
    expect(store.getState().boxVersion).toBeGreaterThan(before)
  })

  it('does tell when redrawing the pages failed, in its own words', async () => {
    const { api, store } = make()
    await store.start()
    api.emit('job.finished', { ...job({ id: 9, kind: 'refresh', collector: null, status: 'failed', error: 'disk full', result: null }), job: 9 })
    await settle()
    expect(store.getState().toasts).toEqual([
      { id: 1, job: 9, outcome: 'failed', kind: 'refresh', collector: '', inserted: 0, error: 'disk full' },
    ])
  })
})

describe('a reply that is older than what the event stream already said', () => {
  it('does not bring a finished job back to life', async () => {
    const { api, store } = make()
    await store.start()
    // The jobs list is asked for while job 9 is still queued, and answers late.
    let answerLate: (() => void) | undefined
    api.jobs = async () => {
      const stale = [job({ id: 9, kind: 'refresh', collector: null, status: 'queued', stage: null, result: null })]
      await new Promise<void>((resolve) => { answerLate = resolve })
      return ok(stale)
    }
    const refreshing = store.refreshJobs()
    // Meanwhile the job finishes and the stream says so.
    api.emit('job.finished', { ...job({ id: 9, kind: 'refresh', collector: null, result: null }), job: 9 })
    await settle()
    expect(store.job(9)?.status).toBe('done')
    answerLate!()
    await refreshing
    expect(store.job(9)?.status).toBe('done') // the older answer did not win
  })

  it('still takes news about jobs it has not finished, and jobs it did not know', async () => {
    const { api, store } = make()
    api.jobList = [job({ id: 1, status: 'running', result: null })]
    await store.start()
    api.jobList = [job({ id: 2, status: 'queued', result: null }), job({ id: 1, status: 'done' })]
    await store.refreshJobs()
    expect(store.job(1)?.status).toBe('done')
    expect(store.job(2)?.status).toBe('queued')
  })
})

const DRAFT = { collector: 'voicemail', step: 'options', source: '/exports/iPhone Voicemail.zip', values: { transcribe: true } }

describe('what is remembered between runs', () => {
  it('reads the recent boxes and where you were when it starts', async () => {
    const { api, store } = make()
    api.sessionReply = ok({ recent: [{ path: '/boxes/Our box', name: 'Our box', opened: '2024-05-01T10:00:00+00:00', exists: true }], last_box: '/boxes/Our box', box: '/boxes/Our box', view: 'jobs', draft: DRAFT })
    await store.start()
    const state = store.getState()
    expect(state.recent.map(box => box.name)).toEqual(['Our box'])
    expect(state.view).toBe('jobs')
    expect(state.draft).toEqual(DRAFT)
  })

  it('works when the worker has nothing remembered, or no box', async () => {
    const { api, store } = make()
    api.box = fail('no_box', 'x')
    api.sessionReply = fail('no_box', 'x')
    await store.start()
    expect(store.getState()).toMatchObject({ recent: [], view: null, draft: null, ready: true })
  })

  it('keeps the section at once and saves it once, a moment later', async () => {
    const { api, store, saves } = make()
    await store.start()
    store.saveView('people')
    store.saveView('jobs')
    expect(store.getState().view).toBe('jobs')
    expect(api.sessionSaved).toEqual([])
    saves.at(-1)!()
    await settle()
    expect(api.sessionSaved).toEqual([{ view: 'jobs' }])
  })

  it('keeps the draft, saves it with the section in one call, and clears it with null', async () => {
    const { api, store, saves } = make()
    await store.start()
    store.saveView('import')
    store.saveDraft(DRAFT)
    expect(store.getState().draft).toEqual(DRAFT)
    saves.at(-1)!()
    await settle()
    expect(api.sessionSaved).toEqual([{ view: 'import', draft: DRAFT }])
    store.saveDraft(null)
    expect(store.getState().draft).toBeNull()
    saves.at(-1)!()
    await settle()
    expect(api.sessionSaved.at(-1)).toEqual({ draft: null })
  })

  it('does not save what has not changed', async () => {
    const { api, store, saves } = make()
    await store.start()
    store.saveDraft(DRAFT)
    saves.at(-1)!()
    await settle()
    store.saveDraft({ ...DRAFT })
    expect(saves).toHaveLength(1)
    expect(api.sessionSaved).toHaveLength(1)
  })

  it('writes what is waiting when the store stops, so closing the page loses nothing', async () => {
    const { api, store } = make()
    await store.start()
    store.saveDraft(DRAFT)
    store.stop()
    await settle()
    expect(api.sessionSaved).toEqual([{ draft: DRAFT }])
  })

  it('opening another box brings that box\'s own section and draft', async () => {
    const { api, store } = make()
    await store.start()
    api.sessionReply = ok({ recent: [], last_box: null, box: '/boxes/Other', view: 'people', draft: null })
    expect(await store.openBox('/boxes/Other')).toBeUndefined()
    expect(store.getState().view).toBe('people')
    expect(store.getState().draft).toBeNull()
  })

  it('forgets a box on the list without touching the open one', async () => {
    const { api, store } = make()
    api.sessionReply = ok({ recent: [{ path: '/boxes/Old', name: 'Old', opened: null, exists: false }], last_box: null, box: '/boxes/Our box', view: null, draft: null })
    await store.start()
    await store.forgetBox('/boxes/Old')
    expect(api.forgotten).toEqual(['/boxes/Old'])
    expect(store.getState().recent).toEqual([])
    expect(store.getState().box).toEqual(BOX)
  })

  it('reopens the box that was open when the worker comes back without one', async () => {
    const { api, store } = make()
    await store.start()
    api.box = fail('no_box', 'You need to open a box first')
    api.emit('worker.state', { state: 'restarting' })
    api.emit('worker.state', { state: 'running' })
    await settle(); await settle()
    api.box = ok(BOX)
    expect(api.calls.filter(call => call[0] === 'boxOpen')).toEqual([['boxOpen', '/boxes/Our box']])
  })
})
