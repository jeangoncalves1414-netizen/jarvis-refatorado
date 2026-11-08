# Plano 017: plano mestre do aplicativo

Escrito em 7/11/2026, a partir do HEAD `21d9e12`. Só leitura de código: nada foi executado. Serve para seguir e para conferir cada funcionalidade nova. Fontes: `docs/CONTEXTO_PARA_CHATGPT.md` (decisões e backlog; os IDs V, C, A, VZ, J, O, S, M, Q vêm da seção 13 dele), `.agents/tasks/desktop-feature-parity/report.md` (inventário com arquivo:linha) e leituras pontuais do código. Itens novos têm prefixo **AQ**.

Legenda de fontes: **A** Jarvis atual, **B** painel antigo (`90a759a`), **C** worktree do Plano 002 (`7242f4b`), **D** Projeto AI / Nexus, **E** 20 referências open source.

## 1. Visão e princípios

**Atualização de 08/11/2026.** C4 recebeu botão no chat, comando na paleta e `/parar`, com consulta dos pedidos ativos da conversa, erro recuperável e acompanhamento do cancelamento. Múltiplos pedidos são escolhidos na Central. A orb saiu da ligação, do Painel pessoal e da entrada de overlay. F0 continua parcial, com validação real de desktop, Windows, provedores e Supabase ainda pendente. Detalhes no documento de continuidade.

Um aplicativo pessoal de agente de IA, para desktop e celular como **um produto só**, que conversa, planeja e age no PC e nas áreas da vida da usuária, sempre de forma visível e controlada. Decisões fixas (seções 2 e 3 do contexto):

1. **Controle antes de aparência.** Toda ação mostra alvo, risco, aprovação, andamento, resultado e erro real. Falha nunca aparece como sucesso.
2. **Poder com limites.** Permissões por escopo, cancelamento e auditoria; nada eleva privilégio em silêncio.
3. **Persona é um perfil trocável** (nome, voz, estilo, frase de ativação). Padrão "Assistente". Sem orbe.
4. **Módulos são janelas sob demanda**, que abrem também sem IA (`/comando`, paleta, botão). O agente só escolhe janelas prontas; números vêm da API.
5. **Registro manual sempre funciona**, com rascunho local até o servidor confirmar.
6. **Um cadastro de comandos e rotinas** com vários gatilhos (horário, palma opcional, `/`, paleta, frase de voz, botão). Cada disparo vira pedido na Central; palma sozinha só executa risco baixo.
7. **Tudo sincroniza** pelo Supabase (inclusive chaves), menos caches, logs e histórico de ações.
8. **Uma rota por capacidade**, mostrando qual provedor e modelo responderam. **Economia de tokens** é requisito: o que não precisa de modelo não chama modelo.
9. **Desktop primeiro, APK depois**, mesmo painel e mesmo backend.

Decisões ainda abertas: editor de notas (J2), Gemini Live (VZ4), busca de lugares (J11).

## 2. Peças-base compartilhadas

A ideia: poucas peças que todo o resto usa. Se uma funcionalidade nova não usa estas peças, ela vira um caminho solto, como a voz e as rotas diretas de hoje.

### PB1. Action Kernel com resultado tipado e concessões de confiança
- **O que faz:** toda ação do agente ou da usuária passa por aqui. Decide o risco (`observe`, `low`, `high`, `critical`), pede aprovação, executa, devolve recibo (alvo, efeito, reversível ou não) e grava no histórico.
- **Quem usa:** chat, modo por etapas, voz, rotinas, gatilhos, botões de janela, celular. Hoje só o chat e o modo por etapas usam de verdade.
- **Já existe:** `app/core/actions.py` (níveis e política), `app/agent/action_executor.py:20` (`ActionExecutor`), `app/agent/tools/catalog.py` (risco por ferramenta e por operação; `system_control` e `open_windows_app` já estão `critical` por padrão e o risco do alvo é calculado, `catalog.py:38-66`), `app/agent/tools/base.py:40` (ferramenta sem metadado cai em `critical` se marcada crítica, senão `low`), `app/storage/action_store.py` (histórico).
- **Falta:** (1) o executor do turno recebe **todas** as ferramentas registradas (`orchestrator.py:497-499`, `:609-611`), e a lista por modo só filtra o que o modelo vê (C3). (2) `finance_tool`, `habit_tool`, `task_tool` e `lifeos_tool` não estão em `TOOL_CATALOG`; ficam com o padrão do `BaseTool` (`low`), sem alvo nem efeito declarados (AQ2). (3) Aprovação mostra pouco: "Executar X" (C1). (4) Rotas diretas e voz não passam por aqui (C10, C6). (5) Sem permissões duradouras por escopo (C2).
- **Concessões de confiança (novo conceito dentro da PB1):** regra gravada pela usuária, com escopo (ferramenta + alvo, por exemplo "fechar o Spotify"), duração (hoje, 30 dias, sempre), limite (quantas vezes) e botão de revogar. O Kernel consulta antes de pedir aprovação. Nunca vale para `critical` sem confirmação extra. É o caminho para a IA agir sem pedir o tempo todo, sem tirar o controle (C2).

### PB2. Registro único de comandos e rotinas, com gatilhos
- **O que faz:** um cadastro de "coisas que se pode pedir" (abrir janela, registrar água, tocar música, sequência de passos), cada uma com **gatilhos**: `/palavra`, paleta, botão, frase de voz, horário, palma, evento.
- **Quem usa:** menu `/`, paleta, voz, agendador, detector de palmas, celular, e o agente (que pode "executar o comando X" em vez de montar ferramentas).
- **Já existe:** só no frontend. `frontend/src/commands/registry.ts` (comandos com `slash`, `aliases`, `action` e `worksOffline`; `parseSlashInput` na linha 168).
- **Falta:** a versão do backend (tabela de rotinas + gatilhos, APScheduler que já está instalado e não é usado, `app/core/scheduler.py` só roda um resumo por hora). Contrato único (AQ3) para o mesmo comando valer no frontend, na voz, na rotina e no celular. Rotinas gravadas na nuvem. Itens A1, A2, A3, A5, A6.

### PB3. Registro de janelas
- **O que faz:** lista de janelas abertas sob demanda, com id, parâmetros tipados e se abre sem IA.
- **Quem usa:** menu `/`, paleta, o agente (ferramenta `open_window`), voz, celular.
- **Já existe:** `frontend/src/windows/registry.ts:91` (`windowRegistry`: finanças, controles do PC; as demais constantes, como `WINDOW_LIFE_OS`, `WINDOW_CINEMA`, `WINDOW_CAMERAS`, `WINDOW_LIVE_CALL`, estão em `commands/registry.ts:61`), `WindowManager.tsx`, `app/agent/tools/open_window.py` (risco `observe`, `catalog.py:52`).
- **Falta:** janelas do Life OS (J1), nota/tarefa criada abre a janela certa (J4), `open_window` também na voz e no APK (J3). Regra já decidida: o agente só escolhe janela pronta e preenche parâmetros.

### PB4. Runs e eventos que alimentam a Central
- **O que faz:** cada pedido vira um Run; ferramentas, aprovações, falhas e cancelamentos viram eventos; a Central só lê isso.
- **Quem usa:** Central, "Ver execução" no chat, parar pedido, auditoria, painel de controle.
- **Já existe:** `app/core/runs.py`, `@track_run` em `orchestrator.py:353`, `app/ui/panel/api/runs.py`, `mission_control.py`, `RunHistory.tsx`, `ActionHistory.tsx`, `MissionControlPage.tsx`.
- **Falta:** `run_id` no começo do turno para "parar pedido" (C4); runs de voz, rotinas, gatilhos, Swarm, Racing e memória em segundo plano (C6); campo **origem** (chat, voz, rotina, palma, janela, celular) e **capacidade** para filtrar (O3); evento de rotina (AQ4); menos ruído de leituras `observe` (C12).

### PB5. Registro de capacidades com saúde real
- **O que faz:** lista de capacidades (chat, voz, STT, imagem, visão, Spotify, WhatsApp, calendário, dispositivos) com "configurado", "alcançável", "último sucesso", provedor e modelo que de fato responderam.
- **Quem usa:** página Integrações, painel de controle, o agente (só oferece ferramenta de capacidade saudável), rotinas (avisam se a capacidade caiu).
- **Já existe:** `app/ui/panel/api/mission_control.py:36-40` (só 3 componentes; "Dispositivos" aparece saudável com zero ou com erro), rotas por capacidade em `SettingsPage.tsx:420-422`, `tests/test_provider_routes.py`.
- **Falta:** O1, O2, A10. Integrações desligadas (Composio, Kasa, MCP, Telegram, WhatsApp) precisam aparecer como "desligado" com o motivo.

### PB6. Perfil do agente
- **O que faz:** nome, estilo, frase de ativação, voz e avatar num lugar só; troca de persona sem mexer em código. Padrão "Assistente".
- **Quem usa:** prompt do sistema, voz, wake word, interface, celular.
- **Já existe:** `agent_profile` em `app/agent/prompts.py:20-65` (nome e estilo), configuração de frase de ativação no perfil.
- **Falta:** voz e avatar no perfil (VZ6); escolher a voz dentro do provedor (VZ1); perfis salvos e sincronizados.

### PB7. Camada de sincronização
- **O que faz:** mesmo dado nos dois aparelhos, com regra de mesclagem por item.
- **Quem usa:** finanças, notas, tarefas, hábitos, rotinas, perfil, configurações e chaves; PC e celular.
- **Já existe:** `frontend/src/utils/syncMerge.ts`, `frontend/src/utils/jarvisCloud.ts`, `app/storage/backend_sync.py`, `app/storage/runtime_settings.py`, `supabase/migrations/202609200001_evolute_snapshots.sql` (tabela `evolute_snapshots` com RLS).
- **Falta:** lápides para exclusão (S1), data de alteração nos hábitos (S2), limpar chave propaga (S3), resposta vazia no celular (S4), e **todo módulo novo precisa entrar no formato de sincronização** antes de ser liberado (regra da seção 8).

### Como as peças se ligam
`PB2 (comando/gatilho)` cria uma intenção. A intenção vira um Run (`PB4`) e passa pelo `PB1`. O `PB1` usa a saúde do `PB5` e o perfil do `PB6`. O resultado abre uma janela (`PB3`) e grava dados que o `PB7` sincroniza.

## 3. Mapa do produto por área

Colunas: **Entrada** (como a usuária chega), **Kernel** (passa pelo Action Kernel: S sim, N não, P parcial hoje), **Sem IA** (funciona com o provedor fora do ar), **Central** (aparece na Central). Estado "hoje" vem do código; "alvo" é o que o plano exige. Detalhe de cada item na seção 6.

### 3.1 Conversa
Chat, modos, menu `/`, paleta, compositor, anexos.
| Funcionalidade | Fontes | Entrada | Kernel | Sem IA | Central | Liga com |
|---|---|---|---|---|---|---|
| Chat com modos (geral, pesquisa, planejar, tutor, navegação, por etapas) | A,B | compositor | S | N | S | Central, Conhecimento, Janelas |
| Menu `/` e paleta Ctrl+K | A,B | digitar `/`, atalho | n/a (comando local) | S | só se o comando agir | Janelas, Automações |
| Parar pedido, orientar pedido (steering) | A(falta),E | botão, paleta | S | S | S | Central (C4, C9) |
| Aprovar dentro da resposta | E | botão no chat | S | S | S | Central (C7) |
| Enviar documentos para consulta, imagens | A,D | compositor | P | N | N | Conhecimento (VZ5) |
| Escape `//` para texto que começa com `/` | A | digitar | n/a | S | N | (A6) |
| Racing (corrida entre modelos), Swarm (especialistas) | A,B | modos ocultos | **N** (passos internos fora do histórico, C6) | N | parcial | decisão: expor como modo ou remover |
| Seletor "Dev Hacker"/persona fixa | B | — | — | — | — | **decidido não fazer**: vira Perfil do agente (PB6) |

### 3.2 Janelas e módulos pessoais
Finanças, hábitos, treino, diário, saúde, vícios, água, rotina, metas, notas, tarefas, estudos, calendário, cinema, câmeras.
| Funcionalidade | Fontes | Entrada | Kernel | Sem IA | Central | Liga com |
|---|---|---|---|---|---|---|
| Finanças (lista, filtros, totais, registro manual) | A,D | `/financas`, paleta, chat | P (ferramenta `finance_tool` sem metadado, AQ2; janela chama `/api/finance` direto) | S | só quando o agente age | Sincronização, Conhecimento |
| Hábitos, água, evolução | A,B,D | `/lifeos`, `/agua` | P | S | N | Sincronização (S2) |
| Treino, diário, saúde física e mental, vícios, rotina, metas | A(`/evolute/`),D | janelas (J1) | alvo: S | S | alvo: S | Rotinas, Sincronização |
| Notas e cofre Markdown; editor estilo Obsidian | A,D | Conhecimento; janela (J2, decisão) | S | S | N | Memória, Sincronização |
| Tarefas, Calendário, Estudos/ENEM, Planejamento | A,B,D | telas e janelas | P (dois caminhos de tarefas, J4) | S | N | Rotinas, Proatividade |
| Cinema, Câmeras, Clima, Painel pessoal | A,B | `/cinema`, `/cameras`, `/clima` | N | S | N | — |
| Gráficos e categorias de finanças; busca de lugares | A(falta),D | janelas (J10, J11) | S | S | N | — |
| Notícias, vídeos, metas com recompensa | D | janelas | — | S | N | fase tardia |

### 3.3 Central de Execuções
| Funcionalidade | Fontes | Entrada | Kernel | Sem IA | Central |
|---|---|---|---|---|---|
| Pedidos, ações, aprovar/recusar/cancelar, linha do tempo | A | `/execucoes`, "Ver execução" | é a própria Central | S | — |
| Objetivos (proatividade) | A | Central | S | N | S |
| Filtros por origem e capacidade, progresso por etapa, exportar diagnóstico | A(falta),E | Central | — | S | (O3) |
| Parar e retomar sequência depois da aprovação (checkpoint) | E | Central, chat | S | S | (C8) |
| Ligar voz, rotinas, gatilhos e celular aos runs | A(falta) | automático | S | S | (C6) |
| Métricas e logs (botão aponta para ID inexistente `'Analytics'`, `SettingsPage.tsx:212`) | A,B | `/metricas` | n/a | S | corrigir (item 7 da paridade) |

### 3.4 Automações e rotinas
| Funcionalidade | Fontes | Entrada | Kernel | Sem IA | Central |
|---|---|---|---|---|---|
| Lembretes, briefing diário | A,B | tela Automações, `/briefing` | P (`ProactiveDaemon` só no desktop, `main.py:190-193`) | S | N |
| Rotinas agendadas por horário | D(`cron_scheduler.py:120`) | tela Automações, `/rotinas` | alvo: S | S | alvo: S |
| Receitas `workflow` (hoje só simulam) | A,D | chat | S (risco alto) | N | S |
| Gatilho de palmas (opcional, desligado) | D(`main.py:1035-1067`),A(esboço) | palma | alvo: S, só risco baixo; resto vira proposta | S | alvo: S |
| Frase de voz e palavra de ativação | A,B,D | voz | alvo: S | S | alvo: S |
| Proatividade com consentimento (sinal, pergunta, intervenção) | A | meta | S | N | S (A8) |
| Dispositivos, clima, Kasa, ponte com pareamento | A,C | Automações | N | S | N |
| Automação de desktop (janelas, pastas, resolução) | A | — (não registrada) | decidir: registrar ou remover (A9) | S | — |
| Tool Forge (criar ferramenta) | A,B | modal sem botão | S, com recibo para instalar código | N | S (A11) |

### 3.5 Conhecimento e memória
| Funcionalidade | Fontes | Entrada | Kernel | Sem IA | Central |
|---|---|---|---|---|---|
| Memória semântica, de perfil, cofre | A,B,D | tela Conhecimento, "lembra que…" | P (`_remember_preferences`, `orchestrator.py:280`, grava sem recibo) | S | N |
| Memória com fonte visível, editável, citada na resposta | E | chat, tela | S | S | (J5) |
| Grafo de memória | D | janela | — | S | (J6) |
| Importar do Nexus (prévia, backup, sem duplicar) | D | tela | S | S | (J7) |
| Identificar quem fala (Perfis) | A,D | Identidade | N | S | N |
| Ferramentas de código, reuniões, vigia de pastas, monitor ambiente | A | só backend | N | — | (J8) |

### 3.6 Controles do PC
| Funcionalidade | Fontes | Entrada | Kernel | Sem IA | Central |
|---|---|---|---|---|---|
| Volume, mídia, brilho, bloqueio de tela | A,D | `/controles`, chat | janela: S via `/api/controls` (`api/controls.py`); chat: S | S | S (mas ruído em C12) |
| Abrir e fechar apps, listar processos | A,D | chat, janela | S (risco do alvo calculado) | S | S |
| Arquivos, scripts, terminal | A,D | chat | S (alto/crítico + recibo) | N | S |
| Visão da tela, câmeras, QR | A,B,C | `/visao`, menu | P | N | N |
| Celular por ADB, área de transferência | A | chat | S | N | S |

### 3.7 Voz
| Funcionalidade | Fontes | Entrada | Kernel | Sem IA | Central |
|---|---|---|---|---|---|
| Ligação com interrupção, ditado, leitura da resposta | A,B,C,D | botão, `/voz`, `/ditado` | **N**: a voz vai ao chat e o modelo escolhe; ferramentas chamadas por voz não entram no histórico (C6) | N | N |
| Provedores TTS e STT, escolha da voz dentro do provedor | A,D | Configurações | n/a | n/a | n/a (VZ1) |
| Palavra de ativação | A,B,D | voz | alvo: S (evento `wake_word` não é tratado no React, A4) | S | alvo: S |
| Comandos de voz determinísticos (frase → comando do PB2) | D | voz | alvo: S | S | alvo: S (A5) |
| Gemini Live | D | ligação | — | N | decisão pendente (VZ4) |
| Pipeline de voz do servidor, VAD, emoção | A | sem uso no frontend | — | — | (VZ3) |

### 3.8 Integrações
Spotify, WhatsApp, Telegram, Composio (Gmail, Calendar, Notion, Slack, GitHub, Jira), Kasa, MCP, ADB, calendário local, Oxyy, plugins.
Entrada: chat e, no alvo, página Integrações (estado real, PB5). Todas passam pelo Kernel (WhatsApp `high` com confirmação, `catalog.py:70`). Funcionam sem IA só quando têm janela ou comando (alvo). Devem aparecer na Central quando agem (A10, O1).

### 3.9 Configurações e perfil
Provedores e rotas por capacidade, chaves, perfil do agente (PB6), tema, backup ZIP, iniciar com o Windows, bandeja, sons. Entrada: `/config`, paleta. Sem IA: sim. Mudança de chave ou rota deve aparecer na Central como evento (hoje não aparece).

### 3.10 Sincronização
Snapshot Supabase (`evolute_snapshots`), login, chaves de API sincronizadas (decisão 6 da seção 2 do contexto), histórico de ações **fica local**. Hoje: mescla por item, sem lápides (S1), hábitos sem data (S2). Entrada: Configurações. Central: evento "sincronizou / conflito" (AQ4).

### 3.11 Celular
`mobile_app/` é um WebView que carrega o mesmo painel (assets copiados por `npm run build:mobile`, M1). Hoje: assets antigos, chat direto quebra com resposta vazia (S4), WebSocket legado só aceita loopback (M2). Alvo: mesmas janelas e comandos, registro manual offline com rascunho, modo conectado ao PC com pareamento e identidade revogável.

## 4. Matriz de interligações (o que uma área dispara ou alimenta na outra)

Linha = origem, coluna = destino. "KERNEL" quer dizer que a ligação obrigatoriamente passa pelo Action Kernel (PB1). "hoje não" marca ligação que deveria existir e não existe no código atual.

| De \ Para | Conversa | Janelas | Central | Automações | Conhecimento | Controles PC | Voz | Integrações | Config/Perfil | Sync | Celular |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Conversa** | — | `open_window` com parâmetros | cada turno vira Run | "cria rotina" vira comando do PB2 (hoje não) | grava memória e nota com fonte | KERNEL | "ouvir resposta" | KERNEL | troca de modo/perfil | — | mesma API |
| **Janelas** | "pergunte ao agente sobre isto" (hoje não) | abrir uma a partir de outra | ações da janela com origem `janela` (só Controles hoje: `api/controls.py:51`) | "agendar isto" (hoje não) | cria nota/lançamento | KERNEL | — | — | — | grava e sincroniza | tela cheia |
| **Central** | "Ver execução" | link para o item afetado (hoje não) | — | histórico das execuções de cada rotina (hoje não) | — | aprovar/recusar/cancelar | — | estado da capacidade | — | — | aprovar pelo celular (hoje não) |
| **Automações** | rotina vira pedido (hoje não existe) | abre janela | um Run por disparo | gatilho → rotina | lê metas e memória | KERNEL, risco baixo sem perguntar, resto vira proposta | fala o resultado | KERNEL | usa perfil e horário silencioso | rotinas sincronizadas | notificação (fase final) |
| **Conhecimento** | contexto de cada turno; fonte citada | nota abre em janela (J4) | leituras `observe` ficam fora do ruído | metas alimentam proatividade | — | — | — | — | — | notas sincronizadas | mesma |
| **Controles PC** | resultado volta ao chat | janela Controles | recibo com alvo e efeito | ação de rotina | — | — | — | — | — | não sincroniza (é local) | só pelo PC |
| **Voz** | fala vira texto do chat **hoje**; alvo: frase conhecida vira comando | `open_window` por voz (J3, hoje não) | Run com origem `voz` (hoje não, C6) | frase de voz é gatilho | — | KERNEL (hoje: via chat/modelo) | — | — | frase de ativação e voz do perfil | — | microfone do aparelho |
| **Integrações** | ferramentas oferecidas só se saudáveis (hoje o catálogo inteiro vai ao executor) | — | falha real aparece | gatilho por evento (e-mail, calendário) | importa dados | — | — | — | chaves | chaves sincronizadas | — |
| **Config/Perfil** | prompt e modelo ativos | — | evento "mudou rota/chave" (hoje não) | horário silencioso, consentimento | — | limites e concessões | provedor, voz | rotas por capacidade | — | tudo sincroniza menos cache/log/histórico | — |
| **Sync** | — | dado fresco na janela | evento "sincronizou/conflito" (hoje não) | rotinas iguais nos dois | notas iguais | — | — | — | chaves | — | mesmo estado |
| **Celular** | chat pelo PC ou direto (S4) | mesmas janelas | Runs do PC visíveis | gatilhos do aparelho (alvo) | — | pelo PC pareado (M2) | STT/TTS do aparelho | — | — | via nuvem | — |

Cadeias principais que o plano precisa tornar verdadeiras:
1. **Voz → comando → Kernel → Central → janela.** Frase conhecida vira comando do PB2, passa pelo Kernel com origem `voz`, aparece na Central e abre a janela.
2. **Gatilho → rotina → pedido.** Horário/palma/frase dispara uma rotina; a rotina gera um Run; risco alto vira aprovação na Central e no celular.
3. **Memória → fonte citada → nota → sincronização.** Resposta cita a memória usada; a usuária abre a nota, edita; a edição sincroniza com lápide se apagar.
4. **Janela → Kernel → Central.** Todo botão que muda o PC ou dados com efeito relevante cria uma ação com origem `janela` (já é assim em Controles, `controls.py:3-6`).
5. **Capacidade com falha → Integrações → agente.** Capacidade fora do ar aparece como tal e deixa de ser oferecida ao modelo.

## 5. Fluxos-alvo (como DEVEM funcionar)

Notação: **[M]** chamada ao modelo, **[K]** passa pelo Action Kernel, **[A]** aprovação da usuária, **[C]** aparece na Central. "Hoje" resume o que o código faz.

### a) "abre minhas finanças" pelo chat
1. Texto vai ao orquestrador. 2. Atalho local reconhece comando conhecido (alvo: usa o PB2, sem modelo; hoje: `_run_local_shortcut` só cobre arquivos e tarefas, `orchestrator.py:668-726`). 3. Se não reconheceu, **[M]** 1 chamada escolhe `open_window(finance)`. 4. **[K]** risco `observe`, sem aprovação. 5. Chat mostra a janela aberta; **[C]** Run curto. **Alvo: 0 ou 1 modelo, 0 aprovações, 3 saltos.** Hoje: 1 modelo, 0 aprovações.

### b) `/gastos` (ou `/financas`) sem IA
`parseSlashInput` (`commands/registry.ts:168`) → comando `lifeos-finance` (`action: open-window`, `worksOffline: true`) → `WindowManager` abre a janela → janela lê `/api/finance`. **Alvo:** 0 modelo, 0 aprovação, nada na Central (só leitura). Registro manual grava com rascunho local até o servidor confirmar, e cria um evento `finance.entry` (não um Run) para auditoria. Já funciona assim, exceto o evento.

### c) "anota que gastei 50 reais no mercado"
1. **[M]** o modelo escolhe `finance_tool` com valor 50, categoria mercado. 2. **[K]** risco `low` (hoje por padrão do `BaseTool`; alvo: metadado explícito com alvo "lançamento de R$ 50,00, mercado, hoje" e efeito "cria; reversível"). 3. Executa sem pedir, e o recibo traz **o id do lançamento**. 4. Resposta do modelo repete o número que veio da API (regra: números nunca vêm do texto do modelo). 5. **[C]** Run com a ação e botão "desfazer". 6. Chat oferece "abrir finanças". **Alvo: 1 modelo, 0 aprovação, desfazer em 1 clique.** Hoje: registra e passa pelo executor, mas sem alvo/efeito legíveis (AQ2) e sem desfazer.

### d) "fecha o Spotify"
1. **[M]** escolhe `open_windows_app(close, Spotify)`. 2. **[K]** o risco é calculado pelo alvo (`catalog.py:61-66`, `_open_app_target_risk`). 3. **[A]** na primeira vez: mostra "encerrar processos: Spotify.exe (2 processos)". 4. A usuária escolhe "só agora" ou **"sempre para o Spotify"** (concessão de escopo, PB1). 5. Nas próximas, executa direto. 6. **[C]** recibo com processos encerrados. **Alvo: 1 modelo, 1 aprovação na primeira vez e 0 depois.** Hoje: pede aprovação sempre que o risco do alvo for alto, e a tela mostra só "Executar X".

### e) Pedido por voz durante a ligação que aciona ferramenta
1. STT (Groq/Oxyy/Google) → texto. 2. Se a frase for conhecida (PB2), executa o comando direto (sem modelo). 3. Senão **[M]** o modelo escolhe a ferramenta pelo mesmo caminho do chat (hoje `/api/chat/stream` usa o orquestrador, mas as ferramentas da voz não entram no histórico, C6). 4. **[K]** com origem `voz`. 5. Risco `low` executa e o TTS fala o resultado real; risco alto: a voz diz "preciso da sua aprovação" e a aprovação aparece na tela e no celular (**[A]**). Nunca aprovar por voz coisa `high` ou `critical`. 6. **[C]** Run com origem `voz`. **Alvo: STT + 0/1 modelo + TTS.**

### f) "lembra que prefiro X" e o uso depois
1. Hoje `_remember_preferences` detecta gatilhos ("prefiro", "lembra que", `orchestrator.py:280-283`) e grava no `memory_store` antes do modelo, sem recibo. Alvo: o texto vira uma **memória com fonte** (data, conversa, origem `chat`), visível na tela Conhecimento, editável e removível. 2. **[K]** `observe`/`low`; evento na Central só se o usuário ligar o filtro. 3. Em turnos futuros, o contexto traz as memórias relevantes (máximo N, por relevância). 4. Quando uma memória influencia a resposta, o chat mostra "usei: prefere X (memória de 07/11)". 5. Sincroniza com lápide. **Alvo: 0 modelo extra para gravar, citação na resposta (J5).**

### g) Tarefa de várias etapas no modo por etapas
1. Modo "Execução por etapas" (ReAct, `react_loop.py:54`; padrão 8 etapas, de 1 a 20). 2. A cada etapa **[M]** + **[K]**. 3. Etapa de risco baixo segue sozinha; etapa `high`/`critical` para e pede **[A]**. 4. **Alvo:** depois da aprovação, a sequência **retoma** do ponto onde parou (checkpoint, C8); hoje aprovar executa só aquela ação e encerra. 5. A usuária pode "parar" a qualquer momento (C4) ou orientar (C9). 6. Contador visível: etapa 3 de 8, modelo chamado 3 vezes. 7. **[C]** um Run com etapas. **Alvo: N modelos (uma por etapa, limite visível), aprovações só nos pontos de risco.**

### h) Sugestão proativa a partir de uma meta
1. Meta cadastrada (Central → Objetivos / janela de metas). 2. Sinal (horário, hábito não feito, prazo perto) é avaliado por regra, **sem modelo**. 3. Só quando há sinal, **[M]** 1 chamada escreve a sugestão curta. 4. A sugestão chega como notificação com **[A]**: "fazer agora / adiar / não sugerir mais". 5. "Fazer agora" vira Run pelo Kernel. 6. Respeita horário silencioso por meta (A8). **Alvo: modelo só quando há sinal.** Hoje: `ProactiveDaemon` só roda no desktop (`main.py:190-193`) e o ciclo completo sinal → consentimento → ação não está fechado.

### i) Rotina agendada (ainda não existe)
Precisa de: tabela `routines` (nome, passos como comandos do PB2, gatilhos, escopo de risco, ligada/desligada, horário silencioso); APScheduler no backend (`app/core/scheduler.py` hoje só faz o resumo por hora, `orchestrator.py:237`); uma função `run_routine(id)` que cria um Run com origem `rotina` e executa cada passo pelo Kernel. Regras: passo de risco baixo executa; passo `high`/`critical` vira proposta e a rotina espera na Central (com prazo). Janela "Automações" para criar e testar ("rodar agora"). Falha nunca aparece como sucesso. **Encaixe:** PB2 (cadastro e gatilhos) + PB4 (Run) + PB1 (concessões: "esta rotina pode fechar o Spotify"). Itens A1, A2, AQ3, AQ4. Sem modelo, a menos que um passo seja "pergunte ao agente".

### j) Pedido pelo celular
Hoje: o WebView abre o mesmo painel e chama a API. Chat direto do aparelho quebra com resposta vazia (S4); o modo conectado ao PC não existe (M2); assets são da interface antiga (M1). **Sem o PC:** funcionam as janelas locais e o registro manual (com rascunho e sincronização depois), e o chat, se o aparelho tiver chave de provedor própria (as chaves sincronizam). **Com o PC pareado (alvo):** o pedido vai ao backend do PC, passa pelo Kernel, vira Run com origem `celular`, e a aprovação pode ser dada no celular. **Alvo:** comandos e janelas iguais, aprovação remota, estado "PC offline" claro.

### Nota por fluxo (hoje)
| Fluxo | Nota hoje | Principal atrito |
|---|---|---|
| a) abrir finanças | bom | usa modelo para algo que um comando resolve |
| b) `/gastos` | bom | sem evento de auditoria |
| c) registrar gasto | com atrito | sem alvo/efeito legível nem desfazer (AQ2) |
| d) fechar Spotify | com atrito | aprovação sempre igual, sem lembrar a escolha (C1, C2) |
| e) voz com ferramenta | com atrito | fora do histórico, sem origem (C6, C10) |
| f) memória | com atrito | grava sem recibo, sem fonte citada (J5) |
| g) várias etapas | com atrito | aprovar encerra a sequência (C8) |
| h) proativo | com atrito | ciclo não fechado, só desktop (A8) |
| i) rotina agendada | inexistente | A1, A2 |
| j) celular | quebrado | S4, M1, M2 |

## 6. Inventário completo de funcionalidades

Estado: **existe** (usável na interface atual), **parcial**, **falta**, **não fazer** (decidido). Fase: F0 a F8 (seção 7). Os IDs V, C, A, VZ, J, O, S, M, Q estão no backlog (seção 13 do contexto). IDs **AQ** são novos:

| ID | Item novo | Tam. |
|---|---|---|
| AQ1 | Ponto de entrada único de intenção (chat, voz, rotina, janela, celular e rotas diretas como `/api/browser/run`, `server.py:1737-1747`, que chama a ferramenta sem Kernel) | G |
| AQ2 | Metadado de risco, alvo e efeito para `finance_tool`, `habit_tool`, `task_tool`, `lifeos_tool` (hoje fora de `TOOL_CATALOG`) | P |
| AQ3 | Contrato único de comando, valendo no frontend, no backend, na voz, na rotina e no celular | M |
| AQ4 | Eventos de sistema (rotina disparou, sincronizou, conflito, mudou rota/chave) que aparecem na Central | M |
| AQ5 | Contador visível e limite de etapas e de chamadas ao modelo por turno | M |
| AQ6 | Medidor de uso de modelo em segundo plano, com chave para desligar o que não for essencial (reflexion, destilação de habilidades, resumo diário) | M |
| AQ7 | Fila offline (rascunho local) para registro manual no celular e no PC, enviada quando o servidor confirmar | M |
| AQ8 | Teste de contrato da "definição de pronto": percorre registro de comandos, janelas e catálogo e reprova item sem risco, entrada ou sync | P |
| AQ9 | "Desfazer" em 1 clique para ações marcadas como reversíveis (`reversible` já existe em `catalog.py`) | M |

### Inventário

| Funcionalidade | Fonte | Estado | Área | Fase | ID |
|---|---|---|---|---|---|
| Chat com modos geral, pesquisa, planejar, tutor, navegação | A,B | existe | Conversa | — | — |
| Modo por etapas (ReAct, 1 a 20 etapas) | A | parcial (aprovar encerra) | Conversa | F5 | C8 |
| Swarm e Racing (backend, sem botão) | A,B | parcial | Conversa | F6 | C6 |
| Menu `/` com busca, paleta Ctrl+K | A | existe | Conversa | — | — |
| Escape `//` | A | falta | Conversa | F2 | A6 |
| Parar pedido (chat e paleta) | A | falta | Conversa | F0 | C4 |
| Orientar pedido sem cancelar | E | falta | Conversa | F5 | C9 |
| Aprovar e recusar dentro do chat | E | falta | Conversa | F5 | C7 |
| Enviar documentos para consulta | A,D | falta | Conversa | F4 | VZ5 |
| Spotlight Alt+Space e visão Alt+V no visual novo | A,B | parcial (visual antigo) | Conversa | F6 | A7 |
| Comandos com barra do painel antigo (`/clima`, `/pesquisa`…) | B | existe (reescritos no registro) | Conversa | — | — |
| Seletor "Dev Hacker"/persona fixa | B | não fazer (vira Perfil do agente) | Perfil | — | — |
| Orbe flutuante | A,B,D | não fazer | — | — | — |
| Personagem 3D | — | não fazer agora | — | F8 | F |
| Janela Finanças (lista, filtros, totais, registro manual) | A,D | existe | Janelas | — | — |
| Finanças: gráficos, categorias avançadas | D | falta | Janelas | F4 | J10 |
| Janela Controles do PC (volume, mídia, brilho, bloqueio) | A,D | existe, não validada | Controles PC | F0 | V2 |
| Hábitos, água, evolução (Life OS) | A,B,D | existe | Janelas | — | — |
| Treino, diário, saúde física e mental, vícios, rotina, metas, Pomodoro, SOS | A,D | parcial (`/evolute/` separado) | Janelas | F4 | J1 |
| Editor de notas estilo Obsidian/Notion | D | falta, **decisão** | Janelas | F4 | J2 |
| Cofre Markdown e notas | A | existe | Conhecimento | — | — |
| Abrir pelo chat o item criado (nota, tarefa) e unificar tarefas | A | parcial | Janelas | F4 | J4 |
| `open_window` na voz e no APK | A | falta | Janelas | F4 | J3 |
| Tarefas, Calendário, Estudos/ENEM, Planejamento | A,B,D | existe | Janelas | — | — |
| Cinema, Câmeras, Clima, Painel pessoal | A,B | existe (clima simulado) | Janelas | — | — |
| Notícias, vídeos, metas com recompensas | D | falta | Janelas | F8 | J1 |
| Busca de lugares (Places ou OpenStreetMap) | D | falta, adiado | Janelas | F8 | J11 |
| Central: pedidos, ações, aprovar, recusar, cancelar, linha do tempo | A | existe | Central | — | — |
| Central: filtros por origem/capacidade, progresso, exportar | A,E | falta | Central | F1 | O3 |
| Runs de voz, rotinas, Swarm, Racing e memória em segundo plano | A | falta | Central | F1 | C6 |
| Ruído de leituras `observe` na Central | A | parcial | Central | F1 | C12 |
| Resultado com alvo, efeito, reversibilidade, escopo | A | parcial | Kernel | F1 | C1 |
| Servidor aplica ferramentas por modo e turno | A | falta | Kernel | F1 | C3 |
| Rotas diretas e voz fora do Kernel | A | parcial | Kernel | F1 | C10, AQ1 |
| Risco/alvo para ferramentas de módulos pessoais | A | falta | Kernel | F1 | AQ2 |
| Desfazer em 1 clique | A | falta | Kernel | F5 | AQ9 |
| Permissões por escopo, duração, limite e revogação | E | falta | Kernel | F5 | C2 |
| Cancelamento em ferramentas longas | A | parcial | Kernel | F5 | C5 |
| Retomar sequência depois da aprovação | E | falta | Kernel | F5 | C8 |
| Contador e limite de etapas/modelo por turno | — | falta | Kernel | F5 | AQ5 |
| Cadastro único de comandos/rotinas com gatilhos | D,A | parcial (só frontend) | Automações | F2 | A1, AQ3 |
| Rotinas agendadas (horário) | D | falta | Automações | F2 | A2 |
| Eventos de sistema na Central | — | falta | Automações | F2 | AQ4 |
| Lembretes e briefing diário | A,B | existe | Automações | — | — |
| Receitas `workflow` (hoje só simulam) | A,D | parcial | Automações | F2 | A2 |
| Palmas opcionais (padrões, calibragem, risco baixo direto) | D | falta (esboço) | Automações | F5 | A3 |
| Proatividade com consentimento | A | parcial | Automações | F5 | A8 |
| Objetivos | A | existe | Central | — | — |
| Automação de desktop (janelas, pastas, resolução) | A | parcial (não registrada) | Automações | F2 | A9 |
| Tool Forge (criar ferramentas, com aprovação) | A,B | parcial (sem botão) | Automações | F5 | A11 |
| Extensões e plugins (pasta vazia) | A | parcial | Integrações | F6 | A10 |
| Memória semântica, de perfil, cofre | A,B,D | existe | Conhecimento | — | — |
| Memória com fonte, edição e citação | E | falta | Conhecimento | F4 | J5 |
| Grafo de memória | D | falta | Conhecimento | F6 | J6 |
| Importar do Nexus com prévia e backup | D | falta | Conhecimento | F4 | J7 |
| Ferramentas de código, reuniões, vigia de pastas, monitor ambiente | A | parcial (só backend) | Conhecimento | F6 | J8 |
| Leitor de QR (tela) | A,C | parcial | Controles PC | F6 | J9 |
| Identificar quem fala | A,D | existe | Voz | — | — |
| Volume, mídia, abrir/fechar apps, listar processos | A,D | existe | Controles PC | — | C1 |
| Arquivos, scripts, terminal com recibo | A,D | existe | Controles PC | — | — |
| Visão, câmeras | A,B | existe | Controles PC | — | — |
| ADB, área de transferência, Kasa | A | parcial (sem tela / biblioteca ausente) | Integrações | F6 | A10 |
| Ligação com interrupção, ditado, ouvir resposta | A,B,C,D | existe | Voz | — | V4 |
| Provedores TTS/STT; escolher a voz dentro do provedor | A,D | parcial | Voz | F6 | VZ1 |
| Palavra de ativação na interface | A,B,D | parcial | Voz | F2 | A4 |
| Comandos de voz determinísticos | D | falta | Voz | F2 | A5 |
| Pipeline de voz do servidor, VAD, emoção | A | parcial | Voz | F6 | VZ3 |
| Trocar voz durante a chamada, URL de áudio (planos 003/015/002) | A,C | parcial | Voz | F6 | VZ2 |
| Gemini Live | D | falta, **decisão** | Voz | F6 | VZ4 |
| Perfil do agente: voz e avatar | A | parcial | Perfil | F6 | VZ6, PB6 |
| Página Integrações com estado real | A | parcial | Integrações | F1 | O1 |
| Provedor/modelo que respondeu e razão da troca | A | falta | Integrações | F1 | O2 |
| Composio, MCP, Spotify, WhatsApp, Telegram | A | parcial (sem tela / desligado) | Integrações | F6 | A10 |
| Latência no cabeçalho | B | falta | Config | F1 | O4 |
| Erros silenciosos nas telas antigas | A | parcial | Config | F1 | O5 |
| Medidor de modelo em segundo plano | — | falta | Config | F1 | AQ6 |
| Confirmação própria no lugar de `confirm()` | A | parcial | Config | F8 | Q2 |
| Backup ZIP, bandeja, iniciar com o Windows, sons | A,B | existe | Config | — | — |
| Métricas e logs (botão aponta para `'Analytics'`) | A,B | parcial | Config | F1 | O5 |
| Sincronização Supabase com chaves | A,D | existe, risco | Sincronização | F3 | V3 |
| Lápides, data nos hábitos, limpar chave | A | falta | Sincronização | F3 | S1, S2, S3 |
| Fila offline para registro manual | A | parcial (rascunho local) | Sincronização | F3 | AQ7 |
| Chat direto do celular com resposta vazia | A | quebrado | Celular | F3 | S4 |
| Assets do APK novos | A | falta | Celular | F7 | M1 |
| Modo conectado ao PC (pareamento, revogação) | A | falta | Celular | F7 | M2, C11 |
| Teste em aparelho, release, compatibilidade | A | falta | Celular | F7 | M3, M4, M5 |
| Validar app, hardware, Supabase, voz; trocar chave exposta | A | falta | Validação | F0 | V1–V6 |
| Modularizar `server.py` e `App.tsx`; CI; CSS órfão; Q6, Q7 | A | falta | Qualidade | F8 | Q1, Q3–Q7 |
| Teste da definição de pronto | — | falta | Qualidade | F1 | AQ8 |
| Open Interpreter como base | E | não fazer (só especialista com aprovação, futuro) | — | F8 | F |
| Personalizar painel em tempo real pelo agente | — | não fazer (layouts salvos pela usuária, futuro) | — | F8 | F |
| Copiar código do Nexus | D | não fazer (só domínio e ideias) | — | — | — |
| WebSocket legado como transporte principal | A | não fazer (substituir por um transporte; loopback só) | Celular | F7 | M2 |
| Quest Log | B | não fazer (a Central substitui) | — | — | — |

## 7. Roteiro em fases

Regra: cada fase deixa algo que a usuária **usa** no fim dela, e não quebra o que já funciona. Tamanhos: P, M, G. Cada fase termina com revisão curta de código e commit próprio.

### F0. Validar e proteger (sem custo de IA, P)
- **Objetivo:** saber o que realmente funciona e fechar o risco da chave exposta.
- **Itens:** V1 a V6, C4 (parar pedido).
- **Depende de:** nada.
- **Aceitação:** o app abre por `python -m app.main` com o painel novo e a versão no rodapé; chave da Fish trocada e `test_fish_audio.py`/`.mp3` apagados; "Parar pedido" cancela um Run em andamento.
- **Fica pronto para usar:** painel novo no desktop, botão de parar.

### F1. Controle verdadeiro (peças PB1, PB4, PB5; G, dividir em 4 entregas)
- **Objetivo:** tudo que age passa por um só lugar, com alvo, efeito e histórico.
- **Itens:** AQ2 (P) → C12 (P) → C1 (M) → C3 (M) → C10 e AQ1 (G) → C6 (M) → O1, O2 (M) → O3, O4, O5 → AQ6 (M) → AQ8 (P).
- **Depende de:** F0.
- **Aceitação:** teste que lista as ferramentas e reprova qualquer uma sem metadado; aprovação de "fechar app" mostra os processos; voz e `/api/browser/run` geram ação na Central com origem; o executor só recebe as ferramentas do modo; Integrações mostra "desligado" para o que não está instalado; contador de chamadas ao modelo por turno.
- **Fica pronto para usar:** aprovações que explicam o que vão fazer; Central completa; Integrações honesta.

### F2. Comandos e rotinas (peça PB2; G)
- **Objetivo:** um cadastro de comandos com gatilhos, e a primeira rotina agendada.
- **Itens:** AQ3 (M) → A6 (P) → A4 (P) → A5 (M) → A1 (G) → A2 (G) → AQ4 (M) → A9 (M).
- **Depende de:** F1 (Kernel e Runs com origem).
- **Aceitação:** a mesma frase (`/foco`, "modo foco", horário 08:00) dispara o mesmo comando; cada disparo cria Run com origem `rotina`/`voz`/`comando`; rotina com passo de risco alto espera aprovação e não executa sozinha; "rodar agora" funciona; wake word abre a ligação e mostra se o detector está ativo.
- **Fica pronto para usar:** rotinas por horário e por voz, criadas e testadas na janela Automações.

### F3. Dados seguros (peça PB7; M)
- **Objetivo:** nada some nem volta sem querer na sincronização.
- **Itens:** S1, S2, S3, S4, AQ7.
- **Depende de:** F0 (V3). Pode andar junto com F2.
- **Aceitação:** teste de mesclagem com dois dispositivos: apagar em um não ressuscita no outro; editar hábito em um chega ao outro; registro manual feito sem servidor entra depois sem duplicar.
- **Fica pronto para usar:** PC e celular com os mesmos dados, confiável.

### F4. Janelas e conhecimento (PB3; G em várias entregas)
- **Objetivo:** módulos de vida como janelas sob demanda, com memória citada.
- **Itens:** J4 → J3 → J1 (hábitos, treino e diário primeiro; depois saúde, vícios, rotina, metas) → J5 → J10 → VZ5 → J7; J2 só depois da decisão.
- **Depende de:** F1 (cada janela já nasce com Kernel/Central) e F3 (cada janela já nasce sincronizada).
- **Aceitação:** cada janela cumpre a seção 8; memória usada aparece citada na resposta e pode ser editada ou apagada.
- **Fica pronto para usar:** Life OS completo em janelas, notas e memórias editáveis.

### F5. Autonomia com consentimento (G)
- **Objetivo:** subir do nível 2 para 4 sem perder controle.
- **Itens:** C2 (concessões, G) → C8 (G) → C7 (M) → C9 (M) → AQ9 (M) → AQ5 (M) → C5 (G) → A8 (G) → A3 (palmas, G) → A11 (M).
- **Depende de:** F1 e F2.
- **Aceitação:** "sempre permitir fechar o Spotify" vira regra visível com validade e botão de revogar; retomar sequência após aprovação; palma dupla só executa risco baixo, o resto vira proposta; proatividade só sugere com consentimento e respeita horário silencioso.
- **Fica pronto para usar:** a IA age sozinha dentro do que a usuária liberou, e para sempre que sai disso.

### F6. Voz e integrações (G)
- **Itens:** VZ1, VZ2, VZ3, VZ6, A7, A10 (Composio, Kasa, MCP, Telegram, WhatsApp, Spotify com tela), J8, J9, J6; VZ4 só após a decisão.
- **Depende de:** F1 (PB5) e F2.
- **Aceitação:** cada integração mostra estado real e passa pelo Kernel; voz escolhida dentro do provedor faz parte do perfil.

### F7. Celular (G)
- **Itens:** M1, M2, M3, M4, M5, C11.
- **Depende de:** F1, F2, F3.
- **Aceitação:** APK gerado com o painel novo; pareamento com o PC e identidade revogável; aprovar uma ação do PC pelo celular; "PC desligado" claro; teste em aparelho físico.

### F8. Qualidade e futuro
- **Itens:** Q1 a Q7, J11, Q2, Open Interpreter como especialista, layouts salvos, personagem 3D.
- Ordem livre; Q1 (quebrar `server.py` com 2.105 linhas e `App.tsx` com 991) deve ser feito aos poucos, sempre que uma fase mexer no arquivo.

### Como fica o lote 3
Lote 3 = **F0 + F1 até C1/C3** e a primeira metade de **F2** (AQ3, A6, A4). Motivo: sem F1 as rotinas nasceriam fora do Kernel. Ordem do lote: V1–V5, C4, AQ2, C12, C1, C3, AQ3, A6, A4, S1, S2. Continua valendo a ordem do contexto (seção 13), com AQ2 e AQ3 entrando como itens pequenos antes de A1.

## 8. Definição de pronto (para qualquer funcionalidade nova)

Marque cada linha antes de dar o item por concluído:

- [ ] **Kernel:** toda ação com efeito passa pelo Action Kernel, com risco declarado no catálogo, alvo e efeito legíveis, aprovação quando `high`/`critical`, e opção de desfazer se for reversível.
- [ ] **Sem IA:** funciona sem o provedor (comando `/`, paleta, botão) quando faz sentido; se precisa de IA, a tela diz isso.
- [ ] **Porta de entrada:** tem comando `/palavra` e entrada na paleta no registro de comandos; se for janela, está no registro de janelas.
- [ ] **Central:** a ação cria Run ou evento com **origem** (chat, voz, rotina, palma, janela, celular); falha real aparece como falha.
- [ ] **Sincroniza:** o dado entra no formato de sincronização, com data de alteração e lápide para exclusão; registro manual tem rascunho local.
- [ ] **Gatilhos:** pode ser usada numa rotina (horário, voz, palma) quando fizer sentido.
- [ ] **Números e fatos** vêm da API, nunca do texto do modelo.
- [ ] **Teste:** teste automatizado do caminho principal e de um erro; o teste de contrato (AQ8) passa.
- [ ] **Economia:** não adiciona chamada ao modelo em segundo plano sem o medidor (AQ6) mostrá-la.
- [ ] **Segurança:** nenhum segredo em log ou resposta; entrada validada; `mobile_app/` não é tocado fora do `npm run build:mobile`.

