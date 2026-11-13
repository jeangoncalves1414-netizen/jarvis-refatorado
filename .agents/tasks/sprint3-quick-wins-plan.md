# SPRINT 3 — Quick Wins UX/DX

**Data**: 2026-11-13  
**Objetivo**: Implementar 5 melhorias de UX com ROI altíssimo (< 2h total)  
**Impacto**: Humanizar comunicação do Jarvis, reduzir frustração do usuário

---

## 📋 Resumo Executivo

Implementar 5 correções rápidas que humanizam a comunicação do sistema:

| # | Melhoria | Tempo | Impacto | ROI |
|---|----------|-------|---------|-----|
| 1 | Mensagens Anti-Spam amigáveis | 5min | 🔴 Alto | ⭐⭐⭐⭐⭐ |
| 2 | Guardrail messages humanizadas | 5min | 🟡 Médio | ⭐⭐⭐⭐⭐ |
| 3 | Error messages com sugestões | 30min | 🟡 Médio | ⭐⭐⭐⭐⭐ |
| 4 | Wait tool com countdown | 15min | 🟢 Baixo | ⭐⭐⭐ |
| 5 | Rate limit messages amigáveis | 30min | 🟡 Médio | ⭐⭐⭐⭐ |

**Total estimado**: ~1h 25min  
**Resultado**: Sistema percebido como 10x mais amigável e profissional

---

## 🎯 Correções Detalhadas

### 1. WhatsApp Anti-Spam/Anti-Loop Humanizado

**Arquivo**: `app/agent/tools/whatsapp.py`

**Problema**: Mensagens em MAIÚSCULAS com termos técnicos assustam usuário

**Mudanças**:

```python
# LINHA 70 - ANTES
if time_diff < 10:
    return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")

# LINHA 70 - DEPOIS
if time_diff < 10:
    remaining = int(10 - time_diff)
    return ToolResult(
        ok=False, 
        message=f"⏱️ Vamos com calma! Aguarde mais {remaining}s antes de enviar outra mensagem para esse contato. "
                "(Isso evita envios acidentais em sequência)"
    )

# LINHA 73 - ANTES
if _last_sent_msg.get(phone) == message and time_diff < 300:
    return ToolResult(ok=False, message="ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos.")

# LINHA 73 - DEPOIS
if _last_sent_msg.get(phone) == message and time_diff < 300:
    elapsed_min = int(time_diff / 60)
    return ToolResult(
        ok=False,
        message=f"🔄 Hmm, parece que você enviou essa mesma mensagem para esse contato há {elapsed_min} minuto(s). "
                "Quer realmente enviar de novo? (Se sim, aguarde mais um pouco)"
    )
```

**Benefícios**:
- ✅ Tom amigável (emoji + linguagem natural)
- ✅ Feedback específico (quantos segundos faltam)
- ✅ Contexto claro (por que está bloqueando)

**Tempo**: 5 minutos

---

### 2. Tool Guardrails Humanizados

**Arquivo**: `app/agent/tool_guardrails.py`

**Problema**: Mensagens técnicas ("resultado sem progresso", "chamadas repetidas excessivas")

**Mudanças**:

```python
# LINHA 32 - ANTES
if count >= self.exact_repeat_limit:
    return ToolGuardrailDecision(False, f"Ferramenta bloqueada por chamadas repetidas excessivas: {tool_name}.")

# LINHA 32 - DEPOIS
if count >= self.exact_repeat_limit:
    return ToolGuardrailDecision(
        False, 
        f"⚠️ Percebi que tentei usar '{tool_name}' {count} vezes seguidas com os mesmos parâmetros "
        "sem sucesso. Vamos tentar uma abordagem diferente?"
    )

# LINHA 48 - ANTES
if count >= self.no_progress_limit and self._looks_no_progress(text):
    return ToolGuardrailDecision(False, f"Ferramenta interrompida por resultado sem progresso: {tool_name}.")

# LINHA 48 - DEPOIS
if count >= self.no_progress_limit and self._looks_no_progress(text):
    return ToolGuardrailDecision(
        False, 
        f"⚠️ A ferramenta '{tool_name}' está retornando resultados vazios ou repetidos. "
        "Isso geralmente significa que preciso de mais informações ou que algo não está configurado corretamente. "
        "Quer que eu tente outra forma de resolver isso?"
    )
```

**Benefícios**:
- ✅ Explica O QUE aconteceu em linguagem simples
- ✅ Explica POR QUE parou
- ✅ Sugere próximo passo

**Tempo**: 5 minutos

---

### 3. WhatsApp Error Messages com Sugestões

**Arquivo**: `app/agent/tools/whatsapp.py`

**Problema**: Erros dizem O QUE deu errado mas não COMO resolver

**Mudanças**:

```python
# LINHA ~58 (resolve_contact) - ANTES
if not phone:
    return ToolResult(
        ok=False,
        message=f"Não foi possível resolver o contato '{target}'. "
                f"Insira o número de telefone completo ou cadastre o contato em 'data/contatos.csv'."
    )

# LINHA ~58 - DEPOIS
if not phone:
    return ToolResult(
        ok=False,
        message=f"📱 Não encontrei o contato '{target}' na sua lista.\n\n"
                "Você pode:\n"
                "• Usar o número completo (exemplo: +5511999887766)\n"
                "• Ou cadastrar o contato no arquivo data/contatos.csv\n\n"
                "Quer que eu te ajude a cadastrar?"
    )

# LINHA ~96 (login required) - ANTES
if "login" in stderr or "login" in stdout:
    return ToolResult(
        ok=False,
        message="WhatsApp desconectado. Por favor, execute 'npx mudslide login' no terminal para parear o QR Code."
    )

# LINHA ~96 - DEPOIS
if "login" in stderr or "login" in stdout:
    return ToolResult(
        ok=False,
        message="📱 Seu WhatsApp Web precisa ser conectado novamente.\n\n"
                "Vou te guiar:\n"
                "1️⃣ Abra um terminal (Win+R → digite 'cmd' → Enter)\n"
                "2️⃣ Cole este comando: npx mudslide login\n"
                "3️⃣ Escaneie o QR Code com seu celular\n\n"
                "Depois disso, pode tentar enviar a mensagem novamente!",
        data={
            "quick_action": {
                "label": "📋 Copiar comando",
                "value": "npx mudslide login"
            }
        }
    )

# LINHA ~102 (mudslide not installed) - ANTES
else:
    return ToolResult(
        ok=False,
        message="Erro ao enviar mensagem. Verifique se o Mudslide está instalado: npm install -g mudslide"
    )

# LINHA ~102 - DEPOIS
else:
    error_detail = result.stderr[:200] if result.stderr else "Erro desconhecido"
    return ToolResult(
        ok=False,
        message=f"❌ Não consegui enviar a mensagem. O erro foi:\n{error_detail}\n\n"
                "Possíveis causas:\n"
                "• Mudslide não está instalado (execute: npm install -g mudslide)\n"
                "• WhatsApp Web desconectado (execute: npx mudslide login)\n"
                "• Problema de conexão com a internet\n\n"
                "Quer que eu tente diagnosticar o problema?"
    )
```

**Benefícios**:
- ✅ Passo-a-passo claro
- ✅ Múltiplas soluções possíveis
- ✅ Ação rápida (copiar comando)
- ✅ Oferece ajuda adicional

**Tempo**: 30 minutos

---

### 4. Wait Tool com Countdown Visual

**Arquivo**: `app/agent/tools/wait.py`

**Problema**: Esperas longas (>5s) congelam sem feedback, usuário fica ansioso

**Mudanças**:

```python
# Adicionar imports
from app.agent.run_tracking import record_run_step
from app.core.runs import check_run_cancelled, RunCancelled

# Método execute - DEPOIS
def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
    seconds = args.get("seconds", 0)
    
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return ToolResult(ok=False, message="Tempo de espera inválido. Use um número positivo de segundos.")
    
    if seconds > 3600:
        return ToolResult(ok=False, message="Tempo de espera muito longo (máximo: 1 hora).")
    
    # Para esperas curtas (<5s), apenas aguarda
    if seconds < 5:
        time.sleep(seconds)
        return ToolResult(ok=True, message=f"⏱️ Aguardei {seconds:.0f}s.")
    
    # Para esperas longas, mostra countdown
    record_run_step(f"⏳ Aguardando {seconds:.0f}s...", kind="step")
    
    # Countdown em chunks de 1s, com cancelamento suportado
    elapsed = 0
    update_interval = 5  # Atualiza UI a cada 5s
    
    try:
        while elapsed < seconds:
            check_run_cancelled()  # Permite cancelamento via Ctrl+C
            
            remaining = seconds - elapsed
            
            # Atualiza UI a cada 5s ou nos últimos 3s
            if elapsed % update_interval == 0 or remaining <= 3:
                if remaining > 3:
                    record_run_step(f"⏳ Aguardando... {remaining:.0f}s restantes", kind="step")
                else:
                    record_run_step(f"⏳ Quase lá... {remaining:.0f}s", kind="step")
            
            time.sleep(1)
            elapsed += 1
        
        return ToolResult(ok=True, message="✅ Espera concluída!")
        
    except RunCancelled:
        return ToolResult(
            ok=False, 
            message=f"⏸️ Espera cancelada após {elapsed:.0f}s de {seconds:.0f}s."
        )
```

**Benefícios**:
- ✅ Feedback visual contínuo
- ✅ Usuário sabe quanto falta
- ✅ Suporta cancelamento (Ctrl+C)
- ✅ Mensagens contextuais ("Quase lá..." nos últimos 3s)

**Tempo**: 15 minutos

---

### 5. Rate Limit Messages Humanizados

**Arquivo**: `app/services/llm.py` (classe KeyRotator)

**Problema**: Mensagens técnicas sobre "429", "chaves em cooldown", etc.

**Mudanças**:

```python
# Método wait_message (linha ~115) - ANTES
def wait_message(self, provider: str, settings: Any, *, user_facing: bool = False) -> str:
    import math
    keys = self._cleaned_keys(provider, settings)
    blocked = [k for k in keys if self.cooldowns.get(k, 0) > time.time()]
    seconds = max(1, math.ceil(min((self.cooldowns[k] for k in blocked), default=time.time()) - time.time()))
    reason = self.reasons.get(min(blocked, key=lambda k: self.cooldowns[k]), 'limite temporário de uso') if blocked else 'limite temporário de uso'
    if user_facing:
        if seconds <= 15:
            return "Estou um pouco sobrecarregado no momento. Tente novamente em alguns segundos."
        return f"O serviço atingiu um {reason}. Tente novamente em cerca de {seconds} segundos."
    return f"{provider.capitalize()}: {reason} (429). {len(blocked)} de {len(keys)} chaves em espera. Próxima tentativa em cerca de {seconds} segundos. As chaves continuam configuradas."

# Método wait_message - DEPOIS
def wait_message(self, provider: str, settings: Any, *, user_facing: bool = False) -> str:
    import math
    keys = self._cleaned_keys(provider, settings)
    blocked = [k for k in keys if self.cooldowns.get(k, 0) > time.time()]
    seconds = max(1, math.ceil(min((self.cooldowns[k] for k in blocked), default=time.time()) - time.time()))
    
    if user_facing:
        if seconds <= 15:
            return "⏱️ Estou processando muitas solicitações ao mesmo tempo. " \
                   "Vou me liberar em alguns segundos!"
        elif seconds <= 60:
            return f"⏱️ Preciso de uma pausa rápida de ~{seconds}s para recuperar acesso ao serviço de IA. " \
                   "Isso é normal quando há muito uso simultâneo. Aguarde um momentinho!"
        else:
            minutes = math.ceil(seconds / 60)
            return f"⏱️ O serviço de IA está com alta demanda. Vou precisar de ~{minutes} minuto(s) " \
                   "para recuperar acesso. Enquanto isso, você pode continuar navegando ou tentar outro comando!"
    
    # Mensagem técnica para logs
    reason = self.reasons.get(min(blocked, key=lambda k: self.cooldowns[k]), 'rate limit') if blocked else 'rate limit'
    return f"[{provider.capitalize()}] {len(blocked)}/{len(keys)} chaves em cooldown. " \
           f"Retry em ~{seconds}s. Motivo: {reason}"
```

**Mudanças adicionais em `_recover_synthesis()` (linha ~1420)**:

```python
# Logging durante backoff - DEPOIS
for attempt in range(max_attempts):
    # ... código existente ...
    
    if attempt < max_attempts - 1:
        min_cooldown = _key_rotator.min_cooldown_remaining("groq", self.settings)
        
        if 0 < min_cooldown <= max_wait_threshold:
            wait_time = min(min_cooldown + 0.5, 2 ** (attempt + 1))
            
            # MUDANÇA: Log mais amigável
            record_run_step(
                f"⏳ Aguardando {wait_time:.0f}s para próxima tentativa de síntese... "
                f"(tentativa {attempt + 1}/{max_attempts})",
                kind="step"
            )
            
            time.sleep(wait_time)
        else:
            if min_cooldown == float('inf'):
                msg = "❌ Nenhuma chave de API disponível no momento."
            else:
                msg = f"⏸️ Tempo de espera muito longo ({min_cooldown:.0f}s). Interrompendo tentativas."
            
            _log(f"[LLM] {msg}")
            break
```

**Benefícios**:
- ✅ Linguagem natural (sem "429", sem "chaves em cooldown")
- ✅ Tom empático ("Preciso de uma pausa")
- ✅ Contexto claro ("alta demanda", "uso simultâneo")
- ✅ Sugestões de ação ("você pode continuar navegando")
- ✅ Diferenciação por gravidade (<15s vs <60s vs >60s)

**Tempo**: 30 minutos

---

## 📊 Verificação

### Compilação
```bash
python -m py_compile app/agent/tools/whatsapp.py
python -m py_compile app/agent/tool_guardrails.py
python -m py_compile app/agent/tools/wait.py
python -m py_compile app/services/llm.py
```

### Testes Manuais

**Teste 1 - Anti-Spam**:
1. Enviar mensagem WhatsApp
2. Tentar enviar novamente imediatamente
3. Verificar: mensagem amigável com countdown?

**Teste 2 - Guardrails**:
1. Forçar loop com tool repetindo 3x
2. Verificar: mensagem humanizada?

**Teste 3 - Wait Countdown**:
1. `wait(seconds=20)`
2. Verificar: countdown visível a cada 5s?

**Teste 4 - Rate Limit**:
1. Esgotar todas as chaves (forçar 429)
2. Verificar: mensagem amigável sem termos técnicos?

---

## 🎯 Impacto Esperado

**Antes do SPRINT 3**:
```
Usuário: "Jarvis, envia mensagem pro João"
Jarvis: "ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número."
Usuário: 😨 "Por que o Jarvis tá gritando comigo??"
```

**Depois do SPRINT 3**:
```
Usuário: "Jarvis, envia mensagem pro João"
Jarvis: "⏱️ Vamos com calma! Aguarde mais 8s antes de enviar outra mensagem para esse contato. (Isso evita envios acidentais em sequência)"
Usuário: 😊 "Ah, faz sentido! Obrigada por cuidar disso"
```

**Mudança de percepção**:
- ❌ "O Jarvis é agressivo e técnico"
- ✅ "O Jarvis é prestativo e me explica as coisas"

---

## 🚀 Implementação

**Ordem sugerida**:
1. WhatsApp anti-spam (5min) — maior ROI
2. Guardrails (5min) — maior ROI
3. Rate limit messages (30min) — impacto frequente
4. Error messages (30min) — melhora recovery
5. Wait countdown (15min) — polimento

**Total**: ~1h 25min

**Entrega**: Branch `sprint3-ux-quick-wins` pronto para merge

---

## 📝 Guia de Estilo Emergente

Baseado nas mudanças, cristalizando o tom de voz do Jarvis:

### ✅ Fazer
- Usar emojis contextuais (⏱️, 🔄, ✅, ❌, 📱)
- Explicar o PORQUÊ, não só o QUE
- Oferecer próximos passos concretos
- Tom empático e prestativo
- Linguagem natural, casual mas respeitosa

### ❌ Evitar
- MAIÚSCULAS agressivas
- Termos técnicos (429, rate limit, cooldown, anti-spam)
- Jargão de desenvolvedor
- Mensagens que só dizem "não" sem alternativa
- Tom de repreensão

### 💬 Exemplos

**Erro genérico**:
- ❌ "Error: Operation failed"
- ✅ "❌ Ops, algo deu errado. Quer que eu tente de novo?"

**Espera**:
- ❌ "Processing..."
- ✅ "⏳ Aguardando... 15s restantes"

**Limite atingido**:
- ❌ "RATE_LIMIT_EXCEEDED"
- ✅ "⏱️ Estou com muito trabalho no momento. Vou me liberar em alguns segundos!"

**Confirmação**:
- ❌ "Action completed successfully"
- ✅ "✅ Pronto! Mensagem enviada com sucesso"

---

**Status**: Plano pronto para implementação. Aguardando aprovação ou início imediato.
