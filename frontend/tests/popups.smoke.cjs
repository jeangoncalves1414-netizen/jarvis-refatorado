const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')

// Lote 6, Fase 3: fila/pilha dos popups, ttl, mesma chave, Fixar, Esc, movimento reduzido,
// deduplicação com context.ui_popups, clique fora livre, 360 px e configuração dos popups.
const popup = (id, { key = id, title = id, ttl = 0, lines = [] } = {}) => ({
  id: `pop_${id}`, key, template: 'info', version: 1, title, origin: 'chat', created_at: 1, ttl_ms: ttl, pinned: false,
  data: { title, lines, tone: 'info' }, animate: {},
})

;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } })
    page.setDefaultTimeout(15000)
    await page.addInitScript(() => {
      localStorage.setItem('jarvis-react-session', 'session-1')
      window.__wsSockets = []
      window.__wsSent = []
      class FakeWebSocket {
        constructor(url) {
          this.url = url
          this.readyState = 1
          window.__wsSockets.push(this)
          setTimeout(() => this.onopen && this.onopen({}), 0)
        }
        send(data) { window.__wsSent.push(JSON.parse(data)) }
        close() { this.readyState = 3 }
      }
      FakeWebSocket.CONNECTING = 0
      FakeWebSocket.OPEN = 1
      FakeWebSocket.CLOSING = 2
      FakeWebSocket.CLOSED = 3
      window.WebSocket = FakeWebSocket
      window.__wsEmit = obj => window.__wsSockets.forEach(socket => socket.onmessage && socket.onmessage({ data: JSON.stringify(obj) }))
    })
    const errors = []
    page.on('pageerror', err => errors.push(err.message))
    const popupPosts = []
    const apiCalls = []
    let popupSettings = { enabled: true, auto: true, ttl_seconds: 8, max_visible: 3 }
    await page.route('**/api/**', async route => {
      const request = route.request()
      const url = new URL(request.url())
      apiCalls.push(url.pathname)
      let data = { ok: true }, status = 200
      if (url.pathname === '/api/sessions') data = { sessions: [{ id: 'session-1', title: 'Conversa um', type: 'chat' }] }
      else if (url.pathname.endsWith('/history')) data = { history: [] }
      else if (url.pathname === '/api/runs') data = { ok: true, runs: [], next_cursor: null }
      else if (url.pathname === '/api/mission-control') data = { ok: true, components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] }
      else if (url.pathname === '/api/approvals') data = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
      else if (url.pathname === '/api/planning') data = { ok: true, workspace: { content: '', is_open: false }, preferences: {} }
      else if (url.pathname === '/api/settings/agent-loop') data = { ok: true, settings: { mode: 'auto', max_steps: 8, max_model_calls: 10, auto_verify: true } }
      else if (url.pathname === '/api/settings/popups') {
        if (request.method() === 'POST') { popupSettings = JSON.parse(request.postData() || '{}'); popupPosts.push(popupSettings) }
        data = { ok: true, settings: popupSettings }
      }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    })
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
    await page.locator('.ws-chat-header strong').filter({ hasText: 'Conversa um' }).waitFor()
    const emit = value => page.evaluate(event => window.__wsEmit(event), value)
    const show = value => emit({ type: 'ui_popup', session_id: 'session-1', run_id: 'run-1', popup: value })
    const cards = page.locator('.ws-popup')
    const card = title => cards.filter({ has: page.locator('.ws-popup-head strong', { hasText: title }) })
    const away = () => page.mouse.move(5, 5)
    const closeAll = async () => {
      await page.keyboard.press('Control+k')
      const input = page.locator('.cmd-palette-header input')
      await input.waitFor()
      await input.fill('Fechar popups')
      await page.locator('.cmd-item').filter({ hasText: 'Fechar todos os popups' }).click()
    }
    await away()

    // Aparece e some sozinho depois do ttl.
    await show(popup('a', { title: 'Some sozinho', ttl: 1200, lines: ['linha um'] }))
    await card('Some sozinho').waitFor()
    await card('Some sozinho').getByText('linha um').waitFor()
    await card('Some sozinho').waitFor({ state: 'detached', timeout: 6000 })

    // Mesma chave atualiza no lugar, sem empilhar.
    await show(popup('b', { key: 'k1', title: 'Primeiro' }))
    await card('Primeiro').waitFor()
    await show(popup('c', { key: 'k1', title: 'Segundo' }))
    await card('Segundo').waitFor()
    assert.equal(await cards.count(), 1)
    await card('Segundo').getByRole('button', { name: 'Fechar popup' }).click()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)

    // 5 popups: 3 na tela, 2 na fila; fechar um traz o próximo.
    for (const n of [1, 2, 3, 4, 5]) await show(popup(`f${n}`, { title: `Fila ${n}` }))
    await card('Fila 3').waitFor()
    await page.waitForTimeout(150)
    assert.equal(await cards.count(), 3)
    await page.getByText('+2 na fila', { exact: true }).waitFor()
    assert.equal(await card('Fila 4').count(), 0)
    await card('Fila 1').getByRole('button', { name: 'Fechar popup' }).click()
    await card('Fila 4').waitFor()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 3)
    // Clique fora dos cartões não é bloqueado pela camada.
    assert.equal(await page.locator('.ws-popup-layer').evaluate(el => getComputedStyle(el).pointerEvents), 'none')
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Configurações', exact: true }).click()
    await page.locator('.st-nav').waitFor()
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Conversas', exact: true }).click().catch(async () => {
      await page.locator('.ws-sidebar').getByRole('button', { name: /Conversas|Chat/ }).first().click()
    })

    // Paleta: "Fechar popups" limpa a tela e a fila.
    await closeAll()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)
    assert.equal(await page.getByText('na fila', { exact: false }).count(), 0)

    // Fixar impede expirar; soltar volta a contar.
    await show(popup('pin', { title: 'Fixado', ttl: 1200 }))
    await card('Fixado').getByRole('button', { name: 'Fixar popup' }).click()
    await away()
    await page.waitForTimeout(2200)
    assert.equal(await card('Fixado').count(), 1)
    assert.equal(await card('Fixado').locator('.ws-popup-ttl').count(), 0)
    await card('Fixado').getByRole('button', { name: 'Soltar popup' }).click()
    await away()
    await card('Fixado').waitFor({ state: 'detached', timeout: 6000 })

    // Esc fecha o popup focado.
    await show(popup('esc', { title: 'Fecha com Esc' }))
    await card('Fecha com Esc').locator('.ws-popup-head strong').click()
    await page.keyboard.press('Escape')
    await card('Fecha com Esc').waitFor({ state: 'detached' })

    // Popup do WebSocket e o mesmo id no "complete" do turno: um só.
    const composer = page.getByLabel('Mensagem para o agente')
    await composer.fill('mostra um aviso')
    await composer.press('Enter')
    await page.waitForFunction(() => window.__wsSent.length === 1)
    const dup = popup('dup', { title: 'Sem duplicar' })
    await show(dup)
    await card('Sem duplicar').waitFor()
    await emit({ type: 'complete', session_id: 'session-1', summary: 'Mostrei.', intent: 'agent_loop', actions: [], context: { run_id: 'run-2', ui_popups: [dup, popup('ctx', { title: 'Só no contexto' })] } })
    await card('Só no contexto').waitFor()
    assert.equal(await card('Sem duplicar').count(), 1)
    // Popup inválido não abre e avisa.
    await show({ ...popup('bad', { title: 'Inválido' }), template: 'nada' })
    await page.getByText('O agente pediu um popup inválido.', { exact: false }).first().waitFor()
    assert.equal(await card('Inválido').count(), 0)

    // Movimento reduzido: sem animação, opacidade final logo no começo.
    await closeAll()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await show(popup('calm', { title: 'Calmo', lines: ['a', 'b'] }))
    await card('Calmo').waitFor()
    assert.equal(await card('Calmo').getAttribute('data-motion'), 'calm')
    await page.waitForTimeout(200)
    assert.equal(await card('Calmo').evaluate(el => getComputedStyle(el).opacity), '1')
    assert.equal(await card('Calmo').locator('[data-popup-item]').count(), 2)
    await page.emulateMedia({ reducedMotion: 'no-preference' })

    // 360 px: popup no topo, sem rolagem horizontal.
    await page.setViewportSize({ width: 360, height: 844 })
    await card('Calmo').waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    const box = await card('Calmo').boundingBox()
    assert.ok(box && box.x >= 0 && box.x + box.width <= 360 && box.y < 120)
    await page.setViewportSize({ width: 1366, height: 900 })

    // Configurações > Agente e popups > Popups animados.
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Configurações', exact: true }).click()
    await page.locator('.st-nav').getByRole('button', { name: 'Agente e popups' }).click()
    const settings = page.locator('.popup-settings-card')
    await settings.getByRole('heading', { name: 'Popups animados' }).waitFor()
    await settings.getByLabel('Máximo na tela (1 a 5)').fill('2')
    await settings.getByLabel('Fechar sozinho após (s, 0 = fica até fechar)').fill('0')
    await settings.getByRole('button', { name: 'Salvar configuração dos popups' }).click()
    await settings.getByText('Configuração dos popups salva.', { exact: true }).waitFor()
    assert.deepEqual(popupPosts.at(-1), { enabled: true, auto: true, ttl_seconds: 0, max_visible: 2 })
    // O novo limite vale na hora.
    for (const n of [1, 2, 3]) await show(popup(`m${n}`, { title: `Limite ${n}` }))
    await page.getByText('na fila', { exact: false }).first().waitFor()
    assert.equal(await cards.count(), 2)
    assert.ok(!apiCalls.includes('/api/chat'))

    assert.deepEqual(errors, [])
    console.log('PASS — ttl, mesma chave, fila 3+2, clique fora, paleta fecha popups, Fixar, Esc, sem duplicar com o complete, inválido avisa, movimento reduzido, 360 px e configuração')
  } finally { await browser.close() }
})().catch(err => { console.error(err); process.exit(1) })
