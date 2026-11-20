import { useEffect, useState } from 'react'
import { useStore, useT } from '../hooks.tsx'
import { size, type MailMessage, type PreviewMail, type SenderRow } from './types.ts'
import css from './mail.module.css'

const when = (iso: string) => iso.replace('T', ' ').slice(0, 16)

/**
 * A sender's mail over the window, latest first (subject, date, the first words), and one mail in
 * full when it is chosen. Everything is shown as text: a mail's HTML is never drawn here. Escape, the
 * cross or a click beside it closes it.
 */
export function Preview({ source, sender, onClose }: { source: number; sender: SenderRow; onClose: () => void }) {
  const store = useStore()
  const t = useT()
  const [mails, setMails] = useState<readonly PreviewMail[] | undefined>()
  const [open, setOpen] = useState<MailMessage | undefined>()
  const [failure, setFailure] = useState<string | undefined>()

  useEffect(() => {
    let current = true
    void store.api.call<{ mails: PreviewMail[] }>('mail.preview', { source, address: sender.address }).then((reply) => {
      if (!current) return
      if (reply.ok) setMails(reply.result.mails)
      else setFailure(reply.error.message)
    })
    return () => { current = false }
  }, [store, source, sender.address])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const read = async (mail: PreviewMail) => {
    const reply = await store.api.call<MailMessage>('mail.message', { source, position: mail.position })
    if (reply.ok) setOpen(reply.result)
    else setFailure(reply.error.message)
  }
  const people = (list: readonly (readonly [string, string])[]) => list.map(([name, address]) => (name ? `${name} <${address}>` : address)).join(', ')
  const title = t('mail.preview.title', { name: sender.name })

  return (
    <div className={css.backdrop} onClick={onClose}>
      <div className={css.overlay} role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <div className={css.overlayHead}>
          <h2>{title}</h2>
          <button type="button" className={css.close} aria-label={t('mail.preview.close')} onClick={onClose}>{'×'}</button>
        </div>
        {failure && <p className={css.problem}>{t('mail.failed', { message: failure })}</p>}
        {open ? (
          <article className={css.message}>
            <button type="button" className={css.back} onClick={() => setOpen(undefined)}>{'← '}{t('mail.preview.back', { name: sender.name })}</button>
            <h3>{open.subject}</h3>
            <dl className={css.headers}>
              <dt>{t('mail.preview.from')}</dt><dd>{people([open.from])}</dd>
              {open.to.length > 0 && <><dt>{t('mail.preview.to')}</dt><dd>{people(open.to)}</dd></>}
              {open.cc.length > 0 && <><dt>{t('mail.preview.cc')}</dt><dd>{people(open.cc)}</dd></>}
              <dt>{' '}</dt><dd>{open.date}</dd>
              {open.attachments.length > 0 && <><dt>{t('mail.preview.files')}</dt><dd>{open.attachments.join(', ')}</dd></>}
            </dl>
            <div className={css.text}>{open.text}</div>
          </article>
        ) : (
          <ul className={css.mails}>
            {mails?.length === 0 && <li className={css.empty}>{t('mail.preview.none')}</li>}
            {mails?.map(mail => (
              <li key={mail.position}>
                <button type="button" className={css.mailButton} onClick={() => void read(mail)}>
                  <span className={css.mailTop}><strong>{mail.subject || '—'}</strong><time>{when(mail.date)}</time></span>
                  <span className={css.snippet}>{mail.snippet}</span>
                  <span className={css.mailMeta}>{size(mail.size)}{mail.attachments ? ` · \u{1f4ce} ${mail.attachments}` : ''}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
