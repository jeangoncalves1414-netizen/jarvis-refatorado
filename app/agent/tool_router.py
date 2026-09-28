"""
Tool Router - Sistema inteligente de roteamento de ferramentas.
Baseado no padrão do reverse-skill para seleção automática de ferramentas.
"""

from __future__ import annotations

import os
import importlib
import importlib.util
import inspect
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class TaskCategory(Enum):
    """Categorias de tarefas para roteamento."""
    CODE = "code"
    WEB_SEARCH = "web_search"
    CALENDAR = "calendar"
    FILES = "files"
    SYSTEM = "system"
    VISION = "vision"
    AUTOMATION = "automation"
    COMMUNICATION = "communication"
    MEDIA = "media"
    MEMORY = "memory"
    SECURITY = "security"
    DEVELOPMENT = "development"


@dataclass
class ToolCapability:
    """Descrição da capacidade de uma ferramenta."""
    name: str
    description: str
    category: TaskCategory
    priority: int = 1  # 1 = mais prioritário
    requires_auth: bool = False
    dependencies: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=lambda: ["windows", "linux", "macos"])


@dataclass
class ToolInfo:
    """Informações sobre uma ferramenta registrada."""
    module_path: str
    class_name: str
    capabilities: List[ToolCapability]
    available: bool = True
    health_status: str = "ok"  # ok, degraded, unavailable


class ToolRouter:
    """
    Router inteligente de ferramentas.
    Seleciona automaticamente a melhor ferramenta baseada na tarefa.
    """

    def __init__(self, tools_dir: str = "app/agent/tools"):
        self.tools_dir = tools_dir
        self.tools: Dict[str, ToolInfo] = {}
        self.task_matrix: Dict[TaskCategory, List[str]] = {}
        self._initialize_tool_registry()
        self._build_task_matrix()

    def _initialize_tool_registry(self) -> None:
        """Descobre e registra todas as ferramentas disponíveis."""
        if not os.path.exists(self.tools_dir):
            print(f"[ToolRouter] Diretório de ferramentas não encontrado: {self.tools_dir}")
            return

        for filename in os.listdir(self.tools_dir):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            module_name = filename[:-3]
            module_path = os.path.join(self.tools_dir, filename)

            try:
                self._register_tool_from_file(module_name, module_path)
            except Exception as e:
                print(f"[ToolRouter] Erro ao registrar {module_name}: {e}")

    def _register_tool_from_file(self, module_name: str, module_path: str) -> None:
        """Registra uma ferramenta a partir de um arquivo Python."""
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Procura classes com métodos decorados
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if self._is_tool_class(obj):
                    capabilities = self._extract_capabilities(obj)
                    if capabilities:
                        tool_key = f"{module_name}.{name}"
                        self.tools[tool_key] = ToolInfo(
                            module_path=module_path,
                            class_name=name,
                            capabilities=capabilities
                        )
                        print(f"[ToolRouter] Registrado: {tool_key} com {len(capabilities)} capacidades")

        except Exception as e:
            print(f"[ToolRouter] Erro ao carregar {module_name}: {e}")

    def _is_tool_class(self, obj: Any) -> bool:
        """Verifica se uma classe é uma ferramenta."""
        # Heurística: tem métodos que parecem ferramentas
        if not inspect.isclass(obj):
            return False

        for method_name, method in inspect.getmembers(obj, inspect.isfunction):
            if hasattr(method, '__tool__'):
                return True

        return False

    def _extract_capabilities(self, tool_class: Any) -> List[ToolCapability]:
        """Extrai capacidades de uma classe de ferramenta."""
        capabilities = []

        for method_name, method in inspect.getmembers(tool_class, inspect.isfunction):
            if hasattr(method, '__tool__'):
                capability = ToolCapability(
                    name=method_name,
                    description=getattr(method, '__tool_description__', ''),
                    category=getattr(method, '__tool_category__', TaskCategory.SYSTEM),
                    priority=getattr(method, '__tool_priority__', 1)
                )
                capabilities.append(capability)

        return capabilities

    def _build_task_matrix(self) -> None:
        """Constrói matriz de roteamento tarefa → ferramenta."""
        self.task_matrix = {category: [] for category in TaskCategory}

        for tool_key, tool_info in self.tools.items():
            for capability in tool_info.capabilities:
                if capability.category not in self.task_matrix:
                    self.task_matrix[capability.category] = []
                self.task_matrix[capability.category].append(tool_key)

        # Ordenar por prioridade
        for category in self.task_matrix:
            self.task_matrix[category].sort(
                key=lambda k: min((cap.priority for cap in self.tools[k].capabilities), default=999)
            )

    def route(self, task: TaskCategory, context: Dict[str, Any] | None = None) -> Optional[str]:
        """
        Roteia uma tarefa para a melhor ferramenta disponível.
        Retorna a chave da ferramenta ou None se nenhuma disponível.
        """
        if task not in self.task_matrix:
            print(f"[ToolRouter] Categoria de tarefa desconhecida: {task}")
            return None

        candidates = self.task_matrix[task]
        if not candidates:
            print(f"[ToolRouter] Nenhuma ferramenta para categoria: {task}")
            return None

        # Filtrar ferramentas disponíveis
        available = [key for key in candidates if self.tools[key].available]
        if not available:
            print(f"[ToolRouter] Nenhuma ferramenta disponível para: {task}")
            return None

        # Selecionar a mais prioritária
        best_tool = available[0]
        print(f"[ToolRouter] Roteado {task} → {best_tool}")
        return best_tool

    def get_tool_info(self, tool_key: str) -> Optional[ToolInfo]:
        """Retorna informações de uma ferramenta."""
        return self.tools.get(tool_key)

    def list_tools_by_category(self, category: TaskCategory) -> List[str]:
        """Lista ferramentas por categoria."""
        return self.task_matrix.get(category, [])

    def check_tool_health(self, tool_key: str) -> str:
        """Verifica saúde de uma ferramenta."""
        tool_info = self.tools.get(tool_key)
        if not tool_info:
            return "unavailable"

        # Simulação de health check
        try:
            # Tenta importar o módulo
            spec = importlib.util.spec_from_file_location(
                tool_key.split('.')[0],
                tool_info.module_path
            )
            if spec and spec.loader:
                tool_info.health_status = "ok"
                tool_info.available = True
            else:
                tool_info.health_status = "unavailable"
                tool_info.available = False
        except Exception:
            tool_info.health_status = "degraded"
            tool_info.available = False

        return tool_info.health_status

    def refresh_tool_index(self) -> None:
        """Recarrega índice de ferramentas."""
        print("[ToolRouter] Recarregando índice de ferramentas...")
        self.tools.clear()
        self._initialize_tool_registry()
        self._build_task_matrix()
        print(f"[ToolRouter] Índice atualizado: {len(self.tools)} ferramentas")


# Decorador para marcar métodos como ferramentas
def tool(description: str = "", category: TaskCategory = TaskCategory.SYSTEM, priority: int = 1):
    """Decorador para marcar um método como ferramenta."""
    def decorator(func: Callable) -> Callable:
        func.__tool__ = True
        func.__tool_description__ = description
        func.__tool_category__ = category
        func.__tool_priority__ = priority
        return func
    return decorator


# Singleton global
_router_instance: Optional[ToolRouter] = None


def get_router() -> ToolRouter:
    """Retorna instância singleton do router."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ToolRouter()
    return _router_instance
