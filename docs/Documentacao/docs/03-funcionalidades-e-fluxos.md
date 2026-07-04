# Funcionalidades e Fluxos

## Funcionalidades centrais

### 1. Interação por texto
- o usuário envia uma mensagem ao agente,
- o agente interpreta a intenção,
- o agente decide se precisa usar um módulo ou ferramenta.

### 2. Interação por voz
- entrada por microfone,
- transcrição para texto,
- resposta por voz,
- possibilidade de interrupção e contexto contínuo.

### 3. Visão computacional
- captura de tela ou contexto visual,
- análise da imagem,
- interpretação do que está acontecendo na tela,
- uso para auxiliar o usuário em tarefas visuais.

### 4. Memória persistente
- salvar preferências,
- registrar fatos relevantes,
- lembrar contexto das interações,
- construir uma persona do usuário ao longo do tempo.

### 5. Automação do desktop
- abrir apps,
- manipular arquivos,
- controlar mídia,
- realizar ações simples de produtividade.

### 6. Painel essencial
- resumo da atividade,
- lista de tarefas e metas,
- histórico recente,
- módulos simpáticos e leves.

## Fluxo principal do agente
1. o usuário envia uma mensagem;
2. o sistema gera contexto;
3. o agente identifica intenção;
4. o agente escolhe o módulo ou ferramenta;
5. a ação é executada;
6. o resultado é retornado ao usuário;
7. o estado é persistido na memória.

## Fluxo de decisão do agente
O agente deve levar em conta:
- contexto atual,
- preferências do usuário,
- histórico da interação,
- risco da ação,
- urgência da tarefa,
- necessidade de confirmação.

## Regras de segurança
- ações sensíveis exigem confirmação,
- acesso a arquivos deve ser limitado,
- comandos destrutivos devem ser bloqueados por padrão,
- o agente deve explicar o que vai fazer antes de agir.
