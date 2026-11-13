## Finding 4: Rate Limit Recovery Insuficiente com Cooldown Curto

**Categoria**: Performance
**Prioridade**: 🟡 IMPORTANTE

### Problema Atual
O arquivo `app/services/llm.py` implementa retry com exponential backoff (linhas 1434-1437), mas ainda desiste rapidamente quando há cooldown < 10s restante. A função `_recover_synthesis` (linhas 1339-1356) tenta apenas 1 chave alternativa e desiste.

Cenário problemático:
1. Todas as chaves entram em rate limit (429)
2. Uma chave tem cooldown de apenas 8 segundos restantes
3. Sistema retorna "sobrecarregado" ao invés de aguardar 8s e tentar novamente
4. Usuário recebe erro mesmo havendo solução iminente

### Impacto no Usuário
- **Falhas desnecessárias**: Usuário vê erro "sobrecarregado" quando esperar 8-10s resolveria
- **Frustração**: Operação falha sem tentar suficientemente
- **Degradação de experiência**: Em horários de pico, usuário enfrenta falhas frequentes

### Proposta de Solução
Implementar retry mais persistente quando o cooldown restante é curto (< 15s):

1. Se `min_cooldown_remaining() < 15s`, esperar e tentar novamente
2. Mostrar mensagem informativa: "Aguardando serviço disponível (X segundos)..."
3. Só retornar erro se **todas** as chaves estão em cooldown > 30s

### Implementação Estimada
**Média** — 2 horas

### Arquivos Envolvidos
- `app/services/llm.py` (linhas 1339-1437, método `_recover_synthesis` e retry logic)
- `app/services/llm.py` (classe `KeyRotator`, método `min_cooldown_remaining`)

### Exemplo de Código
```python
# Antes (linha 1434-1437)
if min_cooldown > 0 and min_cooldown <= 15:
    wait_time = min(min_cooldown + 0.5, 2 ** (attempt + 1))
    _log(f"[LLM] Rate limit backoff attempt {attempt + 1}/{max_attempts}, waiting {wait_time:.1f}s")
    time.sleep(wait_time)
    # Loop continua

# Depois
if min_cooldown > 0:
    # Se cooldown é curto, vale a pena esperar
    if min_cooldown <= 30:
        wait_time = min(min_cooldown + 1.0, 2 ** (attempt + 1))
        user_msg = f"Aguardando serviço disponível ({int(min_cooldown)}s)..."
        _log(f"[LLM] Rate limit backoff attempt {attempt + 1}/{max_attempts}, waiting {wait_time:.1f}s")
        
        # Notificar usuário se há callback de progresso
        if context and context.get("on_progress"):
            context["on_progress"](user_msg)
        
        time.sleep(wait_time)
        # Loop continua para tentar novamente
    else:
        # Cooldown muito longo (>30s), desiste
        break
```
