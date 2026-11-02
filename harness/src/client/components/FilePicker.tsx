import { useEffect, useState } from 'react'
import type { FileEntry, FilesListing } from '../api.ts'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import css from '../caixa.module.css'

/** A server-side listing of the person's own folders (the worker limits it), to pick a file or folder. */
export function FilePicker({ onPick, startAt }: { onPick: (path: string) => void; startAt?: string }) {
  const store = useStore()
  const t = useT()
  const [listing, setListing] = useState<FilesListing | undefined>()
  const [failure, setFailure] = useState<string | undefined>()

  const open = async (path?: string) => {
    setFailure(undefined)
    const reply = await store.api.files(path)
    if (reply.ok) setListing(reply.result)
    else setFailure(reply.error.message)
  }
  useEffect(() => { void open(startAt) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={css.picker} role="group" aria-label={t('import.input.browse')}>
      {failure && <p className={css.error} role="alert">{t('common.error', { message: failure })}</p>}
      {!listing && !failure && <p className={css.muted}>{t('common.loading')}</p>}
      {listing && (
        <>
          <div className={css.where}>{listing.path}</div>
          <ul className={css.entries}>
            {listing.parent && (
              <li><button type="button" className={css.link} onClick={() => void open(listing.parent!)}>{t('import.input.up')}</button></li>
            )}
            {listing.entries.map((entry: FileEntry) => (
              <li key={entry.path}>
                {entry.kind === 'directory' ? (
                  <>
                    <button type="button" className={css.link} onClick={() => void open(entry.path)}>{entry.name}/</button>
                    <button type="button" className={css.link} onClick={() => onPick(entry.path)}>{t('import.input.useFolder')}</button>
                  </>
                ) : (
                  <>
                    <span>{entry.name}</span>
                    <button type="button" className={css.link} onClick={() => onPick(entry.path)}>{t('import.input.use')}</button>
                  </>
                )}
              </li>
            ))}
            {listing.entries.length === 0 && <li className={css.muted}>{t('import.input.empty')}</li>}
          </ul>
        </>
      )}
    </div>
  )
}

/** What the Inbox folder of the open box holds; reloads when the worker says it changed. */
export function InboxList({ onPick }: { onPick: (path: string) => void }) {
  const store = useStore()
  const t = useT()
  const { inboxVersion } = useCaixa()
  const [listing, setListing] = useState<{ path: string; entries: FileEntry[] } | undefined>()

  useEffect(() => {
    let current = true
    void store.api.inbox().then((reply) => { if (current && reply.ok) setListing({ path: reply.result.path, entries: [...reply.result.entries] }) })
    return () => { current = false }
  }, [store, inboxVersion])

  if (!listing) return <p className={css.muted}>{t('common.loading')}</p>
  if (listing.entries.length === 0) return <p className={css.muted}>{t('import.input.inbox.empty', { path: listing.path })}</p>
  return (
    <ul className={css.entries}>
      {listing.entries.map(entry => (
        <li key={entry.name}>
          <span>{entry.name}{entry.kind === 'directory' ? '/' : ''}</span>
          <button type="button" className={css.link} onClick={() => onPick(entry.absolute ?? entry.path)}>{t('import.input.use')}</button>
        </li>
      ))}
    </ul>
  )
}
