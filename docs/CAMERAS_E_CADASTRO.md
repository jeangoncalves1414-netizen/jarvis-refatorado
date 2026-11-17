# Câmeras e cadastro de pessoas

Para a política atual de texto, privacidade na voz e níveis de comandos, veja [Histórico, contexto e níveis](HISTORICO_CONTEXTO_E_NIVEIS.md).

## Usar a câmera USB

1. Reinicie o backend após atualizar o código e recarregue o painel.
2. No chat ou na ligação, peça **“o que você vê na câmera?”**. As câmeras conectadas e habilitadas são descobertas automaticamente. Aceite a permissão de câmera do navegador quando solicitada.
3. Jarvis captura um quadro de cada câmera e responde por número. Não abre o painel nem exige selecionar uma câmera ou repetir a pergunta em outro campo.
4. Para limitar o pedido, diga **“olha na câmera 1”** ou **“quem aparece na câmera da sala?”**. Nomes e dispositivos desativados podem ser ajustados em **Configurações → Câmeras**.
5. Para ver os controles, peça **“abra o painel de câmeras”** ou clique no botão Câmeras.

O painel captura um quadro das câmeras solicitadas. Pedidos de identificação são comparados localmente aos rostos cadastrados; uma pessoa sem correspondência confiável é desconhecida. Perguntas visuais gerais seguem o provedor de visão configurado. A captura depende da permissão e da disponibilidade do dispositivo. Uma câmera explicitamente solicitada que esteja ausente não é substituída por outra. Números permanecem estáveis enquanto o navegador conservar o catálogo e o identificador do dispositivo.

Neste computador, o Edge também lista **DroidCam Video** e **OBS Virtual Camera**, além de **USB Camera (5258:4a55)**. Desative fontes virtuais que não estiver usando. Uma câmera sem imagem ou sem acesso é informada como indisponível; isso não significa que a cena esteja vazia.

Esta versão lista webcams locais. Câmeras IP/RTSP e descoberta na rede ainda não estão implementadas.

## Preparar Jean

O nome e o papel de administrador, sozinhos, não são amostras biométricas. Diga **“Olá Jarvis, sou Jean, pode me registrar como admin?”**. O nome é aproveitado da apresentação. Digite somente a senha de desbloqueio no campo protegido; depois escolha por voz **rosto**, **voz** ou **os dois**. O cadastro prepara os modelos locais necessários e ativa a identificação nas ligações quando uma voz é registrada. Não é necessário apagar o administrador existente.

O chat de texto desbloqueado pertence ao proprietário e não exige confirmação facial para consultar seu histórico. Nas ligações, a evidência de voz é obtida novamente a cada fala: apenas a voz reconhecida do administrador principal libera dados pessoais. O rosto de alguém presente no fundo não prova quem está falando.

## Apresentar Jamille

Digite ou diga **“Jarvis, quero te apresentar minha irmã Jamille”**.

1. Jarvis cumprimenta e pergunta se a pessoa quer registrar **rosto**, **voz** ou **os dois**. A escolha autoriza as modalidades indicadas.
2. Qualquer pessoa pode iniciar o próprio cadastro, sem senha administrativa. O perfil criado é sempre de usuário comum, sem permissões privadas. Também é possível pedir “Jarvis, quero me cadastrar” e informar o nome no diálogo.
3. Quando a escolha inclui voz, ela vem primeiro. Jarvis orienta com o mesmo provedor e voz configurados para o assistente, sem usar a síntese do navegador. A gravação começa ao terminar a instrução. Jamille lê o texto; as palavras ficam verdes. O servidor exige pelo menos 80% e verifica a amostra novamente antes de avançar. Há botões de início/conclusão como alternativa; não são obrigatórios no fluxo normal.
4. Somente rosto pula inteiramente a leitura e a gravação de voz. Somente voz salva ao validar a leitura. Ambos avança para a câmera após a voz.
5. A câmera é selecionada automaticamente por presença de um único rosto e movimento entre quadros. Se não houver rosto detectável, usa a atividade visual como alternativa. Siga as três orientações faladas: frente, um lado e lado oposto. A captura espera terminar cada instrução. O seletor continua disponível para corrigir a escolha quando necessário.
6. Jarvis só anuncia sucesso depois de salvar todas as referências. Ao concluir ou cancelar, a captura de cadastro é encerrada.

O diálogo escuta localmente o nome e escolhas como “rosto”, “voz” e “os dois”, após terminar cada instrução. Também funciona sem ligação ativa. A apresentação pode incluir o nome: **“Olá Jarvis, sou Jamille, quero me cadastrar”**. Se faltar o nome, Jarvis pergunta e recebe a resposta por voz. Durante o cadastro, a captura da ligação fica pausada e retoma ao encerrar. A escuta fica desligada durante a digitação da senha administrativa. Os comandos e a senha não são enviados ao chat. A conclusão fecha o diálogo depois da confirmação falada.

As referências biométricas são vetores locais. O áudio bruto do cadastro guiado não é persistido. O cadastro pendente expira em dez minutos; cancelar descarta as referências ainda não salvas. Se faltar um modelo, houver mais de uma pessoa/voz ou a leitura falhar, a interface mostra o erro e permite tentar novamente. A primeira preparação de modelos pode precisar de internet.

## Refazer seu cadastro de administrador

Digite ou diga **“Jarvis, quero me registrar como admin”** ou **“quero me cadastrar novamente como administrador”**. O painel abre um campo de senha mascarado, no estilo da tela de desbloqueio. Use a **senha de desbloqueio do aplicativo**. Não é necessário lembrar a antiga senha separada do perfil. Se ainda não houver administrador, informe seu nome no diálogo; configure antes a senha de abertura se ela estiver desativada. A senha é enviada somente à verificação local de cadastro; não é enviada ao modelo nem gravada no chat.

Após validar a senha, Jarvis pergunta quais modalidades registrar e conduz a coleta. O recadastro substitui as referências de voz e rosto do administrador existente, mantendo seu identificador, nome, senha, memórias e permissões. Escolher somente uma modalidade remove as referências antigas da outra. Confirmações biométricas anteriores deixam de autorizar novos pedidos.

## Falas consecutivas e tempo de resposta

A identificação da chamada segmenta o áudio e compara separadamente trechos de pessoas que falam uma após a outra. Quando detecta múltiplos locutores, também transcreve os trechos para vincular nomes às falas. Janelas de áudio não reutilizam números locais de locutor como identidade. Trechos muito curtos (menos de dois segundos), sobrepostos ou incertos ficam desconhecidos. Se o navegador juntar segmentos do microfone, as evidências são reunidas no servidor e consumidas uma única vez. Uma fala misturada não herda o acesso administrativo de um participante.

O atraso fixo de detecção por silêncio caiu de 3 s para 800 ms. A espera adicional após uma transcrição completa caiu para 150 ms; frases aparentemente incompletas recebem 1,8 s. No detector neural, finais confiáveis podem encerrar após 800 ms; a alternativa sem previsão espera 2 s, e uma previsão incerta espera até 3 s. Isso reduz esperas locais; transcrição, modelo de conversa e síntese ainda têm seus próprios tempos. Uma gravação com vários locutores exige processamento extra.

O perfil atual continua válido até a conclusão. Cancelamento, leitura inválida ou falha ao salvar não deixam você sem administrador. Não é preciso apagar o perfil antes. Esse fluxo não altera as biometrias cadastradas separadamente para desbloquear o aplicativo; elas são gerenciadas nas configurações de bloqueio.

## Permissões e limites

Novos usuários começam como visitantes. Em **Identidade → Níveis de acesso por voz**, o proprietário usa a senha de desbloqueio para escolher visitante, usuário autorizado ou administrador delegado. Esses níveis liberam comandos específicos, sem conceder acesso às conversas e memórias pessoais do proprietário. Consulte a lista em [Histórico, contexto e níveis](HISTORICO_CONTEXTO_E_NIVEIS.md).

Quando existe um administrador cadastrado, pessoas desconhecidas ou sem permissão podem conversar normalmente por texto e voz. O modelo recebe somente a conversa comum recente, mantida temporariamente em memória, sem o histórico, as memórias, as instruções pessoais ou as ferramentas do proprietário. Esses turnos não são acrescentados ao histórico privado pelo chat. O contexto comum é limitado a 20 mensagens por conversa e pode ser descartado ao reiniciar o backend. Observação da câmera e cadastro guiado continuam com fluxos próprios. Informar “sou Jean” ou enviar um identificador de perfil não autentica ninguém.

Essa checagem protege o fluxo de resposta do assistente. Ela não substitui o bloqueio do aplicativo, as permissões do Windows ou a proteção dos arquivos locais. O painel já desbloqueado continua mostrando seus dados. A biometria implementada não tem prova de vida nem proteção validada contra foto, vídeo ou áudio reproduzido. Movimentar a cabeça serve para coletar referências, não é garantia de prova de vida.

## Validação

Na atualização de 14/11/2026, passaram **151 testes Python** de identidade, privacidade, cadastro, segmentação, atribuição de falas, voz e bloqueio. Também passaram **78 cenários distintos de interface**, em execuções focadas, cobrindo câmera sem painel, múltiplas câmeras, escolha por movimento, cadastro por voz, senha administrativa, retomada da chamada, interrupções e cancelamentos. A checagem TypeScript e a compilação de produção foram executadas. Os números se referem a testes automatizados; não são uma medida de precisão biométrica.

Os testes de interface usam webcam e áudio simulados ou respostas controladas do reconhecimento. Separadamente, em 13/11/2026, o Edge instalado abriu especificamente **USB Camera (5258:4a55)** por `getUserMedia` e recebeu vídeo real de **640×480**, sem salvar a imagem. A captura nativa via Media Foundation também recebeu um quadro. O Chromium headless fornecido pelos testes retornou `NotSupportedError` com o hardware real; isso não ocorreu no Edge.

Ainda é necessário validar o reconhecimento com referências reais de Jean e Jamille, iluminação, distância e ruído. Os testes não medem taxa de falsos reconhecimentos nem resistência a reprodução de áudio/foto.

## Botões de biometria nas configurações

Após marcar o consentimento, Cadastrar rosto e Cadastrar voz abrem um diálogo para digitar a senha de desbloqueio. Remover biometrias também solicita essa senha, sem exigir marcar consentimento de captura. Cancelar não altera os dados. Essas referências são do bloqueio de abertura; para identificação durante conversas, use o cadastro guiado em Identidade. Instalações antigas sem bloqueio de abertura conservam a autorização manual legada por senha de perfil; o fluxo guiado administrativo exige a senha de desbloqueio ativa.
