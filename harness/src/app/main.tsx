/**
 * Caixa's own browser interface: the Caixa page on a page of its own, served by `caixa serve`
 * (Python, see `caixa/web.py`). Nothing here comes from DeepSeek Harness: the same pages, the same
 * store and the same `/api/caixa/*` calls, with Caixa's own translator and the Nord colours.
 */

import { createRoot } from 'react-dom/client'
import { makeApi } from '../client/api.ts'
import { CaixaPage } from '../client/CaixaPage.tsx'
import { Providers, type Translate } from '../client/hooks.tsx'
import { dictionaries, type CaixaKey } from '../client/locales.ts'
import { Store } from '../client/store.ts'
import { ToastHost } from '../client/Toasts.tsx'
import './app.css'

/** The dictionary for the browser's language (Chinese or English; anything else reads English). */
export function translator(languages: readonly string[]): Translate {
  const chosen = languages.some(language => language.toLowerCase().startsWith('zh')) ? dictionaries.zh : dictionaries.en
  return (key: CaixaKey, values?: Record<string, string | number>) => {
    const text = chosen[key] ?? dictionaries.en[key] ?? key
    return values ? text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in values ? String(values[name]) : whole)) : text
  }
}

function remembered() {
  const key = 'caixa.lastBox'
  return {
    get: () => { try { return localStorage.getItem(key) } catch { return null } },
    set: (path: string | null) => { try { path === null ? localStorage.removeItem(key) : localStorage.setItem(key, path) } catch { /* private window */ } },
  }
}

const root = document.getElementById('caixa')
if (root) {
  const store = new Store(makeApi(), { memory: remembered() })
  void store.start()
  const t = translator(navigator.languages?.length ? navigator.languages : [navigator.language ?? 'en'])
  document.documentElement.lang = t('page.title') === dictionaries.zh['page.title'] ? 'zh' : 'en'
  createRoot(root).render(
    <Providers store={store} t={t}>
      <CaixaPage />
      <ToastHost />
    </Providers>,
  )
}
