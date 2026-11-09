// Isolated API fixtures; no real model, action or user data is touched.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')
const { assertSourceHasNoBrokenText, assertPageHasNoBrokenText } = require('./broken-text.cjs')
const { mkdirSync } = require('node:fs')
const path = require('node:path')
const output = path.join(require('node:os').tmpdir(), 'agent-workspace-review')
mkdirSync(output, { recursive: true })

;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ viewport: { width: 1536, height: 960 } })
    page.setDefaultTimeout(15000)
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    let failCancel = true, offline = false, cancelCalls = 0
    const now = 1793920000
    const run = { id: 'run-test', session_id: 'session-1', mode: 'research', status: 'running', created_at: now, finished_at: null, result_summary: null }
    const action = { id: 'action-test', run_id: run.id, tool_name: 'web_search', status: 'running', preview: 'Pesquisar referências', risk: 'low', updated_at: now }
    const old = { ...run, id: 'run-old', status: 'interrupted', mode: 'planning', result_summary: 'Backend reiniciado; pedido interrompido e não reexecutado.', finished_at: now + 5 }
    const event = { id: 1, kind: 'created', status: 'running', timestamp: now, summary: 'Pedido recebido.', action_id: null }
    const queries = []
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url())
      let status = 200, data = { ok: true }
      if (url.pathname === '/api/sessions') data = { sessions: [{ id: 'session-1', title: 'Referências do projeto', type: 'chat' }] }
      else if (url.pathname.endsWith('/history')) data = { history: [] }
      else if (url.pathname === '/api/settings/llm') data = { effective_provider: 'Teste', effective_model: 'Modelo de teste' }
      else if (url.pathname === '/api/mission-control') data = { ok: true, components: [], summary: { pending_actions: 1, failed_actions: 0, devices: 0 }, goals: [], pending_actions: [], recent_actions: [action] }
      else if (url.pathname === '/api/approvals') data = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
      else if (url.pathname === '/api/actions') data = { ok: true, actions: [action], next_cursor: null }
      else if (url.pathname === '/api/actions/action-test') data = { ok: true, action, events: [{ ...event, action_id: action.id }] }
      else if (url.pathname === '/api/runs') {
        queries.push(url.searchParams.toString())
        const items = url.searchParams.has('before') ? [old] : [run]
        data = { ok: true, runs: items.filter(item => !url.searchParams.has('status') || url.searchParams.get('status') === item.status), next_cursor: url.searchParams.has('before') ? null : 2 }
      } else if (url.pathname.endsWith('/cancel')) {
        cancelCalls++
        if (failCancel) { status = 500; data = { ok: false, error: 'Não foi possível registrar o cancelamento.' } }
        else { run.status = 'cancel_requested'; data = { ok: true, run } }
      } else if (url.pathname.startsWith('/api/runs/')) {
        const selected = url.pathname.endsWith('run-old') ? old : run
        data = { ok: true, run: selected, actions: selected === run ? [action] : [], events: [event, { ...event, id: 2, kind: 'status', status: selected.status, timestamp: now + 5, summary: selected.result_summary }] }
      }
      if (offline && url.pathname.startsWith('/api/runs')) { status = 503; data = { ok: false, error: 'Pedidos temporariamente indisponíveis.' } }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    })
    await page.routeWebSocket('**/ws/chat', socket => socket.close())
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Execuções' }).click()
    const panel = page.getByRole('region', { name: 'Pedidos de execução', exact: true })
    await panel.locator('.ws-run-row').click()
    const detail = page.getByRole('region', { name: 'Detalhes do pedido', exact: true })
    await detail.getByRole('button', { name: 'Cancelar pedido' }).click()
    await detail.getByRole('alert').filter({ hasText: 'Não foi possível registrar' }).waitFor()
    assert.equal(cancelCalls, 1)
    await detail.getByRole('definition').filter({ hasText: 'Em andamento' }).waitFor()
    failCancel = false
    await detail.getByRole('button', { name: 'Cancelar pedido' }).click()
    await detail.getByRole('status').filter({ hasText: 'Aguardando confirmação' }).waitFor()
    assert.equal(cancelCalls, 2)
    assert(await detail.getByRole('button', { name: 'Cancelar pedido' }).isDisabled())
    assert.equal(await detail.getByRole('definition').filter({ hasText: 'Cancelado', exact: true }).count(), 0)
    await page.screenshot({ path: path.join(output, 'desktop-request-cancelling.png') })
    await page.reload()
    await panel.locator('.ws-run-row').click()
    await detail.getByRole('status').filter({ hasText: 'Aguardando confirmação' }).waitFor()
    await detail.locator('.ws-run-action').click()
    await detail.getByRole('heading', { name: 'Detalhes da ação' }).waitFor()
    await detail.getByRole('button', { name: 'Fechar detalhes' }).click()
    offline = true
    await page.getByRole('button', { name: 'Atualizar', exact: true }).click()
    await detail.getByRole('alert').filter({ hasText: 'último estado recebido' }).waitFor()
    assert.equal(await detail.locator('.ws-run-action').count(), 1)
    offline = false
    run.status = 'cancelled'; run.finished_at = now + 15; run.result_summary = 'Pedido encerrado após cancelamento. Etapas já executadas não foram desfeitas.'
    action.status = 'succeeded'
    await page.getByRole('button', { name: 'Atualizar', exact: true }).click()
    await detail.getByRole('definition').filter({ hasText: 'Cancelado', exact: true }).waitFor()
    assert.equal(await detail.getByRole('button', { name: 'Cancelar pedido' }).count(), 0)
    await panel.getByRole('button', { name: 'Mais pedidos' }).click()
    await panel.locator('.ws-run-row').filter({ hasText: 'Interrompido após reinício' }).click()
    await detail.getByText('Backend reiniciado; pedido interrompido e não reexecutado.', { exact: true }).first().waitFor()
    await panel.getByRole('button', { name: 'Pedidos anteriores' }).click()
    await panel.getByRole('button', { name: 'Todas as conversas' }).click()
    await panel.getByRole('button', { name: 'Conversa atual' }).waitFor()
    await panel.getByLabel('Filtrar pedidos por estado').selectOption('cancelled')
    await panel.locator('.ws-run-row').click()
    assert(queries.some(query => query.includes('session_id=session-1')))
    await page.setViewportSize({ width: 360, height: 844 })
    await detail.scrollIntoViewIfNeeded()
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    await page.screenshot({ path: path.join(output, 'mobile-request-360.png') })
    await detail.getByRole('button', { name: 'Abrir conversa' }).click()
    await page.getByRole('heading', { name: 'O que vamos fazer hoje?' }).waitFor()
    assertSourceHasNoBrokenText(); await assertPageHasNoBrokenText(page)
    assert.deepEqual(errors, [])
    console.log('PASS: request grouping, cancel 500/retry/pending/terminal, reload, stale detail, recovery, pagination, session filter, mobile 360 and conversation link.')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
