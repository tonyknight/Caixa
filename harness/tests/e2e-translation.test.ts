// Translation in Settings, in a real browser against the real worker: the endpoint is tried with the
// Test button (here a stand-in for an OpenAI-compatible server), the key is saved outside the box and
// never comes back to the page, and an endpoint on the internet needs an explicit yes.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { canRun, openCaixa, playwright, shot, startHarness, type Running } from './e2e-support.ts'

const run = canRun && playwright() ? describe : describe.skip

/** Every file under `folder`, read as text. */
function everything(folder: string): string {
  return readdirSync(folder).map((name) => {
    const path = join(folder, name)
    return statSync(path).isDirectory() ? everything(path) : readFileSync(path, 'latin1')
  }).join('\n')
}

run('translation settings, in a browser', () => {
  let running: Running
  let model: Server
  let endpoint: string
  let box: string
  const asked: { authorization: string | undefined; body: any }[] = []

  beforeAll(async () => {
    model = createServer((request, response) => {
      let text = ''
      request.on('data', chunk => { text += chunk })
      request.on('end', () => {
        const body = JSON.parse(text)
        asked.push({ authorization: request.headers.authorization, body })
        if (body.model === 'missing-model') {
          response.writeHead(404, { 'Content-Type': 'application/json' })
          response.end(JSON.stringify({ error: { message: 'model "missing-model" not found' } }))
          return
        }
        response.writeHead(200, { 'Content-Type': 'application/json' })
        response.end(JSON.stringify({ choices: [{ message: { content: 'Good morning! We arrived safely.' } }] }))
      })
    })
    await new Promise<void>(resolve => model.listen(0, '127.0.0.1', resolve))
    endpoint = `http://127.0.0.1:${(model.address() as AddressInfo).port}/v1`
    running = await startHarness()
    box = join(running.work, 'Translation box')
    const made = await running.rpc('box.create', { path: box, name: 'Translation box', owner: 'Maria Costa' })
    expect(made.ok, JSON.stringify(made)).toBe(true)
  }, 180_000)
  afterAll(async () => { await running?.stop(); model?.close() })

  it('tests an endpoint, says why a wrong model fails, and keeps the key out of the box and the page', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click()
      await page.getByRole('group', { name: 'Translation' }).waitFor()
      await page.getByLabel('Translation endpoint').fill(endpoint)
      await page.getByLabel('Translation model').fill('missing-model')
      await page.getByRole('button', { name: 'Test', exact: true }).click()
      const result = page.getByTestId('translation-test-result')
      await result.waitFor()
      expect(await result.textContent()).toContain('The test failed.')
      expect(await result.textContent()).toContain('model "missing-model" not found')

      await page.getByLabel('Translation model').fill('test-model')
      await page.getByLabel('API key').fill('sk-browser-secret')
      await page.getByRole('button', { name: 'Test', exact: true }).click()
      await page.getByText('It works.', { exact: false }).waitFor()
      expect(await result.textContent()).toContain('Good morning! We arrived safely.')
      await shot(page, 'translation-test')
      const last = asked[asked.length - 1]!
      expect(last.authorization).toBe('Bearer sk-browser-secret')
      expect(last.body.messages[0].content).toContain('Return only the translated text and nothing else')
      expect((await running.rpc('settings.get')).result.values['translation.endpoint']).toBe('')  // testing saved nothing

      await page.getByLabel('Translate messages that are not in English').check()
      await page.getByRole('button', { name: 'Save settings' }).click()
      await page.getByText('Settings saved.').waitFor()
      await page.getByText('A key is saved for this endpoint.', { exact: false }).waitFor()
      expect(await page.getByLabel('API key').inputValue()).toBe('')
      const saved = (await running.rpc('settings.get')).result
      expect(saved.values['translation.enabled']).toBe(true)
      expect(saved.translation).toEqual({ key_saved: true })
      expect(JSON.stringify(saved)).not.toContain('sk-browser-secret')
      expect(everything(box)).not.toContain('sk-browser-secret')

      // the saved key is used when none is typed
      await page.getByRole('button', { name: 'Test', exact: true }).click()
      await page.getByText('It works.', { exact: false }).waitFor()
      expect(asked[asked.length - 1]!.authorization).toBe('Bearer sk-browser-secret')
    } finally { await browser.close() }
  }, 180_000)

  it('will not turn on a service on the internet without an explicit yes', async () => {
    const browser = await playwright()!.chromium.launch()
    try {
      const page = await openCaixa(browser, running)
      await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click()
      await page.getByRole('group', { name: 'Translation' }).waitFor()
      await page.getByLabel('Translation endpoint').fill('https://openrouter.ai/api/v1')
      await page.getByRole('button', { name: 'Save settings' }).click()
      await page.getByText('message text would leave this computer', { exact: false }).waitFor()
      expect((await running.rpc('settings.get')).result.values['translation.endpoint']).toBe(endpoint)
      await page.getByLabel('Allow a service on the internet').check()
      await page.getByRole('button', { name: 'Save settings' }).click()
      await page.getByText('Settings saved.').waitFor()
      expect((await running.rpc('settings.get')).result.values['translation.endpoint']).toBe('https://openrouter.ai/api/v1')
      // the key saved for the local endpoint is not offered to the new host
      await page.getByText('No key is saved for this endpoint.', { exact: false }).waitFor()
    } finally { await browser.close() }
  }, 180_000)
})
