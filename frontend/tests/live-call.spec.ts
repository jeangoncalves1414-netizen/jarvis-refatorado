import { test, expect, type Page } from '@playwright/test'

async function setup(page: Page, engine = 'browser') {
  const requests: { path: string; body: any }[] = []
  const events: any[] = []
  const control = { sttDelay: 0, sttGate: null as Promise<void> | null, text: 'conte uma curiosidade', streamStatus: 200, streamEvent: null as any, streamEvents: null as any[] | null }
  await page.addInitScript(() => {
    const state = { level: 0, starts: 0, stops: 0, tracksStopped: 0, contextsClosed: 0, suspended: 0, recognizers: 0, plays: 0, pauses: 0, holdAudio: false }
    ;(window as any).voiceTest = state
    Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia: async () => ({ getTracks: () => [{ stop: () => state.tracksStopped++ }] }) } })
    class Recorder {
      static isTypeSupported() { return true }
      state = 'inactive'; mimeType = 'audio/webm'; ondataavailable: any; onstop: any
      start() { this.state = 'recording'; state.starts++ }
      stop() { if (this.state !== 'recording') return; this.state = 'inactive'; state.stops++; queueMicrotask(() => { this.ondataavailable?.({ data: new Blob(['a'.repeat(1200)]) }); this.onstop?.() }) }
    }
    ;(window as any).MediaRecorder = Recorder
    ;(window as any).AudioContext = class {
      state = 'running'
      createAnalyser() { return { fftSize: 1024, getByteTimeDomainData(data: Uint8Array) { data.fill(128 + state.level) } } }
      createMediaStreamSource() { return { connect() {} } }
      async close() { this.state = 'closed'; state.contextsClosed++ }
      async suspend() { this.state = 'suspended'; state.suspended++ }
    }
    ;(window as any).SpeechRecognition = class { start() { state.recognizers++ }; abort() {}; stop() {} }
    HTMLMediaElement.prototype.play = async function () {
      state.plays++; Object.defineProperty(this, 'paused', { configurable: true, value: false })
      this.dispatchEvent(new Event('playing'))
      if (!state.holdAudio) setTimeout(() => { Object.defineProperty(this, 'paused', { configurable: true, value: true }); this.dispatchEvent(new Event('ended')) }, 50)
    }
    HTMLMediaElement.prototype.pause = function () { state.pauses++; Object.defineProperty(this, 'paused', { configurable: true, value: true }) }
  })
  await page.route('**/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    const raw = request.postData()
    let body: any = raw
    try { body = raw ? JSON.parse(raw) : null } catch { /* audio */ }
    requests.push({ path, body })
    let data: any = { ok: true }
    if (path === '/api/settings/mic') data = { engine, sensitivity: 75, gain: 1, silence_ms: 800 }
    if (path === '/api/voice/capture/status') data = { available: true }
    if (path === '/api/voice/capture/start') data = { ok: true, seq: 0, threshold: 100 }
    if (path === '/api/voice/capture/events') {
      await new Promise(resolve => setTimeout(resolve, 100))
      data = { active: true, seq: 1, events: events.splice(0) }
    }
    if (path === '/api/voice/stt') {
      if (control.sttGate) await control.sttGate
      if (control.sttDelay) await new Promise(resolve => setTimeout(resolve, control.sttDelay))
      data = { ok: true, text: control.text }
    }
    if (path === '/api/chat/stream') {
      const replies = control.streamEvents || [control.streamEvent || { status: 'complete', plan: { summary: 'Aqui está a resposta.', intent: 'general' } }]
      await route.fulfill({ status: control.streamStatus, contentType: 'text/event-stream', body: replies.map(reply => `data: ${JSON.stringify(reply)}\n\n`).join('') }); return
    }
    if (path === '/api/voice/tts/stream') { await route.fulfill({ status: 503 }); return }
    if (path === '/api/voice/tts') {
      const wav = Buffer.alloc(32044)
      wav.write('RIFF', 0); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8)
      wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22)
      wav.writeUInt32LE(16000, 24); wav.writeUInt32LE(32000, 28); wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34)
      wav.write('data', 36); wav.writeUInt32LE(32000, 40)
      await route.fulfill({ contentType: 'audio/wav', body: wav }); return
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.goto('/tests/live-call.html', { waitUntil: 'domcontentloaded' })
  await page.getByText('Abrir chamada', { exact: true }).click()
  await expect(page.getByTestId('diagnostics')).toContainText(engine === 'browser' ? 'fallback-vad' : 'backend-sr')
  const chats = () => requests.filter(r => r.path === '/api/chat/stream')
  return { requests, events, control, chats }
}

async function level(page: Page, value: number) { await page.evaluate(value => { (window as any).voiceTest.level = value }, value) }
async function ptt(page: Page) {
  await page.getByTitle('Alternar entre modo contínuo e segurar para falar').click()
  await expect(page.getByTestId('diagnostics')).toContainText('fallback-vad')
}

test('announces actual tools before completion and keeps receipts outside the reply', async ({ page }) => {
  const app = await setup(page, 'auto')
  await page.evaluate(() => {
    const original = window.fetch.bind(window)
    window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) !== '/api/chat/stream') return original(input, init)
      const stream = new ReadableStream<Uint8Array>({ start(controller) {
        ;(window as any).pushChatEvent = (event: unknown) => controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`))
        ;(window as any).finishChatStream = () => controller.close()
      } })
      return Promise.resolve(new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } }))
    }) as typeof fetch
  })
  app.events.push({ type: 'transcript', turn_id: 'spoken', text: 'Abra o Roblox', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => !!(window as any).pushChatEvent)).toBe(true)
  const entry = { id: 'open-1', tool: 'web_search', status: 'running', label: 'Abrir roblox.com', speech: 'Abrindo Roblox.', sources: [] }
  const push = (data: unknown) => page.evaluate(data => (window as any).pushChatEvent(data), data)
  await push({ status: 'progress', phase: 'tool_activity', run_id: 'voice-run', activity: entry })
  await expect.poll(() => app.requests.filter(r => r.path === '/api/voice/tts').map(r => r.body.text)).toContain('Abrindo Roblox.')
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.plays)).toBe(1)
  await push({ status: 'progress', phase: 'tool_activity', run_id: 'voice-run', activity: { ...entry, detail: 'Verificando janela' } })
  const done = { ...entry, status: 'succeeded', result: 'Confirmado por janela roblox.com - Opera' }
  await push({ status: 'progress', phase: 'tool_activity', run_id: 'voice-run', activity: done })
  await push({ status: 'complete', plan: { intent: 'agent_loop', summary: 'Abri Roblox.', context: { run_id: 'voice-run', tool_activity: [done] } } })
  await page.evaluate(() => (window as any).finishChatStream())
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.receipt.run_id)).toBe('voice-run')
  const exchange = await page.evaluate(() => (window as any).savedExchange)
  expect(exchange.reply).toBe('Abri Roblox.')
  expect(exchange.receipt.activity).toEqual([done])
  expect(app.requests.filter(r => r.path === '/api/voice/tts' && r.body.text === 'Abrindo Roblox.')).toHaveLength(1)
  const activity = page.locator('.ws-tool-activity')
  await expect(activity.locator('summary')).toHaveText('Usou 1 ferramenta')
  await expect(activity.locator('li')).not.toBeVisible()
  await activity.locator('summary').click()
  await expect(activity).toContainText('Abrir roblox.com')
  await expect(activity).toContainText('Confirmado por janela')
})

test('completed tools do not play stale announcements and plain replies have no tool block', async ({ page }) => {
  const app = await setup(page, 'auto')
  const entry = { id: 'fast', tool: 'web_search', label: 'Abrir youtube.com', speech: 'Abrindo YouTube.', status: 'running' }
  app.control.streamEvents = [
    { status: 'progress', phase: 'tool_activity', activity: entry },
    { status: 'progress', phase: 'tool_activity', activity: { ...entry, status: 'succeeded' } },
    { status: 'complete', plan: { summary: 'Abri YouTube.', intent: 'general' } },
  ]
  app.events.push({ type: 'transcript', turn_id: 'fast-turn', text: 'Abra o YouTube', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.reply)).toBe('Abri YouTube.')
  expect(await page.evaluate(() => (window as any).voiceTest.plays)).toBe(1)
  app.control.streamEvents = null
  app.events.push({ type: 'transcript', turn_id: 'hello', text: 'Olá tudo bem', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.reply)).toBe('Aqui está a resposta.')
  expect(await page.evaluate(() => (window as any).savedExchange.receipt.activity)).toEqual([])
  await expect(page.locator('.ws-tool-activity')).toHaveCount(1)
})

test('VAD envia uma fala normal uma vez e mantém a origem voice', async ({ page }) => {
  const app = await setup(page)
  await level(page, 20)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await level(page, 0)
  await expect.poll(() => app.chats().length).toBe(1)
  expect(app.chats()[0].body.origin).toBe('voice')
  await expect(page.getByText('Aqui está a resposta.', { exact: false })).toBeVisible()
  await expect(page.getByTestId('orb')).toHaveText('listening')
})

test('PTT suporta silêncio longo e só envia ao soltar', async ({ page }) => {
  const app = await setup(page)
  await ptt(page)
  await page.keyboard.down('Space')
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await page.waitForTimeout(2100) // supera o buffer de silêncio de 1,8 s
  expect(app.chats()).toHaveLength(0)
  expect(await page.evaluate(() => (window as any).voiceTest.stops)).toBe(0)
  await page.keyboard.up('Space')
  await expect.poll(() => app.chats().length).toBe(1)
})

test('perder o foco solta o PTT e keyup não duplica a fala', async ({ page }) => {
  const app = await setup(page)
  await ptt(page)
  await page.keyboard.down('Space')
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await page.evaluate(() => window.dispatchEvent(new Event('blur')))
  await page.keyboard.up('Space')
  await expect.poll(() => app.chats().length).toBe(1)
  expect(await page.evaluate(() => (window as any).voiceTest.stops)).toBe(1)
})

test('espaço em campo de texto não grava nem envia', async ({ page }) => {
  const app = await setup(page)
  await ptt(page)
  await page.getByLabel('Campo de texto').focus()
  await page.keyboard.press('Space')
  expect(app.chats()).toHaveLength(0)
  expect(await page.evaluate(() => (window as any).voiceTest.starts)).toBe(0)
})

test('fechar durante STT descarta a resposta tardia e libera o mic', async ({ page }) => {
  const app = await setup(page)
  let release!: () => void
  app.control.sttGate = new Promise<void>(resolve => { release = resolve })
  await ptt(page)
  await page.keyboard.down('Space')
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await page.keyboard.up('Space')
  await expect.poll(() => app.requests.filter(r => r.path === '/api/voice/stt').length).toBe(1)
  await page.getByRole('button', { name: 'Encerrar', exact: true }).click()
  release()
  await page.waitForTimeout(650)
  expect(app.chats()).toHaveLength(0)
  expect(await page.evaluate(() => (window as any).voiceTest.tracksStopped)).toBeGreaterThan(0)
})

test('cancelar não suspende o microfone e permite a próxima fala', async ({ page }) => {
  const app = await setup(page)
  await page.getByRole('button', { name: 'Cancelar pedido' }).click()
  await expect(page.getByTestId('orb')).toHaveText('listening')
  expect(await page.evaluate(() => (window as any).voiceTest.suspended)).toBe(0)
  expect(await page.evaluate(() => (window as any).voiceTest.recognizers)).toBe(0)
  await level(page, 20)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await level(page, 0)
  await expect.poll(() => app.chats().length).toBe(1)
})

test('captura do PC despacha fala e não inicia outro reconhecedor', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.events.push({ type: 'transcript', text: 'Olá pelo PC', turn_id: 'pc-1' })
  await expect.poll(() => app.chats().length).toBe(1)
  await expect(page.getByTestId('orb')).toHaveText('listening')
  expect(await page.evaluate(() => (window as any).voiceTest.recognizers)).toBe(0)
  expect(await page.evaluate(() => (window as any).voiceTest.starts)).toBe(0)
})

test('trocar PC para PTT encerra a captura antiga e aceita STT lento', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.control.sttDelay = 2800
  await ptt(page)
  await expect.poll(() => app.requests.filter(r => r.path === '/api/voice/capture/stop').length).toBe(1)
  await page.keyboard.down('Space')
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await page.keyboard.up('Space')
  await expect.poll(() => app.chats().length, { timeout: 5000 }).toBe(1)
})

test('barge-in para o áudio do PC antes de processar a nova fala', async ({ page }) => {
  const app = await setup(page, 'auto')
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = true })
  app.events.push({ type: 'transcript', text: 'Fale bastante', turn_id: 'pc-1' })
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.plays)).toBeGreaterThan(0)
  app.events.push({ type: 'barge_in' })
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.pauses)).toBeGreaterThan(0)
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = false })
  app.events.push({ type: 'transcript', text: 'Agora outra pergunta', turn_id: 'pc-2' })
  await expect.poll(() => app.chats().length).toBe(2)
})

for (const status of ['error', 'complete']) {
  test(`erro técnico fica na tela e não é falado (${status})`, async ({ page }) => {
    const app = await setup(page, 'auto')
    const diagnostic = "'BrowserAgent' object has no attribute 'navigate'"
    app.control.streamEvent = status === 'error'
      ? { status, error: diagnostic }
      : { status, plan: { intent: 'tool_execution', summary: diagnostic, context: { speech_summary: 'Não consegui concluir o pedido. Os detalhes estão na tela.' } } }
    app.events.push({ type: 'transcript', text: 'Abra o YouTube', turn_id: 'error-1' })
    await expect.poll(() => app.requests.filter(r => r.path === '/api/voice/tts').length).toBeGreaterThan(0)
    const spoken = app.requests.filter(r => r.path.startsWith('/api/voice/tts')).map(r => r.body.text).join(' ')
    expect(spoken).toContain('Não consegui concluir')
    expect(spoken).not.toContain('BrowserAgent')
    await expect(page.getByText(diagnostic, { exact: false }).first()).toBeVisible()
    await expect(page.getByTestId('orb')).toHaveText('listening')
  })
}

test('PC acumula frase incompleta e espera a transcrição da continuação', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.events.push({ type: 'transcript', text: 'Olá quero que você abra', turn_id: 'part-1' })
  await expect(page.getByText('Olá quero que você abra', { exact: false }).first()).toBeVisible()
  await page.waitForTimeout(2000)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'state', state: 'speaking' })
  await page.waitForTimeout(2800)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'state', state: 'listening' }, { type: 'transcript', text: 'o YouTube e depois abra o Spotify', turn_id: 'part-2' })
  await expect.poll(() => app.chats().length).toBe(1)
  expect(app.chats()[0].body.message).toBe('Olá quero que você abra o YouTube e depois abra o Spotify')
})

test('encerrar descarta a frase pendente sem enviar pedido', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.events.push({ type: 'transcript', text: 'Quero que você abra', turn_id: 'pending-1' })
  await expect(page.getByText('Quero que você abra', { exact: false }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Encerrar', exact: true }).click()
  await page.waitForTimeout(4700)
  expect(app.chats()).toHaveLength(0)
})

test('VAD mantém a gravação durante pausa de dois segundos no meio do pedido', async ({ page }) => {
  const app = await setup(page)
  app.control.text = 'Abra o roblox.com no navegador e depois de 10 segundos abra o Spotify'
  await level(page, 20)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await level(page, 0)
  await page.waitForTimeout(2100)
  expect(await page.evaluate(() => (window as any).voiceTest.stops)).toBe(0)
  expect(app.chats()).toHaveLength(0)
  await level(page, 20)
  await page.waitForTimeout(250)
  await level(page, 0)
  await expect.poll(() => app.chats().length, { timeout: 7000 }).toBe(1)
  expect(app.chats()[0].body.message).toBe(app.control.text)
  expect(await page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
})

test('PC aguarda continuação mesmo depois de uma primeira frase completa', async ({ page }) => {
  const app = await setup(page, 'auto')
  expect(app.requests.find(r => r.path === '/api/voice/capture/start')?.body.silence_ms).toBe(3000)
  app.events.push({ type: 'transcript', text: 'Abra o roblox.com no navegador', turn_id: 'first' })
  await expect(page.getByText('Abra o roblox.com no navegador', { exact: false }).first()).toBeVisible()
  await page.waitForTimeout(2100)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'state', state: 'speaking' })
  await page.waitForTimeout(3200)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'processing', turn_id: 'second' }, { type: 'state', state: 'listening' })
  await page.waitForTimeout(3200)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'transcript', text: 'e depois de 10 segundos abra o Spotify', turn_id: 'second' })
  await expect.poll(() => app.chats().length).toBe(1)
  expect(app.chats()[0].body.message).toBe('Abra o roblox.com no navegador e depois de 10 segundos abra o Spotify')
})

test('PC preserva a ordem quando as transcrições terminam invertidas', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.events.push({ type: 'processing', turn_id: 'first' }, { type: 'processing', turn_id: 'second' },
    { type: 'transcript', turn_id: 'second', text: 'e depois abra o Spotify' })
  await page.waitForTimeout(3300)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'transcript', turn_id: 'first', text: 'Abra o Roblox' })
  await expect.poll(() => app.chats().length).toBe(1)
  expect(app.chats()[0].body.message).toBe('Abra o Roblox e depois abra o Spotify')
})

for (const diagnostic of [false, true]) {
  test(`resposta fragmentada filtra links e diagnóstico antes do TTS (${diagnostic})`, async ({ page }) => {
    const app = await setup(page, 'auto')
    const raw = diagnostic
      ? "AttributeError: 'BrowserAgent' object has no attribute 'navigate'"
      : 'Pedido de abertura enviado ao navegador: https://www.roblox.com Confirmado: abri roblox (navegador opera.exe, janela "roblox.com/pt/home - Opera").'
    app.control.streamEvents = [
      ...raw.split(/(?<=[.:])/).map(chunk => ({ status: 'streaming', chunk })),
      { status: 'complete', plan: { intent: 'general', summary: raw } },
    ]
    app.events.push({ type: 'transcript', text: 'Abra Roblox', turn_id: 'speak' })
    await expect.poll(() => app.requests.filter(r => r.path === '/api/voice/tts').length).toBeGreaterThan(0)
    const spoken = app.requests.filter(r => r.path.startsWith('/api/voice/tts')).map(r => r.body.text).join(' ')
    expect(spoken).not.toMatch(/https|www|\.com|opera|\.exe|janela|AttributeError|BrowserAgent|navigate/i)
    expect(spoken).toContain(diagnostic ? 'Não consegui concluir' : 'abri roblox')
    await expect(page.getByText(raw, { exact: false }).first()).toBeVisible()
  })
}

test('detector neural conserva segmentos durante pausa longa e só envia no fim do turno', async ({ page }) => {
  const app = await setup(page, 'auto')
  expect(app.requests.find(r => r.path === '/api/voice/capture/start')?.body.semantic_turns).toBe(true)
  app.events.push({ type: 'transcript', text: 'Abra Roblox', turn_id: 'segment', semantic: true, turn_complete: false },
    { type: 'state', state: 'listening' })
  await page.waitForTimeout(8500)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'transcript', text: 'e depois de dez segundos abra Spotify', turn_id: 'final', semantic: true, turn_complete: true })
  await expect.poll(() => app.chats().length, { timeout: 2000 }).toBe(1)
  expect(app.chats()[0].body.message).toBe('Abra Roblox e depois de dez segundos abra Spotify')
})

test('fim de turno sem novo texto libera segmentos já transcritos', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.events.push({ type: 'processing', turn_id: 'segment' }, { type: 'turn_end' },
    { type: 'transcript', text: 'Explique o assunto', turn_id: 'segment', semantic: true, turn_complete: false })
  await expect.poll(() => app.chats().length, { timeout: 2000 }).toBe(1)
})

test('interrupção cancela a execução exata e preserva o pedido para o complemento', async ({ page }) => {
  const app = await setup(page, 'auto')
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = true })
  app.control.streamEvents = [
    { status: 'progress', phase: 'started', run_id: 'run_voice_test' },
    { status: 'complete', plan: { summary: 'Uma explicação muito longa que ainda não foi ouvida por completo.' } },
  ]
  app.events.push({ type: 'transcript', text: 'Explique o Roblox', turn_id: 'first', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.plays)).toBeGreaterThan(0)
  app.events.push({ type: 'barge_in' }, { type: 'state', state: 'speaking' })
  await expect.poll(() => app.requests.filter(r => r.path === '/api/runs/run_voice_test/cancel').length).toBe(1)
  await page.waitForTimeout(3500)
  expect(app.chats()).toHaveLength(1)
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = false })
  app.control.streamEvents = null
  app.events.push({ type: 'state', state: 'listening' }, { type: 'transcript', text: 'mas somente a parte de criar jogos', turn_id: 'second', semantic: true, turn_complete: true })
  await expect.poll(() => app.chats().length).toBe(2)
  expect(app.chats()[1].body.message).toContain('Pedido anterior: Explique o Roblox')
  expect(app.chats()[1].body.message).toContain('mas somente a parte de criar jogos')
  expect(app.chats()[1].body.message).not.toContain('Uma explicação muito longa')
})
