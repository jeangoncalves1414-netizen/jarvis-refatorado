# Plano de Implementação — Sprint 1: Correções Críticas

**Data**: 2026-01-11  
**Workspace**: `c:\Users\maria\Desktop\Jarvis`  
**Objetivo**: Implementar 3 correções críticas de segurança e robustez conforme checkup do sistema

---

## Visão Geral

Este sprint corrige 3 problemas de alta prioridade identificados no checkup:

1. **Ponto 10**: Checklist delete_list sem confirmação (risco destrutivo)
2. **Ponto 8**: Web search sem fallback de snippets para recovery de síntese
3. **Ponto 2**: Vision sem fallback automático Groq → Gemini

**Esforço total estimado**: 9h  
**Breaking changes**: Nenhum  
**Dependências**: `app/core/critical_confirm.py` já existe e funcional

---

## Correção 1: Checklist Delete com Confirmação (Ponto 10)

### Contexto

**Arquivo**: `app/agent/tools/checklist_tool.py` (linha 166-175)

**Problema**: O bloco `if act == "delete_list":` executa `checklist_store.delete_list()` imediatamente sem pedir confirmação ao usuário.

**Gravidade**: 🔴 ALTA — Operação destrutiva pode causar perda acidental de dados

### Código Atual

```python
if act == "delete_list":
    target = self._resolve_list(list_id, title)
    if not target:
        return {"ok": False, "error": "Lista não encontrada para exclusão."}
    success = checklist_store.delete_list(target["id"])
    return {
        "ok": success,
        "message": f"Lista '{target['title']}' excluída com sucesso.",
    }
```

### Implementação

**Passo 1**: Adicionar integração com CriticalConfirm no bloco delete_list

**Arquivo**: `app/agent/tools/checklist_tool.py`

**Localização**: Dentro do método `run()`, no bloco `if act == "delete_list":` (aproximadamente linha 166)

**Diff a aplicar**:

```python
if act == "delete_list":
    target = self._resolve_list(list_id, title)
    if not target:
        return {"ok": False, "error": "Lista não encontrada para exclusão."}
    
    # NOVO: Integração com CriticalConfirm
    count = target.get("pending_count", 0) + target.get("completed_count", 0)
    detail = f"Excluir lista '{target['title']}' com {count} item(ns)?"
    
    from app.core.critical_confirm import CriticalConfirm
    critical = CriticalConfirm()
    
    # Pedir confirmação (se enabled)
    approved = critical.request(tool="checklist_tool", detail=detail)
    if not approved:
        return {"ok": False, "error": "Exclusão cancelada pelo usuário."}
    
    success = checklist_store.delete_list(target["id"])
    return {
        "ok": success,
        "message": f"Lista '{target['title']}' excluída com sucesso.",
    }
```

**Notas importantes**:
- A API `CriticalConfirm.request()` retorna `bool` diretamente (o wait é interno)
- Se confirmações estão desabilitadas (`enabled=False`), `request()` retorna `True` automaticamente
- O timeout padrão é 300s (5 minutos)

### Verificação

**Comando**: Executar testes unitários de checklist

```bash
python -m pytest tests/agent/tools/test_checklist_tool.py -v -k delete
```

**Resultado esperado**: 
- Testes de delete_list devem passar
- Novo comportamento: confirmação é solicitada antes da exclusão
- Se usuário cancela, lista não é excluída e erro "Exclusão cancelada" é retornado

**Teste manual** (necessário após implementação):
1. Iniciar servidor: `python -m app.main`
2. No painel, criar uma checklist de teste: "Teste Delete"
3. Adicionar 3 itens quaisquer
4. Solicitar via chat: "Exclua a checklist Teste Delete"
5. Verificar que painel exibe confirmação: "Excluir lista 'Teste Delete' com 3 item(ns)?"
6. Cancelar confirmação
7. Verificar que lista ainda existe
8. Solicitar novamente exclusão
9. Confirmar exclusão
10. Verificar que lista foi removida

---

## Correção 2: Web Search Fallback Snippets (Ponto 8)

### Contexto

**Arquivos**: 
- `app/agent/tools/web_search.py` (linha 425+)
- `app/agent/tools/base.py` (linha 11-20)

**Problema**: Quando `web_search` executa busca com sucesso mas a síntese LLM falha por rate limit, o método `_recover_synthesis` (em `app/services/llm.py`) não tem acesso aos snippets crus das fontes encontradas. O `ToolResult` atual só inclui a mensagem de síntese formatada.

**Gravidade**: 🔴 MÉDIA-ALTA — Pesquisas custam requisições HTTP e refinamento iterativo; perder esses dados força o usuário a repetir a busca

### Código Atual

**Em `web_search.py` (aproximadamente linha 425)**:

```python
if action in {"search", "research"}:
    try:
        results, steps, effective_q = search_with_refinement(query, limit=limit)
        
        if not results:
            return ToolResult(
                ok=True,
                message=f"Evidência insuficiente...",
                data={"query": query, "results": [], "steps": steps, "evidence_status": "insufficient"},
            )
        
        # ... código de leitura das páginas (se action == "research") ...
        
        synthesis_msg = _format_search_response(query, results, refined_query=refined_from)
        
        return ToolResult(
            ok=True,
            message=synthesis_msg,
            data={
                "query": query,
                "effective_query": effective_q,
                "results": results,  # Completo para UI
                "steps": steps,
                "workflow": action,
                "evidence_status": "excerpts" if ... else "insufficient",
            },
        )
```

**Em `base.py` (linha 11-20)**:

```python
def model_observation(self) -> str:
    """Expose record identifiers as well as the human receipt to the planner."""
    import json
    fields = ("tasks", "task", "habits", "habit", "transactions", "transaction",
              "checklists", "checklist", "results", "record", "record_id", "personal_receipt", "bulk_preview", "content", "list_id", "trans_ids", "task_ids", "habit_ids")
    details = {key: self.data[key] for key in fields if key in self.data}
    # ...
```

### Implementação

**Passo 1**: Adicionar `fallback_snippets` ao ToolResult.data em web_search.py

**Arquivo**: `app/agent/tools/web_search.py`

**Localização**: Dentro do bloco `if action in {"search", "research"}:`, logo antes do `return ToolResult(...)` final (aproximadamente linha 440)

**Diff a aplicar**:

```python
        # ... código de leitura das páginas ...
        
        refined_from = effective_q if effective_q.lower() != query.lower() else None
        synthesis_msg = _format_search_response(query, results, refined_query=refined_from)
        
        # NOVO: Preparar snippets compactos para fallback de recovery
        fallback_snippets = [
            {
                "title": r.get("title", "")[:100],
                "url": r.get("url", ""),
                "snippet": (r.get("excerpt") or r.get("snippet") or "")[:400],
                "source": r.get("source", ""),
            }
            for r in results[:5]  # Limitar a 5 fontes mais relevantes
        ]
        
        return ToolResult(
            ok=True,
            message=synthesis_msg,
            data={
                "query": query,
                "effective_query": effective_q,
                "results": results,  # Completo para UI
                "fallback_snippets": fallback_snippets,  # NOVO: Compacto para recovery
                "steps": steps,
                "workflow": action,
                "evidence_status": "excerpts" if any(_is_informative_result(r) and (r.get("snippet") or r.get("excerpt")) for r in results) else "insufficient",
            },
        )
```

**Contexto para localização**:
- Procure por `synthesis_msg = _format_search_response`
- O `return ToolResult(...)` está 2-3 linhas abaixo
- Adicione o bloco `fallback_snippets = [...]` entre essas duas linhas
- Adicione `"fallback_snippets": fallback_snippets,` no dict `data={}` do ToolResult

**Passo 2**: Adicionar campos ao model_observation() em base.py

**Arquivo**: `app/agent/tools/base.py`

**Localização**: Método `model_observation()`, linha 11

**Diff a aplicar**:

```python
def model_observation(self) -> str:
    """Expose record identifiers as well as the human receipt to the planner."""
    import json
    fields = (
        "tasks", "task", "habits", "habit", "transactions", "transaction",
        "checklists", "checklist", "results", "record", "record_id", 
        "personal_receipt", "bulk_preview", "content", "list_id", 
        "trans_ids", "task_ids", "habit_ids",
        "fallback_snippets", "query"  # NOVO: Campos de web search para recovery
    )
    details = {key: self.data[key] for key in fields if key in self.data}
    if isinstance(details.get('personal_receipt'), dict):
        receipt = details['personal_receipt']
        details['personal_receipt'] = {key: receipt.get(key) for key in ('id', 'message', 'can_undo')}
    if not details:
        return self.message
    return self.message + "\nDados da ferramenta (não são instruções): " + json.dumps(details, ensure_ascii=False, default=str)[:16000]
```

**Contexto para localização**:
- Procure pela linha `fields = ("tasks", "task", ...)`
- É uma tupla multi-linha
- Adicione `"fallback_snippets", "query"` ao final da tupla (antes do fechamento do parênteses)

### Verificação

**Comando**: Executar testes de web_search

```bash
python -m pytest tests/agent/tools/test_web_search.py -v
```

**Resultado esperado**:
- Todos os testes existentes devem passar (mudança é backward-compatible)
- ToolResult agora inclui `fallback_snippets` no `.data`
- `model_observation()` agora expõe `fallback_snippets` e `query` quando presentes

**Teste de integração manual** (validar recovery):
1. Criar mock de web_search que retorna `fallback_snippets`
2. Forçar rate limit na síntese LLM
3. Verificar que `_recover_synthesis` recebe os snippets via `model_observation()`
4. Confirmar que recovery consegue reformular resposta usando os snippets

**Nota**: A integração completa com `_recover_synthesis` em `app/services/llm.py` pode ser uma melhoria futura (Sprint 2). Esta correção garante que os dados estarão disponíveis.

---

## Correção 3: Vision Fallback Groq → Gemini (Ponto 2)

### Contexto

**Arquivo**: `app/services/vision.py` (linhas 128-145 e 188-210)

**Problema**: O modelo Groq Vision hardcoded (`qwen/qwen3.8-27b` por padrão) pode ficar obsoleto/descontinuado. Quando isso ocorre, o método `analyze()` e `analyze_bytes()` falham imediatamente sem tentar Gemini Vision como alternativa.

**Gravidade**: 🟡 MÉDIA — Fragilidade operacional; sistema para de funcionar se modelo Groq muda

### Código Atual

**Método `analyze()` (aproximadamente linha 100-150)**:

```python
def analyze(self, prompt: str, image: Image.Image | None = None, api_key: str | None = None, provider: str | None = None) -> dict[str, Any]:
    # ... código de preparação de imagem ...
    
    active_provider = (provider or self.provider).lower()
    active_key = api_key or (self.groq_api_key if active_provider == "groq" else self.api_key)
    
    if not active_key:
        return {
            "ok": False,
            "reply": f"Chave de API do {active_provider.capitalize()} necessária...",
            "capture_path": filepath,
            "capture_filename": filename,
        }
    
    ok = True
    try:
        if active_provider == "groq":
            client = self._get_client("groq", active_key)
            res = client.chat.completions.create(
                model=self.groq_model,  # <- Pode falhar se modelo inválido
                messages=[...]
            )
            # ... processamento de resposta ...
            reply = res.choices[0].message.content or ""
        else:
            # Código Gemini...
    except Exception as e:
        ok = False
        reply = f"Erro na análise visual ({active_provider}): {e}"  # <- Sem fallback
    
    return {"ok": ok, "reply": reply, ...}
```

### Implementação

**Passo 1**: Adicionar try-catch com fallback no método `analyze()`

**Arquivo**: `app/services/vision.py`

**Localização**: Dentro do método `analyze()`, bloco try-except que chama Groq (aproximadamente linha 128)

**Diff a aplicar**:

```python
    ok = True
    try:
        if active_provider == "groq":
            client = self._get_client("groq", active_key)
            res = client.chat.completions.create(
                model=self.groq_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                    ]
                }]
            )
            raw_text = res.choices[0].message.content or ""
            if "<think>" in raw_text and "</think>" in raw_text:
                raw_text = raw_text.split("</think>")[-1].strip()
            reply = raw_text
        else:
            from google.genai import types
            client = self._get_client("gemini", active_key)
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg"
                    ),
                    prompt
                ]
            )
            reply = response.text or "Nenhum detalhe visual extraído."
    except Exception as e:
        # NOVO: Verificar se é erro de modelo e tentar fallback para Gemini
        error_str = str(e).lower()
        is_model_error = any(keyword in error_str for keyword in [
            "not found", "invalid model", "404", "model_not_found", "model not found"
        ])
        
        if is_model_error and active_provider == "groq":
            # FALLBACK AUTOMÁTICO para Gemini Vision
            print(f"[Vision] Modelo Groq '{self.groq_model}' inválido ou obsoleto. Fallback para Gemini Vision.")
            try:
                from google.genai import types
                gemini_key = self.api_key  # Chave Gemini
                if not gemini_key:
                    ok = False
                    reply = f"Fallback Gemini solicitado mas chave de API não configurada. Erro original: {e}"
                else:
                    client = self._get_client("gemini", gemini_key)
                    response = client.models.generate_content(
                        model=self.model,
                        contents=[
                            types.Part.from_bytes(
                                data=image_bytes,
                                mime_type="image/jpeg"
                            ),
                            prompt
                        ]
                    )
                    reply = response.text or "Nenhum detalhe visual extraído."
                    ok = True
            except Exception as fallback_error:
                ok = False
                reply = f"Fallback para Gemini Vision também falhou: {fallback_error}. Erro Groq original: {e}"
        else:
            # Outro tipo de erro ou já estava usando Gemini
            ok = False
            reply = f"Erro na análise visual ({active_provider}): {e}"
```

**Contexto para localização**:
- Procure por `res = client.chat.completions.create(model=self.groq_model`
- O bloco try-except está logo acima
- Substitua o `except Exception as e:` existente pelo novo código acima

**Passo 2**: Aplicar mesma lógica ao método `analyze_bytes()`

**Arquivo**: `app/services/vision.py`

**Localização**: Método `analyze_bytes()` (aproximadamente linha 188)

**Diff a aplicar** (estrutura similar ao Passo 1):

```python
def analyze_bytes(self, prompt: str, image_bytes: bytes, api_key: str | None = None, provider: str | None = None) -> str:
    """Analisa uma imagem em bytes com prompt."""
    image_b64 = base64.b64encode(image_bytes).decode()
    active_provider = (provider or self.provider).lower()
    active_key = api_key or (self.groq_api_key if active_provider == "groq" else self.api_key)

    if not active_key:
        return f"Chave de API do {active_provider.capitalize()} necessária para visão computacional."

    try:
        if active_provider == "groq":
            client = self._get_client("groq", active_key)
            res = client.chat.completions.create(
                model=self.groq_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                    ]
                }]
            )
            raw_text = res.choices[0].message.content or ""
            if "<think>" in raw_text and "</think>" in raw_text:
                raw_text = raw_text.split("</think>")[-1].strip()
            return raw_text
        else:
            from google.genai import types
            client = self._get_client("gemini", active_key)
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/png"
                    ),
                    prompt
                ]
            )
            return response.text or "Sem resposta gerada."
    except Exception as e:
        # NOVO: Fallback para Gemini se erro de modelo Groq
        error_str = str(e).lower()
        is_model_error = any(keyword in error_str for keyword in [
            "not found", "invalid model", "404", "model_not_found", "model not found"
        ])
        
        if is_model_error and active_provider == "groq":
            print(f"[Vision] Modelo Groq '{self.groq_model}' inválido. Fallback para Gemini Vision.")
            try:
                gemini_key = self.api_key
                if not gemini_key:
                    return f"Fallback Gemini solicitado mas chave não configurada. Erro original: {e}"
                
                from google.genai import types
                client = self._get_client("gemini", gemini_key)
                response = client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/png"
                        ),
                        prompt
                    ]
                )
                return response.text or "Sem resposta gerada."
            except Exception as fallback_error:
                return f"Fallback para Gemini falhou: {fallback_error}. Erro Groq: {e}"
        else:
            return f"Erro ao analisar imagem: {e}"
```

### Verificação

**Comando**: Executar testes de vision

```bash
python -m pytest tests/services/test_vision.py -v
```

**Resultado esperado**:
- Testes existentes continuam passando
- Fallback para Gemini ocorre automaticamente quando Groq falha com erro de modelo

**Teste de integração manual**:
1. Modificar temporariamente `GROQ_VISION_MODEL` no `.env` para um modelo inválido:
   ```
   GROQ_VISION_MODEL=modelo-invalido-teste
   ```
2. Iniciar servidor e solicitar análise de visão
3. Observar logs: deve aparecer mensagem "[Vision] Modelo Groq 'modelo-invalido-teste' inválido ou obsoleto. Fallback para Gemini Vision."
4. Verificar que análise de visão funciona (usando Gemini)
5. Restaurar `.env` para valor correto

**Teste com mock**:
- Criar mock de Groq client que lança `RuntimeError("model_not_found: qwen/qwen3.8-27b")`
- Criar mock de Gemini client que retorna sucesso
- Verificar que `analyze()` e `analyze_bytes()` retornam resposta do Gemini

---

## Resumo das Mudanças

### Arquivos Modificados

1. **`app/agent/tools/checklist_tool.py`**
   - Adicionar import e integração com `CriticalConfirm` no bloco `delete_list`
   - ~10 linhas adicionadas

2. **`app/agent/tools/web_search.py`**
   - Adicionar construção de `fallback_snippets` antes do return
   - ~10 linhas adicionadas

3. **`app/agent/tools/base.py`**
   - Adicionar `"fallback_snippets", "query"` ao tuple `fields`
   - 1 linha modificada

4. **`app/services/vision.py`**
   - Substituir bloco `except Exception as e:` em `analyze()` por versão com fallback
   - Substituir bloco `except Exception as e:` em `analyze_bytes()` por versão com fallback
   - ~40 linhas modificadas total

### Testes Necessários

#### Testes Automatizados (unitários)

```bash
# Checklist
python -m pytest tests/agent/tools/test_checklist_tool.py -v -k delete

# Web Search
python -m pytest tests/agent/tools/test_web_search.py -v

# Vision
python -m pytest tests/services/test_vision.py -v
```

#### Testes Manuais

1. **Checklist delete confirmation**:
   - Criar lista, solicitar exclusão, verificar confirmação, cancelar
   - Repetir e confirmar, verificar exclusão

2. **Web search fallback**:
   - Executar pesquisa, verificar que `fallback_snippets` está presente no ToolResult.data
   - (Teste de recovery completo é Sprint 2)

3. **Vision fallback**:
   - Configurar modelo Groq inválido, solicitar análise de visão
   - Verificar log de fallback e sucesso com Gemini

### Critérios de Aceitação

- [ ] **Correção 1**: Delete de checklist solicita confirmação; cancelamento preserva lista
- [ ] **Correção 2**: Web search inclui `fallback_snippets` no ToolResult.data; `model_observation()` expõe esses campos
- [ ] **Correção 3**: Análise de visão faz fallback automático para Gemini quando modelo Groq inválido; log de fallback aparece no console

### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| CriticalConfirm timeout muito longo | Baixa | Médio | Timeout padrão é 300s (razoável); usuário pode desabilitar confirmações globalmente |
| Fallback Gemini sem chave configurada | Média | Alto | Verificação de chave antes de tentar fallback; mensagem clara se chave ausente |
| Snippets muito grandes para context window | Baixa | Baixo | Limitado a 5 fontes × 400 chars = 2KB (desprezível) |

---

## Próximos Passos (Pós-Sprint 1)

Após implementação e validação do Sprint 1, seguir para **Sprint 2**:
- Ponto 4: Rate limit com smart wait (recovery inteligente)
- Ponto 1: Melhorar descriptions de checklist (tool selection)
- Ponto 7: Timer com feedback audível (auditoria)

---

**Plano criado e pronto para implementação.**
