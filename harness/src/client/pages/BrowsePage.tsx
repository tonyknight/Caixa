import { useEffect, useState } from 'react'
import { boxUrl, type FileEntry } from '../api.ts'
import { useCaixa, useStore, useT } from '../hooks.tsx'
import css from '../caixa.module.css'

type Kind = 'page' | 'image' | 'audio' | 'video' | 'text' | 'other'

export function kindOf(name: string): Kind {
  const extension = name.toLowerCase().split('.').pop() ?? ''
  if (extension === 'html' || extension === 'htm') return 'page'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'avif'].includes(extension)) return 'image'
  if (['mp3', 'm4a', 'aac', 'wav', 'ogg', 'oga', 'opus'].includes(extension)) return 'audio'
  if (['mp4', 'mov', 'm4v', 'webm', 'ogv'].includes(extension)) return 'video'
  if (['txt', 'md', 'json', 'csv', 'log'].includes(extension)) return 'text'
  return 'other'
}

function useSize() {
  const t = useT()
  return (bytes: number | null): string => {
    if (bytes === null) return ''
    if (bytes < 1024) return t('browse.size.bytes', { count: bytes })
    if (bytes < 1024 * 1024) return t('browse.size.kb', { count: Math.round(bytes / 1024) })
    return t('browse.size.mb', { count: (bytes / 1024 / 1024).toFixed(1) })
  }
}

/** The box's folders and files, and a viewer for the page, photo, recording or file you pick. */
export function BrowsePage() {
  const { box, boxVersion } = useCaixa()
  const store = useStore()
  const t = useT()
  const size = useSize()
  const [folder, setFolder] = useState('')
  const [entries, setEntries] = useState<FileEntry[] | undefined>()
  const [failure, setFailure] = useState<string | undefined>()
  const [hasIndex, setHasIndex] = useState(false)
  const [open, setOpen] = useState<FileEntry | { name: string; path: string } | undefined>()

  useEffect(() => {
    let current = true
    if (!box) return
    setEntries(undefined)
    void store.api.browse(folder === '' ? undefined : folder).then((reply) => {
      if (!current) return
      if (reply.ok) {
        setEntries([...reply.result.entries])
        setFailure(undefined)
        if (folder === '') setHasIndex(reply.result.entries.some(entry => entry.name === 'index.html' && entry.kind === 'file'))
      } else setFailure(reply.error.message)
    })
    return () => { current = false }
  }, [store, box?.root, folder, boxVersion])

  if (!box) return <p className={css.banner}>{t('import.needBox')}</p>

  const parts = folder === '' ? [] : folder.split('/')
  const crumb = (index: number) => parts.slice(0, index + 1).join('/')

  return (
    <div className={css.section}>
      <h2>{t('browse.heading')}</h2>
      {hasIndex && (
        <p><button type="button" className={css.button} onClick={() => setOpen({ name: 'index.html', path: 'index.html' })}>{t('browse.index')}</button></p>
      )}
      <nav className={css.crumbs} aria-label={t('browse.path')}>
        <button type="button" className={css.link} onClick={() => setFolder('')} aria-current={folder === '' ? 'location' : undefined}>{t('browse.root')}</button>
        {parts.map((part, index) => (
          <span key={crumb(index)}>/ <button type="button" className={css.link} onClick={() => setFolder(crumb(index))}
                                              aria-current={index === parts.length - 1 ? 'location' : undefined}>{part}</button></span>
        ))}
      </nav>
      {failure && <p className={css.error} role="alert">{t('common.error', { message: failure })}</p>}
      <div className={css.browser}>
        <div className={css.listPane}>
          {!entries && !failure && <p className={css.muted}>{t('common.loading')}</p>}
          {entries && entries.length === 0 && <p className={css.muted}>{folder === '' ? t('browse.boxEmpty') : t('browse.empty')}</p>}
          {entries && entries.length > 0 && (
            <ul className={css.entries}>
              {entries.map(entry => (
                <li key={entry.path}>
                  {entry.kind === 'directory'
                    ? <button type="button" className={css.link} onClick={() => { setFolder(entry.path); setOpen(undefined) }}>{entry.name}/</button>
                    : <button type="button" className={css.link} onClick={() => setOpen(entry)} aria-label={`${t('browse.open')} ${entry.name}`}
                              aria-current={open?.path === entry.path ? 'true' : undefined}>{entry.name}</button>}
                  {entry.kind === 'file' && <span className={css.size}>{size(entry.size)}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className={css.viewer}>
          {open ? <Viewer name={open.name} path={open.path} /> : <p className={css.muted}>{t('browse.pick')}</p>}
        </div>
      </div>
    </div>
  )
}

function Viewer({ name, path }: { name: string; path: string }) {
  const t = useT()
  const url = boxUrl(path)
  const kind = kindOf(name)
  const link = <p><a href={url} target="_blank" rel="noopener noreferrer">{t('browse.newTab')}</a></p>
  if (kind === 'page' || kind === 'text') {
    // No scripts run in the frame (the file is served under a policy that forbids them), and its
    // sandbox only lets it keep its own address so its links to other pages work.
    return <>{link}<iframe className={css.frame} title={t('browse.frame', { name })} src={url} sandbox="allow-same-origin" /></>
  }
  if (kind === 'image') return <>{link}<img className={css.media} src={url} alt={name} /></>
  if (kind === 'audio') return <>{link}<audio className={css.progress} controls src={url} aria-label={name} /></>
  if (kind === 'video') return <>{link}<video className={css.media} controls src={url} aria-label={name} /></>
  return (
    <>
      <p>{t('browse.noPreview')}</p>
      <p><a href={url} download={name}>{t('browse.download', { name })}</a></p>
    </>
  )
}
