# Item 3: evidências das correções de alcance na UI nova

Primeira iteração. `review-item3.json` não existia, então o item foi implementado do zero. Branch `main`, sem worktree.

**Commit do item:** `36bbb35` (`fix: corrigir alcance da UI e permitir remover dispositivo da ponte pelo PC`).

## O que mudou

| Pedido | Feito | Arquivos |
|---|---|---|
| Métricas & Logs | O botão em Configurações navegava para `'Analytics'`, ID que não existe em `navigation.ts`. Agora navega para `'Análises'`, o ID da visão rotulada "Métricas". | `frontend/src/pages/SettingsPage.tsx:212` |
| Quest Log morto | Removidos `frontend/src/hooks/useQuestLog.ts`, o `lazy` do `QuestLogPanel`, o `useQuestLog()` e o bloco que renderizava o painel em `App.tsx`. Ver a decisão abaixo. | `frontend/src/hooks/useQuestLog.ts` (apagado), `frontend/src/App.tsx` |
| Tool Forge | Não mexi. O `lazy` em `App.tsx` e `isToolForgeOpen` continuam como estavam, e nada abre o modal. | nenhum |
| Remover dispositivo | Botão "Remover" em cada dispositivo de Automações → Dispositivos conectados. Ele abre um `<dialog className="ws-confirm-dialog">`, o mesmo padrão do diálogo de excluir conversa do `ChatPage`, sem `window.confirm`. O erro da ponte aparece num `role="alert"` dentro do cartão. Para isso foi preciso mudar a política da ponte no backend, decisão do orquestrador (opção C). | `frontend/src/pages/AutomationsPage.tsx`, `frontend/src/App.tsx`, `app/services/device_bridge.py`, `app/ui/panel/server.py` |
| Paleta | Entradas "Abrir conversa por voz" (`setLiveCallOpen(true)`, o mesmo do botão `AudioLines` do `WorkspaceComposer`) e "Ditado" (`toggleVoiceInput`, o mesmo do botão de microfone). O subtítulo do Ditado muda para "Parar a gravação e transcrever para o chat" enquanto grava. O Ditado também leva para Conversas, onde o texto transcrito aparece. | `frontend/src/components/CommandPalette.tsx`, `frontend/src/App.tsx` |
| Parar pedido | Pulado. Ver a decisão abaixo. | nenhum |

## Mudança de política da ponte (opção C, decidida pelo orquestrador)

**Antes.** `remove_device` só removia com a credencial do próprio dispositivo e devolvia `False` sem mensagem. O painel só guarda a credencial do "Jarvis Desktop" (`localStorage['jarvis-bridge-desktop-token']`). A da lâmpada de teste é descartada no pareamento. Com isso, nenhum outro dispositivo podia ser removido pelo PC.

**Agora.**

- **Sem a credencial do próprio dispositivo**, a remoção só é aceita quando o principal do control plane é `loopback`: `server.py` passa `local_owner=principal.mode == "loopback"`. É a mesma condição que libera o código de pareamento (`server.py:932`). Para chegar a esse principal, o pedido precisa passar por `ControlPlanePolicy.authorize`: Host confiável, Origin ausente ou confiável, cliente `127.0.0.1` ou `::1` e modo de acesso `loopback`.
- **Pela rede, nada muda.** No modo `lan`, todo pedido exige o token de controle (401 sem ele) e vira o principal `lan`, mesmo vindo de `127.0.0.1`. Com o token, a remoção ainda exige a credencial do próprio dispositivo. A credencial de outro dispositivo, como a do desktop, não serve. Assim o caminho relaxado não fica mais fraco que o do pareamento: o pareamento também não é exibido no modo `lan`.
- **O caminho relaxado só revoga.** `local_owner` é lido apenas por `remove_device`. Comandos continuam exigindo credencial: o teste HTTP confirma que um `command` vindo do loopback sem credencial recebe 400.
- **Recusa com mensagem.** `remove_device` passou a devolver um dict. As respostas são `{"ok": true, "removed": id}` em caso de sucesso, ou `{"ok": false, "error": ...}` com "device_id é obrigatório.", "Dispositivo não encontrado na ponte." ou "A ponte recusou a remoção. Sem a credencial do próprio dispositivo, só o painel local do PC, no modo de acesso loopback, pode removê-lo.". O servidor continua respondendo 400 na recusa.
- **Auditoria.** O evento `device.removed` agora registra `{"revoked_by": "device"}` ou `{"revoked_by": "local_owner"}`. Antes o payload era `{}`.
- **Remover o "Jarvis Desktop".** O painel envia a credencial guardada e, se a remoção der certo, apaga `jarvis-bridge-desktop-token` do `localStorage`. Para os outros dispositivos, o painel não envia credencial nenhuma.

**Diferença em relação ao texto da decisão.** O orquestrador pediu um teste em que "loopback + token" removesse outro dispositivo. No modo `loopback` não existe token de controle: `JARVIS_CONTROL_TOKEN` só é exigido e verificado no modo `lan` (`app/config.py:58-62`, `control_plane.py:86-93`). No modo `lan`, o principal é sempre `lan`, inclusive em `127.0.0.1`, e o pareamento também fica bloqueado. Segui a restrição (1) ao pé da letra, com a mesma proteção do pareamento. O teste de sucesso roda então no modo `loopback`, com Host e Origin confiáveis. O token aparece nos testes do modo `lan`: sem ele, 401; com ele, a remoção ainda exige a credencial do próprio dispositivo. Para remover pelo PC no modo `lan`, seria preciso uma regra nova, mais permissiva que a do pareamento, e não a criei.

## Decisões sobre Quest Log e Parar pedido

- **Quest Log.** `startQuest`, `addStep`, `updateStepStatus` e `completeQuest` não eram chamados em lugar nenhum. `openQuestLog` e `toggleQuestLog` também não, então `questLog.isOpen` nunca ficava `true` e o `QuestLogPanel` nunca era montado. Nada alcançável dependia do hook, e por isso ele foi removido. Ficaram sem uso `frontend/src/components/QuestLogPanel.tsx` e os tipos `ProcessQuest`, `ProcessStepItem` e `ProcessStepStatus` em `types.ts`, que só ele usa. Ficaram fora do pedido, que citava só o hook e as referências em `App.tsx`. Podem ser removidos num item futuro.
- **Parar pedido: pulado e registrado como pendente.** O frontend só conhece o `run_id` quando o turno termina: em `useChat.ts:314`, pela resposta REST (`data.context.run_id`), e em `useChat.ts:495`, pelo evento WebSocket `complete`. Durante o pedido, não há id de run ativo no estado. A Central lista runs, mas só dentro de `RunHistory`, e não expõe um "run ativo" para o `App`. Oferecer o comando exigiria fiação nova, como o backend enviar o `run_id` no início do turno ou o `App` consultar `/api/runs?status=running`. Pendente, junto com o item 4 de `PENDENCIAS_DO_PAINEL.md` ("permitir parar um pedido em andamento pelo próprio chat").

## Pendências para o passo de documentação

- Tool Forge: o modal continua no código e nada o abre. Ligá-lo exige recibo de aprovação para instalar código (item 3 de `PENDENCIAS_DO_PAINEL.md`).
- Parar pedido pela paleta ou pelo chat: falta o id do run ativo no frontend (ver acima).
- `docs/PENDENCIAS_DO_PAINEL.md`, linha do item 4, ainda pede para "reconciliar o Quest Log com os eventos do servidor" e linka `../frontend/src/hooks/useQuestLog.ts`, que este commit apagou. O link quebrou e essa parte da pendência deixou de existir. `docs/PROJECT_CONTINUITY.md` ainda descreve o Quest Log como "uma visualização legada". Não editei os docs neste item.
- A remoção de dispositivos pelo PC não está disponível no modo `lan` (ver a diferença acima).

## Comandos e resultados

Todos rodados depois das edições finais. Python: `C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe`, a partir da raiz. Node: o `node` do PATH, a partir de `frontend/`.

| Verificação | Comando | Resultado |
|---|---|---|
| TypeScript | `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` | exit 0, sem erros |
| Python da ponte e do control plane | `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_device_bridge.py tests/test_control_plane_security.py` | **13 passaram**, 0 falharam, 1 aviso (depreciação do OpenTelemetry, que já existia), 7,04 s. Log: `%TEMP%\item3-pytest.log` |
| Smoke do workspace | `PLAYWRIGHT_MODULE=<...>\playwright\driver\package PANEL_TEST_URL=http://127.0.0.1:5174 PANEL_TEST_OUTPUT=<screenshots>\item3 node tests/workspace.smoke.cjs` | exit 0. Todos os blocos `PASS`, inclusive os três novos. Log: `%TEMP%\item3-workspace-smoke.log` |
| Smoke dos pedidos | `PLAYWRIGHT_MODULE=<...> PANEL_TEST_URL=http://127.0.0.1:5174 node tests/runs.smoke.cjs` | exit 0, `PASS: request grouping, cancel 500/retry/pending/terminal, ...`. Log: `%TEMP%\item3-runs-smoke.log` |
| Grafo (`graphify update .`) | não rodado | No item 2, passou de 5 minutos sem saída. `graphify-out/` é ignorado pelo git. O grafo local pode estar desatualizado. |

### Servidor Vite usado nos testes

A porta **5173 já estava ocupada** pelo PID 12708 (`node ... vite.js --host 127.0.0.1 --port 5173 --strictPort`, iniciado às 12:08 pelo runtime do Codex). Não iniciei nem parei esse processo, porque é a prévia que a usuária usa. Subi um servidor só para os testes, com `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort` (PID 9732, Vite 7.3.6, pronto em 660 ms), e passei `PANEL_TEST_URL=http://127.0.0.1:5174` às duas suítes. Depois dos testes, rodei `taskkill /PID 9732 /T /F`, que encerrou também os filhos 18932 e 10072. Conferi depois que a 5174 não tinha mais listener e que a 5173 seguia com o PID 12708. O backend real (`python -m app.main`) não foi iniciado.

## Cobertura nova nos testes

`frontend/tests/workspace.smoke.cjs`, com todas as APIs simuladas:

- **Mocks novos.** `/api/bridge` com GET devolvendo dois dispositivos ("Jarvis Desktop" e "Lâmpada de teste"), POST `pairing_code` e POST `remove`, que registra o corpo e pode recusar com 400 e mensagem. `/api/voice/stt` devolve um texto fixo. O microfone é simulado com `addInitScript`: `getUserMedia` devolve uma trilha silenciosa de `AudioContext.createMediaStreamDestination()`, e nenhum dispositivo real de áudio é aberto.
- **Métricas.** Configurações → "📊 Métricas & Logs" → a barra superior mostra "Métricas", aparece "LOGS AO VIVO" e não aparece "MIGRAÇÃO GRADUAL".
- **Paleta, voz.** Busca "conversa por voz" (um único resultado) e Enter. O diálogo "Chamada com Jarvis" mostra "Ouvindo continuamente", o que prova que a captura começou. "Encerrar" fecha o diálogo.
- **Paleta, ditado.** "Ditado" e Enter: o botão do composer vira "Parar gravação" com `aria-pressed="true"`. Na paleta de novo, o subtítulo passa a "Parar a gravação e transcrever para o chat". Enter outra vez: uma chamada a `/api/voice/stt`, e o campo de mensagem recebe "Texto ditado pela paleta".
- **Remoção.** "Manter dispositivo" não chama a API. Com a ponte recusando: o alerta "A ponte recusou a remoção…" aparece, a lâmpada continua e o pedido sai sem `device_token`. Em 360 px: o alerta e o diálogo cabem sem rolagem horizontal. Com a ponte aceitando: a lâmpada some e o alerta é limpo. Remover o "Jarvis Desktop" envia `device_token` igual à credencial guardada e apaga a chave do `localStorage`. Por fim, o cartão mostra "Nenhum cliente conectado.". `assert.deepEqual(errors, [])` continua no fim, sem erros JavaScript de página.

Testes Python:

- `tests/test_device_bridge.py`: o teste existente passou a checar `["ok"]`. `test_removal_without_own_credential_requires_local_owner` cobre `device_id` vazio, dispositivo inexistente, recusa com a credencial de outro dispositivo, remoção com `local_owner=True` e o evento `revoked_by: local_owner`.
- `tests/test_control_plane_security.py`, por HTTP real em `127.0.0.1:<porta livre>`, com `DeviceBridgeService` apontado para `tmp_path` e sem dispositivo real:
  - `test_local_owner_removes_another_device_and_gains_nothing_else`: no modo loopback com Origin confiável, remove "phone" sem a credencial dele, e a credencial do phone deixa de valer. Um `command` sem credencial recebe 400. Remover de novo devolve "não encontrado".
  - `test_loopback_removal_with_foreign_origin_is_refused`: com `Origin: https://evil.example`, 403 "Origem não confiável." e o dispositivo continua.
  - `test_network_removal_still_requires_control_token_and_own_credential`: no modo `lan`, sem token, 401. Com token e sem credencial, 400 com a mensagem clara. Com token e a credencial do desktop, 400. Com token e a credencial do próprio phone, 200.

## Capturas

Pasta: `c:/Users/maria/Desktop/Jarvis/.agents/tasks/desktop-batch1/screenshots/item3/`. Usei uma subpasta para não sobrescrever as capturas do item 1, citadas em `item1-evidence.md`. Todas vêm de dados simulados.

Novas deste item:

- `desktop-metrics-from-settings.png` (1536 px): Métricas aberta pelo botão de Configurações.
- `desktop-palette-voice.png` (1536 px): a paleta com "Abrir conversa por voz".
- `desktop-device-remove-error.png` (1536 px): os botões Remover nos dois dispositivos e o alerta da recusa.
- `mobile-device-remove-error-360.png` (360 px): o alerta da recusa sem rolagem horizontal.
- `mobile-device-remove-confirm-360.png` (360 px): o diálogo "Remover Lâmpada de teste?".

Regeneradas pela mesma execução, como regressão: `desktop-chat.png`, `desktop-executions.png`, `mobile-360.png`, `mobile-390.png`, `mobile-timeline-360.png`. As capturas de `runs.smoke.cjs` (`desktop-request-cancelling.png`, `mobile-request-360.png`) ficam no caminho fixo do teste, `%TEMP%\agent-workspace-review`.

## Efeito visível

- Configurações → "Métricas & Logs" abre Métricas, em vez de cair no aviso de migração.
- A paleta (Ctrl K) tem "Abrir conversa por voz" e "Ditado".
- Em Automações, cada dispositivo tem "Remover", com confirmação. Pelo painel no PC, a remoção funciona para qualquer dispositivo. Se a ponte recusar, a mensagem aparece no cartão.
- Nada muda no Quest Log, porque ele nunca aparecia.

## Observações fora do escopo

- **Código de pareamento some após 5 s.** O polling de `/api/bridge` em `App.tsx` substitui o estado inteiro com o GET, e o GET não traz `pairing_code`, o que é correto: só o POST `pairing_code` o devolve. Por isso o código obtido na abertura vira "—" no primeiro refresh, como se vê na captura desktop. Isso já acontecia antes deste item e não foi alterado.
- **Título e subtítulo colados na paleta.** No servidor de desenvolvimento, o título e o subtítulo de cada item da paleta aparecem colados ("Abrir conversa por vozFalar com…"). Isso vem do CSS que a paleta já tinha e não foi alterado.

## Não testado

- O backend real, o microfone real, a ligação com STT e TTS reais, e o modo `lan` com um celular de verdade. Tudo foi exercitado com mocks, dados temporários e o servidor HTTP de teste.
- `npm run build` e o pacote `frontend/dist` não foram gerados neste item.

## Observações

- Os arquivos de `.agents/tasks/desktop-batch1/`, incluindo este, continuam não rastreados, como nos itens 1 e 2.
- `docs/DECISOES_E_IDEIAS.md` continua não rastreado e não foi alterado.
