## Finding 8: Confirmação Crítica com Timeout Silencioso

**Categoria**: UX
**Prioridade**: 🟡 IMPORTANTE

### Problema Atual
O arquivo `app/core/critical_confirm.py` (linha 49-52) implementa timeout de 5 minutos (300s) para confirmações críticas, mas **não há feedback visual de contagem regressiva**:

```python
# Linha 49-52
if self._done.wait(timeout=300):
    with self._lock:
        return self._approved
return False
```

O usuário vê apenas:
```
[CONFIRMAÇÃO] {detail}
Confirme no painel ou diga 'confirmar'/'cancelar'
```

Sem saber que tem apenas 5 minutos, e sem ver o tempo restante.

### Impacto no Usuário
- **Perda de contexto**: Após 5 minutos, usuário pode ter esquecido o que estava confirmando
- **Frustração**: Confirmação expira silenciosamente, ação é cancelada sem aviso claro
- **Retrabalho**: Usuário precisa reiniciar operação do zero após timeout
- **Ansiedade**: Sem countdown, usuário não sabe urgência da confirmação

### Proposta de Solução
Adicionar feedback visual de countdown no painel:

1. **Toast persistente** no painel com barra de progresso mostrando tempo restante
2. **Aviso aos 60s**: "Confirmação expira em 1 minuto"
3. **Aviso aos 10s**: "Confirmação expira em 10 segundos!" (mais destaque)
4. **Mensagem de expiração**: Se timeout, mostrar "Confirmação expirada. Operação cancelada."

### Implementação Estimada
**Média** — 2.5 horas

### Arquivos Envolvidos
- `app/core/critical_confirm.py` (adicionar callback de countdown)
- `app/ui/panel/templates/index.html` (adicionar modal de confirmação com countdown)
- `app/ui/panel/static/js/panel.js` (lógica de atualização do countdown)

### Exemplo de Código
```python
# critical_confirm.py - adicionar callbacks

class CriticalConfirm:
    def __init__(self, enabled: bool = True):
        self.enabled = self._load_pref(enabled)
        self._lock = threading.Lock()
        self._pending: dict | None = None
        self._done = threading.Event()
        self._approved = False
        self._countdown_callbacks: list[Callable[[int], None]] = []  # NOVO
    
    def add_countdown_callback(self, callback: Callable[[int], None]) -> None:
        """Callback será chamado com segundos restantes a cada 1s durante espera."""
        self._countdown_callbacks.append(callback)
    
    def request(self, tool: str, detail: str = "") -> bool:
        """Solicita confirmação para ação crítica."""
        if not self.enabled:
            return True
        
        req_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._pending = {"id": req_id, "tool": tool, "detail": detail}
            self._approved = False
            self._done.clear()
        
        print(f"\n[CONFIRMAÇÃO] {detail or f'Executar {tool}?'}")
        print("Confirme no painel ou diga 'confirmar'/'cancelar' (5 minutos)")
        
        # Thread de countdown
        def countdown():
            for remaining in range(300, 0, -1):
                if self._done.is_set():
                    break
                
                # Notificar callbacks a cada segundo
                for cb in self._countdown_callbacks:
                    try:
                        cb(remaining)
                    except Exception:
                        pass
                
                # Avisos especiais
                if remaining == 60:
                    print("[CONFIRMAÇÃO] ⚠️  Expira em 1 minuto")
                elif remaining == 10:
                    print("[CONFIRMAÇÃO] 🚨 Expira em 10 segundos!")
                
                time.sleep(1)
        
        threading.Thread(target=countdown, daemon=True).start()
        
        if self._done.wait(timeout=300):
            with self._lock:
                return self._approved
        
        # Timeout atingido
        print("[CONFIRMAÇÃO] ❌ Expirada. Operação cancelada.")
        with self._lock:
            self._pending = None
        return False
```

```javascript
// panel.js - UI do countdown
function showConfirmationModal(reqId, tool, detail, timeoutSeconds) {
    const modal = document.getElementById('confirm-modal');
    const detailEl = document.getElementById('confirm-detail');
    const countdownEl = document.getElementById('confirm-countdown');
    const progressBar = document.getElementById('confirm-progress');
    
    detailEl.textContent = detail || `Executar ${tool}?`;
    
    let remaining = timeoutSeconds;
    const interval = setInterval(() => {
        remaining--;
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        countdownEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        const progress = (remaining / timeoutSeconds) * 100;
        progressBar.style.width = `${progress}%`;
        
        // Mudar cor quando crítico
        if (remaining <= 10) {
            progressBar.classList.add('bg-error');
            countdownEl.classList.add('text-error');
        } else if (remaining <= 60) {
            progressBar.classList.add('bg-secondary');
        }
        
        if (remaining <= 0) {
            clearInterval(interval);
            modal.classList.add('hidden');
            showToast('Confirmação expirada. Operação cancelada.', 'error');
        }
    }, 1000);
    
    modal.classList.remove('hidden');
}
```
