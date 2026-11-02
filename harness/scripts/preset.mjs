// The browser build's contract with DSH. (Used by build.mjs and its tests.)
//
// The browser half must be in the form DSH's module system loads. DSH builds its own plugins with a
// tsdown preset that is not published, so this reproduces its contract (see
// packages/client/tsdown.client.ts in deepseek-harness at the pinned version):
//
//   window.__ModuleLoader__.load({ id: "<package name>", factory: (require) => { …; return module.exports } })
//
// - CommonJS body, wrapped in that factory; `module`/`exports` are declared inside it;
// - every module DSH shares (react, the cordis framework, the slot and primitive libraries, and the
//   packages this plugin lists under `dsh.client.inject`) stays a `require(...)` answered by DSH's
//   module table; everything else is bundled in;
// - no other `@deepseek-ai/*` value import is allowed (it would duplicate a runtime DSH shares);
// - a source map accompanies it.


export const PLATFORM_MODULES = [
  'react', 'react/jsx-runtime', 'react-dom', 'react-dom/client', '@deepseek-ai/cordis',
  'zod', '@tanstack/react-virtual',
  '@deepseek-ai/dsh-client-store',
  '@deepseek-ai/dsh-client-ui-slots',
  '@deepseek-ai/dsh-client-ui-primitives',
  '@deepseek-ai/dsh-client-ui-dockkit',
]

/** esbuild options for the browser half of a plugin whose package.json is `manifest`. */
export function clientOptions(manifest, root) {
  const requested = new Set([...PLATFORM_MODULES, ...(manifest.dsh?.client?.inject ?? [])])
  const isRequested = (specifier) =>
    [...requested].some(name => specifier === name || specifier.startsWith(`${name}/`))
  const purity = {
    name: 'caixa-client-purity',
    setup(b) {
      b.onResolve({ filter: /^@deepseek-ai\// }, (args) => {
        if (isRequested(args.path)) return { path: args.path, external: true }
        return { errors: [{ text: `"${args.path}" is not a module DSH shares with plugins; list it under dsh.client.inject in package.json, or collaborate through cordis services.` }] }
      })
      b.onResolve({ filter: /^(react|react-dom)(\/.*)?$/ }, (args) => ({ path: args.path, external: true }))
    },
  }
  return {
    bundle: true,
    sourcemap: true,
    logLevel: 'silent',
    absWorkingDir: root,
    entryPoints: { client: 'src/client/index.tsx' },
    outfile: 'lib/client.js',
    format: 'cjs',
    platform: 'browser',
    target: 'es2022',
    jsx: 'automatic',
    plugins: [purity],
    define: { 'process.env.NODE_ENV': '"production"' },
    banner: { js: `window.__ModuleLoader__.load({ id: ${JSON.stringify(manifest.name)}, factory: (require) => { var module = { exports: {} }; var exports = module.exports;` },
    footer: { js: 'return module.exports; } });' },
  }
}
