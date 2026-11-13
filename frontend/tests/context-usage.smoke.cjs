const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')

;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage()
    await page.addInitScript(() => {
      localStorage.setItem('jarvis-react-session', 'context-test')
      window.WebSocket = class { close() {} send() {} }
    })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname
      let data = { ok: true }
      if (path === '/api/app-lock') data = { configured: true, enabled: false, unlocked: true }
      else if (path === '/api/sessions') data = { sessions: [{ id: 'context-test', title: 'Teste de contexto', type: 'chat' }] }
      else if (path.endsWith('/history')) data = { history: [
        { role: 'assistant', content: 'Resposta antiga sem medição.' },
        { role: 'assistant', content: 'Resposta com contexto medido.', meta: { context_usage: [
          { provider: 'groq', model: 'modelo-teste', estimated_tokens: 4200, before_tokens: 6500, budget: 6000, reduced: true },
          { provider: 'groq', model: 'modelo-teste', estimated_tokens: 3500, before_tokens: 3500, budget: 6000, reduced: false },
        ] } },
      ] }
      else if (path === '/api/runs') data = { runs: [], next_cursor: null }
      else if (path === '/api/mission-control') data = { components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] }
      else if (path === '/api/approvals') data = { mode: { enabled: false }, rules: [], durations: {} }
      else if (path === '/api/preferences') data = { preferences: {} }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
    })
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:8000')
    const details = page.locator('.ws-turn-meta')
    await details.locator('summary').waitFor()
    assert.equal(await details.count(), 1)
    assert.match(await details.locator('summary').innerText(), /3\.500.*última chamada medida.*reduzido/)
    await details.locator('summary').click()
    assert.match(await details.innerText(), /4\.200.*6\.000.*6\.500/)
    assert.match(await details.innerText(), /Não representa cobrança/)
    await page.setViewportSize({ width: 360, height: 780 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    assert.deepEqual(errors, [])
    console.log('PASS context usage: per-call estimate, reduction, old history, 360px')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
