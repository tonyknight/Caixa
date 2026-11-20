import { useCallback, useEffect, useState } from 'react'
import type { Job } from '../api.ts'
import { ProgressView } from '../components/Progress.tsx'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import { MailList, useCounts, type Category, type RowTool } from './MailList.tsx'
import { Preview } from './Preview.tsx'
import { Sources } from './Sources.tsx'
import { size, sourceName, type CleanReply, type CleanWritten, type SenderRow } from './types.ts'
import css from './mail.module.css'

const DOTS: Record<string, string> = {
  lists: 'dotLists', notices: 'dotNotices', unsubscribe: 'dotUnsubscribe', spam_trash: 'dotSpam', receipts: 'dotReceipts', kept: 'dotKept',
}
const KEPT = 'kept'

/**
 * Clean mail: what cleaning an mbox would leave out, by group and sender, the senders to keep, and
 * the Cleaned mbox written beside its source. Opened in a window of its own from the import wizard.
 */
export function CleanMail() {
  const store = useStore()
  const t = useT()
  const counts = useCounts()
  const { jobs } = useCaixa()
  const [source, setSource] = useState<number | undefined>()
  const [reply, setReply] = useState<CleanReply | undefined>()
  const [view, setView] = useState('lists')
  const [failure, setFailure] = useState<string | undefined>()
  const [looking, setLooking] = useState<SenderRow | undefined>()
  const [asking, setAsking] = useState(false)
  const [writing, setWriting] = useState<number | undefined>()
  const [started, setStarted] = useState(0)

  useEffect(() => { document.title = `${t('mail.clean.title')} — Caixa` }, [t])
  useEffect(() => {
    if (!asking) return
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setAsking(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [asking])

  const answer = (result: { ok: true; result: CleanReply } | { ok: false; error: { message: string } }) => {
    if (result.ok) { setReply(result.result); setFailure(undefined) } else setFailure(result.error.message)
  }
  const open = useCallback(async (chosen: number) => {
    setSource(chosen)
    setView('lists')
    answer(await store.api.call<CleanReply>('mail.clean', { source: chosen }))
  }, [store])
  const keep = async (rows: readonly SenderRow[], on: boolean) => {
    if (source === undefined || rows.length === 0) return
    answer(await store.api.call<CleanReply>('mail.keep', { source, addresses: rows.map(r => r.address), keep: on }))
  }
  const write = async () => {
    setAsking(false)
    if (source === undefined) return
    const started = await store.api.call<Job>('mail.clean.write', { source })
    if (started.ok) { setWriting(started.result.id); setStarted(Date.now()) } else setFailure(started.error.message)
  }

  if (source === undefined || !reply) {
    return (
      <>
        <Sources title={t('mail.clean.title')} lead={t('mail.clean.lead')} verb={(name) => t('mail.sources.clean', { name })} onChoose={(id) => void open(id)} />
        {failure && <p className={css.problem} role="alert">{t('mail.failed', { message: failure })}</p>}
      </>
    )
  }

  const groups = reply.groups
  const categories: Category[] = [
    ...groups.map(group => ({
      key: group.key, label: group.label, dot: DOTS[group.key] ?? 'dotLists',
      line: `${counts.senders(group.senders)} · ${counts.mails(group.mails)} · ${size(group.size)}`,
    })),
    {
      key: KEPT, label: t('mail.kept'), dot: DOTS.kept!, dropTarget: true,
      line: `${counts.senders(reply.kept_senders.length)} · ${counts.mails(reply.kept_senders.reduce((n, r) => n + r.mails, 0))}`,
    },
  ]
  const group = groups.find(g => g.key === view)
  const rows = view === KEPT ? reply.kept_senders : group?.rows ?? []
  const junk = view !== KEPT && view !== 'receipts'
  const look: RowTool = { key: 'look', symbol: '↗', label: (row) => t('mail.look', { name: row.name }), onClick: setLooking }
  const tools: RowTool[] = view === KEPT
    ? [look, { key: 'unkeep', symbol: '↶', danger: true, label: (row) => t('mail.unkeepOne', { name: row.name }), onClick: (row) => void keep([row], false) }]
    : junk ? [look, { key: 'keep', symbol: '✓', label: (row) => t('mail.keepOne', { name: row.name }), onClick: (row) => void keep([row], true) }] : [look]
  const hint = view === KEPT ? t('mail.hint.kept') : view === 'receipts' ? t('mail.hint.receipts') : t('mail.hint.junk')
  const job = jobs.find(j => j.id === writing)
  const written = job?.status === 'done' ? (job.result as unknown as CleanWritten) : undefined
  const name = sourceName(reply.source)

  return (
    <>
      <MailList
        notice={<>
          {failure && <p className={css.problemBar} role="alert">{t('mail.failed', { message: failure })}</p>}
          {written && (
            <div className={css.written} role="status" aria-label={t('mail.written')}>
              <strong>{t('mail.written')}</strong> <code>{written.path}</code>
              <span>{t('mail.written.line', { mails: written.mails.toLocaleString('en'), left: written.left_out.toLocaleString('en'), size: size(written.left_out_size) })}</span>
            </div>
          )}
          {job && !written && job.status !== 'failed' && (
            <div className={css.writingBar}>
              <span>{t('mail.write.writing')}</span>
              <ProgressView step={job.stage ? { stage: job.stage, current: job.current, total: job.total, message: job.message ?? '' } : undefined}
                            stages={['writing', 'checking']} startedAt={started} />
            </div>
          )}
          {job?.status === 'failed' && <p className={css.problemBar} role="alert">{t('mail.failed', { message: job.error ?? '' })}</p>}
        </>}
        brand={<>{t('mail.clean.title')}<small>{name}</small><small>{reply.source.account} · {counts.mails(reply.source.mails)}</small></>}
        categories={categories}
        view={view}
        onView={setView}
        title={view === KEPT ? t('mail.kept') : group?.label ?? ''}
        hint={hint}
        rows={rows}
        tools={tools}
        selectable={view !== 'receipts'}
        onDrop={(target, chosen) => { if (target === KEPT) void keep(chosen, true) }}
        actions={(selected, done) => view === KEPT
          ? <button type="button" className={css.pill} onClick={() => { done(); void keep(selected, false) }}>{t('mail.unkeep')}</button>
          : junk ? <button type="button" className={css.pill} onClick={() => { done(); void keep(selected, true) }}>{t('mail.keep')}</button> : null}
        primary={<button type="button" className={`${css.pill} ${css.pillPrimary}`} disabled={job !== undefined && !written && job.status !== 'failed'}
                         onClick={() => setAsking(true)}>{t('mail.write')}</button>}
        quiet={looking !== undefined || asking}
      />
      {looking && <Preview source={source} sender={looking} onClose={() => setLooking(undefined)} />}
      {asking && (
        <div className={css.backdrop} onClick={() => setAsking(false)}>
          <div className={css.confirm} role="dialog" aria-modal="true" aria-labelledby="clean-ask" onClick={(event) => event.stopPropagation()}>
            <h2 id="clean-ask">{t('mail.write.ask', { mails: reply.left_out.mails.toLocaleString('en'), size: size(reply.left_out.size), senders: reply.left_out.senders.toLocaleString('en') })}</h2>
            <p>{t('mail.write.explain', { kept: reply.kept.mails.toLocaleString('en'), source: name })}</p>
            <div className={css.buttons}>
              <button type="button" className={css.button} onClick={() => setAsking(false)}>{t('mail.write.cancel')}</button>
              <button type="button" className={`${css.button} ${css.primaryButton}`} autoFocus onClick={() => void write()}>{t('mail.write.go')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
