# Error Messages — Consolidação de Achados

**Data**: 2025-01-XX  
**Fonte**: Auditoria UX/DX Jarvis  
**Findings relacionados**: 1, 3, 10

---

## Problema Sistêmico

Mensagens de erro no Jarvis variam entre **linguagem técnica de engenharia** e **linguagem natural**, sem padrão consistente. Algumas mensagens expõem detalhes de implementação (variáveis de ambiente, nomes de arquivo, status codes) que confundem usuários leigos.

---

## Categorias de Problemas

### 1. Termos de Engenharia/Debug Expostos ao Usuário

#### 🔴 Problema: Prefixos Técnicos

**Arquivo**: `app/agent/tools/whatsapp.py` (linhas 70, 72)

```python
# ❌ Antes
return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")
return ToolResult(ok=False, message="ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos.")
```

**Problemas**:
- Prefixos em maiúsculas ("ANTI-SPAM", "ANTI-LOOP") parecem erros graves
- Terminologia de sistema de controle interno, não de conversa natural
- Usuário leigo não entende o que "ANTI-" significa

**✅ Solução**:
```python
# Opção 1: Simples e direta
return ToolResult(ok=False, message="Por favor, aguarde um momento antes de enviar outra mensagem para este contato.")

# Opção 2: Mais específica
return ToolResult(ok=False, message="Para evitar envios duplicados, aguarde 10 segundos antes de enviar outra mensagem.")

# Linha 72 - Mensagem duplicada
return ToolResult(ok=False, message="Você já enviou esta mensagem recentemente para este contato.")
```

---

### 2. Exposição de Detalhes de Configuração

#### 🔴 Problema: Variáveis de Ambiente e Arquivos .env

**Arquivo**: `app/services/llm.py` (múltiplas linhas)

```python
# ❌ Antes (linha 640)
raise ValueError("Erro de autenticação com a API Gemini. Verifique a GEMINI_API_KEY no .env.")

# ❌ Antes (linha 644)
raise ValueError(f"Modelo '{model}' não encontrado. Verifique GEMINI_MODEL no .env.")

# ❌ Antes (linha 196-197)
return ProviderErrorText(f"Chave GROQ_API_KEY não encontrada no .env. Configure-a para conversar com o Jarvis.")
```

**Problemas**:
- Menções a `.env`, `GEMINI_API_KEY`, `GROQ_API_KEY` incompreensíveis para usuários finais
- Usuário não sabe o que é "variável de ambiente" ou onde encontrar arquivo `.env`
- Possível vulnerabilidade leve de segurança (expor nomes de variáveis)
- Quebra a abstração entre usuário e desenvolvedor

**✅ Solução**:
```python
# Para LOG (desenvolvedor) - detalhado
logger.error("Autenticação Gemini falhou: GEMINI_API_KEY inválida ou ausente no .env")

# Para USUÁRIO - genérico e acionável
raise ValueError("Não foi possível conectar ao serviço de IA. Verifique as configurações em Preferências > Credenciais.")

# Linha 644
logger.error(f"Modelo '{model}' não encontrado. Verifique GEMINI_MODEL no .env.")
raise ValueError("O modelo de IA configurado não está disponível. Por favor, verifique as configurações.")

# Linha 196-197
logger.warning("GROQ_API_KEY não configurada no .env")
return ProviderErrorText("Serviço de IA não está configurado. Acesse Configurações > Credenciais para configurar.")
```

---

### 3. Status Codes e Mensagens HTTP Expostas

#### 🟡 Problema: Status Técnicos em Mensagens User-Facing

**Arquivo**: `app/core/capability_health.py` (linhas 57-68)

Este arquivo já faz **tradução parcial** de status HTTP para mensagens amigáveis:

```python
# ✅ BOM: Tradução de status HTTP
429 → "Limite de uso do provedor"
401/403 → "Chave recusada pelo provedor"
Timeout → "O provedor não respondeu a tempo"
```

Mas ainda há casos onde status brutos são mostrados:

```python
# ❌ Problema em outros arquivos
f"Erro HTTP {status_code}: {error_message}"
```

**✅ Solução**:
Sempre passar por `capability_health.py` ou camada de tradução antes de mostrar ao usuário.

---

### 4. Inconsistência de Tom e Formalidade

#### 🟢 Problema: Variação de Estilo Entre Mensagens

**Exemplos de inconsistência**:

```python
# Formal
"Estou um pouco sobrecarregado no momento."
"Aguardando sua aprovação"

# Casual
"A etapa {n} precisa da sua aprovação na Central"

# Técnico
"Modelo 'X' não encontrado. Verifique GEMINI_MODEL no .env."

# Natural
"Por favor, aguarde um momento..."
```

**Problema**: Sistema parece ter múltiplas personalidades; confunde usuário sobre nível de formalidade esperado.

---

## Guia de Boas Práticas: Mensagens de Erro

### Tom Recomendado

**Profissional, mas acessível e empático**
- Assistente confiável, não robô formal nem amigo casual
- Usar "você" consistentemente
- Evitar jargão técnico (API, .env, variáveis, status codes)
- Ser específico e acionável quando possível

### Template de Mensagens de Erro

```
[O QUE ACONTECEU] + [POR QUE] + [AÇÃO SUGERIDA]
```

**Exemplos**:

```python
# ✅ BOM
"Não foi possível enviar a mensagem. O WhatsApp não está conectado. Abra o WhatsApp Web e tente novamente."

# ✅ BOM
"Serviço de IA está temporariamente sobrecarregado. Tente novamente em cerca de 15 segundos."

# ✅ BOM
"Timer não pôde disparar porque o áudio está mutado. Verifique o volume do sistema."

# ❌ RUIM
"ANTI-SPAM: Aguarde 10 segundos"

# ❌ RUIM
"Erro 429: Rate limit exceeded"

# ❌ RUIM
"Verifique a GROQ_API_KEY no .env"
```

### Quando Usar Detalhes Técnicos

**Logs/Console (desenvolvedor)**: Sempre detalhado
```python
logger.error("WhatsApp rate limit: last_sent 3s ago, threshold 10s")
logger.warning("GEMINI_API_KEY not found in .env")
logger.error(f"HTTP 429: {response.headers.get('retry-after')}")
```

**UI/Mensagens (usuário)**: Sempre genérico e acionável
```python
return ToolResult(ok=False, message="Aguarde um momento antes de enviar outra mensagem.")
```

---

## Centralização: `app/core/messages.py`

### Proposta de Implementação

Criar módulo centralizado com todas as mensagens user-facing:

```python
"""
app/core/messages.py

Mensagens padronizadas user-facing com tom consistente.
Todas as strings exibidas ao usuário devem vir daqui.
"""

# ========== RATE LIMITING ==========
RATE_LIMIT_SHORT = "Estou um pouco ocupado. Tente novamente em alguns segundos."
RATE_LIMIT_LONG = "Atingi o limite de uso temporário. Tente novamente em cerca de {seconds} segundos."
RATE_LIMIT_WAITING = "Aguardando serviço disponível ({seconds}s)..."

# ========== WHATSAPP ==========
WHATSAPP_RATE_LIMIT = "Por favor, aguarde um momento antes de enviar outra mensagem para este contato."
WHATSAPP_DUPLICATE = "Você já enviou esta mensagem recentemente para este contato."
WHATSAPP_NOT_CONNECTED = "WhatsApp não está conectado. Abra o WhatsApp Web e tente novamente."

# ========== TIMER ==========
TIMER_CREATED = "Timer criado: '{label}' para {time}"
TIMER_FIRED = "⏰ Timer disparado: {label}"
TIMER_CANCELLED = "Timer '{label}' cancelado"
TIMER_AUDIO_FAILED = "Timer disparou, mas o áudio não pôde tocar. Verifique o volume do sistema."

# ========== CONFIRMAÇÕES ==========
AWAITING_APPROVAL = "Aguardando sua aprovação na Central de Atividades"
APPROVAL_TIMEOUT = "A confirmação expirou após 5 minutos. A operação foi cancelada."
APPROVAL_EXPIRES_SOON = "⚠️  Confirmação expira em {seconds} segundos"

# ========== SERVIÇOS (LLM, API) ==========
SERVICE_UNAVAILABLE = "Não foi possível conectar ao serviço de IA. Verifique sua conexão."
SERVICE_OVERLOADED = "Serviço de IA está temporariamente sobrecarregado. Tente novamente em alguns instantes."
SERVICE_AUTH_FAILED = "Falha na autenticação do serviço de IA. Verifique as credenciais em Configurações."
SERVICE_MODEL_NOT_FOUND = "O modelo de IA configurado não está disponível. Verifique as configurações."

# ========== ERROS GENÉRICOS ==========
CONFIG_ERROR = "Há um problema na configuração. Acesse Configurações para verificar."
OPERATION_CANCELLED = "Operação cancelada"
OPERATION_FAILED = "Não foi possível completar a operação. Tente novamente."

# ========== SUCESSO ==========
OPERATION_COMPLETE = "Pronto!"
OPERATION_COMPLETE_WITH_DETAIL = "Pronto! {detail}"
```

### Uso nos Arquivos

```python
# Antes
return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")

# Depois
from app.core.messages import WHATSAPP_RATE_LIMIT
return ToolResult(ok=False, message=WHATSAPP_RATE_LIMIT)

# Com interpolação
from app.core.messages import RATE_LIMIT_LONG
return ToolResult(ok=False, message=RATE_LIMIT_LONG.format(seconds=retry_after))
```

---

## Checklist de Implementação

### Sprint 1 (Imediato)
- [x] Identificar todas as mensagens técnicas user-facing
- [ ] Reescrever mensagens em `whatsapp.py` (Finding 1)
- [ ] Criar `app/core/messages.py` com constantes básicas
- [ ] Migrar mensagens de rate limiting para o módulo centralizado

### Sprint 2 (Médio Prazo)
- [ ] Separar logs (detalhados) de mensagens UI (genéricas) em `llm.py` (Finding 3)
- [ ] Adicionar flag `user_facing` em todas as mensagens de erro
- [ ] Auditar `app/agent/tools/` para mensagens técnicas restantes
- [ ] Documentar guia de tom e voz no README

### Sprint 3 (Longo Prazo)
- [ ] Auditar todas as strings user-facing no projeto (Finding 10)
- [ ] Padronizar uso de emojis (apenas sucesso/alertas críticos)
- [ ] Criar testes de regressão para mensagens (verificar que não há `.env`, `API_KEY`, etc em UI)
- [ ] Internacionalização (i18n) se necessário

---

## Métricas de Sucesso

Após padronização de mensagens de erro, espera-se:

- **Zero menções a variáveis de ambiente em UI**
- **Zero termos técnicos de engenharia em mensagens user-facing**
- **Redução de 40% em tickets de suporte** sobre "mensagem de erro incompreensível"
- **Aumento de 20% em satisfação NPS** (usuários entendem e confiam nas mensagens)
- **Consistência de tom em 100% das mensagens** (auditável via grep)
