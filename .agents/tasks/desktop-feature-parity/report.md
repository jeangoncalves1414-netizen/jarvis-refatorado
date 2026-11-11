# Paridade de funcionalidades do app desktop

Investigação somente leitura, feita em 2026-11-07 sobre o HEAD `da00309`. Nenhum arquivo do projeto foi alterado. O backend não foi iniciado, `npm run build` não foi executado e nenhuma ferramenta que age no sistema real foi chamada.

## 1. Resposta direta

**Não, o app desktop não tem tudo o que os outros projetos tinham, mas a diferença está mais na ligação do que no código.** A maior parte do que você citou existe no backend do Jarvis: ligação por voz com interrupção, STT e TTS com quatro provedores, palavra de ativação, paleta de comandos, lembretes, briefing, objetivos, execução por etapas, agente de navegador, controle de volume, mídia e aplicativos, arquivos, scripts, visão de tela, câmeras, tomadas Kasa e ADB. O problema é que boa parte disso só existe como ferramenta que o modelo pode chamar, sem tela própria. Algumas peças estão desligadas: a palavra de ativação detecta "Ei Jarvis" e avisa um canal que a interface não escuta; o detector de palmas é um esboço que nunca é iniciado; o agendador é interno; a automação de desktop e o Composio nem são registrados. Comparado ao Nexus, faltam palmas, rotinas agendadas pelo usuário, brilho, bloqueio de tela, editor de notas, grafo de memória e tela de finanças. Há um fato que muda a sua percepção do app: **o desktop serve um pacote de 9 de outubro de 2026**, anterior à reconstrução de 6 e 7 de novembro. Ao abrir o app você ainda vê o painel antigo, com seletor de persona "Dev Hacker" e comandos `/clima`; a Central com "Ver execução" não aparece. Por isso faz sentido melhorar o desktop antes do APK. A primeira entrega do inventário é justamente empacotar a versão atual, e o modo conectado do APK depende das mesmas aprovações e do mesmo histórico que precisam ser fechados no desktop.

## 2. Tabela de paridade

### Legenda

**Fontes.**

| Fonte | O que é |
|---|---|
| A | Jarvis atual, HEAD `da00309`: backend e interface React reconstruída |
| B | Painel antes da reconstrução, commit `90a759a` |
| C | Worktree do Plano 002 (`7242f4b`) |
| D | Projeto AI / Nexus |

**Estado no desktop atual.**

| Estado | Significado |
|---|---|
| (1) | Pode ser usado na interface nova |
| (2) | Só aparece em tela legada: Painel pessoal, `spotlight.html` ou o pacote antigo servido hoje |
| (3) | Existe só no backend ou como ferramenta do agente, sem interface |
| (4) | Existia antes ou em outro projeto e falta agora |

A coluna **Teste** indica se há arquivo em `tests/` que cobre o recurso. "Rodado" quer dizer que executei esse arquivo nesta revisão e ele passou. Os demais testes não foram executados e, sozinhos, não provam funcionamento. Nenhum recurso aqui foi validado fim a fim com hardware, provedores reais ou o Windows.

### Comandos

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Paleta de comandos (Ctrl+K e Alt+J) | A, B | (1) | `frontend/src/App.tsx:122`. `frontend/src/components/CommandPalette.tsx` lista navegação, água, briefing, backup, sons, cinema, visão e câmeras. Não tem ligação, ditado nem "parar pedido". | Sem teste de frontend versionado |
| Comandos com barra (`/clima`, `/pesquisa`, `/planejar`, `/visao`, `/estudos`, `/cinema`) | B | (4) | Ficaram em `frontend/src/components/ChatComposer.tsx:68`, que hoje só fornece tipos. O compositor novo (`WorkspaceComposer.tsx`) não tem esse recurso. Os comandos só inseriam texto e trocavam o modo; o backend não interpreta barras. | Nenhum |
| Palavra de ativação ("Ei Jarvis", Vosk) | A, B, D | (3), quebrado | O detector inicia em `app/main.py:156` e `app/ui/panel/server.py:2081`, e o Vosk está instalado. A interruptor de ativação fica em `SettingsPage.tsx:613`. O evento `wake_word` (`server.py:1999`) vai para o WebSocket legado, mas nenhum hook React trata esse tipo de mensagem: os tipos tratados são `chat`, `chunk`, `complete`, `error`, `image`, `reasoning`, `search`, `tutor` e `tv`. O pacote antigo também não trata. A frase fixa "Ei Jarvis" amarra o recurso à persona. | Nenhum |
| Detector de palmas | A (esboço), D | (4) | `app/services/clap_detector.py` só calcula a energia de um quadro recebido. Não abre microfone, não detecta palma dupla e só é exportado em `app/services/__init__.py:11`. No Nexus ele é ligado na inicialização: `src/main.py:1035-1067`. | Nenhum |
| Atalhos globais Alt+Space (Spotlight) e Alt+V (visão) | A, B | (2) | `app/main.py:270-289` (pywebview). Abrem `templates/spotlight.html`, servido em `server.py:290` com o visual antigo. | Nenhum |
| Enter para enviar e Shift+Enter para nova linha | A, B | (1) | `WorkspaceComposer.tsx:21` | Nenhum |
| Comandos por fala | A, D | (1), via chat | O ditado e a ligação enviam texto ao chat, e o agente escolhe as ferramentas. Não existe camada de comandos de voz determinísticos. As ferramentas chamadas pela voz ainda não entram no histórico ([PENDENCIAS](../../../docs/PENDENCIAS_DO_PAINEL.md), item 4). | `test_voice_api.py`, não rodado |

### Ligação por voz

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Ligação com interrupção (barge-in) | A, B, C (`live_call.js`), D | (1) | Botão "Abrir conversa por voz" em `WorkspaceComposer.tsx:27`, além de "Mais ferramentas" (`AppShell.tsx:44`). A interrupção fica em `useMediaAssistant.ts:520`, `:676` e `:1233`. | `test_voice_modular.py` rodado; `test_voice_api.py` e `test_stt_recovery.py` não rodados |
| Ditado pelo microfone | A, B | (1) | Botão Mic em `WorkspaceComposer.tsx:27` | `test_stt_providers.py`, não rodado |
| Ler a resposta em voz alta e leitura automática | A, B | (1) | Botão "Ouvir resposta" em `ChatPage.tsx`. A chave "Respostas em voz" fica em `AgentControls.tsx`. | Nenhum de interface |
| Provedor de TTS (Fish, Gemini, Edge, Oxyy) | A, D | (1) | `SettingsPage.tsx:230` | `test_fish_tts.py`, `test_fish_emotions.py`, não rodados |
| Provedor de STT (Groq, Oxyy, Google) | A | (1) | Tipo `SttSettings` em `types.ts:13` e configurações | `test_stt_providers.py`, não rodado |
| Escolha da voz dentro do provedor | A | (3), parcial | `types.ts:11` tem `tts_voice`, `fish_reference_id` e `oxyy_voice`, mas a tela só troca o provedor | Nenhum |
| Pipeline de voz no servidor (`/api/voice/realtime/stream`) e sessão de chamada (`/api/call`) | A | (3) | `app/ui/panel/api/voice.py:144` e `server.py:1268`. Nenhuma chamada no frontend. | `test_super_features.py`, `test_advanced_features.py`, não rodados |
| VAD (TEN), detector de turno e emoção na voz | A | (3) | `app/services/voice/vad/`, `turn_detector.py`, `voice_emotion.py` | `test_ten_and_reverse_skill.py`, não rodado |
| Identificação de quem fala | A, D | (1) | `IdentityPage.tsx:81` e `:110` (Perfis, dentro de Conhecimento) | `test_voice_identity.py`, não rodado |
| Voz ao vivo com Gemini Live (fala para fala) | D | (4) | `src/services/gemini_live.py` no Nexus | — |

### Automação

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Lembretes | A, B | (1) | `AutomationsPage.tsx` (formulário e lista); ferramenta `proactive_agent` | Nenhum |
| Briefing diário (gerar e configurar) | A, B | (1) | `AutomationsPage.tsx` e "Rotina diária" nas configurações. O `ProactiveDaemon` só inicia no modo desktop (`app/main.py:190-193`). | `test_lifeos_integration.py`, não rodado |
| Objetivos e proatividade | A | (1) | "Objetivos" na Central, em `MissionControlPage.tsx:25-39` | `test_proactive_goals.py`, não rodado |
| Execução por etapas (ReAct) com pedidos, aprovação e cancelamento | A | (1) | Modo em `WorkspaceComposer.tsx:25`; cancelamento em `RunHistory.tsx:52` | `test_runs.py`, `test_action_history.py`, não rodados (o inventário registra que passaram) |
| Agente de navegador | A, D | (1), via modo "Navegação" | Ferramenta `browser_agent`, de risco alto e com aprovação (`catalog.py`). `/api/browser/run` (`server.py:1720`) não é chamado pela interface. | `test_browser_agent.py`, não rodado |
| Rotinas agendadas pelo usuário (cron) | D | (4) | O Nexus inicia `NexusCronScheduler` em `src/main.py:503-507`, e a classe tem `add_job` em `cron_scheduler.py:120`. O `app/core/scheduler.py` do Jarvis só roda um resumo interno a cada hora (`orchestrator.py:183` e `:237`). O APScheduler está instalado, mas não é usado. | Nenhum |
| Receitas de fluxo (`workflow`) | A, D | (3) | Ferramenta de risco alto. Segundo o inventário, as receitas gerais só simulam ([PENDENCIAS](../../../docs/PENDENCIAS_DO_PAINEL.md), item 7). | `test_action_kernel.py`, não rodado |
| Automação de desktop (abrir URL ou pasta, focar ou minimizar janela, resolução) | A | (3), desligada | `app/automation/desktop_automation.py` e `app/agent/tools/desktop_automation_tool.py` existem, mas não aparecem em `registry.py:111-176` | Nenhum |
| Especialistas (Swarm) | A | (3) | `orchestrator.py:784`. O modo não aparece no compositor, nem antes nem agora. | `test_debate_and_healer.py`, não rodado |
| Corrida entre modelos (Racing) | A, B (só a chave visual) | (3) | O backend aceita o modo (`server.py:1428` e `orchestrator.py:803`), e `useChat.ts:307` envia `racing`. No painel antigo, a chave ficava só no estado local do `ChatPage` e nunca chegava a `sendText`, que era chamado sem esse argumento. | `test_llm_racing.py`, não rodado |
| Criar ferramentas (Tool Forge) | A, B | (4), inalcançável | O modal é carregado em `App.tsx:42`, mas `setIsToolForgeOpen(true)` não existe em lugar nenhum. No painel antigo a propriedade `onOpenToolForge` também nunca foi ligada a um botão. | `test_desktop_modules.py`, não rodado |
| Extensões e plugins | A | (3), vazio | `PluginManager` inicia em `app/main.py:71`, mas `app/plugins/builtin/` está vazio e `ExtensionManager` não é usado | Nenhum |
| Vigia de pastas e monitor ambiente | A | (3) | `/api/ambient/alerts` (`server.py:1184`) não é chamado pela interface | Nenhum |

### Controles

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Volume, mídia, abrir apps e listar processos | A, D | (3) | Ferramenta `system_control`. Está classificada como `observe` em `catalog.py:14`, o que dispensa aprovação (`app/core/actions.py:143`), embora altere o sistema. | `test_system_control_security.py` rodado, 17 testes |
| Abrir e fechar aplicativos do Windows | A, D | (3) | `open_windows_app`, de risco `low` (`catalog.py:26`): fechar um app não pede aprovação | `test_app_manager.py`, não rodado |
| Brilho, bloqueio de tela, captura e maximizar ou fechar janela | D | (4) | `src/tools/system_control.py:53-89` no Nexus. O Jarvis não tem brilho nem bloqueio, e a parte de janelas ficou na ferramenta desligada. | — |
| Arquivos | A, D | (3) | `file_manager`, de risco alto e com aprovação | `test_file_manager_security.py`, não rodado |
| Scripts com confirmação | A, D | (1), quando o agente propõe | O modal "Executar script?" fica em `App.tsx:902`. A autorização usa recibo de uso único (`server.py:1460`). | `test_script_runner_security.py`, não rodado |
| Terminal "hacker" | A, D | (3) | `/api/hacker` com recibo (`server.py:1223-1251`) e ferramenta `hacker_mode`, de risco crítico | `test_hacker_terminal.py`, não rodado |
| Análise de tela (visão) | A, B, D | (1) | "Analisar tela" no menu "•••" do compositor (`WorkspaceComposer.tsx:26`) e na paleta | Sem teste dedicado |
| Câmeras | A, B | (1) | `CameraWorkspace`, aberto pela paleta e por "Mais ferramentas" | Nenhum |
| Leitor de QR | A, C (`qr_scanner.js`) | (3) na interface nova; (4) para a tela | `/api/qr/read` (`server.py:889`) e ferramenta `qr_reader`. A tela de leitura só existe no painel estático antigo do worktree. | `test_qr_reader.py`, não rodado |
| Clima ou ar-condicionado | A, B | (1), simulado | `AutomationsPage.tsx:40`: "A integração física com o dispositivo pode ser adicionada depois" | `test_cinema_and_climate.py`, não rodado |
| Ponte de dispositivos com código de pareamento | A, C | (1), com lâmpada de teste | `AutomationsPage.tsx:110`. A remoção existe no servidor (`server.py:945`), mas não há botão. A Central sempre marca "Dispositivos" como saudável (`mission_control.py:39`). | `test_device_bridge.py` rodado, 2 testes |
| Tomadas Kasa | A, D (casa conectada) | (3), sem a biblioteca | Ferramenta `kasa_control` registrada, mas a biblioteca `kasa` não está instalada | Nenhum |
| Celular por ADB, área de transferência, digitação, papel de parede, compartilhamento de arquivos | A | (3) | Registradas em `registry.py:111-176` | `test_tool_catalog.py` rodado (metadados) |
| Ícone na bandeja e iniciar com o Windows | A, B | (1) | `SettingsPage.tsx:614`. A entrada no registro do Windows não está ativa nesta máquina. | Nenhum |
| Orbe flutuante destacável | A, B, D | (2) | Só no `DashboardHero` do Painel pessoal (`App.tsx:814`) | `test_orb_canonical_integrity.py`, não rodado |

### Conhecimento e memória

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Memórias semânticas (coleções e limpeza de memórias técnicas) | A, B, D | (1) | `MemoriesPage.tsx` | `test_conversation_runtime.py`, não rodado |
| Memória de perfil (adicionar, excluir e limpar) | A | (1) | `MemoriesPage.tsx` | `test_profile_memory.py`, não rodado |
| Cofre em Markdown (nota do dia, fatos, busca e notas) | A | (1) | `VaultPanel` em `MemoriesPage.tsx:83` e ferramentas `Vault*` | `test_desktop_modules.py`, não rodado |
| Editor de notas com blocos e links | D | (4) | `src/ui/nexus_modules/notes.html` no Nexus | — |
| Grafo de memória | D | (4) | `memory_graph.html` no Nexus. O `graphify-out/` do Jarvis é um grafo do código, não da memória. | — |
| Documentos (gerar, ou enviar para consulta) | A | Gerar: (3). Enviar: (4) | Ferramenta `document_generator`. O compositor só aceita imagens. | Nenhum |
| Planejamento na conversa | A | (1) | `PlanningWorkspace` no cabeçalho do chat | `test_planning_workspace.py`, não rodado |
| Fontes usadas na resposta | E | (4) | Falta, conforme [PENDENCIAS](../../../docs/PENDENCIAS_DO_PAINEL.md), item 7 | — |

### Integrações

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Página Integrações | A | (1), limitada | Mostra apenas três componentes: Ações, IA e voz, Dispositivos (`mission_control.py:36-40`) | `test_mission_control.py`, não rodado |
| Composio (Gmail, Google Calendar, Notion, Slack, GitHub, Jira) | A | (3), desligado | `composio_manager.py:19` em diante. `composio_tools.py` não é registrado, e a biblioteca `composio` não está instalada. | Nenhum |
| Calendário local | A, B | (1) | Tela Calendário e ferramenta `calendar` | `test_critical_services.py`, não rodado |
| Spotify | A, D | (3) | Ferramenta `spotify` | `test_app_manager.py`, não rodado |
| WhatsApp e Telegram | A, D | (3) | Ferramentas `whatsapp` (risco alto) e `telegram_bot` | `test_tool_catalog.py` rodado (metadados) |
| Cliente MCP | A, D | (3) | Ferramenta `mcp`, sem tela de configuração | Nenhum |
| Gateway Oxyy e catálogo de modelos | A | (1) | Configurações | `test_settings_api.py`, não rodado |
| Sincronização na nuvem (Supabase, Life OS) | A, D | (1), com risco | `SettingsPage.tsx:939`. Pode incluir chaves de provedor ([PENDENCIAS](../../../docs/PENDENCIAS_DO_PAINEL.md), item 2). | `test_evolute_sync.py`, `test_runtime_settings_sync.py`, não rodados |
| Cinema | A, B | (1) | Menu "•••" do compositor | `test_cinema_and_climate.py`, não rodado |
| Geração de imagem, busca na web, clima e cotações | A, D | Ferramentas: (3). Clima e cotações: (2), no Painel pessoal | `image_generator`, `web_search`, `realtime` | `test_tools_smoke.py`, não rodado |

### Painel e observabilidade

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Central de Execuções (pedidos, ações, aprovar, recusar, cancelar e linha do tempo) | A | (1) | `MissionControlPage.tsx`, `RunHistory.tsx` e `ActionHistory.tsx` | `test_runs.py`, `test_action_history.py`, `test_action_kernel.py`, não rodados |
| "Ver execução" a partir do chat | A | (1) no código; ausente no pacote servido | `ChatPage.tsx` | Smoke de navegador citado em PROJECT_CONTINUITY, não versionado |
| Aprovação dentro da conversa | E | (4) | O chat só traz o link "Ver execução" e o botão de script (`MessageRenderer.tsx:35`) | — |
| Painel lateral de controle (modelo, aprovações, atividade e conexões) | A | (1) | `AgentControls.tsx` | Nenhum |
| Rotas por capacidade e fallback | A | (1) | `SettingsPage.tsx:420-422` | `test_provider_routes.py`, não rodado |
| Métricas e logs | A, B | (1) pela navegação; atalho quebrado | O botão "Métricas & Logs" das configurações navega para `'Analytics'` (`SettingsPage.tsx:212`). Esse ID não existe, então a tela cai no aviso "disponível no painel legado em /legacy" (`App.tsx:780`). Só que `/legacy` redireciona para `/` (`server.py:233`). | Nenhum |
| Backup em ZIP | A, B | (1) | Configurações e paleta | Nenhum |
| Latência do servidor no cabeçalho | B | (4) | Antigo `AppShell.tsx:142-144` em `90a759a`. O cabeçalho novo mostra só conectado ou desconectado. | — |
| Quest Log | B | (4), estava morto | `startQuest` nunca foi chamado, nem antes nem agora, e o painel abria só com tarefas ativas. A Central substitui esse papel. | — |

### Módulos pessoais

| Recurso | Fontes | Estado | Evidência | Teste |
|---|---|---|---|---|
| Life OS (hábitos, água, evolução) | A, B, D | (1) | `EvoluteHubPage.tsx`. A janela `/evolute/` acrescenta anti-vício, treino, leitura, mente, Pomodoro e SOS (`evolute/src/components`). | `test_habits_tasks_finance.py`, `test_lifeos_integration.py`, não rodados |
| Estudos e ENEM (flashcards, Feynman, quadro, questões) | A, B, D | (1) | `StudyPage.tsx` | `test_enem_api.py`, `test_srs.py`, `test_tutor_store.py`, não rodados |
| Tarefas | A, B, D | (1) | Painel pessoal. Há dois caminhos de tarefas ([PENDENCIAS](../../../docs/PENDENCIAS_DO_PAINEL.md), item 7). | `test_habits_tasks_finance.py`, `test_app_flow.py`, não rodados |
| Finanças pessoais (lançamentos) | A, D | (3) na interface do Jarvis; tela (4) | Ferramenta `FinanceTool` e `/api/finance`. O card de finanças do Painel pessoal só mostra cotações. O Nexus tem `finance.html`. | `test_habits_tasks_finance.py`, não rodado |
| Diário de saúde, notícias, vídeos e metas com recompensas | D | (4) | `health.html`, `journal.html`, `news.html`, `videos.html` e `goals.html` no Nexus. O Jarvis tem `NewsTool`, de tipo (3). | — |
| Assistente de reuniões (ata) | A | (3) | `/api/meeting/*` (`app/ui/panel/api/routes/system_routes.py:70`) | Nenhum |
| Ferramentas de código (revisão, correção, sandbox, snapshots, desofuscação, diagramas) | A | (3) | `app/ui/panel/api/routes/code_routes.py` e `system_routes.py` | `test_review_and_snapshots.py`, não rodado |

## 3. O que a reconstrução removeu ou escondeu

Comparação entre `90a759a` e `da00309`: 24 arquivos em `frontend/src`, com 1.101 inserções e 764 remoções.

| O que mudou | Efeito | Evidência |
|---|---|---|
| Seletor de persona (Jarvis, Dev Hacker, Analista, Tutor, Criativo) | Removido. Nunca foi enviado ao backend, porque `useChat.ts` não tem campo de persona. | `ChatComposer.tsx:18` (sem uso) |
| Chave Racing | Removida. No painel antigo era só visual, mas o backend aceita o modo. | `90a759a:frontend/src/pages/ChatPage.tsx:91` e `:405`; `server.py:1428` |
| Comandos com barra | Removidos com o compositor antigo | `ChatComposer.tsx:68` |
| Botão de abortar do Quest Log | Removido. Só mudava o estado visual (transcrição, mensagem [51]). | `git diff 90a759a da00309 -- frontend/src/hooks/useQuestLog.ts` |
| Ações rápidas (Life OS, Cinema, Visão, Voz, Câmeras, Ligação) | Saíram da barra lateral e foram para "Mais ferramentas", recolhido no painel de controle à direita | `App.tsx:794-801` e `AppShell.tsx:44-45` |
| Hero com orbe, clima e botões de voz e ligação | Antes ficava na tela Início. Agora só aparece em Módulos pessoais → Painel pessoal. | `App.tsx:814` |
| Latência no cabeçalho | Substituída pelo estado da Central | Antigo `AppShell.tsx:142-144` |
| Lista de conversas dentro do chat e menu de exportação | Foram para a barra lateral global. Copiar, Exportar e Excluir viraram botões no cabeçalho. | `ChatPage.tsx` |
| Paleta de comandos | Equivalente: a lista agora é gerada de `navigation.ts`, e nenhuma ação foi perdida | `git diff ... CommandPalette.tsx` |

Telas que ganharam acesso direto na navegação: Execuções, Automações, Integrações, Calendário, Métricas e Perfis. No painel antigo, Automações, Análises, Calendário e Identidade só abriam pelos botões das configurações ou pela paleta.

O painel estático antigo (`app/ui/panel/static/js/*.js`, com `live_call.js`, `qr_scanner.js`, `telemetry-chart.js` e `study/*`) saiu do `main` no commit `5d013a9`. Ele só existe no worktree C. A rota `/legacy` hoje redireciona para `/`.

## 4. Entrega no desktop

- **Como o app é aberto.** Por `python -m app.main` ou com duplo clique em `run_jarvis.pyw`, que chama `app.main.main()` sem console. Sem `--server`, o app abre uma janela pywebview em `http://127.0.0.1:8000/app/` (`app/main.py:206`), ícone na bandeja, a janela oculta do Spotlight (`:207`), os atalhos Alt+Space e Alt+V (`:270-289`), a palavra de ativação (`:156`) e o `ProactiveDaemon` (`:193`). Não há `.bat`, `.exe` ou atalho do Jarvis na Área de Trabalho, e "Iniciar com o Windows" não está ativo no registro. Os scripts em `scripts/` só geram o APK.
- **O que a janela serve.** `/app/` entrega `frontend/dist/index.html` (`server.py:199-200`). `frontend/dist` é ignorado pelo git (`.gitignore:19`).
- **O pacote é anterior ao código.** `frontend/dist/index.html` e o JS mais novo são de **2026-10-09 15:09**. O arquivo mais novo em `frontend/src` é de **2026-11-07 13:13**. Nos 76 arquivos JS do pacote:

  | Texto procurado | Resultado no pacote |
  |---|---|
  | `Ver execu`, `/api/runs`, `Execução por etapas`, `Controle do agente`, `Buscar no workspace` | Ausentes |
  | `Dev Hacker`, `/clima` | Presentes em `ChatPage-BaUnUcLq.js` |
  | `AÇÕES RÁPIDAS` | Presente em `index-DKcHu7C3.js` e `CommandPalette-CB_egiXU.js` |

  **Hoje você vê o painel antigo**, com persona, comandos com barra e ações rápidas na lateral. A Central nova, o painel de controle e "Ver execução" não aparecem. Isso confirma o item 1 do [inventário](../../../docs/PENDENCIAS_DO_PAINEL.md) e a constatação da mensagem [66] da transcrição.
- **Cuidado ao reempacotar.** O script `build` de `frontend/package.json` já chama `scripts/postbuild.js` e o npm ainda roda o gancho `postbuild`, então a cópia acontece duas vezes. O `postbuild.js` apaga e recopia `mobile_app/app/src/main/assets/assets` (linhas 36-40). Gerar o pacote desktop hoje altera os assets Android versionados.

## 5. Outras fontes

**C, worktree do Plano 002.** `git log main..7242f4b` mostra dois commits que não estão no `main`: `173061c` (2026-09-19) e `7242f4b` (2026-09-20). Eles saem de `1861eae`, que está no `main`. Os nove arquivos que esses commits tocam existem no `main` em versão igual ou mais nova:

| Arquivo | Situação no `main` |
|---|---|
| `app/core/execution_receipts.py` | Idêntico |
| `app/core/control_plane.py` | Mais novo: as funções de origem e de host recebem `runtime_port` |
| `app/services/device_bridge.py` | Mais novo: separa `command` de `receive_command` (linha 174) |
| `app/config.py` | Mantém a projeção segura `token_configured` (linha 71) |
| `server.py` | Mantém recibos para script e terminal (linhas 1238-1251 e 1460) |

As linhas que só existem no worktree são comentários, a rota `/` servindo o template antigo e um endpoint ReAct mais simples. **O `main` não perdeu nenhuma peça do plano de controle.** `tests/test_control_plane_security.py` passou nesta revisão, com 7 testes. O worktree também guarda arquivos não commitados, entre eles o painel estático antigo. O único recurso de interface que falta no `main` é a tela de leitura de QR.

**D, Projeto AI / Nexus**, em `D:\Downloads\Projeto AI`. Existe. Recursos que o Jarvis não tem:

- palma dupla ligada na inicialização;
- cron do usuário com APScheduler;
- Gemini Live;
- brilho e bloqueio de tela;
- telas de notas, grafo de memória, finanças, rotinas, fluxos, saúde, diário, leitura, notícias, vídeos e metas com recompensas.

Segundo a mensagem [11] da transcrição e o `ANALYSIS.md`, o Nexus serve como fonte de domínio, não de código: a API fica aberta na rede e o bootstrap não registra ferramentas essenciais.

**E, referências**, em `D:\Downloads\AI-Panel-References-TEMP-2026-11-04\`: `ANALYSIS.md` e `README.md` com 20 projetos (LibreChat, Jan, OpenHands, LangGraph, assistant-ui e outros). Recursos que nenhuma das fontes A a D tem e que combinam com a direção do produto:

1. **Retomar um pedido depois da aprovação** (checkpoints do LangGraph). Hoje, aprovar uma etapa do ReAct executa aquela ação e encerra a sequência.
2. **Permissões por escopo, com duração e revogação** (Jan e OpenClaw).
3. **Aprovar ou recusar dentro da própria resposta do chat** (assistant-ui).
4. **Orientar um pedido em andamento** sem cancelá-lo (o padrão de steering do Hermes Deck).
5. **Memória com fonte visível, editável por item e citada na resposta** (AnythingLLM, Khoj e Letta).

**Transcrição do Codex.** Você pediu um "painel top", com "o agente de IA tendo muito controle tipo uma IA suprema" e sem a personalidade do Jarvis [1]. Depois pediu um app de celular "real baixável" [14] e um painel no nível de ChatGPT e Claude "com alguns controles a mais" [24]. O Codex removeu "controles sem efeito real" [26] e o botão de abortar que só mudava o visual [51]. Isso explica o sumiço da persona, do Racing e do botão de abortar: foi uma decisão, não uma perda acidental.

## 6. Melhorias recomendadas para o desktop

As dez melhorias abaixo estão em ordem de prioridade. Elas seguem a direção do produto: primeiro confiabilidade e controle, nenhuma ligação com a persona Jarvis, e toda ação nova passando pelo Action Kernel. A coluna "Depende de" se refere aos itens de [PENDENCIAS_DO_PAINEL.md](../../../docs/PENDENCIAS_DO_PAINEL.md).

| # | Melhoria | Tamanho | Arquivos | Depende de |
|---|---|---|---|---|
| 1 | **Entregar no desktop a versão atual.** Separar o build web da cópia para Android, remover a dupla execução do `postbuild`, gerar `frontend/dist` e mostrar a versão do pacote no rodapé. | S | `frontend/package.json`, `frontend/scripts/postbuild.js`, `AppShell.tsx` | É o item 1 |
| 2 | **Corrigir o risco das ferramentas de controle.** Definir risco por ação: volume e mídia `low`, fechar app ou processo `high`. `system_control` deixa de ser `observe`. Ampliar `test_tool_catalog.py`. | S/M | `app/agent/tools/catalog.py`, `app/core/actions.py`, `system_control.py`, `open_windows_app.py` | Item 3 (alvo e efeito) |
| 3 | **Ligar a palavra de ativação à interface.** Tratar o evento `wake_word` para abrir a ligação, tornar a frase configurável no perfil (neutra) e informar no painel se o detector está ativo. | S/M | `server.py:1999`, `app/services/voice/wake_word.py`, `useChat.ts`, `App.tsx` | Item 2 (perfil neutro), para a frase |
| 4 | **Levar a voz ao histórico e permitir parar pelo chat.** As ferramentas chamadas na ligação geram pedido e aparecem na Central; "parar" cancela o pedido ativo. | M | `useMediaAssistant.ts`, `app/agent/orchestrator.py`, `app/core/runs.py`, `ChatPage.tsx` | Item 4 (cancelamento) |
| 5 | **Criar a tela "Controles do PC"** na navegação nova: volume, mídia, apps, janelas, visão e câmeras. Cada botão cria uma proposta no Action Kernel, com resultado na Central, em vez de chamar a ferramenta direto. Registrar `desktop_automation` atrás do catálogo, ou remover. | M | Nova `frontend/src/pages/ControlsPage.tsx`, `navigation.ts`, novo `app/ui/panel/api/controls.py`, `registry.py` | Itens 3 e 4; melhoria 2 |
| 6 | **Fazer a página Integrações refletir a realidade.** Mostrar Spotify, WhatsApp, Telegram, MCP, Kasa, calendário e Composio com "configurado", "alcançável" e "último sucesso". Corrigir "Dispositivos" saudável com zero itens. Remover ou instalar o que está desligado (Composio, Kasa). | M | `app/ui/panel/api/mission_control.py`, `WorkspaceOverview.tsx`, `registry.py` | Item 5 |
| 7 | **Correções pequenas de alcance.** Trocar `'Analytics'` por `'Análises'`. Remover o Quest Log morto. Abrir o Tool Forge ou retirá-lo (instalar código exige recibo). Pôr botão de remover dispositivo. Adicionar Ligação, Ditado e Parar pedido à paleta. | S | `SettingsPage.tsx:212`, `App.tsx:41-46`, `:68`, `:70`, `AutomationsPage.tsx`, `CommandPalette.tsx` | Nenhuma; o Tool Forge depende do item 3 |
| 8 | **Rotinas agendadas reais em Automações.** Usar o APScheduler já instalado, com cada disparo criando um pedido e escopo de autorização. Substituir as receitas que só simulam. O cron do Nexus serve de referência de recurso. | M/L | `app/core/scheduler.py`, `app/agent/tools/workflow.py`, `app/services/proactive.py`, `AutomationsPage.tsx` | Itens 3, 4 e 7 |
| 9 | **Spotlight (Alt+Space) no visual novo**, reaproveitando a paleta e o envio ao chat em vez do `spotlight.html` antigo. | M | `app/main.py:270-289`, `templates/spotlight.html`, `CommandPalette.tsx` | Melhoria 1 |
| 10 | **Conhecimento e domínios do Nexus via adapters.** Abrir pela resposta a nota ou tarefa criada, editar e citar a fonte, e oferecer uma tela de finanças pessoais. | L | `MemoriesPage.tsx`, `app/services/memory_vault.py`, `app/storage/task_store.py`, `lifestyle_tools.py` | Item 7 |

Fica de fora por enquanto: o detector de palmas, porque depende de microfone contínuo, tende a disparar sem querer e tem pouco efeito sobre o controle, e a orbe ou o efeito visual da persona. As melhorias 1 a 4 também preparam o APK: o modo conectado (item 6) precisa das mesmas aprovações, cancelamento e histórico.

## 7. Método e limites

- Testes executados com `python -B -m pytest -q -p no:cacheprovider`:

  | Arquivos | Resultado |
  |---|---|
  | `test_system_control_security.py`, `test_device_bridge.py`, `test_tool_catalog.py`, `test_voice_modular.py` | 25 passaram |
  | `test_control_plane_security.py` | 7 passaram |

  Os testes de controle do sistema usam `subprocess.Popen` simulado e os de ponte usam `tmp_path`. `git status` ficou igual ao de antes.
- Não executei `test_voice_api.py` porque ele sobe um servidor HTTP e chama rotas de provedor.
- O repositório não tem testes de frontend versionados.
- O estado de cada recurso veio da leitura do código e de buscas no pacote compilado. Nenhum foi exercitado com o backend rodando.
- Não abri `test_fish_audio.py`, que contém uma credencial embutida.
