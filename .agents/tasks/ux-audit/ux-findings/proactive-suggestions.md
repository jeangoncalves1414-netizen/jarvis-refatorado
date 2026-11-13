# Proactive Suggestions — Consolidação de Achados

**Data**: 2025-01-XX  
**Fonte**: Auditoria UX/DX Jarvis + Análise de Código  
**Arquivos relacionados**: `app/core/pattern_learner.py`, `app/agent/orchestrator.py`

---

## Contexto: Sistema Proativo Existente

Jarvis já possui **infraestrutura para sugestões proativas** através do `PatternLearner`:

**Arquivo**: `app/core/pattern_learner.py`

```python
class PatternLearner:
    """Aprende padrões de comportamento do usuário e notifica proativamente."""
    
    def learn_pattern(self, context: dict) -> None:
        """Registra comportamento do usuário."""
        pass
    
    def suggest_action(self, current_context: dict) -> str | None:
        """Retorna sugestão proativa baseada em padrões aprendidos."""
        pass
```

**Uso atual**: Sistema de callbacks existe, mas **não há evidência de integração completa com UI** ou feedback audível confirmado (relacionado ao Finding 7 do user request original).

---

## Problema: Sugestões Proativas Subaproveitadas

### Cenários Não Explorados

1. **Rotinas Diárias**
   - Usuário sempre toca música às 9h → Sugerir "Quer que eu toque sua playlist matinal?"
   - Usuário sempre cria checklist de compras às sextas → "É sexta, quer criar sua lista de compras?"

2. **Contexto de Tempo**
   - Timer de 25 min (Pomodoro) termina → "Quer outro ciclo de 25 minutos?"
   - Usuário sempre para música ao sair para almoço (12h-13h) → "Pausando música para o almoço?"

3. **Sequências de Ações**
   - Usuário sempre abre Spotify depois de fechar reunião no Teams → Sugerir automaticamente
   - Após busca web sobre restaurante, usuário sempre envia mensagem WhatsApp → "Quer compartilhar isso?"

4. **Erros Recorrentes**
   - Usuário tenta comando que falha repetidamente → "Parece que você está tentando X. Posso ajudar de outra forma?"
   - Rate limit frequente em horário específico → "Vejo que você costuma usar às 14h. Quer que eu reserve capacidade?"

### Por Que Importa

- **Reduz atrito**: Usuário não precisa repetir comandos rotineiros
- **Demonstra inteligência**: Sistema "entende" o usuário ao longo do tempo
- **Aumenta engajamento**: Usuário vê valor contínuo, não apenas reativo
- **Diferenciação competitiva**: Assistentes genéricos não aprendem padrões pessoais

---

## Oportunidades Identificadas

### 1. Sugestões de Continuidade

#### Cenário: Usuário Deixa Tarefa Incompleta

**Padrão detectado**:
```python
# Usuário cria checklist mas não adiciona itens
user_action = "criar checklist de viagem"
# ... 5 minutos se passam ...
# Nenhuma ação adicional

# Sistema sugere proativamente:
suggestion = "Vi que você criou uma checklist de viagem. Quer que eu adicione alguns itens comuns?"
```

**Exemplos de continuidade**:
- Checklist criada sem itens → "Quer que eu adicione itens comuns de [categoria]?"
- Timer cancelado antes de terminar → "O timer ainda tinha X minutos. Quer recriar?"
- Busca web sem follow-up → "Encontrei informações sobre X. Quer que eu resuma?"
- Música pausada por muito tempo → "Música pausada há 20 minutos. Quer continuar ou desligar?"

---

### 2. Sugestões de Otimização

#### Cenário: Usuário Usa Caminho Ineficiente

**Padrão detectado**:
```python
# Usuário sempre faz sequência:
# 1. "Abre Spotify"
# 2. (aguarda 10s)
# 3. "Toca Bohemian Rhapsody"

# Sistema aprende e sugere shortcut:
suggestion = "Notei que você sempre toca música ao abrir Spotify. Posso fazer isso em um comando?"
```

**Exemplos de otimização**:
- Usuário sempre pede "busca X" + "resuma" → Sugerir "Quer que eu sempre resuma buscas automaticamente?"
- Usuário sempre confirma ações críticas → "Você sempre aprova ações de [tipo]. Quer pular confirmação para isso?"
- Usuário sempre usa mesmos parâmetros → "Quer que eu use '[valor]' como padrão?"

---

### 3. Sugestões Contextuais Baseadas em Tempo

#### Cenário: Rotinas em Horários Específicos

**Implementação**:
```python
# pattern_learner.py - adicionar análise temporal

class PatternLearner:
    def detect_time_based_patterns(self) -> list[TimePattern]:
        """Detecta padrões recorrentes em horários específicos."""
        patterns = []
        
        # Exemplo: Usuário sempre toca música entre 9h-9:15h nos dias de semana
        pattern = TimePattern(
            action="tocar música",
            time_range=(9, 9.25),  # 9h00 - 9h15
            days_of_week=[0, 1, 2, 3, 4],  # Segunda a sexta
            confidence=0.85,  # 85% das vezes
            last_occurrences=10  # Ocorreu 10 vezes
        )
        patterns.append(pattern)
        
        return patterns
    
    def should_suggest_now(self, pattern: TimePattern) -> bool:
        """Verifica se deve sugerir ação baseada em tempo."""
        now = datetime.now()
        
        # Está no horário do padrão?
        if not pattern.is_in_time_range(now):
            return False
        
        # Dia da semana correto?
        if now.weekday() not in pattern.days_of_week:
            return False
        
        # Confiança suficiente?
        if pattern.confidence < 0.7:
            return False
        
        # Já sugeriu hoje?
        if pattern.suggested_today():
            return False
        
        return True
```

**Exemplos de sugestões temporais**:
- 9h em dia de semana → "Bom dia! Quer tocar sua playlist matinal?"
- 12h → "Hora do almoço. Quer que eu pause a música?"
- 18h sexta-feira → "Fim de semana! Quer criar sua lista de compras?"
- 22h → "Quer que eu configure um timer de desligamento do Spotify?"

---

### 4. Sugestões Baseadas em Contexto de Sistema

#### Cenário: Estado do Sistema Indica Oportunidade

**Implementação**:
```python
# orchestrator.py - adicionar context awareness

class ContextAwareSuggestions:
    def check_system_context(self) -> list[Suggestion]:
        """Verifica estado do sistema e sugere ações."""
        suggestions = []
        
        # Spotify tocando há 2h+ sem interação
        if spotify.is_playing() and spotify.last_interaction() > 7200:
            suggestions.append(Suggestion(
                text="Música tocando há 2 horas. Quer pausar ou trocar?",
                actions=["pausar música", "tocar outra playlist"],
                priority="low"
            ))
        
        # Checklist com muitos itens pendentes
        if checklist.pending_items_count() > 10:
            suggestions.append(Suggestion(
                text="Você tem 10+ itens pendentes na checklist. Quer revisar?",
                actions=["listar itens pendentes", "limpar concluídos"],
                priority="medium"
            ))
        
        # Timers frequentemente esquecidos
        if timer.cancellation_rate() > 0.5:
            suggestions.append(Suggestion(
                text="Notei que você cancela muitos timers. Quer ajustar durações padrão?",
                actions=["ver histórico de timers", "configurar durações"],
                priority="low"
            ))
        
        return suggestions
```

**Exemplos de sugestões contextuais**:
- Muitos rate limits recentes → "Vejo que você está usando bastante. Quer que eu otimize o uso de API?"
- Erro recorrente → "Esse comando falhou 3x. Posso tentar de outra forma?"
- Funcionalidade não usada → "Você sabia que eu posso tirar fotos da tela e analisá-las?"

---

### 5. Sugestões de Recuperação de Erro

#### Cenário: Usuário Enfrenta Problema Repetido

**Implementação**:
```python
# error_recovery.py - novo módulo

class ErrorRecoverySuggestions:
    def __init__(self):
        self.error_history: list[ErrorEvent] = []
    
    def log_error(self, error: ErrorEvent):
        """Registra erro para análise de padrões."""
        self.error_history.append(error)
        
        # Se erro recorrente (3x em 10 min), sugerir solução
        recent_errors = [e for e in self.error_history 
                        if e.timestamp > time.time() - 600]
        
        if self._is_recurring_error(recent_errors, error):
            return self._suggest_recovery(error)
    
    def _suggest_recovery(self, error: ErrorEvent) -> Suggestion:
        """Sugere solução baseada no tipo de erro."""
        
        if error.type == "rate_limit":
            return Suggestion(
                text="Vejo que você está atingindo limites frequentemente. Quer que eu espaçe as requisições automaticamente?",
                actions=["ativar modo econômico", "ver uso de API"]
            )
        
        elif error.type == "whatsapp_not_connected":
            return Suggestion(
                text="WhatsApp não está conectado. Quer que eu abra o WhatsApp Web para você?",
                actions=["abrir WhatsApp Web", "pular mensagem"]
            )
        
        elif error.type == "spotify_not_found":
            return Suggestion(
                text="Não encontrei essa música. Quer tentar buscar de outra forma ou escolher outra?",
                actions=["buscar artista similar", "tocar playlist"]
            )
        
        return None
```

---

## Interface de Sugestões Proativas na UI

### Design: Notification Bar não-intrusiva

```html
<!-- Adicionar ao index.html -->
<div id="proactive-suggestions" class="fixed bottom-20 left-0 right-0 z-40 pointer-events-none">
    <div class="container mx-auto px-4">
        <div id="suggestion-card" class="bg-primary-container text-on-primary-container rounded-lg shadow-lg p-4 flex items-center gap-4 max-w-2xl mx-auto pointer-events-auto hidden animate-slide-up">
            <span class="material-symbols-outlined text-2xl">lightbulb</span>
            
            <div class="flex-1">
                <p id="suggestion-text" class="text-sm font-medium"></p>
            </div>
            
            <div class="flex gap-2">
                <button id="suggestion-accept" class="px-4 py-2 bg-primary text-on-primary rounded-md hover:bg-primary/80 transition-all text-sm font-medium">
                    Sim
                </button>
                <button id="suggestion-dismiss" class="px-4 py-2 bg-surface-variant text-on-surface-variant rounded-md hover:bg-surface-variant/80 transition-all text-sm">
                    Não, obrigado
                </button>
            </div>
        </div>
    </div>
</div>

<style>
@keyframes slide-up {
    from {
        transform: translateY(100%);
        opacity: 0;
    }
    to {
        transform: translateY(0);
        opacity: 1;
    }
}

.animate-slide-up {
    animation: slide-up 0.3s ease-out;
}
</style>

<script>
// Mostrar sugestão proativa
function showProactiveSuggestion(text, acceptAction) {
    const card = document.getElementById('suggestion-card');
    const textEl = document.getElementById('suggestion-text');
    const acceptBtn = document.getElementById('suggestion-accept');
    const dismissBtn = document.getElementById('suggestion-dismiss');
    
    textEl.textContent = text;
    card.classList.remove('hidden');
    
    // Aceitar sugestão
    acceptBtn.onclick = () => {
        acceptAction();
        hideSuggestion();
    };
    
    // Dispensar sugestão
    dismissBtn.onclick = () => {
        hideSuggestion();
        // Log para não sugerir novamente hoje
        logSuggestionDismissed(text);
    };
    
    // Auto-dismiss após 15s
    setTimeout(() => {
        if (!card.classList.contains('hidden')) {
            hideSuggestion();
        }
    }, 15000);
}

function hideSuggestion() {
    const card = document.getElementById('suggestion-card');
    card.classList.add('animate-slide-down');
    setTimeout(() => {
        card.classList.add('hidden');
        card.classList.remove('animate-slide-down');
    }, 300);
}

// Exemplo de uso
showProactiveSuggestion(
    "Bom dia! Quer tocar sua playlist matinal?",
    () => sendMessage("toca minha playlist matinal")
);
</script>
```

---

## Backend: Sistema de Decisão de Sugestões

```python
# app/agent/proactive_suggester.py - NOVO

from datetime import datetime, timedelta
from app.core.pattern_learner import PatternLearner
from app.storage.user_prefs import UserPrefs

class ProactiveSuggester:
    """Gerencia sugestões proativas baseadas em padrões e contexto."""
    
    def __init__(self, pattern_learner: PatternLearner, user_prefs: UserPrefs):
        self.pattern_learner = pattern_learner
        self.user_prefs = user_prefs
        self.suggestions_shown_today: set[str] = set()
    
    def get_suggestion(self) -> Suggestion | None:
        """Retorna sugestão proativa se apropriado."""
        
        # Não sugerir se usuário está ativamente usando
        if self._user_is_active():
            return None
        
        # Verificar se há padrão temporal aplicável
        time_suggestion = self._check_time_patterns()
        if time_suggestion:
            return time_suggestion
        
        # Verificar contexto de sistema
        context_suggestion = self._check_system_context()
        if context_suggestion:
            return context_suggestion
        
        # Verificar oportunidades de continuidade
        continuity_suggestion = self._check_continuity()
        if continuity_suggestion:
            return continuity_suggestion
        
        return None
    
    def _check_time_patterns(self) -> Suggestion | None:
        """Verifica padrões baseados em tempo."""
        patterns = self.pattern_learner.detect_time_based_patterns()
        
        for pattern in patterns:
            if self.pattern_learner.should_suggest_now(pattern):
                # Não sugerir se já mostrou hoje
                suggestion_id = f"time_{pattern.action}_{datetime.now().date()}"
                if suggestion_id in self.suggestions_shown_today:
                    continue
                
                self.suggestions_shown_today.add(suggestion_id)
                
                return Suggestion(
                    id=suggestion_id,
                    text=f"Quer {pattern.action}? Você costuma fazer isso neste horário.",
                    action=pattern.action,
                    priority="medium",
                    expires_at=datetime.now() + timedelta(minutes=5)
                )
        
        return None
    
    def _check_system_context(self) -> Suggestion | None:
        """Verifica estado do sistema."""
        # Implementar context awareness
        pass
    
    def _check_continuity(self) -> Suggestion | None:
        """Verifica tarefas incompletas."""
        # Implementar continuity suggestions
        pass
    
    def _user_is_active(self) -> bool:
        """Verifica se usuário está ativamente usando o sistema."""
        last_interaction = self.user_prefs.last_interaction_time
        if not last_interaction:
            return False
        
        # Considera ativo se interagiu nos últimos 2 minutos
        return (datetime.now() - last_interaction).total_seconds() < 120
```

---

## Configuração de Preferências: Controle do Usuário

```python
# app/storage/user_prefs.py - adicionar flags

class UserPrefs:
    def __init__(self):
        # ... campos existentes ...
        
        # Sugestões proativas
        self.proactive_suggestions_enabled: bool = True
        self.suggestion_frequency: str = "balanced"  # "aggressive", "balanced", "minimal"
        self.suggestion_categories: set[str] = {
            "time_based",      # Rotinas em horários específicos
            "continuity",      # Tarefas incompletas
            "optimization",    # Shortcuts e otimizações
            "context",         # Estado do sistema
            "error_recovery"   # Ajuda com erros recorrentes
        }
```

**UI de configuração**:
```html
<!-- settings.html -->
<section>
    <h3>Sugestões Proativas</h3>
    <label>
        <input type="checkbox" id="proactive-enabled" checked>
        Ativar sugestões proativas
    </label>
    
    <label>
        Frequência:
        <select id="suggestion-frequency">
            <option value="minimal">Mínima (apenas críticas)</option>
            <option value="balanced" selected>Equilibrada</option>
            <option value="aggressive">Máxima (todas as oportunidades)</option>
        </select>
    </label>
    
    <p class="text-sm text-on-surface-variant">
        Categorias de sugestões:
    </p>
    <label><input type="checkbox" checked> Rotinas de horário</label>
    <label><input type="checkbox" checked> Tarefas incompletas</label>
    <label><input type="checkbox" checked> Otimizações</label>
    <label><input type="checkbox" checked> Contexto do sistema</label>
    <label><input type="checkbox" checked> Ajuda com erros</label>
</section>
```

---

## Métricas de Sucesso

Após implementar sugestões proativas melhoradas:

- **Taxa de aceitação de sugestões > 30%** (usuário clica "Sim")
- **Redução de 20% em comandos repetitivos** (rotinas automatizadas)
- **Aumento de 25% em engajamento diário** (usuário interage mais frequentemente)
- **Satisfação com "inteligência" do sistema > 70%** (survey NPS)
- **Taxa de disable de sugestões < 10%** (usuários não acham intrusivo)

---

## Checklist de Implementação

### Sprint 3 (3 horas)
- [ ] Criar componente de UI para sugestões proativas (notification bar)
- [ ] Integrar `PatternLearner` existente com sistema de sugestões
- [ ] Implementar detecção básica de padrões temporais
- [ ] Adicionar preferências de sugestões em `user_prefs.py`

### Sprint 4 (4 horas)
- [ ] Implementar sugestões de continuidade (tarefas incompletas)
- [ ] Context awareness (estado de Spotify, checklists, timers)
- [ ] Sistema de throttling (não sugerir demais)
- [ ] Analytics para rastrear aceitação/rejeição de sugestões

### Sprint 5 (3 horas)
- [ ] Sugestões de otimização (shortcuts detectados)
- [ ] Error recovery suggestions (erros recorrentes)
- [ ] Refinamento baseado em feedback
- [ ] A/B testing de mensagens de sugestão
