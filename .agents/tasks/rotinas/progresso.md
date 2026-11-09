# Progresso - Rotinas (espera real, verificação de efeito, rotinas e gatilhos)

## Fase 1 - Espera real e verificação de efeito

Commit: `686209d` (`feat(rotinas): fase 1 - wait real e verificacao de efeito`), branch `feat/rotinas`, sem push.

### Mudanças por arquivo

- `app/core/waits.py` (novo): `wait_seconds(seconds, *, label)` com fatias de 0,5 s, `check_run_cancelled()` a cada fatia e contador uma vez por segundo; `current_wait_reporter` (ContextVar); `MAX_INLINE_WAIT = 3600`; `_monotonic`/`_sleep` injetáveis. Sem reporter, grava `update_run_progress` (fase `waiting`) e publica `agent_progress` para o chat (caminho nativo).
- `app/agent/tools/wait.py` (novo): `WaitTool` (`wait`, `seconds` 1..3600, `reason`). Acima de 3600 s devolve `ok=False` com "Espera maior que 1 hora: crie uma rotina com horário (ferramenta routine)."
- `app/agent/tools/registry.py`: registra `WaitTool`; `wait` em `GENERAL_TOOL_NAMES`, `LOOP_DATA_TOOLS` e `core_groq`; `execute_tool` relança `RunCancelled` (antes virava "Erro interno"); palavra-chave do loop para `web_search` ganhou `youtube|site|link|url` (sem isso "abre o YouTube" não recebia ferramenta de abrir link).
- `app/services/llm.py`: `wait` na lista fixa do Groq.
- `app/agent/tools/catalog.py`: entrada `wait` (risco `low`, alvo "pausa entre ações", efeito "Apenas espera; nada é alterado.").
- `app/agent/tools/timer.py`: descrição nova ("Alarme sonoro ... NÃO pausa nem espera entre ações; para esperar use wait.") e do parâmetro `action`.
- `app/core/actions.py`: `running -> cancelled` passa a ser transição válida (cancelamento no meio de uma etapa que coopera).
- `app/agent/action_executor.py`: `RunCancelled` antes do `except Exception` -> ação `cancelled` com "Pedido cancelado durante a execução." e relança; `capture_before` antes da ferramenta; `check_effect` depois de sucesso (exceção da sonda = `not_applicable`), texto anexado à mensagem e ao `result_summary`, `result.data["effect"]`.
- `app/agent/effect_checks.py` (novo): `EffectCheck`, `enabled`, `capture_before`, `check_effect`, sondas `_processes`, `_window_titles`, `_spotify_title` (janelas do processo Spotify.exe), `_sleep`, `_monotonic`. Regras da seção 5 do plano (app 6 s, Spotify open 8 s, search_play 10 s, controles 3 s, URL 8 s; YouTube watch/results confirma "abri o vídeo", mas diz que não consegue confirmar que está tocando).
- `app/agent/loop_policy.py`: `wait_intent(text)` e `mentions_alarm(text)`; `should_use_agent_loop` devolve `(True, "pedido com espera")` com espera + verbo de ação, sem "?", respeitando `off`.
- `app/agent/orchestrator.py`: no loop, pedido com espera e sem alarme tira `timer` das ferramentas.
- `app/agent/react_loop.py`: `wait` em `REACT_TOOLS`; `ReActStep.effect_status`/`evidence`; `_act` define `current_wait_reporter` (fase `waiting` com `wait_remaining`/`wait_total`); `_emit(extra=...)`; `_after_action` lê o efeito; `_finish`: efeito não confirmado -> resposta por regra (`_evidence_summary`, sem o texto do modelo); tudo confirmado -> texto do modelo + "Confirmado: ..."; regras novas no prompt (wait x timer, >1 h vira rotina, só dizer que abriu/tocou com "Confirmado").
- `app/storage/action_store.py`: `update_run_progress` aceita `wait_remaining`/`wait_total`.
- Frontend: `useChat.ts` (`parseProgress` lê `wait_remaining`/`wait_total`), `ChatPage.tsx` ("Aguardando 42 s de 50" com barra; fase `waiting` não fecha o contador), `RunHistory.tsx` (mesmo texto na Central), `workspace.css` (barra `.ws-agent-wait-bar`).
- Testes: `tests/conftest.py` (fixture autouse `effect_checks_off`), `tests/test_wait_and_effects.py` (novo), `tests/test_loop_policy.py` e `tests/test_agent_loop.py` (casos novos: ordem spotify -> wait 50 -> youtube com relógio falso, `timer` fora do prompt, alarme mantém `timer`, contador 3,2,1,0, cancelar no meio da espera, "Pronto, tocando!" substituído quando o YouTube não confirma, tudo confirmado mantém o texto + "Confirmado:").

### Decisões tomadas sem perguntar

- Abrir app confirma com processo OU janela com o nome (o plano pedia os dois). Motivo: apps como a Calculadora moderna e apps na bandeja não têm os dois ao mesmo tempo; a evidência diz o que foi visto.
- Spotify `open` exige o processo `Spotify.exe`; a janela só entra na evidência (o Spotify pode abrir minimizado na bandeja).
- O título do Spotify é lido das janelas do processo `Spotify.exe` (o título "Artista - Música" não contém "Spotify", então `_get_spotify_window_title` da ferramenta não serve para confirmar).
- A checagem roda antes da transição para `succeeded` (a ação fica `running` durante a sondagem) para gravar mensagem e evidência numa transição só.
- `running -> cancelled` foi liberado no Kernel em vez de usar `interrupted`, conforme o plano (1.1).
- No chat nativo (sem loop) a resposta final continua sendo do modelo; ele recebe a observação com "Confirmado"/"não consegui confirmar". A resposta montada por regra vale para o loop, que é o caminho do pedido com espera.

### Testes rodados

- `C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe -B -m pytest -q -p no:cacheprovider tests/test_wait_and_effects.py tests/test_loop_policy.py tests/test_agent_loop.py tests/test_tool_catalog.py tests/test_action_kernel.py tests/test_action_gateway.py tests/test_runs.py tests/test_turn_tool_allowlist.py tests/test_token_economy.py tests/test_popups_infra.py tests/test_open_window.py tests/test_native_action_boundary.py tests/test_auto_approvals.py` -> 317 passed (1ª tentativa teve 1 falha no meu teste novo, que esperava só processo mas a janela falsa já confirmava; teste ajustado).
- `frontend`: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` -> sem erros; `npm run build` -> ok (só o aviso antigo de chunk grande).
- `node -e "require('./broken-text.cjs').assertSourceHasNoBrokenText()"` em `frontend/tests` -> ok. Os `*.smoke.cjs` não foram rodados: precisam do painel em `127.0.0.1:5173` (servidor de desenvolvimento).

### Pendências

- Smoke de navegador do contador de espera (precisa do servidor de desenvolvimento).

## Fase 2 - Motor de rotinas, agendador e UI

### Mudanças por arquivo

- `app/storage/routine_store.py`: store SQLite local (`data/routines.sqlite3`) com criação de tabelas (`routines`, `routine_runs`), CRUD de rotinas, controle de histórico com poda a 200 execuções, mapeamento seguro de tipos em `_columns` (`enabled`, `steps_json`, `triggers_json`, `quiet_json`, `catch_up_minutes`, `name`, `id`), método `mark_interrupted` para recuperação de reinício.
- `app/routines/models.py`: modelos e validação completa do contrato de rotinas (`RoutineStep`, `RoutineTrigger`, `Routine`, `validate_routine`, `operation_spec`, `step_tool_names`).
- `app/routines/triggers.py`: cálculo e conversão de horários com `ZoneInfo('America/Sao_Paulo')`, `build_aps_trigger`, `next_runs`, `next_run`, `missed_fires`, `in_quiet_hours`, `describe_trigger`, `describe_when`.
- `app/routines/runner.py`: `RoutineRunner` para execução de rotinas, suporte a lock concorrente, criação de Run isolada (`origin='routine'`), execução sequencial com `wait_seconds` e cancelamento cooperativo, pausa com checkpoints de aprovação para ações de risco (`awaiting_confirmation`), políticas de falha (`stop`, `continue`, `retry`) e timeout.
- `app/routines/service.py`: `RoutineService` com agendador em background (APScheduler `BackgroundScheduler` com `MemoryJobStore`), recuperação de execuções perdidas (`catch_up_minutes`), tolerância de horário de silêncio, correspondência de frases de voz e comandos `/`.
- `app/agent/tools/routine_tool.py`: ferramenta nativa `routine` para gerenciamento via agente (`create`, `list`, `update`, `enable`, `disable`, `delete`, `run_now`, `next_runs`).
- `app/agent/tools/catalog.py`: catálogo da ferramenta `routine` com riscos e descrições em português.
- `app/agent/popups.py`: popups automáticos tipo `info` para criação e atualização de rotinas.
- `app/agent/orchestrator.py`: despacho direto de frase de voz correspondente a rotinas sem acionar LLM.
- `app/ui/panel/api/routines.py`: endpoints REST `/api/routines`, `/api/routines/<id>`, `/api/routines/next`, `/api/routines/meta`, `/api/routines/alerts`, `/api/routines/<id>/enable`, `/api/routines/<id>/run`, `/api/routines/<id>/delete`.
- `app/ui/panel/server.py`: registro das rotas GET e POST de rotinas no servidor HTTP do painel.
- `app/agent/tools/open_window.py`: suporte à janela `routines` (`WindowSpec('Rotinas', {'routine_id': _text(60)})`).
- `frontend/src/windows/registry.ts`: registro da janela `WINDOW_ROUTINES = 'routines'`, definição de `routinesDef`, tipagem `RoutinesWindowParams` e `openRun?: (id: string) => void` em `WindowComponentProps`.
- `frontend/src/windows/WindowManager.tsx`: repasse de `openRun` do `WindowHost` até o componente da janela.
- `frontend/src/components/AppShell.tsx`: repasse de `openRun` para `WindowHost`.
- `frontend/src/commands/registry.ts`: comando fixo `window-routines` (`/rotinas`), remoção de colisão de alias em `Automações`, ação tipo `routine`, handler `runRoutine`, mesclagem de comandos dinâmicos `setDynamicCommands` / `getAllCommands`.
- `frontend/src/components/CommandPalette.tsx`: integração com `getAllCommands()`.
- `frontend/src/hooks/useChat.ts`: despacho do evento `jarvis:routine-event` para o app quando chegam notificações de rotina pelo WebSocket.
- `frontend/src/App.tsx`: handler `runRoutine` com feedback e navegação para a Central, sincronização dinâmica dos comandos de barra das rotinas a partir de `/api/routines`.
- `frontend/src/windows/RoutinesWindow.tsx` (novo): interface da janela de Rotinas com lista de rotinas ativas/inativas, histórico detalhado com link para a Central, botão 'Executar agora', aba de alertas, editor de passos e gatilhos (horário, voz, comando, evento, horário de silêncio, tolerância), confirmação de exclusão com `ConfirmDialog`.
- `frontend/src/styles/windows.css`: estilização completa da janela `.ws-routines` com tokens `--ws-*`.
- Testes: `tests/test_routines_store.py`, `tests/test_routines_runner.py`, `tests/test_routines_scheduler.py`, `tests/test_routine_tool.py`, `tests/test_routines_api.py`, `tests/test_open_window.py`.

### Testes rodados

- Pytest (backend de rotinas e Kernel): 95 passed em 25.96s (`test_routines_store.py`, `test_routines_runner.py`, `test_routines_scheduler.py`, `test_routine_tool.py`, `test_routines_api.py`, `test_open_window.py`, `test_wait_and_effects.py`).
- Frontend: `tsc --noEmit` limpo (0 erros).
- Frontend: `npm run build` gerado com sucesso em 2m 9s (`RoutinesWindow-D5BAhNHy.js` 23.46 kB).
- Frontend: `broken-text.cjs` verificado sem quebras de acentuação.

