import { describe, expect, it } from 'vitest'
import { Config, workerArguments } from '../src/host/index.ts'

describe('the worker command line', () => {
  const base = { command: ['caixa'], readOnly: false, roots: [], cwd: '' }

  it('starts with the program, then "worker"', () => {
    expect(workerArguments(base)).toEqual(['caixa', 'worker'])
    expect(workerArguments({ ...base, command: ['uv', 'run', 'caixa'] })).toEqual(['uv', 'run', 'caixa', 'worker'])
  })

  it('adds the box, read-only and the picker folders', () => {
    expect(workerArguments({ ...base, box: '/b', readOnly: true, roots: ['/a', '/c'] }))
      .toEqual(['caixa', 'worker', '--box', '/b', '--read-only', '--root', '/a', '--root', '/c'])
  })

  it('has a schema DSH can validate, with the defaults a plain install needs', () => {
    const validate = Config as unknown as (value: unknown) => unknown
    expect(validate({})).toEqual({ command: ['caixa'], readOnly: false, roots: [], cwd: '' })
    expect(() => validate({ readOnly: 'yes' })).toThrow()
  })
})
