---
name: qr-reader
description: Habilidade autônoma para detectar e decodificar QR Codes diretamente da tela ou câmera do usuário sob demanda via visão computacional.
---

# 📷 Skill: Leitura Inteligente de QR Code (Tela & Câmera)

Esta habilidade ensina o Jarvis a capturar e decodificar automaticamente QR Codes quando o usuário solicitar no chat.

## 💡 Quando Utilizar

Disparada automaticamente quando o usuário faz solicitações como:
- *"Olha minha tela e lê o QR code"*
- *"Tem um QR code na minha tela, o que tá escrito nele?"*
- *"Olha minha câmera e lê esse QR code"*
- *"Escanear QR code"*
- *"Lê o código QR pra mim"*

## ⚙️ Fluxo de Execução

1. **Se o usuário pedir para ler da TELA**:
   - Execute a ferramenta `qr_reader` com `{"source": "screen"}` OU a ferramenta `vision` com `action: "analyze_screen"` e `prompt: "Identifique e leia qualquer QR code visível na tela"`.
   - Ambas as ferramentas possuem decodificador AST/OpenCV integrado que extrai o texto do QR code automaticamente.

2. **Se o usuário pedir para ler da CÂMERA**:
   - Execute a ferramenta `qr_reader` com `{"source": "camera"}` OU orientar a captura de frame.

3. **Resposta para o Usuário**:
   - Apresente o conteúdo decodificado com clareza em formato Markdown.
   - Se for uma URL (ex: `http://` ou `https://`), ofereça abrir no navegador se o usuário desejar.
   - Se for uma chave Pix, código Wi-Fi ou texto puro, formate adequadamente em bloco de código.
