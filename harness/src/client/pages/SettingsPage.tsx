import { useEffect, useMemo, useState } from 'react'
import type { SettingsReply } from '../api.ts'
import { OptionsForm } from '../components/OptionsForm.tsx'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import { fields as formFields, initialValues, toOptions, type FormValues } from '../options-form.ts'
import css from '../caixa.module.css'

const GROUPS = ['privacy', 'translation', 'speech']

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

  useEffect(() => {
    let current = true
    if (!box) return
    void store.api.settings().then((reply) => {
      if (!current) return
      if (reply.ok) { setLoaded(reply.result); setValues(initialValues(formFields(reply.result.schema), reply.result.values)) }
      else setFailure(reply.error.message)
    })
    return () => { current = false }
  }, [store, box?.root])

  const fields = useMemo(() => loaded ? formFields(loaded.schema) : [], [loaded])
  const { options, problems: fieldProblems } = useMemo(
    () => loaded ? toOptions(fields, values, loaded.values) : { options: {}, problems: {} },
    [fields, values, loaded],
  )
  if (!box) return <p className={css.banner}>{t('import.needBox')}</p>

  const dirty = Object.keys(options).length > 0
  const save = async () => {
    setSaved(false); setProblems([]); setFailure(undefined)
    const reply = await store.api.saveSettings(options)
    if (reply.ok) {
      setLoaded(reply.result)
      setValues(initialValues(fields, reply.result.values))
      setSaved(true)
    } else {
      const listed = (reply.error.data as { errors?: string[] } | undefined)?.errors
      if (listed?.length) setProblems(listed)
      else setFailure(reply.error.message)
    }
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
            <button type="button" className={css.button} disabled={!dirty} onClick={() => { setValues(initialValues(fields, loaded.values)); setProblems([]) }}>{t('settings.revert')}</button>
          </div>
          {saved && <p role="status">{t('settings.saved')}</p>}
          {dirty && !saved && <p className={css.muted}>{t('settings.unsaved')}</p>}
        </form>
      )}
    </div>
  )
}
