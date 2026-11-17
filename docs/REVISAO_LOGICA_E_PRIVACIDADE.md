# Revisão de lógica e privacidade — 13/11/2026

Escopo: integração entre chat HTTP/SSE/WebSocket, agenda, memórias, identidade, recadastro, bloqueio do app, câmeras e captura de áudio. Esta revisão não é uma auditoria exaustiva de todos os módulos.

## Correções

- Respostas restritas por identidade não consultam nem consomem lembretes privados e não gravam o pedido recusado na memória semântica. Entradas WebSocket que não sejam objetos JSON são rejeitadas sem encerrar o processamento das próximas mensagens.
- Arquivos existentes de identidade ou bloqueio com estrutura inválida falham de forma fechada. Não são tratados como uma instalação vazia que permita substituir o administrador ou desabilitar o bloqueio. Perfis órfãos também impedem a criação de outro administrador.
- As operações que verificam senhas de perfis compartilham um limite de cinco falhas, seguido de espera de 30 segundos. Alternar entre autenticação, cadastro, permissões e recadastro não reinicia esse limite. O contador é local ao processo; reiniciar o servidor o reinicia.
- Cadastros rejeitam nomes duplicados e referências faciais muito semelhantes às de outro perfil. Adicionar uma face exige consistência com as referências já cadastradas. Vetores inválidos, não finitos, vazios ou incompatíveis não desbloqueiam o app. As verificações de similaridade são conservadoras e não equivalem a uma garantia de identidade.
- Chamada, cadastro e painel de identidade usam o catálogo de câmeras habilitadas. Seleção explícita não substitui silenciosamente uma câmera por outra; seleção automática pode tentar a próxima habilitada. A enumeração evita abrir a câmera virtual padrão quando os dispositivos já estão identificados.
- Pedidos como “todas as pessoas na câmera 2” selecionam a câmera 2; nomes respeitam limites de palavras. Itens inválidos e valores nulos do catálogo antigo deixam de derrubar a leitura das configurações.
- Fechar telas invalida aberturas pendentes e encerra streams de câmera e microfone. Sair da identidade descarta a gravação ainda em andamento, sem cadastrar ou verificar a amostra depois. Temporizadores pertencem à gravação que os criou.
- Novas referências faciais são armazenadas como vetores; a inclusão manual deixa de persistir uma cópia bruta da fotografia. Fotografias legadas não são removidas por esta revisão.

## Limites mantidos

O painel desbloqueado continua sendo a sessão do proprietário: o bloqueio por identidade protege o fluxo do assistente, não isola todas as telas e rotas por pessoa. Não há prova de vida validada contra fotos, vídeos ou áudio reproduzido.

Não foram modificados perfis, senhas ou amostras reais. Os testes usam dados isolados e mídia simulada. Reconhecimento com pessoas reais, ruído, iluminação e resistência a falsos reconhecimentos precisam de validação específica.

## Verificação

- 140 testes Python passaram, abrangendo identidade, autorização, recadastro, bloqueio, câmera, controle de ações e segurança. Os 12 testes específicos de regressão também passaram após a revisão final da fixture.
- 57 cenários únicos de interface passaram ao longo das execuções: chat com câmera, seleção, cadastro, chamadas e liberação de recursos. Um teste de cancelamento de chamada excedeu a espera de cinco segundos na execução conjunta; passou nas duas repetições isoladas, sem alteração nessa funcionalidade.
- Os cinco testes de desmontagem de telas verificam captura ativa e abertura pendente; não apenas a aparência dos botões.

## Continuação: cancelamento e respostas atrasadas

- A leitura manual de Identidade agora reutiliza o microfone e o leitor local do cadastro guiado, sem iniciar `SpeechRecognition` do navegador. Se o leitor não estiver disponível, o feedback avisa e a gravação manual continua possível.
- Uma confirmação facial pendente não restaura a autorização depois de esquecer o perfil, fechar a câmera ou sair da tela. Ao iniciar outra confirmação, a evidência anterior é descartada.
- A exibição do bloqueio limpa a evidência de identidade guardada no navegador. Uma resposta antiga da consulta de bloqueio não pode substituir um estado mais recente.
- A biometria de desbloqueio respeita o catálogo de câmeras habilitadas. Cancelar a gravação, trocar voz por rosto ou sair interrompe a captura e descarta a amostra antes do envio. Durante o envio, a interface aguarda o resultado da operação.
- Desmontar o cadastro guiado avisa os outros componentes que o cadastro terminou, evitando deixar a captura visual impedida por um estado antigo.

Nesta continuação, 31 cenários únicos de interface passaram ao longo das execuções, incluindo dez novos testes de leitura local, cancelamento, bloqueio e respostas atrasadas. A compilação final de produção passou; permanecem os avisos de tamanho de alguns arquivos JavaScript e de importação estática/dinâmica já existentes. Não houve mudanças no backend nesta rodada.


## Correção da conversa pública e do cadastro (14/11/2026)

- A negativa fixa foi substituída por conversa geral sem contexto do proprietário. Texto e voz usam o mesmo caminho: nenhum histórico privado, memória pessoal, priming, ferramenta ou lembrete do administrador é fornecido ao modelo nesse modo. Pedidos privados continuam exigindo reconhecimento com permissão.
- O contexto público recente fica separado em memória, limitado a 20 mensagens por conversa e a 128 conversas. Mensagens públicas não são persistidas como histórico do proprietário pelo frontend, inclusive ao alternar para um turno privado. Cancelamentos e falhas também preservam essa separação. O painel local já desbloqueado permanece a interface do proprietário; isto não implementa contas isoladas para todas as páginas.
- Qualquer pessoa pode pedir “quero me cadastrar” ou usar Cadastro guiado em Identidade. O cadastro comum exige consentimento e leitura validada, cria somente role=user e não concede permissões privadas, mesmo se a requisição tentar impor outro papel.
- Cadastro/recadastro administrativo usa a senha de desbloqueio ativa. A antiga senha do perfil não autoriza gestão enquanto esse bloqueio estiver ativo. A troca/desativação da senha revoga tickets administrativos pendentes. Novos cadastros administrativos concorrentes não criam dois administradores. Instalações antigas sem senha de abertura conservam somente a gestão manual legada por senha de perfil.
- Os botões de biometria de abertura solicitam senha em um diálogo, sem exigir que o usuário descubra um campo em outra seção. A câmera/microfone só são solicitados depois dessa confirmação. Remover biometrias não depende do consentimento para novas capturas. O diálogo diferencia as referências de desbloqueio das referências de identidade durante a conversa.
- Senhas, perfis e amostras reais não foram alterados. Validação usa dados isolados e mídia simulada; não atesta a precisão do reconhecimento no hardware real.

Validação desta correção: a primeira rodada de backend passou com 55 testes; a rodada final, incluindo cancelamentos e regressões de orquestração/voz, passou com 56 testes. Na interface, 86 cenários únicos passaram ao longo das execuções (32 de identidade/cadastro/câmeras, 30 de ligação e 24 de experiência de chat). A preparação antiga dos testes de chat foi atualizada para simular o bloqueio de abertura e usar a classe/altura reais da lista atual. Um cenário de pausa VAD excedeu o prazo na rodada ampliada e passou na repetição isolada. A compilação final TypeScript/Vite passou com os avisos já existentes de tamanho de chunks e importação estática/dinâmica. `git diff --check` não encontrou erros de whitespace.


## Cadastro por fala e leitura flexível — 14/11/2026

- Cadastro guiado escuta nome e respostas localmente, inclusive fora da chamada. Cada resposta usa um trecho separado e é descartada ao mudar de etapa. A escuta ignora os períodos em que a instrução está sendo falada, pode ser pausada e libera o microfone ao cancelar ou sair.
- O nome do primeiro administrador pode ser ditado. A senha permanece no campo protegido; focar esse campo encerra a ditagem de nome. O áudio e os comandos de cadastro não passam pelo chat.
- A captura da chamada é pausada durante o cadastro e retomada ao finalizar, se a chamada ainda estiver aberta. Assim a referência não é enviada como pedido comum nem processada por dois capturadores concorrentes.
- Destaque e validação guiada contam ocorrências das palavras sem exigir sequência, ignorando caixa, acentos e pontuação. Cada ocorrência falada só pode satisfazer uma ocorrência do texto. O limite passou de 85% para 80%, verificado pelo servidor no áudio recebido; porcentagem fornecida pelo cliente não é aceita. A gravação termina ao atingir o mínimo indicado pelo leitor, com nova checagem no servidor.
- A omissão de Jarvis deixa de travar as palavras seguintes ou a aprovação quando o restante cobre 80%. Isso não altera o vocabulário do modelo de transcrição nem garante que nomes próprios sejam reconhecidos corretamente.

Validação: 26 testes Python passaram. Os 31 cenários de câmera, ciclo de captura e cadastro público passaram. Dos 30 cenários de chamada, 29 passaram na execução ampla; o cenário de continuação de frase excedeu o tempo de espera e passou isoladamente, sem alterar sua lógica. O teste adicional de foco na senha também passou. Reconhecimento com microfone/voz reais e calibração em ruído não foram medidos; os testes de interface simulam áudio e transcrição.
