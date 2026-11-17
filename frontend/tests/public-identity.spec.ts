import { test, expect } from '@playwright/test'
import { findReadWords, MIN_READING_COVERAGE } from '../src/components/enrollmentReading'

test('anyone can request ordinary enrollment without an administrator password', async ({ page }) => {
  await localVoice(page)
  const actions: any[] = []
  await page.route('**/api/identity', route => {
    const body = route.request().postDataJSON(); actions.push(body)
    return route.fulfill({ json: { ok: true, ticket: 'public-ticket', phrase: 'Eu autorizo minha voz.', name: 'Jamille' } })
  })
  await page.goto('/tests/identity-page.html?enroll')
  await page.evaluate(async () => (await import('/src/components/LiveEnrollment.tsx')).handleLiveIntroduction('Olá Jarvis sou Jamille, quero me cadastrar'))
  const dialog = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
  await dialog.getByRole('button', { name: 'Autorizar voz', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Concluir leitura' })).toBeVisible()
  await expect(dialog.locator('input[type="password"]')).toHaveCount(0)
  expect(actions[0]).toMatchObject({ action: 'enrollment_authorize', purpose: 'user', name: 'Jamille', admin_password: '' })
  await dialog.getByRole('button', { name: 'Cancelar cadastro' }).click()
  await expect.poll(() => actions.some(a => a.action === 'enrollment_cancel')).toBe(true)
})

for (const kind of ['rosto', 'voz']) {
  test(`settings ${kind} button requests the password instead of remaining disabled`, async ({ page }) => {
    const actions: any[] = []
    await page.addInitScript(() => {
      ;(window as any).mediaRequests = 0
      Object.defineProperty(navigator, 'mediaDevices', { value: { enumerateDevices: async () => [], getUserMedia: async () => { (window as any).mediaRequests++; throw new Error('No hardware in test') } } })
    })
    await page.route('**/api/app-lock', route => {
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON(); actions.push(body)
        return route.fulfill({ status: body.password === 'unlock-password' ? 200 : 400, json: body.password === 'unlock-password' ? { ok: true } : { ok: false, error: 'Senha inválida.' } })
      }
      return route.fulfill({ json: { ok: true, configured: true, enabled: true, unlocked: true, face: false, voice: false } })
    })
    await page.goto('/tests/identity-page.html?settings')
    await page.getByRole('checkbox').check()
    const button = page.getByRole('button', { name: `Cadastrar ${kind}`, exact: true })
    await expect(button).toBeEnabled()
    await button.click()
    const dialog = page.getByRole('dialog', { name: 'Autorizar biometria' })
    expect(await page.evaluate(() => (window as any).mediaRequests)).toBe(0)
    await dialog.getByLabel('Senha de desbloqueio').fill('wrong')
    await dialog.getByRole('button', { name: 'Confirmar senha' }).click()
    await expect(dialog.getByRole('alert')).toHaveText('Senha inválida.')
    expect(await page.evaluate(() => (window as any).mediaRequests)).toBe(0)
    await dialog.getByLabel('Senha de desbloqueio').fill('unlock-password')
    await dialog.getByRole('button', { name: 'Confirmar senha' }).click()
    await expect(dialog).toBeHidden()
    expect(actions.map(a => a.action)).toEqual(['verify_password', 'verify_password'])
  })
}

test('removing unlock biometrics opens a password field and preserves them on cancellation', async ({ page }) => {
  const actions: any[] = []
  await page.route('**/api/app-lock', route => {
    if (route.request().method() === 'POST') actions.push(route.request().postDataJSON())
    return route.fulfill({ json: { ok: true, configured: true, enabled: true, unlocked: true, face: true, voice: true } })
  })
  await page.goto('/tests/identity-page.html?settings')
  await page.getByRole('button', { name: 'Remover biometrias' }).click()
  let dialog = page.getByRole('dialog', { name: 'Autorizar biometria' })
  await dialog.getByRole('button', { name: 'Cancelar' }).click()
  expect(actions).toEqual([])
  await page.getByRole('button', { name: 'Remover biometrias' }).click()
  dialog = page.getByRole('dialog', { name: 'Autorizar biometria' })
  await dialog.getByLabel('Senha de desbloqueio').fill('unlock-password')
  await dialog.getByRole('button', { name: 'Confirmar senha' }).click()
  await expect(dialog).toBeHidden()
  expect(actions).toHaveLength(1)
  expect(actions[0]).toMatchObject({ action: 'remove_biometrics', password: 'unlock-password' })
})


test('reading counts words out of order without multiplying repeated words', () => {
  expect(MIN_READING_COVERAGE).toBe(.8)
  expect(findReadWords('Eu autorizo o Jarvis a reconhecer minha voz', 'VOZ minha reconhecer a o autorizo eu')).toEqual([0, 1, 2, 4, 5, 6, 7])
  expect(findReadWords('Referência VOZ Jarvis voz', 'jarvis referencia voz')).toEqual([0, 1, 2])
  expect(findReadWords('um dois três quatro cinco', 'cinco três quatro dois')).toHaveLength(4)
  expect(findReadWords('um dois três quatro cinco', 'um um um um um')).toEqual([0])
})

async function localVoice(page: import('@playwright/test').Page) {
  await page.route('**/api/voice/identity/model', route => route.fulfill({ json: { ok: true, ready: true } }))
  await page.route('**/api/voice/tts', route => route.fulfill({ status: 503, json: { ok: false } }))
  await page.addInitScript(() => {
    const state = { processors: [] as any[], stopped: 0, closed: 0, starts: 0, constraints: [] as any[] }
    ;(window as any).localVoice = state
    window.speechSynthesis.speak = utterance => { setTimeout(() => utterance.onend?.(new Event('end') as SpeechSynthesisEvent), 0) }
    window.speechSynthesis.cancel = () => undefined
    Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia: async (constraints: MediaStreamConstraints) => { state.constraints.push(constraints); return { getTracks: () => [{ stop: () => state.stopped++ }] } } } })
    ;(window as any).MediaRecorder = class {
      state = 'inactive'; mimeType = 'audio/webm'; onstop: any; ondataavailable: any
      constructor(public stream: MediaStream) {}
      start() { this.state = 'recording'; state.starts++ }
      stop() { if (this.state !== 'recording') return; this.state = 'inactive'; queueMicrotask(() => { this.ondataavailable?.({ data: new Blob(['sample']) }); this.onstop?.() }) }
    }
    ;(window as any).AudioContext = class {
      state = 'running'; destination = {}
      createMediaStreamSource() { return { connect() {}, disconnect() {} } }
      createScriptProcessor() {
        const processor = { active: true, onaudioprocess: null as any, connect() {}, disconnect() { this.active = false } }
        state.processors.push(processor)
        return processor
      }
      async resume() {}
      async close() { this.state = 'closed'; state.closed++ }
    }
  })
}

async function say(page: import('@playwright/test').Page) {
  await expect.poll(() => page.evaluate(() => (window as any).localVoice.processors.filter((p: any) => p.active).length)).toBe(1)
  await page.evaluate(() => {
    const processor = (window as any).localVoice.processors.find((p: any) => p.active)
    for (const amplitude of [.1, 0]) processor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(16000).fill(amplitude) } })
  })
}

for (const microphone of ['', 'usb']) test(`guided enrollment uses ${microphone || 'default'} microphone and stops at eighty percent`, async ({ page }) => {
  await localVoice(page)
  await page.addInitScript(() => localStorage.setItem('jarvis_mic_device', 'old-usb-microphone'))
  await page.route('**/api/settings/mic', route => route.fulfill({ json: { ok: true, device_id: microphone, device_name: microphone ? 'USB microphone' : '' } }))
  let text = 'meu nome é Jamille'
  const actions: any[] = []
  await page.route('**/api/identity/reading', route => route.fulfill({ json: { ok: true, text } }))
  await page.route('**/api/identity', route => {
    actions.push(route.request().postDataJSON())
    return route.fulfill({ json: { ok: true, ticket: 'voice-ticket', phrase: 'Jarvis minha voz autoriza referência', name: 'Jamille' } })
  })
  await page.goto('/tests/identity-page.html?enroll')
  await page.evaluate(async () => (await import('/src/components/LiveEnrollment.tsx')).startIdentityEnrollment())
  const dialog = page.getByRole('dialog')
  await say(page)
  await expect(dialog.getByText('Conhecer Jamille')).toBeVisible()
  expect(actions).toEqual([])
  text = 'sim autorizo minha voz'; await say(page)
  await expect(dialog.getByRole('button', { name: 'Concluir leitura', exact: true })).toBeVisible()
  text = 'REFERENCIA autoriza VOZ minha'; await say(page)
  await expect.poll(() => actions.some(a => a.action === 'live_enroll')).toBe(true)
  expect(actions.filter(a => a.action === 'enrollment_voice')).toHaveLength(1)
  expect(actions.find(a => a.action === 'live_enroll')).toMatchObject({ face_consent: false, images: [] })
  await expect(dialog).toBeHidden()
  expect(await page.evaluate(() => (window as any).localVoice.processors.some((p: any) => p.active))).toBe(false)
  const constraints = await page.evaluate(() => (window as any).localVoice.constraints)
  expect(constraints.length).toBeGreaterThan(0)
  const expected = microphone ? { exact: microphone } : { ideal: 'default' }
  expect(constraints.every((c: MediaStreamConstraints) => JSON.stringify((c.audio as MediaTrackConstraints).deviceId) === JSON.stringify(expected))).toBe(true)
})

test('administrator name dictation stops before password entry', async ({ page }) => {
  await localVoice(page)
  await page.route('**/api/identity/reading', route => route.fulfill({ json: { ok: true, text: 'eu sou Jean' } }))
  await page.goto('/tests/identity-page.html?enroll')
  await page.evaluate(async () => (await import('/src/components/LiveEnrollment.tsx')).startIdentityEnrollment({ admin: true }))
  const dialog = page.getByRole('dialog')
  await say(page)
  await expect(dialog.getByText('Jean', { exact: true })).toBeVisible()
  await expect(dialog.getByLabel('Senha administrativa')).toHaveValue('')
  await expect.poll(() => page.evaluate(() => (window as any).localVoice.processors.some((p: any) => p.active))).toBe(false)
  await dialog.getByLabel('Senha administrativa').focus()
  await expect.poll(() => page.evaluate(() => (window as any).localVoice.processors.some((p: any) => p.active))).toBe(false)
})

test('closing enrollment discards a late spoken answer and releases the microphone', async ({ page }) => {
  await localVoice(page)
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  let requested = false
  await page.route('**/api/identity/reading', async route => { requested = true; await gate; await route.fulfill({ json: { ok: true, text: 'Jamille' } }).catch(() => {}) })
  await page.goto('/tests/identity-page.html?enroll')
  await page.evaluate(async () => (await import('/src/components/LiveEnrollment.tsx')).startIdentityEnrollment())
  await say(page)
  await expect.poll(() => requested).toBe(true)
  await page.getByRole('button', { name: 'Cancelar cadastro' }).click()
  release()
  await expect(page.getByRole('dialog')).toBeHidden()
  expect(await page.evaluate(() => (window as any).localVoice.processors.some((p: any) => p.active))).toBe(false)
  expect(await page.evaluate(() => (window as any).localVoice.stopped)).toBeGreaterThan(0)
})
