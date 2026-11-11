# Lote 4: relatório para você testar o app

Branch `main`, sem push. Escopo encurtado a seu pedido depois de O1/O2. Evidências por passo nesta pasta (`step1-evidence.md` a `step3-evidence.md`).

## Commits
| Commit | Propósito |
|---|---|
| `f70595a` | C10 + AQ1: controles do PC, navegador automatizado, script e terminal passam pelo Action Kernel; voz grava a origem `voice` |
| `4a40270` | C6: Runs com campo origem; voz, Swarm, Racing e memória em segundo plano aparecem na Central |
| `890c8cf` | O1 + O2: Integrações com estado real; registro do provedor e modelo que responderam depois de uma troca |
| `e1bb1a7` | Docs: continuidade, pendências, decisões, contexto e plano 017 |

## O que testar à mão
Abra o app com `python -m app.main`.
1. **Integrações** (menu Integrações ou `/integracoes`): os cartões vêm em três grupos (IA e voz, Dispositivos, Integrações e aplicativos). O que não está instalado ou configurado (Composio, Kasa, MCP, Telegram, WhatsApp) deve aparecer como "Desligado", com o motivo. "Dispositivos" com nenhum aparelho pareado mostra "Desligado", nunca "Funcionando". Depois de uma conversa, o cartão Conversa deve mostrar "Funcionando", o horário do último sucesso e quem respondeu (provedor · modelo · ms). Se o provedor principal falhar (por exemplo, por limite 429), aparece "Última troca" com o motivo.
2. **Voz na Central:** faça um pedido pela ligação de voz que use uma ferramenta (por exemplo, "abre o bloco de notas"). Em Execuções, a linha do pedido mostra "Voz · data", e o detalhe mostra "Origem: Voz".
3. **Rotas diretas pedindo aprovação:** use a janela Controles do PC; a ação aparece na Central com a origem "Janela". Um script confirmado no chat aparece como "Chat", com a confirmação pelo recibo. `/api/browser/run` (sem botão no app) agora fica aguardando aprovação na Central.
4. **Etapas internas:** no modo Racing ou no especialista (Swarm), o detalhe do pedido lista "Etapa interna" para cada provedor ou especialista. O salvamento da conversa na memória aparece como "Segundo plano".

## Testes e build
- Python: **243 passed** em 19 arquivos: `test_action_gateway`, `test_capability_health`, `test_control_plane_security`, `test_conversation_runtime`, `test_run_origins` (novos ou alterados no lote), mais `test_runs`, `test_action_history`, `test_mission_control`, `test_orchestrator`, `test_chat`, `test_llm_racing`, `test_god_mode_components`, `test_provider_routes`, `test_llm_provider`, `test_turn_tool_allowlist`, `test_orchestrator_action_results`, `test_action_proposals`, `test_settings_api`, `test_pc_controls`. Houve 3 avisos de depreciação de dependências.
- `tsc --noEmit`: sem erros.
- `workspace.smoke.cjs` contra o Vite em 127.0.0.1:5173: **PASS** (11 blocos), na primeira execução. `runs.smoke.cjs` e `chat-cancel.smoke.cjs` não rodaram, como você pediu.
- `npm run build` (só web): passou, com o aviso de chunks grandes que já existia. `mobile_app/` não mudou.
- O tempo-limite do cliente HTTP em `test_control_plane_security.py` subiu de 3 s para 15 s. Esses testes estouravam 3 s também antes deste lote, porque a máquina estava lenta. Nenhuma asserção mudou.

## Pontos quentes para revisar primeiro
1. `app/core/capability_health.py` (`track_model_call`): decide quem respondeu e se houve troca. Ele olha a exceção em tratamento (`sys.exc_info`) quando a segunda tentativa começa. Vale conferir com uma falha real de provedor.
2. `app/agent/action_gateway.py` e as rotas em `server.py` (`/api/script/run`, `/api/hacker/execute`, `/api/browser/run`): o recibo vale como aprovação.
3. `app/agent/run_tracking.py` (`in_background`, `background_run`): eventos gravados depois que o pedido terminou.
4. `app/ui/panel/api/capabilities.py`: os motivos de "desligado" vêm das listas de `registry.py`, não do registro montado de verdade.

## Pendente (adiado por você)
O3, O4, O5, AQ6, AQ8, S3, S4 e AQ7. Uma versão parcial de O3, O4 e O5, sem testes, está guardada em `git stash` com a mensagem "lote4 grupo4 parcial (O3 O4 O5)". Ela inclui os filtros da Central, a latência no cabeçalho e os erros das telas antigas.

## O que NÃO foi verificado
Backend real com seus dados, efeitos reais no Windows, provedores reais e trocas reais (429), bibliotecas opcionais (Kasa, Telegram), npx/mudslide, Spotify real, servidores MCP, ponte com aparelhos reais, Supabase e APK.

## Lembrete
A chave da Fish Audio exposta em export antigo continua precisando ser trocada no provedor (V5).
