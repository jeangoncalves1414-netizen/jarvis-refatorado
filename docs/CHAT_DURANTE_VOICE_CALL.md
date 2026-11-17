# Chat durante a chamada de voz

A fala transcrita aparece no chat assim que é enviada ao agente. Cada trecho recebido pelo stream atualiza o mesmo balão de resposta no chat e nas legendas da chamada. O texto não espera o término da geração nem da reprodução do áudio para aparecer. Atividades de ferramentas também atualizam o turno durante a execução.

Os trechos são uma prévia local: não disparam novos pedidos ao modelo nem gravações repetidas do histórico. Ao concluir, a troca é acrescentada uma vez, usando os metadados finais e as regras existentes de privacidade. Cancelar explicitamente ou encerrar remove a prévia; eventos atrasados não a restauram. Trocar de conversa oculta a prévia e impede inserir a conclusão na conversa seguinte.

Quando uma nova fala interrompe um pedido ainda em andamento, o mesmo balão do usuário permanece durante a pausa. A continuação transcrita é acrescentada a ele, inclusive na captura do PC e quando há vários complementos sucessivos. A resposta parcial antiga é descartada, e a nova requisição atualiza a resposta desse mesmo turno. A conclusão atrasada de uma requisição anterior não pode apagar nem substituir a continuação. Depois que um turno termina, uma nova fala cria outro balão.

Respostas sem trechos intermediários aparecem quando o servidor entrega o texto, ainda antes de terminar a reprodução. A transcrição do usuário continua dependendo do reconhecedor atual; esta mudança não transforma o STT por gravação em transcrição contínua. A síntese de voz mantém sua fila e sanitização existentes.

Validação automatizada: stream aberto com vários trechos, atualização sem duplicação, áudio mantido em reprodução, complementos sucessivos mantendo o elemento do balão, conclusão atrasada de requisições substituídas, cancelamento enquanto aguarda complemento, troca de conversa e ausência de gravação de histórico para turnos públicos. Não foi feita uma chamada com microfone e provedor reais.
