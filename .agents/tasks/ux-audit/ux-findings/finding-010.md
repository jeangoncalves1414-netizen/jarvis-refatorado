## Finding 10: Inconsistência de Linguagem em Mensagens de Status

**Categoria**: UX
**Prioridade**: 🟢 NICE-TO-HAVE

### Problema Atual
Análise de mensagens ao usuário em diversos arquivos revela **inconsistência de tom e formalidade**:

**Formal/Técnico**:
- `app/services/llm.py` linha 118: `"Estou um pouco sobrecarregado no momento."`
- `app/storage/action_store.py` linha 228: `"Aguardando sua aprovação"`

**Casual/Coloquial**:
- `app/agent/react_loop.py` linha 37: `"A etapa {n} precisa da sua aprovação na Central"`

**Misto**:
- Algumas mensagens usam "você", outras usam "usuária", outras não usam pronome
- Algumas têm emojis (⏰, ⚠️), outras não

### Impacto no Usuário
- **Percepção de inconsistência**: Sistema parece ter "múltiplas personalidades"
- **Confusão leve**: Mudança de tom entre mensagens pode parecer que são sistemas diferentes
- **Profissionalismo**: Inconsistência pode parecer falta de polimento/cuidado

### Proposta de Solução
Criar **guia de tom e voz** e padronizar todas as mensagens:

**Tom recomendado**: Profissional, mas acessível e empático
- Usar "você" consistentemente
- Tom de assistente confiável, não robô formal nem amigo casual
- Emojis apenas em contextos de sucesso/celebração ou alertas críticos

**Exemplos**:
- ✅ "Estou um pouco sobrecarregado. Tente novamente em alguns segundos."
- ✅ "Aguardando sua aprovação na Central de Atividades"
- ✅ "⏰ Timer disparado: {label}"
- ❌ "Estou meio ocupadão agora rsrs" (muito casual)
- ❌ "ERRO: RATE_LIMIT_EXCEEDED" (muito técnico)

### Implementação Estimada
**Complexa** — 4 horas (auditoria completa + rewrites)

### Arquivos Envolvidos
- Todos os arquivos que retornam `ToolResult` em `app/agent/tools/`
- `app/services/llm.py` (mensagens de erro)
- `app/agent/orchestrator.py` (mensagens de status)
- `app/storage/action_store.py` (mensagens de confirmação)
- Criar `app/core/messages.py` com constantes de mensagens padronizadas

### Exemplo de Código
```python
# NOVO: app/core/messages.py
"""Mensagens padronizadas user-facing com tom consistente."""

# Rate limiting
RATE_LIMIT_SHORT = "Estou um pouco ocupado. Tente novamente em alguns segundos."
RATE_LIMIT_LONG = "Atingi o limite de uso temporário. Tente novamente em cerca de {seconds} segundos."

# Confirmações
AWAITING_APPROVAL = "Aguardando sua aprovação na Central de Atividades"
APPROVAL_TIMEOUT = "A confirmação expirou. A operação foi cancelada."

# Timer
TIMER_CREATED = "Timer criado: '{label}' para {time}"
TIMER_FIRED = "⏰ Timer disparado: {label}"
TIMER_CANCELLED = "Timer '{label}' cancelado"

# Erros genéricos
SERVICE_UNAVAILABLE = "Não foi possível conectar ao serviço. Verifique sua conexão."
CONFIG_ERROR = "Há um problema na configuração. Por favor, verifique as configurações."

# Sucesso
OPERATION_COMPLETE = "Pronto! {detail}"
```

```python
# Uso nos arquivos
from app.core.messages import RATE_LIMIT_SHORT, TIMER_CREATED

# Antes
return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos")

# Depois
return ToolResult(ok=False, message=RATE_LIMIT_SHORT)

# Antes
return ToolResult(ok=True, message=f"Timer [{timer_id}] criado com sucesso: '{desc}'...")

# Depois
return ToolResult(ok=True, message=TIMER_CREATED.format(label=desc, time=fire_at.strftime('%H:%M')))
```
