// @vitest-environment jsdom
import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { CaixaPage } from '../src/client/CaixaPage.tsx'
import { dictionaries, en, zh } from '../src/client/locales.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

describe('the Caixa page', () => {
  it('has a title, the lead and a navigation of sections, starting on the box', async () => {
    await renderWith(<CaixaPage />)
    expect(screen.getByRole('heading', { level: 1, name: 'Caixa' })).toBeTruthy()
    expect(screen.getByText('Collect, preserve and pass on a digital life.')).toBeTruthy()
    const nav = screen.getByRole('navigation', { name: 'Caixa sections' })
    expect(Array.from(nav.querySelectorAll('button')).map(b => b.textContent)).toEqual(['Box', 'Import', 'Jobs', 'People', 'Browse', 'Settings'])
    expect(screen.getByRole('button', { name: 'Box' }).getAttribute('aria-current')).toBe('page')
    expect(screen.getByRole('heading', { name: 'Our box' })).toBeTruthy()
  })

  it('moves between sections', async () => {
    const view = await renderWith(<CaixaPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Jobs' }))
    expect(screen.getByRole('heading', { name: 'Jobs' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Jobs' }).getAttribute('aria-current')).toBe('page')
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))
    await view.flush()
    expect(screen.getByText('Where do your messages come from?')).toBeTruthy()
  })

  it('says so, in words, when the worker is not there, and not when it is', async () => {
    const view = await renderWith(<CaixaPage />)
    expect(screen.queryByRole('status')).toBeNull()
    await view.emit('worker.state', { state: 'restarting' })
    expect(screen.getByRole('status').textContent).toBe(en['worker.restarting'])
    await view.emit('worker.state', { state: 'failed' })
    expect(screen.getByRole('status').textContent).toBe(en['worker.failed'])
    await view.emit('worker.state', { state: 'running' })
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('speaks Chinese when asked', async () => {
    await renderWith(<CaixaPage />, () => undefined, 'zh')
    expect(screen.getByText(zh['page.lead'])).toBeTruthy()
    expect(screen.getByRole('button', { name: zh['nav.import'] })).toBeTruthy()
  })
})

describe('the text', () => {
  it('has English and Chinese with the same keys, and every {placeholder} in both', () => {
    expect(Object.keys(zh).sort()).toEqual(Object.keys(en).sort())
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      const holes = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
      expect(holes(zh[key]), key).toBe(holes(en[key]))
      expect(zh[key].trim(), key).not.toBe('')
    }
    expect(Object.keys(dictionaries)).toEqual(['en', 'zh'])
  })

  it('has no key that no component uses', async () => {
    const { readFileSync, readdirSync, statSync } = await import('node:fs')
    const { join } = await import('node:path')
    const files: string[] = []
    const walk = (folder: string) => readdirSync(folder).forEach((name) => {
      const path = join(folder, name)
      statSync(path).isDirectory() ? walk(path) : /\.(tsx?|ts)$/.test(name) && name !== 'locales.ts' && files.push(path)
    })
    walk(join(import.meta.dirname, '../src/client'))
    const source = files.map(file => readFileSync(file, 'utf8')).join('\n')
    const dynamic = ['type.', 'input.', 'import.step.', 'stage.', 'status.', 'nav.', 'worker.', 'form.', 'toast.', 'people.', 'browse.', 'settings.']
    const unused = (Object.keys(en) as string[]).filter(key =>
      !source.includes(`'${key}'`) && !source.includes(`"${key}"`) && !dynamic.some(prefix => key.startsWith(prefix) && source.includes(`\`${prefix}`)))
    expect(unused).toEqual([])
  })
})
