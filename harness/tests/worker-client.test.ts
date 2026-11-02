import { afterEach, describe, expect, it } from 'vitest'
import { WorkerClient, WorkerError, UNAVAILABLE, type WorkerClientOptions } from '../src/host/worker-client.ts'
import { launchProcess, until } from './helpers.ts'

const clients: WorkerClient[] = []
const make = (options: WorkerClientOptions = {}, launch = launchProcess()) => {
  const client = new WorkerClient(launch, { restartDelayMs: 20, maxRestartDelayMs: 40, ...options })
  clients.push(client)
  return client
}
afterEach(async () => { await Promise.all(clients.splice(0).map(client => client.close())) })

describe('requests', () => {
  it('matches each answer to its request, even out of order', async () => {
    const client = make()
    client.start()
    const answers = await Promise.all([1, 2, 3].map(n => client.request('echo', { n })))
    expect(answers).toEqual([{ n: 1 }, { n: 2 }, { n: 3 }])
  })

  it('turns an error answer into a WorkerError that says why', async () => {
    const client = make()
    client.start()
    const error = await client.request('fail').catch(e => e)
    expect(error).toBeInstanceOf(WorkerError)
    expect(error).toMatchObject({ message: 'Nope.', code: -32000, kind: 'conflict' })
  })

  it('ignores a line that is not JSON and carries on', async () => {
    const lines: string[] = []
    const client = make({ log: m => lines.push(m) })
    client.start()
    expect(await client.request('junk')).toBe('after junk')
    expect(lines.join()).toContain('not JSON')
  })

  it('refuses to send before the worker is running', async () => {
    const error = await make().request('echo').catch(e => e)
    expect(error).toMatchObject({ code: UNAVAILABLE, kind: 'worker_unavailable' })
  })
})

describe('notifications', () => {
  it('reach every listener until it is removed', async () => {
    const client = make()
    client.start()
    const a: unknown[] = []
    const b: unknown[] = []
    const stopA = client.onNotification(n => a.push(n))
    client.onNotification(n => b.push(n))
    await client.request('notify')
    await until(() => a.length === 1 && b.length === 1)
    expect(a[0]).toEqual({ method: 'job.progress', params: { job: 1 } })
    stopA()
    await client.request('notify')
    await until(() => b.length === 2)
    expect(a).toHaveLength(1)
  })

  it('survive a listener that throws', async () => {
    const client = make()
    client.start()
    client.onNotification(() => { throw new Error('bug') })
    const heard: unknown[] = []
    client.onNotification(n => heard.push(n))
    await client.request('notify')
    await until(() => heard.length === 1)
  })
})

describe('supervision', () => {
  it('fails waiting requests with a plain error when the worker dies, then starts it again', async () => {
    const client = make()
    client.start()
    const waiting = client.request('hang').catch(e => e)
    client.request('die').catch(() => undefined)
    expect(await waiting).toMatchObject({ kind: 'worker_unavailable' })
    await until(() => client.status === 'running')
    expect(await client.request('echo', { again: true })).toEqual({ again: true })
  })

  it('opens the same box again in the new worker', async () => {
    const client = make()
    client.start()
    await client.request('box.open', { path: '/boxes/ours' })
    client.request('die').catch(() => undefined)
    await until(() => client.status === 'restarting')
    await until(() => client.status === 'running')
    let opened: unknown = []
    await until(() => {
      client.request('opened').then((o) => { opened = o }).catch(() => undefined)
      return JSON.stringify(opened) === '["/boxes/ours"]'
    })
  })

  it('gives up after repeated failures and says so', async () => {
    const lines: string[] = []
    const client = make({ maxRestarts: 2, log: m => lines.push(m) }, launchProcess([process.execPath, '-e', 'process.exit(1)']))
    client.start()
    await until(() => client.status === 'failed')
    expect(lines.join()).toContain('giving up')
  })

  it('reports a worker that cannot be started', () => {
    const lines: string[] = []
    const client = make({ log: m => lines.push(m) }, () => { throw new Error('no such program') })
    client.start()
    expect(client.status).toBe('failed')
    expect(lines.join()).toContain('no such program')
  })

  it('tells listeners about state changes', async () => {
    const client = make()
    const seen: string[] = []
    client.onState(state => seen.push(state))
    client.start()
    await client.close()
    expect(seen).toEqual(['running', 'stopped'])
  })

  it('does not restart after close, and close ends the worker', async () => {
    const client = make()
    client.start()
    await client.request('echo')
    await client.close()
    expect(client.status).toBe('stopped')
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(client.status).toBe('stopped')
  })
})

describe('the real worker', () => {
  const real = (process.env.CAIXA_COMMAND ?? 'caixa').split(' ')

  it('answers worker.info over the real protocol', async () => {
    const client = make({}, launchProcess([...real, 'worker']))
    client.start()
    const info = await client.request('worker.info') as { protocol: number; methods: string[] }
    expect(info.protocol).toBe(1)
    expect(info.methods).toContain('import.start')
  })

  it('reports its errors with the kind a page can act on', async () => {
    const client = make({}, launchProcess([...real, 'worker']))
    client.start()
    expect(await client.request('box.status').catch(e => e)).toMatchObject({ kind: 'no_box' })
  })
})
