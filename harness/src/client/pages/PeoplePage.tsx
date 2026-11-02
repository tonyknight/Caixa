import { useEffect, useMemo, useState, type FormEvent } from 'react'
import type { CaixaError, Handle, Job, Person, PersonChange } from '../api.ts'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import css from '../caixa.module.css'

type Outcome = { message: string; jobId: number | null }

/** Who is in the box: the queue of handles no one is named for, and the people already there. */
export function PeoplePage() {
  const { box, boxVersion, readOnly, jobs } = useCaixa()
  const store = useStore()
  const t = useT()
  const [people, setPeople] = useState<Person[]>([])
  const [handles, setHandles] = useState<Handle[]>([])
  const [loaded, setLoaded] = useState(false)
  const [outcome, setOutcome] = useState<Outcome | undefined>()
  const [failure, setFailure] = useState<string | undefined>()
  const [renaming, setRenaming] = useState<number | undefined>()
  const [merging, setMerging] = useState<number | undefined>()

  useEffect(() => {
    let current = true
    if (!box) return
    void Promise.all([store.api.people(), store.api.unresolved()]).then(([listed, unresolved]) => {
      if (!current) return
      if (listed.ok) setPeople(listed.result.people)
      if (unresolved.ok) setHandles(unresolved.result.handles)
      setLoaded(true)
    })
    return () => { current = false }
  }, [store, box?.root, boxVersion])

  if (!box) return <p className={css.banner}>{t('import.needBox')}</p>

  const job: Job | undefined = outcome?.jobId != null ? jobs.find(candidate => candidate.id === outcome.jobId) : undefined

  /** Run a change, and follow the job that redraws the pages. */
  const change = async (run: () => Promise<{ ok: true; result: PersonChange } | { ok: false; error: CaixaError }>, message: (person: Person) => string) => {
    setFailure(undefined)
    const reply = await run()
    if (!reply.ok) { setFailure(reply.error.kind === 'conflict' ? reply.error.message.replace(/ Use move to give it to this person\.$/, '') : reply.error.message); return false }
    setOutcome({ message: message(reply.result.person), jobId: reply.result.job?.id ?? null })
    setRenaming(undefined)
    setMerging(undefined)
    void store.refreshJobs()
    store.touch()
    return true
  }

  return (
    <div className={css.section}>
      <h2>{t('people.heading')}</h2>
      {readOnly && <p className={css.banner}>{t('people.readOnly')}</p>}
      {failure && <p className={css.error} role="alert">{failure}</p>}
      {outcome && (
        <div className={css.banner} role="status">
          <p>{outcome.message}</p>
          {outcome.jobId != null && (
            <p className={css.muted}>
              {!job || job.status === 'queued' || job.status === 'running' ? t('people.redrawing')
                : job.status === 'done' ? t('people.redrawn') : t('people.redrawFailed', { error: job.error ?? '' })}
            </p>
          )}
        </div>
      )}

      <h3>{t('people.unresolved', { count: handles.length })}</h3>
      {handles.length > 0 && <p className={css.muted}>{t('people.unresolved.lead')}</p>}
      {loaded && handles.length === 0 && <p className={css.muted}>{t('people.unresolved.none')}</p>}
      {handles.length > 0 && (
        <table className={css.table}>
          <thead><tr><th>{t('people.service')}</th><th>{t('people.identifier')}</th><th>{t('people.messages')}</th><th /></tr></thead>
          <tbody>
            {handles.map(handle => (
              <HandleRow key={`${handle.service}|${handle.identifier}`} handle={handle} people={people} disabled={readOnly}
                         onLink={(who, move) => change(() => store.api.link(handle.service, handle.identifier, who, move), person => t('people.linked', { identifier: handle.identifier, name: person.name }))}
                         conflict={failure} />
            ))}
          </tbody>
        </table>
      )}

      <h3>{t('people.people', { count: people.length })}</h3>
      {loaded && people.length === 0 && <p className={css.muted}>{t('people.none')}</p>}
      <ul className={css.entries}>
        {people.map(person => (
          <li key={person.id} style={{ display: 'block', padding: '0.5rem 0.3rem' }}>
            <PersonRow person={person} others={people.filter(other => other.id !== person.id)} disabled={readOnly}
                       renaming={renaming === person.id} merging={merging === person.id}
                       onStartRename={() => { setRenaming(person.id); setMerging(undefined) }}
                       onStartMerge={() => { setMerging(person.id); setRenaming(undefined) }}
                       onCancel={() => { setRenaming(undefined); setMerging(undefined) }}
                       onRename={name => change(() => store.api.rename(person.id, name), renamed => t('people.renamed', { name: renamed.name }))}
                       onMerge={target => change(() => store.api.merge(person.id, target), kept => t('people.merged', { name: kept.name }))} />
          </li>
        ))}
      </ul>
    </div>
  )
}

function HandleRow({ handle, people, disabled, onLink, conflict }: {
  handle: Handle; people: Person[]; disabled: boolean; conflict: string | undefined
  onLink: (person: number | string, move: boolean) => Promise<boolean>
}) {
  const t = useT()
  const [name, setName] = useState('')
  const [asked, setAsked] = useState<string | undefined>()
  const listId = useMemo(() => `people-${handle.service}-${handle.identifier}`.replace(/\W+/g, '-'), [handle])
  const submit = async (event: FormEvent, move = false) => {
    event.preventDefault()
    const chosen = name.trim()
    if (chosen === '') return
    setAsked(chosen)
    const existing = people.find(person => person.name.toLowerCase() === chosen.toLowerCase())
    if (await onLink(existing ? existing.id : chosen, move)) setName('')
  }
  return (
    <tr>
      <td>{handle.service}</td>
      <td>{handle.identifier}{handle.display_name && handle.display_name !== handle.identifier ? <><br /><span className={css.muted}>{handle.display_name}</span></> : null}</td>
      <td>{handle.messages}</td>
      <td>
        <form onSubmit={submit}>
          <input className={css.input} style={{ width: '14rem' }} type="text" list={listId} value={name} disabled={disabled}
                 aria-label={t('people.nameFor', { identifier: handle.identifier })} onChange={event => setName(event.target.value)} />
          <datalist id={listId}>{people.map(person => <option key={person.id} value={person.name} />)}</datalist>
          {' '}
          <button type="submit" className={css.button} disabled={disabled || name.trim() === ''}>{t('people.link')}</button>
          {conflict && asked && /already names/.test(conflict) && (
            <> <button type="button" className={css.link} onClick={event => void submit(event, true)}>{t('people.moveHere', { name: asked })}</button></>
          )}
        </form>
      </td>
    </tr>
  )
}

function PersonRow({ person, others, disabled, renaming, merging, onStartRename, onStartMerge, onCancel, onRename, onMerge }: {
  person: Person; others: Person[]; disabled: boolean; renaming: boolean; merging: boolean
  onStartRename: () => void; onStartMerge: () => void; onCancel: () => void
  onRename: (name: string) => Promise<boolean>; onMerge: (target: number) => Promise<boolean>
}) {
  const t = useT()
  const [name, setName] = useState(person.name)
  const [target, setTarget] = useState('')
  const [confirming, setConfirming] = useState(false)
  const chosen = others.find(other => String(other.id) === target)
  useEffect(() => { if (renaming) setName(person.name) }, [renaming, person.name])
  useEffect(() => { if (!merging) { setTarget(''); setConfirming(false) } }, [merging])

  return (
    <div>
      <strong>{person.name}</strong>{person.is_owner && <> <span className={css.badge}>{t('people.owner')}</span></>}
      {' '}<span className={css.muted}>{t('people.items', { count: person.items })} · {t('people.aliases', { count: person.aliases })}</span>
      {!renaming && !merging && (
        <>
          {' '}<button type="button" className={css.link} disabled={disabled} onClick={onStartRename} aria-label={`${t('people.rename')} ${person.name}`}>{t('people.rename')}</button>
          {!person.is_owner && others.length > 0 && <> <button type="button" className={css.link} disabled={disabled} onClick={onStartMerge} aria-label={`${t('people.merge')} ${person.name}`}>{t('people.merge')}</button></>}
        </>
      )}
      {renaming && (
        <form onSubmit={(event) => { event.preventDefault(); if (name.trim() !== '') void onRename(name.trim()) }} style={{ marginTop: '0.3rem' }}>
          <input className={css.input} style={{ width: '16rem' }} type="text" value={name} aria-label={t('people.renameFor', { name: person.name })} onChange={event => setName(event.target.value)} />
          {' '}<button type="submit" className={css.button} disabled={name.trim() === '' || name.trim() === person.name}>{t('people.save')}</button>
          {' '}<button type="button" className={css.button} onClick={onCancel}>{t('people.cancel')}</button>
        </form>
      )}
      {merging && (
        <div style={{ marginTop: '0.3rem' }}>
          <label>{t('people.mergeInto', { name: person.name })}{' '}
            <select className={css.select} style={{ width: 'auto' }} value={target} onChange={(event) => { setTarget(event.target.value); setConfirming(false) }}>
              <option value="">{t('people.mergeChoose')}</option>
              {others.map(other => <option key={other.id} value={other.id}>{other.name}</option>)}
            </select>
          </label>
          {chosen && !confirming && <> <button type="button" className={css.button} onClick={() => setConfirming(true)}>{t('people.merge')}</button></>}
          {chosen && confirming && (
            <div className={css.banner} role="alertdialog" aria-label={t('people.mergeConfirm', { source: person.name, target: chosen.name })}>
              <p>{t('people.mergeConfirm', { source: person.name, target: chosen.name })}</p>
              <button type="button" className={`${css.button} ${css.primary}`} onClick={() => void onMerge(chosen.id)}>{t('people.mergeDo')}</button>
            </div>
          )}
          {' '}<button type="button" className={css.button} onClick={onCancel}>{t('people.cancel')}</button>
        </div>
      )}
    </div>
  )
}
