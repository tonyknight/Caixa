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
  const names = ['job.progress', 'job.finished', 'preview.progress', 'inbox.changed', 'worker.state']
  for (const name of names) {
    source.addEventListener(name, (event) => {
      let payload: unknown
      try { payload = JSON.parse((event as MessageEvent<string>).data) } catch { return }
      onEvent(name, payload)
    })
  }
  return () => source.close()
}

// --- What the worker returns (see caixa/service.py) -------------------------------------------

export interface ImportRecord {
  readonly id: number
  readonly collector: string
  readonly status: string
  readonly started_at: string
  readonly inserted: number
  readonly updated: number
  readonly unchanged: number
}

export interface BoxStatus {
  readonly name: string
  readonly root: string
  readonly items: number
  readonly by_type: Readonly<Record<string, number>>
  readonly people: number
  readonly owner: string | null
  readonly imports: readonly ImportRecord[]
}

/** One property of a collector's options JSON Schema (the subset the worker validates). */
export interface OptionSpec {
  readonly type?: 'string' | 'integer' | 'number' | 'boolean'
  readonly default?: string | number | boolean
  readonly enum?: readonly (string | number)[]
  readonly minimum?: number
  readonly maximum?: number
  readonly title?: string
  readonly description?: string
  /** The option is a file on this computer: the form offers to browse for it. */
  readonly 'x-picker'?: 'file'
}

export interface OptionsSchema {
  readonly type: 'object'
  readonly properties: Readonly<Record<string, OptionSpec>>
}

export interface CollectorDescription {
  readonly id: string
  readonly name: string
  readonly platform: string
  readonly inputs: readonly string[]
  readonly how_to_export: string
  readonly options_schema: OptionsSchema
  readonly source: string
}

export interface PreviewResult {
  readonly items: number
  readonly conversations: number
  readonly first: string | null
  readonly last: string | null
  readonly participants: readonly string[]
  readonly unresolved: readonly string[]
  readonly warnings: readonly string[]
}

/** How far a preview or an import is. */
export interface Step {
  readonly stage: string
  readonly current: number
  readonly total: number | null
  readonly message: string
}

export interface ImportResult {
  readonly inserted: number
  readonly updated: number
  readonly unchanged: number
  readonly pages: number
  readonly unresolved: readonly string[]
  readonly warnings: readonly string[]
  /** True once this import has been undone. */
  readonly undone?: boolean
}

/** The import that can be undone now (the newest), or why none can. */
export interface UndoInfo {
  readonly job: number | null
  readonly collector?: string
  readonly source?: string
  readonly taken?: string
  readonly people_changes?: number
  readonly reason: string | null
}

export type JobStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrupted'

export interface Job {
  readonly id: number
  readonly kind: string
  readonly collector: string | null
  readonly source: string | null
  readonly options: Readonly<Record<string, unknown>>
  readonly status: JobStatus
  readonly stage: string | null
  readonly current: number
  readonly total: number | null
  readonly message: string | null
  readonly result: ImportResult | null
  readonly error: string | null
  readonly log: string | null
  readonly created_at: string
  readonly started_at: string | null
  readonly finished_at: string | null
}

export interface FileEntry {
  readonly name: string
  readonly path: string
  readonly kind: 'file' | 'directory'
  readonly size: number | null
  readonly modified: string
  readonly absolute?: string
}

export interface FilesListing {
  readonly path: string
  readonly parent: string | null
  readonly roots: readonly string[]
  readonly entries: readonly FileEntry[]
}

export interface InboxListing {
  readonly path: string
  readonly entries: readonly FileEntry[]
}

export interface JobLog {
  readonly text: string
  readonly size: number
  readonly truncated: boolean
}

export interface Person {
  readonly id: number
  readonly name: string
  readonly is_owner: boolean
  readonly aliases: number
  readonly items: number
}

/** A number, address or name that no person is known for yet. */
export interface Handle {
  readonly service: string
  readonly identifier: string
  readonly display_name: string | null
  readonly messages: number
  readonly collector: string
}

/** What a change to people returns: the person as they now are, and the job that redraws pages. */
export interface PersonChange {
  readonly person: Person
  readonly job: Job | null
}

export interface WorkerInfo {
  readonly version: string
  readonly protocol: number
  readonly read_only: boolean
  readonly methods: readonly string[]
}

export interface BrowseListing {
  readonly path: string
  readonly entries: readonly FileEntry[]
}

export interface SettingsReply {
  readonly values: Readonly<Record<string, string | number | boolean>>
  readonly schema: OptionsSchema
  readonly box: { readonly root: string; readonly name: string }
}

/** A box opened lately (from Caixa's own memory, not from the box). */
export interface RecentBox {
  readonly path: string
  readonly name: string
  readonly opened: string | null
  /** False when the folder is no longer there. */
  readonly exists: boolean
}

/** The unfinished import: which source, how far through the steps, what was typed and chosen. */
export interface ImportDraft {
  readonly collector: string
  readonly step: string
  readonly source: string
  readonly values: Readonly<Record<string, string | boolean>>
}

/** What is remembered between runs: boxes, and where you were in the open one. */
export interface SessionInfo {
  readonly recent: readonly RecentBox[]
  readonly last_box: string | null
  readonly box: string | null
  readonly view: string | null
  readonly draft: ImportDraft | null
}

/** Where the host serves a file of the box (see src/host/box-files.ts). */
export const boxUrl = (path: string): string => `/api/caixa/box?path=${encodeURIComponent(path)}`

/** The worker, as the pages use it. Every method resolves to a result; none throws. */
export interface Api {
  boxStatus(): Promise<CaixaResult<BoxStatus>>
  boxCreate(path: string, name: string, owner: string): Promise<CaixaResult<BoxStatus>>
  boxOpen(path: string): Promise<CaixaResult<BoxStatus>>
  collectors(): Promise<CaixaResult<CollectorDescription[]>>
  /** With a `token`, the preview's progress is announced (`preview.progress`) and it can be cancelled. */
  preview(collector: string, source: string, options: Record<string, unknown>, token?: string): Promise<CaixaResult<PreviewResult>>
  cancelPreview(token: string): Promise<CaixaResult<{ cancelled: boolean }>>
  undoInfo(): Promise<CaixaResult<UndoInfo>>
  /** Undo the newest import (runs as a job). */
  undo(): Promise<CaixaResult<Job>>
  /** Run an earlier import again, with the same source and options. */
  again(job: number): Promise<CaixaResult<Job>>
  startImport(collector: string, source: string, options: Record<string, unknown>): Promise<CaixaResult<Job>>
  cancel(job: number): Promise<CaixaResult<Job>>
  jobs(limit?: number): Promise<CaixaResult<Job[]>>
  jobLog(job: number): Promise<CaixaResult<JobLog>>
  files(path?: string, showHidden?: boolean): Promise<CaixaResult<FilesListing>>
  inbox(): Promise<CaixaResult<InboxListing>>
  browse(path?: string): Promise<CaixaResult<BrowseListing>>
  settings(): Promise<CaixaResult<SettingsReply>>
  saveSettings(values: Record<string, unknown>): Promise<CaixaResult<SettingsReply>>
  info(): Promise<CaixaResult<WorkerInfo>>
  session(): Promise<CaixaResult<SessionInfo>>
  /** Keep the section (`view`) and/or the import `draft` (null clears it) for the open box. */
  setSession(values: { view?: string | null; draft?: ImportDraft | null }): Promise<CaixaResult<SessionInfo>>
  forgetBox(path: string): Promise<CaixaResult<SessionInfo>>
  /** A text report to paste when something does not work; with a source, it checks that source. */
  diagnostics(collector?: string, source?: string): Promise<CaixaResult<{ text: string }>>
  people(): Promise<CaixaResult<{ people: Person[] }>>
  unresolved(): Promise<CaixaResult<{ handles: Handle[] }>>
  link(service: string, identifier: string, person: number | string, move?: boolean): Promise<CaixaResult<PersonChange>>
  rename(person: number, name: string): Promise<CaixaResult<PersonChange>>
  merge(source: number, target: number): Promise<CaixaResult<PersonChange>>
  /** Any worker method, for the pages that need one the wrappers above do not cover. */
  call<T = unknown>(method: string, params?: Record<string, unknown>): Promise<CaixaResult<T>>
  /** Follow the worker's notifications; returns the function that stops following. */
  follow(onEvent: (name: string, payload: unknown) => void): () => void
}

export function makeApi(fetcher: typeof fetch = fetch, makeSource?: (url: string) => EventSource): Api {
  const run = <T,>(method: string, params: Record<string, unknown> = {}) => call<T>(method, params, fetcher)
  return {
    boxStatus: () => run('box.status'),
    boxCreate: (path, name, owner) => run('box.create', { path, name, owner }),
    boxOpen: path => run('box.open', { path }),
    collectors: () => run('collectors.list'),
    preview: (collector, source, options, token) => run('import.preview', token ? { collector, source, options, token } : { collector, source, options }),
    cancelPreview: token => run('import.preview.cancel', { token }),
    undoInfo: () => run('import.undo.info'),
    undo: () => run('import.undo'),
    again: job => run('import.again', { job }),
    startImport: (collector, source, options) => run('import.start', { collector, source, options }),
    cancel: job => run('import.cancel', { job }),
    jobs: (limit = 100) => run('jobs.list', { limit }),
    jobLog: job => run('jobs.log', { job }),
    files: (path, showHidden = false) => run('files.list', path === undefined ? { show_hidden: showHidden } : { path, show_hidden: showHidden }),
    inbox: () => run('inbox.list'),
    browse: path => run('browse.list', path === undefined ? {} : { path }),
    settings: () => run('settings.get'),
    saveSettings: values => run('settings.set', { values }),
    info: () => run('worker.info'),
    session: () => run('session.get'),
    setSession: values => run('session.set', { values }),
    forgetBox: path => run('session.forget', { path }),
    diagnostics: (collector, source) => run('diagnostics.report', collector && source ? { collector, source } : {}),
    people: () => run('people.list'),
    unresolved: () => run('people.unresolved'),
    link: (service, identifier, person, move = false) => run('people.link', { service, identifier, person, move }),
    rename: (person, name) => run('people.rename', { person, name }),
    merge: (source, target) => run('people.merge', { source, target }),
    call: run,
    follow: onEvent => follow(onEvent, makeSource),
  }
}
