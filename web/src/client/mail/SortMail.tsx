import { useCallback, useEffect, useState } from 'react'
import type { CaixaResult, Person } from '../api.ts'
import { useStore, useT } from '../hooks.tsx'
import { MailList, useCounts, type Category, type RowTool } from './MailList.tsx'
import { Preview } from './Preview.tsx'
import { Sources } from './Sources.tsx'
import { size, sourceName, type OwnerAddresses, type SenderRow, type SortReply, type SortRow } from './types.ts'
import css from './mail.module.css'

const DOTS: Record<string, string> = { known: 'dotReceipts', to_sort: 'dotUnsubscribe', to_import: 'dotLists', ignored: 'dotSpam', imported: 'dotKept' }
const HINTS: Record<string, string> = { known: 'mail.hint.known', to_sort: 'mail.hint.toSort', to_import: 'mail.hint.toImport', ignored: 'mail.hint.ignored', imported: 'mail.hint.imported' }

/** The mbox named in the window's address (`/mail/sort?source=4`), if any. */
function named(): number | undefined {
  const value = Number(new URLSearchParams(window.location.search).get('source'))
  return Number.isInteger(value) && value > 0 ? value : undefined
}

/**
 * Sort mail: an mbox's senders as Known, To sort, To import, Ignored and Imported, chosen and
 * ignored the way the box's index page sorts people, with a name field for an address nobody is
 * known by, and what importing the chosen would bring.
 */
export function SortMail() {
  const store = useStore()
  const t = useT()
  const counts = useCounts()
  const [source, setSource] = useState<number | undefined>()
  const [reply, setReply] = useState<SortReply | undefined>()
  const [view, setView] = useState('known')
  const [failure, setFailure] = useState<string | undefined>()
  const [looking, setLooking] = useState<SenderRow | undefined>()
  const [naming, setNaming] = useState<string | undefined>()
  const [people, setPeople] = useState<readonly string[]>([])
  const [owner, setOwner] = useState<OwnerAddresses | undefined>()

  useEffect(() => { document.title = `${t('mail.sort.title')} — Caixa` }, [t])

  const answer = (result: CaixaResult<SortReply>) => {
    if (result.ok) { setReply(result.result); setFailure(undefined) } else setFailure(result.error.message)
  }
  const refresh = useCallback(async (chosen: number) => { answer(await store.api.call<SortReply>('mail.senders', { source: chosen })) }, [store])
  const open = useCallback(async (chosen: number) => {
    setSource(chosen)
    setView('known')
    await refresh(chosen)
    const found = await store.api.call<OwnerAddresses>('mail.owner', { source: chosen })
    if (found.ok) setOwner(found.result)
    const listed = await store.api.people()
    if (listed.ok) setPeople(listed.result.people.filter((p: Person) => !p.is_owner).map((p: Person) => p.name).sort((a: string, b: string) => a.localeCompare(b)))
  }, [store, refresh])
  useEffect(() => { const chosen = named(); if (chosen !== undefined) void open(chosen) }, [open])

  if (source === undefined || !reply) {
    return (
      <>
        <Sources title={t('mail.sort.title')} lead={t('mail.sort.lead')} verb={(name) => t('mail.sources.sort', { name })} onChoose={(id) => void open(id)} />
        {failure && <p className={css.problem} role="alert">{t('mail.failed', { message: failure })}</p>}
      </>
    )
  }

  const decide = async (method: 'mail.choose' | 'mail.ignore', rows: readonly SenderRow[], on: boolean) => {
    if (rows.length === 0) return
    const flag = method === 'mail.choose' ? 'choose' : 'ignore'
    answer(await store.api.call<SortReply>(method, { source, addresses: rows.map(r => r.address), [flag]: on }))
  }
  const choose = (rows: readonly SenderRow[]) => void decide('mail.choose', rows, true)
  const ignore = (rows: readonly SenderRow[]) => void decide('mail.ignore', rows, true)
  /** Out of To import: a known person is ignored (they are imported unless ignored); anyone else's choice is forgotten. */
  const dontImport = (rows: readonly SenderRow[]) => {
    const known = rows.filter(r => (r as SortRow).known_by === 'address')
    const others = rows.filter(r => (r as SortRow).known_by !== 'address')
    if (known.length) void decide('mail.ignore', known, true)
    if (others.length) void decide('mail.choose', others, false)
  }
  const link = async (row: SenderRow, person: string) => {
    setNaming(undefined)
    const linked = await store.api.link('Mail', row.address, person)
    if (!linked.ok) { setFailure(linked.error.message); return }
    if (!people.includes(person)) setPeople([...people, person].sort((a, b) => a.localeCompare(b)))
    await refresh(source)
  }
  const confirmOwner = async () => {
    if (!owner) return
    const saved = await store.api.call<OwnerAddresses>('mail.owner.set', { source, addresses: owner.proposed })
    if (saved.ok) { setOwner(saved.result); await refresh(source) } else setFailure(saved.error.message)
  }

  const categories: Category[] = reply.categories.map(c => ({
    key: c.key, label: c.label, dot: DOTS[c.key] ?? 'dotLists', dropTarget: c.key === 'to_import' || c.key === 'ignored',
    line: `${counts.senders(c.senders)} · ${counts.mails(c.mails)} · ${size(c.size)}`,
  }))
  const current = reply.categories.find(c => c.key === view)
  const rows = current?.rows ?? []
  const sort = (row: SenderRow) => row as SortRow
  const look: RowTool = { key: 'look', symbol: '↗', label: (row) => t('mail.look', { name: row.name }), onClick: setLooking }
  const tool = {
    choose: { key: 'choose', symbol: '✓', label: (row: SenderRow) => t('mail.chooseOne', { name: row.name }), onClick: (row: SenderRow) => choose([row]) },
    ignore: { key: 'ignore', symbol: '×', danger: true, label: (row: SenderRow) => t('mail.ignoreOne', { name: row.name }), onClick: (row: SenderRow) => ignore([row]) },
    name: { key: 'name', symbol: '✎', label: (row: SenderRow) => t('mail.nameOne', { name: row.name }), onClick: (row: SenderRow) => setNaming(row.address) },
    confirm: {
      key: 'confirm', symbol: '✓', show: (row: SenderRow) => sort(row).known_by === 'name',
      label: (row: SenderRow) => t('mail.confirmName', { person: sort(row).person ?? '', address: row.address }),
      onClick: (row: SenderRow) => void link(row, sort(row).person ?? row.name),
    },
    dontImport: { key: 'out', symbol: '×', danger: true, label: (row: SenderRow) => t('mail.dontImportOne', { name: row.name }), onClick: (row: SenderRow) => dontImport([row]) },
    unignore: { key: 'back', symbol: '↶', label: (row: SenderRow) => t('mail.unignoreOne', { name: row.name }), onClick: (row: SenderRow) => void decide('mail.ignore', [row], false) },
  }
  const tools: Record<string, RowTool[]> = {
    known: [tool.confirm, tool.ignore, look],
    to_sort: [tool.choose, tool.name, tool.ignore, look],
    to_import: [tool.dontImport, look],
    ignored: [tool.unignore, look],
    imported: [look],
  }
  const pill = (label: string, act: () => void, done: () => void) =>
    <button type="button" className={css.pill} onClick={() => { done(); act() }}>{label}</button>
  const note = (row: SenderRow) => {
    const r = sort(row)
    const parts = [
      r.known_by === 'address' ? t('mail.note.known') : r.known_by === 'name' ? t('mail.note.byName', { person: r.person ?? '' }) : '',
      r.owner_wrote ? t('mail.note.wrote', { count: r.owner_wrote }) : '',
    ].filter(Boolean)
    return parts.length ? parts.join(' · ') : undefined
  }
  const picked = reply.selection
  const conversations = picked.threads === 1 ? t('mail.count.conversation') : t('mail.count.conversations', { count: picked.threads.toLocaleString('en') })
  const unconfirmed = owner && owner.confirmed.length === 0 && owner.proposed.length > 0

  return (
    <>
      <MailList
        notice={<>
          {failure && <p className={css.problemBar} role="alert">{t('mail.failed', { message: failure })}</p>}
          {unconfirmed && (
            <section className={css.ownerBar} aria-label={t('mail.owner.region')}>
              <span>{t('mail.owner.text', { addresses: owner.proposed.join(', '), account: owner.account })}</span>
              <button type="button" className={`${css.pill} ${css.pillPrimary}`} onClick={() => void confirmOwner()}>{t('mail.owner.confirm')}</button>
            </section>
          )}
        </>}
        brand={<>{t('mail.sort.title')}<small>{sourceName(reply.source)}</small><small>{reply.source.account} · {counts.mails(reply.source.mails)}</small></>}
        categories={categories}
        view={view}
        onView={(key) => { setView(key); setNaming(undefined) }}
        title={current?.label ?? ''}
        hint={t((HINTS[view] ?? 'mail.hint.known') as never)}
        rows={rows}
        tools={tools[view] ?? [look]}
        note={note}
        naming={naming ? { address: naming, suggestions: people, onApply: (row, name) => void link(row, name), onCancel: () => setNaming(undefined) } : undefined}
        selectable={view !== 'imported'}
        onDrop={(target, chosen) => { if (target === 'to_import') choose(chosen); else if (target === 'ignored') ignore(chosen) }}
        onDelete={view === 'to_sort' || view === 'known' ? ignore : undefined}
        actions={(selected, done) => (
          view === 'to_sort' ? <>{pill(t('mail.choose'), () => choose(selected), done)}{pill(t('mail.ignore'), () => ignore(selected), done)}</>
            : view === 'known' ? pill(t('mail.ignore'), () => ignore(selected), done)
              : view === 'to_import' ? pill(t('mail.dontImport'), () => dontImport(selected), done)
                : view === 'ignored' ? pill(t('mail.unignore'), () => void decide('mail.ignore', selected, false), done) : null
        )}
        primary={<span className={css.bring}>{t('mail.bring', { mails: counts.mails(picked.mails), threads: conversations, size: size(picked.size) })}</span>}
        quiet={looking !== undefined || naming !== undefined}
      />
      {looking && <Preview source={source} sender={looking} onClose={() => setLooking(undefined)} />}
    </>
  )
}
