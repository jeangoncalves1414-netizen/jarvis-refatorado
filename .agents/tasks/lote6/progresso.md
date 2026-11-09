# Progresso do lote 6

## Fase 1: inventário e expansão do catálogo/comandos

**Status:** feita (itens 1.1 a 1.8 do plano).

### O que mudou
- 1.1 `tests/conftest.py`: fixture não autouse `isolated_lote6_data` (cwd em tmp; `lifestyle.db`, Life OS, cofre, `runtime_settings`, auto-aprovações e Central em tmp). Devolve `store` e `root`.
- 1.2 Cofre: as 4 ferramentas (`vault_search`, `vault_daily_log`, `vault_save_note`, `vault_update_profile`) ganharam `parameters`, validação e descrições, entraram em `GENERAL_TOOL_NAMES` e no catálogo. `vault_save_note` só aceita 01-Daily-Notes, 03-Priming-Notes, 04-Projects e 05-Notas (padrão 05-Notas; a pasta é criada pelo próprio `save_note`), título 1-120 e conteúdo até 20.000; devolve caminho relativo ao cofre. Entrada órfã `notes` removida do catálogo e do `core_groq`.
- 1.3 Operações novas: habit_tool `create_many`, `check_many`, `update` com `new_name`/`category`/`routine_block`, `list only_today`, busca por nome sem acento/maiúscula (delete só com nome exato; ambíguo → erro listando candidatos). task_tool `create_many`, `update` (novo `TaskService.update_task`), `list include_completed`, toggle/delete por título. finance_tool `add_many`, `update` (via `FinanceService.update_transaction`), `list` com `period`/`type`/`category` (via `query_transactions`). lifeos_tool `set_water` (novo `LifeOSService.set_water`, devolve `previous_ml`), `add_water` limitado a 1-5.000. calendar `create_many` e `list` com `day`/`upcoming_days`. timer `cancel` por rótulo (`_TimerManager.cancel`). Lotes validam tudo antes de gravar.
- 1.4 Catálogo: entrada para toda ferramenta geral (cinema, clipboard_intelligence, document_generator, image_generator, jarvis_mode, news_reader, phantom_typer, proactive_agent, qr_reader, screen_peeler, smart_drop_zone, system_tray, telegram_bot, wallpaper_engine, wormhole, vault_*, open_screen); calendar e timer com risco por operação; `target_detail` de lote ("3 hábitos: Ler, Correr, Meditar", "2 lançamentos, total R$ 80,00", "total do dia: 3.000 ml").
- 1.5 `open_screen` (observe, ids iguais a `navigation.ts`, apelidos em português). Frontend: `extractScreenRequest` em `navigation.ts`; `App.tsx` ganhou `applyAgentUi(context)` (janela + tela); `useChat` troca `onOpenWindow` por `onAgentContext`. Orquestrador nativo grava `tool_calls` (todas as chamadas em ordem) além de `tool_results`; caminho de marcadores repassa `open_screen`. Groq: mapa de palavras-chave → ferramenta.
- 1.6 Descrições reescritas (hábitos × Life OS, lote, formatos de data); REGRA Nº 2 do prompt cita as ferramentas novas e "uma chamada em lote".
- 1.7 `app/agent/tools/inventory.py` (`build_inventory`, `render_markdown`, `python -m app.agent.tools.inventory`). Inventário ANTES/DEPOIS em `.agents/tasks/lote6/inventario.md`.
- 1.8 Testes novos: `tests/test_tool_ops_lote6.py` (13), `tests/test_open_screen.py` (10); `tests/test_tool_catalog.py` ampliado (contrato de todas as ferramentas gerais, riscos novos, detalhes de lote, inventário).

### Testes rodados
- `python -B -m pytest -q -p no:cacheprovider tests/test_tool_ops_lote6.py tests/test_open_screen.py tests/test_tool_catalog.py` → 122 passed (primeira tentativa).
- Novos + conjunto R + `tests/test_tools_smoke.py` (17 arquivos) → 1ª rodada: 1 falha (`test_action_proposals::test_every_catalog_tool_has_a_complete_declared_proposal`: `jarvis_mode` sem argumentos não tinha efeito declarado). Corrigido com `effect` na entrada do catálogo. 2ª rodada: **293 passed**.
- Frontend: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` → limpo.
- Nenhum teste usou `data/lifestyle.db` nem `data/action_journal.sqlite3` (fixture `isolated_lote6_data` / `tmp_path`). A suíte completa e `tests/test_habits_tasks_finance.py` não foram rodadas.

### Decisões
- Arquivo do inventário: `inventario.md` (nome pedido na instrução da fase; o plano dizia `inventario-ferramentas.md`). Status em `progresso.md` em vez de `fase-1.md`, também pela instrução.
- `smart_drop_zone` subiu para high com aprovação (move arquivos em massa em Downloads/Área de Trabalho; desfazer é manual). `document_generator` é low, mas vira high quando o agente passa `output_path` (pode sobrescrever qualquer arquivo). `telegram_bot.start_bot` também high (abre controle remoto pelo Telegram). Com o Modo liberado nada disso pede aprovação.
- `clipboard_intelligence`, `qr_reader`, `news_reader` e `cinema.search/discover/detect_url` = observe (só leem); `screen_peeler`, `wallpaper_engine`, `image_generator`, `jarvis_mode` = low.
- `jarvis_mode` sem `command` cai em critical (fecha para o mais estrito); a ferramenta recusa de qualquer forma.
- Validação de pasta do cofre ficou na ferramenta; as rotas antigas do painel (`/api/vault/notes`) continuam chamando `save_note` sem essa checagem (fora do escopo da fase; pendência abaixo).
- Busca por nome: nome exato primeiro; sem exato, check/uncheck/update/toggle aceitam um único nome que contenha o texto; delete exige nome exato.
- `habit_tool create` agora recusa dia da semana desconhecido (antes gravava o texto cru).
- `phantom_typer`, `screen_peeler` e `smart_drop_zone` ganharam `parameters` tipados (antes `{}`).

### Pendências
- Rota `/api/vault/notes` do painel (server.py e api/vault.py) ainda aceita `folder` livre; aplicar `NOTE_FOLDERS` lá numa fase futura.
- O frontend não tem smoke test de `open_screen`; só `tsc`.

### Commit
- `a49a907` feat(lote6): fase 1 - catalogo completo, operacoes em lote e open_screen (local, sem push).


## Fase 2: loop agêntico (C8, AQ5, Parar pedido, configuração)

**Status:** feita (itens 2.1 a 2.7 do plano). Relançada depois da interrupção do PC.

### Trabalho parcial encontrado
- `app/core/ui_events.py`, `app/core/loop_checkpoints.py` e `app/agent/loop_policy.py` (não versionados, da execução interrompida) compilavam e batiam com o plano. Mantidos sem mudança.
- Decisão: `ui_events.py` pertence à Fase 2 (item 2.1: barramento `agent_progress`/`agent_reply`). O `ContextVar current_popups` já declarado nele fica sem uso até a Fase 3, como o plano prevê.

### O que mudou
- 2.1 Barramento: `server.py` assina `ui_events` ao subir o WebSocket do chat (`_forward_ui_event` → `_broadcast_json` para todos os `_ws_clients`, mesmo padrão de `_broadcast_wake_word`); cancela a assinatura ao parar.
- 2.2 Configuração `agent_loop` em `runtime_settings.py` (`get/set_agent_loop_settings`: `mode` auto/always/off, `max_steps` 1-20 (8), `max_model_calls` 1-30 (10), `auto_verify` (true); valida tudo antes de gravar, campo desconhecido recusado, mensagens em pt-BR; arquivo corrompido volta aos padrões). Rotas `GET/POST /api/settings/agent-loop` (resposta `{ok, settings}`).
- 2.3 `RunRecord` ganhou `resume_pending`, `reply`, `progress`. `ActionStore`: `set_resume_pending`, `finish_resume`, `update_run_progress` (sem evento na Central), `finish_run(..., reply=None)`; `_refresh_run` nunca encerra um pedido com `resume_pending` (fica `awaiting_confirmation` ou `running`); `cancel_run` limpa a pendência e chama `loop_checkpoints.discard_for_run`.
- 2.4 `react_loop.py` reescrito sobre o mesmo motor: `run_loop` aceita `allowed_tools`, `max_model_calls`, `progress`, `verify`, `history`, `save_reply` (o construtor também aceita `allowed_tools`/`budget`/`progress`/`verify` como padrões). Parser `parse_plan`: `ACOES:` (1-5, JSON, cercas ``` aceitas) e formato antigo; plano inválido nada executa. Prompt compacto (ferramentas do turno com descrição ≤160 e esquema reduzido, 6 etapas ×200, 4 mensagens ×300, orçamento visível). Orçamento: limite encerra sem nova chamada e responde por regra ("Fiz X de Y etapa(s): … Parei no limite de N …. Confira na Central."). `ReActTrajectory` ganhou `model_calls`, `max_steps`, `max_model_calls`, `stopped_reason`. Novo `app/agent/verification.py` (hábitos criados/marcados, tarefas, lançamentos, água, lembretes, nota do cofre) roda a leitura `observe` pelo mesmo executor, no mesmo Run.
- Retomada (C8): etapa aguardando aprovação marca `resume_pending` **antes** de registrar o checkpoint, relê a ação; se a aprovação já terminou durante o turno e `take` vence, continua na mesma thread (uma vez só). Senão devolve "A etapa N precisa da sua aprovação na Central: … Assim que você aprovar, eu continuo sozinho." A retomada define `current_run`/`current_origin`, executa o resto do lote, volta a planejar, grava o histórico da sessão, `finish_resume(reply=…)` e publica `agent_reply`.
- 2.5 `loop_policy.should_use_agent_loop` no `_dispatch_request` (depois de Racing, atalho local e checagem da chave; ferramentas = `registry.allowed_tool_names(mode="general", provider, text)`); `plan.intent = "agent_loop"` (modo react continua `react_loop`), contexto com `steps_count`, `model_calls`, `max_steps`, `max_model_calls`, `pending_action_id`, `stopped_reason`. `react_max_steps` padrão virou `None` (= configuração); `/api/react` sem `max_steps` usa a configuração. `handle_request(on_progress=…)` e `handle_request_stream` entregam `{"status": "progress", …}`. `api/actions.py`: aprovar retoma (`take` depois do callback, resposta com `resumed`), recusar/expirar/cancelada-antes-de-iniciar chamam `abandon`.
- 2.6 Frontend: `useChat` trata WS `agent_progress` (estado `agentProgress`) e `agent_reply` (turno aberto → resposta final; sem turno → mensagem nova com `run_id`, sem duplicar, histórico salvo); vigia prefere `run.reply`; aviso "Aguardando aprovação na Central; depois eu continuo sozinho.". `ChatPage` mostra "Etapa 3 de 8 · 3/10 chamadas ao modelo · planejando" no balão (e "Continuando a sequência…" fora do turno). `useMediaAssistant`: SSE `progress` na linha de status da ligação; resposta do loop (sem pedaços transmitidos) é falada a partir de `plan.summary`. `RunHistory`: progresso e "Resposta do agente" no detalhe, contador na linha do pedido ativo, rótulos dos eventos de retomada. Configurações: seção "Agente e popups" (ícone `Bot`) com `AgentLoopSettings.tsx` (modo com explicação, limites, verificação automática, erro do servidor na tela).

### Testes rodados
- `tests/test_conversation_runtime.py tests/test_god_mode_components.py` → 38 passed (após atualizar os contratos planejados).
- `tests/test_loop_policy.py tests/test_agent_loop.py tests/test_agent_loop_settings.py` → 51 passed (primeira tentativa).
- Fase + R + `test_tool_ops_lote6.py` + `test_god_mode_components.py` (19 arquivos) → **336 passed**.
- `tsc --noEmit` limpo; `npm run build` ok.
- Smoke (Vite 5174, APIs simuladas): `agent-loop.smoke.cjs` PASS; `chat-cancel.smoke.cjs` PASS.
- Nenhum teste tocou `data/` real (fixture `isolated_lote6_data`; fixture `runtime` agora também põe `runtime_settings` em tmp). Suíte completa e `test_habits_tasks_finance.py` não rodadas.

### Mudanças de contrato em testes existentes (planejadas)
- `test_react_waits_for_bound_approval_without_resuming_loop` → `..._then_resumes_loop`: 2 prompts, Run `succeeded`, `reply == "feito"`, histórico recebe a resposta.
- `test_approval_can_arrive_as_soon_as_react_proposal_is_visible`: continua uma vez só (2 prompts, 1 execução) e consome o FINISH.
- `test_react_real_whiteboard_approval_targets_only_original_conversation`: ganhou o `FINISH` que a retomada consome.
- Fixture `runtime`: `resume_runner` síncrono, checkpoints limpos, `runtime_settings` em tmp.
- `chat-cancel.smoke.cjs` já falhava antes desta fase (o selo do Modo liberado quebra com `/api/approvals` simulado como `{ok:true}`); a simulação ganhou `/api/approvals` com `mode`. Nenhum componente mudou por isso.

### Decisões
- Orçamento e lista de ferramentas são por chamada de `run_loop` (o orquestrador monta a lista a cada turno); o construtor aceita os mesmos valores como padrão. Assim os testes antigos que trocam `agent.react_loop` continuam valendo.
- Modo "Execução por etapas" (`react`) mantém `REACT_TOOLS`; o loop automático usa as ferramentas do turno do modo geral.
- Falha de **ação** encerra com "Execução encerrada com falha na etapa N" (regra antiga). Falha só de **verificação** não derruba o pedido: entra no histórico para o modelo corrigir e, se o modelo encerrar mesmo assim, a resposta ganha "Atenção: etapa N: verificação: …".
- Aprovação que chega enquanto a ferramenta ainda executa (estado `authorized`/`running` na releitura) fica com quem aprovou; o turno só toma o checkpoint quando a ação já está terminal.
- Recusar/expirar: Run vira `cancelled`/`failed` pela regra de contagem existente; `finish_resume(failed=False)` para recusa.
- `agent_reply` com turno aberto vira a resposta final daquele turno (texto do plano). Sem turno, entra como mensagem nova.
- Fala da ligação: só respostas `agent_loop`/`react_loop` sem pedaços são faladas a partir do resumo (não muda os outros caminhos).
- `loop_policy`: `always` também respeita os modos excluídos (tutor, planning, research, swarm, vision, coder); `react` sempre usa o loop, mesmo com `off`.

### Pendências
- A ligação por voz não fala a resposta **retomada** (`agent_reply` chega pelo WebSocket e entra no chat, mas não vai para o TTS da ligação).
- `/api/react` (botão do modo etapas) não mostra progresso em tempo real; usa o mesmo Run, visível na Central.
- Reinício do backend perde o checkpoint (decisão 5 do plano): o Run vira `interrupted` pela recuperação existente.

### Commit
- `22f7425` feat(lote6): fase 2 - loop agentico com verificacao, retomada apos aprovacao e contador (local, sem push).


## Fase 3: infraestrutura de popups (backend, primitivas de animação, fila/pilha, chat e voz)

**Status:** feita (itens 3.1 a 3.5 do plano).

### O que mudou
- 3.1 Backend: `app/agent/popups.py` (`POPUP_TEMPLATES` com `info`; `validate_popup_request`, `build_popup` no envelope da seção c, `emit`, `popups_for_result`, `after_tool_success`; `AUTO_POPUPS` vazio para a Fase 4). `ui_events.py` (da Fase 2, reaproveitado) ganhou `current_popup_session` e `current_popup_listener` ao lado de `current_popups`. Ferramenta `show_popup` (observe, catálogo, `GENERAL_TOOL_NAMES`, palavra-chave Groq `popup/mostra`), linha nova na REGRA Nº 2 do prompt. Gancho no `ActionExecutor._execute` depois de `succeeded`, dentro de `try/except`. `handle_request` abre o coletor (só no pedido de fora; chamada aninhada usa o mesmo) e grava `plan.context["ui_popups"]`; `handle_request(on_popup=…)` e `handle_request_stream` emitem `{"status": "popup", "popup"}` no SSE. A retomada do loop (`_with_run_context`) abre o próprio coletor. `run_action` com origem fora de chat/voz zera o coletor (janela nunca gera popup). `GET /api/popups/<template>` (`app/ui/panel/api/popups.py`, sem Run, origem `command`; listas como `?lines=a&lines=b`). Configuração `popups` (`get/set_popup_settings`: `enabled`, `auto`, `ttl_seconds` 0-120, `max_visible` 1-5) e `GET/POST /api/settings/popups`.
- 3.2 `frontend/src/popups/motion.tsx`: `motionTokens`, `useCalmMotion`, `PopupFrame`, `StaggerList`, `CountUp`, `LiquidGauge`, `TypewriterText`, `InsertHighlight`. `frontend/src/styles/popups.css` (escopo `.ws-popup-*`, só `--ws-*`, tokens `--ws-motion-*`, regra `prefers-reduced-motion`), importado em `main.tsx`.
- 3.3 `popups/types.ts`, `registry.ts` (`info`, `parsePopupEnvelope`, `extractPopups`), `PopupProvider.tsx` (`reducePopups` puro: fila FIFO, mesma `key` atualiza no lugar, `id` repetido descartado, `max_visible` ao vivo; lê `/api/settings/popups` uma vez), `PopupHost.tsx` (camada não modal `aria-live`, ttl só depois da entrada, pausa com mouse/foco, Fixar/Soltar, Fechar, Esc no popup focado, "+N na fila"), `templates/InfoPopup.tsx`. `PopupProvider` em `main.tsx` dentro do `WindowProvider`; `PopupHost` no `App.tsx`. `applyAgentUi` mostra `context.ui_popups`; `useChat` ganhou `onPopup` (WS `ui_popup`); `useMediaAssistant` ganhou `onAgentContext` (SSE `popup` e `plan.context` do `complete`).
- 3.4 `commands/registry.ts`: ação `{kind: 'popup', template, argParam?}`, handlers `openPopup(template, params)` (busca `/api/popups/...`) e `clearPopups`; entrada de paleta "Fechar popups" (operação local `clear-popups`). Configurações > "Agente e popups": `PopupSettings.tsx` ("Mostrar popups", "Popups automáticos", "Fechar sozinho após (s)", "Máximo na tela"), aplica o novo limite na hora.
- 3.5 Testes novos: `tests/test_popups_infra.py` (12), `tests/test_popups_mirror.py` (1), `frontend/tests/popups.smoke.cjs`.

### Testes rodados
- `tests/test_popups_infra.py` → 12 passed (primeira tentativa).
- Fase 3 + Fase 2 + `test_tool_ops_lote6` + `test_open_screen` + `test_god_mode_components` + conjunto R (22 arquivos) → **359 passed**.
- `tsc --noEmit` limpo; `npm run build` ok.
- Smoke (Vite 5174, APIs simuladas): `popups.smoke.cjs` PASS (2 correções no caminho: chave do React passou a ser `popup.key` para atualizar no lugar sem animar saída/entrada; o teste passou a clicar no item da paleta em vez de digitar antes de ela carregar). `agent-loop.smoke.cjs` PASS, `chat-cancel.smoke.cjs` PASS.
- `workspace.smoke.cjs` falha **antes** de qualquer passo de popup: a simulação dele devolve `/api/approvals` como `{ok:true}` e o selo do Modo liberado quebra (mesmo problema que a Fase 2 registrou no chat-cancel). Conferido com um script à parte: com `/api/approvals` simulado com `mode`, a tela carrega. Não corrigido aqui (fora da fase).
- Nenhum teste tocou `data/` real (`isolated_lote6_data`). Suíte completa e `test_habits_tasks_finance.py` não rodadas.

### Decisões
- `ui_events.py` da Fase 2 reaproveitado; o envelope do WS leva `session_id` do turno via `current_popup_session`.
- O evento WS `ui_popup` é tratado antes do filtro por conversa (como `wake_word`): a camada de popups é única do app e vale para a ligação e para retomadas.
- `enabled=false` desliga os popups do agente (chat/voz, explícitos e automáticos); comandos `/` e a paleta continuam abrindo popups (pedido direto da usuária).
- Popups só nascem num turno de conversa (coletor aberto). Ação aprovada pela Central fora do loop roda na thread de quem aprovou, sem coletor: não gera popup. A retomada do loop gera (barramento).
- A ligação por voz agora aplica todo o `plan.context` pelo `applyAgentUi` (popups e também `open_window`/`open_screen`), como o plano pede (função única).
- `ttl_seconds` aceita 0 a 120 (0 = fixo até fechar); o plano só dizia o padrão 8.
- `PopupProvider` fica no `main.tsx` (o `App` usa `usePopups`), ao lado do `WindowProvider`.

### Pendências
- `workspace.smoke.cjs`: simulação de `/api/approvals` desatualizada (pré-existente).
- O `useDirectChat` (celular) não mostra popups; `PopupHost` não é desenhado no modo celular (decisão 17).

### Commit
- `e28ae89` feat(lote6): fase 3 - infraestrutura de popups animados (fila, primitivas, show_popup, /api/popups, chat e voz) (local, sem push).


## Fase 4: modelos de popup (hábitos, agenda, água, anotação ao vivo)

**Status:** feita (itens 4.1 a 4.6 do plano).

### O que mudou
- 4.1 `app/agent/popups.py`: modelos `habit_list` (filter today/all, highlight; itens relidos do `HabitService`, `completed`, `total`, `highlight_ids`), `schedule` (date; compromissos do dia do `CalendarService`, em ordem), `water` (sem parâmetros; `get_daily_summary`, `previous_ml` vindo de `animate.from_ml`), `live_notes` (title ≤80, format text/bullets/checklist, dictate; `draft_id` novo, popup fixo `ttl_ms=0`). `AUTO_POPUPS`: habit_tool create/create_many (`added_ids`), check/check_many (`checked_ids`), update (`updated_ids`); calendar create_reminder/create_many (um `schedule` por dia, até 3); lifeos_tool add_water/set_water (`from_ml`/`to_ml`). Resultado com `ok=False` nunca gera popup. `PopupSpec.key` agora recebe `(params, data)` e há `sticky`. `build_popup` passa `animate` ao builder. `/api/evolute/water/add` devolve também `popup` (água), sem mudar os campos antigos.
- 4.2 `app/ui/panel/api/notes_live.py`: `POST /api/notes/live` (só loopback), valida `draft_id` (`[a-z0-9]{8,32}`), título 1-80, formato, conteúdo 1-20.000; grava por `run_action("vault_save_note", …, source="popup:live_notes", origin="window")` em `05-Notas`; responde `ok`, `path`, `title`, `action`. Aprovação pendente → 202; falha → 500 com a mensagem real. Ligado no despacho de POST do `server.py`.
- 4.3 Frontend: `HabitListPopup` (StaggerList, selo de feito em sequência, streak e "feitos hoje" com CountUp), `SchedulePopup` (linha do tempo, item novo com `data-new` + InsertHighlight, "Hoje/Amanhã" em pt-BR), `WaterPopup` (LiquidGauge de previous → current contra a meta, "3.000 de 3.000 ml", "meta batida", moldura `tone-ok`), `LiveNotesPopup` (TypewriterText durante o ditado, Texto/Lista/Checklist com reformatação, Gravar/Parar, Salvar, estados salvo/rascunho local/erro, rascunho em `localStorage` `lifeos_live_note_<draft_id>` até o servidor confirmar, salva ao parar o ditado, ao fechar e no botão). `popups/registry.ts` com `parseData` estrito dos 4 modelos; `popups/noteFormat.ts`; estilos em `popups.css`. `TypewriterText` ganhou `startAt` (texto já na tela não é redigitado).
- 4.4 `hooks/useLiveDictation.ts` (motor: ligação ativa → captura do PC → navegador → manual; frases de parada "fim da nota", "terminar anotação", "parar anotação"); `utils/backendCapture.ts` (`postCapture`, `LOOPBACK_HOSTS`, `fetchCaptureEvents`, extraídos do `useMediaAssistant`); `utils/dictationBus.ts` (ponte com a ligação). `useMediaAssistant`: com um popup de nota gravando durante a ligação, as falas (captura do PC, navegador e VAD do navegador) vão para a nota em vez do agente e a linha de status diz "Anotando…".
- 4.5 Comandos: `/habitos`, `/hidratacao`, `/compromissos`, `/nota [título]` (popup, sem IA). Ação `popup` ganhou `params` fixos. `/agua` continua somando 250 ml e mostra o popup devolvido pela rota.
- 4.6 Testes: `tests/test_popup_templates.py` (17) e `frontend/tests/popups.smoke.cjs` ampliado.

### Testes rodados
- `tests/test_popup_templates.py tests/test_popups_infra.py` → 29 passed (primeira tentativa).
- Fase 4 + Fases 1-3 + conjunto R (23 arquivos: popup_templates, popups_infra, popups_mirror, agent_loop, tool_ops_lote6, open_screen, loop_policy, agent_loop_settings, god_mode_components + R) → **376 passed**.
- `tsc --noEmit`: 1 erro de tipo no `useLiveDictation` (resposta do `/api/settings/mic`), corrigido; 2ª rodada limpa. `npm run build` ok.
- Smoke (Vite 5174, APIs simuladas): `popups.smoke.cjs` PASS na primeira execução (Fase 3 + hábitos entrando um a um registrados por MutationObserver, água "3.000 de 3.000 ml" e "meta batida", valor final no primeiro quadro com movimento reduzido, agenda com destaque, `/habitos` e `/hidratacao` sem `/api/chat`, `/nota Compras` + Checklist + Salvar com `- [ ] ` por linha, 500 mantém o rascunho e mostra o erro, ditado pela captura simulada e "fim da nota" para e salva). `agent-loop.smoke.cjs` PASS, `chat-cancel.smoke.cjs` PASS (regressão do `useMediaAssistant`).
- Nenhum teste tocou `data/` real (`isolated_lote6_data`; o registro global do gateway foi trocado por um com as ferramentas do teste). Suíte completa e `test_habits_tasks_finance.py` não rodadas.

### Decisões
- `habit_list` com `filter=today` inclui sempre os hábitos destacados: um hábito recém-criado para outro dia aparece no popup automático.
- Popup automático de hábitos destaca pelos nomes devolvidos pela ferramenta (`highlight`) e anima pelos ids (`added_ids`/`checked_ids`/`updated_ids`). `uncheck` não gera popup (fora da tabela do plano).
- `water.previous_ml` vem do resultado do serviço (`previous_ml`, ou total − adicionado) via `animate.from_ml`; `current_ml`, meta e % são relidos do Life OS no builder. No `/hidratacao`, `previous_ml = current_ml`.
- `live_notes` é fixo (`ttl_ms=0`) e o `draft_id` tem 16 caracteres. Título gravado no cofre = `"<título> (<6 primeiros do draft_id>)"` (arquivo `05-Notas/<Título>-<id>.md`): estável por rascunho e sem sobrescrever outra nota com o mesmo título. Conteúdo vazio é recusado.
- `/nota` abre com `dictate=false` (escrever à mão funciona sem IA; o botão Gravar liga o ditado). Pelo agente (`show_popup`), `dictate` padrão true começa a gravar sozinho.
- Durante o ditado o texto aparece com efeito de digitação; "Editar texto" para a gravação e volta à caixa editável (edição manual sempre disponível, sem gravar ao mesmo tempo).
- Ponte com a ligação por voz num módulo único (`dictationBus`) em vez de contexto React: a ligação informa se está ouvindo e entrega as falas ao destino registrado pelo popup.
- Removido o apelido `hidratacao` do comando `/agua`: agora `/hidratacao` só mostra a água (não soma 250 ml).

### Pendências
- O popup de nota não recebe o texto provisório da captura do PC (o backend só entrega frases inteiras); no navegador há texto provisório.
- `workspace.smoke.cjs` continua com a simulação de `/api/approvals` desatualizada (pré-existente, não rodado).

### Commit
- `d2a7b17` feat(lote6): fase 4 - popups de habitos, agenda, agua e anotacao ao vivo com ditado (local, sem push).


## Fase 5: extras (busca de lugares, janela e popup Lugares, popup de tarefas)

**Status:** feita (itens 5.1 a 5.4 do plano, extras 1 e 2 da seção e; o extra 3, `open_screen`, já tinha entrado na Fase 1).

### O que mudou
- 5.1 `app/services/places.py`: `search_places(query, near)` com Nominatim (`format=jsonv2`, `addressdetails=1`, `limit=8`, `accept-language=pt-BR`, `User-Agent: JarvisPessoal/0.1 (uso pessoal; desktop)`, timeout 8 s, trava global de 1 req/s, cache em memória 100 buscas × 24 h, `email` opcional) e Google Places (API New, Text Search, `X-Goog-Api-Key` + `X-Goog-FieldMask` do plano) só quando há chave `google_places`; falha do Google cai no OSM com `notice`. Resultado normalizado (`provider`, `results` [name, address, lat, lon, category, rating?], `bbox` [oeste, sul, leste, norte], `attribution`). Erro de rede → `ok: False` com motivo (nunca lista vazia fingindo sucesso, e nada vai ao cache). A chave nunca aparece no resultado nem nas mensagens. `cached_search` lê só o cache (sem rede).
- `runtime_settings`: `google_places` entrou nas chaves de API (`GOOGLE_PLACES_API_KEY(S)`, mesmo caminho de `get/set/sync_api_keys`, sincroniza pelo `_write`); `get_places_settings()` lê `places.email` (validado). Configurações > Provedores: campo "Google Places API Key (opcional)" com explicação.
- `app/agent/tools/places_search.py` (observe; catálogo com escopo "Envia o texto da busca ao OpenStreetMap ou ao Google"), em `GENERAL_TOOL_NAMES`, palavras-chave do Groq (`lugar`, `perto`, `endereco`, `mapa`, `onde fica`), linha nova na REGRA Nº 2 do prompt. A mensagem da ferramenta lista os 5 primeiros resultados (nome — endereço) para o modelo responder com dados reais.
- 5.2 Popup `places` (backend `app/agent/popups.py`, automático depois de `places_search`; ids `p0..pN` e `animate.added_ids`) e `PlacesPopup.tsx` (StaggerList, nota, atribuição OSM, "Ver no mapa" abre a janela). Janela `places` (`open_window.py` com `query` ≤120 e `near` ≤80; `windows/registry.ts`; `PlacesWindow.tsx`): campos "O que procurar"/"Perto de", busca só ao enviar, lista, `iframe` `openstreetmap.org/export/embed.html?bbox=…&layer=mapnik&marker=lat,lon` centrado no resultado escolhido, "Abrir no mapa", atribuição visível. `GET /api/places?q=&near=` (`app/ui/panel/api/places.py`) passa por `run_action("places_search", …, origin="window", source="window:places")`: aparece na Central e não gera popup. Comando `/lugares <busca>` (ação `open-window` ganhou `argParam`; `openWindow(windowId, params?)`). Utilitário `frontend/src/utils/places.ts` (tipos, validação, URL do mapa).
- 5.3 Popup `task_list` (filter pending/all; automático para task_tool create/create_many/toggle/complete/done/update com `added_ids`/`toggled_ids`/`updated_ids`) e `TaskListPopup.tsx` (entrada em sequência, selo + risco animado na concluída, prioridade P1-P4, prazo "hoje/amanhã/dd/mm", pendentes com CountUp). Comando `/pendencias`.
- 5.4 Testes: novo `tests/test_places.py` (17, rede simulada em `urllib.request.urlopen`, relógio/espera falsos); `tests/test_popup_templates.py` (+2 de `task_list`, `TaskTool` no registro do teste); `tests/test_open_window.py` (+janela `places` válida/inválida e espelho de ids com `windows/registry.ts`); `frontend/tests/popups.smoke.cjs` ampliado.

### Testes rodados
- `tests/test_places.py tests/test_popup_templates.py tests/test_open_window.py` → 1ª rodada: 1 falha esperada (espelho de janelas antes do frontend existir); depois do frontend, verde.
- Fase 5 + Fases 1-4 + conjunto R (24 arquivos: places, popup_templates, open_window, popups_infra, popups_mirror, agent_loop, tool_ops_lote6, open_screen, loop_policy, agent_loop_settings, god_mode_components + R) → **401 passed**.
- `tests/test_backend_cloud_sync.py tests/test_runtime_settings_sync.py` (chaves de API mudaram) → 24 passed (ambos isolam em tmp).
- `tsc --noEmit` limpo; `npm run build` ok (aviso de chunk > 800 kB só do `elk`/mermaid, já existente).
- Smoke (Vite 5174, APIs e mapa do OSM simulados, nenhuma requisição externa): `popups.smoke.cjs` 1ª rodada falhou (a janela buscava 2× ao abrir no modo estrito do React: o efeito rodava duas vezes); corrigido com busca inicial única por montagem; 2ª rodada **PASS** (tarefas animadas e riscadas na mesma chave, `/pendencias`, popup Lugares com 3 resultados e atribuição, "Ver no mapa", `/lugares padaria` abre e busca uma vez, `iframe` com `bbox`/`marker`, trocar resultado move o marcador, digitar não busca, Enter busca). `agent-loop.smoke.cjs` PASS, `chat-cancel.smoke.cjs` PASS.
- Nenhum teste tocou `data/` real nem a rede. Suíte completa e `test_habits_tasks_finance.py` não rodadas.

### Decisões
- O popup `places` nunca consulta o provedor: o builder lê só o cache da busca feita pelo Kernel (ferramenta ou janela). `show_popup(places)` ou `/api/popups/places` sem busca anterior devolvem "Busque o lugar primeiro…" (400). Assim toda consulta a terceiros fica na Central.
- `/lugares padaria` e o agente abrindo a janela com `query` contam como envio: a janela busca uma vez ao abrir. Depois disso, digitar nunca busca; só Enter/"Buscar". `/lugares` sem texto abre a janela vazia.
- "Ver no mapa" do popup reabre a busca na janela (resposta vem do cache do backend, sem nova consulta ao OSM; registra uma leitura na Central com origem janela).
- `task_list` com `pending` inclui sempre as tarefas que a ação acabou de mexer (a recém-concluída aparece riscada), como o `habit_list` faz com os destacados.
- E-mail do Nominatim: só por `runtime_settings.places.email` ou `NOMINATIM_EMAIL`, sem campo na tela (opcional pela política; mantido fora para não crescer a fase).
- Resultado vazio do provedor é sucesso real ("Nenhum lugar encontrado…"), diferente de erro de rede (`ok: False`).
- Mapa por `iframe` do OSM (sem biblioteca nova); "Abrir no mapa" usa `openstreetmap.org/?mlat=…&mlon=…`. Sem Google Maps embutido (exigiria outra chave e outros termos).
- Nada da seção (e) foi pulado. Continuam fora do lote: rotinas/gatilhos, palmas, steering, aprovar no chat, timer em popup.

### Pendências
- Busca de lugares e mapa nunca testados contra o Nominatim/Google reais (só simulados). O `iframe` do OSM dentro do app desktop (pywebview) não foi conferido.
- Sem tela para o e-mail de contato do Nominatim.
- `inventario.md` não foi regenerado com `places_search` (fica para a Fase 6).

### Commit
- `24d0577` feat(lote6): fase 5 - busca de lugares (OSM/Google opcional), janela e popup Lugares, popup de tarefas e /pendencias (local, sem push).


## Fase 6: integração final, build e smoke tests

**Status:** feita (itens 6.1 a 6.4 do plano).

### Testes rodados
- 6.1 pytest direcionado, 26 arquivos (9 novos do lote: tool_ops_lote6, open_screen, loop_policy, agent_loop, agent_loop_settings, popups_infra, popups_mirror, popup_templates, places; mais god_mode_components, backend_cloud_sync, runtime_settings_sync e o conjunto R) → **425 passed** na primeira rodada. Nenhuma costura entre fases quebrou.
- 6.2 `tsc --noEmit` limpo; `npm run build` ok (só o aviso antigo do `elk` > 800 kB). `git status -- mobile_app` vazio.
- 6.3 Smoke (Vite 5174, APIs simuladas): `agent-loop` PASS, `chat-cancel` PASS, `popups` PASS (todos na 1ª rodada). `runs` e `workspace` falhavam na carga inicial pela simulação de `/api/approvals` sem `mode` (pré-existente, registrado nas Fases 2 e 3). Simulação corrigida igual à do `chat-cancel`: `runs` PASS; `workspace` passa as 6 primeiras partes e para em "Ditado pela paleta" (botão "Parar gravação" não aparece). O mesmo arquivo corrigido rodado contra o frontend da tag `antes-lote6` (cópia por `git archive` em pasta temporária, Vite 5175) falha no mesmo passo: não é regressão do lote. Diagnóstico: sem erro de página; o gravador não liga com o microfone simulado no navegador sem tela. Ficou falhando (3 tentativas: simulação, diagnóstico, comparação com a base).
- Vites de teste encerrados pelo PID; pasta temporária removida.

### 6.4 Definição de pronto e documentação
- Configurações novas (`agent_loop`, `popups`) e a chave `google_places` passam por `runtime_settings._write` (sincronizam). Notas de `05-Notas` ficam no cofre, coletado por `rglob("*.md")` no `backend_sync` (sincronizam). Rascunho local de nota (localStorage) não sincroniza.
- `inventario.md`: seção DEPOIS regenerada com `places_search` e `show_popup` (a anterior também tinha caracteres quebrados por codificação; agora em UTF-8).
- `docs/CONTEXTO_PARA_CHATGPT.md`: C8, AQ5 e J11 marcados como entregues no lote 6; "Situação do lote 6" na seção 13.
- `report.md` escrito (o que mudou por funcionalidade, commits, roteiro de teste no app real por chat, voz e comandos, resultados, pendências, como reverter).

### Decisões
- Correção dos smoke `runs`/`workspace` foi só na simulação (mesma linha que a Fase 2 pôs no `chat-cancel`); nenhum componente mudou.
- O passo de ditado do `workspace` não foi mexido: falha igual na base e corrigir exigiria trocar a simulação do gravador de áudio, fora do escopo.
- `report.md` e `progresso.md` versionados por pedido da instrução da Fase 6 (o plano dizia não versionar `.agents/`; `plan.md` e `inventario.md` continuam fora do git).

### Pendências
- Smoke `workspace`: passo "Ditado pela paleta" (pré-existente); as partes depois dele não são conferidas por esse teste.
- Demais pendências das Fases 1 a 5 continuam valendo (lista consolidada no `report.md`).

### Commits
- `ff46cbc` feat(lote6): fase 6 - integracao final: simulacao de /api/approvals nos smoke runs e workspace, contexto atualizado (C8, AQ5, J11).
- Commit seguinte: `report.md` e `progresso.md` (local, sem push).