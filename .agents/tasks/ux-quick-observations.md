# Observações Rápidas de UX — Análise Preliminar

**Data**: 2026-11-13  
**Contexto**: Análise manual enquanto workflow de auditoria profunda está rodando

---

## 🔴 CRÍTICO — Quick Wins Identificados

### 1. Mensagens Anti-Spam/Anti-Loop Agressivas

**Arquivo**: `app/agent/tools/whatsapp.py` linhas 70-73

**Problema Atual**:
```python
return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")
return ToolResult(ok=False, message="ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos.")
```

**Por que é problema**:
- **MAIÚSCULAS**: Tom agressivo, parece que o usuário fez algo errado
- **Termos técnicos**: "ANTI-SPAM", "ANTI-LOOP" não são amigáveis
- **Falta de contexto**: Usuário não sabe por que tem essa limitação

**Impacto no Usuário**:
- Frustração: parece que está sendo repreendido
- Confusão: "por que o Jarvis está gritando comigo?"
- Desconfiança: "será que o Jarvis acha que sou spam?"

**Solução Proposta**:
```python
# ANTES (linha 70)
return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")

# DEPOIS
return ToolResult(
    ok=False, 
    message="⏱️ Vamos com calma! Aguarde mais alguns segundos antes de enviar outra mensagem para esse contato. "
            "(Isso evita envios acidentais em sequência)"
)

# ANTES (linha 73)
return ToolResult(ok=False, message="ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos.")

# DEPOIS
return ToolResult(
    ok=False,
    message="🔄 Hmm, parece que você acabou de enviar essa mesma mensagem para esse contato há pouco tempo. "
            "Quer mesmo enviar de novo?"
)
```

**Benefícios**:
- Tom amigável e empático (emoji + explicação)
- Linguagem natural (sem termos técnicos)
- Contexto claro (por que está bloqueando)
- Sugere alternativa ("Quer mesmo enviar de novo?")

**Implementação**: < 5 minutos
**Prioridade**: 🔴 **CRÍTICA** (aparece em interação direta com usuário)

---

### 2. Timeout Feedback Ausente

**Contexto**: Várias operações têm timeouts (browser 15s, LLM rate limit retry até 10s) mas usuário não vê feedback

**Problema Atual**:
- Browser service: timeout de 15s sem indicação de progresso
- LLM retry: aguarda 2s, 4s, 8s silenciosamente
- Timer: dispara após N segundos sem countdown visível

**Impacto no Usuário**:
- Ansiedade: "o sistema travou ou está processando?"
- Abandono: usuário cancela antes do timeout expirar
- Frustração: não sabe quanto tempo falta

**Solução Proposta**:

**A. Progress Reporting via run_tracking**:
```python
# Em app/services/llm.py linha ~1420
from app.agent.run_tracking import record_run_step

# Durante backoff
for attempt in range(max_attempts):
    if attempt < max_attempts - 1:
        cooldown = _key_rotator.min_cooldown_remaining("groq", settings)
        
        if 0 < cooldown <= max_wait_threshold:
            wait_time = min(cooldown + 0.5, 2 ** (attempt + 1))
            
            # ADICIONAR FEEDBACK
            record_run_step(
                f"⏳ Aguardando {wait_time:.0f}s para próxima tentativa... (chaves em cooldown)",
                kind="step"
            )
            
            time.sleep(wait_time)
```

**B. Browser Timeout com Progress**:
```python
# Em app/services/browser/service.py
from app.agent.run_tracking import record_run_step

def navigate(self, url: str):
    record_run_step(f"🌐 Navegando para {url}...", kind="step")
    
    try:
        # navegação existente
        pass
    except TimeoutError:
        record_run_step(
            f"⏱️ Navegação para {url} demorou mais de 15s. "
            "Isso pode ser normal para sites lentos.",
            kind="warning"
        )
```

**Benefícios**:
- Usuário vê progresso em tempo real no painel
- Reduz ansiedade de "travou?"
- Contexto claro: "está demorando, mas é normal"

**Implementação**: 1-2 horas
**Prioridade**: 🟡 **IMPORTANTE**

---

### 3. Error Messages sem Sugestões de Correção

**Problema Atual**: Erros como "WhatsApp desconectado" não dizem o que fazer

**Exemplo** (`whatsapp.py` linha ~96):
```python
if "login" in stderr or "login" in stdout:
    return ToolResult(
        ok=False,
        message="WhatsApp desconectado. Por favor, execute 'npx mudslide login' no terminal para parear o QR Code."
    )
```

**Impacto no Usuário**:
- Incerteza: "como eu executo isso?"
- Interrupção do fluxo: precisa abrir terminal manualmente
- Erro pode assustar usuários não-técnicos

**Solução Proposta**:
```python
# DEPOIS
if "login" in stderr or "login" in stdout:
    return ToolResult(
        ok=False,
        message="📱 Seu WhatsApp precisa ser conectado novamente. "
                "Vou te ajudar a fazer isso:\n\n"
                "1. Abra um terminal (pressione Win+R, digite 'cmd', Enter)\n"
                "2. Cole este comando: npx mudslide login\n"
                "3. Escaneie o QR Code que aparecer com seu celular\n\n"
                "Depois disso, você pode tentar enviar a mensagem novamente!",
        data={
            "action_button": {
                "label": "📋 Copiar comando",
                "command": "npx mudslide login"
            }
        }
    )
```

**Benefícios**:
- Guia passo-a-passo claro
- Botão para copiar comando (menos chance de erro de digitação)
- Tom empático ("Vou te ajudar")

**Implementação**: 30 minutos
**Prioridade**: 🟡 **IMPORTANTE**

---

### 4. Guardrail "No Progress" sem Explicação

**Arquivo**: `app/agent/tool_guardrails.py` linha 48

**Problema Atual**:
```python
return ToolGuardrailDecision(False, f"Ferramenta interrompida por resultado sem progresso: {tool_name}.")
```

**Impacto no Usuário**:
- Confusão: "o que é 'resultado sem progresso'?"
- Frustração: "por que o Jarvis parou de funcionar?"
- Usuário não sabe se deve tentar de novo

**Solução Proposta**:
```python
# DEPOIS
return ToolGuardrailDecision(
    False, 
    f"⚠️ Percebi que a ferramenta '{tool_name}' está retornando o mesmo resultado repetidamente "
    f"sem resolver o problema. Vamos tentar uma abordagem diferente?"
)
```

**Benefícios**:
- Linguagem natural (sem termos técnicos)
- Explica O QUE aconteceu e POR QUE parou
- Sugere próximo passo ("abordagem diferente")

**Implementação**: < 5 minutos
**Prioridade**: 🟡 **IMPORTANTE**

---

### 5. Wait Tool sem Countdown Visual

**Arquivo**: `app/agent/tools/wait.py` (presumido baseado em grep)

**Problema Atual**:
- `wait(seconds=30)` congela por 30s sem feedback
- Usuário não sabe se travou ou está aguardando
- Impossível cancelar mid-wait

**Impacto no Usuário**:
- Ansiedade: "travou?"
- Frustração: "quanto tempo falta?"
- Interrupção forçada: Ctrl+C ou fecha o app

**Solução Proposta**:
```python
# Em app/agent/tools/wait.py
from app.agent.run_tracking import record_run_step
import time

def execute(self, args, context):
    seconds = args.get("seconds", 0)
    
    # Para esperas curtas (<5s), apenas aguarda
    if seconds < 5:
        time.sleep(seconds)
        return ToolResult(ok=True, message=f"Aguardei {seconds}s.")
    
    # Para esperas longas, mostra countdown
    record_run_step(f"⏳ Aguardando {seconds}s...", kind="step")
    
    # Countdown em chunks de 1s
    for remaining in range(seconds, 0, -1):
        if remaining % 5 == 0 or remaining <= 3:  # Atualiza a cada 5s e nos últimos 3s
            record_run_step(
                f"⏳ Aguardando... {remaining}s restantes",
                kind="step"
            )
        time.sleep(1)
    
    return ToolResult(ok=True, message="✅ Espera concluída!")
```

**Benefícios**:
- Feedback visual de progresso
- Usuário sabe exatamente quanto tempo falta
- Menos ansiedade

**Implementação**: 15 minutos
**Prioridade**: 🟢 **NICE-TO-HAVE** (wait tool não é usado frequentemente)

---

## 🟡 IMPORTANTE — Melhorias de Médio Prazo

### 6. Rate Limit Messaging Técnico

**Arquivo**: `app/services/llm.py` (KeyRotator)

**Problema**: Mensagens como "Groq: limite temporário de uso (429). 3 de 3 chaves em espera."

**Impacto**: Usuário não-técnico não entende "429" ou "chaves em espera"

**Solução**:
```python
# ANTES
return f"{provider.capitalize()}: {reason} (429). {len(blocked)} de {len(keys)} chaves em espera."

# DEPOIS
if seconds <= 15:
    return f"⏱️ Estou um pouco ocupado no momento, mas vou me liberar em alguns segundos! "
           f"(Minhas chaves de API estão se recuperando)"
else:
    return f"⏱️ Vou precisar de uma pausa de ~{seconds}s para recuperar acesso ao serviço de IA. "
           f"Isso é normal quando muitas pessoas usam ao mesmo tempo!"
```

**Implementação**: 30 minutos
**Prioridade**: 🟡 **IMPORTANTE**

---

### 7. Onboarding Inexistente

**Problema**: Primeira experiência não tem tour, wizard ou exemplos clicáveis

**Impacto**: Usuário novo fica perdido sem saber o que fazer

**Solução Proposta**:
1. **Welcome Modal** na primeira vez:
   - "Olá! 👋 Sou o Jarvis, seu assistente pessoal"
   - 3-5 ações de exemplo clicáveis
   - Link para tutorial interativo

2. **Tooltips Contextuais**:
   - Aparecem na primeira vez que usuário vê cada seção
   - "Aqui você vê suas conversas anteriores"
   - "Clique aqui para enviar mensagem"

3. **Empty States com Sugestões**:
   - Quando chat está vazio: "Experimente perguntar: 'Que horas são?'"
   - Quando não tem rotinas: "Quer que eu configure uma rotina matinal?"

**Implementação**: 4-6 horas
**Prioridade**: 🟡 **IMPORTANTE** (afeta adoção de novos usuários)

---

### 8. Browser Timeout Fixo

**Arquivo**: Baseado em testes `test_browser_tool.py`

**Problema**: Timeout de 15s fixo pode frustrar em sites lentos

**Solução**:
- Timeout adaptativo baseado no histórico do domínio
- Ou configuração por usuário: "Modo Rápido" (10s) vs "Modo Paciente" (30s)
- Ou detecção inteligente: se primeira carga falhou, tenta com 2x timeout

**Implementação**: 2-3 horas
**Prioridade**: 🟢 **NICE-TO-HAVE**

---

### 9. Confirmações Redundantes

**Problema**: Sistema pode pedir confirmação múltiplas vezes para ações similares

**Solução**:
- "Lembrar minha escolha para esta sessão" checkbox
- Pre-approve ações comuns para usuários avançados
- Undo inteligente ao invés de confirmação prévia

**Implementação**: 3-4 horas
**Prioridade**: 🟢 **NICE-TO-HAVE**

---

### 10. Falta de "Status Bar" Persistente

**Problema**: Usuário não sabe o estado do sistema (conectado? processando? idle?)

**Solução**:
- Status bar no topo/rodapé:
  - 🟢 **Online** | 🟡 **Processando...** | 🔴 **Desconectado**
  - Última ação: "Enviou mensagem há 2min"
  - API keys status: "✅ Groq | ✅ Gemini | ⚠️ OpenAI (cooldown 30s)"

**Implementação**: 2-3 horas
**Prioridade**: 🟡 **IMPORTANTE**

---

## 📊 Métricas de Impacto Estimadas

| Melhoria | Implementação | Impacto UX | ROI |
|----------|--------------|-----------|-----|
| 1. Mensagens Anti-Spam | 5min | 🔴 Alto | ⭐⭐⭐⭐⭐ |
| 2. Timeout Feedback | 1-2h | 🟡 Médio | ⭐⭐⭐⭐ |
| 3. Error Suggestions | 30min | 🟡 Médio | ⭐⭐⭐⭐⭐ |
| 4. Guardrail Messages | 5min | 🟡 Médio | ⭐⭐⭐⭐⭐ |
| 5. Wait Countdown | 15min | 🟢 Baixo | ⭐⭐⭐ |
| 6. Rate Limit Messages | 30min | 🟡 Médio | ⭐⭐⭐⭐ |
| 7. Onboarding | 4-6h | 🔴 Alto | ⭐⭐⭐⭐ |
| 8. Browser Timeout | 2-3h | 🟢 Baixo | ⭐⭐ |
| 9. Confirmações | 3-4h | 🟢 Baixo | ⭐⭐ |
| 10. Status Bar | 2-3h | 🟡 Médio | ⭐⭐⭐ |

**ROI = Impacto / Implementação** (quanto maior, melhor)

---

## 🚀 Recomendação de Implementação

**SPRINT 3 — Quick Wins (< 2h total)**:
1. Mensagens Anti-Spam humanizadas (5min)
2. Guardrail messages humanizadas (5min)
3. Error suggestions para WhatsApp (30min)
4. Wait countdown visual (15min)
5. Rate limit messages humanizadas (30min)

**Total**: ~1h 25min de trabalho, **impacto massivo na percepção do usuário**

**SPRINT 4 — Medium Wins (< 6h total)**:
1. Timeout feedback via run_tracking (1-2h)
2. Status bar persistente (2-3h)
3. Onboarding welcome modal (2-3h)

---

## 💡 Insights Gerais

### Tom de Voz Inconsistente
- Alguns lugares: formal ("Por favor, execute...")
- Outros lugares: casual ("Vou te ajudar")
- Alguns lugares: técnico ("ANTI-LOOP", "429")

**Recomendação**: Criar guia de estilo consistente:
- Tom: amigável, empático, casual mas respeitoso
- Emojis: usar quando apropriado (⏱️, 🌐, ✅, ❌)
- Evitar: maiúsculas agressivas, termos técnicos, jargão

### Feedback Assíncrono
- Muitas operações longas sem feedback intermediário
- `run_tracking` já existe mas está subutilizado

**Recomendação**: Usar `record_run_step()` religiosamente para:
- Operações > 3s
- Cada tentativa de retry
- Progresso de uploads/downloads
- Mudanças de estado importantes

### Error Recovery
- Erros geralmente param a execução
- Falta sugestões do que fazer a seguir

**Recomendação**: Sempre incluir "próximo passo" em erros:
- "Quer que eu tente de novo?"
- "Posso abrir as configurações para você?"
- "Vamos tentar uma abordagem diferente?"

---

**Status**: Observações preliminares. Aguardando workflow de auditoria completa para findings detalhados.
