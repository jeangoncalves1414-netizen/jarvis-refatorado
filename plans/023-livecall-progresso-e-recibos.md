# Fala durante ações e ferramentas separadas da resposta

## Escopo e decisões

- Publicar o início real de cada ferramenta no stream da livecall, antes de chamar sua implementação. Propostas aguardando aprovação não geram anúncio de execução.
- Reutilizar o TTS e a fila de áudio existentes, sem bloquear as ferramentas. Anunciar uma vez por ID; interromper junto com o pedido e descartar anúncios que ficaram atrasados.
- Descrever abertura, pesquisa e espera a partir da ferramenta e dos argumentos efetivos. URLs na fala viram nomes conhecidos ou “o site”; os rótulos usam somente o domínio.
- Manter as verificações de efeito: “Abrindo” não significa “Abri”. Respostas finais de ações confirmadas usam recibos curtos; erros, processos e janelas ficam nos detalhes.
- Colocar a seção recolhida “Usou N ferramentas” abaixo da resposta, também nas legendas da ligação. Exibir operação/alvo, ferramenta, estado, resultado e fontes ao expandir.
- Preservar ID do pedido e recibos quando a livecall acrescenta o turno ao histórico. Não salvar todo o contexto interno como metadados da mensagem.

## Componentes alcançados

Executor e coletor de atividades; orquestrador e loop de ações; fila de áudio e leitura SSE da livecall; persistência do chat; componente compartilhado de ferramentas e modal da ligação; testes Python e Playwright.

## Verificação

- Python: início emitido antes de executar, contexto do listener restaurado, metadados persistidos, alvos sem credenciais, efeito não confirmado sem afirmação de sucesso, falhas nos detalhes.
- Playwright: stream mantido aberto comprova áudio antes da conclusão; eventos repetidos não repetem fala; anúncios atrasados não tocam; recibos separados e recolhidos; mensagens comuns sem ferramentas; regressão de interrupções, captura e chat.
- TypeScript, build e verificação de whitespace.

Resultado: 30 testes Playwright aprovados; 100 casos Python e 44 subtestes aprovados entre a rodada principal e a reexecução da asserção adaptada para diagnósticos no recibo. Após o ajuste final de preservação de rótulos, os 5 testes focados passaram novamente. TypeScript, compilação Python, build e diff-check aprovados. Build mantém aviso já existente de chunks grandes.

## Limites

A primeira fala depende da latência do provedor TTS atual. Uma ação que terminar antes de o áudio ficar pronto pode não ter anúncio intermediário, evitando falar “abrindo” depois de já terminar. Não foi feito teste acústico com microfone/alto-falantes reais. Históricos antigos não são reescritos automaticamente. Nenhuma dependência nova.
