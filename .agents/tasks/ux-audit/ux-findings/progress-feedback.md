# Progress Feedback — Consolidação de Achados

**Data**: 2025-01-XX  
**Fonte**: Auditoria UX/DX Jarvis  
**Findings relacionados**: 2, 4, 5, 7, 8

---

## Problema Sistêmico

Operações longas (> 2s) no Jarvis ocorrem **sem feedback visual ou audível ao usuário**, criando percepção de travamento. Thread principal pode ficar bloqueada por 10-30s durante rate limiting, sem qualquer indicação de progresso.

---

## Categorias de Operações Sem Feedback

### 1. Operações de Automação Externa (Spotify, Apps)

#### 🔴 CRÍTICO: Spotify — 10+ Segundos Silenciosos

**Arquivo**: `app/agent/tools/spotify.py` (linhas 164-188)

**Fluxo atual**:
```python
# Linha 164-165: Abrir Spotify
if not was_running:
    _open_spotify()
    time.sleep(2.0)  # ← 2s silencioso

# Linha 175-176: Aguardar renderização
time.sleep(5.0 if not was_running else 2.5)  # ← 2.5-5s silencioso

# Linha 178-179: Focar janela
if _focus_spotify():
    time.sleep(1.5)  # ← 1.5s silencioso

# Linhas 181-185: Navegação por teclado
pyautogui.press("tab")
time.sleep(0.2)
pyautogui.press("down")
time.sleep(0.2)
pyautogui.press("enter")
time.sleep(1.0)  # ← 1s silencioso
```

**Total**: Até 10.2 segundos de espera sem qualquer feedback.

**Impacto no usuário**:
- Usuário diz "toca Bohemian Rhapsody"
- Sistema fica silencioso por 10+ segundos
- Usuário pensa que sistema travou ou não ouviu
- Pode cancelar, clicar novamente, ou fechar a janela
- Ansiedade e frustração durante espera

**✅ Solução: Callbacks de Progresso**

```python
def search_play(query: str, context: dict | None = None) -> ToolResult:
    """Busca e toca música/playlist no Spotify.
    
    Args:
        query: Termo de busca
        context: Deve conter callback 'on_progress' para feedback visual
    """
    def _progress(msg: str):
        """Helper para notificar progresso."""
        if context and context.get("on_progress"):
            context["on_progress"](msg)
        print(f"[Spotify] {msg}")
    
    was_running = _is_spotify_running()
    
    if not was_running:
        _progress("Abrindo Spotify...")  # ← FEEDBACK
        _open_spotify()
        time.sleep(2.0)
    
    _progress(f"Buscando '{query}' no Spotify...")  # ← FEEDBACK
    time.sleep(5.0 if not was_running else 2.5)
    
    if _focus_spotify():
        _progress("Selecionando primeira música...")  # ← FEEDBACK
        time.sleep(1.5)
        
        # Navegação por teclado
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.2)
        pyautogui.write(query, interval=0.03)
        time.sleep(0.2)
        
        pyautogui.press("tab")
        time.sleep(0.2)
        pyautogui.press("down")
        time.sleep(0.2)
        
        _progress("Iniciando reprodução...")  # ← FEEDBACK
        pyautogui.press("enter")
        time.sleep(1.0)
        
        return ToolResult(ok=True, message=f"Tocando '{query}' no Spotify.")
```

**Implementação na UI**:
```javascript
// panel.js - Mostrar toast com spinner durante operação
function onToolProgress(toolName, message) {
    showToast(message, 'info', {
        spinner: true,
        duration: null  // Persiste até próxima atualização
    });
}
```

---

### 2. Rate Limiting e Retry

#### 🔴 CRÍTICO: Thread Principal Bloqueada Durante Rate Limit

**Arquivo**: `app/core/rate_limit.py` (linha 27)

```python
# ❌ Problema: time.sleep bloqueante
def wait(self) -> None:
    with self._lock:
        self._clean()
        if len(self._timestamps) < self.max_per_window:
            self._timestamps.append(time.time())
            return
        wait = self.window - (time.time() - self._timestamps[0])
    
    if wait > 0:
        time.sleep(max(0.1, wait))  # ← BLOQUEIA THREAD PRINCIPAL (10-30s)
```

**Impacto**:
- Durante pico de uso, **UI congela completamente** por 10-30s
- Usuário não consegue clicar, navegar, ou cancelar
- Sistema parece ter crashado
- Barge-in bloqueado (usuário não consegue interromper)

**✅ Solução: Não Bloquear Thread**

```python
def check(self) -> float:
    """Verifica rate limit sem bloquear.
    
    Returns:
        0.0 se pode prosseguir
        float > 0 indicando segundos a esperar
    """
    with self._lock:
        self._clean()
        if len(self._timestamps) < self.max_per_window:
            return 0.0
        return self.window - (time.time() - self._timestamps[0])

def record(self) -> None:
    """Registra timestamp após operação bem-sucedida."""
    with self._lock:
        self._timestamps.append(time.time())

# Uso no orchestrator ou tool
wait_seconds = self.rate_limiter.check()
if wait_seconds > 0:
    # NÃO bloqueia; retorna mensagem ao usuário
    return ToolResult(
        ok=False,
        message=f"Aguarde {int(wait_seconds)}s antes de tentar novamente.",
        retry_after=wait_seconds  # UI pode mostrar countdown
    )

# Se OK, executa operação e registra
result = _execute_operation()
self.rate_limiter.record()
```

---

#### 🟡 IMPORTANTE: Retry Desiste com Cooldown Curto

**Arquivo**: `app/services/llm.py` (linhas 1339-1437)

**Problema**: Retry abandona prematuramente mesmo quando cooldown < 15s.

```python
# ❌ Antes: Desiste rapidamente
if min_cooldown > 0 and min_cooldown <= 15:
    wait_time = min(min_cooldown + 0.5, 2 ** (attempt + 1))
    _log(f"[LLM] Rate limit backoff attempt {attempt + 1}/{max_attempts}, waiting {wait_time:.1f}s")
    time.sleep(wait_time)
    # Mas max_attempts = 2, então desiste após 2 tentativas
```

**Cenário problemático**:
1. Usuário faz pergunta
2. Todas as chaves em rate limit
3. Uma chave tem cooldown de 8s restantes
4. Sistema tenta 2x e desiste → retorna "sobrecarregado"
5. Usuário vê erro mesmo havendo solução em 8s

**✅ Solução: Retry Persistente com Feedback**

```python
def _retry_with_backoff(self, prompt: str, context: dict | None = None) -> str:
    """Retry com exponential backoff e feedback ao usuário.
    
    Args:
        context: Deve conter 'on_progress' callback para notificar usuário
    """
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            return self._call_llm(prompt)
        
        except RateLimitError as e:
            min_cooldown = self.key_rotator.min_cooldown_remaining()
            
            # Se cooldown < 30s, vale a pena esperar
            if min_cooldown > 0 and min_cooldown <= 30:
                wait_time = min(min_cooldown + 1.0, 2 ** (attempt + 1))
                
                # ✅ FEEDBACK ao usuário
                message = f"Aguardando serviço disponível ({int(min_cooldown)}s)..."
                _log(f"[LLM] Rate limit backoff attempt {attempt + 1}/{max_attempts}, waiting {wait_time:.1f}s")
                
                if context and context.get("on_progress"):
                    context["on_progress"](message)
                
                time.sleep(wait_time)
                continue  # Tenta novamente
            
            else:
                # Cooldown muito longo (>30s), desiste
                _log(f"[LLM] Min cooldown {min_cooldown}s > 30s, aborting retry")
                raise
    
    # Esgotou tentativas
    raise RateLimitError("Todas as chaves em rate limit após 5 tentativas")
```

**Feedback na UI**:
```javascript
// Toast com barra de progresso durante retry
function showRetryProgress(seconds) {
    const toast = showToast(`Aguardando serviço disponível (${seconds}s)`, 'info', {
        duration: seconds * 1000,
        progressBar: true
    });
}
```

---

### 3. Timer — Confirmação de Disparo

#### 🟡 IMPORTANTE: Timer Dispara Sem Confirmação Visual

**Arquivo**: `app/agent/tools/timer.py` (linhas 90-127)

**Problema**: Timer cria alarme, dispara, mas usuário não tem confirmação de que funcionou.

```python
# ❌ Antes: Sem feedback de confirmação
def _fire(self, timer_id: str, label: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n*** ALERTA TIMER [{timer_id}]: {label} ({stamp}) ***", flush=True)
    
    # Toca beeps
    try:
        for _ in range(3):
            winsound.Beep(1000, 350)
            time.sleep(0.15)
        success = True
    except Exception as e:
        _log(f"[Timer {timer_id}] Falha ao tocar beep: {e}")
        success = False
    
    # ← Sem notificação visual ao usuário
```

**Impacto**:
- Se som estiver mutado ou sem alto-falante, falha silenciosa
- Usuário não tem confiança de que timer funcionou
- Perda de compromissos em caso de falha

**✅ Solução: Confirmação Visual + Audível**

```python
def _fire(self, timer_id: str, label: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n*** ALERTA TIMER [{timer_id}]: {label} ({stamp}) ***", flush=True)
    
    success = False
    
    # Tenta tocar beeps
    try:
        for _ in range(3):
            winsound.Beep(1000, 350)
            time.sleep(0.15)
        success = True
        _log(f"[Timer {timer_id}] Áudio tocou com sucesso.")
    except Exception as e:
        _log(f"[Timer {timer_id}] Falha ao tocar beep: {e}")
        success = False
    
    # ✅ FALLBACK: Notificação Windows se áudio falhar
    if not success:
        try:
            from app.services.notifications import WindowsNotification
            notifier = WindowsNotification()
            notifier.show(
                title=f"⏰ Timer: {label}",
                message=f"O timer disparou às {stamp} (áudio falhou)",
                duration=10
            )
            _log(f"[Timer {timer_id}] Fallback: notificação Windows enviada.")
        except Exception as notif_err:
            _log(f"[Timer {timer_id}] Fallback também falhou: {notif_err}")
    
    # ✅ NOTIFICAR PAINEL via event bus
    try:
        from app.ui.panel.event_bus import emit_event
        emit_event("timer_fired", {
            "timer_id": timer_id,
            "label": label,
            "success": success,
            "timestamp": stamp
        })
    except Exception as ev_err:
        _log(f"[Timer {timer_id}] Falha ao emitir evento: {ev_err}")
```

**UI**: Toast no painel quando timer dispara

```javascript
// panel.js - Listener de evento timer_fired
eventBus.on('timer_fired', (data) => {
    const icon = data.success ? '⏰' : '⚠️';
    const statusText = data.success ? 'disparou' : 'disparou (áudio falhou)';
    
    showToast(
        `${icon} Timer "${data.label}" ${statusText}`,
        data.success ? 'success' : 'warning',
        { duration: 10000, playSound: true }
    );
});
```

---

### 4. Confirmações Críticas — Countdown Silencioso

#### 🟡 IMPORTANTE: Timeout de 5 Minutos Sem Indicação Visual

**Arquivo**: `app/core/critical_confirm.py` (linhas 49-52)

**Problema**: Usuário tem 5 minutos para confirmar, mas não vê countdown.

```python
# ❌ Antes: Timeout silencioso
if self._done.wait(timeout=300):
    with self._lock:
        return self._approved
return False  # ← Timeout expirou, mas usuário não foi avisado gradualmente
```

**Impacto**:
- Usuário esquece que tem confirmação pendente
- Após 5 min, operação é cancelada silenciosamente
- Frustração e retrabalho

**✅ Solução: Countdown com Avisos Intermediários**

```python
def request(self, tool: str, detail: str = "") -> bool:
    """Solicita confirmação com countdown visível."""
    if not self.enabled:
        return True
    
    req_id = uuid.uuid4().hex[:12]
    with self._lock:
        self._pending = {"id": req_id, "tool": tool, "detail": detail}
        self._approved = False
        self._done.clear()
    
    print(f"\n[CONFIRMAÇÃO] {detail or f'Executar {tool}?'}")
    print("Confirme no painel (5 minutos)")
    
    # ✅ Thread de countdown com avisos
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
            
            # ✅ Avisos em momentos críticos
            if remaining == 60:
                print("[CONFIRMAÇÃO] ⚠️  Expira em 1 minuto")
                self._emit_warning(60)
            elif remaining == 10:
                print("[CONFIRMAÇÃO] 🚨 Expira em 10 segundos!")
                self._emit_warning(10)
            
            time.sleep(1)
    
    threading.Thread(target=countdown, daemon=True).start()
    
    if self._done.wait(timeout=300):
        with self._lock:
            return self._approved
    
    # ✅ Timeout atingido - mensagem clara
    print("[CONFIRMAÇÃO] ❌ Expirada. Operação cancelada.")
    with self._lock:
        self._pending = None
    return False

def _emit_warning(self, seconds_remaining: int):
    """Emite evento de aviso para UI."""
    try:
        from app.ui.panel.event_bus import emit_event
        emit_event("confirmation_warning", {"seconds": seconds_remaining})
    except Exception:
        pass
```

**UI**: Modal com barra de progresso

```html
<!-- Modal de confirmação com countdown -->
<div id="confirm-modal" class="modal">
    <div class="modal-content">
        <h3>Confirmação Necessária</h3>
        <p id="confirm-detail"></p>
        
        <!-- ✅ Barra de progresso visual -->
        <div class="progress-bar">
            <div id="confirm-progress" class="progress-fill"></div>
        </div>
        
        <p class="countdown">
            Expira em: <span id="confirm-countdown">5:00</span>
        </p>
        
        <button onclick="confirmAction()">Confirmar</button>
        <button onclick="cancelAction()">Cancelar</button>
    </div>
</div>
```

---

## Sistema de Callbacks de Progresso

### Proposta: Padronizar Interface de Progresso

Todas as ferramentas com operações > 1s devem aceitar `context` com callback `on_progress`:

```python
# Interface padrão
def tool_function(args, context: dict | None = None) -> ToolResult:
    """
    Args:
        context: Dict com callbacks opcionais:
            - on_progress: Callable[[str], None] - Notifica progresso
            - on_cancellable: Callable[[Callable], None] - Permite cancelamento
    """
    def _progress(msg: str):
        if context and context.get("on_progress"):
            context["on_progress"](msg)
        print(f"[Tool] {msg}")
    
    _progress("Iniciando operação...")
    # ... operação longa ...
    _progress("Processando...")
    # ... mais operação ...
    _progress("Finalizando...")
    
    return ToolResult(ok=True, message="Concluído")
```

### UI: Sistema de Toast com Spinner

```javascript
// panel.js - Sistema de feedback visual
class ProgressToast {
    show(message, options = {}) {
        const toast = document.createElement('div');
        toast.className = 'toast progress-toast';
        
        // Spinner se operação em andamento
        if (options.spinner) {
            const spinner = document.createElement('div');
            spinner.className = 'spinner';
            toast.appendChild(spinner);
        }
        
        const text = document.createElement('span');
        text.textContent = message;
        toast.appendChild(text);
        
        document.getElementById('toast-container').appendChild(toast);
        
        // Auto-dismiss após duration (se especificado)
        if (options.duration) {
            setTimeout(() => toast.remove(), options.duration);
        }
        
        return toast;
    }
    
    update(toast, message) {
        toast.querySelector('span').textContent = message;
    }
    
    dismiss(toast) {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }
}
```

---

## Checklist de Implementação

### Sprint 1 (Imediato)
- [ ] Desbloqueio de rate limiter (`app/core/rate_limit.py`) - método `check()` ao invés de `wait()`
- [ ] Feedback visual em Spotify (`app/agent/tools/spotify.py`) - callbacks "Abrindo...", "Buscando...", etc
- [ ] Sistema básico de toast com spinner na UI

### Sprint 2 (Médio Prazo)
- [ ] Retry persistente com feedback em `llm.py` - mostrar "Aguardando (Xs)..."
- [ ] Confirmação de timer com fallback para Windows Notification
- [ ] Countdown visual em confirmações críticas
- [ ] Event bus para comunicação tool → UI

### Sprint 3 (Longo Prazo)
- [ ] Padronizar interface de progresso em todas as ferramentas
- [ ] Permitir cancelamento de operações longas
- [ ] Progress bar para operações com duração conhecida
- [ ] Telemetria de operações longas (identificar novas oportunidades de feedback)

---

## Métricas de Sucesso

Após implementar feedback de progresso, espera-se:

- **Zero operações > 2s sem feedback visual** (auditável via testes)
- **Redução de 60% em cancelamentos prematuros** (usuário não acha que travou)
- **Aumento de 40% em satisfação com responsividade** (survey NPS)
- **Redução de 50% em reports de "sistema travado"** (tickets de suporte)
