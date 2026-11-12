/**
 * The host half of Caixa's plugin: runs `caixa worker` and opens it to the browser.
 *
 * Everything that touches the archive happens in Python. This plugin starts the worker as a managed
 * child process through DSH's subprocess service, keeps it running (see `worker-client.ts`), and
 * registers `/api/caixa/*` routes on DSH's connection. Those routes are owner-only and sit behind
 * DSH's launch token, signed cookie and Host/Origin checks, so the worker has no network listener
 * and is never reachable directly.
 */

import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'
import type {} from '@deepseek-ai/dsh-client-connection'
import type {} from '@deepseek-ai/dsh-subprocess'
import { caixaRoutes } from './routes.ts'
import { WorkerClient, type WorkerProcess } from './worker-client.ts'

export const name = 'caixa'
export const inject = ['connection', 'subprocess']

export interface Config {
  /** The program that runs the worker and any leading arguments; `worker` and the flags follow. */
  command: string[]
  /** A box to open when the worker starts; the browser can open another. */
  box?: string
  /** Refuse every method that would change the box. */
  readOnly: boolean
  /** A folder the file picker may show besides the home folder (repeatable). */
  roots: string[]
  /** Where the worker runs; empty means the folder DSH was started in. */
  cwd: string
  /** True when the harness was started by `caixa serve`: the window is Caixa's own (its name, its page first). */
  shell: boolean
}

export const Config: Schema<Config> = Schema.object({
  command: Schema.array(Schema.string()).default(['caixa']).description('Program (and leading arguments) that runs `caixa worker`.'),
  box: Schema.string().description('A box to open when the worker starts.'),
  readOnly: Schema.boolean().default(false).description('Refuse every method that would change the box.'),
  roots: Schema.array(Schema.string()).default([]).description('Extra folders the file picker may show.'),
  cwd: Schema.string().default('').description('Where the worker runs; empty means the folder DSH was started in.'),
  shell: Schema.boolean().default(false).description('The harness was started by `caixa serve`: show Caixa\'s name and open on its page.'),
})

/** The worker's command line for a configuration. */
export function workerArguments(config: Config): string[] {
  const args = [...config.command, 'worker']
  if (config.box) args.push('--box', config.box)
  if (config.readOnly) args.push('--read-only')
  for (const root of config.roots) args.push('--root', root)
  return args
}

export function apply(ctx: Context, config: Config): void {
  const argv = workerArguments(config)
  const cwd = config.cwd || process.cwd()

  const launch = (executable: string): (() => WorkerProcess) => () => {
    const handle = ctx.subprocess.spawn({
      argv: [executable, ...argv.slice(1)],
      cwd,
      stdio: { stdin: 'pipe', stdout: 'pipe', stderr: 'inherit' },
      graceMs: 5000,
    })
    if (!handle.stdin || !handle.stdout) throw new Error('the subprocess service gave no pipes')
    return {
      stdin: handle.stdin,
      stdout: handle.stdout,
      done: handle.done.catch(() => undefined),
      stop: () => handle.terminate(),
    }
  }

  const log = (message: string) => ctx.logger('caixa').warn(message)
  let client: WorkerClient | undefined
  const routes: (() => Promise<void>)[] = []

  ctx.effect(() => () => {
    void Promise.all(routes.map(dispose => dispose()))
    return client?.close()
  }, 'caixa: worker and routes')

  void ctx.subprocess.resolveExecutable(argv[0]!).then((executable) => {
    client = new WorkerClient(launch(executable), { log })
    for (const route of caixaRoutes(client, { shell: config.shell })) routes.push(ctx.connection.fetch.register(route))
    client.start()
  }, (error: unknown) => {
    // No `caixa` program: the routes still answer, with a plain "not running" the page can show.
    log(`cannot start the Caixa worker: ${String(error)}`)
    client = new WorkerClient(() => { throw error instanceof Error ? error : new Error(String(error)) }, { log })
    for (const route of caixaRoutes(client, { shell: config.shell })) routes.push(ctx.connection.fetch.register(route))
    client.start()
  })
}
