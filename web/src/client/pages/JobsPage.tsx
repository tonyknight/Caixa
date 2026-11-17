import { useEffect, useState } from 'react'
import type { Job, JobLog, UndoInfo } from '../api.ts'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import css from '../caixa.module.css'

const ACTIVE = new Set(['queued', 'running'])

function Log({ job }: { job: Job }) {
  const store = useStore()
  const t = useT()
  const [log, setLog] = useState<JobLog | undefined>()
  // Re-read while the job runs (its stage changes) and once more when it ends.
  useEffect(() => {
    let current = true
    void store.api.jobLog(job.id).then((reply) => { if (current && reply.ok) setLog(reply.result) })
    return () => { current = false }
  }, [store, job.id, job.status, job.stage])
  if (!log) return <p className={css.muted}>{t('jobs.log.loading')}</p>
  return (
    <>
      {log.truncated && <p className={css.muted}>{t('jobs.log.truncated')}</p>}
      {log.text.trim() === '' ? <p className={css.muted}>{t('jobs.log.empty')}</p> : <pre className={css.log} tabIndex={0}>{log.text}</pre>}
    </>
  )
}

function Details({ job }: { job: Job }) {
  const t = useT()
  const options = Object.entries(job.options)
  return (
    <div className={css.card} role="region" aria-label={t('jobs.details', { id: job.id })}>
      <h3>{t('jobs.details', { id: job.id })}</h3>
      <p>{job.source}</p>
      {options.length > 0 && <><h3>{t('jobs.options')}</h3><ul>{options.map(([name, value]) => <li key={name}>{name}: {String(value)}</li>)}</ul></>}
      {job.result && <><h3>{t('jobs.result')}</h3><p>{t('import.report.counts', { inserted: job.result.inserted, updated: job.result.updated, unchanged: job.result.unchanged })}</p></>}
      {job.error && <div className={css.error} role="alert"><strong>{t('jobs.error')}</strong><br />{job.error}</div>}
      <h3>{t('jobs.log')}</h3>
      <Log job={job} />
    </div>
  )
}

/** Running and finished imports, with cancel and each job's log. */
/** The newest import, with a way to take it back (asked twice: it removes things). */
function UndoLast() {
  const { jobs, names, readOnly, boxVersion } = useCaixa()
  const store = useStore()
  const t = useT()
  const [info, setInfo] = useState<UndoInfo | undefined>()
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState<string | undefined>()
  const busy = jobs.some(job => ACTIVE.has(job.status))
  const finished = jobs.filter(job => !ACTIVE.has(job.status)).length
  useEffect(() => {
    let current = true
    void store.api.undoInfo().then((reply) => { if (current && reply.ok) setInfo(reply.result) })
    return () => { current = false }
  }, [store, finished, boxVersion])
  if (!info || info.job === null || readOnly) return null
  const undo = async () => {
    setAsking(false)
    const reply = await store.api.undo()
    setNote(reply.ok ? t('undo.started') : t('undo.failed', { message: reply.error.message }))
    if (reply.ok) void store.refreshJobs()
  }
  return (
    <div className={css.card} role="region" aria-label={t('undo.heading')}>
      <h3>{t('undo.heading')}</h3>
      <p>{t('undo.what', { job: info.job, name: (info.collector && names[info.collector]) || info.collector || '', source: info.source ?? '' })}</p>
      <p className={css.muted}>{t('undo.lead')}</p>
      {(info.people_changes ?? 0) > 0 && <p className={css.banner}>{t('undo.people', { count: info.people_changes ?? 0 })}</p>}
      {note && <p role="status">{note}</p>}
      <div className={css.actions}>
        {asking ? (
          <>
            <button type="button" className={`${css.button} ${css.primary}`} onClick={() => void undo()}>{t('undo.confirm')}</button>
            <button type="button" className={css.button} onClick={() => setAsking(false)}>{t('undo.keep')}</button>
          </>
        ) : <button type="button" className={css.button} disabled={busy} onClick={() => { setNote(undefined); setAsking(true) }}>{t('undo.start')}</button>}
      </div>
    </div>
  )
}

export function JobsPage({ selected, onSelect }: { selected: number | undefined; onSelect: (job: number | undefined) => void }) {
  const { jobs, names, readOnly } = useCaixa()
  const store = useStore()
  const t = useT()
  useEffect(() => { void store.loadNames(); void store.refreshJobs() }, [store])
  const current = jobs.find(job => job.id === selected)

  return (
    <div className={css.section}>
      <h2>{t('jobs.heading')}</h2>
      <UndoLast />
      {jobs.length === 0 ? <p className={css.muted}>{t('jobs.none')}</p> : (
        <table className={css.table}>
          <thead><tr><th>#</th><th>{t('jobs.source')}</th><th>{t('jobs.status')}</th><th>{t('jobs.started')}</th><th /></tr></thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.kind === 'import' ? ((job.collector && names[job.collector]) || job.collector) : t(`jobs.kind.${job.kind}` as CaixaKey)}<br /><span className={css.muted}>{job.source}</span></td>
                <td>
                  <span className={css.badge}>{t(`status.${job.status}` as CaixaKey)}</span>
                  {job.result?.undone && <> <span className={css.badge}>{t('jobs.undone')}</span></>}
                  {job.status === 'running' && job.stage && <><br /><span className={css.muted}>{t(`stage.${job.stage}` as CaixaKey)}{job.message ? ` — ${job.message}` : ''}</span></>}
                </td>
                <td>{job.started_at ? new Date(job.started_at).toLocaleString() : ''}</td>
                <td>
                  <button type="button" className={css.link} onClick={() => onSelect(job.id === selected ? undefined : job.id)} aria-expanded={job.id === selected}>
                    {t('jobs.select')}<span className="sr-only"> {job.id}</span>
                  </button>
                  {ACTIVE.has(job.status) && <> <button type="button" className={css.link} onClick={() => void store.api.cancel(job.id)}>{t('jobs.cancel')}</button></>}
                  {job.kind === 'import' && !ACTIVE.has(job.status) && !readOnly && (
                    <> <button type="button" className={css.link} onClick={() => void store.api.again(job.id).then(() => store.refreshJobs())}>{t('jobs.again')}<span className="sr-only"> {job.id}</span></button></>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {current && <Details job={current} />}
    </div>
  )
}
