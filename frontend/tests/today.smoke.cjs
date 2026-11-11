const assert = require('node:assert/strict')
const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ viewport: { width: 1300, height: 850 } })
    page.on('pageerror', error => console.error(error.stack))
    await page.addInitScript(() => {
      localStorage.setItem('jarvis-active-screen', 'Dashboard')
      localStorage.setItem('jarvis-react-session', 'demo')
    })
    let chatSocket
    await page.routeWebSocket('**/ws/chat', socket => { chatSocket = socket })
    let done = false
    let expense = 42
    let failFinance = false
    let writes = 0
    const habits = () => [
      { id: 'walk', name: 'Caminhada', completed_today: false, start_time: '09:00' },
      { id: 'read', name: 'Leitura', isPriority: true, completed_today: done, completed_at: done ? Date.now() / 1000 : null },
    ]
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url())
      let status = 200
      let json = { ok: true }
      if (url.pathname === '/api/personal') json = { ok: true, tasks: [], plans: [], workouts: [], accounts: {}, recurring_due: [], history: [], preferences: { blocks: ['habits', 'tasks', 'workout', 'finance', 'notes'], reduced_motion: false, review: 'off' } }
      if (url.pathname === '/api/lifeos/habits') {
        assert.equal(url.searchParams.get('today'), '1')
        json.habits = habits()
      } else if (url.pathname === '/api/lifeos/habits/read/toggle') {
        assert.deepEqual(route.request().postDataJSON(), { completed: true })
        done = true
        writes++
        json.habit = { ...habits()[1], changed: true }
      } else if (url.pathname === '/api/finance') {
        const payload = route.request().postDataJSON()
        assert.equal(payload.action, 'list')
        assert.equal(payload.date_from, payload.date_to)
        if (failFinance) status = 503
        else json = { ok: true, transactions: [{ id: 'tx', description: 'Mercado', type: 'expense', amount: expense, timestamp: Date.now() / 1000 - 240 }], totals: { expense } }
      } else if (url.pathname === '/api/approvals') {
        json = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
      } else if (url.pathname === '/api/mission-control') {
        json = { ok: true, components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] }
      } else if (url.pathname === '/api/notes/recent') {
        json.notes = [{ path: '05-Notas/ideia.md', title: 'Ideia do dia', modified: Date.now() }]
      } else if (url.pathname === '/api/sessions') {
        json.sessions = [{ id: 'demo', title: 'Conversa', type: 'chat' }]
      }
      await route.fulfill({ status, json })
    })

    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
    const today = page.getByRole('region', { name: 'Hoje', exact: true })
    await today.getByText('Leitura', { exact: true }).first().waitFor()
    await today.getByRole('button', { name: 'Feito', exact: true }).click()
    await today.getByText('1 de 2 feitos').waitFor()
    await today.getByText('Caminhada', { exact: true }).waitFor()
    assert.equal(writes, 1)
    await today.getByText('Registros de hoje', { exact: true }).click()
    await today.getByText('Mercado', { exact: true }).waitFor()
    await today.locator('.today-history').getByText('Ideia do dia', { exact: true }).waitFor()
    const money = today.getByRole('region', { name: 'Saídas de hoje' })
    await money.getByText(/42,00/).waitFor()
    expense = 67
    assert.ok(chatSocket, 'Conexão ao barramento do painel')
    chatSocket.send(JSON.stringify({ type: 'personal_data_changed', area: 'finance' }))
    await money.getByText(/67,00/).waitFor()
    failFinance = true
    await page.evaluate(() => window.dispatchEvent(new Event('jarvis:finance-changed')))
    await money.getByRole('button', { name: 'Tentar novamente' }).waitFor()
    assert.equal(await today.getByText('Caminhada', { exact: true }).isVisible(), true)
    failFinance = false
    await money.getByRole('button', { name: 'Tentar novamente' }).click()
    await money.getByText(/67,00/).waitFor()
    if (process.env.SCREENSHOT_DIR) {
      require('node:fs').mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true })
      await today.screenshot({ path: process.env.SCREENSHOT_DIR + '/hoje-desktop.png' })
    }
    await page.setViewportSize({ width: 390, height: 844 })
    const width = await today.evaluate(node => ({ client: node.clientWidth, scroll: node.scrollWidth }))
    assert.ok(width.scroll <= width.client + 1, 'Cartão Hoje deve caber no celular')
    if (process.env.SCREENSHOT_DIR) await today.screenshot({ path: process.env.SCREENSHOT_DIR + '/hoje-mobile.png' })
    console.log('PASS — hábito prioritário, marcação única, histórico, gasto via evento do agente, falha isolada, nova tentativa e 390 px')
  } finally {
    await browser.close()
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
