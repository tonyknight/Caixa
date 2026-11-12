/**
 * What the Caixa pages share: the open box, the jobs, and the notices about finished jobs.
 *
 * It has no React in it. One instance is made when the plugin loads and opens the worker's event
 * stream at once, so a job that finishes while someone is elsewhere in DSH still raises its toast;
 * the pages and the toast host read it through `useSyncExternalStore` (see `hooks.ts`).
 */

import type { Api, BoxStatus, CaixaError, ImportDraft, Job, RecentBox, SessionInfo, Step } from './api.ts'

export type WorkerStatus = 'unknown' | 'running' | 'restarting' | 'failed' | 'stopped'

/** A notice about a job that has ended; its words come from the locale, so only facts are kept. */
export interface Toast {
  readonly id: number
  readonly job: number
  readonly outcome: 'done' | 'failed' | 'cancelled' | 'interrupted'
  /** `import`, or `refresh` (pages redrawn after a change to people). */
  readonly kind: string
  readonly collector: string
  readonly inserted: number
  readonly error: string | null
}

export interface State {
  readonly worker: WorkerStatus
  /** True when the worker refuses every change (`--read-only`). */
  readonly readOnly: boolean
  /** The open box; null when none is open (or the worker has none yet). */
  readonly box: BoxStatus | null
  /** True once the first look at the worker has finished, so pages do not flash "no box". */
  readonly ready: boolean
  /** Newest first. */
  readonly jobs: readonly Job[]
  /** Collector display names by id (for jobs and toasts); loaded on first use. */
  readonly names: Readonly<Record<string, string>>
  readonly toasts: readonly Toast[]
  /** Bumped when the box's Inbox folder changes, so pickers re-read it. */
  readonly inboxVersion: number
  /** Bumped when pages or people may have changed, so lists re-read themselves. */
  readonly boxVersion: number
  /** Boxes opened lately, newest first (Caixa's own memory, kept between runs). */
  readonly recent: readonly RecentBox[]
  /** The section that was open when the page last closed, for the open box; null if none. */
  readonly view: string | null
  /** The import that was being set up and not yet started; null if none. */
  readonly draft: ImportDraft | null
  /** How far the previews being watched are, by the token each was started with. */
  readonly previews: Readonly<Record<string, Step>>
}

export interface StoreOptions {
  /** How long a toast stays; 0 keeps it until dismissed. */
  readonly toastMs?: number
  /** Remember the last box across page loads (localStorage); injected so tests can use a fake. */
  readonly memory?: { get(): string | null; set(path: string | null): void }
  readonly setTimer?: (callback: () => void, ms: number) => unknown
  /** Waits a moment before saving where you are, so typing is saved once, not on every key. */
  readonly debounce?: (callback: () => void, ms: number) => unknown
}

const FINISHED = new Set(['done', 'failed', 'cancelled', 'interrupted'])

export class Store {
  private state: State = {
    worker: 'unknown', readOnly: false, box: null, ready: false, jobs: [], names: {}, toasts: [], inboxVersion: 0, boxVersion: 0, recent: [], view: null, draft: null, previews: {},
  }
  private listeners = new Set<() => void>()
  private stopFollowing: (() => void) | undefined
  private nextToast = 1
  private loadingNames: Promise<void> | undefined
  /** What is waiting to be saved (the section and/or the draft), and the timer that will save it. */
  private pending: { view?: string | null; draft?: ImportDraft | null } = {}
  private pendingTimer: unknown
  /** The box that was open last, so a worker that comes back without one can be told it again. */
  private lastRoot: string | undefined

  constructor(readonly api: Api, private readonly options: StoreOptions = {}) {}

  // --- Subscribing -------------------------------------------------------------------------

  getState = (): State => this.state

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  private set(change: Partial<State>): void {
    this.state = { ...this.state, ...change }
    for (const listener of [...this.listeners]) listener()
  }

  // --- Life ---------------------------------------------------------------------------------

  /** Open the event stream and take a first look at the worker. */
  async start(): Promise<void> {
    this.stopFollowing ??= this.api.follow((name, payload) => this.heard(name, payload))
    const info = await this.api.info()
    if (info.ok) this.set({ readOnly: info.result.read_only })
    await this.refreshBox()
    if (this.state.box === null) await this.reopenLastBox()
    await this.refreshJobs()
    await this.loadSession()
    this.set({ ready: true })
  }

  stop(): void {
    this.flushSession()
    this.stopFollowing?.()
    this.stopFollowing = undefined
  }

  // --- What is remembered between runs -----------------------------------------------------

  /** Read the recent boxes and where you were in the open box. */
  async loadSession(): Promise<void> {
    const reply = await this.api.session()
    this.applySession(reply.ok ? reply.result : undefined)
  }

  private applySession(info: SessionInfo | undefined): void {
    this.set({ recent: info?.recent ?? [], view: info?.view ?? null, draft: info?.draft ?? null })
  }

  /** The section is kept now and saved a moment later. */
  saveView(view: string | null): void {
    if (view === this.state.view) return
    this.set({ view })
    this.remember({ view })
  }

  /** The draft is kept now and saved a moment later; null clears it. */
  saveDraft(draft: ImportDraft | null): void {
    if (JSON.stringify(draft) === JSON.stringify(this.state.draft)) return
    this.set({ draft })
    this.remember({ draft })
  }

  private remember(change: { view?: string | null; draft?: ImportDraft | null }): void {
    this.pending = { ...this.pending, ...change }
    if (this.pendingTimer !== undefined) return
    this.pendingTimer = (this.options.debounce ?? setTimeout)(() => this.flushSession(), 400)
  }

  /** Send what is waiting to be saved (also when the page is closing). */
  flushSession(): void {
    this.pendingTimer = undefined
    const values = this.pending
    this.pending = {}
    if (Object.keys(values).length > 0 && this.state.box) void this.api.setSession(values)
  }

  async forgetBox(path: string): Promise<void> {
    const reply = await this.api.forgetBox(path)
    if (reply.ok) this.set({ recent: reply.result.recent })
  }

  private async reopenLastBox(): Promise<void> {
    const last = this.options.memory?.get()
    if (!last) return
    const reply = await this.api.boxOpen(last)
    if (reply.ok) this.set({ box: reply.result })
    else this.options.memory?.set(null) // it moved or was deleted: forget it
  }

  // --- Reading the worker ------------------------------------------------------------------

  async refreshBox(): Promise<void> {
    const reply = await this.api.boxStatus()
    if (reply.ok) { this.lastRoot = reply.result.root; this.set({ box: reply.result, boxVersion: this.state.boxVersion + 1 }) }
    else if (reply.error.kind === 'no_box') this.set({ box: null })
  }

  async refreshJobs(): Promise<void> {
    const reply = await this.api.jobs()
    if (!reply.ok) return
    // The list may have been asked for before a job finished and answered after the stream said so:
    // an answer that is older than what was already heard must not bring a finished job back to life.
    const heard = new Map(this.state.jobs.filter(job => FINISHED.has(job.status)).map(job => [job.id, job]))
    this.set({ jobs: reply.result.map(job => (heard.has(job.id) && !FINISHED.has(job.status) ? heard.get(job.id)! : job)) })
  }

  /** The display names of the collectors (once). */
  loadNames(): Promise<void> {
    this.loadingNames ??= this.api.collectors().then((reply) => {
      if (reply.ok) this.set({ names: Object.fromEntries(reply.result.map(c => [c.id, c.name])) })
      else this.loadingNames = undefined
    })
    return this.loadingNames
  }

  // --- Changing the box --------------------------------------------------------------------

  async createBox(path: string, name: string, owner: string): Promise<CaixaError | undefined> {
    const reply = await this.api.boxCreate(path, name, owner)
    if (!reply.ok) return reply.error
    this.options.memory?.set(reply.result.root)
    this.flushSession()
    this.set({ box: reply.result, jobs: [], boxVersion: this.state.boxVersion + 1 })
    this.lastRoot = reply.result.root
    await this.refreshJobs()
    await this.loadSession()
    return undefined
  }

  async openBox(path: string): Promise<CaixaError | undefined> {
    const reply = await this.api.boxOpen(path)
    if (!reply.ok) return reply.error
    this.options.memory?.set(reply.result.root)
    this.flushSession()
    this.set({ box: reply.result, boxVersion: this.state.boxVersion + 1 })
    this.lastRoot = reply.result.root
    await this.refreshJobs()
    await this.loadSession()
    return undefined
  }

  // --- The event stream --------------------------------------------------------------------

  private heard(name: string, payload: unknown): void {
    const data = (payload ?? {}) as Record<string, unknown>
    if (name === 'worker.state') {
      const next = String(data.state) as WorkerStatus
      const was = this.state.worker
      this.set({ worker: next })
      if (next === 'running' && was !== 'running' && this.state.ready) void this.comeBack()
    } else if (name === 'preview.progress') {
      const token = String(data.token ?? '')
      if (token) {
        this.set({ previews: { ...this.state.previews, [token]: {
          stage: String(data.stage ?? ''), current: Number(data.current ?? 0),
          total: data.total === null || data.total === undefined ? null : Number(data.total), message: String(data.message ?? ''),
        } } })
      }
    } else if (name === 'job.progress') {
      this.progress(data)
    } else if (name === 'job.finished') {
      this.finished(data as unknown as Job & { job: number })
    } else if (name === 'inbox.changed') {
      this.set({ inboxVersion: this.state.inboxVersion + 1 })
    }
  }

  /** The worker is running again: if it came back without a box, open the one that was open. */
  private async comeBack(): Promise<void> {
    const before = this.lastRoot
    await this.refreshBox()
    if (this.state.box === null && before) {
      const reply = await this.api.boxOpen(before)
      if (reply.ok) this.set({ box: reply.result, boxVersion: this.state.boxVersion + 1 })
    }
    await this.refreshJobs()
  }

  private progress(data: Record<string, unknown>): void {
    const id = Number(data.job)
    if (!this.state.jobs.some(job => job.id === id)) return void this.refreshJobs()
    this.set({
      jobs: this.state.jobs.map(job => job.id !== id ? job : {
        ...job,
        status: 'running',
        stage: String(data.stage ?? job.stage ?? ''),
        current: Number(data.current ?? 0),
        total: data.total === null || data.total === undefined ? null : Number(data.total),
        message: String(data.message ?? ''),
      }),
    })
  }

  private finished(job: Job & { job: number }): void {
    const { job: id, ...rest } = job
    const known = this.state.jobs.some(existing => existing.id === id)
    const merged = { ...rest, id } as Job
    this.set({ jobs: known ? this.state.jobs.map(existing => existing.id === id ? merged : existing) : [merged, ...this.state.jobs] })
    if (!FINISHED.has(job.status)) return
    // Redrawing pages after a change to people is routine: only its failure is worth a notice.
    if (merged.kind !== 'import' && merged.status === 'done') { this.set({ boxVersion: this.state.boxVersion + 1 }); return }
    void this.loadNames().then(() => this.toast(merged))
    void this.refreshBox() // the counts changed
  }

  private toast(job: Job): void {
    const toast: Toast = {
      id: this.nextToast++,
      job: job.id,
      outcome: job.status as Toast['outcome'],
      kind: job.kind,
      collector: (job.collector && this.state.names[job.collector]) || job.collector || '',
      inserted: job.result?.inserted ?? 0,
      error: job.error,
    }
    this.set({ toasts: [...this.state.toasts, toast] })
    const ms = this.options.toastMs ?? 10_000
    if (ms > 0) (this.options.setTimer ?? setTimeout)(() => this.dismissToast(toast.id), ms)
  }

  dismissToast = (id: number): void => {
    if (this.state.toasts.some(toast => toast.id === id)) this.set({ toasts: this.state.toasts.filter(toast => toast.id !== id) })
  }

  /** A preview has ended: its progress is no longer needed. */
  forgetPreview(token: string): void {
    if (!(token in this.state.previews)) return
    const { [token]: _gone, ...rest } = this.state.previews
    this.set({ previews: rest })
  }

  /** Tell lists to re-read (after people or pages changed). */
  touch(): void {
    this.set({ boxVersion: this.state.boxVersion + 1 })
  }

  // --- Reading what is ongoing -------------------------------------------------------------

  job(id: number): Job | undefined {
    return this.state.jobs.find(job => job.id === id)
  }
}
