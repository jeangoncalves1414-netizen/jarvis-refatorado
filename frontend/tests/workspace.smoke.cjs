// Run with PLAYWRIGHT_MODULE pointing to an installed playwright/playwright-core.
// All API traffic is intercepted: these tests never alter personal data.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')
const { mkdirSync } = require('node:fs')
const path = require('node:path')
const output = process.env.PANEL_TEST_OUTPUT || path.join(require('node:os').tmpdir(), 'agent-workspace-review')
mkdirSync(output, { recursive: true })

;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ viewport: { width: 1536, height: 960 }, deviceScaleFactor: 1 })
    page.setDefaultTimeout(20000)
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    let offline = false, historyOffline = false, approvals = 0, sent = null, deletions = 0, titles = 0
    let bridgeDevices = [{ id: 'jarvis-desktop', name: 'Jarvis Desktop', kind: 'controller', platform: 'desktop', connected: true }, { id: 'sim-lamp', name: 'Lâmpada de teste', kind: 'light', platform: 'simulator', connected: true }]
    let refuseRemoval = false, sttCalls = 0
    const removals = []
    const histories = new Map()
    let sessions = [{ id: 'session-1', type: 'chat', title: 'Ideias para meu projeto' }, { id: 'session-2', type: 'chat', title: 'Planejamento da semana' }]
    const snapshot = { ok: true, components: [{ id: 'action_kernel', label: 'Ações', status: 'healthy', reason: 'Registro disponível.' }, { id: 'providers', label: 'IA e voz', status: 'healthy', reason: 'Provedor configurado.' }, { id: 'bridge', label: 'Dispositivos', status: 'degraded', reason: 'Nenhum dispositivo conectado.' }], summary: { pending_actions: 1, failed_actions: 1, devices: 0, active_goals: 0 }, goals: [], pending_actions: [{ id: 'action-1', tool_name: 'file_write', preview: 'Criar um arquivo na pasta autorizada', risk: 'medium', status: 'awaiting_confirmation', updated_at: 1793920000 }], recent_actions: [{ id: 'action-2', tool_name: 'web_search', preview: 'Pesquisar referências', result_summary: 'Pesquisa concluída.', risk: 'low', status: 'succeeded', updated_at: 1793920000 }] }
    const oldAction = { id: 'action-old', tool_name: 'old_search', preview: 'Pesquisar uma referência antiga', risk: 'low', status: 'succeeded', updated_at: 1793900000 }
    const events = action => [
      { id: 1, status: 'proposed', kind: 'created', timestamp: action.updated_at - 5, summary: action.preview },
      { id: 2, status: 'running', kind: 'transition', timestamp: action.updated_at - 3 },
      { id: 3, status: action.status, kind: 'transition', timestamp: action.updated_at, summary: action.result_summary },
    ]
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url()), method = route.request().method()
      let data = { ok: true }, status = 200
      if (url.pathname === '/api/mission-control') { data = offline ? { ok: false, error: 'Servidor de teste indisponível.' } : snapshot; status = offline ? 503 : 200 }
      else if (url.pathname === '/api/runs') data = { ok: true, runs: [], next_cursor: null }
      else if (url.pathname === '/api/runs/run-linked') data = { ok: true, run: { id: 'run-linked', session_id: sent.session_id, status: 'succeeded', mode: 'react', created_at: 1793920000, result_summary: 'Resultado deste pedido.' }, actions: [], events: [] }
      else if (url.pathname === '/api/actions') {
        const filter = url.searchParams.get('status'), query = url.searchParams.get('q') || ''
        let items = url.searchParams.has('before') ? [oldAction] : [...snapshot.pending_actions, ...snapshot.recent_actions]
        items = items.filter(item => (!filter || item.status === filter) && (item.tool_name + ' ' + item.preview).includes(query))
        data = historyOffline ? { ok: false, error: 'Histórico temporariamente indisponível.' } : { ok: true, actions: items, next_cursor: url.searchParams.has('before') ? null : 2 }
        status = historyOffline ? 503 : 200
      }
      else if (url.pathname.startsWith('/api/actions/') && method === 'GET') {
        const action = [...snapshot.pending_actions, ...snapshot.recent_actions, oldAction].find(item => url.pathname.endsWith(item.id))
        data = historyOffline ? { ok: false, error: 'Detalhes temporariamente indisponíveis.' } : { ok: true, action, events: events(action) }
        status = historyOffline ? 503 : 200
      }
      else if (url.pathname === '/api/sessions') {
        if (method === 'POST') { const body = route.request().postDataJSON(); const session = { id: 'new-session', title: body.title, type: body.type }; sessions = [session, ...sessions]; data = { ok: true, id: session.id, session } }
        else data = { sessions }
      }
      else if (url.pathname.endsWith('/history')) {
        if (method === 'POST') histories.set(url.pathname, route.request().postDataJSON().history)
        data = { history: histories.get(url.pathname) || [] }
      }
      else if (url.pathname === '/api/sessions/new-session' && method === 'DELETE') deletions++
      else if (url.pathname === '/api/sessions/new-session' && method === 'POST') titles++
      else if (url.pathname === '/api/settings/llm') data = { effective_provider: 'Provedor de teste', effective_model: 'Modelo de demonstração' }
      else if (url.pathname === '/api/chat') { sent = route.request().postDataJSON(); data = { ok: true, reply: 'Resposta de teste recebida. Podemos organizar o projeto em etapas.', context: { run_id: 'run-linked' } } }
      else if (url.pathname.endsWith('/approve')) { approvals++; status = 410; data = { ok: false, error: 'Ação expirou; solicite novamente pela conversa.' } }
      else if (url.pathname === '/api/goals') { status = 500; data = { ok: false, error: 'Não foi possível salvar o objetivo.' } }
      else if (url.pathname === '/api/planning') data = { ok: true, workspace: { session_id: '', title: 'Plano', content: '', is_open: false }, preferences: { auto_open_for_planning: false } }
      else if (url.pathname === '/api/voice/stt' && method === 'POST') { sttCalls++; data = { ok: true, text: 'Texto ditado pela paleta' } }
      else if (url.pathname === '/api/bridge') {
        const body = method === 'POST' ? route.request().postDataJSON() : {}
        if (method === 'GET') data = { ok: true, protocol: 'jarvis-bridge-v1', devices: bridgeDevices, events: [] }
        else if (body.action === 'pairing_code') data = { ok: true, pairing_code: 'TESTE-123' }
        else if (body.action === 'remove') {
          removals.push(body)
          if (refuseRemoval) { status = 400; data = { ok: false, error: 'A ponte recusou a remoção. Sem a credencial do próprio dispositivo, só o painel local do PC, no modo de acesso loopback, pode removê-lo.' } }
          else { bridgeDevices = bridgeDevices.filter(device => device.id !== body.device_id); data = { ok: true, removed: body.device_id } }
        }
      }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    })
    // Force the existing REST fallback instead of contacting a real chat socket.
    await page.routeWebSocket('**/ws/chat', socket => socket.close())
    // Simulated silent microphone: no real audio device is opened.
    await page.addInitScript(() => { navigator.mediaDevices.getUserMedia = async () => new AudioContext().createMediaStreamDestination().stream })
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
    await page.getByRole('heading', { name: 'O que vamos fazer hoje?' }).waitFor()
    await page.getByText('Modelo de demonstração').first().waitFor()
    await page.screenshot({ path: path.join(output, 'desktop-chat.png') })
    console.log('PASS: initial desktop render')
    await page.getByRole('button', { name: 'Planejar um projeto' }).click()
    assert.equal(await page.getByLabel('Modo de conversa').inputValue(), 'planning')
    assert.match(await page.getByLabel('Mensagem para o agente').inputValue(), /plano de projeto/)
    await page.getByLabel('Modo de conversa').selectOption('react')
    await page.getByLabel('Mensagem para o agente').fill('Organizar meu projeto')
    await page.getByRole('button', { name: 'Enviar mensagem', exact: true }).click()
    await page.getByText('Resposta de teste recebida.', { exact: false }).first().waitFor()
    assert.equal(sent.mode, 'react')
    await page.getByRole('button', { name: 'Ver execução' }).waitFor()
    await page.reload()
    await page.getByRole('button', { name: 'Ver execução' }).click()
    await page.getByText('Resultado deste pedido.', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'Fechar pedido' }).click()
    await page.getByRole('heading', { name: 'Execuções', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Autorizar uma vez' }).click()
    await page.getByRole('alert').filter({ hasText: 'Ação expirou' }).waitFor()
    assert.equal(approvals, 1)
    await page.getByLabel('Título do objetivo').fill('Meu objetivo preservado')
    await page.getByLabel('Próximo passo', { exact: true }).fill('Primeira etapa')
    await page.getByRole('button', { name: 'Criar objetivo' }).click()
    await page.getByRole('alert').filter({ hasText: 'Não foi possível salvar' }).waitFor()
    assert.equal(await page.getByLabel('Título do objetivo').inputValue(), 'Meu objetivo preservado')
    await page.getByLabel('Filtrar ações por estado').selectOption('succeeded')
    await page.locator('.ws-execution-row').filter({ hasText: 'web search' }).waitFor()
    assert.equal(await page.locator('.ws-execution-row').count(), 1)
    await page.locator('.ws-execution-row').click()
    await page.getByRole('heading', { name: 'Detalhes da ação' }).waitFor()
    await page.getByRole('heading', { name: 'Linha do tempo' }).waitFor()
    assert.equal(await page.locator('.ws-action-timeline li').count(), 3)
    await page.getByText('3 s', { exact: true }).waitFor()
    await page.screenshot({ path: path.join(output, 'desktop-executions.png') })
    console.log('PASS: chat, approvals, goal drafts, execution filters')
    await page.getByRole('button', { name: 'Próxima', exact: true }).click()
    await page.locator('.ws-execution-row').filter({ hasText: 'old search' }).waitFor()
    await page.getByText('Página 2', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'Anterior', exact: true }).click()
    await page.locator('.ws-execution-row').filter({ hasText: 'web search' }).waitFor()
    await page.getByLabel('Buscar ações').fill('ausente')
    await page.getByRole('heading', { name: 'Nenhuma ação nesta seleção' }).waitFor()
    await page.getByLabel('Buscar ações').fill('web_search')
    await page.locator('.ws-execution-row').waitFor()
    await page.locator('.ws-execution-row').click()
    await page.getByRole('heading', { name: 'Linha do tempo' }).waitFor()
    historyOffline = true
    await page.getByRole('button', { name: 'Atualizar', exact: true }).click()
    await page.getByRole('alert').filter({ hasText: 'Histórico temporariamente indisponível' }).waitFor()
    assert.equal(await page.locator('.ws-action-timeline li').count(), 3)
    await page.getByRole('alert').filter({ hasText: 'Detalhes temporariamente indisponíveis' }).waitFor()
    historyOffline = false
    await page.reload()
    await page.getByRole('heading', { name: 'Execuções', exact: true }).waitFor()
    await page.locator('.ws-execution-row').filter({ hasText: 'web search' }).click()
    await page.getByRole('heading', { name: 'Linha do tempo' }).waitFor()
    assert.equal(await page.locator('.ws-action-timeline li').count(), 3)
    await page.setViewportSize({ width: 360, height: 844 })
    await page.getByRole('heading', { name: 'Linha do tempo' }).scrollIntoViewIfNeeded()
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    await page.screenshot({ path: path.join(output, 'mobile-timeline-360.png') })
    await page.setViewportSize({ width: 1536, height: 960 })
    console.log('PASS: timeline, duration, pagination, search, stale-history errors and reload')
    offline = true
    await page.getByRole('button', { name: 'Atualizar', exact: true }).click()
    await page.getByText('Desconectado', { exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'Autorizar uma vez' }).isDisabled(), true)
    offline = false
    await page.getByRole('button', { name: 'Atualizar', exact: true }).click()
    await page.getByText('Conectado', { exact: true }).waitFor()
    console.log('PASS: disconnect and recovery')
    await page.keyboard.press('Control+k')
    await page.getByPlaceholder('Buscar páginas e ações…').fill('Integrações')
    await page.keyboard.press('Enter')
    await page.getByRole('heading', { name: 'Integrações', exact: true }).waitFor()
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Nova conversa', exact: true }).click()
    await page.getByRole('heading', { name: 'O que vamos fazer hoje?' }).waitFor()
    for (const width of [390, 360]) {
      await page.setViewportSize({ width, height: 844 })
      await page.getByRole('button', { name: 'Abrir navegação', exact: true }).click()
      const drawer = page.getByRole('dialog', { name: 'Navegação', exact: true })
      await drawer.getByRole('button', { name: 'Execuções' }).waitFor()
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: 'Controle do agente', exact: true }).click()
      await page.getByRole('dialog', { name: 'Controle do agente', exact: true }).getByRole('button', { name: 'Gerenciar modelos' }).waitFor()
      await page.keyboard.press('Escape')
      const composer = await page.locator('.ws-composer').boundingBox()
      assert(composer.x >= 0 && composer.x + composer.width <= width && composer.y + composer.height <= 844)
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
      await page.screenshot({ path: path.join(output, 'mobile-' + width + '.png') })
    }
    await page.getByLabel('Mensagem para o agente').fill('Novo título de conversa')
    await page.getByRole('button', { name: 'Enviar mensagem', exact: true }).click()
    await page.locator('.ws-chat-header strong').filter({ hasText: 'Novo título de conversa' }).waitFor()
    assert.equal(titles, 1)
    await page.getByRole('button', { name: 'Enviar mensagem', exact: true }).waitFor()
    await page.locator('.ws-chat-header').getByRole('button', { name: 'Excluir conversa', exact: true }).click()
    const confirmation = page.getByRole('dialog', { name: 'Excluir esta conversa?' })
    await confirmation.getByRole('button', { name: 'Manter conversa' }).click()
    assert.equal(deletions, 0)
    await page.locator('.ws-chat-header').getByRole('button', { name: 'Excluir conversa', exact: true }).click()
    await confirmation.getByRole('button', { name: 'Excluir conversa', exact: true }).click()
    await page.getByRole('heading', { name: 'O que vamos fazer hoje?' }).waitFor()
    assert.equal(deletions, 1)

    await page.setViewportSize({ width: 1536, height: 960 })
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Configurações', exact: true }).click()
    await page.getByRole('button', { name: /Métricas & Logs/ }).click()
    await page.locator('.ws-topbar strong').filter({ hasText: 'Métricas' }).waitFor()
    await page.getByText('LOGS AO VIVO', { exact: true }).waitFor()
    assert.equal(await page.getByText('MIGRAÇÃO GRADUAL').count(), 0)
    await page.screenshot({ path: path.join(output, 'desktop-metrics-from-settings.png') })
    console.log('PASS: Configurações → Métricas & Logs abre Métricas')

    await page.locator('.ws-sidebar').getByRole('button', { name: 'Conversas', exact: true }).click()
    const palette = page.getByRole('dialog', { name: 'Buscar no workspace' })
    await page.keyboard.press('Control+k')
    await palette.getByPlaceholder('Buscar páginas e ações…').fill('conversa por voz')
    assert.equal(await palette.locator('.cmd-item').count(), 1)
    await palette.locator('.cmd-item').filter({ hasText: 'Abrir conversa por voz' }).waitFor()
    await page.screenshot({ path: path.join(output, 'desktop-palette-voice.png') })
    await page.keyboard.press('Enter')
    const call = page.getByRole('dialog', { name: 'Chamada com Jarvis' })
    await call.getByText('Ouvindo continuamente', { exact: false }).waitFor()
    await call.getByRole('button', { name: 'Encerrar', exact: true }).click()
    await call.waitFor({ state: 'detached' })
    await page.keyboard.press('Control+k')
    await palette.getByPlaceholder('Buscar páginas e ações…').fill('Ditado')
    await palette.locator('.cmd-item').filter({ hasText: 'Ditar uma mensagem para o chat' }).waitFor()
    await page.keyboard.press('Enter')
    const mic = page.locator('.ws-composer').getByRole('button', { name: 'Parar gravação', exact: true })
    await mic.waitFor()
    assert.equal(await mic.getAttribute('aria-pressed'), 'true')
    await page.keyboard.press('Control+k')
    await palette.getByPlaceholder('Buscar páginas e ações…').fill('Ditado')
    await palette.locator('.cmd-item').filter({ hasText: 'Parar a gravação e transcrever para o chat' }).waitFor()
    await page.keyboard.press('Enter')
    await page.waitForFunction(() => document.querySelector('.ws-composer textarea')?.value === 'Texto ditado pela paleta')
    assert.equal(sttCalls, 1)
    await page.locator('.ws-composer').getByRole('button', { name: 'Ditar mensagem', exact: true }).waitFor()
    await page.getByLabel('Mensagem para o agente').fill('')
    console.log('PASS: paleta abre a conversa por voz e liga/desliga o ditado com transcrição')

    await page.locator('.ws-sidebar').getByRole('button', { name: 'Automações', exact: true }).click()
    const bridgeCard = page.locator('.bridge-card')
    const lamp = bridgeCard.locator('.bridge-device').filter({ hasText: 'Lâmpada de teste' })
    await lamp.waitFor()
    const removeLamp = bridgeCard.getByRole('button', { name: 'Remover Lâmpada de teste', exact: true })
    const lampDialog = page.getByRole('dialog', { name: 'Remover Lâmpada de teste?' })
    await removeLamp.click()
    await lampDialog.getByRole('button', { name: 'Manter dispositivo' }).click()
    await lampDialog.waitFor({ state: 'hidden' })
    assert.equal(removals.length, 0)
    refuseRemoval = true
    await removeLamp.click()
    await lampDialog.getByRole('button', { name: 'Remover dispositivo', exact: true }).click()
    await bridgeCard.getByRole('alert').filter({ hasText: 'A ponte recusou a remoção' }).waitFor()
    assert.equal(removals.length, 1)
    assert.equal(removals[0].device_id, 'sim-lamp')
    assert.equal(removals[0].device_token, undefined)
    await lamp.waitFor()
    await bridgeCard.scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(output, 'desktop-device-remove-error.png') })
    await page.setViewportSize({ width: 360, height: 844 })
    await bridgeCard.getByRole('alert').scrollIntoViewIfNeeded()
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    await page.screenshot({ path: path.join(output, 'mobile-device-remove-error-360.png') })
    refuseRemoval = false
    await removeLamp.click()
    await lampDialog.waitFor()
    const dialogBox = await page.locator('.bridge-card dialog').boundingBox()
    assert(dialogBox.x >= 0 && dialogBox.x + dialogBox.width <= 360)
    await page.screenshot({ path: path.join(output, 'mobile-device-remove-confirm-360.png') })
    await lampDialog.getByRole('button', { name: 'Remover dispositivo', exact: true }).click()
    await lamp.waitFor({ state: 'detached' })
    assert.equal(await bridgeCard.getByRole('alert').count(), 0)
    assert.equal(removals.length, 2)
    assert.equal(removals[1].device_token, undefined)
    await page.evaluate(() => localStorage.setItem('jarvis-bridge-desktop-token', 'credencial-de-teste'))
    await bridgeCard.getByRole('button', { name: 'Remover Jarvis Desktop', exact: true }).click()
    await page.getByRole('dialog', { name: 'Remover Jarvis Desktop?' }).getByRole('button', { name: 'Remover dispositivo', exact: true }).click()
    await bridgeCard.getByText('Nenhum cliente conectado.').waitFor()
    assert.equal(removals[2].device_id, 'jarvis-desktop')
    assert.equal(removals[2].device_token, 'credencial-de-teste')
    assert.equal(await page.evaluate(() => localStorage.getItem('jarvis-bridge-desktop-token')), null)
    console.log('PASS: remoção de dispositivo com confirmação, erro visível, 360 px e limpeza da credencial local')
    assert.deepEqual(errors, [])
    console.log('PASS: chat/mode, navigation, approvals 410, goal 500 draft, filters/details, disconnect/recovery, palette, mobile drawers/layout. Screenshots: ' + output)
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
