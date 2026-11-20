import { useEffect, useState } from 'react'
import type { Job } from '../api.ts'
import { FilePicker } from '../components/FilePicker.tsx'
import { ProgressView } from '../components/Progress.tsx'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import { size, sourceName, type MailSource, type ReadResult } from './types.ts'
import css from './mail.module.css'

/**
 * Where a mail window starts: the mboxes the box has read already (choose one), or another to read,
 * with the account it comes from. Reading runs as a job; when it is done the mbox it read is chosen
 * (or, for a zip of several, the one picked from the list).
 */
export function Sources({ title, lead, verb, onChoose }: {
  title: string
  lead: string
  /** The words on a source's button ("Clean {name}"). */
  verb: (name: string) => string
  onChoose: (source: number) => void
}) {
  const store = useStore()
  const t = useT()
  const { jobs } = useCaixa()
  const [sources, setSources] = useState<readonly MailSource[] | undefined>()
  const [path, setPath] = useState('')
  const [account, setAccount] = useState('')
  const [picking, setPicking] = useState(false)
  const [job, setJob] = useState<number | undefined>()
  const [started, setStarted] = useState(0)
  const [failure, setFailure] = useState<string | undefined>()
  const [choices, setChoices] = useState<ReadResult['sources'] | undefined>()

  useEffect(() => {
    let current = true
    void store.api.call<{ sources: MailSource[] }>('mail.sources').then((reply) => {
      if (current && reply.ok) setSources(reply.result.sources.filter(s => s.status === undefined || s.status === 'read'))
    })
    return () => { current = false }
  }, [store])

  const running: Job | undefined = jobs.find(j => j.id === job)
  useEffect(() => {
    if (!running) return
    if (running.status === 'done' && running.result) {
      const read = running.result as unknown as ReadResult
      setJob(undefined)
      if (read.sources.length === 1) onChoose(read.sources[0]!.source_id)
      else setChoices(read.sources)
    } else if (running.status === 'failed' || running.status === 'cancelled' || running.status === 'interrupted') {
      setJob(undefined)
      setFailure(running.error ?? running.status)
    }
  }, [running, onChoose])

  const read = async () => {
    setFailure(undefined)
    const params: Record<string, unknown> = { source: path.trim() }
    if (account.trim()) params.account = account.trim()
    const reply = await store.api.call<Job>('mail.read', params)
    if (reply.ok) { setJob(reply.result.id); setStarted(Date.now()) }
    else setFailure(reply.error.message)
  }

  return (
    <main className={css.start}>
      <h1 className={css.startTitle}>{title}</h1>
      <p className={css.lead}>{lead}</p>
      {choices ? (
        <section className={css.panel}>
          <p>{t('mail.read.which')}</p>
          <ul className={css.sourceList}>
            {choices.map(choice => (
              <li key={choice.source_id}>
                <button type="button" className={css.sourceButton} onClick={() => onChoose(choice.source_id)}>
                  {verb(sourceName(choice))}
                </button>
                <span className={css.muted}>{t('mail.sources.line', { account: choice.account, mails: choice.mails.toLocaleString('en'), size: '' }).replace(/ · $/, '')}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <>
          <section className={css.panel}>
            <h2>{t('mail.sources.heading')}</h2>
            {sources?.length === 0 && <p className={css.muted}>{t('mail.sources.none')}</p>}
            <ul className={css.sourceList}>
              {sources?.map(source => (
                <li key={source.id}>
                  <button type="button" className={css.sourceButton} onClick={() => onChoose(source.id)}>
                    {verb(sourceName(source))}
                  </button>
                  <span className={css.muted}>{t('mail.sources.line', { account: source.account ?? '', mails: source.mails.toLocaleString('en'), size: size(source.size ?? 0) })}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className={css.panel}>
            <h2>{t('mail.read.heading')}</h2>
            <div className={css.field}>
              <label htmlFor="mail-source">{t('mail.read.source')}</label>
              <small id="mail-source-help">{t('mail.read.sourceHelp')}</small>
              <span className={css.inline}>
                <input id="mail-source" aria-describedby="mail-source-help" className={css.input} value={path} onChange={(event) => setPath(event.target.value)} />
                <button type="button" className={css.button} onClick={() => setPicking(!picking)}>{t('mail.read.choose')}</button>
              </span>
            </div>
            {picking && <FilePicker onPick={(picked) => { setPath(picked); setPicking(false) }} />}
            <div className={css.field}>
              <label htmlFor="mail-account">{t('mail.read.account')}</label>
              <small id="mail-account-help">{t('mail.read.accountHelp')}</small>
              <input id="mail-account" aria-describedby="mail-account-help" className={css.input} value={account} onChange={(event) => setAccount(event.target.value)} />
            </div>
            {failure && <p className={css.problem} role="alert">{t('mail.failed', { message: failure })}</p>}
            {running ? (
              <div className={css.progress}>
                <p>{t('mail.read.reading')}</p>
                <ProgressView step={running.stage ? { stage: running.stage, current: running.current, total: running.total, message: running.message ?? '' } : undefined}
                              stages={['reading']} startedAt={started} />
              </div>
            ) : (
              <p><button type="button" className={`${css.button} ${css.primaryButton}`} disabled={!path.trim()} onClick={() => void read()}>{t('mail.read.go')}</button></p>
            )}
          </section>
        </>
      )}
    </main>
  )
}
