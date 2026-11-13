## Finding 9: Wake Word Detection com Polling Bloqueante

**Categoria**: Performance
**Prioridade**: 🟡 IMPORTANTE

### Problema Atual
O arquivo `app/services/voice/wake_word.py` (linhas 209, 217, 220) usa múltiplos `time.sleep` bloqueantes no loop principal de detecção de wake word:

```python
# Linha 209
import time; time.sleep(0.2)

# Linha 217
import time; time.sleep(0.5)

# Linha 220
import time; time.sleep(0.2)
```

Este loop roda em thread separada, mas os sleeps indicam polling ineficiente ao invés de event-driven.

### Impacto no Usuário
- **Latência de detecção**: Atraso de 0.2-0.5s entre falar wake word e sistema responder
- **CPU desperdiçado**: Polling constante ao invés de espera event-driven
- **Bateria (laptops)**: Polling consome mais energia que event callbacks
- **Responsividade degradada**: Durante sleeps, sistema não detecta wake word

### Proposta de Solução
Substituir polling com sleeps por sistema event-driven ou callback-based:

**Opção 1 - Event-driven com threading.Event**:
```python
def _loop(self):
    while self._running:
        if not self._enabled:
            self._enabled_event.wait()  # Bloqueia até enabled=True
            continue
        
        # Processa audio stream com callback ao invés de polling
        stream.start_stream()  # callback interno processa chunks
```

**Opção 2 - Reduzir latência dos sleeps**:
Se event-driven não for possível, reduzir sleeps para < 50ms:
```python
# Ao invés de time.sleep(0.2), usar wait com timeout curto
if not self._enabled_event.wait(timeout=0.05):
    continue
```

### Implementação Estimada
**Média** — 2 horas

### Arquivos Envolvidos
- `app/services/voice/wake_word.py` (linhas 209, 217, 220)
- Biblioteca de audio (pyaudio/sounddevice) para callback-based streaming

### Exemplo de Código
```python
# Antes (linha 220)
if not self._enabled:
    import time; time.sleep(0.2)
    continue

# Depois - Event-driven
if not self._enabled:
    # Bloqueia até enabled=True, sem polling
    self._enabled_event.wait()
    continue

# Ou se precisar de timeout para cleanup
if not self._enabled:
    # Timeout curto (50ms) para permitir verificação de _running
    if self._enabled_event.wait(timeout=0.05):
        # Foi habilitado, continua
        pass
    continue
```

```python
# Abordagem event-driven completa
def _loop(self):
    """Loop principal event-driven sem polling."""
    while self._running:
        # Aguarda até ser habilitado
        self._enabled_event.wait()
        
        if not self._running:
            break
        
        try:
            # Abre stream com callback (não-bloqueante)
            stream = self._audio.open(
                format=self._format,
                channels=1,
                rate=self._rate,
                input=True,
                frames_per_buffer=self._chunk,
                stream_callback=self._audio_callback  # NOVO
            )
            
            stream.start_stream()
            
            # Aguarda até ser desabilitado (event-driven)
            while self._enabled and self._running:
                time.sleep(0.1)  # Check periódico leve
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            logger.error(f"Wake word stream error: {e}")
            time.sleep(1.0)  # Backoff em caso de erro

def _audio_callback(self, in_data, frame_count, time_info, status):
    """Callback processado em thread de audio (não-bloqueante)."""
    if not self._enabled:
        return (None, pyaudio.paContinue)
    
    # Processa audio chunk
    audio_chunk = np.frombuffer(in_data, dtype=np.int16)
    
    # Detecção de wake word aqui (sem polling)
    if self._detect_wake_word(audio_chunk):
        self._on_wake_word_detected()
    
    return (None, pyaudio.paContinue)
```
