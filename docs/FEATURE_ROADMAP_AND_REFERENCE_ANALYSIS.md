# 🚀 Roadmap de Melhorias & Análise Completa de Projetos de Referência para o Jarvis

Este documento centraliza todas as funcionalidades, arquiteturas e oportunidades de inovação mapeadas a partir dos **8 projetos de referência** clonados na pasta `C:\Users\maria\Desktop\referenceprojects`.

---

## 📦 Visão Geral dos Repositórios de Referência

| Repositório | Foco Principal | Destaques Técnicos & Funcionais |
| :--- | :--- | :--- |
| **Ada-SI** | Interface Futurista, Tool Forge & Quests | • Canvas 3D Reativo (Three.js Tunnel & Core Sphere)<br>• Quest Log (Painel de Etapas com tempo decorrido e cancelamento)<br>• Tool Forge Pipeline (ToolPlanCard, ToolBuildViewer, PipApprovalCard, UiPreviewCard) |
| **Brahma-AI** | Automação de SO & Dispositivos | • Desktop Search indexado por tipo de arquivo e filtros temporais<br>• Controle de Dispositivos IoT (TP-Link Kasa)<br>• Automação de Clipboard e Screen Processor |
| **ai-memory-vault** | Memória Persistente & Priming | • Obsidian Vault como motor de memória externa sem limite de contexto<br>• AI Priming (injeção de notas/regras específicas por tipo de tarefa antes de executar)<br>• Daily Notes e Boot Config em Markdown (`VAULT-INDEX.md` / `CLAUDE.md`) |
| **private-agent** | Automação Mobile & Acesso Remoto | • Automação nativa do Android via Accessibility Service (leitura de tela, coordenadas)<br>• Controle Remoto via Bot do Telegram em segundo plano |
| **G0DM0D3** | IA Liberada, Tuning & Benchmarking | • **AutoTune**: Motor de hiperparâmetros adaptativo (temperatura, top_p, top_k) por categoria com aprendizado EMA<br>• **GODMODE / UltraPlinian**: Corrida paralela de múltiplos LLMs e pontuação composta<br>• **STM (Semantic Transformation Modules)**: Normalizador de saídas (remove hesitações como "Acho que", preâmbulos e firulas) |
| **IRIS-X** | HUD Holográfico & Mobile Vision | • Componentes Visuais Quantum HUD (`IrisQuantumHUD.tsx`, `IrisHolographicOrb.tsx`) e leitor biométrico<br>• Multimodal Screen Streaming em tempo real com Dock Flutuante Glassmorphic |
| **IRIS-AI** | Suíte Completa de Automação OS & Ferramentas | • **ScreenPeeler**: Captura de área retangular com OCR e envio direto para o clipboard (`Ctrl+Alt+X`)<br>• **Phantom Typer**: Injeção de digitação em qualquer janela/editor (`Ctrl+Alt+Space`)<br>• **Smart Drop Zones**: Organização autônoma de pastas (Downloads, Projetos)<br>• **Gerador de Documentos**: Geração de apresentações PowerPoint (.pptx), planilhas Excel (.xlsx) e PDFs estilizados<br>• **Wormhole**: Túneis para expor portas locais (localhost:3000/8000) para a internet<br>• **Mobile Telekinesis**: Controle total via ADB (toque, câmera remota, instalação de APKs)<br>• **AI Wallpaper Engine**: Troca de plano de fundo do Windows via linguagem natural |
| **Mark-L** | Continuidade de Sessão & Proatividade 2.0 | • **Session Memory**: Resumo da sessão anterior integrado no briefing matinal ("Ontem você parou em...")<br>• **Background Topic Monitoring**: Monitoramento diário de tópicos de interesse com notificações proativas<br>• **Proactive 2.0**: Proatividade consciente do horário, contexto recente e cooldowns não intrusivos<br>• **Clipboard Intelligence**: Painel flutuante com ações rápidas ao copiar texto (Traduzir, Explicar, Refatorar)<br>• **Instant Vision Acknowledgment**: Confirmação por voz imediata ao iniciar análise de tela/webcam |

---

## 🔍 Matriz de Paridade & Comparação com o Jarvis Atual

| Funcionalidade / Inovação | Origem | Estado Atual no Jarvis | Precisa Implementar no Jarvis? |
| :--- | :--- | :--- | :--- |
| **Orb 3D & Avatar Reativo em Three.js** | `Ada-SI` / `IRIS-X` / `IRIS-AI` | 2D HTML Canvas simples (`JarvisOrb.tsx`). | **SIM 🚀** (WebGL/Three.js, rotação por ponteiro, reatividade à voz e 5 estados de agente). |
| **Quest Log / Drawer Lateral de Etapas** | `Ada-SI` | Accordion estático `Reasoning.tsx` no chat. | **SIM 🚀** (Drawer retrátil com cronômetro, status por sub-etapa e botão de abortar). |
| **Tool Forge (Pipeline de Criação de Tools)** | `Ada-SI` / `IRIS-AI` | Execução manual via `DevAgent`/`HackerMode`. | **SIM 🚀** (Pipeline com `ToolPlanCard`, `ToolBuildViewer`, `PipApprovalCard` e `UiPreviewCard`). |
| **Busca Indexada na Área de Trabalho (Desktop Search)** | `Brahma-AI` / `IRIS-AI` / `Mark-L` | Manipulação genérica de arquivos em lote. | **SIM 🚀** (Busca rápida por categorias *code*, *doc*, *image* e filtros temporais *today*, *yesterday*). |
| **Controle de Casa Inteligente IoT (TP-Link Kasa)** | `Brahma-AI` | Nenhuma integração IoT. | **SIM 🚀** (Ferramenta `kasa_control.py` para descoberta e acionamento de tomadas/lâmpadas na rede local). |
| **AI Priming & Memória Externa em Markdown (Vault Engine)** | `ai-memory-vault` | Memória semântica ChromaDB e memória de perfil. | **SIM 🚀** (Injeção de regras/guias de conhecimento específicos antes de executar tarefas complexas). |
| **Controle Remoto via Telegram Bot & Mobile ADB** | `private-agent` / `IRIS-AI` | Apenas interface web local e atalhos Windows. | **SIM 🚀** (Bot de Telegram em background para comandos/voz remotos e controle ADB Android). |
| **AutoTune (Ajuste Dinâmico de Hiperparâmetros do LLM)** | `G0DM0D3` | Temperatura fixa na configuração. | **SIM 🚀** (Ajuste automático de `temperature`, `top_p`, `frequency_penalty` por tipo de query + aprendizado EMA). |
| **Módulos STM (Limpeza & Normalização de Respostas do LLM)** | `G0DM0D3` | Sem pós-processamento de formato de texto. | **SIM 🚀** (Filtro para remover hesitações como "Acho que", preâmbulos e enrolação). |
| **ScreenPeeler OCR (`Ctrl+Alt+X`) & Phantom Typer (`Ctrl+Alt+Space`)** | `IRIS-AI` | Análise de tela inteira via Gemini Vision. | **SIM 🚀** (Atalho para capturar região retangular com OCR para clipboard e injeção de texto em qualquer janela). |
| **Gerador de Apresentações, Planilhas & PDFs (PPTX, XLSX, PDF)** | `IRIS-AI` / `IRIS-X` | Apenas texto formatado em Markdown. | **SIM 🚀** (Ferramentas para gerar arquivos `.pptx`, `.xlsx` e `.pdf` estilizados sob demanda). |
| **Smart Drop Zones (Organização Autônoma de Pastas)** | `IRIS-AI` | Operações manuais de mover/copiar arquivos. | **SIM 🚀** (Regras automáticas para organizar Downloads e área de trabalho por tipo/projeto). |
| **Wormhole (Túneis de Porta Local para Web)** | `IRIS-AI` | Nenhuma integração de túnel. | **SIM 🚀** (Expor `localhost:8000` ou aplicações web desenvolvidas pelo Jarvis usando ngrok/localtunnel). |
| **Session Memory & Continuidade Diária (Yesterday recap)** | `Mark-L` | Histórico de conversas sem resumo matinal. | **SIM 🚀** (Resumo automático do encerramento da sessão para recautelar no briefing do dia seguinte). |
| **Background Topic Monitoring (Rss / News Watchdog)** | `Mark-L` | Leitor RSS manual. | **SIM 🚀** (Monitoramento diário em segundo plano de tópicos definidos pelo usuário com alerta proativo). |
| **Proactive 2.0 (Consciência de Horário, Contexto e Cooldowns)** | `Mark-L` | Sugestões proativas simples baseadas em horário. | **SIM 🚀** (Proatividade com rotação de temas, contexto da conversa recente e cooldown de 20 min). |
| **Clipboard Intelligence (Painel Flutuante)** | `Mark-L` | Histórico básico de cópias (`clipboard.py`). | **SIM 🚀** (Painel rápido acionado ao copiar texto com atalhos para Traduzir, Explicar, Refatorar). |
| **Instant Vision Acknowledgment** | `Mark-L` / `Brahma-AI` | O usuário aguarda em silêncio o processamento visual. | **SIM 🚀** (Resposta por voz/texto imediata "Analisando sua tela..." enquanto o Gemini Vision é executado). |

---

## 🗺️ Plano de Implementação / Roadmap em Fases (TODAS AS FASES CONCLUÍDAS ✅)

### 📍 Fase 1: Painel de Quests, Processos & Resposta Instantânea (UI/UX)
- [x] Implementar o `QuestLogPanel` (drawer lateral retrátil) no frontend React com status de sub-etapas (*pending*, *active*, *done*, *error*), cronômetro e botão de abortar quest.
- [x] Adicionar **Instant Vision Acknowledgment**: feedback sonoro/visual imediato ao solicitar análise de tela antes do processamento do modelo.

### 📍 Fase 2: Jarvis Orb 3D Reativo (Three.js & WebGL)
- [x] Substituir o canvas 2D do `JarvisOrb.tsx` por um visualizer 3D em Three.js (`JarvisOrb3D.tsx`).
- [x] Adicionar rotação interativa com o ponteiro do mouse, partículas iluminadas e transição fluida entre os 5 estados: `idle`, `thinking`, `streaming`, `tool_executing`, `celebrating`.

### 📍 Fase 3: Continuidade de Sessão, Proatividade 2.0 & Monitor de Tópicos
- [x] Implementar o **Session Memory Engine**: gerar um resumo curto ao final de cada sessão e integrá-lo ao briefing do dia seguinte (`save_session_summary`, `get_yesterday_summary`).
- [x] Evoluir o `ProactiveAgent` para o modo 2.0 (consciente de horário, contexto recente e rotação de tópicos).
- [x] Criar o **Background Topic Monitor**: verificação diária em background de termos configurados (`add_monitored_topic`, `check_monitored_topics_updates`).

### 📍 Fase 4: Automação Avançada de SO, Visão & Produtividade
- [x] Criar o **ScreenPeeler** (`screen_peeler.py`) para captura de tela retangular com OCR para o clipboard.
- [x] Criar o **Phantom Typer** (`phantom_typer.py`) para injeção de digitação direta na janela ativa do SO.
- [x] Implementar **Smart Drop Zones** (`smart_drop_zone.py`) para organização autônoma de pastas (Downloads, Desktop).
- [x] Integrar a Inteligência de Clipboard no `clipboard.py`.

### 📍 Fase 5: Expansão de Ferramentas (IoT, Gerador de Documentos & Mobile)
- [x] Integrar a busca rápida indexada no Desktop (`desktop_search.py`).
- [x] Adicionar suporte a **TP-Link Kasa IoT** (`kasa_control.py`).
- [x] Criar geradores autônomos de **PowerPoint (.pptx)**, **Excel (.xlsx)** e **PDF** (`document_generator.py`).
- [x] Adicionar bot de **Telegram para Controle Remoto** (`telegram_bot.py`) e suporte a **Mobile Telekinesis via ADB** (`mobile_adb.py`).

### 📍 Fase 6: Motor de Inteligência & Tool Forge Pipeline
- [x] Implementar o **AutoTune Sampling Engine** (`app/services/autotune.py`) para ajuste dinâmico de hiperparâmetros por categoria via EMA.
- [x] Adicionar o **STM (Semantic Transformation Modules)** (`app/services/stm_filters.py`) para filtrar prolixidade e hesitações das respostas.
- [x] Implementar o **AI Priming System** (`app/services/ai_priming.py`) para injeção de conhecimento contextual em tarefas específicas.
- [x] Construir a interface e pipeline de **Tool Forge** (`app/services/tool_forge.py`, `ToolForgeModal.tsx`, endpoint `/api/tool-forge`).

---
