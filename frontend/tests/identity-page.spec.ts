import { test, expect } from '@playwright/test'

test('voice command levels require owner password and never offer private access', async ({ page }) => {
  let level = 'visitor'
  const grants: any[] = []
  await page.route('**/api/**', route => {
    const body = route.request().postDataJSON()
    if (body?.action === 'set_permission') { grants.push(body); level = body.level }
    return route.fulfill({ json: { ok: true, ready: true, has_admin: true, profiles: [
      { id: 'owner', name: 'Jean', role: 'admin' }, { id: 'guest', name: 'Ana', role: 'user', command_level: level },
    ] } })
  })
  await page.goto('/tests/identity-page.html')
  const select = page.getByLabel('Nível de voz de Ana')
  await expect(select).toBeDisabled()
  await page.getByLabel('Senha para permissões').fill('test-password')
  await select.selectOption('delegate')
  await expect(select).toHaveValue('delegate')
  expect(grants).toEqual([{ action: 'set_permission', profile_id: 'guest', level: 'delegate', admin_password: 'test-password' }])
  await expect(page.getByText('Níveis de acesso por voz', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Nível de voz de Jean')).toHaveCount(0)
})

for (const mode of ['pending', 'verify', 'enroll']) {
  test(`leaving identity releases microphone and never uploads abandoned recording: ${mode}`, async ({ page }) => {
    const actions: string[] = []
    await page.route('**/api/**', route => {
      const body = route.request().postDataJSON()
      if (body?.action) actions.push(body.action)
      return route.fulfill({ json: { ok: true, ready: true, has_admin: true, profiles: [{ id: 'jean', name: 'Jean', role: 'admin' }] } })
    })
    await page.addInitScript(delayed => {
      const state = { starts: 0, stopped: 0, requested: 0, release: () => {} }
      ;(window as any).micTest = state
      Object.defineProperty(navigator, 'mediaDevices', { value: {
        enumerateDevices: async () => [],
        getUserMedia: async () => {
          state.requested++
          if (delayed) await new Promise<void>(resolve => { state.release = resolve })
          return { getTracks: () => [{ stop: () => state.stopped++ }] }
        },
      } })
      ;(window as any).MediaRecorder = class {
        state = 'inactive'; mimeType = 'audio/webm'; onstop: any; ondataavailable: any
        constructor(public stream: MediaStream) {}
        start() { this.state = 'recording'; state.starts++ }
        stop() { this.state = 'inactive'; queueMicrotask(() => { this.ondataavailable?.({ data: new Blob(['sample']) }); this.onstop?.() }) }
      }
    }, mode === 'pending')
    await page.goto('/tests/identity-page.html')
    if (mode === 'enroll') {
      await page.getByRole('combobox').first().selectOption('jean')
      await page.getByPlaceholder('Senha de desbloqueio para as amostras').fill('test-password')
      await page.getByRole('button', { name: 'Gravar leitura' }).click()
    } else await page.getByRole('button', { name: 'Testar voz', exact: true }).click()
    await expect.poll(() => page.evaluate(() => (window as any).micTest.requested)).toBe(1)
    if (mode !== 'pending') await expect.poll(() => page.evaluate(() => (window as any).micTest.starts)).toBe(1)
    await page.getByRole('button', { name: 'Sair da identidade' }).click()
    if (mode === 'pending') await page.evaluate(() => (window as any).micTest.release())
    await expect.poll(() => page.evaluate(() => (window as any).micTest.stopped)).toBeGreaterThan(0)
    await page.waitForTimeout(200)
    expect(actions).not.toContain('observe')
    expect(actions).not.toContain('add_sample')
  })
}

for (const pending of [false, true]) {
  test(`unmounting camera workspace stops streams, including pending opens: ${pending}`, async ({ page }) => {
    await page.addInitScript(delayed => {
      const state = { requested: 0, stopped: 0, release: () => {} }
      ;(window as any).cameraTest = state
      Object.defineProperty(navigator, 'mediaDevices', { value: {
        enumerateDevices: async () => [{ deviceId: 'usb', kind: 'videoinput', label: 'USB' }],
        getUserMedia: async () => {
          state.requested++
          if (delayed) await new Promise<void>(resolve => { state.release = resolve })
          const stream = new MediaStream()
          stream.getTracks = () => [{ stop: () => state.stopped++ }] as MediaStreamTrack[]
          return stream
        },
      } })
    }, pending)
    await page.goto('/tests/identity-page.html?camera')
    await expect.poll(() => page.evaluate(() => (window as any).cameraTest.requested)).toBe(1)
    if (!pending) await expect(page.getByText('1 câmera(s) ao vivo. A análise só acontece quando você pedir.')).toBeVisible()
    await page.getByRole('button', { name: 'Sair da identidade' }).click({ force: true })
    if (pending) await page.evaluate(() => (window as any).cameraTest.release())
    await expect.poll(() => page.evaluate(() => (window as any).cameraTest.stopped)).toBeGreaterThan(0)
  })
}
