# Jarvis Rebuild

Este projeto é uma reconstrução modular de uma assistente pessoal de desktop com foco em:
- voz e interação natural,
- automação de tarefas,
- memória e contexto,
- painel novo e extensível.

## Estrutura
- app/core: sistemas de segurança e gerenciamento (rate limiting, guardrails, scheduler, etc)
- app/agent: orquestração do agente e ferramentas
- app/domain: módulos de domínio (voz, arquivos, produtividade)
- app/services: integrações externas (visão, automação Windows, browser)
- app/plugins: sistema de plugins extensível
- app/storage: persistência (memória, sessões, vetores)
- app/ui: painel web simples e modular

## Funcionalidades Implementadas

### Segurança e Controle
- **RateLimiter**: Controle de chamadas API com janela deslizante
- **ToolGuardrails**: Bloqueio de repetições e detecção de loops sem progresso
- **CriticalConfirm**: Confirmação para ações críticas
- **Telemetria**: Logging estruturado de eventos

### Automação Windows
- **AppManager**: Escaneamento de registry e abertura de aplicativos
- **WindowControl**: Controle de janelas (foco, fechar)
- **FileProcessor**: Operações batch de arquivos

### Visão e Web
- **VisionService**: Captura e análise de tela com Gemini Vision
- **BrowserAgent**: Automação web com Playwright

### Sistema
- **Scheduler**: Agendamento de tarefas recorrentes
- **Heartbeat**: Monitoramento de saúde do sistema
- **SettingsManager**: Gerenciamento de configurações
- **UserManager**: Gerenciamento multi-usuário

### Ferramentas Avançadas
- **CodeHelper**: Assistência de código (gerar, explicar, refatorar)
- **ImageGenerator**: Geração de imagens via API
- **HackerMode**: Automação avançada com scripts
- **Workflow**: Cadeias de ferramentas em sequência
- **MCP**: Integração Model Context Protocol
- **DevAgent**: Agente especializado em desenvolvimento
- **ProactiveAgent**: Sugestões proativas baseadas em contexto

### Sistema de Plugins
- **BasePlugin**: Interface base para plugins
- **PluginManager**: Gerenciamento de ciclo de vida de plugins
- Integração dinâmica com ToolRegistry

### Multi-Agent e Memória
- **AgentManager**: Gerenciamento de múltiplos agentes com perfis
- **SemanticMemory**: Memória vetorial com ChromaDB
  - Expiração automática de memórias antigas
  - Ranking de importância e access count
  - Contexto temporal com timestamps
  - Limpeza automática de duplicatas

### Voice Nativo
- **WhisperSTT**: Speech-to-Text offline usando Whisper
- **WakeWordDetector**: Detecção de wake word ("Jarvis") por energia de áudio

### Proatividade
- **PatternLearner**: Aprendizado de padrões de comportamento
  - Detecção de padrões temporais (hora, dia da semana)
  - Sistema de confiança baseado em frequência
  - Sugestões proativas baseadas em contexto

### Integrações Windows
- **WindowsNotification**: Notificações do Windows 10/11
- **CalendarService**: Calendário simples com eventos e lembretes

### UI Desktop
- **TrayIcon**: Ícone na bandeja do sistema com menu de contexto

### LLM Local
- **OllamaLLM**: Cliente para Ollama (LLM local offline)

## Como executar

```bash
python -m app.main --demo
```

ou, após instalar as dependências:

```bash
jarvis-rebuild --demo
```

## Dependências Opcionais
Algumas funcionalidades requerem dependências adicionais:
- **Visão**: mss, Pillow, google-genai
- **Browser**: playwright
- **Clap Detector**: numpy
- **Memória Vetorial**: chromadb
- **Voice Nativo**: openai-whisper, pyaudio
- **Notificações Windows**: win10toast
- **Tray Icon**: pystray, pillow
- **LLM Local**: requests (Ollama deve estar instalado separadamente)

## Arquitetura
O projeto segue princípios de modularidade extrema:
- Arquivos ≤ 300 linhas
- Funções ≤ 50 linhas
- Type hints obrigatórios
- Imports absolutos apenas
- Graceful degradation para dependências opcionais
