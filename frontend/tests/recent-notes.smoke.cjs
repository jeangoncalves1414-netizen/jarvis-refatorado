const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')

;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage()
    page.on('pageerror', error => console.error(error.stack))
    const base = process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173'
    let badSave = true, badList = false
    const received = []
    const path = '05-Notas/Ideia.md'
    await page.addInitScript(() => {
      localStorage.setItem('jarvis-active-screen', 'Dashboard')
      localStorage.setItem('lifeos_infinite_notes', JSON.stringify('Uma ideia antiga\n• [09:12] Nota rápida de teste'))
      localStorage.setItem('lifeos_live_note_teste0001', JSON.stringify({ title: 'A retomar', format: 'checklist', content: '- [ ] Tarefa antiga' }))
      window.WebSocket = class { static OPEN = 1; readyState = 1; send() {} close() {} }
    })
    await page.route('**/*', async route => {
      const url = new URL(route.request().url())
      if (url.origin !== new URL(base).origin) return route.abort()
      if (!url.pathname.startsWith('/api/')) return route.continue()
      let status = 200, data = { ok: true }
      if (url.pathname === '/api/approvals') data = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
      if (url.pathname === '/api/notes/recent') {
        status = badList ? 503 : 200
        data = { notes: [{ title: 'Ideia do agente', path, modified: Date.now() }] }
      } else if (url.pathname === '/api/notes/read') {
        assert.equal(url.searchParams.get('path'), path)
        data = { ok: true, content: 'Texto completo da ideia' }
      } else if (url.pathname === '/api/notes/live') {
        received.push(route.request().postDataJSON())
        status = badSave ? 503 : 200
        data = badSave ? { ok: false, error: 'Offline' } : { ok: true, path }
      } else if (url.pathname === '/api/operational/snapshot') {
        data = { ok: false }; status = 503
      } else if (url.pathname === '/api/finance') data = { totals: { expense: 0 }, transactions: [] }
      else if (url.pathname === '/api/lifeos/habits') data = { habits: [] }
      return route.fulfill({ status, json: data })
    })
    await page.goto(base)
    const notes = page.getByRole('region', { name: 'Últimas anotações' })
    const article = name => notes.locator('.recent-note-row').filter({ hasText: name })
    await article('Ideia do agente').getByRole('button', { name: 'Abrir' }).click()
    let dialog = page.getByRole('dialog', { name: 'Ideia do agente' })
    await dialog.getByText('Texto completo da ideia').waitFor()
    await dialog.getByRole('button', { name: 'Fechar anotação' }).click()
    await notes.getByRole('button', { name: /Ver mais/ }).click()
    await article('Caderno Infinito').getByRole('button', { name: 'Abrir' }).click()
    dialog = page.getByRole('dialog', { name: 'Caderno Infinito' })
    await dialog.getByText(/Uma ideia antiga/).waitFor()
    await page.keyboard.press('Escape')
    await article('A retomar').getByRole('button', { name: 'Retomar' }).click()
    const popup = page.locator('.ws-popup').filter({ hasText: 'Anotação ao vivo' })
    assert.equal(await popup.getByLabel('Texto da anotação').inputValue(), '- [ ] Tarefa antiga')
    await popup.getByLabel('Texto da anotação').fill('- [x] Preservada')
    await popup.getByRole('button', { name: 'Salvar anotação' }).click()
    await popup.getByText(/Não foi possível salvar/).waitFor()
    assert.equal(received.at(-1).draft_id, 'teste0001')
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('lifeos_live_note_teste0001')).content), '- [x] Preservada')
    badSave = false
    await popup.getByRole('button', { name: 'Salvar anotação' }).click()
    await popup.getByText(/Salvo no cofre/).waitFor()
    assert.equal(await page.evaluate(() => localStorage.getItem('lifeos_live_note_teste0001')), null)
    badList = true
    await page.evaluate(() => window.dispatchEvent(new Event('jarvis:notes-changed')))
    await notes.getByText(/Cofre indisponível/).waitFor()
    await article('Caderno Infinito').getByRole('button', { name: 'Abrir' }).click()
    await page.getByRole('dialog', { name: 'Caderno Infinito' }).waitFor()
    console.log('recent-notes.smoke OK')
  } finally {
    await browser.close()
  }
})().catch(err => { console.error(err); process.exitCode = 1 })
