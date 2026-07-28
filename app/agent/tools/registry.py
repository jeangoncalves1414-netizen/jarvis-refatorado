from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from .file_manager import FileManagerTool
from .system_control import SystemControlTool
from .jarvis_mode import JarvisModeTool
from .web_search import WebSearchTool
from .browser_agent import BrowserAgentTool
from .timer import TimerTool
from .whatsapp import WhatsAppTool
from .spotify import SpotifyTool
from .whiteboard import WhiteboardAddTextTool, WhiteboardAddImageTool, WhiteboardClearTool
from .clipboard import ClipboardTool, NewsTool
from .open_windows_app import OpenWindowsAppTool
from .script_runner import ScriptRunnerTool
from .vision_tool import VisionTool
from .realtime_tool import RealTimeTool
from .cinema_tool import CinemaTool
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

GENERAL_TOOL_NAMES = {
    "file_manager", "system_control", "jarvis_mode", "web_search", "browser_agent", "timer",
    "whatsapp", "spotify", "clipboard", "news_reader", "open_windows_app", "script_runner",
    "vision", "realtime", "proactive_agent", "system_tray", "cinema",
}

TUTOR_TOOL_NAMES = {
    "whiteboard_add_text", "whiteboard_add_image", "whiteboard_clear",
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
        self._register(WhatsAppTool())
        self._register(SpotifyTool())
        self._register(ClipboardTool())
        self._register(NewsTool())
        self._register(OpenWindowsAppTool())
        self._register(ScriptRunnerTool())
        self._register(VisionTool())
        self._register(RealTimeTool())
        self._register(CinemaTool())
        self._register(ProactiveAgentTool())
        if TRAY_TOOL_AVAILABLE:
            self._register(SystemTrayTool())
        self._register(WhiteboardAddTextTool())
        self._register(WhiteboardAddImageTool())
        self._register(WhiteboardClearTool())
        if tutor_store:
            self._register(TutorSaveProgressTool(tutor_store))
            self._register(TutorAddFlashcardTool(tutor_store))
            self._register(TutorSaveFeynmanTool(tutor_store))
        if enem_store:
            self._register(EnemSaveQuestionTool(enem_store))
        
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

    def get_tool(self, name: str) -> BaseTool | None:
        return self.tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self.tools.values())

    def get_tool_declarations(self, mode: str = "general") -> list[dict[str, Any]]:
        allowed = TUTOR_TOOL_NAMES if mode == "tutor" else GENERAL_TOOL_NAMES
        declarations = []
        for tool in self.list_tools():
            if tool.name not in allowed:
                continue
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })
        return declarations

    def execute_tool(self, name: str, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(ok=False, message=f"Ferramenta '{name}' não está cadastrada no registro.")
        try:
            return tool.execute(args, context=context)
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
