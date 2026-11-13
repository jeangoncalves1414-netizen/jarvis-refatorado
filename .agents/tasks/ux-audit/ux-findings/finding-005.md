## Finding 5: Timer Sem Confirmação de Áudio ao Usuário

**Categoria**: UX
**Prioridade**: 🟡 IMPORTANTE

### Problema Atual
O arquivo `app/agent/tools/timer.py` cria timers e retorna sucesso imediatamente (linhas 183-187), mas **nunca confirma ao usuário se o áudio realmente tocou** quando o timer dispara.

No método `_fire` (linhas 90-127):
- Linha 103-105: Toca 3 beeps com `winsound.Beep`
- Linha 106: `success = True` é definido, mas **não há callback user-facing**
- Linhas 119-127: Callbacks são invocados, mas **não há confirmação na UI do painel**

### Impacto no Usuário
- **Falta de confiança**: Usuário cria timer mas não tem feedback se funcionou
- **Frustração**: Em caso de falha silenciosa (sem alto-falante, som mutado), usuário não sabe
- **Perda de compromissos**: Se o áudio falhar silenciosamente, o usuário perde o lembrete

### Proposta de Solução
Adicionar confirmação audível e visual quando timer dispara:

1. **Notificação visual no painel**: Toast/banner mostrando "Timer '{label}' disparado"
2. **Log na Central de Atividades**: Registrar disparo com status (sucesso/falha)
3. **Fallback para notificação Windows**: Se `winsound.Beep` falhar, usar `WindowsNotification`

### Implementação Estimada
**Simples** — 1.5 horas

### Arquivos Envolvidos
- `app/agent/tools/timer.py` (linhas 90-127, método `_fire`)
- `app/services/notifications.py` (para fallback de notificação Windows)
- `app/ui/panel/` (para adicionar toast/notificação visual)

### Exemplo de Código
```python
# Linha 90-127, método _fire
def _fire(self, timer_id: str, label: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n*** ALERTA TIMER [{timer_id}]: {label} ({stamp}) ***", flush=True)
    
    success = False
    try:
        from app.core.logger import logger
        logger.info("Timer", f"⏰ Timer [{timer_id}] '{label}' disparado.")
    except Exception:
        pass
    
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
        
        # NOVO: Fallback para notificação Windows
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
            _log(f"[Timer {timer_id}] Fallback de notificação também falhou: {notif_err}")
    
    # NOVO: Notificar painel via websocket ou API de eventos
    try:
        from app.ui.panel.event_bus import emit_event
        emit_event("timer_fired", {
            "timer_id": timer_id,
            "label": label,
            "success": success,
            "timestamp": stamp
        })
    except Exception as ev_err:
        _log(f"[Timer {timer_id}] Falha ao emitir evento para painel: {ev_err}")
    
    # Restante do código (audit log, callbacks)...
```
