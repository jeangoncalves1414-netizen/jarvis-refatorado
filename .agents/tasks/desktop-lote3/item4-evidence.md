# Lote 3, item 4: AQ3 (base) + A6 + A4

## O que foi feito
- **AQ3 (base do contrato de comandos)** em `frontend/src/commands/registry.ts`: `COMMAND_CONTRACT_VERSION`, `COMMAND_ORIGINS` (comando, paleta, voz, rotina, palma, janela, celular, mesmos nomes planejados para a origem dos Runs), `CommandContract` serializável (id, rótulo, slash, apelidos, grupo, ação, `worksOffline`), `toCommandContract`/`getCommandContracts` e `runCommandById(id, handlers, { origin, args })`, o ponto de entrada comum para gatilhos que só conhecem o id. Id desconhecido não executa nada. Nenhum gatilho de voz/rotina/palma foi construído; o único uso novo é o do wake word (A4).
- **A6 (escape `//`)**: `parseSlashInput` devolve `escaped` para texto que começa com `//`; o compositor não abre o menu, não mostra "comando desconhecido", exibe a nota "será enviado como texto, sem a primeira barra" e envia. `App.sendChatMessage` remove só a primeira barra (`unescapeSlash`). `/clima` continua só preparando a pergunta.
- **A4 (palavra de ativação na UI)**:
  - Backend: `GET /api/wake-word` agora usa `_wake_word_status()` em `app/ui/panel/server.py` e devolve também `running` (thread de escuta viva), `active` (ligado e rodando) e `phrase` (frase do perfil). Antes só havia `enabled`/`available`.
  - `useChat` trata o evento WebSocket `wake_word` (callback `onWakeWord`); `App.handleWakeWord` mostra "Ouvi “frase”" por 6 s e abre a conversa por voz via `runCommandById('action-live-call', …, { origin: 'voz' })`, exceto se já houver ligação ou ditado em andamento.
  - Indicador discreto na legenda do compositor ("● Ativação por voz ativa “frase”" ou "Ativação por voz inativa" quando ligado e disponível, mas sem escuta); a descrição do interruptor em Configurações também mostra o estado real. O estado é reconsultado a cada 15 s (desktop).

## Decisões conservadoras (sem pausar)
- Abrir a ligação no wake word segue o critério de aceitação da fase F2 do plano 017 ("wake word abre a ligação e mostra se o detector está ativo"). Se a usuária preferir só o aviso, basta remover a chamada `runCommandById` em `handleWakeWord`.
- O indicador "ativo" depende da thread do detector estar viva, não só do interruptor, para não mostrar "ativo" quando o modelo Vosk não carregou.
- Paleta e menu `/` continuam chamando `runCommand` direto (comportamento inalterado).
- O backend não ganhou cadastro de comandos: a versão do backend (rotinas + gatilhos, A1/A2) fica para depois.

## Verificação
- `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_wake_word_status.py tests/test_agent_profile.py`: 15 passed (3 testes novos: estado ativo/inativo/indisponível, evento com a frase do perfil e limpeza de cliente morto).
- `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`: sem erros.
- Smoke de navegador: ampliado em `frontend/tests/workspace.smoke.cjs` (mock de `/api/wake-word`, indicador, `//` enviado como `/clima de hoje` sem menu), mas NÃO executado nesta etapa; roda no passo final. O evento `wake_word` via WebSocket não é coberto pelo smoke (o teste fecha o socket de propósito para usar o REST).
- Não verificado: detector real (Vosk/microfone), WebSocket real.
