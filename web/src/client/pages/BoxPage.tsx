import { useState, type FormEvent } from 'react'
import { FilePicker } from '../components/FilePicker.tsx'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import css from '../caixa.module.css'

/** The boxes opened lately: open one with a click, or take a missing one off the list. */
function RecentBoxes({ busy, onOpen }: { busy: boolean; onOpen: (path: string) => void }) {
  const { recent, box } = useCaixa()
  const store = useStore()
  const t = useT()
  const shown = recent.filter(entry => entry.path !== box?.root)
  if (shown.length === 0) return null
  return (
    <div className={css.card}>
      <h3 id="caixa-recent">{t('box.recent.heading')}</h3>
      <ul className={css.recent} aria-labelledby="caixa-recent">
        {shown.map(entry => (
          <li key={entry.path}>
            <strong>{entry.name || entry.path}</strong>
            <span className={css.muted}>{entry.path}</span>
            {entry.opened && <span className={css.muted}>{t('box.recent.opened', { when: new Date(entry.opened).toLocaleString() })}</span>}
            {entry.exists
              ? <button type="button" className={`${css.button} ${css.primary}`} disabled={busy} onClick={() => onOpen(entry.path)}
                        aria-label={t('box.recent.open', { name: entry.name || entry.path })}>{t('box.open.submit')}</button>
              : <span className={css.muted}>{t('box.recent.missing')}</span>}
            {!entry.exists && (
              <button type="button" className={css.link} onClick={() => void store.forgetBox(entry.path)}
                      aria-label={t('box.recent.forget', { name: entry.name || entry.path })}>{t('box.recent.forget.short')}</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

const KNOWN_TYPES = ['text', 'call', 'voicemail', 'email', 'media', 'system']

function Picker({ label, help, value, onChange }: { label: string; help?: string; value: string; onChange: (path: string) => void }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  return (
    <div>
      <label className={css.field}>
        {label}
        {help && <span className={css.help}>{help}</span>}
        <input className={css.input} type="text" value={value} onChange={event => onChange(event.target.value)} required />
      </label>
      <button type="button" className={css.button} onClick={() => setOpen(!open)} aria-expanded={open}>{t('import.input.browse')}</button>
      {open && <FilePicker onPick={(path) => { onChange(path); setOpen(false) }} />}
    </div>
  )
}

/** Create or open a box when none is open; otherwise what is in the open one. */
export function BoxPage({ onImport }: { onImport: () => void }) {
  const { box, ready } = useCaixa()
  const store = useStore()
  const t = useT()
  const [replacing, setReplacing] = useState(false)
  const [folder, setFolder] = useState('')
  const [name, setName] = useState('')
  const [owner, setOwner] = useState('')
  const [openFolder, setOpenFolder] = useState('')
  const [failure, setFailure] = useState<string | undefined>()
  const [busy, setBusy] = useState(false)

  const run = async (action: () => Promise<{ message: string } | undefined>) => {
    setBusy(true)
    setFailure(undefined)
    const error = await action()
    setBusy(false)
    if (error) setFailure(error.message)
    else setReplacing(false)
  }
  const create = (event: FormEvent) => { event.preventDefault(); void run(() => store.createBox(folder.trim(), name.trim(), owner.trim())) }
  const open = (event: FormEvent) => { event.preventDefault(); void run(() => store.openBox(openFolder.trim())) }

  if (!ready) return <p className={css.muted}>{t('common.loading')}</p>

  if (box && !replacing) {
    const types = Object.entries(box.by_type)
    return (
      <div className={css.section}>
        <h2>{box.name}</h2>
        <p className={css.muted}>{t('box.dashboard.where', { path: box.root })}</p>
        <p>{box.owner ? t('box.dashboard.owner', { name: box.owner }) : t('box.dashboard.noOwner')}</p>
        <div className={css.numbers}>
          <div><span className={css.number}>{box.items}</span> {t('box.dashboard.itemsLabel')}</div>
          <div><span className={css.number}>{box.people}</span> {t('box.dashboard.peopleLabel')}</div>
        </div>
        <h3>{t('box.dashboard.types')}</h3>
        {types.length === 0 ? <p className={css.muted}>{t('box.dashboard.empty')}</p> : (
          <ul>
            {types.map(([type, count]) => (
              <li key={type}>{KNOWN_TYPES.includes(type) ? t(`type.${type}` as CaixaKey) : type}: {count}</li>
            ))}
          </ul>
        )}
        <h3>{t('box.dashboard.imports')}</h3>
        {box.imports.length === 0 ? <p className={css.muted}>{t('box.dashboard.noImports')}</p> : (
          <table className={css.table}>
            <tbody>
              {[...box.imports].reverse().map(record => (
                <tr key={record.id}>
                  <td>{record.collector}</td>
                  <td>{new Date(record.started_at).toLocaleString()}</td>
                  <td>{t('import.report.counts', { inserted: record.inserted, updated: record.updated, unchanged: record.unchanged })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className={css.actions}>
          <button type="button" className={`${css.button} ${css.primary}`} onClick={onImport}>{t('box.dashboard.import')}</button>
          <button type="button" className={css.button} onClick={() => setReplacing(true)}>{t('box.dashboard.other')}</button>
        </div>
      </div>
    )
  }

  return (
    <div className={css.section}>
      <h2>{t('box.none.title')}</h2>
      <p>{t('box.none.lead')}</p>
      {failure && <p className={css.error} role="alert">{failure}</p>}
      <RecentBoxes busy={busy} onOpen={path => void run(() => store.openBox(path))} />
      <form className={css.card} onSubmit={create}>
        <h3>{t('box.create.heading')}</h3>
        <Picker label={t('box.create.folder')} help={t('box.create.folder.help')} value={folder} onChange={setFolder} />
        <label className={css.field}>{t('box.create.name')}
          <input className={css.input} type="text" value={name} onChange={event => setName(event.target.value)} />
        </label>
        <label className={css.field}>{t('box.create.owner')}
          <span className={css.help}>{t('box.create.owner.help')}</span>
          <input className={css.input} type="text" value={owner} onChange={event => setOwner(event.target.value)} />
        </label>
        <div className={css.actions}>
          <button type="submit" className={`${css.button} ${css.primary}`} disabled={busy || folder.trim() === ''}>{t('box.create.submit')}</button>
        </div>
      </form>
      <form className={css.card} onSubmit={open}>
        <h3>{t('box.open.heading')}</h3>
        <Picker label={t('box.open.folder')} value={openFolder} onChange={setOpenFolder} />
        <div className={css.actions}>
          <button type="submit" className={css.button} disabled={busy || openFolder.trim() === ''}>{t('box.open.submit')}</button>
          {box && <button type="button" className={css.button} onClick={() => setReplacing(false)}>{t('common.back')}</button>}
        </div>
      </form>
    </div>
  )
}
