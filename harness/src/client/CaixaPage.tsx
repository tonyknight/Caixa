import { useCallback, useEffect, useState } from 'react'
import { call, workerState, type WorkerState } from './api.ts'

/** What the page needs from its host: translated text. */
export interface CaixaPageInjected {
  readonly t: (key: string, values?: Record<string, string>) => string
}

interface Info {
  readonly version: string
  readonly read_only: boolean
}

/** The Caixa page. For now it only says whether the worker is there; later tickets add the pages. */
export function CaixaPage({ t }: CaixaPageInjected) {
  const [state, setState] = useState<WorkerState | 'checking'>('checking')
  const [info, setInfo] = useState<Info | undefined>()

  const check = useCallback(async () => {
    setState('checking')
    const current = await workerState()
    setState(current)
    if (current !== 'running') return setInfo(undefined)
    const reply = await call<Info>('worker.info')
    setInfo(reply.ok ? reply.result : undefined)
  }, [])

  useEffect(() => { void check() }, [check])

  return (
    <main style={{ padding: '2rem', maxWidth: '44rem' }} data-testid="caixa-page">
      <h1>{t('page.title')}</h1>
      <p>{t('page.lead')}</p>
      <p role="status">
        {state === 'checking' && t('worker.checking')}
        {state === 'running' && t('worker.running', { version: info?.version ?? '' })}
        {state === 'restarting' && t('worker.restarting')}
        {state === 'failed' && t('worker.failed')}
        {state === 'stopped' && t('worker.stopped')}
      </p>
      {info?.read_only && <p>{t('worker.readOnly')}</p>}
      {state !== 'running' && state !== 'checking' && (
        <button type="button" onClick={() => void check()}>{t('worker.retry')}</button>
      )}
    </main>
  )
}
