# Inventário de ferramentas do agente (lote 6, fase 1)

Gerado por `python -m app.agent.tools.inventory` (seção DEPOIS). Risco calculado pelo catálogo do Action Kernel com só o argumento da operação; `open_windows_app.open` aparece high porque, sem `app_name`, o alvo é desconhecido.

## O que mudou (resumo)

- Operações novas: `habit_tool` create_many, check_many, update com new_name/category/routine_block, list only_today, check/uncheck/update/delete por nome (delete só com nome exato; ambíguo → erro com candidatos). `task_tool` create_many, update, list include_completed, toggle/delete por título. `finance_tool` add_many, update, list com period/type/category. `lifeos_tool` set_water (total do dia, 0-10.000 ml); add_water limitado a 1-5.000 ml. `calendar` create_many (até 10), list com day e upcoming_days. `timer` cancel pelo rótulo.
- Lotes validam tudo antes de gravar; limites: 20 hábitos, 20 tarefas, 20 lançamentos, 10 lembretes.
- Ferramenta nova `open_screen` (observe): telas do app, espelho de `frontend/src/navigation.ts`.
- Cofre visível ao modelo: `vault_search` (observe), `vault_daily_log`, `vault_save_note`, `vault_update_profile` (low), com parâmetros tipados. `vault_save_note` só aceita 01-Daily-Notes, 03-Priming-Notes, 04-Projects e 05-Notas (padrão); título 1-120, conteúdo até 20.000.
- Catálogo: entrada para toda ferramenta de `GENERAL_TOOL_NAMES`; `calendar` e `timer` com risco por operação (list = observe). Subiram para high (com aprovação): `phantom_typer`, `telegram_bot.send/start_bot`, `system_tray.enable_boot/disable_boot`, `wormhole.start`, `smart_drop_zone`, `document_generator` com `output_path` próprio. Entrada órfã `notes` removida do catálogo e da lista fixa do Groq.
- `phantom_typer`, `screen_peeler` e `smart_drop_zone` ganharam `parameters` (antes o modelo recebia `{}`).
- Groq: mapa de palavras-chave → ferramenta (hábito, tarefa, água/bebi, gastei/paguei, nota/anota, lembrete/agenda, tela/painel/abre).
- Contexto da resposta nativa ganhou `tool_calls` (todas as chamadas em ordem); `tool_results` continua com a última por nome.

## ANTES (HEAD antes-lote6, copiado da seção a do plano)

Fonte: `app/agent/tools/registry.py` (`GENERAL_TOOL_NAMES`, `TUTOR_TOOL_NAMES`), `app/agent/tools/catalog.py` (`TOOL_CATALOG`), `parameters` de cada ferramenta. "Visível" = está em `GENERAL_TOOL_NAMES` (o modelo recebe e o executor do turno aceita, C3). "Catálogo" = entrada explícita em `TOOL_CATALOG`; sem ela vale o padrão do `BaseTool` (`low`, ou `critical` se `critical=True`), sem alvo/efeito.

| Ferramenta | Visível | Operações (`action`) | Parâmetros | Catálogo / risco | Lacunas achadas |
|---|---|---|---|---|---|
| habit_tool | sim | list, create, update, check, uncheck, delete | habit_id, name, category, routine_block, days_of_week, start_time, time_exceptions, items_list, add/remove_days, add/remove_items | sim; list observe, escrita low, delete high | sem lote (vários hábitos = várias chamadas); delete só por id (modelo só conhece nomes); update não renomeia nem muda categoria/bloco; duplica conceito com lifeos_tool |
| task_tool | sim | list, create, toggle, delete | task_id, title, priority, project, due_date | sim | sem lote; sem update; list não mostra concluídas; delete só por id |
| finance_tool | sim | summary, add, list, delete | type, amount, category, description, trans_id | sim | sem lote; list sem filtros (período/tipo/categoria) apesar de `FinanceService.query_transactions`; sem update apesar de `update_transaction` |
| lifeos_tool | sim | add_water, get_water, check_habit, uncheck_habit, list_habits, log_workout, summary, motivate | amount, habit_name, workout_name, notes (não usado) | sim | não define total do dia ("bebi 3 L hoje"); `amount` sem limite |
| calendar | sim | list, create_reminder, cancel_reminder | query, title, start, reminder_minutes, reminder_at, reminder_policy | sim, `low` sem mapa por operação (list deveria ser observe) | list sem filtro de dia; sem lote |
| timer | sim | list, set_timer, set_alarm | duration, time, label | sim, `low` sem mapa | sem cancelar (o catálogo promete "cancele o timer") |
| open_window | sim | (window_id) finance, pc-controls | window_id, params | sim, observe | não abre telas do app ("abre o painel") |
| planning_workspace | sim | open, close, append, update, status, set_auto_open | action, title, content, enabled | sim, low | ok |
| web_search | sim | search, research, open_url | action, query, max_results | sim, observe | ok |
| system_control | sim | telemetry, list_processes, get/set_brightness, lock_screen, mídia, volume, open_app | action, level, app_name | sim, por operação | ok |
| open_windows_app | sim | open, close, status, list | action, app_name | sim, por operação + alvo | ok |
| vision / realtime / desktop_search | sim | vários | vários | sim, observe | ok |
| spotify, clipboard, whatsapp, browser_agent, file_manager, script_runner, mobile_adb, kasa_control | sim | vários | vários | sim | ok |
| jarvis_mode, news_reader, cinema, qr_reader, proactive_agent, system_tray, image_generator, screen_peeler, phantom_typer, smart_drop_zone, document_generator, telegram_bot, wormhole, wallpaper_engine, clipboard_intelligence | sim | ver `parameters` | ver `parameters` | **não** (padrão `low` sem alvo/efeito) | auditoria pendente: phantom_typer digita, telegram envia, wormhole expõe porta, system_tray muda a inicialização: todos estão `low` hoje |
| vault_search, vault_daily_log, vault_save_note, vault_update_profile | **não** (registradas, fora de `GENERAL_TOOL_NAMES`) | — | **sem `parameters`** (BaseTool devolve `{}`) | não | o modelo não vê; `save_note(folder=...)` aceita qualquer pasta (caminho com `..` escapa do vault) |
| code_helper, hacker_mode, workflow, mcp, dev_agent | não (fora da lista geral) | — | — | hacker_mode/workflow sim | fora do escopo |
| `notes` | aparece no catálogo e no `core_groq`, **sem ferramenta registrada** | — | — | entrada órfã | remover do `core_groq` e do catálogo (Fase 1) |
| Tutor (whiteboard_*, tutor_*, enem_save_question) | só modo tutor | — | — | parcial | fora do escopo |

Outras observações:
- Caminho nativo (`AgentOrchestrator._run_llm_with_tools`) faz **uma rodada** de chamadas de ferramenta e uma geração final (`_chat_gemini_stream` e `_chat_groq_stream`, `app/services/llm.py:804-840` e `:1201-1240`). Não há continuação nem verificação.
- `executed_tool_results` é indexado por nome de ferramenta: duas chamadas da mesma ferramenta no turno se sobrescrevem.
- `ReActLoopEngine` (`app/agent/react_loop.py`) só aceita `REACT_TOOLS` (6 ferramentas), uma ação por etapa, encerra a sequência quando uma etapa pede aprovação (C8) e não conta chamadas ao modelo (AQ5).
- `core_groq` (`registry.py:allowed_tool_names`) corta hábitos/tarefas/água no Groq a menos que o texto contenha o nome técnico da ferramenta ("habit_tool").

## DEPOIS (regenerado na fase 6, inclui places_search e show_popup)

| Ferramenta | Visível | Catálogo | Operações (risco) | Parâmetros (* obrigatório) |
|---|---|---|---|---|
| browser_agent | geral | sim | — (high) | goal*: string; start_url: string; fast_action: string (auto/dump_dom/click_text/type_input); target_text: string; target_selector: string |
| calendar | geral | sim | list (observe), create_reminder (low), create_many (low), cancel_reminder (low) | action*: string (list/create_reminder/create_many/cancel_reminder); query: string; title: string; start: string; reminder_minutes: integer; reminder_at: string; reminder_policy: string (once/until_confirmed/next_conversation); reminders: array [reminder_at, reminder_minutes, reminder_policy, start, title]; day: string; upcoming_days: integer |
| cinema | geral | sim | search (observe), play (low), discover (observe), detect_url (observe) | action*: string (search/play/discover/detect_url); query: string; imdb_id: string; url: string; media_type: string (auto/movie/tv); season: integer; episode: integer |
| clipboard | geral | sim | read (low), write (low), copy (low), history (low) | action*: string (read/write/copy/history); text: string |
| clipboard_intelligence | geral | sim | read (observe), refactor (observe), explain_error (observe), translate (observe), summarize (observe) | action*: string (read/refactor/explain_error/translate/summarize); text: string |
| code_helper | não | não | generate (low), explain (low), refactor (low) | action*: string (generate/explain/refactor); code*: string; language: string |
| desktop_search | geral | sim | — (observe) | — |
| dev_agent | não | não | — (low) | task*: string (review/debug/test); code: string |
| document_generator | geral | sim | pptx (low), xlsx (low), pdf (low) | format*: string (pptx/xlsx/pdf); title*: string; content*: string; output_path: string |
| file_manager | geral | sim | list (high), read (high) | action*: string (list/read); path: string |
| finance_tool | geral | sim | summary (observe), add (low), add_many (low), list (observe), update (low), delete (high) | action*: string (summary/add/add_many/list/update/delete); type: string (expense/income); amount: number; category: string; description: string; date: string; trans_id: string; entries: array [amount, category, date, description, type]; period: string (week/month/all) |
| habit_tool | geral | sim | list (observe), create (low), create_many (low), update (low), check (low), check_many (low), uncheck (low), delete (high) | action*: string (list/create/create_many/update/check/check_many/uncheck/delete); habit_id: string; name: string; category: string; routine_block: string (morning/afternoon/evening/anytime); days_of_week: array[string]; start_time: string; items_list: array[string]; new_name: string; time_exceptions: object; add_days: array[string]; remove_days: array[string]; add_items: array[string]; remove_items: array[string]; habits: array [category, days_of_week, items_list, name, routine_block, start_time]; names: array[string]; only_today: boolean |
| hacker_mode | não | sim | — (critical) | — |
| image_generator | geral | sim | — (low) | prompt*: string; size: string (256x256/512x512/1024x1024) |
| jarvis_mode | geral | sim | silent (low), hybrid (low), call_mode (low) | command*: string (silent/hybrid/call_mode) |
| kasa_control | geral | sim | discover (high), on (high), off (high), toggle (high), status (high) | action*: string (discover/on/off/toggle/status); device_alias: string; device_ip: string |
| lifeos_tool | geral | sim | add_water (low), set_water (low), get_water (observe), check_habit (low), uncheck_habit (low), list_habits (observe), log_workout (low), summary (observe), motivate (observe) | action*: string (add_water/set_water/get_water/check_habit/uncheck_habit/list_habits/log_workout/summary/motivate); amount: number; total_ml: number; habit_name: string; workout_name: string |
| mcp | não | não | — (low) | server: string; action*: string; tool: string; params: object |
| mobile_adb | geral | sim | devices (high), dump_ui (high), tap_element (high), tap_xy (high), type_text (high), swipe (high), press_key (high), shell (high), install (high), push (high), pull (high), screenshot (high), reboot (high), logcat (high) | action*: string (devices/dump_ui/tap_element/tap_xy/type_text/swipe/press_key/shell/install/push/pull/screenshot/reboot/logcat); command: string; x: integer; y: integer; direction: string (up/down/left/right); key: string (home/back/recents/enter/delete); device_serial: string; destination: string; output_path: string |
| news_reader | geral | sim | — (observe) | limit: integer; feed_url: string |
| open_screen | geral | sim | — (observe) | screen*: string (Dashboard/Chat/Central/Automações/Memórias/Integrações/Estudos/Evolução/Calendário/Painel pessoal/Análises/Identidade/Configurações) |
| open_window | geral | sim | — (observe) | window_id*: string (finance/pc-controls/places); params: object |
| open_windows_app | geral | sim | open (high), close (high), status (observe), list (observe) | action*: string (open/close/status/list); app_name: string |
| phantom_typer | geral | sim | — (high) | text*: string; delay_seconds: number |
| places_search | geral | sim | — (observe) | query*: string; near: string |
| planning_workspace | geral | sim | open (low), close (low), append (low), update (low), status (low), set_auto_open (low) | action*: string (open/close/append/update/status/set_auto_open); title: string; content: string; enabled: boolean |
| proactive_agent | geral | sim | configure_briefing (low), add_reminder (low), get_status (observe), trigger_briefing (observe) | action*: string (configure_briefing/add_reminder/get_status/trigger_briefing); enabled: boolean; briefing_time: string; topics: array[string]; custom_instructions: string; reminder_message: string; reminder_time: string |
| qr_reader | geral | sim | screen (observe), camera (observe) | source*: string (screen/camera); monitor: integer; camera_index: integer; timeout: number |
| realtime | geral | sim | get_weather (observe), get_news (observe), get_finance (observe), get_holidays (observe) | action*: string (get_weather/get_news/get_finance/get_holidays); city: string; year: integer; limit: integer |
| screen_peeler | geral | sim | — (low) | prompt: string |
| script_runner | geral | sim | — (critical) | language*: string (python/powershell); code*: string; description*: string |
| show_popup | geral | sim | — (observe) | template*: string (habit_list/info/live_notes/places/schedule/task_list/water); params: object |
| smart_drop_zone | geral | sim | — (high) | target_folder: string (Downloads/Desktop) |
| spotify | geral | sim | play_pause (low), next (low), previous (low), current_track (low), search_play (low), open (low) | action*: string (play_pause/next/previous/current_track/search_play/open); query: string |
| system_control | geral | sim | telemetry (observe), open_app (low), list_processes (observe), media_play_pause (low), media_next (low), media_prev (low), volume_up (low), volume_down (low), volume_mute (low), get_brightness (observe), set_brightness (low), lock_screen (low) | action*: string (telemetry/open_app/list_processes/media_play_pause/media_next/media_prev/volume_up/volume_down/volume_mute/get_brightness/set_brightness/lock_screen); level: integer; app_name: string |
| system_tray | geral | sim | enable_boot (high), disable_boot (high), status (observe) | action*: string (enable_boot/disable_boot/status) |
| task_tool | geral | sim | list (observe), create (low), create_many (low), update (low), toggle (low), delete (high) | action*: string (list/create/create_many/update/toggle/delete); task_id: string; title: string; priority: integer; project: string; due_date: string; new_title: string; tasks: array [due_date, priority, project, title]; include_completed: boolean |
| telegram_bot | geral | sim | send (high), start_bot (high), stop_bot (low), status (observe) | action*: string (send/start_bot/stop_bot/status); message: string; chat_id: string |
| timer | geral | sim | set_timer (low), set_alarm (low), list (observe), cancel (low) | action*: string (set_timer/set_alarm/list/cancel); duration: string; time: string; label: string |
| vault_daily_log | geral | sim | — (low) | entry*: string; category: string |
| vault_save_note | geral | sim | — (low) | title*: string; content*: string; folder: string (01-Daily-Notes/03-Priming-Notes/04-Projects/05-Notas) |
| vault_search | geral | sim | — (observe) | query*: string; limit: integer |
| vault_update_profile | geral | sim | — (low) | fact*: string |
| vision | geral | sim | analyze_screen (observe), analyze_camera (observe) | action*: string (analyze_screen/analyze_camera); prompt: string |
| wallpaper_engine | geral | sim | — (low) | query: string; image_url: string |
| web_search | geral | sim | search (observe), research (observe), open_url (observe) | action*: string (search/research/open_url); query*: string; max_results: integer |
| whatsapp | geral | sim | — (high) | target*: string; message*: string |
| whiteboard_add_image | tutor | sim | — (low) | image_url*: string; x*: number; y*: number; width: integer; height: integer |
| whiteboard_add_text | tutor | sim | — (low) | text*: string; x*: number; y*: number; size: integer; color: string |
| whiteboard_clear | tutor | sim | — (high) | — |
| whiteboard_edit | tutor | sim | list (low), update (low), move (low), resize (low), duplicate (low), delete (low) | action*: string (list/update/move/resize/duplicate/delete); element_id: string; x: number; y: number; width: number; height: number; color: string; size: number; content: string; font_weight: string (normal/bold); font_style: string (normal/italic); variant: string (paragraph/heading/quote/code/callout); list_style: string (plain/bullets/tasks); background_color: string; font_family: string; text_decoration: string (none/underline/line-through); object_fit: string (contain/cover/fill); opacity: number; caption: string; rotation: number; z_index: number; locked: boolean |
| workflow | não | sim | — (high) | recipe: object; recipe_id: string (planejamento_semanal/encerrar_dia); dry_run: boolean |
| wormhole | geral | sim | start (high), stop (low), list (observe) | action*: string (start/stop/list); port: integer |

## Efeitos por operação

- `browser_agent` (high): Controla um navegador: abre páginas, clica e digita para cumprir o objetivo (até 10 passos).
- `calendar.list` (observe): Apenas lê os compromissos do calendário; nada é alterado.
- `calendar.create_reminder` (low): Cria um lembrete no calendário local.
- `calendar.create_many` (low): Cria vários lembretes no calendário local de uma vez.
- `calendar.cancel_reminder` (low): Para os avisos do lembrete indicado.
- `cinema.search` (observe): Apenas pesquisa o catálogo de filmes e séries; nada é alterado.
- `cinema.play` (low): Abre o player do título no painel.
- `cinema.discover` (observe): Apenas pesquisa fontes aprovadas; nada é alterado.
- `cinema.detect_url` (observe): Apenas analisa a página informada; nada é alterado.
- `clipboard.read` (low): Lê o histórico ou copia um texto para a área de transferência, substituindo o conteúdo atual.
- `clipboard.write` (low): Lê o histórico ou copia um texto para a área de transferência, substituindo o conteúdo atual.
- `clipboard.copy` (low): Lê o histórico ou copia um texto para a área de transferência, substituindo o conteúdo atual.
- `clipboard.history` (low): Lê o histórico ou copia um texto para a área de transferência, substituindo o conteúdo atual.
- `clipboard_intelligence.read` (observe): Apenas lê o texto copiado; nada é alterado.
- `clipboard_intelligence.refactor` (observe): Apenas lê o texto copiado e prepara o pedido para a resposta; nada é alterado.
- `clipboard_intelligence.explain_error` (observe): Apenas lê o texto copiado e prepara o pedido para a resposta; nada é alterado.
- `clipboard_intelligence.translate` (observe): Apenas lê o texto copiado e prepara o pedido para a resposta; nada é alterado.
- `clipboard_intelligence.summarize` (observe): Apenas lê o texto copiado e prepara o pedido para a resposta; nada é alterado.
- `desktop_search` (observe): Apenas procura arquivos; nada é alterado.
- `document_generator.pptx` (low): Gera uma apresentação PowerPoint e salva o arquivo.
- `document_generator.xlsx` (low): Gera uma planilha Excel e salva o arquivo.
- `document_generator.pdf` (low): Gera um PDF e salva o arquivo.
- `file_manager.list` (high): Lista o conteúdo da pasta; nada é alterado.
- `file_manager.read` (high): Lê o conteúdo do arquivo; nada é alterado.
- `finance_tool.summary` (observe): Apenas lê o resumo financeiro; nada é alterado.
- `finance_tool.add` (low): Registra um lançamento de receita ou despesa.
- `finance_tool.add_many` (low): Registra vários lançamentos de uma vez; se algum for inválido, nenhum é gravado.
- `finance_tool.list` (observe): Apenas lê os lançamentos do período; nada é alterado.
- `finance_tool.update` (low): Corrige valor, tipo, categoria, descrição ou data de um lançamento.
- `finance_tool.delete` (high): Exclui um lançamento financeiro.
- `habit_tool.list` (observe): Apenas lê os hábitos; nada é alterado.
- `habit_tool.create` (low): Cria um hábito novo.
- `habit_tool.create_many` (low): Cria vários hábitos de uma vez; se algum for inválido, nenhum é criado.
- `habit_tool.update` (low): Altera nome, categoria, período, dias, horário ou itens de um hábito existente.
- `habit_tool.check` (low): Marca o hábito como concluído hoje.
- `habit_tool.check_many` (low): Marca vários hábitos como concluídos hoje.
- `habit_tool.uncheck` (low): Desfaz a marcação de hoje do hábito.
- `habit_tool.delete` (high): Remove o hábito.
- `image_generator` (low): Envia a descrição ao serviço de imagens e devolve o link da imagem gerada; pode consumir créditos.
- `jarvis_mode.silent` (low): Desliga a fala das respostas (só texto).
- `jarvis_mode.hybrid` (low): Volta a falar as respostas.
- `jarvis_mode.call_mode` (low): Abre a interface de ligação por voz.
- `kasa_control.discover` (high): Procura dispositivos Kasa na rede; nada é alterado.
- `kasa_control.on` (high): Liga o dispositivo.
- `kasa_control.off` (high): Desliga o dispositivo.
- `kasa_control.toggle` (high): Inverte o estado do dispositivo (liga se estiver desligado e vice-versa).
- `kasa_control.status` (high): Apenas lê o estado do dispositivo; nada é alterado.
- `lifeos_tool.add_water` (low): Soma a quantidade informada ao consumo de água de hoje.
- `lifeos_tool.set_water` (low): Define o total de água de hoje no valor informado.
- `lifeos_tool.get_water` (observe): Apenas lê o consumo de água de hoje; nada é alterado.
- `lifeos_tool.check_habit` (low): Marca o hábito do Life OS como concluído hoje.
- `lifeos_tool.uncheck_habit` (low): Desmarca o hábito do Life OS de hoje.
- `lifeos_tool.list_habits` (observe): Apenas lê os hábitos do Life OS; nada é alterado.
- `lifeos_tool.log_workout` (low): Registra o treino de hoje e marca o hábito de treino.
- `lifeos_tool.summary` (observe): Apenas lê o resumo do dia; nada é alterado.
- `lifeos_tool.motivate` (observe): Apenas lê o resumo do dia para uma mensagem; nada é alterado.
- `mobile_adb.devices` (high): Apenas lê informações do celular; nada é alterado.
- `mobile_adb.dump_ui` (high): Apenas lê informações do celular; nada é alterado.
- `mobile_adb.tap_element` (high): Interage com a tela do celular como um toque ou digitação.
- `mobile_adb.tap_xy` (high): Interage com a tela do celular como um toque ou digitação.
- `mobile_adb.type_text` (high): Interage com a tela do celular como um toque ou digitação.
- `mobile_adb.swipe` (high): Interage com a tela do celular como um toque ou digitação.
- `mobile_adb.press_key` (high): Interage com a tela do celular como um toque ou digitação.
- `mobile_adb.shell` (high): Executa um comando dentro do celular.
- `mobile_adb.install` (high): Instala um aplicativo no celular.
- `mobile_adb.push` (high): Envia um arquivo deste computador para o celular.
- `mobile_adb.pull` (high): Copia um arquivo do celular para este computador.
- `mobile_adb.screenshot` (high): Tira uma captura da tela do celular e salva um arquivo neste computador.
- `mobile_adb.reboot` (high): Reinicia o celular.
- `mobile_adb.logcat` (high): Apenas lê informações do celular; nada é alterado.
- `news_reader` (observe): Apenas lê manchetes de um feed RSS; nada é alterado.
- `open_screen` (observe): Muda o app para a tela indicada; nenhum dado é alterado.
- `open_window` (observe): Abre uma janela do painel; nenhum dado é alterado.
- `open_windows_app.open` (high): Abre o aplicativo, ou traz a janela para a frente se já estiver aberto.
- `open_windows_app.close` (high): Encerra todos os processos listados: pede para sair e, se não saírem, força o encerramento.
- `open_windows_app.status` (observe): Apenas verifica se o aplicativo está em execução; nada é alterado.
- `open_windows_app.list` (observe): Apenas lê os aplicativos em execução; nada é alterado.
- `phantom_typer` (high): Cola o texto na janela que estiver ativa, como se fosse digitado pela usuária.
- `places_search` (observe): Envia o texto da busca ao provedor de mapas e lê os resultados; nada é alterado.
- `planning_workspace.open` (low): Abre, atualiza ou fecha o painel de planejamento desta conversa.
- `planning_workspace.close` (low): Abre, atualiza ou fecha o painel de planejamento desta conversa.
- `planning_workspace.append` (low): Abre, atualiza ou fecha o painel de planejamento desta conversa.
- `planning_workspace.update` (low): Abre, atualiza ou fecha o painel de planejamento desta conversa.
- `planning_workspace.status` (low): Abre, atualiza ou fecha o painel de planejamento desta conversa.
- `planning_workspace.set_auto_open` (low): Abre, atualiza ou fecha o painel de planejamento desta conversa.
- `proactive_agent.configure_briefing` (low): Altera horário, tópicos ou instruções do briefing matinal.
- `proactive_agent.add_reminder` (low): Agenda um lembrete do assistente proativo.
- `proactive_agent.get_status` (observe): Apenas lê a configuração do briefing e os lembretes; nada é alterado.
- `proactive_agent.trigger_briefing` (observe): Apenas monta o briefing agora; nada é alterado.
- `qr_reader.screen` (observe): Apenas captura a tela e lê QR codes; nada é alterado.
- `qr_reader.camera` (observe): Apenas liga a câmera por alguns segundos para ler QR codes; nada é alterado.
- `realtime.get_weather` (observe): Apenas consulta dados públicos; nada é alterado.
- `realtime.get_news` (observe): Apenas consulta dados públicos; nada é alterado.
- `realtime.get_finance` (observe): Apenas consulta dados públicos; nada é alterado.
- `realtime.get_holidays` (observe): Apenas consulta dados públicos; nada é alterado.
- `screen_peeler` (low): Captura a tela, extrai o texto com o serviço de visão e copia o texto para a área de transferência.
- `script_runner` (critical): Executa o script neste computador com as permissões do seu usuário.
- `show_popup` (observe): Mostra um popup do painel; nenhum dado é alterado.
- `smart_drop_zone` (high): Move os arquivos soltos da pasta para subpastas por tipo (Documentos, Imagens, Compactados, Executaveis, Codigos).
- `spotify.play_pause` (low): Controla a reprodução do Spotify (pausar, pular, abrir ou tocar uma busca).
- `spotify.next` (low): Controla a reprodução do Spotify (pausar, pular, abrir ou tocar uma busca).
- `spotify.previous` (low): Controla a reprodução do Spotify (pausar, pular, abrir ou tocar uma busca).
- `spotify.current_track` (low): Controla a reprodução do Spotify (pausar, pular, abrir ou tocar uma busca).
- `spotify.search_play` (low): Controla a reprodução do Spotify (pausar, pular, abrir ou tocar uma busca).
- `spotify.open` (low): Controla a reprodução do Spotify (pausar, pular, abrir ou tocar uma busca).
- `system_control.telemetry` (observe): Apenas lê o uso de CPU e memória; nada é alterado.
- `system_control.open_app` (low): Abre o aplicativo informado, se estiver na lista permitida.
- `system_control.list_processes` (observe): Apenas lê a lista de processos; nada é alterado.
- `system_control.media_play_pause` (low): Pausa ou retoma a mídia que está tocando.
- `system_control.media_next` (low): Pula para a próxima faixa do player ativo.
- `system_control.media_prev` (low): Volta para a faixa anterior do player ativo.
- `system_control.volume_up` (low): Aumenta o volume do sistema.
- `system_control.volume_down` (low): Diminui o volume do sistema.
- `system_control.volume_mute` (low): Liga ou desliga o mudo do sistema.
- `system_control.get_brightness` (observe): Apenas lê o brilho atual da tela; nada é alterado.
- `system_control.set_brightness` (low): Ajusta o brilho da tela para o nível informado.
- `system_control.lock_screen` (low): Bloqueia a sessão do Windows; é preciso entrar de novo para continuar.
- `system_tray.enable_boot` (high): Registra o Jarvis para iniciar junto com o Windows.
- `system_tray.disable_boot` (high): Remove o Jarvis da inicialização do Windows.
- `system_tray.status` (observe): Apenas verifica se o Jarvis inicia com o Windows; nada é alterado.
- `task_tool.list` (observe): Apenas lê as tarefas; nada é alterado.
- `task_tool.create` (low): Cria uma tarefa nova.
- `task_tool.create_many` (low): Cria várias tarefas de uma vez; se alguma for inválida, nenhuma é criada.
- `task_tool.update` (low): Altera título, prioridade, projeto ou vencimento da tarefa.
- `task_tool.toggle` (low): Conclui a tarefa ou a reabre.
- `task_tool.delete` (high): Exclui a tarefa.
- `telegram_bot.send` (high): Envia a mensagem pelo Telegram ao chat indicado.
- `telegram_bot.start_bot` (high): Liga o bot do Telegram, que passa a receber comandos dos contatos autorizados.
- `telegram_bot.stop_bot` (low): Para o bot do Telegram.
- `telegram_bot.status` (observe): Apenas verifica se o bot do Telegram está rodando; nada é alterado.
- `timer.set_timer` (low): Cria um timer de contagem regressiva com aviso sonoro neste PC.
- `timer.set_alarm` (low): Cria um alarme para o horário informado, com aviso sonoro neste PC.
- `timer.list` (observe): Apenas lê os timers e alarmes ativos; nada é alterado.
- `timer.cancel` (low): Cancela o timer ou alarme ativo com esse rótulo.
- `vault_daily_log` (low): Acrescenta uma linha com horário ao diário de hoje.
- `vault_save_note` (low): Salva a nota no cofre; uma nota com o mesmo título na mesma pasta é substituída.
- `vault_search` (observe): Apenas procura nas notas do cofre; nada é alterado.
- `vault_update_profile` (low): Acrescenta um fato ou preferência ao seu perfil, que o agente lê nas conversas.
- `vision.analyze_screen` (observe): Apenas captura e analisa a imagem; nada é alterado.
- `vision.analyze_camera` (observe): Apenas captura e analisa a imagem; nada é alterado.
- `wallpaper_engine` (low): Baixa uma imagem e troca o papel de parede da área de trabalho.
- `web_search.search` (observe): Apenas pesquisa e lê resultados; nada é alterado.
- `web_search.research` (observe): Apenas pesquisa e lê resultados; nada é alterado.
- `web_search.open_url` (observe): Apenas pesquisa e lê resultados; nada é alterado.
- `whatsapp` (high): Envia a mensagem pelo WhatsApp ao destinatário.
- `wormhole.start` (high): Expõe a porta local na internet por um link público.
- `wormhole.stop` (low): Encerra o túnel da porta indicada.
- `wormhole.list` (observe): Apenas lista os túneis ativos; nada é alterado.
