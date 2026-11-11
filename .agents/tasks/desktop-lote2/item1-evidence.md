# Item 1 do lote 2: segurança do `open_windows_app` e sobras do lote 1

HEAD inicial: 36bbb35. Sem backend real, sem ação no sistema: os testes mockam `subprocess.Popen`, `os.startfile`, `psutil.process_iter` e a leitura do registro do Windows.

## Achados obrigatórios (review-item2)

### Achado 1: shell sem aprovação em `AppManager.open_app`
- `app/services/app_manager.py`: saiu todo `shell=True`. Novo `_spawn(argv)` chama `subprocess.Popen(lista, shell=False)`.
  - Passo 1 (`_EXEC_PATHS`): o texto fixo vira lista (`Update.exe --processStart Discord.exe` → `[exe, "--processStart", "Discord.exe"]`).
  - Passo 2 (`_SYSTEM_COMMANDS`): `shutil.which(nome)` resolve o executável. Se não estiver no PATH (ex.: chrome), `os.startfile(nome)` usa o App Paths do Windows, sem cmd.exe.
  - Passo 5 (antes, o shell genérico): só `shutil.which(nome)` exato no PATH, sem shell. "cmd /c echo x", "notepad && calc" etc. não resolvem e `open_app` devolve False.
  - Flags: `.cmd/.bat` com `CREATE_NO_WINDOW`; `.exe` com `CREATE_NEW_CONSOLE` sem redirecionar a saída, para cmd/powershell abrirem com janela visível. Antes, o cmd ficava preso num console oculto.
- Novo `AppManager.is_known_target(nome)`: True só para alias (mapa padrão + `aliases.json`), `_SYSTEM_COMMANDS`, chave de `_URI_PROTOCOLS` ou app achado no registro por `find_app`. Função de módulo `is_known_app_target` usa um `AppManager` compartilhado (aliases e cache de registro).
- `app/core/actions.py`: `ToolMetadata` ganhou `target_risk(operação, argumentos)`. Esse risco só eleva o risco da operação, nunca reduz. Exceção ou valor inválido vira `critical`.
- `app/agent/tools/catalog.py`: `open_windows_app` usa `_open_app_target_risk`. `open` é `low` só quando todos os alvos presentes (`app_name` e/ou `command`, que é a chave do caminho de marcadores) são conhecidos. Nos demais casos, inclusive caminho de arquivo existente, nome vazio ou ausente e tipo não-string, é `high`. `status`/`list`/`close` mantêm observe/observe/high.

### Achado 2: casamento por substring em `is_app_running`/`close_app`
- Casamento exato, sem diferenciar maiúsculas, no stem do executável (`_exe_stem`: tira pasta e `.exe`). Nome vazio devolve `(False, [])`.
- Efeito colateral, aceito por segurança: apps cujo processo tem outro nome deixam de casar pelo apelido (ex.: "calc" não pega `CalculatorApp.exe`; "whatsapp" não pega `WhatsApp.Root.exe`). `status` diz "não está em execução" e `close` não fecha esses apps. Um mapa alias→processo real fica para depois.

### Achado 3: teste ponta a ponta do caminho de marcadores
- `tests/test_action_kernel.py::test_marker_volume_runs_as_low_and_kill_waits_for_approval`: `ActionExecutor` com `ToolRegistry` real e `legacy_execute` igual ao adaptador do orquestrador (`registry.run_by_marker(name, args.get("command"), user)`). `run_by_marker` recebe `(kind, arg: str, user_line)`, então ligá-lo direto passaria o dict como `arg`. `{"command": "volume_up"}` termina low/succeeded; `{"command": "kill_process"}` fica em critical/awaiting_confirmation sem tocar Popen/psutil.
- Extra: `test_marker_open_with_free_text_waits_for_approval`: `{"command": "cmd /c echo x"}` fica high/awaiting sem Popen/startfile. `{"command": "bloco de notas"}` termina low/succeeded com `shell=False`.

## Achados não bloqueantes

| Achado | Situação |
|---|---|
| review-item1 #1, `mobile_release` sem chamador | **Aplicado**: comando de conferência manual citado em `docs/MOBILE_EVOLUTION.md`, logo após o passo do APK. Os scripts de APK não foram alterados, porque o passo não pode rodá-los. |
| review-item1 #2, conferir desktop e APK | **Pulado**: exige `npm run build:mobile` e o script do APK, proibidos neste passo. Continua no item 1 de `PENDENCIAS_DO_PAINEL.md`. |
| review-item2 #2 (parte: alvo/efeito na proposta) | **Pulado**: lote futuro, por instrução. Só o casamento exato foi feito. |
| review-item3 #1, remover o controle local corta os comandos | **Aplicado**: o diálogo de `jarvis-desktop` tem texto próprio (Ligar/Desligar param e como parear de novo). O botão continua visível. |
| review-item3 #2, credencial velha após "não encontrado" | **Aplicado**: `removeBridgeDevice` apaga `jarvis-bridge-desktop-token` quando a ponte responde "Dispositivo não encontrado" para `jarvis-desktop`. |
| review-item3 #3, Remover recusa no modo lan | **Aplicado**: registrado na linha "002 — controle local e ponte" de `PENDENCIAS_DO_PAINEL.md`. |
| review-item3 #4, docs apontam para o Quest Log apagado | **Aplicado**: item 4 de `PENDENCIAS_DO_PAINEL.md` sem o link para `useQuestLog.ts` (agora aponta para `useChat.ts`). `PROJECT_CONTINUITY.md` diz que o Quest Log foi removido. |
| review-item3 #5, `QuestLogPanel.tsx` e tipos órfãos | **Aplicado**: arquivo removido (`git rm`) junto com `ProcessStepStatus`, `ProcessStepItem` e `ProcessQuest` em `types.ts`. Sem outros usos (grep); o typecheck passa. O CSS antigo, se existir, ficou. |
| review-item3 #6, fiação do "Parar pedido" | **Aplicado**: registrado no item 4 de `PENDENCIAS_DO_PAINEL.md` (backend envia o `run_id` no início do turno ou o App consulta `/api/runs?status=running`). |
| review-item3 #7, falha de rede na remoção sem teste | **Aplicado**: `workspace.smoke.cjs` aborta o POST `remove` (`route.abort()`) e confere o alerta "Sem conexão com a ponte" e a credencial preservada. Também cobre o caso "não encontrado", que apaga a credencial, e o aviso próprio do diálogo. |

## Decisões
- Classificação por alvo no catálogo, via `target_risk`, e não na ferramenta: o executor continua decidindo só pelo `ToolMetadata`, e o mecanismo só eleva o risco.
- Alvo app do registro conta como conhecido mesmo com a busca aproximada de `find_app`: o que abre é o executável instalado achado no registro, não o texto do modelo.
- Nome livre aprovado (high) só abre se for executável exato no PATH ou arquivo existente (`os.startfile`). Nunca vira comando de shell.

## Testes
- `pytest tests/test_app_manager.py tests/test_system_control_security.py tests/test_tool_catalog.py tests/test_action_kernel.py tests/test_orchestrator_action_results.py`: **93 passed**.
- `pytest tests/test_action_history.py tests/test_native_action_boundary.py tests/test_runs.py tests/test_tools_smoke.py tests/test_mission_control.py tests/test_conversation_runtime.py`: **68 passed**.
- `tsc --noEmit -p tsconfig.json`: sem erros.
- `workspace.smoke.cjs`: 8 linhas PASS, inclusive a nova de remoção (aviso do controle local, falha de rede, credencial velha). `runs.smoke.cjs`: PASS.
  - Nota: já havia um Vite na porta 5173 desde as 12:08, que não foi iniciado por este passo. O que iniciei falhou com "port in use" e saiu sozinho. O servidor existente não foi parado. O smoke rodou contra ele com o código atual, como prova a asserção do texto novo do diálogo. Foi preciso forçar `PANEL_TEST_URL=http://127.0.0.1:5173`, porque o ambiente tinha 5174.
- Screenshots: `.agents/tasks/desktop-lote2/item1-screens/` (desktop-device-remove-error.png, mobile-device-remove-confirm-360.png, mobile-device-remove-error-360.png e as demais do smoke).
