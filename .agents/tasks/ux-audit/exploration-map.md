# UX/DX Audit — Exploration Map

**Data**: 2025-01-XX  
**Objetivo**: Mapear áreas relevantes para auditoria de experiência do usuário (UX) e desenvolvedor (DX)

---

## 1. Arquivos Mais Relevantes para UX

### Core — Feedback ao Usuário
- **`app/ui/panel/app.py`** — Renderizador de painel; HTML estático; mensagens de status e cards visuais
- **`app/main.py`** — Ponto de entrada; janela desktop (pywebview); system tray; gerenciamento de porta/processo
- **`app/core/telemetry.py`** — Log estruturado de eventos; silencioso em caso de erro (não expõe falhas ao usuário)
- **`app/core/critical_confirm.py`** — Sistema de confirmação para ações críticas; timeout de 5 min; mensagem console

### Agente — Orquestração e Respostas
- **`app/agent/orchestrator.py`** — Motor principal do agente; lógica de turno; escolha de ferramentas; extração de memória; tratamento de erro e rate limiting
- **`app/services/llm.py`** — Gerenciador de LLM com rotação de chaves; rate limit (429); cooldown; fallback entre Groq/Gemini/Oxyy; mensagens de erro ao usuário
- **`app/agent/tools/registry.py`** — Registro de ferramentas; keyword matching para Groq (GROQ_KEYWORD_TOOLS); modos de estudo; ferramentas MCP dinâmicas
- **`app/agent/action_executor.py`** — Executor de ações; proposta/aprovação; status `awaiting_confirmation`
- **`app/storage/action_store.py`** — Armazena ações; estados `running`, `awaiting_confirmation`, `authorized`; expiração de propostas

### Rate Limit & Erros
- **`app/services/rate_limits.py`** — Funções de detecção de rate limit (429); parsing de `retry-after`; mensagens seguras (sem credenciais)
- **`app/core/capability_health.py`** — Análise de falhas de provedor; máscaras de chaves; mensagens user-facing ("Limite de uso do provedor")
- **`app/core/rate_limit.py`** — RateLimiter genérico com janela deslizante; sleep interno (bloqueante)

### Ferramentas Visíveis ao Usuário
- **`app/agent/tools/checklist_tool.py`** — Checklist estilo Google Keep; ações `create_list`, `add_items`, `get_list`, `list_summaries`, `delete_list`; parsing de linguagem natural
- **`app/agent/tools/whatsapp.py`** — Envia mensagens WhatsApp; **mensagens técnicas anti-spam/anti-loop** expostas diretamente ao usuário
- **`app/agent/tools/timer.py`** — Timer/alarme; beeps do Windows; callbacks; feedback "Li o arquivo" sem tool_calls
- **`app/agent/tools/web_search.py`** — Busca web; síntese de resultados; fallback em caso de rate limit
- **`app/agent/tool_activity.py`** — Gera labels/speech para atividades; usado para feedback de progresso

### Contexto e Memória
- **`app/core/pattern_learner.py`** — Aprende padrões de comportamento; notificações proativas; callbacks
- **`app/agent/loop_policy.py`** — Política de loop vs turno único; detecção de wait_intent (`aguarde X segundos`)

---

## 2. Hotspots Encontrados (Grep)

### 2.1 Mensagens Técnicas Expostas ao Usuário

**Arquivo**: `app/agent/tools/whatsapp.py`  
**Linhas**: 70, 72  
**Snippet**:
```python
return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")
return ToolResult(ok=False, message="ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos.")
```
**Problema**: Mensagens técnicas com termos de engenharia ("ANTI-SPAM", "ANTI-LOOP") são mostradas diretamente ao usuário em vez de mensagens naturais.

---

### 2.2 Rate Limit (429) — Mensagens e Tratamento

**Arquivo**: `app/services/llm.py`  
**Linhas**: múltiplas (87, 118-119, 469, 723, 1014, 1339, 1434)  
**Snippets**:
```python
# Linha 87
print(f"[KeyRotator] Chave {mask_key(key)} colocada em cooldown por {int(duration_seconds)}s devido a Rate Limit (429).")

# Linha 118-119 (user-facing)
if seconds <= 15:
    return "Estou um pouco sobrecarregado no momento. Tente novamente em alguns segundos."
return f"O serviço atingiu um {reason}. Tente novamente em cerca de {seconds} segundos."

# Linha 1339-1356 (_recover_synthesis)
def _recover_synthesis(error: Exception) -> str | None:
    """Tenta recuperar síntese usando chave alternativa quando rate limit ocorre.
    
    TECH DEBT (FINDING 3 - REVIEW SPRINT 1):
    [...]
    Por enquanto, a solução atual resolve 90% dos casos (web search rate limit)
    e é backward-compatible com o sistema existente.
    """
```
**Problema**: Retry com backoff curto (linha 1434-1436) implementado, mas ainda desiste rapidamente. Mensagem "Estou um pouco sobrecarregado" é boa, mas poderia ter fallback mais robusto.

---

### 2.3 `time.sleep` — Bloqueios Síncronos

**Arquivos e Contextos**:
- `app/services/voice/wake_word.py` (linhas 209, 217, 220) — Polling de wake word com sleep; pode travar interface
- `app/agent/tools/spotify.py` (linhas 165, 175, 178, 181, 183, 185) — Sleep para esperar renderização do Spotify (2-5s); **UX ruim se silencioso**
- `app/agent/tools/timer.py` (linha 87) — Sleep de 1s no timer; linha 103: sleep de 0.15s entre beeps
- `app/agent/tools/phantom_typer.py` (linhas 32, 42) — Sleep antes de digitar (0.5s delay); pode parecer lento
- `app/core/rate_limit.py` (linha 27) — Sleep bloqueante durante rate limiting; trava o thread
- `app/services/app_manager.py` (linhas 330, 405) — Sleep após fechar/abrir app (0.3-0.4s); bloqueante
- `app/main.py` (linhas 59, 155, 320, 351) — Sleep para aguardar porta liberar; main loop

**Problema**: Muitos `time.sleep` bloqueantes em operações que o usuário espera. Sem feedback visual, o usuário não sabe se o sistema travou ou está processando.

---

### 2.4 Mensagens de Espera e Status

**Arquivos**:
- `app/agent/loop_policy.py` — Detecta `aguarde X segundos` na fala do usuário via regex
- `app/agent/tool_activity.py` (linha 41) — Gera label "Aguardar X segundos" para feedback
- `app/storage/action_store.py` (linhas 211, 228) — Status `awaiting_confirmation` com mensagem "Aguardando sua aprovação"
- `app/agent/react_loop.py` (linha 37) — `WAITING_TEXT`: "A etapa {n} precisa da sua aprovação na Central: {preview} Assim que você aprovar, eu continuo sozinho."

**Observação**: Sistema de status `awaiting_confirmation` bem estruturado, mas a mensagem `WAITING_TEXT` poderia ser mais concisa.

---

### 2.5 Errors e Failure Messages

**Exemplos**:
- `app/core/capability_health.py` (linhas 57-68) — Traduz status HTTP para mensagens user-friendly:
  - 429 → "Limite de uso do provedor"
  - 401/403 → "Chave recusada pelo provedor"
  - Timeout → "O provedor não respondeu a tempo"
- `app/services/llm.py` (linhas 640, 642-643) — Mensagens de erro Gemini/Groq:
  - "Erro de autenticação com a API Gemini. Verifique a GEMINI_API_KEY no .env."
  - "Limite de taxa da API Gemini excedido. Tente novamente em alguns instantes."
  - "Modelo 'X' não encontrado. Verifique GEMINI_MODEL no .env."

**Observação**: Mensagens de erro bem escritas, mas algumas ainda expõem detalhes técnicos (.env, nomes de variáveis).

---

## 3. Hipóteses Iniciais de Problemas UX

### Hipótese 1: **Feedback Visual Ausente Durante Operações Longas**
- **Evidência**: Múltiplos `time.sleep` (Spotify 2-5s, phantom_typer 0.5s, app_manager 0.3-0.4s) sem feedback
- **Impacto**: Usuário não sabe se o sistema está processando ou travado
- **Investigação**: Adicionar spinners, progress indicators ou mensagens intermediárias ("Aguardando Spotify abrir...")

### Hipótese 2: **Mensagens Técnicas Expostas ao Usuário**
- **Evidência**: "ANTI-SPAM", "ANTI-LOOP", "AWAITING_CONFIRMATION", "Verifique a GEMINI_API_KEY no .env"
- **Impacto**: Linguagem de engenharia confunde usuário leigo; quebra imersão
- **Investigação**: Reescrever mensagens para linguagem natural ("Espere um pouco antes de enviar outra mensagem")

### Hipótese 3: **Rate Limit Recovery Insuficiente**
- **Evidência**: `_recover_synthesis` tenta 1 chave alternativa e desiste; backoff curto implementado mas pode não ser suficiente para cooldowns > 15s
- **Impacto**: Usuário recebe "sobrecarregado" mesmo quando há chaves disponíveis com cooldown curto restante
- **Investigação**: Implementar retry mais persistente; usar todas as chaves disponíveis; fallback cross-provider mais agressivo

### Hipótese 4: **Keyword Matcher Frágil (Tool Selection)**
- **Evidência**: `GROQ_KEYWORD_TOOLS` usa regex estático; "lista" matcha checklist_tool mesmo quando usuário quer "listar memórias"
- **Impacto**: Ferramenta errada escolhida; frustra usuário que precisa repetir
- **Investigação**: Adicionar contexto negativo (ex: `lista.*memória` → não ativar checklist); usar embedding semântico para desambiguação

### Hipótese 5: **Checklist: Ambiguidade entre `list_all` e `get_list`**
- **Evidência**: Original user request (issue 1): "liste os itens da checklist X" → LLM chama `list_summaries` ao invés de `get_list`
- **Impacto**: Usuário pede detalhes de uma lista, recebe só resumos de todas
- **Investigação**: Renomear `list_all` → `list_summaries`; melhorar description do parâmetro `action`; adicionar exemplos no docstring

---

## 4. Próximos Passos

1. **Auditoria Profunda de Feedback Visual**:
   - Mapear todos os pontos onde `time.sleep > 0.5s` ocorre
   - Adicionar mensagens intermediárias ou spinners
   - Testar fluxos longos (Spotify, web search, vision)

2. **Reescrita de Mensagens User-Facing**:
   - Criar glossário de mensagens naturais para substituir termos técnicos
   - Auditar todas as strings retornadas em `ToolResult.message`
   - Remover menções a `.env`, variáveis de ambiente, status codes

3. **Stress Test de Rate Limiting**:
   - Simular rate limit em todas as chaves simultaneamente
   - Verificar se retry com backoff funciona corretamente
   - Testar fallback cross-provider (Groq → Gemini → Oxyy)

4. **Melhorar Tool Selection (Keyword Matching)**:
   - Adicionar contexto negativo para desambiguação
   - Considerar embedding semântico para pedidos ambíguos
   - Logar casos de tool selection errada para análise

5. **Testes de Integração Automatizados** (issue 9 do user):
   - Criar `tests/test_live_integration.py` com os 11 cenários
   - Fixture para subir/descer servidor
   - Rodar no CI para detectar regressões UX

---

## Notas

- O sistema tem bom tratamento de rate limit (429), mas pode ser mais resiliente
- Mensagens de erro são geralmente claras, mas ainda expõem detalhes técnicos
- Falta feedback visual durante operações síncronas longas
- Sistema de confirmação (`awaiting_confirmation`) bem estruturado
- Pattern learner e proatividade implementados, mas sem feedback audível confirmado (issue 7)
