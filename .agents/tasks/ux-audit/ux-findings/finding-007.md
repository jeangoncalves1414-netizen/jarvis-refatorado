## Finding 7: Bloqueio de Thread Principal com `time.sleep` em Rate Limiter

**Categoria**: Performance
**Prioridade**: 🔴 CRÍTICO

### Problema Atual
O arquivo `app/core/rate_limit.py` (linha 27) usa `time.sleep` **bloqueante** que trava a thread principal:

```python
# Linha 27
time.sleep(max(0.1, wait))
```

Este sleep é chamado dentro de `RateLimiter.wait()`, que é usado sincronicamente em múltiplos pontos do sistema, incluindo no loop principal do agente (`app/agent/orchestrator.py`).

### Impacto no Usuário
- **UI congelada**: Durante rate limiting, toda a interface pode ficar não responsiva
- **Barge-in bloqueado**: Usuário não consegue interromper operação em andamento
- **Percepção de travamento**: Sistema parece "congelado" ao invés de "ocupado"
- **Degradação de experiência**: Em rate limit de 10-30s, toda a aplicação fica travada

### Proposta de Solução
Substituir `time.sleep` bloqueante por implementação assíncrona ou thread separada:

**Opção 1 - Async/await** (requer refatoração maior):
```python
async def wait_async(self) -> None:
    # ... lógica ...
    await asyncio.sleep(wait)
```

**Opção 2 - Threading com Event** (menor impacto):
```python
def wait(self) -> None:
    with self._lock:
        if len(self._timestamps) < self.max_per_window:
            return
        wait = self.window - (time.time() - self._timestamps[0])
    
    if wait > 0:
        # Não bloqueia thread principal; retorna controle imediatamente
        event = threading.Event()
        def delayed_continue():
            time.sleep(max(0.1, wait))
            event.set()
        
        threading.Thread(target=delayed_continue, daemon=True).start()
        # Retorna exceção específica para caller tratar
        raise RateLimitWait(wait_seconds=wait, event=event)
```

**Opção 3 - Separar rate limit de execução** (mais simples):
```python
def check(self) -> float:
    """Retorna segundos a esperar, ou 0 se pode prosseguir."""
    with self._lock:
        self._clean()
        if len(self._timestamps) < self.max_per_window:
            return 0.0
        return self.window - (time.time() - self._timestamps[0])

# Caller decide como esperar (background, mensagem ao usuário, etc)
```

### Implementação Estimada
**Complexa** — 5 horas (Opção 2 ou 3)

### Arquivos Envolvidos
- `app/core/rate_limit.py` (classe `RateLimiter`)
- Todos os callers de `RateLimiter.wait()` (orchestrator, tools, etc)
- `app/agent/orchestrator.py` (ajustar uso do rate limiter)

### Exemplo de Código
```python
# Opção 3: Simples e não-bloqueante

class RateLimiter:
    def check_and_record(self) -> float:
        """Verifica rate limit e registra timestamp se permitido.
        
        Returns:
            0.0 se pode prosseguir (timestamp registrado)
            float > 0 indicando segundos a esperar
        """
        with self._lock:
            self._clean()
            if len(self._timestamps) < self.max_per_window:
                self._timestamps.append(time.time())
                return 0.0
            return self.window - (time.time() - self._timestamps[0])

# No orchestrator ou tool:
wait_seconds = self.rate_limiter.check_and_record()
if wait_seconds > 0:
    # Não bloqueia; retorna mensagem ao usuário
    return ToolResult(
        ok=False, 
        message=f"Aguarde {int(wait_seconds)}s antes de tentar novamente."
    )
```
