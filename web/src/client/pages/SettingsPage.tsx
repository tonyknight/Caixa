import { useEffect, useMemo, useState } from 'react'
import type { ContactsCheck, ResetResult, SettingsReply, SummariesTest, TranslationTest, WorkerInfo } from '../api.ts'
import { DiagnosticsReport } from '../components/Diagnostics.tsx'
import { OptionsForm } from '../components/OptionsForm.tsx'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import { fields as formFields, initialValues, toOptions, type FormValues } from '../options-form.ts'
import css from '../caixa.module.css'

/** Why this Mac's Contacts could not be used, as the worker names it, and the words for it. */
const MAC_PROBLEMS: Readonly<Record<string, CaixaKey>> = {
  no_access: 'contacts.mac.no_access', empty: 'contacts.mac.empty', not_a_mac: 'contacts.mac.not_a_mac',
}

const GROUPS = ['privacy', 'contacts', 'translation', 'summaries', 'speech', 'performance']
/** A setting with no group in its name (`workers`) goes under Performance. */
const inGroup = (name: string, group: string) => group === 'performance' ? !name.includes('.') : name.startsWith(`${group}.`)

/** The box's location, and its settings as a form drawn from the schema the worker publishes. */
export function SettingsPage({ onChangeBox }: { onChangeBox: () => void }) {
  const { box, readOnly } = useCaixa()
  const store = useStore()
  const t = useT()
  const [loaded, setLoaded] = useState<SettingsReply | undefined>()
  const [values, setValues] = useState<FormValues>({})
  const [problems, setProblems] = useState<string[]>([])
  const [saved, setSaved] = useState(false)
  const [failure, setFailure] = useState<string | undefined>()
  // The translation key is not a setting: it is typed here, saved outside the box, and never read back.
  const [key, setKey] = useState('')
  const [keySaved, setKeySaved] = useState(false)
  const [contacts, setContacts] = useState<ContactsCheck | undefined>()
  const [worker, setWorker] = useState<WorkerInfo | undefined>()
  const [resetting, setResetting] = useState<'no' | 'asking' | 'busy'>('no')
  const [forgetNames, setForgetNames] = useState(false)
  const [reset, setReset] = useState<ResetResult | undefined>()
  const [resetFailure, setResetFailure] = useState<string | undefined>()
  const [testing, setTesting] = useState(false)
  const [tested, setTested] = useState<TranslationTest | undefined>()
  const [summarizing, setSummarizing] = useState<'no' | 'testing' | 'starting' | 'started'>('no')
  const [summaryTested, setSummaryTested] = useState<SummariesTest | undefined>()

  useEffect(() => {
    let current = true
    if (!box) return
    void store.api.settings().then((reply) => {
      if (!current) return
      if (reply.ok) { setLoaded(reply.result); setKeySaved(reply.result.translation?.key_saved ?? false); setValues(initialValues(formFields(reply.result.schema), reply.result.values)) }
      else setFailure(reply.error.message)
    })
    void store.api.checkContacts().then((reply) => { if (current && reply.ok) setContacts(reply.result) })
    void store.api.info().then((reply) => { if (current && reply.ok) setWorker(reply.result) })
    return () => { current = false }
  }, [store, box?.root])

  const fields = useMemo(() => loaded ? formFields(loaded.schema) : [], [loaded])
  const { options, problems: fieldProblems } = useMemo(
    () => loaded ? toOptions(fields, values, loaded.values) : { options: {}, problems: {} },
    [fields, values, loaded],
  )
  if (!box) return <p className={css.banner}>{t('import.needBox')}</p>

  const dirty = Object.keys(options).length > 0 || key.trim() !== ''
  const endpoint = String(values['translation.endpoint'] ?? '').trim()
  const save = async () => {
    setSaved(false); setProblems([]); setFailure(undefined)
    const reply = await store.api.saveSettings(options)
    if (reply.ok) {
      setLoaded(reply.result)
      setValues(initialValues(fields, reply.result.values))
      setKeySaved(reply.result.translation?.key_saved ?? false)
      void store.api.checkContacts().then((checked) => { if (checked.ok) setContacts(checked.result) })
      if (key.trim()) {
        const kept = await store.api.saveTranslationKey(String(reply.result.values['translation.endpoint'] ?? ''), key.trim())
        if (!kept.ok) { setFailure(kept.error.message); return }
        setKeySaved(kept.result.key_saved); setKey('')
      }
      setSaved(true)
    } else {
      const listed = (reply.error.data as { errors?: string[] } | undefined)?.errors
      if (listed?.length) setProblems(listed)
      else setFailure(reply.error.message)
    }
  }
  const startAgain = async () => {
    setResetting('busy'); setResetFailure(undefined); setReset(undefined)
    const reply = await store.api.resetBox(forgetNames)
    setResetting('no')
    if (!reply.ok) { setResetFailure(reply.error.message); return }
    setReset(reply.result)
    await store.refreshBox()
    await store.refreshJobs()
  }
  const forgetKey = async () => {
    const reply = await store.api.saveTranslationKey(endpoint, '')
    if (reply.ok) { setKeySaved(reply.result.key_saved); setKey('') } else setFailure(reply.error.message)
  }
  /** The Workers setting as typed, for Apple Intelligence's helpers (left out when empty). */
  const workersNow = () => (String(values['workers'] ?? '').trim() ? { workers: Number(values['workers']) } : {})
  const test = async () => {
    setTesting(true); setTested(undefined)
    const reply = await store.api.testTranslation({
      'translation.provider': String(values['translation.provider'] ?? '') || 'auto', ...workersNow(),
      'translation.endpoint': endpoint, 'translation.model': String(values['translation.model'] ?? '').trim(),
    }, key.trim())
    setTesting(false)
    setTested(reply.ok ? reply.result : { ok: false, message: reply.error.message })
  }

  const typed = (name: string) => String(values[name] ?? '').trim()
  const testSummaries = async () => {
    setSummarizing('testing'); setSummaryTested(undefined)
    const reply = await store.api.call<SummariesTest>('summaries.test', {
      values: {
        'summaries.provider': typed('summaries.provider') || 'auto', ...workersNow(),
        'summaries.endpoint': typed('summaries.endpoint'), 'summaries.model': typed('summaries.model'),
        'translation.endpoint': endpoint, 'translation.model': typed('translation.model'),
      },
      key: key.trim(),
    })
    setSummarizing('no')
    setSummaryTested(reply.ok ? reply.result : { ok: false, message: reply.error.message })
  }
  const summarizeNow = async () => {
    setSummarizing('starting')
    const reply = await store.api.call('mail.summarize', {})
    if (!reply.ok) { setSummarizing('no'); setFailure(reply.error.message); return }
    setSummarizing('started')
    await store.refreshJobs()
  }
  const summariesOn = Boolean(loaded?.values['summaries.enabled'])

  return (
    <div className={css.section}>
      <h2>{t('settings.heading')}</h2>
      <div className={css.card}>
        <h3>{t('settings.box')}</h3>
        <p>{box.name}</p>
        <p className={css.muted}>{t('settings.box.where', { path: box.root })}</p>
        <button type="button" className={css.button} onClick={onChangeBox}>{t('settings.box.other')}</button>
      </div>
      <p className={css.muted}>{t('settings.local')}</p>
      {worker?.restart_needed && <p className={css.banner} role="alert" data-testid="caixa-restart">{t('settings.restart')}</p>}
      {readOnly && <p className={css.banner}>{t('settings.readOnly')}</p>}
      {failure && <p className={css.error} role="alert">{t('common.error', { message: failure })}</p>}
      {!loaded && !failure && <p className={css.muted}>{t('common.loading')}</p>}
      {loaded && (
        <form onSubmit={(event) => { event.preventDefault(); void save() }}>
          {GROUPS.map((group) => {
            const members = fields.filter(f => inGroup(f.name, group))
            if (members.length === 0) return null
            return (
              <fieldset key={group} className={css.group} disabled={readOnly}>
                <legend>{t(`settings.group.${group}` as CaixaKey)}</legend>
                <OptionsForm fields={members} values={values} problems={fieldProblems}
                             onChange={(name, value) => { setSaved(false); setValues({ ...values, [name]: value }) }} />
                {group === 'contacts' && contacts && (
                  <div data-testid="contacts-check">
                    {contacts.mac.on && (
                      <p className={contacts.mac.problem ? css.problem : css.muted}>
                        {contacts.mac.problem
                          ? t(MAC_PROBLEMS[contacts.mac.problem] ?? 'contacts.mac.empty')
                          : t('contacts.mac.ok', { count: contacts.mac.people.toLocaleString() })}
                      </p>
                    )}
                    {contacts.file.on && (
                      <p className={contacts.file.problem ? css.problem : css.muted}>
                        {contacts.file.problem
                          ? t('contacts.file.problem', { message: contacts.file.problem })
                          : t('contacts.file.ok', { count: contacts.file.people.toLocaleString() })}
                      </p>
                    )}
                    {!contacts.mac.on && !contacts.file.on && <p className={css.muted}>{t('contacts.none')}</p>}
                  </div>
                )}
                {group === 'translation' && (
                  <>
                    <div>
                      <label className={css.field} htmlFor="caixa-translation-key">{t('translation.key')}</label>
                      <span id="caixa-translation-key-help" className={css.help}>{t('translation.key.help')}</span>
                      <input id="caixa-translation-key" className={css.input} type="password" autoComplete="off" value={key}
                             aria-describedby="caixa-translation-key-help caixa-translation-key-state"
                             onChange={(event) => { setSaved(false); setKey(event.target.value) }} />
                      <p id="caixa-translation-key-state" className={css.muted}>
                        {t(keySaved ? 'translation.key.saved' : 'translation.key.none')}{' '}
                        {keySaved && <button type="button" className={css.link} onClick={() => void forgetKey()}>{t('translation.key.forget')}</button>}
                      </p>
                    </div>
                    <div>
                      <button type="button" className={css.button} disabled={testing} aria-describedby="caixa-translation-test-help" onClick={() => void test()}>
                        {t(testing ? 'translation.testing' : 'translation.test')}
                      </button>
                      <span id="caixa-translation-test-help" className={css.help}>{t('translation.test.help')}</span>
                      {tested?.ok === true && (
                        <div role="status" data-testid="translation-test-result">
                          <p><strong>{t('translation.test.ok', { seconds: tested.seconds })}</strong></p>
                          <p className={css.muted}>{t('translation.test.sample', { sample: tested.sample })}</p>
                          <p>{t('translation.test.answer', { translation: tested.translation })}</p>
                        </div>
                      )}
                      {tested?.ok === false && <p className={css.error} role="alert" data-testid="translation-test-result">{t('translation.test.failed', { message: tested.message })}</p>}
                    </div>
                  </>
                )}
                {group === 'summaries' && (
                  <>
                    <div>
                      <button type="button" className={css.button} disabled={summarizing === 'testing'} aria-describedby="caixa-summaries-test-help" onClick={() => void testSummaries()}>
                        {t(summarizing === 'testing' ? 'translation.testing' : 'summaries.test')}
                      </button>
                      <span id="caixa-summaries-test-help" className={css.help}>{t('summaries.test.help')}</span>
                      {summaryTested?.ok === true && (
                        <div role="status" data-testid="summaries-test-result">
                          <p><strong>{t('summaries.test.ok', { seconds: summaryTested.seconds, words: summaryTested.words })}</strong></p>
                          <p>{summaryTested.summary}</p>
                        </div>
                      )}
                      {summaryTested?.ok === false && <p className={css.error} role="alert" data-testid="summaries-test-result">{t('summaries.test.failed', { message: summaryTested.message })}</p>}
                    </div>
                    <div>
                      <button type="button" className={css.button} disabled={readOnly || !summariesOn || summarizing === 'starting'} aria-describedby="caixa-summaries-now-help" onClick={() => void summarizeNow()}>
                        {t('summaries.now')}
                      </button>
                      <span id="caixa-summaries-now-help" className={css.help}>{t('summaries.now.help')}</span>
                      {summarizing === 'started' && <p role="status" data-testid="summaries-started">{t('summaries.started')}</p>}
                    </div>
                  </>
                )}
              </fieldset>
            )
          })}
          {problems.length > 0 && (
            <div className={css.error} role="alert">
              <strong>{t('settings.problems')}</strong>
              <ul>{problems.map(problem => <li key={problem}>{problem}</li>)}</ul>
            </div>
          )}
          <div className={css.actions}>
            <button type="submit" className={`${css.button} ${css.primary}`} disabled={readOnly || !dirty || Object.keys(fieldProblems).length > 0}>{t('settings.save')}</button>
            <button type="button" className={css.button} disabled={!dirty} onClick={() => { setValues(initialValues(fields, loaded.values)); setProblems([]); setKey('') }}>{t('settings.revert')}</button>
          </div>
          {saved && <p role="status">{t('settings.saved')}</p>}
          {dirty && !saved && <p className={css.muted}>{t('settings.unsaved')}</p>}
        </form>
      )}
      <div className={css.card}>
        <h3>{t('diagnostics.heading')}</h3>
        <p>{t('diagnostics.lead')}</p>
        <DiagnosticsReport />
      </div>
      <div className={css.card} role="region" aria-label={t('reset.heading')}>
        <h3>{t('reset.heading')}</h3>
        <p>{t('reset.lead')}</p>
        <label className={css.check}>
          <input type="checkbox" checked={forgetNames} disabled={readOnly || resetting === 'busy'} onChange={event => setForgetNames(event.target.checked)} />
          <span>{t('reset.forgetNames')}</span>
        </label>
        {resetting === 'no' && <button type="button" className={css.button} disabled={readOnly} onClick={() => { setReset(undefined); setResetting('asking') }}>{t('reset.start')}</button>}
        {resetting !== 'no' && (
          <div className={css.banner} role="alertdialog" aria-label={t('reset.confirm', { name: box.name })}>
            <p>{t(forgetNames ? 'reset.confirmForget' : 'reset.confirm', { name: box.name })}</p>
            <button type="button" className={`${css.button} ${css.primary}`} disabled={resetting === 'busy'} onClick={() => void startAgain()}>{t(resetting === 'busy' ? 'reset.working' : 'reset.do')}</button>
            {' '}<button type="button" className={css.button} disabled={resetting === 'busy'} onClick={() => setResetting('no')}>{t('people.cancel')}</button>
          </div>
        )}
        {reset && (
          <div role="status" data-testid="reset-result">
            <p><strong>{t('reset.done', { count: reset.removed.toLocaleString() })}</strong>{reset.names_kept > 0 && <> {t('reset.namesKept', { count: reset.names_kept })}</>}</p>
            {reset.left.length > 0 && <><p>{t('reset.left')}</p><ul>{reset.left.map(file => <li key={file}>{file}</li>)}</ul></>}
          </div>
        )}
        {resetFailure && <p className={css.error} role="alert">{t('common.error', { message: resetFailure })}</p>}
      </div>
      {worker && (
        <p className={css.muted} data-testid="caixa-version">
          {t('settings.version', { version: worker.version, commit: worker.commit || t('settings.unknown'), when: worker.started ? new Date(worker.started).toLocaleString() : t('settings.unknown') })}
        </p>
      )}
    </div>
  )
}
