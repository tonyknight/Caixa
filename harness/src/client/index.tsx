/**
 * The browser half of Caixa's plugin: one sidebar icon that opens the Caixa page.
 *
 * It registers into DSH's slots the way DSH's own pages do (`main` for the page, `sidebar.panellist`
 * for the icon) and talks to Python only through `/api/caixa/*` (see `api.ts`).
 */

import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type {} from '@deepseek-ai/dsh-client-ui-layout/client'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'
import { CaixaIcon } from './CaixaIcon.tsx'
import { CaixaPage, type CaixaPageInjected } from './CaixaPage.tsx'
import { NS, dictionaries, type CaixaKey } from './locales.ts'

declare module '@deepseek-ai/dsh-client-ui-slots' {
  interface LocaleNamespaceMap {
    /** Copy for Caixa's pages. */
    caixa: CaixaKey
  }
}

export const inject = ['slots', 'locale']

const PANEL_ID = 'caixa'

// DSH types its slots and dictionaries per registration; the casts below only widen that typing
// for a component whose text comes from the `t` it is given. The tests and the end-to-end run check
// what the types would.
export function apply(ctx: Context): void {
  ctx.effect(() => ctx.locale.register(NS, dictionaries), 'caixa: dictionaries')
  const t = ctx.locale.bind(NS)
  ctx.slots.inject('main', () => ctx.slots.register({
    name: 'main',
    key: PANEL_ID,
    locale: NS,
    inject: (): CaixaPageInjected => ({ t: (key, values) => t(key as never, values as never) }),
  }, CaixaPage as never))
  ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
    name: 'sidebar.panellist',
    id: PANEL_ID,
    order: 20,
    locale: NS,
    label: () => t('panel' as never),
  }, CaixaIcon as never))
}
