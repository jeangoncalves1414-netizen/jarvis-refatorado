# Lote 4, passo 1: C10 + AQ1 (tudo que executa ferramenta passa pelo Action Kernel)

Base: `main` em 16e8e59. Um commit: `f70595a` (`feat: rotas diretas e voz pelo Action Kernel (C10, AQ1)`). Sem revisores.

## O que mudou
- **Ponto de entrada único para rotas diretas** (`app/agent/action_gateway.py`, novo): `run_action(tool, args, source=..., user_text=..., run_mode=..., execute=None, context=None, confirmed_by=None)` abre um Run, monta o `ActionExecutor` limitado à ferramenta pedida (metadado do registro, ou de `TOOL_CATALOG` quando a ferramenta não está registrada) e devolve `ActionOutcome` (ação registrada, resultado real, `pending`, `succeeded`, `cancelled`, `crashed`). Risco, aprovação e histórico são os do chat.
- **Controles do PC** (`app/ui/panel/api/controls.py`) passaram a usar o gateway; respostas iguais às de antes.
- **`/api/browser/run`** (`server.py`): deixou de chamar `tool.execute` direto. Vai pelo gateway com origem `api:browser`. `browser_agent` é `high`, então a rota responde **202 `pending`** e só roda depois da aprovação na Central (o callback do broker executa com o mesmo contexto). Não há chamador no frontend.
- **`/api/script/run`** e **`/api/hacker/execute` com recibo**: o subprocesso agora roda dentro do gateway (`script_runner` e `hacker_mode`, ambos `critical`). O recibo de uso único continua sendo a única porta; ele é registrado como a confirmação (`confirmed_by`): a ação entra na Central como `awaiting_confirmation → authorized → running → succeeded/failed`, com o texto "Confirmada no chat com recibo de uso único." / "Aprovada no terminal com recibo de uso único.". O código do script não aparece na proposta. As respostas ganharam o campo `action`.
- **Voz**: a origem do pedido (`chat` ou `voice`) fica em `current_origin` (`app/core/runs.py`). `handle_request`/`handle_request_stream` aceitam `origin`; o `ActionExecutor` prefixa a origem das ações com `voice:` (ex.: `voice:function:<sessão>`). O servidor lê `origin` em `/api/chat`, `/api/chat/stream` e no WebSocket (`request_origin`: só `chat`/`voice`; outro valor vira `chat`). O frontend envia `origin: 'voice'` na ligação ao vivo (`/api/chat/stream`) e em todo `sendText` disparado pelo `useMediaAssistant` (ditado, wake word, fallback). O pipeline de voz do servidor (`streaming_pipeline.py`) chama `handle_request(..., origin="voice")`.
- **Central**: detalhes da ação mostram "Origem" (Voz, Janela do painel, Navegador automatizado, Script confirmado no chat, Terminal, Execução por etapas, Conversa).

## Decisões tomadas sem perguntar
- Script e terminal já tinham aprovação explícita (recibo de uso único). Para não pedir duas vezes, o recibo vale como a aprovação do Kernel; nada roda sem recibo, como antes. Nenhuma regra de segurança foi afrouxada.
- `/api/browser/run` passa a exigir aprovação na Central (risco `high` já declarado no catálogo). É mudança de comportamento só para quem chamava a rota direto; o app não chama.
- Chamada aninhada de `handle_request` sem `origin` herda a origem do pedido externo. Valor de origem desconhecido vira `chat`.
- O3 (filtro por origem) não foi feito: só a origem gravada e exibida no detalhe.

## Fora deste passo (ficam para C6 e seguintes)
- Swarm (`/api/swarm`) e Racing: subagentes só chamam modelo e busca, sem efeito no sistema; histórico deles é C6.
- `/api/automation` (clima), `/api/qr/read`, `/api/vision/capture`, `/api/tool-forge`: não usam ferramentas do registro; não mexidos.
- `app/services/proactive.py` chama `web_search` (leitura) em segundo plano sem Kernel: é "memória/proatividade em segundo plano" (C6).
- Racing executado em outras threads não herda `current_origin` (C6).
- Celular (`useDirectChat`) fala direto com o provedor, sem backend; não há Kernel nesse caminho.

## Testes
- `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_action_gateway.py tests/test_control_plane_security.py tests/test_pc_controls.py tests/test_conversation_runtime.py`: **131 passed**.
- `tests/test_action_history.py tests/test_runs.py tests/test_action_proposals.py tests/test_turn_tool_allowlist.py tests/test_orchestrator.py tests/test_chat.py tests/test_mission_control.py`: **62 passed**.
- Novos: `tests/test_action_gateway.py` (7 testes, 11 casos), voz com origem em `test_conversation_runtime.py` (2), script pelo Kernel e navegador aguardando aprovação em `test_control_plane_security.py` (2), asserções de histórico no teste do terminal. O fixture `panel_http_server` agora isola o histórico em pasta temporária.
- Typecheck do frontend (`tsc --noEmit`): sem erros.

## Não verificado
- Backend real, navegador automatizado real, scripts e terminal reais (subprocess simulado), ligação de voz real e provedores.
