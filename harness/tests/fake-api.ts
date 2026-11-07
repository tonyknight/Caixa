import type {
  Api, BoxStatus, BrowseListing, SettingsReply, Handle, Person, PersonChange, WorkerInfo, CaixaResult, CollectorDescription, FilesListing, InboxListing, Job, JobLog,
  PreviewResult, SessionInfo, ImportDraft,
} from '../src/client/api.ts'

export const ok = <T,>(result: T): CaixaResult<T> => ({ ok: true, result })
export const fail = (kind: string, message: string): CaixaResult<never> =>
  ({ ok: false, error: { code: -32000, message, kind } })

export const BOX: BoxStatus = {
  name: 'Our box', root: '/boxes/Our box', items: 12, by_type: { text: 9, email: 3 }, people: 3, owner: 'Maria Costa',
  imports: [{ id: 1, collector: 'chattr', status: 'done', started_at: '2024-05-01T10:00:00+00:00', inserted: 12, updated: 0, unchanged: 0 }],
}

export const COLLECTORS: CollectorDescription[] = [
  {
    id: 'whatsapp', name: 'WhatsApp', platform: 'WhatsApp', inputs: ['file', 'folder', 'zip'], source: 'chattr',
    how_to_export: 'In WhatsApp, open a chat, then Export chat.',
    options_schema: { type: 'object', properties: {
      contacts: { type: 'string', default: '', title: 'Contacts file (.vcf)', description: 'A vCard export.' },
      owner: { type: 'string', default: '', title: 'Your name' },
    } },
  },
  {
    id: 'imessage', name: 'iMessage', platform: 'Apple', inputs: ['database'], source: 'chattr',
    how_to_export: 'Give the app Full Disk Access.',
    options_schema: { type: 'object', properties: {
      spam_mode: { type: 'string', default: 'aggressive', enum: ['aggressive', 'conservative', 'disabled'], title: 'Spam filtering' },
      workers: { type: 'integer', default: 4, minimum: 1, maximum: 8, title: 'Workers' },
      transcribe: { type: 'boolean', default: false, title: 'Transcribe' },
    } },
  },
]

export const job = (over: Partial<Job> = {}): Job => ({
  id: 1, kind: 'import', collector: 'whatsapp', source: '/exports/chat.txt', options: {}, status: 'done', stage: 'done',
  current: 0, total: null, message: '', result: { inserted: 7, updated: 0, unchanged: 0, pages: 2, unresolved: [], warnings: [] },
  error: null, log: '/boxes/Our box/.caixa/logs/job-1.log', created_at: '2024-05-01T10:00:00+00:00',
  started_at: '2024-05-01T10:00:01+00:00', finished_at: '2024-05-01T10:00:09+00:00', ...over,
})

/** A scriptable stand-in for the worker; every reply can be replaced and every call is recorded. */
export class FakeApi implements Api {
  calls: [string, ...unknown[]][] = []
  listener: ((name: string, payload: unknown) => void) | undefined
  followed = 0
  stopped = 0
  box: CaixaResult<BoxStatus> = ok(BOX)
  jobList: Job[] = []
  collectorList: CollectorDescription[] = COLLECTORS
  previewReply: CaixaResult<PreviewResult> = ok({ items: 7, conversations: 1, first: '2024-03-01', last: '2024-03-05', participants: ['Ana Costa'], unresolved: ['Ana Costa'], warnings: [] })
  startReply: CaixaResult<Job> = ok(job({ id: 5, status: 'queued', stage: null, result: null }))
  filesReply: (path: string | undefined) => CaixaResult<FilesListing> = path => ok({
    path: path ?? '/home/me', parent: path && path !== '/home/me' ? '/home/me' : null, roots: ['/home/me'],
    entries: [
      { name: 'Exports', path: '/home/me/Exports', kind: 'directory', size: null, modified: '2024-01-01T00:00:00+00:00' },
      { name: 'chat.zip', path: '/home/me/chat.zip', kind: 'file', size: 2048, modified: '2024-01-01T00:00:00+00:00' },
    ],
  })
  inboxReply: CaixaResult<InboxListing> = ok({ path: '/boxes/Our box/Inbox', entries: [] })
  logReply: CaixaResult<JobLog> = ok({ text: 'hello from the collector\n', size: 25, truncated: false })
  readOnly = false
  browseReply: (path: string | undefined) => CaixaResult<BrowseListing> = path => ok({
    path: path ?? '',
    entries: path === 'Messages/Ana Costa'
      ? [
          { name: 'Attachments', path: 'Messages/Ana Costa/Attachments', kind: 'directory', size: null, modified: '2024-03-01T00:00:00+00:00' },
          { name: '(2024) Ana Costa.html', path: 'Messages/Ana Costa/(2024) Ana Costa.html', kind: 'file', size: 4096, modified: '2024-03-01T00:00:00+00:00' },
          { name: 'photo.png', path: 'Messages/Ana Costa/photo.png', kind: 'file', size: 2_500_000, modified: '2024-03-01T00:00:00+00:00' },
          { name: 'voice.mp3', path: 'Messages/Ana Costa/voice.mp3', kind: 'file', size: 100, modified: '2024-03-01T00:00:00+00:00' },
          { name: 'clip.mp4', path: 'Messages/Ana Costa/clip.mp4', kind: 'file', size: 100, modified: '2024-03-01T00:00:00+00:00' },
          { name: 'doc.pdf', path: 'Messages/Ana Costa/doc.pdf', kind: 'file', size: 100, modified: '2024-03-01T00:00:00+00:00' },
        ]
      : path === 'Messages'
        ? [{ name: 'Ana Costa', path: 'Messages/Ana Costa', kind: 'directory', size: null, modified: '2024-03-01T00:00:00+00:00' }]
        : [
            { name: 'Messages', path: 'Messages', kind: 'directory', size: null, modified: '2024-03-01T00:00:00+00:00' },
            { name: 'index.html', path: 'index.html', kind: 'file', size: 800, modified: '2024-03-01T00:00:00+00:00' },
          ],
  })
  settingsReply: CaixaResult<SettingsReply> = ok(SETTINGS)
  savedSettings: Record<string, unknown>[] = []
  saveReply: ((values: Record<string, unknown>) => CaixaResult<SettingsReply>) | undefined
  peopleList: Person[] = PEOPLE
  handleList: Handle[] = HANDLES
  /** Reply to the next people change (link, rename or merge); replace to script failures. */
  changeReply: (kind: string, args: unknown[]) => CaixaResult<PersonChange> = (_kind, _args) => ok({ person: PEOPLE[2]!, job: job({ id: 9, kind: 'refresh', collector: null, source: null, status: 'queued', stage: null, result: null }) })
  sessionReply: CaixaResult<SessionInfo> = ok({ recent: [], last_box: null, box: '/boxes/Our box', view: null, draft: null })
  sessionSaved: { view?: string | null; draft?: ImportDraft | null }[] = []
  forgotten: string[] = []
  diagnosticsReply: CaixaResult<{ text: string }> = ok({ text: 'Caixa diagnostic report (2024-05-01 10:00 UTC)\n\n== Caixa ==\ncaixa 0.1.0\n' })
  generic: Record<string, (params: Record<string, unknown>) => CaixaResult<unknown>> = {}

  private record(name: string, ...args: unknown[]) { this.calls.push([name, ...args]) }
  async boxStatus() { this.record('boxStatus'); return this.box }
  async boxCreate(path: string, name: string, owner: string) { this.record('boxCreate', path, name, owner); return this.box }
  async boxOpen(path: string) { this.record('boxOpen', path); return this.box }
  async collectors() { this.record('collectors'); return ok(this.collectorList) }
  async preview(collector: string, source: string, options: Record<string, unknown>) { this.record('preview', collector, source, options); return this.previewReply }
  async startImport(collector: string, source: string, options: Record<string, unknown>) { this.record('startImport', collector, source, options); return this.startReply }
  async cancel(id: number) { this.record('cancel', id); return ok(job({ id, status: 'cancelled' })) }
  async jobs() { this.record('jobs'); return ok(this.jobList) }
  async jobLog(id: number) { this.record('jobLog', id); return this.logReply }
  async files(path?: string, showHidden?: boolean) { this.record('files', path, showHidden); return this.filesReply(path) }
  async browse(path?: string) { this.record('browse', path); return this.browseReply(path) }
  async settings() { this.record('settings'); return this.settingsReply }
  async saveSettings(values: Record<string, unknown>) {
    this.record('saveSettings', values); this.savedSettings.push(values)
    if (this.saveReply) return this.saveReply(values)
    return ok({ ...SETTINGS, values: { ...SETTINGS.values, ...values } } as SettingsReply)
  }
  async info() { this.record('info'); return ok<WorkerInfo>({ version: '0.1.0', protocol: 1, read_only: this.readOnly, methods: [] }) }
  async session() { this.record('session'); return this.sessionReply }
  async setSession(values: { view?: string | null; draft?: ImportDraft | null }) {
    this.record('setSession', values); this.sessionSaved.push(values)
    return this.sessionReply
  }
  async forgetBox(path: string) {
    this.record('forgetBox', path); this.forgotten.push(path)
    if (!this.sessionReply.ok) return this.sessionReply
    return ok({ ...this.sessionReply.result, recent: this.sessionReply.result.recent.filter(box => box.path !== path) })
  }
  async diagnostics(collector?: string, source?: string) { this.record('diagnostics', collector, source); return this.diagnosticsReply }
  async people() { this.record('people'); return ok({ people: this.peopleList }) }
  async unresolved() { this.record('unresolved'); return ok({ handles: this.handleList }) }
  async link(service: string, identifier: string, person: number | string, move?: boolean) { this.record('link', service, identifier, person, move); return this.changeReply('link', [service, identifier, person, move]) }
  async rename(person: number, name: string) { this.record('rename', person, name); return this.changeReply('rename', [person, name]) }
  async merge(source: number, target: number) { this.record('merge', source, target); return this.changeReply('merge', [source, target]) }
  async inbox() { this.record('inbox'); return this.inboxReply }
  async call<T = unknown>(method: string, params: Record<string, unknown> = {}) {
    this.record('call', method, params)
    const handler = this.generic[method]
    return (handler ? handler(params) : fail('unknown_method', `no fake for ${method}`)) as CaixaResult<T>
  }
  follow(onEvent: (name: string, payload: unknown) => void) {
    this.followed += 1
    this.listener = onEvent
    return () => { this.stopped += 1; this.listener = undefined }
  }
  emit(name: string, payload: unknown) { this.listener?.(name, payload) }
}

export const PEOPLE: Person[] = [
  { id: 1, name: 'Maria Costa', is_owner: true, aliases: 2, items: 9 },
  { id: 2, name: 'Rui Pereira', is_owner: false, aliases: 1, items: 4 },
  { id: 3, name: 'Ana A', is_owner: false, aliases: 1, items: 2 },
]

export const HANDLES: Handle[] = [
  { service: 'WhatsApp', identifier: 'Ana Costa', display_name: null, messages: 7, collector: 'whatsapp' },
  { service: 'iMessage', identifier: '+1 555 0102', display_name: 'Unknown', messages: 3, collector: 'imessage' },
]

export const SETTINGS: SettingsReply = {
  values: { 'privacy.default': 'private', 'translation.enabled': false, 'translation.endpoint': '', 'translation.model': '', 'speech.model': '', 'speech.language': '' },
  schema: { type: 'object', properties: {
    'privacy.default': { type: 'string', default: 'private', enum: ['private', 'family', 'public'], title: 'Who can see new items', description: 'Privacy given to items when first imported.' },
    'translation.enabled': { type: 'boolean', default: false, title: 'Translate with a local model', description: 'Off by default.' },
    'translation.endpoint': { type: 'string', default: '', title: 'Translation endpoint', description: 'An address on this computer.' },
    'translation.model': { type: 'string', default: '', title: 'Translation model' },
    'speech.model': { type: 'string', default: '', title: 'Speech-to-text model', 'x-picker': 'file' },
    'speech.language': { type: 'string', default: '', title: 'Speech language' },
  } },
  box: { root: '/boxes/Our box', name: 'Our box' },
}

export const settle = () => new Promise(resolve => setTimeout(resolve, 0))
