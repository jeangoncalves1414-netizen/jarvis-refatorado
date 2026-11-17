# Microfone do aplicativo

Em Configurações → Voz e microfone, selecione **Microfone padrão do sistema** ou um dos dispositivos de entrada. Se os nomes não aparecerem, use **Permitir acesso e atualizar microfones**. A lista acompanha conexões e desconexões; a preferência é salva automaticamente.

A escolha vale na próxima captura. Encerre e reabra chamadas ou gravações que já estejam usando o dispositivo anterior. A escuta de ativação contínua passa a usar a escolha quando reabrir sua captura; reiniciar o Jarvis também aplica a preferência.

`/api/settings/mic` guarda o nome e o identificador do navegador. O frontend usa `openMicrophone` para abrir o dispositivo exato. O cache local mantém a escolha disponível na tela bloqueada. A captura nativa resolve o nome para o índice atual, pois índices podem mudar após reconectar equipamentos. Os nomes truncados pelo Windows só são aceitos quando a correspondência é única. Ausência ou ambiguidade resulta em erro, sem abrir outro microfone.

O reconhecimento Web Speech de pronúncia/ditado recebe a faixa de áudio selecionada. Esse caminho exige suporte a [`SpeechRecognition.start(audioTrack)`](https://github.com/MicrosoftDocs/edge-developer/blob/main/microsoft-edge/web-platform/speech-recognition-api.md), disponível no Chrome/Edge de desktop a partir de 135. Navegadores sem esse recurso recebem uma orientação para atualizar ou usar a captura do PC; não se ignora a seleção. Chamadas e cadastros com MediaRecorder não dependem desse recurso.

Os testes cobrem persistência, restauração do padrão, falha ao salvar, desconexão, resolução de nomes/índices e cadastro com microfone específico. A troca entre equipamentos físicos não foi medida nesta alteração.
