from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PluginConfig:
    """Configuração padrão para plugins."""
    enabled: bool = True
    priority: int = 100  # Menor = maior prioridade
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


class BasePlugin(ABC):
    """Interface base que todos os plugins devem implementar."""
    
    def __init__(self, config: PluginConfig):
        self.config = config
        self._initialized = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome único do plugin."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Versão do plugin."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Descrição do plugin."""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Inicializa o plugin. Retorna True se sucesso."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Limpa recursos do plugin."""
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Any]:
        """Retorna lista de ferramentas fornecidas pelo plugin."""
        pass
    
    def get_api_routes(self) -> List[tuple[str, Any]]:
        """Retorna rotas API adicionais (opcional)."""
        return []
    
    @property
    def is_initialized(self) -> bool:
        """Verifica se o plugin foi inicializado."""
        return self._initialized
