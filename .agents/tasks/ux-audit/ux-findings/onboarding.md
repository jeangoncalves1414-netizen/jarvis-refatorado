# Onboarding e Primeiro Uso — Consolidação de Achados

**Data**: 2025-01-XX  
**Fonte**: Auditoria UX/DX Jarvis  
**Finding relacionado**: 6

---

## Problema Sistêmico

Jarvis não possui **nenhuma forma de onboarding** para novos usuários. A interface apresenta apenas um orb visual e campo de input, sem exemplos, tooltips, ou orientação sobre o que o sistema pode fazer. Isso resulta em curva de aprendizado íngreme e alta taxa de abandono.

---

## Estado Atual: Ausência Completa de Onboarding

### Análise do Código

**Arquivo**: `app/ui/panel/templates/index.html`

**Elementos ausentes**:
- ❌ Welcome screen / modal de boas-vindas
- ❌ Tooltips contextuais
- ❌ Exemplos de comandos clicáveis
- ❌ Tour interativo
- ❌ Seção de "Sugestões" quando chat vazio
- ❌ Help/FAQ acessível
- ❌ Indicação visual de funcionalidades disponíveis

**Primeira experiência do usuário**:
1. Abre Jarvis pela primeira vez
2. Vê tela com orb e campo de input
3. Não sabe o que digitar
4. Tenta algo genérico ("oi", "ajuda")
5. Sem orientação clara sobre funcionalidades avançadas
6. Abandona ou precisa ler documentação externa

---

## Impacto no Usuário

### Problemas Identificados

1. **Curva de aprendizado íngreme**
   - Usuário não sabe por onde começar
   - Funcionalidades avançadas permanecem ocultas (vision, checklist, timer, Spotify)
   - Precisa descobrir por tentativa e erro

2. **Taxa de abandono alta**
   - Usuário sem orientação tende a desistir rapidamente
   - Falta de "momento aha" inicial
   - Sem demonstração de valor imediato

3. **Necessidade de documentação externa**
   - Usuário precisa assistir vídeos ou ler wiki
   - Quebra o fluxo de experiência dentro do app
   - Aumenta barreira de entrada

4. **Funcionalidades subutilizadas**
   - Recursos avançados como vision, pattern learning, confirmação crítica ficam desconhecidos
   - Usuário usa apenas 20-30% das capacidades do sistema
   - ROI reduzido do desenvolvimento de features

---

## Soluções Propostas

### 1. Welcome Screen na Primeira Inicialização

#### Design: Modal de Boas-Vindas

**Quando mostrar**: Primeira vez que o usuário abre Jarvis (flag `onboarding_completed` em localStorage)

**Conteúdo**:
- Título acolhedor: "👋 Bem-vindo ao Jarvis"
- Descrição breve (1 parágrafo): "Seu assistente pessoal de automação..."
- Grid de 4-6 comandos exemplo **clicáveis**
- Botão "Começar" para fechar modal

**Benefícios**:
- Primeira impressão positiva
- Demonstra valor imediatamente
- Permite experimentação sem barreira (clicar em exemplo)
- Reduz ansiedade de "página em branco"

#### Implementação

```html
<!-- Adicionar ao index.html -->
<div id="welcome-modal" class="fixed inset-0 bg-black/70 z-50 hidden items-center justify-center">
    <div class="bg-surface-container rounded-xl p-8 max-w-2xl mx-4 shadow-2xl animate-fade-in">
        <h2 class="text-headline-lg font-headline-lg text-primary-fixed-dim mb-4">
            👋 Bem-vindo ao Jarvis
        </h2>
        <p class="text-body-md text-on-surface mb-6">
            Seu assistente pessoal de automação. Controle aplicativos, crie lembretes, 
            busque informações e automatize tarefas — tudo por voz ou texto.
        </p>
        
        <p class="text-body-sm text-on-surface-variant mb-4">
            Experimente alguns exemplos para começar:
        </p>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all group">
                <div class="flex items-start gap-3">
                    <span class="material-symbols-outlined text-primary-fixed-dim text-2xl">music_note</span>
                    <div>
                        <p class="font-medium text-on-surface group-hover:text-primary-fixed-dim">"Toca Bohemian Rhapsody no Spotify"</p>
                        <p class="text-xs text-on-surface-variant">Controla Spotify automaticamente</p>
                    </div>
                </div>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all group">
                <div class="flex items-start gap-3">
                    <span class="material-symbols-outlined text-secondary-fixed-dim text-2xl">checklist</span>
                    <div>
                        <p class="font-medium text-on-surface group-hover:text-secondary-fixed-dim">"Cria uma checklist de compras"</p>
                        <p class="text-xs text-on-surface-variant">Gerencia listas e tarefas</p>
                    </div>
                </div>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all group">
                <div class="flex items-start gap-3">
                    <span class="material-symbols-outlined text-tertiary-fixed-dim text-2xl">camera</span>
                    <div>
                        <p class="font-medium text-on-surface group-hover:text-tertiary-fixed-dim">"Tire uma foto da tela"</p>
                        <p class="text-xs text-on-surface-variant">Vision AI analisa imagens</p>
                    </div>
                </div>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all group">
                <div class="flex items-start gap-3">
                    <span class="material-symbols-outlined text-primary-fixed-dim text-2xl">timer</span>
                    <div>
                        <p class="font-medium text-on-surface group-hover:text-primary-fixed-dim">"Timer de 5 minutos"</p>
                        <p class="text-xs text-on-surface-variant">Lembretes e alarmes</p>
                    </div>
                </div>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all group">
                <div class="flex items-start gap-3">
                    <span class="material-symbols-outlined text-primary-fixed-dim text-2xl">search</span>
                    <div>
                        <p class="font-medium text-on-surface group-hover:text-primary-fixed-dim">"Busca notícias sobre IA"</p>
                        <p class="text-xs text-on-surface-variant">Busca web com síntese</p>
                    </div>
                </div>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all group">
                <div class="flex items-start gap-3">
                    <span class="material-symbols-outlined text-secondary-fixed-dim text-2xl">send</span>
                    <div>
                        <p class="font-medium text-on-surface group-hover:text-secondary-fixed-dim">"Envia mensagem pro João"</p>
                        <p class="text-xs text-on-surface-variant">WhatsApp automatizado</p>
                    </div>
                </div>
            </button>
        </div>
        
        <button id="welcome-dismiss" class="w-full py-3 px-6 bg-primary-fixed-dim text-on-primary-fixed rounded-lg hover:bg-primary-fixed transition-all font-medium">
            Começar a Usar
        </button>
        
        <p class="text-xs text-on-surface-variant text-center mt-4">
            Dica: Use voz ou texto. Diga "Jarvis" para ativar por voz.
        </p>
    </div>
</div>

<script>
// Verificar se é primeira vez
if (!localStorage.getItem('onboarding_completed')) {
    document.getElementById('welcome-modal').classList.remove('hidden');
    document.getElementById('welcome-modal').classList.add('flex');
}

// Botão "Começar"
document.getElementById('welcome-dismiss').addEventListener('click', () => {
    localStorage.setItem('onboarding_completed', 'true');
    document.getElementById('welcome-modal').classList.add('fade-out');
    setTimeout(() => {
        document.getElementById('welcome-modal').classList.add('hidden');
    }, 300);
});

// Clicar em comando exemplo preenche input
document.querySelectorAll('.example-command').forEach(btn => {
    btn.addEventListener('click', () => {
        const commandText = btn.querySelector('p.font-medium').textContent.replace(/"/g, '');
        document.querySelector('#chat-input').value = commandText;
        document.querySelector('#chat-input').focus();
        
        localStorage.setItem('onboarding_completed', 'true');
        document.getElementById('welcome-modal').classList.add('fade-out');
        setTimeout(() => {
            document.getElementById('welcome-modal').classList.add('hidden');
        }, 300);
    });
});
</script>

<style>
@keyframes fade-in {
    from { opacity: 0; transform: scale(0.95); }
    to { opacity: 1; transform: scale(1); }
}

.animate-fade-in {
    animation: fade-in 0.3s ease-out;
}

.fade-out {
    animation: fade-in 0.3s ease-out reverse;
}
</style>
```

---

### 2. Seção de Sugestões Quando Chat Vazio

#### Design: Empty State com Sugestões

**Quando mostrar**: Quando não há mensagens no chat (usuário novo ou após limpar conversa)

**Conteúdo**:
- Título: "Como posso ajudar?"
- Lista de 3-4 categorias de comandos
- Sugestões rotativas (muda a cada abertura)

#### Implementação

```html
<!-- Adicionar dentro do chat-container -->
<div id="empty-state" class="flex flex-col items-center justify-center h-full text-center p-8">
    <div class="orb-visual mb-6">
        <!-- Animação do orb -->
    </div>
    
    <h3 class="text-headline-md text-on-surface mb-2">Como posso ajudar?</h3>
    <p class="text-body-sm text-on-surface-variant mb-8">Escolha uma das opções ou digite seu pedido</p>
    
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl">
        <button class="suggestion-card p-4 rounded-lg bg-primary-container hover:bg-primary-container/80 transition-all">
            <span class="material-symbols-outlined text-3xl text-on-primary-container mb-2">music_note</span>
            <p class="text-sm text-on-primary-container font-medium">Tocar Música</p>
        </button>
        
        <button class="suggestion-card p-4 rounded-lg bg-secondary-container hover:bg-secondary-container/80 transition-all">
            <span class="material-symbols-outlined text-3xl text-on-secondary-container mb-2">checklist</span>
            <p class="text-sm text-on-secondary-container font-medium">Criar Lista</p>
        </button>
        
        <button class="suggestion-card p-4 rounded-lg bg-tertiary-container hover:bg-tertiary-container/80 transition-all">
            <span class="material-symbols-outlined text-3xl text-on-tertiary-container mb-2">search</span>
            <p class="text-sm text-on-tertiary-container font-medium">Buscar Info</p>
        </button>
        
        <button class="suggestion-card p-4 rounded-lg bg-primary-container hover:bg-primary-container/80 transition-all">
            <span class="material-symbols-outlined text-3xl text-on-primary-container mb-2">timer</span>
            <p class="text-sm text-on-primary-container font-medium">Timer/Alarme</p>
        </button>
    </div>
    
    <p class="text-xs text-on-surface-variant mt-8">
        💡 Dica: Você pode usar voz ou texto. Experimente "Jarvis, abra o Spotify"
    </p>
</div>

<script>
// Esconder empty state quando há mensagens
function updateEmptyState() {
    const messageCount = document.querySelectorAll('.message').length;
    const emptyState = document.getElementById('empty-state');
    
    if (messageCount === 0) {
        emptyState.classList.remove('hidden');
    } else {
        emptyState.classList.add('hidden');
    }
}

// Suggestion cards preenchem input com exemplos
const suggestions = {
    'Tocar Música': ['Toca Bohemian Rhapsody no Spotify', 'Coloca rock dos anos 80', 'Pausa a música'],
    'Criar Lista': ['Cria uma checklist de compras', 'Adiciona leite na lista de compras', 'Lista minhas checklists'],
    'Buscar Info': ['Busca notícias sobre IA hoje', 'Qual a previsão do tempo?', 'Pesquisa sobre Python'],
    'Timer/Alarme': ['Timer de 10 minutos', 'Me lembre em 1 hora', 'Alarme às 15h']
};

document.querySelectorAll('.suggestion-card').forEach(card => {
    card.addEventListener('click', () => {
        const category = card.querySelector('p').textContent;
        const examples = suggestions[category] || [];
        const randomExample = examples[Math.floor(Math.random() * examples.length)];
        
        document.querySelector('#chat-input').value = randomExample;
        document.querySelector('#chat-input').focus();
    });
});
</script>
```

---

### 3. Tooltips Contextuais

#### Design: Tooltips Informativos ao Hover

**Onde adicionar**:
- Botão de voz: "Clique ou diga 'Jarvis'"
- Campo de input: "Digite um comando ou use voz"
- Ícones do menu: Descrição de cada seção
- Botões de ação: Preview da ação

#### Implementação

```html
<!-- Usar biblioteca de tooltips ou implementar custom -->
<button class="voice-button" data-tooltip="Clique para falar ou diga 'Jarvis'">
    <span class="material-symbols-outlined">mic</span>
</button>

<style>
/* Tooltip simples com CSS puro */
[data-tooltip] {
    position: relative;
}

[data-tooltip]::before {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%) translateY(-8px);
    padding: 8px 12px;
    background: rgba(0, 0, 0, 0.9);
    color: white;
    border-radius: 6px;
    font-size: 12px;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s, transform 0.2s;
    z-index: 1000;
}

[data-tooltip]::after {
    content: '';
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-top-color: rgba(0, 0, 0, 0.9);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
}

[data-tooltip]:hover::before,
[data-tooltip]:hover::after {
    opacity: 1;
}

[data-tooltip]:hover::before {
    transform: translateX(-50%) translateY(-4px);
}
</style>
```

---

### 4. Tour Interativo Opcional

#### Design: Guided Tour de 3-4 Passos

**Quando oferecer**: 
- Botão "Ver Tour" no menu de configurações
- Sugestão sutil após fechar welcome screen: "Quer um tour rápido?"

**Passos do tour**:
1. **Passo 1**: "Este é o chat. Digite ou use voz para dar comandos."
2. **Passo 2**: "Aqui ficam suas tarefas e atividades. Clique para ver histórico."
3. **Passo 3**: "O Jarvis aprende com você. Ele vai sugerir ações com base nos seus hábitos."
4. **Passo 4**: "Configure credenciais e preferências aqui."

#### Implementação (usando biblioteca shepherd.js ou similar)

```javascript
// tour.js
import Shepherd from 'shepherd.js';

function startTour() {
    const tour = new Shepherd.Tour({
        defaultStepOptions: {
            cancelIcon: { enabled: true },
            classes: 'shepherd-theme-custom',
            scrollTo: { behavior: 'smooth', block: 'center' }
        }
    });
    
    tour.addStep({
        id: 'chat',
        text: 'Este é o chat. Digite ou use voz para dar comandos ao Jarvis.',
        attachTo: { element: '#chat-container', on: 'bottom' },
        buttons: [
            { text: 'Próximo', action: tour.next }
        ]
    });
    
    tour.addStep({
        id: 'tasks',
        text: 'Aqui ficam suas tarefas e atividades. Clique para ver histórico e ações pendentes.',
        attachTo: { element: '#tasks-button', on: 'right' },
        buttons: [
            { text: 'Voltar', action: tour.back },
            { text: 'Próximo', action: tour.next }
        ]
    });
    
    tour.addStep({
        id: 'learning',
        text: 'O Jarvis aprende com você! Ele vai sugerir ações proativas com base nos seus hábitos.',
        attachTo: { element: '#orb', on: 'top' },
        buttons: [
            { text: 'Voltar', action: tour.back },
            { text: 'Próximo', action: tour.next }
        ]
    });
    
    tour.addStep({
        id: 'settings',
        text: 'Configure credenciais, preferências e visualize logs aqui.',
        attachTo: { element: '#settings-button', on: 'left' },
        buttons: [
            { text: 'Voltar', action: tour.back },
            { text: 'Concluir', action: tour.complete }
        ]
    });
    
    tour.start();
}

// Oferecer tour após fechar welcome screen
document.getElementById('welcome-dismiss').addEventListener('click', () => {
    // ... fechar modal ...
    
    setTimeout(() => {
        if (confirm('Quer fazer um tour rápido de 30 segundos?')) {
            startTour();
        }
    }, 1000);
});
```

---

## Onboarding Progressivo: Níveis de Revelação

### Nível 1: Primeira Sessão (0-5 minutos)
- ✅ Welcome screen com exemplos básicos
- ✅ Empty state com sugestões
- ✅ Tooltips básicos ao hover

### Nível 2: Primeira Hora (5-60 minutos)
- ✅ Tour opcional (se usuário clicar "Ver Tour")
- ✅ Dica contextual ao usar funcionalidade pela primeira vez
  - Exemplo: Primeira busca web → "💡 Você pode pedir síntese com 'resuma os resultados'"

### Nível 3: Primeiro Dia (1-24 horas)
- ✅ Notificação de funcionalidades não exploradas
  - "Você sabia? O Jarvis pode tirar fotos da tela e analisá-las."
- ✅ Sugestões baseadas em uso
  - Se usa muito Spotify → "Você pode pedir playlists específicas, tipo 'coloca jazz relaxante'"

### Nível 4: Primeira Semana (1-7 dias)
- ✅ Funcionalidades avançadas reveladas gradualmente
  - Pattern learning: "O Jarvis está aprendendo seus hábitos. Isso ajuda ele a ser mais proativo."
  - Confirmação crítica: Primeira ação destrutiva → "Vou pedir confirmação para ações importantes."

---

## Armazenamento de Estado de Onboarding

```python
# app/storage/user_prefs.py - adicionar flags de onboarding

class UserPrefs:
    def __init__(self):
        self.onboarding_completed: bool = False
        self.tour_completed: bool = False
        self.features_discovered: set[str] = set()  # ['spotify', 'checklist', 'vision', ...]
        self.tips_shown: set[str] = set()  # ['web_search_synthesis', 'voice_activation', ...]
        self.first_session_date: datetime | None = None
    
    def mark_feature_discovered(self, feature: str):
        """Marca funcionalidade como descoberta pelo usuário."""
        self.features_discovered.add(feature)
        self._save()
    
    def should_show_tip(self, tip_id: str) -> bool:
        """Verifica se deve mostrar dica específica."""
        return tip_id not in self.tips_shown
    
    def mark_tip_shown(self, tip_id: str):
        """Marca dica como já mostrada."""
        self.tips_shown.add(tip_id)
        self._save()
```

---

## Métricas de Sucesso

Após implementar onboarding, espera-se:

- **Taxa de abandono reduzida em 40%** (primeiras 24h)
- **Tempo até primeira ação bem-sucedida < 2 minutos** (vs ~10 min sem onboarding)
- **Taxa de descoberta de funcionalidades avançadas aumentada em 60%**
  - Vision, checklist, pattern learning, confirmação crítica
- **Redução de 50% em perguntas de "o que o Jarvis pode fazer?"** (suporte)
- **Aumento de 30% em engajamento semanal** (usuários retornando)
- **NPS de novos usuários aumenta de ~30 para ~60+** (medido em primeira semana)

---

## Checklist de Implementação

### Sprint 3 (4 horas)
- [ ] Criar welcome screen com 6 exemplos clicáveis
- [ ] Implementar empty state com sugestões rotativas
- [ ] Adicionar tooltips em botões principais
- [ ] Sistema de localStorage para `onboarding_completed`

### Sprint 4 (3 horas)
- [ ] Implementar tour interativo opcional (shepherd.js ou similar)
- [ ] Adicionar flags de onboarding em `user_prefs.py`
- [ ] Sistema de tips contextuais (primeira vez usando funcionalidade)
- [ ] Analytics para rastrear progresso de onboarding

### Sprint 5 (2 horas)
- [ ] Revelação progressiva de funcionalidades avançadas
- [ ] Notificações de funcionalidades não exploradas
- [ ] Sugestões personalizadas baseadas em uso
- [ ] Refinamento baseado em feedback de usuários beta
