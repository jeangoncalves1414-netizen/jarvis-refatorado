# LiveCall: pausas de formulação e texto falado

## Problema

O buffer anterior de 1,8 s enviava frases aparentemente completas antes da
continuação. O VAD do navegador também encerrava a gravação nesse intervalo.
A captura do PC usava o silêncio configurado, que podia ser ainda menor.
Transcrições concorrentes podiam chegar invertidas ou enquanto outra fala
estava em andamento. O fracionamento do TTS por pontos quebrava URLs antes
da sanitização, expondo pedaços do endereço à voz.

## Correção

- LiveCall solicita 3 s de silêncio na captura do PC e usa no mínimo 3 s no
  VAD do navegador. Não altera a configuração global do microfone.
- O buffer de continuação passa a 3 s; frases explicitamente incompletas
  mantêm 4,5 s. PTT continua enviando somente ao soltar.
- A captura do PC mantém a ordem dos segmentos e aguarda fala/transcrições
  pendentes antes de enviar. Continuação que já começou bloqueia o timer.
- A voz aguarda a resposta final, aplica `speech_summary`/estado de erro e
  limpa o texto inteiro. Não divide URLs nos pontos durante o streaming.
- Os sanitizadores do painel e Python removem URLs/domínios comuns,
  metadados de processo/janela e linhas de log reconhecidas. Exceções técnicas
  reconhecidas viram um aviso curto. A resposta original permanece na tela.

## Verificação

- 18 cenários Playwright passaram, incluindo pausa de 2,1 s no áudio,
  continuação após frase completa, STT lento/fora de ordem, links fragmentados,
  erro fragmentado, fechamento, cancelamento, PTT e interrupção de áudio.
- Build de produção e TypeScript passaram; aviso já existente de chunks grandes.
- A bateria Python teve 34 testes e 44 subtestes aprovados, incluindo as
  regressões dos sanitizadores. Um teste existente de fallback sem chave
  (`test_orchestrator_llm_fallback_when_no_api_key`) falha: espera intent
  `general`, mas o runtime retorna `error`. O comportamento do orquestrador
  não foi alterado nesta correção. A tentativa de isolar as credenciais não
  resolveu a divergência; o teste foi preservado para investigação separada.

## Limites

Não foi usado o microfone real nem reiniciada a chamada do usuário. Sair
completamente e reabrir o Jarvis carrega backend e painel atualizados.
A espera e a sanitização antes da voz aumentam o tempo até começar a resposta.
O detector continua baseado em silêncio; pausas acima da janela podem separar
pedidos. A filtragem de texto reconhece padrões, não toda possível forma de log
ou domínio. PTT permite delimitar manualmente falas com pausas mais longas.
