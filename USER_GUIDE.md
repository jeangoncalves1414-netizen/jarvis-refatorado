# Guia do Usuário - Jarvis

## O que o Jarvis pode fazer?

### 🎯 Automação Windows
- **Abrir aplicativos**: Abra qualquer app instalado no Windows
- **Controlar janelas**: Focar ou fechar janelas específicas
- **Gerenciar arquivos**: Mover, copiar e organizar arquivos em lote

### 👁️ Visão e Web
- **Analisar tela**: Entenda o que está na sua tela usando IA
- **Automação web**: Navegue em sites, clique em botões, preencha formulários

### 📊 Sistema
- **Agendamento**: Programe tarefas recorrentes
- **Monitoramento**: Acompanhe a saúde do sistema
- **Configurações**: Gerencie preferências persistentes
- **Multi-usuário**: Suporte para perfis de usuários diferentes

### 🛠️ Ferramentas Avançadas
- **Code Helper**: Gere, explique e refatore código
- **Image Generator**: Crie imagens com IA
- **Hacker Mode**: Execute scripts de automação avançada
- **Workflow**: Cadeie múltiplas ferramentas em sequência
- **MCP**: Integre com serviços externos via protocolo MCP
- **Dev Agent**: Assistente especializado em desenvolvimento
- **Proactive Agent**: Sugestões proativas baseadas em contexto

### 🎵 Produtividade
- **Spotify**: Controle sua música
- **WhatsApp**: Envie mensagens
- **Clipboard**: Gerencie área de transferência
- **Timer**: Temporizadores e alarmes
- **Web Search**: Pesquise na internet
- **Whiteboard**: Quadro interativo para anotações

### 📚 Educação
- **Tutor**: Sistema de aprendizado com flashcards
- **Feynman**: Técnica de explicação simplificada
- **ENEM**: Banco de questões para estudo

### 🔒 Segurança
- **Rate Limiting**: Controle de chamadas para evitar abuso
- **Guardrails**: Bloqueio de repetições e loops infinitos
- **Critical Confirm**: Confirmação para ações perigosas

### 🧠 Memória Inteligente
- **Expiração automática**: Memórias antigas são removidas após 90 dias
- **Ranking de importância**: Memórias importantes têm prioridade
- **Contexto temporal**: Jarvis sabe quando algo foi dito
- **Limpeza de duplicatas**: Remove memórias repetidas automaticamente

### 🎤 Voice Nativo
- **Whisper STT**: Transcrição offline de voz para texto
- **Wake Word**: Detecta "Jarvis" automaticamente
- **Hands-free**: Use o Jarvis sem teclado/mouse

### 🤖 Proatividade
- **Pattern Learner**: Aprende seus hábitos
- **Sugestões inteligentes**: Jarvis antecipa suas necessidades
- **Aprendizado contínuo**: Melhora com o tempo

### 📅 Integrações Windows
- **Calendário**: Gerencie eventos e lembretes
- **Notificações**: Alertas do Windows 10/11
- **Tray Icon**: Acesso rápido pela bandeja

### 💻 LLM Local
- **Ollama**: Use modelos locais (privacidade total)
- **Offline**: Funciona sem internet

---

## Exemplos de Pedidos

### Automação Windows
```
"Abre o Chrome"
"Abre o Notepad e o Spotify"
"Fecha a janela do Bloco de Notas"
"Foca na janela do Visual Studio"
"Move todos os arquivos .txt da pasta Downloads para Documentos"
"Copia todas as imagens da pasta Imagens para Backup"
```

### Visão e Web
```
"O que está na minha tela agora?"
"Analisa essa captura de tela e me diga o que fazer"
"Abre o site do Google"
"Clica no botão de login"
"Preenche o formulário com meu nome"
"Tira um screenshot da página"
```

### Sistema
```
"Agenda um backup para rodar a cada hora"
"Verifica se o sistema está saudável"
"Salva a configuração atual"
"Cria um novo usuário chamado Maria"
"Lista todos os usuários"
```

### Ferramentas Avançadas
```
"Gera uma função Python para ordenar uma lista"
"Explica esse código para mim"
"Refatora essa função para ser mais eficiente"
"Cria uma imagem de um gato no espaço"
"Executa o script de backup"
"Roda o workflow de deploy"
"Revisa esse código e aponta bugs"
"O que você sugere que eu faça agora?"
```

### Produtividade
```
"Toca a próxima música no Spotify"
"Pausa o Spotify"
"Envia 'Oi' para o João no WhatsApp"
"Copia o texto selecionado"
"Cola o conteúdo da área de transferência"
"Define um timer de 10 minutos"
"Pesquise sobre Python na internet"
"Adiciona 'Revisar código' ao quadro"
"Limpa o quadro"
```

### Educação
```
"Salva meu progresso no estudo de Python"
"Cria um flashcard sobre listas em Python"
"Explique o conceito de recursão como se eu tivesse 10 anos"
"Salva essa questão do ENEM para revisar"
"Mostra as questões salvas do ENEM"
```

### Memória Inteligente
```
"Lembre que prefiro usar Chrome"
"O que eu te disse semana passada sobre meu projeto?"
"Esquece essa preferência"
```

### Calendário
```
"Adiciona reunião às 14h hoje"
"Mostra meus eventos de hoje"
"Quais lembretes tenho para as próximas 2 horas?"
"Cancela a reunião das 14h"
```

### Arquivos
```
"Lista os arquivos da pasta Downloads"
"Cria uma pasta chamada Projetos"
"Deleta o arquivo teste.txt"
"Renomeia arquivo1.txt para projeto_final.txt"
"Move o relatório.pdf para a pasta Documentos"
```

---

## Como Usar

### Via Interface Web
1. Inicie o servidor: `python -m app.main --demo`
2. Acesse `http://localhost:8000` no navegador
3. Digite seus comandos no chat

### Via Linha de Comando
```bash
python -m app.main --demo
```

### Via API
```python
from app.agent.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()
result = orchestrator.process("Abre o Chrome")
```

---

## Dicas

- **Seja específico**: "Abre o Chrome" funciona melhor que "Abre navegador"
- **Use contexto**: "Move os arquivos da pasta Downloads" é mais claro que "Move arquivos"
- **Combine comandos**: "Abre o Chrome e vai para google.com"
- **Peça ajuda**: "O que você pode fazer?" lista funcionalidades disponíveis

---

## Limitações

- Algumas funcionalidades requerem dependências opcionais (ChromaDB, Playwright, etc.)
- Automação web funciona melhor em sites estáticos
- Visão requer API key do Gemini
- Automação Windows é específica para Windows 10/11
- Voice nativo requer microfone e dependências de áudio
- Ollama requer instalação separada do Ollama
- Tray icon requer Windows

---

## Próximos Passos

- Configure suas API keys no arquivo de configuração
- Explore o painel web para funcionalidades visuais
- Crie workflows personalizados para tarefas recorrentes
- Configure o sistema de multi-usuário se compartilhar o Jarvis
