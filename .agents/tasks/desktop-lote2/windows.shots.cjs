// Verificação da etapa final (lote 2): janelas Finanças e Controles do PC e menu "/" em desktop e 360 px.
// Toda a API é simulada; nada real (volume, brilho, bloqueio, dados) é tocado.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')
const { mkdirSync } = require('node:fs')
const path = require('node:path')
const output = process.env.PANEL_TEST_OUTPUT
mkdirSync(output, { recursive: true })

const snapshot = { ok: true, components: [{ id: 'action_kernel', label: 'Ações', status: 'healthy', reason: 'ok' }, { id: 'providers', label: 'IA e voz', status: 'degraded', reason: 'Provedor indisponível.' }], summary: { pending_actions: 0, failed_actions: 0, devices: 0, active_goals: 0 }, goals: [], pending_actions: [], recent_actions: [] }

async function run(browser, label, viewport) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 })
  page.setDefaultTimeout(15000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let chatCalls = 0, failNextAdd = true, lockCalls = 0, brightnessSupported = true
  const finance = [
    { id: 'fin_a', type: 'expense', amount: 42.5, category: 'Mercado', description: 'Compras da semana', date_str: new Date().toISOString().slice(0, 10) },
    { id: 'fin_b', type: 'income', amount: 1200, category: 'Salário', description: 'Adiantamento', date_str: new Date().toISOString().slice(0, 10) },
  ]
  const controlCalls = []
  const totals = () => {
    const income = finance.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0)
    const expense = finance.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0)
    return { income, expense, net: income - expense, count: finance.length, by_category: [] }
  }
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url()), method = route.request().method()
    let data = { ok: true }, status = 200
    if (url.pathname === '/api/mission-control') data = snapshot
    else if (url.pathname === '/api/runs') data = { ok: true, runs: [], next_cursor: null }
    else if (url.pathname === '/api/sessions') data = { sessions: [] }
    else if (url.pathname.endsWith('/history')) data = { history: [] }
    else if (url.pathname === '/api/settings/llm') data = { effective_provider: 'Provedor de teste', effective_model: 'Modelo de demonstração' }
    else if (url.pathname === '/api/chat') { chatCalls++; data = { ok: true, reply: 'x' } }
    else if (url.pathname === '/api/finance') {
      const body = route.request().postDataJSON() || {}
      if (body.action === 'list') data = { ok: true, transactions: finance, totals: totals(), categories: [...new Set(finance.map(t => t.category))], truncated: false }
      else if (body.action === 'add') {
        if (failNextAdd) { failNextAdd = false; status = 500; data = { ok: false, error: 'Falha de teste ao gravar.' } }
        else { finance.unshift({ id: body.id, type: body.type, amount: body.amount, category: body.category || 'Outros', description: body.description, date_str: body.date }); data = { ok: true } }
      }
    }
    else if (url.pathname === '/api/controls/run') {
      const body = route.request().postDataJSON() || {}
      controlCalls.push(body)
      if (body.operation === 'get_brightness') {
        if (brightnessSupported) data = { ok: true, message: 'Brilho atual: 60%.', data: { brightness: 60 } }
        else { status = 200; data = { ok: false, message: '', error: 'Este monitor não expõe controle de brilho.' } }
      }
      else if (body.operation === 'set_brightness') data = { ok: true, message: `Brilho ajustado para ${body.level}%.`, data: { brightness: body.level } }
      else if (body.operation === 'lock_screen') { lockCalls++; data = { ok: true, message: 'Tela bloqueada.' } }
      else data = { ok: true, message: 'Feito.' }
    }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.routeWebSocket('**/ws/chat', socket => socket.close())
  await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')
  await page.getByRole('heading', { name: 'O que vamos fazer hoje?' }).waitFor()
  const composer = page.getByLabel('Mensagem para o agente')

  // Menu "/"
  await composer.fill('/')
  const menu = page.getByRole('listbox', { name: 'Comandos' })
  await menu.waitFor()
  await page.screenshot({ path: path.join(output, `${label}-menu-barra.png`) })
  await composer.fill('/fin')
  assert(await menu.getByRole('option').filter({ hasText: 'Finanças' }).count() >= 1)
  await page.screenshot({ path: path.join(output, `${label}-menu-barra-filtro-fin.png`) })
  await composer.fill('/con')
  assert(await menu.getByRole('option').filter({ hasText: 'Controles' }).count() >= 1)
  await composer.fill('')

  // Finanças: abre por /gastos (apelido), sem IA.
  await composer.fill('/gastos')
  await page.keyboard.press('Enter')
  const win = page.getByRole('dialog', { name: 'Finanças' })
  await win.waitFor()
  await win.getByText('Compras da semana').waitFor()
  await win.getByText('Modo manual', { exact: false }).waitFor()
  await page.screenshot({ path: path.join(output, `${label}-financas-lista.png`) })
  // Lançamento manual: primeira gravação falha, o rascunho fica, a segunda funciona.
  await win.getByLabel('Valor (R$)').fill('19,90')
  await win.getByPlaceholder('Outros').fill('Transporte')
  await win.getByLabel('Descrição').fill('Ônibus')
  await win.getByRole('button', { name: 'Salvar lançamento' }).click()
  await win.getByRole('alert').waitFor()
  await page.screenshot({ path: path.join(output, `${label}-financas-erro-rascunho.png`) })
  assert.equal(await win.getByLabel('Valor (R$)').inputValue(), '19,90')
  // Fecha e reabre: o rascunho volta.
  await page.keyboard.press('Escape')
  await win.waitFor({ state: 'detached' })
  await composer.fill('/financas')
  await page.keyboard.press('Enter')
  await win.waitFor()
  assert.equal(await win.getByLabel('Valor (R$)').inputValue(), '19,90')
  await win.getByRole('button', { name: 'Tentar novamente' }).or(win.getByRole('button', { name: 'Salvar lançamento' })).click()
  await win.getByText('Ônibus').first().waitFor()
  assert.equal(await win.getByLabel('Valor (R$)').inputValue(), '')
  await page.screenshot({ path: path.join(output, `${label}-financas-salvo.png`) })
  // Exclusão usa o diálogo do app.
  await win.getByRole('button', { name: 'Excluir lançamento de Mercado' }).click()
  await page.getByRole('alertdialog').or(page.getByRole('dialog').filter({ hasText: 'Excluir' })).first().waitFor()
  await page.screenshot({ path: path.join(output, `${label}-financas-confirmar-exclusao.png`) })
  await page.keyboard.press('Escape')
  await page.waitForTimeout(200)
  if (await win.count()) { await page.keyboard.press('Escape'); await page.waitForTimeout(200) }

  // Controles do PC
  if (await win.count()) await win.getByRole('button', { name: 'Fechar janela' }).click()
  await composer.fill('/controles')
  await page.keyboard.press('Enter')
  const pc = page.getByRole('dialog', { name: 'Controles do PC' })
  await pc.waitFor()
  await pc.getByText('Brilho atual: 60%.').waitFor()
  await page.screenshot({ path: path.join(output, `${label}-controles-pc.png`) })
  await pc.getByRole('slider').fill('30')
  await pc.getByRole('button', { name: 'Aplicar brilho' }).click()
  await pc.getByText('Brilho ajustado para 30%.').waitFor()
  await pc.getByRole('button', { name: /Bloquear/ }).first().click()
  await page.screenshot({ path: path.join(output, `${label}-controles-bloqueio-confirmar.png`) })
  assert.equal(lockCalls, 0, 'nada pode bloquear antes da confirmação')
  await page.keyboard.press('Escape')
  assert.equal(lockCalls, 0)
  assert(controlCalls.some(c => c.operation === 'set_brightness' && c.level === 30))
  assert.equal(chatCalls, 0, 'nenhuma chamada ao modelo')
  assert.deepEqual(errors, [])
  if (viewport.width <= 640) assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'overflow horizontal em 360px')
  await page.close()
  console.log(`PASS (${label}): menu /, Finanças (modo manual, rascunho, erro, reabrir, salvar, exclusão) e Controles do PC (brilho, bloqueio com confirmação), sem chat`)
}

;(async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    await run(browser, 'desktop', { width: 1536, height: 960 })
    await run(browser, 'mobile360', { width: 360, height: 844 })
  } finally {
    await browser.close()
  }
})().catch(error => { console.error(error); process.exit(1) })
