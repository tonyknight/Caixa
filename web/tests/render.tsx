import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { act } from 'react'
import { Providers, translator } from '../src/client/hooks.tsx'
import { en, zh } from '../src/client/locales.ts'
import { Store } from '../src/client/store.ts'
import { FakeApi, settle } from './fake-api.ts'

export const t = translator(en)

/** Render a page with a store over a fake worker; the store has already taken its first look. */
export async function renderWith(ui: ReactElement, setup: (api: FakeApi) => void = () => undefined, language: 'en' | 'zh' = 'en') {
  const api = new FakeApi()
  setup(api)
  const store = new Store(api, { toastMs: 0 })
  await act(async () => { await store.start() })
  const view = render(
    <Providers store={store} t={translator(language === 'en' ? en : zh, en)}>{ui}</Providers>,
  )
  /** Let pending promises (the fake worker's replies) land and React settle. */
  const flush = async () => { await act(async () => { await settle(); await settle() }) }
  /** Something the worker announced. */
  const emit = async (name: string, payload: unknown) => { await act(async () => { api.emit(name, payload); await settle(); await settle() }) }
  await flush() // the page's own first requests (a collector list, an inbox) have been answered
  return { api, store, flush, emit, ...view }
}
