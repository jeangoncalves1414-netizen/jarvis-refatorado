# Plano do Lote 6: controle total, loop agêntico e popups animados

Escrito a partir do HEAD `dacbf1e` (tag `antes-lote6`, ponto de retorno). Só leitura de código; nada executado além de leituras. A usuária está fora de casa: **nenhum coder pausa nem pergunta**. Ambiguidade nova: decida, registre em `.agents/tasks/lote6/decisoes-fase-N.md` e siga. Regras dela: planejar bem, **sem revisão/reviewers**, com testes e correção quando falharem. Pode ser revertido (`git reset` para `antes-lote6` é decisão dela, nunca do coder).

## 0. Regras fixas para todas as fases

- Workspace: `c:\Users\maria\Desktop\Jarvis` (trabalho direto em `main`, sem worktree). Git: `E:\PortableGit-2.54.0-64\cmd\git.exe`. Python: `C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe` (abaixo, `$PY`).
- Produto: toda ação com efeito passa pelo Action Kernel (`ActionExecutor` / `action_gateway.run_action`) com risco, alvo e efeito no `TOOL_CATALOG`, e aparece na Central com origem. O agente só escolhe templates/janelas/telas **prontos** e preenche parâmetros tipados; nunca gera UI nem código. Números exibidos vêm da API, nunca do texto do modelo. Tudo abre também sem IA (`/comando`, paleta). Regra resolve antes de modelo (economia de tokens).
- UI e mensagens em português do Brasil. Tema: tokens `--ws-*` de `frontend/src/styles/ws-tokens.css`.
- **Testes nunca escrevem em dados reais** (`data/lifestyle.db`, `data/action_journal.sqlite3`, `data/calendar.json`, `data/vault/`, `data/runtime_settings.json`, `data/auto_approvals.json`, `~/Documents/Evolute/data/lifeos_db.json`). Use a fixture `isolated_lote6_data` (criada na Fase 1, item 1.1) ou `tmp_path` + `monkeypatch`.
- **Nunca** rodar a suíte completa nem `tests/test_habits_tasks_finance.py`. Só arquivos direcionados:
  `& $PY -B -m pytest -q -p no:cacheprovider <arquivos>`
- **Conjunto de regressão R** (já conferido: todos isolam dados com `tmp_path`/`monkeypatch`):
  `tests/test_tool_catalog.py tests/test_open_window.py tests/test_turn_tool_allowlist.py tests/test_conversation_runtime.py tests/test_action_kernel.py tests/test_action_gateway.py tests/test_runs.py tests/test_run_origins.py tests/test_settings_api.py tests/test_action_proposals.py tests/test_orchestrator_action_results.py tests/test_native_action_boundary.py tests/test_agent_profile.py tests/test_voice_api.py`
- Frontend (rodar em `frontend/`): `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` e `npm run build`. **Nunca** `npm run build:mobile`; nunca tocar em `mobile_app/`.
- Smoke tests de navegador (APIs simuladas, nunca o backend real):
  1. Em `frontend/`, subir o Vite em segundo plano numa porta livre (não use nem mate a 5173, que pode ser a prévia da usuária): `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort` (se ocupada, 5175). Anote o PID.
  2. `$env:PLAYWRIGHT_MODULE='C:\Users\maria\AppData\Local\Programs\Python\Python311\Lib\site-packages\playwright\driver\package'; $env:PANEL_TEST_URL='http://127.0.0.1:5174'; node tests/<arquivo>.smoke.cjs`
  3. Encerrar só o PID que você abriu: `taskkill /PID <pid> /T /F`.
- Não iniciar `python -m app.main` nem servidor contra dados reais. Servidores HTTP em teste usam `ThreadingHTTPServer(("127.0.0.1", 0), server.PanelHandler)` como em `tests/test_conversation_runtime.py::test_http_react_and_stream_publish_same_request_contract`.
- Ao fim de cada fase: testes da fase + R verdes, `tsc` limpo, commit local em `main` com mensagem `feat(lote6): fase N - <resumo>` (git add só dos arquivos tocados, nunca `-A`; não versionar `.agents/`, `test_fish_audio.*`). Nunca `push`. Escrever `.agents/tasks/lote6/fase-N.md` com: o que mudou, comandos rodados e resultado, decisões, pendências.
- Se um teste existente quebrar por mudança de contrato **planejada** (listada neste plano), atualize o teste e registre. Se quebrar por regressão, corrija o código.

---

## (a) Inventário atual de ferramentas, operações e parâmetros (ANTES)

Fonte: `app/agent/tools/registry.py` (`GENERAL_TOOL_NAMES`, `TUTOR_TOOL_NAMES`), `app/agent/tools/catalog.py` (`TOOL_CATALOG`), `parameters` de cada ferramenta. "Visível" = está em `GENERAL_TOOL_NAMES` (o modelo recebe e o executor do turno aceita, C3). "Catálogo" = entrada explícita em `TOOL_CATALOG`; sem ela vale o padrão do `BaseTool` (`low`, ou `critical` se `critical=True`), sem alvo/efeito.

| Ferramenta | Visível | Operações (`action`) | Parâmetros | Catálogo / risco | Lacunas achadas |
|---|---|---|---|---|---|
| habit_tool | sim | list, create, update, check, uncheck, delete | habit_id, name, category, routine_block, days_of_week, start_time, time_exceptions, items_list, add/remove_days, add/remove_items | sim; list observe, escrita low, delete high | sem lote (vários hábitos = várias chamadas); delete só por id (modelo só conhece nomes); update não renomeia nem muda categoria/bloco; duplica conceito com lifeos_tool |
| task_tool | sim | list, create, toggle, delete | task_id, title, priority, project, due_date | sim | sem lote; sem update; list não mostra concluídas; delete só por id |
| finance_tool | sim | summary, add, list, delete | type, amount, category, description, trans_id | sim | sem lote; list sem filtros (período/tipo/categoria) apesar de `FinanceService.query_transactions`; sem update apesar de `update_transaction` |
| lifeos_tool | sim | add_water, get_water, check_habit, uncheck_habit, list_habits, log_workout, summary, motivate | amount, habit_name, workout_name, notes (não usado) | sim | não define total do dia ("bebi 3 L hoje"); `amount` sem limite |
| calendar | sim | list, create_reminder, cancel_reminder | query, title, start, reminder_minutes, reminder_at, reminder_policy | sim, `low` sem mapa por operação (list deveria ser observe) | list sem filtro de dia; sem lote |
| timer | sim | list, set_timer, set_alarm | duration, time, label | sim, `low` sem mapa | sem cancelar (o catálogo promete "cancele o timer") |
| open_window | sim | (window_id) finance, pc-controls | window_id, params | sim, observe | não abre telas do app ("abre o painel") |
| planning_workspace | sim | open, close, append, update, status, set_auto_open | action, title, content, enabled | sim, low | ok |
| web_search | sim | search, research, open_url | action, query, max_results | sim, observe | ok |
| system_control | sim | telemetry, list_processes, get/set_brightness, lock_screen, mídia, volume, open_app | action, level, app_name | sim, por operação | ok |
| open_windows_app | sim | open, close, status, list | action, app_name | sim, por operação + alvo | ok |
| vision / realtime / desktop_search | sim | vários | vários | sim, observe | ok |
| spotify, clipboard, whatsapp, browser_agent, file_manager, script_runner, mobile_adb, kasa_control | sim | vários | vários | sim | ok |
| jarvis_mode, news_reader, cinema, qr_reader, proactive_agent, system_tray, image_generator, screen_peeler, phantom_typer, smart_drop_zone, document_generator, telegram_bot, wormhole, wallpaper_engine, clipboard_intelligence | sim | ver `parameters` | ver `parameters` | **não** (padrão `low` sem alvo/efeito) | auditoria pendente: phantom_typer digita, telegram envia, wormhole expõe porta, system_tray muda a inicialização: todos estão `low` hoje |
| vault_search, vault_daily_log, vault_save_note, vault_update_profile | **não** (registradas, fora de `GENERAL_TOOL_NAMES`) | — | **sem `parameters`** (BaseTool devolve `{}`) | não | o modelo não vê; `save_note(folder=...)` aceita qualquer pasta (caminho com `..` escapa do vault) |
| code_helper, hacker_mode, workflow, mcp, dev_agent | não (fora da lista geral) | — | — | hacker_mode/workflow sim | fora do escopo |
| `notes` | aparece no catálogo e no `core_groq`, **sem ferramenta registrada** | — | — | entrada órfã | remover do `core_groq` e do catálogo (Fase 1) |
| Tutor (whiteboard_*, tutor_*, enem_save_question) | só modo tutor | — | — | parcial | fora do escopo |

Outras observações:
- Caminho nativo (`AgentOrchestrator._run_llm_with_tools`) faz **uma rodada** de chamadas de ferramenta e uma geração final (`_chat_gemini_stream` e `_chat_groq_stream`, `app/services/llm.py:804-840` e `:1201-1240`). Não há continuação nem verificação.
- `executed_tool_results` é indexado por nome de ferramenta: duas chamadas da mesma ferramenta no turno se sobrescrevem.
- `ReActLoopEngine` (`app/agent/react_loop.py`) só aceita `REACT_TOOLS` (6 ferramentas), uma ação por etapa, encerra a sequência quando uma etapa pede aprovação (C8) e não conta chamadas ao modelo (AQ5).
- `core_groq` (`registry.py:allowed_tool_names`) corta hábitos/tarefas/água no Groq a menos que o texto contenha o nome técnico da ferramenta ("habit_tool").

## (b) Desenho do loop agêntico (Fase 2)

**Base:** evoluir `ReActLoopEngine` em `app/agent/react_loop.py` (não criar segundo motor). Ele usa `llm_service.ask(prompt)` (texto, funciona com Gemini, Groq e Oxyy) e o `ActionExecutor`, então Kernel, Central, cancelamento e auto-aprovação já valem.

**Quando o orquestrador usa o loop** (`app/agent/loop_policy.py`, função `should_use_agent_loop(text, mode, settings) -> tuple[bool, str]`, só regra, zero modelo):
- `mode == "react"` (modo "Execução por etapas" já existente) → sempre.
- `settings.mode == "off"` → nunca (fora do modo react). `"always"` → todo pedido em `general`/`chat` que não seja atalho local.
- `"auto"` (padrão): usa o loop quando o texto normalizado (sem acento, minúsculo) tem **≥ 2 verbos de ação** da lista `adiciona/adicionar/cria/criar/coloca/marca/registra/lanca/anota/agenda/abre/abrir/apaga/remove/muda/atualiza/manda/envia/pesquisa/procura/liga/desliga/toca/bebi/gastei/comprei` (formas conjugadas por radical), **ou** 1 verbo + conector de sequência (`depois`, `em seguida`, `e entao`, `por fim`, `tambem`, `;`), **ou** pedido explícito de verificação (`confere se`, `verifica se`, `confirma se`). Não usa para texto com menos de 4 palavras nem para pergunta pura (termina em `?` e sem verbo imperativo). Modos `tutor`, `planning`, `research`, `swarm`, `vision` nunca entram em `auto`.
- Exemplo de aceitação: "abre o painel, adiciona ler e meditar nos hábitos, depois agenda dentista amanhã às 15h e depois coloca que bebi 3L de água hoje" → loop. "oi tudo bem?" e "abre minhas finanças" → caminho normal.

**Protocolo do planejador** (uma chamada `ask` por rodada):
- Mantém o formato antigo (`FERRAMENTA: x` + `ARGS: {json}`; `FINISH: texto`) para compatibilidade com os testes.
- Novo formato em lote: `ACOES: [{"ferramenta": "...", "args": {...}}, ...]` (JSON, de 1 a 5 itens). Misturar `FINISH` com ação, JSON inválido, item sem `ferramenta` ou `args` não objeto → plano inválido, nada executa (mesma regra de hoje).
- O prompt lista só as ferramentas permitidas do turno (`registry.allowed_tool_names(mode="general", provider, user_text)`, C3) em forma compacta: nome, descrição cortada em 160 caracteres, e esquema reduzido (nome do parâmetro, tipo, enum; sem descrições longas). Histórico: últimas 6 etapas com observação cortada em 200 caracteres; contexto da conversa: últimas 4 mensagens da sessão cortadas em 300 caracteres. Instrução fixa: "números e fatos só das observações; prefira operações em lote (`create_many`, `add_many`); termine com FINISH quando tudo estiver feito e verificado".
- Ferramenta fora da lista do turno → "bloqueada pelo modo atual" (o `ActionExecutor` já faz isso).

**Orçamento e contador (AQ5):**
- `max_steps` = ações executadas (padrão 8, 1 a 20). `max_model_calls` = chamadas `ask` (padrão 10, 1 a 30). O que esgotar primeiro encerra. Ao esgotar, **não** chama o modelo de novo: a resposta final é montada por regra ("Fiz 5 de 7 etapas: … Parei no limite de 10 chamadas ao modelo. Confira na Central.").
- Cada ação é uma "etapa"; cada `ask` incrementa `model_calls`. Verificação por regra não conta como chamada ao modelo.
- Progresso: o loop chama `progress(event)` a cada fase (`planning`, `acting`, `verifying`, `waiting_approval`, `resumed`, `done`, `cancelled`, `limit`). O orquestrador publica no barramento `app/core/ui_events.py` (evento `agent_progress`, formato na seção c) e grava `RunRecord.progress = {"step", "max_steps", "model_calls", "max_model_calls", "phase"}` via `ActionStore.update_run_progress(run_id, progress)`. A Central mostra "Etapa 3 de 8 · modelo 3/10".

**Verificação seguida, sem modelo** (`app/agent/verification.py`): mapa `(ferramenta, operação) → verificador`. Depois de uma ação de escrita que deu `succeeded`, o loop roda a leitura correspondente **pelo mesmo executor** (operação `observe`, aparece na Central como leitura do mesmo Run) e compara:
- habit_tool create/create_many → `list` contém os nomes criados; check/check_many → `completed_today`.
- task_tool create/create_many → `list` contém os títulos.
- finance_tool add/add_many → `list` contém os ids devolvidos.
- lifeos_tool add_water/set_water → `get_water.current_ml` igual ao total devolvido.
- calendar create_reminder/create_many → `list` contém o título na data.
- vault_save_note → `vault_search` acha o título.
Falha na verificação: a etapa fica `verification_passed=False` com nota "verificação: X não apareceu na leitura" e entra no histórico; o modelo decide corrigir ou encerrar. Configuração `auto_verify` (padrão ligada).

**Checkpoint e retomada após aprovação (C8):**
- Novo `app/core/loop_checkpoints.py`: registro em memória (como `PendingActionBroker`, TTL 600 s, nada vai ao disco) `register(action_id, checkpoint)`, `take(action_id)` atômico, `discard_for_run(run_id)`. O checkpoint guarda: objetivo, histórico, etapas e chamadas já usadas, ações restantes do lote, contexto, `session_id`, `run_id`, origem e um `resume(final_action_status)` (closure do motor) e `abandon(reason)`.
- `RunRecord` ganha `resume_pending: bool = False`, `reply: str | None = None` e `progress: dict | None = None` (registros antigos continuam válidos pelos padrões). `ActionStore._refresh_run`: com `resume_pending` e `turn_done`, o Run **nunca** vai a terminal (fica `awaiting_confirmation` se houver proposta aguardando, senão `running`). Novos métodos: `set_resume_pending(run_id, bool)`, `finish_resume(run_id, *, failed, reply)` (limpa a pendência, grava `reply`, recalcula), `update_run_progress`. `finish_run` aceita `reply` opcional. `cancel_run` limpa `resume_pending` e chama `loop_checkpoints.discard_for_run`.
- Quando uma ação do loop fica `awaiting_confirmation`: o loop registra o checkpoint, marca `set_resume_pending(True)`, **relê** a ação no store. Se ela já não está aguardando (aprovação chegou durante o turno) e `take` devolve o checkpoint, o loop limpa a pendência e continua na mesma thread. Se `take` falhar, quem aprovou é dono da retomada. Senão, devolve a trajetória pausada com `final_output` "A etapa N precisa da sua aprovação na Central. Assim que você aprovar, eu continuo sozinho." e `pending_action_id`.
- `app/ui/panel/api/actions.py` (aprovar): depois do `callback()`, `cp = loop_checkpoints.take(action_id)`; se existir, `loop_checkpoints.resume_runner(cp, final_status)` (padrão: thread daemon; testes substituem por execução síncrona). Resposta ganha `"resumed": true`. A retomada define `current_run` e `current_origin` na thread, executa as ações restantes do lote, continua o planejamento até FINISH/limite/cancelamento, grava a resposta no histórico da sessão (`save_session_history`, a mesma função do orquestrador, passada no checkpoint), chama `finish_resume(..., reply=...)` e publica `agent_reply`.
- Recusar (`reject`): `take` + `abandon("Etapa recusada; a sequência foi encerrada sem novas etapas.")`: nenhuma chamada nova ao modelo, limpa a pendência, publica `agent_progress(done)` e `agent_reply`. Aprovação expirada (`410`): `take` + `abandon`.
- Auto-aprovação (regra ou Modo liberado) aprova na hora: a etapa executa sem pausa, nada muda.
- Cancelar ("Parar pedido", C4): `check_run_cancelled()` antes de cada `ask`, antes de cada ação e no início da retomada; `cancel_run` descarta o checkpoint. Aprovar depois do cancelamento continua devolvendo 409 (já acontece) e nunca retoma.

**Um Run só:** primeiro turno e retomada usam o mesmo `run_id`; todas as ações, leituras de verificação e eventos ficam nele.

**Chat e voz:** `handle_request_stream` passa a entregar `{"status": "progress", ...}` (fila interna, como `chunk`). O WebSocket do chat recebe `agent_progress`/`agent_reply` pelo barramento. `useChat` mostra o contador no balão de "pensando" e, quando chega `agent_reply` para a conversa ativa fora de um turno, acrescenta a resposta como mensagem do assistente. A ligação por voz mostra o contador na linha de status e fala a resposta final como hoje.

**Configuração** (`app/storage/runtime_settings.py`, chave `agent_loop`): `mode` (`auto`|`always`|`off`, padrão `auto`), `max_steps` (1-20, 8), `max_model_calls` (1-30, 10), `auto_verify` (bool, true). Rotas `GET/POST /api/settings/agent-loop` em `app/ui/panel/api/settings.py`. Tela: nova seção "Agente e popups" em `SettingsPage.tsx`. Gravação via `_write` (sincroniza com Supabase pelo mesmo caminho das outras configurações).

## (c) Contratos dos templates de popup (Fases 3 e 4)

**Princípio:** o agente escolhe o template e passa só seletores tipados (data, filtro, título, formato). Os números e listas são montados pelo backend a partir dos serviços (`HabitService`, `CalendarService`, `LifeOSService`, `memory_vault`). Popups também nascem **automaticamente** do resultado de ferramentas de dados (zero chamada extra ao modelo).

**Backend**
- `app/agent/popups.py`: `POPUP_TEMPLATES: dict[str, PopupSpec]` com `title`, validadores de parâmetros (mesmo estilo de `open_window.py`: `_text`, `_choice`, `_iso_date`; parâmetro desconhecido → `ValueError` em pt-BR) e `builder(params, context) -> data`. Funções: `validate_popup_request(template, params)`, `build_popup(template, params, *, origin, run_id, session_id, key=None, animate=None) -> dict`, `popups_for_result(tool_name, args, result) -> list[dict]` (popups automáticos) e `emit(popup)` (publica no barramento e acumula no coletor do turno).
- Coletor do turno: `ContextVar` `current_popups` em `app/core/ui_events.py`; o orquestrador cria a lista no início de `handle_request` e a coloca em `plan.context["ui_popups"]` no fim. A retomada do loop cria a sua.
- Ferramenta `show_popup` (`app/agent/tools/show_popup.py`), risco `observe`, efeito "Mostra um popup do painel; nenhum dado é alterado". Parâmetros: `template` (enum dos ids), `params` (objeto). Devolve `data.ui_popup`.
- Gancho no Kernel: `ActionExecutor._execute`, depois de gravar `succeeded`, chama `app.agent.popups.after_tool_success(name, args, result)` dentro de `try/except` (popup nunca derruba ação). Só emite quando `current_origin` é `chat` ou `voice`, a configuração `popups.enabled` está ligada, e (para automáticos) `popups.auto` ligada. Rotas de janela (`origin="window"`) não geram popup.
- `GET /api/popups/<template>?<params>` (`app/ui/panel/api/popups.py`, ligado no despacho de GET do `server.py` como os outros módulos `handle_*_get`): monta o popup sem IA para os comandos `/`. Só leitura, sem Run (mesma regra C12 das leituras de janela).
- Configuração `popups` em `runtime_settings`: `enabled` (true), `auto` (true), `ttl_seconds` (8; 0 = fixo até fechar), `max_visible` (3, 1-5). Rotas `GET/POST /api/settings/popups`.

**Envelope do evento** (WebSocket do chat, barramento `ui_events`):
```json
{"type": "ui_popup", "session_id": "…", "run_id": "run_…",
 "popup": {"id": "pop_<uuid>", "key": "habits", "template": "habit_list", "version": 1,
           "title": "Hábitos", "origin": "chat|voice|command", "created_at": 1793920000.0,
           "ttl_ms": 8000, "pinned": false, "data": {…}, "animate": {…}}}
```
Os mesmos objetos `popup` vão em `plan.context.ui_popups` (lista) na resposta final de `/ws/chat` (`complete`), `/api/chat` e `/api/chat/stream`, e o SSE também emite `{"status": "popup", "popup": {...}}` assim que o popup nasce. O frontend descarta `id` repetido. `key` igual a um popup visível **atualiza** esse popup (anima só o que é novo) em vez de empilhar outro.

Outros eventos do barramento: `{"type": "agent_progress", "session_id", "run_id", "step", "max_steps", "model_calls", "max_model_calls", "phase", "summary"}` e `{"type": "agent_reply", "session_id", "run_id", "reply"}`.

**Templates**

| template | key | Parâmetros do agente | `data` (da API) | `animate` | Automático quando |
|---|---|---|---|---|---|
| `info` (Fase 3) | `info:<uuid>` | `title` ≤60, `lines` lista ≤6 × 120, `tone` info/ok/warn | igual aos parâmetros (texto, sem números calculados) | entrada | nunca |
| `habit_list` | `habits` | `filter` today/all (padrão today), `highlight` lista de nomes ≤20 | `items: [{id, name, category, routine_block, start_time, days_of_week, completed_today, streak}]` | `added_ids`, `checked_ids` em ordem | habit_tool create/create_many/check/check_many/update ok |
| `schedule` | `schedule:<data>` | `date` AAAA-MM-DD (padrão hoje) | `date`, `events: [{id, title, start, reminder_at}]` do dia em ordem | `added_ids` | calendar create_reminder/create_many ok |
| `water` | `water:<data>` | nenhum | `date`, `current_ml`, `previous_ml`, `target_ml`, `percentage` (de `LifeOSService.get_daily_summary`; `previous_ml` = total − adicionado) | `from_ml` → `to_ml` | lifeos_tool add_water/set_water ok; `/agua` |
| `live_notes` | `notes:<draft_id>` | `title` ≤80, `format` text/bullets/checklist (padrão bullets), `dictate` bool (padrão true) | `draft_id`, `title`, `format`, `content` inicial vazio | escrita contínua | só por `show_popup` ou `/nota` |
| `task_list` (Fase 5) | `tasks` | `filter` pending/all | `items: [{id, title, priority, due_date, completed}]` | `added_ids`, `toggled_ids` | task_tool create/create_many/toggle ok |
| `places` (Fase 5) | `places:<hash da busca>` | `query` ≤120, `near` ≤80 | `query`, `provider` osm/google, `results: [{name, address, lat, lon, category, rating?}]`, `bbox` | entrada em sequência | places_search ok |

**Frontend**
- `frontend/src/popups/registry.ts`: espelho dos ids e validadores de `data` (como `windows/registry.ts`; dado inválido → popup não abre e aparece aviso "O agente pediu um popup inválido"). Cada template: `title`, `icon`, `parseData`, `component` (lazy).
- `frontend/src/popups/PopupProvider.tsx` (contexto `usePopups()`: `show(envelope)`, `dismiss(id)`, `pin(id)`, `clear()`), `PopupHost.tsx` (camada fixa, não modal, `aria-live="polite"`, sem bloquear cliques fora). Regras de fila: até `max_visible` visíveis empilhados (desktop canto inferior direito, largura 360 px; ≤640 px: topo, largura total); os demais aguardam em fila FIFO; mesma `key` atualiza no lugar; `ttl` conta só quando o popup está totalmente animado e pausa com mouse/foco; botão "Fixar" (pin) cancela o ttl; botão "Fechar" e `Esc` com foco no popup; popup ativo (ditado ligado) nunca expira.
- Entradas: `useChat` (eventos WS `ui_popup` e `context.ui_popups` do `complete`), `useMediaAssistant` (SSE `popup` e `plan.context.ui_popups` do `complete` na ligação), e comandos (`GET /api/popups/<template>`). Todas chegam numa função única do `App.tsx`, `applyAgentUi(context)`, que também trata `open_window` e `open_screen`.

## (d) Primitivas de animação (Fase 3, reutilizadas na 4 e 5)

Arquivo único `frontend/src/popups/motion.tsx` + `frontend/src/styles/popups.css`. Usa `framer-motion` (já dependência, chunk `vendor-motion`). Tokens de tempo em TS (`motionTokens`) e CSS (`--ws-motion-fast: 160ms`, `--ws-motion-base: 280ms`, `--ws-motion-slow: 900ms`, easing `cubic-bezier(.2,.8,.2,1)`).

1. `useCalmMotion()`: `true` quando `useReducedMotion()` do framer **ou** `matchMedia('(prefers-reduced-motion: reduce)')`. Toda primitiva lê isso: com movimento reduzido, mostra o estado final sem transição (só troca de opacidade ≤120 ms).
2. `PopupFrame`: entrada (fade + slide 12 px + scale .98), saída, `layout` para reordenar a pilha. Cabeçalho com ícone, título, Fixar, Fechar; barra fina de ttl.
3. `StaggerList<T>({ items, getId, newIds, renderItem })`: itens existentes aparecem estáticos; ids em `newIds` entram um por um na ordem (intervalo 280 ms) com destaque `--ws-accent-soft` que some em 1,2 s. Base de habit_list, task_list, schedule e places.
4. `CountUp({ from, to, format })`: interpola número com `requestAnimationFrame` (900 ms). Usado para ml, %, streak.
5. `LiquidGauge({ fromPct, toPct, targetLabel })`: SVG de copo/tanque com duas ondas (`path` animado em loop suave) cujo nível sobe de `fromPct` para `toPct`; linha tracejada da meta em 100 %; acima de 100 % o nível fica no topo e aparece "meta batida". Valores em texto ao lado com `CountUp` (acessível: `role="img"` + `aria-label` "1.500 de 3.000 ml, 50 %").
6. `TypewriterText({ committed, interim })`: revela o texto novo de `committed` a ~40 caracteres/s (rápido quando há fila grande), cursor piscante; `interim` (fala ainda não confirmada) em `--ws-muted` itálico. Base das anotações ao vivo.
7. `InsertHighlight`: pulso único em volta de um elemento novo (usado no item da agenda inserido na linha do tempo do dia).

## (e) Extras escolhidos (Fase 5, escopo limitado)

1. **Busca de lugares (J11):** ferramenta `places_search` (`observe`; efeito "envia o texto da busca ao provedor de mapas e lê resultados; nada é alterado"). Padrão OpenStreetMap/Nominatim (`https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=8&accept-language=pt-BR&q=…`) seguindo a política de uso: `User-Agent` próprio identificando o app (`JarvisPessoal/0.1 (uso pessoal; desktop)`), parâmetro `email` opcional via configuração, **no máximo 1 requisição por segundo** (trava global), cache em memória (100 buscas, 24 h), **sem autocompletar** (só busca ao enviar), atribuição "© colaboradores do OpenStreetMap" visível. Google Places (API New, Text Search `POST https://places.googleapis.com/v1/places:searchText`, cabeçalhos `X-Goog-Api-Key` e `X-Goog-FieldMask: places.displayName,places.formattedAddress,places.location,places.rating,places.primaryType`) só quando houver chave `google_places` configurada; falha do Google cai no OSM e diz isso. Popup `places` (lista + mapa) e janela `places` no registro de janelas (abre sem IA com campo de busca), comando `/lugares <busca>`. Mapa: `iframe` do `https://www.openstreetmap.org/export/embed.html?bbox=…&layer=mapnik&marker=lat,lon` (sem biblioteca nova) e link "Abrir no mapa".
2. **Popup de tarefas** (`task_list`) automático para task_tool, reaproveitando `StaggerList`; comando `/pendencias`.
3. **Tela pelo agente** (`open_screen`, Fase 1): o agente abre telas do app ("abre o painel" → `Painel pessoal`).

Fora deste lote: rotinas/gatilhos (A1/A2), palmas, steering (C9), aprovar dentro do chat (C7), timer em popup.

## (f) Decisões tomadas nas ambiguidades

1. **Motor do loop:** evoluir `react_loop.py` com `llm_service.ask` em vez de fazer várias rodadas de function calling nos três provedores (`llm.py`). Motivo: um ponto só, testável com `SimpleNamespace(ask=...)` como os testes atuais, funciona igual em Gemini/Groq/Oxyy.
2. **Ações em lote no planejador (`ACOES:`)** além do formato antigo: o pedido de exemplo cabe em 2 chamadas ao modelo (planejar + concluir) em vez de 5. Economia de tokens.
3. **Quando usar o loop:** detector por regra (seção b), padrão `auto`; pedido simples continua no caminho nativo de 1 rodada.
4. **Recusar uma etapa encerra a sequência** sem chamar o modelo de novo. Motivo: recusa costuma significar "pare"; evita gasto. A resposta diz o que foi feito e o que ficou de fora.
5. **Retomada em memória** (como o broker de aprovação): reinício do backend perde o checkpoint; o Run vira `interrupted` pela recuperação que já existe. Argumentos nunca vão ao disco.
6. **Popups montados pelo backend com dados da API;** o agente só escolhe template e seletores. Popups automáticos nascem do resultado das ferramentas, sem chamada extra ao modelo.
7. **Popup chega por dois canais** (barramento WebSocket ao vivo + `context.ui_popups` na resposta final), com deduplicação por `id`. O WebSocket do chat está sempre conectado no app desktop, então a ligação por voz também recebe ao vivo; o SSE cobre quando o WebSocket cair.
8. **"Bebi 3 L de água hoje" = total do dia** → nova operação `lifeos_tool.set_water` (`total_ml`). "Bebi mais um copo / mais 500 ml" → `add_water`. As descrições das ferramentas dizem isso ao modelo.
9. **"Adicionar hábitos" usa `habit_tool`** (cadastro em `data/lifestyle.db`, que é o único que cria hábitos). `lifeos_tool` fica para água, treino, resumo do dia e marcar hábitos do Life OS. Não unificar os dois sistemas neste lote; as descrições deixam a divisão explícita.
10. **"Abre o painel" sem qualificador = tela `Painel pessoal`** (via `open_screen`). "Abre o Life OS/evolução" = tela `Evolução`.
11. **Anotações ao vivo:** salvas no cofre (`memory_vault.save_note`) na pasta nova `05-Notas`, título estável por rascunho (salvar de novo sobrescreve o mesmo arquivo, comportamento atual de `save_note`), pelo Kernel (`run_action("vault_save_note", …, origin="window", source="popup:live_notes")`). Rascunho local em `localStorage` (`lifeos_live_note_<draft_id>`) até o servidor confirmar. Salva ao parar o ditado, ao fechar e no botão "Salvar". Formatos: Texto (frases unidas), Lista (`- item` por fala), Checklist (`- [ ] item` por fala); trocar o formato reformata o conteúdo.
12. **Motor do ditado:** igual à ligação: captura do PC (`/api/voice/capture/*`, frase a frase, digitada com `TypewriterText`), senão reconhecimento do navegador (com texto provisório), senão digitação manual. **Durante uma ligação por voz**, enquanto o popup de anotação estiver gravando, as falas vão para a nota e não para o agente, até a usuária dizer "fim da nota", "terminar anotação" ou "parar anotação", ou clicar em Parar.
13. **Vault:** `folder` passa a aceitar só pastas conhecidas (`01-Daily-Notes`, `03-Priming-Notes`, `04-Projects`, `05-Notas`); outra pasta → erro. Corrige a fuga de diretório achada no inventário.
14. **Riscos da auditoria (Fase 1):** leitura = `observe`; efeito local reversível = `low`; digitar no PC, enviar mensagem, mudar a inicialização do Windows, expor porta na rede = `high` com confirmação. `phantom_typer`, `telegram_bot.send`, `system_tray.enable_boot/disable_boot`, `wormhole.start` sobem para `high`. Com o Modo liberado ligado pela usuária, nada disso pede aprovação (comportamento do lote 5).
15. **Limites de lote:** até 20 hábitos, 20 tarefas, 20 lançamentos, 10 lembretes por chamada; acima disso a ferramenta recusa com mensagem clara (nada gravado). Itens inválidos no meio do lote: valida tudo antes, grava só se todos forem válidos.
16. **Contadores padrão:** 8 etapas, 10 chamadas ao modelo; o modo "Execução por etapas" (`mode == "react"`) continua aceitando 1 a 20 pelo `/api/react`.
17. **Celular (APK):** fora do escopo; o celular recebe `context.ui_popups` pelo HTTP se um dia usar o mesmo componente. Nada em `mobile_app/`.

---

## (g) Fases de implementação (ordem fixa, um coder por fase)

### FASE 1 — Inventário e expansão do catálogo/comandos (feature 1)

- [ ] 1.1 Fixture de isolamento para o lote.
  Criar em `tests/conftest.py` a fixture **não autouse** `isolated_lote6_data(tmp_path, monkeypatch)`: `monkeypatch.chdir(tmp_path)`; `app.services.habits.DB_PATH` → `tmp_path/"data"/"lifestyle.db"` e chamar `init_db()`, `init_task_tables()` e `init_finance_tables()` depois do patch; `app.services.lifeos._DOCUMENTS_DB` e `_LOCAL_DB` → `tmp_path/"lifeos"/"lifeos_db.json"`; `app.services.memory_vault.VAULT_DIR`, `DAILY_NOTES_DIR`, `PROFILE_DIR`, `PRIMING_DIR`, `PROJECTS_DIR` → equivalentes em `tmp_path/"vault"`; `app.storage.runtime_settings.DATA_DIR`/`RUNTIME_SETTINGS_FILE` → tmp; `app.agent.action_executor.auto_approvals` → `AutoApprovalStore(tmp_path/"auto_approvals.json")` (conferir a assinatura em `app/storage/auto_approvals.py`); `app.storage.action_store.action_store` → `ActionStore(tmp_path/"journal.sqlite3")` (fechar `_runtime_lock` no teardown). Devolve um objeto com `store` e `root`. CalendarService usa `data/calendar.json` relativo ao cwd, coberto pelo `chdir`.
  Arquivos: `tests/conftest.py`.
  Verificar: `& $PY -B -m pytest -q -p no:cacheprovider tests/test_tool_catalog.py tests/test_conversation_runtime.py` continua verde.

- [ ] 1.2 Ferramentas do cofre visíveis e seguras.
  Em `app/agent/tools/memory_vault_tool.py`, dar `parameters` (JSON Schema) e descrições claras às quatro ferramentas; `vault_save_note` valida `folder` contra a lista da decisão 13 e `title`/`content` (título 1-120, conteúdo ≤ 20.000). Incluir as quatro em `GENERAL_TOOL_NAMES`. Catálogo: `vault_search` observe; `vault_daily_log`, `vault_save_note`, `vault_update_profile` low, com alvo (`title`/`category`), efeito e reversibilidade ("edite ou apague o arquivo no cofre"). Remover a entrada órfã `notes` do `TOOL_CATALOG` e do `core_groq`.
  Arquivos: `app/agent/tools/memory_vault_tool.py`, `app/agent/tools/registry.py`, `app/agent/tools/catalog.py`, `app/services/memory_vault.py` (só se precisar da pasta `05-Notas` criada).

- [ ] 1.3 Operações novas e em lote nas ferramentas pessoais (decisões 8, 9, 15).
  - `habit_tool`: `create_many` (`habits`: lista de objetos com `name`, `category`, `routine_block`, `days_of_week`, `start_time`, `items_list`), `check_many` (`names`), `delete` e `check` aceitam nome exato (sem diferenciar acento/maiúscula; ambíguo → erro listando candidatos), `update` ganha `new_name`, `category`, `routine_block`, `list` ganha `only_today`. Devolve sempre `habit_ids`/`habits` criados.
  - `task_tool`: `create_many` (`tasks`: `title`, `priority` 1-4, `project`, `due_date`), `update` (`title`/`new_title`, `priority`, `due_date`, `project`; criar `TaskService.update_task` em `app/services/tasks.py`), `list` ganha `include_completed`, `delete`/`toggle` por título exato.
  - `finance_tool`: `add_many` (`entries`), `list` com `period` (week/month/all), `type`, `category` usando `FinanceService.query_transactions`, `update` usando `FinanceService.update_transaction`; devolve ids criados.
  - `lifeos_tool`: `set_water` (`total_ml` 0-10.000) implementado como `LifeOSService.set_water(total_ml)` novo (calcula a diferença e reutiliza a lógica de `add_water`, devolvendo `previous_ml`, `total_ml`, `target_ml`, `percentage`); `add_water.amount` limitado a 1-5.000.
  - `calendar`: `list` com `day` (AAAA-MM-DD) e `upcoming_days` (1-31); `create_many` (`reminders`: mesmos campos do `create_reminder`, até 10).
  - `timer`: `cancel` por `label` (adicionar `cancel(label)` no `_TimerManager`).
  Arquivos: `app/agent/tools/lifestyle_tools.py`, `app/agent/tools/lifeos_tool.py`, `app/agent/tools/calendar_tool.py`, `app/agent/tools/timer.py`, `app/services/tasks.py`, `app/services/lifeos.py`.

- [ ] 1.4 Catálogo completo e auditoria de risco.
  Em `catalog.py`: operações novas com risco/efeito/reversibilidade (`create_many`/`check_many`/`add_many`/`set_water`/`update` low; `delete` continua high); `calendar` e `timer` ganham mapa por operação (`list` observe; criação/cancelamento low); `target_detail` para lotes ("3 hábitos: Ler, Correr, Meditar", "2 lançamentos, total R$ 80,00", "total do dia: 3.000 ml"). Entradas novas para **toda** ferramenta de `GENERAL_TOOL_NAMES` sem catálogo (lista na seção a), lendo o `run`/`execute` de cada uma para declarar operações e efeitos reais, com os riscos da decisão 14. Nenhuma operação declarada em `enum` pode cair em `critical` por omissão.
  Arquivos: `app/agent/tools/catalog.py`.

- [ ] 1.5 Ferramenta `open_screen` e roteamento no Groq.
  Criar `app/agent/tools/open_screen.py` (risco observe; `screen` em enum com os ids de `frontend/src/navigation.ts`: Dashboard, Chat, Central, Automações, Memórias, Integrações, Estudos, Evolução, Calendário, Painel pessoal, Análises, Identidade, Configurações; descrição com apelidos em português, ex. "painel" → Painel pessoal). Devolve `data.ui_screen = {"screen": id}`. Registrar, incluir em `GENERAL_TOOL_NAMES`, catálogo. No frontend, `App.tsx` passa a tratar `context.tool_results.open_screen.data.ui_screen` (função `applyAgentUi(context)` que reúne janela + tela; trocar `extractWindowRequest` no `onOpenWindow` do `useChat` por um `onAgentContext`). Corrigir `executed_tool_results` no caminho nativo do orquestrador para não perder chamadas repetidas (guardar a última por nome como hoje **e** uma lista `tool_calls` em ordem no contexto). No `registry.allowed_tool_names` do Groq, acrescentar um mapa de palavras-chave → ferramenta (`habito`→habit_tool, `tarefa`→task_tool, `agua`/`bebi`→lifeos_tool, `gastei`/`paguei`→finance_tool, `nota`/`anota`→vault_save_note, `lembrete`/`agenda`/`compromisso`→calendar, `tela`/`painel`/`abre`→open_screen).
  Arquivos: `app/agent/tools/open_screen.py`, `app/agent/tools/registry.py`, `app/agent/tools/catalog.py`, `app/agent/orchestrator.py`, `frontend/src/App.tsx`, `frontend/src/hooks/useChat.ts`.

- [ ] 1.6 Descrições para o modelo e prompt.
  Reescrever `description` e descrições de parâmetros das ferramentas pessoais, calendar, timer, open_window, open_screen e vault com: quando usar, quando **não** usar (habit_tool × lifeos_tool), preferência por lote, formato de data/hora. Atualizar a "REGRA Nº 2" de `build_function_calling_system_prompt` em `app/agent/prompts.py` com as ferramentas novas e "para vários itens do mesmo tipo, uma chamada em lote".
  Arquivos: as ferramentas acima, `app/agent/prompts.py`.

- [ ] 1.7 Inventário gerado (ANTES e DEPOIS).
  Criar `app/agent/tools/inventory.py` com `build_inventory(registry) -> list[dict]` (ferramenta, visível no geral/tutor, operações com risco/efeito, parâmetros com tipo e enum) e `render_markdown(...)`; `python -m app.agent.tools.inventory` imprime a tabela. Gravar `.agents/tasks/lote6/inventario-ferramentas.md` com a seção ANTES (copiar a seção a deste plano) e a seção DEPOIS (saída do módulo).
  Arquivos: `app/agent/tools/inventory.py`, `.agents/tasks/lote6/inventario-ferramentas.md`.

- [ ] 1.8 Testes da Fase 1.
  - Ampliar `tests/test_tool_catalog.py`: teste de contrato (AQ8 parcial) que, para **cada** ferramenta de `GENERAL_TOOL_NAMES` registrada, exige entrada em `TOOL_CATALOG` e, para cada valor do `enum` de `action`, risco diferente de `critical` e efeito não vazio; casos de risco das novas operações e das subidas da decisão 14.
  - Novo `tests/test_tool_ops_lote6.py` (usa `isolated_lote6_data`): create_many cria 3 hábitos e devolve ids; lote com item inválido não grava nada; limite 21 recusado; delete/check por nome e nome ambíguo; task create_many/update/list include_completed; finance add_many/list filtrado/update; set_water de 1.000 para 3.000 devolve `previous_ml=1000`; calendar create_many + list por dia; timer cancel; vault_save_note recusa `folder="../x"` e salva em `05-Notas` dentro do tmp; execução pelo `ActionExecutor` mostra alvo do lote na prévia.
  - Novo `tests/test_open_screen.py`: ids iguais aos de `frontend/src/navigation.ts` (ler o arquivo como texto, extrair `id: '…'`), id inválido recusado, risco observe, contexto `ui_screen`.
  - Novo teste em `tests/test_tool_catalog.py` para `build_inventory` (toda ferramenta geral aparece; nenhuma operação crítica por omissão).
  Verificar: `& $PY -B -m pytest -q -p no:cacheprovider tests/test_tool_ops_lote6.py tests/test_open_screen.py` + R; em `frontend/`: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`. Commit.

### FASE 2 — Loop agêntico (feature 2: C8, AQ5, Parar pedido, configuração)

Depende da Fase 1 (lotes e verificadores usam as operações novas).

- [ ] 2.1 Barramento de eventos da UI.
  Criar `app/core/ui_events.py`: `subscribe(fn) -> unsubscribe`, `publish(event: dict)` (thread-safe, nunca levanta; cada assinante em `try/except`), `ContextVar current_popups` (usado na Fase 3). No `server.py`, ao iniciar o servidor WS (onde `_ws_loop` é definido), assinar um transmissor que envia o JSON a todos os `_ws_clients` com `asyncio.run_coroutine_threadsafe`, no padrão de `_broadcast_wake_word`.
  Arquivos: `app/core/ui_events.py`, `app/ui/panel/server.py`.

- [ ] 2.2 Configuração do loop.
  `get_agent_loop_settings()`/`set_agent_loop_settings(values)` em `runtime_settings.py` (seção b, validação com limites; valor inválido → `ValueError` em pt-BR). `GET/POST /api/settings/agent-loop` em `app/ui/panel/api/settings.py` (mesmo padrão de `/api/settings/mic`).
  Arquivos: `app/storage/runtime_settings.py`, `app/ui/panel/api/settings.py`.

- [ ] 2.3 Run com retomada e progresso.
  `RunRecord`: `resume_pending`, `reply`, `progress` (seção b; incluir em `public_dict`). `ActionStore`: `set_resume_pending`, `finish_resume`, `update_run_progress`, `finish_run(..., reply=None)`, regra de `_refresh_run` com `resume_pending`, `cancel_run` limpando a pendência e chamando `loop_checkpoints.discard_for_run`. Criar `app/core/loop_checkpoints.py` (seção b; `resume_runner` substituível).
  Arquivos: `app/core/runs.py`, `app/storage/action_store.py`, `app/core/loop_checkpoints.py`.

- [ ] 2.4 Motor do loop.
  Em `app/agent/react_loop.py`: construtor aceita `allowed_tools` (padrão `REACT_TOOLS` para chamadas antigas), `budget` (`max_steps`, `max_model_calls`), `progress` callback, `verify` (bool), `history` da conversa e `save_reply` (para a retomada). Parser aceita `ACOES:` (1-5) e o formato antigo. Prompt compacto (seção b). Executa o lote em ordem; aprovação pendente → checkpoint com ações restantes; retomada; limite sem chamada extra; `ReActTrajectory` ganha `model_calls` e `stopped_reason` (`finish`/`limit_steps`/`limit_calls`/`waiting_approval`/`rejected`/`cancelled`/`invalid_plan`). Criar `app/agent/verification.py` (seção b) e chamá-lo depois de cada escrita bem-sucedida quando `verify` estiver ligado.
  Arquivos: `app/agent/react_loop.py`, `app/agent/verification.py`.

- [ ] 2.5 Orquestrador e aprovação.
  Criar `app/agent/loop_policy.py` (`should_use_agent_loop`). Em `_dispatch_request`: depois de Racing e do atalho local, decidir pelo loop; montar `allowed_tools` com `registry.allowed_tool_names(mode="general", provider, user_text=text)`; ler orçamento das configurações (o `react_max_steps` do `/api/react` continua valendo quando enviado; padrão vira `None` = configuração); `progress` publica `agent_progress` (com `session_id`, `run_id`) e grava `update_run_progress`; `plan.intent = "agent_loop"` (modo react mantém `react_loop`), `plan.context` com `steps_count`, `model_calls`, `max_steps`, `max_model_calls`, `pending_action_id`, `stopped_reason`. `handle_request_stream` repassa progresso como `{"status": "progress", ...}`. Em `app/ui/panel/api/actions.py`: aprovar retoma (`take` depois do callback), recusar e expirar chamam `abandon`; resposta com `resumed`.
  Arquivos: `app/agent/loop_policy.py`, `app/agent/orchestrator.py`, `app/ui/panel/api/actions.py`, `app/ui/panel/server.py` (só se `/api/react` precisar do novo padrão).

- [ ] 2.6 Frontend: contador, resposta retomada, Parar pedido, Central e Configurações.
  - `useChat.ts`: tratar WS `agent_progress` (estado `agentProgress` exposto) e `agent_reply` (se for a conversa ativa: com turno aberto, vira a resposta final; sem turno, acrescenta mensagem do assistente com `run_id`). O vigia de turno passa a preferir `run.reply` a `result_summary`. O tratamento de `awaiting_confirmation` passa a dizer "Aguardando aprovação na Central; depois eu continuo sozinho."
  - `ChatPage.tsx` (ou onde o balão "Pensando…" é desenhado): linha "Etapa 3 de 8 · 3/10 chamadas ao modelo" com a fase em texto ("planejando", "executando", "verificando", "aguardando aprovação"). O botão "Parar pedido" existente continua sendo o cancelamento (o Run volta a `running` na retomada, então `useConversationRun` o encontra).
  - `useMediaAssistant.ts`: SSE `progress` atualiza o status da ligação ("Etapa 2 de 8…").
  - `RunHistory.tsx`: mostrar `progress` e `reply` quando existirem.
  - `SettingsPage.tsx`: seção nova `agent` ("Agente e popups", ícone `Bot` do lucide) com modo (Automático / Sempre / Desligado, com explicação curta), limites de etapas e de chamadas ao modelo (campos numéricos com limites), verificação automática; salva em `/api/settings/agent-loop`; erro do servidor aparece na tela.
  Arquivos: `frontend/src/hooks/useChat.ts`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/hooks/useMediaAssistant.ts`, `frontend/src/components/RunHistory.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/styles/workspace.css` ou `settings.css`.

- [ ] 2.7 Testes da Fase 2.
  - Novo `tests/test_loop_policy.py`: frases da seção b (exemplo da usuária → loop; saudações, perguntas e pedido único → não; `off`/`always`; modos excluídos).
  - Novo `tests/test_agent_loop.py` (fixture no padrão `runtime` de `test_conversation_runtime.py` + `isolated_lote6_data` quando usar ferramentas reais): lote `ACOES` com 3 ações em 1 chamada + FINISH = 2 chamadas e um Run com 3 ações; limite de chamadas encerra sem chamada extra e resposta por regra; limite de etapas; verificação registra leitura `observe` no mesmo Run e detecta divergência (registry falso que "esquece" o item); pausa por aprovação → `actions.handle_actions_post(.../approve)` com `resume_runner` síncrono executa ações restantes e novo planejamento no **mesmo** Run, termina `succeeded` com `reply`, histórico da sessão recebe a resposta; recusar encerra sem nova chamada; cancelar enquanto aguarda descarta o checkpoint e aprovar depois devolve 409 sem retomar; aprovação que chega durante o turno continua uma vez só (sem dupla execução); eventos `agent_progress` publicados (assinar `ui_events`); ferramenta fora da lista do turno bloqueada; orquestrador em `general` usa o loop no pedido de várias partes e o caminho nativo no simples.
  - Novo `tests/test_agent_loop_settings.py`: GET/POST `/api/settings/agent-loop` com limites (padrão de `tests/test_settings_api.py`).
  - Atualizar `tests/test_conversation_runtime.py` (mudança de contrato planejada): `test_react_waits_for_bound_approval_without_resuming_loop` → passa a provar que retoma (prompts 2, Run `succeeded`, `reply == "feito"`); `test_approval_can_arrive_as_soon_as_react_proposal_is_visible` → continua uma vez só e consome o FINISH. Ajustar o fixture `runtime` para `resume_runner` síncrono.
  - Novo smoke `frontend/tests/agent-loop.smoke.cjs`: WebSocket falso (classe no `addInitScript` que guarda a instância e expõe `window.__wsEmit(obj)` chamando `onmessage`); emitir `agent_progress` → texto "Etapa 2 de 8" visível; `agent_reply` → mensagem do assistente aparece; Configurações > "Agente e popups" salva e envia POST com os valores; sem erros de página; 360 px sem rolagem horizontal.
  Verificar: `& $PY -B -m pytest -q -p no:cacheprovider tests/test_loop_policy.py tests/test_agent_loop.py tests/test_agent_loop_settings.py tests/test_tool_ops_lote6.py` + R; `tsc`; smoke `agent-loop.smoke.cjs` e `chat-cancel.smoke.cjs` (regressão do Parar pedido). Commit.

### FASE 3 — Infraestrutura de popups (feature 3 base, chat e voz)

Depende da Fase 2 (barramento `ui_events`).

- [ ] 3.1 Backend de popups.
  `app/agent/popups.py` (seção c) com o template `info` e o mecanismo automático vazio (mapa preenchido na Fase 4); `app/agent/tools/show_popup.py` registrada em `GENERAL_TOOL_NAMES` e no catálogo (observe); gancho `after_tool_success` no `ActionExecutor._execute`; coletor `current_popups` aberto em `handle_request` e copiado para `plan.context["ui_popups"]` (também na retomada do loop); SSE `{"status": "popup"}` em `handle_request_stream`; `GET /api/popups/<template>` em `app/ui/panel/api/popups.py` ligado no `server.py`; configuração `popups` (`get/set_popup_settings`, `GET/POST /api/settings/popups`). Descrição de `show_popup` diz ao modelo que popups de hábitos/agenda/água aparecem sozinhos depois das ferramentas; usar `show_popup` só para mostrar algo pedido ("mostra minha água") ou `live_notes`.
  Arquivos: `app/agent/popups.py`, `app/agent/tools/show_popup.py`, `app/agent/tools/registry.py`, `app/agent/tools/catalog.py`, `app/agent/action_executor.py`, `app/agent/orchestrator.py`, `app/ui/panel/api/popups.py`, `app/ui/panel/server.py`, `app/storage/runtime_settings.py`, `app/ui/panel/api/settings.py`.

- [ ] 3.2 Primitivas de animação e estilo.
  `frontend/src/popups/motion.tsx` com as 7 primitivas da seção d e `frontend/src/styles/popups.css` (escopo `.ws-popup-*`, só tokens `--ws-*`, regra `@media (prefers-reduced-motion: reduce)`), importado onde os outros CSS do workspace são importados.
  Arquivos: `frontend/src/popups/motion.tsx`, `frontend/src/styles/popups.css`, `frontend/src/main.tsx` ou `App.tsx` (import do CSS).

- [ ] 3.3 Fila/pilha e host.
  `frontend/src/popups/types.ts` (envelope), `registry.ts` (template `info`; `parseData`), `PopupProvider.tsx` (lógica de fila da seção c em funções puras exportadas, ex. `reducePopups(state, action)`), `PopupHost.tsx`, `templates/InfoPopup.tsx`. `App.tsx`: envolver com `PopupProvider` dentro do `WindowProvider`, renderizar `PopupHost` junto do `WindowHost`; `applyAgentUi(context)` mostra `context.ui_popups`; `useChat` ganha `onPopup` para WS `ui_popup`; `useMediaAssistant` ganha `onAgentContext` (SSE `popup` e `plan.context` do `complete`) para a ligação. Ler `popups.max_visible`/`ttl_seconds` de `/api/settings/popups` uma vez no início (falha → padrões).
  Arquivos: `frontend/src/popups/*`, `frontend/src/App.tsx`, `frontend/src/hooks/useChat.ts`, `frontend/src/hooks/useMediaAssistant.ts`.

- [ ] 3.4 Comandos `/` e paleta.
  Em `commands/registry.ts`: nova ação `{ kind: 'popup'; template: string }` e handler `openPopup(template, args)` em `CommandHandlers`; no `App.tsx` o handler busca `GET /api/popups/<template>` e mostra (origem `command`). Comando base desta fase: nenhum template de dados ainda; adicionar a entrada de paleta "Fechar popups" (`local`, operação nova `clear-popups`). Configurações: na seção "Agente e popups" (criada na Fase 2), campos "Mostrar popups", "Popups automáticos", "Fechar sozinho após (s)" e "Máximo na tela".
  Arquivos: `frontend/src/commands/registry.ts`, `frontend/src/App.tsx`, `frontend/src/pages/SettingsPage.tsx`.

- [ ] 3.5 Testes da Fase 3.
  - Novo `tests/test_popups_infra.py`: validação de template/parâmetros (desconhecido recusado, parâmetro extra recusado, texto longo recusado); `show_popup` pelo executor em turno de chat publica um `ui_popup` no barramento e aparece em `plan.context["ui_popups"]`; turno de voz idem com `origin="voice"`; `run_action` com `origin="window"` não emite; popups desligados nas configurações não emitem; falha no builder não derruba a ação (ação continua `succeeded`); `GET /api/popups/info` com servidor de teste; SSE de `/api/chat/stream` contém `status: popup`.
  - Novo `tests/test_popups_mirror.py`: ids de template em `app/agent/popups.py` iguais aos de `frontend/src/popups/registry.ts` (ler como texto).
  - Novo smoke `frontend/tests/popups.smoke.cjs` (WebSocket falso da Fase 2): `info` aparece e some após o ttl; mesma `key` atualiza sem empilhar; 5 popups → 3 visíveis e os outros entram quando um fecha; Fixar impede expirar; `Esc` fecha o focado; `emulateMedia({ reducedMotion: 'reduce' })` sem animação; popup via `context.ui_popups` no `complete` com o mesmo `id` não duplica; 360 px sem rolagem horizontal; clique fora não é bloqueado.
  Verificar: `& $PY -B -m pytest -q -p no:cacheprovider tests/test_popups_infra.py tests/test_popups_mirror.py tests/test_agent_loop.py` + R; `tsc`; smoke `popups.smoke.cjs` e `agent-loop.smoke.cjs`. Commit.

### FASE 4 — Templates de popup: hábitos, agendamento, água, anotações ao vivo (feature 3 templates)

Depende da Fase 3.

- [ ] 4.1 Builders e popups automáticos no backend.
  Em `app/agent/popups.py`: templates `habit_list`, `schedule`, `water`, `live_notes` (seção c); `popups_for_result` mapeando habit_tool, calendar e lifeos_tool (operações da tabela) para popup com `added_ids`/`checked_ids`/`from_ml`/`to_ml` vindos de `result.data` e listas relidas dos serviços. `/api/evolute/water/add` (usado pelo `/agua`) devolve também o popup `water` montado (campo `popup`), sem mudar os campos atuais.
  Arquivos: `app/agent/popups.py`, `app/ui/panel/server.py` (rota de água).

- [ ] 4.2 Salvar anotação ao vivo pelo Kernel.
  `POST /api/notes/live` (`app/ui/panel/api/notes_live.py`, só loopback como `voice_capture.py`): valida `draft_id`, `title`, `format`, `content` (≤ 20.000), monta o título estável e chama `run_action("vault_save_note", {"title", "content", "folder": "05-Notas"}, source="popup:live_notes", user_text="Salvar anotação", origin="window")`. Responde `ok`, `path` relativo ao cofre, `action` (para a Central). Falha real vira erro, nunca sucesso.
  Arquivos: `app/ui/panel/api/notes_live.py`, `app/ui/panel/server.py`.

- [ ] 4.3 Componentes dos templates.
  `frontend/src/popups/templates/HabitListPopup.tsx` (`StaggerList`, selo de concluído, streak com `CountUp`), `SchedulePopup.tsx` (linha do tempo do dia, item novo com `InsertHighlight`, horários formatados em pt-BR), `WaterPopup.tsx` (`LiquidGauge` de `previous_ml` a `current_ml` contra `target_ml`, texto "1.500 de 3.000 ml"), `LiveNotesPopup.tsx` (`TypewriterText`, seletor Texto/Lista/Checklist, Gravar/Parar, Salvar, estado "salvo"/"rascunho local"/erro; edição manual sempre possível). Registrar em `popups/registry.ts` com `parseData` estrito.
  Arquivos: `frontend/src/popups/templates/*.tsx`, `frontend/src/popups/registry.ts`, `frontend/src/styles/popups.css`.

- [ ] 4.4 Ditado ao vivo (chat e ligação).
  Criar `frontend/src/hooks/useLiveDictation.ts`: escolhe o motor (decisão 12) reaproveitando as funções de captura do `useMediaAssistant.ts` (extrair para `frontend/src/utils/backendCapture.ts` só o que for preciso: start/stop/poll de `/api/voice/capture/*`); emite `onPhrase(text)` e `onInterim(text)`; reconhece as frases de parada. No `useMediaAssistant.ts`, adicionar `dictationSinkRef`: durante a ligação, se um popup `live_notes` estiver gravando, `dispatchBackendSpeech` e o caminho do navegador entregam o texto ao sink em vez de `sendTextStreamAndPlay`, e a ligação mostra "Anotando…". O popup registra/remove o sink pelo `usePopups`/contexto. Fora da ligação, o popup usa o próprio `useLiveDictation`; se o microfone do PC estiver ocupado, cai no navegador e avisa.
  Arquivos: `frontend/src/hooks/useLiveDictation.ts`, `frontend/src/utils/backendCapture.ts`, `frontend/src/hooks/useMediaAssistant.ts`, `frontend/src/popups/templates/LiveNotesPopup.tsx`.

- [ ] 4.5 Comandos sem IA.
  Em `commands/registry.ts` (grupo Life OS): `/habitos` → popup `habit_list`; `/hidratacao` → popup `water`; `/compromissos` → popup `schedule` de hoje; `/nota [título]` → popup `live_notes` (`argHint: 'título'`, `worksOffline: true`: escrever à mão funciona sem IA; ditado precisa de STT e a tela diz isso). `/agua` continua somando 250 ml e passa a mostrar o popup `water` devolvido pela rota.
  Arquivos: `frontend/src/commands/registry.ts`, `frontend/src/App.tsx`.

- [ ] 4.6 Testes da Fase 4.
  - Novo `tests/test_popup_templates.py` (com `isolated_lote6_data`): habit_tool `create_many` em turno de chat gera **um** `habit_list` com `added_ids` na ordem e itens relidos do banco tmp; duas chamadas seguidas geram dois eventos com a mesma `key`; `calendar.create_reminder` gera `schedule` do dia com o evento; `set_water` 1.000 → 3.000 gera `water` com `previous_ml=1000`, `current_ml=3000`, `target_ml` do Life OS tmp; popup automático desligado não emite; `show_popup(live_notes)` valida formato; `POST /api/notes/live` grava em `tmp/vault/05-Notas` pelo Kernel (ação na Central com `origin` window), salvar de novo sobrescreve o mesmo arquivo, conteúdo grande recusado, pedido não local recusado; o cenário completo da usuária pelo loop (registry real das ferramentas pessoais, `ask` falso com um `ACOES` de 4 itens: `open_screen`, `habit_tool.create_many`, `calendar.create_reminder`, `lifeos_tool.set_water`) produz um Run com as 4 ações + leituras de verificação e três popups (`habit_list`, `schedule`, `water`) em `plan.context["ui_popups"]`.
  - Ampliar `frontend/tests/popups.smoke.cjs`: `habit_list` com 3 novos mostra os itens entrando um a um (registrar a ordem com `MutationObserver` em `data-popup-item`); `water` termina mostrando "3.000 de 3.000 ml" e "meta batida" (e com movimento reduzido mostra o valor final já no primeiro quadro); `schedule` destaca o item novo; `/habitos` e `/hidratacao` chamam `/api/popups/...` e nunca `/api/chat`; `/nota Compras` + digitação manual + formato Checklist + Salvar envia `POST /api/notes/live` com `- [ ] ` por linha; servidor com erro 500 mantém o rascunho e mostra o erro; ditado simulado (mock de `/api/voice/capture/start|events|stop` devolvendo eventos `transcript`) escreve as frases no popup e "fim da nota" para a gravação.
  Verificar: `& $PY -B -m pytest -q -p no:cacheprovider tests/test_popup_templates.py tests/test_popups_infra.py tests/test_agent_loop.py tests/test_tool_ops_lote6.py` + R; `tsc`; smoke `popups.smoke.cjs`. Commit.

### FASE 5 — Extras (feature 4)

Depende da Fase 4 (primitivas e templates).

- [ ] 5.1 Serviço e ferramenta de lugares.
  `app/services/places.py`: `search_places(query, near="") -> dict` com Nominatim (política da seção e: User-Agent, 1 req/s com trava, cache 100×24 h, `email` opcional da configuração, `timeout` 8 s, `urllib.request` como `app/services/realtime.py`) e Google Places (só com chave `google_places` em `get_api_keys()`; conferir como as chaves são nomeadas em `runtime_settings.get_api_keys`/`set_api_keys` e no `SettingsPage.tsx`, adicionando o campo "Google Places API Key (opcional)"). Resultado normalizado (seção c) com `provider` e `bbox`. Erro de rede vira `ok: False` com motivo, nunca lista vazia fingindo sucesso. `app/agent/tools/places_search.py` (observe, catálogo com escopo "envia o texto da busca ao OpenStreetMap ou ao Google"), em `GENERAL_TOOL_NAMES` e no mapa de palavras-chave do Groq (`lugar`, `perto`, `endereco`, `mapa`, `onde fica`).
  Arquivos: `app/services/places.py`, `app/agent/tools/places_search.py`, `app/agent/tools/registry.py`, `app/agent/tools/catalog.py`, `app/storage/runtime_settings.py` (se precisar de `places_email`), `frontend/src/pages/SettingsPage.tsx`.

- [ ] 5.2 Popup e janela de lugares.
  Template `places` no backend (automático depois de `places_search`) e no frontend (`PlacesPopup.tsx`: lista com `StaggerList`, botão "Ver no mapa" que abre a janela). Janela `places` (`frontend/src/windows/PlacesWindow.tsx` + `windows/registry.ts` + espelho em `app/agent/tools/open_window.py` com parâmetro `query`): campo de busca (envia só ao confirmar, sem autocompletar), lista, `iframe` do mapa OSM centrado no resultado escolhido, atribuição OSM visível, link externo. Rota `GET /api/places?q=&near=` (`app/ui/panel/api/places.py`) para a janela sem IA, passando pelo Kernel com `run_action("places_search", ..., origin="window")` (aparece na Central, é uma consulta a terceiros). Comando `/lugares <busca>` abre a janela com a busca.
  Arquivos: `app/agent/popups.py`, `app/ui/panel/api/places.py`, `app/ui/panel/server.py`, `app/agent/tools/open_window.py`, `frontend/src/windows/PlacesWindow.tsx`, `frontend/src/windows/registry.ts`, `frontend/src/popups/templates/PlacesPopup.tsx`, `frontend/src/popups/registry.ts`, `frontend/src/commands/registry.ts`.

- [ ] 5.3 Popup de tarefas.
  Template `task_list` (backend automático para task_tool create/create_many/toggle/update; frontend `TaskListPopup.tsx` com `StaggerList` e risco visual de concluída); comando `/pendencias`.
  Arquivos: `app/agent/popups.py`, `frontend/src/popups/templates/TaskListPopup.tsx`, `frontend/src/popups/registry.ts`, `frontend/src/commands/registry.ts`.

- [ ] 5.4 Testes da Fase 5.
  - Novo `tests/test_places.py` (`monkeypatch` em `urllib.request.urlopen`, nenhuma rede real): URL e `User-Agent` corretos, `accept-language=pt-BR`; segunda busca igual vem do cache sem rede; duas buscas diferentes seguidas respeitam ≥1 s (relógio falso via `monkeypatch` de `time.monotonic`/`time.sleep`); sem chave usa OSM; com chave usa Google com os cabeçalhos certos e cai no OSM se o Google falhar (resultado diz o provedor); erro de rede → `ok False`; ferramenta observe no catálogo; `GET /api/places` cria Run com origem `window`; popup `places` automático.
  - Ampliar `tests/test_popup_templates.py` com `task_list`; ampliar `tests/test_open_window.py` com a janela `places` (parâmetro `query` válido/ inválido).
  - Ampliar `popups.smoke.cjs`: popup `places` com 3 resultados; `/lugares padaria` abre a janela, a busca só dispara ao enviar, o `iframe` recebe `bbox`/`marker`, atribuição visível; `task_list` animada.
  Verificar: `& $PY -B -m pytest -q -p no:cacheprovider tests/test_places.py tests/test_popup_templates.py tests/test_open_window.py` + R; `tsc`; smoke `popups.smoke.cjs`. Commit.

### FASE 6 — Integração final, build do frontend e smoke tests

- [ ] 6.1 Verificação cruzada completa.
  Rodar todos os arquivos novos e R juntos:
  `& $PY -B -m pytest -q -p no:cacheprovider tests/test_tool_ops_lote6.py tests/test_open_screen.py tests/test_loop_policy.py tests/test_agent_loop.py tests/test_agent_loop_settings.py tests/test_popups_infra.py tests/test_popups_mirror.py tests/test_popup_templates.py tests/test_places.py` + R. Corrigir as costuras entre fases (ex.: verificador da Fase 2 para operações da Fase 5, popups na retomada do loop, `applyAgentUi` cobrindo janela + tela + popups no chat e na voz).

- [ ] 6.2 Frontend.
  Em `frontend/`: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` e `npm run build` (sem avisos novos de chunk acima de 800 kB; se `popups` pesar, manter os templates em `lazy`). Conferir que `mobile_app/` não mudou (`git status -- mobile_app`).

- [ ] 6.3 Smoke tests.
  Rodar `chat-cancel.smoke.cjs`, `runs.smoke.cjs`, `workspace.smoke.cjs`, `agent-loop.smoke.cjs`, `popups.smoke.cjs` contra o Vite de teste (seção 0). Se algum smoke antigo quebrar por texto mudado planejado (ex.: aviso de aprovação), atualizar o teste e registrar.

- [ ] 6.4 Definição de pronto e documentação.
  Conferir para cada entrega a seção 8 do plano mestre (Kernel, sem IA, `/comando`, Central com origem, números da API, teste do caminho principal e de um erro, segurança). Sincronização: confirmar que as configurações novas passam por `runtime_settings._write` e que as notas novas ficam no cofre já sincronizado; registrar o que não sincroniza. Atualizar `docs/CONTEXTO_PARA_CHATGPT.md` (seção 13: marcar C8 e AQ5 como entregues no lote 6, J11 com a solução OSM/Google; situação do lote 6) e escrever `.agents/tasks/lote6/report.md` no formato do relatório do lote 5: o que mudou por fase, commits, como testar com o app real (roteiro da frase de exemplo da usuária por chat e por voz, `/nota` ditando, `/lugares`), dependências (nenhuma nova de pip/npm esperada), pendências e o que nunca foi verificado no app real.
  Verificar: tudo de 6.1 a 6.3 verde. Commit final `feat(lote6): integracao final e docs`. Sem push.
