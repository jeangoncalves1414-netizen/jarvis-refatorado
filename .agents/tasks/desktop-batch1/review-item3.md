# Alcance da UI nova: Métricas, voz na paleta e remoção de dispositivos da ponte pelo PC

O commit `36bbb35` corrige pontos do painel novo que não eram alcançáveis ou estavam ligados errado. O botão "📊 Métricas & Logs" de Configurações passa a navegar para `'Análises'`, o ID real da visão Métricas em `navigation.ts:15`; antes caía no aviso de migração. A fiação morta do Quest Log sai de `App.tsx`, junto com `useQuestLog.ts`. A paleta (Ctrl K) ganha "Abrir conversa por voz" e "Ditado", ligados a `setLiveCallOpen(true)` e `toggleVoiceInput`, os mesmos handlers do composer. Em Automações, cada dispositivo ganha "Remover", com um `<dialog className="ws-confirm-dialog">` próprio e o erro num `role="alert"`. Para isso a ponte passa a aceitar a revogação sem a credencial do próprio dispositivo quando o principal do control plane é `loopback`, a mesma regra que protege o código de pareamento. Tool Forge ficou intocado, e "Parar pedido" foi pulado porque o frontend não tem o id do run ativo durante o pedido.

Watch for: remover o "Jarvis Desktop" apaga `jarvis-bridge-desktop-token`, e a partir daí Ligar e Desligar falham até a usuária clicar em "Adicionar lâmpada de teste", a única ação que registra o controle de novo. O diálogo não avisa disso (confirmed, non-blocking). No modo `lan`, e portanto também no app Android quando receber esta interface, o botão Remover aparece em todos os dispositivos, mas a ponte recusa todos os que não mandam a própria credencial. A escolha é declarada e a mensagem de erro explica (confirmed, non-blocking). `docs/PENDENCIAS_DO_PAINEL.md` linka o hook apagado (confirmed, adiado para o passo de documentação).

**Verdict**: APPROVED

## High-level view

O conserto de Métricas é a troca de um ID. `resolveScreen` já convertia um `'Analytics'` salvo, mas `onNavigate` recebia o ID cru. No commit pai, o Quest Log só tinha referências dentro do próprio hook (`git grep` em `36bbb35^`), sem efeito, fetch nem socket, então `isOpen` nunca ficava `true` e nada alcançável dependia dele. `QuestLogPanel.tsx` e os tipos `ProcessQuest`, `ProcessStepItem` e `ProcessStepStatus` ficam órfãos, como a evidência declara.

As entradas novas da paleta chamam os mesmos handlers que o composer recebe em `App.tsx:833-834`, e o Ditado leva para Conversas, onde o texto transcrito aparece. Os textos novos falam em "o agente". "Chamada com Jarvis" e o ID `jarvis-desktop` já existiam, então o commit não acopla nada novo à persona.

A política de revogação deriva `local_owner` do principal autenticado, e não de algo que o cliente envia. O caminho só revoga: `command` continua exigindo credencial, e o evento `device.removed` registra `revoked_by`. Qualquer processo local que chame sem Origin passa a revogar qualquer dispositivo. É a mesma classe de acesso que já lê o código de pareamento e registra dispositivos, então a diferença é pequena.

No modo `lan`, todo pedido vira o principal `lan`, mesmo vindo de `127.0.0.1`, e o PC não remove outros dispositivos. O orquestrador pedia um teste com "loopback + token", mas essa combinação não existe, porque o token só é verificado no modo `lan` (`control_plane.py:87-94`). O implementador manteve a regra do pareamento em vez de criar uma mais permissiva, e registrou a escolha como pendência.

Na UI, a remoção usa diálogo próprio, bloqueia Esc enquanto remove e mostra no cartão o erro do servidor ou da rede. O problema está num efeito colateral: remover o "Jarvis Desktop" invalida a credencial que todos os comandos do PC usam.

"Parar pedido" ficou de fora porque o id não existe durante o pedido. `useChat.ts` só grava `finalRunIdRef` quando o turno termina, pela resposta REST (linhas 314-319) ou pelo evento `complete` (linha 495).

Os testes Python cobrem a regra nova por unidade e por HTTP real: sucesso em loopback, Origin estranha com 403 e, no modo `lan`, 401 sem token, 400 sem credencial, 400 com a credencial do desktop e 200 com a do próprio dispositivo. O smoke cobre Métricas, voz e ditado pela paleta com microfone e STT simulados, e a remoção com recusa, 360 px e limpeza da credencial. Os logs em `%TEMP%` são posteriores à última edição de cada arquivo. O `tsc --noEmit`, rodado aqui como spot-check, terminou com exit 0. Os dez arquivos do commit pertencem ao item, e os tokens dos testes são valores fixos de teste. Não testado: o ramo de falha de rede de `removeBridgeDevice` (`TypeError` convertido em "Sem conexão com a ponte..."), a UI num painel servido em `lan`, Ligar e Desligar depois de remover o "Jarvis Desktop", o backend real com microfone, STT e TTS reais, e `npm run build`. Os bundles em `app/ui/panel/static/assets` e `mobile_app` ainda carregam `QuestLogPanel-*.js` até a próxima geração.

<details>
<summary>Issues (7)</summary>

1. **Remover o controle local corta os comandos do PC** (non-blocking, confirmed): depois de remover o "Jarvis Desktop", Ligar e Desligar mandam `device_token: ''` e recebem 400, e só "Adicionar lâmpada de teste" registra o controle de novo. Dar ao diálogo de `jarvis-desktop` um texto próprio que avise disso, ou esconder "Remover" no controle local.
2. **Credencial velha depois de "não encontrado"** (non-blocking, confirmed): se o desktop já tiver sido removido por outra aba, a remoção falha, a chave fica no `localStorage` e `registerBridgeDemo` não registra o controle de novo. Apagar `jarvis-bridge-desktop-token` também quando a ponte responder "Dispositivo não encontrado" para `jarvis-desktop`.
3. **Remover sempre recusa no modo `lan`** (non-blocking, confirmed, escolha declarada): num painel servido em `lan`, como o app Android reconstruído, o botão aparece em todos os dispositivos e só funciona com a própria credencial. Registrar em `PENDENCIAS_DO_PAINEL.md` junto com a falta de remoção pelo PC no modo `lan`.
4. **Docs apontam para o Quest Log apagado** (non-blocking, confirmed): `docs/PENDENCIAS_DO_PAINEL.md` (item 4) linka `../frontend/src/hooks/useQuestLog.ts`, e `docs/PROJECT_CONTINUITY.md` ainda o descreve como visualização legada. Corrigir no passo de documentação.
5. **`QuestLogPanel.tsx` e tipos órfãos** (non-blocking, confirmed): o componente e `ProcessQuest`, `ProcessStepItem` e `ProcessStepStatus` não têm mais uso. Remover num item futuro.
6. **"Parar pedido" pendente** (non-blocking, confirmed): falta o id do run ativo no frontend. Registrar no item 4 de `PENDENCIAS_DO_PAINEL.md` a fiação necessária: o backend enviar o `run_id` no início do turno ou o `App` consultar `/api/runs?status=running`.
7. **Falha de rede na remoção sem teste** (non-blocking, confirmed): a conversão de `TypeError` em "Sem conexão com a ponte..." não é exercitada. Acrescentar ao smoke um passo com `route.abort()` no POST `remove` que confira o alerta.

</details>

<details>
<summary>Details</summary>

### Regra `local_owner` da ponte e o limite do modo `lan`

A decisão de revogar passa por dois lugares. O servidor calcula `local_owner` a partir do principal que `ControlPlanePolicy.authorize` devolveu, e `DeviceBridgeService.remove_device` decide entre a credencial do próprio dispositivo e esse sinal:

```
POST /api/bridge {action: "remove", device_id, device_token?}
        │
        ▼
ControlPlanePolicy.authorize
  Host não confiável ............ 403
  Origin presente e estranha .... 403
  modo lan: sem token ........... 401
            com token ........... principal "lan"
  modo loopback: cliente remoto . 403
                 cliente local .. principal "loopback"
        │
        ▼
server.py: local_owner = principal.mode == "loopback"
        │
        ▼
remove_device
  device_id vazio ............... 400 "device_id é obrigatório."
  não existe .................... 400 "Dispositivo não encontrado na ponte."
  credencial própria válida ..... remove, revoked_by "device"
  senão, local_owner ............ remove, revoked_by "local_owner"
  senão ......................... 400 "A ponte recusou a remoção..."
```

O caminho bloqueado pelo modo `lan` aparece na UI. O botão "Remover" é renderizado para todos os dispositivos, independentemente do modo. Num painel servido em `lan`, como no app Android depois de reconstruído, todo clique em um dispositivo que não seja o próprio controle termina no alerta "Sem a credencial do próprio dispositivo, só o painel local do PC, no modo de acesso loopback, pode removê-lo." (confirmed pelo código, não exercitado). O comportamento falha fechado e a mensagem diz o que fazer, então não bloqueia. Mesmo assim, precisa entrar nas pendências, junto com a ausência de remoção pelo PC no modo `lan`, que a evidência já lista.

### Remover o "Jarvis Desktop" corta os comandos do PC

`removeBridgeDevice` trata `jarvis-desktop` como caso especial. Ele envia a credencial guardada e, se a ponte aceitar, apaga a chave:

```ts
if (isLocalController) localStorage.removeItem('jarvis-bridge-desktop-token')
```

`sendBridgeCommand` usa essa mesma chave como credencial da origem de todo comando:

```ts
const deviceToken = localStorage.getItem('jarvis-bridge-desktop-token') || ''
... body: JSON.stringify({ action: 'command', target_id: targetId, command, source: 'jarvis-desktop', device_token: deviceToken })
```

Depois de remover o desktop, Ligar e Desligar na lâmpada, ou em qualquer dispositivo real que continue pareado, mandam `device_token: ''` e recebem 400. O teste HTTP confirma que `command` sem credencial é recusado (confirmed). O único caminho que registra o controle de novo é `registerBridgeDemo`. Ele só registra `jarvis-desktop` quando a chave está vazia e, junto, registra outra "Lâmpada de teste". A usuária precisa adivinhar que deve clicar em "Adicionar lâmpada de teste" para voltar a controlar um dispositivo real. O diálogo mostra o mesmo texto para todos ("O dispositivo perde o acesso à ponte..."), sem dizer que remover o controle local desliga os comandos do PC.

Existe um caso menor no mesmo trecho. Se a remoção do desktop falhar com "Dispositivo não encontrado" porque outra aba já o removeu, a chave fica no `localStorage` com uma credencial que não vale mais (confirmed: `removeItem` só roda depois do sucesso). `registerBridgeDemo` vê a chave preenchida e não registra o controle de novo, então os comandos continuam falhando sem caminho de recuperação pela UI.

</details>

<details>
<summary>File map</summary>

- `app/services/device_bridge.py`: `remove_device` com `local_owner`, retorno em dict com mensagem e `revoked_by` no evento.
- `app/ui/panel/server.py`: passa `local_owner=principal.mode == "loopback"` na ação `remove`.
- `frontend/src/App.tsx`: remove o Quest Log, acrescenta `removeBridgeDevice` e passa os handlers de voz para a paleta.
- `frontend/src/components/CommandPalette.tsx`: entradas "Abrir conversa por voz" e "Ditado".
- `frontend/src/hooks/useQuestLog.ts`: apagado.
- `frontend/src/pages/AutomationsPage.tsx`: botão Remover, diálogo de confirmação e alerta de erro.
- `frontend/src/pages/SettingsPage.tsx`: `'Analytics'` → `'Análises'`.
- `frontend/tests/workspace.smoke.cjs`: mocks de `/api/bridge`, STT e microfone, e blocos para Métricas, paleta e remoção.
- `tests/test_device_bridge.py`: retorno em dict e teste de `local_owner`.
- `tests/test_control_plane_security.py`: três testes HTTP de remoção (loopback, Origin estranha e `lan`).

Diff completo: `git -C c:/Users/maria/Desktop/Jarvis show 36bbb35`.

</details>
