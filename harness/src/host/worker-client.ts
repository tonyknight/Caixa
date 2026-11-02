/**
 * A client for `caixa worker`: JSON-RPC 2.0 over a child process's standard input and output, one
 * JSON object per line (the protocol is described at the top of `caixa/worker.py`).
 *
 * The client owns the supervision a long-lived helper needs: it matches responses to requests,
 * passes the worker's notifications on, answers every waiting request with a plain error if the
 * worker dies, and starts it again with a growing pause. If a person had opened a box, it opens
 * the same box again in the new worker.
 *
 * How the process is started is injected (`launch`), so the host plugin uses DSH's subprocess
 * service and the tests use a plain child process.
 */

import { createInterface } from 'node:readline'
import type { Readable, Writable } from 'node:stream'

/** What the client needs of a started worker. */
export interface WorkerProcess {
  readonly stdin: Writable
  readonly stdout: Readable
  /** Resolves when the process has exited; never rejects. */
  readonly done: Promise<unknown>
  /** Ask the process to stop. */
  stop(): void
}

export interface Notification {
  readonly method: string
  readonly params: unknown
}

export type WorkerState = 'stopped' | 'running' | 'restarting' | 'failed'

/** An error from the worker, or from reaching it; `kind` says why in a word. */
export class WorkerError extends Error {
  constructor(
    message: string,
    readonly code: number,
    readonly kind: string,
    readonly data?: unknown,
  ) {
    super(message)
    this.name = 'WorkerError'
  }
}

/** The JSON-RPC code for "the worker could not be reached" (outside the worker's own codes). */
export const UNAVAILABLE = -32001

export interface WorkerClientOptions {
  /** Pause before the first restart, doubling up to `maxRestartDelayMs`. */
  readonly restartDelayMs?: number
  readonly maxRestartDelayMs?: number
  /** Give up after this many restarts in a row without a stable run. */
  readonly maxRestarts?: number
  /** A run this long counts as stable and resets the restart count. */
  readonly stableAfterMs?: number
  /** Called with each problem worth logging (never a request's content). */
  readonly log?: (message: string) => void
}

interface Pending {
  readonly resolve: (value: unknown) => void
  readonly reject: (error: WorkerError) => void
}

export class WorkerClient {
  private process: WorkerProcess | undefined
  private state: WorkerState = 'stopped'
  private nextId = 1
  private pending = new Map<number, Pending>()
  private listeners = new Set<(notification: Notification) => void>()
  private stateListeners = new Set<(state: WorkerState) => void>()
  private closed = false
  private restarts = 0
  private restartTimer: ReturnType<typeof setTimeout> | undefined
  private stableTimer: ReturnType<typeof setTimeout> | undefined
  private lastBox: string | undefined
  private readonly options: Required<Omit<WorkerClientOptions, 'log'>> & Pick<WorkerClientOptions, 'log'>

  constructor(
    private readonly launch: () => WorkerProcess,
    options: WorkerClientOptions = {},
  ) {
    this.options = {
      restartDelayMs: options.restartDelayMs ?? 1000,
      maxRestartDelayMs: options.maxRestartDelayMs ?? 30_000,
      maxRestarts: options.maxRestarts ?? 5,
      stableAfterMs: options.stableAfterMs ?? 10_000,
      log: options.log,
    }
  }

  get status(): WorkerState {
    return this.state
  }

  /** Start the worker; calling it again while running does nothing. */
  start(): void {
    if (this.closed || this.process) return
    let started: WorkerProcess
    try {
      started = this.launch()
    } catch (error) {
      this.options.log?.(`could not start the Caixa worker: ${String(error)}`)
      this.setState('failed')
      return
    }
    this.process = started
    this.setState('running')
    createInterface({ input: started.stdout }).on('line', line => this.receive(line))
    started.stdin.on('error', () => undefined) // a closed pipe is reported through `done`
    this.stableTimer = setTimeout(() => { this.restarts = 0 }, this.options.stableAfterMs)
    this.stableTimer.unref?.()
    void started.done.then(() => this.exited(started))
    if (this.lastBox !== undefined) {
      this.request('box.open', { path: this.lastBox }).catch(() => undefined)
    }
  }

  private setState(state: WorkerState): void {
    this.state = state
    for (const listener of this.stateListeners) listener(state)
  }

  private receive(line: string): void {
    let message: Record<string, unknown>
    try {
      message = JSON.parse(line) as Record<string, unknown>
    } catch {
      this.options.log?.('the Caixa worker sent a line that was not JSON')
      return
    }
    if (typeof message !== 'object' || message === null) return
    if (typeof message.id === 'number' && this.pending.has(message.id)) {
      const waiting = this.pending.get(message.id)
      this.pending.delete(message.id)
      const error = message.error as { code?: number; message?: string; data?: { kind?: string } } | undefined
      if (error) {
        waiting?.reject(new WorkerError(
          error.message ?? 'The Caixa worker reported an error.',
          error.code ?? -32603,
          error.data?.kind ?? 'error',
          error.data,
        ))
      } else {
        waiting?.resolve(message.result)
      }
      return
    }
    if (typeof message.method === 'string' && !('id' in message)) {
      const notification: Notification = { method: message.method, params: message.params }
      for (const listener of this.listeners) {
        try { listener(notification) } catch { /* a listener's bug must not stop the others */ }
      }
    }
  }

  private exited(which: WorkerProcess): void {
    if (this.process !== which) return
    this.process = undefined
    clearTimeout(this.stableTimer)
    const unavailable = () => new WorkerError('The Caixa worker stopped.', UNAVAILABLE, 'worker_unavailable')
    for (const waiting of this.pending.values()) waiting.reject(unavailable())
    this.pending.clear()
    if (this.closed) return this.setState('stopped')
    if (this.restarts >= this.options.maxRestarts) {
      this.options.log?.('the Caixa worker keeps stopping; giving up')
      return this.setState('failed')
    }
    const delay = Math.min(this.options.restartDelayMs * 2 ** this.restarts, this.options.maxRestartDelayMs)
    this.restarts += 1
    this.setState('restarting')
    this.restartTimer = setTimeout(() => this.start(), delay)
    this.restartTimer.unref?.()
  }

  /**
   * Call a worker method.
   * @returns the method's result.
   * @throws {WorkerError} with the worker's `kind`, or `worker_unavailable` when it cannot be reached.
   */
  request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    const target = this.process
    if (!target || this.state !== 'running') {
      return Promise.reject(new WorkerError('The Caixa worker is not running.', UNAVAILABLE, 'worker_unavailable'))
    }
    const id = this.nextId++
    return new Promise<unknown>((resolve, reject) => {
      this.pending.set(id, {
        resolve: (value) => {
          if ((method === 'box.open' || method === 'box.create') && typeof params.path === 'string') {
            this.lastBox = params.path
          }
          resolve(value)
        },
        reject,
      })
      const line = JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n'
      target.stdin.write(line, (error) => {
        if (error) {
          this.pending.delete(id)
          reject(new WorkerError('The Caixa worker could not be written to.', UNAVAILABLE, 'worker_unavailable'))
        }
      })
    })
  }

  /** Be told about the worker's notifications (`job.progress`, `job.finished`, `inbox.changed`). */
  onNotification(listener: (notification: Notification) => void): () => void {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  onState(listener: (state: WorkerState) => void): () => void {
    this.stateListeners.add(listener)
    return () => { this.stateListeners.delete(listener) }
  }

  /** Stop the worker for good: no restart, waiting requests fail. */
  async close(): Promise<void> {
    this.closed = true
    clearTimeout(this.restartTimer)
    clearTimeout(this.stableTimer)
    const running = this.process
    if (!running) return this.setState('stopped')
    running.stdin.end() // the worker cancels unfinished jobs and exits when its input closes
    const forced = setTimeout(() => running.stop(), 5000)
    forced.unref?.()
    await running.done
    clearTimeout(forced)
  }
}
