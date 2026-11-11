# Lote 3, item 1: AQ2 e C12

## O que mudou

### AQ2: metadado de risco, alvo e efeito para as ferramentas de módulos pessoais
- `app/agent/tools/catalog.py`: `habit_tool`, `task_tool`, `finance_tool` e `lifeos_tool` entraram em `TOOL_CATALOG` com risco por operação (campo `action`, ou `command` no caminho de marcadores):
  - leitura (`list`, `summary`, `get_water`, `list_habits`, `motivate`): `observe`;
  - gravação (criar, atualizar, marcar/desmarcar, adicionar lançamento, registrar água/treino): `low`;
  - exclusão (`delete` de hábito, tarefa e lançamento): `high`, portanto aguarda aprovação;
  - ação fora do mapa (ou texto livre em `command`): `critical`.
- `app/core/actions.py`: `ToolMetadata` ganhou `target_arguments` e `operation_effects`, com `target_for(arguments)` e `effect_for(arguments)`. As quatro ferramentas declaram alvo (nome/id do hábito, título/id da tarefa, descrição/categoria/id do lançamento, hábito/treino do Life OS) e uma frase de efeito por operação. O alvo passa por `redact`. Não alterei `risk_for` (só extraí a leitura da operação para `_operation`, mesmo comportamento).
- Não liguei alvo/efeito ao texto da aprovação: isso é o item C1 (próximo).

### C12: ruído de leituras `observe` na Central
- `app/storage/action_store.py`: `page()` e `run_page()` ganharam `include_reads` (padrão `False`). Por padrão ficam fora das listas: ações `observe` concluídas com sucesso e originadas de janelas do painel (`source` começa com `panel:`), e pedidos cujas ações são todas desse tipo. Nada é apagado; `run_details` e `details` seguem mostrando tudo, e `include_reads` traz as leituras de volta.
- `app/ui/panel/api/actions.py` e `runs.py`: parâmetro `include_reads=1|true` na consulta.
- `frontend/src/components/ActionHistory.tsx` e `RunHistory.tsx`: botão "Ocultar leituras das janelas" / "Com leituras das janelas" (alterna `include_reads`).

## Arquivos
app/agent/tools/catalog.py, app/core/actions.py, app/storage/action_store.py, app/ui/panel/api/actions.py, app/ui/panel/api/runs.py, frontend/src/components/ActionHistory.tsx, frontend/src/components/RunHistory.tsx, tests/test_tool_catalog.py, tests/test_pc_controls.py.

## Testes
- Novos em `tests/test_tool_catalog.py`: metadado de toda ação declarada das 4 ferramentas (sem `critical`, com efeito), risco por operação, alvo/efeito, e fluxo pelo executor (leitura e gravação rodam, exclusão aguarda aprovação).
- Novos em `tests/test_pc_controls.py`: leitura de brilho fica fora das listas por padrão mas continua registrada; leitura com falha continua visível.
- `pytest tests/test_tool_catalog.py tests/test_pc_controls.py tests/test_runs.py tests/test_action_history.py tests/test_action_kernel.py`: 196 passed.
- `pytest tests/test_tools_smoke.py tests/test_lifeos_integration.py tests/test_habits_tasks_finance.py tests/test_orchestrator_action_results.py tests/test_mission_control.py tests/test_conversation_runtime.py tests/test_open_window.py`: 76 passed.
- `tsc --noEmit`: sem erros.

## Decisões tomadas sem perguntar
- Exclusões das ferramentas pessoais ficaram em `high` (aprovação), por serem irreversíveis hoje (não há desfazer; AQ9 é F5). Criar/marcar/registrar ficaram `low` para "anota que gastei 50" continuar em 1 passo.
- C12: a regra de ocultação é restrita a leituras bem-sucedidas vindas de janelas do painel (`panel:*`). Leituras feitas dentro de uma conversa do agente (ex.: pesquisa na web) continuam aparecendo, porque fazem parte de um pedido de chat. Leitura com falha também continua visível.
- Operação vazia (`action: ""`) é tratada como desconhecida (`critical`), mais estrita que o padrão do `run`. Conservador.
- Não criei o teste "reprova qualquer ferramenta sem metadado" (AQ8, item posterior).
