import { useEffect, useMemo, useState } from 'react'
import type { CollectorDescription, Job, PreviewResult } from '../api.ts'
import { FilePicker, InboxList } from '../components/FilePicker.tsx'
import { OptionsForm } from '../components/OptionsForm.tsx'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import { fields as formFields, initialValues, toOptions, type FormValues } from '../options-form.ts'
import css from '../caixa.module.css'

type Step = 'source' | 'export' | 'input' | 'options' | 'preview' | 'run'
const STEPS: Step[] = ['source', 'export', 'input', 'options', 'preview', 'run']

/** The import wizard: source → how to export → choose → options → preview → run → report. */
export function ImportPage({ onShowJob, onShowPeople }: { onShowJob: (job: number) => void; onShowPeople: () => void }) {
  const { box, readOnly } = useCaixa()
  const store = useStore()
  const t = useT()
  const [collectors, setCollectors] = useState<CollectorDescription[] | undefined>()
  const [step, setStep] = useState<Step>('source')
  const [collector, setCollector] = useState<CollectorDescription | undefined>()
  const [source, setSource] = useState('')
  const [values, setValues] = useState<FormValues>({})
  const [jobId, setJobId] = useState<number | undefined>()

  useEffect(() => {
    let current = true
    void store.api.collectors().then((reply) => { if (current && reply.ok) setCollectors(reply.result) })
    return () => { current = false }
  }, [store])

  const fields = useMemo(() => collector ? formFields(collector.options_schema) : [], [collector])
  const reset = () => { setStep('source'); setCollector(undefined); setSource(''); setJobId(undefined) }

  if (!box) return <p className={css.banner}>{t('import.needBox')}</p>
  if (readOnly) return <p className={css.banner}>{t('import.readOnly')}</p>

  const choose = (picked: CollectorDescription) => {
    setCollector(picked)
    setValues(initialValues(formFields(picked.options_schema)))
    setStep('export')
  }

  return (
    <div className={css.section}>
      <h2>{t('import.heading')}</h2>
      <ol className={css.steps} aria-label={t('import.steps')}>
        {STEPS.map((name, index) => (
          <li key={name} className={`${css.step} ${name === step ? css.stepCurrent : STEPS.indexOf(step) > index ? css.stepDone : ''}`}
              aria-current={name === step ? 'step' : undefined}>
            {t(`import.step.${name}` as CaixaKey)}
          </li>
        ))}
      </ol>
      {step === 'source' && <SourceStep collectors={collectors} onChoose={choose} />}
      {step === 'export' && collector && <ExportStep collector={collector} onBack={() => setStep('source')} onNext={() => setStep('input')} />}
      {step === 'input' && collector && (
        <InputStep collector={collector} value={source} onChange={setSource} onBack={() => setStep('export')} onNext={() => setStep('options')} />
      )}
      {step === 'options' && collector && (
        <OptionsStep fields={fields} values={values} onChange={(name, value) => setValues({ ...values, [name]: value })}
                     onBack={() => setStep('input')} onNext={() => setStep('preview')} />
      )}
      {step === 'preview' && collector && (
        <PreviewStep collector={collector} source={source} values={values} fields={fields} onBack={() => setStep('options')}
                     onStarted={(job) => { setJobId(job.id); setStep('run') }} />
      )}
      {step === 'run' && collector && jobId !== undefined && (
        <RunStep collector={collector} jobId={jobId} onAgain={reset} onShowJob={onShowJob} onShowPeople={onShowPeople} />
      )}
    </div>
  )
}

function SourceStep({ collectors, onChoose }: { collectors: CollectorDescription[] | undefined; onChoose: (c: CollectorDescription) => void }) {
  const t = useT()
  if (!collectors) return <p className={css.muted}>{t('common.loading')}</p>
  if (collectors.length === 0) return <p className={css.muted}>{t('import.source.none')}</p>
  return (
    <>
      <p>{t('import.source.lead')}</p>
      <ul className={css.grid}>
        {collectors.map(c => (
          <li key={c.id}>
            <button type="button" className={css.choice} onClick={() => onChoose(c)}>
              <strong>{c.name}</strong>
              <span>{t('import.source.takes', { inputs: c.inputs.map(kind => t(`input.${kind}` as CaixaKey)).join(', ') })}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

function ExportStep({ collector, onBack, onNext }: { collector: CollectorDescription; onBack: () => void; onNext: () => void }) {
  const t = useT()
  return (
    <>
      <div className={css.card}>
        <h3>{t('import.export.heading', { name: collector.name })}</h3>
        <p className={css.howto}>{collector.how_to_export}</p>
      </div>
      <div className={css.actions}>
        <button type="button" className={css.button} onClick={onBack}>{t('common.back')}</button>
        <button type="button" className={`${css.button} ${css.primary}`} onClick={onNext}>{t('import.export.next')}</button>
      </div>
    </>
  )
}

function InputStep({ collector, value, onChange, onBack, onNext }: {
  collector: CollectorDescription; value: string; onChange: (path: string) => void; onBack: () => void; onNext: () => void
}) {
  const t = useT()
  const [browsing, setBrowsing] = useState(false)
  return (
    <>
      <h3>{t('import.input.heading')}</h3>
      <p className={css.muted}>{t('import.source.takes', { inputs: collector.inputs.map(kind => t(`input.${kind}` as CaixaKey)).join(', ') })}</p>
      <label className={css.field}>{t('import.input.typed')}
        <span className={css.help}>{t('import.input.typed.help')}</span>
        <input className={css.input} type="text" value={value} onChange={event => onChange(event.target.value)} />
      </label>
      <div className={css.actions}>
        <button type="button" className={css.button} onClick={() => setBrowsing(!browsing)} aria-expanded={browsing}>{t('import.input.browse')}</button>
      </div>
      {browsing && <FilePicker onPick={(path) => { onChange(path); setBrowsing(false) }} />}
      <h3>{t('import.input.inbox')}</h3>
      <p className={css.muted}>{t('import.input.inbox.lead')}</p>
      <InboxList onPick={onChange} />
      <div className={css.actions}>
        <button type="button" className={css.button} onClick={onBack}>{t('common.back')}</button>
        <button type="button" className={`${css.button} ${css.primary}`} disabled={value.trim() === ''} onClick={onNext}>{t('import.input.next')}</button>
      </div>
      {value.trim() === '' ? <p className={css.muted}>{t('import.input.none')}</p> : <p className={css.muted}>{t('import.input.chosen', { path: value })}</p>}
    </>
  )
}

function OptionsStep({ fields, values, onChange, onBack, onNext }: {
  fields: ReturnType<typeof formFields>; values: FormValues; onChange: (name: string, value: string | boolean) => void; onBack: () => void; onNext: () => void
}) {
  const t = useT()
  const [shown, setShown] = useState(false)
  const { problems } = toOptions(fields, values)
  const blocked = Object.keys(problems).length > 0
  return (
    <>
      <h3>{t('import.options.heading')}</h3>
      {fields.length === 0 ? <p className={css.muted}>{t('import.options.none')}</p>
        : <OptionsForm fields={fields} values={values} problems={shown ? problems : {}} onChange={onChange} />}
      <div className={css.actions}>
        <button type="button" className={css.button} onClick={onBack}>{t('common.back')}</button>
        <button type="button" className={`${css.button} ${css.primary}`} onClick={() => { setShown(true); if (!blocked) onNext() }}>{t('import.options.next')}</button>
      </div>
    </>
  )
}

function PreviewStep({ collector, source, values, fields, onBack, onStarted }: {
  collector: CollectorDescription; source: string; values: FormValues; fields: ReturnType<typeof formFields>;
  onBack: () => void; onStarted: (job: Job) => void
}) {
  const store = useStore()
  const t = useT()
  const [preview, setPreview] = useState<PreviewResult | undefined>()
  const [failure, setFailure] = useState<string | undefined>()
  const [starting, setStarting] = useState(false)
  const { options } = useMemo(() => toOptions(fields, values), [fields, values])

  useEffect(() => {
    let current = true
    void store.api.preview(collector.id, source, options).then((reply) => {
      if (!current) return
      if (reply.ok) setPreview(reply.result)
      else setFailure(reply.error.message)
    })
    return () => { current = false }
  }, [store, collector.id, source, options])

  const start = async () => {
    setStarting(true)
    const reply = await store.api.startImport(collector.id, source, options)
    if (reply.ok) { void store.refreshJobs(); onStarted(reply.result) }
    else { setFailure(reply.error.message); setStarting(false) }
  }

  return (
    <>
      <h3>{t('import.preview.heading')}</h3>
      {!preview && !failure && <p className={css.muted} role="status">{t('import.preview.working')}</p>}
      {failure && <div className={css.error} role="alert"><strong>{t('import.preview.error')}</strong><br />{failure}</div>}
      {preview && (
        <div className={css.card}>
          <p><strong>{t('import.preview.counts', { items: preview.items, conversations: preview.conversations })}</strong></p>
          {preview.first && preview.last && <p>{t('import.preview.range', { first: preview.first, last: preview.last })}</p>}
          {preview.items === 0 && <p>{t('import.preview.nothing')}</p>}
          {preview.participants.length > 0 && <><h3>{t('import.preview.people')}</h3><p>{preview.participants.join(', ')}</p></>}
          {preview.unresolved.length > 0 && (
            <>
              <h3>{t('import.preview.unresolved', { count: preview.unresolved.length })}</h3>
              <p>{preview.unresolved.slice(0, 20).join(', ')}{preview.unresolved.length > 20 ? ' …' : ''}</p>
              <p className={css.muted}>{t('import.preview.unresolved.help')}</p>
            </>
          )}
          {preview.warnings.length > 0 && <><h3>{t('import.preview.warnings')}</h3><ul>{preview.warnings.map(w => <li key={w}>{w}</li>)}</ul></>}
        </div>
      )}
      <div className={css.actions}>
        <button type="button" className={css.button} onClick={onBack}>{t('common.back')}</button>
        <button type="button" className={`${css.button} ${css.primary}`} disabled={!preview || preview.items === 0 || starting} onClick={() => void start()}>
          {t('import.preview.start')}
        </button>
      </div>
    </>
  )
}

function RunStep({ collector, jobId, onAgain, onShowJob, onShowPeople }: { collector: CollectorDescription; jobId: number; onAgain: () => void; onShowJob: (job: number) => void; onShowPeople: () => void }) {
  const { jobs } = useCaixa()
  const store = useStore()
  const t = useT()
  const job = jobs.find(candidate => candidate.id === jobId)

  if (!job || job.status === 'queued' || job.status === 'running') {
    const queued = !job || job.status === 'queued'
    return (
      <div className={css.card} role="status">
        <h3>{queued ? t('import.run.queued') : t('import.run.working', { name: collector.name })}</h3>
        {job && !queued && (
          <>
            <p>{t(`stage.${job.stage ?? 'starting'}` as CaixaKey)}{job.message ? ` — ${job.message}` : ''}</p>
            {job.total ? <progress className={css.progress} max={job.total} value={job.current} /> : <progress className={css.progress} />}
          </>
        )}
        <div className={css.actions}>
          <button type="button" className={css.button} onClick={() => void store.api.cancel(jobId)}>{t('import.run.cancel')}</button>
        </div>
      </div>
    )
  }

  const result = job.result
  return (
    <div className={css.card}>
      {job.status === 'done' && result ? (
        <>
          <h3>{t('import.report.done')}</h3>
          <p>{t('import.report.counts', { inserted: result.inserted, updated: result.updated, unchanged: result.unchanged })}</p>
          <p>{t('import.report.pages', { count: result.pages })}</p>
          {result.unresolved.length > 0 && (
            <p>{t('import.report.unresolved', { count: result.unresolved.length })}{' '}
              <button type="button" className={css.link} onClick={onShowPeople}>{t('import.report.name')}</button></p>
          )}
          {result.warnings.length > 0 && <><h3>{t('import.report.warnings')}</h3><ul>{result.warnings.map(w => <li key={w}>{w}</li>)}</ul></>}
        </>
      ) : job.status === 'failed' ? (
        <div className={css.error} role="alert"><strong>{t('import.report.failed')}</strong><br />{job.error}</div>
      ) : job.status === 'cancelled' ? <p>{t('import.report.cancelled')}</p> : <p>{t('import.report.interrupted')}</p>}
      <div className={css.actions}>
        <button type="button" className={`${css.button} ${css.primary}`} onClick={onAgain}>{t('import.report.again')}</button>
        <button type="button" className={css.button} onClick={() => onShowJob(jobId)}>{t('import.report.job')}</button>
      </div>
    </div>
  )
}
