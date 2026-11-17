import { test, expect, type Page } from '@playwright/test'

test.use({ launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }, permissions: ['camera'] })

async function fakeAudio(page: Page) {
  await page.addInitScript(() => {
    const state = { requests: 0, starts: 0, stopped: 0, closed: 0, recognizers: 0, context: null as any, recorder: null as any }
    ;(window as any).mediaTest = state
    Object.defineProperty(navigator, 'mediaDevices', { value: {
      enumerateDevices: async () => [],
      getUserMedia: async () => { state.requests++; return { getTracks: () => [{ stop: () => state.stopped++ }] } },
    } })
    ;(window as any).SpeechRecognition = class { constructor() { state.recognizers++ } start() {} stop() {} }
    ;(window as any).MediaRecorder = class {
      state = 'inactive'; mimeType = 'audio/webm'; onstop: any; ondataavailable: any
      constructor(public stream: MediaStream) { state.recorder = this }
      start() { this.state = 'recording'; state.starts++ }
      stop() { this.state = 'inactive'; queueMicrotask(() => { this.ondataavailable?.({ data: new Blob(['sample']) }); this.onstop?.() }) }
    }
    ;(window as any).AudioContext = class {
      state = 'running'; processor: any; destination = {}
      constructor() { state.context = this }
      createMediaStreamSource() { return { connect() {}, disconnect() {} } }
      createScriptProcessor() { this.processor = { connect() {}, disconnect() {}, onaudioprocess: null }; return this.processor }
      async resume() {}
      async close() { this.state = 'closed'; state.closed++ }
    }
  })
}

test('manual enrollment uses the local reader and releases it on exit', async ({ page }) => {
  await fakeAudio(page)
  let phrase = '', readings = 0
  await page.route('**/api/**', route => {
    if (route.request().url().endsWith('/identity/reading')) {
      readings++
      return route.fulfill({ json: { ok: true, text: phrase } })
    }
    return route.fulfill({ json: { ok: true, ready: true, has_admin: true, profiles: [{ id: 'jean', name: 'Jean', role: 'admin' }] } })
  })
  await page.goto('/tests/identity-page.html')
  await page.getByRole('combobox').first().selectOption('jean')
  await page.getByPlaceholder('Senha de desbloqueio para as amostras').fill('test-password')
  phrase = await page.locator('.identity-enrollment-phrase p').innerText()
  await page.getByRole('button', { name: 'Gravar leitura' }).click()
  await expect.poll(() => page.evaluate(() => Boolean((window as any).mediaTest.context?.processor?.onaudioprocess))).toBeTruthy()
  await page.evaluate(() => (window as any).mediaTest.context.processor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(16000) } }))
  await expect(page.locator('.identity-enrollment-phrase span').first()).toHaveCSS('color', 'rgb(54, 230, 165)')
  expect(readings).toBe(1)
  expect(await page.evaluate(() => (window as any).mediaTest.requests)).toBe(1)
  expect(await page.evaluate(() => (window as any).mediaTest.recognizers)).toBe(0)
  await page.getByRole('button', { name: 'Sair da identidade' }).click()
  await expect.poll(() => page.evaluate(() => (window as any).mediaTest.closed)).toBe(1)
})

for (const action of ['cancel', 'leave', 'switch']) {
  test(`lock voice recording is discarded after ${action}`, async ({ page }) => {
    await fakeAudio(page)
    const submissions: any[] = []
    await page.route('**/api/app-lock', route => {
      if (route.request().method() === 'POST') submissions.push(route.request().postDataJSON())
      return route.fulfill({ json: { ok: true, configured: true, enabled: true, unlocked: false, voice: true, face: true } })
    })
    await page.goto('/tests/identity-page.html?lock')
    await page.getByRole('button', { name: 'Usar voz', exact: true }).click()
    await page.getByRole('button', { name: 'Gravar voz', exact: true }).click()
    await expect.poll(() => page.evaluate(() => (window as any).mediaTest.starts)).toBe(1)
    if (action === 'leave') await page.getByRole('button', { name: 'Sair da identidade' }).evaluate((element: HTMLButtonElement) => element.click())
    else await page.getByRole('button', { name: action === 'cancel' ? 'Cancelar' : 'Usar rosto', exact: true }).click()
    await expect.poll(() => page.evaluate(() => (window as any).mediaTest.stopped)).toBeGreaterThan(0)
    await page.waitForTimeout(200)
    expect(submissions).toEqual([])
  })
}

test('showing the lock clears cached identity evidence', async ({ page }) => {
  let unlocked = true
  await page.route('**/api/app-lock', route => route.fulfill({ json: { ok: true, configured: true, enabled: true, unlocked, voice: false, face: false } }))
  await page.clock.install()
  await page.goto('/tests/identity-page.html?lock')
  await expect(page.getByText('Painel desbloqueado')).toBeVisible()
  await page.evaluate(async () => (await import('/src/utils/identityEvidence.ts')).rememberIdentityEvidence('old-proof'))
  unlocked = false
  await page.clock.runFor(10001)
  await expect(page.getByRole('heading', { name: 'Desbloquear Jarvis' })).toBeVisible()
  expect(await page.evaluate(async () => (await import('/src/utils/identityEvidence.ts')).takeIdentityEvidence())).toBeUndefined()
})

test.describe('face authorization', () => {
  for (const action of ['forget', 'leave', 'close']) {
    test(`late face confirmation cannot authorize after ${action}`, async ({ page }) => {
      let release!: () => void
      const gate = new Promise<void>(resolve => { release = resolve })
      let verifying = false
      await page.route('**/api/**', async route => {
        if (route.request().postDataJSON()?.action === 'verify_access') {
          verifying = true
          await gate
          return route.fulfill({ json: { ok: true, matched: true, requires_confirmation: false, evidence_token: 'late-proof' } })
        }
        return route.fulfill({ json: { ok: true, has_admin: true, profiles: [{ id: 'jean', name: 'Jean', role: 'admin' }] } })
      })
      await page.goto('/tests/identity-page.html')
      await page.getByRole('combobox').first().selectOption('jean')
      await page.getByPlaceholder('Senha de desbloqueio para as amostras').fill('test-password')
      await page.getByRole('button', { name: 'Abrir câmera escolhida' }).click()
      await expect.poll(() => page.locator('video').evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThanOrEqual(2)
      await page.getByRole('button', { name: 'Confirmar rosto para próximo pedido' }).click()
      await expect.poll(() => verifying).toBeTruthy()
      await page.getByRole('button', { name: action === 'forget' ? 'Esquecer perfil ativo' : action === 'close' ? 'Fechar' : 'Sair da identidade', exact: true }).click()
      const response = page.waitForResponse(r => r.url().endsWith('/api/identity') && r.request().postDataJSON()?.action === 'verify_access')
      release(); await response
      await page.waitForTimeout(100)
      expect(await page.evaluate(async () => (await import('/src/utils/identityEvidence.ts')).takeIdentityEvidence())).toBeUndefined()
    })
  }
})

test('an old unlocked status cannot replace a newer locked status', async ({ page }) => {
  let reads = 0, release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/app-lock', async route => {
    const read = ++reads
    if (read === 2) await gate
    return route.fulfill({ json: { ok: true, configured: true, enabled: true, unlocked: read < 3, voice: false, face: false } })
  })
  await page.clock.install()
  await page.goto('/tests/identity-page.html?lock')
  await expect(page.getByText('Painel desbloqueado')).toBeVisible()
  await page.clock.runFor(10001)
  await expect.poll(() => reads).toBe(2)
  await page.clock.runFor(10000)
  await expect(page.getByRole('heading', { name: 'Desbloquear Jarvis' })).toBeVisible()
  const response = page.waitForResponse('**/api/app-lock')
  release(); await response
  await expect(page.getByText('Painel desbloqueado')).toHaveCount(0)
})

test('leaving guided enrollment releases its active state for other captures', async ({ page }) => {
  await page.goto('/tests/identity-page.html?enroll')
  await page.evaluate(async () => {
    ;(window as any).enrollmentStates = []
    window.addEventListener('jarvis-enrollment-active', event => (window as any).enrollmentStates.push((event as CustomEvent).detail))
    const { handleLiveIntroduction } = await import('/src/components/LiveEnrollment.tsx')
    handleLiveIntroduction('Jarvis quero te apresentar minha irmã Jamille')
  })
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Sair da identidade' }).evaluate((element: HTMLButtonElement) => element.click())
  expect(await page.evaluate(() => (window as any).enrollmentStates)).toEqual([true, false])
})
