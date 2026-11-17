import { describe, expect, it } from 'vitest'
import { fields, initialValues, toOptions } from '../src/client/options-form.ts'
import { COLLECTORS } from './fake-api.ts'

const imessage = fields(COLLECTORS[1]!.options_schema)
const whatsapp = fields(COLLECTORS[0]!.options_schema)

describe('the form model', () => {
  it('draws one field per option, in the schema\'s order, with the right kind', () => {
    expect(imessage.map(f => [f.name, f.kind])).toEqual([['spam_mode', 'select'], ['workers', 'number'], ['transcribe', 'checkbox']])
    expect(whatsapp.map(f => f.kind)).toEqual(['text', 'text'])
    expect(imessage[0]!.choices).toEqual(['aggressive', 'conservative', 'disabled'])
    expect(imessage[1]).toMatchObject({ integer: true, min: 1, max: 8, label: 'Workers' })
  })

  it('uses the option\'s name when the schema gives no title, and keeps the description as help', () => {
    const [plain] = fields({ type: 'object', properties: { depth: { type: 'integer', description: 'How deep.' } } })
    expect(plain).toMatchObject({ label: 'depth', help: 'How deep.' })
  })

  it('starts from the defaults', () => {
    expect(initialValues(imessage)).toEqual({ spam_mode: 'aggressive', workers: '4', transcribe: false })
    expect(initialValues(whatsapp)).toEqual({ contacts: '', owner: '' })
  })
})

describe('a field that points at a file on this computer', () => {
  const [model, language] = fields({
    type: 'object',
    properties: {
      model: { type: 'string', default: '', title: 'Speech model', 'x-picker': 'file' },
      language: { type: 'string', default: '', title: 'Language' },
    },
  })

  it('is marked, so the form can offer to browse for it', () => {
    expect(model!.picker).toBe(true)
    expect(language!.picker).toBe(false)
    expect(imessage.some(f => f.picker)).toBe(false)
  })
})

describe('what is sent', () => {
  it('nothing, when nothing was changed', () => {
    expect(toOptions(imessage, initialValues(imessage))).toEqual({ options: {}, problems: {} })
  })

  it('only the changes, typed as the schema says', () => {
    const values = { ...initialValues(imessage), spam_mode: 'disabled', workers: '2', transcribe: true }
    expect(toOptions(imessage, values).options).toEqual({ spam_mode: 'disabled', workers: 2, transcribe: true })
  })

  it('trims text and treats blank as the default', () => {
    expect(toOptions(whatsapp, { contacts: '  /me/contacts.vcf  ', owner: '' }).options).toEqual({ contacts: '/me/contacts.vcf' })
  })

  it('a blank number means the default', () => {
    expect(toOptions(imessage, { ...initialValues(imessage), workers: ' ' })).toEqual({ options: {}, problems: {} })
  })

  it('names each problem on its own field', () => {
    const result = toOptions(imessage, { ...initialValues(imessage), workers: '0' })
    expect(result.problems.workers).toEqual({ key: 'form.atLeast', values: { name: 'Workers', min: 1 } })
    expect(toOptions(imessage, { ...initialValues(imessage), workers: '9' }).problems.workers!.key).toBe('form.atMost')
    expect(toOptions(imessage, { ...initialValues(imessage), workers: '2.5' }).problems.workers!.key).toBe('form.whole')
    expect(toOptions(imessage, { ...initialValues(imessage), workers: 'lots' }).problems.workers!.key).toBe('form.number')
  })

  it('a number field that is not an integer accepts decimals', () => {
    const [ratio] = fields({ type: 'object', properties: { ratio: { type: 'number', default: 0.5 } } })
    expect(toOptions([ratio!], { ratio: '0.75' }).options).toEqual({ ratio: 0.75 })
    expect(toOptions([ratio!], { ratio: '0.5' }).options).toEqual({})
  })
})

describe('against what is saved now (a settings page)', () => {
  const current = { spam_mode: 'disabled', workers: 2, transcribe: true }

  it('starts from the saved values, not the defaults', () => {
    expect(initialValues(imessage, current)).toEqual({ spam_mode: 'disabled', workers: '2', transcribe: true })
  })

  it('sends nothing when nothing differs from what is saved', () => {
    expect(toOptions(imessage, initialValues(imessage, current), current)).toEqual({ options: {}, problems: {} })
  })

  it('sends a value put back to its default, because that is a change from what is saved', () => {
    const values = { spam_mode: 'aggressive', workers: '4', transcribe: false }
    expect(toOptions(imessage, values, current).options).toEqual({ spam_mode: 'aggressive', workers: 4, transcribe: false })
  })
})
