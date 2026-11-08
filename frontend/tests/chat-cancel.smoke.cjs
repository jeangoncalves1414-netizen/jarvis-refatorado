const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')

;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage()
    page.setDefaultTimeout(15000)
    await page.addInitScript(() => {
      localStorage.setItem('jarvis-react-session', 'session-1')
      window.WebSocket = class { close() {} send() {} }
    })
    const errors = []
    page.on('pageerror', err => errors.push(err.message))
    let fail = true, offline = false
    const calls = []
    const run = { id: 'run-1', session_id: 'session-1', status: 'running' }
    const other = { id: 'run-2', session_id: 'session-2', status: 'running' }
    let extra = null
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url())
      let data = { ok: true }, status = 200
      if (url.pathname === '/api/sessions') data = { sessions: [{ id: 'session-1', title: 'Conversa um', type: 'chat' }, { id: 'session-2', title: 'Conversa dois', type: 'chat' }] }
      else if (url.pathname.endsWith('/history')) data = { history: [] }
      else if (url.pathname === '/api/runs') {
        if (offline) return route.abort()
        data = { ok: true, runs: [run, other, extra].filter(item => item && item.session_id === url.searchParams.get('session_id') && item.status === url.searchParams.get('status')), next_cursor: null }
      } else if (url.pathname.endsWith('/cancel')) {
        calls.push(url.pathname)
        if (fail) { status = 500; data = { ok: false, error: 'Falha simulada ao cancelar.' } }
        else { run.status = 'cancel_requested'; data = { ok: true, run } }
      } else if (url.pathname === '/api/runs/run-1') data = { ok: true, run }
      else if (url.pathname === '/api/mission-control') data = { ok: true, components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] }
      else if (url.pathname === '/api/planning') data = { ok: true, workspace: { content: '', is_open: false }, preferences: {} }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    })
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
    const stop = page.getByRole('button', { name: 'Parar pedido', exact: true })
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('Parar pedido') && !b.disabled))
    await stop.click()
    await page.getByText('Falha simulada ao cancelar.', { exact: true }).waitFor()
    assert.equal(run.status, 'running')
    fail = false
    await page.keyboard.press('Control+k')
    await page.getByRole('dialog', { name: 'Buscar no workspace' }).getByRole('textbox').fill('parar pedido')
    await page.getByText('Parar pedido desta conversa', { exact: true }).click()
    await page.getByText('Cancelamento solicitado. Aguardando o encerramento da etapa em andamento.', { exact: true }).waitFor()
    assert.equal(await stop.isDisabled(), true)
    assert.deepEqual(calls, ['/api/runs/run-1/cancel', '/api/runs/run-1/cancel'])
    assert.equal(other.status, 'running')
    run.status = 'cancelled'
    await page.getByText('Pedido cancelado. Os efeitos das etapas concluídas foram preservados.', { exact: true }).waitFor()
    run.status = 'running'
    await page.reload()
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('Parar pedido') && !b.disabled))
    extra = { ...run, id: 'run-3' }
    await page.getByText('Há vários pedidos nesta conversa. Escolha o pedido em Execuções.', { exact: true }).waitFor()
    assert.equal(await stop.isDisabled(), true)
    extra = null
    offline = true
    await page.waitForFunction(() => document.body.textContent.includes('Failed to fetch'))
    assert.equal(await stop.isDisabled(), true)
    offline = false
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('Parar pedido') && !b.disabled))
    await page.setViewportSize({ width: 360, height: 844 })
    await page.getByLabel('Mensagem para o agente').fill('/parar')
    await page.getByLabel('Mensagem para o agente').press('Enter')
    await page.getByText('Cancelamento solicitado. Aguardando o encerramento da etapa em andamento.', { exact: true }).waitFor()
    assert.equal(calls.length, 3)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await page.getByLabel('Mensagem para o agente').fill('/voz')
    await page.getByLabel('Mensagem para o agente').press('Enter')
    await page.getByRole('dialog', { name: 'Conversa por voz' }).waitFor()
    assert.equal(await page.locator('.live-call-orb-wrapper, .reactor-orb-stage').count(), 0)
    assert.deepEqual(errors, [])
    console.log('PASS — cancelamento pelo chat, paleta e /parar, retry, isolamento, reload, desconexão, 360 px e ligação sem orb')
  } finally { await browser.close() }
})().catch(err => { console.error(err); process.exit(1) })
