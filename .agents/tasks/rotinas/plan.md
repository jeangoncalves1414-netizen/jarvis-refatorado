# Plano - Espera real, verificação de efeito, rotinas e gatilhos

Worktree: `c:\Users\maria\Desktop\Jarvis\.worktrees\rotinas` (branch `feat/rotinas`, base `7d11f7a`).
Use SEMPRE caminhos absolutos dentro do worktree; caminho relativo cai no repositório principal.
Ordem: Fase 1 (Feature 1) -> Fase 2 (Feature 2) -> Fase 3 (Feature 3). Cada fase termina com testes verdes e um commit local (nunca push).

## 0. Regras fixas (todas as fases)

- Python: `C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe -B -m pytest -q -p no:cacheprovider <arquivos>` (abreviado abaixo como `PYTEST <arquivos>`). Só arquivos listados; nunca a suíte completa; nunca `tests/test_habits_tasks_finance.py`.
- Testes nunca escrevem em `data/`: use `tmp_path`, a fixture `isolated_lote6_data` ou as fixtures autouse novas (item 1.1 e 2.1).
- Frontend (em `frontend/`): `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` e `npm run build` (nunca `build:mobile`).
- Todo texto de interface, mensagem de ferramenta e erro de API em português, com acentos corretos (o smoke `broken-text.cjs` rejeita acento quebrado; salve arquivos em UTF-8).
- Conjunto de regressão do Kernel/loop (rodar ao fim de cada fase): `PYTEST tests/test_agent_loop.py tests/test_loop_policy.py tests/test_tool_catalog.py tests/test_action_kernel.py tests/test_action_gateway.py tests/test_runs.py tests/test_turn_tool_allowlist.py tests/test_token_economy.py tests/test_popups_infra.py tests/test_open_window.py tests/test_native_action_boundary.py tests/test_auto_approvals.py`.
- Registrar progresso em `.agents/tasks/rotinas/progresso.md` (mesmo formato do lote 7: mudanças por arquivo, testes rodados, decisões, pendências).

## 1. Diagnóstico (lido no código)

- O pedido "Abra o spotify, aguarde 50 segundos e abra uma música no youtube" tem 2 verbos de ação, então `loop_policy.should_use_agent_loop` escolhe o loop. O planejador (`react_loop._build_prompt`) só tem `timer` para "esperar"; `timer set_timer` agenda um bipe numa thread (`_TimerManager`) e retorna na hora, então as 3 ações rodam juntas.
- `ActionExecutor._execute` marca `succeeded` quando a ferramenta devolve `ok=True`; `open_windows_app open`, `spotify open/search_play` e `web_search open_url` devolvem `ok=True` sem conferir nada. `_finish` usa o texto do modelo.
- `RunCancelled` herda de `Exception`: dentro de `_execute` ele cai no `except Exception` e a ação vira `failed` ("lançou exceção") antes de ser relançado.
- Retomada após aprovação: `loop_checkpoints.register(action_id, LoopCheckpoint(resume, abandon))`; `app/ui/panel/api/actions.py::_resume_loop/_abandon_loop` chamam esses callbacks; `sweep_expired_proposals` expira propostas após 600 s (só roda em `GET /api/actions` e `GET /api/runs`).
- `app/core/scheduler.py` é um laço simples usado só pelo resumo por hora. APScheduler 3.11.2, psutil 7.2.2 e `zoneinfo('America/Sao_Paulo')` estão instalados.
- `PanelServer.start()` é chamado por vários testes; `app/main.py:148` chama `panel.start()` no app real.

## 2. Decisões (com motivo)

1. **Espera = ferramenta nova `wait`** (`app/agent/tools/wait.py`) e não um tipo especial do loop: assim ela passa pelo Kernel (aparece na Central, cancela por "Parar pedido") e funciona no loop, no chat nativo e nas rotinas sem caminho paralelo. Parâmetros: `seconds` (int 1..3600), `reason` (texto curto). Acima de 3600 s devolve `ok=False` com "Espera maior que 1 hora: crie uma rotina com horário (ferramenta routine)". Risco `low` (não `observe`) para aparecer na Central sem `include_reads`; efeito "Apenas espera; nada é alterado".
2. **Laço de espera único** em `app/core/waits.py::wait_seconds(seconds, *, label)`: dorme em fatias de 0,5 s, chama `check_run_cancelled()` a cada fatia e reporta o restante a cada 1 s por um `ContextVar` `current_wait_reporter` (callable `(remaining, total)`); sem reporter, grava `store.update_run_progress(run_id, {"phase": "waiting", ...})` se houver Run. Relógio e sono injetáveis (`_monotonic`, `_sleep`) para testes sem esperar de verdade. As rotinas usam o mesmo laço para `delay_before`.
3. **`timer` fica só como alarme**: descrição nova "Alarme sonoro para avisar a usuária depois (timer/alarme). NÃO pausa nem espera entre ações; para esperar use wait." Quando o pedido tem intenção de espera e não cita alarme/timer/avise/lembre, o orquestrador tira `timer` das ferramentas do loop (o modelo não consegue errar).
4. **Verificação de efeito por regra, no `ActionExecutor`** (vale para chat, loop, gateway e rotinas): novo `app/agent/effect_checks.py::check_effect(tool, args, result) -> EffectCheck(status, evidence)` com `status` em `confirmed | unconfirmed | not_applicable`. Nunca transforma sucesso em falha (app lento não é erro); acrescenta a evidência à mensagem e ao `result_summary`, e grava `result.data["effect"]`. Chave global `effect_checks.enabled` (fixture autouse desliga nos testes antigos; testes novos ligam).
5. **Resposta final com evidência**: em `react_loop._finish`, se alguma etapa tem efeito `unconfirmed`, a resposta é montada por regra (sem o texto do modelo): "Etapa 1: Spotify aberto (confirmado: processo Spotify.exe, janela "Spotify Premium"). Etapa 3: abri o YouTube, mas não consegui confirmar que está tocando." Se tudo foi confirmado, texto do modelo + linha "Confirmado: ...".
6. **Armazenamento das rotinas** em `app/storage/routine_store.py` (SQLite `data/routines.sqlite3`, padrão do `ActionStore`: classe com `path`, singleton de módulo `routine_store`, quem usa resolve `store_module.routine_store` na chamada para os testes trocarem).
7. **Agendador: APScheduler `BackgroundScheduler` com `MemoryJobStore`**, tz `America/Sao_Paulo`. Motivo: `CronTrigger`/`IntervalTrigger`/`DateTrigger` já resolvem dias da semana, fuso e `get_next_fire_time` (usado também para "próximas execuções" sem o agendador ligado), e `coalesce` + `misfire_grace_time` tratam hibernação. O SQLite das rotinas é a única fonte da verdade; os jobs são recriados a partir dele em `start()` e a cada alteração (`sync_jobs`). Não usamos `SQLAlchemyJobStore` (dependência nova e jobs em pickle).
8. **Tolerância de recuperação** (`catch_up_minutes`, padrão 15, 0..720): ao iniciar, para cada rotina com horário, a última data prevista entre `last_scheduled_for` e agora roda uma vez (gatilho `catch_up`) se estiver dentro da tolerância; as demais perdidas viram uma linha `missed` no histórico.
9. **Aprovação no meio da rotina** reaproveita `loop_checkpoints` (mesmo TTL de 600 s e a mesma varredura). Recusa ou expiração encerram a rotina como `failed` com motivo claro ("Etapa 2 não foi aprovada a tempo (expirou)"), independentemente de `on_failure`. O agendador roda a cada 60 s `sweep_expired_proposals()` só quando existe execução de rotina pausada, para a expiração acontecer mesmo com o painel fechado. Reinício do backend marca execuções `running/paused` como `interrupted`.
10. **Popup de resumo** ao criar rotina usa o template existente `info` (sem renderer novo no frontend), via entrada em `AUTO_POPUPS` para `("routine", "create")` e `("routine", "update")`.
11. **Gatilho `/comando`** vira comando dinâmico no registro do frontend (`kind: 'routine'`), e **frase de voz** é casada no orquestrador antes do loop (zero chamada ao modelo), valendo para chat e voz.
12. **Gatilhos de evento** (Fase 3): uma thread `EventWatcher`, intervalo padrão 15 s (10..120), pausável; padrão de toda regra é `mode: "alert"`. Alertas não criam Run (não poluem a Central); ficam no histórico da rotina e na lista "Alertas". `mode: "run"` cria Run de origem `routine` e passa pelo Kernel normalmente. Rotina com gatilho de evento recusa etapas de encerrar processo (`open_windows_app close`, qualquer operação `close|kill|terminate|end_task`): nunca matar processo automaticamente. "Janela de horário" é condição opcional (`window: {start, end}`) de qualquer gatilho de evento, não um gatilho sozinho.
13. **Alertas de recurso globais** (CPU/RAM/disco) ficam em Configurações (`runtime_settings` grupo `events`), desligados por padrão (CPU 90 % por 120 s, RAM 90 % por 120 s, disco C: 95 %); o watcher fica ligado por padrão, mas só faz leitura de processos/recursos se alguma regra ativa precisar.
14. `routine` não pode ser etapa de rotina (sem recursão) e `wait` também não (use `delay_before`). Máx. 20 etapas, 4 gatilhos (no máximo 1 de horário, 1 voz, 1 comando, 1 evento).
15. Timeout de etapa: a chamada da ferramenta roda num `ThreadPoolExecutor` e o runner espera `timeout` s; se estourar, a etapa vira `failed` ("Tempo esgotado; a ferramenta pode continuar rodando"). A thread não é morta (limite aceito e registrado).

## 3. Modelo de dados

```text
routines(id TEXT PK 'rt_<hex>', name TEXT, enabled INT, steps_json TEXT, triggers_json TEXT,
         quiet_json TEXT NULL, catch_up_minutes INT, created_at REAL, updated_at REAL,
         last_scheduled_for REAL NULL, last_run_at REAL NULL, last_status TEXT NULL,
         last_run_id TEXT NULL, last_summary TEXT NULL)
routine_runs(id TEXT PK 'rr_<hex>', routine_id TEXT, run_id TEXT NULL, trigger_kind TEXT,
             scheduled_for REAL NULL, started_at REAL, finished_at REAL NULL,
             status TEXT  -- running|paused|succeeded|failed|cancelled|skipped|missed|interrupted|alert
             , step_index INT, summary TEXT)   -- índice (routine_id, started_at DESC); máx. 200 por rotina
```

Etapa (contrato, validado em `app/routines/models.py`):
```json
{"id": "s1", "label": "Abrir Chrome", "tool": "open_windows_app", "operation": "open",
 "params": {"app_name": "chrome"}, "delay_before": 0, "on_failure": "stop|continue|retry",
 "retries": 0, "timeout": null}
```
- `tool` existe no registro e no `TOOL_CATALOG` e não é `routine`/`wait`. `operation` deve estar no `enum` do argumento de operação da ferramenta (`properties.action.enum` do schema; senão `metadata.operation_arguments[0]`); ferramenta sem operação usa `""`.
- Argumentos executados = `{**params, <arg_de_operação>: operation}`. `params` é objeto JSON de até 4 KB, chaves do schema da ferramenta.
- `delay_before` 0..3600 s; `retries` 0..3 (só com `retry`, 2 s entre tentativas); `timeout` null ou 5..600 s.

Gatilho (`triggers_json`, lista):
```json
{"type": "at", "datetime": "2026-11-10T08:00"}            // horário local SP
{"type": "daily", "time": "08:00"}
{"type": "weekdays", "time": "08:00"}
{"type": "weekly", "days": ["mon","wed"], "time": "08:00"}
{"type": "interval", "minutes": 30}                         // 5..1440
{"type": "voice", "phrase": "modo foco"}
{"type": "command", "slash": "foco"}                         // [a-z0-9-], sem colidir com comandos fixos
{"type": "event", "event": "calendar_before|app_started|app_closed|resource|idle|returned",
 "params": {...}, "mode": "alert|run", "cooldown_minutes": 30, "window": {"start":"08:00","end":"22:00"}}
```
"Agora" não é gatilho gravado: `create` aceita `run_now: true`. `quiet_json`: `{"start":"22:00","end":"07:00"}`; gatilhos de horário e evento dentro dele viram `skipped`; "Executar agora", voz e comando ignoram.

## 4. API (novo `app/ui/panel/api/routines.py`, registrar nos tuplos de GET (~linha 691) e POST (~linha 1974) de `app/ui/panel/server.py`)

| Método e rota | Corpo / resposta |
|---|---|
| `GET /api/routines` | `{ok, routines:[{...routine, next_run, last_status, last_summary, last_run_id}]}` |
| `GET /api/routines/<id>` | `{ok, routine, history:[routine_runs, até 50]}`; 404 "Rotina não encontrada." |
| `GET /api/routines/next?limit=10` | próximas execuções de todas as rotinas ativas |
| `GET /api/routines/meta` | ferramentas permitidas em etapas: `{tool, label, operation_argument, operations:[{name, risk}], params:{nome: tipo/descrição}}` a partir do registro + `TOOL_CATALOG` (`risk_for`) |
| `GET /api/routines/alerts?limit=30` | alertas recentes (status `alert`) |
| `POST /api/routines` | cria; valida; 400 com mensagem em português; devolve `{ok, routine, next_run, run_id?}` |
| `POST /api/routines/<id>` | atualiza (substitui campos editáveis) |
| `POST /api/routines/<id>/enable` | `{enabled: bool}` |
| `POST /api/routines/<id>/run` | executa agora em segundo plano; `{ok, run_id}`; 409 se já está rodando |
| `POST /api/routines/<id>/delete` | apaga rotina e histórico |
| `GET/POST /api/settings/events` | grupo `events` do `runtime_settings` (Fase 3) |

Rotas são ações da janela sobre dados do app (como a janela Finanças): CRUD direto; as ETAPAS sempre passam pelo Kernel ao executar. Toda alteração publica `ui_events.publish({"type": "routine_changed", "routine_id"})`; cada execução publica `routine_run` (início/fim) e `add_run_event(run_id, "routine", ...)` (AQ4).

## 5. Verificação de efeito por tipo de ação (`app/agent/effect_checks.py`)

Sondas injetáveis no módulo: `_processes() -> set[str]` (psutil, nomes em minúsculas), `_window_titles() -> list[str]` (EnumWindows visíveis), `_sleep`, `_monotonic`. Espera curta com polling de 0,5 s.

| Ferramenta / operação | Como confirma | Prazo |
|---|---|---|
| `open_windows_app open`, `system_control open_app`, `desktop_automation open_app` | `app_manager.running_processes_for(name)` ou executável do alias em `_processes()`, e janela visível cujo título contém o nome | 6 s |
| `open_windows_app` com `already_running` | confirmado na hora ("já estava aberto") | 0 |
| `spotify open` | `Spotify.exe` em `_processes()` + janela com "Spotify" | 8 s |
| `spotify search_play` | título da janela do Spotify no formato "Artista - Música" (`_get_spotify_window_title` contém " - "); evidência = título | 10 s |
| `spotify play_pause/next/previous` | título do Spotify mudou em relação ao lido antes (lê antes em `check_effect` via `before` capturado no executor); senão `unconfirmed` | 3 s |
| `web_search open_url`, `desktop_automation open_url` | processo de navegador (chrome, msedge, firefox, brave, opera) + janela cujo título contém o domínio-chave (youtube -> "YouTube"; outros: primeira palavra do host) | 8 s |
| URL de YouTube (`watch`/`results`) | além do anterior, título diferente de "YouTube" puro conta como "abri o vídeo"; tocar não é confirmável -> texto "abri o YouTube, mas não consigo confirmar que está tocando" | 8 s |
| demais ferramentas | `not_applicable` (dados já têm a releitura de `app/agent/verification.py`) | - |

Textos: `confirmed` -> "Confirmado: <evidência>."; `unconfirmed` -> "Abri, mas não consegui confirmar: <motivo>." Para ler o "antes" do Spotify, o executor chama `effect_checks.capture_before(tool, args)` antes de `legacy_execute` (barato, só para spotify).

## 6. Desenho da janela "Rotinas" (`frontend/src/windows/RoutinesWindow.tsx`)

- Tema: variáveis de `frontend/src/styles/ws-tokens.css` (sem cores fixas); padrão de estrutura, `panelRequest` e `ConfirmDialog` igual a `FinanceWindow.tsx`. 860x660.
- Coluna esquerda: lista (nome, selo do gatilho "Diário 08:00" / "Voz: modo foco" / "/foco" / "Evento: CPU > 90 %", próxima execução "amanhã 08:00", último resultado com cor por status, chave Ativa, botão "Executar agora"). Botão "Nova rotina". Aba "Alertas" com os alertas recentes.
- Painel direito (editor): Nome; Gatilhos (Horário: Nenhum/Uma vez/Todo dia/Dias úteis/Semanal com caixas seg..dom/A cada N minutos + campo de hora/data; Frase de voz; Comando "/"; Evento: tipo + parâmetros + "Só avisar"/"Executar a rotina" + intervalo entre avisos + janela de horário); Horário de silêncio; Tolerância se o PC estiver desligado (min).
- Etapas: cartão por etapa com Ferramenta (select de `/api/routines/meta`), Operação (select, mostra o risco: "baixo", "alto - pede aprovação"), parâmetros gerados do schema (texto/número/caixa), "Esperar antes (s)", "Se falhar: Parar / Continuar / Tentar de novo (n)", "Tempo limite (s)"; botões ↑ ↓ Remover; "Adicionar etapa". Aviso fixo: "Etapas de risco alto ou crítico pedem aprovação na Central, salvo regra ou Modo liberado."
- Rodapé: Salvar, Cancelar, Excluir (ConfirmDialog). Erros da API aparecem em texto vermelho.
- Aba "Histórico": `routine_runs` (data, gatilho, status, resumo, "Ver na Central" -> `openRun(run_id)`).
- Atualiza ao receber `routine_changed`/`routine_run` (o evento chega pelo socket do `useChat`; expor por um `CustomEvent('jarvis:routine-event')` disparado em `useChat.ts`).
- Funciona sem IA: só chama `/api/routines*`.

---

# Fase 1 - Espera real e verificação de efeito

- [ ] 1.1 Criar `app/core/waits.py` (`current_wait_reporter`, `wait_seconds`, `MAX_INLINE_WAIT = 3600`) e `app/agent/tools/wait.py` (`WaitTool`, nome `wait`, descrição "Espera N segundos ANTES da próxima ação deste pedido (ex.: 'espere 50 s'). Cancela com 'Parar pedido'. Para alarme sonoro use timer."). Registrar em `app/agent/tools/registry.py::_register_builtin_tools`, entrada `"wait"` em `app/agent/tools/catalog.py` (risco `low`, alvo "pausa entre ações", efeito/reversibilidade/escopo em português), `wait` em `LOOP_DATA_TOOLS` e na lista `core_groq` de `allowed_tool_names`, e no `REACT_TOOLS` de `react_loop.py`. Em `ActionExecutor._execute`, tratar `RunCancelled` antes do `except Exception`: transição `cancelled` com "Pedido cancelado durante a execução." e relançar.
      Files: app/core/waits.py, app/agent/tools/wait.py, app/agent/tools/registry.py, app/agent/tools/catalog.py, app/agent/react_loop.py, app/agent/action_executor.py, tests/test_wait_and_effects.py (novo)
      Verify: `PYTEST tests/test_wait_and_effects.py tests/test_tool_catalog.py tests/test_turn_tool_allowlist.py` - testes novos: espera com relógio falso chama o reporter com 3,2,1,0; cancelamento no meio levanta `RunCancelled` e a ação fica `cancelled`; 3601 s devolve `ok=False` com a mensagem de rotina; catálogo e allowlist passam.

- [ ] 1.2 Separar `timer` de espera: nova descrição do `TimerTool` (decisão 3) e do parâmetro `action`; em `app/agent/loop_policy.py` adicionar `wait_intent(text) -> int | None` (regex sobre o texto normalizado: `(espera|espere|aguarda|aguarde|depois de|apos)\s+(\d+)\s*(s|seg|segundos?|min|minutos?|h|horas?)` -> segundos) e `mentions_alarm(text)` (alarme, timer, temporizador, me avis, me lembr, despert). `should_use_agent_loop` devolve `(True, "pedido com espera")` quando há espera e ≥1 verbo de ação (antes do teste de conversa só se não houver "?"; respeita `off`). Em `orchestrator._dispatch_request` (bloco do loop, ~linha 990), se `wait_intent` e não `mentions_alarm`, remover `timer` de `allowed`. Em `react_loop._build_prompt` acrescentar às Regras: usar `wait` para esperar (timer não pausa); pedido com horário/repetição vira `routine` (Fase 2 adiciona a ferramenta; a regra pode entrar já); espera > 1 h -> rotina; "só diga que abriu/tocou se a observação disser 'Confirmado'".
      Files: app/agent/tools/timer.py, app/agent/loop_policy.py, app/agent/orchestrator.py, app/agent/react_loop.py, tests/test_loop_policy.py, tests/test_agent_loop.py
      Verify: `PYTEST tests/test_loop_policy.py tests/test_agent_loop.py` - novos casos: "Abra o spotify, aguarde 50 segundos e abra uma música no youtube" -> loop com motivo "pedido com espera" e `wait_intent == 50`; "me avisa em 10 minutos" não perde `timer`; teste de loop com `FakeRegistry` + plano `ACOES: [spotify open, wait 50, web_search open_url]` executa em ordem (registro de chamadas com marcas de tempo do relógio falso: a 3ª ação só depois do fim da espera) e o prompt não lista `timer` nesse pedido.

- [ ] 1.3 Contagem regressiva visível: em `ReActLoopEngine._act`, definir `current_wait_reporter` durante `executor.execute` para chamar `self._emit(state, "waiting", f"Aguardando {r} s", extra={"wait_remaining": r, "wait_total": t})` (`_emit` ganha `extra` mesclado ao payload). No frontend, `parseProgress` em `frontend/src/hooks/useChat.ts` aceita `wait_remaining`/`wait_total`, e o componente que mostra `agentProgress` (procurar `agentProgress` em `frontend/src`) exibe "Aguardando 42 s de 50" com barra; a fase `waiting` não fecha o contador. A Central já mostra `progress` do Run; em `RunHistory.tsx` exibir o mesmo texto quando `progress.phase === 'waiting'`.
      Files: app/agent/react_loop.py, frontend/src/hooks/useChat.ts, componente do contador, frontend/src/components/RunHistory.tsx, tests/test_agent_loop.py
      Verify: `PYTEST tests/test_agent_loop.py` (novo: eventos de progresso com `phase == "waiting"` e `wait_remaining` decrescente chegam ao callback e ao `update_run_progress`); em `frontend/`: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` limpo.

- [ ] 1.4 Verificação de efeito: criar `app/agent/effect_checks.py` conforme a seção 5 (`EffectCheck` dataclass, `enabled = True`, `capture_before`, `check_effect`, sondas injetáveis). Em `ActionExecutor._execute`, depois de `succeeded`, chamar `check_effect` (dentro de try: falha da sonda vira `not_applicable`), anexar o texto à mensagem e ao `result_summary`, gravar `result.data["effect"] = {"status", "evidence"}`. Em `tests/conftest.py` nova fixture autouse `effect_checks_off` (`monkeypatch.setattr("app.agent.effect_checks.enabled", False)`).
      Files: app/agent/effect_checks.py, app/agent/action_executor.py, tests/conftest.py, tests/test_wait_and_effects.py
      Verify: `PYTEST tests/test_wait_and_effects.py tests/test_action_kernel.py tests/test_action_gateway.py tests/test_native_action_boundary.py` - novos (com `enabled=True` e sondas falsas): processo aparece na 3ª sondagem -> `confirmed` com evidência; nunca aparece -> `unconfirmed`, ação continua `succeeded`, mensagem contém "não consegui confirmar"; `search_play` com título "Artista - Música" -> confirmado; `open_url` youtube com janela "Lofi - YouTube - Google Chrome" -> confirmado "abri o vídeo"; ferramenta de dados -> `not_applicable`; exceção na sonda não derruba a ação.

- [ ] 1.5 Resposta final com evidência: no loop, `_after_action` lê `state.results[...]`.data["effect"]; `unconfirmed` -> `verification_passed=False` e `self_correction_note` com o texto; `confirmed` guarda a evidência no passo (campo novo `ReActStep.evidence: str = ""`). `_finish` aplica a decisão 5.
      Files: app/agent/react_loop.py, tests/test_agent_loop.py
      Verify: `PYTEST tests/test_agent_loop.py` - novos: modelo responde "FINISH: Pronto, tocando!" mas a etapa 3 está `unconfirmed` -> resposta não contém "Pronto, tocando" e contém "não consegui confirmar"; tudo confirmado -> texto do modelo + "Confirmado:".

- [ ] 1.6 Fechamento da fase: rodar o conjunto de regressão da seção 0, `tsc` e `npm run build` em `frontend/`; atualizar `progresso.md`; commit `feat(rotinas): fase 1 - espera real e verificacao de efeito`.
      Verify: todos verdes; `git status` sem arquivos de `data/`.

# Fase 2 - Motor de rotinas

- [ ] 2.1 Modelo e armazenamento: `app/routines/__init__.py`, `app/routines/models.py` (dataclasses `RoutineStep`, `RoutineTrigger`, `Routine`; `validate_routine(payload, registry, catalog) -> Routine` com todas as regras da seção 3 e mensagens em português; `step_arguments(step, tool)`), `app/storage/routine_store.py` (`RoutineStore(path="data/routines.sqlite3")`: `create/get/list/update/delete/set_enabled`, `add_run/update_run/history/alerts`, `mark_interrupted()`, poda a 200 execuções por rotina; singleton `routine_store`). Fixture autouse `isolated_routines` em `tests/conftest.py` troca `app.storage.routine_store.routine_store` por store em `tmp_path`.
      Files: app/routines/__init__.py, app/routines/models.py, app/storage/routine_store.py, tests/conftest.py, tests/test_routines_store.py (novo)
      Verify: `PYTEST tests/test_routines_store.py` - CRUD, persistência ao reabrir o arquivo, validações recusadas (ferramenta desconhecida, `routine` como etapa, operação fora do enum, `delay_before` 4000, 21 etapas, 2 gatilhos de horário, slash inválido), poda do histórico, `mark_interrupted`.

- [ ] 2.2 Cálculo de horários: `app/routines/triggers.py` - `TZ = ZoneInfo("America/Sao_Paulo")`, `build_aps_trigger(trigger)` (`DateTrigger`/`CronTrigger(day_of_week=...)`/`IntervalTrigger`), `next_runs(routine, now, count)`, `missed_fires(routine, since, now)`, `in_quiet_hours(quiet, now)` (atravessa meia-noite), `describe_trigger(trigger)` em português ("Todo dia às 08:00", "Dias úteis às 08:00", "Seg e qua às 08:00", "A cada 30 min", "Em 10/11 às 08:00").
      Files: app/routines/triggers.py, tests/test_routines_scheduler.py (novo)
      Verify: `PYTEST tests/test_routines_scheduler.py` - próximas datas para daily/weekdays (sexta 09:00 -> segunda 08:00)/weekly/interval/at; `at` no passado -> sem próxima; horário de silêncio 22:00-07:00 às 23:30 e 06:59 dentro, 07:00 fora; `missed_fires` com PC desligado 3 dias.

- [ ] 2.3 Executor de rotina: `app/routines/runner.py` `RoutineRunner.start(routine, trigger_kind, scheduled_for=None) -> run_id|None`. Lock por rotina (já rodando -> linha `skipped` "Ainda em execução"). Cria Run com `store.create_run(session_id=f"routine:{id}", mode="routine", source=f"routine:{id}", origin="routine")`, linha em `routine_runs`, `add_run_event(run_id, "routine", "Rotina X iniciada (gatilho: ...)")`. Para cada etapa, com `current_run` setado: `check_run_cancelled`; `wait_seconds(delay_before)` com reporter que publica `{"type":"routine_progress", routine_id, run_id, step, wait_remaining}` e `update_run_progress`; `ActionExecutor(frozenset({tool}), ToolCallGuardrailController(), call_com_timeout, metadata_for=..., store=store, source=f"routine:{id}")` e `execute(tool, args, user_text=f"Rotina {name}, etapa {n}")`. Status `awaiting_confirmation` -> `set_resume_pending(run, True)`, `loop_checkpoints.register(action.id, LoopCheckpoint(resume=..., abandon=...))`, linha `paused`, popup `info` (tom warn) "Rotina X aguarda aprovação na Central (até 10 min)", retorna. `resume` continua do índice seguinte (ou aplica `on_failure` se a ação falhou); `abandon` fecha como `failed` (decisão 9). Falha: `stop` encerra, `continue` segue, `retry` repete até `retries`. Fim: `finish_run` (ou `finish_resume` se pausou) com resumo por regra incluindo evidências de efeito; atualiza `routines.last_*`; publica `routine_run`. Execução síncrona injetável para testes (`runner.spawn = lambda fn: fn()`).
      Files: app/routines/runner.py, tests/test_routines_runner.py (novo)
      Verify: `PYTEST tests/test_routines_runner.py` (registro falso de ferramentas, `ActionStore` em tmp_path, `loop_checkpoints.resume_runner` síncrono, relógio de espera falso) - ordem e `delay_before` respeitados; Run com `origin == "routine"` na `run_page`; etapa alta pausa, aprovar via `app.ui.panel.api.actions` (`POST /api/actions/<id>/approve` pelo handler) retoma e conclui; recusa -> `failed` com motivo; expiração por `sweep_expired_proposals` com relógio adiantado -> `failed` "expirou"; regra de auto-aprovação e Modo liberado executam sem pausar; `continue`/`retry(2)`/`stop`; timeout; cancelamento do Run para na espera; sobreposição -> `skipped`.

- [ ] 2.4 Serviço e agendador: `app/routines/service.py` `RoutineService` (singleton `routine_service`): `create/update/delete/set_enabled/list_with_next/run_now/next_runs/match_phrase/command_triggers`; `start()` cria `BackgroundScheduler(timezone=TZ, job_defaults={"coalesce": True, "max_instances": 1})`, `mark_interrupted`, recuperação (decisão 8), `sync_jobs()` (um job por rotina ativa com horário, `misfire_grace_time=catch_up*60`, id = routine id), job de 60 s de varredura de pausadas; `stop()`. Disparo do job: quiet hours -> `skipped`; grava `last_scheduled_for`; chama o runner. Iniciar em `app/main.py` logo após `panel.start()` (linha ~148) e parar no encerramento; NÃO iniciar em `PanelServer.start()` (testes o chamam). Substituir o uso de `app/core/scheduler.py`? Não: fica como está (fora do escopo).
      Files: app/routines/service.py, app/main.py, tests/test_routines_scheduler.py
      Verify: `PYTEST tests/test_routines_scheduler.py tests/test_routines_runner.py` - `sync_jobs` cria/remove jobs ao ativar/desativar/apagar (inspecionar `scheduler.get_jobs()` com agendador iniciado em pausa `start(paused=True)`); recuperação com `last_scheduled_for` de 10 min atrás roda 1 vez `catch_up`, de 2 h atrás com tolerância 15 vira `missed`; `match_phrase("Jarvis, modo foco!")` acha a rotina com frase "modo foco".

- [ ] 2.5 Ferramenta do agente `routine`: `app/agent/tools/routine_tool.py` (`action`: create, list, update, enable, disable, delete, run_now, next_runs; `routine_id`, `name`, `steps` (array do contrato), `triggers` (array), `quiet_hours`, `run_now` bool). Mensagens com resumo e próxima execução; `data` com `routine`, `next_run`, `routine_ids`. Registrar no registro; catálogo `"routine"`: `operation_arguments=("action",)`, risco observe (list, next_runs), low (create, update, enable, disable, run_now), high com confirmação (delete), alvo `name`/`routine_id`, efeitos em português. `LOOP_KEYWORD_TOOLS` e `GROQ_KEYWORD_TOOLS`: padrão `\brotina|\btodo dia|\btodos os dias|\btoda (segunda|terca|quarta|quinta|sexta|sabado|domingo)|\bdias uteis|\ba cada \d+ ?min|\bas \d{1,2} ?h` -> `routine`. `AUTO_POPUPS` em `app/agent/popups.py`: `("routine","create")` e `("routine","update")` montam `info` (tom ok) com título "Rotina criada"/"Rotina atualizada", linhas: nome, gatilho descrito, até 3 etapas resumidas ("1. Abrir chrome", "2. após 30 s: tocar Foco no Spotify"), "Próxima: amanhã 08:00". Regra no prompt do loop (item 1.2) agora cita a ferramenta. Frase de voz: em `orchestrator._dispatch_request`, antes do loop/LLM (junto do atalho local), `routine_service.match_phrase(text)` -> `run_now` e `AgentPlan(intent="routine", summary='Rotina "X" iniciada. Acompanhe na Central.')`, sem chamada ao modelo.
      Files: app/agent/tools/routine_tool.py, app/agent/tools/registry.py, app/agent/tools/catalog.py, app/agent/popups.py, app/agent/orchestrator.py, tests/test_routine_tool.py (novo), tests/test_popups_infra.py
      Verify: `PYTEST tests/test_routine_tool.py tests/test_tool_catalog.py tests/test_popups_infra.py tests/test_turn_tool_allowlist.py tests/test_token_economy.py` - criar pela ferramenta "todo dia às 8h abre o Chrome e 30 s depois toca a playlist Foco" (args como o modelo mandaria: daily 08:00, etapas open_windows_app open chrome + spotify search_play "Foco" com delay 30) grava e devolve próxima execução; popup `info` emitido com as linhas; `delete` exige aprovação; `routine` aparece no catálogo do loop para "todo dia às 8h..." e não para "abre o spotify, espera 50 s e abre o youtube"; frase de voz roda a rotina com 0 chamadas ao `llm_service`.

- [ ] 2.6 API: `app/ui/panel/api/routines.py` com as rotas da seção 4 (validação de JSON e limites como em `runs.py`; erros 400/404/409 em português) e registro em `app/ui/panel/server.py`.
      Files: app/ui/panel/api/routines.py, app/ui/panel/server.py, tests/test_routines_api.py (novo)
      Verify: `PYTEST tests/test_routines_api.py tests/test_runs.py` - chamar `handle_routines_get/post` direto (como `tests/test_runs.py` chama `runs`): criar, listar com `next_run`, editar etapas (reordenar), ativar/desativar, executar agora devolve `run_id` cujo Run tem origem `routine`, apagar, `meta` lista operações com risco, JSON inválido -> 400, id inexistente -> 404.

- [ ] 2.7 Frontend: janela e comandos. `WINDOW_ROUTINES = 'routines'` + `routinesDef` (params `routine_id` texto 60) em `frontend/src/windows/registry.ts`; `"routines": WindowSpec("Rotinas", {"routine_id": _text(60)})` em `app/agent/tools/open_window.py`; `WindowComponentProps` ganha `openRun?: (id: string) => void`, passado pelo `WindowManager.tsx` a partir do `App.tsx` (mesmo `setLinkedRun(id); setActive('Central')` da linha ~719). Criar `RoutinesWindow.tsx` (seção 6). Em `commands/registry.ts`: comando fixo `window-routines` (label "Rotinas", slash `rotinas`, aliases `rotina`, `automacoes`, `agendamentos`, grupo de ações rápidas, `worksOffline: true`); tipo de ação `{ kind: 'routine'; routineId: string }`, `CommandHandlers.runRoutine`, `setDynamicCommands(list)` mesclado em `getCommand`, `getSlashCommands` e na lista da paleta (fixos têm prioridade; slash duplicado é ignorado); `App.tsx` busca `GET /api/routines` ao abrir e após `jarvis:routine-event` e registra um comando por gatilho `command`; `runRoutine` faz `POST /api/routines/<id>/run` e mostra o retorno. `useChat.ts` despacha `CustomEvent('jarvis:routine-event')` para `routine_changed`/`routine_run`/`routine_progress` (antes do filtro de `session_id`).
      Files: frontend/src/windows/registry.ts, frontend/src/windows/WindowManager.tsx, frontend/src/windows/RoutinesWindow.tsx (novo), frontend/src/commands/registry.ts, frontend/src/App.tsx, frontend/src/hooks/useChat.ts, app/agent/tools/open_window.py, tests/test_open_window.py
      Verify: `PYTEST tests/test_open_window.py`; em `frontend/`: `tsc --noEmit` limpo e `npm run build` ok. Smoke opcional e barato: se o ambiente Vite 5174 + Playwright do lote 7 estiver disponível, rodar `node tests/popups.smoke.cjs` (garante que paleta e popups não quebraram).

- [ ] 2.8 Fechamento da fase: conjunto de regressão + `PYTEST tests/test_routines_store.py tests/test_routines_scheduler.py tests/test_routines_runner.py tests/test_routine_tool.py tests/test_routines_api.py tests/test_wait_and_effects.py`; `tsc` e `npm run build`; `progresso.md`; commit `feat(rotinas): fase 2 - motor de rotinas`.

# Fase 3 - Gatilhos de evento e alertas (por regra, sem modelo)

- [ ] 3.1 Configurações: grupo `events` em `app/storage/runtime_settings.py` (`get_event_settings/set_event_settings`, validação com erro em português): `enabled` (true), `interval_seconds` (15, 10..120), `cpu|ram|disk: {enabled: false, threshold: 90|90|95 (50..99), for_seconds: 120 (0..3600)}`, `disk_path` ("C:\\"), `cooldown_minutes` (30, 1..1440). Rotas `GET/POST /api/settings/events` em `app/ui/panel/api/settings.py` (mesmo padrão de `/api/settings/agent-loop`, linhas 129 e 313).
      Files: app/storage/runtime_settings.py, app/ui/panel/api/settings.py, tests/test_event_watcher.py (novo), tests/test_settings_api.py
      Verify: `PYTEST tests/test_event_watcher.py tests/test_settings_api.py tests/test_agent_loop_settings.py` (usar `isolated_lote6_data`, que já isola `runtime_settings`) - padrão, gravação, valores inválidos -> 400.

- [ ] 3.2 Watcher: `app/routines/watcher.py` `EventWatcher` (uma thread daemon "routine-events", `start/stop/pause/resume`, `tick(now)` público para teste). Cada `tick` coleta só o que as regras ativas pedem: processos (`psutil.process_iter(["name"])` uma vez), CPU (`psutil.cpu_percent(None)`), RAM (`virtual_memory().percent`), disco (`disk_usage(path).percent`), ocioso (`GetLastInputInfo` via ctypes; `idle` com `minutes`, `returned` quando sai do ocioso), agenda (`CalendarService().get_events(now, now+1 dia)`; `calendar_before` com `minutes` dispara uma vez por evento quando `start - now <= minutes`). Regras: gatilhos `event` das rotinas ativas + alertas globais do item 3.1. Recurso exige acima do limite por `for_seconds` e rearma abaixo de `threshold - 5`; `app_started/app_closed` comparam o conjunto do tick anterior (primeiro tick só aprende). Respeita `cooldown_minutes`, `window` e horário de silêncio. Disparo: `mode alert` -> `popups.emit(build_popup("info", {title, lines, tone:"warn"}))` + linha `alert` no histórico + `ui_events` `routine_alert`; `mode run` -> `RoutineRunner.start(routine, f"event:{type}")` (Kernel: baixo roda, alto/crítico espera aprovação salvo Modo liberado). Sem nenhuma regra ativa o tick não lê nada. Iniciado/parado pelo `RoutineService.start/stop`; `set_event_settings` e `routine_changed` recarregam as regras. Validação (em `models.validate_routine`): rotina com gatilho de evento recusa etapa de encerrar processo ("Gatilho automático não pode encerrar programas.").
      Files: app/routines/watcher.py, app/routines/service.py, app/routines/models.py, tests/test_event_watcher.py
      Verify: `PYTEST tests/test_event_watcher.py tests/test_routines_store.py` - sondas falsas e `tick` com relógio falso: CPU 95 % por 2 ticks com `for_seconds=20` e intervalo 15 -> 1 alerta, sem repetir no cooldown, rearma após cair; `app_started` spotify dispara só na transição; `calendar_before 10` dispara uma vez por evento; `mode run` cria Run de origem `routine` e uma etapa alta fica `awaiting_confirmation`; com Modo liberado executa; rotina de evento com `open_windows_app close` é recusada; nenhuma regra -> sondas não chamadas; `pause()` impede disparo.

- [ ] 3.3 Frontend: na `RoutinesWindow.tsx`, editor do gatilho "Evento" (tipos: "Compromisso em N minutos", "Programa abriu", "Programa fechou", "Uso de CPU/RAM/disco acima de", "Fiquei ausente por N min", "Voltei ao PC"; campos de parâmetro; "Só avisar" (padrão) / "Executar a rotina"; intervalo entre avisos; janela de horário) e aba "Alertas" alimentada por `GET /api/routines/alerts`. Em Configurações, novo componente `frontend/src/components/EventAlertsSettings.tsx` (ligar/pausar o monitor, intervalo, CPU/RAM/disco com limite e duração, explicação "nada é encerrado automaticamente; só avisos, salvo rotina configurada para executar") renderizado em `SettingsPage.tsx` ao lado de `AgentLoopSettings` (`{desktop && ...}`), com palavras-chave de busca como o lote 7 fez.
      Files: frontend/src/windows/RoutinesWindow.tsx, frontend/src/components/EventAlertsSettings.tsx (novo), frontend/src/pages/SettingsPage.tsx
      Verify: em `frontend/`: `tsc --noEmit` limpo e `npm run build` ok.

- [ ] 3.4 Fechamento: conjunto de regressão + `PYTEST tests/test_event_watcher.py tests/test_settings_api.py tests/test_agent_loop_settings.py tests/test_routines_store.py tests/test_routines_scheduler.py tests/test_routines_runner.py tests/test_routine_tool.py tests/test_routines_api.py tests/test_wait_and_effects.py`; `tsc` e `npm run build`; conferir que nenhum arquivo em `data/` mudou por teste (`git status`; mtime de `data/routines.sqlite3` inexistente/inalterado); atualizar `progresso.md` e `docs/CONTEXTO_PARA_CHATGPT.md` (A1, A2, AQ3, AQ4 marcados com o commit e o que ficou pendente); commit `feat(rotinas): fase 3 - gatilhos de evento e alertas`.

## 7. Lacunas assumidas

- Tocar no YouTube não é confirmável sem automação do navegador: a resposta diz "abri, mas não consigo confirmar que está tocando".
- Aprovação de etapa de rotina vale 10 min (TTL compartilhado do broker); rotinas de madrugada com etapa alta tendem a expirar. Mostrado no popup e no histórico; aumentar o TTL só para rotinas fica como pendência.
- Thread de ferramenta que estoura `timeout` não é morta.
- Rotinas não sincronizam com o celular/nuvem neste lote (PB7 fica pendente).
- Comandos `/` de rotina só existem no frontend desktop após carregar `/api/routines`; sem backend não há rotina para rodar.
