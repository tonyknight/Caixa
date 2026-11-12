import { useEffect, useRef, useState } from 'react'
import type { Step } from '../api.ts'
import { useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import css from '../caixa.module.css'

/** The stages an import goes through, in order (a preview stops after `linking`). */
export const IMPORT_STAGES = ['preparing', 'importing', 'linking', 'filing', 'rendering', 'syncing'] as const
export const PREVIEW_STAGES = ['preparing', 'importing', 'linking'] as const

/** `75` → "1 min 15 s"; under a minute, just seconds. */
export function duration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds))
  const minutes = Math.floor(whole / 60)
  if (minutes >= 60) return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
  return minutes ? `${minutes} min ${whole % 60} s` : `${whole} s`
}

/**
 * Where a preview or an import is: the stages with the current one marked, how many of how many,
 * what is being read, a bar, the time so far and (once there is enough to go on) roughly how long is left.
 */
export function ProgressView({ step, stages, startedAt, now = Date.now }: {
  step: Step | undefined
  stages: readonly string[]
  /** When the work began (milliseconds); the time so far counts from here. */
  startedAt: number
  now?: () => number
}) {
  const t = useT()
  const [, tick] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => tick(n => n + 1), 1000)
    return () => clearInterval(timer)
  }, [])
  // Remember when this stage began and where it was then, to judge its speed.
  const seen = useRef<{ stage: string; at: number; current: number } | undefined>(undefined)
  const stage = step?.stage ?? 'starting'
  if (step && seen.current?.stage !== step.stage) seen.current = { stage: step.stage, at: now(), current: step.current }

  const position = stages.indexOf(stage)
  const counted = step && step.total !== null && step.total > 0
  let left: string | undefined
  if (step && counted && seen.current) {
    const done = step.current - seen.current.current
    const took = (now() - seen.current.at) / 1000
    if (done >= 5 && took >= 3 && step.current < step.total!) left = duration((step.total! - step.current) * (took / done))
  }
  return (
    <div className={css.progressBox}>
      <ol className={css.stages} aria-label={t('progress.steps')}>
        {stages.map((name, index) => (
          <li key={name} className={index < position ? css.stageDone : index === position ? css.stageNow : css.stageNext}
              aria-current={index === position ? 'step' : undefined}>
            {t(`stage.${name}` as CaixaKey)}
          </li>
        ))}
      </ol>
      <p className={css.progressLine}>
        <strong>{t(`stage.${stage}` as CaixaKey)}</strong>
        {counted && <> · {t('progress.count', { current: step!.current.toLocaleString(), total: step!.total!.toLocaleString() })}</>}
        {step?.message ? <> · <span className={css.muted}>{step.message}</span></> : null}
      </p>
      {counted ? <progress className={css.progress} max={step!.total!} value={step!.current} /> : <progress className={css.progress} />}
      <p className={css.muted}>
        {t('progress.elapsed', { time: duration((now() - startedAt) / 1000) })}
        {left && <> · {t('progress.left', { time: left })}</>}
      </p>
    </div>
  )
}
