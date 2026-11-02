/**
 * Serving the box's own files (its generated pages, their photos, audio and video) to the browser.
 *
 * `GET|HEAD /api/caixa/box?path=<path inside the box>`. DSH registers fetch routes at exact paths, so
 * this is one path with a query rather than a `/api/caixa/box/*` prefix. The worker decides what a path
 * may be (`browse.file` refuses anything outside the box and anything under `.caixa/`); this reads the
 * file it names. Because the generated pages link to each other and to their media with relative URLs,
 * which a query-string route would break, served HTML has those links rewritten to this route.
 *
 * Everything is sent with a strict Content-Security-Policy (no scripts; images and media only from
 * here) and `nosniff`. Only pages, plain text, common images, audio and video are shown inline; any
 * other file is sent as an attachment. Audio and video answer `Range` requests so they can seek.
 */

import { createReadStream, readFileSync } from 'node:fs'
import { posix } from 'node:path'
import { Readable } from 'node:stream'
import { UNAVAILABLE, WorkerError } from './worker-client.ts'

export const ROUTE = '/api/caixa/box'
const MAX_PAGE_BYTES = 20_000_000

export const CSP = [
  "default-src 'none'", "img-src 'self' data:", "media-src 'self'", "style-src 'unsafe-inline'",
  "font-src 'self'", "frame-ancestors 'self'", "base-uri 'none'", "form-action 'none'",
].join('; ')

interface Caller {
  request(method: string, params?: Record<string, unknown>): Promise<unknown>
}

interface FileInfo {
  readonly path: string
  readonly name: string
  readonly mime: string
  readonly size: number
  readonly absolute: string
}

const INLINE = /^(text\/html|text\/plain|image\/(png|jpeg|gif|webp|bmp|avif)|audio\/[\w.+-]+|video\/[\w.+-]+)$/

const SKIP = /^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|\/\/|\/|#)/

/** The URL the browser should use for a path inside the box. */
export function boxUrl(path: string, fragment = ''): string {
  return `${ROUTE}?path=${encodeURIComponent(path)}${fragment}`
}

/**
 * Point a page's relative links at the route. `pagePath` is the page's own path in the box; links
 * that would leave the box, and links to other sites or to places on the same page, are left alone.
 */
export function rewriteLinks(html: string, pagePath: string): string {
  const folder = posix.dirname(pagePath)
  return html.replace(/\b(href|src|poster)=("([^"]*)"|'([^']*)')/g, (whole, attribute: string, quoted: string, double?: string, single?: string) => {
    const value = (double ?? single ?? '').replace(/&amp;/g, '&')
    if (value === '' || SKIP.test(value)) return whole
    const [beforeFragment = '', ...rest] = value.split('#')
    const fragment = rest.length ? `#${rest.join('#')}` : ''
    const target = beforeFragment.split('?')[0] ?? ''
    let decoded: string
    try { decoded = decodeURI(target) } catch { return whole }
    const resolved = posix.normalize(posix.join(folder, decoded))
    if (resolved.startsWith('..') || resolved === '.' || posix.isAbsolute(resolved)) return whole
    return `${attribute}="${boxUrl(resolved, fragment).replace(/&/g, '&amp;')}"`
  })
}

function headers(extra: Record<string, string>): Headers {
  return new Headers({
    'content-security-policy': CSP,
    'x-content-type-options': 'nosniff',
    'cache-control': 'no-store',
    'referrer-policy': 'no-referrer',
    ...extra,
  })
}

function plain(status: number, text: string): Response {
  return new Response(text, { status, headers: headers({ 'content-type': 'text/plain; charset=utf-8' }) })
}

/** `Range: bytes=…` for a file of `size` bytes: [start, end] inclusive, or undefined when unusable. */
export function parseRange(header: string, size: number): [number, number] | 'unsatisfiable' | undefined {
  const found = /^bytes=(\d*)-(\d*)$/.exec(header.trim())
  if (!found || (found[1] === '' && found[2] === '')) return undefined
  let start: number
  let end: number
  if (found[1] === '') { // the last N bytes
    start = Math.max(0, size - Number(found[2]))
    end = size - 1
  } else {
    start = Number(found[1])
    end = found[2] === '' ? size - 1 : Math.min(Number(found[2]), size - 1)
  }
  if (size === 0 || start >= size || start > end) return 'unsatisfiable'
  return [start, end]
}

export async function serveBoxFile(client: Caller, request: Request): Promise<Response> {
  const path = new URL(request.url).searchParams.get('path')
  if (path === null || path === '' || path.includes('\0')) return plain(400, 'Say which file: ?path=Messages/…')
  let info: FileInfo
  try {
    info = await client.request('browse.file', { path }) as FileInfo
  } catch (error) {
    if (error instanceof WorkerError) {
      if (error.kind === 'not_found') return plain(404, error.message)
      if (error.kind === 'outside_roots') return plain(403, error.message)
      if (error.code === UNAVAILABLE) return plain(503, error.message)
      return plain(502, error.message)
    }
    throw error
  }
  const inline = INLINE.test(info.mime)
  const common: Record<string, string> = {
    'content-type': info.mime.startsWith('text/') ? `${info.mime}; charset=utf-8` : info.mime,
    'accept-ranges': 'bytes',
  }
  if (!inline) common['content-disposition'] = `attachment; filename*=UTF-8''${encodeURIComponent(info.name)}`
  const head = request.method === 'HEAD'

  if (info.mime === 'text/html' && info.size <= MAX_PAGE_BYTES) {
    const body = rewriteLinks(readFileSync(info.absolute, 'utf8'), info.path)
    const bytes = Buffer.byteLength(body)
    return new Response(head ? null : body, { headers: headers({ ...common, 'content-length': String(bytes), 'accept-ranges': 'none' }) })
  }

  const wanted = request.headers.get('range')
  const range = wanted ? parseRange(wanted, info.size) : undefined
  if (range === 'unsatisfiable') return new Response(null, { status: 416, headers: headers({ ...common, 'content-range': `bytes */${info.size}` }) })
  const [start, end] = range ?? [0, Math.max(0, info.size - 1)]
  const length = info.size === 0 ? 0 : end - start + 1
  const out = headers({ ...common, 'content-length': String(length), ...(range ? { 'content-range': `bytes ${start}-${end}/${info.size}` } : {}) })
  if (head || length === 0) return new Response(null, { status: range ? 206 : 200, headers: out })
  const stream = Readable.toWeb(createReadStream(info.absolute, { start, end })) as ReadableStream<Uint8Array>
  return new Response(stream, { status: range ? 206 : 200, headers: out })
}
