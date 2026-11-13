# Clipboard e contexto — 13/11/2026

## Alterações

- `clipboard_intelligence` entrega o conteúdo pela chave `content`, já aceita por `ToolResult.model_observation()`. O texto deixa de ficar limitado à prévia de 300 caracteres recebida pelo agente. O limite global de 16 mil caracteres dos dados de observação permanece.
- A observação compartilhada inclui ação, provedor, modelo e resultado de conferência. Campos internos arbitrários continuam excluídos.
- `clipboard copy/write` relê o clipboard e compara o texto completo, incluindo espaços e quebras de linha. Retorna `verified=true` somente se os conteúdos forem iguais.
- Se a escrita foi enviada, mas a leitura não confirma, o retorno distingue execução de confirmação e orienta não repetir automaticamente. `ok=true` nesse caso indica comando enviado, não efeito confirmado; `verified=false` registra a incerteza.
- Falha de escrita retorna erro; ação desconhecida não cai mais silenciosamente em leitura.
- A recuperação de sobrecarga após ferramentas preserva os resultados e informa que as ações não foram repetidas, sem recomendar reenviar o pedido. A proteção existente contra reexecução foi mantida.

## Testes

55 testes passaram: clipboard, recuperação Groq, memória, correções desktop e gateway de ações. Três avisos de depreciação de dependências. Os cenários de falha de API e clipboard foram simulados de forma controlada.

Três conversas reais em `scratch/clipboard-controls-live`:

1. Jarvis copiou texto longo; ferramenta retornou `verified=true`.
2. Em sessão nova, sem o código no pedido, `clipboard_intelligence read` permitiu responder corretamente `JARVIS-82741`, localizado após os primeiros 300 caracteres.
3. Jarvis copiou `Jean, clipboard copiado e conferido pelo Jarvis!` e confirmou a leitura de conferência.

A leitura independente pelo Windows (`Get-Clipboard -Raw`) confirmou igualdade exata do texto final. Ele foi deixado no clipboard para o usuário testar com Ctrl+V.

Não houve falha real de provedor nas três conversas desta rodada. A recuperação sem repetição foi validada nos testes automatizados; não é garantia contra duplicações entre pedidos novos e independentes. A precisão visual não foi alterada.
