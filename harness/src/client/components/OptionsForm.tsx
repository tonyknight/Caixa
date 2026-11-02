import { useId } from 'react'
import type { Field, FormValues, Problem } from '../options-form.ts'
import { useT } from '../hooks.tsx'
import css from '../caixa.module.css'

/** A form drawn from `fields` (see options-form.ts); it keeps no state of its own. */
export function OptionsForm({
  fields, values, problems, onChange,
}: {
  fields: readonly Field[]
  values: FormValues
  problems: Readonly<Record<string, Problem>>
  onChange: (name: string, value: string | boolean) => void
}) {
  const t = useT()
  const prefix = useId()
  return (
    <div>
      {fields.map((f) => {
        const id = `${prefix}-${f.name}`
        const problem = problems[f.name]
        const message = problem ? t(problem.key, problem.values) : undefined
        const described = [f.help ? `${id}-help` : '', message ? `${id}-problem` : ''].filter(Boolean).join(' ') || undefined
        const note = <>
          {f.help && <span id={`${id}-help`} className={css.help}>{f.help}</span>}
          {message && <p id={`${id}-problem`} className={css.problem} role="alert">{message}</p>}
        </>
        if (f.kind === 'checkbox') {
          return (
            <div key={f.name}>
              <label className={css.check} htmlFor={id}>
                <input id={id} type="checkbox" checked={values[f.name] === true} aria-describedby={described}
                       onChange={event => onChange(f.name, event.target.checked)} />
                <span>{f.label}</span>
              </label>
              {note}
            </div>
          )
        }
        return (
          <div key={f.name}>
            <label className={css.field} htmlFor={id}>{f.label}</label>
            {note}
            {f.kind === 'select' ? (
              <select id={id} className={css.select} value={String(values[f.name] ?? '')} aria-describedby={described}
                      onChange={event => onChange(f.name, event.target.value)}>
                {f.choices.map(choice => <option key={choice} value={choice}>{choice}</option>)}
              </select>
            ) : (
              <input id={id} className={css.input} type={f.kind === 'number' ? 'number' : 'text'} value={String(values[f.name] ?? '')}
                     min={f.min} max={f.max} step={f.integer ? 1 : 'any'} aria-invalid={problem ? true : undefined} aria-describedby={described}
                     onChange={event => onChange(f.name, event.target.value)} />
            )}
          </div>
        )
      })}
    </div>
  )
}
