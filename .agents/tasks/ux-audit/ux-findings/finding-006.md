## Finding 6: Ausência de Onboarding e Exemplos Visíveis

**Categoria**: UX
**Prioridade**: 🟡 IMPORTANTE

### Problema Atual
O arquivo `app/ui/panel/templates/index.html` (e outros templates) **não contém nenhuma tela de boas-vindas, tooltips ou exemplos de comandos** para novos usuários.

Investigação:
- Linha 1-150 do `index.html`: Apenas estrutura de navegação e orb visual
- Nenhum elemento com ID `welcome-screen`, `onboarding`, `tutorial`, `examples`
- Nenhuma seção de "Comandos Sugeridos" ou "Comece Aqui"

### Impacto no Usuário
- **Curva de aprendizado íngreme**: Usuário novo não sabe por onde começar
- **Funcionalidades ocultas**: Usuário não descobre ferramentas avançadas (vision, timer, checklist)
- **Taxa de abandono alta**: Sem orientação inicial, usuário pode desistir rapidamente
- **Necessidade de documentação externa**: Usuário precisa ler manual ao invés de aprender na prática

### Proposta de Solução
Adicionar sistema de onboarding progressivo:

1. **Welcome Screen na primeira inicialização**:
   - "Bem-vindo ao Jarvis! Aqui estão algumas coisas que posso fazer..."
   - Lista de 5-7 comandos de exemplo clicáveis
   
2. **Tooltips contextuais**:
   - Hover sobre "New Task" → "Tente: 'Abra o Spotify', 'Crie uma checklist', 'Tire uma foto'"
   
3. **Seção de Sugestões no Chat**:
   - Quando chat está vazio, mostrar "Sugestões" com comandos comuns
   
4. **Guided Tour opcional**:
   - Botão "Ver Tour" no menu de configurações
   - Tour interativo de 3-4 passos mostrando funcionalidades principais

### Implementação Estimada
**Complexa** — 4 horas

### Arquivos Envolvidos
- `app/ui/panel/templates/index.html` (adicionar modal de welcome)
- `app/ui/panel/static/js/panel.js` (lógica de onboarding)
- `app/storage/user_prefs.py` (salvar flag `onboarding_completed`)
- `app/ui/panel/static/css/panel.css` (estilos do onboarding)

### Exemplo de Código
```html
<!-- Adicionar ao index.html após o nav -->
<div id="welcome-modal" class="fixed inset-0 bg-black/70 z-50 hidden items-center justify-center">
    <div class="bg-surface-container rounded-xl p-8 max-w-2xl mx-4 shadow-2xl">
        <h2 class="text-headline-lg font-headline-lg text-primary-fixed-dim mb-4">
            👋 Bem-vindo ao Jarvis
        </h2>
        <p class="text-body-md text-on-surface mb-6">
            Seu assistente pessoal de automação. Aqui estão algumas coisas que posso fazer:
        </p>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all">
                <span class="material-symbols-outlined text-primary-fixed-dim">music_note</span>
                <span class="ml-2">"Toca Bohemian Rhapsody no Spotify"</span>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all">
                <span class="material-symbols-outlined text-secondary-fixed-dim">checklist</span>
                <span class="ml-2">"Cria uma checklist de compras"</span>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all">
                <span class="material-symbols-outlined text-tertiary-fixed-dim">camera</span>
                <span class="ml-2">"Tire uma foto da tela"</span>
            </button>
            
            <button class="example-command text-left p-4 rounded-lg border border-outline-variant hover:bg-primary-fixed-dim/10 transition-all">
                <span class="material-symbols-outlined text-primary-fixed-dim">timer</span>
                <span class="ml-2">"Timer de 5 minutos"</span>
            </button>
        </div>
        
        <button id="welcome-dismiss" class="w-full py-3 px-6 bg-primary-fixed-dim text-on-primary-fixed rounded-lg hover:bg-primary-fixed transition-all">
            Começar
        </button>
    </div>
</div>

<script>
// Verificar se é primeira vez
if (!localStorage.getItem('onboarding_completed')) {
    document.getElementById('welcome-modal').classList.remove('hidden');
    document.getElementById('welcome-modal').classList.add('flex');
}

document.getElementById('welcome-dismiss').addEventListener('click', () => {
    localStorage.setItem('onboarding_completed', 'true');
    document.getElementById('welcome-modal').classList.add('hidden');
});

// Clicar em comando exemplo preenche o input do chat
document.querySelectorAll('.example-command').forEach(btn => {
    btn.addEventListener('click', () => {
        const text = btn.querySelector('span:last-child').textContent.replace(/"/g, '');
        document.querySelector('#chat-input').value = text;
        document.getElementById('welcome-modal').classList.add('hidden');
        localStorage.setItem('onboarding_completed', 'true');
    });
});
</script>
```
