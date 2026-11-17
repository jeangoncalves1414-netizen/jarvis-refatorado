import { test, expect } from '@playwright/test'
import { isCameraObservationRequest } from '../src/utils/cameraRequest'

const questions = [
  'identifica quem aparece na câmera',
  'Jarvis, identifique quem está na câmera',
  'Você consegue me reconhecer pela webcam?',
  'Reconheça meu rosto pela câmera',
  'Jarvis você vê alguém na câmera',
  'ver se tem alguém na câmera',
  'Jarvis, você consegue ver alguém na câmera?',
  'Você está vendo alguém pela webcam?',
  'Por favor, olha minha câmera',
  'Quem aparece na câmera?',
  'O que você vê na câmera?',
  'Jarvis, me fala quem você vê na câmera',
]

test('recognizes observation requests without capturing for other camera topics', () => {
  for (const question of questions) expect(isCameraObservationRequest(question), question).toBe(true)
  for (const question of [
    'Não olha minha câmera', 'Você pode configurar a câmera?',
    'Ver gravação da câmera de ontem', 'Como instalar o driver da webcam?',
    'Qual câmera comprar?', 'Você consegue ver minhas mensagens?',
    'Ver se tem alguém na câmera sem abrir a câmera',
    'Não me reconheça pela câmera', 'Como reconhecer pessoas pela câmera?',
  ]) expect(isCameraObservationRequest(question), question).toBe(false)
})

test.use({ launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }, permissions: ['camera'] })

for (const question of questions.slice(0, 8)) {
  test(`chat sends a real frame for: ${question}`, async ({ page }) => {
    let frames = 0
    const textRequests: string[] = []
    await page.route('**/api/**', async route => {
      const pathname = new URL(route.request().url()).pathname
      if (pathname === '/api/vision/analyze-frame') {
        const body = route.request().postDataJSON()
        expect(body.prompt).toBe(question)
        expect(body.image).toMatch(/^data:image\/jpeg;base64,/)
        expect(body.image.length).toBeGreaterThan(1000)
        frames++
        return route.fulfill({ json: { ok: true, reply: 'Quadro de teste recebido.' } })
      }
      if (pathname.startsWith('/api/chat')) textRequests.push(pathname)
      const replies: Record<string, unknown> = {
        '/api/app-lock': { ok: true, configured: true, enabled: false },
        '/api/sessions': { sessions: [], id: 'demo' },
        '/api/sessions/demo/history': { history: [] },
      }
      return route.fulfill({ status: pathname in replies ? 200 : 503, json: replies[pathname] || {} })
    })
    await page.addInitScript(() => localStorage.setItem('jarvis-active-screen', 'Chat'))
    await page.goto('/')
    const input = page.locator('.ws-composer textarea:visible').first()
    await input.fill(question)
    await input.press('Enter')
    await expect(page.getByText(/Quadro de teste recebido/).first()).toBeVisible({ timeout: 20000 })
    await expect(page.getByRole('dialog', { name: 'Espaço de câmeras' })).toBeHidden()
    expect(frames).toBe(1)
    expect(textRequests).toEqual([])
  })
}

test('camera denial keeps the request visible without sending text-only chat', async ({ page }) => {
  const submitted: string[] = []
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.startsWith('/api/chat') || pathname === '/api/vision/analyze-frame') submitted.push(pathname)
    const replies: Record<string, unknown> = {
      '/api/app-lock': { ok: true, configured: true, enabled: false },
      '/api/sessions': { sessions: [] },
    }
    return route.fulfill({ status: pathname in replies ? 200 : 503, json: replies[pathname] || {} })
  })
  await page.addInitScript(() => {
    localStorage.setItem('jarvis-active-screen', 'Chat')
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Denied', 'NotAllowedError') }
  })
  await page.goto('/')
  const input = page.locator('.ws-composer textarea:visible').first()
  await input.fill(questions[0])
  await input.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Espaço de câmeras' })
  await expect(page.getByText('Não consegui acessar as câmeras. Confira a conexão e a permissão de câmera.')).toBeVisible()
  await expect(dialog).toBeHidden()
  expect(submitted).toEqual([])
})
