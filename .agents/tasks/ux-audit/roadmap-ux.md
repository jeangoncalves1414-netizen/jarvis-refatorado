# Roadmap UX/DX — Jarvis

Este roadmap organiza as melhorias de experiência do usuário e desenvolvedor em 3 sprints progressivos, priorizando impacto e complexidade de implementação.

---

## Sprint 1 — Quick Wins (1–2 semanas)

### Objetivo
Eliminar os pontos de fricção mais visíveis com implementações rápidas e sem refatorações grandes.

### Itens

#### 1. Humanizar Mensagens Anti-Spam ✅
**Ref**: Finding 1  
**Tempo**: 0.5h  
**Arquivo**: `app/agent/tools/whatsapp.py`

Substituir "ANTI-SPAM" e "ANTI-LOOP" por linguagem natural.

**Critério de sucesso**: 
- Enviar mensagem duplicada retorna texto compreensível sem termos técnicos
- Zero menções a "ANTI-X" em mensagens user-facing

---

#### 2. Feedback Visual nas Operações do Spotify ✅
**Ref**: Finding 2 (🔴 CRÍTICO)  
**Tempo**: 1h  
**Arquivo**: `app/agent/tools/spotify.py`

Adicionar prints informativos durante os 10s de operação silenciosa.

**Critério de sucesso**:
- Comando "toca música X" exibe: "Abrindo Spotify...", "Buscando...", "Selecionando..."
- Usuário sempre sabe que sistema está trabalhando
- Tempo percebido de espera reduz em 50%

---

#### 3. Rate Limit Recovery Melhorado ✅
**Ref**: Finding 4  
**Tempo**: 1.5h  
**Arquivo**: `app/services/llm.py`

Aumentar persistência de retry para cooldowns < 30s com mensagem informativa.

**Critério de sucesso**:
- Rate limit com 8-15s restante não retorna erro imediato
- Mensagem "Aguardando Xs..." exibida ao usuário
- Taxa de erro "sobrecarregado" reduz em 60% em horários de pico

---

#### 4. Confirmação Visual de Timer ✅
**Ref**: Finding 5  
**Tempo**: 1h  
**Arquivo**: `app/agent/tools/timer.py`

Adicionar confirmação quando timer dispara, com fallback se áudio falhar.

**Critério de sucesso**:
- Timer disparado exibe "⏰ Timer disparado: {label}" no console
- Fallback visual destacado se `winsound.Beep` falhar
- Zero timers silenciosos

---

#### 5. Separar Mensagens Dev vs User ✅
**Ref**: Finding 3  
**Tempo**: 1.5h  
**Arquivo**: `app/services/llm.py`

Diferenciar mensagens técnicas (logs) de mensagens user-facing (UI).

**Critério de sucesso**:
- Erro de configuração não menciona ".env", variáveis de ambiente, ou chaves de API
- Logs técnicos preservam detalhes para debug
- 100% das mensagens de erro são compreensíveis para leigos

---

### Resultados Esperados do Sprint 1

✅ **5 melhorias implementadas**  
⏱️ **~5.5 horas de desenvolvimento**  
🎯 **Principais problemas de UX resolvidos**:
- Sistema nunca parece travado (feedback em operações longas)
- Mensagens sempre compreensíveis (zero jargão técnico)
- Menos falhas desnecessárias (retry melhorado)

---

## Sprint 2 — Melhorias Significativas (3–4 semanas)

### Objetivo
Resolver problemas estruturais que requerem refatoração moderada e afetam múltiplos componentes.

### Itens

#### 6. Desbloqueio de Rate Limiter (Thread Principal) 🔴
**Ref**: Finding 7 (CRÍTICO)  
**Tempo**: 5h  
**Arquivos**: `app/core/rate_limit.py`, `app/agent/orchestrator.py`, múltiplas tools

**Problema**: `time.sleep` bloqueante trava UI por 10-30s durante rate limiting.

**Solução**: Refatorar `RateLimiter.wait()` para método `check()` não-bloqueante que retorna tempo de espera sem travar thread.

**Implementação**:
1. Criar método `check_and_record() -> float` que retorna 0.0 (ok) ou segundos a esperar
2. Atualizar todos os callers para tratar wait > 0 retornando mensagem ao usuário
3. Remover `time.sleep` do rate limiter

**Critério de sucesso**:
- UI responsiva durante rate limiting
- Barge-in funciona mesmo com rate limit ativo
- Usuário recebe mensagem "Aguarde Xs" sem congelar interface

**Dependências**: Nenhuma

---

#### 7. Countdown Visual em Confirmações Críticas ⚠️
**Ref**: Finding 8  
**Tempo**: 2.5h  
**Arquivos**: `app/core/critical_confirm.py`, `app/ui/panel/templates/index.html`, `app/ui/panel/static/js/panel.js`

**Problema**: Timeout de 5 minutos ocorre silenciosamente sem countdown visual.

**Solução**: Adicionar modal no painel com barra de progresso mostrando tempo restante.

**Implementação**:
1. Thread de countdown em `critical_confirm.py` chama callbacks a cada 1s
2. Modal no painel recebe updates via websocket/event bus
3. Avisos aos 60s e 10s restantes
4. Mensagem de expiração se timeout

**Critério de sucesso**:
- Modal de confirmação exibe tempo restante em tempo real
- Aviso destacado aos 60s e 10s
- Usuário nunca perde contexto por timeout silencioso

**Dependências**: Requer sistema de eventos UI (websocket ou polling leve)

---

#### 8. Wake Word Detection Event-Driven 🔧
**Ref**: Finding 9  
**Tempo**: 2h  
**Arquivo**: `app/services/voice/wake_word.py`

**Problema**: Polling com `time.sleep(0.2-0.5s)` desperdiça CPU e aumenta latência.

**Solução**: Substituir polling por callbacks ou reduzir latência para < 50ms.

**Implementação**:
1. Substituir sleeps de 0.2-0.5s por `threading.Event.wait(timeout=0.05)`
2. Idealmente: migrar para stream callback-based (pyaudio/sounddevice)
3. Remover polling desnecessário

**Critério de sucesso**:
- Latência de detecção < 100ms (atualmente 200-500ms)
- CPU usage do processo reduz em 10-15%
- Bateria dura mais em laptops

**Dependências**: Nenhuma (pode ser implementado incrementalmente)

---

#### 9. Sistema de Onboarding Interativo 🎓
**Ref**: Finding 6  
**Tempo**: 4h  
**Arquivos**: `app/ui/panel/templates/index.html`, `app/ui/panel/static/js/panel.js`, `app/storage/user_prefs.py`

**Problema**: Novos usuários não sabem por onde começar; funcionalidades ocultas.

**Solução**: Welcome screen na primeira inicialização + seção de sugestões no chat vazio.

**Implementação**:
1. Modal de boas-vindas com 5-7 comandos de exemplo clicáveis
2. Flag `onboarding_completed` em `localStorage` ou `user_prefs.json`
3. Seção "Sugestões" no chat vazio com comandos comuns
4. Botão "Ver Tour" opcional no menu

**Critério de sucesso**:
- Novo usuário vê welcome screen na primeira abertura
- Exemplos clicáveis preenchem input do chat
- Taxa de primeira interação aumenta em 80%
- Redução de 50% em perguntas "o que posso fazer?"

**Dependências**: Nenhuma

---

#### 10. Padronização de Linguagem (Guia de Tom e Voz) 📝
**Ref**: Finding 10  
**Tempo**: 4h  
**Arquivos**: Todos em `app/agent/tools/`, `app/services/llm.py`, `app/core/messages.py` (novo)

**Problema**: Mensagens inconsistentes (formal/casual/técnico) quebram profissionalismo.

**Solução**: Criar guia de tom e módulo centralizado de mensagens.

**Implementação**:
1. Criar `app/core/messages.py` com constantes de mensagens padronizadas
2. Auditar todos os arquivos que retornam `ToolResult` ou mensagens ao usuário
3. Reescrever mensagens seguindo tom consistente: profissional, acessível, empático
4. Documentar guia de tom em `docs/voice-and-tone.md`

**Tom recomendado**:
- Usar "você" consistentemente
- Assistente confiável, não robô formal nem amigo casual
- Emojis apenas para sucesso/alertas críticos

**Critério de sucesso**:
- 100% das mensagens user-facing seguem mesmo tom
- Zero variações de formalidade entre diferentes módulos
- Percepção de sistema "polido" aumenta

**Dependências**: Deve ser última tarefa do sprint (afeta múltiplos arquivos)

---

### Resultados Esperados do Sprint 2

✅ **5 melhorias estruturais implementadas**  
⏱️ **~17.5 horas de desenvolvimento**  
🎯 **Problemas críticos de performance e UX resolvidos**:
- UI nunca trava (rate limiter não-bloqueante)
- Novos usuários aprendem sistema sozinhos (onboarding)
- Sistema responsivo e eficiente (wake word event-driven)
- Confirmações críticas nunca expiram silenciosamente
- Linguagem consistente e profissional

---

## Sprint 3 — Excelência (ongoing)

### Objetivo
Refinar detalhes, adicionar telemetria, e estabelecer práticas de qualidade contínua.

### Itens

#### 11. Testes de Integração Automatizados 🧪
**Tempo**: 6h  
**Prioridade**: 🟢 NICE-TO-HAVE (mas importante para DX)

**Problema**: Não existe test suite que rode contra servidor real. Regressões UX podem passar despercebidas.

**Solução**: Criar `tests/test_live_integration.py` com os 11 cenários auditados.

**Implementação**:
1. Fixture que sobe/desce servidor Jarvis
2. Testes para cada scenario:
   - Spotify com feedback visual
   - Timer com confirmação
   - Rate limit com recovery
   - WhatsApp sem anti-spam visível
   - Confirmação com countdown
   - etc.
3. CI/CD pipeline executa testes antes de merge

**Critério de sucesso**:
- 11 testes de integração passando
- CI detecta regressões UX automaticamente
- Cobertura de cenários críticos > 80%

---

#### 12. Telemetria UX para Identificar Friction Points 📊
**Tempo**: 8h  
**Prioridade**: 🟢 NICE-TO-HAVE

**Problema**: Não sabemos quais friction points reais ocorrem em produção.

**Solução**: Sistema de telemetria opt-in para coletar métricas anônimas.

**Métricas a coletar**:
- Tempo médio de resposta por tool
- Taxa de cancelamento de operações
- Erros mais frequentes
- Comandos mais usados
- Taxa de uso de onboarding

**Implementação**:
1. Módulo `app/telemetry/collector.py` com opt-in em settings
2. Envio para analytics local (SQLite) ou serviço externo (opcional)
3. Dashboard simples para visualizar métricas
4. Privacy by design: zero dados pessoais, apenas métricas agregadas

**Critério de sucesso**:
- Dashboard mostra top 10 operações por tempo de resposta
- Identifica padrões de erro em produção
- Decisões de roadmap baseadas em dados reais

---

#### 13. Migração para Async/Await (Refatoração Grande) 🏗️
**Tempo**: 20h+  
**Prioridade**: 🟢 NICE-TO-HAVE (longo prazo)

**Problema**: Múltiplos `time.sleep` bloqueantes em código síncrono.

**Solução**: Refatorar componentes críticos para async/await.

**Escopo**:
- `app/services/llm.py` → async calls
- `app/agent/tools/spotify.py` → async operations
- `app/core/rate_limit.py` → async wait
- `app/services/voice/wake_word.py` → async stream

**Benefícios**:
- Eliminação de todos os sleeps bloqueantes
- UI sempre responsiva
- Melhor uso de recursos (CPU, threads)
- Código mais moderno e manutenível

**Critério de sucesso**:
- Zero `time.sleep` no código crítico
- UI 100% não-bloqueante
- Retrocompatibilidade preservada (wrappers sync)

**Atenção**: Refatoração grande, requer planejamento cuidadoso e testes extensivos.

---

#### 14. Auditoria Completa de Acessibilidade (WCAG 2.1) ♿
**Tempo**: 12h  
**Prioridade**: 🟢 NICE-TO-HAVE (mas importante para inclusão)

**Problema**: Não houve auditoria de acessibilidade para usuários com deficiências.

**Escopo**:
- Screen readers (NVDA, JAWS, Narrator)
- Navegação por teclado (sem mouse)
- Contraste de cores (WCAG AA/AAA)
- Labels e ARIA attributes
- Alternativas de áudio para notificações visuais

**Implementação**:
1. Auditoria com ferramentas automatizadas (axe, Lighthouse)
2. Testes manuais com screen readers
3. Correções de HTML semântico e ARIA
4. Documentação de atalhos de teclado
5. Testes com usuários reais (se possível)

**Critério de sucesso**:
- WCAG 2.1 Level AA compliance
- Navegação 100% por teclado
- Screen readers leem todas as informações críticas
- Contraste de texto > 4.5:1

---

#### 15. Sistema Centralizado de Event Bus para Feedback em Tempo Real 🔔
**Tempo**: 10h  
**Prioridade**: 🟢 NICE-TO-HAVE

**Problema**: Feedback de progresso é fragmentado entre tools; não há padrão unificado.

**Solução**: Event bus centralizado para comunicação backend → frontend.

**Implementação**:
1. WebSocket server em `app/ui/panel/websocket.py`
2. Eventos padronizados:
   - `tool.progress` (label, percentage)
   - `tool.complete` (result)
   - `timer.fired` (label, timestamp)
   - `confirmation.countdown` (seconds_remaining)
3. Frontend escuta eventos e atualiza UI em tempo real
4. Todas as tools usam event bus consistentemente

**Critério de sucesso**:
- Todas as operações > 1s emitem eventos de progresso
- UI atualiza em tempo real sem polling
- Padrão unificado para todas as tools
- Latência de eventos < 50ms

---

### Resultados Esperados do Sprint 3

✅ **5 melhorias de excelência implementadas**  
⏱️ **~56 horas de desenvolvimento (pode ser distribuído ao longo de meses)**  
🎯 **Sistema polido, acessível, e com qualidade de produto comercial**:
- Testes automatizados previnem regressões
- Telemetria guia decisões de produto
- Sistema responsivo e eficiente (async)
- Acessível para todos os usuários
- Feedback em tempo real unificado

---

## Métricas de Sucesso Globais

### Como medir que a UX melhorou

#### 1. Métricas de Performance
- **Tempo de resposta médio** (tools): redução de 30%
  - Spotify: de 10s → 8s (com feedback percebido < 2s)
  - LLM com rate limit: de falha imediata → retry automático
  
- **Taxa de erro user-facing**: redução de 50%
  - Rate limit "sobrecarregado": de 20% → < 5% das tentativas
  - Confirmações expiradas: de 15% → < 3%

- **Responsividade da UI**: 100% não-bloqueante
  - Zero reports de "sistema travado"
  - Barge-in funciona em 100% das situações

#### 2. Métricas de Usabilidade
- **Taxa de completação de primeira tarefa** (novos usuários): > 80%
  - Usuário consegue executar comando na primeira tentativa
  
- **Taxa de uso de onboarding**: > 60%
  - Novos usuários interagem com welcome screen
  
- **Comandos descobertos**: aumento de 40%
  - Usuários usam mais funcionalidades (vision, timer, checklist)

#### 3. Métricas de Satisfação
- **NPS (Net Promoter Score)**: aumento de 15 pontos
  - Coleta via survey opcional após 7 dias de uso
  
- **Taxa de abandono**: redução de 30%
  - Usuários permanecem ativos após primeira semana
  
- **Reports de confusão**: redução de 70%
  - Menos perguntas "o que significa X?"
  - Menos reports de "não sei o que fazer"

#### 4. Métricas de Qualidade (DX)
- **Cobertura de testes de integração**: > 80%
  - Cenários críticos cobertos
  
- **Tempo para implementar nova tool**: redução de 20%
  - Padrões claros (messages.py, event bus) aceleram desenvolvimento
  
- **Taxa de regressão**: redução de 60%
  - CI detecta problemas antes de produção

---

## Dependências entre Sprints

```
Sprint 1 (Quick Wins)
    ↓
    ├─→ Sprint 2.6 (Rate Limiter) — usa mensagens padronizadas de Sprint 1.5
    ├─→ Sprint 2.10 (Linguagem) — audita mudanças de Sprint 1
    └─→ Sprint 3.11 (Testes) — valida implementações de Sprint 1
    
Sprint 2 (Melhorias Significativas)
    ↓
    ├─→ Sprint 3.12 (Telemetria) — usa event bus de Sprint 3.15
    ├─→ Sprint 3.13 (Async) — refatora código de Sprint 2.6, 2.8
    └─→ Sprint 3.15 (Event Bus) — usa countdown de Sprint 2.7
```

**Ordem recomendada**:
1. Sprint 1 completo (5.5h) — base de mensagens humanizadas
2. Sprint 2.6 (5h) — desbloqueia UI (crítico)
3. Sprint 2.7, 2.8, 2.9 em paralelo (8.5h total) — sem dependências entre si
4. Sprint 2.10 (4h) — padroniza tudo que veio antes
5. Sprint 3 conforme necessidade e capacidade da equipe

---

## Roadmap Visual

```
Sprint 1 (1-2 semanas)
████████████████████ 100%
├─ Anti-Spam Messages
├─ Spotify Feedback
├─ Rate Limit Recovery
├─ Timer Confirmation
└─ Dev vs User Messages

Sprint 2 (3-4 semanas)
████████░░░░░░░░░░░░ 40%
├─ Rate Limiter Non-Blocking 🔴
├─ Countdown Confirmações
├─ Wake Word Event-Driven
├─ Sistema de Onboarding
└─ Padronização de Linguagem

Sprint 3 (ongoing)
███░░░░░░░░░░░░░░░░░ 15%
├─ Testes de Integração
├─ Telemetria UX
├─ Migração Async/Await
├─ Auditoria Acessibilidade
└─ Event Bus Centralizado
```

---

## Próximos Passos Imediatos

1. ✅ **Aprovar roadmap** com stakeholders
2. 🚀 **Iniciar Sprint 1** (5.5h de desenvolvimento)
3. 📊 **Definir baseline de métricas** antes das mudanças
4. 🧪 **Setup de teste manual** para validar cada quick win
5. 📝 **Documentar resultados** de Sprint 1 para guiar Sprint 2

---

## Observações Finais

- **Prioridade**: Sprints 1 e 2 têm ROI muito alto; Sprint 3 é incremental e pode ser ongoing
- **Recursos**: Sprint 1 pode ser feito por 1 dev em 1 dia; Sprint 2 requer 2-3 dias; Sprint 3 é distribuído
- **Risco**: Itens críticos (Finding 7 - Rate Limiter) devem ser priorizados no Sprint 2
- **Feedback loop**: Coletar feedback de usuários após Sprint 1 para ajustar prioridades de Sprint 2
