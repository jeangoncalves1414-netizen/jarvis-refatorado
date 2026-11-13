# Achados da Investigação — Serviço LLM

**Investigador:** Agente de Checkup (análise estática)  
**Data:** 2025-01-11  
**Arquivos analisados:** `app/services/llm.py`, `app/services/vision.py`, `app/services/rate_limits.py`

---

## PONTO 2 — Visão: Modelo Hardcoded sem Validação

### Status
**CONFIRMADO** — Problema verificado com evidência clara no código-fonte.

### Evidência

**Arquivo:** `app/services/vision.py`, linha 39-40
```python
self.model = model
self.groq_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
```

**Uso do modelo:** `app/services/vision.py`, linha 128-138
```python
if active_provider == "groq":
    client = self._get_client("groq", active_key)
    res = client.chat.completions.create(
        model=self.groq_model,  # <- Modelo definido sem validação
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        }]
    )
```

**Infraestrutura de fallback existente:** `app/services/vision.py`, linha 44-52
```python
def _get_client(self, provider: str, api_key: str):
    if provider == "groq":
        if not self._groq_client:
            from groq import Groq
            self._groq_client = Groq(api_key=api_key)
        return self._groq_client
    else:
        from google import genai
        return genai.Client(api_key=api_key)  # <- Cliente Gemini já disponível
```

### Análise

1. **Confirmação do problema:**
   - `GROQ_VISION_MODEL` é definido no `__init__()` usando `os.getenv()` com default hardcoded `"qwen/qwen3.8-27b"`
   - NENHUMA validação é feita para verificar se o modelo existe na API Groq
   - Se o modelo for descontinuado, a primeira chamada a `analyze()` falhará com erro de API (ex: 404, model not found)

2. **Sem health-check:**
   - Não há validação na inicialização do serviço
   - Não há validação lazy no primeiro uso
   - Não há tentativa de fallback automático para Gemini Vision quando Groq falha

3. **Cliente Gemini já disponível:**
   - O método `_get_client()` já suporta provider "gemini" e retorna `genai.Client`
   - O atributo `self.model` já existe com default `"gemini-flash-latest"` (linha 29)
   - A lógica de análise com Gemini já está implementada (linhas 142-156)

### Gravidade e Impacto

**Gravidade:** MÉDIA  
**Impacto:**

- **Fragilidade operacional:** Se Groq descontinuar o modelo `qwen/qwen3.8-27b`, todas as análises de visão com provider="groq" falharão imediatamente
- **Experiência do usuário degradada:** Erro de API não é user-friendly ("model not found") ao invés de fallback silencioso
- **Sem recuperação automática:** Sistema não tenta Gemini Vision como backup, mesmo tendo infraestrutura pronta
- **Detecção tardia:** Falha só acontece em runtime no primeiro uso, não na inicialização do serviço

### Avaliação da Solução Proposta

**Solução proposta original:**
> Adicionar um health-check na inicialização que valida se o modelo existe e faz fallback para Gemini Vision automaticamente.

**Avaliação:** VIÁVEL, mas requer ajustes para evitar latência na inicialização.

#### Opção 1: Health-check na inicialização (NÃO RECOMENDADO)
- **Prós:** Detecta modelo obsoleto antes do primeiro uso
- **Contras:**
  - Adiciona latência na inicialização do serviço (requisição HTTP síncrona)
  - Groq API não tem endpoint público `/models` para listar modelos disponíveis (precisa tentar uma chamada dummy)
  - Falha de rede na inicialização pode bloquear startup do Jarvis

#### Opção 2: Validação lazy com fallback automático (RECOMENDADO)
Implementar try-catch no método `analyze()` que detecta falha de modelo Groq e faz fallback para Gemini:

```python
# Pseudo-código da solução recomendada
try:
    if active_provider == "groq":
        client = self._get_client("groq", active_key)
        res = client.chat.completions.create(
            model=self.groq_model,
            messages=[...]
        )
        reply = res.choices[0].message.content or ""
except Exception as e:
    # Detectar erros de modelo não encontrado/inválido
    if "not found" in str(e).lower() or "invalid model" in str(e).lower() or "404" in str(e):
        # Fallback automático para Gemini Vision
        print(f"[Vision] Modelo Groq '{self.groq_model}' inválido ou obsoleto. Fallback para Gemini Vision.")
        active_provider = "gemini"
        # Repetir a chamada com Gemini
        # [código de análise Gemini]
    else:
        raise  # Outros erros devem propagar
```

**Vantagens da Opção 2:**
- Zero overhead na inicialização
- Fallback ocorre apenas quando necessário (modelo realmente inválido)
- Aproveita 100% da infraestrutura existente (cliente Gemini já disponível)
- Mensagem de log clara para auditoria ("Modelo X obsoleto, usando Gemini")

#### Opção 3: Configuração com modelo de fallback explícito
Adicionar variável de ambiente `GROQ_VISION_FALLBACK_PROVIDER=gemini` para configurar comportamento:

```python
self.groq_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
self.fallback_provider = os.getenv("GROQ_VISION_FALLBACK_PROVIDER", "gemini")
```

### Recomendação Final

**Implementar Opção 2** (validação lazy com fallback automático):

1. **Detectar falhas de modelo inválido** no método `analyze()` via exception handling
2. **Logar o fallback** para auditoria: `"[Vision] Modelo Groq 'X' inválido. Fallback para Gemini Vision."`
3. **Repetir a análise com Gemini** usando código já existente
4. **Opcional:** Cache do resultado da validação (flag `_groq_model_failed`) para evitar retry em cada chamada

**Onde implementar:**
- Arquivo: `app/services/vision.py`
- Método: `analyze()`, bloco try-catch da chamada Groq (linha ~127-140)
- Adicionar lógica similar em `analyze_bytes()` (linha ~166-180)

---

## PONTO 4 — Rate Limit: Retry com Backoff ao Invés de Falha Imediata

### Status
**CONFIRMADO** — Comportamento atual verificado; solução proposta requer ajustes.

### Evidência

**Arquivo:** `app/services/llm.py`, linha 1322-1348 (função `_recover_synthesis`)
```python
def _recover_synthesis(error: Exception) -> str | None:
    if not is_rate_limit(error):
        return None
    _key_rotator.mark_rate_limit(api_key, error)
    next_key = _key_rotator.get_key("groq", self.settings)
    if not next_key or next_key == api_key:
        return None  # <- DESISTE IMEDIATAMENTE se não houver chave disponível
    # Only prose is retried: no tools or callbacks can repeat a completed action.
    recovery_messages, _ = fit_request([
        {"role": "system", "content": "Responda em português..."},
        {"role": "user", "content": normalized[-1]["content"] if normalized else "Resuma os resultados."},
        {"role": "user", "content": "Resultados confirmados:\n" + _tool_results_text()},
    ], [])
    try:
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
        # <- NÃO HÁ RETRY; retorna None imediatamente
    return None
```

**KeyRotator (gerenciador de cooldown):** `app/services/llm.py`, linha 46-91
```python
def get_key(self, provider: str, settings: Any) -> str:
    cleaned = self._cleaned_keys(provider, settings)
    if not cleaned:
        return ""
    now = time.time()
    start_idx = self.indices.get(provider, 0) % len(cleaned)
    # Procura a primeira chave que não está em cooldown
    for i in range(len(cleaned)):
        idx = (start_idx + i) % len(cleaned)
        k = cleaned[idx]
        cooldown_until = self.cooldowns.get(k, 0)
        if now >= cooldown_until:  # <- Chave disponível AGORA
            self.indices[provider] = idx
            return k
    # Se todas estiverem em cooldown, NÃO retorna chave bloqueada
    return ""  # <- Retorna vazio se TODAS as chaves estão em cooldown
```

**Função de extração de retry time:** `app/services/rate_limits.py`, linha 14-33
```python
def retry_seconds(error: Exception, default: float = 60) -> float:
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    delays = []
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw:
        try:
            delays.append(float(raw))
        except (TypeError, ValueError):
            try:
                delays.append(parsedate_to_datetime(str(raw)).timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
    for duration in re.findall(r"(?:try again in|retry in|retryDelay[\"']?\s*:\s*[\"']?)([0-9.hms\s]+)", str(error), re.I):
        parts = re.findall(r"(\d+(?:\.\d+)?)\s*(h|m|s)", duration)
        if parts:
            delays.append(sum(float(n) * {"h": 3600, "m": 60, "s": 1}[unit] for n, unit in parts))
    valid = [d for d in delays if math.isfinite(d) and d > 0]
    return math.ceil(max(valid)) + 1 if valid else default
```

### Análise

1. **Confirmação do comportamento atual:**
   - `_recover_synthesis()` é chamado quando a síntese final (após execução de tools) falha com rate limit 429
   - Marca a chave atual em cooldown via `_key_rotator.mark_rate_limit()`
   - Tenta obter PRÓXIMA chave com `_key_rotator.get_key()`
   - Se não houver chave disponível IMEDIATAMENTE (todas em cooldown), retorna `None` e desiste
   - **APENAS 1 TENTATIVA** com a próxima chave; se falhar, retorna `None`

2. **Como mede o cooldown:**
   - `retry_seconds(error, default=60)` extrai tempo de espera do header `Retry-After` ou da mensagem de erro
   - `mark_rate_limit()` usa `retry_seconds()` para calcular duração do cooldown
   - Cooldown é registrado como timestamp absoluto: `time.time() + retry_seconds`
   - `get_key()` compara `now >= cooldown_until` para verificar se chave está disponível

3. **Problema confirmado:**
   - Não há exponential backoff: tentativa única com próxima chave
   - Não há espera ativa: se cooldown < 10s, poderia aguardar ao invés de desistir
   - Cenário típico de falha:
     - Chave 1: cooldown 8s
     - Chave 2: cooldown 5s
     - `_recover_synthesis()` não aguarda; retorna `None` → usuário vê "sobrecarregado"

### Gravidade e Impacto

**Gravidade:** MÉDIA-ALTA  
**Impacto:**

- **Falsos positivos de indisponibilidade:** Usuário recebe mensagem "sobrecarregado" mesmo quando o sistema poderia esperar 2-4s e completar a síntese
- **Experiência degradada após tools executadas:** Ações já foram realizadas (checklist criada, memória salva), mas resposta final não é sintetizada
- **Desperdício de capacidade de recuperação:** Sistema tem múltiplas chaves mas não usa wait strategy inteligente para cooldowns curtos
- **Inconsistência com rotação imediata em outros fluxos:** `_generate_groq_stream()` faz rotação IMEDIATA com retry; `_recover_synthesis()` desiste

### Avaliação da Solução Proposta

**Solução proposta original:**
> Implementar retry com exponential backoff curto (2s, 4s) antes de entregar mensagem de "sobrecarregado", especialmente quando cooldown restante é < 10s.

**Avaliação:** VIÁVEL e RECOMENDADO, mas com ajustes no design.

#### Problema com exponential backoff clássico
- Exponential backoff (2s → 4s → 8s → 16s...) é projetado para **retry de erro transitório desconhecido**
- No caso de rate limit 429, o **tempo de espera exato é conhecido** via header `Retry-After`
- Usar backoff exponencial IGNORA a informação precisa fornecida pela API

#### Solução Recomendada: Smart Wait com Limite de Espera

**Estratégia:**
1. Verificar se há chave disponível com `cooldown_remaining < 10s`
2. Se sim, **aguardar ativamente** até o cooldown expirar (sleep)
3. Tentar novamente com a chave recém-liberada
4. Máximo de 2 ciclos de espera (total ~10s de wait time)
5. Se nenhuma chave ficar disponível em 10s, retornar `None` (fallback atual)

**Pseudo-código da implementação:**

```python
def _recover_synthesis(error: Exception) -> str | None:
    if not is_rate_limit(error):
        return None
    
    _key_rotator.mark_rate_limit(api_key, error)
    
    # Tenta até 2 vezes com smart wait (max 10s total)
    max_wait_per_attempt = 5  # segundos
    max_attempts = 2
    
    for attempt in range(max_attempts):
        next_key = _key_rotator.get_key("groq", self.settings)
        
        if next_key and next_key != api_key:
            # Chave disponível AGORA, tenta imediatamente
            try:
                # [código de recovery existente]
                response = Groq(api_key=next_key, max_retries=0).chat.completions.create(...)
                result = response.choices[0].message.content
                if result:
                    _emit_chunk(result)
                    return result
            except Exception as recovery_error:
                if is_rate_limit(recovery_error):
                    _key_rotator.mark_rate_limit(next_key, recovery_error)
                    # Continua para próxima tentativa
                else:
                    return None  # Erro não-429, desiste
        
        # Nenhuma chave disponível AGORA; verifica se vale a pena esperar
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
        else:
            # Última tentativa, sem espera
            break
    
    return None  # Todas as tentativas falharam
```

**Método auxiliar para KeyRotator:**

```python
def min_cooldown_remaining(self, provider: str, settings: Any) -> float:
    """Retorna o menor tempo de cooldown restante (em segundos) dentre todas as chaves.
    Retorna 0 se há chave disponível agora; retorna float('inf') se não há chaves."""
    keys = self._cleaned_keys(provider, settings)
    if not keys:
        return float('inf')
    
    now = time.time()
    remaining = [max(0, self.cooldowns.get(k, 0) - now) for k in keys]
    return min(remaining)
```

#### Por que NÃO usar exponential backoff?

**Exemplo comparativo:**

**Cenário:** Chave 1 com cooldown de 6s, chave 2 com cooldown de 3s.

| Estratégia | Tentativa 1 | Tentativa 2 | Resultado |
|------------|-------------|-------------|-----------|
| **Atual (sem retry)** | Falha imediata | - | Desiste; mensagem "sobrecarregado" |
| **Exponential backoff (2s, 4s)** | Espera 2s → Falha (chave 2 ainda bloqueada) | Espera 4s → Sucesso | **6s de espera** |
| **Smart wait (cooldown-aware)** | Espera 3.5s → Sucesso com chave 2 | - | **3.5s de espera** |

**Conclusão:** Smart wait é mais eficiente porque usa informação precisa do cooldown.

### Onde Implementar

**Arquivo:** `app/services/llm.py`  
**Método:** `_recover_synthesis()` (linha 1322)  
**Adicionar método:** `KeyRotator.min_cooldown_remaining()` (classe KeyRotator, linha 27)

### Validação Necessária

**IMPORTANTE:** Como este ponto envolve comportamento de retry em runtime (espera ativa), a validação completa requer **teste em runtime** com rate limit real:

1. **Teste unitário (mock):** Simular cooldowns curtos (2s, 5s) e verificar que wait ocorre
2. **Teste de integração (sandbox):** Forçar rate limit 429 com múltiplas chaves em cooldown curto
3. **Métricas:** Logar tempo total de espera em recovery e taxa de sucesso após wait

**Este achado marca explicitamente:** A solução proposta é válida por análise estática, mas a eficácia do smart wait só pode ser confirmada em runtime com rate limit real da API Groq.

---

## Resumo Executivo

| Ponto | Status | Gravidade | Validação |
|-------|--------|-----------|-----------|
| **PONTO 2** (Visão: modelo hardcoded) | ✅ CONFIRMADO | MÉDIA | Análise estática completa |
| **PONTO 4** (Rate limit: retry com backoff) | ✅ CONFIRMADO | MÉDIA-ALTA | Análise estática + **requer teste runtime** |

### Próximos Passos

1. **Ponto 2:** Implementar fallback lazy para Gemini Vision no método `analyze()` de `vision.py`
2. **Ponto 4:** Implementar smart wait com limite de 10s em `_recover_synthesis()` + adicionar `min_cooldown_remaining()` ao KeyRotator
3. **Teste runtime:** Validar Ponto 4 com rate limit real forçado (múltiplas chamadas rápidas para esgotar quota)

---

**Fim dos Achados — Investigação LLM Service**
