# Lote 3: relatório para revisão externa

Projeto: c:\Users\maria\Desktop\Jarvis (branch `main`, sem push). Base: plano mestre `plans/017-plano-mestre-do-aplicativo.md`, fases F0 a F3, e backlog da seção 13 de `docs/CONTEXTO_PARA_CHATGPT.md`. Evidências por item nesta pasta: `item1-evidence.md` a `item5-evidence.md`.

## Commits (de 77213fe em diante)
| Commit | Propósito |
|---|---|
| `77213fe` | C4: Parar pedido no chat, na paleta e em `/parar` (consulta periódica a `/api/runs`); orb retirada da ligação e do Painel pessoal |
| `7a46176` | Docs: plano mestre 017 e contexto completo para outras IAs |
| `9ca78f6` | AQ2: ferramentas pessoais (hábitos, tarefas, finanças, Life OS) no catálogo com risco, alvo e efeito por operação; C12: leituras das janelas fora das listas da Central por padrão |
| `308b557` | C1: propostas de aprovação com alvo, mudança, reversibilidade e escopo; fechar app lista os processos |
| `0c0e413` | C3: o executor do chat só aceita as ferramentas do modo e do turno |
| `9336be0` | AQ3 (base, só frontend): contrato de comandos com origem e `runCommandById`; A6: escape `//`; A4: palavra de ativação abre a conversa por voz e há indicador do detector |
| `8066a5c` | S1: lápides de exclusão na sincronização; S2: `updated_at` nos hábitos com "mais recente vence" |
| `16e8e59` | Docs: registro do lote 3 e progresso das fases F0 a F3 |

Não houve commit de correção de regressão: nenhuma regressão apareceu na etapa final.

## Arquivos-chave por item
- **C4 + orb:** `frontend/src/hooks/useConversationRun.ts` (novo), `frontend/src/App.tsx`, `frontend/src/commands/registry.ts`, `frontend/src/components/WorkspaceComposer.tsx`, `frontend/src/components/LiveCallModal.tsx`, `frontend/src/components/DashboardHero.tsx`, `frontend/tests/chat-cancel.smoke.cjs` (novo).
- **AQ2 + C12:** `app/agent/tools/catalog.py`, `app/core/actions.py` (`target_for`, `effect_for`), `app/storage/action_store.py` (`include_reads`), `app/ui/panel/api/actions.py`, `app/ui/panel/api/runs.py`, `frontend/src/components/ActionHistory.tsx`, `RunHistory.tsx`.
- **C1:** `app/core/action_proposals.py` (novo), `app/agent/action_executor.py` (`propose`), `app/core/actions.py` (reversibilidade, escopo, `PREVIEW_LIMIT` 800), `app/agent/tools/catalog.py` (29 ferramentas declaradas), `app/services/app_manager.py` (`running_processes_for`).
- **C3:** `app/agent/tools/registry.py` (`allowed_tool_names`), `app/agent/orchestrator.py` (`turn_tool_names` nos dois executores).
- **AQ3 + A6 + A4:** `frontend/src/commands/registry.ts`, `frontend/src/components/WorkspaceComposer.tsx`, `frontend/src/App.tsx` (`handleWakeWord`, `unescapeSlash`), `frontend/src/hooks/useChat.ts` (`onWakeWord`), `app/ui/panel/server.py` (`_wake_word_status`, `GET /api/wake-word`).
- **S1 + S2:** `app/storage/sync_tombstones.py` (novo), `app/storage/backend_sync.py` (`drop_deleted_*`, `_delete_lifestyle_rows`, `_delete_notes`, `_record_deleted_notes`, regra de hábitos em `_prefer_remote`), `app/services/finance.py`, `habits.py`, `tasks.py`, `app/storage/task_store.py` (registram a lápide), `tests/conftest.py` (lápides sempre em `tmp_path`).

## Testes e build (etapa final, 8/11/2026)
- **Python:** `python -B -m pytest -q -p no:cacheprovider --tb=short` na união de 28 arquivos (os 26 da lista do lote mais `test_action_proposals.py` e `test_turn_tool_allowlist.py`, novos do lote): **389 passed, 1 deselected, 3 avisos de depreciação de dependências**, 125 s. Os testes novos dos commits `9ca78f6..HEAD` foram descobertos com `git diff --name-only 7a46176..HEAD -- tests`.
- **Item 5 isolado:** `test_backend_cloud_sync.py`, `test_runtime_settings_sync.py`, `test_evolute_sync.py`, `test_habits_tasks_finance.py`: 34 passed (5 testes novos de S1/S2).
- **TypeScript:** `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`: sem erros.
- **Navegador (Vite em 127.0.0.1:5173, APIs simuladas, encerrado depois):** `workspace.smoke.cjs` PASS (11 blocos), `runs.smoke.cjs` PASS, `chat-cancel.smoke.cjs` PASS. Todos na primeira execução, sem timeout.
- **Build:** `npm run build` (só web) passou, com o aviso existente de chunks acima de 800 kB. `git status` sem nenhuma mudança em `mobile_app/`. `npm run build:mobile` não foi executado.
- `data/sync_tombstones.json` não existe depois dos testes.

## Decisões tomadas sem perguntar
- Exclusões pelas ferramentas pessoais ficaram `high` (aprovação), porque não há desfazer; criar/marcar/registrar ficaram `low`. Operação vazia ou desconhecida é `critical`.
- C12 oculta só leituras bem-sucedidas de janelas (`panel:*`); nada é apagado.
- Propostas só dizem "Reversível" quando existe saída real hoje; autorizar vale só para aquela execução (C2 não foi feito). WhatsApp mostra destinatário e os 80 primeiros caracteres; código de script e texto digitado no celular não aparecem.
- C3: em provedores por marcadores a lista é a do modo; plugins não estão na lista do modo geral e o chat não os executa.
- A4: a frase de ativação abre a conversa por voz (critério da F2); o indicador depende da thread do detector viva.
- AQ3 ficou só na base do frontend; backend, voz, rotina e celular não foram feitos.
- S1: lápides para finanças, hábitos, registros de hábito, tarefas (rotina e painel) e notas. Metas, categorias de finanças, memórias e seções do cofre do frontend (`mergeSection`) ficaram de fora. Expiram em 90 dias. Nota apagada por lápide é copiada para `.conflitos/<nome>.apagada.<ms>.md`. A lápide de nota apagada direto na pasta usa o instante da última coleta em que ela existia, para que edição feita em outro dispositivo nesse intervalo vença. O frontend não mudou: repassa o snapshot do backend inteiro, com `tombstones`.
- S2: hábito sem `updated_at` (banco ou snapshot antigo) usa `created_at`; empate mantém o local.

## Pontos quentes para revisar primeiro
1. **Mesclagem com lápides** (`app/storage/backend_sync.py`: `merge_snapshots`, `apply_snapshot`, `_delete_lifestyle_rows`, `_delete_notes`; `app/storage/sync_tombstones.py`). Conferir a comparação `carimbo <= lápide`, a expiração de 90 dias, a remoção de filhas (`habit_logs`, `task_subtasks`) e a detecção de notas apagadas pela lista de vistas. Risco principal: apagar algo que não devia, ou ressuscitar por relógio errado entre dispositivos (os carimbos são do relógio de cada máquina).
2. **Executor e ferramentas por turno** (`app/agent/orchestrator.py`, `app/agent/tools/registry.py`): qualquer rota que monte o `ActionExecutor` sem `turn_tool_names` volta a aceitar tudo.
3. **Texto das propostas** (`app/core/action_proposals.py`, `catalog.py`): vazamento de valores sensíveis nos alvos (passam por `redact`) e afirmações de reversibilidade.
4. **Risco das ferramentas pessoais** (`catalog.py`): mapeamento por `action`/`command`; texto livre em `command` vira `critical`.
5. **Parar pedido** (`frontend/src/hooks/useConversationRun.ts`): consulta a cada 2 s; vários pedidos ativos na mesma conversa levam à Central.
6. **Wake word** (`App.handleWakeWord`, `server.py` `_wake_word_status`): abrir a ligação sozinho ao ouvir a frase.

## O que NÃO foi verificado
- Backend real com dados pessoais (`python -m app.main` não foi iniciado).
- Windows real: processos ao fechar app, brilho, bloqueio, volume, detector de wake word (Vosk/microfone).
- Provedores reais de IA e voz.
- Supabase real e dois dispositivos reais (a sincronização foi testada com dois "dispositivos" em pastas temporárias).
- APK: não foi gerado (`build:mobile` não rodou) e o app do celular não foi testado.
- Evento `wake_word` pelo WebSocket real (o smoke fecha o socket de propósito).
- Suíte pytest completa. Observação: os testes antigos de `test_habits_tasks_finance.py` (antes da fixture `finance_db`) ainda usam `data/lifestyle.db` real; o arquivo foi executado porque estava na lista do lote, como nos lotes anteriores. As lápides geradas nesses testes ficam em pasta temporária pela nova fixture do `conftest.py`.

## Lembrete para a usuária
A chave da Fish Audio exposta em export antigo continua precisando ser trocada no provedor (V5).
