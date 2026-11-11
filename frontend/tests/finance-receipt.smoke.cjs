const { chromium, expect } = require('@playwright/test')
const assert = require('node:assert/strict')

// Painel real, com extrato e eventos do agente inteiramente em memória.
async function run() {
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ reducedMotion: 'reduce' })
    page.on('pageerror', error => console.error(error.stack))
    const session = 'finance-fixture'
    await page.addInitScript(id => localStorage.setItem('jarvis-react-session', id), session)
    let socket
    await page.routeWebSocket('**/ws/chat', ws => { socket = ws })
    const entries = Array.from({ length: 4 }, (_, index) => ({
      id: 'tx' + index, type: 'expense', amount: 10 + index, category: 'Mercado',
      description: 'Compra ' + index, date_str: '2025-06-17',
    }))
    let net = -46
    let lastFilter, savedRequest, failSave = true
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname
      let data = { ok: true }, status = 200
      if (path === '/api/approvals') data = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
      if (path === '/api/sessions') data.sessions = [{ id: session, title: 'Finanças teste', type: 'chat' }]
      if (path.endsWith('/history')) data.history = []
      if (path === '/api/runs') data.runs = []
      if (path === '/api/mission-control') Object.assign(data, { components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] })
      if (path === '/api/finance') {
        const body = route.request().postDataJSON()
        if (body.action === 'list') {
          lastFilter = body
          Object.assign(data, { transactions: entries, totals: { net, income: 0, expense: -net, count: entries.length }, categories: ['Mercado'], truncated: false })
        } else if (body.action === 'get') data.transaction = entries.find(entry => entry.id === body.id)
        else if (body.action === 'update') {
          savedRequest = body
          if (failSave) { status = 503; data = { ok: false, error: 'Serviço indisponível' } }
        }
      }
      await route.fulfill({ status, json: data })
    })
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
    await expect.poll(() => Boolean(socket)).toBe(true)
    await expect(page.locator('.ws-chat-header strong')).toContainText('Finanças teste')
    const show = id => socket.send(JSON.stringify({ type: 'ui_popup', session_id: session, popup: {
      id: 'pop_' + id, key: 'finance-receipt', template: 'finance_receipt', version: 1,
      origin: 'chat', ttl_ms: 0, title: 'Finanças', data: { entries: [entries[3]], before: -33, after: -46, period: '2025-06' },
    } }))
    const popup = page.locator('.ws-finance-receipt')
    show('first')
    await expect(popup).toContainText('junho de 2025')
    await expect(popup).toContainText('46,00')
    if (process.env.SCREENSHOT_DIR) {
      require('node:fs').mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true })
      await popup.locator('..').screenshot({ path: process.env.SCREENSHOT_DIR + '/recibo-financas.png' })
    }
    await popup.getByRole('button', { name: 'Ver finanças' }).click()
    const panel = page.locator('.ws-finance')
    await expect(panel.locator('.ws-finance-list li')).toHaveCount(3)
    await expect(panel.locator('form')).toHaveCount(0)
    await panel.getByRole('button', { name: 'Ver todos os lançamentos' }).click()
    await expect(panel.locator('.ws-finance-list li')).toHaveCount(4)
    await panel.getByText('Filtros do extrato').click()
    await panel.getByLabel('Período', { exact: true }).selectOption('week')
    await panel.getByRole('button', { name: 'Registrar', exact: true }).click()
    const amount = panel.getByLabel('Valor (R$)')
    await amount.fill('99,90')
    net = -50
    await page.evaluate(() => window.dispatchEvent(new Event('jarvis:finance-changed')))
    await expect(panel.locator('.ws-finance-totals')).toContainText('50,00')
    await expect(amount).toHaveValue('99,90')
    assert.ok(lastFilter.date_from && lastFilter.date_to)
    show('second')
    await popup.getByRole('button', { name: 'Corrigir Compra 3' }).click()
    const confirm = page.getByRole('alertdialog')
    await expect(confirm).toContainText('Substituir o rascunho?')
    await confirm.getByRole('button', { name: 'Cancelar' }).click()
    await expect(amount).toHaveValue('99,90')
    show('third')
    await popup.getByRole('button', { name: 'Corrigir Compra 3' }).click()
    await confirm.getByRole('button', { name: 'Substituir' }).click()
    await expect(amount).toHaveValue('13')
    await amount.fill('14,50')
    await panel.getByRole('button', { name: 'Salvar alterações' }).click()
    await expect(panel.getByRole('alert')).toContainText('rascunho foi mantido')
    await expect(amount).toHaveValue('14,50')
    failSave = false
    await panel.getByRole('button', { name: 'Tentar novamente' }).click()
    await expect(panel.getByRole('status')).toHaveText('Lançamento atualizado.')
    assert.deepEqual([savedRequest.action, savedRequest.id, savedRequest.amount], ['update', 'tx3', 14.5])
    console.log('Recibo, consulta compacta, filtro, atualização, rascunho e correção verificados.')
  } finally {
    await browser.close()
  }
}

run().catch(error => { console.error(error); process.exitCode = 1 })
