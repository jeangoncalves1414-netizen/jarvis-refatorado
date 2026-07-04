# Comandos e Ferramentas

## Objetivo
Documentar os comandos principais que o agente deve entender e as ferramentas associadas a cada um.

## Categorias de comandos

### 1. Comandos de arquivos
Exemplos:
- listar arquivos,
- abrir pasta,
- criar pasta,
- ler um arquivo,
- escrever em um arquivo.

Ferramentas associadas:
- FileManagerService

### 2. Comandos de produtividade
Exemplos:
- criar tarefa,
- completar tarefa,
- listar tarefas,
- registrar hábito.

Ferramentas associadas:
- ProductivityService
- HabitService

### 3. Comandos de automação
Exemplos:
- abrir app,
- fechar app,
- reproduzir mídia,
- pausar conteúdo,
- ajustar volume.

Ferramentas associadas:
- AppControlService
- MediaControlService

### 4. Comandos de visão
Exemplos:
- analisar tela,
- resumir o que está visível,
- identificar elementos visuais.

Ferramentas associadas:
- VisionService

### 5. Comandos de voz
Exemplos:
- falar resposta,
- ouvir input,
- transcrever áudio.

Ferramentas associadas:
- STTService
- TTSService

## Padrão de comando
Cada ação deve seguir uma estrutura simples:
- intent: o objetivo da ação,
- target: o alvo da ação,
- params: parâmetros opcionais,
- confidence: nível de confiança do agente.

## Exemplo de comando estruturado
```json
{
  "intent": "create_task",
  "target": "productivity",
  "params": {
    "title": "Estudar Python"
  },
  "confidence": 0.95
}
```

## Regras para novos comandos
- usar nomes claros,
- manter comandos pequenos e previsíveis,
- documentar o fluxo de execução,
- manter o módulo responsável isolado.
