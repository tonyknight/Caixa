/**
 * The browser half of Caixa's plugin: a sidebar icon that opens the Caixa page, and a toast host
 * that tells you when an import has ended wherever you are in DSH.
 *
 * It registers into DSH's slots the way DSH's own pages do (`main` for the page, `sidebar.panellist`
 * for the icon, `shell.overlay` for the toasts) and talks to Python only through `/api/caixa/*`
 * (see `api.ts`). One store, made when the plugin loads, feeds all of them.
 */

import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type {} from '@deepseek-ai/dsh-client-ui-layout/client'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'
import { makeApi } from './api.ts'
import { CaixaIcon } from './CaixaIcon.tsx'
import { CaixaPage } from './CaixaPage.tsx'
import { Providers, type Translate } from './hooks.tsx'
import { NS, dictionaries, type CaixaKey } from './locales.ts'
import { Store } from './store.ts'
import { ToastHost } from './Toasts.tsx'

declare module '@deepseek-ai/dsh-client-ui-slots' {
  interface LocaleNamespaceMap {
    /** Copy for Caixa's pages. */
    caixa: CaixaKey
  }
}

export const inject = ['slots', 'locale']

const PANEL_ID = 'caixa'

function remembered() {
  const key = 'caixa.lastBox'
  return {
    get: () => { try { return localStorage.getItem(key) } catch { return null } },
    set: (path: string | null) => { try { path === null ? localStorage.removeItem(key) : localStorage.setItem(key, path) } catch { /* private window */ } },
  }
}

// DSH types its slots and dictionaries per registration; the casts below only widen that typing
// for components whose text comes from the translator they are given. The tests and the end-to-end
// run check what the types would.
export function apply(ctx: Context): void {
  ctx.effect(() => ctx.locale.register(NS, dictionaries), 'caixa: dictionaries')
  const t = ctx.locale.bind(NS)
  const translate: Translate = (key, values) => t(key as never, values as never)
  const store = new Store(makeApi(), { memory: remembered() })
  void store.start()
  ctx.effect(() => () => store.stop(), 'caixa: store')

  const Page = () => <Providers store={store} t={translate}><CaixaPage /></Providers>
  const Toasts = () => <Providers store={store} t={translate}><ToastHost /></Providers>

  ctx.slots.inject('main', () => ctx.slots.register({
    name: 'main',
    key: PANEL_ID,
    locale: NS,
    inject: () => ({}),
  }, Page as never))
  ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
    name: 'sidebar.panellist',
    id: PANEL_ID,
    order: 20,
    locale: NS,
    label: () => t('panel' as never),
  }, CaixaIcon as never))
  ctx.slots.inject('shell.overlay', () => ctx.slots.register({
    name: 'shell.overlay',
    id: 'caixa.toasts',
    locale: NS,
    inject: () => ({}),
  }, Toasts as never))
}
