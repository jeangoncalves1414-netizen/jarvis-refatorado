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


_MAX_BATCH_NAMES = 6


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _batch_names(items: Any, field: str, singular: str, plural: str) -> str:
    """"3 hábitos: Ler, Correr, Meditar" para listas de objetos (ou de textos, com ``field`` vazio)."""
    if not isinstance(items, list) or not items:
        return f"nenhum {singular} informado; a ferramenta vai recusar"
    names = []
    for item in items:
        value = item.get(field) if isinstance(item, dict) and field else item
        names.append(str(value).strip()[:40] if isinstance(value, str) and value.strip() else "(sem nome)")
    extra = len(names) - _MAX_BATCH_NAMES
    shown = ", ".join(names[:_MAX_BATCH_NAMES]) + (f" e mais {extra}" if extra > 0 else "")
    return f"{len(names)} {singular if len(names) == 1 else plural}: {shown}"


def _habit_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    if operation == "create_many":
        return _batch_names(arguments.get("habits"), "name", "hábito", "hábitos")
    if operation == "check_many":
        return _batch_names(arguments.get("names"), "", "hábito", "hábitos")
    return ""


def _task_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    if operation == "create_many":
        return _batch_names(arguments.get("tasks"), "title", "tarefa", "tarefas")
    return ""


def _finance_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    if operation == "add_many":
        entries = arguments.get("entries")
        if not isinstance(entries, list) or not entries:
            return "nenhum lançamento informado; a ferramenta vai recusar"
        amounts = [entry.get("amount") for entry in entries if isinstance(entry, dict)]
        if len(amounts) != len(entries) or not all(_is_number(a) for a in amounts):
            return f"{len(entries)} lançamentos, algum sem valor numérico válido"
        noun = "lançamento" if len(entries) == 1 else "lançamentos"
        return f"{len(entries)} {noun}, total {_brl(float(sum(amounts)))}"
    if operation not in ("add", "create"):
        return ""
    kind = "receita" if str(arguments.get("type", "")).strip().lower() in ("income", "receita", "ganho") else "despesa"
    amount = arguments.get("amount")
    if _is_number(amount):
        return f"{kind} de {_brl(float(amount))}"
    return f"{kind} sem valor numérico válido"


def _lifeos_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    if operation == "set_water":
        total = arguments.get("total_ml")
        return f"total do dia: {int(total):,} ml".replace(",", ".") if _is_number(total) else "total de água inválido; a ferramenta vai recusar"
    if operation == "add_water":
        amount = arguments.get("amount", 250)
        return f"somar {int(amount):,} ml".replace(",", ".") if _is_number(amount) else "quantidade inválida; a ferramenta vai recusar"
    return ""


def _calendar_target_detail(operation: str, arguments: dict[str, Any]) -> str:
    if operation == "create_many":
        return _batch_names(arguments.get("reminders"), "title", "lembrete", "lembretes")
    if operation == "create_reminder":
        start = _text(arguments, "start")
        return f"em {start[:16].replace('T', ' ')}" if start else ""
    return ""


def _home_target_risk(operation: str, arguments: dict[str, Any]) -> ActionRisk:
    from app.services.home_assistant import target_risk

    return target_risk(operation, _text(arguments, "entity"))


def _document_target_risk(_operation: str, arguments: dict[str, Any]) -> ActionRisk:
    """Caminho de saída livre pode sobrescrever qualquer arquivo: pede aprovação."""
    return "high" if _text(arguments, "output_path") else "low"


def _document_target_detail(_operation: str, arguments: dict[str, Any]) -> str:
    path = _text(arguments, "output_path")
    return f"salvar em {path[:120]} (substitui arquivo de mesmo nome)" if path else "salvar em data/exports/"


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
        ("timer", "productivity"), "critical", reversible=True,
        operation_arguments=("action",), default_operation="list",
        operation_risks=_by_operation(observe=("list",), low=("set_timer", "set_alarm", "cancel")),
        target_arguments=("label", "duration", "time"), default_target="timers e alarmes",
        operation_effects=(
            ("list", "Apenas lê os timers e alarmes ativos; nada é alterado."),
            ("set_timer", "Cria um timer de contagem regressiva com aviso sonoro neste PC."),
            ("set_alarm", "Cria um alarme para o horário informado, com aviso sonoro neste PC."),
            ("cancel", "Cancela o timer ou alarme ativo com esse rótulo."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            *_same_text("Reversível: cancele o timer ou o alarme.", "set_timer", "set_alarm"),
            ("cancel", "Reversível: crie o timer ou o alarme de novo."),
        ),
        scope="Só timers e alarmes do Jarvis; somem se o backend reiniciar.",
    ),
    # Espera real entre ações (risco low para aparecer na Central sem "incluir leituras").
    "wait": ToolMetadata(
        ("wait", "control"), "low", reversible=True, default_target="pausa entre ações",
        effect="Apenas espera; nada é alterado.",
        reversibility="Nada a desfazer; use 'Parar pedido' para interromper a espera.",
        scope="Só este pedido; as próximas etapas esperam o fim da pausa.",
    ),
    # Rotinas gravadas. Criar ou executar é low: cada etapa passa pelo Kernel com o próprio risco
    # na hora de rodar (etapa alta ou crítica pede aprovação, salvo regra ou Modo liberado).
    "routine": ToolMetadata(
        ("routine", "automation"), "critical", reversible=True,
        operation_arguments=("action",), default_operation="list",
        operation_risks=_by_operation(
            observe=("list", "next_runs"),
            low=("create", "update", "enable", "disable", "run_now"),
            high=("delete",),
        ),
        target_arguments=("name", "routine_id"), default_target="suas rotinas",
        operation_effects=(
            ("list", "Apenas lê as rotinas e a próxima execução; nada é alterado."),
            ("next_runs", "Apenas lê as próximas execuções agendadas; nada é alterado."),
            ("create", "Grava uma rotina nova com etapas e gatilhos; cada etapa passa pela aprovação do próprio risco ao rodar."),
            ("update", "Altera nome, etapas, gatilhos, silêncio ou tolerância de uma rotina existente."),
            ("enable", "Ativa a rotina: os gatilhos de horário voltam a disparar."),
            ("disable", "Desativa a rotina: os gatilhos de horário param de disparar."),
            ("run_now", "Executa a rotina agora; cada etapa passa pela aprovação do próprio risco."),
            ("delete", "Apaga a rotina e o histórico de execuções dela."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "list", "next_runs"),
            ("create", "Reversível: apague ou desative a rotina."),
            ("update", "Reversível: edite a rotina de volta; a versão anterior não é guardada."),
            ("enable", "Reversível: desative a rotina."),
            ("disable", "Reversível: ative a rotina."),
            ("run_now", "Não garantida: depende das etapas; elas não são desfeitas automaticamente."),
            ("delete", "Não reversível: a rotina e o histórico somem; recrie manualmente se precisar."),
        ),
        scope="Só a rotina indicada, neste computador (rotinas não sincronizam).",
    ),
    "calendar": ToolMetadata(
        ("calendar", "productivity"), "critical", reversible=True,
        operation_arguments=("action",), default_operation="list",
        operation_risks=_by_operation(observe=("list",), low=("create_reminder", "create_many", "cancel_reminder")),
        target_arguments=("title", "query"), default_target="calendário local", target_detail=_calendar_target_detail,
        operation_effects=(
            ("list", "Apenas lê os compromissos do calendário; nada é alterado."),
            ("create_reminder", "Cria um lembrete no calendário local."),
            ("create_many", "Cria vários lembretes no calendário local de uma vez."),
            ("cancel_reminder", "Para os avisos do lembrete indicado."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            *_same_text("Reversível: cancele o lembrete criado; um lembrete cancelado pode ser criado de novo.", "create_reminder", "create_many"),
            ("cancel_reminder", "Reversível: crie o lembrete de novo."),
        ),
        scope="Só o calendário local do Jarvis.",
    ),
    "open_screen": ToolMetadata(
        ("ui", "screen"), "observe", target_arguments=("screen", "command"), default_target="tela do app",
        effect="Muda o app para a tela indicada; nenhum dado é alterado.", reversibility="Reversível: volte para a tela anterior.",
        scope="Só as telas do app.",
    ),
    "show_popup": ToolMetadata(
        ("ui", "popup"), "observe", target_arguments=("template", "command"), default_target="popup do painel",
        effect="Mostra um popup do painel; nenhum dado é alterado.", reversibility="Reversível: feche o popup.",
        scope="Só a camada de popups do painel.",
    ),
    "places_search": ToolMetadata(
        ("places", "observe"), "observe", target_arguments=("query", "command"), default_target="busca de lugares",
        effect="Envia o texto da busca ao provedor de mapas e lê os resultados; nada é alterado.",
        reversibility="Nada a desfazer.",
        scope="Envia o texto da busca ao OpenStreetMap ou ao Google (só com chave configurada).",
    ),
    # Cofre de memória (Markdown local, sincronizado com o celular).
    "vault_search": ToolMetadata(
        ("vault", "observe"), "observe", target_arguments=("query",), default_target="cofre de memória",
        effect="Apenas procura nas notas do cofre; nada é alterado.", reversibility="Nada a desfazer.",
        scope="Só as notas do cofre.",
    ),
    "vault_daily_log": ToolMetadata(
        ("vault", "notes"), "low", reversible=True, target_arguments=("category",), default_target="diário de hoje no cofre",
        effect="Acrescenta uma linha com horário ao diário de hoje.",
        reversibility="Reversível: edite ou apague a linha no arquivo do diário no cofre.", scope="Só o diário de hoje.",
    ),
    "vault_save_note": ToolMetadata(
        ("vault", "notes"), "low", reversible=True, target_arguments=("title",), default_target="nota no cofre",
        effect="Salva a nota no cofre; uma nota com o mesmo título na mesma pasta é substituída.",
        reversibility="Reversível: edite ou apague o arquivo no cofre; o conteúdo substituído não é guardado.",
        scope="Só a pasta do cofre indicada (01-Daily-Notes, 03-Priming-Notes, 04-Projects ou 05-Notas).",
    ),
    "vault_update_profile": ToolMetadata(
        ("vault", "profile"), "low", reversible=True, default_target="seu perfil no cofre (USER-PROFILE.md)",
        effect="Acrescenta um fato ou preferência ao seu perfil, que o agente lê nas conversas.",
        reversibility="Reversível: edite ou apague a linha no arquivo do perfil no cofre.", scope="Só o arquivo do perfil.",
    ),
    # Auditoria do lote 6 (decisão 14): leitura = observe; efeito local reversível = low;
    # digitar no PC, enviar mensagem, mudar a inicialização do Windows, expor porta ou
    # mover arquivos em massa = high com confirmação.
    "cinema": ToolMetadata(
        ("media", "web"), "critical",
        operation_arguments=("action",), default_operation="search",
        operation_risks=_by_operation(observe=("search", "discover", "detect_url"), low=("play",)),
        target_arguments=("query", "imdb_id", "url"), default_target="busca de filmes e séries",
        operation_effects=(
            ("search", "Apenas pesquisa o catálogo de filmes e séries; nada é alterado."),
            ("discover", "Apenas pesquisa fontes aprovadas; nada é alterado."),
            ("detect_url", "Apenas analisa a página informada; nada é alterado."),
            ("play", "Abre o player do título no painel."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "search", "discover", "detect_url"),
            ("play", "Reversível: feche o player."),
        ),
        scope="Só consulta catálogos públicos e o player do painel.",
    ),
    "clipboard_intelligence": ToolMetadata(
        ("clipboard", "observe"), "critical",
        operation_arguments=("action",), default_operation="read",
        operation_risks=_by_operation(observe=("read", "refactor", "explain_error", "translate", "summarize")),
        default_target="texto copiado na área de transferência",
        operation_effects=(
            ("read", "Apenas lê o texto copiado; nada é alterado."),
            *_same_text("Apenas lê o texto copiado e prepara o pedido para a resposta; nada é alterado.", "refactor", "explain_error", "translate", "summarize"),
        ),
        reversibility="Nada a desfazer.", scope="Só o texto copiado agora; a área de transferência não muda.",
    ),
    "document_generator": ToolMetadata(
        ("files", "documents"), "critical", reversible=True,
        operation_arguments=("format",), default_operation="pdf",
        operation_risks=_by_operation(low=("pptx", "xlsx", "pdf")),
        target_risk=_document_target_risk,
        target_arguments=("title",), default_target="documento novo", target_detail=_document_target_detail,
        operation_effects=(
            ("pptx", "Gera uma apresentação PowerPoint e salva o arquivo."),
            ("xlsx", "Gera uma planilha Excel e salva o arquivo."),
            ("pdf", "Gera um PDF e salva o arquivo."),
        ),
        reversibility="Reversível: apague o arquivo gerado; um arquivo de mesmo nome é substituído.",
        scope="Só o arquivo gerado; caminho próprio pede aprovação.",
    ),
    "image_generator": ToolMetadata(
        ("image", "web"), "low", target_arguments=("size",), default_target="gerador de imagens (Oxyy)",
        effect="Envia a descrição ao serviço de imagens e devolve o link da imagem gerada; pode consumir créditos.",
        reversibility="Nada a desfazer neste computador; o uso de créditos não volta.", scope="Só esta geração.",
    ),
    "jarvis_mode": ToolMetadata(
        ("ui", "mode"), "critical", reversible=True,
        operation_arguments=("command",), default_operation="",
        operation_risks=_by_operation(low=("silent", "hybrid", "call_mode")),
        default_target="modo de interação do assistente",
        operation_effects=(
            ("silent", "Desliga a fala das respostas (só texto)."),
            ("hybrid", "Volta a falar as respostas."),
            ("call_mode", "Abre a interface de ligação por voz."),
        ),
        effect="Troca o modo de interação do assistente (silencioso, com voz ou ligação).",
        reversibility="Reversível: escolha outro modo.", scope="Só o modo do assistente neste app.",
    ),
    "news_reader": ToolMetadata(
        ("news", "observe"), "observe", target_arguments=("feed_url",), default_target="manchetes de notícias (RSS)",
        effect="Apenas lê manchetes de um feed RSS; nada é alterado.", reversibility="Nada a desfazer.",
        scope="Só consulta o feed público.",
    ),
    "phantom_typer": ToolMetadata(
        ("desktop", "keyboard"), "high", requires_confirmation=True, default_target="janela ativa do Windows",
        target_detail=lambda _op, args: f"texto de {len(_text(args, 'text'))} caracteres" if _text(args, "text") else "sem texto",
        effect="Cola o texto na janela que estiver ativa, como se fosse digitado pela usuária.",
        reversibility="Não garantida: o programa que recebe o texto pode enviá-lo ou executá-lo; use Ctrl+Z se ele permitir.",
        scope="A janela que estiver em foco no momento da execução.",
    ),
    "proactive_agent": ToolMetadata(
        ("proactive", "productivity"), "critical", reversible=True,
        operation_arguments=("action",), default_operation="get_status",
        operation_risks=_by_operation(observe=("get_status", "trigger_briefing"), low=("configure_briefing", "add_reminder")),
        target_arguments=("briefing_time", "reminder_time"), default_target="assistente proativo (briefing e lembretes)",
        operation_effects=(
            ("get_status", "Apenas lê a configuração do briefing e os lembretes; nada é alterado."),
            ("trigger_briefing", "Apenas monta o briefing agora; nada é alterado."),
            ("configure_briefing", "Altera horário, tópicos ou instruções do briefing matinal."),
            ("add_reminder", "Agenda um lembrete do assistente proativo."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "get_status", "trigger_briefing"),
            ("configure_briefing", "Reversível: configure o briefing de volta; o valor anterior não é guardado."),
            ("add_reminder", "Reversível: o lembrete é avisado uma vez e some."),
        ),
        scope="Só as configurações do assistente proativo.",
    ),
    "qr_reader": ToolMetadata(
        ("vision", "observe"), "critical",
        operation_arguments=("source",), default_operation="screen",
        operation_risks=_by_operation(observe=("screen", "camera")),
        default_target="tela ou câmera deste computador",
        operation_effects=(
            ("screen", "Apenas captura a tela e lê QR codes; nada é alterado."),
            ("camera", "Apenas liga a câmera por alguns segundos para ler QR codes; nada é alterado."),
        ),
        reversibility="Nada a desfazer.", scope="Só a captura desta leitura.",
    ),
    "screen_peeler": ToolMetadata(
        ("vision", "clipboard"), "low", default_target="tela atual e área de transferência",
        effect="Captura a tela, extrai o texto com o serviço de visão e copia o texto para a área de transferência.",
        reversibility="Não reversível: o conteúdo anterior da área de transferência não é guardado.",
        scope="A tela inteira no momento da captura.",
    ),
    "smart_drop_zone": ToolMetadata(
        ("files", "organize"), "high", requires_confirmation=True, target_arguments=("target_folder",),
        default_target="pasta Downloads",
        effect="Move os arquivos soltos da pasta para subpastas por tipo (Documentos, Imagens, Compactados, Executaveis, Codigos).",
        reversibility="Reversível com trabalho: os arquivos continuam nas subpastas da mesma pasta, mas é preciso movê-los de volta à mão.",
        scope="Só os arquivos soltos de Downloads ou da Área de Trabalho; subpastas não são mexidas.",
    ),
    "system_tray": ToolMetadata(
        ("system", "startup"), "critical",
        operation_arguments=("action",), default_operation="status",
        operation_risks=_by_operation(observe=("status",), high=("enable_boot", "disable_boot")),
        default_target="inicialização automática do Windows",
        operation_effects=(
            ("status", "Apenas verifica se o Jarvis inicia com o Windows; nada é alterado."),
            ("enable_boot", "Registra o Jarvis para iniciar junto com o Windows."),
            ("disable_boot", "Remove o Jarvis da inicialização do Windows."),
        ),
        operation_reversibility=(
            ("status", "Nada a desfazer."),
            ("enable_boot", "Reversível: desative a inicialização automática depois."),
            ("disable_boot", "Reversível: ative a inicialização automática de novo."),
        ),
        scope="Só a entrada do Jarvis na inicialização do Windows do seu usuário.",
    ),
    "telegram_bot": ToolMetadata(
        ("messaging",), "critical",
        operation_arguments=("action",), default_operation="status",
        operation_risks=_by_operation(observe=("status",), low=("stop_bot",), high=("send", "start_bot")),
        target_arguments=("chat_id",), default_target="Telegram",
        target_detail=lambda op, args: _whatsapp_target_detail(op, args) if op == "send" else "",
        operation_effects=(
            ("status", "Apenas verifica se o bot do Telegram está rodando; nada é alterado."),
            ("stop_bot", "Para o bot do Telegram."),
            ("send", "Envia a mensagem pelo Telegram ao chat indicado."),
            ("start_bot", "Liga o bot do Telegram, que passa a receber comandos dos contatos autorizados."),
        ),
        operation_reversibility=(
            ("status", "Nada a desfazer."),
            ("stop_bot", "Reversível: ligue o bot de novo."),
            ("send", "Não reversível: a mensagem enviada não pode ser retirada por aqui."),
            ("start_bot", "Reversível: pare o bot depois."),
        ),
        scope="Só o bot do Telegram configurado neste computador.",
    ),
    "wallpaper_engine": ToolMetadata(
        ("desktop", "appearance"), "low", target_arguments=("query", "image_url"), default_target="papel de parede do Windows",
        effect="Baixa uma imagem e troca o papel de parede da área de trabalho.",
        reversibility="Reversível: escolha outro papel de parede; o anterior não é guardado.",
        scope="Só o papel de parede do seu usuário.",
    ),
    "wormhole": ToolMetadata(
        ("network", "tunnel"), "critical",
        operation_arguments=("action",), default_operation="list",
        operation_risks=_by_operation(observe=("list",), low=("stop",), high=("start",)),
        target_arguments=("port",), default_target="túneis de rede",
        operation_effects=(
            ("list", "Apenas lista os túneis ativos; nada é alterado."),
            ("stop", "Encerra o túnel da porta indicada."),
            ("start", "Expõe a porta local na internet por um link público."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            ("stop", "Reversível: abra o túnel de novo."),
            ("start", "Reversível: encerre o túnel; quem acessou enquanto ele estava aberto não é desfeito."),
        ),
        scope="Só a porta indicada deste computador.",
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
            low=("create", "create_many", "update", "check", "check_many", "complete", "done", "uncheck", "undo"),
            high=("delete",),
        ),
        target_arguments=("name", "habit_id"), default_target="seus hábitos", target_detail=_habit_target_detail,
        operation_effects=(
            ("list", "Apenas lê os hábitos; nada é alterado."),
            ("create", "Cria um hábito novo."),
            ("create_many", "Cria vários hábitos de uma vez; se algum for inválido, nenhum é criado."),
            ("update", "Altera nome, categoria, período, dias, horário ou itens de um hábito existente."),
            ("check_many", "Marca vários hábitos como concluídos hoje."),
            ("check", "Marca o hábito como concluído hoje."),
            ("complete", "Marca o hábito como concluído hoje."),
            ("done", "Marca o hábito como concluído hoje."),
            ("uncheck", "Desfaz a marcação de hoje do hábito."),
            ("undo", "Desfaz a marcação de hoje do hábito."),
            ("delete", "Remove o hábito."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            *_same_text("Reversível: exclua o hábito depois.", "create", "create_many"),
            ("update", "Reversível: edite o hábito de volta; o valor anterior não é guardado."),
            *_same_text("Reversível: desmarque o hábito de hoje.", "check", "check_many", "complete", "done"),
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
            low=("create", "create_many", "update", "toggle", "complete", "done"),
            high=("delete",),
        ),
        target_arguments=("title", "task_id"), default_target="suas tarefas", target_detail=_task_target_detail,
        operation_effects=(
            ("list", "Apenas lê as tarefas; nada é alterado."),
            ("create", "Cria uma tarefa nova."),
            ("create_many", "Cria várias tarefas de uma vez; se alguma for inválida, nenhuma é criada."),
            ("update", "Altera título, prioridade, projeto ou vencimento da tarefa."),
            ("toggle", "Conclui a tarefa ou a reabre."),
            ("complete", "Conclui a tarefa ou a reabre."),
            ("done", "Conclui a tarefa ou a reabre."),
            ("delete", "Exclui a tarefa."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            *_same_text("Reversível: exclua a tarefa depois.", "create", "create_many"),
            ("update", "Reversível: edite a tarefa de volta; o valor anterior não é guardado."),
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
            low=("add", "create", "add_many", "update"),
            high=("delete",),
        ),
        target_arguments=("description", "category", "trans_id"), default_target="suas finanças",
        target_detail=_finance_target_detail,
        operation_effects=(
            ("summary", "Apenas lê o resumo financeiro; nada é alterado."),
            ("list", "Apenas lê os lançamentos do período; nada é alterado."),
            ("add", "Registra um lançamento de receita ou despesa."),
            ("create", "Registra um lançamento de receita ou despesa."),
            ("add_many", "Registra vários lançamentos de uma vez; se algum for inválido, nenhum é gravado."),
            ("update", "Corrige valor, tipo, categoria, descrição ou data de um lançamento."),
            ("delete", "Exclui um lançamento financeiro."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "summary", "list"),
            *_same_text("Reversível: exclua o lançamento depois.", "add", "create", "add_many"),
            ("update", "Reversível: corrija o lançamento de volta; o valor anterior não é guardado."),
            ("delete", "Não reversível: não há desfazer; recrie o lançamento manualmente se precisar."),
        ),
        scope="Só o lançamento indicado; os totais são recalculados.",
    ),
    "lifeos_tool": ToolMetadata(
        ("lifeos", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="summary",
        operation_risks=_by_operation(
            observe=("get_water", "list_habits", "summary", "motivate"),
            low=("add_water", "set_water", "check_habit", "check", "uncheck_habit", "uncheck", "log_workout"),
        ),
        target_arguments=("habit_name", "workout_name"), default_target="seu Life OS", target_detail=_lifeos_target_detail,
        operation_effects=(
            ("get_water", "Apenas lê o consumo de água de hoje; nada é alterado."),
            ("list_habits", "Apenas lê os hábitos do Life OS; nada é alterado."),
            ("summary", "Apenas lê o resumo do dia; nada é alterado."),
            ("motivate", "Apenas lê o resumo do dia para uma mensagem; nada é alterado."),
            ("add_water", "Soma a quantidade informada ao consumo de água de hoje."),
            ("set_water", "Define o total de água de hoje no valor informado."),
            ("check_habit", "Marca o hábito do Life OS como concluído hoje."),
            ("check", "Marca o hábito do Life OS como concluído hoje."),
            ("uncheck_habit", "Desmarca o hábito do Life OS de hoje."),
            ("uncheck", "Desmarca o hábito do Life OS de hoje."),
            ("log_workout", "Registra o treino de hoje e marca o hábito de treino."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "get_water", "list_habits", "summary", "motivate"),
            *_same_text("Não há desfazer automático; corrija o registro de hoje manualmente.", "add_water", "log_workout"),
            ("set_water", "Reversível: defina o total de novo; o valor anterior aparece no resultado."),
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
    # Fase contexto 2: memórias com fonte; só pelo Kernel (run_action), não é oferecida ao modelo.
    "memory_tool": ToolMetadata(
        ("memory",), "low",
        operation_arguments=("operation",), default_operation="save",
        operation_risks=_by_operation(observe=("list",), low=("save", "update", "delete")),
        target_arguments=("text", "id"), default_target="memórias com fonte",
        operation_effects=(
            ("list", "Apenas lê as memórias com fonte; nada é alterado."),
            ("save", "Grava a memória com a data, a conversa e a origem."),
            ("update", "Troca o texto da memória e recalcula a preferência."),
            ("delete", "Remove a memória (fica uma lápide local com a data)."),
        ),
        operation_reversibility=(
            ("list", "Nada a desfazer."),
            ("save", "Reversível: remova a memória em Memórias > Com fonte."),
            ("update", "Reversível: edite o texto de volta; o anterior não é guardado."),
            ("delete", "Não há desfazer automático; salve a memória de novo se precisar."),
        ),
        effect="Grava, edita ou remove uma memória com fonte.",
        reversibility="Reversível: edite ou remova em Memórias > Com fonte.",
        scope="Só o arquivo de memórias do app.",
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
    # Fase contexto 3: Home Assistant opcional; o risco sobe pelo domínio da entidade.
    "home": ToolMetadata(
        ("home", "device"), "high",
        operation_arguments=("operation",), default_operation="list_entities",
        operation_risks=_by_operation(
            observe=("list_entities", "get_state"),
            low=("turn_on", "turn_off", "toggle", "set", "run_scene"), high=("run_script",),
        ),
        target_risk=_home_target_risk,
        target_arguments=("entity",), default_target="casa (Home Assistant)",
        operation_effects=(
            ("list_entities", "Apenas lista os aparelhos do Home Assistant; nada é alterado."),
            ("get_state", "Apenas lê o estado do aparelho; nada é alterado."),
            ("turn_on", "Liga o aparelho (fechadura: tranca; cortina: abre)."),
            ("turn_off", "Desliga o aparelho (fechadura: destranca; cortina: fecha)."),
            ("toggle", "Inverte o estado do aparelho."),
            ("set", "Ajusta o brilho da luz ou a temperatura do climatizador."),
            ("run_scene", "Ativa a cena: vários aparelhos mudam de uma vez."),
            ("run_script", "Executa o script do Home Assistant, que pode acionar qualquer aparelho."),
        ),
        operation_reversibility=(
            *_same_text("Nada a desfazer.", "list_entities", "get_state"),
            *_same_text("Reversível: acione o aparelho de novo.", "turn_on", "turn_off", "toggle"),
            ("set", "Reversível: ajuste de volta; o valor anterior não é guardado."),
            *_same_text("Não garantida: depende do que a cena ou o script faz.", "run_scene", "run_script"),
        ),
        scope="Só a entidade indicada no Home Assistant configurado.",
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
