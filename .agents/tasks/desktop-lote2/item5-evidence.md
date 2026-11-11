# Item 5: sistema de janelas dentro do app + módulo Finanças + ferramenta `open_window`

## O que mudou
### Frontend
- `frontend/src/windows/registry.ts` (novo): registro de janelas (id, título, ícone, tamanho, componente `lazy`, `parseParams` estrito). Só existe a janela `finance` por enquanto; o item 6 acrescenta `controls`. Também traz `extractWindowRequest`, que lê o pedido do agente em `context.tool_results.open_window.data.ui_window`.
- `frontend/src/windows/WindowManager.tsx` (novo): `WindowProvider` (contexto: abrir, fechar, focar, atualizar) e `WindowHost` (montado no `AppShell`). Várias janelas, z-order por foco (clique), arrastar pela barra de título, redimensionar (bordas direita/baixo e canto), maximizar/restaurar (botão ou duplo clique), fechar, Esc fecha a focada. Em largura <= 640px a janela vira folha em tela cheia, sem arrastar nem redimensionar. Reabrir uma janela já aberta só a foca; reabrir com parâmetros remonta o conteúdo com os novos parâmetros.
- `frontend/src/windows/FinanceWindow.tsx` (novo): formulário (valor, tipo, categoria, descrição, data padrão hoje), lista com filtros (período, tipo, categoria), totais vindos da API, editar, excluir. Rascunho em `localStorage` (`jarvis-finance-draft`) a cada alteração; só é apagado depois que o servidor confirma a gravação. Falha ao salvar mantém o rascunho, mostra o erro e o botão vira "Tentar novamente" (o mesmo id é reenviado, então não duplica). Reabrir a janela restaura o rascunho ("Rascunho restaurado"). Indicador discreto "Modo manual · IA indisponível" quando o componente `providers` de `useOperationalSnapshot` (recebido do `AppShell`, sem novo polling) não está saudável. Nada bloqueia e o registro manual nunca chama o modelo.
- `frontend/src/components/ConfirmDialog.tsx` (novo): diálogo de confirmação do app (não existia um; `window.confirm` não é usado na janela). Foco inicial em Cancelar, Esc e clique fora cancelam.
- `frontend/src/styles/windows.css` (novo, importado em `main.tsx`).
- `frontend/src/main.tsx`: `WindowProvider` envolve o `App`. `AppShell.tsx`: renderiza `<WindowHost>`.
- `frontend/src/commands/registry.ts`: comando `window-finance` (`/financas`, apelido `gastos`, então `/gastos` também funciona; aparece na paleta como "Abrir Finanças", `worksOffline: true`, grupo Life OS).
- `frontend/src/App.tsx`: `openWindow` do registro de comandos usa o gerenciador para ids gerenciados (ids antigos Life OS, Cinema, Câmeras e Conversa por voz continuam nos modais atuais). `useChat({ onOpenWindow })` abre a janela pedida pelo agente.
- `frontend/src/hooks/useChat.ts`: aceita `onOpenWindow` e o dispara quando a resposta traz `open_window` com `ok: true`, tanto no WebSocket (`complete`) quanto no POST `/api/chat`. Nenhum transporte novo.

### Backend
- `app/services/finance.py`: `normalize_entry` (valida tipo, valor finito > 0 e <= 1e9, categoria <= 60, descrição <= 300, data ISO, padrão hoje), `get_transaction`, `query_transactions` (filtros período/tipo/categoria; totais de receita, despesa, saldo, contagem e por categoria calculados em SQL sobre TODO o filtro, não só as linhas retornadas; lista de categorias; `truncated`), `update_transaction`.
- `app/ui/panel/api/routes/system_routes.py` (`/api/finance`): novas ações `list` e `update`; `add`/`create` agora validam (400 com mensagem em pt-BR em vez de gravar valor 0 ou lixo) e aceitam `date`; id do cliente validado por regex (idempotência do reenvio). A resposta padrão (sem ação) continua igual para o painel antigo.
- `app/agent/tools/open_window.py` (novo): `OpenWindowTool`. Aceita só ids do registro (`WINDOWS`) e parâmetros validados por janela (chave desconhecida, tipo errado ou valor fora da faixa viram erro). Devolve `ui_window: {window_id, params}`. O caminho de marcadores usa `command` como id.
- `app/agent/tools/registry.py`: registra a ferramenta, inclui em `GENERAL_TOOL_NAMES` e na lista curta do Groq. `app/agent/tools/catalog.py`: risco `observe`, sem confirmação (passa pelo Action Kernel e aparece na Central).
- `app/agent/orchestrator.py`: no caminho de marcadores, expõe `context.tool_results.open_window` com o mesmo formato do caminho nativo (que já expunha `tool_results`).

## Testes
- `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_open_window.py tests/test_habits_tasks_finance.py`: 33 passaram.
- Rodada ampliada (`test_habits_tasks_finance`, `test_open_window`, `test_tools_smoke`, `test_orchestrator`, `test_orchestrator_action_results`, `test_native_action_boundary`, `test_chat`, `test_evolute_sync`): 47 passaram antes de acrescentar os 3 testes de orquestrador; os 3 também passam.
- Novos em `tests/test_habits_tasks_finance.py` (banco temporário via `monkeypatch` de `app.services.habits.DB_PATH`, não tocam `data/lifestyle.db`): lista/filtros/totais (período, tipo, categoria, limite com totais completos), ciclo adicionar/reenviar mesmo id/editar/404/excluir, data padrão hoje e entradas inválidas (400).
- Novos em `tests/test_open_window.py`: id conhecido ok, desconhecido erro, parâmetros inválidos rejeitados, ferramenta registrada com `enum` do registro, execução pelo Action Kernel com risco `observe` e status `succeeded` (e `failed` para id desconhecido), pedido de janela chegando ao contexto nos caminhos nativo e de marcadores, id desconhecido nunca gera `ui_window`.
- `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` (frontend): sem erros.
- Sem smoke de navegador nem screenshots (ficam para a etapa final).

## Decisões (opção conservadora)
- Parâmetros do `open_window` para `finance`: `period` escolhe o período da lista; `type`, `category`, `amount`, `description`, `date` só pré-preenchem o formulário. O agente nunca grava: o lançamento só existe depois que a usuária clica em salvar.
- Se já existe rascunho salvo, ele vence o pré-preenchimento do agente (nada digitado se perde). Editar um lançamento com rascunho sujo pede confirmação para substituir.
- Id existente em `add` substitui o lançamento (comportamento já existente do `INSERT OR REPLACE`), usado de propósito para o reenvio idempotente.
- "Modo manual" aparece só quando o snapshot carregou e `providers` não está `healthy`; sem conexão com a central o indicador não aparece.
- `open_window` com ids que não estão nos dois registros (Python e TS) falha; os dois precisam ser atualizados juntos ao criar janelas (item 6).

## Pendências / não verificado
- Sincronização: `finance_transactions` já está no snapshot do item 3 (`app/storage/backend_sync.py`, vence o `timestamp` mais recente; `update_transaction` renova o `timestamp`). Exclusão de lançamento não tem marcador de remoção no merge, então um lançamento excluído num dispositivo pode voltar de outro na próxima sincronização. Não corrigido aqui (exigiria lápide/tombstone no schema); fica como pendência.
- `/api/chat/stream` (usado só pela conversa por voz em `useMediaAssistant`) não dispara `onOpenWindow`.
- `useDirectChat` (APK/standalone) não tem ferramentas, então não abre janelas pelo agente.
- Comportamento visual (arrastar, redimensionar, folha em 360 px, Esc, restauração do rascunho) não foi exercitado em navegador; só tipos e testes Python.
- Os testes antigos de `test_habits_tasks_finance.py` (`test_finance_service_lifecycle`, etc.) seguem escrevendo em `data/lifestyle.db` real e limpam depois; não alterei.
