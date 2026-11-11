const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')
const { assertSourceHasNoBrokenText, assertPageHasNoBrokenText } = require('./broken-text.cjs')

// Lote 6, Fase 2: contador do loop agêntico, resposta retomada e configuração "Agente e popups".
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
    const savedHistories = []
    const loopPosts = []
    let failNextSave = false
    let waterFails = true
    const waterPosts = []
    let loopSettings = { mode: 'auto', max_steps: 8, max_model_calls: 10, auto_verify: true, extract_memory_always: false }
    await page.route('**/api/**', async route => {
      const request = route.request()
      const url = new URL(request.url())
      let data = { ok: true }, status = 200
      if (url.pathname === '/api/sessions') data = { sessions: [{ id: 'session-1', title: 'Conversa um', type: 'chat' }] }
      else if (url.pathname.endsWith('/history')) {
        if (request.method() === 'POST') savedHistories.push(JSON.parse(request.postData() || '{}').history)
        data = { history: [] }
      } else if (url.pathname === '/api/evolute/water/add') {
        waterPosts.push(JSON.parse(request.postData() || '{}').amount_ml)
        if (waterFails) { status = 500; data = { ok: false, error: 'banco indisponível' } } else data = { ok: true, total_ml: 500, added_ml: 250 }
      } else if (url.pathname === '/api/runs') data = { ok: true, runs: [], next_cursor: null }
      else if (url.pathname === '/api/mission-control') data = { ok: true, components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] }
      else if (url.pathname === '/api/approvals') data = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
      else if (url.pathname === '/api/planning') data = { ok: true, workspace: { content: '', is_open: false }, preferences: {} }
      else if (url.pathname === '/api/settings/agent-loop') {
        if (request.method() === 'POST') {
          const body = JSON.parse(request.postData() || '{}')
          loopPosts.push(body)
          if (failNextSave) { status = 400; data = { ok: false, error: 'O limite de etapas deve ser um número inteiro de 1 a 20.' } }
          else { loopSettings = body; data = { ok: true, settings: loopSettings } }
        } else data = { ok: true, settings: loopSettings }
      }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    })
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
    await page.locator('.ws-chat-header strong').filter({ hasText: 'Conversa um' }).waitFor()

    // Turno aberto: o contador aparece no balão do assistente.
    const composer = page.getByLabel('Mensagem para o agente')
    await composer.fill('adiciona ler e meditar nos hábitos e depois agenda dentista amanhã')
    await composer.press('Enter')
    await page.waitForFunction(() => window.__wsSent.length === 1)
    const sent = await page.evaluate(() => window.__wsSent[0])
    assert.equal(sent.session_id, 'session-1')
    const progress = { type: 'agent_progress', session_id: 'session-1', run_id: 'run-1', step: 2, max_steps: 8, model_calls: 2, max_model_calls: 10, phase: 'acting' }
    await page.evaluate(event => window.__wsEmit(event), progress)
    await page.getByText('Etapa 2 de 8', { exact: true }).waitFor()
    await page.getByText('· 2/10 chamadas ao modelo', { exact: true }).waitFor()
    await page.getByText('· executando', { exact: true }).waitFor()
    // Evento de outra conversa nunca entra nesta.
    await page.evaluate(event => window.__wsEmit({ ...event, session_id: 'outra', step: 7 }), progress)
    assert.equal(await page.getByText('Etapa 7 de 8', { exact: true }).count(), 0)

    // A etapa pede aprovação: o turno termina com o aviso.
    await page.evaluate(() => window.__wsEmit({ type: 'complete', session_id: 'session-1', summary: 'A etapa 3 precisa da sua aprovação na Central. Assim que você aprovar, eu continuo sozinho.', intent: 'agent_loop', actions: [], context: { run_id: 'run-1' } }))
    await page.getByText('Assim que você aprovar, eu continuo sozinho.', { exact: false }).first().waitFor()
    await page.waitForFunction(() => !document.querySelector('.ws-agent-progress'))

    // Retomada fora do turno: contador "Continuando" e depois a resposta como mensagem nova.
    await page.evaluate(event => window.__wsEmit({ ...event, step: 3, model_calls: 2, phase: 'resumed' }), progress)
    await page.getByText('Etapa 3 de 8', { exact: true }).waitFor()
    await page.getByText('Continuando a sequência…', { exact: true }).waitFor()
    await page.evaluate(() => window.__wsEmit({ type: 'agent_reply', session_id: 'session-1', run_id: 'run-1', reply: 'Tudo feito depois da aprovação.' }))
    await page.locator('.ws-message.assistant').filter({ hasText: 'Tudo feito depois da aprovação.' }).waitFor()
    await page.waitForFunction(() => !document.querySelector('.ws-agent-progress'))
    const lastHistory = savedHistories.at(-1)
    assert.equal(lastHistory.at(-1).role, 'assistant')
    assert.equal(lastHistory.at(-1).content, 'Tudo feito depois da aprovação.')
    assert.equal(lastHistory.at(-1).run_id, 'run-1')
    assert.equal(typeof lastHistory.at(-1).timestamp, 'number')
    // A mesma resposta repetida não duplica a mensagem.
    await page.evaluate(() => window.__wsEmit({ type: 'agent_reply', session_id: 'session-1', run_id: 'run-1', reply: 'Tudo feito depois da aprovação.' }))
    await page.waitForTimeout(200)
    assert.equal(await page.locator('.ws-message.assistant').filter({ hasText: 'Tudo feito depois da aprovação.' }).count(), 1)

    // MG9: a resposta retomada de OUTRO pedido não fecha o turno em andamento; entra como mensagem própria.
    await composer.fill('segunda pergunta')
    await composer.press('Enter')
    await page.waitForFunction(() => window.__wsSent.length === 2)
    await page.evaluate(event => window.__wsEmit(event), { ...progress, run_id: 'run-2', step: 1, phase: 'planning' })
    await page.getByText('Etapa 1 de 8', { exact: true }).waitFor()
    await page.evaluate(() => window.__wsEmit({ type: 'agent_reply', session_id: 'session-1', run_id: 'run-antigo', reply: 'Resposta do pedido antigo.' }))
    await page.locator('.ws-message.assistant').filter({ hasText: 'Resposta do pedido antigo.' }).waitFor()
    assert.equal(await page.getByText('Etapa 1 de 8', { exact: true }).count(), 1, 'o contador do pedido em andamento continua')
    await page.evaluate(() => window.__wsEmit({ type: 'complete', session_id: 'session-1', summary: 'Resposta da segunda pergunta.', intent: 'agent_loop', actions: [], context: { run_id: 'run-2' } }))
    await page.locator('.ws-message.assistant').filter({ hasText: 'Resposta da segunda pergunta.' }).waitFor()
    await page.waitForFunction(() => !document.querySelector('.ws-agent-progress'))
    const afterB = savedHistories.at(-1).slice(-2)
    assert.deepEqual(afterB.map(item => item.content), ['Resposta do pedido antigo.', 'Resposta da segunda pergunta.'])
    assert.deepEqual(afterB.map(item => item.run_id), ['run-antigo', 'run-2'])

    // MG23: se a gravação da água falha, mostra o erro real, não soma e guarda o rascunho; depois reenvia.
    await composer.fill('/agua')
    await page.keyboard.press('Enter')
    await page.getByText('Não consegui registrar +250ml de água (banco indisponível)', { exact: false }).first().waitFor()
    assert.equal(await page.getByText('+250ml de água registrados', { exact: false }).count(), 0)
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('jarvis-water-drafts') || '[]').length), 1)
    waterFails = false
    await composer.fill('/agua')
    await page.keyboard.press('Enter')
    await page.getByText('Reenviei 250ml de água que estavam guardados.', { exact: false }).first().waitFor()
    assert.equal(await page.evaluate(() => localStorage.getItem('jarvis-water-drafts')), null)
    assert.deepEqual(waterPosts, [250, 250, 250])

    // Turno com erro: a falha aparece e o chat não fica preso; o próximo envio funciona.
    await composer.fill('terceira pergunta')
    await composer.press('Enter')
    await page.waitForFunction(() => window.__wsSent.length === 3)
    await page.evaluate(() => window.__wsEmit({ type: 'error', session_id: 'session-1', message: 'Falha na comunicação com o Jarvis.' }))
    await page.locator('.ws-error').filter({ hasText: 'Não foi possível obter resposta do Jarvis' }).waitFor()
    await composer.fill('quarta pergunta')
    await composer.press('Enter')
    await page.waitForFunction(() => window.__wsSent.length === 4)

    // Configurações > Agente e popups.
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Configurações', exact: true }).click()
    await page.locator('.st-nav').getByRole('button', { name: 'Agente e popups' }).click()
    const card = page.locator('.agent-loop-card')
    await card.getByRole('heading', { name: 'Execução em várias etapas' }).waitFor()
    await card.getByLabel('Sempre').check()
    await card.getByLabel('Limite de etapas (1 a 20)').fill('12')
    await card.getByLabel('Limite de chamadas ao modelo (1 a 30)').fill('15')
    await card.getByRole('switch').first().click()
    assert.equal(await card.getByRole('switch').nth(1).getAttribute('aria-checked'), 'false')
    await card.getByRole('switch').nth(1).click()
    await card.getByRole('button', { name: 'Salvar configuração do agente' }).click()
    await card.getByText('Configuração do agente salva.', { exact: true }).waitFor()
    assert.deepEqual(loopPosts.at(-1), { mode: 'always', max_steps: 12, max_model_calls: 15, auto_verify: false, extract_memory_always: true })
    failNextSave = true
    await card.getByRole('button', { name: 'Salvar configuração do agente' }).click()
    await card.getByRole('alert').filter({ hasText: 'O limite de etapas deve ser um número inteiro de 1 a 20.' }).waitFor()

    await page.setViewportSize({ width: 360, height: 844 })
    await card.waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    assertSourceHasNoBrokenText(); await assertPageHasNoBrokenText(page)
    assert.deepEqual(errors, [])
    console.log('PASS — contador do loop, resposta retomada sem duplicar, isolamento por conversa, configuração do agente, erro do servidor e 360 px')
  } finally { await browser.close() }
})().catch(err => { console.error(err); process.exit(1) })
