# LiveCall: detecção neural local e interrupções

## Decisão

O usuário escolheu detector local, mantendo os provedores atuais. O desktop
estava configurado com motor `auto`. Substituir o timeout simples por Silero
VAD + Smart Turn v3.2 na captura do PC. Sem nova API paga e sem enviar áudio
a outro serviço para detectar o fim de turno. STT/LLM/TTS continuam usando
os provedores já configurados.

## Implementação

- Pesos ONNX fixados por revisão e SHA-256. Instalação explícita reproduzível:
  `python -m app.services.voice.turn_audio --install`. Pesos já instalados
  nesta máquina (~11 MB). Licenças e origem do extrator de características
  em `app/services/voice/vendor`.
- Silero mantém seu estado entre frames para distinguir voz de silêncio.
  Smart Turn avalia os últimos 8 s de áudio em uma thread separada, sem
  bloquear a leitura do microfone. Inferência começa após 0,6 s de pausa.
- Política conservadora: probabilidade >= 0,8 e silêncio >= 1,5 s permitem
  finalizar; caso contrário, aguarda até 8 s. Retomar a fala invalida a
  previsão anterior. Um corte de 20 s para transcrição não encerra o turno.
- O painel acumula segmentos até a decisão final e não adiciona novamente
  os 3 s de debounce quando o backend já decidiu. Resultados STT preservam
  ordem e não atravessam chamadas encerradas.
- O início de uma execução por voz publica seu run_id. Interromper cancela
  exatamente essa execução e o áudio, descartando a resposta atrasada.
  Cancelamento cooperativo não desfaz ações já concluídas.
- Complemento após interrupção mantém o pedido anterior como referência,
  com orientação para não repetir ações confirmadas. O trecho ouvido é
  estimado pelo progresso do áudio; a resposta inteira não é tratada como ouvida.
- Modelos só carregam quando a captura semântica é solicitada e são
  liberados ao fechar. ONNX usa uma thread por sessão, sem spin de espera.
- Falta ou falha de modelo é exposta no diagnóstico. O navegador/móvel
  continua sendo fallback de detecção simples; PTT continua manual.

## Evidências

- 21 cenários Playwright de livecall passaram, incluindo segmento parcial
  com pausa longa, final sem novo texto, cancelamento do run exato e complemento.
- 23 testes Python de detecção/voz e 44 subtestes passaram. Depois foi
  acrescentado o caso de previsão atrasada: os 7 testes de detecção passaram.
- 35 testes de runtime da conversa passaram antes da regressão adicional de
  anúncio/cancelamento do run; essa regressão adicional também passou.
- TypeScript, build de produção e `git diff --check` passaram. O build
  mantém o aviso existente sobre chunks grandes.
- Modelos reais carregados e executados nesta máquina. Avaliação exploratória
  nos primeiros 9 registros em português das primeiras linhas públicas do
  dataset `pipecat-ai/smart-turn-data-v3.1-test`, split `train`: 9/9 rótulos
  corretos, sendo 8 incompletos e 1 completo. Todos esses exemplos são
  sintéticos. Não é um benchmark representativo nem prova de desempenho com
  o microfone do usuário. Inferência medida nessa amostra: 356–519 ms.
- Resultados locais da amostra: `scratch/voice-public-results.json`.

## Limites e validação real

Sem reiniciar o Jarvis ou capturar a conversa atual do usuário. É preciso sair
completamente e reabrir para usar o novo backend/painel. Testar pausas naturais,
complementos, ruído e alto-falantes no hardware real. PyAudio não oferece
cancelamento acústico de eco aqui: permanece um limiar adicional durante TTS.
O modelo estima término; não prevê uma continuação depois de qualquer pausa.
O limite de 8 s impede espera infinita. Sem timestamps por palavra, o trecho
ouvido durante uma interrupção é apenas uma aproximação.

## Fontes primárias

- https://github.com/pipecat-ai/smart-turn
- https://docs.pipecat.ai/server/utilities/turn-detection/smart-turn-overview
- https://github.com/snakers4/silero-vad
- https://docs.livekit.io/agents/logic/turns/turn-detector/
- https://developers.openai.com/api/docs/guides/realtime-vad
