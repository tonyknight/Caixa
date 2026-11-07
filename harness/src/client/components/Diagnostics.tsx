import { useId, useState } from 'react'
import { useStore, useT } from '../hooks.tsx'
import css from '../caixa.module.css'

/**
 * A button that asks the worker for a diagnostic report (about a source, when one is given) and
 * shows it to copy. The report holds no names or numbers; it is made for pasting into a message.
 */
export function DiagnosticsReport({ collector, source }: { collector?: string; source?: string }) {
  const store = useStore()
  const t = useT()
  const id = useId()
  const [text, setText] = useState<string | undefined>()
  const [working, setWorking] = useState(false)
  const [failure, setFailure] = useState<string | undefined>()
  const [copied, setCopied] = useState(false)

  const create = async () => {
    setWorking(true)
    setFailure(undefined)
    setCopied(false)
    const reply = await store.api.diagnostics(collector, source)
    setWorking(false)
    if (reply.ok) setText(reply.result.text)
    else setFailure(reply.error.message)
  }
  const copy = async () => {
    try { await navigator.clipboard.writeText(text ?? ''); setCopied(true) } catch { /* the text can still be selected by hand */ }
  }

  return (
    <div>
      <button type="button" className={css.button} disabled={working} onClick={() => void create()}>
        {working ? t('diagnostics.working') : t('diagnostics.create')}
      </button>
      {failure && <p className={css.error} role="alert">{t('diagnostics.failed', { message: failure })}</p>}
      {text !== undefined && (
        <div>
          <label className={css.field} htmlFor={id}>{t('diagnostics.label')}</label>
          <textarea id={id} className={css.report} readOnly rows={14} value={text} onFocus={event => event.target.select()} />
          <div className={css.actions}>
            <button type="button" className={css.button} onClick={() => void copy()}>{t('diagnostics.copy')}</button>
            {copied && <span role="status">{t('diagnostics.copied')}</span>}
          </div>
        </div>
      )}
    </div>
  )
}

/** A refusal's message as a first line and a list of the lines that follow (what was found, what was wanted). */
export function Reasons({ message }: { message: string }) {
  const [first = '', ...rest] = message.split('\n').filter(line => line.trim() !== '')
  return (
    <>
      <span>{first}</span>
      {rest.length > 0 && <ul>{rest.map((line, index) => <li key={index}>{line}</li>)}</ul>}
    </>
  )
}
