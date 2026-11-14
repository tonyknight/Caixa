import { useEffect, useMemo, useState } from 'react'
import type { ContactsCheck, SettingsReply, TranslationTest, WorkerInfo } from '../api.ts'
import { DiagnosticsReport } from '../components/Diagnostics.tsx'
import { OptionsForm } from '../components/OptionsForm.tsx'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import { fields as formFields, initialValues, toOptions, type FormValues } from '../options-form.ts'
import css from '../caixa.module.css'

/** When the interface bundle was built (set by the build; absent when run unbundled, as in tests). */
declare const __CAIXA_BUILT__: string | undefined
const BUILT: string | undefined = typeof __CAIXA_BUILT__ === 'undefined' ? undefined : __CAIXA_BUILT__

/** Why this Mac's Contacts could not be used, as the worker names it, and the words for it. */
const MAC_PROBLEMS: Readonly<Record<string, CaixaKey>> = {
  no_access: 'contacts.mac.no_access', empty: 'contacts.mac.empty', not_a_mac: 'contacts.mac.not_a_mac',
}

const GROUPS = ['privacy', 'contacts', 'translation', 'speech']

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
  const [testing, setTesting] = useState(false)
  const [tested, setTested] = useState<TranslationTest | undefined>()

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
  const forgetKey = async () => {
    const reply = await store.api.saveTranslationKey(endpoint, '')
    if (reply.ok) { setKeySaved(reply.result.key_saved); setKey('') } else setFailure(reply.error.message)
  }
  const test = async () => {
    setTesting(true); setTested(undefined)
    const reply = await store.api.testTranslation({
      'translation.endpoint': endpoint, 'translation.model': String(values['translation.model'] ?? '').trim(),
    }, key.trim())
    setTesting(false)
    setTested(reply.ok ? reply.result : { ok: false, message: reply.error.message })
  }

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
            const members = fields.filter(f => f.name.startsWith(`${group}.`))
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
      {worker && (
        <p className={css.muted} data-testid="caixa-version">
          {t('settings.version', { version: worker.version, commit: worker.commit || t('settings.built.unknown'), when: worker.started ? new Date(worker.started).toLocaleString() : t('settings.built.unknown') })}
        </p>
      )}
      <p className={css.muted} data-testid="caixa-built">{t('settings.built', { when: BUILT ? new Date(BUILT).toLocaleString() : t('settings.built.unknown') })}</p>
    </div>
  )
}
