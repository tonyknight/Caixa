import { afterEach, describe, expect, it } from 'vitest'
import { caixaRoutes, type FetchRoute } from '../src/host/routes.ts'
import { WorkerClient } from '../src/host/worker-client.ts'
import { launchProcess, until } from './helpers.ts'

const clients: WorkerClient[] = []
function setup(started = true) {
  const client = new WorkerClient(launchProcess(), { restartDelayMs: 20 })
  clients.push(client)
  if (started) client.start()
  const routes = new Map(caixaRoutes(client).map(route => [`${route.methods[0]} ${route.path}`, route]))
  const route = (key: string): FetchRoute => routes.get(key)!
  return { client, route }
}
afterEach(async () => { await Promise.all(clients.splice(0).map(client => client.close())) })

const post = (body: unknown) => new Request('http://127.0.0.1/api/caixa/rpc', {
  method: 'POST',
  body: typeof body === 'string' ? body : JSON.stringify(body),
})

describe('the route table', () => {
  it('has exactly the three routes, each under /api/caixa/', () => {
    const { route } = setup(false)
    for (const key of ['POST /api/caixa/rpc', 'GET /api/caixa/status', 'GET /api/caixa/events']) {
      expect(route(key).path.startsWith('/api/caixa/')).toBe(true)
    }
    expect(caixaRoutes(setup(false).client)).toHaveLength(3)
  })

  it('buffers request bodies (so DSH applies its size cap)', () => {
    expect(caixaRoutes(setup(false).client).every(r => r.requestBody === 'buffered')).toBe(true)
  })
})

describe('POST /api/caixa/rpc', () => {
  it('returns a result', async () => {
    const response = await setup().route('POST /api/caixa/rpc').fetch(post({ method: 'echo', params: { a: 1 } }))
    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ ok: true, result: { a: 1 } })
  })

  it('returns a worker error as data, with its kind', async () => {
    const response = await setup().route('POST /api/caixa/rpc').fetch(post({ method: 'fail' }))
    expect(response.status).toBe(200)
    expect(await response.json()).toMatchObject({ ok: false, error: { code: -32000, message: 'Nope.', kind: 'conflict' } })
  })

  it('refuses a body that is not JSON, a bad method name, and parameters that are not an object', async () => {
    const { route } = setup()
    const rpc = route('POST /api/caixa/rpc')
    for (const body of ['not json', {}, { method: 5 }, { method: '../etc' }, { method: 'a b' }, { method: 'echo', params: [1] }, { method: 'echo', params: 'x' }]) {
      const response = await rpc.fetch(post(body))
      expect(response.status, JSON.stringify(body)).toBe(400)
      expect((await response.json()).ok).toBe(false)
    }
  })

  it('says 503 when the worker is not running', async () => {
    const response = await setup(false).route('POST /api/caixa/rpc').fetch(post({ method: 'echo' }))
    expect(response.status).toBe(503)
    expect(await response.json()).toMatchObject({ ok: false, error: { kind: 'worker_unavailable' } })
  })

  it('never lets a response be cached', async () => {
    const response = await setup().route('POST /api/caixa/rpc').fetch(post({ method: 'echo' }))
    expect(response.headers.get('cache-control')).toBe('no-store')
  })
})

describe('GET /api/caixa/status', () => {
  it('reports the worker state', async () => {
    expect(await (await setup().route('GET /api/caixa/status').fetch(new Request('http://x/'))).json()).toEqual({ worker: 'running' })
    expect(await (await setup(false).route('GET /api/caixa/status').fetch(new Request('http://x/'))).json()).toEqual({ worker: 'stopped' })
  })
})

describe('GET /api/caixa/events', () => {
  async function read(response: Response, until: (text: string) => boolean): Promise<string> {
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let text = ''
    while (!until(text)) {
      const { value, done } = await reader.read()
      if (done) break
      text += decoder.decode(value)
    }
    reader.releaseLock()
    return text
  }

  it('streams the worker state and then every notification', async () => {
    const { client, route } = setup()
    const controller = new AbortController()
    const response = await route('GET /api/caixa/events').fetch(new Request('http://x/', { signal: controller.signal }))
    expect(response.headers.get('content-type')).toContain('text/event-stream')
    await client.request('notify')
    const text = await read(response, t => t.includes('job.progress'))
    expect(text).toContain('event: worker.state\ndata: {"state":"running"}')
    expect(text).toContain('event: job.progress\ndata: {"job":1}')
    controller.abort()
  })

  it('stops listening when the browser goes away', async () => {
    const { client, route } = setup()
    const controller = new AbortController()
    const response = await route('GET /api/caixa/events').fetch(new Request('http://x/', { signal: controller.signal }))
    await read(response, t => t.includes('worker.state'))
    controller.abort()
    await until(() => {
      let heard = 0
      const off = client.onNotification(() => { heard += 1 })
      off()
      return heard === 0
    })
    // a further notification must not throw into a closed stream
    await client.request('notify')
  })
})
