/** What the mail methods of the service return (see `caixa/service.py`, "Mail"). */

export interface MailSource {
  readonly id: number
  readonly path: string
  readonly member: string
  readonly kind: string
  readonly account: string | null
  readonly status?: string
  readonly mails: number
  readonly size: number | null
  readonly parent_id?: number | null
}

/** One sender in a list: who, and how much of their mail (and the space it takes). */
export interface SenderRow {
  readonly name: string
  readonly address: string
  readonly mails: number
  readonly size: number
}

export interface CleanGroup {
  readonly key: string
  readonly label: string
  readonly senders: number
  readonly mails: number
  readonly size: number
  readonly rows: readonly SenderRow[]
}

export interface CleanReply {
  readonly source: { readonly id: number; readonly path: string; readonly member: string; readonly kind: string; readonly account: string; readonly mails: number; readonly size: number | null }
  readonly groups: readonly CleanGroup[]
  readonly left_out: { readonly senders: number; readonly mails: number; readonly size: number }
  readonly kept: { readonly senders: number; readonly mails: number }
  readonly kept_senders: readonly SenderRow[]
}

export interface PreviewMail {
  readonly position: number
  readonly date: string
  readonly offset: number | null
  readonly subject: string
  readonly recipients: readonly (readonly [string, string, string])[]
  readonly snippet: string
  readonly size: number
  readonly attachments: number
}

export interface MailMessage {
  readonly from: readonly [string, string]
  readonly to: readonly (readonly [string, string])[]
  readonly cc: readonly (readonly [string, string])[]
  readonly subject: string
  readonly date: string
  readonly text: string
  readonly attachments: readonly string[]
}

/** The result of a `mail-read` job. */
export interface ReadResult {
  readonly mails: number
  readonly sources: readonly { readonly source_id: number; readonly path: string; readonly member: string; readonly account: string; readonly mails: number; readonly reused: boolean }[]
}

/** The result of a `mail-clean` job. */
export interface CleanWritten {
  readonly path: string
  readonly source_id: number
  readonly mails: number
  readonly size: number
  readonly left_out: number
  readonly left_out_size: number
}

/** `/exports/Takeout/Mail/All mail.mbox` → `All mail.mbox` (a zip member's own name for one in a zip). */
export const sourceName = (source: { path: string; member: string }): string =>
  (source.member || source.path).split(/[\\/]/).filter(Boolean).pop() ?? source.path

/** 4200 → "4.1 KB" (sizes are counted in binary units, as file managers do). */
export function size(bytes: number): string {
  if (bytes < 1024) return `${bytes.toLocaleString('en')} bytes`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1 }
  return `${value.toLocaleString('en', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ${units[unit]}`
}

/** The browser window the mail windows open in: one, reused, beside Caixa's. */
export const MAIL_WINDOW = 'caixa-mail'

/** Open Clean mail or Sort mail in its window (the same one each time). */
export function openMailWindow(which: 'clean' | 'sort', open: (url: string, name: string) => unknown = (url, name) => window.open(url, name)): void {
  const opened = open(`/mail/${which}`, MAIL_WINDOW) as Window | null
  opened?.focus?.()
}

/** A sender in Sort mail: how they are known, how often the owner wrote to them, whether chosen. */
export interface SortRow extends SenderRow {
  readonly known_by: 'address' | 'name' | null
  readonly person: string | null
  readonly owner_wrote: number
  readonly chosen: boolean
}

export interface SortCategory {
  readonly key: string
  readonly label: string
  readonly senders: number
  readonly mails: number
  readonly size: number
  readonly rows: readonly SortRow[]
}

export interface SortReply {
  readonly source: CleanReply['source']
  readonly categories: readonly SortCategory[]
  /** What importing the chosen senders would bring. */
  readonly selection: { readonly threads: number; readonly mails: number; readonly size: number; readonly senders: number }
}

export interface OwnerAddresses {
  readonly account: string
  readonly confirmed: readonly string[]
  readonly proposed: readonly string[]
}
