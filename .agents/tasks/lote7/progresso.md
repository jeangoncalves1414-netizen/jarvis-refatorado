# Lote 7 - progresso

Data: 2026-11-09
Tag: antes-lote7 -> 887553c

- Pacote 0: concluido
- Pacote 1: concluido (4e785a8)
- Pacote 2: concluido (45de018)
- Pacote 3: concluido (7d11f7a)
- Pacote 4: pendente
- Pacote 5: pendente
- Pacote 6: pendente


## Pacote 1 - Aprovações e loop sem estado preso (MG1, MG3, MG8, MG12)

**Status:** concluído. Commit `4e785a8` (`feat(lote7): pacote 1 - aprovacoes e loop sem estado preso`).

### Mudanças (arquivo por arquivo)
- `app/storage/auto_approvals.py`: regras ganharam `risk`, `digest` e `broad`. `add_rule` recusa regra de ação crítica sem digest e regra de ação alta sem alvo, sem digest e sem `broad`. `match(..., risk, digest)`: regra com digest só vale para os mesmos argumentos; chamada crítica exige regra com digest; chamada alta sem alvo exige digest ou regra `broad` (regras antigas largas deixam de valer). `remember_scope` guarda risco e digest; novo `scope_detail`. Modo liberado: validade opcional `forever` (padrão, comportamento antigo), `1h`, `today`; `liberated_until` persistido; `liberated()` se desliga sozinho ao vencer; `mode()` devolve `until`. Nova função `needs_exact_arguments`.
- `app/agent/action_executor.py`: `_auto_approve` passa `risk` e `arguments_digest` para `match` e `remember_scope`.
- `app/ui/panel/api/approvals.py`: regra criada de uma proposta fica amarrada ao digest quando a ação é crítica ou alta sem alvo; regra manual calcula o risco pelo `TOOL_CATALOG` (ferramenta desconhecida conta como alta) e exige `confirm_broad: true`; padrão de duração agora `now` (era `always`); `/mode` aceita `validity`; estado devolve `validities`.
- `frontend/src/components/AutoApprovals.tsx`: "Permitir e autorizar" e o formulário manual começam em "Só agora"; seletor "Ao ligar, vale por" (Até desligar / 1 hora / Hoje) ao lado do Modo liberado; texto "Ligado até ..."; selo vermelho mantido e com a validade no título; caixa "Vale para qualquer alvo" no formulário manual; rodapé explica as regras de risco.
- `app/storage/action_store.py`: `fail_stuck_resume(run_id, reply)` (encerra como falha pedido com `resume_pending` sem ponto de retomada) e `expire_stale_proposals(max_age)` (marca `expired` as propostas paradas).
- `app/ui/panel/api/actions.py`: `_resume_loop` e `_abandon_loop` chamam `_close_orphan_run` quando o checkpoint sumiu (só depois do prazo de 600 s, para não fechar pedido cujo ponto ainda está sendo registrado); publica `agent_reply` com a falha; nova `sweep_expired_proposals(store)` chamada em `GET /api/actions` e `GET /api/runs`.
- `app/ui/panel/api/runs.py`: chama a varredura antes de listar/detalhar pedidos.
- `app/agent/react_loop.py`: `_verify_and_correct` usa só o status da ação (não procura "erro"/"falha" no texto); `_finish` usa `_unresolved_failure` (falha só conta se a mesma ferramenta e o mesmo alvo não tiveram sucesso depois; sem alvo declarado vale a ferramenta); "Atenção" só para etapas com sucesso e verificação divergente.
- `tests/conftest.py`: fixture `autouse` `isolated_auto_approvals` troca o store em `app.storage.auto_approvals`, `app.agent.action_executor` e `app.ui.panel.api.approvals` por um store em `tmp_path`.
- `tests/test_auto_approvals.py` (novo, 23 testes): regra com operação/alvo, curinga, alvo vazio (phantom_typer), script com descrição repetida e código diferente, regras antigas largas, regra manual crítica recusada, expiração, revogação, mudança de duração, Modo liberado sem validade, com 1 h (relógio falso), hoje, persist e reinício.
- `tests/test_agent_loop.py` (+9): aprovação tardia (410) e recusa tardia encerram o pedido como `failed` sem `resume_pending`; varredura (via `GET /api/runs`) expira a proposta e encerra o pedido; varredura sem loop; autocorreção (mesma ferramenta/alvo) não falha; sem correção falha com a etapa certa; sucesso em outro alvo não esconde a falha; texto com "erros"/"falha" em sucesso não vira falha.

### Testes rodados
- `pytest tests/test_agent_loop.py tests/test_auto_approvals.py` → 1ª rodada 2 falhas minhas (a edição de `runs.py` não tinha aplicado; `True` em vez de `true` num JSON do teste); corrigidas.
- Conjunto ampliado (13 arquivos: agent_loop, auto_approvals, action_gateway, action_history, action_kernel, action_proposals, control_plane_security, conversation_runtime, native_action_boundary, open_window, runs, tool_catalog, tool_ops_lote6) → **318 passed**.
- `tsc --noEmit` limpo (depois de corrigir crases perdidas em `AutoApprovals.tsx`); `npm run build` ok.
- Smoke (Vite 5174 com APIs simuladas, Playwright com chromium 1228 via shim em TEMP): `agent-loop` PASS, `chat-cancel` PASS, `popups` PASS, `runs` PASS. `workspace` falha no passo "Ditado pela paleta liga o microfone" (MG27, pré-existente, linha 243).
- Nenhum teste tocou `data/` real (data/auto_approvals.json não existe; mtime de lifestyle.db e action_journal.sqlite3 inalterado). Suíte completa e `test_habits_tasks_finance.py` não rodadas.

### Decisões
- Ação crítica (ex.: `script_runner`, `hacker_mode`): "Permitir e autorizar" cria regra amarrada ao digest dos argumentos exatos (código incluso), em vez de recusar. Regra manual para crítica é recusada.
- Ação alta sem alvo (ex.: `phantom_typer`, `file_manager` sem `path`): regra criada de proposta também fica amarrada ao digest; regra manual exige a caixa "Vale para qualquer alvo" (`confirm_broad`).
- Regras antigas sem digest para ação crítica, ou largas para ação alta sem alvo, deixam de casar (ficam na lista até serem revogadas ou vencerem).
- Padrão de duração "Só agora" no botão, no formulário manual e no backend.
- Modo liberado: comportamento mantido (aprova tudo, inclusive crítica); validade opcional com padrão "Até desligar"; selo vermelho mantido.
- Varredura sem thread: roda ao consultar `/api/actions` e `/api/runs`; prazo = TTL do checkpoint (600 s) + 5 s.
- `_close_orphan_run` só age se a ação tem mais de ~595 s, por causa da ordem intencional em `_pause` (pendência gravada antes do registro do checkpoint).
- Teste de `mic_capture` com microfone falso não feito: exigiria simular `speech_recognition`/`pyaudio`, não era barato.

### Pendências
- O status do pedido na Central continua `failed` quando alguma ação falhou, mesmo que o agente a tenha corrigido depois (`_refresh_run` olha o status das ações). A resposta e o `intent` agora estão corretos; mudar `_refresh_run` seria decisão de produto.
- `mic_capture` / `/api/voice/capture/*` sem testes (MG12 parcial). MG2 `critical` em turno com conteúdo externo não tratado (decisão da usuária: manter).
- `workspace.smoke.cjs` segue falhando no passo de ditado (MG27, pacote 5).
- Checkpoint do loop continua só em memória (pacote 6).

## Pacote 2 - Nada some e nada mente (MG4, MG5, MG9, MG13, MG23)
**Status:** concluído. Commit `45de018` (`feat(lote7): pacote 2 - nada some e nada mente`).
### Mudanças (arquivo por arquivo)
- `app/services/llm.py` (`_chat_groq_stream`): ferramenta que lança exceção devolve ao modelo "A ferramenta X falhou; nada foi confirmado."; resultado vazio vira "A ferramenta X não devolveu resultado; nada foi confirmado." (acabou o "Acao concluida com sucesso."). `RunCancelled` é repassado (no laço de ferramentas, no resgate de `failed_generation`, no `except` externo e nos retries de 413 e de troca de chave 429). O fallback do turno final agora começa com "Resultados das ferramentas:" (sem "Pronto."). O resgate de `failed_generation` também trata exceção da ferramenta e não diz mais "Acao processada com sucesso.".
- `frontend/src/hooks/useMediaAssistant.ts`: evento SSE `status: "error"` é falado, aparece no balão e na linha de status; `plan.summary` é usado sempre que nada foi transmitido em pedaços, para qualquer intenção (menos `cancelled`). Acentos quebrados corrigidos ("Ligação pausada", "máquina", "é detectada").
- `frontend/src/hooks/useChat.ts`: novo `turnRunIdRef` (vem do `agent_progress`, ignorando run_id que já tem mensagem do assistente). `agent_reply` só fecha o turno em andamento se o `run_id` for o mesmo; senão anexa como nova mensagem e não apaga o contador do pedido atual. `failReply` genérico agora também preenche `chatError`, porque `answer` só aparece com a conversa vazia (antes a falha ficava invisível com histórico).
- `frontend/src/hooks/useStudy.ts`: 6 mensagens com acento quebrado corrigidas.
- `frontend/src/pages/SettingsPage.tsx`: "°" trocado por "·" nos rótulos (34 linhas; o separador original era "·", como na linha "Oxyy · 200+ modelos").
- `frontend/src/utils/waterDrafts.ts` (novo): `postWater` (devolve o erro real), rascunhos em `localStorage` (`jarvis-water-drafts`, máx. 50), `flushWaterDrafts` (reenvia em ordem, para no primeiro erro).
- `frontend/src/App.tsx`: `handleQuickAddWater` só diz "registrados" com confirmação do servidor; falha mostra o erro real, não soma e guarda rascunho. Reenvio ao abrir o app, ao voltar a rede (`online`) e após o próximo registro bem-sucedido.
- `frontend/src/pages/DashboardPage.tsx`: `handleAddWater` sem soma local; falha mostra erro real, guarda rascunho e exibe aviso com botão "Reenviar" (também aparece se houver rascunhos de uma sessão anterior). O total só muda com `total_ml` do servidor (ou recarrega o status).
- `frontend/tests/broken-text.cjs` (novo) + os 5 `*.smoke.cjs`: ao final de cada smoke, falha se `frontend/src` ou o texto da tela tiver a sequência de acento quebrado.
- `frontend/tests/agent-loop.smoke.cjs`: simula `/api/evolute/water/add`; novos trechos: `agent_reply` de outro pedido durante um turno (MG9), registro de água com falha e reenvio (MG23), turno com `error` (mostra o aviso e o chat não fica preso).
- `tests/test_llm_groq_tools.py` (novo, 4 testes, cliente Groq falso via `sys.modules["groq"]`): exceção da ferramenta, resultado vazio, `RunCancelled` não engolido, fallback sem "Pronto.".
### Testes rodados
- `pytest tests/test_llm_groq_tools.py tests/test_llm_provider.py tests/test_llm_racing.py tests/test_turn_tool_allowlist.py tests/test_capability_health.py` → **31 passed** (4 novos passaram na 1ª rodada).
- `tsc --noEmit` limpo; `npm run build` ok.
- Smoke (Vite 5174, APIs simuladas): `agent-loop` PASS (já com água, MG9 e erro), `chat-cancel` PASS, `popups` PASS, `runs` PASS. `workspace` falha no mesmo passo de antes (ditado pela paleta, MG27, pré-existente), então não chega à checagem de acento quebrado no fim.
- Nenhum teste tocou `data/` real. Suíte completa e `test_habits_tasks_finance.py` não rodadas.
### Decisões
- Resultado vazio de ferramenta no Groq conta como "nada confirmado" (não como sucesso).
- Erro SSE na voz é anexado ao que já foi falado (se houver) em vez de substituí-lo.
- Rascunho de água é por aparelho (`localStorage`); risco aceito: se o servidor gravou mas a resposta não chegou, o reenvio pode somar 250 ml em dobro.
- `EvoluteHubPage.tsx` (também chama `water/add`) não foi mexido: ele já não soma localmente nem diz "registrado" em falha.
- Mudança de produto mínima: o erro genérico de chat passa a aparecer no aviso vermelho com histórico aberto.
### Pendências
- Sem teste automático do tratamento de `status: "error"` na ligação por voz (`useMediaAssistant` exige microfone/áudio); validado só por tsc e leitura.
- `turnRunIdRef` depende do `agent_progress` para saber o run do turno: em turno sem loop (sem progresso) um `agent_reply` durante a espera sempre vira mensagem nova, o que é o comportamento pedido.
- `workspace.smoke.cjs` segue falhando no ditado (MG27, pacote 5).
## Pacote 3 - Economia de tokens (MG6, MG7)
**Status:** concluído. Commit `7d11f7a` (`feat(lote7): pacote 3 - economia de tokens`).
### Mudanças (arquivo por arquivo)
- `app/agent/orchestrator.py`: nova constante `_MEMORY_TRIGGERS` (prefiro, prefer, me lembre, lembra que, lembre que, lembre-se, quero que você, meu nome é, me chamo, eu moro, moro em, eu trabalho, eu estudo, eu sou, minha idade, meu aniversário, não esqueça, anota que, guarda que, sempre que; comparadas sem acento) e `_should_extract_memory`. `_remember_preferences` só dispara a thread `_extract` (chamada a `llm_service.ask`) quando a mensagem tem gatilho ou quando `extract_memory_always` está ligado. O salvamento de preferência de estilo no `memory_store` não mudou. O loop passa `narrow=True` ao pedir `allowed_tool_names`.
- `app/storage/runtime_settings.py`: campo `extract_memory_always` (bool, padrão `False`) em `agent_loop` (get/set com validação; valor inválido volta ao padrão no get e dá erro 400 com mensagem em português no set).
- `app/agent/loop_policy.py`: pergunta/conversa não entra no loop: `?` em qualquer posição, "você acha" / "por que" em qualquer lugar, ou pedido que abre com (depois de "jarvis", "me", "pode", "por favor"...) "o que", "por que", "porque", "como", "explica/explique", "qual", "quais", "quem", "onde", "quanto(s)", "você acha/acredita/sabe". Verbo de ação só conta no começo de cada oração (divisão por vírgula, ponto, ";", "e", "depois", "então", "em seguida", "por fim", "também"). A checagem de verificação (`confere se`) e a de sequência foram mantidas. Modos `always`/`react`/`off` não mudaram.
- `app/agent/tools/registry.py`: `allowed_tool_names(..., narrow=False)`. Com `narrow=True` (só o loop), qualquer provedor recebe: `LOOP_DATA_TOOLS` (habit_tool, task_tool, lifeos_tool, calendar, vault_save_note, vault_search, open_window, open_screen) + ferramentas citadas pelo nome + as dos padrões `GROQ_KEYWORD_TOOLS` + novo `LOOP_KEYWORD_TOOLS` (web_search, open_windows_app, system_control, spotify, timer, whatsapp, file_manager, image_generator, cinema, planning_workspace, script_runner, vision). Chat nativo e Groq no chat ficam como estavam.
- `frontend/src/components/AgentLoopSettings.tsx` (+ palavras-chave em `SettingsPage.tsx`): chave "Extrair memórias de toda mensagem" (desligada) em Configurações > Agente e popups, com texto explicando o gatilho e o custo.
- `frontend/tests/agent-loop.smoke.cjs` e `popups.smoke.cjs`: mock com o campo novo; o smoke do agente liga a segunda chave e confere o POST.
- `tests/test_loop_policy.py`: +8 frases (as 3 do MG7 e variações de pergunta com verbos de ação).
- `tests/test_agent_loop_settings.py`: dicionário padrão com o campo novo.
- `tests/test_token_economy.py` (novo, 14 testes): mensagem simples faz exatamente 1 chamada ao `llm_service` (conta `chat_with_functions_stream`, `ask`, `generate`; espera as threads); mensagem com gatilho faz 1 + 1 extração e grava a memória; opção ligada devolve o comportamento antigo; validação da opção; catálogo do loop filtrado para gemini/groq/oxyy/marker, sempre com as ferramentas de dados e seguindo as palavras do pedido.
### Testes rodados
- 13 arquivos (`token_economy`, `loop_policy`, `agent_loop_settings`, `agent_loop`, `turn_tool_allowlist`, `conversation_runtime`, `popups_infra`, `popup_templates`, `tool_catalog`, `auto_approvals`, `llm_groq_tools`, `open_window`, `runs`) → **323 passed**. Falhas durante o trabalho: 1ª rodada de `test_token_economy` (faltava `mode_resolver` no agente falso) e 2 testes de configuração do agente com o dicionário antigo; corrigidos.
- `tsc --noEmit` limpo; `npm run build` ok.
- Smoke (Vite 5174, APIs simuladas): `agent-loop` PASS (com a nova chave), `popups` PASS (a 1ª tentativa estourou o tempo no passo "hábitos em sequência", com um Vite antigo ainda na porta; passou na repetição sem mudança de código), `chat-cancel` PASS, `runs` PASS.
- Nenhum teste tocou `data/` real (busca em sessions.json, logs.jsonl e action_journal.sqlite3 sem as frases dos testes; as datas recentes em `data/` vêm do app em execução). Suíte completa e `test_habits_tasks_finance.py` não rodadas.
### Decisões
- A opção "Extrair memórias de toda mensagem" fica dentro de `agent_loop` (mesma tela e mesma rota `/api/settings/agent-loop`), em vez de um grupo novo de configurações.
- Gatilhos além dos pedidos: "meu nome é", "me chamo", "eu moro/trabalho/estudo/sou" etc. "sempre que" e "eu sou" são largos; custam no máximo uma chamada em segundo plano.
- Interrogativos extras na conversa: "qual/quais/quem/onde/quanto(s)" e "você sabe/acredita". "quando" ficou de fora porque "quando chegar em casa, liga a luz" é pedido.
- No loop, o filtro vale também para o Gemini. Ferramentas raras (`kasa_control`, `telegram_bot`...) só entram se o nome aparecer no texto.
- `?` em qualquer posição tira o pedido do loop mesmo com "confere se"; no modo "Sempre" o loop continua valendo.
### Pendências
- Não há medidor de tokens (AQ6): a contagem de chamadas só existe no teste.
- `LOOP_KEYWORD_TOOLS` é heurística por palavra.
- `workspace.smoke.cjs` segue falhando no ditado (MG27, pacote 5).
## Pacote 4 - Segurança local e repositório (MG10, MG14, MG15, MG17, MG26, V5)
**Status:** concluído. Commit: `feat(lote7): pacote 4 - seguranca local e repositorio`.
### Mudanças (arquivo por arquivo)
- `app/ui/panel/api/vault_write.py` (novo): `POST /api/vault/notes`, `daily/log` e `profile/fact` passam pelo Action Kernel com origem `window` (`vault_save_note`, `vault_daily_log`, `vault_update_profile`) e aparecem na Central. A pasta da nota usa a mesma lista da ferramenta (`NOTE_FOLDERS`), recusa `..`, caminho absoluto, `:` e pasta fora da lista (400, mensagem em português) e ainda confere `resolve()` + `relative_to(VAULT_DIR)`. Padrão sem pasta: `04-Projects` (como antes). Aprovação pendente devolve 202. A resposta continua com `ok` e `path` (relativo ao cofre).
- `app/ui/panel/api/vault.py`: apagado (roteador FastAPI morto; `git grep` não achou nenhum import nem `include_router`).
- `app/services/memory_vault.py` (`save_note`): defesa em profundidade, levanta `ValueError` se a pasta resolvida sair do cofre.
- `app/ui/panel/server.py`: rota `/api/vault` delega ao módulo novo. `/api/evolute/water/add` valida 1 a 5000 ml (ausente = 250; negativo, zero, acima de 5000, texto, booleano, lista = 400 "Quantidade de água inválida: informe de 1 a 5000 ml.") e registra por `run_action("lifeos_tool", {"action": "add_water", ...}, origin="window")`; a resposta mantém `total_ml`, `added_ml` e `popup` (origem de popup `command`) e ganha `action`. Novo `_friendly_error(exc, ação)`: a tela recebe "Não foi possível <ação>. Os detalhes técnicos ficaram no diagnóstico."; o texto técnico vai para o console e para `diagnostics` (`panel/route_error`). Aplicado em: chat (`/api/chat` e o evento `error` do stream), água, hábito (marcar e prioridade), lembrete do calendário (POST, inclusive a mensagem de data inválida) e cofre.
- `app/core/secrets_mask.py` (novo): `mask_key` (só os 4 últimos caracteres, `…wxyz`) e `scrub_key` (troca a chave inteira dentro de uma mensagem de erro).
- `app/services/llm.py`: 5 mensagens do console (cooldown, rotação Groq/Gemini em 4 pontos) usam `mask_key`, sem os 8 primeiros caracteres.
- `app/services/voice/stt/engine.py`: log do Groq Whisper e do Oxyy mostra só `mask_key(key)` e passa o erro por `scrub_key`.
- `pyproject.toml`: `websockets`, `numpy`, `requests`, `vosk`, `pystray`, `pywin32` (marcador `sys_platform == 'win32'`) e `duckduckgo_search` em `dependencies`; `faster-whisper` segue no extra `local-stt`; novo extra `oxyy` (`openai`, importado em `llm.py`, `stt/engine.py` e `image_generator.py`). Acentos quebrados de `markers` corrigidos. Arquivo regravado em UTF-8 sem BOM.
- `app/contexto.md`: chave `anon` e chave `publishable` do Supabase trocadas por `<SUPABASE_ANON_KEY>` e `<SUPABASE_PUBLISHABLE_KEY>` (o id do projeto ficou).
- V5: `test_fish_audio.py` e `test_fish_audio.mp3` (não versionados) apagados da raiz sem imprimir o conteúdo; `.gitignore` ganhou `test_fish_audio.*`.
- `tests/test_lote7_security.py` (novo, 25 testes): `/api/vault/notes` com `..`, `../../Desktop`, `..\fora`, pasta fora da lista, número, caminho absoluto e `C:\Windows\Temp` (400, nada gravado fora do cofre, nenhuma ação registrada); nota válida grava dentro do cofre e cria Run `window`; pasta padrão; diário e perfil pelo Kernel; `save_note` recusa pasta fora do cofre; roteador morto não existe mais; água inválida (9 casos) não altera o total nem registra ação; água válida (5000 e padrão 250) cria ação `lifeos_tool` e Run `window`; máscara de chave (unidade, `KeyRotator.mark_cooldown` e `_transcribe_groq` com Groq falso).
### Testes rodados
- `pytest tests/test_lote7_security.py` → **25 passed** (1ª rodada).
- Junto com `test_popup_templates`, `test_popups_infra`, `test_run_origins`, `test_tool_ops_lote6`, `test_stt_providers`, `test_stt_recovery`, `test_llm_groq_tools`, `test_llm_provider`, `test_llm_racing`, `test_control_plane_security`, `test_provider_routes`, `test_conversation_runtime` → **146 passed, 2 failed**. As 2 falhas (`test_stt_providers.py::test_whisper_local_success` e `::test_whisper_local_fallback_to_google`) já existiam: os testes usam `STTEngine._transcribe_whisper_local`, método que não existe no HEAD. Não mexi nelas.
- Tudo com fixture `isolated_lote6_data`/`tmp_path`; `git status -- data` limpo. Suíte completa, `test_habits_tasks_finance.py` e `test_desktop_modules.py` (grava no cofre real) não rodados.
### Decisões
- "Origem command" da água: `command` não é uma origem válida de Run (`RUN_ORIGINS`; viraria `chat`). O Run usa `window` (rota direta do painel, como `notes_live` e `places`) e o popup de água continua com a origem `command`.
- Frontend não mudou: `VaultPanel.tsx` só usa `daily/log` e `profile/fact` e lê `ok`.
- Mensagens técnicas ainda cruas: cerca de 55 outros `str(exc)` em `server.py` (rotas menos visíveis) ficaram para depois; só as mais visíveis foram trocadas.
- `openai` virou extra `oxyy` em vez de dependência obrigatória (importado de forma preguiçosa).
### Pendências
- **A usuária ainda precisa trocar/revogar a chave da Fish Audio no site da Fish Audio** (estava no `test_fish_audio.py` apagado). Apagar o arquivo não invalida a chave nem limpa cópias antigas (Lixeira, backups, histórico de chat).
- Conferir o RLS do Supabase (V3) antes de manter o remoto público; a troca no `contexto.md` não remove as chaves do histórico do git.
- 2 testes de `test_stt_providers.py` quebrados antes deste pacote (`_transcribe_whisper_local`).
