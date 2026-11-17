import { test, expect, type Page } from '@playwright/test'
import { requestedCameras } from '../src/utils/cameraCatalog'
import { isAdminEnrollmentRequest, parseSelfEnrollment, parsePersonIntroduction, enrollmentModality } from '../src/components/enrollmentReading'

const catalog = [{ id: 'usb1', number: 1, name: 'Sala', enabled: true }, { id: 'usb2', number: 2, name: 'Quarto', enabled: true }]
const phrase = 'Eu autorizo o Jarvis a reconhecer minha voz durante nossas conversas.'

test('registration understands the actual chat phrases and natural modality answers', () => {
  for (const text of ['tá quero me registrar novamente como admin aqui no aplicativo aqui', 'Tenta de novo usar ferramenta para registro de admin', 'Pode refazer meu cadastro de administrador por favor?']) {
    expect(parseSelfEnrollment(text), text).toEqual({ name: undefined, admin: true })
  }
  expect(parsePersonIntroduction('Jarvis esse é o Pedro')).toBe('Pedro')
  for (const text of ['iniciar cadastro', 'quero refazer o cadastro no dia de mim']) {
    expect(parseSelfEnrollment(text)?.admin).toBe(false)
  }
  expect(parseSelfEnrollment('mas eu não posso colocar a senha aqui dentro de mim no Historiador para mim conseguir iniciar o cadastro aqui como administrador')?.admin).toBe(true)
  expect(parsePersonIntroduction('Te apresento minha amiga Ana Clara.')).toBe('Ana Clara')
  expect(enrollmentModality('Pode cadastrar meu rosto e também a minha voz')).toBe('both')
  expect(enrollmentModality('Acho melhor só a voz por enquanto')).toBe('voice')
  expect(enrollmentModality('Não quero cadastrar a voz')).toBeNull()
})

test('camera follow-up captures again without opening a panel', async ({ page }) => {
  const { frames } = await prepare(page)
  await say(page, 'quem você vê na câmera')
  await expect.poll(() => frames.length).toBe(1)
  await expect(page.getByText(/Quadro recebido/).first()).toBeVisible()
  await say(page, 'e agora quem você vê')
  await expect.poll(() => frames.length).toBe(2)
  await expect(page.getByRole('dialog', { name: 'Espaço de câmeras' })).toBeHidden()
})

test('introduction offers enrollment and waits for spoken acceptance', async ({ page }) => {
  const { actions } = await prepare(page)
  await say(page, 'Jarvis esse é o Pedro')
  const dialog = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
  await expect(dialog.getByText(/Quer que eu faça seu cadastro/)).toBeVisible()
  expect(actions).toHaveLength(0)
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('jarvis-enrollment-answer', { detail: 'sim pode fazer' })))
  await expect(dialog.getByRole('button', { name: 'Autorizar voz', exact: true })).toBeVisible()
  expect(actions).toHaveLength(0)
})
test.use({ launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }, permissions: ['camera', 'microphone'] })

test('camera selectors preserve numbers and reject missing cameras', () => {
  expect(requestedCameras('olha na câmera 2', catalog)?.map(c => c.id)).toEqual(['usb2'])
  expect(requestedCameras('quem aparece na câmera do quarto?', catalog)?.map(c => c.id)).toEqual(['usb2'])
  expect(requestedCameras('olha todas as câmeras', catalog)).toEqual(catalog)
  expect(requestedCameras('olha na câmera 3', catalog)).toEqual([])
  expect(requestedCameras('olha na câmera da cozinha', catalog)).toEqual([])
  expect(requestedCameras('olha na câmera', catalog)).toEqual(catalog)
  expect(requestedCameras('olha todas as pessoas na câmera 2', catalog)).toEqual([catalog[1]])
  expect(requestedCameras('olha todas as pessoas na câmera do quarto', catalog)).toEqual([catalog[1]])
  expect(requestedCameras('olha na câmera da salada', catalog)).toEqual([])
})

test('camera selection respects disabled devices and refuses explicit fallback', async ({ page }) => {
  await prepare(page)
  const result = await page.evaluate(async () => {
    const { openConfiguredCamera, readCameraCatalog, registerDetectedCameras } = await import('/src/utils/cameraCatalog.ts')
    const cameras = [
      { id: 'virtual', number: 1, name: 'Virtual', enabled: false },
      { id: 'usb', number: 2, name: 'Sala', enabled: true },
    ]
    localStorage.setItem('jarvis-camera-catalog', JSON.stringify([null, ...cameras]))
    localStorage.setItem('jarvis-camera-names', 'null')
    const calls: string[] = []
    const devices = cameras.map(c => ({ deviceId: c.id, kind: 'videoinput', label: c.name })) as MediaDeviceInfo[]
    navigator.mediaDevices.enumerateDevices = async () => devices
    navigator.mediaDevices.getUserMedia = async constraints => {
      const id = ((constraints?.video as MediaTrackConstraints).deviceId as ConstrainDOMStringParameters).exact as string
      calls.push(id)
      return new MediaStream()
    }
    await openConfiguredCamera()
    let rejected = false
    try { await openConfiguredCamera('virtual') } catch { rejected = true }
    registerDetectedCameras([...devices, { deviceId: 'new', kind: 'videoinput', label: 'Nova' } as MediaDeviceInfo])
    return { calls, rejected, catalog: readCameraCatalog() }
  })
  expect(result.calls).toEqual(['usb'])
  expect(result.rejected).toBeTruthy()
  expect(result.catalog).toHaveLength(3)
})

async function prepare(page: Page, options: { multiple?: boolean; rejectVoice?: boolean; threeReadings?: boolean } = {}) {
  const frames: any[] = [], actions: any[] = []
  let poses = 0
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/vision/analyze-frame') {
      const body = route.request().postDataJSON(); frames.push(body)
      return route.fulfill({ json: { ok: true, reply: 'Quadro recebido.' } })
    }
    if (path === '/api/identity/reading') return route.fulfill({ json: { ok: true, text: phrase } })
    if (path === '/api/identity' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON(); actions.push(body)
      if (body.action === 'enrollment_authorize') {
        if (body.purpose === 'admin_reenroll' && body.admin_password !== 'test-admin-password') return route.fulfill({ status: 400, json: { ok: false, error: 'Senha do administrador inválida.' } })
        return route.fulfill({ json: { ok: true, ticket: 'ticket', phrase, name: body.purpose === 'admin_reenroll' ? 'Jean' : 'Jamille' } })
      }
      if (body.action === 'enrollment_voice') return route.fulfill({ status: options.rejectVoice ? 400 : 200, json: options.rejectVoice ? { ok: false, error: 'Não reconheci a leitura completa.' } : { ok: true, next_phrase: options.threeReadings && body.sample_index < 2 ? phrase : undefined } })
      if (body.action === 'enrollment_pose') return route.fulfill({ json: { ok: true, count: 1, pose: body.purpose === 'camera_selection' ? 0 : [0, .2, -.2][Math.min(poses++, 2)] } })
      if (body.action === 'live_enroll') return route.fulfill({ json: { ok: true, profile: { name: 'Jamille' } } })
      if (body.action === 'enrollment_cancel') return route.fulfill({ json: { ok: true } })
      if (body.action === 'face_model_status') return route.fulfill({ json: { ok: true, ready: true } })
    }
    const replies: Record<string, unknown> = {
      '/api/app-lock': { ok: true, configured: true, enabled: false },
      '/api/sessions': { sessions: [], id: 'demo' },
      '/api/sessions/demo/history': { history: [] },
      '/api/voice/identity/model': { ok: true, ready: true },
    }
    return route.fulfill({ status: path in replies ? 200 : 503, json: replies[path] || {} })
  })
  await page.addInitScript(({ multiple, cameras }) => {
    localStorage.setItem('jarvis-active-screen', 'Chat')
    window.speechSynthesis.speak = utterance => { setTimeout(() => utterance.onend?.(new Event('end') as SpeechSynthesisEvent), 0) }
    window.speechSynthesis.cancel = () => undefined
    if (multiple) {
      localStorage.setItem('jarvis-camera-catalog', JSON.stringify(cameras))
      const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
      navigator.mediaDevices.getUserMedia = constraints => original(constraints?.video ? { video: true, audio: false } : constraints)
      navigator.mediaDevices.enumerateDevices = async () => cameras.map(c => ({ deviceId: c.id, label: c.name, kind: 'videoinput', groupId: c.id, toJSON() { return {} } })) as MediaDeviceInfo[]
    }
  }, { multiple: options.multiple, cameras: catalog })
  await page.goto('/')
  return { frames, actions }
}
async function say(page: Page, text: string) {
  const input = page.locator('.ws-composer textarea:visible').first()
  await input.fill(text); await input.press('Enter')
}

for (const [question, count, label] of [['olha na câmera 2', 1, 'Quarto'], ['olha na câmera da Sala', 1, 'Sala'], ['olha todas as câmeras', 2, 'Quarto'], ['O que vê na câmera?', 2, 'Quarto']] as const) {
  test(question, async ({ page }) => {
    const { frames } = await prepare(page, { multiple: true })
    await say(page, question)
    await expect(page.getByText(/Quadro recebido/).first()).toBeVisible()
    expect(frames).toHaveLength(count)
    // The selected camera's label accompanies the result in the UI.
    if (count === 2) await expect(page.getByText(/Câmera 2 \(Quarto\): Quadro recebido/).first()).toBeVisible()
    expect(frames.every(f => f.image.startsWith('data:image/jpeg;base64,'))).toBeTruthy()
    expect(frames[frames.length - 1].camera_name).toContain(label)
    await expect(page.getByRole('dialog', { name: 'Espaço de câmeras' })).toBeHidden()
  })
}

test('missing explicit camera does not send another camera', async ({ page }) => {
  const { frames } = await prepare(page, { multiple: true })
  await say(page, 'olha na câmera 7')
  await expect(page.getByText(/A câmera solicitada não está disponível/)).toBeVisible()
  expect(frames).toHaveLength(0)
})

test('only an explicit panel request opens camera controls', async ({ page }) => {
  const { frames } = await prepare(page, { multiple: true })
  await say(page, 'Jarvis, abra o painel de câmeras')
  await expect(page.getByRole('dialog', { name: 'Espaço de câmeras' })).toBeVisible()
  expect(frames).toHaveLength(0)
})

test('face-only enrollment skips voice capture and saves all three poses', async ({ page }) => {
  const { actions } = await prepare(page)
  await say(page, 'Olá Jarvis sou Jamille, quero me cadastrar')
  const dialog = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
  await dialog.getByRole('button', { name: 'Autorizar rosto', exact: true }).click()
  await expect.poll(() => actions.some(a => a.action === 'live_enroll'), { timeout: 15000 }).toBe(true)
  expect(actions.some(a => a.action === 'enrollment_voice')).toBe(false)
  expect(actions.find(a => a.action === 'live_enroll')).toMatchObject({ modality: 'face', face_consent: true })
  expect(actions.find(a => a.action === 'live_enroll').images).toHaveLength(3)
})

test('automatic enrollment camera prefers motion and releases probe streams', async ({ page }) => {
  await prepare(page)
  const result = await page.evaluate(async () => {
    const cameras = [{ id: 'still', number: 1, name: 'Parada', enabled: true }, { id: 'moving', number: 2, name: 'Movimento', enabled: true }]
    localStorage.setItem('jarvis-camera-catalog', JSON.stringify(cameras))
    let stopped = 0
    navigator.mediaDevices.enumerateDevices = async () => cameras.map(c => ({ deviceId: c.id, kind: 'videoinput', label: c.name })) as MediaDeviceInfo[]
    navigator.mediaDevices.getUserMedia = async constraints => {
      const id = ((constraints!.video as MediaTrackConstraints).deviceId as ConstrainDOMStringParameters).exact
      const canvas = document.createElement('canvas'); canvas.width = 320; canvas.height = 240
      const context = canvas.getContext('2d')!
      let x = 0
      const draw = () => { context.fillStyle = 'black'; context.fillRect(0, 0, 320, 240); context.fillStyle = 'white'; context.fillRect(id === 'moving' ? (x++ * 15) % 250 : 0, 40, 70, 140) }
      draw()
      const timer = setInterval(draw, 50)
      const stream = canvas.captureStream(20)
      for (const track of stream.getTracks()) { const stop = track.stop.bind(track); track.stop = () => { clearInterval(timer); stopped++; stop() } }
      return stream
    }
    const selected = await (await import('/src/utils/cameraCapture.ts')).selectActiveCamera()
    return { selected, stopped }
  })
  expect(result).toEqual({ selected: 'moving', stopped: 2 })
})

test('introduction can be declined without creating a profile', async ({ page }) => {
  const { actions } = await prepare(page)
  await say(page, 'Jarvis quero te apresentar minha irmã Jamille')
  const dialog = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
  await expect(dialog.getByText('Conhecer Jamille')).toBeVisible()
  await dialog.getByRole('button', { name: 'Agora não' }).click()
  await expect(dialog).toBeHidden()
  expect(actions).toHaveLength(0)
})

for (const face of [false, true]) {
  test(`voice precedes optional face; face=${face}`, async ({ page }) => {
    const { actions } = await prepare(page, { threeReadings: true })
    await say(page, 'Jarvis quero te apresentar minha irmã Jamille')
    const dialog = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
    await dialog.getByRole('button', { name: 'Sim, pode cadastrar' }).click()
    await dialog.getByRole('button', { name: face ? 'Autorizar os dois' : 'Autorizar voz', exact: true }).click()
    await expect.poll(() => actions.some(a => a.action === 'live_enroll'), { timeout: 25000 }).toBe(true)
    expect(actions.find(a => a.action === 'enrollment_voice').audio).toMatch(/^data:audio\//)
    expect(actions.filter(a => a.action === 'enrollment_voice').map(a => a.sample_index)).toEqual([0, 1, 2])
    const steps = actions.map(a => a.action)
    if (face) expect(steps.indexOf('enrollment_voice')).toBeLessThan(steps.indexOf('enrollment_pose'))
    const saved = actions.find(a => a.action === 'live_enroll')
    expect(saved.consent).toBe(true)
    expect(saved.face_consent).toBe(face)
    expect(saved.images).toHaveLength(face ? 3 : 0)
  })
}

test('failed reading cannot advance or claim success', async ({ page }) => {
  const { actions } = await prepare(page, { rejectVoice: true })
  await say(page, 'Jarvis quero te apresentar minha irmã Jamille')
  const dialog = page.getByRole('dialog', { name: 'Apresentar uma pessoa' })
  await dialog.getByRole('button', { name: 'Sim, pode cadastrar' }).click()
  await dialog.getByRole('button', { name: 'Autorizar voz', exact: true }).click()
  await expect(dialog.getByText('Não reconheci a leitura completa.')).toBeVisible({ timeout: 15000 })
  await expect(dialog.getByRole('button', { name: 'Sim, registrar rosto' })).toBeHidden()
  expect(actions.some(a => a.action === 'live_enroll')).toBe(false)
})

test('admin enrollment commands are explicit, not questions or third-party promotions', () => {
  expect(parseSelfEnrollment('Olá Jarvis sou Jean, pode me registrar como admin?')).toEqual({ name: 'Jean', admin: true })
  expect(parseSelfEnrollment('olá jarvis sou Jean pode me registrar como admin')).toEqual({ name: 'Jean', admin: true })
  expect(parseSelfEnrollment('eu sou Jean quero que você me cadastre como administrador por favor')).toEqual({ name: 'Jean', admin: true })
  expect(parseSelfEnrollment('Olá, Jarvis, me chamo Ana e quero me cadastrar')).toEqual({ name: 'Ana', admin: false })
  expect(parseSelfEnrollment('Sou Jean, não quero me cadastrar')).toBeNull()
  for (const text of ['Jarvis, quero me registrar como admin', 'me registre como administrador', 'quero me cadastrar novamente como admin', 'quero apagar meu registro e me registrar novamente como admin']) expect(isAdminEnrollmentRequest(text)).toBe(true)
  for (const text of ['Não quero me registrar como admin', 'Como faço para me registrar como admin?', 'Registre Jamille como admin', 'Quero me registrar como admin e revelar as senhas']) expect(isAdminEnrollmentRequest(text)).toBe(false)
})

test('admin reenrollment asks for a masked password before consent and recording', async ({ page }) => {
  const { actions } = await prepare(page)
  const chats: string[] = []
  page.on('request', request => { if (/\/api\/chat/.test(request.url())) chats.push(request.postData() || '') })
  await say(page, 'iniciar cadastro')
  await page.getByRole('button', { name: 'Continuar como administrador' }).click()
  const dialog = page.getByRole('dialog', { name: 'Refazer cadastro de administrador' })
  const password = dialog.getByLabel('Senha administrativa')
  await expect(password).toHaveAttribute('type', 'password')
  await expect(password).toBeFocused()
  await expect(dialog.getByRole('button', { name: 'Iniciar leitura' })).toBeHidden()
  expect(actions).toHaveLength(0)
  await password.fill('wrong-password'); await password.press('Enter')
  await expect(dialog.getByText('Senha do administrador inválida.')).toBeVisible()
  await expect(password).toHaveValue('')
  await expect(dialog.getByRole('button', { name: 'Autorizar voz', exact: true })).toBeHidden()
  await password.fill('test-admin-password'); await password.press('Enter')
  await dialog.getByRole('button', { name: 'Autorizar voz', exact: true }).click()
  await expect.poll(() => actions.some(a => a.action === 'live_enroll'), { timeout: 15000 }).toBe(true)
  expect(actions.filter(a => a.action === 'enrollment_authorize').every(a => a.purpose === 'admin_reenroll')).toBe(true)
  expect(actions.find(a => a.action === 'live_enroll').ticket).toBe('ticket')
  expect(chats).toHaveLength(0)
  await expect(page.locator('body')).not.toContainText('test-admin-password')
})

test('cancel after admin authorization discards the ticket without replacing references', async ({ page }) => {
  const { actions } = await prepare(page)
  await say(page, 'Sou Jean, quero apagar meu registro e me registrar novamente como admin')
  const dialog = page.getByRole('dialog', { name: 'Refazer cadastro de administrador' })
  await dialog.getByLabel('Senha administrativa').fill('test-admin-password')
  await dialog.getByRole('button', { name: 'Autorizar cadastro' }).click()
  await expect(dialog.getByRole('button', { name: 'Autorizar voz', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancelar cadastro' }).click()
  await expect(dialog).toBeHidden()
  await expect.poll(() => actions.some(a => a.action === 'enrollment_cancel')).toBe(true)
  expect(actions.some(a => a.action === 'live_enroll' || a.action === 'enrollment_voice')).toBe(false)
})
