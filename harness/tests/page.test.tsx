// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CaixaPage } from '../src/client/CaixaPage.tsx'
import { dictionaries, en, zh } from '../src/client/locales.ts'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const t = (key: string, values: Record<string, string> = {}) =>
  (en as Record<string, string>)[key]!.replace(/\{(\w+)\}/g, (_, name: string) => values[name] ?? '')

function serve(state: string, info = { version: '1.2.3', read_only: false }) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith('/status') ? { worker: state } : { ok: true, result: info },
  ))))
}

describe('the Caixa page', () => {
  it('says the worker is running, with its version', async () => {
    serve('running')
    render(<CaixaPage t={t} />)
    expect(screen.getByRole('heading', { name: 'Caixa' })).toBeTruthy()
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('running (version 1.2.3)'))
  })

  it('says when the box is open read-only', async () => {
    serve('running', { version: '1', read_only: true })
    render(<CaixaPage t={t} />)
    await waitFor(() => expect(screen.getByText(en['worker.readOnly'])).toBeTruthy())
  })

  it('explains a worker that could not start and offers to check again', async () => {
    serve('failed')
    render(<CaixaPage t={t} />)
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe(en['worker.failed']))
    expect(screen.getByRole('button', { name: en['worker.retry'] })).toBeTruthy()
  })
})

describe('the text', () => {
  it('has English and Chinese with the same keys, and every {placeholder} in both', () => {
    expect(Object.keys(zh).sort()).toEqual(Object.keys(en).sort())
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      const holes = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
      expect(holes(zh[key]), key).toBe(holes(en[key]))
    }
    expect(Object.keys(dictionaries)).toEqual(['en', 'zh'])
  })
})
