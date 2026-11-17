import { test, expect, type Page } from '@playwright/test'

async function setup(page: Page, engine = 'browser', microphone = '') {
  const requests: { path: string; body: any }[] = []
  const events: any[] = []
  const control = { sttDelay: 0, sttGate: null as Promise<void> | null, text: 'conte uma curiosidade', streamStatus: 200, streamEvent: null as any, streamEvents: null as any[] | null }
  await page.addInitScript(() => {
    const state = { level: 0, starts: 0, stops: 0, tracksStopped: 0, contextsClosed: 0, suspended: 0, recognizers: 0, plays: 0, pauses: 0, holdAudio: false, constraints: [] as any[], audios: [] as HTMLMediaElement[] }
    ;(window as any).voiceTest = state
    Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia: async (constraints: any) => { state.constraints.push(constraints); return { getTracks: () => [{ stop: () => state.tracksStopped++ }] } } } })
    class Recorder {
      constructor(public stream: MediaStream) {}
      static isTypeSupported() { return true }
      state = 'inactive'; mimeType = 'audio/webm'; ondataavailable: any; onstop: any
      start() { this.state = 'recording'; state.starts++ }
      stop() { if (this.state !== 'recording') return; this.state = 'inactive'; state.stops++; queueMicrotask(() => { this.ondataavailable?.({ data: new Blob(['a'.repeat(1200)]) }); this.onstop?.() }) }
    }
    ;(window as any).MediaRecorder = Recorder
    ;(window as any).AudioContext = class {
      state = 'running'
      createAnalyser() { return { fftSize: 1024, getByteTimeDomainData(data: Uint8Array) { data.fill(128 + state.level) } } }
      createMediaStreamSource() { return { connect() {}, disconnect() {} } }
      createScriptProcessor() {
        let timer: ReturnType<typeof setInterval>
        return { onaudioprocess: null as any, connect() { timer = setInterval(() => this.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array(16000) } }), 100) }, disconnect() { clearInterval(timer) } }
      }
      async resume() {}
      async close() { this.state = 'closed'; state.contextsClosed++ }
      async suspend() { this.state = 'suspended'; state.suspended++ }
    }
    ;(window as any).SpeechRecognition = class { start() { state.recognizers++ }; abort() {}; stop() {} }
    window.speechSynthesis.speak = utterance => { setTimeout(() => utterance.onend?.(new Event('end') as SpeechSynthesisEvent), 0) }
    window.speechSynthesis.cancel = () => undefined
    HTMLMediaElement.prototype.play = async function () {
      state.audios.push(this)
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
    if (path === '/api/sessions') data = { ok: true, id: 'e2e-session', sessions: [{ id: 'e2e-session', title: 'Chamada', type: 'chat' }] }
    if (path.endsWith('/history')) data = { ok: true, history: [] }
    if (path === '/api/settings/mic') data = { ok: true, engine, sensitivity: 75, gain: 1, silence_ms: 800, device_id: microphone, device_name: microphone ? 'USB microphone' : '' }
    if (path === '/api/voice/capture/status') data = { available: true }
    if (path === '/api/voice/capture/start') data = { ok: true, seq: 0, threshold: 100 }
    if (path === '/api/identity' && body?.action === 'enrollment_authorize') data = { ok: true, ticket: 'test-ticket', phrase: 'Eu autorizo o Jarvis a reconhecer minha voz durante nossas conversas.' }
    if (path === '/api/identity/reading') data = { ok: true, text: 'Eu autorizo o' }
    if (path === '/api/identity' && body?.action === 'live_enroll') data = { ok: true, profile: { name: 'Ana' } }
    if (path === '/api/voice/identity/model' || (path === '/api/identity' && body?.action === 'face_model_status')) data = { ok: true, ready: true }
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

async function holdChatStream(page: Page) {
  await page.evaluate(() => {
    const original = window.fetch.bind(window)
    window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) !== '/api/chat/stream') return original(input, init)
      return Promise.resolve(new Response(new ReadableStream<Uint8Array>({ start(controller) {
        const held = { push: (event: unknown) => controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`)), finish: () => controller.close(), body: JSON.parse(String(init?.body)) }
        ;((window as any).heldChatStreams ||= []).push(held)
        ;(window as any).pushChatEvent = held.push
        ;(window as any).finishChatStream = held.finish
      } }), { headers: { 'Content-Type': 'text/event-stream' } }))
    }) as typeof fetch
  })
  return (data: unknown) => page.evaluate(data => (window as any).pushChatEvent(data), data)
}

test('voice chat updates the same exchange on each chunk before completion or audio ends', async ({ page }) => {
  const app = await setup(page, 'auto')
  const push = await holdChatStream(page)
  const rows = async () => JSON.parse(await page.getByTestId('chat-messages').innerText())
  app.events.push({ type: 'transcript', text: 'Conte uma história', turn_id: 'incremental', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => !!(window as any).pushChatEvent)).toBe(true)
  await expect.poll(async () => (await rows()).map((row: any) => row.content)).toEqual(['Conte uma história'])
  for (const [chunk, expected] of [['Era uma', 'Era uma'], [' vez uma estrela.', 'Era uma vez uma estrela.']]) {
    await push({ status: 'streaming', chunk })
    await expect.poll(async () => (await rows()).map((row: any) => row.content)).toEqual(['Conte uma história', expected])
    await expect(page.locator('.live-call-card')).toContainText(expected)
  }
  expect(app.requests.filter(r => r.path.endsWith('/history') && r.body?.history)).toHaveLength(0)
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = true })
  await push({ status: 'complete', plan: { summary: 'Era uma vez uma estrela brilhante.', context: { run_id: 'incremental-run' } } })
  await page.evaluate(() => (window as any).finishChatStream())
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.plays)).toBeGreaterThan(0)
  await expect.poll(async () => (await rows())[1]?.content).toBe('Era uma vez uma estrela brilhante.')
  expect(await page.evaluate(() => (window as any).savedExchange)).toBeUndefined()
  await page.evaluate(() => (window as any).voiceTest.audios.forEach((audio: HTMLMediaElement) => audio.dispatchEvent(new Event('ended'))))
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.receipt.run_id)).toBe('incremental-run')
  await expect.poll(async () => (await rows()).length).toBe(2)
  expect(app.requests.filter(r => r.path.endsWith('/history') && r.body?.history)).toHaveLength(1)
})

test('cancelled voice preview is removed and late chunks cannot restore it', async ({ page }) => {
  const app = await setup(page, 'auto')
  const push = await holdChatStream(page)
  app.events.push({ type: 'transcript', text: 'Conte uma história', turn_id: 'cancel-preview', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => !!(window as any).pushChatEvent)).toBe(true)
  await push({ status: 'streaming', chunk: 'Uma resposta parcial' })
  await expect(page.getByTestId('chat-messages')).toContainText('Uma resposta parcial')
  await page.getByRole('button', { name: 'Encerrar', exact: true }).click()
  await expect(page.getByTestId('chat-messages')).toHaveText('[]')
  await push({ status: 'complete', plan: { summary: 'Resposta atrasada' } })
  await page.evaluate(() => (window as any).finishChatStream())
  await expect(page.getByTestId('chat-messages')).toHaveText('[]')
  expect(app.requests.filter(r => r.path.endsWith('/history') && r.body?.history)).toHaveLength(0)
})

test('paused voice request keeps its bubble across repeated continuations and late old streams', async ({ page }) => {
  const app = await setup(page, 'auto')
  await holdChatStream(page)
  const rows = async () => JSON.parse(await page.getByTestId('chat-messages').innerText())
  const push = (index: number, data: unknown) => page.evaluate(({ index, data }) => (window as any).heldChatStreams[index].push(data), { index, data })
  const finish = (index: number) => page.evaluate(index => (window as any).heldChatStreams[index].finish(), index)
  app.events.push({ type: 'transcript', text: 'Explique o Roblox', turn_id: 'original', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => (window as any).heldChatStreams?.length)).toBe(1)
  const timestamp = (await rows())[0].timestamp
  await page.locator('.live-call-subtitles p').first().evaluate(element => { (window as any).originalVoiceBubble = element })
  await push(0, { status: 'streaming', chunk: 'Uma primeira resposta' })
  for (const [index, text] of ['mas somente sobre criar jogos', 'e com exemplos simples'].entries()) {
    app.events.push({ type: 'state', state: 'speaking' })
    await expect(page.getByTestId('orb')).toHaveText('listening')
    await expect.poll(async () => (await rows()).length).toBe(1)
    expect((await rows())[0].timestamp).toBe(timestamp)
    expect(await page.evaluate(() => (window as any).originalVoiceBubble.isConnected)).toBe(true)
    app.events.push({ type: 'state', state: 'listening' }, { type: 'transcript', text, turn_id: `continue-${index}`, semantic: true, turn_complete: true })
    await expect.poll(() => page.evaluate(() => (window as any).heldChatStreams.length)).toBe(index + 2)
    await push(index + 1, { status: 'streaming', chunk: `Resposta nova ${index}` })
    await push(index, { status: 'complete', plan: { summary: 'Resposta antiga atrasada' } })
    await finish(index)
    await expect.poll(async () => (await rows())[1]?.content).toBe(`Resposta nova ${index}`)
    expect((await rows())[0].timestamp).toBe(timestamp)
    expect(await page.evaluate(() => (window as any).originalVoiceBubble.isConnected)).toBe(true)
  }
  const combined = 'Explique o Roblox mas somente sobre criar jogos e com exemplos simples'
  await expect.poll(async () => (await rows())[0].content).toBe(combined)
  expect(await page.evaluate(() => (window as any).heldChatStreams[2].body.message)).toContain('Pedido anterior: Explique o Roblox mas somente sobre criar jogos')
  await push(2, { status: 'complete', plan: { summary: 'Resposta final combinada.', context: { run_id: 'continued-run' } } })
  await finish(2)
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.user)).toBe(combined)
  await expect.poll(async () => (await rows()).map((row: any) => row.content)).toEqual([combined, 'Resposta final combinada.'])
  expect(app.requests.filter(r => r.path.endsWith('/history') && r.body?.history)).toHaveLength(1)
  expect(await page.evaluate(() => (window as any).originalVoiceBubble.isConnected)).toBe(true)
  app.events.push({ type: 'transcript', text: 'Agora conte uma curiosidade', turn_id: 'new-turn', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => (window as any).heldChatStreams.length)).toBe(4)
  await expect.poll(async () => (await rows())[2]?.content).toBe('Agora conte uma curiosidade')
  await page.getByRole('button', { name: 'Encerrar', exact: true }).click()
  await finish(3)
})

for (const ending of ['close', 'cancel']) {
  test(`pending voice continuation is discarded on ${ending}`, async ({ page }) => {
    const app = await setup(page, 'auto')
    const push = await holdChatStream(page)
    app.events.push({ type: 'transcript', text: 'Explique o Roblox', turn_id: 'pending', semantic: true, turn_complete: true })
    await expect.poll(() => page.evaluate(() => !!(window as any).pushChatEvent)).toBe(true)
    await push({ status: 'streaming', chunk: 'Resposta parcial' })
    app.events.push({ type: 'state', state: 'speaking' })
    await expect(page.getByTestId('orb')).toHaveText('listening')
    await expect(page.getByTestId('chat-messages')).toContainText('Explique o Roblox')
    await page.getByRole('button', { name: ending === 'close' ? 'Encerrar' : 'Cancelar pedido', exact: true }).click()
    await expect(page.getByTestId('chat-messages')).toHaveText('[]')
    await push({ status: 'complete', plan: { summary: 'Não deve reaparecer' } })
    await page.evaluate(() => (window as any).finishChatStream())
    await expect(page.getByTestId('chat-messages')).toHaveText('[]')
  })
}

test('browser microphone continuation keeps the same request bubble while recording', async ({ page }) => {
  const app = await setup(page)
  app.control.text = 'Explique o Roblox'
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = true })
  await level(page, 20)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await level(page, 0)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.plays)).toBeGreaterThan(0)
  const rows = async () => JSON.parse(await page.getByTestId('chat-messages').innerText())
  const timestamp = (await rows())[0].timestamp
  app.control.text = 'mas apenas a criação de jogos'
  await level(page, 30)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(2)
  expect((await rows())[0].timestamp).toBe(timestamp)
  expect((await rows())[0].content).toBe('Explique o Roblox')
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = false })
  await level(page, 0)
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.user)).toBe('Explique o Roblox mas apenas a criação de jogos')
  await expect.poll(async () => (await rows()).length).toBe(2)
  expect(app.chats()).toHaveLength(2)
})

test('switching chats hides the voice preview and rejects the late final exchange', async ({ page }) => {
  const app = await setup(page, 'auto')
  const push = await holdChatStream(page)
  app.events.push({ type: 'transcript', text: 'Conte uma história', turn_id: 'switch-preview', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => !!(window as any).pushChatEvent)).toBe(true)
  await push({ status: 'streaming', chunk: 'Primeiro trecho' })
  await expect(page.getByTestId('chat-messages')).toContainText('Primeiro trecho')
  await page.getByRole('button', { name: 'Nova conversa de teste' }).click()
  await push({ status: 'streaming', chunk: ' da conversa anterior' })
  await expect(page.getByTestId('chat-messages')).toHaveText('[]')
  await push({ status: 'complete', plan: { summary: 'Resposta anterior' } })
  await page.evaluate(() => (window as any).finishChatStream())
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.reply)).toBe('Resposta anterior')
  await expect(page.getByTestId('chat-messages')).toHaveText('[]')
  expect(app.requests.filter(r => r.path.endsWith('/history') && r.body?.history)).toHaveLength(0)
})

test('voice call opens the globally selected microphone', async ({ page }) => {
  await setup(page, 'browser', 'usb')
  expect(await page.evaluate(() => (window as any).voiceTest.constraints[0].audio.deviceId)).toEqual({ exact: 'usb' })
  await page.getByRole('button', { name: 'Encerrar', exact: true }).click()
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.tracksStopped)).toBeGreaterThan(0)
})

test('paired Android call transcribes and plays a reply with identification disabled', async ({ page }) => {
  await page.route('**/tests/live-call.html', async route => {
    const response = await route.fetch()
    await route.fulfill({ response, body: (await response.text()).replace('<head>', '<head><meta name="jarvis-paired-android">') })
  })
  await page.addInitScript(() => localStorage.setItem('jarvis_speaker_identification', '1'))
  const app = await setup(page)
  await expect(page.getByRole('button', { name: 'Ligar câmera de identificação' })).toHaveCount(0)
  const transcription = page.waitForRequest(request => request.url().endsWith('/api/voice/stt'))
  await level(page, 20)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await level(page, 0)
  expect((await transcription).headers()['x-jarvis-identify-speaker']).toBe('0')
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.plays)).toBeGreaterThan(0)
  expect(app.requests.some(request => request.path === '/api/identity')).toBe(false)
  await page.getByRole('button', { name: 'Encerrar', exact: true }).click()
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.tracksStopped)).toBeGreaterThan(0)
})

test('public voice reply carries its privacy flag to chat persistence', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.control.streamEvent = { status: 'complete', plan: { summary: 'Vamos conversar.', intent: 'general', context: { access_mode: 'public', identity_restricted: true } } }
  app.events.push({ seq: 1, text: 'Olá Jarvis', type: 'transcript' })
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.receipt?.meta?.access_mode)).toBe('public')
  expect(await page.evaluate(() => (window as any).savedExchange?.reply)).toBe('Vamos conversar.')
  expect(app.requests.filter(r => r.path.endsWith('/history') && r.body?.history)).toHaveLength(0)
})

test('buffered speakers send their own evidence together without borrowing the last identity', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('jarvis_speaker_identification', '1'))
  const app = await setup(page, 'auto')
  let merged: any
  await page.route('**/api/identity', route => {
    const body = route.request().postDataJSON()
    if (body.action !== 'merge_turns') return route.fallback()
    merged = body
    return route.fulfill({ json: { ok: true, evidence_token: 'group-proof' } })
  })
  app.events.push(
    { type: 'processing', turn_id: 'jean' }, { type: 'processing', turn_id: 'ana' },
    { type: 'transcript', turn_id: 'jean', text: 'Olá Jarvis', semantic: true, turn_complete: false,
      speaker: { matched: true, profile: { name: 'Jean' }, evidence_token: 'jean-proof' } },
    { type: 'transcript', turn_id: 'ana', text: 'quem falou com você?', semantic: true, turn_complete: true,
      speaker: { matched: true, profile: { name: 'Ana' }, evidence_token: 'ana-proof' } },
  )
  await expect.poll(() => app.chats().length).toBe(1)
  expect(merged.tokens).toEqual(['jean-proof', 'ana-proof'])
  expect(app.chats()[0].body.identity_token).toBe('group-proof')
  expect(app.chats()[0].body.message).toBe('Olá Jarvis quem falou com você?')
})

test('spoken camera request waits for the observation and narrates it without ordinary chat', async ({ page }) => {
  const app = await setup(page, 'auto')
  await page.evaluate(() => {
    window.addEventListener('jarvis-request-camera', event => {
      event.preventDefault()
      setTimeout(() => (event as CustomEvent).detail.resolve('Câmera 1: vejo Jean. Câmera 2: não detectei pessoas.'), 100)
    })
  })
  app.events.push({ type: 'transcript', turn_id: 'camera', text: 'Quem você vê na câmera?', semantic: true, turn_complete: true })
  await expect.poll(() => app.requests.some(r => r.path === '/api/voice/tts' && r.body.text.includes('Câmera 1: vejo Jean'))).toBe(true)
  await expect(page.getByText(/Câmera 1: vejo Jean\. Câmera 2: não detectei pessoas\./)).toBeVisible()
  await expect(page.getByTestId('orb')).toHaveText('listening')
  expect(app.chats()).toHaveLength(0)
})

test('closing the call while a camera is being analyzed prevents late narration', async ({ page }) => {
  const app = await setup(page, 'auto')
  await page.evaluate(() => {
    window.addEventListener('jarvis-request-camera', event => {
      event.preventDefault()
      ;(window as any).cameraReply = (event as CustomEvent).detail.resolve
    })
  })
  app.events.push({ type: 'transcript', turn_id: 'camera-close', text: 'Quem você vê na câmera?', semantic: true, turn_complete: true })
  await expect.poll(() => page.evaluate(() => Boolean((window as any).cameraReply))).toBe(true)
  await page.getByRole('button', { name: 'Encerrar', exact: true }).click()
  await page.evaluate(() => (window as any).cameraReply('Uma resposta que chegou depois do encerramento.'))
  await page.waitForTimeout(200)
  expect(app.requests.some(r => r.path === '/api/voice/tts')).toBe(false)
  expect(app.chats()).toHaveLength(0)
})

test('pedido falado de recadastro administrativo abre senha sem enviar ao chat', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.events.push({ type: 'transcript', turn_id: 'admin-intro', text: 'Olá Jarvis sou Jean, pode me registrar como admin?', semantic: true, turn_complete: true })
  const panel = page.getByRole('dialog', { name: 'Refazer cadastro de administrador' })
  await expect(panel.getByLabel('Senha administrativa')).toBeVisible()
  await expect(panel.getByLabel('Senha administrativa')).toHaveAttribute('type', 'password')
  expect(app.chats()).toHaveLength(0)
  await panel.getByRole('button', { name: 'Cancelar cadastro' }).click()
  await expect(panel).toBeHidden()
  expect(app.requests.some(r => r.body?.action === 'live_enroll')).toBe(false)
})

test('apresentação durante a ligação cadastra a leitura e libera o próximo turno', async ({ page }) => {
  const app = await setup(page, 'auto')
  app.events.push({ type: 'transcript', turn_id: 'intro', text: 'Olá Jarvis, essa aqui é minha irmã Ana.', semantic: true, turn_complete: true })
  const panel = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
  await expect(panel.getByText('Conhecer Ana')).toBeVisible()
  expect(app.requests.some(r => r.body?.action === 'live_enroll')).toBe(false)
  await panel.getByRole('button', { name: 'Sim, pode cadastrar', exact: true }).click()
  await panel.getByRole('button', { name: 'Autorizar voz', exact: true }).click()
  const words = panel.locator('.enrollment-reading span')
  await expect(words.nth(2)).toHaveCSS('color', 'rgb(54, 230, 165)')
  await panel.getByRole('button', { name: 'Concluir leitura' }).click()
  await expect.poll(() => app.requests.some(r => r.body?.action === 'live_enroll')).toBe(true)
  const payload = app.requests.find(r => r.body?.action === 'enrollment_voice')?.body
  expect(payload.audio).toMatch(/^data:audio\/webm;base64,/)
  expect(app.requests.some(r => r.path === '/api/voice/capture/stop')).toBe(true)
  expect(app.chats()).toHaveLength(0)
  await expect(panel).toBeHidden()
  await expect.poll(() => app.requests.some(r => r.path === '/api/voice/capture/start' && r.body.identify_speakers)).toBe(true)
  app.events.push({ type: 'transcript', turn_id: 'next', text: 'Conte uma história', semantic: true, turn_complete: true })
  await expect.poll(() => app.chats().length).toBe(1)
})
async function ptt(page: Page) {
  await page.getByTitle('Alternar entre modo contínuo e segurar para falar').click()
  await expect(page.getByTestId('diagnostics')).toContainText('fallback-vad')
}

test('captura três posições automaticamente e orienta a leitura na chamada', async ({ page }) => {
  const app = await setup(page, 'auto')
  await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 320; canvas.height = 240
    const ctx = canvas.getContext('2d')!
    const timer = setInterval(() => ctx.fillRect(0, 0, 320, 240), 80)
    Object.defineProperty(navigator.mediaDevices, 'getUserMedia', { value: async () => canvas.captureStream(10) })
    Object.defineProperty(navigator.mediaDevices, 'enumerateDevices', { value: async () => [{ deviceId: 'usb1', kind: 'videoinput', label: 'USB' }] })
    window.addEventListener('pagehide', () => clearInterval(timer), { once: true })
    const guides: string[] = []
    ;(window as any).spokenGuides = guides
    window.speechSynthesis.speak = speech => { guides.push(speech.text); setTimeout(() => speech.onend?.(new Event('end') as SpeechSynthesisEvent), 0) }
  })
  const angles = [0, 0, .18, .16, -.19]
  await page.route('**/api/identity', route => {
    const body = route.request().postDataJSON()
    if (body.action !== 'enrollment_pose') return route.fallback()
    return route.fulfill({ json: { ok: true, count: 1, pose: body.purpose === 'camera_selection' ? 0 : angles.shift() ?? -.19 } })
  })
  await page.getByRole('button', { name: 'Ligar câmera de identificação' }).click()
  app.events.push({ type: 'transcript', turn_id: 'intro-camera', text: 'Essa aqui é minha irmã Ana.', semantic: true, turn_complete: true })
  const panel = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
  await panel.getByRole('button', { name: 'Sim, pode cadastrar', exact: true }).click()
  await panel.getByRole('button', { name: 'Autorizar os dois', exact: true }).click()
  await panel.getByRole('button', { name: 'Concluir leitura' }).click()
  await expect.poll(() => app.requests.some(r => r.body?.action === 'live_enroll'), { timeout: 15000 }).toBe(true)
  expect(app.requests.filter(r => r.path === '/api/voice/tts').map(r => r.body.text)).toEqual(expect.arrayContaining([
    'Olhe de frente para a câmera.', 'Vire levemente a cabeça para um lado.', 'Agora vire a cabeça para o lado oposto.'
  ]))
  expect(app.requests.find(r => r.body?.action === 'live_enroll')?.body.images).toHaveLength(3)
})

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
  await expect(page.locator('.live-call-card').getByText('Aqui está a resposta.', { exact: false })).toBeVisible()
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

for (const status of ['cancel_requested', 'cancelled', 'failed']) {
  test(`confirmação por voz usa o recibo de cancelamento: ${status}`, async ({ page }) => {
    const app = await setup(page, 'auto')
    await page.route('**/api/runs/run_cancel_test/cancel', route => route.fulfill({
      status: status === 'failed' ? 503 : 200, contentType: 'application/json',
      body: JSON.stringify({ ok: status !== 'failed', run: { id: 'run_cancel_test', status } }),
    }))
    await page.evaluate(() => { (window as any).voiceTest.holdAudio = true })
    app.control.streamEvents = [
      { status: 'progress', phase: 'started', run_id: 'run_cancel_test' },
      { status: 'complete', plan: { summary: 'Esta fala ainda está tocando.' } },
    ]
    app.events.push({ type: 'transcript', text: 'Explique esse assunto', turn_id: 'cancel', semantic: true, turn_complete: true })
    await expect.poll(() => page.evaluate(() => (window as any).voiceTest.plays)).toBeGreaterThan(0)
    await page.evaluate(() => { (window as any).voiceTest.holdAudio = false })
    await page.getByRole('button', { name: 'Cancelar pedido' }).click()
    const expected = status === 'cancel_requested' ? 'Cancelamento solicitado.'
      : status === 'cancelled' ? 'Pedido cancelado.' : 'Não consegui confirmar o cancelamento'
    await expect.poll(() => app.requests.filter(r => r.path === '/api/voice/tts').map(r => r.body.text).join('\n')).toContain(expected)
    expect(app.requests.filter(r => r.path === '/api/voice/tts').some(r => r.body.text.startsWith('Cancelado.'))).toBe(false)
    await expect(page.getByTestId('orb')).toHaveText('listening')
  })
}

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
  await page.waitForTimeout(1000)
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

test('VAD envia uma frase completa sem os antigos três segundos de espera', async ({ page }) => {
  const app = await setup(page)
  app.control.text = 'Abra o roblox.com no navegador e depois de 10 segundos abra o Spotify'
  await level(page, 20)
  await expect.poll(() => page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
  await level(page, 0)
  await expect.poll(() => app.chats().length, { timeout: 2500 }).toBe(1)
  expect(app.chats()[0].body.message).toBe(app.control.text)
  expect(await page.evaluate(() => (window as any).voiceTest.starts)).toBe(1)
})

test('PC aguarda continuação enquanto a fala ainda não terminou', async ({ page }) => {
  const app = await setup(page, 'auto')
  expect(app.requests.find(r => r.path === '/api/voice/capture/start')?.body.silence_ms).toBe(800)
  app.events.push({ type: 'transcript', text: 'Abra o roblox.com no navegador', turn_id: 'first', semantic: true, turn_complete: false })
  await expect(page.getByText('Abra o roblox.com no navegador', { exact: false }).first()).toBeVisible()
  await page.waitForTimeout(2100)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'state', state: 'speaking' })
  await page.waitForTimeout(3200)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'processing', turn_id: 'second' }, { type: 'state', state: 'listening' })
  await page.waitForTimeout(3200)
  expect(app.chats()).toHaveLength(0)
  app.events.push({ type: 'transcript', text: 'e depois de 10 segundos abra o Spotify', turn_id: 'second', semantic: true, turn_complete: true })
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
  await expect.poll(() => app.chats().length).toBe(1)
  expect(app.chats()[0].body.message).toBe('Explique o assunto')
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
  await expect(page.getByTestId('chat-messages')).toContainText('Explique o Roblox')
  await page.evaluate(() => { (window as any).voiceTest.holdAudio = false })
  app.control.streamEvents = null
  app.events.push({ type: 'state', state: 'listening' }, { type: 'transcript', text: 'mas somente a parte de criar jogos', turn_id: 'second', semantic: true, turn_complete: true })
  await expect.poll(() => app.chats().length).toBe(2)
  expect(app.chats()[1].body.message).toContain('Pedido anterior: Explique o Roblox')
  expect(app.chats()[1].body.message).toContain('mas somente a parte de criar jogos')
  expect(app.chats()[1].body.message).not.toContain('Uma explicação muito longa')
  await expect.poll(() => page.evaluate(() => (window as any).savedExchange?.user)).toBe('Explique o Roblox mas somente a parte de criar jogos')
})
