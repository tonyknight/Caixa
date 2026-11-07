import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { boxUrl, CSP, parseRange, rewriteLinks, serveBoxFile } from '../src/host/box-files.ts'
import { caixaRoutes } from '../src/host/routes.ts'
import { WorkerClient } from '../src/host/worker-client.ts'
import { launchProcess, withOwnHome } from './helpers.ts'

const caixaOk = (() => { try { execFileSync('caixa', ['--version'], { stdio: 'ignore' }); return true } catch { return false } })()

describe('rewriting a page\'s links', () => {
  const page = 'Messages/Ana Costa/(2024) Ana Costa.html'

  it('points relative links and media at the route, relative to the page', () => {
    const html = '<a href="../../index.html">All</a><a href="(2023)%20Ana%20Costa.html">2023</a><img src="Attachments/photo%201.png" alt="x"><source src=\'../Groups/Costa%20Family/a.mp3\'>'
    const out = rewriteLinks(html, page)
    expect(out).toContain(`href="${boxUrl('index.html').replace(/&/g, '&amp;')}"`)
    expect(out).toContain(`href="/api/caixa/box?path=${encodeURIComponent('Messages/Ana Costa/(2023) Ana Costa.html')}"`)
    expect(out).toContain(`src="/api/caixa/box?path=${encodeURIComponent('Messages/Ana Costa/Attachments/photo 1.png')}"`)
    expect(out).toContain(`src="/api/caixa/box?path=${encodeURIComponent('Messages/Groups/Costa Family/a.mp3')}"`)
  })

  it('keeps the fragment of a link', () => {
    expect(rewriteLinks('<a href="(2024)%20Ana.html#m-abc123">x</a>', page)).toContain(`${encodeURIComponent('Messages/Ana Costa/(2024) Ana.html')}#m-abc123`)
  })

  it('leaves alone: places on the same page, other sites, absolute paths and data', () => {
    const same = '<a href="#date-2024-03-01">1</a><a href="https://example.org/x">x</a><a href="//cdn.example/x">y</a><a href="/etc/passwd">z</a><a href="mailto:a@b.c">m</a><img src="data:image/png;base64,AAAA"><a href="">e</a>'
    expect(rewriteLinks(same, page)).toBe(same)
  })

  it('does not let a link climb out of the box', () => {
    const out = rewriteLinks('<a href="../../../../etc/passwd">x</a><a href="../../..">y</a>', page)
    expect(out).toBe('<a href="../../../../etc/passwd">x</a><a href="../../..">y</a>')
  })

  it('leaves text that merely looks like an attribute, and bad escapes, alone', () => {
    expect(rewriteLinks('<p>write href=oops in prose</p><a href="%E0%A4%A">bad</a>', page)).toContain('href="%E0%A4%A"')
  })
})

describe('byte ranges', () => {
  it.each([
    ['bytes=0-9', 100, [0, 9]], ['bytes=10-', 100, [10, 99]], ['bytes=-5', 100, [95, 99]],
    ['bytes=90-500', 100, [90, 99]], ['bytes=-500', 100, [0, 99]],
  ])('%s of %i', (header, size, expected) => { expect(parseRange(header, size)).toEqual(expected) })

  it('refuses a range outside the file and ignores what it cannot read', () => {
    expect(parseRange('bytes=100-', 100)).toBe('unsatisfiable')
    expect(parseRange('bytes=5-2', 100)).toBe('unsatisfiable')
    expect(parseRange('bytes=0-1', 0)).toBe('unsatisfiable')
    for (const odd of ['items=0-1', 'bytes=-', 'bytes=a-b', 'bytes=0-1,5-6']) expect(parseRange(odd, 100)).toBeUndefined()
  })
})

const run = caixaOk ? describe : describe.skip

run('serving a real box through the real worker', () => {
  let folder: string
  let box: string
  let client: WorkerClient
  const png = Buffer.from('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082', 'hex')

  const ask = (path: string | null, init: RequestInit = {}) => serveBoxFile(client, new Request(`http://127.0.0.1/api/caixa/box${path === null ? '' : `?path=${encodeURIComponent(path)}`}`, init))

  beforeAll(async () => {
    folder = mkdtempSync(join(tmpdir(), 'caixa-box-files-'))
    box = join(folder, 'Box')
    execFileSync('caixa', ['box', 'create', box, '--name', 'Files box'], { stdio: 'ignore' })
    mkdirSync(join(box, 'Messages', 'Ana Costa', 'Attachments'), { recursive: true })
    writeFileSync(join(box, 'Messages', 'Ana Costa', '(2024) Ana Costa.html'), '<html><body><a href="../../index.html">All</a><img src="Attachments/photo.png"><script>alert(1)</script></body></html>')
    writeFileSync(join(box, 'Messages', 'Ana Costa', 'Attachments', 'photo.png'), png)
    writeFileSync(join(box, 'Messages', 'Ana Costa', 'Attachments', 'voice.mp3'), Buffer.alloc(1000, 7))
    writeFileSync(join(box, 'Messages', 'Ana Costa', 'Attachments', 'notes.txt'), 'plain notes')
    writeFileSync(join(box, 'Messages', 'Ana Costa', 'Attachments', 'drawing.svg'), '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
    writeFileSync(join(box, 'Messages', 'Ana Costa', 'Attachments', 'weird.bin'), 'data')
    writeFileSync(join(box, 'index.html'), '<html>index</html>')
    writeFileSync(join(folder, 'outside.txt'), 'secret')
    symlinkSync(join(folder, 'outside.txt'), join(box, 'Messages', 'link.txt'))
    client = new WorkerClient(launchProcess(withOwnHome(['caixa', 'worker'])))
    client.start()
    await client.request('box.open', { path: box })
  }, 60_000)
  afterAll(async () => { await client?.close(); rmSync(folder, { recursive: true, force: true }) })

  it('serves a page with its links rewritten, under a strict policy', async () => {
    const response = await ask('Messages/Ana Costa/(2024) Ana Costa.html')
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('text/html; charset=utf-8')
    expect(response.headers.get('content-security-policy')).toBe(CSP)
    expect(response.headers.get('x-content-type-options')).toBe('nosniff')
    expect(response.headers.get('content-disposition')).toBeNull()
    const text = await response.text()
    expect(text).toContain(`src="/api/caixa/box?path=${encodeURIComponent('Messages/Ana Costa/Attachments/photo.png')}"`)
    expect(text).toContain('path=index.html')
    expect(response.headers.get('content-length')).toBe(String(Buffer.byteLength(text)))
  })

  it('forbids scripts, whatever the page contains', () => {
    expect(CSP).toContain("default-src 'none'")
    expect(CSP).not.toMatch(/script-src/)
    expect(CSP).not.toContain("'unsafe-eval'")
    expect(CSP).toContain("frame-ancestors 'self'")
  })

  it('serves a photo as it is, and sends HEAD without a body', async () => {
    const photo = await ask('Messages/Ana Costa/Attachments/photo.png')
    expect(photo.headers.get('content-type')).toBe('image/png')
    expect(Buffer.from(await photo.arrayBuffer()).equals(png)).toBe(true)
    const head = await ask('Messages/Ana Costa/Attachments/photo.png', { method: 'HEAD' })
    expect(head.headers.get('content-length')).toBe(String(png.length))
    expect(await head.text()).toBe('')
  })

  it('lets audio seek with byte ranges', async () => {
    const whole = await ask('Messages/Ana Costa/Attachments/voice.mp3')
    expect(whole.headers.get('accept-ranges')).toBe('bytes')
    expect((await whole.arrayBuffer()).byteLength).toBe(1000)
    const part = await ask('Messages/Ana Costa/Attachments/voice.mp3', { headers: { range: 'bytes=100-199' } })
    expect(part.status).toBe(206)
    expect(part.headers.get('content-range')).toBe('bytes 100-199/1000')
    expect((await part.arrayBuffer()).byteLength).toBe(100)
    const tail = await ask('Messages/Ana Costa/Attachments/voice.mp3', { headers: { range: 'bytes=-10' } })
    expect(tail.headers.get('content-range')).toBe('bytes 990-999/1000')
    const beyond = await ask('Messages/Ana Costa/Attachments/voice.mp3', { headers: { range: 'bytes=5000-' } })
    expect(beyond.status).toBe(416)
    expect(beyond.headers.get('content-range')).toBe('bytes */1000')
  })

  it('shows plain text, and sends anything else as a download (svg and unknown types included)', async () => {
    const text = await ask('Messages/Ana Costa/Attachments/notes.txt')
    expect(text.headers.get('content-type')).toBe('text/plain; charset=utf-8')
    expect(text.headers.get('content-disposition')).toBeNull()
    for (const name of ['drawing.svg', 'weird.bin']) {
      const response = await ask(`Messages/Ana Costa/Attachments/${name}`)
      expect(response.headers.get('content-disposition'), name).toMatch(/^attachment; filename\*=UTF-8''/)
    }
  })

  it('says 400 without a path, 404 for what is not there or not a file', async () => {
    expect((await ask(null)).status).toBe(400)
    expect((await ask('')).status).toBe(400)
    expect((await ask('Messages/nothing.html')).status).toBe(404)
    expect((await ask('Messages')).status).toBe(404)
  })

  it('refuses anything outside the box: up-and-out paths, absolute paths, links, and .caixa', async () => {
    for (const path of ['../outside.txt', 'Messages/../../outside.txt', join(folder, 'outside.txt'), 'Messages/link.txt', '.caixa/caixa.sqlite', '.caixa/box.yaml']) {
      const response = await ask(path)
      expect([403, 404], path).toContain(response.status)
      expect(await response.text(), path).not.toContain('secret')
    }
  })

  it('says 503 when the worker is not running', async () => {
    const stopped = new WorkerClient(launchProcess(withOwnHome(['caixa', 'worker'])))
    expect((await serveBoxFile(stopped, new Request('http://x/api/caixa/box?path=index.html'))).status).toBe(503)
  })

  it('is one of the owner-only routes, for GET and HEAD only', () => {
    const route = caixaRoutes(client).find(r => r.path === '/api/caixa/box')!
    expect(route.methods).toEqual(['GET', 'HEAD'])
    expect(route.requestBody).toBe('buffered')
  })
})
