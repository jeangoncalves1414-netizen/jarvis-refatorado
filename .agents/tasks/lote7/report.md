# Lote 7 - relatório final

Base: tag `antes-lote7` (`887553c`). Branch `main`. Nada foi enviado (sem push).
Origem da lista de trabalho: `.agents/tasks/auditoria-geral/report.md`.
Detalhe arquivo por arquivo de cada pacote: `.agents/tasks/lote7/progresso.md`.

**Escopo entregue: pacotes 1 a 4.** O pacote 5 foi cortado por decisão da usuária (ela fará com o Gemini no Antigravity) e o pacote 6 não foi começado. Os smoke tests do pacote 5 e a suíte pytest completa não foram rodados no fechamento, para economizar tokens.

## Commits

| Pacote | Commit | Mensagem |
|---|---|---|
| 1 | `4e785a8` | feat(lote7): pacote 1 - aprovacoes e loop sem estado preso |
| 2 | `45de018` | feat(lote7): pacote 2 - nada some e nada mente |
| 3 | `7d11f7a` | feat(lote7): pacote 3 - economia de tokens |
| 4 | `4289ddc` | feat(lote7): pacote 4 - seguranca local e repositorio |
| relatório | (este commit) | docs(lote7): relatorio final |

## Pacote 1 - Aprovações e loop sem estado preso (MG1, MG3, MG8, MG12)

**Feito**
- Regras de "Permitir e autorizar" agora têm risco e digest dos argumentos. Ação crítica (ex.: `script_runner`) só gera regra amarrada ao código exato; regra manual para crítica é recusada. Ação alta sem alvo (ex.: `phantom_typer`) fica amarrada ao digest, ou exige a caixa "Vale para qualquer alvo" no formulário manual. Regras antigas largas deixam de valer.
- Duração padrão passou de "Sempre" para "Só agora" (botão, formulário e backend).
- Modo liberado ganhou validade opcional ao ligar: até desligar (padrão, igual ao antigo), 1 hora ou hoje. Selo vermelho mantido.
- Aprovar ou recusar depois de 10 min não deixa mais o pedido "em andamento": o pedido é encerrado como falha com mensagem. Propostas paradas viram "expiradas" (varredura ao consultar `/api/actions` e `/api/runs`).
- O loop só considera falha a etapa que não foi corrigida depois (mesma ferramenta e mesmo alvo) e usa o status da ação, não a procura por "erro"/"falha" no texto.
- Fixture `autouse` isola `auto_approvals` em `tmp_path` nos testes (MG12 parcial).

**Como testar no app**
1. Configurações > Aprovações: o botão "Permitir e autorizar" começa em "Só agora". Crie uma regra manual para `script_runner`: deve ser recusada.
2. Peça um script com "Permitir e autorizar"; peça outro com a mesma descrição e código diferente: deve pedir aprovação de novo.
3. Ligue o Modo liberado com "1 hora" e veja o texto "Ligado até ...".
4. Deixe uma proposta do loop esperando mais de 10 min e aprove: o pedido deve aparecer como falha, não "em andamento".

**Testes:** `tests/test_auto_approvals.py` (23, novo) e `tests/test_agent_loop.py` (+9). Conjunto de 13 arquivos na época: 318 passaram.

**Pendente:** status do pedido na Central continua `failed` se alguma ação falhou mesmo que o agente a tenha corrigido (`_refresh_run`; decisão de produto). `mic_capture` e `/api/voice/capture/*` sem testes. MG2 (Modo liberado aprova crítica depois de ler conteúdo externo) mantido por decisão da usuária. Checkpoint do loop ainda só em memória (pacote 6).

## Pacote 2 - Nada some e nada mente (MG4, MG5, MG9, MG13, MG23)

**Feito**
- Groq: ferramenta que lança exceção ou volta vazia informa "falhou; nada foi confirmado" (acabou o "Ação concluída com sucesso"). `RunCancelled` é repassado. O fallback não começa mais com "Pronto.".
- Ligação por voz: evento `error` é falado e aparece no balão; `plan.summary` é usado sempre que nada foi transmitido (atalhos como "crie uma tarefa X" voltam a ser falados).
- Chat: `agent_reply` de outro pedido não fecha mais o balão do turno atual (compara `run_id`). Falha genérica de chat aparece no aviso vermelho mesmo com histórico aberto.
- Água: só diz "registrados" com confirmação do servidor; falha mostra o erro real, não soma, guarda rascunho em `localStorage` e reenvia ao abrir o app, ao voltar a rede e após o próximo registro bem-sucedido. Dashboard mostra aviso com botão "Reenviar".
- Acentos quebrados corrigidos em `useMediaAssistant.ts`, `useStudy.ts` e `SettingsPage.tsx` ("°" virou "·"); checagem `broken-text.cjs` ao final dos 5 smoke tests.

**Como testar no app**
1. Ligação por voz: diga "crie uma tarefa comprar pão"; deve responder por voz e balão.
2. Desligue o backend e clique no botão de água: deve mostrar erro, não somar. Religue e veja o reenvio.
3. Com um pedido esperando aprovação, envie outra pergunta e aprove o primeiro: a resposta nova não pode ser trocada pela antiga.

**Testes:** `tests/test_llm_groq_tools.py` (4, novo); 31 passaram nos 5 arquivos de LLM/ferramentas. Smoke `agent-loop`, `chat-cancel`, `popups`, `runs` passaram na época.

**Pendente:** sem teste automático do `status: "error"` na voz (exige microfone). Rascunho de água é por aparelho; se o servidor gravou mas a resposta não chegou, o reenvio pode somar 250 ml em dobro. `EvoluteHubPage.tsx` não foi mexido.

## Pacote 3 - Economia de tokens (MG6, MG7)

**Feito**
- Extração de memória em segundo plano só dispara com gatilho ("prefiro", "me lembre", "meu nome é", "eu moro" etc.). Nova chave "Extrair memórias de toda mensagem" (desligada) em Configurações > Agente e popups devolve o comportamento antigo.
- Perguntas e conversa não entram mais no loop (`?`, "o que", "por que", "como", "explica", "qual", "quem", "onde", "quanto", "você acha"...). Verbo de ação só conta no começo de cada oração.
- No loop, o catálogo enviado ao modelo é filtrado por provedor: ferramentas de dados (hábito, tarefa, LifeOS, agenda, notas, abrir janela/tela) + as citadas pelo nome + as das palavras do pedido.

**Como testar no app**
1. Mande "oi, tudo bem?" e confira que só uma chamada ao modelo é feita (log do provedor ou painel do provedor).
2. Mande "prefiro respostas curtas": deve haver a segunda chamada de extração.
3. Pergunte "por que o céu é azul": não deve abrir o loop (sem "Etapa X de N").
4. Ligue a chave "Extrair memórias de toda mensagem" e confirme o POST em `/api/settings/agent-loop`.

**Testes:** `tests/test_token_economy.py` (14, novo), `tests/test_loop_policy.py` (+8 frases), `tests/test_agent_loop_settings.py`. Conjunto de 13 arquivos na época: 323 passaram.

**Pendente:** sem medidor de tokens (AQ6). `LOOP_KEYWORD_TOOLS` é heurística por palavra. "eu sou" e "sempre que" são gatilhos largos (custam no máximo uma chamada).

## Pacote 4 - Segurança local e repositório (MG10, MG14, MG15, MG17, MG26, V5)

**Feito**
- `POST /api/vault/notes`, `daily/log` e `profile/fact` passam pelo Action Kernel (origem `window`, aparecem na Central). Pasta validada contra a lista de pastas da ferramenta, sem `..`, caminho absoluto ou `:`; `save_note` também recusa pasta fora do cofre. Roteador FastAPI morto `app/ui/panel/api/vault.py` apagado.
- `/api/evolute/water/add` valida 1 a 5000 ml (ausente = 250) e registra por `run_action("lifeos_tool", ...)`.
- Erros técnicos não vão mais crus para a tela nas rotas mais visíveis (chat, água, hábito, lembrete, cofre); o detalhe fica no console e em `diagnostics`.
- Chaves no console mostram só os 4 últimos caracteres (`app/core/secrets_mask.py`).
- `pyproject.toml` completo (`websockets`, `numpy`, `requests`, `vosk`, `pystray`, `pywin32` no Windows, `duckduckgo_search`; extra `oxyy` com `openai`).
- `app/contexto.md`: chaves Supabase trocadas por marcadores.
- V5: `test_fish_audio.py` e `.mp3` apagados da raiz; `.gitignore` com `test_fish_audio.*`.

**Como testar no app**
1. Criar nota no cofre pelo painel: continua gravando em `data/vault/04-Projects` e aparece na Central.
2. Chamada manual com pasta `../../Desktop` em `/api/vault/notes`: 400, nada gravado fora do cofre.
3. Água com 0, -5 ou 99999 ml: 400 com mensagem em português; total não muda.
4. `pip install -e .` em ambiente limpo deve trazer as dependências obrigatórias.

**Testes:** `tests/test_lote7_security.py` (25, novo). Junto com 12 arquivos vizinhos: 146 passaram, 2 falharam (`test_stt_providers.py::test_whisper_local_success` e `::test_whisper_local_fallback_to_google`, que já falhavam antes: o método `_transcribe_whisper_local` não existe no HEAD).

**Pendente:** a usuária precisa trocar/revogar a chave da Fish Audio no site (apagar o arquivo não invalida a chave nem limpa cópias na Lixeira, backups ou histórico de chat). Conferir o RLS do Supabase (V3); a troca no `contexto.md` não remove as chaves do histórico do git. Cerca de 55 `str(exc)` em rotas menos visíveis de `server.py`. Os 2 testes de STT local quebrados.

## Verificação do fechamento (nesta etapa)

- `pytest` nos 7 arquivos criados/alterados no lote 7 (`test_agent_loop`, `test_agent_loop_settings`, `test_auto_approvals`, `test_llm_groq_tools`, `test_loop_policy`, `test_lote7_security`, `test_token_economy`): **134 passaram**, 0 falhas (38 s).
- `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` em `frontend/`: sem erros.
- Não rodados: smoke tests (os 4 do lote passaram ao fim de cada pacote; `workspace` falha no passo do ditado, MG27), suíte pytest completa, `test_habits_tasks_finance.py`, `test_desktop_modules.py`.
- Nada testado com o app real aberto, provedores reais de IA, Supabase real ou APK.

## Para o Gemini/Antigravity

Instruções gerais para a outra IA: repositório `c:\Users\maria\Desktop\Jarvis`, branch `main`. Nunca dar push, nunca mexer no stash, nunca em `mobile_app/`, nunca `git add -A` (adicionar arquivos pelo nome). Mensagens de commit curtas e convencionais. Textos para a usuária em português com acentos corretos (existe checagem de acento quebrado nos smoke tests). Depois de editar o frontend: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `npm run build` e os smoke tests em `frontend/tests/` (`agent-loop`, `chat-cancel`, `popups`, `runs`, `workspace`) com o Vite e APIs simuladas. Tag de retorno: `antes-lote7`.

### Pacote 5 - verdade na tela e limpeza (frontend, P/M)

Itens: MG21, MG22, MG16, MG29, MG24, MG20, MG27. Verificação: `tsc`, `npm run build` e os 5 smoke tests. Textos abaixo copiados da auditoria (`.agents/tasks/auditoria-geral/report.md`); o número de linha pode ter mudado depois dos pacotes 1 a 4, confirme com busca.

1. **MG21 - Verdade na tela (média).**
   - Arquivo: `frontend/src/components/QuantumStatsWidget.tsx:9-16`, usado em `frontend/src/pages/DashboardPage.tsx:134` (Painel pessoal).
   - Problema: CPU, RAM, ping e threads são números aleatórios (`Math.random`) a cada 2,5 s. Viola "números vêm da API". Reprodução: abrir o Painel pessoal; os valores mudam sozinhos sem ligação com o PC.
   - Correção sugerida: remover o widget ou ligar em `/api/metrics` (CPU e RAM reais; sem ping falso).

2. **MG22 - Painel pessoal desatualizado (média).**
   - Arquivos: `frontend/src/App.tsx:422-431` (atualiza só quando a tela ativa é `Dashboard` = "Início"), `App.tsx:199,298-301` (`taskInputRef` nunca ligado a um campo), `App.tsx:666` (`<DashboardPage>` renderizado em `active === 'Painel pessoal'`).
   - Problema: os dados do Painel pessoal (tarefas, finanças, clima) só se atualizam enquanto a tela "Início" está aberta, onde não aparecem. Depois de "abre o painel e adiciona hábitos", o painel provavelmente mostra dados velhos até recarregar. "Nova tarefa" vai para Início e foca um campo que não existe.
   - Correção sugerida: atualizar quando `active === 'Painel pessoal'` e também ao receber popup ou `agent_reply` de ferramentas de dados. Ligar `taskInputRef` ao campo do painel e mandar `openNewTask` para 'Painel pessoal'.
   - Observação da auditoria: `DashboardPage` escuta alguns eventos de sincronização locais, mas nenhum emitido pelas ações do backend; confirmar no app real.

3. **MG16 - Desempenho / consultas periódicas (baixa).**
   - Arquivos: `frontend/src/App.tsx:334` (`/api/bridge` a cada 5 s), `App.tsx:359` (`/api/metrics` + `/api/logs` a cada 15 s), `App.tsx:342` (wake word, 15 s), `frontend/src/components/AutoApprovals.tsx:20` (15 s), `frontend/src/components/FloatingCoreOverlay.tsx:26` (5 s).
   - Problema: com o app parado são cerca de 25 requisições por minuto, mesmo com a janela escondida. Métricas e logs são buscados fora da tela Métricas.
   - Correção sugerida: buscar métricas só na tela que mostra; pausar tudo com `document.hidden`; bridge a cada 15-30 s.

4. **MG29 - `confirm()` nativo (baixa).**
   - Arquivos: `useChat.ts:267`, `useDirectChat.ts:512`, `useStudy.ts:200,218,568`, `MemoriesPage.tsx:52`, `App.tsx:405,447` (8 confirmações nativas fora do tema; a de `useStudy.ts:218` tinha acento quebrado, corrigido no pacote 2).
   - Correção sugerida: trocar pelo `ConfirmDialog` que já existe (`frontend/src/components/ConfirmDialog.tsx`). Achar com `Select-String 'confirm\('`.

5. **MG24 - Acessibilidade (baixa).**
   - Arquivos: `frontend/src/components/LiveCallModal.tsx`, `CinemaModal.tsx`, `ToolForgeModal.tsx`, `BiometricScannerModal.tsx`.
   - Problema: a ligação não fecha com Esc, não põe o foco no modal e não respeita "reduzir movimento". Os outros três modais não têm `role="dialog"` ou Esc. `ConfirmDialog` e `WindowManager` já fazem certo.
   - Correção sugerida: copiar o padrão de `ConfirmDialog.tsx` (role, Esc, foco, `prefers-reduced-motion`).

6. **MG20 - Código morto (baixa, M).**
   - Arquivos: `frontend/src/components/JarvisOrb3D.tsx`, `JarvisOrb.tsx`, `ReactorCommandCard.tsx`, `FloatingCoreOverlay.tsx` (nenhum é importado por tela ativa); `frontend/src/styles.css` (cerca de 305 classes sem uso literal no TS/TSX, incluindo 23 `quest-*`, 9 `cmd-*`, `calendar-focus*`); 15 scripts de depuração versionados na raiz (`check_chat_html.py`, `line_lookup*.py`, `temp_*.py`...). O roteador FastAPI morto `app/ui/panel/api/vault.py` já foi apagado no pacote 4.
   - Atenção: o número de classes é um teto, porque nomes montados em tempo de execução não aparecem na busca. Conferir cada classe antes de apagar. `FloatingCoreOverlay.tsx` tem um `setInterval` (MG16); apague o componente ou ajuste, não os dois.
   - Correção sugerida: remover em um commit só de limpeza; rodar `tsc`, `npm run build` e os smoke tests. Não apagar os scripts da raiz sem listar para a usuária o que cada um faz.

7. **MG27 - Smoke `workspace` quebrado (baixa).**
   - Arquivo: `frontend/tests/workspace.smoke.cjs`, passo "Ditado pela paleta liga o microfone do compositor" (linha ~243).
   - Problema: falha igual antes e depois dos lotes 6 e 7; as partes depois do passo (menu "/", etc.) e a checagem final de acento quebrado não são conferidas.
   - Correção sugerida: simular `MediaRecorder`/`getUserMedia` no smoke ou pular o passo com aviso, para o resto do teste voltar a rodar.

### Pacote 6 - maior, sem pressa (lista pronta para outra IA)

Cada item deve virar um commit próprio, com testes pytest que não dependam de provedor real nem de `data/` (usar `tmp_path` e as fixtures de `tests/conftest.py`).

1. **MG11 - Histórico da voz só pelo servidor (M, média).** `frontend/src/hooks/useChat.ts:713-725` (`appendExchange`). Depois que o backend grava o turno (o SSE recebe `session_id` e `handle_request` salva), o navegador manda o histórico inteiro por `POST /api/sessions/{sid}/history` e sobrescreve o do servidor, perdendo `run_id` das mensagens e podendo apagar o que o servidor gravou no meio-tempo. Causa provável de balões "recriados" na ligação por voz (não confirmada). Correção: quando o turno foi pelo SSE com `session_id`, não regravar; só recarregar o histórico do servidor, ou criar rota que só acrescenta.
2. **O3/O4/O5 refeitos do zero (MG25).** O `stash@{0}` "lote4 grupo4 parcial (O3 O4 O5)" (base `890c8cf`) não aplica mais por inteiro (conflito em `app/storage/action_store.py`, `AppShell.tsx`, `RunHistory.tsx`). Usar só como referência de ideias; **não mexer no stash** e não descartá-lo sem aval da usuária.
3. **C7 - Aprovar e recusar dentro da resposta do chat.** Hoje só há o link "Ver execução". Reaproveitar `AlwaysAllowButton`.
4. **Checkpoint do loop em disco.** Hoje `app/core/loop_checkpoints.py` guarda só em memória (TTL 600 s); reiniciar o backend perde a retomada (C8).
5. **AQ6 - Medidor de chamadas ao modelo em segundo plano**, com chave para desligar o não essencial. Hoje a contagem só existe nos testes.
6. **A1/A2 - Rotinas com APScheduler** (cadastro, agendador; palmas A3 depois).
7. **MG2 - Modo liberado e conteúdo externo.** Só depois de a usuária decidir (opção: manter aprovação para `critical` em turno que leu conteúdo externo).
8. Outros achados abertos da auditoria, sem pacote definido: **MG18** (`app/services/voice/mic_capture.py:176-191`: `_active` fica `True` se o microfone não abre em 6 s; usar número de geração por captura e despausar a palavra de ativação no timeout), **MG19** (`app/services/places.py:154-190`: mensagem útil com 0 resultados e campo de e-mail de contato em Configurações), **MG28** (cerca de 31 `catch` vazios em `App.tsx`, 21 em `useMediaAssistant.ts`, 11 em `useDirectChat.ts`, 11 em `jarvisCloud.ts`, 10 em `StudyPage.tsx`; começar pelas ações da usuária: salvar, apagar, registrar, com `setNotice(erro)`), **MG30** (tema: cores fixas em `SettingsPage.tsx`, `ChatComposer.tsx`, `PlanningWorkspace.tsx`, `DashboardPage.tsx`, `LiveCallModal.tsx`, `StudyDialog.tsx`; migrar para `styles/ws-tokens.css`, uma tela por pacote), **2 testes quebrados** em `tests/test_stt_providers.py` (`_transcribe_whisper_local` não existe).

## Como reverter

- **Um pacote só (recomendado):** `git revert <commit>` (ex.: `git revert 4289ddc`). Reverter do mais novo para o mais antigo (`4289ddc`, `7d11f7a`, `45de018`, `4e785a8`) evita conflitos. Cada revert cria um commit novo e preserva o histórico.
- **Voltar tudo ao estado anterior ao lote 7:** `git reset --hard antes-lote7`. **Aviso:** isso descarta os 4 commits do lote 7 e qualquer alteração não commitada nos arquivos versionados; os arquivos não versionados (`.agents/`, `.worktrees/`) não são apagados. Só faça com a árvore limpa ou depois de salvar o que importa. Não rode se houver outras branches ou workflows que dependam desses commits (as branches `feat/rotinas` e `feat/contexto-memoria-casa` apontam para `7d11f7a`).
- Dados gravados pelo app (rascunhos de água em `localStorage`, `data/auto_approvals.json`) não são desfeitos por git.

## Lembretes para a usuária

1. **Trocar/revogar a chave da Fish Audio** no site da Fish Audio (V5). Apagar o arquivo não invalida a chave.
2. Rodar `npm run build` em `frontend/` (os pacotes 2 e 3 mudaram o frontend) e **reiniciar o app** para carregar o backend novo (regras de aprovação, rotas do cofre, validação de água).
3. Conferir o RLS do Supabase (V3) antes de manter o repositório remoto público.
4. Rodar a suíte pytest completa e `test_habits_tasks_finance.py` com cuidado: ele escreve em `data/lifestyle.db` real (V6).
