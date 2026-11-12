/**
 * The browser's door to `caixa worker`: owner-only routes on DSH's own connection.
 *
 * DSH admits a request here only after its Host and Origin checks and its browser authentication,
 * and answers 403 to anyone who is not the owner, so the Python worker is never reachable except
 * through these routes.
 *
 * - `POST /api/caixa/rpc`    `{ "method": "box.status", "params": {} }` → `{ "ok": true, "result": … }`
 *                            or `{ "ok": false, "error": { "code", "message", "kind", "data" } }`
 * - `GET  /api/caixa/events` a stream (server-sent events) of the worker's notifications
 * - `GET  /api/caixa/status` `{ "worker": "running" | "restarting" | "failed" | "stopped" }`
 * - `GET|HEAD /api/caixa/box?path=…` a file of the box (see `box-files.ts`)
 */

import { ROUTE as BOX_ROUTE, serveBoxFile } from './box-files.ts'
import type { Notification, WorkerClient } from './worker-client.ts'
import { UNAVAILABLE, WorkerError } from './worker-client.ts'

export interface FetchRoute {
  readonly path: string
  readonly methods: readonly ('GET' | 'HEAD' | 'POST')[]
  readonly requestBody: 'buffered' | 'streaming'
  readonly fetch: (request: Request) => Promise<Response>
}

const METHOD_NAME = /^[a-z][a-z.]*[a-zA-Z]$/
const HEARTBEAT_MS = 15_000

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  })
}

function failure(error: WorkerError, status = 200): Response {
  return json({ ok: false, error: { code: error.code, message: error.message, kind: error.kind, data: error.data } }, status)
}

/** The routes for one worker client. */
export function caixaRoutes(client: WorkerClient, options: { shell?: boolean } = {}): FetchRoute[] {
  return [
    {
      path: '/api/caixa/rpc',
      methods: ['POST'],
      requestBody: 'buffered',
      fetch: async (request) => {
        let body: unknown
        try {
          body = await request.json()
        } catch {
          return failure(new WorkerError('The request was not valid JSON.', -32700, 'invalid_request'), 400)
        }
        const { method, params } = (body ?? {}) as { method?: unknown; params?: unknown }
        if (typeof method !== 'string' || !METHOD_NAME.test(method)) {
          return failure(new WorkerError('A request needs a method name such as "box.status".', -32600, 'invalid_request'), 400)
        }
        if (params !== undefined && (typeof params !== 'object' || params === null || Array.isArray(params))) {
          return failure(new WorkerError('Parameters must be an object.', -32602, 'invalid_params'), 400)
        }
        try {
          const result = await client.request(method, (params ?? {}) as Record<string, unknown>)
          return json({ ok: true, result })
        } catch (error) {
          if (error instanceof WorkerError) return failure(error, error.code === UNAVAILABLE ? 503 : 200)
          throw error
        }
      },
    },
    {
      path: '/api/caixa/status',
      methods: ['GET'],
      requestBody: 'buffered',
      // `shell` (only when set): the window is Caixa's own, so the page takes the name and the first view
      fetch: async () => json(options.shell ? { worker: client.status, shell: true } : { worker: client.status }),
    },
    {
      path: BOX_ROUTE,
      methods: ['GET', 'HEAD'],
      requestBody: 'buffered',
      fetch: request => serveBoxFile(client, request),
    },
    {
      path: '/api/caixa/events',
      methods: ['GET'],
      requestBody: 'buffered',
      fetch: async (request) => eventStream(client, request.signal),
    },
  ]
}

function eventStream(client: WorkerClient, signal: AbortSignal): Response {
  const encoder = new TextEncoder()
  let cleanup = () => undefined as void
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const send = (text: string) => {
        try { controller.enqueue(encoder.encode(text)) } catch { cleanup() }
      }
      const forward = (notification: Notification) => {
        send(`event: ${notification.method}\ndata: ${JSON.stringify(notification.params)}\n\n`)
      }
      const stopListening = client.onNotification(forward)
      const stopState = client.onState(state => send(`event: worker.state\ndata: ${JSON.stringify({ state })}\n\n`))
      const heartbeat = setInterval(() => send(': keep-alive\n\n'), HEARTBEAT_MS)
      cleanup = () => {
        clearInterval(heartbeat)
        stopListening()
        stopState()
        try { controller.close() } catch { /* already closed */ }
      }
      signal.addEventListener('abort', cleanup, { once: true })
      send(`event: worker.state\ndata: ${JSON.stringify({ state: client.status })}\n\n`)
    },
    cancel() { cleanup() },
  })
  return new Response(stream, {
    headers: {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-store',
      'x-accel-buffering': 'no',
    },
  })
}
