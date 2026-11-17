import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globalSetup: ['./tests/global-setup.ts'],
    // What Caixa remembers between runs (the last box) lives in a per-user folder. Workers the tests
    // start must not write to a real one, so the whole run gets its own.
    env: { CAIXA_HOME: mkdtempSync(join(tmpdir(), 'caixa-test-home-')) },
  },
})
