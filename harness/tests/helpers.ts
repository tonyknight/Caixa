import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { WorkerProcess } from '../src/host/worker-client.ts'

export const FAKE = fileURLToPath(new URL('./fixtures/fake-worker.mjs', import.meta.url))

/**
 * A command line for a real `caixa worker` with a Caixa folder of its own, so it starts with no box
 * open: a worker reopens the box that was open last time, and tests must not meet each other's.
 */
export function withOwnHome(command: string[]): string[] {
  return ['env', `CAIXA_HOME=${mkdtempSync(join(tmpdir(), 'caixa-worker-home-'))}`, ...command]
}

/** Start a plain child process as a worker: the fake one, or any command line. */
export function launchProcess(command: string[] = [process.execPath, FAKE]): () => WorkerProcess {
  return () => {
    const child = spawn(command[0]!, command.slice(1), { stdio: ['pipe', 'pipe', 'inherit'] })
    return {
      stdin: child.stdin!,
      stdout: child.stdout!,
      done: new Promise(resolve => child.on('close', resolve)),
      stop: () => { child.kill('SIGTERM') },
    }
  }
}

export const until = async (ok: () => boolean, ms = 10_000): Promise<void> => {
  const end = Date.now() + ms
  while (!ok()) {
    if (Date.now() > end) throw new Error('timed out waiting')
    await new Promise(resolve => setTimeout(resolve, 20))
  }
}
