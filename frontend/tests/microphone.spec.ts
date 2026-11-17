import { test, expect, type Page } from '@playwright/test'

async function setup(page: Page) {
  const state = { settings: { ok: true, sensitivity: 75, silence_ms: 800, gain: 1, engine: 'auto', device_id: '', device_name: '' }, failSave: false }
  await page.route('**/api/settings/mic', route => {
    if (route.request().method() === 'POST') {
      if (state.failSave) return route.fulfill({ status: 500, json: { ok: false, error: 'Falha ao salvar' } })
      Object.assign(state.settings, route.request().postDataJSON())
    }
    return route.fulfill({ json: state.settings })
  })
  await page.route('**/api/voice/capture/devices', route => route.fulfill({ json: { available: true, devices: [] } }))
  await page.addInitScript(() => {
    const devices = ['default', 'communications', 'laptop', 'usb'].map((id, i) => ({ kind: 'audioinput', deviceId: id, label: ['Default', 'Communications', 'Laptop mic', 'USB microphone'][i] }))
    const state = { devices, captures: [] as any[], stopped: 0 }
    ;(window as any).microphoneTest = state
    Object.defineProperty(navigator, 'mediaDevices', { value: {
      enumerateDevices: async () => state.devices,
      getUserMedia: async (constraints: any) => {
        state.captures.push(constraints)
        const track = { kind: 'audio', readyState: 'live', id: constraints.audio.deviceId?.exact || 'default', stop: () => state.stopped++ }
        return { getTracks: () => [track], getAudioTracks: () => [track] }
      },
    } })
  })
  await page.goto('/tests/microphone.html')
  await expect(page.getByLabel('Microfone do aplicativo')).toBeEnabled()
  return state
}

async function capture(page: Page) {
  return page.evaluate(async () => {
    const { openMicrophone } = await import('/src/utils/micPrefs.ts')
    const stream = await openMicrophone({ echoCancellation: true })
    stream.getTracks().forEach(track => track.stop())
    return (window as any).microphoneTest.captures.at(-1)
  })
}

test('one selection persists across reloads and restores the system default', async ({ page }) => {
  const state = await setup(page)
  const select = page.getByLabel('Microfone do aplicativo')
  await expect(select.locator('option')).toHaveText(['Microfone padrão do sistema', 'Laptop mic', 'USB microphone'])
  await select.selectOption('usb')
  await expect.poll(() => state.settings.device_name).toBe('USB microphone')
  expect(await capture(page)).toEqual({ audio: { echoCancellation: true, deviceId: { exact: 'usb' } } })
  await page.reload()
  await expect(select).toHaveValue('usb')
  await select.selectOption('')
  await expect.poll(() => state.settings.device_name).toBe('')
  expect(await capture(page)).toEqual({ audio: { echoCancellation: true, deviceId: { ideal: 'default' } } })
})

test('failed save preserves the working microphone', async ({ page }) => {
  const state = await setup(page)
  state.failSave = true
  await page.getByLabel('Microfone do aplicativo').selectOption('usb')
  await expect(page.getByText('Falha ao salvar', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Microfone do aplicativo')).toHaveValue('')
  expect((await capture(page)).audio.deviceId).toEqual({ ideal: 'default' })
})

test('disconnected selected microphone never opens another device', async ({ page }) => {
  const state = await setup(page)
  await page.getByLabel('Microfone do aplicativo').selectOption('usb')
  await expect.poll(() => state.settings.device_id).toBe('usb')
  await page.evaluate(() => { (window as any).microphoneTest.devices = [] })
  const error = await page.evaluate(async () => {
    try { await (await import('/src/utils/micPrefs.ts')).openMicrophone() } catch (error) { return String(error) }
  })
  expect(error).toContain('Microfone selecionado indisponível')
  expect(await page.evaluate(() => (window as any).microphoneTest.captures)).toEqual([])
})

test('recognition receives the chosen audio track and releases it on cancellation', async ({ page }) => {
  const state = await setup(page)
  await page.getByLabel('Microfone do aplicativo').selectOption('usb')
  await expect.poll(() => state.settings.device_id).toBe('usb')
  const result = await page.evaluate(async () => {
    const { createMicrophoneRecognition } = await import('/src/utils/micPrefs.ts')
    let started!: (track: any) => void
    const ready = new Promise<any>(resolve => { started = resolve })
    class Recognition { start(track: any) { started(track) }; stop() {}; abort() {} }
    const recognition = createMicrophoneRecognition(Recognition)
    recognition.start()
    const track = await ready
    recognition.abort()
    return { id: track.id, stopped: (window as any).microphoneTest.stopped }
  })
  expect(result).toEqual({ id: 'usb', stopped: 1 })
})

test('locked app uses the last saved device and refreshed ids resolve by name', async ({ page }) => {
  const state = await setup(page)
  await page.getByLabel('Microfone do aplicativo').selectOption('usb')
  await expect.poll(() => state.settings.device_id).toBe('usb')
  await expect(page.getByLabel('Microfone do aplicativo')).toBeEnabled()
  await page.route('**/api/settings/mic', route => route.fulfill({ status: 403 }))
  await page.evaluate(() => { (window as any).microphoneTest.devices.find((d: any) => d.deviceId === 'usb').deviceId = 'usb-new' })
  expect((await capture(page)).audio.deviceId).toEqual({ exact: 'usb-new' })
})

test('cancelled recognition does not capture after settings finish loading', async ({ page }) => {
  await setup(page)
  await page.route('**/api/settings/mic', async route => {
    await new Promise(resolve => setTimeout(resolve, 100))
    await route.fulfill({ json: { ok: true, device_name: 'USB microphone', device_id: 'usb' } })
  })
  await page.evaluate(async () => {
    const { createMicrophoneRecognition } = await import('/src/utils/micPrefs.ts')
    class Recognition { start() { throw new Error('Capture must not start') }; stop() {}; abort() {} }
    const recognition = createMicrophoneRecognition(Recognition)
    recognition.start(); recognition.abort()
  })
  await page.waitForTimeout(200)
  expect(await page.evaluate(() => (window as any).microphoneTest.captures)).toEqual([])
})
