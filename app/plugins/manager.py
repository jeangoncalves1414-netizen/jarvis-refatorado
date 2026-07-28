from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from .base import BasePlugin, PluginConfig

logger = logging.getLogger(__name__)


class PluginManager:
    """Gerencia ciclo de vida dos plugins."""
    
    def __init__(self, plugin_dirs: List[str] | None = None):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_dirs = plugin_dirs or ["app/plugins/builtin"]
        self._load_builtin_plugins()
    
    def _load_builtin_plugins(self) -> None:
        """Carrega plugins nativos do diretório builtin."""
        builtin_dir = Path("app/plugins/builtin")
        if not builtin_dir.exists():
            return
        
        for module_file in builtin_dir.glob("*.py"):
            if module_file.name.startswith("_"):
                continue
            
            module_name = f"app.plugins.builtin.{module_file.stem}"
            try:
                module = importlib.import_module(module_name)
                # Procura classes que herdam de BasePlugin
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BasePlugin) and 
                        attr != BasePlugin):
                        config = PluginConfig()
                        plugin = attr(config)
                        self.plugins[plugin.name] = plugin
                        logger.info(f"Plugin carregado: {plugin.name} v{plugin.version}")
            except Exception as e:
                logger.error(f"Falha ao carregar plugin {module_name}: {e}")
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Carrega um plugin específico."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            if plugin.config.enabled and not plugin.is_initialized:
                try:
                    success = plugin.initialize()
                    if success:
                        plugin._initialized = True
                        logger.info(f"Plugin inicializado: {plugin_name}")
                        return True
                    else:
                        logger.error(f"Falha na inicialização do plugin: {plugin_name}")
                        return False
                except Exception as e:
                    logger.error(f"Erro ao inicializar plugin {plugin_name}: {e}")
                    return False
        return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Descarrega um plugin."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            if plugin.is_initialized:
                try:
                    plugin.shutdown()
                    plugin._initialized = False
                    logger.info(f"Plugin descarregado: {plugin_name}")
                    return True
                except Exception as e:
                    logger.error(f"Erro ao descarregar plugin {plugin_name}: {e}")
                    return False
        return False
    
    def initialize_all(self) -> None:
        """Inicializa todos os plugins habilitados."""
        for plugin_name in self.plugins:
            self.load_plugin(plugin_name)
    
    def shutdown_all(self) -> None:
        """Desliga todos os plugins."""
        for plugin_name in list(self.plugins.keys()):
            self.unload_plugin(plugin_name)
    
    def get_plugin_tools(self) -> List[Any]:
        """Retorna todas as ferramentas de plugins carregados."""
        tools = []
        for plugin in self.plugins.values():
            if plugin.is_initialized:
                try:
                    tools.extend(plugin.get_tools())
                except Exception as e:
                    logger.error(f"Erro ao obter ferramentas do plugin {plugin.name}: {e}")
        return tools
    
    def get_plugin_api_routes(self) -> List[tuple[str, Any]]:
        """Retorna todas as rotas API de plugins."""
        routes = []
        for plugin in self.plugins.values():
            if plugin.is_initialized:
                try:
                    routes.extend(plugin.get_api_routes())
                except Exception as e:
                    logger.error(f"Erro ao obter rotas API do plugin {plugin.name}: {e}")
        return routes
    
    def get_plugin(self, name: str) -> BasePlugin | None:
        """Retorna um plugin específico."""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """Lista todos os plugins com status."""
        return [
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "enabled": plugin.config.enabled,
                "initialized": plugin.is_initialized
            }
            for plugin in self.plugins.values()
        ]
