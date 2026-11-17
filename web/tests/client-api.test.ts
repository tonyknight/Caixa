import { describe, expect, it, vi } from 'vitest'
import { call, follow, workerState } from '../src/client/api.ts'

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

describe('call', () => {
  it('posts the method and parameters to the owner-only route, with the cookie', async () => {
    const fetcher = vi.fn(async () => reply({ ok: true, result: { a: 1 } }))
    expect(await call('box.status', { x: 1 }, fetcher as never)).toEqual({ ok: true, result: { a: 1 } })
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/caixa/rpc')
    expect(init).toMatchObject({ method: 'POST', credentials: 'same-origin' })
    expect(JSON.parse(init.body as string)).toEqual({ method: 'box.status', params: { x: 1 } })
  })

  it('hands a worker error back as data', async () => {
    const error = { code: -32000, message: 'No.', kind: 'conflict' }
    expect(await call('x.y', {}, (async () => reply({ ok: false, error })) as never)).toEqual({ ok: false, error })
  })

  it('reports a network failure as worker_unavailable instead of throwing', async () => {
    const result = await call('x.y', {}, (async () => { throw new TypeError('offline') }) as never)
    expect(result).toMatchObject({ ok: false, error: { kind: 'worker_unavailable' } })
  })
})

describe('workerState', () => {
  it('reads the state, and says stopped when it cannot', async () => {
    expect(await workerState((async () => reply({ worker: 'restarting' })) as never)).toBe('restarting')
    expect(await workerState((async () => { throw new Error('x') }) as never)).toBe('stopped')
  })
})

describe('follow', () => {
  class FakeSource {
    listeners = new Map<string, (e: MessageEvent<string>) => void>()
    closed = false
    addEventListener(name: string, listener: (e: MessageEvent<string>) => void) { this.listeners.set(name, listener) }
    close() { this.closed = true }
    emit(name: string, data: string) { this.listeners.get(name)?.({ data } as MessageEvent<string>) }
  }

  it('passes each notification on with its parsed payload, ignores junk, and can be stopped', () => {
    const source = new FakeSource()
    const events: [string, unknown][] = []
    const stop = follow((name, payload) => events.push([name, payload]), (url) => {
      expect(url).toBe('/api/caixa/events')
      return source as unknown as EventSource
    })
    source.emit('job.progress', '{"job":3}')
    source.emit('job.finished', 'not json')
    source.emit('inbox.changed', '{"entries":[]}')
    expect(events).toEqual([['job.progress', { job: 3 }], ['inbox.changed', { entries: [] }]])
    stop()
    expect(source.closed).toBe(true)
  })
})
