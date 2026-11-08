"""Central safety catalog for built-in tools.

Tool implementations stay small; the registration boundary owns the policy
metadata consumed by the Action Kernel.  Unknown/plugin tools intentionally
fall back to their own metadata (or the conservative BaseTool default).
"""
from __future__ import annotations

from typing import Any

from app.core.actions import ActionRisk, ToolMetadata

_MAX_LISTED_PROCESSES = 5
_MESSAGE_EXCERPT = 80


def _by_operation(**levels: tuple[str, ...]) -> tuple[tuple[str, ActionRisk], ...]:
    """Agrupa operações por risco: ``observe=(...), low=(...), high=(...)``."""
    return tuple((operation, risk) for risk, operations in levels.items() for operation in operations)


def _same_text(text: str, *operations: str) -> tuple[tuple[str, str], ...]:
    """Mesma frase para várias operações: ``_same_text("...", "check", "done")``."""
    return tuple((operation, text) for operation in operations)


def _text(arguments: dict[str, Any], *names: str) -> str:
    """Primeiro argumento de texto preenchido entre ``names``."""
    for name in names:
        value = arguments.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _open_app_target_risk(operation: str, arguments: dict[str, Any]) -> ActionRisk:
    """``open`` só é low para app conhecido; nome livre ou caminho de arquivo pede aprovação.

    O caminho de marcadores envia o nome em "command"; as chamadas nativas, em "app_name".
    """
    if operation != "open":
        return "observe"
    from app.services.app_manager import is_known_app_target

    targets = [arguments[name] for name in ("app_name", "command") if name in arguments]
    known = bool(targets) and all(isinstance(t, str) and is_known_app_target(t) for t in targets)
    return "low" if known else "high"


def _open_app_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    """``close``: lista os processos em execução que serão encerrados (só leitura). ``open``: avisa app desconhecido."""
    app_name = _text(arguments, "app_name", "command")
    if operation == "close":
        if not app_name:
            return "nenhum aplicativo informado; nada será encerrado"
        from app.services.app_manager import running_processes_for

        processes = running_processes_for(app_name)
        if not processes:
            return "nenhum processo em execução com esse nome; nada será encerrado"
        shown = [f"{label} ({count} {'processo' if count == 1 else 'processos'})" for label, count in processes[:_MAX_LISTED_PROCESSES]]
        extra = len(processes) - _MAX_LISTED_PROCESSES
        return "encerrar processos: " + ", ".join(shown) + (f" e mais {extra} executável(is)" if extra > 0 else "")
    if operation == "open" and app_name:
        from app.services.app_manager import is_known_app_target

        if not is_known_app_target(app_name):
            return "fora dos aplicativos conhecidos; será iniciado como foi digitado"
    return ""


def _system_control_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    if operation == "set_brightness":
        from app.agent.tools.system_control import parse_brightness_level

        level = parse_brightness_level(arguments.get("level"))
        return f"brilho em {level}%" if level is not None else "nível de brilho inválido; a ferramenta vai recusar"
    return ""


def _finance_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    if operation not in ("add", "create"):
        return ""
    kind = "receita" if str(arguments.get("type", "")).strip().lower() in ("income", "receita", "ganho") else "despesa"
    amount = arguments.get("amount")
    if isinstance(amount, (int, float)) and not isinstance(amount, bool):
        return f"{kind} de R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{kind} sem valor numérico válido"


def _whatsapp_target_detail(_operation: str, arguments: dict[str, Any]) -> str:
    message = _text(arguments, "message")
    if not message:
        return "sem texto de mensagem"
    excerpt = " ".join(message.split())
    return f'mensagem de {len(message)} caracteres: "{excerpt[:_MESSAGE_EXCERPT]}{"…" if len(excerpt) > _MESSAGE_EXCERPT else ""}"'


def _script_target_detail(_operation: str, arguments: dict[str, Any]) -> str:
    language = _text(arguments, "language") or "python"
    return f"script {language[:20]}; o código não é exibido aqui"


def _adb_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    command = _text(arguments, "command")
    if operation == "type_text":
        return f"texto de {len(command)} caracteres (conteúdo protegido)" if command else ""
    if operation in ("shell", "tap_element") and command:
        return ("comando: " if operation == "shell" else "elemento: ") + command[:120]
    if operation in ("push", "pull", "install", "screenshot"):
        path = _text(arguments, "destination", "output_path", "command")
        return f"caminho: {path[:120]}" if path else ""
    x, y = arguments.get("x"), arguments.get("y")
    if operation == "tap_xy" and all(isinstance(v, int) and not isinstance(v, bool) for v in (x, y)):
        return f"posição ({x}, {y})"
    return ""


TOOL_CATALOG: dict[str, ToolMetadata] = {
    # Ferramentas de leitura (C1): a proposta diz que nada é alterado.
    "web_search": ToolMetadata(
        ("web", "observe"), "observe", target_arguments=("query",), default_target="busca na internet",
        effect="Apenas pesquisa e lê resultados; nada é alterado.", reversibility="Nada a desfazer.",
        scope="Só consulta fontes públicas da web.",
    ),
    # Ferramentas de controle têm risco por operação (ToolMetadata.risk_for).
    # Os nomes espelham o despacho de cada ferramenta; o que estiver fora do
    # mapa recebe "critical" e exige aprovação.
    "system_control": ToolMetadata(
        ("system", "control"), "critical",
        # O caminho de marcadores envia a operação em "command".
        operation_arguments=("action", "command"), default_operation="telemetry",
        operation_risks=_by_operation(
            observe=("telemetry", "list_processes", "get_brightness"),
            low=("open_app", "set_brightness", "lock_screen", "media_play_pause", "play", "pause", "media_next", "next",
                 "media_prev", "prev", "previous", "volume_up", "volume_down", "volume_mute"),
        ),
        target_arguments=("app_name",), default_target="este computador", target_detail=_system_control_target_detail,
        operation_effects=(
            ("telemetry", "Apenas lê o uso de CPU e memória; nada é alterado."),
            ("list_processes", "Apenas lê a lista de processos; nada é alterado."),
            ("get_brightness", "Apenas lê o brilho atual da tela; nada é alterado."),
            ("open_app", "Abre o aplicativo informado, se estiver na lista permitida."),
            ("set_brightness", "Ajusta o brilho da tela para o nível informado."),
            ("lock_screen", "Bloqueia a sessão do Windows; é preciso entrar de novo para continuar."),
            *_same_text("Pausa ou retoma a mídia que está tocando.", "media_play_pause", "play", "pause"),
            *_same_text("Pula para a próxima faixa do player ativo.", "media_next", "next"),
            *_same_text("Volta para a faixa anterior do player ativo.", "media_prev", "prev", "previous"),
            ("volume_up", "Aumenta o volume do sistema."),
            ("volume_down", "Diminui o volume do sistema."),
            ("volume_mute", "Liga ou desliga o mudo do sistema."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "telemetry", "list_processes", "get_brightness"),
            ("open_app", "Reversível: feche o aplicativo depois."),
            ("set_brightness", "Reversível: ajuste o brilho de volta; o valor anterior não é guardado."),
            ("lock_screen", "Reversível: desbloqueie com sua senha; nada é perdido."),
            *_same_text("Reversível: acione o mesmo controle de novo.", "media_play_pause", "play", "pause", "volume_mute"),
            *_same_text("Reversível: use o controle da faixa oposta.", "media_next", "next", "media_prev", "prev", "previous"),
            *_same_text("Reversível: use o controle de volume oposto.", "volume_up", "volume_down"),
        ),
        scope="Só este computador; nenhum arquivo é alterado.",
    ),
    "vision": ToolMetadata(
        ("vision", "observe"), "observe", default_target="tela ou câmera deste computador",
        effect="Apenas captura e analisa a imagem; nada é alterado.", reversibility="Nada a desfazer.",
        scope="Só a imagem desta captura.",
    ),
    "realtime": ToolMetadata(
        ("realtime", "observe"), "observe", default_target="dados em tempo real (clima, notícias, finanças)",
        effect="Apenas consulta dados públicos; nada é alterado.", reversibility="Nada a desfazer.",
        scope="Só consulta serviços públicos.",
    ),
    "desktop_search": ToolMetadata(
        ("desktop", "observe"), "observe", target_arguments=("query",), default_target="arquivos deste computador",
        effect="Apenas procura arquivos; nada é alterado.", reversibility="Nada a desfazer.",
        scope="Só pastas permitidas; os arquivos não são abertos nem alterados.",
    ),
    # Só pede ao painel que abra uma janela do registro; não altera dados nem o sistema.
    "open_window": ToolMetadata(
        ("ui", "window"), "observe", target_arguments=("window_id", "command"), default_target="janela do painel",
        effect="Abre uma janela do painel; nenhum dado é alterado.", reversibility="Reversível: feche a janela.",
        scope="Só janelas do registro do painel.",
    ),
    "planning_workspace": ToolMetadata(
        ("planning", "workspace"), "low", reversible=True, default_target="painel de planejamento da conversa",
        effect="Abre, atualiza ou fecha o painel de planejamento desta conversa.",
        reversibility="Reversível: edite o plano ou feche o painel.", scope="Só o plano desta conversa.",
    ),
    "timer": ToolMetadata(
        ("timer", "productivity"), "low", reversible=True, target_arguments=("label",), default_target="timers e alarmes",
        effect="Lista, cria timers de contagem regressiva ou alarmes com horário fixo.",
        reversibility="Reversível: cancele o timer ou o alarme.", scope="Só timers e alarmes do Jarvis.",
    ),
    "calendar": ToolMetadata(
        ("calendar", "productivity"), "low", reversible=True, target_arguments=("title", "query"), default_target="calendário local",
        effect="Lista, cria ou cancela lembretes do calendário local.",
        reversibility="Reversível: cancele o lembrete criado; um lembrete cancelado pode ser criado de novo.",
        scope="Só o calendário local do Jarvis.",
    ),
    "notes": ToolMetadata(
        ("notes", "productivity"), "low", reversible=True, default_target="suas anotações",
        effect="Lê ou cria anotações.", reversibility="Reversível: edite ou apague a anotação criada.",
        scope="Só as anotações do Jarvis.",
    ),
    "whiteboard_add_text": ToolMetadata(
        ("whiteboard", "productivity"), "low", reversible=True, default_target="quadro da conversa",
        effect="Adiciona um texto ao quadro.", reversibility="Reversível: apague o elemento adicionado.",
        scope="Só o quadro desta conversa.",
    ),
    "whiteboard_add_image": ToolMetadata(
        ("whiteboard", "productivity"), "low", reversible=True, default_target="quadro da conversa",
        effect="Adiciona uma imagem ao quadro.", reversibility="Reversível: apague o elemento adicionado.",
        scope="Só o quadro desta conversa.",
    ),
    "whiteboard_edit": ToolMetadata(
        ("whiteboard", "productivity"), "low", reversible=True, default_target="quadro da conversa",
        effect="Altera um elemento do quadro.", reversibility="Reversível: edite o elemento de volta; o conteúdo anterior não é guardado.",
        scope="Só o quadro desta conversa.",
    ),
    "whiteboard_clear": ToolMetadata(
        ("whiteboard", "productivity"), "high", requires_confirmation=True, default_target="quadro da conversa de origem",
        effect="Limpa todos os elementos do quadro.", reversibility="Não reversível: o quadro não oferece desfazer.",
        scope="Todos os elementos do quadro desta conversa.",
    ),
    "open_windows_app": ToolMetadata(
        ("desktop", "application"), "critical",
        operation_arguments=("action",), default_operation="open",
        operation_risks=_by_operation(observe=("list", "status"), low=("open",), high=("close",)),
        target_risk=_open_app_target_risk,
        target_arguments=("app_name", "command"), default_target="aplicativos do Windows",
        target_detail=_open_app_target_detail,
        operation_effects=(
            ("list", "Apenas lê os aplicativos em execução; nada é alterado."),
            ("status", "Apenas verifica se o aplicativo está em execução; nada é alterado."),
            ("open", "Abre o aplicativo, ou traz a janela para a frente se já estiver aberto."),
            ("close", "Encerra todos os processos listados: pede para sair e, se não saírem, força o encerramento."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "list", "status"),
            ("open", "Reversível: feche o aplicativo depois."),
            ("close", "Não reversível: o aplicativo precisa ser aberto de novo e dados não salvos nele se perdem."),
        ),
        scope="Só processos com exatamente o nome do executável indicado; vale o que estiver aberto ao autorizar.",
    ),
    # Módulos pessoais (AQ2). Ler é observe; gravar é low; apagar é high e pede aprovação.
    # A operação é a ação pedida; ação fora do mapa recebe "critical". O padrão de cada
    # ferramenta (``default_operation``) espelha o padrão do seu ``run``.
    "habit_tool": ToolMetadata(
        ("habits", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="list",
        operation_risks=_by_operation(
            observe=("list",),
            low=("create", "update", "check", "complete", "done", "uncheck", "undo"),
            high=("delete",),
        ),
        target_arguments=("name", "habit_id"), default_target="seus hábitos",
        operation_effects=(
            ("list", "Apenas lê os hábitos; nada é alterado."),
            ("create", "Cria um hábito novo."),
            ("update", "Altera dias, horário ou itens de um hábito existente."),
            ("check", "Marca o hábito como concluído hoje."),
            ("complete", "Marca o hábito como concluído hoje."),
            ("done", "Marca o hábito como concluído hoje."),
            ("uncheck", "Desfaz a marcação de hoje do hábito."),
            ("undo", "Desfaz a marcação de hoje do hábito."),
            ("delete", "Remove o hábito."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            ("create", "Reversível: exclua o hábito depois."),
            ("update", "Reversível: edite o hábito de volta; o valor anterior não é guardado."),
            *_same_text("Reversível: desmarque o hábito de hoje.", "check", "complete", "done"),
            *_same_text("Reversível: marque o hábito de novo.", "uncheck", "undo"),
            ("delete", "Não reversível: não há desfazer; recrie o hábito manualmente se precisar."),
        ),
        scope="Só o hábito indicado, nos seus dados.",
    ),
    "task_tool": ToolMetadata(
        ("tasks", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="list",
        operation_risks=_by_operation(
            observe=("list",),
            low=("create", "toggle", "complete", "done"),
            high=("delete",),
        ),
        target_arguments=("title", "task_id"), default_target="suas tarefas",
        operation_effects=(
            ("list", "Apenas lê as tarefas pendentes; nada é alterado."),
            ("create", "Cria uma tarefa nova."),
            ("toggle", "Conclui a tarefa ou a reabre."),
            ("complete", "Conclui a tarefa ou a reabre."),
            ("done", "Conclui a tarefa ou a reabre."),
            ("delete", "Exclui a tarefa."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            ("create", "Reversível: exclua a tarefa depois."),
            *_same_text("Reversível: alterne a tarefa de novo.", "toggle", "complete", "done"),
            ("delete", "Não reversível: não há desfazer; recrie a tarefa manualmente se precisar."),
        ),
        scope="Só a tarefa indicada, nos seus dados.",
    ),
    "finance_tool": ToolMetadata(
        ("finance", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="summary",
        operation_risks=_by_operation(
            observe=("summary", "list"),
            low=("add", "create"),
            high=("delete",),
        ),
        target_arguments=("description", "category", "trans_id"), default_target="suas finanças",
        target_detail=_finance_target_detail,
        operation_effects=(
            ("summary", "Apenas lê o resumo financeiro; nada é alterado."),
            ("list", "Apenas lê os lançamentos recentes; nada é alterado."),
            ("add", "Registra um lançamento de receita ou despesa."),
            ("create", "Registra um lançamento de receita ou despesa."),
            ("delete", "Exclui um lançamento financeiro."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "summary", "list"),
            *_same_text("Reversível: exclua o lançamento depois.", "add", "create"),
            ("delete", "Não reversível: não há desfazer; recrie o lançamento manualmente se precisar."),
        ),
        scope="Só o lançamento indicado; os totais são recalculados.",
    ),
    "lifeos_tool": ToolMetadata(
        ("lifeos", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="summary",
        operation_risks=_by_operation(
            observe=("get_water", "list_habits", "summary", "motivate"),
            low=("add_water", "check_habit", "check", "uncheck_habit", "uncheck", "log_workout"),
        ),
        target_arguments=("habit_name", "workout_name"), default_target="seu Life OS",
        operation_effects=(
            ("get_water", "Apenas lê o consumo de água de hoje; nada é alterado."),
            ("list_habits", "Apenas lê os hábitos do Life OS; nada é alterado."),
            ("summary", "Apenas lê o resumo do dia; nada é alterado."),
            ("motivate", "Apenas lê o resumo do dia para uma mensagem; nada é alterado."),
            ("add_water", "Soma a quantidade informada ao consumo de água de hoje."),
            ("check_habit", "Marca o hábito do Life OS como concluído hoje."),
            ("check", "Marca o hábito do Life OS como concluído hoje."),
            ("uncheck_habit", "Desmarca o hábito do Life OS de hoje."),
            ("uncheck", "Desmarca o hábito do Life OS de hoje."),
            ("log_workout", "Registra o treino de hoje e marca o hábito de treino."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "get_water", "list_habits", "summary", "motivate"),
            *_same_text("Não há desfazer automático; corrija o registro de hoje manualmente.", "add_water", "log_workout"),
            *_same_text("Reversível: desmarque o hábito de hoje.", "check_habit", "check"),
            *_same_text("Reversível: marque o hábito de novo.", "uncheck_habit", "uncheck"),
        ),
        scope="Só o registro de hoje, nos seus dados.",
    ),
    "spotify": ToolMetadata(
        ("media",), "low", default_target="Spotify neste computador",
        effect="Controla a reprodução do Spotify (pausar, pular, abrir ou tocar uma busca).",
        reversibility="Reversível: acione o controle oposto ou pause.", scope="Só o player do Spotify.",
    ),
    "clipboard": ToolMetadata(
        ("clipboard",), "low", default_target="área de transferência",
        effect="Lê o histórico ou copia um texto para a área de transferência, substituindo o conteúdo atual.",
        reversibility="Não reversível: o conteúdo anterior da área de transferência não é guardado.",
        scope="Só a área de transferência deste computador.",
    ),
    "whatsapp": ToolMetadata(
        ("messaging",), "high", requires_confirmation=True, target_arguments=("target",),
        default_target="contato do WhatsApp", target_detail=_whatsapp_target_detail,
        effect="Envia a mensagem pelo WhatsApp ao destinatário.",
        reversibility="Não reversível: a mensagem enviada não pode ser retirada por aqui.",
        scope="Só este destinatário e esta mensagem.",
    ),
    "browser_agent": ToolMetadata(
        ("browser", "automation"), "high", requires_confirmation=True, target_arguments=("goal",),
        default_target="navegador automatizado",
        effect="Controla um navegador: abre páginas, clica e digita para cumprir o objetivo (até 10 passos).",
        reversibility="Não garantida: cliques e formulários enviados em sites não são desfeitos.",
        scope="Só a sessão do navegador automatizado, sem acesso a outros programas.",
    ),
    "file_manager": ToolMetadata(
        ("files",), "high", requires_confirmation=True,
        operation_arguments=("action",), default_operation="list",
        target_arguments=("path",), default_target="pasta de trabalho do Jarvis",
        operation_effects=(
            ("list", "Lista o conteúdo da pasta; nada é alterado."),
            ("read", "Lê o conteúdo do arquivo; nada é alterado."),
        ),
        operation_reversibility=_same_text("Nada a desfazer.", "list", "read"),
        scope="Só a pasta de trabalho do Jarvis e este caminho.",
    ),
    "script_runner": ToolMetadata(
        ("script", "system"), "critical", requires_confirmation=True, target_arguments=("description",),
        default_target="script no computador", target_detail=_script_target_detail,
        effect="Executa o script neste computador com as permissões do seu usuário.",
        reversibility="Não garantida: depende do que o script faz; trate como irreversível.",
        scope="Este computador e tudo que o seu usuário do Windows pode alterar.",
    ),
    "hacker_mode": ToolMetadata(
        ("script", "system"), "critical", requires_confirmation=True, target_arguments=("command", "script"),
        default_target="terminal deste computador",
        effect="Executa o comando no terminal, depois da análise de risco.",
        reversibility="Não garantida: depende do comando; trate como irreversível.",
        scope="Este computador, com as permissões do seu usuário.",
    ),
    "mobile_adb": ToolMetadata(
        ("mobile", "automation"), "high", requires_confirmation=True,
        operation_arguments=("action",), default_operation="devices",
        target_arguments=("device_serial",), default_target="celular conectado por ADB",
        target_detail=_adb_target_detail,
        operation_effects=(
            *_same_text("Apenas lê informações do celular; nada é alterado.", "devices", "dump_ui", "logcat"),
            ("screenshot", "Tira uma captura da tela do celular e salva um arquivo neste computador."),
            *_same_text("Interage com a tela do celular como um toque ou digitação.", "tap_element", "tap_xy", "type_text", "swipe", "press_key"),
            ("shell", "Executa um comando dentro do celular."),
            ("install", "Instala um aplicativo no celular."),
            ("push", "Envia um arquivo deste computador para o celular."),
            ("pull", "Copia um arquivo do celular para este computador."),
            ("reboot", "Reinicia o celular."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "devices", "dump_ui", "logcat"),
            ("screenshot", "Reversível: apague o arquivo salvo."),
            *_same_text("Não garantida: o app do celular pode reagir ao toque ou ao texto de forma que não se desfaz.", "tap_element", "tap_xy", "type_text", "swipe", "press_key"),
            ("shell", "Não garantida: depende do comando; trate como irreversível."),
            ("install", "Reversível: desinstale o aplicativo depois."),
            ("push", "Reversível: apague o arquivo enviado; um arquivo de mesmo nome é substituído."),
            ("pull", "Reversível: apague a cópia; um arquivo de mesmo nome neste computador é substituído."),
            ("reboot", "Não reversível: o celular reinicia e o que estava aberto é fechado."),
        ),
        scope="Só o celular conectado por ADB.",
    ),
    "kasa_control": ToolMetadata(
        ("device", "automation"), "high", requires_confirmation=True,
        operation_arguments=("action",), default_operation="discover",
        target_arguments=("device_alias", "device_ip"), default_target="dispositivos Kasa da rede local",
        operation_effects=(
            ("discover", "Procura dispositivos Kasa na rede; nada é alterado."),
            ("status", "Apenas lê o estado do dispositivo; nada é alterado."),
            ("on", "Liga o dispositivo."),
            ("off", "Desliga o dispositivo."),
            ("toggle", "Inverte o estado do dispositivo (liga se estiver desligado e vice-versa)."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "discover", "status"),
            *_same_text("Reversível: acione o dispositivo de novo.", "on", "off", "toggle"),
        ),
        scope="Só o dispositivo indicado na rede local.",
    ),
    "workflow": ToolMetadata(
        ("workflow",), "high", requires_confirmation=True, target_arguments=("recipe_id",),
        default_target="receita de workflow",
        effect="Só simula a receita: mostra as etapas sem executá-las.", reversibility="Nada a desfazer: nada é executado.",
        scope="Somente simulação; nenhuma etapa roda de verdade.",
    ),
}


def metadata_for(tool_name: str, fallback: ToolMetadata) -> ToolMetadata:
    return TOOL_CATALOG.get(tool_name, fallback)
