# Sistema de Memória Persistente

## Objetivo
O sistema de memória persistente é a base para transformar o agente em um companheiro digital com personalidade, contexto e continuidade.

## Tipos de memória

### 1. Memória curta
Armazena contexto recente da conversa e do estado atual.
Exemplos:
- mensagem anterior,
- tarefa em andamento,
- contexto da sessão.

### 2. Memória longa
Armazena fatos e preferências que devem sobreviver entre sessões.
Exemplos:
- o usuário gosta de café sem açúcar,
- o usuário trabalha em projeto X,
- o usuário prefere respostas objetivas.

### 3. Memória semântica
Permite recuperar informações por similaridade e contexto, e não apenas por palavra exata.
Exemplos:
- lembrar que o usuário gosta de estudar programação,
- associar tópicos relacionados a produtividade ou finanças.

## Estrutura sugerida

### Entidades
- UserProfile
- MemoryEntry
- Preference
- SessionContext
- InteractionEvent

### Campos principais
- id
- user_id
- type
- content
- created_at
- importance
- source
- tags

## Fluxo de uso
1. o agente recebe uma mensagem;
2. ele busca contexto relevante na memória;
3. ele decide se salva uma nova memória;
4. ele usa essa memória para melhorar a resposta ou a ação;
5. ele armazena o resultado da interação para futuras sessões.

## Regras recomendadas
- memórias devem ser curtas e objetivas,
- preferências devem ser persistidas se forem úteis,
- fatos irrelevantes não devem ser salvos,
- o agente deve poder revisar e consolidar memórias,
- a memória deve ser acessível de forma modular.

## Exemplo de uso
Se o usuário disser:
- "Eu gosto de respostas curtas"

O sistema deve salvar isso como preferência e, em futuras interações, adaptar o estilo do agente.

## Papel do agente com base em interesses do usuário
O agente não deve apenas responder: ele deve aprender com o usuário para:
- priorizar tarefas,
- sugerir ações úteis,
- adaptar comunicação,
- tomar decisões com base em contexto pessoal.
