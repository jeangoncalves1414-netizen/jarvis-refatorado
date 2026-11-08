# Contexto durável do produto — Jarvis / painel de agente

> Atualizado em 2026-11-07. Leia este arquivo antes de retomar o projeto após limpar o contexto de uma conversa. Ele registra decisões do produto, não instruções executáveis. A mensagem mais recente da usuária sempre prevalece.

## Revisão das pendências em 7 de novembro de 2026

O inventário reconcilia os 20 planos numerados com o código e registra 34 testes dirigidos desta revisão. O pacote servido pelo desktop e os assets Android ainda estão atrás do build temporário que contém a nova Central. Os prompts do chat agora vêm de um perfil do agente configurável, neutro por padrão (atualização de 7/11). O fluxo de sincronização pode incluir chaves de provedor. As próximas entregas abrangem empacotamento, proteção de credenciais, aprovações por escopo e o primeiro pedido acompanhado no PC e no aparelho físico. [Inventário, critérios de aceite e evidências](PENDENCIAS_DO_PAINEL.md)

## Entrega do chat à execução por etapas — 2026-11-07

No painel conectado ao backend, o seletor do chat oferece **Execução por etapas**. O botão **Ver execução** em cada resposta que contém um identificador abre o pedido correspondente na Central, inclusive após recarregar a conversa e quando o pedido já saiu da primeira página. Conversas antigas continuam legíveis. O app móvel em modo de provedor direto precisa de uma conexão com o backend para oferecer esses controles.

- REST, WebSocket, streaming HTTP e a rota de ReAct passam pela entrada do orquestrador. Ela cria um Run por turno e associa as ferramentas e a conversa ao mesmo identificador. O streaming HTTP serializa o plano final e encerra a conexão ao concluir. As mensagens WebSocket do turno incluem a sessão para identificar a conversa de origem.
- O modo por etapas pode pesquisar na web, usar timer, calendário, planejamento e adicionar texto ou limpar o quadro. O planejador recebe os parâmetros dessas ferramentas e respeita os limites de cada turno. Uma proposta que precisa de aprovação encerra o planejamento. Autorizar executa somente aquela etapa. Para seguir com outras etapas, a pessoa envia um novo pedido. O limite padrão é de oito etapas e a API aceita de uma a vinte.
- **Exemplo verificado.** Uma proposta para limpar o quadro mantém as duas conversas intactas até a autorização. Mesmo se o plano sugerir outro identificador nos argumentos, a ferramenta limpa apenas o quadro da conversa de origem. A proposta já pode ser decidida assim que aparece na Central, inclusive com o planejador ainda na outra thread.
- O cancelamento é verificado antes e depois do planejamento e entre ferramentas. Uma chamada em andamento pode precisar retornar. Uma falha de ferramenta, um plano inválido, a ausência de provedor ou o limite de etapas aparecem como falha. A Central preserva o estado de cada ação já executada.
- Meios de entrada diferentes reconhecem os mesmos atalhos explícitos de criar tarefa e listar arquivos. **Criar tarefa grava na mesma lista persistente de Painel pessoal**, com o identificador da tarefa na resposta. O armazenamento serializa alterações concorrentes no processo. Uma falha de leitura preserva o arquivo de tarefas anterior. A listagem usa a pasta base configurada e a resposta mostra até 40 nomes. O journal recebe a contagem ou uma falha. Uma simples pergunta sobre metas, tarefas ou documentos segue para a conversa.
- **Cobertura restante.** Swarm e Racing pelo chat têm registro do pedido, mas as chamadas internas de cada especialista/provedor ainda carecem de eventos por etapa. A rota direta de Swarm, rotinas, memória em segundo plano, automações diretas e o provedor direto do celular continuam fora dessa integração. A próxima prioridade é exibir alvo, operação e efeito também nas demais propostas, seguida das permissões por escopo e da conexão do APK com a Central.

**Verificação desta entrega.** Passaram 98 testes Python com dados temporários e rede externa bloqueada. Eles incluem uma chamada HTTP real à rota de aprovação, o evento terminal do streaming HTTP, o isolamento dos quadros, a leitura pela API de tarefas depois da criação pelo chat e seis criações concorrentes. Permanecem três avisos de depreciação de dependências.

TypeScript e os testes de navegador `frontend/tests/workspace.smoke.cjs` e `frontend/tests/runs.smoke.cjs` passaram. O primeiro cobre o novo modo e o vínculo da resposta após recarregar. O segundo cobre detalhes, cancelamento e largura de 360 px. As APIs nesses testes de navegador são simuladas. O build Vite em pasta temporária passou com o aviso existente de tamanho dos pacotes de diagramas. A validação com provedor real e APK instalado continua pendente.

Para experimentar em desenvolvimento, inicie o backend do projeto pelo comando `python -m app.main` e abra a prévia Vite em `http://127.0.0.1:5173`. No chat, selecione **Execução por etapas**. **Ver execução** aparece nas respostas vinculadas a pedidos da Central.

## Entrega anterior de pedidos, recuperação e cancelamento — 2026-11-07

O segundo incremento implementou **Run** nos turnos que passavam por `_run_llm_with_tools`, nos caminhos nativo e de marcadores, inclusive no worker de streaming. A seção mais recente acima registra a ampliação desse escopo.

- `RunRecord` registra identidade, sessão, modo solicitado, origem, política aplicada, estados, timestamps e resumo terminal. O conteúdo integral do pedido e a deliberação do modelo não são copiados para esse journal. `AgentPlan.context.run_id` identifica o pedido na resposta; cada `ActionRecord.run_id` liga a ferramenta ao pedido. O contexto é local à thread; callbacks aprovados depois conservam a identidade de origem.
- SQLite mantém estado e eventos de ação/pedido na mesma transação. A resposta terminar não conclui um pedido com propostas ainda pendentes. Aprovação, recusa, falha e conclusão atualizam o agregado. A API oferece `GET /api/runs`, detalhes, replay por `after_event_id` e `POST /api/runs/{id}/cancel`, sob o controle existente de host/origem/token. A listagem filtra por estado/sessão e pagina por sequência de criação.
- Cancelamento cooperativo entre etapas: bloqueia novas propostas e início de ferramentas, cancela propostas ainda não iniciadas e descarta callbacks pendentes. Durante chamada de ferramenta ou provedor não cooperativo, permanece `cancel_requested` até o retorno. O resultado de uma etapa já executada é preservado; cancelamento não significa desfazer efeitos. Ainda não foram adicionados tokens de interrupção dentro de subprocessos, navegador ou adaptadores de ferramentas.
- Na partida do painel, um lock de arquivo mantido pelo processo impede dois runtimes atuais de tomar o mesmo journal. Apenas o proprietário faz a recuperação: propostas/autorizações antigas expiram; ações `running` passam a `interrupted` com efeito externo desconhecido; pedidos abertos passam a `interrupted`. Nada é reexecutado. Leituras e reabertura por leitores não provocam recuperação. O lock termina ao encerrar o processo, não ao parar só o servidor HTTP. Executáveis antigos que não usam esse lock não são suportados em paralelo.
- A Central mostra **Pedidos de execução**, filtro por estado/conversa atual, paginação, etapas, linha do tempo, duração e abertura da conversa original. O cancelamento trata erro/retry, mantém estado recebido quando desconecta e espera confirmação real. Ações antigas permanecem no histórico individual. O botão de “Abortar Quest” que só alterava React deixou de ser conectado, e o Quest Log foi removido do painel; a Central de Execuções é a fonte de verdade de Run.
- A retenção preserva grupos inteiros: até 2.000 pedidos como limite flexível, removendo primeiro pedidos terminais antigos com suas ações/eventos ao criar novos. Ações vinculadas não são podadas individualmente. Ações avulsas mantêm o limite anterior; pedidos ativos podem ultrapassar o limite, e o total de ações vinculadas pode exceder 2.000.

### Validação e observações desta etapa

- **59 testes Python passaram** (inclui 13 testes de Run e um teste HTTP novo): agrupamento, dois turnos independentes, aprovação posterior, disputa cancelamento/início, ferramenta lenta, cancelamento de ação aprovada, evento atômico, recuperação exclusiva/idempotente, paginação, retenção por grupo, exceções sem segredo no journal e bloqueio de origem estrangeira.
- Comando: `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_runs.py tests/test_action_history.py tests/test_orchestrator_action_results.py tests/test_action_kernel.py tests/test_actions.py tests/test_mission_control.py tests/test_native_action_boundary.py tests/test_guardrails_thread_safety.py tests/test_control_plane_security.py tests/test_tool_catalog.py`. Permanece um aviso de depreciação do OpenTelemetry.
- TypeScript e os testes `frontend/tests/workspace.smoke.cjs` e `frontend/tests/runs.smoke.cjs` passaram. O teste de pedidos cobre cancelamento 500/retry/pendente/terminal, reload, falha preservando detalhes, recuperação, filtros, paginação, 360 px e link para conversa. Screenshots sintéticos revisados em `%TEMP%/agent-workspace-review`, incluindo `mobile-request-360.png`.
- Build Vite direto passou em `C:\Users\maria\AppData\Local\Temp\agent-workspace-build-20261107-runs` (log com o mesmo nome e extensão `.log`), em 1m04s. Continua o aviso de chunks grandes de diagramas. Não foi usado `npm run build` nem o postbuild Android. Prévia verificada com HTTP 200 em `http://127.0.0.1:5173/`; depende do processo Vite ativo.
- A migração/recuperação só foram executadas em bancos temporários. Backend pessoal, provedores reais, Windows e APK instalado não foram testados. Não executar uma segunda instância sobre o mesmo journal. O APK e seus assets não foram regenerados.
- Próxima prioridade: levar os caminhos legados ao mesmo núcleo, transmitir cancelamento para adaptadores longos e substituir propostas genéricas por alvo/operação/efeito/escopo. Só então tratar o agrupamento e a interrupção como universais. Conexão real desktop/celular e validação do APK continuam necessárias.

## Entrega de confiabilidade e histórico — 2026-11-07

Após a autorização para prosseguir, foi entregue o primeiro incremento do núcleo da fase 1 e do histórico da fase 3. Esta seção descreve a entrega anterior à implementação de pedidos documentada acima.

- `ActionExecutor` agora recebe `ToolResult` completo nos caminhos de function calling e marcadores. `ok=False`, retorno inválido e exceção não viram sucesso. Execução imediata e aprovada usam o mesmo fluxo. Corrigido também um import local que impedia o caminho de marcadores de executar; nesse caminho, uma mensagem otimista produzida antes da ferramenta é substituída pelo erro/proposta quando necessário.
- Cada turno tem seus próprios guardrails, com contadores protegidos por lock. Aprovações pendentes conservam os limites do turno de origem. Uma lista vazia de ferramentas permitidas bloqueia todas as ferramentas.
- Os argumentos de uma proposta são copiados profundamente e vinculados por digest. Transições de aprovação usam comparação de estado na transação e o callback é retirado uma única vez. Recusar descarta o callback; rejeitar uma ação já iniciada retorna conflito. Após reinício ou expiração, tentar aprovar retorna 410 e não reexecuta a ferramenta.
- Estado e eventos de cada ação são gravados juntos em SQLite. A API oferece histórico paginado, busca por ferramenta/proposta, filtro por estado, detalhes e replay com `after_event_id`. A paginação usa a sequência de criação para não repetir itens quando novas ações chegam.
- A Central usa essa API para mostrar linha do tempo, duração quando há início conhecido, resultado e aprovações nos detalhes, inclusive fora das dez propostas do resumo. Preserva a última página/detalhes quando há erro e indica dados possivelmente desatualizados. Os contadores abrangem todo o histórico retido, não só as vinte ações recentes.
- O journal guarda resumos limitados, com ocultação dos valores conhecidos em argumentos sensíveis e de formatos comuns de credenciais. Não persiste `ToolResult.data` nem o corpo de exceções. Essa ocultação é defensiva e não garante identificar todo segredo em texto livre; não é criptografia nem auditoria de todos os logs legados.

### Persistência, migração e recuperação

- Caminho padrão novo: `data/action_journal.sqlite3`. A primeira abertura importa os snapshots de `data/action_journal.jsonl` uma única vez, em transação, sem alterar ou apagar o arquivo anterior. Cada snapshot recebe apenas um evento `legacy_import`; etapas anteriores não são inventadas.
- A partir dessa abertura, novas gravações usam SQLite. Retornar ao código antigo faria o aplicativo ler o JSONL desatualizado; isso **não** constitui rollback completo dos dados. Para backup consistente, parar o backend antes de copiar o banco e conservar o JSONL original. Não apagar o banco para tentar repetir uma aprovação.
- A retenção original era de 2.000 ações com preservação das não terminais; para ações vinculadas a pedidos, agora vale a retenção por grupo descrita acima. Não é um arquivo de auditoria ilimitado.
- Aprovações executáveis continuam somente em memória, com validade de dez minutos. A entrega posterior expira propostas automaticamente na partida. Durante o mesmo processo, a expiração por TTL ainda é refletida no journal ao tentar aprovar; não existe um varredor periódico.
- A entrega posterior reconcilia `running` como `interrupted` ao iniciar o runtime exclusivo. Não tratar registros de um backend desligado como prova de atividade atual nem reexecutá-los automaticamente.
- A migração foi exercitada em arquivos temporários. O backend pessoal não foi iniciado nesta entrega para testar ferramentas reais, e o banco de ações pessoal não foi migrado durante a validação.

### Validação deste incremento

- **45 testes Python passaram**, cobrindo falhas tipadas nos dois caminhos do orquestrador, dois turnos concorrentes, aprovação simultânea, parâmetros congelados, replay, reabertura do banco, importação legada, rollback de estado quando falha a escrita de evento, retenção, filtros e contadores. Comando: `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_action_history.py tests/test_orchestrator_action_results.py tests/test_action_kernel.py tests/test_actions.py tests/test_mission_control.py tests/test_native_action_boundary.py tests/test_guardrails_thread_safety.py tests/test_control_plane_security.py tests/test_tool_catalog.py`.
- TypeScript passou. `frontend/tests/workspace.smoke.cjs` passou com APIs simuladas: inclui agora linha do tempo/duração, paginação, busca, erro preservando o histórico, reload e detalhes em 360 px, além dos fluxos da entrega anterior.
- Build Vite direto passou em `C:\Users\maria\AppData\Local\Temp\agent-workspace-build-20261107-actions`, sem postbuild Android. Permanece o aviso de chunks grandes de diagramas. Log: `C:\Users\maria\AppData\Local\Temp\agent-workspace-build-20261107-actions.log`. Prévia Vite reiniciada em processo oculto e verificada com HTTP 200 em `http://127.0.0.1:5173/`; sua disponibilidade depende desse processo.
- Os testes usam ferramentas e dados sintéticos; não comprovam integração fim a fim com provedores reais, controle do Windows ou APK instalado. Assets Android preexistentes foram preservados nesta entrega.

### Sequência após esta primeira entrega

Run, vínculo de sessão, recuperação e cancelamento entre etapas foram adicionados na entrega acima. Continuam pendentes os caminhos de ferramentas externos ao executor, cancelamento dentro dos adaptadores e propostas com alvo/efeito/escopo claros. A identidade do agente continua independente da navegação.

## Entrega de interface — 2026-11-06

A usuária autorizou começar a recriação do painel com qualidade de interface semelhante a ChatGPT/Claude e controles adicionais. Essa autorização antecipou a camada visual da fase 4; **não significa que as fases 1–2 do núcleo estejam concluídas**.

- Identidade visual neutra provisória: **Workspace**, grafite com acento verde suave. Não altera prompt, voz ou personalidade do modelo.
- Navegação única em `frontend/src/navigation.ts`, usada pela barra lateral e pela paleta de comandos; as mesmas áreas estão acessíveis no menu móvel. IDs persistidos antigos preservados. O padrão de entrada passa a Conversas.
- Novo AppShell com histórico de conversas, filtro, criação de sessão, módulos pessoais recolhíveis e painel de controle do agente. O antigo Dashboard continua em **Módulos pessoais → Painel pessoal**, preservando suas funções.
- Chat reconstruído com sugestões que preenchem o rascunho, modos reais, anexos de imagem, ditado, ligação, análise de tela, cópia/exportação, confirmação de exclusão, acompanhamento do streaming e opção de voltar à última mensagem. Mantidos renderer e workspace de planejamento. Título automático desktop foi transferido do ChatPage para useChat; mobile conserva sua implementação.
- Painel lateral: modelo/provedor informados pelo backend, fallback, aprovações, últimas ações, conexões e controle de reprodução em voz. Removidos da nova experiência os seletores de persona/racing que não eram enviados ao agente.
- Execuções: propostas com autorizar/recusar, tratamento de HTTP 409/410/500 e `ok:false`, bloqueio de envio duplicado, filtros, busca, detalhes, resultado registrado e objetivos com rascunho preservado quando falha a escrita.
- Início e Integrações usam o snapshot existente. Estado de conexão começa desconhecido, tem timeout e polling sem sobreposição, preserva o último snapshot e identifica sua desatualização. Estar conectado à central **não** comprova a saúde de todas as ferramentas.
- Novo CSS em `frontend/src/styles/workspace.css`, isolado da folha legada. Menus móveis e paleta usam `dialog` nativo para foco/Escape. Viewport web permite zoom. Nenhuma dependência adicionada.

### Validação desta entrega

- TypeScript: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` passou.
- Vite: build direto em pasta temporária, sem executar o postbuild que altera assets Android. Passou; continua havendo aviso de chunk grande da biblioteca de diagramas.
- `frontend/tests/workspace.smoke.cjs`: teste de navegador com APIs totalmente simuladas, sem escrita nos dados pessoais. Cobriu envio/modo, navegação, aprovação expirada, erro de objetivo com preservação de rascunho, filtros/detalhes, desconexão/recuperação, paleta, drawers/layout 360 e 390 px, título automático e exclusão confirmada. Passou sem erros JavaScript de página.
- Capturas revisadas em `C:\Users\maria\AppData\Local\Temp\agent-workspace-review`. As capturas usam dados de teste, não evidenciam funcionamento de provedores reais.
- Verificação adicional sem mocks: o backend da porta 8000 estava indisponível; a prévia em `http://127.0.0.1:5173` manteve o chat renderizado e indicou desconexão corretamente. A prévia depende do processo Vite continuar ativo.
- Para repetir: iniciar Vite em localhost; executar o smoke test com `PLAYWRIGHT_MODULE` apontando para uma instalação de Playwright. Nesta máquina foi usado `C:\Users\maria\AppData\Local\Programs\Python\Python311\Lib\site-packages\playwright\driver\package`.

### Limites atuais após o incremento de 2026-11-07

- Run e eventos agrupam turnos do chat que passam por `_run_llm_with_tools`, com cancelamento cooperativo entre etapas. Os demais caminhos ainda precisam ser unificados. Há linha do tempo persistente por pedido e ação; o resumo continua limitado a 20 ações recentes/10 pendentes. Recusar proposta não é interromper ferramenta em execução.
- O defeito de ToolResult convertido em texto foi corrigido nos caminhos nativo e de marcadores que passam pelo executor. Ainda é necessário revisar/unificar outros caminhos de ferramentas e rotinas. O painel apresenta o **resultado registrado**, sem certificar o efeito externo ou impedir toda afirmação incorreta do modelo.
- As conexões refletem o diagnóstico atualmente fornecido pelo backend, inclusive limitações de health check de dispositivos.
- Voz/provedores reais, APK instalado e automações sobre o sistema não foram exercitados nesta entrega. O APK e seus assets preexistentes não foram regenerados.
- Configurações, estudos, conhecimento, Life OS e outros módulos conservam os componentes existentes dentro da nova navegação. Sua modernização interna é incremental.
- Próximo trabalho de núcleo: concluir fase 1 e implementar fase 2 do plano 016. Próximo trabalho visual: refinar telas internas, configurações de modelos e cenários com dados reais após validação de conexão.

## Direção atual do produto

O produto deve ser um aplicativo pessoal de agente de IA com um painel de controle excelente, organizado e confiável. O nome **Jarvis** pode continuar sendo usado como nome técnico ou temporário do projeto, mas a estrutura do aplicativo **não pode depender da personalidade de Jarvis**: a identidade, a voz, o nome e o estilo do agente precisam ser um perfil opcional e intercambiável.

O centro do produto é o agente e sua capacidade real de conversar, planejar e executar ações de forma visível e controlada. Não é apenas um organizador de tarefas, nem um painel de "Evolução" separado. Recursos de vida pessoal, hábitos, notas, metas e finanças podem existir como módulos integrados, sem substituir a tela principal do agente.

## Prioridades confirmadas

1. **Confiabilidade e controle antes de aparência ou persona.** Cada ação deve mostrar o que fará, o alvo, o risco, a confirmação exigida, o andamento, o resultado e o erro real.
2. **Painel principal do agente.** O aplicativo deve abrir no agente/painel central; módulos como Evolução/Life OS são acessíveis dentro dele.
3. **Uma rota efetiva por capacidade.** Chat, voz/TTS, transcrição/STT, imagem, vídeo, visão e embeddings precisam mostrar claramente qual provedor e modelo estão ativos agora, qual é o fallback e por que houve troca. Não apresentar várias seleções concorrentes como se todas estivessem em uso.
4. **Multimodal, mas sem promessas falsas.** Voz contínua, chat, memória, visão, geração de mídia, automações, conhecimento e integrações devem ser adicionados como capacidades com estado e recibos verificáveis.
5. **Desktop e celular fazem parte do mesmo produto.** O APK deve abrir o painel principal, não uma versão isolada do módulo Evolução. O celular deve usar as mesmas regras de consentimento, segurança e registro de execução do desktop.
6. **Poder com limites claros.** "IA suprema" significa alta capacidade sob controle do dono: permissões por escopo, confirmações para efeitos relevantes, cancelamento, auditoria, credenciais locais protegidas e nenhuma elevação silenciosa de privilégios.
7. **Custo e autonomia importam.** A arquitetura deve aceitar modelos locais e provedores externos, sem ficar presa a um gateway. Uso de chaves múltiplas é somente para as chaves autorizadas da usuária, com failover legítimo; não é um mecanismo para burlar limites de terceiros.

## O que os chats do Jarvis confirmaram

### `Consertar funções do Jarvis`

- A intenção inicial era um assistente útil semelhante a um chat de IA, com custos controlados, e não uma cópia rígida do personagem Jarvis.
- O painel de provedores ficou confuso porque misturava catálogo, provedor ativo, modelo selecionado e fallback; o agente chegou a relatar uma identidade/modelo diferente do caminho realmente ativo.
- A solução desejada é uma arquitetura multi-provedor por capacidade, com o caminho efetivo exposto no painel e no contexto factual do agente.
- O modo ligação/voz precisa parecer ao vivo e contínuo, porém essa meta deve ser medida e validada; não basta um fluxo de gravar, parar, transcrever e responder ser chamado de streaming.
- Oxyy foi tratado como um gateway útil para testes de chat, imagem, vídeo, STT, TTS e embeddings, não como dependência exclusiva. Processamento externo deve ser explícito para dados sensíveis.

### `Verificar acesso ao projeto Jarvis`

- A experiência móvel correta abre o painel completo do agente; Evolução é um módulo dentro do produto.
- O projeto já passou por tentativas de empacotamento Android, conexão de voz, recuperação de STT/TTS e modularização. Estado atual do código e testes é mais confiável do que qualquer afirmação antiga de conclusão.
- O núcleo de ações deve proteger ferramentas de navegador, arquivos, mensagens e scripts, e chamadas nativas do modelo também precisam atravessar o mesmo limite de autorização.
- Uma confirmação visual não basta: a confirmação precisa produzir uma autorização de servidor, de uso único e de curta duração, ligada ao conteúdo que será executado.

### `Implement Plan 002: secure local control…` (outro checkout Jarvis)

- O plano implementou parcialmente uma base importante: modo local/LAN, token de controle, origem confiável, credenciais de dispositivo revogáveis e recibos de autorização para scripts/terminal.
- O executor registrou que os testes de segurança e compilação Python passaram, mas o build do frontend não pôde ser feito naquele checkout e a inspeção de JSONL ainda estava incompleta. Portanto, não tratar esse histórico como uma certificação total; validar o código do checkout principal antes de estender essas áreas.
- Esse trabalho reforça a ordem correta: não expor controle remoto, pareamento de dispositivos ou execução privilegiada antes de ter autenticação, escopo, recibo e auditoria.

## Arquitetura de produto que deve guiar decisões

```text
Painel / chat / voz / celular
            |
       Run + eventos
            |
  política + consentimento + cancelamento
            |
  Action Kernel / adaptadores de capacidade
            |
resultado tipado + recibo + histórico visível
```

- Cada pedido do usuário cria ou participa de uma **execução** com eventos anexados, não apenas texto no chat.
- Ferramentas retornam resultado tipado (`ok`, saída, erro, efeitos, duração, links/artefatos); uma falha nunca pode aparecer como sucesso.
- Ações relevantes precisam de preview estruturado e política por capacidade/escopo, não apenas uma confirmação genérica.
- Execuções precisam ser canceláveis de ponta a ponta e o painel deve refletir a saúde real de cada integração.
- Persona é uma camada de apresentação sobre esse sistema, não seu núcleo.

## Ordem de entrega recomendada

1. Corrigir o ciclo de vida de execução: `Run`, `RunEvent`, resultado tipado, recibo, erro e cancelamento reais.
2. Criar a Central de Execuções e unificar o registro de ações, chat/quest log e estado das integrações.
3. Simplificar a experiência do painel e a rota de modelos/provedores por capacidade.
4. Separar marca/perfil/persona da estrutura do produto; consolidar a navegação principal.
5. Integrar módulos do Projeto AI/Nexus como adaptadores configurados e com recibos, não copiando seu backend inseguro.
6. Só então ampliar automações, navegador, Windows, dispositivos, MCP e fluxos persistentes.

O plano detalhado atual é `plans/016-neutral-agent-control-platform.md`.

## Referências já preparadas

- Vinte referências open source foram baixadas apenas para estudo em `D:\Downloads\AI-Panel-References-TEMP-2026-11-04`.
- A seleção, versões fixadas e análise ficam em `README.md`, `manifest.json` e `ANALYSIS.md` nessa pasta.
- Elas são inspiração de padrões; não devem ser copiadas sem checar licença, compatibilidade e segurança.

## Conversas exportadas do Antigravity

Em 2026-11-05 foram lidos os nove exports de `C:\Users\maria\Documents\BadIce\chat_exports\`: conversas 01–08 e 10. A conversa 09 (`Advanced Jarvis Personal AI Development`) não foi exportada em texto, apenas em `.pb`; portanto, não foi interpretada.

Os exports misturam diálogos com logs extensos e conteúdo de ferramentas. As conclusões abaixo vêm dos pedidos explícitos da usuária e de problemas observáveis, não de alegações de conclusão feitas por agentes antigos.

### 01 — Teste de voz Fish Audio

- Voz de alta qualidade e reprodução imediata são desejadas como capacidade do agente.
- O export continha uma chave de API em texto aberto. Ela **não deve ser reutilizada**, não entra neste repositório/documento e deve ser revogada ou rotacionada no provedor antes de novos testes.
- Toda chave deve permanecer no backend/gerenciador de segredos; nunca no frontend, APK, logs, commits ou arquivos de exportação.

### 02 — Erro de conexão do chatbot

- Houve falha `Failed to fetch` no chat Android apesar de a chave estar configurada.
- A lição de arquitetura é separar e apresentar: disponibilidade do backend, conectividade do app, autenticação, rota/modelo efetivos e erro recuperável. Uma chave configurada não é prova de que o fluxo móvel funciona.
- O teste de dispositivo deve ser fim a fim e reportar erro acionável, nunca apenas um erro genérico de rede.

### 03 — Plano de integração de recursos

- Este foi um histórico muito longo e ruidoso de alterações incrementais. Ele reforça a decisão atual de não continuar acrescentando funcionalidades sobre uma base sem ciclo de execução, testes e módulos claros.
- Temas recorrentes: seleção confusa de provedores/modelos, ferramentas locais, voz/visão, painel, memória, estudo, execução de scripts e automações. Eles pertencem ao produto, mas precisam ser integrados pelo Action Kernel, com política, recibo e testes.
- Não assumir que uma função listada nesse chat está pronta: verificar código e testes atuais antes de reutilizá-la.

### 04 — Reversão de código-fonte

- O projeto já sofreu regressões visuais e móveis depois de mudanças amplas de tema/personagem. A usuária tentou reverter para antes de alterações de tema amarelo/"Raphael".
- Consequência permanente: mudanças de identidade visual/persona nunca podem se misturar a mudanças de arquitetura ou de aplicativo móvel. Fazer commits pequenos, testes de regressão e rollback claro.

### 05 — Life OS / Evolução

- O módulo de evolução pessoal tem uma visão rica: estudo ENEM, flashcards, simulados e métricas; treino, saúde, água e nutrição; hábitos, memória, anti-vício, socialização, diário/calendário e visualização de progresso.
- Requisitos de UX que permanecem úteis: dados editáveis/excluíveis, histórico por data, calendário, comparação temporal, replay/timelapse de evolução, correlações e automações que reduzem cliques.
- Esse módulo deve ser opcional e integrado ao agente; não é a identidade nem a tela principal do produto. Não tratar auto-registros de hábitos ou anti-vício como fato sem confirmação da usuária.

### 06 — Grafo de conhecimento e chat

- Conhecimento persistente, busca de memórias relevantes, streaming do chat, voz e sessões foram investigados como fundações do produto.
- O grafo de conhecimento deve ser um índice explicável sobre fontes, entidades e relações, com proveniência, edição/remoção e recuperação seletiva — nunca um contexto gigante injetado em todos os prompts.
- Memória, sessões, chat e ferramentas precisam compartilhar IDs de execução e uma política de privacidade; o grafo não deve autorizar ações.

### 07 — Componente de chat

- A usuária valorizou uma experiência de chat moderna, fluida e testável, inclusive a possibilidade de testar componentes isoladamente antes de colocá-los no painel.
- A implementação deve preservar esse princípio: componentes de interface podem ser prototipados isoladamente, mas só entram no produto quando conectados a estados reais de streaming, erro, cancelamento, confirmação e acessibilidade.

### 08 — Jarvis Chat

- Visão de longo prazo: agente local/pessoal com voz, câmera sob solicitação, navegador, aplicativos, clipboard, música, pesquisa, casa/dispositivos e celular próprio, sempre sob controle da dona e com custos baixos.
- A prioridade expressa foi primeiro tornar prompt, conversa e function calling coerentes. Isso continua alinhado ao plano atual de ciclo de execução tipado e adaptadores por capacidade.
- O aplicativo próprio de celular é desejado, mas deve consumir o mesmo backend seguro e não uma coleção separada de atalhos frágeis.

### 10 — Hermes Agent e autonomia

- A usuária quer memória persistente, ajuda proativa e eventualmente execução paralela (conversar enquanto o agente executa uma tarefa), sem que isso quebre controle de navegador ou crie ações inesperadas.
- A autonomia deve ser construída como execução em segundo plano observável, com fila, estado, cancelamento, política e confirmação — não como um script que age sozinho.
- O contexto do agente deve ser enxuto, factual e recuperado sob demanda para evitar alucinação e custo excessivo. Planejamento/análise e execução podem ser separados internamente, porém toda ação externa continua precisando do mesmo limite de política e recibo.
- Um visualizador modular e animado pode mostrar efeitos confirmados (por exemplo, um item criado), mas deve ser discreto, opcional e nunca ocultar o que realmente aconteceu.
- O modo de estudos/professor ENEM é uma direção futura válida: sessões salvas, quadro espacial/zoom, materiais e questões. Não é o primeiro incremento; depende primeiro de sessões, conhecimento e execução confiáveis.

## O que ficou explicitamente obsoleto

- O produto não deve ser preso à personalidade, à cor ou ao personagem "Jarvis"/"Raphael". Nome, voz, avatar e estilo ficam em `AgentProfile` intercambiável.
- Não reiniciar o produto inteiro a cada nova ideia, nem trazer grandes blocos do Projeto AI sem adapta-los. O caminho é evolução modular e testável sobre o núcleo atual.
- Não prometer autonomia total, controle residencial/IoT, navegação irrestrita ou "app inteiro funcionando" sem validação atual, política de acesso e testes de ponta a ponta.

## Regras de continuidade

- Não sobrescrever alterações locais existentes sem identificar o dono e o escopo.
- `npm run build` gera só `frontend/dist` e pode rodar no checkout principal. `npm run build:mobile` substitui os assets Android rastreados; rodar só quando a intenção for atualizar o APK.
- Não dizer que um recurso funciona apenas porque foi implementado em um chat passado; confirmar em código e teste atual.
- Não transformar o dashboard em um produto dependente da identidade "Jarvis". A usuária planeja trocar a personalidade.
- Quando houver conflito entre esta nota e uma conversa nova, a conversa nova vence.
