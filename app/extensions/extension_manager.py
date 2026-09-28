"""
Extension Manager - Sistema de extensões modulares para Jarvis.
Baseado nos padrões do Brahma-AI-Lite e ten-framework.
"""

from __future__ import annotations

import os
import sys
import importlib
import inspect
import threading
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ExtensionHook(Enum):
    """Hooks disponíveis para extensões."""
    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"
    ON_COMMAND = "on_command"
    ON_VOICE_START = "on_voice_start"
    ON_VOICE_END = "on_voice_end"
    ON_TOOL_CALL = "on_tool_call"
    ON_MEMORY_WRITE = "on_memory_write"


@dataclass
class ExtensionInfo:
    """Informações sobre uma extensão."""
    name: str
    version: str
    author: str
    description: str
    module_path: str
    enabled: bool = True
    hooks: Dict[ExtensionHook, List[Callable]] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


class ExtensionManager:
    """
    Gerenciador de extensões do Jarvis.
    Suporta hot-reload, hooks lifecycle, e descoberta automática.
    """

    def __init__(self, extensions_dir: str = "app/extensions"):
        self.extensions_dir = Path(extensions_dir)
        self.extensions: Dict[str, ExtensionInfo] = {}
        self.hooks: Dict[ExtensionHook, List[Callable]] = {hook: [] for hook in ExtensionHook}
        self._lock = threading.Lock()
        self._load_extensions()

    def _load_extensions(self) -> None:
        """Carrega todas as extensões do diretório."""
        if not self.extensions_dir.exists():
            print(f"[ExtensionManager] Criando diretório de extensões: {self.extensions_dir}")
            self.extensions_dir.mkdir(parents=True, exist_ok=True)
            return

        # Adicionar diretório ao path
        if str(self.extensions_dir.parent) not in sys.path:
            sys.path.insert(0, str(self.extensions_dir.parent))

        for filename in os.listdir(self.extensions_dir):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            module_name = filename[:-3]
            self._load_extension(module_name)

    def _load_extension(self, module_name: str) -> Optional[ExtensionInfo]:
        """Carrega uma extensão específica."""
        try:
            module_path = self.extensions_dir / f"{module_name}.py"
            if not module_path.exists():
                print(f"[ExtensionManager] Extensão não encontrada: {module_name}")
                return None

            spec = importlib.util.spec_from_file_location(module_name, str(module_path))
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Extrair metadados da extensão
            metadata = self._extract_metadata(module)
            if not metadata:
                print(f"[ExtensionManager] Extensão sem metadados: {module_name}")
                return None

            # Registrar hooks
            hooks = self._register_hooks(module, metadata.name)

            extension_info = ExtensionInfo(
                name=metadata.name,
                version=metadata.version,
                author=metadata.author,
                description=metadata.description,
                module_path=str(module_path),
                hooks=hooks,
                dependencies=getattr(metadata, "dependencies", [])
            )

            with self._lock:
                self.extensions[metadata.name] = extension_info

            print(f"[ExtensionManager] Extensão carregada: {metadata.name} v{metadata.version}")
            return extension_info

        except Exception as e:
            print(f"[ExtensionManager] Erro ao carregar {module_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_metadata(self, module: Any) -> Optional[Any]:
        """Extrai metadados de um módulo de extensão."""
        if hasattr(module, "EXTENSION_METADATA"):
            return module.EXTENSION_METADATA

        # Tentar criar metadados a partir de atributos do módulo
        class Metadata:
            def __init__(self, module: Any):
                self.name = getattr(module, "EXTENSION_NAME", module.__name__)
                self.version = getattr(module, "EXTENSION_VERSION", "1.0.0")
                self.author = getattr(module, "EXTENSION_AUTHOR", "Unknown")
                self.description = getattr(module, "EXTENSION_DESCRIPTION", "")
                self.dependencies = getattr(module, "EXTENSION_DEPENDENCIES", [])

        try:
            return Metadata(module)
        except Exception:
            return None

    def _register_hooks(self, module: Any, extension_name: str) -> Dict[ExtensionHook, List[Callable]]:
        """Registra hooks de uma extensão."""
        hooks = {hook: [] for hook in ExtensionHook}

        for hook_name in ExtensionHook:
            hook_func = getattr(module, hook_name.value, None)
            if hook_func and callable(hook_func):
                hooks[hook_name].append(hook_func)
                with self._lock:
                    self.hooks[hook_name].append(hook_func)
                print(f"[ExtensionManager] Hook registrado: {extension_name}.{hook_name.value}")

        return hooks

    def reload_extension(self, extension_name: str) -> bool:
        """Recarrega uma extensão (hot-reload)."""
        if extension_name not in self.extensions:
            print(f"[ExtensionManager] Extensão não encontrada: {extension_name}")
            return False

        # Remover hooks antigos
        old_hooks = self.extensions[extension_name].hooks
        for hook, funcs in old_hooks.items():
            for func in funcs:
                if func in self.hooks[hook]:
                    self.hooks[hook].remove(func)

        # Recarregar módulo - usar nome do arquivo correto
        extension_info = self.extensions[extension_name]
        module_name = os.path.basename(extension_info.module_path).replace('.py', '')
        if module_name in sys.modules:
            del sys.modules[module_name]

        new_info = self._load_extension(module_name)
        return new_info is not None

    def enable_extension(self, extension_name: str) -> bool:
        """Habilita uma extensão."""
        if extension_name not in self.extensions:
            return False

        self.extensions[extension_name].enabled = True
        print(f"[ExtensionManager] Extensão habilitada: {extension_name}")
        return True

    def disable_extension(self, extension_name: str) -> bool:
        """Desabilita uma extensão."""
        if extension_name not in self.extensions:
            return False

        self.extensions[extension_name].enabled = False
        print(f"[ExtensionManager] Extensão desabilitada: {extension_name}")
        return True

    def call_hook(self, hook: ExtensionHook, *args: Any, **kwargs: Any) -> List[Any]:
        """Executa todos os hooks registrados para um tipo."""
        results = []

        with self._lock:
            hook_funcs = list(self.hooks[hook])  # Copia dentro do lock para evitar race condition

        for func in hook_funcs:
            try:
                result = func(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"[ExtensionManager] Erro no hook {hook.value}: {e}")

        return results

    def list_extensions(self) -> List[ExtensionInfo]:
        """Lista todas as extensões carregadas."""
        return list(self.extensions.values())

    def get_extension(self, name: str) -> Optional[ExtensionInfo]:
        """Retorna informações de uma extensão."""
        return self.extensions.get(name)

    def create_extension_template(self, name: str) -> str:
        """Cria um template de extensão."""
        template_path = self.extensions_dir / f"{name}.py"
        
        template_content = f'''"""
{name} - Extensão do Jarvis
"""

EXTENSION_METADATA = type("Metadata", (), {{
    "name": "{name}",
    "version": "1.0.0",
    "author": "Seu Nome",
    "description": "Descrição da extensão",
    "dependencies": []
}})()


def on_startup():
    """Hook chamado na inicialização do Jarvis."""
    print(f"[{name}] Inicializando...")


def on_shutdown():
    """Hook chamado no encerramento do Jarvis."""
    print(f"[{name}] Encerrando...")


def on_command(command: str, context: dict):
    """Hook chamado quando um comando é recebido."""
    print(f"[{name}] Comando: {{command}}")
    # Retorne True para marcar o comando como handled
    return False


# Adicione mais hooks conforme necessário:
# def on_voice_start():
# def on_voice_end(transcript: str):
# def on_tool_call(tool_name: str, args: dict):
# def on_memory_write(key: str, value: any):
'''

        template_path.write_text(template_content, encoding="utf-8")
        print(f"[ExtensionManager] Template criado: {template_path}")
        return str(template_path)


# Singleton global
_manager_instance: Optional[ExtensionManager] = None


def get_manager() -> ExtensionManager:
    """Retorna instância singleton do ExtensionManager."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ExtensionManager()
    return _manager_instance
