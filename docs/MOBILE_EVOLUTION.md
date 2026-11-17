# Jarvis no Android

O ícone do Jarvis abre o mesmo painel do PC. Conversas, histórico, configurações e módulos usam o servidor do computador. Na tela menor, **Abrir navegação** dá acesso ao menu lateral e **Controle do agente** abre os controles. O PC deve estar com o Jarvis em execução e o telefone na mesma rede Wi-Fi. O cabo só é necessário para instalar e parear.

Para abrir o despertador, os hábitos ou as conversas locais, use **Voltar → Rotina offline** na tela inicial do painel. A mesma opção aparece se o PC estiver indisponível. O histórico do chat de rotina continua no aparelho.

Na ligação, o telefone usa seu próprio microfone para transcrição e o PC sintetiza as respostas com a referência de voz Fish Audio configurada no Jarvis. A conversa por voz atende perguntas gerais. Para consultar dados pessoais ou executar comandos privados, use o chat de texto desbloqueado. O painel pareado usa senha e dispensa o cadastro e a verificação por rosto ou voz.

## Rotina offline

O app Android reúne Hábitos, Finanças, Chat e Ajustes. O chat guarda as mensagens neste aparelho e executa comandos de rotina offline. Experimente `Criar hábito Ler`, `Gastei doze e cinquenta no café`, `Corrige o último gasto para quinze` ou `Resumo da manhã`. As respostas dão acesso ao painel do registro.

No Chat, **+** abre uma conversa e o botão **Histórico de conversas** alterna entre elas. Cada conversa guarda seu rascunho e as últimas 60 trocas no aparelho. Toque em uma sugestão ou abra **Comandos** para preencher a mensagem, revise e envie pela seta. Nas mensagens você pode copiar o texto, reutilizar um pedido e ouvir a resposta com a voz do Android.

## Finanças no celular

A aba Finanças mostra despesas de hoje e do mês e os lançamentos recentes. Os totais incluem as despesas anteriores à lista de 100 registros e acompanham as edições offline. Antes da primeira sincronização com a versão atual do PC, o painel identifica o subtotal disponível no aparelho. No chat, pergunte `Quanto gastei hoje?` ou `Quanto gastei no mês?`.

Ao registrar uma receita ou despesa no chat, o cartão oferece **Desfazer lançamento**. A ação remove o registro no aparelho e envia a alteração ao PC na próxima sincronização. Se você já alterou o lançamento, revise-o em Finanças.

## Despertador e manhã

Em **Ajustes**, marque os dias, escolha o horário de cada um e salve. O app mostra o próximo toque. **Ouvir teste** inicia a prévia. **Adiar 5 min** programa outro toque e **Acordei** abre o resumo. O toque e a motivação usam gravações Fish Audio incluídas no APK e funcionam offline. Com o painel conectado e desbloqueado, o Jarvis também lê o resumo de hábitos usando a voz atual do PC. O volume do alarme controla a faixa de despertar.

O resumo usa o bloco da manhã e os horários matinais da rotina do PC. Para incluir um hábito manualmente, vá a **Hábitos → Editar → Incluir na minha manhã neste celular**. Toque em **Concluir** para passar ao próximo, ou em **Ver dia completo** para abrir a lista do dia.

## Sincronização

A edição funciona offline. Com os aparelhos pareados, abrir o app ou usar **Ajustes → Sincronizar agora** inicia a troca por Wi-Fi. O Android agenda tentativas em segundo plano em rede sem franquia, a partir de 15 minutos, conforme a política de bateria do sistema. O PC precisa estar ligado e acessível no endereço pareado. O celular recebe a agenda de hábitos e até 100 lançamentos recentes. Em caso de divergência, Ajustes permite escolher o valor do PC ou do celular.

Para parear um APK de desenvolvimento instalado e autorizado por USB, execute na raiz do projeto, substituindo o endereço pelo IPv4 local do PC. Em um celular novo, instale primeiro o app com `.\mobile_app\gradlew.bat -p mobile_app installDebug`.

```powershell
python -m scripts.mobile_wifi pair 192.168.0.44
python -m scripts.mobile_wifi serve
```

O inicializador normal do Jarvis também abre o serviço quando encontra um pareamento. A conexão usa HTTPS na porta 48731, com certificado e credencial provisionados pelo cabo. Repita o pareamento e reinicie o serviço se mudar o endereço do PC ou expirar o certificado (um ano). A transferência manual continua disponível com `python -m scripts.sync_mobile_routine`.

## Instalar o painel no telefone pareado

Na raiz do projeto, com o celular autorizado por USB e o pareamento Wi-Fi acima configurado, execute:

```powershell
.\scripts\build_mobile_jarvis.ps1 -Install
```

Reabra o Jarvis no PC depois do primeiro pareamento do painel. O script atualiza o aplicativo de desenvolvimento, preserva os dados locais e provisiona uma credencial privada pelo ADB. O APK contém o certificado público do PC. O painel usa HTTPS na porta 48732 e WSS na 48733 e respeita o bloqueio do Jarvis. Se trocar o IP ou renovar o certificado, repita o pareamento Wi-Fi, a instalação e a abertura do servidor.

O painel é servido de `frontend/dist`. Use `-RebuildWeb` para recompilar as interfaces do PC a partir dos fontes. Nas próximas atualizações apenas do painel web, basta recompilar no PC e reabrir o app. A rotina offline permanece em `mobile_app/app/src/main/routineAssets/routine.html`.
