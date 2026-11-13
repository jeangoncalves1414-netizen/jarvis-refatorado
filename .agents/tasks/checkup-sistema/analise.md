# Análise Completa do Checkup do Sistema Jarvis

**Data**: 2026-01-11  
**Investigador**: Kiro (análise estática de código)  
**Workspace**: `c:\Users\maria\Desktop\Jarvis`

---

## Resumo Executivo

De 10 pontos críticos investigados:
- ✅ **6 CONFIRMADOS** (pontos 1, 2, 4, 7, 8, 9, 10)
- ❌ **1 REFUTADO** (ponto 3 - memória já é cross-session por design)
- ⚠️ **2 PARCIALMENTE CONFIRMADOS** (pontos 5, 6 - necessitam validação runtime)
- 🟡 **1 NÃO VERIFICÁVEL** (ponto 6 - requer execução com LLM real)

**Prioridade de correção**:
1. 🔴 **ALTA**: Pontos 4, 8, 10 (rate limit recovery, web search fallback, delete sem confirmação)
2. 🟡 **MÉDIA**: Pontos 1, 2, 5, 7 (tool descriptions, vision fallback, keyword matcher, timer feedback)
3. 🟢 **BAIXA**: Ponto 9 (testes de integração - melhoria de QA)

---

## Ponto 1: Checklist — LLM Escolhe Ação Errada

### Status: ✅ CONFIRMADO

**Problema**: Quando usuário pede "liste os itens da checklist X", o LLM às vezes chama `list_all` ao invés de `get_list` com o título.

### Evidência

**Arquivo**: `app/agent/tools/checklist_tool.py` linha 44-47

```python
"action": {
    "type": "string",
    "enum": ["create_list", "add_items", "toggle_item", "get_list", "list_all", "list", "delete_list", "delete_item"],
    "description": "create_list deve incluir text ou items quando o usuário pedir itens. Consultar não exclui: use delete_list para excluir.",
},
```

**Análise**:
- A description do parâmetro `action` é genérica e não diferencia claramente:
  - `list_all` / `list` → lista RESUMOS de todas as checklists (apenas títulos + contadores)
  - `get_list` → busca ITENS de uma checklist específica
- LLM pode interpretar "liste os itens" como comando para `list_all` se a description não for explícita

### Gravidade: 🟡 MÉDIA
- **Impacto funcional**: Usuário recebe lista de resumos ao invés dos itens solicitados
- **Frequência**: Intermitente (depende do contexto e modelo usado)

### Solução Proposta

**1. Renomear `list_all` → `list_summaries`** (melhora semântica):
```python
"enum": ["create_list", "add_items", "toggle_item", "get_list", "list_summaries", "delete_list", "delete_item"],
```

**2. Melhorar description do parâmetro**:
```python
"description": (
    "get_list: busca ITENS de uma checklist específica (use title ou list_id); "
    "list_summaries: lista RESUMOS (apenas títulos) de todas as checklists; "
    "create_list deve incluir text ou items quando o usuário pedir itens; "
    "Consultar não exclui: use delete_list para excluir."
),
```

**3. Melhorar description individual** (quando model suportar):
```python
"get_list": {
    "type": "string",
    "description": "Busca os ITENS pendentes e concluídos de uma checklist específica. Use quando o usuário quiser ver 'os itens de X', 'o que tem em X', etc."
},
"list_summaries": {
    "type": "string",
    "description": "Lista RESUMOS (apenas títulos e contadores) de TODAS as checklists. Use quando o usuário pedir 'quantas checklists tenho', 'liste minhas checklists', etc."
}
```

---

## Ponto 2: Visão — Modelo Hardcoded sem Validação

### Status: ✅ CONFIRMADO

**Problema**: `GROQ_VISION_MODEL` default `qwen/qwen3.8-27b` pode ficar obsoleto; sem health-check ou fallback automático para Gemini Vision.

### Evidência

Ver relatório completo em `findings-llm.md`.

**Arquivo**: `app/services/vision.py` linha 39
```python
self.groq_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
```

**Uso**: linha 128
```python
res = client.chat.completions.create(
    model=self.groq_model,  # <- Sem validação
    messages=[...]
)
```

### Gravidade: 🟡 MÉDIA
- **Fragilidade operacional**: Falha imediata se modelo descontinuado
- **Sem recovery**: Sistema não tenta Gemini Vision automaticamente

### Solução Recomendada

**Validação lazy com fallback automático** (Opção 2 do relatório):

```python
def analyze(self, ...):
    try:
        if active_provider == "groq":
            res = client.chat.completions.create(model=self.groq_model, ...)
            reply = res.choices[0].message.content or ""
    except Exception as e:
        if "not found" in str(e).lower() or "invalid model" in str(e).lower():
            print(f"[Vision] Modelo Groq '{self.groq_model}' inválido. Fallback para Gemini Vision.")
            active_provider = "gemini"
            # Repetir com Gemini...
        else:
            raise
```

**Vantagens**:
- Zero overhead na inicialização
- Fallback só quando necessário
- Aproveita infraestrutura Gemini já existente

---

## Ponto 3: Memória — Busca Cross-Session

### Status: ❌ REFUTADO

**Conclusão**: O problema NÃO existe. A busca de memória JÁ É global por design.

### Evidência Detalhada

Ver relatório completo em `findings-memory.md`.

**Comprovação**:
1. `memory_facts.relevant()` chama `list_facts()` **sem filtro de session_id**
2. `semantic_memory.search_memories()` faz `collection.query()` **sem parâmetro `where` para session**
3. Comentário explícito no código (`orchestrator.py:499`): **"Global recall is deliberate"**

### Possível Origem do Equívoco

O campo `session_id` existe nos metadados mas é **apenas para rastreamento/auditoria**, NÃO é usado como filtro.

Se o usuário relatou problema de memória não encontrada, as causas prováveis são:
- **Rate limit na síntese** (ponto 4) — memória recuperada mas resposta não sintetizada
- **Threshold de distância** muito restritivo (`USER_MEMORY_MAX_DISTANCE = 0.45`)
- **Chroma não inicializado** — apenas busca textual disponível

---

## Ponto 4: Rate Limit — Retry com Backoff

### Status: ✅ CONFIRMADO

**Problema**: `_recover_synthesis` tenta 1 chave alternativa e desiste, mesmo quando cooldown é curto (<10s).

### Evidência

Ver relatório completo em `findings-llm.md`.

**Arquivo**: `app/services/llm.py` linha 1322-1348

```python
def _recover_synthesis(error: Exception) -> str | None:
    if not is_rate_limit(error):
        return None
    _key_rotator.mark_rate_limit(api_key, error)
    next_key = _key_rotator.get_key("groq", self.settings)
    if not next_key or next_key == api_key:
        return None  # <- DESISTE IMEDIATAMENTE
    # ... apenas 1 tentativa com nova chave
```

### Gravidade: 🔴 MÉDIA-ALTA
- **Falsos positivos de indisponibilidade**: Usuário vê "sobrecarregado" quando sistema poderia esperar 2-5s
- **Ferramentas executadas sem síntese**: Ação realizada mas resposta não entregue

### Solução Recomendada

**Smart wait com limite de espera** (ao invés de exponential backoff clássico):

```python
def _recover_synthesis(error: Exception) -> str | None:
    if not is_rate_limit(error):
        return None
    
    _key_rotator.mark_rate_limit(api_key, error)
    max_wait_per_attempt = 5  # segundos
    max_attempts = 2
    
    for attempt in range(max_attempts):
        next_key = _key_rotator.get_key("groq", self.settings)
        
        if next_key and next_key != api_key:
            try:
                # [código de recovery]
                return result
            except Exception as recovery_error:
                if is_rate_limit(recovery_error):
                    _key_rotator.mark_rate_limit(next_key, recovery_error)
        
        if attempt < max_attempts - 1:
            min_cooldown = _key_rotator.min_cooldown_remaining("groq", self.settings)
            if 0 < min_cooldown <= max_wait_per_attempt:
                time.sleep(min_cooldown + 0.5)
            else:
                break
    
    return None
```

**Por que smart wait > exponential backoff**: Rate limit 429 fornece tempo EXATO no header `Retry-After`.

---

## Ponto 5: Tool Selection — Keyword Matcher Frágil

### Status: ⚠️ PARCIALMENTE CONFIRMADO

**Problema**: `GROQ_KEYWORD_TOOLS` usa regex estático; "lista" matcha checklist_tool mesmo quando usuário quer listar memórias.

### Evidência

**Arquivo**: `app/agent/tools/registry.py` linhas 102-131

```python
GROQ_KEYWORD_TOOLS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = tuple(
    (re.compile(pattern), tools)
    for pattern, tools in (
        (r"\bchecklist|\blista\b|\blistas\b|\bmercado\b|\bcompras\b", ("checklist_tool",)),
        (r"\btaref|\bpendencia", ("task_tool",)),
        # ... outros patterns
    )
)
```

**Análise**:
- `r"\blista\b"` matcha "lista" em qualquer contexto:
  - "liste minhas memórias" → ativa checklist_tool ❌
  - "liste as checklists" → ativa checklist_tool ✅
  - "lista de tarefas" → ativa checklist_tool ❌ (deveria ser task_tool)

### Gravidade: 🟡 MÉDIA
- **Impacto**: LLM recebe tool irrelevante no contexto, desperdiçando tokens
- **Mitigação**: LLM ainda pode ignorar a tool e escolher outra

### Solução Proposta

**Adicionar lógica de exclusão pós-matching** (não é possível com regex negativo puro):

```python
def allowed_tool_names(self, mode: str = "general", provider: str | None = None, user_text: str = "", *, narrow: bool = False) -> frozenset[str]:
    # ... código atual ...
    
    # Aplicar matchers
    for pattern, tools in GROQ_KEYWORD_TOOLS + LOOP_KEYWORD_TOOLS:
        if pattern.search(normalized):
            dynamic_tools.update(tools)
    
    # NOVO: Contexto negativo — remover tools ativadas incorretamente
    if re.search(r"\blista.*\b(?:memor|lembr)", normalized):
        dynamic_tools.discard("checklist_tool")
    
    if re.search(r"\blista.*\b(?:taref|pendenc|fazer)", normalized):
        dynamic_tools.discard("checklist_tool")
        dynamic_tools.add("task_tool")
    
    if re.search(r"\blist.*\b(?:checklist|compra|mercado)", normalized):
        dynamic_tools.discard("task_tool")
        dynamic_tools.add("checklist_tool")
    
    # ... resto do código
```

**Limitação**: Solução heurística; validação completa requer testes A/B com LLM real.

---

## Ponto 6: Sequência de Ações — Confirmação Intermediária

### Status: 🟡 NÃO VERIFICÁVEL POR ANÁLISE ESTÁTICA

**Problema**: No teste "criar arquivo, esperar 2s, ler", resposta diz "Li o arquivo" mas `tools: []`.

### Análise

**Arquivo**: `app/agent/orchestrator.py` + `app/agent/action_executor.py`

**Como funciona**:
1. LLM retorna `function_calls: [{file_manager, create}, {wait, 2s}, {file_manager, read}]`
2. `ActionExecutor` executa cada call sequencialmente
3. Resultados vão para `executed_tool_results` (dict interno)
4. `tool_calls` no response do painel vem de `response.function_calls` do LLM

**Hipóteses**:
- **H1**: LLM não devolveu `function_calls` explícitas (síntese direta sem tool marker)
- **H2**: `ActionExecutor` executou mas não atualizou `context.tool_calls`
- **H3**: API do painel não expõe `executed_tool_results` corretamente

### Gravidade: 🟡 MÉDIA
- **Impacto**: Auditoria incompleta; difícil rastrear quais tools foram executadas
- **Workaround**: Logs na Central registram execuções

### Validação Necessária

**Requer teste runtime**:
1. Submeter pedido "Crie arquivo teste.txt, espere 2s, leia o arquivo"
2. Capturar resposta completa do `/api/agent/request`
3. Verificar campos:
   - `response.function_calls` (do LLM)
   - `response.tool_calls` (do executor)
   - `executed_tool_results` (interno)
4. Logar cada etapa do `ActionExecutor.execute()`

**Não é possível confirmar por análise estática** pois depende do comportamento do LLM (quais tool calls ele retorna) e do fluxo multi-turn.

---

## Ponto 7: Timer — Sem Feedback Audível Confirmado

### Status: ✅ CONFIRMADO

**Problema**: Timer cria alarme e retorna sucesso, mas nunca confirma se o som tocou.

### Evidência

**Arquivo**: `app/agent/tools/timer.py` linhas 49-70

```python
@staticmethod
def _fire(label: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n*** ALERTA TIMER: {label} ({stamp}) ***", flush=True)
    try:
        from app.core.logger import logger
        logger.warn("Timer", f"⏰ Timer disparado: {label}")
    except Exception:
        pass
    try:
        for _ in range(3):
            winsound.Beep(1000, 350)  # <- Toca beep 3x
            time.sleep(0.15)
    except Exception:
        pass  # <- Falha silenciosa
```

**Análise**:
- `_fire()` é chamado em thread separada quando timer dispara
- `winsound.Beep()` pode falhar silenciosamente (ex: dispositivo de áudio desconectado)
- Não há callback de confirmação retornando ao chamador original

### Gravidade: 🟡 MÉDIA
- **Impacto**: Usuário não sabe se alarme funcionou (especialmente em ambientes headless)
- **Workaround**: Print e log existem, mas não são visíveis na interface

### Solução Proposta

**Opção 1: Callback de confirmação** (mais robusto):

```python
class _TimerManager:
    def __init__(self):
        # ...
        self._fire_callbacks = []  # Lista de callbacks
    
    def add_fire_callback(self, callback: Callable[[str, bool], None]) -> None:
        """Registra callback (label, success) que será chamado quando timer disparar."""
        self._fire_callbacks.append(callback)
    
    def _fire(self, label: str) -> None:
        # ... código existente ...
        success = False
        try:
            for _ in range(3):
                winsound.Beep(1000, 350)
                time.sleep(0.15)
            success = True
        except Exception as e:
            logger.error("Timer", f"Falha ao tocar beep: {e}")
        
        # Notificar callbacks
        for callback in self._fire_callbacks:
            try:
                callback(label, success)
            except Exception:
                pass
```

**Opção 2: Registro em arquivo de auditoria** (mais simples):

```python
def _fire(self, label: str) -> None:
    # ... código existente ...
    audit_file = "data/timer_audit.log"
    try:
        with open(audit_file, "a", encoding="utf-8") as f:
            status = "SUCCESS" if beep_success else "FAILED"
            f.write(f"{datetime.now().isoformat()} | {status} | {label}\n")
    except Exception:
        pass
```

---

## Ponto 8: Web Search — Fallback quando Síntese Trunca

### Status: ✅ CONFIRMADO

**Problema**: Na pesquisa web, resposta fica truncada por rate limit; `_recover_synthesis` não tem material bruto para reformular.

### Evidência

Ver relatório completo em `findings-websearch.md`.

**Fluxo do problema**:
1. `web_search.execute()` busca fontes, lê páginas, formata síntese em `message`
2. Retorna `ToolResult(ok=True, message=synthesis, data={"results": [...snippets...]})`
3. `Orchestrator` passa apenas `message` para LLM (via `model_observation()`)
4. LLM tenta sintetizar mas falha com 429
5. `_recover_synthesis` só tem `message` (síntese já formatada), não os snippets crus
6. Recovery falha ou retorna resposta empobrecida

### Gravidade: 🔴 MÉDIA-ALTA
- **Dados perdidos**: Snippets custaram requisições HTTP e refinamento iterativo
- **Experiência degradada**: Usuário vê "sobrecarregado" quando busca encontrou dados ricos

### Solução Recomendada

**Mudança 1: Incluir snippets compactos no `ToolResult.data`**:

```python
# Em web_search.py:
fallback_snippets = [
    {
        "title": r.get("title", ""),
        "url": r.get("url", ""),
        "snippet": (r.get("excerpt") or r.get("snippet") or "")[:400],
        "source": r.get("source", ""),
    }
    for r in results[:5]
]

return ToolResult(
    ok=True,
    message=synthesis_msg,
    data={
        "results": results,  # completo para UI
        "fallback_snippets": fallback_snippets,  # compacto para recovery
        # ...
    },
)
```

**Mudança 2: Incluir `fallback_snippets` nos campos expostos**:

```python
# Em app/agent/tools/base.py:
fields = (..., "fallback_snippets", "query")
```

**Resultado**: `_recover_synthesis` receberá snippets compactos (5 × 400 chars = ~2KB) e poderá reformular resposta.

---

## Ponto 9: Testes de Integração Automatizados

### Status: ✅ CONFIRMADO

**Problema**: Não existe test suite que rode contra o servidor real.

### Evidência

Ver relatório completo em `findings-tests.md`.

**Confirmação**:
- ✅ 150+ arquivos de teste existem (unitários e de componente isolados)
- ❌ `test_live_integration.py` NÃO EXISTE
- ⚠️ `test_live_server.py` existe mas apenas tenta conectar (não sobe servidor)

### Gravidade: 🟡 MÉDIA-ALTA
- **Regressões não detectadas**: Mudanças podem quebrar sistema sem falhar testes unitários
- **Validação manual repetitiva**: Usuário executou 11 cenários manualmente (deveria ser automatizado)
- **CI incompleto**: Pipeline roda apenas testes unitários

### Solução Proposta

**Criar `tests/test_live_integration.py`** com:
1. **Fixture** que sobe servidor em background (thread com Flask/FastAPI)
2. **11 cenários end-to-end**:
   - Checklist create & get_list (ponto 1)
   - Vision model fallback (ponto 2)
   - Memory cross-session (ponto 3)
   - Rate limit recovery (ponto 4)
   - Tool selection keyword (ponto 5)
   - File sequence (ponto 6)
   - Timer audio (ponto 7)
   - Web search fallback (ponto 8)
   - Memory save & search baseline (ponto 9)
   - Checklist delete confirmation (ponto 10)
   - Rate limit all keys exhausted (ponto 11)
3. **Validação**: resposta + efeitos colaterais (arquivo criado, memória salva, etc.)

**Outline completo**: Ver `findings-tests.md` linhas 200-730.

---

## Ponto 10: Checklist Delete Sem Confirmação

### Status: ✅ CONFIRMADO

**Problema**: "Exclua a checklist X" exclui imediatamente sem confirmação.

### Evidência

**Arquivo**: `app/agent/tools/checklist_tool.py` linhas 166-175

```python
if act == "delete_list":
    target = self._resolve_list(list_id, title)
    if not target:
        return {"ok": False, "error": "Lista não encontrada para exclusão."}
    success = checklist_store.delete_list(target["id"])  # <- EXCLUSÃO IMEDIATA
    return {
        "ok": success,
        "message": f"Lista '{target['title']}' excluída com sucesso.",
    }
```

**Confirmação**: Não há chamada a `critical_confirm.request()` antes da exclusão.

### Gravidade: 🔴 MÉDIA-ALTA
- **Ação destrutiva sem confirmação**: Usuário pode perder lista com múltiplos itens acidentalmente
- **Inconsistência**: Outras operações destrutivas (finance delete, task delete) pedem confirmação

### Solução Recomendada

**Integrar com CriticalConfirm**:

```python
if act == "delete_list":
    target = self._resolve_list(list_id, title)
    if not target:
        return {"ok": False, "error": "Lista não encontrada para exclusão."}
    
    # NOVO: Pedir confirmação
    count = target.get("pending_count", 0) + target.get("completed_count", 0)
    detail = f"Excluir lista '{target['title']}' com {count} item(ns)?"
    
    from app.core.critical_confirm import get_critical_confirm
    critical = get_critical_confirm()
    if not critical.is_enabled():
        # Confirmação desabilitada: prossegue
        pass
    else:
        req_id = critical.request(tool="checklist_tool", detail=detail)
        approved = critical.wait(req_id, timeout=300)
        if not approved:
            return {"ok": False, "error": "Exclusão cancelada pelo usuário."}
    
    success = checklist_store.delete_list(target["id"])
    return {"ok": success, "message": f"Lista '{target['title']}' excluída com sucesso."}
```

**Também**: Marcar `delete_list` no catálogo de ferramentas como `risk: "destructive"`.

---

## Matriz de Priorização

| Ponto | Status | Gravidade | Esforço | Prioridade | Validação |
|-------|--------|-----------|---------|------------|-----------|
| **4** | ✅ | 🔴 ALTA | Médio | **1** | Runtime (rate limit real) |
| **8** | ✅ | 🔴 ALTA | Baixo | **1** | Estática + Runtime |
| **10** | ✅ | 🔴 ALTA | Baixo | **1** | Estática + Manual |
| **2** | ✅ | 🟡 MÉDIA | Baixo | **2** | Runtime (mock erro 404) |
| **1** | ✅ | 🟡 MÉDIA | Baixo | **2** | Manual (testes com LLM) |
| **7** | ✅ | 🟡 MÉDIA | Médio | **2** | Manual (verificar beep) |
| **5** | ⚠️ | 🟡 MÉDIA | Médio | **2** | Runtime (A/B test) |
| **9** | ✅ | 🟡 MÉDIA | Alto | **3** | Automático (CI) |
| **6** | 🟡 | 🟡 MÉDIA | Alto | **3** | Runtime (LLM real) |
| **3** | ❌ | N/A | N/A | **N/A** | NENHUMA (falso positivo) |

---

## Limitações da Análise

Esta investigação foi feita por **análise estática** (leitura do código-fonte). As seguintes validações exigem **execução em runtime**:

1. **Ponto 1** (Checklist): Testar com LLM real se description melhorada resolve ambiguidade
2. **Ponto 2** (Visão): Forçar erro 404 do Groq e validar fallback para Gemini
3. **Ponto 4** (Rate limit): Esgotar quota e validar smart wait com cooldown < 10s
4. **Ponto 5** (Tool selection): A/B test com frases ambíguas ("lista memórias" vs "lista checklists")
5. **Ponto 6** (Sequência de ações): Executar pedido multi-ação e capturar `tool_calls`
6. **Ponto 7** (Timer): Criar timer, aguardar disparo, verificar callback/log
7. **Ponto 8** (Web search): Forçar rate limit durante síntese e validar recovery com snippets
8. **Ponto 10** (Delete): Executar delete e confirmar que CriticalConfirm intercepta

---

## Próximos Passos

### Implementação Imediata (Sprint 1)

1. **Ponto 10** (Delete confirmation) — 2h de implementação
2. **Ponto 8** (Web search fallback) — 4h de implementação + testes
3. **Ponto 2** (Vision fallback) — 3h de implementação + testes

### Implementação Curto Prazo (Sprint 2)

4. **Ponto 4** (Rate limit smart wait) — 6h de implementação + validação runtime
5. **Ponto 1** (Checklist descriptions) — 2h de ajuste + testes manuais
6. **Ponto 7** (Timer feedback) — 4h de implementação + auditoria

### Implementação Médio Prazo (Sprint 3)

7. **Ponto 5** (Keyword matcher) — 6h de refatoração + A/B testing
8. **Ponto 9** (Test suite) — 16h de implementação + CI integration

### Investigação Adicional

9. **Ponto 6** (Sequência de ações) — Requer debugging com LLM real; não priorizar até ter evidência reproduzível

---

**Fim da Análise Completa**
