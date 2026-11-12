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
import { isShell, makeApi } from './api.ts'
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

export const inject = ['slots', 'locale', 'layout']

/** The harness's own name, wherever it puts it in the window's title. */
const HARNESS_NAME = 'DeepSeek Harness'
const OUR_NAME = 'Caixa'

/** Keep the window's title saying Caixa: the harness writes its own name there on every change. */
export function ownTitle(document: Document): () => void {
  const fix = () => { if (document.title.includes(HARNESS_NAME)) document.title = document.title.split(HARNESS_NAME).join(OUR_NAME) }
  fix()
  const title = document.querySelector('title')
  if (!title || typeof MutationObserver === 'undefined') return () => undefined
  const observer = new MutationObserver(fix)
  observer.observe(title, { childList: true, characterData: true, subtree: true })
  return () => observer.disconnect()
}

function BrandName() {
  return <span style={{ fontWeight: 600, fontSize: '1.05rem' }}>{OUR_NAME}</span>
}
function BrandMark() {
  return <CaixaIcon size={22} />
}

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

  // Started by `caixa serve`, the window is Caixa's own: its name and mark where the harness shows
  // its brand, its name in the title, and its page first. Inside someone's own harness Caixa stays a
  // guest: one more panel, nothing renamed.
  let stopTitle: (() => void) | undefined
  let left = false
  ctx.effect(() => () => { left = true; stopTitle?.() }, 'caixa: shell')
  void isShell().then((shell) => {
    if (!shell || left) return
    stopTitle = ownTitle(document)
    ctx.slots.inject('sidebar.brand.mark', () => ctx.slots.inject('sidebar.brand.name', function* () {
      yield ctx.slots.register({ name: 'sidebar.brand.mark' } as never, BrandMark as never)
      yield ctx.slots.register({ name: 'sidebar.brand.name' } as never, BrandName as never)
    } as never))
    try { (ctx as unknown as { layout: { selectPanel(id: string): void } }).layout.selectPanel(PANEL_ID) } catch { /* the page is not mounted yet: it is one click away */ }
  })
}
