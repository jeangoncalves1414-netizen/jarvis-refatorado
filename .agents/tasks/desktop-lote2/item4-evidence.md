# Item 4: registro único de comandos, paleta e menu `/` sem IA

## O que mudou
- `frontend/src/commands/registry.ts` (novo): registro único. Cada comando tem `id` estável, rótulo, título da paleta, descrição, apelidos, palavra do `/`, grupo, ação tipada (`navigate`, `open-window`, `set-mode`, `backend`, `local`), `worksOffline` e ícone. Também traz `searchSlashCommands`, `parseSlashInput`, `searchCommands` (paleta, sem diferenciar acentos), `describeCommand` (texto que depende do estado) e `runCommand(command, handlers, args)`.
- Gatilhos futuros (frase de voz, palmas, agenda): devem guardar só o `id` e chamar `runCommand(getCommand(id), handlers)`. Nada disso foi construído.
- `frontend/src/components/CommandPalette.tsx`: lista montada de `commands`. Props reduzidas a `isOpen`, `onClose`, `handlers`, `recording`. Todas as entradas anteriores continuam, com os mesmos títulos (incluindo "Abrir conversa por voz" e "Ditado"). Entradas novas: Modo Pesquisa, Modo Planejamento, Perguntar o clima.
- `frontend/src/components/WorkspaceComposer.tsx`: menu `/` pequeno, só aparece quando o texto é `/` + palavra sem espaço; busca, setas, Enter/Tab, Esc e mouse. Comando reconhecido (inclusive `/pesquisa tema`) roda localmente e o compositor é limpo. `/xyz` desconhecido mostra "Comando desconhecido: /xyz..." na legenda e nada é enviado. O envio por Enter e pelo botão passa pelo mesmo caminho.
- `frontend/src/App.tsx`: objeto único `commandHandlers`, usado pela paleta e pelo compositor (via `ChatPage`). `frontend/src/pages/ChatPage.tsx` só repassa a prop. CSS do menu em `frontend/src/styles/workspace.css`.
- `navigation.ts` não mudou (AppShell e persistência de tela continuam usando).

## Comandos antigos do commit 90a759a
| Antigo | Agora |
| --- | --- |
| `/pesquisa` | troca para o modo Pesquisa; texto após a palavra vai ao compositor, sem enviar |
| `/planejar` | idem, modo Planejamento |
| `/cinema` | abre o Cinema |
| `/visao` | analisa a tela (Visão) |
| `/estudos` | abre a página Estudos |
| `/clima [cidade]` | escreve "Qual o clima em <cidade>?" no compositor, sem enviar |

Outros: `/inicio /conversas /execucoes /automacoes /conhecimento /integracoes /lifeos /calendario /painel /metricas /perfis /config /foco /agua /nova /voz /ditado /briefing /backup /sons /cameras`. `/gastos`, `/financas` e `/controles` ficam para os itens 5 e 6 (basta novas entradas `open-window`).

## Decisões (opção conservadora)
- `/clima` não tem equivalente local, então só prepara a pergunta; o envio é decisão da usuária.
- `/pesquisa` e `/planejar` com texto não enviam: o texto fica no compositor com o modo trocado.
- `worksOffline` significa "o comando em si roda sem modelo/provedor". É `false` para conversa por voz, ditado, briefing e visão.
- Todo texto que começa com `/` é tratado como comando (como pedido no brief). Uma mensagem que precise começar com `/` (ex.: um caminho) não pode ser enviada assim. Pendência: criar um escape (ex. `//`) se a usuária precisar.
- Janelas existentes (Life OS, Cinema, Câmeras, Conversa por voz) entram como `open-window` com ids (`life-os`, `cinema`, `cameras`, `live-call`); o item 5 troca o `openWindow` do App pelo gerenciador de janelas.

## Verificação
- `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` (frontend): sem erros.
- `frontend/tests/workspace.smoke.cjs` ampliado e checado com `node --check`; NÃO executado (fica para a etapa final). Cobre: paleta lista todas as entradas (>= 28, títulos antigos), busca sem acento, `/` abre o menu, texto comum não abre, setas/Esc, filtro + Enter executa local, `/planejar tema`, clique do mouse, `/clima Recife`, `/execucoes`, `/xyz` mostra dica e nada vai à API de chat (contador `chatCalls`).
- Nenhum teste Python tocado nesta etapa.
