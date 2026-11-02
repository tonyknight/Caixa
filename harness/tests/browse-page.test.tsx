// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { BrowsePage, kindOf } from '../src/client/pages/BrowsePage.tsx'
import { fail, ok } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const page = () => renderWith(<BrowsePage />)
const into = async (view: Awaited<ReturnType<typeof page>>, name: string) => { fireEvent.click(screen.getByRole('button', { name: `${name}/` })); await view.flush() }

describe('the kinds of file', () => {
  it.each([
    ['(2024) Ana.html', 'page'], ['photo.JPG', 'image'], ['a.webp', 'image'], ['voice.mp3', 'audio'], ['clip.mp4', 'video'],
    ['notes.txt', 'text'], ['doc.pdf', 'other'], ['drawing.svg', 'other'], ['noextension', 'other'],
  ])('%s is %s', (name, kind) => { expect(kindOf(name)).toBe(kind) })
})

describe('the box listing', () => {
  it('starts at the root with folders and files, and the index page offered', async () => {
    await page()
    expect(screen.getByRole('heading', { name: 'Browse' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Messages/' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Open index.html' })).toBeTruthy()
    expect(screen.getByRole('button', { name: "Open the box's index page" })).toBeTruthy()
    expect(screen.getByText('Choose a page, photo or file on the left to see it here.')).toBeTruthy()
  })

  it('goes into folders, keeps a breadcrumb, and goes back up through it', async () => {
    const view = await page()
    await into(view, 'Messages')
    await into(view, 'Ana Costa')
    const crumbs = screen.getByRole('navigation', { name: 'Where you are' })
    expect(within(crumbs).getAllByRole('button').map(b => b.textContent)).toEqual(['Box', 'Messages', 'Ana Costa'])
    expect(within(crumbs).getByRole('button', { name: 'Ana Costa' }).getAttribute('aria-current')).toBe('location')
    expect(view.api.calls).toContainEqual(['browse', 'Messages/Ana Costa'])
    fireEvent.click(within(crumbs).getByRole('button', { name: 'Messages' }))
    await view.flush()
    expect(screen.getByRole('button', { name: 'Ana Costa/' })).toBeTruthy()
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Where you are' })).getByRole('button', { name: 'Box' }))
    await view.flush()
    expect(screen.getByRole('button', { name: 'Messages/' })).toBeTruthy()
  })

  it('shows file sizes in plain units', async () => {
    const view = await page()
    await into(view, 'Messages')
    await into(view, 'Ana Costa')
    expect(screen.getByText('4 KB')).toBeTruthy()
    expect(screen.getByText('2.4 MB')).toBeTruthy()
    expect(screen.getAllByText('100 bytes').length).toBe(3)
  })

  it('says when a folder, or the whole box, is empty', async () => {
    await renderWith(<BrowsePage />, (api) => { api.browseReply = path => ok({ path: path ?? '', entries: [] }) })
    expect(screen.getByText('The box has nothing to show yet. Import an export first.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: "Open the box's index page" })).toBeNull()
  })

  it('shows the worker\'s plain error', async () => {
    await renderWith(<BrowsePage />, (api) => { api.browseReply = () => fail('not_found', "'Messages' is not in the box.") })
    expect(screen.getByRole('alert').textContent).toBe("Something went wrong: 'Messages' is not in the box.")
  })

  it('needs a box', async () => {
    await renderWith(<BrowsePage />, (api) => { api.box = fail('no_box', 'x') })
    expect(screen.getByText('Open or create a box first (see the Box section).')).toBeTruthy()
  })
})

describe('the viewer', () => {
  async function opened(name: string) {
    const view = await page()
    await into(view, 'Messages')
    await into(view, 'Ana Costa')
    fireEvent.click(screen.getByRole('button', { name: `Open ${name}` }))
    return view
  }

  it('shows a page in a frame that cannot run scripts, from the box route, with a way to open it in a tab', async () => {
    await opened('(2024) Ana Costa.html')
    const frame = screen.getByTitle('The page (2024) Ana Costa.html') as HTMLIFrameElement
    expect(frame.getAttribute('src')).toBe(`/api/caixa/box?path=${encodeURIComponent('Messages/Ana Costa/(2024) Ana Costa.html')}`)
    expect(frame.getAttribute('sandbox')).toBe('allow-same-origin') // never allow-scripts
    const tab = screen.getByRole('link', { name: 'Open in a new tab' })
    expect(tab.getAttribute('href')).toBe(frame.getAttribute('src'))
    expect(tab.getAttribute('target')).toBe('_blank')
    expect(tab.getAttribute('rel')).toContain('noopener')
  })

  it('opens the index page from the shortcut', async () => {
    const view = await page()
    fireEvent.click(screen.getByRole('button', { name: "Open the box's index page" }))
    expect(screen.getByTitle('The page index.html').getAttribute('src')).toBe('/api/caixa/box?path=index.html')
    await view.flush()
  })

  it('shows a photo, plays audio and video, and offers anything else as a download', async () => {
    await opened('photo.png')
    expect(screen.getByRole('img', { name: 'photo.png' }).getAttribute('src')).toContain('photo.png')
    fireEvent.click(screen.getByRole('button', { name: 'Open voice.mp3' }))
    expect(screen.getByLabelText('voice.mp3').tagName).toBe('AUDIO')
    fireEvent.click(screen.getByRole('button', { name: 'Open clip.mp4' }))
    expect(screen.getByLabelText('clip.mp4').tagName).toBe('VIDEO')
    fireEvent.click(screen.getByRole('button', { name: 'Open doc.pdf' }))
    expect(screen.getByText('This kind of file cannot be shown here.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Download doc.pdf' }).getAttribute('download')).toBe('doc.pdf')
  })

  it('marks which file is open', async () => {
    await opened('photo.png')
    expect(screen.getByRole('button', { name: 'Open photo.png' }).getAttribute('aria-current')).toBe('true')
    expect(screen.getByRole('button', { name: 'Open voice.mp3' }).getAttribute('aria-current')).toBeNull()
  })
})
