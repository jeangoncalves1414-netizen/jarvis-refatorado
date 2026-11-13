## Finding 1: Mensagens Técnicas Anti-Spam Expostas ao Usuário

**Categoria**: UX
**Prioridade**: 🟡 IMPORTANTE

### Problema Atual
O arquivo `app/agent/tools/whatsapp.py` expõe mensagens técnicas de engenharia diretamente ao usuário:
- Linha 70: `"ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número."`
- Linha 72: `"ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos."`

Essas mensagens usam terminologia de debug/engenharia (`ANTI-SPAM`, `ANTI-LOOP`) que quebram a imersão e confundem usuários leigos.

### Impacto no Usuário
- **Quebra de imersão**: O usuário vê termos técnicos de sistema de controle interno
- **Confusão**: Usuário leigo não entende por que o sistema está "anti" alguma coisa
- **Percepção de erro**: Prefixos em maiúsculas como "ANTI-" parecem mensagens de erro graves

### Proposta de Solução
Reescrever as mensagens em linguagem natural, mantendo a função de rate limiting mas humanizando o texto:

```python
# Antes (linha 70)
return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")

# Depois
return ToolResult(ok=False, message="Por favor, aguarde um momento antes de enviar outra mensagem para este contato.")

# Antes (linha 72)
return ToolResult(ok=False, message="ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos.")

# Depois
return ToolResult(ok=False, message="Você já enviou esta mensagem recentemente para este contato. Deseja enviar mesmo assim?")
```

### Implementação Estimada
**Simples** — 0.5 horas

### Arquivos Envolvidos
- `app/agent/tools/whatsapp.py` (linhas 70, 72)

### Exemplo de Código
```python
# Linha 70-71
if time_diff < 10:
    return ToolResult(ok=False, message="Por favor, aguarde um momento antes de enviar outra mensagem para este contato.")

# Linha 72-73
if _last_sent_msg.get(phone) == message and time_diff < 300:
    return ToolResult(ok=False, message="Você já enviou esta mensagem recentemente para este contato.")
```
