import { useCaixa, useStore, useT } from './hooks.tsx'
import type { Toast } from './store.ts'
import css from './caixa.module.css'

function Message({ toast }: { toast: Toast }) {
  const t = useT()
  if (toast.outcome === 'done') return <>{t('toast.done', { name: toast.collector, count: toast.inserted })}</>
  if (toast.outcome === 'failed') return <>{t('toast.failed', { name: toast.collector, error: toast.error ?? '' })}</>
  if (toast.outcome === 'cancelled') return <>{t('toast.cancelled', { name: toast.collector })}</>
  return <>{t('toast.interrupted', { name: toast.collector })}</>
}

/** Notices about imports that ended. Registered in DSH's `shell.overlay`, so they show on any DSH page. */
export function ToastHost() {
  const { toasts } = useCaixa()
  const store = useStore()
  const t = useT()
  if (toasts.length === 0) return null
  return (
    <div className={css.toasts} role="region" aria-label={t('toast.region')} aria-live="polite">
      {toasts.map(toast => (
        <div key={toast.id} className={`${css.toast} ${toast.outcome === 'failed' ? css.toastBad : ''}`} role="status">
          <p><Message toast={toast} /></p>
          <button type="button" className={css.link} onClick={() => store.dismissToast(toast.id)}>{t('toast.dismiss')}</button>
        </div>
      ))}
    </div>
  )
}
