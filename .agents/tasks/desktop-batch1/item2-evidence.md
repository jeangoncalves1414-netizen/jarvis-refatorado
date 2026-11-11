# Item 2: evidências da classificação de risco das ferramentas de controle

Primeira iteração. `review-item2.json` não existia, então o item foi implementado do zero. Branch `main`, sem worktree.

**Commit do item:** `c8615cb` (`fix: classificar risco das ferramentas de controle por operação`).

## Problema

- `system_control` estava como `observe` (`app/agent/tools/catalog.py:14`). Com isso, `ActionRecord.create` (`app/core/actions.py:143`) criava a ação como `proposed` e ela rodava sem aprovação, embora mude volume e mídia e abra apps.
- `open_windows_app` estava como `low` (`catalog.py:26`). Fechar um app, que chama `AppManager.close_app` (terminate e depois kill), rodava sem aprovação.

## O que mudou

| Arquivo | Mudança |
|---|---|
| `app/core/actions.py` | `ToolMetadata` ganhou três campos opcionais (`operation_arguments`, `default_operation`, `operation_risks`) e o método `risk_for(arguments)`. A operação é o valor da primeira chave de `operation_arguments` presente nos argumentos. Se nenhuma estiver presente, vale `default_operation`, que espelha o padrão da ferramenta. Operação fora do mapa recebe `critical`, o nível mais estrito, por regra do kernel e não por configuração. Sem mapa, `risk_for` devolve `default_risk`, então as outras ferramentas não mudam. `__post_init__` valida também os riscos do mapa. `ActionRecord.create` usa `risk_for(arguments)` para o risco gravado e para decidir `awaiting_confirmation`. |
| `app/agent/tools/catalog.py` | Helper `_by_operation(observe=..., low=..., high=...)`. Novas entradas para as duas ferramentas, descritas na tabela abaixo. A tag de capacidade de `system_control` passou de `("system", "observe")` para `("system", "control")`. Só `capabilities[0]` (`"system"`) é gravado, então o journal não muda. |
| `tests/test_tool_catalog.py` | 26 testes novos, descritos na seção de testes. |
| `tests/test_action_kernel.py` | 9 testes novos com o catálogo real e as ferramentas reais, sempre com o sistema mockado. |

### Classificação aplicada

| Ferramenta | observe | low | high | Não reconhecida |
|---|---|---|---|---|
| `system_control` (chaves `action`, depois `command`; padrão `telemetry`) | `telemetry`, `list_processes` | `open_app`, `media_play_pause`, `play`, `pause`, `media_next`, `next`, `media_prev`, `prev`, `previous`, `volume_up`, `volume_down`, `volume_mute` | nenhuma (a ferramenta não tem operação destrutiva) | `critical`, com aprovação. Exemplos: `kill_process`, `kill`, `shutdown`, `None` |
| `open_windows_app` (chave `action`; padrão `open`) | `list`, `status` | `open` | `close` | `critical`, com aprovação. Exemplos: `kill`, `""` |

Detalhes do mapeamento:

- **A chave `command` em `system_control`.** O caminho de marcadores (`orchestrator.py:623`) propõe com `{"command": arg}` e só depois `registry.run_by_marker` traduz isso para `{"action": arg}`. Sem ler `command`, o kernel veria `{"command": "volume_up"}` como `telemetry` (`observe`). Em `open_windows_app`, o marcador traduz `command` para `app_name` e não para `action`, por isso `command` não entra na lista dessa ferramenta. `{"command": "chrome"}` cai em `open`, que é `low`, e isso corresponde ao que a ferramenta executa.
- **Normalização.** `str(valor).strip().lower()`. As ferramentas fazem `.lower()` (system_control) e `.lower().strip()` (open_windows_app). Quando a classificação e a ferramenta divergem, a classificação é sempre a mais estrita das duas. Por exemplo, `open_windows_app` com `action: "kill"` executaria `open`, mas a classificação é `critical`.
- **Matar processo.** Nenhuma das duas ferramentas tem essa operação. Um pedido assim (`kill_process`, `kill`) é operação não reconhecida, recebe `critical` e só roda com aprovação.
- O `default_risk` dessas duas entradas é `"critical"`. Ele não é usado quando há mapa por operação, mas fica registrado como o pior caso para quem ler o catálogo.

## Comandos e resultados

Todos com `C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe`, a partir da raiz do repositório e depois das edições. A saída foi para `%TEMP%\item2-pytest.log` e `%TEMP%\item2-pytest-extra.log`.

| Verificação | Comando | Resultado |
|---|---|---|
| Suíte pedida | `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_action_kernel.py tests/test_actions.py tests/test_tool_catalog.py tests/test_system_control_security.py tests/test_app_manager.py tests/test_native_action_boundary.py tests/test_orchestrator_action_results.py` | **73 passaram**, 0 falharam, 1 aviso (depreciação do OpenTelemetry, que já existia), 6,23 s |
| Contagem por arquivo | o mesmo com `--collect-only` | `test_action_kernel.py` 17 (eram 8), `test_tool_catalog.py` 28 (eram 2), `test_system_control_security.py` 17, `test_app_manager.py` 5, `test_orchestrator_action_results.py` 3, `test_actions.py` 2, `test_native_action_boundary.py` 1 |
| Regressão extra do kernel (não pedida) | `python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_runs.py tests/test_action_history.py tests/test_mission_control.py tests/test_conversation_runtime.py tests/test_guardrails_thread_safety.py tests/test_control_plane_security.py` | **72 passaram**, 0 falharam, 1 aviso (o mesmo), 17,56 s |
| Grafo do código (regra `graphify.md`) | `graphify update .` | Estourou o limite de 5 minutos sem saída. `graphify-out/` é ignorado pelo git, então isso não afeta o commit. O grafo local pode estar desatualizado. |

## Testes novos

Em `tests/test_tool_catalog.py`:

- `test_control_tools_classify_risk_by_operation`, com 22 casos: consultas, volume, mídia, `open_app`, o formato de marcador (`command`), argumento ausente, maiúsculas e espaços, `close` como `high`, e `kill_process`, `kill`, `shutdown`, `None` e `""` como `critical`.
- `test_every_declared_control_operation_has_explicit_risk`, com 2 casos: cada valor do `enum` de `action` declarado pelas duas ferramentas tem risco explícito, ou seja, não cai em `critical`. Se alguém acrescentar uma operação à ferramenta sem classificá-la, esse teste falha.
- `test_tool_without_operation_map_keeps_its_default_risk` e `test_invalid_operation_risk_is_rejected`.

Em `tests/test_action_kernel.py` (helper `_control_executor`: `ActionExecutor` com `metadata_for=TOOL_CATALOG.get`, `ActionStore` em `tmp_path` e a ferramenta real):

- `test_closing_app_waits_for_approval_and_runs_once_after_it`: `close` gera proposta `high` em `awaiting_confirmation`, e `AppManager.close_app` (mockado) não é chamado. Depois de `authorized`, o callback executa uma vez, `close_app` é chamado uma única vez com `"notepad"` e a ação fica `succeeded`. `subprocess.Popen` está mockado e não é chamado.
- `test_unrecognized_system_operation_waits_for_approval`, com `kill_process`, `kill` e `shutdown`: cada um gera proposta `critical` em `awaiting_confirmation`. `subprocess.Popen`, `_press_media_key` e `psutil.process_iter` estão mockados e nenhum é chamado.
- `test_volume_and_media_run_without_approval`, com `volume_up`, `volume_mute` e `media_next`: cada um roda direto, com risco `low` e estado `succeeded`. `_press_media_key` mockado é chamado uma vez e `Popen` não é chamado.
- `test_opening_allowed_app_runs_without_approval`: `open_app` com `notepad` é `low`, roda sem aprovação e chama o `Popen` mockado uma vez com `("notepad.exe", shell=False)`.
- `test_listing_processes_is_observation`: `list_processes` é `observe`, `succeeded`, com `psutil.process_iter` mockado.

Nenhum teste novo toca o sistema real. `test_system_control_security.py` já tinha `test_telemetry_action_still_works` e `test_list_processes_action_still_works`, que leem CPU, RAM e processos reais por psutil, só para leitura. Não alterei esses testes.

## Ferramentas desligadas

`app/automation/desktop_automation.py` e `app/agent/tools/desktop_automation_tool.py` continuam fora do registro. Uma busca por `desktop_automation|DesktopAutomation` em `app/**/*.py` só encontra os próprios arquivos. `registry.py` não importa nem registra `DesktopAutomationTool`, e este lote não mudou isso.

## Efeito visível

- Pedir ao agente para fechar um app agora cria uma proposta na Central e só executa depois de **Autorizar**. Antes, executava direto.
- Volume, mídia, abrir app e as consultas continuam executando direto. A única diferença é o risco gravado no histórico: `low` para volume, mídia e abrir app e `observe` para as consultas. Antes, todas as operações de `system_control` eram gravadas como `observe`.
- O texto da proposta não mudou ("Executar open windows app. Parâmetros registrados de forma protegida."). Mostrar alvo e operação na proposta é outro item de `PROJECT_CONTINUITY.md` e ficou fora deste lote.

## Não testado

- O backend real, um provedor real e o Windows real. Todos os testes usam mocks e dados temporários.
- Rotas que chamam essas ferramentas sem passar pelo `ActionExecutor`, como endpoints diretos do servidor e voz. Essas rotas estão fora do escopo deste item.

## Observações

- Os arquivos de `.agents/tasks/desktop-batch1/`, incluindo este, continuam não rastreados, como no item 1.
- `docs/DECISOES_E_IDEIAS.md` continua não rastreado e não foi alterado.
