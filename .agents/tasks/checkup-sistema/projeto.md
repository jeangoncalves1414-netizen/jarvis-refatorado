# Mapa do Projeto Jarvis — Checkup Detalhado do Sistema

**Data de criação:** 2026-01-11  
**Workspace:** `c:\Users\maria\Desktop\Jarvis`

---

## 1. Visão Geral da Arquitetura

O **Jarvis** é um assistente pessoal de IA desktop (Python + Windows) que orquestra chamadas a LLMs (Gemini, Groq, Oxyy) com ferramentas nativas (tools), memória semântica, sistema de confirmação de ações destrutivas e mecanismos de rate-limit com failover.

### Estrutura de Diretórios Principal

```
c:\Users\maria\Desktop\Jarvis\
├── app/
│   ├── agent/                   # Orquestrador do agente e tools
│   │   ├── orchestrator.py      # Loop principal do agente
│   │   ├── tools/               # Ferramentas nativas
│   │   │   ├── registry.py      # Registro de ferramentas
│   │   │   ├── checklist_tool.py
│   │   │   ├── memory_tool.py
│   │   │   ├── timer.py
│   │   │   ├── web_search.py
│   │   │   ├── video_analyst_tool.py
│   │   │   └── ... (50+ tools)
│   │   ├── modes/               # Modos especializados (tutor, language)
│   │   └── subagents/           # Sub-agentes especializados
│   │
│   ├── services/                # Serviços centrais
│   │   ├── llm.py               # LLMService (Gemini/Groq/Oxyy, rate limit, failover)
│   │   ├── vision.py            # VisionService (captura de tela/câmera)
│   │   ├── memory_kernel.py     # Kernel de memória (save_fact)
│   │   └── ... (70+ services)
│   │
│   ├── storage/                 # Camada de persistência
│   │   ├── checklist_store.py
│   │   ├── memory_facts.py
│   │   ├── session_store.py
│   │   └── vector/              # Memória semântica (Chroma)
│   │       └── semantic_memory.py
│   │
│   └── core/                    # Sistemas de segurança e controle
│       ├── critical_confirm.py  # Sistema CriticalConfirm
│       ├── rate_limit.py
│       ├── guardrails.py
│       └── runs.py              # Rastreamento de pedidos
│
├── tests/                       # Suíte de testes
│   ├── test_orchestrator.py
│   ├── test_memory_tool.py
│   └── ... (50+ testes)
│
├── data/                        # Dados persistidos
│   ├── checklists/
│   ├── memory_facts.json
│   └── sessions/
│
└── .agents/                     # Metadados de workflows
    └── tasks/
        └── checkup-sistema/     # Este checkup
```

---

## 2. Padrões-Chave Identificados

### 2.1 Sistema CriticalConfirm (Confirmação de Ações Destrutivas)

**Localização:** `app/core/critical_confirm.py`

**Como funciona:**
- Sistema de confirmação para ações críticas (ex: excluir checklist)
- Mantém estado `_pending` com request ID, tool name e detail
- Bloqueia execução até aprovação (timeout 300s)
- Estado salvo em `data/critical_confirm.json` (enabled/disabled)
- Usa `threading.Event` para sincronização entre request e resolve

**Integração:**
- Instanciado em `AgentOrchestrator.__init__()` como `self.critical_confirm`
- Ferramentas destrutivas devem chamar `critical_confirm.request()` antes de executar
- Painel UI chama `critical_confirm.resolve()` com aprovação do usuário

### 2.2 Agent Loop (Loop Principal do Agente)

**Localização:** `app/agent/orchestrator.py`

**Como funciona:**
- `AgentOrchestrator._run_llm_with_tools()` é o orquestrador central
- Fluxo:
  1. Resolve modo ativo (auto-routing: `resolve_active_mode()`)
  2. Constrói system prompt com contexto situacional (`build_turn_sections()`)
  3. Busca memórias relevantes (semantic search no Chroma + memory_facts)
  4. Chama LLM com ferramentas declaradas (`registry.get_tool_declarations()`)
  5. Executa ferramentas retornadas (`ActionExecutor`)
  6. Multi-turn: até 3 rodadas de tool calls
  7. Retorna `AgentPlan` com intent, summary, actions
- Suporta streaming com callbacks `on_chunk`, `on_reasoning`

### 2.3 Recovery de Rate-Limit (`_recover_synthesis`)

**Localização:** `app/services/llm.py` (linha ~1322)

**Como funciona:**
- Chamado quando síntese final falha com 429 após ferramentas já executadas
- Marca chave atual em cooldown via `_key_rotator.mark_rate_limit()`
- Tenta obter próxima chave com `_key_rotator.get_key()`
- Monta request simplificado: só user message + resultados confirmados (sem tools)
- 1 tentativa de retry com nova chave
- Se falhar, retorna `None` (warning na Central, resposta montada com resultados)

**Limitação atual:** apenas 1 retry; não implementa exponential backoff curto

### 2.4 Busca Semântica de Memória

**Localização:** `app/storage/vector/semantic_memory.py` + `app/agent/tools/memory_tool.py`

**Como funciona:**
- `SemanticMemory` usa Chroma para vetorizar memórias
- Collections: `user_memory` (global), `episodic_memory` (resumos diários)
- `memory_tool.py`:
  - **save**: grava em `memory_facts` + indexa no Chroma (collection `user_memory`)
  - **search**: busca em `memory_facts.relevant()` + busca vetorial no Chroma
  - **list**: lista direto de `memory_facts`
  - **forget**: remove de `memory_facts` + delete no Chroma
- `metadata` dos vetores: `fact_id`, `session_id`, `importance`

**Problema identificado (ponto 3 do checkup):**
- Busca vetorial não filtra por session_id → memória cross-session OK
- MAS: `memory_facts.relevant()` pode estar filtrando por session (precisa investigar)

### 2.5 Tool Selection — Keyword Matcher

**Localização:** `app/agent/tools/registry.py` (linhas ~107-130)

**Como funciona:**
- `GROQ_KEYWORD_TOOLS`: lista de `(regex_pattern, tuple[tool_names])`
- Exemplos:
  - `r"\bchecklist|\blista\b|\blistas\b"` → `("checklist_tool",)`
  - `r"\btaref|\bpendencia"` → `("task_tool",)`
- Normalização: `normalize_name()` remove acentos, converte para lowercase
- Matcher aplica regex sobre texto normalizado
- Se match, adiciona tool ao `allowed_tool_names`

**Problema identificado (ponto 5 do checkup):**
- `\blista\b` matcha "lista" em qualquer contexto (lista de memórias, lista de tarefas)
- Falta contexto negativo: se "lista.*memória", não ativar checklist_tool

### 2.6 Sistema de Rotação de Chaves (KeyRotator)

**Localização:** `app/services/llm.py` (classe `KeyRotator`)

**Como funciona:**
- Mantém dict `cooldowns` com timestamp de fim do cooldown por chave
- Mantém dict `indices` com índice atual por provedor (groq/gemini/oxyy)
- `get_key()`: round-robin entre chaves não-em-cooldown
- `mark_cooldown()`: bloqueia chave por X segundos
- `mark_rate_limit()`: extrai `retry_seconds()` do erro 429 e bloqueia
- `rotate_next()`: força próxima chave (usado em failover imediato)

**Integração:** `LLMService._api_key_for()` usa `_key_rotator.get_key()`

---

## 3. Mapeamento dos 10 Pontos do Checkup

| # | Ponto do Checkup | Arquivos Relevantes | Resumo de Como Funciona |
|---|------------------|---------------------|-------------------------|
| 1 | **Checklist — LLM escolhe ação errada** | `app/agent/tools/checklist_tool.py` | Tool com actions: `create_list`, `add_items`, `get_list`, `list_all`, `delete_list`. Description do param `action` precisa deixar claro: "list_all" lista resumos; "get_list" pega itens de uma lista específica. |
| 2 | **Visão — modelo hardcoded sem validação** | `app/services/vision.py` (linha ~35), `app/services/llm.py` | `VisionService.__init__()` hardcoda `self.groq_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")`. Sem health-check: chamada falha se modelo obsoleto. Precisa validar na inicialização e fallback para Gemini Vision. |
| 3 | **Memória — busca cross-session falha** | `app/agent/tools/memory_tool.py` (linha ~64-82), `app/storage/memory_facts.py` | `MemoryTool._search()` busca em `memory_facts.relevant()` + busca vetorial global no Chroma. Chroma OK (não filtra session). Investigar se `memory_facts.relevant()` filtra session internamente. |
| 4 | **Rate limit — retry com backoff** | `app/services/llm.py` (função `_recover_synthesis`, linha ~1322) | `_recover_synthesis()` faz 1 retry com próxima chave. Não implementa exponential backoff. Precisa loop de retry: 2s, 4s (max 2 tentativas) antes de desistir. |
| 5 | **Tool selection — keyword matcher frágil** | `app/agent/tools/registry.py` (linha ~107-130, `GROQ_KEYWORD_TOOLS`) | Regex `r"\blista\b"` matcha "lista" sem contexto. Adicionar regex negativo: se "lista.*memória", descartar checklist_tool; se "lista.*tarefas", descartar checklist_tool e ativar task_tool. |
| 6 | **Sequência de ações — confirmação do resultado intermediário** | `app/agent/orchestrator.py` (linha ~626+, loop de tool calls) | Agent loop executa tools via `ActionExecutor`, mas `response.function_calls` pode estar vazio se execução foi interna. Rastreamento em `context.tool_calls` ou `turn_meta` para auditoria. |
| 7 | **Timer — sem feedback audível confirmado** | `app/agent/tools/timer.py` (linha ~49, `_fire()`) | `_fire()` toca beep 3x com `winsound.Beep()`, mas retorno de `set_timer`/`set_alarm` é imediato (não espera disparo). Adicionar callback de confirmação ou log quando áudio dispara. |
| 8 | **Web search — fallback quando Groq corta a síntese** | `app/agent/tools/web_search.py`, `app/services/llm.py` (_recover_synthesis) | `_recover_synthesis()` monta resposta com `_tool_results_text()` (conteúdo de tool messages). Web search precisa guardar snippets crus em `data` do ToolResult para que recovery tenha material. |
| 9 | **Testes de integração automatizados** | `tests/` (atualmente: `test_orchestrator.py`, `test_memory_tool.py`, etc.) | Existem testes unitários. Falta `tests/test_live_integration.py` que sobe servidor real, executa 11 cenários end-to-end (checklist, memória, timer, web search, vision, etc.) e valida respostas. |
| 10 | **Checklist delete_list por título sem confirm** | `app/agent/tools/checklist_tool.py` (action `delete_list`) + `app/core/critical_confirm.py` | `delete_list` chama `checklist_store.delete_list()` imediatamente. Precisa preview com `critical_confirm.request(tool="checklist_tool", detail="Excluir lista 'X' com N itens?")` antes. |

---

## 4. Componentes Críticos Detalhados

### 4.1 LLMService (app/services/llm.py)

**Responsabilidades:**
- Abstração unificada para Gemini, Groq, Oxyy
- Rotação de chaves com cooldown (KeyRotator)
- Failover automático entre provedores
- Streaming com callbacks (on_chunk, on_reasoning)
- Function calling nativo (OpenAI format para Groq/Oxyy, Gemini format para Gemini)
- Recovery de síntese quando rate limit após tools (`_recover_synthesis`)

**Métodos principais:**
- `ask()`: chamada simples (prompt → string)
- `generate()`: chamada estruturada (contents + tools → LLMResponse)
- `generate_stream()`: streaming com callbacks

**Rate Limit Handling:**
- `is_rate_limit(error)`: detecta 429
- `KeyRotator.mark_rate_limit()`: cooldown + retry_seconds do header
- Failover: Groq → Gemini, Gemini → Groq (via SmartLLMRouter)

### 4.2 ToolRegistry (app/agent/tools/registry.py)

**Responsabilidades:**
- Registro central de todas as ferramentas
- Filtragem por modo (general, tutor, language)
- Filtragem por provedor (Groq: keyword matching para reduzir TPM)
- Declaração de ferramentas para LLM (JSON Schema)
- Execução de ferramentas com rastreamento de ações

**Ferramentas registradas:** 70+ (file_manager, web_search, memory, checklist, timer, vision, spotify, whatsapp, etc.)

**Keyword Matcher:** `GROQ_KEYWORD_TOOLS` + `LOOP_KEYWORD_TOOLS` (regex → tools)

**MCP Tools:** ferramentas dinâmicas de servidores MCP (via `DynamicMCPTool`)

### 4.3 SemanticMemory (app/storage/vector/semantic_memory.py)

**Responsabilidades:**
- Indexação vetorial de memórias (Chroma)
- Collections: `user_memory`, `episodic_memory`
- Busca semântica com threshold de distância (`USER_MEMORY_MAX_DISTANCE`)
- Metadata: fact_id, session_id, importance

**Métodos principais:**
- `add_memory(collection, text, metadata, importance)`
- `search_memories(collection, query, n_results, max_distance)`
- `delete_where(collection, filter)`

### 4.4 ActionExecutor (app/agent/action_executor.py)

**Responsabilidades:**
- Executa tool calls retornados pelo LLM
- Aplica guardrails (ToolCallGuardrailController)
- Rastreamento de ações (personal_history)
- Policy de aprovação (auto-approve vs. confirmação)

**Integração:** chamado por `orchestrator._run_llm_with_tools()` no loop de tools

### 4.5 CriticalConfirm (app/core/critical_confirm.py)

**Responsabilidades:**
- Confirmação de ações destrutivas
- Estado: _pending (req_id, tool, detail)
- Bloqueio: `_done.wait(timeout=300)`
- Resolve: `resolve(req_id, approved)`

**Persistência:** `data/critical_confirm.json` (enabled flag)

**Integração:** ferramentas destrutivas chamam `critical_confirm.request()` antes

---

## 5. Fluxo de um Pedido do Usuário

```
1. Usuário envia mensagem
   ↓
2. OrchestrationService.orchestrate()
   ↓
3. AgentOrchestrator._run_llm_with_tools()
   ↓
4. Resolve modo ativo (resolve_active_mode)
   ↓
5. Busca memórias relevantes (semantic_memory.search_memories + memory_facts.relevant)
   ↓
6. Constrói system prompt com contexto (build_turn_sections)
   ↓
7. LLMService.generate_stream() com ferramentas permitidas
   ↓
8. LLM retorna function_calls
   ↓
9. ActionExecutor executa cada tool call
   ↓
10. Se tool destrutivo → CriticalConfirm.request() (bloqueia)
   ↓
11. Resultado volta para LLM (nova rodada, max 3)
   ↓
12. Síntese final (resposta ao usuário)
   ↓
13. Se rate limit 429 → _recover_synthesis (retry com nova chave)
   ↓
14. Resposta final + tool_results markers (search, cinema, media)
```

---

## 6. Sistemas de Segurança e Controle

### 6.1 Rate Limiting
- **KeyRotator:** cooldown por chave, round-robin
- **ProviderRateLimit exception:** sobe quando todas as chaves estão em cooldown
- **wait_message():** mensagem user-facing com tempo de espera

### 6.2 Tool Guardrails
- **ToolCallGuardrailController:** limites por turno (ex: max 3 chamadas do mesmo tool)
- **ToolGuardrails:** catálogo de metadados de risco (risk: safe/destructive/destructive-silent)
- **CriticalConfirm:** confirmação explícita para risk=destructive

### 6.3 Run Tracking
- **current_run:** contexto do pedido atual (run_id, origin, mode, source)
- **record_run_step():** log estruturado de etapas (step/warning/failure)
- **track_model_call decorator:** rastreamento de chamadas a LLMs

### 6.4 Cancellation
- **RunCancelled exception:** interrupção de pedidos (botão "Parar")
- **check_run_cancelled():** verificação periódica em loops longos

---

## 7. Notas para os Investigadores dos 10 Pontos

### Ponto 1 (Checklist — LLM escolhe ação errada)
- **Ação:** Melhorar description do parâmetro `action` em `checklist_tool.py`
- **Renomear:** `list_all` → `list_summaries` (deixa claro que lista resumos, não itens)
- **Verificar:** Se LLM confunde "liste os itens da checklist X" com `list_all` (deveria ser `get_list`)

### Ponto 2 (Visão — modelo hardcoded)
- **Ação:** Adicionar health-check em `VisionService.__init__()` ou lazy no primeiro uso
- **Fallback:** Se Groq Vision model inválido, usar Gemini Vision (`gemini-flash-latest`)
- **Validação:** Tentar listar modelos disponíveis ou catch no primeiro `analyze()`

### Ponto 3 (Memória — busca cross-session)
- **Investigar:** `app/storage/memory_facts.py` → método `relevant()`
- **Verificar:** Se `memory_facts.relevant()` filtra por session_id internamente
- **Solução:** Garantir que busca é global (sem filtro de session)

### Ponto 4 (Rate limit — retry com backoff)
- **Ação:** Implementar loop de retry em `_recover_synthesis()`
- **Backoff:** 2s, 4s (max 2 tentativas adicionais)
- **Condição:** Só retry se `cooldown_remaining < 10s` (evita espera longa)

### Ponto 5 (Tool selection — keyword matcher)
- **Ação:** Adicionar contexto negativo em `GROQ_KEYWORD_TOOLS`
- **Exemplo:** Se "lista.*memória", remover checklist_tool de `allowed_tools`
- **Implementar:** Lógica de exclusão em `allowed_tool_names()`

### Ponto 6 (Sequência de ações — auditoria de resultados)
- **Investigar:** Por que `tools: []` quando LLM diz "Li o arquivo"
- **Verificar:** Se `turn_meta.record()` ou `context.tool_calls` rastreiam execuções internas
- **Solução:** Garantir que todas as tool calls aparecem em `response.function_calls`

### Ponto 7 (Timer — feedback audível)
- **Ação:** Adicionar callback de confirmação em `_fire()`
- **Opção 1:** Callback que retorna True/False (áudio tocou)
- **Opção 2:** Log em arquivo quando `_fire()` é chamado (auditoria)

### Ponto 8 (Web search — fallback de síntese)
- **Ação:** `web_search.py` deve guardar snippets crus em `data` do `ToolResult`
- **Garantir:** `_recover_synthesis()` constrói resposta com snippets quando síntese falha
- **Verificar:** Se `_tool_results_text()` extrai conteúdo de `data`

### Ponto 9 (Testes de integração)
- **Criar:** `tests/test_live_integration.py`
- **Fixture:** Sobe/desce servidor real (ou chama `orchestrator` diretamente)
- **Cenários:** 11 casos (checklist, memória, timer, web search, vision, etc.)
- **Validação:** Verifica resposta + efeitos colaterais (arquivo criado, timer ativo, memória salva)

### Ponto 10 (Checklist delete sem confirm)
- **Ação:** Em `checklist_tool.py`, action `delete_list`:
  1. Resolver lista (id ou título)
  2. Contar itens
  3. Chamar `critical_confirm.request(tool="checklist_tool", detail=f"Excluir lista '{title}' com {count} itens?")`
  4. Se aprovado, executar `checklist_store.delete_list()`
- **Marcar:** Metadata da tool com `risk: "destructive"` no catálogo

---

## 8. Arquivos-Chave por Subsistema

### Orquestração
- `app/agent/orchestrator.py` — Loop principal do agente
- `app/agent/action_executor.py` — Executor de tool calls
- `app/agent/tool_guardrails.py` — Guardrails de segurança

### LLM e Rate Limit
- `app/services/llm.py` — LLMService, KeyRotator, _recover_synthesis
- `app/services/llm_router.py` — SmartLLMRouter (failover)
- `app/services/rate_limits.py` — Detecção de 429, retry_seconds

### Tools
- `app/agent/tools/registry.py` — Registro central
- `app/agent/tools/checklist_tool.py` — Checklist management
- `app/agent/tools/memory_tool.py` — Memória durável
- `app/agent/tools/timer.py` — Alarmes e timers
- `app/agent/tools/web_search.py` — Busca web (DuckDuckGo/Bing)
- `app/agent/tools/vision_tool.py` — Análise de tela/câmera

### Memória
- `app/storage/memory_facts.py` — Fonte de verdade (JSON)
- `app/storage/vector/semantic_memory.py` — Índice vetorial (Chroma)
- `app/services/memory_kernel.py` — save_fact, memory_slots

### Segurança
- `app/core/critical_confirm.py` — Sistema CriticalConfirm
- `app/core/guardrails.py` — ToolGuardrails, catálogo de risco
- `app/core/rate_limit.py` — RateLimiter
- `app/core/runs.py` — Rastreamento de pedidos, RunCancelled

### Testes
- `tests/test_orchestrator.py` — Testes do loop principal
- `tests/test_memory_tool.py` — Testes da memória
- `tests/conftest.py` — Fixtures compartilhados

---

## 9. Comandos de Build e Teste

### Build
- Não há build compilado (Python interpretado)
- Dependências: `pip install -r requirements.txt`

### Testes
- **Todos os testes:** `pytest tests/ -v`
- **Teste específico:** `pytest tests/test_memory_tool.py -v`
- **Com cobertura:** `pytest --cov=app --cov-report=html`

### Execução
- **Iniciar Jarvis:** `python main.py` ou `iniciar_jarvis.bat`
- **Modo dev:** `python app/ui/panel.py` (painel web)

---

## 10. Conclusão do Mapa

Este documento mapeia a arquitetura do sistema Jarvis e localiza os 10 pontos do checkup com precisão cirúrgica. Os investigadores devem:

1. Ler este mapa PRIMEIRO (contexto compartilhado)
2. Abrir os arquivos específicos listados para cada ponto
3. Confirmar o problema descrito no checkup
4. Propor correção fundamentada no código real
5. Escrever testes de verificação

**Próxima etapa:** Investigadores mergulham nos 10 pontos, um por vez, armados com este mapa completo da arquitetura.

---

**Fim do Mapa do Projeto Jarvis**
