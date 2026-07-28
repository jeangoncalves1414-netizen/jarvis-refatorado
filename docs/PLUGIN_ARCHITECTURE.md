# Arquitetura de Plugins/Extensões Jarvis

## Princípios de Design
- **Modularidade**: Cada plugin é independente e auto-contido
- **Descoberta Automática**: Plugins são carregados dinamicamente
- **Interface Padrão**: Todos os plugins seguem a mesma interface
- **Configuração Centralizada**: Gerenciamento unificado de configurações
- **Isolamento de Falhas**: Falha em um plugin não afeta o sistema

## Estrutura de Diretórios

```
app/
├── plugins/                    # Sistema de plugins
│   ├── __init__.py
│   ├── base.py                 # Interface base para plugins
│   ├── manager.py              # Gerenciador de plugins
│   ├── registry.py             # Registro de plugins disponíveis
│   └── builtin/               # Plugins nativos
│       ├── home_assistant.py
│       ├── browser_agent.py
│       ├── security_vision.py
│       ├── finance_tracker.py
│       └── personality_engine.py
├── agent/
│   └── tools/                 # Ferramentas existentes (compatíveis)
└── skills/                    # Skills de alto nível (futuro)
    ├── __init__.py
    ├── base.py
    └── examples/
```

## Interface Base de Plugin

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class PluginConfig:
    """Configuração padrão para plugins."""
    enabled: bool = True
    priority: int = 100  # Menor = maior prioridade
    dependencies: list[str] = None
    config: Dict[str, Any] = None

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
    def get_tools(self) -> list:
        """Retorna lista de ferramentas fornecidas pelo plugin."""
        pass
    
    @abstractmethod
    def get_api_routes(self) -> list:
        """Retorna rotas API adicionais (opcional)."""
        pass
```

## Gerenciador de Plugins

```python
class PluginManager:
    """Gerencia ciclo de vida dos plugins."""
    
    def __init__(self, plugin_dirs: list[str]):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_dirs = plugin_dirs
    
    def discover_plugins(self) -> None:
        """Descobre plugins nos diretórios configurados."""
        pass
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Carrega um plugin específico."""
        pass
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Descarrega um plugin."""
        pass
    
    def get_plugin_tools(self) -> list:
        """Retorna todas as ferramentas de plugins carregados."""
        pass
    
    def get_plugin_api_routes(self) -> list:
        """Retorna todas as rotas API de plugins."""
        pass
```

## Exemplo de Plugin: Home Assistant

```python
class HomeAssistantPlugin(BasePlugin):
    """Plugin para integração com Home Assistant."""
    
    @property
    def name(self) -> str:
        return "home_assistant"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Controle de automação doméstica via Home Assistant API"
    
    def initialize(self) -> bool:
        """Inicializa conexão com Home Assistant."""
        import homeassistant.remote as ha
        self.ha_client = ha.RemoteAPI(
            url=self.config.config.get("url"),
            token=self.config.config.get("token")
        )
        self._initialized = True
        return True
    
    def shutdown(self) -> None:
        """Fecha conexão."""
        if self._initialized:
            self.ha_client.close()
    
    def get_tools(self) -> list:
        """Retorna ferramentas de automação."""
        return [
            HomeAssistantLightTool(self.ha_client),
            HomeAssistantClimateTool(self.ha_client),
            HomeAssistantSecurityTool(self.ha_client)
        ]
    
    def get_api_routes(self) -> list:
        """Retorna rotas API para configuração."""
        return [
            ("/api/plugins/home_assistant/config", self._handle_config),
            ("/api/plugins/home_assistant/entities", self._handle_entities)
        ]
```

## Sistema de Configuração

### Arquivo de Configuração Global
```json
{
  "plugins": {
    "home_assistant": {
      "enabled": true,
      "priority": 50,
      "config": {
        "url": "http://homeassistant.local:8123",
        "token": "YOUR_TOKEN"
      }
    },
    "browser_agent": {
      "enabled": true,
      "priority": 100,
      "config": {
        "headless": false,
        "browser": "chrome"
      }
    }
  }
}
```

### Validação de Configuração
- Validação de esquema com Pydantic
- Valores padrão para campos opcionais
- Validação de dependências entre plugins

## Ciclo de Vida de Plugin

1. **Descoberta**: Scan de diretórios por plugins
2. **Validação**: Verificação de dependências e configuração
3. **Carregamento**: Import dinâmico do módulo
4. **Inicialização**: Chamada de `initialize()`
5. **Registro**: Adição ao registry de ferramentas
6. **Execução**: Uso das ferramentas fornecidas
7. **Descarregamento**: Chamada de `shutdown()` e limpeza

## Integração com Sistema Atual

### ToolRegistry Atual
```python
# app/agent/tools/registry.py
class ToolRegistry:
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self._load_builtin_tools()
        self._load_plugin_tools()
    
    def _load_plugin_tools(self):
        """Carrega ferramentas de plugins."""
        for tool in self.plugin_manager.get_plugin_tools():
            self._register(tool)
```

### Integração com Orchestrator
```python
# app/agent/orchestrator.py
class AgentOrchestrator:
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        # ... resto da inicialização
```

## Boas Práticas

1. **Isolamento**: Cada plugin deve ter suas próprias dependências
2. **Logging**: Usar logging estruturado com nome do plugin
3. **Error Handling**: Capturar exceções internamente, não propagar
4. **Configuração**: Validação rigorosa de configuração
5. **Documentação**: Docstrings completas para ferramentas
6. **Testes**: Cada plugin deve ter testes unitários
7. **Versionamento**: Semantic versioning para plugins

## Exemplos de Plugins Futuros

### Browser Agent
- Automação web com Playwright
- Extração de dados estruturados
- Preenchimento de formulários
- Navegação programática

### Security Vision
- Detecção de movimento com OpenCV
- Reconhecimento facial
- Análise de câmeras de segurança
- Alertas em tempo real

### Finance Tracker
- Rastreamento de gastos
- Análise de investimentos
- Previsões financeiras
- Integração com bancos

### Personality Engine
- Análise de padrões de usuário
- Adaptação de respostas
- Evolução de persona
- Perfil comportamental

## Roadmap de Implementação

### Fase 1: Infraestrutura
- [x] Interface base (BasePlugin)
- [x] Gerenciador de plugins (PluginManager)
- [x] Sistema de configuração
- [x] Integração com ToolRegistry

### Fase 2: Plugins Nativos
- [ ] Home Assistant Plugin
- [ ] Browser Agent Plugin
- [ ] Security Vision Plugin
- [ ] Finance Tracker Plugin

### Fase 3: Sistema de Skills
- [x] Interface de skills
- [x] Gerenciador de skills
- [ ] Skills de produtividade
- [ ] Skills de aprendizado

### Fase 4: Marketplace
- [ ] Sistema de instalação remota
- [ ] Repositório de plugins
- [ ] Validação de segurança
- [ ] Reviews e ratings
