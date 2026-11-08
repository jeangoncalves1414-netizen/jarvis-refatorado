# Contexto completo do projeto (para outra IA)

> Escrito em 7 de novembro de 2026. Foi feito para ser lido sozinho, sem acesso ao código. Onde diz "a usuária", é a dona do projeto. A mensagem mais recente dela sempre prevalece sobre qualquer texto antigo. Nada aqui contém segredos.

## 1. O que é o projeto

Um **aplicativo pessoal de agente de IA** com painel de controle, para desktop (Windows) e celular (Android). O agente conversa, planeja e executa ações no computador da usuária, de forma visível e controlada: toda ação tem risco, aprovação quando necessário, histórico, resultado e cancelamento.

- Nome técnico/temporário do repositório: "Jarvis". **A personalidade Jarvis não faz parte do produto.** Nome, voz, estilo e avatar são um perfil trocável. Padrão atual: "Assistente".
- Origem: o **Projeto AI / Nexus** (primeira versão, webapp) foi recriado como o **Jarvis** (segunda versão, app real com componentes reais). Os dois são repositórios separados. O Jarvis é a base. O Nexus só serve de fonte de ideias e domínio (notas, tarefas, hábitos, finanças, estudo), nunca de código copiado, porque a API dele fica aberta na rede e o bootstrap não registra ferramentas essenciais.
- Linha do tempo das conversas que originaram o projeto: chats no Antigravity IDE (9 exports lidos, um em formato ilegível), três chats do Codex, e depois o Codex e o Kiro (esta sessão) construindo o painel novo.

## 2. Prioridades confirmadas pela usuária

1. **Confiabilidade e controle antes de aparência ou persona.** Cada ação mostra o que fará, o alvo, o risco, a confirmação, o andamento, o resultado e o erro real. Falha nunca aparece como sucesso.
2. **Desktop primeiro, APK depois.** O APK abre o mesmo painel e usa o mesmo backend.
3. **Poder com limites:** permissões por escopo, aprovação para efeitos relevantes, cancelamento, auditoria. Nenhuma elevação silenciosa de privilégios.
4. **Uma rota efetiva por capacidade** (chat, voz/TTS, transcrição/STT, imagem, vídeo, visão, embeddings): o painel deve mostrar qual provedor e modelo estão ativos e por que houve troca.
5. **Sem a orbe.** Um personagem 3D é uma ideia muito futura, última prioridade.
6. **Tudo sincronizado com a nuvem (Supabase), inclusive chaves de API.** Decisão explícita de 7/11/2026: projeto pessoal, a proteção é login + Row Level Security (cada conta lê só a própria linha). Ficam fora só caches, logs e o histórico de ações, que é local de cada máquina.
7. **Economia de tokens.** A usuária tem orçamento limitado de IA. Pediu: implementar muito e revisar só no final, com outra IA (por isso este documento).

## 3. Decisões de produto já tomadas

| Tema | Decisão |
|---|---|
| Módulos (finanças, notas, treino, hábitos, saúde, vícios, rotina, diário) | Janelas flutuantes dentro do app, abertas sob demanda, em vez de seções fixas |
| Regras das janelas | (1) dentro do app, arrastáveis/redimensionáveis/maximizáveis no desktop, tela cheia no celular; (2) toda janela abre também **sem IA** (`/comando`, paleta, botão), para funcionar com o provedor fora do ar; (3) o agente só escolhe entre janelas prontas e preenche parâmetros, nunca gera interface nem código; (4) números vêm da API, nunca do texto do modelo |
| Registro manual | Tem que funcionar sem IA, com rascunho local guardado até o servidor confirmar a gravação |
| Comandos `/` | O menu só aparece ao digitar `/`, com busca (estilo Slack/Notion). Sem fileira fixa de botões. Comandos reconhecidos rodam no próprio app e não vão ao modelo |
| Palmas | Opcional, desligado por padrão. A usuária define padrões (quantidade e ritmo) e liga cada padrão a um comando ou sequência. Palma sozinha só executa ação de risco baixo; o resto vira proposta para aprovar |
| Rotinas agendadas | Sim. Um cadastro único de comandos/rotinas com vários gatilhos: horário, palma, `/`, paleta, frase de voz, botão. Cada disparo cria um pedido na Central |
| Brilho e bloqueio de tela | Sim, na janela "Controles do PC" |
| Finanças | Sim, como janela modular |
| Open Interpreter | Não adotar como base do agente (teria um segundo "cérebro" e contornaria o sistema de aprovação). Pode entrar mais tarde como especialista de programação chamado como ferramenta, com aprovação. Vale estudar o sandbox de sistema operacional dele |
| Personalizar o painel em tempo real pelo agente | Não por enquanto. Mais tarde: layouts e visões salvos pela usuária |
| Gemini Live | **Decisão pendente.** Usa as próprias vozes, não a da Fish Audio. Alternativa a avaliar: pedir texto ao Live e falar com a Fish, perdendo parte da baixa latência. Lembrar a usuária |
| Editor de notas | A usuária ainda não decidiu. Se entrar: janela estilo Obsidian/Notion; candidatos TipTap, BlockNote, Lexical, Milkdown (conferir licença). O cofre atual é Markdown |
| Busca de lugares (Google Maps) | Ideia adiada. Google Places (melhor no Brasil, pago) ou OpenStreetMap (grátis, dados mais fracos) |

## 4. Arquitetura

```text
Painel / chat / voz / celular
            |
       Run + eventos           (um pedido agrupa as ferramentas do turno)
            |
  política + consentimento + cancelamento
            |
  Action Kernel / adaptadores de capacidade
            |
resultado tipado + recibo + histórico visível
```

- **Backend:** Python 3.11. Entrada `python -m app.main` (abre uma janela pywebview em `http://127.0.0.1:8000/app/`, ícone na bandeja, atalhos Alt+Space e Alt+V, detector de palavra de ativação, agente proativo). Servidor do painel em `app/ui/panel/server.py`, com módulos de API em `app/ui/panel/api/`.
- **Agente:** `app/agent/` (orquestrador, executor de ações, loop ReAct, prompts, catálogo de ferramentas em `app/agent/tools/catalog.py`). Núcleo de ações em `app/core/actions.py`. Pedidos em `app/core/runs.py`. Armazenamento SQLite do histórico em `app/storage/action_store.py` (`data/action_journal.sqlite3`).
- **Frontend:** React + TypeScript + Vite em `frontend/src` (navegação em `navigation.ts`, registro de comandos em `commands/registry.ts`, janelas em `windows/`). O desktop serve `frontend/dist`.
- **Celular:** `mobile_app/` (Kotlin com WebView e assets copiados do build). A cópia só acontece por `npm run build:mobile`.
- **Nuvem:** Supabase, tabela `evolute_snapshots` com RLS (`supabase/migrations/202609200001_evolute_snapshots.sql`).
- **Voz:** TTS (Fish Audio, Gemini, Edge, Oxyy), STT (Groq, Oxyy, Google), palavra de ativação com Vosk, ligação com interrupção.
- **Testes:** pytest em `tests/` (o `conftest.py` isola só o journal de ações e as tarefas), testes de navegador em `frontend/tests/*.smoke.cjs` com APIs simuladas.

Níveis de risco do Action Kernel: `observe` (sem aprovação), `low`, `high`, `critical` (exigem aprovação). Risco é decidido por operação, não só por ferramenta. Operação desconhecida cai no nível mais restrito.

## 5. O que foi entregue (cronologia)

**Codex, 4 a 7/11/2026** (painel reconstruído dentro do próprio projeto):
- Interface neutra "Workspace", AppShell, chat central, painel lateral de controle, navegação única para desktop e celular.
- Central de Execuções: histórico persistente em SQLite, busca, filtros, paginação, linha do tempo, pedidos agrupados por conversa, cancelamento real entre etapas, recuperação após reinício sem reexecutar.
- Correção de falhas de ferramenta que apareciam como sucesso; aprovação protegida contra cliques duplos.
- Modo "Execução por etapas" (ReAct) e botão "Ver execução" no chat.
- Criar tarefa pelo chat grava na lista persistente do Painel pessoal.
- 98 testes Python passando na época. Nada foi commitado.

**Kiro, 7/11/2026.** Checkpoint `da00309` do trabalho do Codex, depois dois lotes:

Lote 1:
- `fe25fd8`, `fc5f703`: `npm run build` passou a gerar só `frontend/dist`; a cópia para Android ficou em `npm run build:mobile`; versão e commit aparecem no rodapé; a orbe saiu de todos os gates de build e a regra visual antiga foi marcada como obsoleta.
- `c8615cb`: risco por operação em `system_control` e `open_windows_app` (fechar app exige aprovação; operação desconhecida é `critical`).
- `36bbb35`: botão "Métricas & Logs" corrigido, Quest Log morto removido, "Remover dispositivo" com confirmação (aceito sem a credencial do dispositivo só quando o pedido vem do próprio PC e passa nas checagens do plano de controle), entradas "Conversa por voz" e "Ditado" na paleta.

Lote 2:
- `4a54bc3`: abrir app sem shell; alvo desconhecido exige aprovação; fechar app casa o nome exato do executável.
- `beb907f`: perfil do agente (nome, estilo, frase de ativação), neutro por padrão, usado nos prompts do desktop e do celular. A frase de ativação é recusada se tiver palavra fora do vocabulário do Vosk.
- `692af1b`: sincronização total com o Supabase, mesclando campo a campo (vazio nunca vence preenchido; no mesmo campo vence o carimbo mais recente). Cobre configurações, chaves, perfil, memórias, tarefas, metas, notas do cofre, hábitos, rotina e finanças. Chaves são mascaradas só em logs e telas.
- `75f94b9`, `c6dc5c3`: registro único de comandos, paleta e menu `/` sem IA; comandos antigos restaurados (`/clima`, `/pesquisa`, `/planejar`, `/visao`, `/estudos`, `/cinema`).
- `366e799`: sistema de janelas, janela Finanças (filtros, totais calculados pela API, registro manual, rascunho protegido, modo manual quando a IA está fora) e ferramenta `open_window` (risco `observe`, só ids conhecidos).
- `0d9293e`: janela "Controles do PC" (brilho, bloqueio de tela, volume, mídia) passando pelo Action Kernel.
- `21d9e12`: documentação.

**Verificação do final do lote 2:** 330 testes Python passaram numa união de 25 arquivos de teste, checagem de tipos sem erros, dois testes de navegador e um roteiro de janelas passaram, build web ok, `mobile_app/` intocado. Todos os commits estão na branch `main` do repositório local. Nenhum `git push` foi feito (o remoto é um repositório no GitHub).

## 6. O que NUNCA foi verificado

- O backend real com os dados pessoais (`python -m app.main` não foi iniciado em nenhum teste).
- Efeitos reais no Windows: brilho, bloqueio de tela, volume, mídia, abrir e fechar apps.
- Provedores reais de IA e voz.
- Supabase real: RLS aplicada no projeto, login, restauração entre dois dispositivos.
- O APK: ainda usa a interface antiga, e o comportamento com o novo formato de sincronização não foi testado.
- A suíte pytest completa (o `conftest.py` não isola tudo, e há testes antigos de finanças que escrevem no banco real).

## 7. O que falta implementar (visão rápida; a lista COMPLETA e numerada está na seção 13)

**Lote 3 sugerido, em ordem:**
1. Aprovações que mostrem alvo, efeito, se dá para desfazer e escopo (hoje a maioria mostra um texto genérico); permissões por pasta, app ou dispositivo, com duração e revogação. "Parar pedido" pelo chat e pela paleta.
2. Cadastro único de rotinas com gatilhos (horário via APScheduler já instalado, padrões de palma opcionais, frase de voz); ligar o evento de palavra de ativação à interface; ações de voz aparecendo na Central.
3. Página Integrações com o estado real de cada conexão ("configurado", "funcionando", "último sucesso"); mostrar qual modelo respondeu após uma falha.
4. Mais janelas do Life OS: treino, diário, hábitos, saúde física e mental, vícios, metas.
5. Editor de notas em janela.

**Outras pendências conhecidas:**
- Cancelamento dentro de ferramentas já em execução; passos internos de Swarm e Racing no histórico.
- Aprovar e recusar dentro da própria resposta do chat; retomar uma sequência depois da aprovação (hoje aprovar uma etapa do ReAct executa só ela e encerra).
- Ferramentas existentes sem tela ou desligadas: Composio (Gmail, Notion, Slack), automação de janelas (`desktop_automation`), Tool Forge (sem botão), Kasa, Spotify, WhatsApp, Telegram, MCP.
- Detector de palmas: hoje é só um esboço que nunca é iniciado.
- Brilho/bloqueio de tela e rotinas já têm base; falta o gatilho por palma.
- Sincronização: exclusões não se propagam (um item apagado pode voltar); hábitos não têm data de alteração.
- Chat direto do celular quebra com resposta vazia em duas rotas; `/api/chat/stream` e o chat direto do APK ainda não abrem janelas.
- Celular: gerar o pacote com `npm run build:mobile`, parear com o PC (identidade revogável, recuperação de queda) e testar num aparelho físico.
- Limpeza: arquivos muito grandes (`server.py`, `App.tsx`), confirmações nativas do navegador em memórias/tarefas/Life OS, erros silenciosos em telas antigas, testes antigos de finanças que escrevem em `data/lifestyle.db`.
- Do Projeto AI/Nexus, ainda ausentes: grafo de memória, telas de saúde e diário, rotinas pelo usuário, Gemini Live, brilho e bloqueio (estes dois já feitos).
- Futuro distante: personagem 3D, clones open source de apps conhecidos como fonte de habilidades, busca de lugares.

## 8. Pontos que mais merecem revisão externa

1. **Mesclagem da sincronização** (`frontend/src/utils/syncMerge.ts`, `frontend/src/utils/jarvisCloud.ts`, `app/storage/backend_sync.py`, `app/storage/runtime_settings.py`). É o maior risco de perda silenciosa de dados.
2. **Abrir e fechar apps** (`app/services/app_manager.py`, classificação de risco em `app/agent/tools/catalog.py` e `app/core/actions.py`).
3. **Ferramenta `open_window`** (`app/agent/tools/open_window.py` e o espelho `frontend/src/windows/registry.ts`, que precisam ficar iguais).
4. **Endpoint de controles** (`app/ui/panel/api/controls.py`, `app/agent/tools/system_control.py`).
5. **Remoção de dispositivo sem a credencial dele** quando o pedido vem do próprio PC (`app/services/device_bridge.py`, `app/ui/panel/server.py`).
6. **Aprovação e execução de ações** (`app/agent/action_executor.py`, `app/agent/orchestrator.py`).
7. `/api/finance` (`app/ui/panel/api/routes/system_routes.py`): validação de entrada e uso de `INSERT OR REPLACE`.

## 9. Segurança e cuidados

- **Uma chave de API da Fish Audio ficou exposta** em texto aberto num export do Antigravity e em um script de teste local (`test_fish_audio.py`, não versionado). Ela precisa ser revogada ou trocada no provedor.
- Chaves de provedores agora sincronizam com a nuvem por decisão da usuária. Qualquer chave que já tenha ido para lá antes deve ser rotacionada se houver dúvida.
- A primeira abertura do app migra o histórico de ações de `data/action_journal.jsonl` para SQLite, sem apagar o arquivo antigo. Voltar ao código antigo depois disso não restaura os dados. Para ter uma rede de segurança, copie a pasta `data/` antes.
- Não rodar duas instâncias do backend sobre o mesmo histórico.
- `npm run build` não toca no Android; `npm run build:mobile` toca.

## 10. Como rodar

```powershell
cd C:\Users\maria\Desktop\Jarvis
python -m app.main                  # app desktop com o painel novo
# desenvolvimento do painel:
python -m app.main --server         # só o backend
cd frontend; npm run dev            # http://127.0.0.1:5173
# verificações
python -B -m pytest -q -p no:cacheprovider tests/test_runs.py tests/test_action_kernel.py
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json   # dentro de frontend/
```

Ambiente: Windows, PowerShell. O `git` fica em um pendrive (`E:\PortableGit-2.54.0-64\cmd\git.exe`); sem o pendrive conectado o comando some do PATH. Python em `C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe`.

## 11. Documentos do repositório que complementam este

Anexe ao ChatGPT, se ele aceitar arquivos:
- `docs/PROJECT_CONTINUITY.md`: decisões, entregas e verificações detalhadas, seção por seção.
- `docs/PENDENCIAS_DO_PAINEL.md`: inventário do que falta, com critérios de aceite.
- `docs/DECISOES_E_IDEIAS.md`: decisões e ideias adiadas.
- `plans/016-neutral-agent-control-platform.md`: plano mestre.
- `.agents/tasks/desktop-feature-parity/report.md`: comparação de recursos, com arquivo e linha.
- `.agents/tasks/desktop-lote2/report.md`: relatório do último lote, para revisão.
(Os arquivos em `.agents/tasks/` não estão no git.)

## 12. Sugestão de pedido ao ChatGPT

> Leia este contexto e o `report.md` do lote 2. Faça uma revisão de código dos commits `da00309..21d9e12`, começando pelos pontos da seção 8. Procure perda de dados na sincronização, falhas de segurança, erros de lógica e testes que não provam o que dizem. Para cada achado: arquivo e linha, gravidade, como reproduzir e a correção sugerida. Não reescreva o que já funciona.

Para continuar a implementação em outro chat, peça: "Planeje o lote 3 da seção 7, mantendo as decisões da seção 3 e as prioridades da seção 2."

## 13. Backlog completo e numerado

Esta seção é a lista de referência. A seção 7 é só um resumo. Foi montada cruzando: o inventário `docs/PENDENCIAS_DO_PAINEL.md` (7 prioridades e a tabela de planos 001 a 016), o relatório de paridade do desktop, as anotações dos agentes dos lotes 1 e 2, as 5 ideias das 20 referências open source e os pedidos da usuária. Os planos numerados em `plans/` não foram relidos um a um; valem as conclusões do inventário. "Origem" diz de onde veio cada item. "Tam." é uma estimativa: P (pequeno, até 1 dia de agente), M (médio), G (grande, vários dias ou envolve desenho novo). Itens marcados **[decisão]** dependem de uma escolha da usuária.

### V. Validar o que já foi construído (nada disso foi testado com o app real)
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| V1 | Abrir o app pelo caminho normal (`python -m app.main`) e conferir o painel novo e a versão no rodapé | Lote 1 | P |
| V2 | Testar em hardware real: brilho (WMI pode não funcionar em monitor externo ou PC de mesa), bloqueio de tela, volume, mídia, abrir e fechar apps | Lote 2 | P |
| V3 | Testar a sincronização com o Supabase real: migração `202609200001` aplicada, login, dois dispositivos com chaves diferentes | Lote 2 | P |
| V4 | Pedido com provedor real de IA, ligação por voz com medição de latência e interrupção | Inventário #5 | P |
| V5 | **Trocar a chave da Fish Audio exposta** e apagar `test_fish_audio.py` e o `.mp3` (ou ler a chave de variável de ambiente) | Segurança | P |
| V6 | Rodar a suíte pytest completa. Testes antigos de `test_habits_tasks_finance.py` escrevem em `data/lifestyle.db` real | Lote 2 | P |

### C. Controle, aprovação e segurança
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| C1 | **[Entregue no lote 3, `308b557`]** Aprovações que mostrem **alvo, mudança prevista, reversibilidade e escopo**. Hoje a maioria mostra "Executar X. Parâmetros registrados de forma protegida". Ex.: fechar app deve listar os processos que serão encerrados | Inventário #3, revisão do lote 1 | M |
| C2 | Permissões por pasta, aplicativo, dispositivo ou domínio, com duração, limite e revogação | Inventário #3, referências (Jan, OpenClaw) | G |
| C3 | **[Entregue no lote 3, `0c0e413`]** O servidor deve aplicar a lista de ferramentas permitidas por modo e turno. Hoje o chat convencional entrega ao executor o catálogo completo e só filtra o que o modelo vê | Inventário #3 | M |
| C4 | **[Entregue no lote 3, `77213fe`, por consulta periódica a `/api/runs`]** **"Parar pedido"** pelo chat e pela paleta. Falta o `run_id` no início do turno (hoje só chega no fim): o backend envia cedo ou o App consulta `/api/runs?status=running` | Lote 1 item 3 | P |
| C5 | Cancelamento propagado a ferramentas longas (subprocessos, navegador, adaptadores). Hoje só cancela entre etapas | Inventário #4 | G |
| C6 | Levar ao histórico: ações por voz, rotinas, automações diretas, passos internos de Swarm e Racing, rota direta de Swarm, memória em segundo plano | Inventário #4 | M |
| C7 | Aprovar e recusar **dentro da resposta do chat** (hoje só link "Ver execução") | Referências (assistant-ui) | M |
| C8 | Retomar uma sequência depois da aprovação (checkpoint). Hoje aprovar uma etapa do ReAct executa só ela e encerra | Inventário #4, referências (LangGraph) | G |
| C9 | Orientar um pedido em andamento sem cancelá-lo (steering) | Referências (Hermes Deck) | M |
| C10 | Rotas que chamam ferramentas sem passar pelo `ActionExecutor` (endpoints diretos do servidor, voz) | Lote 1 item 2 | M |
| C11 | Remover dispositivo pelo PC no modo `lan`: hoje todo pedido vira o principal `lan` e o botão não funciona | Lote 1 item 3 | P |
| C12 | **[Entregue no lote 3, `9ca78f6`]** Ler brilho ao abrir "Controles do PC" cria um registro `observe` na Central a cada abertura (ruído) | Lote 2 item 6 | P |

### A. Automação, gatilhos e comandos
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| A1 | **Cadastro único de comandos e rotinas** com vários gatilhos (horário, palma, `/`, paleta, frase de voz, botão). O registro de comandos do frontend já foi desenhado para isso | Usuária | G |
| A2 | **Rotinas agendadas** com APScheduler (já instalado, não usado). Cada disparo cria um pedido. As receitas `workflow` hoje só simulam | Usuária, inventário #7 | G |
| A3 | **Palmas opcionais**: o detector atual é um esboço que nunca inicia. Falta captar o microfone, detectar palma dupla e padrões, calibrar, ligar e desligar, associar padrão a comando ou sequência. Palma sozinha só executa risco baixo | Usuária | G |
| A4 | **[Entregue no lote 3, `9336be0`]** **Palavra de ativação ligada à interface**: o detector funciona e a frase vem do perfil, mas o evento `wake_word` não é tratado por nenhum hook React. Mostrar se o detector está ativo | Paridade | P |
| A5 | Comandos de voz determinísticos (hoje a voz só vai ao chat e o modelo escolhe) | Paridade | M |
| A6 | **[Entregue no lote 3, `9336be0`]** Escape `//` para enviar mensagens que começam com `/` (hoje todo texto com `/` no início é comando). `/clima` só prepara a pergunta | Lote 2 item 4 | P |
| A7 | Spotlight (Alt+Space) e visão (Alt+V) ainda abrem o `spotlight.html` com o visual antigo | Paridade | M |
| A8 | Proatividade: horário silencioso por objetivo, adiamento, feedback, ciclo completo sinal → consentimento → intervenção (plano 005) | Inventário #7 | G |
| A9 | Automação de desktop (janelas, abrir pasta, resolução) existe mas não está registrada. Registrar atrás do catálogo ou remover | Paridade | M |
| A10 | Integrações desligadas ou sem tela: Composio (Gmail, Calendar, Notion, Slack, GitHub, Jira; biblioteca não instalada), Kasa (biblioteca ausente), MCP, Spotify, WhatsApp, Telegram, ADB, plugins e extensões (pasta vazia) | Paridade | G |
| A11 | Tool Forge: o modal existe mas nada o abre. Ligar exige recibo de aprovação para instalar código | Lote 1 item 3 | M |

### VZ. Voz
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| VZ1 | Escolher a voz **dentro** do provedor (`tts_voice`, `fish_reference_id`, `oxyy_voice`). Hoje a tela só troca o provedor | Paridade | P |
| VZ2 | Trocar configuração de voz durante uma chamada de forma segura (plano 003/015) e liberar a URL de áudio na ligação (plano 002) | Inventário | M |
| VZ3 | Pipeline de voz no servidor (`/api/voice/realtime/stream`, `/api/call`), VAD, detector de turno e emoção na voz existem mas o frontend não os usa | Paridade | M |
| VZ4 | **[decisão]** Gemini Live (fala para fala). Não usa a voz da Fish Audio. Opção: pedir texto e falar com a Fish, perdendo latência | Usuária | M |
| VZ5 | Enviar documentos para consulta no chat (o compositor só aceita imagens) | Paridade | M |
| VZ6 | Perfil do agente cobre só nome, estilo e frase de ativação. Voz e avatar ainda não fazem parte do perfil | Lote 2 | M |

### J. Janelas e módulos pessoais
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| J1 | Janelas do Life OS: treino, diário, hábitos, saúde física e mental, vícios, água, rotina, metas. O Life OS separado (`/evolute/`) tem anti-vício, treino, leitura, mente, Pomodoro e SOS | Usuária | G |
| J2 | **[decisão]** Editor de notas em janela, estilo Obsidian/Notion (TipTap, BlockNote, Lexical, Milkdown; conferir licença). O cofre atual é Markdown | Usuária | G |
| J3 | `open_window` também em `/api/chat/stream` (voz) e no chat direto do APK | Lote 2 item 5 | P |
| J4 | Abrir pelo chat o item criado (nota, tarefa). Há dois caminhos de tarefas no código | Inventário #7 | M |
| J5 | Memória com fonte visível, edição, remoção e citação na resposta | Inventário #7, referências (Khoj, Letta) | G |
| J6 | Grafo de memória (existe no Nexus; o `graphify-out/` do Jarvis é um grafo do código) | Paridade | G |
| J7 | Importar dados do Nexus com prévia, backup, destino explícito e repetição sem duplicar | Inventário #7 | G |
| J8 | Ferramentas de código (revisão, correção, snapshots, desofuscação, diagramas), assistente de reuniões, vigia de pastas e monitor ambiente: só existem no backend | Paridade | M |
| J9 | Tela do leitor de QR (só existia no painel estático antigo) | Paridade | P |
| J10 | Finanças pessoais: gráficos, categorias avançadas (hoje há lista, filtros, totais e registro manual) | Usuária | M |
| J11 | Busca de lugares (Google Places ou OpenStreetMap) como janela com mapa e lista | Usuária | G |

### O. Observabilidade e verdade na tela
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| O1 | **Página Integrações com estado real**: "configurado", "alcançável", "último sucesso". Hoje mostra só 3 componentes e "Dispositivos" aparece saudável com zero ou com erro de leitura | Inventário #5 | M |
| O2 | Registrar qual provedor e modelo realmente responderam após uma falha, e a razão da troca. Visão no mesmo contrato. Latência e custo quando conhecidos | Inventário #5 | M |
| O3 | Central: filtros por origem e capacidade, título legível, progresso por etapa, correlação de falhas, exportação revisável de diagnóstico | Inventário #5, plano 004 | M |
| O4 | Latência do servidor no cabeçalho (removida na reconstrução) | Paridade | P |
| O5 | Erros silenciosos em telas antigas (painel pessoal, clima, configurações): mostrar o erro em vez de descartar | Plano 004 | M |

### S. Sincronização
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| S1 | **[Entregue no lote 3, `8066a5c`; expiram em 90 dias]** **Lápides para exclusões**: sem elas, um item apagado (finanças, notas, tarefas) pode voltar | Lote 2 item 3 | M |
| S2 | **[Entregue no lote 3, `8066a5c`]** Hábitos não têm data de alteração: editar em um dispositivo não chega ao outro | Lote 2 item 3 | M |
| S3 | Limpar uma chave de propósito não se propaga; chave diferente no mesmo provedor vence a mais recente | Lote 2 item 3 | P |
| S4 | Chat direto do celular quebra com resposta vazia (duas rotas assumem que toda resposta HTTP bem-sucedida tem corpo legível) | Plano 001 | P |

### M. Celular (depois do desktop)
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| M1 | Gerar o pacote com `npm run build:mobile`; os assets Android ainda são da interface antiga | Inventário #1 | P |
| M2 | Modo conectado ao agente do PC: pareamento, identidade revogável, estado de conexão, recuperação de queda. O WebSocket legado só aceita loopback | Inventário #6 | G |
| M3 | Testar em aparelho físico: microfone, transcrição, saída de voz, permissões negadas, PC indisponível, desconexão e retomada | Inventário #6 | M |
| M4 | Executar o teste `-m mobile_release` ao gerar o APK (nenhum script o chama ainda) | Lote 1 | P |
| M5 | Compatibilidade do APK antigo com o novo formato de sincronização | Lote 2 | M |

### Q. Qualidade e dívida técnica
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| Q1 | Arquivos muito grandes (`server.py`, `App.tsx`) que tornam qualquer mudança arriscada. Modularizar por função com testes de contrato (plano 007) | Inventário | G |
| Q2 | Substituir `confirm()` nativo por diálogo próprio em memórias, tarefas, estudos e Life OS (plano 013) | Inventário | M |
| Q3 | Transformar o roteiro `windows.shots.cjs` (hoje fora do git) em teste versionado em `frontend/tests/` | Lote 2 | P |
| Q4 | CI e release: pacote verificável da versão atual no desktop e no APK, instalação e atualização (plano 006) | Inventário | M |
| Q5 | Remover CSS antigo órfão (Quest Log) | Lote 1 | P |
| Q6 | Validar automação real do Windows (scripts, busca, controle do sistema); filtros e recibo não são isolamento de processo | Planos 008-011 | G |
| Q7 | Fase 5 e 6 do plano 016: contratos comuns, recibos e cenários reais de aceitação para domínios do Nexus e conectores | Inventário | G |

### F. Futuro, sem data
Personagem 3D (última prioridade); Open Interpreter como especialista de programação chamado com aprovação e estudo do sandbox de sistema operacional dele; clones open source de apps conhecidos como fonte de habilidades; layouts e visões salvos pela usuária (em vez de o agente reescrever a interface).

### Ordem sugerida para o lote 3
1. V1 a V5 (validar e trocar a chave), sem custo de IA.
2. C4 + C1 (parar pedido e aprovações com alvo e efeito): pequeno e deixa o resto mais seguro.
3. A1 + A2 + A4 (+ C6 para voz): cadastro de rotinas, agendador e palavra de ativação na interface.
4. O1 + O2: Integrações e modelo que respondeu.
5. S1 + S2: lápides e hábitos, antes de a sincronização acumular mais dados.
6. J1 (treino, diário, hábitos primeiro), depois J2 se a usuária decidir.
7. A3 (palmas): depois que A1 existir.
8. Celular (M1 a M5) quando o desktop estiver estável.

### AQ. Arquitetura (itens novos da análise de 7/11/2026; ver seção 14 e `plans/017-plano-mestre-do-aplicativo.md`)
| ID | O que falta | Origem | Tam. |
|---|---|---|---|
| AQ1 | Ponto de entrada único de intenção para chat, voz, rotina, janela, celular e rotas diretas (`/api/browser/run` chama a ferramenta sem Action Kernel, `server.py:1737-1747`) | Análise de fluxo | G |
| AQ2 | **[Entregue no lote 3, `9ca78f6`]** Metadado de risco, alvo e efeito para `finance_tool`, `habit_tool`, `task_tool`, `lifeos_tool` (fora de `TOOL_CATALOG`) | Análise de fluxo | P |
| AQ3 | **[Base entregue no lote 3, `9336be0`: contrato e `runCommandById` no frontend; backend, voz, rotina e celular continuam pendentes]** Contrato único de comando valendo no frontend, backend, voz, rotina e celular | Análise de fluxo | M |
| AQ4 | Eventos de sistema (rotina disparou, sincronizou, conflito, mudou rota/chave) na Central | Análise de fluxo | M |
| AQ5 | Contador visível e limite de etapas e chamadas ao modelo por turno | Análise de fluxo | M |
| AQ6 | Medidor de uso de modelo em segundo plano, com chave para desligar o não essencial | Análise de fluxo | M |
| AQ7 | Fila offline (rascunho local) para registro manual, enviada quando o servidor confirmar | Análise de fluxo | M |
| AQ8 | Teste de contrato da "definição de pronto" (reprova item sem risco, entrada ou sync) | Análise de fluxo | P |
| AQ9 | "Desfazer" em 1 clique para ações reversíveis | Análise de fluxo | M |

### Situação do lote 3 (8/11/2026)
Entregues: C4, C1, C3, C12, AQ2, A4, A6, S1, S2, base de AQ3, e a **remoção da orb** das superfícies ativas da ligação e do Painel pessoal (`77213fe`; os componentes antigos continuam no repositório sem entrada). Continuam pendentes do lote 3: V1 a V5 (validação manual, sem custo de IA; V5 é trocar a chave da Fish Audio). Relatório para revisão externa: `.agents/tasks/desktop-lote3/report.md` (fora do git).

## 14. Análise de fluxo e arquitetura (7/11/2026)

Só leitura de código, nada executado. Detalhes: `.agents/tasks/verificacao-sistema/report.md` (versão curta) e **plano mestre: `plans/017-plano-mestre-do-aplicativo.md`** (peças-base, mapa por área, matriz de interligações, fluxos-alvo, inventário, fases F0 a F8, definição de pronto).

**Veredito.** As peças principais se ligam (comando `/` → janela; chat → orquestrador → Action Kernel → Central), mas há caminhos que fogem do Kernel (voz, `/api/browser/run`, passos de Swarm e Racing). Serve bem para chat com controle de PC e janelas sem IA; não serve ainda para rotinas, gatilhos, palmas e celular conectado ao PC. Autonomia entre os níveis 1 e 2 de 5 (uma ferramenta por vez, várias etapas com aprovação, aprovar encerra a sequência). A hipótese "autonomia sem aprovação constante exige permissões duradouras por escopo e rotinas de confiança (C2)" procede.

**Diagrama (código real).**
```mermaid
flowchart TD
  CH[Chat] --> STR[/api/chat/stream] --> OR[Orquestrador] --> AK[Action Kernel] --> TC[55 ferramentas]
  AK --> AJ[(historico local)] --> CE[Central]
  SL[Menu / e Paleta] --> WN[Janelas]
  WN -->|/api/controls/run| AK
  WN -->|/api/finance direto| DB[(dados)]
  VZ[Voz] --> STR
  VZ -.->|fora do historico| TC
  REST[/api/browser/run] -.->|sem Kernel| TC
  CF[Configuracoes] --> SB[(Supabase)]
  MO[Celular] --> REST2[REST] --> OR
```

**Fluxos (nota hoje).**
| Fluxo | Nota |
|---|---|
| a) "abre minhas finanças" | bom |
| b) `/gastos` sem IA | bom |
| c) "anota que gastei 50 reais" | com atrito (sem alvo/efeito legível nem desfazer) |
| d) "fecha o Spotify" | com atrito (aprovação não lembra a escolha) |
| e) voz com ferramenta | com atrito (fora do histórico) |
| f) "lembra que prefiro X" | com atrito (sem fonte nem recibo) |
| g) várias etapas | com atrito (aprovar encerra a sequência) |
| h) sugestão proativa | com atrito (ciclo não fechado, só desktop) |
| i) rotina agendada | inexistente |
| j) celular | quebrado |

**Nível de autonomia:** 1,5 de 5. Para subir: concessões por escopo (C2), retomar após aprovação (C8), rotinas pelo Kernel (A1/A2), proatividade com consentimento (A8).

**Os 5 problemas mais importantes.**
1. Caminhos fora do Action Kernel: voz, `/api/browser/run`, Swarm e Racing (C6, C10, AQ1).
2. O servidor não aplica a lista de ferramentas por modo; o executor aceita todas as registradas (C3).
3. Aprovação pobre e sem memória de escolha (C1, C2).
4. Rotinas, gatilhos e palmas não existem; o cadastro de comandos só está no frontend (A1, A2, AQ3).
5. Ferramentas de módulos pessoais fora do catálogo de risco (AQ2) e celular quebrado (S4, M1, M2).

**Plano mestre:** `plans/017-plano-mestre-do-aplicativo.md`. Lote 3 sugerido pelo plano: V1–V5, C4, AQ2, C12, C1, C3, AQ3, A6, A4, S1, S2. Os problemas 2 (C3), 3 (C1; C2 continua aberto) e 5 (AQ2) foram tratados no lote 3; ver "Situação do lote 3" na seção 13.
