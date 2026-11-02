import { createContext, useContext, useSyncExternalStore, type ReactNode } from 'react'
import type { CaixaKey } from './locales.ts'
import type { State, Store } from './store.ts'

export type Translate = (key: CaixaKey, values?: Record<string, string | number>) => string

const StoreContext = createContext<Store | undefined>(undefined)
const TranslateContext = createContext<Translate | undefined>(undefined)

/** Give the pages their store and their translator. */
export function Providers({ store, t, children }: { store: Store; t: Translate; children: ReactNode }) {
  return (
    <StoreContext.Provider value={store}>
      <TranslateContext.Provider value={t}>{children}</TranslateContext.Provider>
    </StoreContext.Provider>
  )
}

export function useStore(): Store {
  const store = useContext(StoreContext)
  if (!store) throw new Error('Caixa pages must be inside <Providers>')
  return store
}

export function useCaixa(): State {
  const store = useStore()
  return useSyncExternalStore(store.subscribe, store.getState, store.getState)
}

export function useT(): Translate {
  const t = useContext(TranslateContext)
  if (!t) throw new Error('Caixa pages must be inside <Providers>')
  return t
}

/** `t` that fills `{name}` holes: what a plain dictionary needs (DSH's own `t` does this itself). */
export function translator(dictionary: Record<string, string>, fallback: Record<string, string> = dictionary): Translate {
  return (key, values = {}) =>
    (dictionary[key] ?? fallback[key] ?? key).replace(/\{(\w+)\}/g, (_, name: string) => String(values[name] ?? ''))
}
