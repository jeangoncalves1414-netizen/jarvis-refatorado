import { test, expect, type Page } from '@playwright/test'

const initial = [{ role: 'user', content: 'Mensagem original', timestamp: 1794312000000 }, { role: 'assistant', content: 'Resposta anterior', run_id: 'plain-chat-run', timestamp: 1794312001000 }]

test('incomplete markdown never locks session loading or deletion', async ({ page }) => {
  await setup(page)
  await page.route('**/api/sessions/*/history', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ history: [{ role: 'assistant', content: '| Tabela incompleta |\n1 objetivo\n# \n|\nTexto depois' }] }) }))
  await page.reload()
  await expect(page.getByText('Texto depois', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Excluir conversa', exact: true }).click()
  await page.getByRole('button', { name: 'Manter conversa' }).click()
  await page.getByLabel('Mensagem para o agente').fill('Ainda responde')
  await expect(page.getByLabel('Mensagem para o agente')).toHaveValue('Ainda responde')
  await page.getByRole('button', { name: 'Excluir conversa', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Excluir conversa', exact: true }).click()
  await expect(page.locator('.ws-sidebar').getByRole('button', { name: 'Teste de conversa', exact: true })).toHaveCount(0)
  await page.getByLabel('Mensagem para o agente').fill('Nova conversa responde')
  await expect(page.getByLabel('Mensagem para o agente')).toHaveValue('Nova conversa responde')
})

test('drafts survive switching sessions and reloading', async ({ page }) => {
  await setup(page)
  const input = page.getByLabel('Mensagem para o agente')
  await input.fill('Rascunho A')
  await page.locator('.ws-sidebar').getByRole('button', { name: 'Planejamento de treinos e finanças da semana 0', exact: true }).click()
  await expect(input).toHaveValue('')
  await input.fill('Rascunho B')
  await page.locator('.ws-sidebar').getByRole('button', { name: 'Teste de conversa', exact: true }).click()
  await expect(input).toHaveValue('Rascunho A')
  await page.reload()
  await expect(input).toHaveValue('Rascunho A')
})

test('sidebar divider resizes and persists', async ({ page }) => {
  await setup(page)
  const divider = page.locator('.ws-sidebar [role="separator"]')
  const before = Number(await divider.getAttribute('aria-valuenow'))
  await divider.focus(); await page.keyboard.press('ArrowUp')
  await expect(divider).toHaveAttribute('aria-valuenow', String(before - 20))
  await page.reload()
  await expect(divider).toHaveAttribute('aria-valuenow', String(before - 20))
})

test('delete dialog can be cancelled without locking the chat', async ({ page }) => {
  await setup(page)
  await page.getByRole('button', { name: 'Excluir conversa', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Excluir esta conversa?' })).toBeVisible()
  await page.getByRole('button', { name: 'Manter conversa' }).click()
  await page.getByLabel('Mensagem para o agente').fill('Interface responde')
  await expect(page.getByLabel('Mensagem para o agente')).toHaveValue('Interface responde')
})

test('message actions sit outside the bubble and history rows do not shrink', async ({ page }) => {
  await setup(page)
  const message = page.locator('.ws-message.user').first()
  await message.hover()
  const bubble = await message.locator('.ws-message-bubble').boundingBox()
  const actions = await message.locator('.ws-message-actions').boundingBox()
  expect(actions!.y).toBeGreaterThanOrEqual(bubble!.y + bubble!.height)
  const rows = page.locator('.ws-sidebar .ws-chat-row')
  expect(await rows.count()).toBe(15)
  for (const row of await rows.all()) expect((await row.boundingBox())!.height).toBeGreaterThanOrEqual(28)
  await page.screenshot({ path: '../scratch/chat-voice-layout.png' })
})

test('contextual title returned by backend updates the sidebar', async ({ page }) => {
  await setup(page, true)
  await expect(page.locator('.ws-sidebar').getByRole('button', { name: 'Organização da semana', exact: true })).toBeVisible()
})

test('voice settings save both rates and a configurable hold key', async ({ page }) => {
  await setup(page)
  await page.evaluate(() => window.dispatchEvent(new Event('jarvis:open-settings')))
  await page.getByRole('button', { name: 'Voz e microfone', exact: true }).click()
  await page.getByLabel('Velocidade padrão de fala').fill('1.5')
  await page.getByLabel('Velocidade ao segurar a tecla').fill('2.25')
  const key = page.getByRole('button', { name: 'Tecla de velocidade: ControlRight' })
  await key.click()
  await page.keyboard.press('ShiftRight')
  await expect(page.getByRole('button', { name: 'Tecla de velocidade: ShiftRight' })).toBeVisible()
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('jarvis-voice-speed')!))).toEqual({ normal: 1.5, held: 2.25, key: 'ShiftRight' })
  await page.screenshot({ path: '../scratch/chat-voice-settings.png' })
})

test('voice speed persists, applies while held and restores on keyup and blur', async ({ page }) => {
  await setup(page)
  await page.locator('.ws-message.user').click()
  await page.evaluate(async () => {
    // @ts-ignore Vite serves this module in the browser test.
    const voice = await import('/src/utils/voiceSpeed.ts')
    voice.saveVoiceSpeed({ normal: 1.25, held: 2.5, key: 'ControlRight' })
    const buffer = new ArrayBuffer(44 + 8000 * 2 * 30)
    const view = new DataView(buffer)
    const text = (offset: number, value: string) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))
    text(0, 'RIFF'); view.setUint32(4, buffer.byteLength - 8, true); text(8, 'WAVEfmt ')
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
    view.setUint32(24, 8000, true); view.setUint32(28, 16000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
    text(36, 'data'); view.setUint32(40, buffer.byteLength - 44, true)
    const audio = voice.createAgentAudio(URL.createObjectURL(new Blob([buffer], { type: 'audio/wav' })))
    await audio.play()
    ;(window as any).speedAudio = audio
  })
  const speed = () => page.evaluate(() => (window as any).speedAudio.playbackRate)
  expect(await speed()).toBe(1.25)
  await page.keyboard.down('ControlRight')
  expect(await speed()).toBe(2.5)
  await page.keyboard.up('ControlRight')
  expect(await speed()).toBe(1.25)
  await page.keyboard.down('ControlRight')
  await page.evaluate(() => window.dispatchEvent(new Event('blur')))
  expect(await speed()).toBe(1.25)
  await page.keyboard.up('ControlRight')
  await page.reload()
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('jarvis-voice-speed')!))).toEqual({ normal: 1.25, held: 2.5, key: 'ControlRight' })
})

async function setup(page: Page, automaticTitle = false) {
  await page.addInitScript(() => {
    localStorage.setItem('jarvis-react-session', 'session-test')
    class FakeSocket {
      static OPEN = 1
      readyState = 1
      onmessage: ((e: { data: string }) => void) | null = null
      onopen: (() => void) | null = null
      constructor(url: string) { if (url.includes('/ws/chat')) (window as any).chatSocket = this; setTimeout(() => this.onopen?.(), 0) }
      send(raw: string) { (window as any).lastRequest = JSON.parse(raw) }
      close() {}
      addEventListener() {}
    }
    window.WebSocket = FakeSocket as any
  })
  let history = structuredClone(initial)
  let active = false
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    let data: any = { ok: true }
    if (url.pathname === '/api/app-lock') data = { ok: true, configured: true, enabled: false, unlocked: true }
    if (url.pathname === '/api/settings/ai') data = { ok: true, routes: {} }
    if (url.pathname === '/api/sessions') data = { sessions: [{ id: 'session-test', title: automaticTitle ? 'Nova conversa' : 'Teste de conversa', type: 'chat' }, ...Array.from({ length: 14 }, (_, i) => ({ id: `old-${i}`, title: `Planejamento de treinos e finanças da semana ${i}`, type: 'chat' }))] }
    else if (url.pathname.endsWith('/auto-title')) data = { ok: true, session: { id: 'session-test', title: 'Organização da semana' } }
    else if (url.pathname === '/api/settings/mic') data = { ok: true, sensitivity: 75, silence_ms: 800, gain: 1, engine: 'auto', device_name: '' }
    else if (url.pathname.endsWith('/history')) {
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON()
        history = body.truncate_to !== undefined ? history.slice(0, body.truncate_to) : body.history
      }
      data = { ok: true, history }
    } else if (url.pathname === '/api/runs') data = { ok: true, runs: active && url.searchParams.get('status') === 'running' ? [{ id: 'run-test', session_id: 'session-test', status: 'running' }] : [] }
    else if (url.pathname === '/api/mission-control') data = { ok: true, components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] }
    else if (url.pathname === '/api/approvals') data = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
    else if (url.pathname === '/api/planning') data = { ok: true, workspace: { content: '', is_open: false }, preferences: {} }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.goto('/')
  await expect(page.getByText('Mensagem original', { exact: true })).toBeVisible()
  return { history: () => history, active: (value: boolean) => { active = value } }
}

async function emit(page: Page, event: object, requestId?: string) {
  await page.evaluate(({ event, requestId }) => {
    const win = window as any
    win.chatSocket.onmessage({ data: JSON.stringify({ session_id: 'session-test', ...event, request_id: requestId || win.lastRequest?.request_id }) })
  }, { event, requestId })
}

test('next message waits for the preceding transcript save', async ({ page }) => {
  await setup(page)
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  let saving = false
  await page.route('**/api/sessions/session-test/history', async route => {
    if (route.request().method() !== 'POST') return route.fallback()
    saving = true
    await gate
    return route.fallback()
  })
  const input = page.getByLabel('Mensagem para o agente')
  await input.fill('Primeiro pedido'); await input.press('Enter')
  await emit(page, { type: 'complete', summary: 'Primeira resposta', context: {} })
  await expect.poll(() => saving).toBe(true)
  await input.fill('Segundo pedido'); await input.press('Enter')
  expect(await page.evaluate(() => (window as any).lastRequest.message)).toBe('Primeiro pedido')
  release()
  await expect.poll(() => page.evaluate(() => (window as any).lastRequest.message)).toBe('Segundo pedido')
})

test('text transcript keeps shared voice exchanges when continuing as owner', async ({ page }) => {
  const state = await setup(page)
  const before = structuredClone(state.history())
  const input = page.getByLabel('Mensagem para o agente')
  await input.fill('Uma pergunta do visitante'); await input.press('Enter')
  await emit(page, { type: 'complete', summary: 'Resposta pública', context: { identity_restricted: true, access_mode: 'public' } })
  await expect(page.getByText('Resposta pública', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Parar pedido', exact: true })).toHaveCount(0)
  expect(state.history()).toEqual(before)
  await input.fill('Agora um pedido autorizado'); await input.press('Enter')
  await emit(page, { type: 'complete', summary: 'Resposta autorizada', context: {} })
  await expect(page.getByText('Resposta autorizada', { exact: true })).toBeVisible()
  await expect.poll(() => state.history().at(-1)?.content).toBe('Resposta autorizada')
  expect(state.history().map(item => item.content)).toEqual([...before.map(item => item.content), 'Uma pergunta do visitante', 'Resposta pública', 'Agora um pedido autorizado', 'Resposta autorizada'])
  const publicMessage = page.locator('.ws-message.user').filter({ hasText: 'Uma pergunta do visitante' })
  await publicMessage.hover()
  await publicMessage.getByRole('button', { name: 'Editar mensagem' }).click()
  await expect(input).toHaveValue('Uma pergunta do visitante')
  expect(state.history()).toEqual(before)
})

test('standby stops visual polling and resumes immediately while active requests remain monitored', async ({ page }) => {
  const state = await setup(page)
  await page.clock.install()
  const requests: string[] = []
  page.on('request', request => { const path = new URL(request.url()).pathname; if (path.startsWith('/api/')) requests.push(path) })
  const setStandby = (value: boolean) => page.evaluate(value => { (window as any).__jarvisStandby = value; window.dispatchEvent(new Event('jarvis:visibility')) }, value)
  await setStandby(true)
  await page.clock.runFor(1000)
  requests.length = 0
  await page.clock.runFor(30000)
  const visual = ['/api/bridge', '/api/wake-word', '/api/metrics', '/api/logs', '/api/mission-control', '/api/planning', '/api/approvals', '/api/runs']
  expect(requests.filter(path => visual.includes(path))).toEqual([])
  // Reabrir pela bandeja no WinForms pode emitir foco sem repetir o evento Shown.
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect.poll(() => requests.includes('/api/mission-control')).toBe(true)
  await expect.poll(() => requests.includes('/api/planning')).toBe(true)
  expect(requests).not.toContain('/api/metrics')
  state.active(true)
  await page.getByLabel('Mensagem para o agente').fill('Pedido em andamento')
  await page.getByLabel('Mensagem para o agente').press('Enter')
  await expect(page.getByRole('button', { name: 'Parar pedido', exact: true })).toBeVisible()
  await setStandby(true)
  requests.length = 0
  await page.clock.runFor(5000)
  expect(requests).toContain('/api/runs')
  expect(requests).not.toContain('/api/mission-control')
  await emit(page, { type: 'complete', summary: 'Concluído em segundo plano', context: {} })
  await setStandby(false)
  await expect(page.getByText('Concluído em segundo plano', { exact: true })).toBeVisible()
})

test('editing cuts history, hover exposes time, failed send restores draft and ignores late reply', async ({ page }) => {
  const state = await setup(page)
  await expect(page.getByRole('button', { name: 'Parar pedido', exact: true })).toHaveCount(0)
  const original = page.locator('.ws-message.user').first()
  await original.hover()
  await expect(original.locator('.ws-message-actions')).toHaveCSS('opacity', '1')
  await expect(original.locator('.ws-message-actions time')).toBeVisible()
  await expect(original.getByRole('button', { name: 'Copiar mensagem' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ver execução' })).toHaveCount(0)
  await expect(page.getByLabel('Opções da mensagem')).toHaveCount(0)
  await original.getByRole('button', { name: 'Editar mensagem' }).click()
  const input = page.getByLabel('Mensagem para o agente')
  await expect(input).toHaveValue('Mensagem original')
  await expect(page.locator('.ws-message')).toHaveCount(0)
  expect(state.history()).toEqual([])
  await input.fill('Mensagem revisada')
  await input.press('Enter')
  await expect(page.locator('.ws-message.user')).toContainText('Mensagem revisada')
  const oldRequest = await page.evaluate(() => (window as any).lastRequest.request_id)
  await input.fill('Rascunho novo')
  await emit(page, { type: 'error', message: 'Erro de conexão com a API' })
  await expect(input).toHaveValue('Mensagem revisada\nRascunho novo')
  await expect(page.locator('.ws-message.user')).toHaveCount(0)
  await emit(page, { type: 'complete', summary: 'Resposta atrasada' }, oldRequest)
  await expect(page.getByText('Resposta atrasada', { exact: true })).toHaveCount(0)
  await input.fill('Enviar de novo')
  await input.press('Enter')
  await emit(page, { type: 'complete', summary: 'Resposta correta', context: {} })
  await expect(page.getByText('Resposta correta', { exact: true })).toBeVisible()
  expect(state.history().map(m => m.content)).toEqual(['Enviar de novo', 'Resposta correta'])
})

test('real tool events, intentional memory, minimal thinking and stop lifecycle', async ({ page }) => {
  const state = await setup(page)
  const input = page.getByLabel('Mensagem para o agente')
  await page.getByLabel('Modo de conversa').selectOption('general')
  await input.fill('Pesquise o assunto')
  state.active(true)
  await input.press('Enter')
  await expect(page.locator('.ws-response-pending')).toBeVisible()
  await expect(page.locator('.ws-response-pending > span')).toHaveCount(3)
  await expect(page.locator('.ws-response-pending > span').first()).toHaveCSS('animation-name', 'ws-response-bounce')
  const dotsMove = await page.locator('.ws-response-pending > span').first().evaluate(dot => { const animation = dot.getAnimations()[0]; animation.pause(); animation.currentTime = 0; const before = getComputedStyle(dot).transform; animation.currentTime = 360; const after = getComputedStyle(dot).transform; animation.play(); return before !== after })
  expect(dotsMove).toBe(true)
  await expect(page.locator('.ws-thinking')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Parar pedido', exact: true })).toBeVisible()
  const entry = { id: 'tool-1', tool: 'web_search', status: 'running', label: 'Pesquisar Roblox.com', sources: [] as any[] }
  await emit(page, { type: 'tool_activity', run_id: 'run-test', activity: entry })
  await expect(page.locator('.ws-tool-activity summary')).toContainText('Pesquisando na web')
  const done = { ...entry, status: 'succeeded', sources: [{ url: 'https://example.org/fonte', title: 'Fonte consultada', read: true }, { url: 'https://example.org/link', title: 'Só encontrado', read: false }] }
  await emit(page, { type: 'tool_activity', run_id: 'run-test', activity: done })
  state.active(false)
  await emit(page, { type: 'complete', summary: 'Pesquisa concluída', context: { run_id: 'run-test', tool_activity: [done], situational_context: { text: 'Água: 500ml', sources: [{ key: 'water', label: 'Água' }] } } })
  await expect(page.getByText('Pesquisa concluída', { exact: true })).toBeVisible()
  await page.locator('.ws-message.assistant').last().hover()
  await expect(page.getByRole('button', { name: 'Ver execução' })).toBeVisible()
  await expect(page.getByText(/Contexto usado/)).toHaveCount(0)
  const activity = page.locator('.ws-message .ws-tool-activity')
  await expect(activity.locator('summary')).toContainText('Usou 1 ferramenta')
  await expect(activity.locator('li').first()).not.toBeVisible()
  expect(await activity.evaluate(el => !!el.previousElementSibling?.classList.contains('ws-message-content'))).toBe(true)
  await expect(activity.locator('summary')).toContainText('Acessou 1 página')
  await activity.locator('summary').click()
  await expect(activity).toContainText('Pesquisar Roblox.com')
  await expect(activity.getByRole('link', { name: 'Fonte consultada' })).toHaveAttribute('href', 'https://example.org/fonte')
  await expect(page.getByRole('button', { name: 'Parar pedido', exact: true })).toHaveCount(0)
  await page.getByLabel('Modo de conversa').selectOption('thinking')
  await input.fill('Busque minha memória')
  await input.press('Enter')
  await expect(page.locator('.ws-thinking')).toHaveText('Pensando…')
  await emit(page, { type: 'complete', summary: 'Memória consultada', context: { memory_lookup: { tool: 'vault_search', summary: 'Uma nota', items: [{ title: 'Nota', text: 'Meu plano' }] } } })
  await expect(page.getByText(/Contexto usado/)).toBeVisible()
  await page.screenshot({ path: 'test-results/chat-experience-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel('Mensagem para o agente')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/chat-experience-mobile.png', fullPage: true })
  await page.reload()
  await expect(page.getByText(/Contexto usado/)).toBeVisible()
})

test('restores login on reload and retains credentials on network failure', async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('lifeos_api_settings')) localStorage.setItem('lifeos_api_settings', JSON.stringify({ userEmail: 'test@example.org', supabaseUrl: 'https://auth.example.test', supabasePublishableKey: 'test-public', supabaseAccessToken: 'expired', supabaseRefreshToken: 'refresh-test', supabaseExpiresAt: 1 }))
  })
  let fail = true, refreshes = 0
  await page.route('https://auth.example.test/**', async route => {
    if (!route.request().url().includes('/auth/')) { await route.fulfill({ json: [] }); return }
    refreshes++
    await route.fulfill({ status: fail ? 503 : 200, contentType: 'application/json', body: JSON.stringify(fail ? {} : { access_token: 'renewed', refresh_token: 'rotated', expires_in: 3600 }) })
  })
  await setup(page)
  await expect(page.locator('.ws-cloud-warning')).toBeVisible()
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('lifeos_api_settings')!).supabaseRefreshToken)).toBe('refresh-test')
  fail = false
  await page.reload()
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('lifeos_api_settings')!).supabaseAccessToken)).toBe('renewed')
  await expect(page.locator('.ws-cloud-warning')).toHaveCount(0)
  const count = refreshes
  await page.reload()
  await expect(page.getByText('Mensagem original', { exact: true })).toBeVisible()
  expect(refreshes).toBe(count)
  await page.evaluate(async () => { const path = '/src/utils/evoluteCloud.ts'; const auth = await import(path); auth.signOutEvoluteCloud() })
  await page.reload()
  await expect(page.getByText('Mensagem original', { exact: true })).toBeVisible()
  expect(refreshes).toBe(count)
  await expect(page.locator('.ws-cloud-warning')).toHaveCount(0)
})

test('logout during token refresh never restores the old account', async ({ page }) => {
  await setup(page)
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  let calls = 0
  await page.route('https://auth.example.test/**', async route => {
    calls++
    await pending
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ access_token: 'late-access', refresh_token: 'late-refresh' }) })
  })
  await page.evaluate(async () => {
    const path = '/src/utils/evoluteCloud.ts'
    const auth = await import(path)
    auth.saveEvoluteSettings({ userEmail: 'test@example.org', supabaseUrl: 'https://auth.example.test', supabasePublishableKey: 'public-test', supabaseAccessToken: 'old', supabaseRefreshToken: 'refresh', supabaseExpiresAt: 1 })
    ;(window as any).refreshTest = Promise.allSettled([auth.refreshAccessToken(), auth.refreshAccessToken()])
  })
  await expect.poll(() => calls).toBe(1)
  await page.evaluate(async () => { const path = '/src/utils/evoluteCloud.ts'; (await import(path)).signOutEvoluteCloud() })
  release()
  await page.evaluate(() => (window as any).refreshTest)
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('lifeos_api_settings')!).supabaseAccessToken)).toBe('')
  await expect(page.locator('.ws-cloud-warning')).toHaveCount(0)
})

test('mode model choices persist independently and can inherit the standard chat route', async ({ page }) => {
  await setup(page)
  const choice = { provider: 'groq', model: 'chat-model' }
  let saved: any = { chat: choice }
  const modes = ['chat', 'voice', 'thinking', 'planning', 'research', 'coder', 'browser', 'react', 'lifeos', 'tutor', 'swarm']
  await page.route('**/api/settings/ai', async route => {
    if (route.request().method() === 'POST') saved = route.request().postDataJSON().routes
    const routes = Object.fromEntries(modes.map(mode => [mode, { primary: saved[mode]?.provider ? saved[mode] : saved.chat, effective: saved[mode]?.provider ? saved[mode] : saved.chat, inherited: mode !== 'chat' && !saved[mode]?.provider }]))
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true, routes }) })
  })
  await page.evaluate(() => window.dispatchEvent(new Event('jarvis:open-settings')))
  await page.getByRole('button', { name: 'Provedores e rotas', exact: true }).click()
  await page.getByLabel('Provedor de Thinking').selectOption('gemini')
  await page.getByLabel('Modelo de Thinking').fill('thinking-model')
  await page.getByLabel('Provedor de Voz padrão').selectOption('groq')
  await page.getByLabel('Modelo de Voz padrão').fill('voice-model')
  await page.getByRole('button', { name: 'Salvar modelos por modo' }).click()
  await expect(page.getByText('Modelos salvos. Serão usados nos próximos pedidos.')).toBeVisible()
  expect(saved.thinking).toEqual({ provider: 'gemini', model: 'thinking-model' })
  expect(saved.voice).toEqual({ provider: 'groq', model: 'voice-model' })
  expect(saved.chat).toEqual(choice)
  expect(saved.research).toEqual({ inherit: true })
  await page.getByLabel('Provedor de Thinking').selectOption('')
  await page.getByRole('button', { name: 'Salvar modelos por modo' }).click()
  await expect(page.getByLabel('Modelo de Thinking')).toBeDisabled()
  await expect.poll(() => saved.thinking).toEqual({ inherit: true })
})


test('plus groups attachments and tools and dismisses on outside click, escape and selection', async ({ page }) => {
  await setup(page)
  const plus = page.getByRole('button', { name: 'Adicionar arquivo ou ferramenta' })
  const popup = page.getByRole('group', { name: 'Arquivos e ferramentas' })
  await expect(popup).toHaveCount(0)
  await plus.click()
  await expect(popup.getByRole('button')).toHaveCount(3)
  await expect(popup.getByRole('button', { name: 'Analisar tela' })).toBeVisible()
  await expect(popup.getByRole('button', { name: 'Cinema', exact: true })).toBeVisible()
  await page.getByLabel('Mensagem para o agente').click()
  await expect(popup).toHaveCount(0)
  await plus.click()
  await page.keyboard.press('Escape')
  await expect(popup).toHaveCount(0)
  await expect(plus).toBeFocused()
  await plus.click()
  const chooserPromise = page.waitForEvent('filechooser')
  await popup.getByRole('button', { name: 'Adicionar arquivo' }).click()
  const chooser = await chooserPromise
  await expect(popup).toHaveCount(0)
  await chooser.setFiles({ name: 'test.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a+9sAAAAASUVORK5CYII=', 'base64') })
  await expect(page.getByAltText('Imagem anexada')).toBeVisible()
  await plus.click()
  await popup.getByRole('button', { name: 'Cinema', exact: true }).click()
  await expect(popup).toHaveCount(0)
})


test('new chat stays local until the first message', async ({ page }) => {
  await setup(page)
  let creates = 0
  await page.route('**/api/sessions', async route => {
    if (route.request().method() !== 'POST') return route.fallback()
    creates++
    await route.fulfill({ json: { id: 'created-on-send', session: { id: 'created-on-send', title: 'Nova conversa', type: 'chat' } } })
  })
  await page.getByLabel('Mensagem para o agente').fill('Rascunho antigo')
  const newChat = page.locator('.ws-sidebar').getByRole('button', { name: 'Nova conversa', exact: true })
  await newChat.click(); await newChat.click(); await newChat.click()
  expect(creates).toBe(0)
  await expect(page.locator('.ws-sidebar .ws-chat-row')).toHaveCount(15)
  await expect(page.locator('.ws-message')).toHaveCount(0)
  await page.locator('.ws-sidebar').getByRole('button', { name: 'Teste de conversa', exact: true }).click()
  await expect(page.getByLabel('Mensagem para o agente')).toHaveValue('Rascunho antigo')
  await newChat.click()
  await page.getByLabel('Mensagem para o agente').fill('Primeira mensagem')
  await page.getByLabel('Mensagem para o agente').press('Enter')
  await expect.poll(() => creates).toBe(1)
  await expect(page.locator('.ws-message.user')).toContainText('Primeira mensagem')
})

test('dragging divider saves only on release', async ({ page }) => {
  await setup(page)
  await page.evaluate(() => {
    const original = Storage.prototype.setItem
    ;(window as any).resizeWrites = 0
    Storage.prototype.setItem = function(key, value) { if (key === 'jarvis-nav-height') (window as any).resizeWrites++; original.call(this, key, value) }
  })
  const divider = page.locator('.ws-sidebar [role="separator"]')
  const rect = (await divider.boundingBox())!
  await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2)
  await page.mouse.down()
  await page.mouse.move(rect.x + rect.width / 2, rect.y - 80, { steps: 30 })
  expect(await page.evaluate(() => (window as any).resizeWrites)).toBe(0)
  await page.mouse.up()
  await expect.poll(() => page.evaluate(() => (window as any).resizeWrites)).toBe(1)
  expect(Number(await divider.getAttribute('aria-valuenow'))).toBeLessThan(250)
})

test('key fields add remove and sync complete rotation', async ({ page }) => {
  await setup(page)
  let keys: Record<string, string> = {}
  let cloud: any
  await page.route('**/api/settings/keys', async route => {
    if (route.request().method() === 'POST') keys = route.request().postDataJSON().keys
    await route.fulfill({ json: { ok: true, keys } })
  })
  await page.route('**/api/settings/sync-snapshot', route => route.fulfill({ json: { ok: true, snapshot: { settings: { 'api_keys.groq': { v: keys.groq, ts: Date.now() } } } } }))
  await page.route('https://cloud.example.test/**', async route => {
    if (route.request().method() === 'POST') { cloud = route.request().postDataJSON(); await route.fulfill({ json: { revision: 1 } }) }
    else await route.fulfill({ json: [] })
  })
  await page.evaluate(() => {
    localStorage.setItem('lifeos_api_settings', JSON.stringify({ supabaseUrl: 'https://cloud.example.test', supabasePublishableKey: 'fake', supabaseAccessToken: 'fake', supabaseExpiresAt: Date.now() + 3600000 }))
    window.dispatchEvent(new Event('jarvis:open-settings'))
  })
  await page.getByRole('button', { name: 'Provedores e rotas', exact: true }).click()
  await page.getByLabel('groq — chave 1', { exact: true }).fill('fake-first')
  await page.getByRole('button', { name: 'Adicionar chave de groq', exact: true }).click()
  await page.getByLabel('groq — chave 2', { exact: true }).fill('fake-second')
  await page.getByRole('button', { name: 'Adicionar chave de groq', exact: true }).click()
  await page.getByRole('button', { name: 'Remover chave 3 de groq', exact: true }).click()
  await page.getByRole('button', { name: 'Salvar Chaves', exact: true }).click()
  await expect.poll(() => keys.groq).toBe('fake-first,fake-second')
  await expect.poll(() => JSON.stringify(cloud)).toContain('fake-first,fake-second')
  const first = page.getByLabel('groq — chave 1', { exact: true })
  await expect(first).toHaveAttribute('type', 'password')
  await page.getByRole('button', { name: 'Mostrar chaves de groq', exact: true }).click()
  await expect(first).toHaveAttribute('type', 'text')
  await expect(first).toHaveValue('fake-first')
  await page.getByRole('button', { name: 'Ocultar chaves de groq', exact: true }).click()
  await expect(first).toHaveAttribute('type', 'password')
  for (let i = 0; i < 7; i++) await page.getByRole('button', { name: 'Adicionar chave de groq', exact: true }).click()
  const list = page.getByRole('group', { name: 'Chaves de groq', exact: true })
  await expect.poll(() => list.evaluate(el => el.scrollTop)).toBeGreaterThan(0)
  expect(await list.evaluate(el => el.scrollHeight > el.clientHeight && el.clientHeight <= 180)).toBe(true)
  await expect(page.getByLabel('groq — chave 9', { exact: true })).toBeInViewport()

})


test('repeated enter sends one chat request and never posts HTTP alongside websocket', async ({ page }) => {
  await setup(page)
  let httpSends = 0
  await page.route('**/api/chat', async route => { httpSends++; await route.fulfill({ json: { ok: true } }) })
  await page.evaluate(() => {
    const win = window as any
    win.sentChats = []
    const original = win.chatSocket.send.bind(win.chatSocket)
    win.chatSocket.send = (raw: string) => { win.sentChats.push(JSON.parse(raw)); original(raw) }
  })
  const input = page.getByLabel('Mensagem para o agente')
  await input.fill('Pedido único')
  await input.press('Enter')
  await input.press('Enter')
  await input.press('Enter')
  await expect(page.locator('.ws-message.user').last()).toContainText('Pedido único')
  expect(await page.evaluate(() => (window as any).sentChats.length)).toBe(1)
  expect(httpSends).toBe(0)
  await emit(page, { type: 'complete', summary: 'Uma resposta', context: {} })
  await expect(page.getByText('Uma resposta', { exact: true })).toBeVisible()
})


for (const eventType of ['error', 'complete']) {
  test(`quota details survive ${eventType} events and restore the draft`, async ({ page }) => {
    await setup(page)
    const input = page.getByLabel('Mensagem para o agente')
    await input.fill('Organize minha semana')
    await input.press('Enter')
    const message = 'Groq: cota diária de tokens (429). 4 de 4 chaves em espera. Próxima tentativa em cerca de 605 segundos. As chaves continuam configuradas.'
    await emit(page, eventType === 'error' ? { type: 'error', message } : { type: 'complete', summary: message, context: {} })
    await expect(page.locator('.ws-error')).toHaveText(new RegExp('cota diária.*605 segundos'))
    await expect(input).toHaveValue('Organize minha semana')
    await expect(page.getByText('Não foi possível obter resposta do Jarvis. Verifique a conexão e tente novamente.', { exact: true })).toHaveCount(0)
  })
}


test('completed action with quota warning is not turned into a failed retry', async ({ page }) => {
  await setup(page)
  const input = page.getByLabel('Mensagem para o agente')
  await input.fill('Registre a nota')
  await input.press('Enter')
  const summary = 'Resultado de notes: Nota registrada.\n\nNão consegui redigir a síntese, os resultados acima foram preservados, sem repetir as ações. Groq: cota diária de tokens (429). 1 de 4 chaves em espera. Próxima tentativa em cerca de 605 segundos.'
  await emit(page, { type: 'complete', summary, context: {} })
  await expect(page.locator('.ws-message.assistant').last()).toContainText('Nota registrada.')
  await expect(page.locator('.ws-error')).toHaveCount(0)
  await expect(input).toHaveValue('')
})


test('autoaprovação move chats selecionados para a lixeira e permite desfazer', async ({ page }) => {
  await setup(page)
  const sidebar = page.locator('.ws-sidebar')
  const calls: string[][] = []
  await page.route('**/api/approvals', route => route.fulfill({ json: { ok: true, mode: { enabled: true }, categories: { bulk: true }, rules: [] } }))
  await page.route('**/api/chat-history/*', route => {
    const { ids } = route.request().postDataJSON()
    calls.push(ids)
    return route.fulfill({ json: { ok: true, ids } })
  })
  await sidebar.getByRole('button', { name: 'Selecionar', exact: true }).click()
  await sidebar.getByRole('checkbox').nth(1).check()
  await sidebar.getByRole('checkbox').nth(2).check()
  await sidebar.getByRole('button', { name: 'Excluir (2)' }).click()
  await expect(sidebar.locator('.ws-chat-row')).toHaveCount(13)
  await sidebar.getByRole('button', { name: 'Desfazer' }).click()
  await expect(sidebar.locator('.ws-chat-row')).toHaveCount(15)
  expect(calls).toEqual([['old-0', 'old-1'], ['old-0', 'old-1']])
})
