import { useEffect, useState } from 'react'
import type { Job } from '../api.ts'
import { duration } from '../components/Progress.tsx'
import { useT } from '../hooks.tsx'
import type { CaixaKey } from '../locales.ts'
import css from './mail.module.css'

/** A job's work has ended (whichever way). */
export const ended = (job: Job | undefined) => job !== undefined && ['done', 'failed', 'cancelled', 'interrupted'].includes(job.status)

/** A small meter beside a window's primary button, from the click to the end of the job:
 *  "Counting…" while what the work brings is worked out, "Starting" until the window has heard of
 *  the job, then its stage, n of N, a bar and the time so far. */
export function InlineProgress({ label, counting, job, startedAt }: {
  label: string
  counting: boolean
  job: Job | undefined
  startedAt: number
}) {
  const t = useT()
  const [, tick] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => tick(n => n + 1), 1000)
    return () => clearInterval(timer)
  }, [])
  const stage = counting ? undefined : (job?.stage || 'starting')
  const counted = !counting && job?.total != null && job.total > 0
  return (
    <span className={css.inlineProgress} role="status" aria-label={label}>
      {counted ? <progress max={job!.total!} value={job!.current ?? 0} /> : <progress />}
      <span>
        {counting ? t('mail.counting') : t(`stage.${stage}` as CaixaKey)}
        {counted && <> · {t('progress.count', { current: (job!.current ?? 0).toLocaleString(), total: job!.total!.toLocaleString() })}</>}
        {!counting && <> · {duration((Date.now() - startedAt) / 1000)}</>}
      </span>
    </span>
  )
}
