/** The browser's side of `/api/caixa/*`: plain `fetch` to the owner-only routes (same origin, with DSH's cookie). */

export interface CaixaError {
  readonly code: number
  readonly message: string
  readonly kind: string
  readonly data?: unknown
}

export type CaixaResult<T> = { readonly ok: true; readonly result: T } | { readonly ok: false; readonly error: CaixaError }

export type WorkerState = 'running' | 'restarting' | 'failed' | 'stopped'

const unreachable = (message: string): CaixaResult<never> => ({
  ok: false,
  error: { code: -32001, message, kind: 'worker_unavailable' },
})

/** Call a worker method; a network failure is reported as `worker_unavailable`, never thrown. */
export async function call<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
  fetcher: typeof fetch = fetch,
): Promise<CaixaResult<T>> {
  try {
    const response = await fetcher('/api/caixa/rpc', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ method, params }),
      credentials: 'same-origin',
    })
    return (await response.json()) as CaixaResult<T>
  } catch {
    return unreachable('Caixa could not be reached.')
  }
}

/** The worker's state as the host plugin sees it. */
export async function workerState(fetcher: typeof fetch = fetch): Promise<WorkerState> {
  try {
    const response = await fetcher('/api/caixa/status', { credentials: 'same-origin' })
    const body = (await response.json()) as { worker?: WorkerState }
    return body.worker ?? 'stopped'
  } catch {
    return 'stopped'
  }
}

/** Follow the worker's notifications; returns the function that stops following. */
export function follow(
  onEvent: (name: string, payload: unknown) => void,
  make: (url: string) => EventSource = url => new EventSource(url),
): () => void {
  const source = make('/api/caixa/events')
  const names = ['job.progress', 'job.finished', 'inbox.changed', 'worker.state']
  for (const name of names) {
    source.addEventListener(name, (event) => {
      let payload: unknown
      try { payload = JSON.parse((event as MessageEvent<string>).data) } catch { return }
      onEvent(name, payload)
    })
  }
  return () => source.close()
}
