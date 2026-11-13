# Friction Points — Consolidação de Achados UX

**Data**: 2025-01-XX  
**Fonte**: Auditoria UX/DX Jarvis  
**Findings relacionados**: 1, 2, 3, 5, 6, 7, 8, 9, 10

---

## Definição

**Friction points** são momentos na experiência do usuário onde há resistência, confusão, espera inesperada, ou quebra de fluxo que impede o usuário de completar sua tarefa de forma fluida.

---

## Mapa de Friction Points Identificados

### 1. Sistema Parece Travado Durante Operações Longas

**Severity**: 🔴 CRÍTICO

**Manifestações**:
- **Spotify**: Usuário pede "toca Bohemian Rhapsody" → 10 segundos de silêncio → música finalmente toca
- **Rate Limiting**: Durante pico de uso, UI congela por 10-30s sem qualquer indicação
- **Phantom Typer**: Delay de 0.5s antes de digitar parece lento sem feedback

**Arquivos afetados**:
- `app/agent/tools/spotify.py` (linhas 164-188)
- `app/core/rate_limit.py` (linha 27)
- `app/agent/tools/phantom_typer.py` (linhas 32, 42)

**Por que é friction**:
- Usuário não sabe se sistema está processando ou travou
- Sem feedback, usuário tende a clicar novamente, causando loops
- Ansiedade e frustração durante espera silenciosa
- Percepção de lentidão mesmo quando operação é tecnicamente aceitável

**Como remover**:
1. Adicionar mensagens de status durante sleeps: "Abrindo Spotify...", "Buscando música..."
2. Mostrar spinner ou progress indicator na UI
3. Permitir cancelamento durante operações longas
4. Feedback audível leve (tom curto) ao iniciar operação longa

**Prioridade**: P0 (resolver imediatamente)

---

### 2. Confirmações Críticas Sem Contexto de Tempo

**Severity**: 🟡 IMPORTANTE

**Manifestações**:
- Usuário aprova ação destrutiva (ex: deletar arquivo)
- Sistema aguarda aprovação com mensagem "Aguardando sua aprovação"
- **Não há countdown visual** mostrando que tem apenas 5 minutos
- Após 5 min, confirmação expira silenciosamente
- Usuário retorna e não entende por que a ação foi cancelada

**Arquivos afetados**:
- `app/core/critical_confirm.py` (linhas 49-52)
- `app/ui/panel/templates/index.html` (ausência de modal de confirmação)

**Por que é friction**:
- Perda de contexto após timeout longo
- Frustração ao descobrir que operação foi cancelada
- Retrabalho: usuário precisa reiniciar operação do zero
- Falta de senso de urgência sem countdown

**Como remover**:
1. Adicionar barra de progresso/countdown no modal de confirmação
2. Avisos aos 60s e 10s antes de expirar
3. Mensagem clara quando timeout ocorre: "Confirmação expirada. Operação cancelada."
4. Permitir extensão do timeout com um clique

**Prioridade**: P1 (resolver em Sprint 2)

---

### 3. Timer Sem Confirmação de Sucesso

**Severity**: 🟡 IMPORTANTE

**Manifestações**:
- Usuário diz "timer de 5 minutos"
- Sistema responde "Timer criado"
- Após 5 minutos, **usuário não tem certeza se o áudio tocou**
- Se som estiver mutado ou sem alto-falante, falha silenciosa

**Arquivos afetados**:
- `app/agent/tools/timer.py` (linhas 90-127)

**Por que é friction**:
- Falta de confiança no sistema
- Usuário precisa testar timers curtos para verificar se funciona
- Perda de compromissos em falhas silenciosas
- Sem feedback de confirmação audível/visual

**Como remover**:
1. Notificação visual no painel quando timer dispara
2. Fallback para Windows Notification se `winsound.Beep` falhar
3. Log na Central de Atividades com status (sucesso/falha áudio)
4. Permitir teste de áudio nas configurações

**Prioridade**: P1 (resolver em Sprint 2)

---

### 4. Novos Usuários Sem Orientação

**Severity**: 🟡 IMPORTANTE

**Manifestações**:
- Usuário abre Jarvis pela primeira vez
- Vê tela vazia com orb visual e campo de input
- **Não há exemplos, tooltips, ou sugestões**
- Usuário não sabe o que o sistema pode fazer
- Abandona sem explorar funcionalidades

**Arquivos afetados**:
- `app/ui/panel/templates/index.html` (ausência de welcome screen)

**Por que é friction**:
- Curva de aprendizado íngreme sem orientação
- Funcionalidades avançadas (vision, checklist, timer) permanecem ocultas
- Taxa de abandono alta para novos usuários
- Necessidade de documentação externa (wiki, vídeos)

**Como remover**:
1. Welcome screen na primeira inicialização com 5-7 comandos exemplo
2. Seção de "Sugestões" quando chat está vazio
3. Tooltips contextuais ao passar mouse sobre elementos
4. Tour interativo opcional (3-4 passos) mostrando funcionalidades principais

**Prioridade**: P2 (resolver em Sprint 3)

---

### 5. Mensagens Técnicas Quebram Imersão

**Severity**: 🟡 IMPORTANTE

**Manifestações**:
- Usuário tenta enviar mensagem WhatsApp rapidamente
- Sistema retorna: **"ANTI-SPAM: Aguarde 10 segundos"**
- Usuário vê termos de engenharia/debug
- Percepção de erro grave ao invés de rate limiting normal

**Arquivos afetados**:
- `app/agent/tools/whatsapp.py` (linhas 70, 72)
- `app/services/llm.py` (múltiplas linhas com mensagens técnicas)

**Exemplos de mensagens problemáticas**:
- "ANTI-SPAM: Aguarde 10 segundos"
- "ANTI-LOOP: Mensagem duplicada detectada"
- "Verifique a GEMINI_API_KEY no .env"
- "AWAITING_CONFIRMATION"

**Por que é friction**:
- Linguagem de engenharia confunde usuários leigos
- Quebra a imersão de conversa natural com assistente
- Prefixos em maiúsculas parecem erros graves
- Exposição de detalhes de implementação (variáveis, arquivos config)

**Como remover**:
1. Reescrever todas as mensagens em linguagem natural
2. Criar guia de tom e voz (profissional mas acessível)
3. Separar mensagens de log (detalhadas) vs UI (genéricas)
4. Usar `app/core/messages.py` centralizado para consistência

**Prioridade**: P0-P1 (Finding 1 é P0; Finding 3 e 10 são P1)

---

### 6. Rate Limiting Falha Desnecessariamente

**Severity**: 🟡 IMPORTANTE

**Manifestações**:
- Usuário faz pergunta durante horário de pico
- Todas as chaves de API entram em rate limit (429)
- Uma chave tem cooldown de apenas 8 segundos restantes
- Sistema retorna "Estou sobrecarregado" ao invés de esperar 8s
- Usuário recebe erro evitável

**Arquivos afetados**:
- `app/services/llm.py` (linhas 1339-1437)

**Por que é friction**:
- Falhas desnecessárias quando solução está a poucos segundos
- Usuário precisa repetir pergunta manualmente após curto período
- Degradação de experiência em horários de pico
- Sistema parece menos confiável do que realmente é

**Como remover**:
1. Implementar retry mais persistente para cooldowns < 30s
2. Mostrar mensagem "Aguardando serviço disponível (Xs)..." durante espera
3. Usar todas as chaves disponíveis antes de desistir
4. Fallback cross-provider mais agressivo (Groq → Gemini → Oxyy)

**Prioridade**: P1 (resolver em Sprint 2)

---

### 7. Wake Word com Latência Perceptível

**Severity**: 🟢 NICE-TO-HAVE

**Manifestações**:
- Usuário diz "Jarvis"
- Sistema demora 0.2-0.5s para responder
- Latência perceptível quebra naturalidade da conversa

**Arquivos afetados**:
- `app/services/voice/wake_word.py` (linhas 209, 217, 220)

**Por que é friction**:
- Polling com sleeps introduz atraso artificial
- CPU desperdiçado com polling constante
- Bateria reduzida em laptops
- Conversa parece menos natural

**Como remover**:
1. Substituir polling por sistema event-driven com callbacks
2. Se polling necessário, reduzir sleep para < 50ms
3. Usar threading.Event ao invés de time.sleep
4. Processar audio stream com callback interno

**Prioridade**: P2 (resolver em Sprint 2-3)

---

### 8. Inconsistência de Linguagem Entre Mensagens

**Severity**: 🟢 NICE-TO-HAVE

**Manifestações**:
- Mensagem A: "Estou um pouco sobrecarregado no momento." (formal)
- Mensagem B: "A etapa {n} precisa da sua aprovação na Central" (casual)
- Algumas mensagens usam emojis, outras não
- Usuário percebe "múltiplas personalidades" do sistema

**Arquivos afetados**:
- `app/services/llm.py`, `app/storage/action_store.py`, `app/agent/react_loop.py`, múltiplas ferramentas

**Por que é friction**:
- Percepção de inconsistência e falta de polimento
- Sistema parece ter sido feito por equipes diferentes
- Confusão leve ao mudar de tom entre mensagens
- Profissionalismo questionado

**Como remover**:
1. Criar guia de tom e voz (profissional, acessível, empático)
2. Auditar todas as strings user-facing
3. Centralizar mensagens em `app/core/messages.py`
4. Usar "você" consistentemente; emojis apenas em sucesso/alertas críticos

**Prioridade**: P2 (resolver em Sprint 3)

---

## Resumo: Top 3 Friction Points Críticos

1. **Sistema parece travado durante operações longas** (Finding 2, 7)  
   → Adicionar feedback visual imediato

2. **Mensagens técnicas quebram imersão** (Finding 1, 3)  
   → Humanizar linguagem user-facing

3. **Rate limiting falha desnecessariamente** (Finding 4)  
   → Retry mais persistente com cooldown < 30s

---

## Métricas de Sucesso

Após remover friction points, espera-se:

- **Tempo de tarefa reduzido em 20-30%** (menos retrabalho por falhas evitáveis)
- **Taxa de abandono de novos usuários reduzida em 40%** (onboarding + feedback claro)
- **Percepção de responsividade melhorada** (medida via survey NPS/CSAT)
- **Redução de 60% em perguntas de suporte** sobre "sistema travou" ou "não sei o que fazer"
