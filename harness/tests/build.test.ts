import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'
import { beforeAll, describe, expect, it } from 'vitest'
import { clientOptions } from '../scripts/preset.mjs'

const root = fileURLToPath(new URL('..', import.meta.url))
const manifest = JSON.parse(readFileSync(`${root}/package.json`, 'utf8'))

// DSH loads a plugin's browser half as `window.__ModuleLoader__.load({ id, factory })`. The preset
// that builds DSH's own plugins is not published, so scripts/build.mjs reproduces its contract and
// these tests hold it to it.
describe('the browser bundle', () => {
  // Built in memory: other tests (and a running dsh) read lib/, so this never writes there.
  let code = ''
  beforeAll(async () => {
    const result = await build({ ...clientOptions(manifest, root), write: false })
    code = result.outputFiles!.find(file => file.path.endsWith('.js'))!.text
  })

  it('registers itself under the package name with a factory', () => {
    expect(code.startsWith(`window.__ModuleLoader__.load({ id: ${JSON.stringify(manifest.name)}, factory: (require) =>`)).toBe(true)
    expect(code.trimEnd().split('\n').filter(l => !l.startsWith('//#')).pop()).toBe('return module.exports; } });')
  })

  it('asks the module table only for modules DSH shares', () => {
    const asked = [...code.matchAll(/require\("([^"]+)"\)/g)].map(m => m[1]!)
    const shared = ['react', 'react/jsx-runtime', 'react-dom', 'react-dom/client', '@deepseek-ai/cordis',
      '@deepseek-ai/dsh-client-ui-slots', '@deepseek-ai/dsh-client-ui-primitives', ...manifest.dsh.client.inject]
    expect(asked.filter(name => !shared.includes(name))).toEqual([])
  })

  it('hands DSH an apply function and the services it needs, when run against a loader', () => {
    let loaded: { id: string; factory: (require: (id: string) => unknown) => Record<string, unknown> } | undefined
    const window = { __ModuleLoader__: { load: (entry: typeof loaded) => { loaded = entry } } }
    new Function('window', code)(window)
    const exports = loaded!.factory((id) => {
      if (id === 'react/jsx-runtime') return { jsx: () => null, jsxs: () => null, Fragment: 'f' }
      if (id === 'react') return new Proxy({ createContext: () => ({ Provider: 'Provider' }) }, { get: (target, name: string) => (target as Record<string, unknown>)[name] ?? (() => undefined) })
      throw new Error(`unexpected require(${id})`)
    })
    expect(typeof exports.apply).toBe('function')
    expect(exports.inject).toEqual(['slots', 'locale'])
  })

  it('refuses to bundle a DSH package it was not told to share', async () => {
    const { writeFileSync, mkdtempSync, rmSync } = await import('node:fs')
    const { tmpdir } = await import('node:os')
    const folder = mkdtempSync(`${tmpdir()}/caixa-gate-`)
    try {
      writeFileSync(`${folder}/entry.ts`, "import { x } from '@deepseek-ai/dsh-client-ui-chat'\nexport const y = x\n")
      const attempt = (inject: string[]) => build({
        ...clientOptions({ ...manifest, dsh: { client: { inject } } }, root),
        entryPoints: [`${folder}/entry.ts`],
        write: false,
      })
      await expect(attempt([])).rejects.toThrow(/not a module DSH shares/)
      const allowed = await attempt(['@deepseek-ai/dsh-client-ui-chat'])
      expect(allowed.outputFiles?.find(f => f.path.endsWith('.js'))?.text).toContain('require("@deepseek-ai/dsh-client-ui-chat")')
    } finally {
      rmSync(folder, { recursive: true, force: true })
    }
  })

  it('names the files the package ships, its patch and the exact DSH version', () => {
    expect(manifest.files).toEqual(expect.arrayContaining(['lib/index.js', 'lib/client.js', 'cordis.patch.yml']))
    expect(manifest.dsh.bundle.patch).toBe('./cordis.patch.yml')
    expect(manifest.engines.dsh).toBe('0.2.2-alpha.2')
    expect(manifest.devDependencies['@deepseek-ai/dsh']).toBe('0.2.2-alpha.2')
  })
})

describe('stylesheets', () => {
  it('compiles x.module.css into hashed class names and injects them once, tagged with the plugin', async () => {
    const { mkdtempSync, mkdirSync, rmSync, writeFileSync } = await import('node:fs')
    const { tmpdir } = await import('node:os')
    const folder = mkdtempSync(`${tmpdir()}/caixa-css-`)
    try {
      mkdirSync(`${folder}/src/client`, { recursive: true })
      writeFileSync(`${folder}/src/client/a.module.css`, '.card { color: red; } .card:hover { color: blue; }\n.other { margin: 0 }')
      writeFileSync(`${folder}/src/client/index.tsx`, "import styles from './a.module.css'\nexport const names = styles\n")
      const result = await build({ ...clientOptions(manifest, folder), write: false })
      const text = result.outputFiles!.find(file => file.path.endsWith('.js'))!.text
      // Run the bundle against a fake page, as DSH would, and read what it did.
      const styles: { dataset: Record<string, string>; textContent: string }[] = []
      const document = {
        querySelector: (selector: string) => styles.find(s => selector.includes(JSON.stringify(s.dataset.pluginCss))) ?? null,
        createElement: () => ({ dataset: {} as Record<string, string>, textContent: '' }),
        head: { appendChild: (element: (typeof styles)[number]) => { styles.push(element) } },
      }
      let loaded: { factory: (require: (id: string) => unknown) => { names: Record<string, string> } } | undefined
      const window = { __ModuleLoader__: { load: (entry: typeof loaded) => { loaded = entry } } }
      new Function('window', 'document', text)(window, document)
      const run = () => loaded!.factory(() => { throw new Error('no requires expected') }).names
      const names = run()
      expect(names.card).toMatch(/^[\w-]+_card$/)
      expect(names.other).toMatch(/^[\w-]+_other$/)
      expect(styles).toHaveLength(1)
      expect(styles[0]!.dataset.plugin).toBe(manifest.name)
      expect(styles[0]!.dataset.pluginCss).toBe(`${manifest.name}/a.module.css`)
      expect(styles[0]!.textContent).toContain(`.${names.card}`) // the css uses the hashed name
      run() // loading the module again must not add a second copy of the style
      expect(styles).toHaveLength(1)
    } finally {
      rmSync(folder, { recursive: true, force: true })
    }
  })
})
