# Congelamento, rascunhos e barra lateral

## Causa identificada

A pausa do depurador no navegador com serviços/dados reais encontrou o loop em
`MessageContent.tsx`, dentro de `parseBlocks`. Linhas como uma tabela sem
separador (`| texto |`), `1 objetivo` ou um cabeçalho vazio não eram reconhecidas
como bloco nem consumidas pelo parágrafo. O índice não avançava e o renderizador
ocupava a thread indefinidamente. Isso explica congelamento ao selecionar uma
conversa, sem falha correspondente no servidor Python.

O parser agora consome como texto toda linha não reconhecida. A regressão cobre
conteúdo incompleto, cancelamento e confirmação de exclusão com API simulada.
Nenhuma conversa real foi excluída nos testes.

## Outras alterações

- Rascunhos locais separados por sessão, escritos a cada alteração, restaurados
  ao trocar de conversa e recarregar. Nova conversa não apaga o rascunho anterior.
- Perfil persistente do WebView no caminho de inicialização realmente usado pelo
  desktop. Antes esse caminho usava um diretório temporário.
- Divisória verticalmente arrastável entre navegação e conversas, com altura salva
  e ajuste pelas setas do teclado; navegação mais compacta e rolagens separadas.
- Respostas atrasadas ao selecionar sessões não substituem a seleção mais recente.
- Modo diagnóstico opt-in `JARVIS_DESKTOP_DEBUG=1` para inspecionar o WebView;
  desativado na execução normal.

Evidências de diagnóstico em `scratch/frozen-desktop-stack.txt`,
`scratch/real-chat-stack.log` e `scratch/real-chat-source.log`.
Os testes da interface ficam em `frontend/tests/chat-experience.spec.ts`.

Validação final: build Vite e TypeScript; 15 cenários de interface (14 passaram
na rodada conjunta; standby passou na reexecução, junto com o caso de Markdown
ampliado para confirmar exclusão simulada). No WebView nativo, conexão CDP,
captura de tela e seleção das quatro conversas reais concluíram sem travar,
conforme `scratch/native-chat-final.log`. Antes da correção a conexão completa e
a captura não concluíam. O navegador com os serviços reais também voltou a
carregar e capturar a página (`scratch/real-chat-fixed.log`).

Limites: rascunhos são texto local a este perfil, sem sincronização entre máquinas
ou persistência de anexos. Se o armazenamento do navegador estiver indisponível,
o texto permanece apenas em memória. Não foi adotada a hipótese de GPU como causa.
