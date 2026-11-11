# Item 6: Controles do PC (brilho, bloqueio de tela, volume, mídia) em janela

## O que mudou
- `app/agent/tools/system_control.py`: novas operações `get_brightness`, `set_brightness` (campo `level`, inteiro 0-100) e `lock_screen`. Volume e mídia seguem como estavam.
  - Brilho usa PowerShell + WMI (`WmiMonitorBrightness` / `WmiMonitorBrightnessMethods`), `shell=False`, comando fixo; o único valor variável é o inteiro já validado.
  - Se o equipamento não expõe brilho (monitor externo, PC de mesa), qualquer falha do PowerShell, timeout ou ausência do executável retorna `ok: false` com motivo claro e `data.supported = false`. Leitura com saída inesperada também é `ok: false`.
  - Bloqueio usa `rundll32.exe user32.dll,LockWorkStation`, `shell=False`. Código de saída diferente de zero vira `ok: false`.
  - Brilho inválido (fora de 0-100, texto, booleano, decimal não inteiro, ausente) é rejeitado antes de qualquer subprocess.
- `app/agent/tools/catalog.py`: mapa de risco por operação: `get_brightness` = observe; `set_brightness` e `lock_screen` = low. O que não está no mapa continua `critical` (exige aprovação).
- `app/ui/panel/api/controls.py` (novo) e registro em `app/ui/panel/server.py` (lista de POST, atrás de `_authorize_api` como as outras rotas): `POST /api/controls/run` com `{operation, level?}`.
  - Só aceita 9 operações da lista; qualquer outra volta 400 sem tocar no Action Kernel. Brilho inválido volta 400.
  - Cria um run (`mode=controls`, `session_id=panel:controls`) e executa `system_control` via `ActionExecutor`, então a ação aparece na Central de Execuções com risco, status e resultado real. A rota não chama subprocess.
  - Resposta: `ok`, `message`, `data` (ex.: `brightness`), `action`. Falha da ferramenta (brilho não suportado) volta 200 com `ok: false` e `error`. Se algum dia uma operação exigir confirmação, volta 202 `pending` e nada roda.
- `app/agent/tools/open_window.py`: janela `pc-controls` ("Controles do PC") no espelho do registro; não aceita parâmetros (o modelo só pede que abra, não define nível de brilho).
- Frontend:
  - `frontend/src/windows/PcControlsWindow.tsx` (novo): slider de brilho com botão "Aplicar brilho", "Ler de novo", botão de bloqueio com diálogo de confirmação do app, volume (diminuir, mudo, aumentar), mídia (anterior, play/pausa, próxima). Faixa de status mostra pendente, concluído (mensagem do servidor) ou falhou (erro do servidor).
  - `frontend/src/windows/registry.ts`: id `pc-controls`, carregamento sob demanda.
  - `frontend/src/commands/registry.ts`: comando `/controles` (apelidos: brilho, bloquear, bloqueio, volume, monitor), aparece na paleta e no menu `/`, `worksOffline: true`.
  - `frontend/src/styles/windows.css`: estilos `.ws-pc*`.
- `tests/test_tools_smoke.py`: o teste existente apertava a tecla real de mudo do Windows; agora simula `_press_media_key` (regra de não executar volume real).

## Testes (subprocess totalmente simulado)
- Novo `tests/test_pc_controls.py` (risco por operação, brilho inválido rejeitado na ferramenta e no endpoint, brilho não suportado com `ok: false`, argv/`shell=False`, leitura de brilho, bloqueio, endpoint cria registro de ação e run, falha vira ação `failed`, operações desconhecidas e JSON inválido recusados, rota registrada, `open_window` abre `pc-controls`).
- Rodados: `tests/test_pc_controls.py tests/test_open_window.py tests/test_tool_catalog.py tests/test_action_kernel.py tests/test_system_control_security.py tests/test_tools_smoke.py tests/test_control_plane_security.py tests/test_native_action_boundary.py tests/test_runs.py`: **210 passed**.
- `tsc --noEmit -p tsconfig.json` em `frontend`: sem erros.
- Nada foi executado de verdade: sem volume, brilho, bloqueio ou apps reais; sem backend real; sem smoke de navegador (fica para a etapa final).

## Decisões (conservadoras)
- Bloquear tela fica com risco `low` (como o brief), mas a janela pede confirmação no diálogo do app antes de enviar, por ser disruptivo.
- Ler brilho ao abrir a janela cria um registro `observe` na Central a cada abertura. Aceito para o slider começar no valor real; o botão "Ler de novo" faz o mesmo sob demanda.
- Brilho só é aplicado no botão "Aplicar brilho" (não a cada movimento do slider), para não encher a Central.
- Sem leitura de volume: as teclas de mídia do Windows não informam o nível, então a janela não mostra número de volume (nenhum número inventado).
- Aliases `tela` e `midia` ficaram fora de `/controles` porque já pertencem a `/visao` e `/cinema`.
- Pela via de marcadores do chat (`[tool:system_control:...]`) o brilho não é utilizável (não há `level`); só pelas chamadas nativas e pela janela.

## Não verificado
- Efeito real no Windows (brilho, bloqueio, volume, mídia), comportamento do PowerShell/WMI em monitores reais, visual da janela no navegador.
