// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { CleanMail } from '../src/client/mail/CleanMail.tsx'
import type { CleanReply } from '../src/client/mail/types.ts'
import { job, ok, type FakeApi } from './fake-api.ts'
import { renderWith } from './render.tsx'

afterEach(cleanup)

const SOURCE = { id: 1, path: '/exports/All mail Including Spam and Trash.mbox', member: '', kind: 'original', account: 'Gmail', status: 'read', mails: 56, size: 35_000, parent_id: null }

const row = (name: string, address: string, mails: number, size: number) => ({ name, address, mails, size })

function reply(kept: string[] = []): CleanReply {
  const fold = row('The Daily Fold', 'news@dailyfold.example.com', 6, 4_200)
  const lists = [fold, row('Gardening Weekly', 'newsletter@gardening.example.com', 2, 900), row('Pedro Alves', 'pedro.alves@example.net', 1, 500)]
    .filter(r => !kept.includes(r.address))
  const sum = (rows: { mails: number; size: number }[]) => ({ senders: rows.length, mails: rows.reduce((n, r) => n + r.mails, 0), size: rows.reduce((n, r) => n + r.size, 0) })
  const notices = [row('Bank Alerts', 'no-reply@bank.example.com', 2, 800)]
  const receipts = [row('Shop', 'no-reply@shop.example.com', 2, 1_000)]
  const junk = [...lists, ...notices]
  return {
    source: { id: 1, path: SOURCE.path, member: '', kind: 'original', account: 'Gmail', mails: 56, size: 35_000 },
    groups: [
      { key: 'lists', label: 'Lists and newsletters', ...sum(lists), rows: lists },
      { key: 'notices', label: 'Notices and no-reply', ...sum(notices), rows: notices },
      { key: 'unsubscribe', label: 'Unsubscribe links', senders: 0, mails: 0, size: 0, rows: [] },
      { key: 'spam_trash', label: 'Spam and Trash', senders: 0, mails: 0, size: 0, rows: [] },
      { key: 'receipts', label: 'Receipts and orders (kept)', ...sum(receipts), rows: receipts },
    ],
    left_out: sum(junk),
    kept: { mails: 56 - sum(junk).mails, senders: 20 },
    kept_senders: kept.includes(fold.address) ? [fold] : [],
  }
}

function scripted(api: FakeApi, kept: string[] = []) {
  api.generic['mail.sources'] = () => ok({ sources: [SOURCE] })
  api.generic['mail.clean'] = () => ok(reply(kept))
  api.generic['mail.keep'] = (params) => {
    const addresses = (params.addresses as string[])
    kept = params.keep === false ? kept.filter(a => !addresses.includes(a)) : [...kept, ...addresses]
    return ok(reply(kept))
  }
  api.generic['mail.preview'] = () => ok({ mails: [
    { position: 7, date: '2024-07-03T12:00:00+00:00', offset: -300, subject: 'The Daily Fold — issue 6', recipients: [['to', 'Maria Costa', 'maria.costa@example.com']], snippet: 'Issue 6: folding chairs, folding maps.', size: 700, attachments: 0 },
    { position: 2, date: '2024-01-03T12:00:00+00:00', offset: -300, subject: 'The Daily Fold — issue 1', recipients: [], snippet: 'Issue 1: folding chairs.', size: 700, attachments: 1 },
  ] })
  api.generic['mail.message'] = () => ok({ from: ['The Daily Fold', 'news@dailyfold.example.com'], to: [['Maria Costa', 'maria.costa@example.com']], cc: [], subject: 'The Daily Fold — issue 6', date: 'Wed, 03 Jul 2024 07:00:00 -0500', text: 'Issue 6: folding chairs, folding maps.\nUnsubscribe', attachments: [] })
  api.generic['mail.clean.write'] = () => ok(job({ id: 9, kind: 'mail-clean', collector: null, status: 'queued', result: null }))
  api.generic['mail.read'] = () => ok(job({ id: 8, kind: 'mail-read', collector: null, status: 'queued', result: null }))
}

async function opened(kept: string[] = []) {
  const view = await renderWith(<CleanMail />, api => scripted(api, kept))
  fireEvent.click(screen.getByRole('button', { name: /Clean All mail Including Spam and Trash\.mbox/ }))
  await view.flush()
  return view
}

const rows = () => screen.getAllByRole('row').slice(1)
const cells = (r: HTMLElement) => within(r).getAllByRole('cell').map(c => c.textContent)

describe('the Clean mail window', () => {
  it('starts from the mboxes already read', async () => {
    await renderWith(<CleanMail />, api => scripted(api))
    expect(screen.getByRole('heading', { name: 'Clean mail' })).toBeTruthy()
    expect(screen.getByText(/Gmail · 56 mails/)).toBeTruthy()
  })

  it('shows the groups with their senders, mails and size, and a group as rows', async () => {
    await opened()
    const sidebar = screen.getByRole('navigation', { name: 'Groups' })
    const lists = within(sidebar).getByRole('link', { name: /Lists and newsletters/ })
    expect(lists.textContent).toContain('3 senders · 9 mails · 5.5 KB')
    expect(within(sidebar).getByRole('link', { name: /Receipts and orders \(kept\)/ })).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lists and newsletters')
    expect(cells(rows()[0]!)).toEqual(expect.arrayContaining(['The Daily Fold', 'news@dailyfold.example.com', '6', '4.1 KB']))
    fireEvent.click(within(sidebar).getByRole('link', { name: /Notices and no-reply/ }))
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Notices and no-reply')
    expect(cells(rows()[0]!)).toContain('Bank Alerts')
    const status = screen.getByRole('contentinfo')
    expect(status.textContent).toContain('1 sender · 2 mails · 800 bytes')
  })

  it('selects with a click and a range with Shift, adds the selection up, and keeps it', async () => {
    const view = await opened()
    fireEvent.click(rows()[0]!)
    fireEvent.click(rows()[2]!, { shiftKey: true })
    const status = screen.getByRole('contentinfo')
    expect(status.textContent).toContain('3 selected · 9 mails · 5.5 KB')
    fireEvent.click(within(status).getByRole('button', { name: 'Keep' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.keep', { source: 1, addresses: ['news@dailyfold.example.com', 'newsletter@gardening.example.com', 'pedro.alves@example.net'], keep: true }])
    expect(rows()).toHaveLength(0)
    fireEvent.keyDown(document, { key: 'Escape' })
  })

  it('keeps every sender of a group at once but the ones deselected', async () => {
    const view = await opened()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all' }))
    expect(screen.getByRole('contentinfo').textContent).toContain('3 selected')
    fireEvent.click(rows()[2]!)  // Pedro stays in the group
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('button', { name: 'Keep' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.keep', { source: 1, addresses: ['news@dailyfold.example.com', 'newsletter@gardening.example.com'], keep: true }])
  })

  it('keeps one sender with the tool on its row, and takes it back in the Kept view', async () => {
    const view = await opened()
    fireEvent.click(screen.getByRole('button', { name: 'Keep The Daily Fold' }))
    await view.flush()
    expect(rows().map(r => cells(r)[1])).not.toContain('The Daily Fold')
    const sidebar = screen.getByRole('navigation', { name: 'Groups' })
    fireEvent.click(within(sidebar).getByRole('link', { name: /Kept/ }))
    expect(cells(rows()[0]!)).toContain('The Daily Fold')
    fireEvent.click(screen.getByRole('button', { name: 'Stop keeping The Daily Fold' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.keep', { source: 1, addresses: ['news@dailyfold.example.com'], keep: false }])
  })

  it('keeps the senders dropped on Kept', async () => {
    const view = await opened()
    fireEvent.click(rows()[1]!)
    const sidebar = screen.getByRole('navigation', { name: 'Groups' })
    const kept = within(sidebar).getByRole('link', { name: /Kept/ })
    fireEvent.dragStart(rows()[1]!, { dataTransfer: { setData: () => undefined, effectAllowed: '' } })
    fireEvent.dragOver(kept)
    fireEvent.drop(kept)
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.keep', { source: 1, addresses: ['newsletter@gardening.example.com'], keep: true }])
  })

  it('shows a sender’s mail in an overlay, and one mail in full', async () => {
    const view = await opened()
    fireEvent.click(screen.getByRole('button', { name: 'Look at the mail from The Daily Fold' }))
    await view.flush()
    const overlay = screen.getByRole('dialog', { name: 'Mail from The Daily Fold' })
    expect(within(overlay).getByText('The Daily Fold — issue 6')).toBeTruthy()
    expect(within(overlay).getByText('Issue 1: folding chairs.')).toBeTruthy()
    fireEvent.click(within(overlay).getByText('The Daily Fold — issue 6'))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.message', { source: 1, position: 7 }])
    expect(within(overlay).getByText(/Unsubscribe/)).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Mail from The Daily Fold' })).toBeNull()
  })

  it('asks before writing the cleaned mbox, then follows the job to the new file', async () => {
    const view = await opened()
    fireEvent.click(screen.getByRole('button', { name: 'Write the cleaned mbox' }))
    const ask = screen.getByRole('dialog', { name: /Leave out 11 mails/ })
    expect(ask.textContent).toContain('4 senders')
    expect(ask.textContent).toContain('is not changed')
    fireEvent.click(within(ask).getByRole('button', { name: 'Write it' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.clean.write', { source: 1 }])
    await view.emit('job.finished', { ...job({ id: 9, kind: 'mail-clean', collector: null, status: 'done', result: { path: '/exports/(2026-11-20) All mail Including Spam and Trash [Cleaned].mbox', source_id: 12, mails: 45, size: 30_000, left_out: 11, left_out_size: 6_400 } as never }), job: 9 })
    const done = within(screen.getByRole('main')).getByRole('status', { name: 'Written' })
    expect(done.textContent).toContain('(2026-11-20) All mail Including Spam and Trash [Cleaned].mbox')
    expect(done.textContent).toContain('45 mails kept, 11 left out')
    expect(within(done).getByRole('link', { name: 'Sort the cleaned mbox' }).getAttribute('href')).toBe('/mail/sort?source=12')
  })

  it('can skip cleaning and go straight to sorting and importing the same mbox', async () => {
    await opened()
    const skip = within(screen.getByRole('contentinfo')).getByRole('link', { name: 'Skip cleaning: sort and import' })
    expect(skip.getAttribute('href')).toBe('/mail/sort?source=1')
  })

  it('shows a meter beside Write and keeps it disabled until the job ends', async () => {
    const view = await opened()
    view.api.generic['mail.clean.write'] = () => ok(job({ id: 9, kind: 'mail-clean', collector: null, status: 'queued', result: null }))
    fireEvent.click(screen.getByRole('button', { name: 'Write the cleaned mbox' }))
    fireEvent.click(within(screen.getByRole('dialog', { name: /Leave out 11 mails/ })).getByRole('button', { name: 'Write it' }))
    await view.flush()
    const bar = screen.getByRole('contentinfo')
    expect((within(bar).getByRole('button', { name: 'Write the cleaned mbox' }) as HTMLButtonElement).disabled).toBe(true)
    expect(within(bar).getByRole('status', { name: 'Writing progress' }).textContent).toContain('Starting')
  })

  it('reads another mbox with its account, then cleans what it read', async () => {
    const view = await renderWith(<CleanMail />, api => scripted(api))
    fireEvent.change(screen.getByLabelText('The mbox'), { target: { value: '/exports/takeout.zip' } })
    fireEvent.change(screen.getByLabelText('Account'), { target: { value: 'Gmail' } })
    fireEvent.click(screen.getByRole('button', { name: 'Read it' }))
    await view.flush()
    expect(view.api.calls).toContainEqual(['call', 'mail.read', { source: '/exports/takeout.zip', account: 'Gmail' }])
    await view.emit('job.finished', { ...job({ id: 8, kind: 'mail-read', collector: null, status: 'done', result: { mails: 56, sources: [{ source_id: 1, path: '/exports/takeout.zip', member: 'All mail.mbox', account: 'Gmail', mails: 56, reused: false }] } as never }), job: 8 })
    await view.flush()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lists and newsletters')
  })
})
