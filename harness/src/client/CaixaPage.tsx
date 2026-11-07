import { useEffect, useRef, useState } from 'react'
import { useCaixa, useStore, useT } from './hooks.tsx'
import type { CaixaKey } from './locales.ts'
import { BoxPage } from './pages/BoxPage.tsx'
import { ImportPage } from './pages/ImportPage.tsx'
import { BrowsePage } from './pages/BrowsePage.tsx'
import { JobsPage } from './pages/JobsPage.tsx'
import { PeoplePage } from './pages/PeoplePage.tsx'
import { SettingsPage } from './pages/SettingsPage.tsx'
import css from './caixa.module.css'

export type Section = 'box' | 'import' | 'jobs' | 'people' | 'browse' | 'settings'
const SECTIONS: Section[] = ['box', 'import', 'jobs', 'people', 'browse', 'settings']

/** The Caixa page: a small navigation and one section at a time. */
export function CaixaPage({ initial = 'box' }: { initial?: Section }) {
  const t = useT()
  const { worker, view, ready } = useCaixa()
  const store = useStore()
  const [section, setSectionNow] = useState<Section>(initial)
  const [job, setJob] = useState<number | undefined>()
  // Where you were last time, once it is known (unless you have already moved somewhere).
  const moved = useRef(false)
  useEffect(() => {
    if (ready && !moved.current && (SECTIONS as string[]).includes(view ?? '')) setSectionNow(view as Section)
  }, [ready, view])
  const setSection = (next: Section) => { moved.current = true; setSectionNow(next); store.saveView(next) }

  return (
    <main className={css.page} data-testid="caixa-page">
      <h1 className={css.title}>{t('page.title')}</h1>
      <p className={css.lead}>{t('page.lead')}</p>
      {(worker === 'restarting' || worker === 'failed' || worker === 'stopped') && (
        <p className={css.banner} role="status">{t(`worker.${worker}` as CaixaKey)}</p>
      )}
      <nav className={css.nav} aria-label={t('nav.label')}>
        {SECTIONS.map(name => (
          <button key={name} type="button" className={`${css.tab} ${name === section ? css.tabActive : ''}`}
                  aria-current={name === section ? 'page' : undefined} onClick={() => setSection(name)}>
            {t(`nav.${name}` as CaixaKey)}
          </button>
        ))}
      </nav>
      {section === 'box' && <BoxPage onImport={() => setSection('import')} />}
      {section === 'import' && <ImportPage onShowJob={(id) => { setJob(id); setSection('jobs') }} onShowPeople={() => setSection('people')} />}
      {section === 'jobs' && <JobsPage selected={job} onSelect={setJob} />}
      {section === 'people' && <PeoplePage />}
      {section === 'browse' && <BrowsePage />}
      {section === 'settings' && <SettingsPage onChangeBox={() => setSection('box')} />}
    </main>
  )
}
