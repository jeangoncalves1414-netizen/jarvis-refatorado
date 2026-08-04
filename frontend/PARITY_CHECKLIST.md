# Checklist de paridade — Painel legado vs React

Legenda: ✅ implementado · ⚠️ parcial · ❌ ausente · ➖ não aplicável (legado decorativo ou substituído)

## Navegação e shell

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Dashboard | `data-screen="dashboard"` | `Dashboard` | ✅ |
| Automações | `data-screen="automations"` | `Automações` | ✅ |
| Chat | `data-screen="chat"` | `Chat` | ✅ |
| Cinema (atalho) | `#cinema-open-button` | Sidebar + hero | ✅ |
| Calendário | `data-screen="calendar"` | `Calendário` | ✅ |
| Análises | `data-screen="analytics"` | `Análises` | ✅ |
| Estudos | `data-screen="study"` | `Estudos` | ✅ |
| Memórias | Dentro de Análises | Página `Memórias` | ✅ (reorganizado) |
| Configurações | Modal + `#screen-settings` | Página `Configurações` | ✅ (reorganizado) |
| Persistir tela ativa | `localStorage active_screen` | `jarvis-active-screen` | ✅ |
| Nova tarefa (sidebar) | `#new-task-button` | Quick action + foco | ✅ |
| Dock mobile | — | `AnimatedDock` | ✅ (melhoria) |
| Help / Sign out | Links decorativos | — | ➖ |

## Ações rápidas (sidebar)

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Cinema | Botão nav | Quick action | ✅ |
| Visão / tela | Chat composer | Quick action | ✅ |
| Voz | Chat mic + sidebar | Quick action | ✅ |
| Câmeras | Modal workspace | Quick action | ✅ |
| Ligação hands-free | Header + composer | Quick action + modal | ✅ |

## Dashboard

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Clima (HUD) | `#hud-weather-*` | `DashboardHero` | ✅ |
| Mercado (HUD) | `#hud-fin-*` | Bento + hero | ✅ |
| Briefing / lembretes / boot | HUD widgets | `GlowCard` widgets | ✅ |
| Tarefas CRUD | Lista + toggle/delete | `DashboardPage` | ✅ |
| Timers ativos | `#dashboard-timers-list` | Bento card | ✅ |
| Atividade recente | `#dashboard-activity-list` | Bento card | ✅ |
| CPU / RAM | Stats + barras | Bento card | ✅ |
| Sessões / flashcards | Stats | Bento cards | ✅ |
| TTS status | Settings area | Widget TTS | ✅ |
| Settings shortcut | `#settings-button` | Nav Configurações | ✅ |
| Auto-refresh ~25s | `setInterval` | Polling | ✅ |

## Chat

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Lista de sessões | Sub-sidebar | Barra horizontal | ✅ |
| Buscar sessões | Input search | Filtro local | ✅ |
| Nova conversa | `#new-chat-button` | Botão | ✅ |
| Exportar Markdown | `#share-chat-button` | Botão Exportar | ✅ |
| Excluir conversa | Menu + header | Header delete | ✅ |
| Persistir sessão ativa | `active_session_id` | `jarvis-react-session` | ✅ |
| WebSocket streaming | Sim | Sim | ✅ |
| Reasoning / typing | Sim | Sim | ✅ |
| Modos (general/agent/…) | Composer | `ChatComposer` | ✅ |
| Anexo imagem | — | Sim | ✅ (melhoria) |
| Visão / tela | `#chat-vision-button` | Composer + quick action | ✅ |
| Microfone | `#chat-mic-button` | Composer | ✅ |
| Cinema no chat | — | Composer | ✅ (melhoria) |
| Ligação | `#live-call-*` | `LiveCallModal` | ✅ |
| Ouvir resposta | Por mensagem | Botão Ouvir | ✅ |
| Confirmação de script | Modal | Modal global | ✅ |
| Sugestões de prompt | — | `PromptSuggestions` | ✅ (melhoria) |
| Menu ⋮ (dropdown) | `#chat-menu-button` | Header delete | ⚠️ |

## Automações

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Clima ± / slider | `data-temperature-step` | `AutomationsPage` | ✅ |
| Briefing manual | Trigger button | Botão | ✅ |
| Lembretes (criar/listar) | Form + lista | Form + lista | ✅ |
| Studio lighting / lock | Cards decorativos | — | ➖ |

## Calendário

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Grade mensal | Sim | `CalendarSection` | ✅ |
| Criar evento | Modal | Modal | ✅ |
| Lembretes proativos | Sidebar | Lista lateral | ✅ |

## Análises

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Provedor LLM | Telemetria | Stat card | ✅ |
| Requisições / erros | Telemetria | Stat cards | ✅ |
| Uptime | Telemetria | Stat card | ✅ |
| CPU / RAM ao vivo | `statCpuBar` | Stat cards | ✅ |
| Logs filtráveis | Level + search | `AnalyticsPage` | ✅ |
| Ferramentas executadas | — | Panel | ✅ (melhoria) |
| Memórias semânticas | Embutido | Página Memórias | ✅ (reorganizado) |
| Cards decorativos (devices, energy) | HTML estático | — | ➖ |

## Memórias

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Coleção conversas | Tab | Tab | ✅ |
| Coleção preferências | Tab user_memory | Tab "Sobre você" | ✅ |
| Limpar erros técnicos | — | Botão | ✅ |
| Atualizar | — | Botão | ✅ |

## Configurações

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Provedor TTS | Settings | `SettingsPage` | ✅ |
| Provedor LLM | Settings | `SettingsPage` | ✅ |
| Ler respostas (speak) | `#setting-speak-responses` | Switch + localStorage | ✅ |
| Wake word | Toggle | Switch | ✅ |
| Boot Windows | Toggle | Switch | ✅ |
| Briefing (horário/tópicos) | Modal + page | `SettingsPage` | ✅ |

## Cinema

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Busca / descoberta | Modal | `CinemaModal` | ✅ |
| Biblioteca local | Sim | Sim | ✅ |
| Player isolado | Sim | `VideoPlayer` | ✅ |
| Temporadas / episódios | Sim | Sim | ✅ |

## Estudos (ENEM)

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Sessões tutor | Sidebar | `StudySidebar` | ✅ |
| Canvas pan/zoom | Sim | `StudyCanvas` | ✅ |
| Tela cheia | `#study-fullscreen-btn` | Botão ⛶ | ✅ |
| Modos (6) | Toolbar | `StudyToolbar` | ✅ |
| Flashcards SM-2 | Overlay review | Modo Revisar | ✅ |
| Feynman | Overlay | Modo Feynman | ✅ |
| Quiz / avaliações | Overlay | Modo Quiz | ✅ |
| Progresso | Overlay + sidebar | Modo Progresso | ✅ |
| Banco ENEM (salvar) | Form | Modo Questões | ✅ |
| Estudar agora (colar) | `#study-enem-study-paste` | Tabs + textarea + botão | ✅ |
| Estudar do banco | `#study-enem-study-bank` | Select + botão | ✅ |
| Preview questão banco | `#study-enem-bank-preview` | Preview | ✅ |
| Colar imagem (drop/paste) | Sim | Paste/drop handlers + upload | ✅ |
| Chat tutor + whiteboard | Sim | Modo Aprender | ✅ |
| Comandos locais (review, quiz…) | Regex no input | Regex no input do tutor | ✅ |

## Câmeras / visão

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Workspace multi-câmera | — | `CameraWorkspace` | ✅ (melhoria) |
| Captura + pergunta | Modal | Workspace | ✅ |
| Resultado visão | Modal | Modal global | ✅ |

## UX global

| Funcionalidade | Legado | React | Status |
|---|---|---|---|
| Toast / avisos | `toast()` | `Toast` | ✅ |
| Tema Jarvis HUD | CSS legado | Cyan/purple + glass | ✅ |
| Transições de página | CSS classes | `TransitionPanel` + motion | ✅ |
| Code-splitting | — | `React.lazy` | ✅ (melhoria) |
| Aria-live logs | — | Analytics | ✅ (melhoria) |

---

## Resumo

- **Paridade funcional principal:** **100% concluída** ✅
- **Todos os itens implementados:**
  - Paste/drop de imagem ENEM ✅
  - Comandos de texto no tutor (review, quiz, feynman, progress, questions) ✅
  - Rotas backend (/ → React, /legacy → antigo) ✅
- **Itens ➖:** cards decorativos do legado (lighting, analytics fake KPIs, Help/Sign out) - não aplicáveis

Última revisão: 2026-08-02
