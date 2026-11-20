import { useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent, type ReactNode } from 'react'
import { useT } from '../hooks.tsx'
import { size, type SenderRow } from './types.ts'
import css from './mail.module.css'

/** A category on the left: its label, its colour, what it holds; some take senders dropped on them. */
export interface Category {
  readonly key: string
  readonly label: string
  /** A colour class from mail.module.css (`dotLists`, `dotKept`, …). */
  readonly dot: string
  readonly line: string
  readonly dropTarget?: boolean
}

/** A button that shows on a row when the pointer is over it. */
export interface RowTool {
  readonly key: string
  readonly symbol: string
  readonly label: (row: SenderRow) => string
  readonly onClick: (row: SenderRow) => void
  readonly danger?: boolean
}

/** "1 sender · 2 mails · 800 bytes" */
export function useCounts() {
  const t = useT()
  const senders = (n: number) => (n === 1 ? t('mail.count.sender') : t('mail.count.senders', { count: n.toLocaleString('en') }))
  const mails = (n: number) => (n === 1 ? t('mail.count.mail') : t('mail.count.mails', { count: n.toLocaleString('en') }))
  return {
    senders,
    mails,
    summary: (rows: readonly SenderRow[]) =>
      `${senders(rows.length)} · ${mails(rows.reduce((n, r) => n + r.mails, 0))} · ${size(rows.reduce((n, r) => n + r.size, 0))}`,
  }
}

/**
 * Senders in categories, the way the box's index page sorts people: the categories on the left with
 * their counts, the senders of one as rows, click and Shift-click to select, drag the selection
 * onto a category that takes it, the tools of a row on hover, and a status bar that adds up the
 * category and the selection and holds the actions.
 */
export function MailList({ brand, categories, view, onView, title, hint, rows, tools, selectable, onDrop, actions, primary, quiet = false }: {
  brand: ReactNode
  categories: readonly Category[]
  view: string
  onView: (key: string) => void
  title: string
  hint: string
  rows: readonly SenderRow[]
  tools: readonly RowTool[]
  selectable: boolean
  onDrop?: (target: string, rows: SenderRow[]) => void
  /** The status bar's actions for what is selected (the selection is cleared by `done`). */
  actions?: (selected: SenderRow[], done: () => void) => ReactNode
  primary?: ReactNode
  /** True while something else (an overlay, a question) has the keyboard. */
  quiet?: boolean
}) {
  const t = useT()
  const counts = useCounts()
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set())
  const [dragging, setDragging] = useState(false)
  const [over, setOver] = useState<string | undefined>()
  const anchor = useRef<string | undefined>(undefined)

  // A new category or new rows (after a change was saved) start with nothing selected.
  useEffect(() => { setPicked(new Set()); anchor.current = undefined }, [view, rows])
  const selected = useMemo(() => rows.filter(r => picked.has(r.address)), [rows, picked])
  const clear = () => { setPicked(new Set()); anchor.current = undefined }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (!quiet && event.key === 'Escape') clear() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [quiet])

  const pick = (row: SenderRow, event: MouseEvent) => {
    if (!selectable) return
    const next = new Set(picked)
    if (event.shiftKey && anchor.current) {
      const from = rows.findIndex(r => r.address === anchor.current)
      const to = rows.findIndex(r => r.address === row.address)
      const [low, high] = from < to ? [from, to] : [to, from]
      rows.slice(low, high + 1).forEach(r => next.add(r.address))
    } else {
      if (next.has(row.address)) next.delete(row.address)
      else next.add(row.address)
      anchor.current = row.address
    }
    setPicked(next)
  }

  const startDrag = (row: SenderRow, event: DragEvent) => {
    if (!picked.has(row.address)) { setPicked(new Set([row.address])); anchor.current = row.address }
    event.dataTransfer?.setData?.('text/plain', row.address)
    setDragging(true)
  }
  const dropped = (key: string) => {
    setOver(undefined)
    setDragging(false)
    const chosen = selected.length ? selected : []
    if (chosen.length && onDrop) onDrop(key, chosen)
    clear()
  }

  return (
    <div className={`${css.app} ${dragging ? css.dragging : ''}`}>
      <nav className={css.sidebar} aria-label={t('mail.groups')}>
        <div className={css.brand}>{brand}</div>
        {categories.map(category => (
          <a key={category.key} href={`#${category.key}`}
             className={`${css.category} ${category.key === view ? css.current : ''} ${over === category.key ? css.drop : ''} ${category.dropTarget ? css.target : ''}`}
             aria-current={category.key === view ? 'page' : undefined}
             onClick={(event) => { event.preventDefault(); onView(category.key) }}
             onDragOver={category.dropTarget ? (event) => { event.preventDefault(); setOver(category.key) } : undefined}
             onDragLeave={category.dropTarget ? () => setOver(undefined) : undefined}
             onDrop={category.dropTarget ? (event) => { event.preventDefault(); dropped(category.key) } : undefined}>
            <span className={`${css.dot} ${css[category.dot] ?? ''}`} aria-hidden="true" />
            <span className={css.categoryText}><span>{category.label}</span><small>{category.line}</small></span>
          </a>
        ))}
      </nav>
      <main className={css.content}>
        <h1 className={css.title}>{title}</h1>
        <p className={css.hint}>{hint}</p>
        <table className={css.table}>
          <thead>
            <tr>
              <th className={css.mark}><span className={css.hidden}>{t('mail.selected', { count: '' })}</span></th>
              <th>{t('mail.column.name')}</th>
              <th>{t('mail.column.address')}</th>
              <th className={css.number}>{t('mail.column.mails')}</th>
              <th className={css.number}>{t('mail.column.size')}</th>
              <th className={css.toolsColumn}><span className={css.hidden}>{t('mail.column.tools')}</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => {
              const on = picked.has(row.address)
              return (
                <tr key={row.address} className={`${css.row} ${on ? css.selected : ''} ${selectable ? css.pickable : ''}`}
                    aria-selected={selectable ? on : undefined} draggable={selectable && onDrop !== undefined}
                    onClick={(event) => pick(row, event)} onDragStart={(event) => startDrag(row, event)}
                    onDragEnd={() => { setDragging(false); setOver(undefined) }}>
                  <td className={css.mark}>{on ? '✓' : ''}</td>
                  <td className={css.name}>{row.name}</td>
                  <td className={css.address}>{row.address}</td>
                  <td className={css.number}>{row.mails.toLocaleString('en')}</td>
                  <td className={css.number}>{size(row.size)}</td>
                  <td className={css.tools}>
                    {tools.map(tool => (
                      <button key={tool.key} type="button" className={`${css.tool} ${tool.danger ? css.toolDanger : ''}`}
                              aria-label={tool.label(row)} title={tool.label(row)}
                              onClick={(event) => { event.stopPropagation(); tool.onClick(row) }}>
                        {tool.symbol}
                      </button>
                    ))}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {rows.length === 0 && <p className={css.empty}>{t('mail.empty')}</p>}
      </main>
      <footer className={css.status} aria-live="polite">
        <span className={css.count}>{counts.summary(rows)}</span>
        {selected.length > 0 && (
          <span className={css.picked}>
            {`${t('mail.selected', { count: selected.length.toLocaleString('en') })} · ${counts.mails(selected.reduce((n, r) => n + r.mails, 0))} · ${size(selected.reduce((n, r) => n + r.size, 0))}`}
          </span>
        )}
        {selected.length > 0 && actions && <span className={css.actions}>{actions(selected, clear)}</span>}
        {primary && <span className={css.primary}>{primary}</span>}
      </footer>
    </div>
  )
}
