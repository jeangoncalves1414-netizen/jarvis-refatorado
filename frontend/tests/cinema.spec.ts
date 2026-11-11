import { test, expect, type Page } from '@playwright/test'

async function setup(page: Page) {
  await page.route('**/api/cinema/session/status/*', route => route.fulfill({ json: { ok: true, status: 'open', media: [], episodes: [] } }))
  await page.route('**/api/cinema/discovery/sources', route => route.fulfill({ json: { ok: true, sources: [{ id: 'plex', name: 'Plex' }, { id: 'disabled', name: 'Desativado', enabled: false }] } }))
  await page.route('**/api/cinema/search?**', route => {
    const params = new URL(route.request().url()).searchParams
    return route.fulfill({ json: { ok: true, results: [{ id: 'tt0133093', title: params.get('q'), type: params.get('type') === 'series' ? 'tv' : 'movie', year: '1999', description: 'Uma descoberta muda tudo.', genres: ['Ficção científica'] }] } })
  })
  await page.route('**/api/cinema/discovery/search?**', route => route.fulfill({ json: { ok: true, results: [{ title: 'Matrix no Plex', url: 'https://www.plex.tv/movie/matrix', source: 'plex.tv', snippet: 'Página do título na plataforma.' }, { title: 'URL inválida', url: 'javascript:alert(1)' }] } }))
  await page.route('**/api/cinema/discovery/probe', route => route.fulfill({ json: { ok: true, media: [{ url: 'https://media.example.com/matrix.mp4', label: 'MP4', direct: true }] } }))
  await page.route('**/api/cinema/library', route => route.fulfill({ json: { ok: true, items: [{ id: 'saved', title: 'Minha série salva', type: 'tv', episodes: [{ season: 1, episode: 2, sources: [{ url: 'https://media.example.com/episode2.mp4', label: '1080p' }] }] }] } }))
  await page.goto('/tests/cinema.html')
  await page.getByRole('button', { name: 'Abrir Cinema', exact: true }).click()
}

test('catalog to source to detected video requires an explicit playback choice', async ({ page }) => {
  await setup(page)
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await page.getByRole('button', { name: 'Matrix Filme · 1999' }).click()
  await expect(page.getByText('Uma descoberta muda tudo.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Onde assistir' })).toHaveAttribute('href', 'https://www.justwatch.com/br/busca?q=Matrix')
  const query = page.waitForRequest(req => req.url().includes('/discovery/search?'))
  await page.getByRole('button', { name: 'Buscar fontes deste título' }).click()
  expect(new URL((await query).url()).searchParams.get('scope')).toBe('web')
  await expect(page.getByRole('link', { name: 'Abrir site' })).toHaveAttribute('href', 'https://www.plex.tv/movie/matrix')
  await expect(page.getByText('URL inválida')).toHaveCount(0)
  await page.getByRole('button', { name: 'Detectar vídeos', exact: true }).first().click()
  await expect(page.getByRole('button', { name: 'Assistir', exact: true })).toBeVisible()
  await expect(page.getByTestId('played')).toHaveText('')
  await page.screenshot({ path: '../scratch/seekee-reference/cinema-desktop.png', fullPage: true })
  await page.getByRole('button', { name: 'Assistir', exact: true }).click()
  await expect(page.getByTestId('played')).toHaveText('https://media.example.com/matrix.mp4')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('search loads successive batches, deduplicates and saves the page limit', async ({ page }) => {
  await setup(page)
  const requested: number[] = []
  await page.route('**/api/cinema/discovery/search?**', async route => {
    const batch = Number(new URL(route.request().url()).searchParams.get('page'))
    requested.push(batch)
    if (batch === 2) await new Promise(resolve => setTimeout(resolve, 600))
    const offset = batch === 1 ? 0 : 10
    await route.fulfill({ json: { ok: true, results: Array.from({ length: 14 }, (_, i) => ({ title: `Resultado ${offset + i}`, url: `https://example.org/${offset + i}` })), next_page: batch + 1 } })
  })
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByLabel('Máximo de páginas').selectOption('2')
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await expect(page.getByText('Resultado 0', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Parar de carregar resultados' })).toBeVisible()
  await expect(page.locator('.cinema-status')).toContainText('24 resultados. Limite de 2 páginas atingido.')
  expect(requested).toEqual([1, 2])
  await page.getByRole('button', { name: 'Próxima', exact: true }).click()
  await expect(page.getByText('Resultado 23', { exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Abrir Cinema', exact: true }).click()
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await expect(page.getByLabel('Máximo de páginas')).toHaveValue('2')
})

test('repeated batches stop, and failed later batches preserve earlier results', async ({ page }) => {
  await setup(page)
  let calls = 0, failLater = false
  await page.route('**/api/cinema/discovery/search?**', route => {
    const batch = Number(new URL(route.request().url()).searchParams.get('page'))
    calls++
    if (failLater && batch > 1) return route.fulfill({ status: 503, json: { ok: false, error: 'Provedor indisponível.' } })
    return route.fulfill({ json: { ok: true, results: [{ title: 'Fonte preservada', url: 'https://example.org/matrix' }], next_page: batch + 1 } })
  })
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await expect(page.locator('.cinema-status')).toContainText('Busca concluída')
  expect(calls).toBe(3)
  failLater = true
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await expect(page.locator('.cinema-status')).toContainText('1 resultados preservados. Provedor indisponível.')
  await expect(page.getByText('Fonte preservada', { exact: true })).toBeVisible()
})

test('stopping additional batches retains results and ignores the late response', async ({ page }) => {
  await setup(page)
  await page.route('**/api/cinema/discovery/search?**', async route => {
    const batch = Number(new URL(route.request().url()).searchParams.get('page'))
    if (batch > 1) await new Promise(resolve => setTimeout(resolve, 800))
    await route.fulfill({ json: { ok: true, results: [{ title: `Fonte lote ${batch}`, url: `https://example.org/${batch}` }], next_page: batch + 1 } }).catch(() => {})
  })
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await expect(page.getByText('Fonte lote 1', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Parar de carregar resultados' }).click()
  await expect(page.locator('.cinema-status')).toContainText('1 resultados. Carregamento interrompido.')
  await page.waitForTimeout(1000)
  await expect(page.getByText('Fonte lote 2', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Fonte lote 1', { exact: true })).toBeVisible()
})

test('series, site filtering and local history survive reopening', async ({ page }) => {
  await setup(page)
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Dark')
  const series = page.waitForRequest(req => req.url().includes('/cinema/search?'))
  await page.getByRole('button', { name: 'Séries', exact: true }).click()
  expect(new URL((await series).url()).searchParams.get('type')).toBe('series')
  await expect(page.getByRole('button', { name: 'Dark Série · 1999' })).toBeVisible()
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await expect(page.getByLabel('Pesquisar em')).toHaveValue('web')
  const scoped = page.waitForRequest(req => req.url().includes('source=plex'))
  await page.getByLabel('Pesquisar em').selectOption('plex')
  expect(new URL((await scoped).url()).searchParams.get('scope')).toBe('approved')
  await expect(page.getByRole('option', { name: 'Desativado' })).toHaveCount(0)
  await page.reload()
  await page.getByRole('button', { name: 'Abrir Cinema', exact: true }).click()
  await expect(page.locator('.cinema-history')).toContainText('Dark')
  await page.getByRole('button', { name: 'Limpar histórico' }).click()
  await expect(page.locator('.cinema-history')).toHaveCount(0)
  await expect.poll(() => page.evaluate(() => localStorage.getItem('jarvis:cinema:search-history:v1'))).toBe('[]')
})

test('late responses cannot replace a newer search', async ({ page }) => {
  await setup(page)
  let finishOld!: () => void
  await page.route('**/api/cinema/search?**', async route => {
    const query = new URL(route.request().url()).searchParams.get('q')
    if (query === 'Antiga') await new Promise<void>(resolve => { finishOld = resolve })
    await route.fulfill({ json: { ok: true, results: [{ id: query, title: query, type: 'movie', year: '2026' }] } }).catch(() => undefined)
  })
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Antiga')
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await expect.poll(() => Boolean(finishOld)).toBe(true)
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Atual')
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Atual Filme · 2026' })).toBeVisible()
  finishOld()
  await expect(page.getByRole('button', { name: 'Antiga Filme · 2026' })).toHaveCount(0)
  await expect(page.locator('.cinema-status')).toContainText('1 resultados')
})

test('agent catalog retains series metadata and saved episodes still play', async ({ page }) => {
  await setup(page)
  await page.getByRole('button', { name: 'Fechar cinema' }).click()
  await page.getByRole('button', { name: 'Resultado do agente' }).click()
  await expect(page.getByRole('button', { name: 'Séries', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Série do agente Série · 2026' }).click()
  await expect(page.getByText('Sinopse preservada.')).toBeVisible()
  await page.getByRole('button', { name: 'Minha biblioteca' }).click()
  await page.locator('.cinema-library > select').first().selectOption('saved')
  await expect(page.locator('.library-controls')).toContainText('Episódio 2')
  await page.getByRole('button', { name: 'Reproduzir', exact: true }).click()
  await expect(page.getByTestId('played')).toHaveText('https://media.example.com/episode2.mp4')
})

test('errors can be retried, URLs are validated and Escape returns focus', async ({ page }) => {
  await setup(page)
  await page.route('**/api/cinema/search?**', route => route.fulfill({ status: 503, json: { ok: false, error: 'Catálogo indisponível.' } }))
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Pesquisar', exact: true }).click()
  await expect(page.locator('.cinema-status')).toHaveText('Catálogo indisponível.')
  await expect(page.getByRole('button', { name: 'Pesquisar', exact: true })).toBeEnabled()
  await page.getByText('Abrir por URL', { exact: true }).click()
  await page.getByLabel('URL de página ou vídeo').fill('javascript:alert(1)')
  await expect(page.getByRole('button', { name: 'Reproduzir URL direta' })).toBeDisabled()
  await page.getByLabel('URL de página ou vídeo').fill('https://example.org/watch')
  await expect(page.getByRole('button', { name: 'Reproduzir URL direta' })).toBeDisabled()
  await expect(page.getByTestId('played')).toHaveText('')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Abrir Cinema', exact: true })).toBeFocused()
})

test('anime discovery scans only the current page with bounded parallelism and verifies actual video', async ({ page }) => {
  await setup(page)
  await page.route('**/api/cinema/discovery/search?**', route => route.fulfill({ json: { ok: true, results: Array.from({ length: 13 }, (_, i) => ({ title: `Fonte ${i}`, url: `https://example.org/watch/${i}` })) } }))
  let active = 0, peak = 0
  const probed: string[] = [], fastProbes: boolean[] = []
  await page.route('**/api/cinema/discovery/probe', async route => {
    const payload = route.request().postDataJSON()
    const url = payload.url as string
    fastProbes.push(payload.fast === true)
    probed.push(url); active++; peak = Math.max(peak, active)
    await new Promise(resolve => setTimeout(resolve, 100))
    active--
    const media = url.endsWith('/0') ? [{ url: 'https://upstream.example/private.mp4', playback_url: '/tests/fixtures/cinema/clip.mp4', session_id: 'probe-session', direct: true }] : [{ url: 'https://example.org/iframe', direct: false }]
    await route.fulfill({ json: { ok: true, media, episodes: [] } })
  })
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Naruto')
  const anime = page.waitForRequest(request => request.url().includes('/discovery/search?'))
  await page.getByRole('button', { name: 'Animes', exact: true }).click()
  expect(new URL((await anime).url()).searchParams.get('q')).toContain('Naruto anime assistir online grátis')
  await page.getByLabel('Só vídeos compatíveis detectados nesta página').check()
  await expect(page.locator('.cinema-scan-progress')).toContainText('Verificação concluída: 12/12', { timeout: 20000 })
  expect(probed).toHaveLength(12)
  expect(fastProbes.every(Boolean)).toBe(true)
  expect(peak).toBeGreaterThan(1); expect(peak).toBeLessThanOrEqual(4)
  await expect(page.locator('.cinema-result-actions')).toHaveCount(1)
  await expect(page.getByText('Vídeo compatível verificado', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Próxima', exact: true }).click()
  await expect(page.getByLabel('Só vídeos compatíveis detectados nesta página')).not.toBeChecked()
  await expect(page.getByText('Fonte 12', { exact: true })).toBeVisible()
  expect(probed).toHaveLength(12)
  await page.getByLabel('Só vídeos compatíveis detectados nesta página').check()
  await expect(page.locator('.cinema-scan-progress')).toContainText('Verificação concluída: 1/1')
  expect(probed[12]).toBe('https://example.org/watch/12')
})

test('batch scanning respects the selected 50-site limit', async ({ page }) => {
  await setup(page)
  await page.route('**/api/cinema/discovery/search?**', route => route.fulfill({ json: { ok: true, results: Array.from({ length: 70 }, (_, i) => ({ title: `Site ${i}`, url: `https://example.org/${i}` })) } }))
  const probed: string[] = []
  await page.route('**/api/cinema/discovery/probe', route => {
    probed.push(route.request().postDataJSON().url)
    return route.fulfill({ json: { ok: true, media: [], episodes: [], status: 'unconfirmed' } })
  })
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await expect(page.locator('.cinema-status')).toContainText('70 resultados')
  await page.getByLabel('Quantidade a verificar').selectOption('50')
  await page.getByLabel('Só vídeos compatíveis detectados nesta página').check()
  await expect(page.locator('.cinema-scan-progress')).toContainText('Verificação concluída: 50/50')
  expect(new Set(probed).size).toBe(50)
  expect(probed).not.toContain('https://example.org/50')
})

test('compatibility scan keeps pending cards visible until each page is checked', async ({ page }) => {
  await setup(page)
  let release!: () => void
  await page.route('**/api/cinema/discovery/probe', async route => {
    await new Promise<void>(resolve => { release = resolve })
    await route.fulfill({ json: { ok: true, media: [], episodes: [], status: 'unconfirmed' } })
  })
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByLabel('Só vídeos compatíveis detectados nesta página').check()
  await expect(page.getByText('Verificando player nesta página…', { exact: true })).toBeVisible()
  await expect(page.getByText('Matrix no Plex', { exact: true })).toBeVisible()
  release()
  await expect(page.locator('.cinema-scan-progress')).toContainText('Verificação concluída: 1/1')
  await expect(page.getByText('Matrix no Plex', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Mostrar 1 não confirmados nesta página' }).click()
  await expect(page.getByText('Matrix no Plex', { exact: true })).toBeVisible()
})

test('detected seasons and episodes survive selecting an episode and custom domains are forwarded', async ({ page }) => {
  await setup(page)
  await page.route('**/api/cinema/discovery/probe', route => route.fulfill({ json: { ok: true, media: [], episodes: [{ season: 1, episode: 2, title: 'Dois', url: 'https://example.org/s01e02' }, { season: 2, episode: 3, title: 'Três', url: 'https://example.org/s02e03' }] } }))
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Anime')
  await page.getByRole('button', { name: 'Animes', exact: true }).click()
  await page.getByLabel('Filtrar por domínio').fill('animesonlinecc.to')
  const filtered = page.waitForRequest(request => request.url().includes('source=domain'))
  await page.getByRole('button', { name: 'Buscar neste site' }).click()
  expect(new URL((await filtered).url()).searchParams.get('source')).toBe('domain:animesonlinecc.to')
  await page.getByRole('button', { name: 'Detectar vídeos', exact: true }).first().click()
  await page.getByLabel('Temporada detectada').selectOption('2')
  const episode = page.waitForRequest(request => request.url().endsWith('/probe'))
  await page.getByRole('button', { name: 'Detectar episódio 3' }).click()
  expect((await episode).postDataJSON().url).toBe('https://example.org/s02e03')
  await expect(page.getByLabel('Temporada detectada')).toBeVisible()
  await expect(page.getByLabel('Temporada detectada')).toHaveValue('2')
})

test('desktop modal is wide, and mobile viewport has no horizontal overflow', async ({ page }) => {
  await setup(page)
  const desktop = await page.locator('.cinema-search-workspace').boundingBox()
  expect(desktop!.width).toBeGreaterThan(1000)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.locator('.cinema-search-workspace').evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
})

test('HLS player discovers resolution, audio tracks and episode controls', async ({ page }) => {
  await setup(page)
  await page.getByRole('button', { name: 'Fechar cinema' }).click()
  await page.getByRole('button', { name: 'Testar player HLS' }).click()
  await expect(page.getByLabel('Resolução')).toContainText('90p')
  await expect(page.getByLabel('Áudio / dublagem')).toContainText('Português')
  await page.getByLabel('Áudio / dublagem').selectOption('1')
  await expect(page.getByLabel('Áudio / dublagem')).toHaveValue('1')
  await page.getByLabel('Resolução').selectOption('0')
  await expect(page.getByLabel('Resolução')).toHaveValue('0')
  await page.getByRole('button', { name: 'Episódios', exact: true }).click()
  await page.getByLabel('Selecionar episódio').getByRole('button', { name: '3', exact: true }).click()
  await expect(page.getByTestId('played')).toHaveText('T2E3')
})


test('site session opens from the page URL and can be closed without starting the detached player', async ({ page }) => {
  await setup(page)
  const opened: string[] = [], closed: string[] = []
  await page.route('**/api/cinema/session/open', route => {
    opened.push(route.request().postDataJSON().url)
    return route.fulfill({ json: { ok: true, session_id: 'session-test', message: 'Sessão aberta. Use o player nessa janela.' } })
  })
  await page.route('**/api/cinema/session/close', route => {
    closed.push(route.request().postDataJSON().session_id)
    return route.fulfill({ json: { ok: true } })
  })
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByRole('button', { name: 'Abrir sessão do site', exact: true }).first().click()
  await expect(page.getByText('Sessão aberta. Use o player nessa janela.', { exact: true })).toBeVisible()
  expect(opened).toHaveLength(1)
  await expect(page.getByTestId('played')).toHaveText('')
  await page.getByRole('button', { name: 'Fechar sessão', exact: true }).click()
  expect(closed).toEqual(['session-test'])
  await expect(page.getByRole('button', { name: 'Fechar sessão', exact: true })).toHaveCount(0)
})

test('probe timeout is shown as inconclusive and session failures allow retry', async ({ page }) => {
  await setup(page)
  await page.route('**/api/cinema/discovery/probe', route => route.fulfill({ json: { ok: true, media: [], episodes: [], status: 'timeout', message: 'O site demorou a responder. A verificação não foi concluída.' } }))
  await page.route('**/api/cinema/session/open', route => route.fulfill({ status: 400, json: { ok: false, error: 'Feche uma sessão antes de abrir outra.' } }))
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByRole('button', { name: 'Detectar vídeos', exact: true }).first().click()
  await expect(page.locator('.cinema-status')).toContainText('A verificação não foi concluída')
  await page.getByRole('button', { name: 'Abrir sessão do site', exact: true }).first().click()
  await expect(page.locator('.cinema-status')).toContainText('Feche uma sessão')
  await expect(page.getByRole('button', { name: 'Abrir sessão do site', exact: true }).first()).toBeEnabled()
})

test('session media uses a local relay, saves the source page and removes closed sessions', async ({ page }) => {
  await setup(page)
  let closed = false
  const source = 'https://www.plex.tv/movie/matrix'
  const relay = '/api/cinema/session/media/session-test/resource-test'
  await page.route('**/api/cinema/session/open', route => route.fulfill({ json: { ok: true, session_id: 'session-test', message: 'Sessão aberta.' } }))
  await page.route('**/api/cinema/session/status/*', route => route.fulfill({ json: { ok: true, status: closed ? 'closed' : 'open', page_url: source, media: [{ url: relay, kind: 'HLS', direct: true, session_id: 'session-test', source_url: source }], episodes: [] } }))
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByRole('button', { name: 'Abrir sessão do site', exact: true }).first().click()
  await expect(page.getByText('plex.tv · 1 fontes capturadas', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Ver vídeos da sessão' }).click()
  await expect(page.locator('.detected-media')).toContainText('http://127.0.0.1:5178' + relay)
  await expect(page.locator('.cinema-result-hint').first()).toContainText('Selecione Assistir')
  await page.getByRole('button', { name: 'Selecionar para salvar' }).click()
  const saved = page.waitForRequest(request => request.url().endsWith('/cinema/library') && request.method() === 'POST')
  await page.getByRole('button', { name: 'Salvar na biblioteca', exact: true }).click()
  expect((await saved).postDataJSON().url).toBe(source)
  closed = true
  await expect(page.getByRole('button', { name: 'Fechar sessão', exact: true })).toHaveCount(0, { timeout: 6000 })
})

test('session diagnostics replace stale availability hints when no stream is captured', async ({ page }) => {
  await setup(page)
  const message = 'Player de vídeo encontrado, mas nenhuma fonte compatível foi capturada.'
  await page.route('**/api/cinema/session/open', route => route.fulfill({ json: { ok: true, session_id: 'diagnostic', message: 'Sessão aberta.' } }))
  await page.route('**/api/cinema/session/status/*', route => route.fulfill({ json: { ok: true, status: 'open', media: [], episodes: [], message } }))
  await page.getByLabel('Pesquisar filmes, séries ou sites').fill('Matrix')
  await page.getByRole('button', { name: 'Sites', exact: true }).click()
  await page.getByRole('button', { name: 'Abrir sessão do site', exact: true }).first().click()
  await page.getByRole('button', { name: 'Ver vídeos da sessão' }).click()
  await expect(page.locator('.cinema-status')).toContainText(message)
  await expect(page.locator('.cinema-result-hint').first()).toContainText(message)
  await expect(page.locator('.detected-media')).toHaveCount(0)
})
