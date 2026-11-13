# Plano de Correções — Checkup do Sistema Jarvis

**Data**: 2026-01-11  
**Workspace**: `c:\Users\maria\Desktop\Jarvis`

---

## Estratégia de Implementação

### Priorização: Impacto × Esforço

```
           ALTO IMPACTO
               │
    ┌──────────┼──────────┐
    │  SPRINT 1           │  SPRINT 2
    │  • Ponto 10         │  • Ponto 4
    │  • Ponto 8          │  • Ponto 1
BAIXO  • Ponto 2          │  • Ponto 7   ALTO
ESFORÇO                   │             ESFORÇO
    │  SPRINT 3           │  BACKLOG
    │  • Ponto 5          │  • Ponto 6
    │  • Ponto 9          │    (investigar)
    └──────────┼──────────┘
               │
           BAIXO IMPACTO
```

---

## SPRINT 1: Correções Críticas de Segurança e UX

### 🔴 Correção 1: Ponto 10 — Checklist Delete com Confirmação

**Objetivo**: Exigir confirmação antes de excluir checklist.

**Esforço**: 🟢 Baixo (2h)  
**Impacto**: 🔴 Alto (previne perda acidental de dados)  
**Breaking Change**: ❌ Não (apenas adiciona step de confirmação)

#### Implementação

**Arquivo**: `app/agent/tools/checklist_tool.py`

**Mudanças**:

```python
def run(self, action: str = "get_list", ...) -> dict[str, Any]:
    # ... código existente ...
    
    if act == "delete_list":
        target = self._resolve_list(list_id, title)
        if not target:
            return {"ok": False, "error": "Lista não encontrada para exclusão."}
        
        # NOVO: Integração com CriticalConfirm
        count = target.get("pending_count", 0) + target.get("completed_count", 0)
        detail = f"Excluir lista '{target['title']}' com {count} item(ns)?"
        
        from app.core.critical_confirm import get_critical_confirm
        critical = get_critical_confirm()
        
        if critical.is_enabled():
            req_id = critical.request(tool="checklist_tool", detail=detail)
            approved = critical.wait(req_id, timeout=300)
            if not approved:
                return {"ok": False, "error": "Exclusão cancelada pelo usuário."}
        
        success = checklist_store.delete_list(target["id"])
        return {"ok": success, "message": f"Lista '{target['title']}' excluída com sucesso."}
```

**Arquivo**: `app/agent/tools/catalog.py` (adicionar metadata)

```python
TOOL_CATALOG = {
    # ... ferramentas existentes ...
    "checklist_tool": ToolMetadata(
        capabilities=("checklist_tool",),
        default_risk="safe",
        operations={
            "delete_list": ToolMetadata(
                capabilities=("checklist_tool", "delete_list"),
                default_risk="destructive",  # <- NOVO
                requires_confirmation=True,
                reversible=False,
            ),
        },
    ),
}
```

#### Testes de Validação

```python
# tests/test_checklist_delete_confirmation.py
def test_delete_list_requires_confirmation(isolated_checklist, monkeypatch):
    """Validar que delete_list pede confirmação antes de excluir."""
    tool = ChecklistTool()
    
    # Criar lista
    tool.run(action="create_list", title="Teste", items=["item1", "item2"])
    
    # Mock de CriticalConfirm
    confirmed = False
    def mock_request(tool, detail):
        assert "Excluir lista 'Teste' com 2 item(ns)" in detail
        return "req_123"
    
    def mock_wait(req_id, timeout):
        return confirmed
    
    monkeypatch.setattr("app.core.critical_confirm.get_critical_confirm().request", mock_request)
    monkeypatch.setattr("app.core.critical_confirm.get_critical_confirm().wait", mock_wait)
    
    # Tentativa de exclusão — NÃO confirmada
    result = tool.run(action="delete_list", title="Teste")
    assert not result["ok"]
    assert "cancelada" in result["error"]
    assert checklist_store.find_list_by_title("Teste") is not None  # Lista ainda existe
    
    # Tentativa de exclusão — CONFIRMADA
    confirmed = True
    result = tool.run(action="delete_list", title="Teste")
    assert result["ok"]
    assert checklist_store.find_list_by_title("Teste") is None  # Lista foi excluída
```

#### Documentação de Mudança

**User-Visible**: ✅ SIM

**Changelog**:
> **[SEGURANÇA]** Excluir checklist agora exige confirmação no painel. Para desabilitar, ajuste "Confirmações Críticas" nas configurações.

---

### 🔴 Correção 2: Ponto 8 — Web Search Fallback de Síntese

**Objetivo**: Guardar snippets crus para recovery quando síntese trunca por rate limit.

**Esforço**: 🟢 Baixo (4h)  
**Impacto**: 🔴 Alto (melhora drasticamente recovery de pesquisas)  
**Breaking Change**: ❌ Não (adiciona dados ao ToolResult)

#### Implementação

**Arquivo**: `app/agent/tools/web_search.py`

**Mudanças**:

```python
def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
    # ... código de busca existente ...
    
    if action in {"search", "research"}:
        try:
            results, steps, effective_q = search_with_refinement(query, limit=limit)
            
            if not results:
                return ToolResult(ok=True, message="Evidência insuficiente...", data={"results": [], ...})
            
            if action == "research":
                # ... leitura das fontes ...
                for result in results:
                    result.update(_page_details(result["url"]))
            
            # NOVO: Preparar snippets compactos para fallback
            fallback_snippets = [
                {
                    "title": r.get("title", "")[:100],
                    "url": r.get("url", ""),
                    "snippet": (r.get("excerpt") or r.get("snippet") or "")[:400],
                    "source": r.get("source", ""),
                }
                for r in results[:5]  # Limitar a 5 fontes
            ]
            
            synthesis_msg = _format_search_response(query, results, refined_query=refined_from)
            
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
                    "evidence_status": "excerpts" if ... else "insufficient",
                },
            )
        except Exception as exc:
            return ToolResult(ok=False, message=f"Não foi possível pesquisar agora: {exc}")
```

**Arquivo**: `app/agent/tools/base.py`

**Mudanças**:

```python
def model_observation(self) -> str:
    """Expose record identifiers as well as the human receipt to the planner."""
    import json
    fields = (
        "tasks", "task", "habits", "habit", "transactions", "transaction",
        "checklists", "checklist", "results", "record", "record_id", 
        "personal_receipt", "bulk_preview", "content", "list_id", 
        "trans_ids", "task_ids", "habit_ids",
        "fallback_snippets", "query"  # NOVO: Adicionar campos de web search
    )
    details = {key: self.data[key] for key in fields if key in self.data}
    # ... resto do código
```

#### Testes de Validação

```python
# tests/test_web_search_recovery.py
def test_web_search_includes_fallback_snippets(monkeypatch):
    """Validar que web_search inclui fallback_snippets no ToolResult.data."""
    tool = WebSearchTool()
    
    # Mock de _search para retornar resultados controlados
    def mock_search(query, limit):
        return [
            {"title": "Fonte 1", "url": "https://example.com/1", "snippet": "Texto 1" * 100},
            {"title": "Fonte 2", "url": "https://example.com/2", "snippet": "Texto 2" * 100},
        ], [], query
    
    monkeypatch.setattr("app.agent.tools.web_search.search_with_refinement", mock_search)
    
    result = tool.execute({"action": "search", "query": "teste"})
    
    assert result.ok
    assert "fallback_snippets" in result.data
    snippets = result.data["fallback_snippets"]
    assert len(snippets) == 2
    assert snippets[0]["title"] == "Fonte 1"
    assert len(snippets[0]["snippet"]) <= 400  # Verificar truncamento


def test_recovery_uses_fallback_snippets_from_web_search(monkeypatch):
    """Validar que _recover_synthesis recebe fallback_snippets via model_observation."""
    from app.agent.tools.base import ToolResult
    
    # Simular ToolResult de web_search com fallback_snippets
    result = ToolResult(
        ok=True,
        message="Síntese truncada...",
        data={
            "fallback_snippets": [
                {"title": "Fonte A", "url": "https://a.com", "snippet": "Conteúdo A", "source": "a.com"},
            ],
            "query": "IA"
        }
    )
    
    observation = result.model_observation()
    
    assert "fallback_snippets" in observation
    assert "Fonte A" in observation
    assert "Conteúdo A" in observation
```

#### Documentação de Mudança

**User-Visible**: ⚠️ Indiretamente (melhora recuperação em caso de rate limit, usuário vê menos erros "sobrecarregado")

**Changelog**:
> **[MELHORIA]** Pesquisas web agora são recuperáveis: se a síntese for interrompida por rate limit, o sistema reformula a resposta usando os trechos encontrados.

---

### 🟡 Correção 3: Ponto 2 — Visão: Fallback Automático para Gemini

**Objetivo**: Detectar modelo Groq Vision inválido e fazer fallback automático para Gemini Vision.

**Esforço**: 🟢 Baixo (3h)  
**Impacto**: 🟡 Médio (previne falhas quando modelo Groq obsoleto)  
**Breaking Change**: ❌ Não (melhora robustez)

#### Implementação

**Arquivo**: `app/services/vision.py`

**Mudanças**:

```python
def analyze(self, image_path: str | None = None, image_b64: str | None = None, prompt: str = "Descreva o que você vê nesta imagem.") -> str:
    # ... código de preparação de imagem ...
    
    active_provider = self._resolve_provider()
    active_key = self._get_key(active_provider)
    
    if not active_key:
        return "Nenhuma chave de API configurada para análise de visão."
    
    # NOVO: Try-catch com fallback automático
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
            reply = res.choices[0].message.content or ""
            return reply.strip()
    except Exception as e:
        error_str = str(e).lower()
        is_model_error = any(keyword in error_str for keyword in ["not found", "invalid model", "404", "model_not_found"])
        
        if is_model_error and active_provider == "groq":
            # FALLBACK AUTOMÁTICO para Gemini Vision
            print(f"[Vision] Modelo Groq '{self.groq_model}' inválido ou obsoleto. Fallback para Gemini Vision.")
            try:
                from google import genai
                from google.genai import types
                client = self._get_client("gemini", self._get_key("gemini"))
                
                # ... código de análise Gemini Vision existente ...
                # (copiar do bloco `else` atual)
                image_part = types.Part.from_bytes(
                    data=base64.b64decode(image_b64),
                    mime_type="image/jpeg"
                )
                res = client.models.generate_content(
                    model=self.model,
                    contents=[prompt, image_part]
                )
                return res.text.strip()
            except Exception as fallback_error:
                return f"Fallback para Gemini Vision também falhou: {fallback_error}"
        else:
            # Outro tipo de erro ou fallback já tentado
            return f"Erro ao analisar imagem: {e}"
    
    # ... código Gemini original ...
```

#### Testes de Validação

```python
# tests/test_vision_fallback.py
def test_vision_fallback_when_groq_model_not_found(monkeypatch):
    """Validar fallback automático para Gemini quando modelo Groq inválido."""
    from app.services.vision import VisionService
    
    vision = VisionService(gemini_api_key="test_key")
    
    # Mock de Groq client que lança erro de modelo não encontrado
    class FakeGroqClient:
        class ChatCompletions:
            def create(self, **kwargs):
                raise RuntimeError("model_not_found: qwen/qwen3.8-27b")
        
        def __init__(self):
            self.chat = self.ChatCompletions()
    
    # Mock de Gemini client que retorna sucesso
    class FakeGeminiClient:
        def generate_content(self, **kwargs):
            class FakeResponse:
                text = "Imagem analisada com sucesso via Gemini."
            return FakeResponse()
    
    monkeypatch.setattr("groq.Groq", lambda **kwargs: FakeGroqClient())
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: FakeGeminiClient())
    
    result = vision.analyze(image_b64="fake_base64", prompt="Teste")
    
    assert "Gemini" in result or "sucesso" in result
    # Verificar que print foi chamado com mensagem de fallback
```

#### Documentação de Mudança

**User-Visible**: ⚠️ Indiretamente (usuário vê menos erros de "modelo não encontrado")

**Changelog**:
> **[ROBUSTEZ]** Análise de visão agora faz fallback automático para Gemini Vision quando o modelo Groq configurado está indisponível.

---

## SPRINT 2: Melhorias de Estabilidade e UX

### 🔴 Correção 4: Ponto 4 — Rate Limit com Smart Wait

**Objetivo**: Implementar retry com espera inteligente (ao invés de desistir imediatamente) quando cooldown < 10s.

**Esforço**: 🟡 Médio (6h)  
**Impacto**: 🔴 Alto (reduz drasticamente falsos positivos de "sobrecarregado")  
**Breaking Change**: ❌ Não (melhora recovery)

#### Implementação

**Arquivo**: `app/services/llm.py`

**Mudanças**:

```python
class KeyRotator:
    # ... métodos existentes ...
    
    def min_cooldown_remaining(self, provider: str, settings: Any) -> float:
        """Retorna o menor tempo de cooldown restante (em segundos) dentre todas as chaves.
        Retorna 0 se há chave disponível agora; retorna float('inf') se não há chaves."""
        keys = self._cleaned_keys(provider, settings)
        if not keys:
            return float('inf')
        
        now = time.time()
        remaining = [max(0, self.cooldowns.get(k, 0) - now) for k in keys]
        return min(remaining)


def _recover_synthesis(error: Exception) -> str | None:
    if not is_rate_limit(error):
        return None
    
    _key_rotator.mark_rate_limit(api_key, error)
    
    # NOVO: Smart wait com até 2 tentativas
    max_wait_per_attempt = 5  # segundos
    max_attempts = 2
    
    for attempt in range(max_attempts):
        next_key = _key_rotator.get_key("groq", self.settings)
        
        if next_key and next_key != api_key:
            # Chave disponível AGORA, tenta imediatamente
            try:
                recovery_messages, _ = fit_request([
                    {"role": "system", "content": "Responda em português..."},
                    {"role": "user", "content": normalized[-1]["content"] if normalized else "Resuma os resultados."},
                    {"role": "user", "content": "Resultados confirmados:\n" + _tool_results_text()},
                ], [])
                
                response = Groq(api_key=next_key, max_retries=0).chat.completions.create(
                    model=model_name, messages=recovery_messages, temperature=0.2,
                    max_completion_tokens=1024, stream=False,
                )
                result = response.choices[0].message.content
                if result:
                    _emit_chunk(result)
                    return result
            except RunCancelled:
                raise
            except Exception as recovery_error:
                if is_rate_limit(recovery_error):
                    _key_rotator.mark_rate_limit(next_key, recovery_error)
                    # Continua para próxima tentativa
                else:
                    return None  # Erro não-429, desiste
        
        # NOVO: Nenhuma chave disponível AGORA; verifica se vale esperar
        if attempt < max_attempts - 1:  # Não esperar na última tentativa
            min_cooldown = _key_rotator.min_cooldown_remaining("groq", self.settings)
            if 0 < min_cooldown <= max_wait_per_attempt:
                # Vale a pena esperar
                wait_time = min_cooldown + 0.5  # Margem de segurança
                print(f"[Recovery] Aguardando {wait_time:.1f}s para chave ficar disponível...")
                time.sleep(wait_time)
                # Loop continua para tentar com a chave recém-liberada
            else:
                # Cooldown muito longo ou sem chaves, desiste
                break
    
    return None  # Todas as tentativas falharam
```

#### Testes de Validação

```python
# tests/test_rate_limit_smart_wait.py
def test_recovery_waits_for_short_cooldown(monkeypatch):
    """Validar que _recover_synthesis aguarda quando cooldown < 5s."""
    # Mock de KeyRotator com cooldown de 3s
    # Mock de time.sleep para capturar chamadas
    # Verificar que sleep(3.5) foi chamado
    # Verificar que segunda tentativa teve sucesso
    pass  # Implementação detalhada no código de teste


def test_recovery_does_not_wait_for_long_cooldown(monkeypatch):
    """Validar que _recover_synthesis desiste quando cooldown > 5s."""
    # Mock de KeyRotator com cooldown de 12s
    # Verificar que sleep NÃO foi chamado
    # Verificar que retornou None (desistiu)
    pass
```

#### Documentação de Mudança

**User-Visible**: ✅ SIM (menos mensagens "sobrecarregado")

**Changelog**:
> **[ESTABILIDADE]** Sistema agora aguarda automaticamente até 10 segundos quando chaves de API estão em cooldown curto, ao invés de falhar imediatamente. Você verá menos mensagens de "sobrecarregado".

---

### 🟡 Correção 5: Ponto 1 — Checklist: Melhorar Descriptions

**Objetivo**: Renomear `list_all` → `list_summaries` e melhorar descriptions para evitar ambiguidade.

**Esforço**: 🟢 Baixo (2h)  
**Impacto**: 🟡 Médio (melhora precisão de tool selection)  
**Breaking Change**: ⚠️ SIM (renomeia action)

#### Implementação

**Arquivo**: `app/agent/tools/checklist_tool.py`

**Mudanças**:

```python
@property
def parameters(self) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                # MUDANÇA: Renomear list_all → list_summaries
                "enum": ["create_list", "add_items", "toggle_item", "get_list", "list_summaries", "delete_list", "delete_item"],
                # MUDANÇA: Description mais explícita
                "description": (
                    "get_list: busca os ITENS (pendentes e concluídos) de uma checklist específica pelo título ou list_id; "
                    "list_summaries: lista apenas os RESUMOS (títulos e contadores) de todas as checklists; "
                    "create_list deve incluir text ou items quando o usuário pedir itens; "
                    "Consultar não exclui: use delete_list para excluir."
                ),
            },
            # ... resto dos parâmetros
        },
        "required": ["action"],
    }

def run(self, action: str = "get_list", ...) -> dict[str, Any]:
    act = (action or "get_list").lower().strip()
    
    # MUDANÇA: Aceitar tanto list_all (retrocompatibilidade) quanto list_summaries
    if act in ("list", "list_all", "list_summaries"):
        lists = checklist_store.list_all()
        return {
            "ok": True,
            "message": f"{len(lists)} checklist(s) encontrada(s).",
            "checklists": lists,
        }
    
    # ... resto do código
```

#### Testes de Validação

```python
# tests/test_checklist_ambiguity.py
def test_get_list_vs_list_summaries_distinction():
    """Validar que descriptions deixam claro: get_list → itens; list_summaries → resumos."""
    tool = ChecklistTool()
    params = tool.parameters
    
    action_desc = params["properties"]["action"]["description"]
    
    # Verificar que description menciona diferença explicitamente
    assert "ITENS" in action_desc.upper()
    assert "RESUMOS" in action_desc.upper()
    assert "get_list" in action_desc
    assert "list_summaries" in action_desc


def test_list_all_still_works_for_retrocompatibility():
    """Validar retrocompatibilidade: list_all ainda funciona."""
    tool = ChecklistTool()
    
    # Criar checklist
    tool.run(action="create_list", title="Teste", items=["item1"])
    
    # list_all ainda funciona (retrocompatibilidade)
    result = tool.run(action="list_all")
    assert result["ok"]
    assert len(result["checklists"]) == 1
    
    # list_summaries também funciona (novo nome)
    result = tool.run(action="list_summaries")
    assert result["ok"]
    assert len(result["checklists"]) == 1
```

**Teste manual necessário**: Submeter prompts ambíguos para LLM real e verificar escolha de action:
- ✅ "liste os itens da checklist Compras" → deve chamar `get_list`
- ✅ "liste minhas checklists" → deve chamar `list_summaries`
- ✅ "quantas checklists eu tenho" → deve chamar `list_summaries`

#### Documentação de Mudança

**User-Visible**: ⚠️ Indiretamente (tool interna; usuário não vê)

**Breaking Change**: ✅ SIM (mas mantém retrocompatibilidade com `list_all`)

**Changelog**:
> **[MELHORIA]** Ferramenta de checklist agora diferencia claramente entre listar itens de uma checklist específica (`get_list`) e listar resumos de todas as checklists (`list_summaries`). A action `list_all` ainda funciona por retrocompatibilidade mas será removida em versões futuras.

---

### 🟡 Correção 6: Ponto 7 — Timer: Feedback Audível Confirmado

**Objetivo**: Adicionar callback/log de confirmação quando timer dispara e áudio toca.

**Esforço**: 🟡 Médio (4h)  
**Impacto**: 🟡 Médio (melhora auditoria de timers)  
**Breaking Change**: ❌ Não (adiciona logging)

#### Implementação

**Arquivo**: `app/agent/tools/timer.py`

**Mudanças**:

```python
class _TimerManager:
    def __init__(self) -> None:
        self._timers = []
        self._thread = threading.Thread(target=self._loop, daemon=True, name="TimerThread")
        self._thread.start()
        # NOVO: Lista de callbacks para notificar quando timer dispara
        self._fire_callbacks: list[Callable[[str, bool], None]] = []
    
    def add_fire_callback(self, callback: Callable[[str, bool], None]) -> None:
        """Registra callback(label, success) que será chamado quando timer disparar."""
        self._fire_callbacks.append(callback)
    
    @staticmethod
    def _fire(label: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n*** ALERTA TIMER: {label} ({stamp}) ***", flush=True)
        
        success = False
        try:
            from app.core.logger import logger
            logger.warn("Timer", f"⏰ Timer disparado: {label}")
        except Exception:
            pass
        
        try:
            for _ in range(3):
                winsound.Beep(1000, 350)
                time.sleep(0.15)
            success = True  # NOVO: Áudio tocou com sucesso
        except Exception as e:
            try:
                from app.core.logger import logger
                logger.error("Timer", f"Falha ao tocar beep para '{label}': {e}")
            except Exception:
                pass
        
        # NOVO: Registrar em arquivo de auditoria
        try:
            audit_file = "data/timer_audit.log"
            with open(audit_file, "a", encoding="utf-8") as f:
                status = "SUCCESS" if success else "FAILED"
                f.write(f"{datetime.now().isoformat()} | {status} | {label}\n")
        except Exception:
            pass
        
        # NOVO: Notificar callbacks registrados
        manager = _TimerManager._instance
        if manager:
            for callback in manager._fire_callbacks:
                try:
                    callback(label, success)
                except Exception:
                    pass
```

**Integração opcional** (notificar via sistema de notificações):

```python
# Em app/main.py ou app/agent/orchestrator.py (inicialização):
try:
    from app.agent.tools.timer import _TimerManager
    from app.services import WindowsNotification
    
    def timer_notification_callback(label: str, success: bool):
        if success:
            WindowsNotification().show("Timer Disparado", label, duration=5)
        else:
            WindowsNotification().show("Timer Falhou", f"Não foi possível tocar áudio para: {label}", duration=8)
    
    _TimerManager().add_fire_callback(timer_notification_callback)
except Exception:
    pass
```

#### Testes de Validação

```python
# tests/test_timer_feedback.py
def test_timer_logs_success_to_audit_file(tmp_path, monkeypatch):
    """Validar que timer grava sucesso no arquivo de auditoria."""
    import time
    
    # Mock de winsound.Beep (sempre sucesso)
    beep_called = []
    monkeypatch.setattr("winsound.Beep", lambda f, d: beep_called.append((f, d)))
    
    # Mock de data path
    audit_file = tmp_path / "timer_audit.log"
    monkeypatch.setattr("app.agent.tools.timer.AUDIT_FILE", str(audit_file))
    
    tool = TimerTool()
    tool.execute({"action": "set_timer", "duration": "1s", "label": "Teste"})
    
    time.sleep(2)  # Aguardar disparo
    
    assert audit_file.exists()
    content = audit_file.read_text()
    assert "SUCCESS | Teste" in content
    assert len(beep_called) >= 3  # 3 beeps


def test_timer_callback_is_invoked(monkeypatch):
    """Validar que callbacks registrados são chamados quando timer dispara."""
    callback_invoked = []
    
    def test_callback(label: str, success: bool):
        callback_invoked.append((label, success))
    
    manager = _TimerManager()
    manager.add_fire_callback(test_callback)
    
    # ... criar timer, aguardar disparo ...
    
    assert len(callback_invoked) == 1
    assert callback_invoked[0][0] == "Teste"
    assert callback_invoked[0][1] is True  # success
```

#### Documentação de Mudança

**User-Visible**: ⚠️ Parcialmente (log é interno, mas notificações são visíveis)

**Changelog**:
> **[AUDITORIA]** Timers agora registram confirmação de disparo em `data/timer_audit.log`. Notificações Windows opcionais podem ser ativadas para alertas visuais quando timer dispara.

---

## SPRINT 3: Refatorações e Melhorias de QA

### 🟡 Correção 7: Ponto 5 — Keyword Matcher com Contexto Negativo

**Objetivo**: Adicionar lógica de exclusão para desambiguar "lista" (memórias vs checklists vs tarefas).

**Esforço**: 🟡 Médio (6h)  
**Impacto**: 🟡 Médio (melhora precisão de tool selection)  
**Breaking Change**: ❌ Não (refina seleção)

#### Implementação

**Arquivo**: `app/agent/tools/registry.py`

**Mudanças**:

```python
def allowed_tool_names(self, mode: str = "general", provider: str | None = None, user_text: str = "", *, narrow: bool = False) -> frozenset[str]:
    # ... código de inicialização ...
    
    # Aplicar matchers de keywords
    for pattern, tools in GROQ_KEYWORD_TOOLS + LOOP_KEYWORD_TOOLS:
        if pattern.search(normalized):
            dynamic_tools.update(tools)
    
    # NOVO: Contexto negativo — desambiguação de "lista"
    if re.search(r"\blista", normalized):
        # Se menciona "memória" ou "lembrar", NÃO ativar checklist
        if re.search(r"\b(?:memor|lembr)", normalized):
            dynamic_tools.discard("checklist_tool")
            dynamic_tools.add("memory")
        
        # Se menciona "tarefa" ou "pendência", NÃO ativar checklist
        elif re.search(r"\b(?:taref|pendenc|fazer|completar)", normalized):
            dynamic_tools.discard("checklist_tool")
            dynamic_tools.add("task_tool")
        
        # Se menciona "checklist" ou "compras" explicitamente, MANTER checklist
        elif re.search(r"\b(?:checklist|compra|mercado)", normalized):
            dynamic_tools.discard("task_tool")
            dynamic_tools.add("checklist_tool")
    
    # ... resto do código
```

#### Testes de Validação

```python
# tests/test_keyword_disambiguation.py
def test_lista_memorias_does_not_activate_checklist():
    """Validar que 'liste minhas memórias' NÃO ativa checklist_tool."""
    registry = ToolRegistry()
    
    tools = registry.allowed_tool_names(mode="general", provider="groq", user_text="liste minhas memórias")
    
    assert "memory" in tools or "memory_tool" in tools
    assert "checklist_tool" not in tools


def test_lista_tarefas_activates_task_tool_not_checklist():
    """Validar que 'lista de tarefas' ativa task_tool, não checklist_tool."""
    registry = ToolRegistry()
    
    tools = registry.allowed_tool_names(mode="general", provider="groq", user_text="lista de tarefas pendentes")
    
    assert "task_tool" in tools
    assert "checklist_tool" not in tools


def test_lista_compras_activates_checklist():
    """Validar que 'lista de compras' ativa checklist_tool."""
    registry = ToolRegistry()
    
    tools = registry.allowed_tool_names(mode="general", provider="groq", user_text="lista de compras do mercado")
    
    assert "checklist_tool" in tools
    assert "task_tool" not in tools
```

**Teste A/B necessário**: Validar com LLM real em produção por 1 semana e medir taxa de tool selection incorreta (métrica: quantas vezes LLM ignora tool sugerida e escolhe outra).

#### Documentação de Mudança

**User-Visible**: ❌ Não (lógica interna)

**Changelog**:
> **[OTIMIZAÇÃO]** Sistema de seleção de ferramentas agora desambigua melhor pedidos com "lista" (memórias vs checklists vs tarefas) baseado em contexto.

---

### 🟢 Correção 8: Ponto 9 — Testes de Integração Automatizados

**Objetivo**: Criar `tests/test_live_integration.py` com 11 cenários end-to-end.

**Esforço**: 🔴 Alto (16h)  
**Impacto**: 🟡 Médio (melhora QA e previne regressões)  
**Breaking Change**: ❌ Não (apenas testes)

#### Outline Completo

Ver `findings-tests.md` linhas 200-730 para outline detalhado dos 11 cenários.

**Resumo da estrutura**:
1. Fixture `live_server` que sobe servidor em thread
2. Fixture `agent_mock_llm` que retorna tool calls determinísticos
3. 11 cenários de teste cobrindo todos os 10 pontos do checkup

**Prioridade reduzida**: Implementar após correções críticas (Sprints 1 e 2) estarem estáveis.

---

## BACKLOG: Investigação Adicional

### 🟡 Investigação: Ponto 6 — Sequência de Ações

**Status**: Não verificável por análise estática; requer debugging com LLM real.

**Próximos passos**:
1. Reproduzir cenário: "Crie arquivo teste.txt, espere 2s, leia o arquivo"
2. Capturar logs completos do `ActionExecutor`
3. Verificar se `response.function_calls` contém as 3 chamadas
4. Se não, investigar por que LLM não retornou tool calls explícitas
5. Se sim, investigar por que `tool_calls` no response do painel está vazio

**Não priorizar** até ter evidência reproduzível do problema.

---

## Resumo de Entregas por Sprint

### SPRINT 1 (1 semana)
- ✅ Ponto 10: Delete com confirmação
- ✅ Ponto 8: Web search fallback
- ✅ Ponto 2: Vision fallback

**Entregáveis**: 3 correções críticas + testes + changelog

### SPRINT 2 (1 semana)
- ✅ Ponto 4: Rate limit smart wait
- ✅ Ponto 1: Checklist descriptions
- ✅ Ponto 7: Timer feedback

**Entregáveis**: 3 melhorias de estabilidade + testes + changelog

### SPRINT 3 (2 semanas)
- ✅ Ponto 5: Keyword matcher
- ✅ Ponto 9: Test suite

**Entregáveis**: 2 refatorações + suite de integração + CI config

---

**Fim do Plano de Correções**
