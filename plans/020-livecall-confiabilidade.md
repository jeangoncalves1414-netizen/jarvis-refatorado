# LiveCall: navegação, erros falados e fragmentação

Diagnóstico: chamada de 10/11/2026, 13h31–13h33, sessão
`d2f88101-51fc-4a15-87f0-daaf73a2e579`. Cinco pesquisas, duas navegações
falhas e nenhuma espera ou abertura do Spotify registrada.

## Correções

1. Separar `browser_agent` (automação visual legada) do serviço `browser`
   (navigate/extract). O contexto nativo não injeta mais um objeto incompatível
   na ferramenta browser; o agente visual continua recebendo sua instância.
2. Validar a resposta nativa antes de entregá-la à voz. Falhas de ferramentas
   têm `speech_summary` curto; o diagnóstico permanece na resposta visual e
   no diário. Eventos SSE de erro também usam aviso conversacional na voz.
3. Acumular segmentos da captura do PC antes de enviar: 1,8 s para uma frase
   completa e 4,5 s para finais claramente incompletos. Nova fala/transcrição
   suspende o envio até receber a continuação. O caminho do navegador também
   retém finais incompletos; PTT mantém o envio ao soltar. Cancelamento e
   encerramento descartam o buffer.
4. Reconhecer pedidos falados com “Olá quero que você…” e “depois de aguardar…”.
   Conferir aberturas explícitas de YouTube/Spotify e esperas contra chamadas
   bem-sucedidas, em ordem. Busca ou consulta de status não contam como abertura.
   O loop pode tentar completar pendências uma vez e não marca sucesso quando
   elas persistem, inclusive no limite de etapas. O caminho nativo também
   informa pedido incompleto. Orientar abertura visível via `web_search/open_url`.

## Validação

- Bateria de 170 testes Python passou, além de 44 subtestes.
- Após reforçar a verificação de destino, 81 testes de política, loop e runtime
  passaram, incluindo a nova regressão de busca sem abertura (há sobreposição
  com a bateria anterior).
- Os 13 cenários Playwright de LiveCall passaram. O teste de fechamento durante
  STT agora usa uma resposta bloqueada até o fechamento, sem corrida de 500 ms.
- Navegação real em Chromium headless até uma página HTTP local: título lido
  corretamente pela BrowserTool.
- TypeScript validado. Build de produção executado ao concluir.

## Limites

Sem reiniciar o app nem interromper a chamada em andamento. As alterações
exigem sair completamente do Jarvis e reabrir para carregar backend e painel.
Não houve teste com voz real, provedor pago ou reprodução no Spotify/YouTube.
A detecção de fim de frase é heurística: não garante entendimento de toda pausa.
A checagem determinística de sequência cobre esperas e aberturas explícitas de
YouTube/Spotify; não é um verificador semântico universal de objetivos. Abrir
uma URL não comprova reprodução de áudio; continuam valendo os verificadores
de efeito e os avisos de resultado não confirmado.
