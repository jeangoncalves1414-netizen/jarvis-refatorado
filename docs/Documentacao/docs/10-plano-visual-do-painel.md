# Plano Visual do Painel

## Objetivo
Criar um painel inspirado no referencial visual extraído dos arquivos de referência, mantendo o visual escuro, premium, moderno e modular, mas adaptado para o novo projeto Jarvis.

## Diretrizes visuais principais

### 1. Tema geral
- fundo preto puro ou quase preto,
- superfícies em cinza muito escuro,
- contraste alto com texto claro,
- acentos em azul elétrico e roxo neon,
- sensação de tecnologia premium e minimalista.

### 2. Paleta de cores
- fundo: `#000000`
- superfície: `#131313`
- superfície secundária: `#1c1b1b`
- superfície elevada: `#201f1f`
- texto principal: `#e5e2e1`
- texto secundário: `#bac9cd`
- azul principal: `#00e0ff`
- roxo secundário: `#9d05ff`
- bordas sutis: `rgba(255,255,255,0.1)`

### 3. Tipografia
- títulos: Sora,
- corpo: Geist,
- labels e metadados: JetBrains Mono.

### 4. Espaçamento
- layout com boas margens,
- cards com padding interno generoso,
- separação visual forte entre seções,
- uso consistente de espaçamento em múltiplos de 8px.

## Estrutura do painel

### Sidebar esquerda
- avatar ou ícone do assistente,
- nome do sistema,
- status de atividade,
- botão principal para nova ação,
- menu de navegação com ícones,
- seção inferior para ajuda e configurações.

### Área principal
- header com título da sessão atual,
- área de conversa ou painel de contexto,
- cards de resumo,
- widgets de atividade,
- módulos de tarefas, memória e automação.

### Subpainel lateral direito ou secundário
- lista de conversas recentes,
- histórico de sessões,
- mensagens rápidas,
- contexto atual.

## Componentes do painel

### 1. Botões
- primários com gradiente azul/roxo,
- secundários com borda azul e fundo translúcido,
- hover com glow sutil.

### 2. Cards
- fundo escuro,
- borda fina,
- leve sombra ao redor,
- padding interno de 24-32px.

### 3. Inputs
- fundo escuro,
- bordas sutis,
- foco com azul elétrico.

### 4. Chips e badges
- pequenos componentes com contraste alto,
- cores de status para ativo, atenção e sucesso.

## Comportamento visual
- transições suaves,
- hover leve,
- micro-interações discretas,
- elementos que parecem tecnológicos e premium.

## Direção de implementação
O painel deve ser implementado em camadas:
1. tema visual central,
2. layout base,
3. componentes reutilizáveis,
4. widgets modulares,
5. integração com o backend do agente.

## Regras de fidelidade ao visual de referência
- não usar cores muito claras,
- manter o visual escuro como base,
- usar azul/roxo como destaque,
- evitar excesso de ornamentação,
- priorizar clareza, contraste e premiumidade.
