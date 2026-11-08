# Decisões e ideias do produto

> Registro durável das decisões da usuária e das ideias adiadas. Leia junto com [PROJECT_CONTINUITY.md](PROJECT_CONTINUITY.md) e [PENDENCIAS_DO_PAINEL.md](PENDENCIAS_DO_PAINEL.md). A mensagem mais recente da usuária sempre prevalece.

## 2026-11-07: prioridades depois do lote 1

### Ordem geral

- **Desktop primeiro, APK depois.** O APK abre o mesmo painel e usa o mesmo backend, então terminar o desktop beneficia os dois.
- O painel novo criado pelo Codex (6 e 7/11) foi aprovado pela usuária ("muito melhor que o anterior"). A base é ele.
- Lote 1 (em andamento em 7/11): interface nova servida pelo app desktop, risco por operação em `system_control` e `open_windows_app`, correções de links quebrados. Relatório em `.agents/tasks/desktop-batch1/report.md`.
- Análise de paridade com o painel antigo, o Projeto AI e as referências: `.agents/tasks/desktop-feature-parity/report.md`.

### Decidido

| Tema | Decisão |
|---|---|
| Palmas | **Opcional, desligado por padrão**, com chave para ligar e desligar. A usuária configura padrões de palma (quantidade e ritmo; calibrar com o próprio som) e associa cada padrão a um comando pré-configurado. Um padrão pode disparar um único comando ou uma sequência. |
| Rotinas agendadas | Sim. Usar o APScheduler já instalado. Cada disparo cria um pedido na Central. |
| Brilho da tela | Sim, na área de controles do PC. "Quanto mais controle melhor." **Entregue (7/11, lote 2):** janela "Controles do PC", `/controles`. |
| Finanças | Sim, como módulo. **Entregue (7/11, lote 2):** janela Finanças, `/financas` e `/gastos`. |
| Comandos com barra (`/`) | Voltam, mas sem poluir a tela: o menu só aparece ao digitar `/`, com busca, no estilo Slack/Notion. Nada de fileira fixa de botões como no Projeto AI. **Entregue (7/11, lote 2):** registro único de comandos, paleta e menu `/` locais. |
| Bloqueio de tela | Sim (equivalente a Win+L), na área de controles do PC. Risco baixo. **Entregue (7/11, lote 2):** botão com confirmação na janela e operação `lock_screen`. |
| Módulos como janelas | **Aprovado** com as quatro regras abaixo. **Entregue em 7/11 (lote 2):** gerenciador de janelas, Finanças, Controles do PC e ferramenta `open_window`. Faltam as janelas de treino, diário, hábitos e demais do Life OS. |
| Orbe | **Fora.** A usuária não quer a orbe. A regra `.agents/rules/jarvis_visual_canonical.md` fica obsoleta, e a verificação da orbe deixa de bloquear builds. Os componentes da orbe ficam no código por enquanto, sem esforço extra. |
| Personagem 3D | Ideia futura, **última prioridade**. Não planejar agora. |
| Sincronização na nuvem | **Tudo sincronizado no Supabase**, incluindo chaves de API, configurações, perfil do agente, memórias, notas, tarefas, metas e registros do Life OS e de finanças (decisão de 7/11). A proteção é por login e Row Level Security: cada conta só lê a própria linha (`supabase/migrations/202609200001_evolute_snapshots.sql`). A migração precisa estar aplicada no projeto Supabase. **Entregue (7/11, lote 2):** mesclagem por campo e snapshot com dados do backend; remoções ainda não se propagam. Ficam fora da nuvem só os caches, logs e o journal de ações, que é local de cada máquina. |
| Registro manual sem IA | **Requisito.** Com o modelo ou o provedor indisponível, a usuária precisa conseguir abrir qualquer janela e registrar à mão gastos, treinos, diário etc. do dia, sem perder o registro. **Entregue para Finanças e Controles do PC (7/11, lote 2);** treino, diário e demais ainda não têm janela. |

### Proposta de arquitetura: um registro de comandos, vários gatilhos

Palmas, rotinas agendadas, comandos com barra, paleta (Ctrl+K) e frases de voz são formas diferentes de disparar a mesma coisa. Proposta para o lote 2:

- **Comando/Rotina**: uma ação ou sequência de ações salva, que sempre passa pelo Action Kernel (aprovação, histórico, cancelamento).
- **Gatilhos**: horário (cron), padrão de palmas, `/comando`, paleta, frase de voz, botão.
- Gatilhos sem confirmação humana (palmas, horário) só executam direto ações de risco baixo ou já autorizadas por escopo. Ação de risco alto vira proposta e espera aprovação.

### Proposta: módulos como janelas abertas sob demanda (em vez de seções fixas)

Ideia da usuária: em vez de uma seção para cada área da vida, pedir ao agente ("me mostra meus gastos", "abre as anotações") e ele abre uma janela com os dados reais, onde dá para consultar, criar e editar. Áreas: hábitos, rotina, tarefas com ações agendadas, saúde mental, saúde física, treino, finanças, vícios e o resto do Life OS.

Recomendação (aceita a ideia, com quatro regras):

1. **Janela flutuante dentro do app**, não janela do Windows. No desktop: arrastar, redimensionar, maximizar. No celular: folha em tela cheia. Assim funciona igual nos dois.
2. **Toda janela também abre sem IA**, pela paleta ou por `/comando`. Abrir pelo agente custa uma chamada ao modelo e falha se o provedor estiver fora.
3. **O agente escolhe entre janelas prontas e preenche os parâmetros** (filtro, período, tipo de gráfico), por uma ferramenta do tipo `abrir_janela(id, parametros)`. Ele não gera a interface nem código de tela. Motivo: estabilidade (o projeto já teve regressões com mudanças amplas de interface), segurança e testes.
4. **Os números vêm da API, não do texto do modelo.** Em finanças e saúde, a janela mostra o registro real; o modelo pode resumir, mas não inventar valores.

**Abrir e registrar sem IA (requisito confirmado em 7/11):**

- Formas de abrir que não passam pelo modelo: comando de texto pronto no chat (`/gastos`, `/treino`, `/diario`), interpretado pelo próprio app; paleta (Ctrl+K); botão ou atalho de teclado; gatilho de rotina ou palma.
- O chat precisa reconhecer esses comandos localmente, antes de chamar o modelo, para funcionar mesmo com o provedor fora.
- Formulários de registro gravam direto pela API do módulo, sem depender do agente.
- Rascunho salvo localmente até a gravação ser confirmada. Se a gravação falhar, o rascunho fica preservado e o app tenta de novo; o registro do dia não se perde.
- Cada janela mostra se está sem IA ("modo manual") de forma discreta, sem bloquear o uso.

Janelas carregam sob demanda (lazy-load), o que deixa o app mais leve. Uma janela pode ser "fixada" para uso longo (editor de notas, sessão de estudo).

**Personalizar o painel em tempo real:** por enquanto, não deixar o agente reescrever a interface. Mais tarde, permitir que a usuária salve visões e layouts (janelas fixadas, filtros salvos).

O Life OS separado (`/evolute/`, com anti-vício, treino, leitura, mente, Pomodoro e SOS) é a fonte desses módulos e pode migrar aos poucos para esse formato.

### Pendente de decisão (lembrar a usuária)

- **Gemini Live.** A usuária gostou da ideia, talvez como um agente separado. O problema: o Gemini Live usa as próprias vozes, não a voz da Fish Audio. Uma alternativa a verificar na hora: pedir a resposta em texto ao Live e falar com a Fish, mas isso perde parte da baixa latência, que é a vantagem do Live. **Lembrar a usuária de decidir.**
- **Tela de notas.** A usuária ainda não sabe. Se entrar, seguir o formato de janela com editor estilo Obsidian/Notion. Candidatos open source a avaliar (conferir licença antes): TipTap, BlockNote, Lexical, Milkdown. O cofre atual é Markdown (`app/services/memory_vault.py`), então um editor com Markdown nativo encaixa melhor.

### Ideias adiadas

- **Busca de lugares (Google Maps).** O agente procura lugares para a usuária ir. Opções: Google Places API (melhores dados no Brasil, exige chave e tem custo por uso) ou OpenStreetMap/Overpass (grátis, dados mais fracos). Encaixa como janela com mapa e lista. Chave fica no backend.
- **Clones open source de apps conhecidos** (editores estilo Adobe, OBS e outros) como referência para dar novas habilidades ao agente. A usuária pode pedir uma pesquisa das opções mais úteis depois.

### Open Interpreter: avaliado em 2026-11-07

Situação atual: a versão original em Python virou fork mantido pela comunidade; em meados de 2026 o projeto foi reescrito em Rust, sob Apache-2.0, como agente de programação no terminal com sandbox do sistema operacional ([Learn AI wiki](https://ai.miraheze.org/wiki/Open_Interpreter), [fork comunitário](https://github.com/endolith/open-interpreter)).

Recomendação: **não adotar como framework do agente.** Ele é um agente completo, com o próprio ciclo de decisão. Colocá-lo dentro do Jarvis criaria dois "cérebros" e contornaria o Action Kernel, que é a base do controle com aprovação e histórico. O Jarvis já tem execução de scripts com recibo e terminal com aprovação. O que vale estudar é o sandbox de sistema operacional da versão Rust, para isolar scripts do agente. Mais tarde, ele pode entrar como um especialista externo para tarefas de programação, chamado como uma ferramenta que passa por aprovação.
