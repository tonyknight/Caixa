/** All text the Caixa pages show, by language. A new language is one more object here. */

export const NS = 'caixa'

/** English: the source language and the key domain. */
export const en = {
  panel: 'Caixa',
  'page.title': 'Caixa',
  'page.lead': 'Collect, preserve and pass on a digital life.',
  'worker.checking': 'Checking the Caixa worker…',
  'worker.running': 'The Caixa worker is running (version {version}).',
  'worker.readOnly': 'This box is open read-only.',
  'worker.restarting': 'The Caixa worker stopped and is starting again.',
  'worker.failed': 'The Caixa worker could not be started. Is Caixa installed on this computer?',
  'worker.stopped': 'The Caixa worker is not running.',
  'worker.retry': 'Check again',
} as const

export type CaixaKey = keyof typeof en
export type Dictionary = Record<CaixaKey, string>

/** Simplified Chinese: DSH expects it beside English. */
export const zh: Dictionary = {
  panel: 'Caixa',
  'page.title': 'Caixa',
  'page.lead': '收集、保存并传承一段数字生活。',
  'worker.checking': '正在检查 Caixa 后台服务…',
  'worker.running': 'Caixa 后台服务正在运行（版本 {version}）。',
  'worker.readOnly': '此档案盒以只读方式打开。',
  'worker.restarting': 'Caixa 后台服务已停止，正在重新启动。',
  'worker.failed': '无法启动 Caixa 后台服务。这台电脑上安装了 Caixa 吗？',
  'worker.stopped': 'Caixa 后台服务未在运行。',
  'worker.retry': '重新检查',
}

/** Dictionaries by language code; other languages fall back to English. */
export const dictionaries: { en: Dictionary; zh: Dictionary } = { en, zh }
