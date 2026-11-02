import { useState } from 'react'
import { useCaixa, useT } from './hooks.tsx'
import type { CaixaKey } from './locales.ts'
import { BoxPage } from './pages/BoxPage.tsx'
import { ImportPage } from './pages/ImportPage.tsx'
import { JobsPage } from './pages/JobsPage.tsx'
import { PeoplePage } from './pages/PeoplePage.tsx'
import css from './caixa.module.css'

export type Section = 'box' | 'import' | 'jobs' | 'people'
const SECTIONS: Section[] = ['box', 'import', 'jobs', 'people']

/** The Caixa page: a small navigation and one section at a time. */
export function CaixaPage({ initial = 'box' }: { initial?: Section }) {
  const t = useT()
  const { worker } = useCaixa()
  const [section, setSection] = useState<Section>(initial)
  const [job, setJob] = useState<number | undefined>()

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
    </main>
  )
}
