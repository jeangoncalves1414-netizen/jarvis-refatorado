from __future__ import annotations

import re
from typing import Any
from .base import BaseTool, ToolResult
from .file_manager import FileManagerTool
from .system_control import SystemControlTool
from .jarvis_mode import JarvisModeTool
from .web_search import WebSearchTool
from .browser_agent import BrowserAgentTool
from .timer import TimerTool
from .wait import WaitTool
from .whatsapp import WhatsAppTool
from .spotify import SpotifyTool
from .whiteboard import WhiteboardAddTextTool, WhiteboardAddImageTool, WhiteboardClearTool, WhiteboardEditTool
from .clipboard import ClipboardTool, NewsTool
from .open_windows_app import OpenWindowsAppTool
from .script_runner import ScriptRunnerTool
from .vision_tool import VisionTool
from .qr_reader_tool import QRReaderTool
from .realtime_tool import RealTimeTool
from .cinema_tool import CinemaTool
from .calendar_tool import CalendarTool
try:
    from .system_tray_tool import SystemTrayTool
    TRAY_TOOL_AVAILABLE = True
except ImportError:
    TRAY_TOOL_AVAILABLE = False
from .tutor_tools import (
    TutorSaveProgressTool,
    TutorAddFlashcardTool,
    TutorSaveFeynmanTool,
    EnemSaveQuestionTool,
)
from .screen_peeler import ScreenPeelerTool
from .phantom_typer import PhantomTyperTool
from .smart_drop_zone import SmartDropZoneTool
from .wormhole import WormholeTool
from .wallpaper_engine import WallpaperEngineTool
from .clipboard_intelligence import ClipboardIntelligenceTool
from .home_tool import HomeTool

from .memory_vault_tool import (
    VaultSearchTool,
    VaultDailyNoteTool,
    VaultSaveNoteTool,
    VaultUserProfileTool,
)

# Fase 5 tools
try:
    from .desktop_search import DesktopSearchTool
    from .kasa_control import KasaControlTool
    from .document_generator import DocumentGeneratorTool
    from .telegram_bot import TelegramBotTool
    from .mobile_adb import MobileTelekinesisADB
    FASE5_TOOLS_AVAILABLE = True
except ImportError:
    FASE5_TOOLS_AVAILABLE = False

try:
    from .code_helper import CodeHelperTool
    from .image_generator import ImageGeneratorTool
    from .hacker_mode import HackerModeTool
    from .workflow import WorkflowTool
    from .mcp_tool import MCPTool
    from .dev_agent import DevAgentTool
    from .proactive_agent import ProactiveAgentTool
    ADVANCED_TOOLS_AVAILABLE = True
except ImportError:
    ADVANCED_TOOLS_AVAILABLE = False

from .lifestyle_tools import HabitTool, TaskTool, FinanceTool
from .lifeos_tool import LifeOSTool
from .open_window import OpenWindowTool
from .open_screen import OpenScreenTool
from .show_popup import ShowPopupTool
from .routine_tool import RoutineTool
from .places_search import PlacesSearchTool
from .planning_workspace import PlanningWorkspaceTool
from .catalog import metadata_for
from app.core.runs import RunCancelled
from .lifestyle_tools import normalize_name

# Groq (limite estrito de tokens): além das ferramentas fixas, entra a ferramenta cujo
# assunto aparece no pedido. As palavras são comparadas sem acento e em minúsculas.
GROQ_KEYWORD_TOOLS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = tuple(
    (re.compile(pattern), tools)
    for pattern, tools in (
        (r"\bhabit", ("habit_tool",)),
        (r"\btaref|\bpendencia", ("task_tool",)),
        (r"\bagua\b|\bbebi\b|\bhidrat|\btreino\b", ("lifeos_tool",)),
        (r"\bgastei\b|\bpaguei\b|\bgasto|\bdespesa|\breceita\b|\bfinanc", ("finance_tool",)),
        (r"\bnota\b|\bnotas\b|\banota|\bcofre\b", ("vault_save_note", "vault_search")),
        (r"\blembrete|\bagenda|\bcompromisso", ("calendar",)),
        (r"\btela\b|\bpainel\b|\babre\b|\babrir\b|\babra\b", ("open_screen",)),
        (r"\bpopup|\bmostra\b|\bmostre\b|\bmostrar\b", ("show_popup",)),
        (r"\blugar|\bperto\b|\bendereco|\bmapa\b|\bonde fica\b", ("places_search",)),
        (r"\bluz\b|\bluzes\b|\blampada|\bar condicionado|\btomada|\bcena\b|\bcortina|\bfechadura|\bcasa\b", ("home",)),
        # Pedido com horário ou repetição vira rotina gravada.
        (r"\brotina|\btodo dia|\btodos os dias|\btoda (segunda|terca|quarta|quinta|sexta)|\btodo (sabado|domingo)|\bdias uteis|\ba cada \d+ ?min|\bas \d{1,2} ?h\b|\bas \d{1,2}:\d{2}", ("routine",)),
    )
)

# Loop agêntico: ferramentas de dados do dia a dia que entram em qualquer pedido, para qualquer provedor.
LOOP_DATA_TOOLS = frozenset({
    "habit_tool", "task_tool", "lifeos_tool", "calendar", "vault_save_note", "vault_search",
    "open_window", "open_screen", "wait",
})

# Só no loop: assuntos das demais ferramentas comuns (as de dados já entram sempre).
LOOP_KEYWORD_TOOLS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = tuple(
    (re.compile(pattern), tools)
    for pattern, tools in (
        (r"\bpesquis|\bbusca|\bprocur|\bnoticia|\bpesquisa|\byoutube|\bsite\b|\blink\b|\burl\b", ("web_search",)),
        (r"\bapp\b|\baplicativo|\bprograma|\bnavegador|\bchrome|\bjanela", ("open_windows_app",)),
        (r"\bvolume|\bbrilho|\bdesligar\b|\breiniciar|\bbloquear|\bsistema\b", ("system_control",)),
        (r"\bmusica|\btoca\b|\btocar\b|\bspotify|\bplaylist", ("spotify",)),
        (r"\btimer\b|\btemporizador|\bcronometro|\balarme|\bminutos\b", ("timer",)),
        (r"\bwhats|\bzap\b|\bmensagem", ("whatsapp",)),
        (r"\barquivo|\bpasta\b|\bdocumento|\bdownloads\b", ("file_manager",)),
        (r"\bimagem|\bdesenh|\bfoto\b", ("image_generator",)),
        (r"\bfilme|\bserie\b", ("cinema",)),
        (r"\bplano\b|\bplanejament|\bplanejar", ("planning_workspace",)),
        (r"\bscript\b|\bcodigo\b|\bexecut", ("script_runner",)),
        (r"\btela\b|\bvejo\b|\bscreenshot|\bprint\b", ("vision",)),
        (r"\brotina|\btodo dia|\btodos os dias|\btoda (segunda|terca|quarta|quinta|sexta)|\btodo (sabado|domingo)|\bdias uteis|\ba cada \d+ ?min|\bas \d{1,2} ?h\b|\bas \d{1,2}:\d{2}", ("routine",)),
    )
)

GENERAL_TOOL_NAMES = {
    "file_manager", "system_control", "jarvis_mode", "web_search", "browser_agent", "timer", "wait",
    "whatsapp", "spotify", "clipboard", "news_reader", "open_windows_app", "script_runner",
    "vision", "qr_reader", "realtime", "proactive_agent", "system_tray", "cinema", "calendar", "image_generator",
    "screen_peeler", "phantom_typer", "smart_drop_zone",
    "desktop_search", "kasa_control", "home", "document_generator", "telegram_bot", "mobile_adb",
    "wormhole", "wallpaper_engine", "clipboard_intelligence",
    "habit_tool", "task_tool", "finance_tool", "lifeos_tool", "open_window", "open_screen", "show_popup",
    "places_search",
    "planning_workspace", "routine",
    "vault_search", "vault_daily_log", "vault_save_note", "vault_update_profile",
}

TUTOR_TOOL_NAMES = {
    "whiteboard_add_text", "whiteboard_add_image", "whiteboard_edit", "whiteboard_clear",
    "tutor_save_progress", "tutor_add_flashcard", "tutor_save_feynman", "enem_save_question",
}


class ToolRegistry:
    def __init__(
        self,
        base_folder: str | None = None,
        tutor_store: Any | None = None,
        enem_store: Any | None = None,
        plugin_manager: Any | None = None,
    ) -> None:
        self.tools: dict[str, BaseTool] = {}
        self._register_builtin_tools(base_folder, tutor_store, enem_store)
        self._register_plugin_tools(plugin_manager)

    def _register_builtin_tools(
        self,
        base_folder: str | None = None,
        tutor_store: Any | None = None,
        enem_store: Any | None = None,
    ) -> None:
        """Registra ferramentas nativas."""
        self._register(FileManagerTool(base_folder=base_folder))
        self._register(SystemControlTool())
        self._register(JarvisModeTool())
        self._register(WebSearchTool())
        self._register(BrowserAgentTool())
        self._register(TimerTool())
        self._register(WaitTool())
        self._register(WhatsAppTool())
        self._register(SpotifyTool())
        self._register(ClipboardTool())
        self._register(NewsTool())
        self._register(OpenWindowsAppTool())
        self._register(ScriptRunnerTool())
        self._register(VisionTool())
        self._register(QRReaderTool())
        self._register(RealTimeTool())
        self._register(CinemaTool())
        self._register(CalendarTool())
        self._register(ProactiveAgentTool())
        if TRAY_TOOL_AVAILABLE:
            self._register(SystemTrayTool())
        self._register(WhiteboardAddTextTool())
        self._register(WhiteboardAddImageTool())
        self._register(WhiteboardEditTool())
        self._register(WhiteboardClearTool())
        if tutor_store:
            self._register(TutorSaveProgressTool(tutor_store))
            self._register(TutorAddFlashcardTool(tutor_store))
            self._register(TutorSaveFeynmanTool(tutor_store))
        if enem_store:
            self._register(EnemSaveQuestionTool(enem_store))

        # Memory Vault (ai-memory-vault)
        self._register(VaultSearchTool())
        self._register(VaultDailyNoteTool())
        self._register(VaultSaveNoteTool())
        self._register(VaultUserProfileTool())

        # Fase 4 — Automação de SO & Produtividade
        self._register(HabitTool())
        self._register(TaskTool())
        self._register(FinanceTool())
        self._register(LifeOSTool())
        self._register(OpenWindowTool())
        self._register(OpenScreenTool())
        self._register(ShowPopupTool())
        self._register(RoutineTool())
        self._register(PlacesSearchTool())
        self._register(PlanningWorkspaceTool())
        self._register(ScreenPeelerTool())
        self._register(PhantomTyperTool())
        self._register(SmartDropZoneTool())
        self._register(WormholeTool())
        self._register(WallpaperEngineTool())
        self._register(ClipboardIntelligenceTool())
        self._register(HomeTool())

        # Fase 5 — Expansão de Ferramentas
        if FASE5_TOOLS_AVAILABLE:
            self._register(DesktopSearchTool())
            self._register(KasaControlTool())
            self._register(DocumentGeneratorTool())
            self._register(TelegramBotTool())
            self._register(MobileTelekinesisADB())
        
        # Ferramentas avançadas FASE 5/6
        if ADVANCED_TOOLS_AVAILABLE:
            self._register(CodeHelperTool())
            self._register(ImageGeneratorTool())
            self._register(HackerModeTool())
            self._register(WorkflowTool())
            self._register(MCPTool())
            self._register(DevAgentTool())


    def _register_plugin_tools(self, plugin_manager: Any | None = None) -> None:
        """Registra ferramentas de plugins."""
        if plugin_manager:
            try:
                for tool in plugin_manager.get_plugin_tools():
                    self._register(tool)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Falha ao registrar ferramentas de plugins: {e}")

    def _register(self, tool: BaseTool) -> None:
        self.tools[tool.name] = tool

    def get_tool_metadata(self, name: str):
        tool = self.get_tool(name)
        if tool is None:
            return None
        return metadata_for(name, tool.metadata)

    def get_tool(self, name: str) -> BaseTool | None:
        return self.tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self.tools.values())

    def allowed_tool_names(
        self,
        mode: str = "general",
        provider: str | None = None,
        user_text: str = "",
        *,
        narrow: bool = False,
    ) -> frozenset[str]:
        """Ferramentas registradas permitidas neste modo e turno.

        É a mesma lista que o modelo enxerga (`get_tool_declarations`) e que o
        executor do turno aplica, para que o servidor não aceite uma ferramenta
        que o modelo não recebeu.

        ``narrow=True`` (loop agêntico) aplica a filtragem por palavras do pedido a qualquer
        provedor, mantendo sempre as ferramentas de dados (``LOOP_DATA_TOOLS``).
        """
        allowed = TUTOR_TOOL_NAMES if mode == "tutor" else GENERAL_TOOL_NAMES

        # Otimização de TPM para provedores com limite estrito de taxa (ex: Groq)
        if (provider == "groq" or narrow) and mode != "tutor":
            core_groq = {
                "web_search", "system_control", "open_windows_app", "timer", "wait",
                "spotify", "whatsapp", "calendar", "file_manager",
                "cinema", "script_runner", "image_generator", "vision", "planning_workspace", "open_window"
            }
            user_lower = (user_text or "").lower()
            # No loop (narrow) só entram as ferramentas de dados e as que o pedido menciona.
            dynamic_tools = set(LOOP_DATA_TOOLS) if narrow else set(core_groq)
            for t_name in allowed:
                if t_name in user_lower or t_name.replace("_", " ") in user_lower:
                    dynamic_tools.add(t_name)
            normalized = normalize_name(user_text)
            for pattern, tools in GROQ_KEYWORD_TOOLS + (LOOP_KEYWORD_TOOLS if narrow else ()):
                if pattern.search(normalized):
                    dynamic_tools.update(tools)
            allowed = allowed.intersection(dynamic_tools)

        allowed_set = set(name for name in allowed if name in self.tools)
        if "home" in allowed_set:
            try:
                from app.services import home_assistant
                if not home_assistant.is_configured():
                    allowed_set.discard("home")
            except Exception:
                allowed_set.discard("home")
        return frozenset(allowed_set)

    def get_tool_declarations(
        self,
        mode: str = "general",
        provider: str | None = None,
        user_text: str = "",
    ) -> list[dict[str, Any]]:
        allowed = self.allowed_tool_names(mode, provider, user_text)
        declarations = []
        for tool in self.list_tools():
            if tool.name not in allowed:
                continue
            declarations.append({
                "name": tool.name,
                "description": tool.description[:250] if provider == "groq" else tool.description,
                "parameters": tool.parameters,
            })
        return declarations

    def execute_tool(self, name: str, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(ok=False, message=f"Ferramenta '{name}' não está cadastrada no registro.")
        try:
            return tool.execute(args, context=context)
        except RunCancelled:
            # "Parar pedido" durante uma espera: o cancelamento sobe até o Kernel.
            raise
        except Exception as e:
            return ToolResult(ok=False, message=f"Erro interno ao executar a ferramenta '{name}': {e}")

    def run_by_marker(self, kind: str, arg: str | None, user_line: str) -> ToolResult:
        """Executa ferramenta pedida pela LLM via marcador (suporta nomes compactos)."""
        kind_l = kind.lower().strip()
        
        # Mapeamento de nomes compactos
        compact_map = {
            "search": "web_search",
            "info": "system_control",
            "mem": "memory_manager",
            "note": "notes",
            "vol": "media_control",
            "file": "file_manager",
            "fs": "file_manager",
            "apps": "app_manager",
        }
        if kind_l in compact_map:
            kind_l = compact_map[kind_l]
        
        # Mapear para ferramentas existentes
        tool_mapping = {
            "open_windows_app": "open_windows_app",
            "web_search": "web_search",
            "file_manager": "file_manager",
            "system_control": "system_control",
            "timer": "timer",
            "whatsapp": "whatsapp",
            "spotify": "spotify",
            "clipboard": "clipboard",
            "notes": "notes",
            "media_control": "media_control",
            "realtime": "realtime",
        }
        
        mapped_name = tool_mapping.get(kind_l, kind_l)
        tool = self.get_tool(mapped_name)
        
        if not tool:
            return ToolResult(ok=False, message=f"Ferramenta '{kind}' não encontrada.")
        
        # Preparar argumentos baseados no tipo de ferramenta
        args = {}
        if arg:
            if mapped_name == "web_search":
                args = {"query": arg}
            elif mapped_name == "open_windows_app":
                args = {"app_name": arg}
            elif mapped_name == "file_manager":
                # Parsear argumentos de arquivo (acao:caminho)
                parts = arg.split("|") if "|" in arg else [arg]
                if len(parts) >= 1:
                    args = {"action": parts[0]}
                if len(parts) >= 2:
                    args["path"] = parts[1]
                if len(parts) >= 3:
                    args["argument"] = parts[2]
            elif mapped_name == "system_control":
                args = {"action": arg}
            elif mapped_name == "vision":
                args = {"action": arg if arg in ("analyze_screen", "analyze_camera") else "analyze_screen", "prompt": user_line}
            elif mapped_name == "realtime":
                args = {"action": arg if arg in ("get_weather", "get_news", "get_finance", "get_holidays") else "get_weather"}
            else:
                args = {"command": arg}
        
        try:
            return tool.execute(args, context={"user_line": user_line})
        except Exception as e:
            return ToolResult(ok=False, message=f"Erro ao executar '{mapped_name}': {e}")


# Instância global do registro de ferramentas
registry = ToolRegistry()
