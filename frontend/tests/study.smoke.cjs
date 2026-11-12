// Run with PLAYWRIGHT_MODULE pointing to an installed playwright/playwright-core.
// Toda a API é interceptada por um servidor falso com estado: o teste nunca altera dados pessoais.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')
const { assertSourceHasNoBrokenText, assertPageHasNoBrokenText } = require('./broken-text.cjs')
const { mkdirSync } = require('node:fs')
const path = require('node:path')
const output = process.env.PANEL_TEST_OUTPUT || path.join(require('node:os').tmpdir(), 'study-smoke')
mkdirSync(output, { recursive: true })

const isoDay = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const lastDays = count => Array.from({ length: count }, (_, index) => {
  const date = new Date()
  date.setDate(date.getDate() - (count - 1 - index))
  return isoDay(date)
})

;(async () => {
  assertSourceHasNoBrokenText()
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
    page.setDefaultTimeout(20000)
    const errors = []
    page.on('pageerror', error => errors.push(error.message))

    const cards = [
      { id: 'c1', front: 'Quanto é 2 + 2?', back: '4', state: 'review' },
      { id: 'c2', front: 'Qual é a capital do Brasil?', back: 'Brasília', state: 'learning' },
    ]
    let dueCards = [...cards]
    const reviewed = []
    let vocabulary = [
      { id: 'v1', word: 'apple', translation: 'maçã', state: 'review' },
      { id: 'v2', word: 'book', translation: 'livro', state: 'learning' },
      { id: 'v3', word: 'house', translation: 'casa', state: 'new', due: '2999-01-01T00:00:00Z' },
    ]
    let dueVocab = vocabulary.slice(0, 2)
    const xp = { total_xp: 130, daily_xp: 30, daily_goal: 100, streak: 3, best_streak: 5, pomodoros: 0 }
    const reviewPosts = [], undoPosts = [], deletePaths = [], pomodoroPosts = []

    const level = () => {
      let n = 1
      while (50 * (n + 1) * n <= xp.total_xp) n++
      const threshold = k => 50 * k * (k - 1)
      return { level: n, name: ['Iniciante', 'Aprendiz', 'Estudante'][n - 1] || 'Dedicado', xp_into_level: xp.total_xp - threshold(n), xp_for_next: threshold(n + 1) - threshold(n), next_threshold: threshold(n + 1) }
    }
    const dashboard = () => ({
      today: isoDay(new Date()),
      due: { flashcards: dueCards.length, vocabulary: dueVocab.length, next_due_at: null },
      xp: { ...xp, goal_met: xp.daily_xp >= xp.daily_goal, studied_today: xp.daily_xp > 0, last_study_date: isoDay(new Date()) },
      level: level(),
      badges: [
        { id: 'first_review', label: 'Primeira revisão', description: 'Faça sua primeira revisão.', earned: true },
        { id: 'reviews_100', label: '100 revisões', description: 'Complete 100 revisões.', earned: false },
        { id: 'streak_7', label: 'Sequência de 7 dias', description: 'Estude 7 dias seguidos.', earned: false },
        { id: 'streak_30', label: 'Sequência de 30 dias', description: 'Estude 30 dias seguidos.', earned: false },
        { id: 'xp_1000', label: '1.000 XP', description: 'Acumule 1.000 XP.', earned: false },
        { id: 'pomodoro_10', label: '10 Pomodoros', description: 'Conclua 10 Pomodoros.', earned: false },
        { id: 'vocab_50', label: '50 palavras', description: 'Tenha 50 palavras no vocabulário.', earned: false },
      ],
    })
    const stats = () => {
      const heatmap = lastDays(371).map((date, index) => ({ date, reviews: index % 3 === 0 ? 4 : 0, xp: index % 3 === 0 ? [10, 30, 60, 120][index % 4] : 0 }))
      heatmap[heatmap.length - 1] = { date: heatmap[heatmap.length - 1].date, reviews: reviewed.length + 3, xp: xp.daily_xp }
      return {
        heatmap,
        daily_reviews: lastDays(30).map((date, index) => ({ date, tutor: index % 4, language: index % 3 })),
        retention: { rate: 0.85, correct: 17, total: 20, window_days: 30 },
        states: {
          tutor: { new: 0, learning: 1, review: 1, relearning: 0 },
          language: { new: 1, learning: 1, review: 1, relearning: 0 },
          total: { new: 1, learning: 2, review: 2, relearning: 0 },
        },
        totals: { reviews: 40, pomodoros: xp.pomodoros, vocabulary: vocabulary.length, flashcards: cards.length },
      }
    }
    const languageDashboard = () => ({
      cefr_level: 'A2', target_language: 'en', placement_done: true,
      stats: { total_vocab: 12, pronunciation_sessions: 4, conversation_sessions: 2, shadowing_sessions: 1 },
      due_vocabulary: dueVocab.length, weak_phonemes: [], streak: xp.streak, daily_xp: xp.daily_xp, daily_goal: xp.daily_goal, total_xp: xp.total_xp,
    })
    const addXp = amount => { xp.daily_xp = Math.max(0, xp.daily_xp + amount); xp.total_xp = Math.max(0, xp.total_xp + amount) }

    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url()), method = route.request().method(), pathname = url.pathname
      let data = { ok: true }, status = 200
      if (pathname === '/api/tutor/progress') data = { ok: true, progress: { current_stage: 'Preparação ENEM', stats: {} }, weak_spots: [] }
      else if (pathname === '/api/tutor/flashcards/due') data = { ok: true, cards: dueCards, next_due_at: null }
      else if (pathname === '/api/tutor/flashcards/review' && method === 'POST') {
        const body = route.request().postDataJSON()
        reviewPosts.push(body)
        const card = dueCards.find(item => item.id === body.card_id)
        dueCards = dueCards.filter(item => item.id !== body.card_id)
        reviewed.push(card)
        addXp(10)
      } else if (pathname === '/api/tutor/flashcards/undo' && method === 'POST') {
        undoPosts.push(pathname)
        const card = reviewed.pop()
        if (!card) { status = 404; data = { ok: false, error: 'nothing_to_undo' } }
        else { dueCards = [card, ...dueCards]; addXp(-10); data = { ok: true, card } }
      }
      else if (pathname === '/api/tutor/feynman') data = { ok: true, attempts: [] }
      else if (pathname === '/api/tutor/assessments') data = { ok: true, assessments: [] }
      else if (pathname === '/api/enem/questions') data = { ok: true, questions: [] }
      else if (pathname === '/api/sessions') data = { ok: true, sessions: [] }
      else if (pathname === '/api/study/categories') data = { ok: true, categories: [] }
      else if (pathname === '/api/study/trash') data = { ok: true, sessions: [] }
      else if (pathname === '/api/study/dashboard') data = dashboard()
      else if (pathname === '/api/study/stats') data = stats()
      else if (pathname === '/api/study/pomodoro' && method === 'POST') {
        pomodoroPosts.push(route.request().postDataJSON())
        xp.pomodoros++
        addXp(20)
        data = { ok: true, xp: dashboard().xp, level: level() }
      }
      else if (pathname === '/api/language/dashboard') data = languageDashboard()
      else if (pathname === '/api/language/vocabulary/due') data = { ok: true, cards: dueVocab, next_due_at: null }
      else if (pathname === '/api/language/pronunciation') data = { ok: true, history: [] }
      else if (pathname === '/api/language/vocabulary' && method === 'GET') data = { ok: true, cards: vocabulary }
      else if (/^\/api\/language\/vocabulary\/[^/]+\/delete$/.test(pathname) && method === 'POST') {
        deletePaths.push(pathname)
        const id = decodeURIComponent(pathname.split('/')[4])
        vocabulary = vocabulary.filter(item => item.id !== id)
        dueVocab = dueVocab.filter(item => item.id !== id)
      }
      else if (pathname === '/api/approvals') data = { ok: true, mode: { enabled: false, persist: false }, rules: [], durations: {} }
      else if (pathname === '/api/mission-control') data = { ok: true, components: [], summary: {}, goals: [], pending_actions: [], recent_actions: [] }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    })
    await page.routeWebSocket('**/ws/chat', socket => socket.close())
    await page.addInitScript(() => { localStorage.setItem('jarvis-active-screen', 'Estudos') })
    // Relógio falso (o tempo continua correndo): permite pular os 25 min do Pomodoro no passo 7.
    await page.clock.install()
    await page.goto(process.env.PANEL_TEST_URL || 'http://127.0.0.1:5173')

    // 1) Painel "Hoje"
    const today = page.locator('.study-today')
    await today.getByText('HOJE', { exact: true }).waitFor()
    await today.locator('span').filter({ hasText: /^2 flashcards para revisar$/ }).waitFor()
    await today.locator('span').filter({ hasText: /^2 palavras para revisar$/ }).waitFor()
    await today.getByText('🔥 3 dias seguidos').waitFor()
    await today.getByText('Nível 2 · Aprendiz').waitFor()
    await today.getByText('30/100 XP').waitFor()
    assert.equal(await today.getByRole('progressbar', { name: 'Meta diária de XP' }).getAttribute('aria-valuenow'), '30')
    await today.getByRole('button', { name: 'Revisar vocabulário' }).waitFor()
    await assertPageHasNoBrokenText(page)
    await page.screenshot({ path: path.join(output, 'study-dashboard.png') })
    console.log('PASS: painel Hoje com pendências, sequência, meta diária e nível')

    // 2) Revisão pelo teclado sem pular cartões
    await today.getByRole('button', { name: 'Revisar agora' }).click()
    const flashcard = page.locator('.flashcard')
    await flashcard.filter({ hasText: 'Quanto é 2 + 2?' }).waitFor()
    await page.keyboard.press('Space')
    await flashcard.filter({ hasText: 'RESPOSTA' }).waitFor()
    await page.keyboard.press('3')
    await flashcard.filter({ hasText: 'Qual é a capital do Brasil?' }).waitFor()
    assert.deepEqual(reviewPosts, [{ card_id: 'c1', grade: 2 }])
    await page.screenshot({ path: path.join(output, 'study-review-keyboard.png') })
    console.log('PASS: Espaço vira, 3 avalia como Bom e o próximo cartão aparece')

    // 3) Desfazer com Z
    await page.keyboard.press('z')
    await flashcard.filter({ hasText: 'Quanto é 2 + 2?' }).waitFor()
    assert.equal(undoPosts.length, 1)
    await page.screenshot({ path: path.join(output, 'study-undo.png') })
    console.log('PASS: Z desfaz e o cartão anterior volta')

    // 4) Progresso visual
    const toolbar = page.locator('.study-toolbar')
    await toolbar.getByRole('button', { name: /Progresso/ }).click()
    const progress = page.locator('.study-progress-panel')
    await progress.locator('.study-heatmap').waitFor()
    assert.equal(await progress.locator('.study-heatmap rect.hm-cell').count(), 371)
    assert.equal(await progress.locator('.study-bars rect.study-bar-bg').count(), 30)
    await progress.locator('.study-retention strong').filter({ hasText: /^85%$/ }).waitFor()
    await progress.getByText('17 de 20 revisões de cartões maduros').waitFor()
    await progress.locator('.study-state-legend b').filter({ hasText: /^Revisão$/ }).waitFor()
    await progress.locator('.study-badge.earned').filter({ hasText: 'Primeira revisão' }).waitFor()
    assert.equal(await progress.locator('.study-badge:not(.earned)').count(), 6)
    await assertPageHasNoBrokenText(page)
    await progress.screenshot({ path: path.join(output, 'study-progress.png') })
    console.log('PASS: mapa de calor (371 dias), barras de 30 dias, retenção, estados e conquistas')

    // 5) Idiomas → Progresso com os contadores reais
    await toolbar.getByRole('button', { name: /Idiomas/ }).click()
    const langToolbar = page.locator('.lang-toolbar')
    await langToolbar.getByRole('button', { name: /Progresso/ }).click()
    const langStat = label => page.locator('.lang-stat').filter({ has: page.locator('small', { hasText: new RegExp(`^${label}$`) }) }).locator('b')
    assert.equal(await langStat('palavras').innerText(), '12')
    assert.equal(await langStat('pronúncias').innerText(), '4')
    assert.equal(await langStat('conversas').innerText(), '2')
    assert.equal(await langStat('shadowings').innerText(), '1')
    await page.screenshot({ path: path.join(output, 'language-progress.png') })
    console.log('PASS: progresso de idiomas mostra palavras, pronúncias e conversas')

    // 6) Excluir palavra com o diálogo do app
    await langToolbar.getByRole('button', { name: /Vocabulário/ }).click()
    await page.getByRole('button', { name: 'Excluir apple', exact: true }).click()
    const dialog = page.getByRole('alertdialog', { name: 'Excluir palavra?' })
    await dialog.waitFor()
    await dialog.getByRole('button', { name: 'Excluir', exact: true }).click()
    await page.getByRole('button', { name: 'Excluir apple', exact: true }).waitFor({ state: 'detached' })
    assert.deepEqual(deletePaths, ['/api/language/vocabulary/v1/delete'])
    console.log('PASS: exclusão de palavra confirmada no diálogo')

    // 7) Pomodoro concluído vale XP uma única vez
    const dock = page.locator('.study-pomodoro-dock')
    await dock.getByRole('button', { name: 'Iniciar', exact: true }).click()
    await dock.getByRole('button', { name: 'Pausar', exact: true }).waitFor()
    await page.clock.fastForward('25:01')
    await page.getByText('Pomodoro concluído! +20 XP').waitFor()
    await page.waitForTimeout(1500)
    assert.deepEqual(pomodoroPosts, [{ minutes: 25 }])
    await toolbar.getByRole('button', { name: /Hoje/ }).click()
    await today.getByText('50/100 XP').waitFor()
    assert.equal(pomodoroPosts.length, 1)
    console.log('PASS: Pomodoro de 25 min registra XP uma vez e o painel atualiza')

    await assertPageHasNoBrokenText(page)
    assert.deepEqual(errors, [])
    console.log('PASS: estudos (Hoje, revisão por teclado, desfazer, progresso, idiomas, exclusão, Pomodoro). Screenshots: ' + output)
  } finally {
    await browser.close()
  }
})().catch(error => { console.error(error); process.exitCode = 1 })
