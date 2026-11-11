# Relatório do lote 2 (para revisão externa)

Data: 2026-11-07. Repositório: `c:\Users\maria\Desktop\Jarvis`, branch `main`, sem push. Este relatório descreve o que foi feito e verificado. Nenhum code review foi feito: a revisão é da usuária, com outra IA. Evidência por item em `item1-evidence.md` a `item6-evidence.md` nesta pasta (fora do git).

## 1. Commits (do mais antigo ao mais novo)

Lote 1:
- `fe25fd8` fix: separar build web da cópia para Android e mostrar versão do painel.
- `fc5f703` fix: tirar a Orbe dos gates de build e marcar pacote com alterações locais.
- `c8615cb` fix: classificar risco das ferramentas de controle por operação.
- `36bbb35` fix: corrigir alcance da UI e permitir remover dispositivo da ponte pelo PC.

Lote 2:
- `4a54bc3` fix: abrir apps sem shell e exigir aprovação para alvo desconhecido (item 1).
- `beb907f` feat: perfil do agente configurável e neutro nos prompts e na frase de ativação (item 2).
- `692af1b` feat: sincronização total com a nuvem, mesclagem por campo, backend no snapshot, chaves mascaradas (item 3).
- `75f94b9` feat: registro único de comandos com paleta e menu `/` sem IA (item 4).
- `366e799` feat: sistema de janelas, módulo Finanças e ferramenta `open_window` (item 5).
- `0d9293e` feat: janela Controles do PC (brilho, bloqueio de tela, volume e mídia) (item 6).
- `c6dc5c3` fix: menu `/` não pula opção quando a lista rola sob o mouse (regressão achada na etapa final).
- `21d9e12` docs: registrar lotes 1 e 2, pendências e decisões entregues (`docs/PROJECT_CONTINUITY.md`, `docs/PENDENCIAS_DO_PAINEL.md`, `docs/DECISOES_E_IDEIAS.md`, este último passou a ser rastreado).

## 2. O que mudou por item (arquivos-chave)

**Item 1 (4a54bc3).** `app_manager` abre aplicativos sem shell; alvo desconhecido exige aprovação. Testes em `tests/test_app_manager.py`.

**Item 2 (beb907f).** Perfil do agente (nome, estilo, frase de ativação) nas runtime settings, neutro por padrão ("Assistente", "ei assistente"). Prompts do desktop e do chat móvel montados a partir dele; frase recusada se tiver palavra fora do vocabulário do detector Vosk. Arquivos: `app/storage/runtime_settings.py`, `app/agent/prompts.py`, `app/ui/panel/api/settings.py`, `frontend/src/pages/SettingsPage.tsx`. Testes: `tests/test_agent_profile.py`.

**Item 3 (692af1b).** Decisão da usuária: tudo sincroniza com o Supabase dela, inclusive chaves de API (proteção: login + RLS da migração `202609200001`; nenhuma tabela nova).
- `frontend/src/utils/syncMerge.ts` (novo, funções puras): mescla campo a campo, vazio nunca vence preenchido, no mesmo campo vence o carimbo mais recente (empate: este dispositivo), máscara de segredos (4 últimos caracteres) e `redactForLog`.
- `frontend/src/utils/jarvisCloud.ts`: chaves/provedor/modelos viram campos carimbados em `vault.fields`; campos legados (`keys`, `provider`...) continuam gravados para o APK antigo; carimbos só mudam quando o conteúdo muda; até 3 tentativas em conflito de revisão; `console.log` de segredos removidos.
- `app/storage/backend_sync.py` (novo): `collect_snapshot`, `merge_snapshots`, `apply_snapshot`, `sync_with_remote`. Cobre configurações, chaves, perfil, memórias, preferências, tarefas, metas, notas do cofre e `lifestyle.db` (hábitos, rotina, finanças).
- `app/ui/panel/api/settings.py`: `GET /api/settings/sync-snapshot`, `POST /api/settings/sync-merge`.
- Aviso para a usuária: a chave da Fish Audio exposta em export antigo continua precisando ser trocada.

**Item 4 (75f94b9).** `frontend/src/commands/registry.ts` (registro único: id, rótulo, apelidos, palavra do `/`, grupo, ação tipada, `worksOffline`). `CommandPalette.tsx` montada dele (todas as entradas antigas mantidas, mais Modo Pesquisa, Modo Planejamento, Perguntar o clima). `WorkspaceComposer.tsx`: menu `/` com busca, setas, Enter/Tab, Esc e mouse; comando reconhecido roda local e não vai ao modelo; `/xyz` mostra dica e não envia. Comandos antigos do commit `90a759a` restaurados (`/clima`, `/pesquisa`, `/planejar`, `/visao`, `/estudos`, `/cinema`).

**Item 5 (366e799).** `frontend/src/windows/` (`registry.ts`, `WindowManager.tsx`, `FinanceWindow.tsx`), `ConfirmDialog.tsx`, `windows.css`. Janelas arrastáveis, redimensionáveis, maximizáveis, Esc fecha a focada, folha em tela cheia em largura <= 640 px. Finanças: lista com filtros e totais vindos da API, adicionar/editar/excluir (diálogo do app), rascunho em `localStorage` mantido até o servidor confirmar, indicador "Modo manual" quando `providers` não está saudável. Backend: `app/services/finance.py` (`normalize_entry`, `query_transactions`, `update_transaction`), `/api/finance` em `app/ui/panel/api/routes/system_routes.py` (ações `list` e `update`; `add` valida), `app/agent/tools/open_window.py` (ferramenta, só ids do registro, parâmetros validados, risco `observe`), registro em `registry.py`/`catalog.py`, `orchestrator.py` expõe `context.tool_results.open_window`, `useChat.ts` abre a janela pelo canal existente.

**Item 6 (0d9293e).** `app/agent/tools/system_control.py`: `get_brightness` (observe), `set_brightness` 0-100 (low), `lock_screen` (low), via PowerShell/WMI e `rundll32.exe user32.dll,LockWorkStation`, `shell=False`; não suportado retorna `ok: false`. `app/ui/panel/api/controls.py` (novo): `POST /api/controls/run`, 9 operações permitidas, executa pelo `ActionExecutor` e aparece na Central. `frontend/src/windows/PcControlsWindow.tsx`, comando `/controles`, janela `pc-controls` também em `open_window`. `tests/test_tools_smoke.py` passou a simular a tecla de mudo.

**Etapa final (c6dc5c3).** O smoke `workspace.smoke.cjs` revelou que, no menu `/`, a seleção por setas pulava de 2 em 2: ao rolar a lista, o item que passava sob o ponteiro parado disparava `onMouseEnter`. Troquei por `onMouseMove` em `WorkspaceComposer.tsx` (uma linha).

## 3. Resultados de verificação

| Verificação | Resultado |
| --- | --- |
| pytest, união de arquivos (ver abaixo) | **330 passed, 1 deselected**, 3 avisos de depreciação (aifc, audioop, OpenTelemetry) |
| `tsc --noEmit -p tsconfig.json` | sem erros |
| `frontend/tests/workspace.smoke.cjs` contra Vite em 5173 | PASS (9 blocos; falhou uma vez antes da correção c6dc5c3: `4 !== 2` na navegação por setas) |
| `frontend/tests/runs.smoke.cjs` | PASS |
| Roteiro novo `windows.shots.cjs` (desktop 1536x960 e 360x844) | PASS nos dois: menu `/`, `/gastos`, modo manual, falha de gravação com rascunho mantido, reabrir restaura, salvar, exclusão com diálogo, `/controles`, aplicar brilho, bloqueio só após confirmação, 0 chamadas ao chat, sem overflow horizontal em 360 px |
| `npm run build` (web-only) | passou em ~44 s; só o aviso já existente de chunks > 800 kB |
| `git status` em `mobile_app\` | nada alterado (`build:mobile` não foi executado) |

**Por que não rodei a suíte inteira.** O `tests/conftest.py` só isola o journal de ações e as tarefas. `tests/smoke_test.py` e `stress_test.py` são suítes de integração/hardware/rede, e há testes antigos (`test_habits_tasks_finance.py`) que escrevem em `data/lifestyle.db` real e limpam depois. Por segurança usei a união abaixo.

Comando: `python -B -m pytest -q -p no:cacheprovider --tb=short` sobre 25 arquivos: `test_action_kernel, test_agent_profile, test_app_manager, test_backend_cloud_sync, test_control_plane_security, test_device_bridge, test_habits_tasks_finance, test_open_window, test_orb_canonical_integrity, test_pc_controls, test_tool_catalog, test_tools_smoke, test_runtime_settings_sync, test_evolute_sync, test_settings_api, test_orchestrator, test_chat, test_conversation_runtime, test_runs, test_action_history, test_orchestrator_action_results, test_mission_control, test_native_action_boundary, test_guardrails_thread_safety, test_system_control_security` (todos em `tests/`). O item deselecionado é `test_backup_apk_exists_and_fresh` (em `test_orb_canonical_integrity.py`; o pytest o exclui da execução padrão, não investiguei a configuração). Não houve falhas anteriores ao lote nem teste enfraquecido. `tests/smoke_test.py` (alterado no lote 1) não foi executado por ser de integração/hardware.

Screenshots em `.agents\tasks\desktop-lote2\screenshots\`: `desktop-menu-barra.png`, `desktop-menu-barra-filtro-fin.png`, `desktop-financas-lista.png`, `desktop-financas-erro-rascunho.png`, `desktop-financas-salvo.png`, `desktop-financas-confirmar-exclusao.png`, `desktop-controles-pc.png`, `desktop-controles-bloqueio-confirmar.png` e as versões `mobile360-*` equivalentes, mais as dos smoke tests (`desktop-slash-menu.png`, `desktop-slash-unknown.png`, `mobile-*`). O script `windows.shots.cjs` está nesta pasta (não está no git) e usa só APIs simuladas.

Processo: o servidor Vite foi iniciado em segundo plano e encerrado (porta 5173 livre ao final).

## 4. Decisões tomadas sem perguntar (opção conservadora)

- Sincronização: união sem propagar remoções (um item apagado pode voltar); limpar uma chave de propósito não se propaga; chave diferente no mesmo provedor vence a mais recente (não une listas); notas: vence `mtime` mais recente e a versão local substituída vai para `data/vault/.conflitos/`; limite de 500 notas de até 512 KB; valores inválidos vindos da nuvem são ignorados.
- Menu `/`: todo texto que começa com `/` é tratado como comando; `/clima` e `/pesquisa tema` só preparam o compositor, sem enviar.
- `open_window`: se há rascunho de Finanças, ele vence o pré-preenchimento do agente; o agente nunca grava um lançamento.
- Controles: bloqueio de tela tem risco `low` mas a janela pede confirmação do app; brilho só é aplicado no botão; não há número de volume (o Windows não informa); ler brilho ao abrir cria um registro `observe` na Central a cada abertura.
- Etapa final: o roteiro `windows.shots.cjs` foi criado só para esta verificação e não entrou no git, para não ampliar o escopo do repositório. Se a usuária quiser, ele pode virar teste em `frontend/tests/`.

## 5. Riscos e pontos quentes (revisar primeiro)

1. **`app_manager` abrir/fechar** (`4a54bc3`): aprovação para alvo desconhecido, ausência de shell e como o alvo é resolvido. Testes com subprocess simulado; nunca abri apps reais.
2. **Mesclagem da sincronização** (`frontend/src/utils/syncMerge.ts`, `jarvisCloud.ts`, `app/storage/backend_sync.py`, `app/storage/runtime_settings.py` `_write`/`_field_ts`): carimbos por campo, impressão digital em `jarvis_stamp_state`, restauração das chaves, tratamento de conflito de revisão e o caminho do APK antigo (`fieldsFromLegacyVault`). É o ponto de maior risco de perda silenciosa de dados. Atenção a hábitos (sem `updated_at`) e a exclusões (sem lápide).
3. **Ferramenta `open_window`** (`app/agent/tools/open_window.py`, espelho em `frontend/src/windows/registry.ts`): os dois registros precisam ficar iguais; validação de parâmetros; `ui_window` só sai para ids conhecidos; `useChat.ts` abre a janela só com `ok: true`.
4. **Endpoint de controles** (`app/ui/panel/api/controls.py`, `system_control.py`): lista fixa de 9 operações, validação de `level`, execução só pelo `ActionExecutor`, comando PowerShell fixo, estado `pending` (202) se uma operação passar a exigir confirmação, e rota atrás de `_authorize_api`.
5. `/api/finance` (`system_routes.py`): `add` agora valida e responde 400; `INSERT OR REPLACE` por id é usado de propósito para reenvio idempotente; totais calculados em SQL sobre todo o filtro.
6. Menu `/` e janelas: foco/teclado (Esc fecha a janela focada e também fecha o menu), e o `onMouseMove` do menu.

## 6. O que NÃO foi verificado

- Backend real (`python -m app.main`) e dados pessoais: nunca iniciado.
- Efeitos reais no Windows: brilho (WMI em monitores reais), bloqueio de tela, volume, mídia, abrir/fechar apps.
- Provedores reais de IA e voz; indicador "Modo manual" foi testado só com snapshot simulado.
- Supabase real, RLS aplicada no projeto, login e restauração entre dois dispositivos reais.
- APK: o painel novo não foi copiado para `mobile_app\` (`build:mobile` não foi executado); o comportamento do APK com o novo formato de cofre também não foi testado.
- Suíte pytest completa e `tests/smoke_test.py`/`stress_test.py`/`test_live_server.py`.
- Pendências conhecidas registradas em `docs/PENDENCIAS_DO_PAINEL.md`: lápides de exclusão, escape `//` para mensagens que começam com `/`, `/api/chat/stream` e chat direto do APK sem `open_window`, testes antigos de finanças que escrevem em `data/lifestyle.db`.
- `test_fish_audio.py` e `test_fish_audio.mp3` continuam sem rastrear, intocados.
