# Lote 3, item 3: C3 (servidor aplica ferramentas por modo e turno)

## O que mudou
- `app/agent/tools/registry.py`: novo `ToolRegistry.allowed_tool_names(mode, provider, user_text)`, que devolve as ferramentas registradas permitidas no modo (tutor ou geral) e no turno (filtro dinâmico do Groq). `get_tool_declarations` passou a usar esse método, então o modelo e o executor partem da mesma lista.
- `app/agent/orchestrator.py`: os dois `ActionExecutor` do turno (function calling nativo e marcadores) recebem `turn_tool_names` em vez de `frozenset(self.registry.tools.keys())`. Ferramenta fora da lista retorna "Ferramenta bloqueada pelo modo atual" e não gera ação.
- Testes: `tests/test_turn_tool_allowlist.py` (novo); os registros simulados de `test_conversation_runtime.py`, `test_open_window.py` e `test_orchestrator_action_results.py` ganharam `allowed_tool_names`.

## Decisões
- Nos provedores por marcadores, a lista é a do modo (o filtro dinâmico só vale para Groq, que usa chamada nativa). Apelidos compactos de marcador (`search`, `vol`, etc.) já não estavam registrados e continuam bloqueados.
- Não alterei o prompt do modelo nem outras rotas (voz, `/api/browser/run`: C10/AQ1) nem o modo por etapas (`react_loop`, que já usa lista própria).
- Plugins não estão em `GENERAL_TOOL_NAMES`, então o modelo nunca os recebeu; agora o executor também não os aceita no chat (consistente com o que o modelo vê).

## Verificação
- pytest: test_turn_tool_allowlist, test_orchestrator_action_results, test_conversation_runtime, test_open_window, test_action_kernel, test_tools_smoke (90 passaram) e test_chat, test_orchestrator, test_native_action_boundary (15 passaram).
- `tsc --noEmit`: sem erros (nenhum arquivo do frontend alterado).
