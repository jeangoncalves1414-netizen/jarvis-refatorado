## Finding 2: Operações Longas do Spotify Sem Feedback Visual

**Categoria**: UX
**Prioridade**: 🔴 CRÍTICO

### Problema Atual
O arquivo `app/agent/tools/spotify.py` contém múltiplos `time.sleep` bloqueantes durante a operação `search_play`:
- Linha 165: `time.sleep(2.0)` — aguarda Spotify abrir
- Linha 175: `time.sleep(5.0 if not was_running else 2.5)` — aguarda renderização da busca
- Linha 178: `time.sleep(1.5)` — aguarda foco na janela
- Linhas 181, 183, 185: `time.sleep(0.2)`, `time.sleep(0.2)`, `time.sleep(1.0)` — navegação por teclado

**Total: até 10 segundos de espera silenciosa** sem qualquer feedback ao usuário.

### Impacto no Usuário
- **Percepção de travamento**: O usuário vê o agente "congelado" por 10+ segundos
- **Ansiedade**: Sem feedback, o usuário não sabe se o sistema está funcionando ou travou
- **Experiência degradada**: Operação simples ("toca música X") parece lenta e não responsiva
- **Potencial cancelamento**: Usuário pode fechar/cancelar achando que o sistema travou

### Proposta de Solução
Adicionar mensagens de status intermediárias durante as esperas longas:

1. Antes de abrir o Spotify: "Abrindo Spotify..."
2. Durante renderização da busca: "Buscando '{query}' no Spotify..."
3. Durante navegação: "Selecionando primeira música..."

Implementar via callback de progresso ou sistema de eventos para atualizar a UI.

### Implementação Estimada
**Média** — 2 horas

### Arquivos Envolvidos
- `app/agent/tools/spotify.py` (linhas 164-188)
- `app/agent/tool_activity.py` (para gerar labels de progresso)
- Sistema de callback de status (pode precisar criar)

### Exemplo de Código
```python
# Antes (linha 164-165)
if not was_running:
    _open_spotify()
    time.sleep(2.0)

# Depois
if not was_running:
    if context and context.get("on_progress"):
        context["on_progress"]("Abrindo Spotify...")
    _open_spotify()
    time.sleep(2.0)

# Linha 175-176
if context and context.get("on_progress"):
    context["on_progress"](f"Buscando '{query}' no Spotify...")
time.sleep(5.0 if not was_running else 2.5)

# Linha 178-179
if _focus_spotify():
    if context and context.get("on_progress"):
        context["on_progress"]("Selecionando música...")
    time.sleep(1.5)
```
