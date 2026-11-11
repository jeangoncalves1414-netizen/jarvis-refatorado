# Item 1: evidências da entrega do novo painel no desktop

Segunda iteração. Corrige os achados de `review-item1.json` e aplica as decisões da usuária de 2026-11-07, recebidas durante o trabalho. Branch `main`, sem worktree.

**Commits do item:**

- `fe25fd8` (`fix: separar build web da cópia para Android e mostrar versão do painel`), primeira iteração.
- `fc5f703` (`fix: tirar a Orbe dos gates de build e marcar pacote com alterações locais`), esta iteração.

## Achados da revisão e o que foi feito

| Achado | Resolução |
|---|---|
| 1. `build_mobile_jarvis.ps1 -RebuildWeb` sem verificação da Orbe (bloqueante) | Resolvido pela decisão da usuária: a Orbe não bloqueia mais nenhum build. A verificação saiu de `sync-mobile-assets.js`, então os três caminhos de APK ficam iguais e nenhum verifica a Orbe. `build_mobile_jarvis.ps1` não foi alterado. A afirmação errada da primeira iteração, de que "o fluxo do APK mantém a verificação", foi corrigida em [conflicts.md](conflicts.md). |
| 2. Teste de igualdade `dist`/assets vermelho localmente | Decisão da usuária: `test_mobile_assets_match_frontend_dist` ganhou o marcador `mobile_release`, excluído por padrão no `addopts` de `pyproject.toml`. Roda com `-m mobile_release` ao gerar o APK. |
| 3. Texto da regra canônica desatualizado | Decisão da usuária: `.agents/rules/jarvis_visual_canonical.md` marcado como OBSOLETO desde 2026-11-07, com o motivo e a única regra válida (assets Android só por `npm run build:mobile`). O texto original ficou abaixo, como histórico. |
| 4. Referências obsoletas a `postbuild.js` | `docs/PENDENCIAS_DO_PAINEL.md`, item 1: o texto descreve o estado atual e o link aponta para `sync-mobile-assets.js`. `docs/PROJECT_CONTINUITY.md:253` e `plans/016-neutral-agent-control-platform.md` (o rótulo da tabela de verificação, o parágrafo após a tabela e a regra das linhas 273-275) agora dizem que `npm run build` não toca `mobile_app/` e que `build:mobile` substitui os assets rastreados. As entradas antigas do registro histórico em `PROJECT_CONTINUITY.md`, nas linhas 42, 70 e 93, ficaram como estavam. |
| 5. Hash sem marca de árvore suja | `vite.config.ts` roda `git status --porcelain -- .` em `frontend/`. Se houver alteração não commitada ou arquivo novo não ignorado, `__PANEL_BUILD__.dirty` vira `true`. A linha mostra `fc5f703*`, e o `title` diz "commit fc5f703 com alterações não commitadas". A checagem cobre só `frontend/`, porque o pacote vem só dali e a raiz sempre tem arquivos não rastreados, como `.agents/tasks/`. Não usei `git describe`, porque o repositório tem tags (`v-mobile-stable` e outras) e a saída deixaria de ser o hash curto. |

## Arquivos do commit `fc5f703`

- `frontend/scripts/sync-mobile-assets.js`: removida a verificação da Orbe. O script só copia o `dist` para os assets Android.
- `scripts/build_mobile_apk.ps1` e `.bat`: a mensagem de erro deixou de citar a Orbe.
- `frontend/vite.config.ts`, `frontend/src/vite-env.d.ts`, `frontend/src/components/AppShell.tsx`: marca `*` de árvore suja.
- `pyproject.toml`, `tests/test_orb_canonical_integrity.py`: marcador `mobile_release`.
- `.agents/rules/jarvis_visual_canonical.md`: cabeçalho de OBSOLETA.
- `docs/PENDENCIAS_DO_PAINEL.md`, `docs/PROJECT_CONTINUITY.md`, `plans/016-neutral-agent-control-platform.md`: referências atualizadas.

## Comandos e resultados (depois do commit `fc5f703`)

| Verificação | Comando | Resultado |
|---|---|---|
| TypeScript | `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` (em `frontend`) | Passou, exit 0 |
| Sintaxe dos scripts | `node --check scripts/sync-mobile-assets.js` e o parser do PowerShell em `build_mobile_apk.ps1` e `build_mobile_jarvis.ps1` | 0 erros |
| Testes da Orbe, execução padrão | `python -B -m pytest -q -p no:cacheprovider tests/test_orb_canonical_integrity.py` | 4 passaram, 1 desmarcado (`mobile_release`), exit 0 |
| Opt-in do teste de igualdade | o mesmo com `-m mobile_release` | Roda só esse teste e falha, como esperado, porque os assets Android ainda são do pacote antigo. Passará depois de `npm run build:mobile`. |
| Coleta da suíte padrão | `python -B -m pytest -q -p no:cacheprovider --collect-only` | 361 de 385 coletados, 24 desmarcados. A configuração de marcadores carregou sem erro. |
| Build web | `npm run build` (em `frontend`), de 19:12:01 a 19:13:01. Log em `%TEMP%\desktop-batch1-build2.log` | Passou, exit 0, `built in 47.67s`. O log não cita Orbe, sincronização nem `mobile_app`. A única linha de stderr é um aviso de configuração do npm (`npm warn Unknown ... config`). |
| `mobile_app/` intocado | snapshot (caminho, tamanho, mtime) de `mobile_app/app/src/main/assets` antes e depois do build, mais `git status --porcelain -- mobile_app` | 86 arquivos antes e 86 depois, 0 diferenças. `git status` não mostra nada em `mobile_app/`. |
| Strings do bundle | `Select-String` nos 76 JS de `frontend/dist/assets` | `Ver execu`: `ChatPage-DNcxyLBm.js`. `/api/runs`: `MissionControlPage-BQbNGVbL.js`. `Execução por etapas`: ChatPage e MissionControlPage. `ws-build-version`: `index-6QouVoUz.js`. **`Dev Hacker`: ausente.** |
| Versão no bundle | regex em `index-6QouVoUz.js` | `version:"0.1.0",commit:"fc5f703",builtAt:"2026-11-07T22:12:13.589Z"`. O esbuild eliminou `dirty:false` e reduziu o rótulo a `${commit}`, o que confirma que a árvore estava limpa no build. |
| Versão na UI buildada | Playwright em `vite preview` (127.0.0.1:4173), APIs respondendo 503, service worker bloqueado, lendo `.ws-sidebar .ws-build-version` | Texto `v0.1.0 · fc5f703 · 07/11/2026`. Title `Versão do painel 0.1.0, commit fc5f703, gerada em 07/11/2026, 19:12:13`. |
| Árvore limpa, suja e sem git | `vite.loadConfigFromFile` em `frontend`: (a) árvore limpa; (b) com um arquivo temporário `frontend/dirty-probe.txt`, apagado em seguida; (c) com o PATH só de node e Windows (`where git` não achou nada) | (a) `commit:"fc5f703", dirty:false`. (b) `dirty:true`. (c) `commit:"", dirty:false`, e o config carregou normalmente, então `npm run dev` não quebra sem git. No fim, `git status -- frontend` estava vazio. |
| Smoke do workspace contra o **dist** | `PANEL_TEST_URL=http://127.0.0.1:4173/ PANEL_TEST_OUTPUT=<screenshots> node tests/workspace.smoke.cjs` | Passou em todos os blocos: render, chat e modo, aprovações 410, objetivo 500, filtros, linha do tempo, desconexão, paleta e layout de 360/390 px. |
| Smoke de pedidos contra o **dist** | `PANEL_TEST_URL=http://127.0.0.1:4173/ node tests/runs.smoke.cjs` | Passou, exit 0 |

Nos dois smoke tests, todas as APIs são simuladas. O backend real (`python -m app.main`) não foi iniciado, e nenhum dado pessoal ou journal foi lido ou migrado. A prévia (PID 6488) foi encerrada no fim.

Uma primeira tentativa de rodar os dois smokes em sequência, com a saída passando por um pipe do PowerShell, estourou o limite de 5 minutos sem mostrar nada. Rodando cada um como processo separado, com a saída em arquivo, os dois terminaram em menos de 1 minuto. O Playwright sozinho abriu a prévia em 1,4 s. A causa provável é o pipe, e não o painel.

## Capturas

Todas estão em `c:/Users/maria/Desktop/Jarvis/.agents/tasks/desktop-batch1/screenshots/` e foram regeneradas às 19:19 a partir do bundle de `fc5f703`, servido por `vite preview`:

- `desktop-chat.png` é a principal. Mostra o shell novo (Workspace, Conversas, Execuções, Controle do agente) e, no rodapé da barra lateral, `v0.1.0 · fc5f703 · 07/11/2026`.
- `desktop-executions.png`, `mobile-360.png`, `mobile-390.png` e `mobile-timeline-360.png` vêm de `workspace.smoke.cjs`.
- `desktop-request-cancelling.png` e `mobile-request-360.png` vêm de `runs.smoke.cjs`, que grava em `%TEMP%\agent-workspace-review`. Copiei os arquivos para cá.

## Não testado

- O app desktop pelo caminho normal (pywebview em `http://127.0.0.1:8000/app/`), porque isso exigiria subir o backend real. Ele serve `frontend/dist/index.html` (`server.py:199-200`), que agora é o build de `fc5f703`.
- `npm run build:mobile`, `build_mobile_apk.*` e `build_mobile_jarvis.ps1`, porque alteram `mobile_app/`. Os assets Android e o APK continuam com o pacote antigo.

## Observações

- `/clima` e "Ações Rápidas" continuam no bundle porque ainda existem no código atual (`ChatComposer.tsx` e `CommandPalette.tsx`). O critério do item exigia só a ausência de `Dev Hacker`.
- `docs/FEATURE_ROADMAP_AND_REFERENCE_ANALYSIS.md` ainda chama a Orbe de canônica. Está registrado em [conflicts.md](conflicts.md) e não foi alterado.
- `docs/DECISOES_E_IDEIAS.md` continua não rastreado. Não alterei esse arquivo nem fiz stage dele.
- Os arquivos de `.agents/tasks/desktop-batch1/` continuam não rastreados, como na primeira iteração.
