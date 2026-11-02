/**
 * The options form, drawn from a collector's JSON Schema: no collector-specific code, so a new
 * collector appears in the wizard with its form already made.
 *
 * Supported (what the worker validates): string, integer, number, boolean, `enum`, `minimum`,
 * `maximum`, `default`, `title`, `description`.
 */

import type { OptionSpec, OptionsSchema } from './api.ts'

export type FieldKind = 'text' | 'number' | 'checkbox' | 'select'

export interface Field {
  readonly name: string
  readonly kind: FieldKind
  /** The schema's title, or the option's own name when it has none. */
  readonly label: string
  readonly help: string
  readonly integer: boolean
  readonly min?: number
  readonly max?: number
  readonly choices: readonly string[]
  readonly default: string | number | boolean | undefined
}

export type FormValues = Record<string, string | boolean>

export function fields(schema: OptionsSchema): Field[] {
  return Object.entries(schema.properties).map(([name, spec]) => field(name, spec))
}

function field(name: string, spec: OptionSpec): Field {
  const kind: FieldKind = spec.enum ? 'select' : spec.type === 'boolean' ? 'checkbox'
    : spec.type === 'integer' || spec.type === 'number' ? 'number' : 'text'
  return {
    name, kind, label: spec.title ?? name, help: spec.description ?? '',
    integer: spec.type === 'integer', min: spec.minimum, max: spec.maximum,
    choices: (spec.enum ?? []).map(String), default: spec.default,
  }
}

/** What each field shows before anyone touches it: the schema's default. */
export function initialValues(list: readonly Field[]): FormValues {
  return Object.fromEntries(list.map(f => [f.name, f.kind === 'checkbox' ? f.default === true : f.default === undefined ? '' : String(f.default)]))
}

export interface Problem {
  readonly key: 'form.whole' | 'form.number' | 'form.atLeast' | 'form.atMost'
  readonly values: Readonly<Record<string, string | number>>
}

/**
 * The options to send: only what differs from the defaults (so a job records what was chosen), typed
 * as the schema says. A blank number or text means "the default". Problems are per field.
 */
export function toOptions(list: readonly Field[], values: FormValues): { options: Record<string, unknown>; problems: Record<string, Problem> } {
  const options: Record<string, unknown> = {}
  const problems: Record<string, Problem> = {}
  for (const f of list) {
    const raw = values[f.name]
    if (f.kind === 'checkbox') {
      if (raw !== (f.default === true)) options[f.name] = raw === true
      continue
    }
    const text = String(raw ?? '').trim()
    if (f.kind === 'number') {
      if (text === '') continue
      const n = Number(text)
      if (!Number.isFinite(n)) { problems[f.name] = { key: 'form.number', values: { name: f.label } }; continue }
      if (f.integer && !Number.isInteger(n)) { problems[f.name] = { key: 'form.whole', values: { name: f.label } }; continue }
      if (f.min !== undefined && n < f.min) { problems[f.name] = { key: 'form.atLeast', values: { name: f.label, min: f.min } }; continue }
      if (f.max !== undefined && n > f.max) { problems[f.name] = { key: 'form.atMost', values: { name: f.label, max: f.max } }; continue }
      if (n !== f.default) options[f.name] = n
      continue
    }
    const fallback = f.default === undefined ? '' : String(f.default)
    if (text !== fallback) options[f.name] = text
  }
  return { options, problems }
}
