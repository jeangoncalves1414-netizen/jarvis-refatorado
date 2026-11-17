# Correções após o teste de conversa de 15/11/2026

O chat `e0a3d0ee-3614-4825-942a-279e2f187e61` mostrou respostas faciais em formato de relatório, perda da referência à câmera em “e agora quem você vê”, recadastro não iniciado com palavras extras e respostas negando recursos existentes. O histórico e o cadastro existente foram preservados.

## Conversa e cadastro

- Pedidos de cadastro aceitam as frases do chat, inclusive “tá quero me registrar novamente como admin aqui no aplicativo aqui” e “Tenta de novo usar ferramenta para registro de admin”. Não é necessário copiar uma frase fixa.
- Apresentações como “esse é o Pedro” e “te apresento minha amiga Ana” oferecem cadastro; a aceitação vem antes da escolha de rosto, voz ou ambos. O cadastro administrativo continua exigindo senha no campo protegido.
- Perguntas de continuidade sobre a câmera usam a última solicitação do chat e capturam imagens novas. Trocar de chat limpa o contexto temporário. Nenhum painel abre sem pedido explícito.
- O reconhecimento facial continua local. O modelo de conversa recebe apenas o pedido e os nomes/rostos desconhecidos medidos para formular uma resposta natural, sem histórico privado ou embeddings. Sem provedor, a observação local ainda é respondida.
- Os prompts distinguem recursos do aplicativo das ferramentas autorizadas no pedido atual. Visitantes não recebem confirmação de execução de comandos que não podem executar.

## Voz e microfone

- Em Configurações → Voz e microfone, “Microfone do aplicativo” permite escolher o padrão do sistema ou um dispositivo específico. A escolha é salva para chamada, cadastro, desbloqueio por voz, ditado, pronúncia e capturas nativas. A captura já aberta deve ser encerrada e reaberta. Dispositivos específicos indisponíveis não são substituídos silenciosamente pelo padrão.
- A leitura mostra o volume recebido e prepara o leitor antes de iniciar a gravação. O leitor local preserva frases finalizadas antes de pausas, além do último trecho; a validação continua exigindo 80% das palavras e uma amostra vocal válida.
- A extração de características usa escala PCM de 16 bits e janela Hamming, conforme a [implementação oficial do WeSpeaker](https://github.com/wenet-e2e/wespeaker/blob/master/wespeaker/bin/infer_onnx.py). O código anterior usava áudio normalizado sem essa escala e a janela padrão da biblioteca. Recomenda-se refazer uma vez a referência de voz após reiniciar o Jarvis; os registros anteriores não foram apagados automaticamente.
- Os modelos são preparados quando a identificação é ativada. A inferência continua paralela à transcrição, mas pode aguardar até 2 segundos adicionais, em vez de descartar o resultado após 350 ms. Esse tempo é um limite, não uma espera fixa; ausência, ambiguidade ou expiração continuam sem acesso privado.
- Pequenas pausas entre segmentos do mesmo locutor local não fragmentam a referência em amostras curtas demais. Trechos de pessoas diferentes não compartilham autorização.
- A espera adicional na interface após um fim de fala confirmado pelo backend passou de 250 para 40 ms. O tempo de transcrição, geração de resposta e síntese ainda depende dos provedores. Não foi medido ganho total em uma chamada real.
- A chamada mostra a identidade reconhecida no trecho ou informa que a voz ainda não foi reconhecida. Os diagnósticos registram também motivo, similaridade e tempo de espera do reconhecimento.

## Verificação prática

Reinicie o Jarvis, refaça a voz com o microfone escolhido e fale normalmente por alguns segundos. Confira o nome mostrado na chamada. Teste novamente com outra pessoa: ela não deve herdar a identificação do administrador. Depois peça uma observação das câmeras, diga “e agora quem você vê” e apresente alguém para testar a oferta de cadastro.

Os testes de regressão usam áudio/identidades simulados e câmeras de teste. Eles verificam os fluxos e a autorização, mas não medem a precisão biométrica da voz real do proprietário nem a latência total com os dispositivos físicos.
