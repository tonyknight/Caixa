import type { BuildOptions } from 'esbuild'

export const PLATFORM_MODULES: readonly string[]
/** esbuild options for the browser half of a plugin whose package.json is `manifest`. */
export function clientOptions(
  manifest: { name: string; dsh?: { client?: { inject?: string[] } } },
  root: string,
): BuildOptions
