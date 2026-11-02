// A stand-in for `caixa worker` that speaks the same line protocol, for the supervisor's tests.
// Methods: "echo" answers with its params, "fail" answers an error, "notify" sends a notification,
// "die" exits at once, "hang" never answers, "junk" prints a line that is not JSON before
// answering, "box.open" remembers the path and "opened" lists them.
import { createInterface } from 'node:readline'

const reply = (message) => process.stdout.write(JSON.stringify({ jsonrpc: '2.0', ...message }) + '\n')
const opened = []
createInterface({ input: process.stdin }).on('line', (line) => {
  const { id, method, params } = JSON.parse(line)
  if (method === 'echo') return reply({ id, result: params })
  if (method === 'box.open') { opened.push(params.path); return reply({ id, result: { opened } }) }
  if (method === 'opened') return reply({ id, result: opened })
  if (method === 'fail') return reply({ id, error: { code: -32000, message: 'Nope.', data: { kind: 'conflict' } } })
  if (method === 'notify') { reply({ method: 'job.progress', params: { job: 1 } }); return reply({ id, result: 'sent' }) }
  if (method === 'die') process.exit(3)
  if (method === 'junk') { process.stdout.write('this is not json\n'); return reply({ id, result: 'after junk' }) }
  if (method === 'hang') return
  reply({ id, error: { code: -32601, message: 'unknown', data: { kind: 'unknown_method' } } })
}).on('close', () => process.exit(0))
