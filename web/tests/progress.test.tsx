// @vitest-environment jsdom
import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { duration, IMPORT_STAGES, ProgressView } from '../src/client/components/Progress.tsx'
import { Providers } from '../src/client/hooks.tsx'
import { renderWith, t } from './render.tsx'

afterEach(cleanup)

describe('how long', () => {
  it('reads as a person would say it', () => {
    expect([0, 9.4, 59.6, 75, 3599, 3725].map(duration)).toEqual(['0 s', '9 s', '1 min 0 s', '1 min 15 s', '59 min 59 s', '1 h 2 min'])
  })
})

describe('how long is left', () => {
  it('is not guessed until there is something to go on, then follows the speed of this stage', async () => {
    let clock = 1_000_000
    const now = () => clock
    const step = (current: number) => ({ stage: 'importing', current, total: 1000, message: '' })
    const view = await renderWith(<ProgressView step={step(0)} stages={IMPORT_STAGES} startedAt={clock} now={now} />)
    expect(screen.queryByText(/left/)).toBeNull()
    clock += 10_000 // ten seconds later, 100 done: 10 a second, 900 to go
    view.rerender(<Providers store={view.store} t={t}><ProgressView step={step(100)} stages={IMPORT_STAGES} startedAt={1_000_000} now={now} /></Providers>)
    expect(screen.getByText(/about 1 min 30 s left/)).toBeTruthy()
    expect(screen.getByText(/So far: 10 s/)).toBeTruthy()
  })

  it('is not shown for a stage with nothing to count', async () => {
    await renderWith(<ProgressView step={{ stage: 'linking', current: 0, total: null, message: 'Matching people' }} stages={IMPORT_STAGES} startedAt={Date.now()} />)
    expect(screen.queryByText(/left/)).toBeNull()
    expect(document.querySelector('progress')!.hasAttribute('value')).toBe(false)
  })
  it('shows translating as a stage of its own once an import reaches it', async () => {
    const view = await renderWith(<ProgressView step={{ stage: 'linking', current: 0, total: null, message: '' }} stages={IMPORT_STAGES} startedAt={Date.now()} />)
    expect(screen.queryByText('Translating messages')).toBeNull()
    view.rerender(<Providers store={view.store} t={t}><ProgressView step={{ stage: 'translating', current: 3, total: 40, message: 'Translating messages' }} stages={IMPORT_STAGES} startedAt={Date.now()} /></Providers>)
    const now = document.querySelector('[aria-current="step"]')!
    expect(now.textContent).toBe('Translating messages')
    expect(now.previousElementSibling!.textContent).toBe('Matching people')
    expect(screen.getByText(/3 of 40/)).toBeTruthy()
  })
  it('shows speech-to-text as a stage of its own, with the recording and its timing', async () => {
    const message = '1.amr: 2.0 s for 30 s of audio (15.0x real time); average 2.0 s each'
    await renderWith(<ProgressView step={{ stage: 'transcribing', current: 1, total: 40, message }} stages={IMPORT_STAGES} startedAt={Date.now()} />)
    const now = document.querySelector('[aria-current="step"]')!
    expect(now.textContent).toBe('Turning speech into text')
    expect(now.previousElementSibling!.textContent).toBe('Reading the export')
    expect(screen.getByText(/1 of 40/)).toBeTruthy()
    expect(screen.getByText(message)).toBeTruthy()
  })
})
