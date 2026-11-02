import { describe, expect, it } from 'vitest'
import { Store } from '../src/client/store.ts'
import { BOX, FakeApi, fail, job, ok, settle } from './fake-api.ts'

const make = (options = {}) => {
  const api = new FakeApi()
  const timers: (() => void)[] = []
  const memory = { value: null as string | null, get() { return this.value }, set(path: string | null) { this.value = path } }
  const store = new Store(api, { toastMs: 5000, memory, setTimer: (callback) => { timers.push(callback); return 0 }, ...options })
  return { api, store, memory, timers }
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
      { id: 1, job: 5, outcome: 'done', collector: 'WhatsApp', inserted: 7, error: null },
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
