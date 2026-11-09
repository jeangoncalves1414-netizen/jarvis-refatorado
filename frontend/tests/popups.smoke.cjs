const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')

// Lote 6, Fase 3: fila/pilha dos popups, ttl, mesma chave, Fixar, Esc, movimento reduzido,
// deduplicação com context.ui_popups, clique fora livre, 360 px e configuração dos popups.
const popup = (id, { key = id, title = id, ttl = 0, lines = [] } = {}) => ({
  id: `pop_${id}`, key, template: 'info', version: 1, title, origin: 'chat', created_at: 1, ttl_ms: ttl, pinned: false,
  data: { title, lines, tone: 'info' }, animate: {},
})
// Fase 4: envelopes dos modelos de dados (formato de app/agent/popups.py).
const envelope = (id, key, template, title, data, animate = {}) => ({ id: `pop_${id}`, key, template, version: 1, title, origin: 'chat', created_at: 1, ttl_ms: 0, pinned: false, data, animate })
const habit = (id, name, done = false, streak = 0) => ({ id, name, category: 'geral', routine_block: 'morning', start_time: '07:00', days_of_week: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'], completed_today: done, streak })
const habitPopup = (id, items, added) => envelope(id, 'habits', 'habit_list', 'Hábitos', { filter: 'today', items, completed: items.filter(item => item.completed_today).length, total: items.length, highlight_ids: added }, { added_ids: added })
const waterPopup = (id, key, previous, current, target = 3000) => envelope(id, key, 'water', 'Água de hoje', { date: '2026-08-04', current_ml: current, previous_ml: previous, target_ml: target, percentage: Math.round(current / target * 100) }, { from_ml: previous, to_ml: current })
// Fase 5: tarefas e lugares.
const task = (id, title, completed = false, priority = 4, due_date = '') => ({ id, title, priority, due_date, completed })
const taskPopup = (id, items, animate) => envelope(id, 'tasks', 'task_list', 'Tarefas', { filter: 'pending', items, pending: items.filter(item => !item.completed).length, total: items.length }, animate)
const placeResults = () => [
  { name: 'Padaria Central', address: 'Rua A, 10, São Paulo', lat: -23.55, lon: -46.63, category: 'bakery' },
  { name: 'Padaria Bela Vista', address: 'Rua B, 20, São Paulo', lat: -23.56, lon: -46.64, category: 'bakery' },
  { name: 'Padoca do Bairro', address: 'Rua C, 30, São Paulo', lat: -23.57, lon: -46.65, category: 'bakery', rating: 4.6 },
]
const placesPopup = id => envelope(id, 'places:abc123', 'places', 'Lugares', { query: 'padaria', near: '', provider: 'osm', results: placeResults().map((item, index) => ({ id: `p${index}`, ...item })), bbox: [-46.651, -23.571, -46.629, -23.549], attribution: '© colaboradores do OpenStreetMap', notice: '' }, { added_ids: ['p0', 'p1', 'p2'] })
const notesPopup = (draft, title, dictate, format = 'bullets') => envelope(`notes-${draft}`, `notes:${draft}`, 'live_notes', 'Anotação ao vivo', { draft_id: draft, title, format, dictate, content: '' })

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
    const notePosts = []
    const captureCalls = []
    let noteStatus = 200
    const captureScript = [
      { seq: 1, type: 'transcript', text: 'comprar pão', stt_ms: 100 },
      { seq: 2, type: 'transcript', text: 'comprar leite', stt_ms: 100 },
      { seq: 3, type: 'transcript', text: 'fim da nota', stt_ms: 100 },
    ]
    let popupSettings = { enabled: true, auto: true, ttl_seconds: 8, max_visible: 3 }
    const placeCalls = []
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
      // Fase 4: comandos sem IA, anotação ao vivo e captura do PC simulada.
      else if (url.pathname === '/api/popups/habit_list') data = { ok: true, popup: habitPopup('cmd-habits', [habit('cmd-h1', 'Beber água', true, 4)], []) }
      else if (url.pathname === '/api/popups/water') data = { ok: true, popup: waterPopup('cmd-water', 'water:cmd', 1000, 1000) }
      else if (url.pathname === '/api/popups/live_notes') {
        data = { ok: true, popup: notesPopup('note0001aaaa', url.searchParams.get('title') || 'Anotação', url.searchParams.get('dictate') !== 'false') }
      }
      else if (url.pathname === '/api/notes/live') {
        notePosts.push(JSON.parse(request.postData() || '{}'))
        if (noteStatus !== 200) { status = noteStatus; data = { ok: false, error: 'Falha simulada no cofre.' } }
        else data = { ok: true, path: '05-Notas/Compras-note00.md' }
      }
      // Fase 5: busca de lugares (janela) e tarefas.
      else if (url.pathname === '/api/places') {
        placeCalls.push({ q: url.searchParams.get('q'), near: url.searchParams.get('near') })
        data = { ok: true, query: url.searchParams.get('q'), near: url.searchParams.get('near') || '', provider: 'osm', results: placeResults(), bbox: [-46.641, -23.561, -46.629, -23.549], attribution: '© colaboradores do OpenStreetMap', notice: '', action: { id: 'act_1', status: 'succeeded' } }
      }
      else if (url.pathname === '/api/popups/task_list') data = { ok: true, popup: taskPopup('cmd-tasks', [task('cmd-t1', 'Pagar luz', false, 1)], {}) }
      else if (url.pathname === '/api/settings/mic') data = { ok: true, engine: 'auto' }
      else if (url.pathname === '/api/voice/capture/status') data = { ok: true, available: true, active: false, reason: '' }
      else if (url.pathname === '/api/voice/capture/start') { captureCalls.push('start'); data = { ok: true, seq: 0, threshold: 300 } }
      else if (url.pathname === '/api/voice/capture/stop') { captureCalls.push('stop'); data = { ok: true } }
      else if (url.pathname === '/api/voice/capture/events') {
        const after = Number(url.searchParams.get('after') || 0)
        await new Promise(resolve => setTimeout(resolve, 500))
        const events = captureScript.filter(event => event.seq > after)
        data = { ok: true, events: events.slice(0, 2), seq: events.length ? events.slice(0, 2).at(-1).seq : after, active: true }
      }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    })
    // Mapa do OSM simulado: nenhuma requisição sai para a internet.
    const mapLoads = []
    await page.route('https://www.openstreetmap.org/**', async route => {
      mapLoads.push(route.request().url())
      await route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>mapa</title>' })
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

    // ── Fase 4: modelos de dados ─────────────────────────────────────────────
    await closeAll()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)
    await page.locator('.ws-sidebar').getByRole('button', { name: 'Conversas', exact: true }).click().catch(async () => {
      await page.locator('.ws-sidebar').getByRole('button', { name: /Conversas|Chat/ }).first().click()
    })
    await away()

    // Hábitos: os 3 novos entram um a um, depois do que já existia.
    await page.evaluate(() => {
      window.__itemOrder = []
      const seen = new Set()
      const record = () => document.querySelectorAll('[data-popup-item]').forEach(el => {
        const id = el.getAttribute('data-popup-item')
        if (id && id.startsWith('hab-') && !seen.has(id)) { seen.add(id); window.__itemOrder.push({ id, t: performance.now() }) }
      })
      window.__itemObserver = new MutationObserver(record)
      window.__itemObserver.observe(document.body, { childList: true, subtree: true })
    })
    const newHabits = [habit('hab-2', 'Ler'), habit('hab-3', 'Meditar'), habit('hab-4', 'Correr')]
    await show(habitPopup('habits1', [habit('hab-1', 'Alongar', true, 3), ...newHabits], ['hab-2', 'hab-3', 'hab-4']))
    await card('Hábitos').locator('[data-popup-item="hab-4"]').waitFor()
    const order = await page.evaluate(() => { window.__itemObserver.disconnect(); return window.__itemOrder })
    assert.deepEqual(order.map(item => item.id), ['hab-1', 'hab-2', 'hab-3', 'hab-4'])
    assert.ok(order[2].t - order[1].t >= 150 && order[3].t - order[2].t >= 150, `itens entraram juntos: ${JSON.stringify(order)}`)
    await card('Hábitos').getByText('1 de 4 feito(s) hoje').waitFor()
    assert.equal(await card('Hábitos').locator('[data-new="true"]').count(), 3)
    await card('Hábitos').getByRole('button', { name: 'Fechar popup' }).click()

    // Água: sobe de 1.500 para 3.000 e termina com "meta batida".
    await show(waterPopup('water1', 'water:2026-08-04', 1500, 3000))
    const water = card('Água de hoje')
    await water.locator('.ws-popup-water-main').waitFor()
    await page.waitForFunction(() => document.querySelector('.ws-popup-water-main')?.textContent === '3.000 de 3.000 ml')
    await water.getByText('meta batida', { exact: true }).waitFor()
    assert.equal(await water.getAttribute('class').then(value => value.includes('tone-ok')), true)
    await water.getByRole('button', { name: 'Fechar popup' }).click()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)
    // Movimento reduzido: o valor final já no primeiro quadro.
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await show(waterPopup('water2', 'water:2026-08-05', 0, 2000))
    const firstFrame = await page.waitForFunction(() => document.querySelector('.ws-popup-water-main')?.textContent || null).then(handle => handle.jsonValue())
    assert.equal(firstFrame, '2.000 de 3.000 ml')
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await card('Água de hoje').getByRole('button', { name: 'Fechar popup' }).click()

    // Agenda: o compromisso novo é destacado na linha do tempo.
    await show(envelope('sched1', 'schedule:2026-08-04', 'schedule', 'Agenda', { date: '2026-08-04', events: [
      { id: 'ev-1', title: 'Academia', start: '2026-08-04T07:00', reminder_at: null },
      { id: 'ev-2', title: 'Dentista', start: '2026-08-04T15:00', reminder_at: '2026-08-04T14:45' },
    ] }, { added_ids: ['ev-2'] }))
    const schedule = card('Agenda')
    await schedule.locator('[data-popup-item="ev-2"] .ws-popup-event[data-new="true"]').waitFor()
    await schedule.locator('.ws-popup-insert.active').waitFor()
    assert.equal(await schedule.locator('.ws-popup-event[data-new="true"]').count(), 1)
    await schedule.getByText('15:00', { exact: true }).waitFor()
    await schedule.getByRole('button', { name: 'Fechar popup' }).click()

    // /habitos e /hidratacao montam o popup pela API, nunca pelo chat.
    const chatBefore = apiCalls.filter(item => item === '/api/chat').length
    await composer.fill('/habitos')
    await page.keyboard.press('Enter')
    await card('Hábitos').getByText('Beber água').waitFor()
    await composer.fill('/hidratacao')
    await page.keyboard.press('Enter')
    await card('Água de hoje').locator('.ws-popup-water-main').waitFor()
    assert.ok(apiCalls.includes('/api/popups/habit_list') && apiCalls.includes('/api/popups/water'))
    assert.equal(apiCalls.filter(item => item === '/api/chat').length, chatBefore)
    await closeAll()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)

    // /nota Compras: escrita à mão, Checklist e Salvar; erro 500 mantém o rascunho.
    await composer.fill('/nota Compras')
    await page.keyboard.press('Enter')
    const note = card('Anotação ao vivo')
    await note.getByLabel('Texto da anotação').waitFor()
    assert.equal(await note.getByLabel('Título da anotação').inputValue(), 'Compras')
    await note.getByLabel('Texto da anotação').fill('pão\nleite')
    await note.getByRole('button', { name: 'Checklist' }).click()
    assert.equal(await note.getByLabel('Texto da anotação').inputValue(), '- [ ] pão\n- [ ] leite')
    noteStatus = 500
    await note.getByRole('button', { name: 'Salvar anotação' }).click()
    await note.getByText('Não foi possível salvar: Falha simulada no cofre.', { exact: false }).waitFor()
    assert.deepEqual(notePosts.at(-1), { draft_id: 'note0001aaaa', title: 'Compras', format: 'checklist', content: '- [ ] pão\n- [ ] leite' })
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('lifeos_live_note_note0001aaaa') || 'null')?.content), '- [ ] pão\n- [ ] leite')
    assert.equal(await note.getByLabel('Texto da anotação').inputValue(), '- [ ] pão\n- [ ] leite')
    noteStatus = 200
    await note.getByRole('button', { name: 'Salvar anotação' }).click()
    await note.getByText('Salvo no cofre (05-Notas/Compras-note00.md).', { exact: true }).waitFor()
    assert.equal(await page.evaluate(() => localStorage.getItem('lifeos_live_note_note0001aaaa')), null)
    assert.equal(apiCalls.filter(item => item === '/api/chat').length, chatBefore)
    await note.getByRole('button', { name: 'Fechar popup' }).click()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)

    // Ditado pelo microfone do PC (captura simulada): frases viram itens; "fim da nota" para e salva.
    const postsBefore = notePosts.length
    await show(notesPopup('note0002bbbb', 'Mercado', true))
    const live = card('Anotação ao vivo')
    await live.getByRole('button', { name: 'Parar ditado' }).waitFor()
    await live.getByText('comprar pão', { exact: false }).waitFor()
    await live.getByRole('button', { name: 'Gravar ditado' }).waitFor({ timeout: 10000 })
    assert.equal(await live.getByLabel('Texto da anotação').inputValue(), '- comprar pão\n- comprar leite')
    assert.ok(captureCalls.includes('start') && captureCalls.at(-1) === 'stop', `captura: ${captureCalls.join(',')}`)
    for (let i = 0; i < 20 && notePosts.length === postsBefore; i += 1) await page.waitForTimeout(100)
    assert.equal(notePosts.length, postsBefore + 1)
    assert.deepEqual(notePosts.at(-1), { draft_id: 'note0002bbbb', title: 'Mercado', format: 'bullets', content: '- comprar pão\n- comprar leite' })
    await live.getByText('Salvo no cofre', { exact: false }).waitFor()

    // ── Fase 5: tarefas e lugares ────────────────────────────────────────────
    await closeAll()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)
    await away()

    // Tarefas: as novas entram com destaque; concluir na mesma chave risca sem empilhar.
    await show(taskPopup('tasks1', [task('t-1', 'Lavar louça'), task('t-2', 'Pagar luz', false, 1), task('t-3', 'Ligar pro banco')], { added_ids: ['t-2', 't-3'] }))
    const tasks = card('Tarefas')
    await tasks.locator('[data-popup-item="t-3"]').waitFor()
    assert.equal(await tasks.locator('.ws-popup-task[data-new="true"]').count(), 2)
    await tasks.getByText('3 pendente(s)', { exact: true }).waitFor()
    await show(taskPopup('tasks2', [task('t-1', 'Lavar louça', true), task('t-2', 'Pagar luz', false, 1), task('t-3', 'Ligar pro banco')], { toggled_ids: ['t-1'] }))
    await tasks.locator('.ws-popup-task[data-done="true"] .ws-popup-task-strike').waitFor()
    await tasks.getByText('2 pendente(s)', { exact: true }).waitFor()
    assert.equal(await cards.count(), 1)
    await tasks.getByText('P1', { exact: true }).waitFor()
    await tasks.getByRole('button', { name: 'Fechar popup' }).click()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)

    // /pendencias monta o popup pela API, sem chat.
    await composer.fill('/pendencias')
    await page.keyboard.press('Enter')
    await card('Tarefas').getByText('Pagar luz').waitFor()
    assert.ok(apiCalls.includes('/api/popups/task_list'))
    await closeAll()
    await page.waitForFunction(() => document.querySelectorAll('.ws-popup').length === 0)

    // Lugares: 3 resultados entram em sequência, atribuição visível, "Ver no mapa" abre a janela.
    await show(placesPopup('places1'))
    const placesCard = card('Lugares')
    await placesCard.locator('[data-popup-item="p2"]').waitFor()
    assert.equal(await placesCard.locator('.ws-popup-place').count(), 3)
    await placesCard.getByText('© colaboradores do OpenStreetMap', { exact: false }).waitFor()
    await placesCard.getByText('4.6', { exact: false }).waitFor()
    await placesCard.getByRole('button', { name: 'Ver no mapa' }).click()
    const placesWindow = page.locator('.ws-window').filter({ has: page.locator('.ws-window-titlebar strong', { hasText: 'Lugares' }) })
    await placesWindow.locator('iframe').waitFor()
    assert.deepEqual(placeCalls.at(-1), { q: 'padaria', near: null })
    await placesWindow.getByRole('button', { name: 'Fechar janela' }).click()
    await placesWindow.waitFor({ state: 'detached' })
    await closeAll()

    // /lugares padaria: abre a janela e busca; digitar não busca, só enviar.
    const callsBefore = placeCalls.length
    await composer.fill('/lugares padaria')
    await page.keyboard.press('Enter')
    await placesWindow.locator('iframe').waitFor()
    assert.equal(placeCalls.length, callsBefore + 1)
    assert.equal(await placesWindow.getByLabel('O que procurar').inputValue(), 'padaria')
    const src = await placesWindow.locator('iframe').getAttribute('src')
    const iframeUrl = new URL(src)
    assert.equal(iframeUrl.origin + iframeUrl.pathname, 'https://www.openstreetmap.org/export/embed.html')
    assert.ok(iframeUrl.searchParams.get('bbox') && iframeUrl.searchParams.get('marker') === '-23.55,-46.63', src)
    await placesWindow.getByText('Mapa: © colaboradores do OpenStreetMap', { exact: false }).waitFor()
    await placesWindow.getByRole('link', { name: 'Abrir no mapa' }).waitFor()
    // Escolher outro resultado move o marcador.
    await placesWindow.getByRole('button', { name: /Padaria Bela Vista/ }).click()
    await page.waitForFunction(() => document.querySelector('.ws-places-map iframe')?.getAttribute('src')?.includes('marker=-23.56%2C-46.64'))
    await placesWindow.getByLabel('O que procurar').fill('farmácia')
    await placesWindow.getByLabel('Perto de').fill('Centro')
    await page.waitForTimeout(400)
    assert.equal(placeCalls.length, callsBefore + 1)
    await placesWindow.getByLabel('Perto de').press('Enter')
    for (let i = 0; i < 20 && placeCalls.length === callsBefore + 1; i += 1) await page.waitForTimeout(100)
    assert.deepEqual(placeCalls.at(-1), { q: 'farmácia', near: 'Centro' })
    assert.equal(apiCalls.filter(item => item === '/api/chat').length, chatBefore)
    await placesWindow.getByRole('button', { name: 'Fechar janela' }).click()

    assert.deepEqual(errors, [])
    console.log('PASS — ttl, mesma chave, fila 3+2, clique fora, paleta fecha popups, Fixar, Esc, sem duplicar com o complete, inválido avisa, movimento reduzido, 360 px, configuração, hábitos em sequência, água com meta batida, agenda com destaque, /habitos, /hidratacao, /nota com Checklist e erro 500, ditado com "fim da nota", tarefas animadas, /pendencias, lugares com mapa, /lugares só busca ao enviar')
  } finally { await browser.close() }
})().catch(err => { console.error(err); process.exit(1) })
