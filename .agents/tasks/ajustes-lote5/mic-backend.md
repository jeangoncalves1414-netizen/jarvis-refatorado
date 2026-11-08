# mic-backend: ligação por voz com SpeechRecognition no PC + balões da ligação

## O que mudou
**Parte A: detecção de fala no backend (modo `backend-sr`)**
- `app/services/voice/mic_capture.py` (novo): abre o microfone com PyAudio (`sr.Microphone`, `device_index` por nome), calibra 0,8 s no início (o limiar nunca fica abaixo do configurado), escuta em thread com o mesmo algoritmo do `sr.listen` (limiar dinâmico com damping 0,15, pausa = `silence_ms`, mínimo 0,35 s, pré-roll 0,35 s) e transcreve pela rota de STT configurada (`pipeline.transcribe_bytes`, WAV 16 kHz). Cada fala vira `transcript` com `turn_id` único.
- `app/ui/panel/api/voice_capture.py` (novo) e rotas em `server.py`. Só aceitam loopback (além da checagem do plano de controle):
  - `GET /api/voice/capture/status`, `/devices`, `/events?after=N&wait=1` (long-poll; também é o heartbeat)
  - `POST /api/voice/capture/start | stop | playback | test`
- Eventos: `state` (calibrating/listening/speaking), `level` (entrada + limiar, ~10/s), `calibrated`, `processing`, `transcript` (texto, `stt_ms`), `empty`, `barge_in`, `error` (fatal), `stopped`.
- Sensibilidade (1-100) -> `energy_threshold = 1100 * 2^((75 - s)/25) / ganho`, limitado a 150-8000. Padrão 75 = 1100 (projeto antigo); sensibilidade maior = limiar menor. Ganho divide o limiar. `silence_ms` padrão passou de 700 para 800 (pause_threshold 0,8 s) e vale também para o navegador.
- Configurações: `/api/settings/mic` ganhou `engine` (`auto` | `backend` | `browser`) e `device_name`. Em Voz e microfone: seletor de motor (mostra "Desligado: motivo" se faltar PyAudio/SpeechRecognition), seletor "Microfone do PC", limiar estimado e "Testar microfone" usando o PC quando ativo (calibra, ouve uma fala, mostra limiar/pico/transcrição/tempo).
- Seleção automática (`useMediaAssistant.ts`): `backend-sr` quando a tela está em 127.0.0.1/localhost e o backend tem SpeechRecognition + PyAudio; senão cai no VAD do navegador e o diagnóstico da ligação mostra "Motor do PC desligado: <motivo>". Falha fatal no meio da ligação também cai no navegador. O fluxo de resposta é o mesmo do modo do navegador (`/api/chat/stream`, TTS em fila por frases, barge-in).
- Integrações (mission-control): novo item "Escuta do PC" (healthy / off com motivo).
- **Eco/interrupção** (abordagem simples): o frontend avisa o backend (`/playback`) quando o áudio do Jarvis começa/termina. Enquanto toca (e 0,5 s depois), o limiar sobe 3x e só voz acima dele por 0,4 s seguidos interrompe (evento `barge_in`, a tela corta o TTS e a fala já capturada segue como próximo turno). Fone de ouvido evita falsos cortes.
- **Wake word**: `WakeWordDetector.set_mic_paused()` fecha o stream do Vosk durante a captura do backend e reabre ao fim (`_pause_wake_word` em `mic_capture.py`).
- **Parada garantida**: Parar/encerrar chama `/stop` (a thread fecha o PyAudio); `pagehide` envia `sendBeacon` para `/stop`; sem consultar `/events` por 25 s o backend encerra sozinho.
- **STT padrão**: voltou para Groq `whisper-large-v3-turbo` e Google como reserva (`config.py`, `runtime_settings.py`, `settings.py`; ordem da rota: groq, google, oxyy, local). `local` continua escolhível. Sem aviso de erro se não foi escolhido. `faster-whisper` saiu das dependências obrigatórias (`pyproject.toml` > extra `local-stt`). SpeechRecognition e PyAudio já estavam em `pyproject.toml`.

**Parte B: balões da ligação**
- Causa: a tela da ligação (`LiveCallModal`) só listava `liveTurns`, e `liveTurns` só era preenchido no caminho `sendTextStreamAndPlay` (Web Speech). No VAD do navegador (o caminho real no app do PC) e no modo nativo ficava só `liveUserTranscript`, sobrescrito a cada fala, e o balão do Jarvis nunca aparecia. O histórico salvo estava certo porque quem gravava era o chat.
- Correção: todo modo cria um turno ao enviar a fala (`beginLiveTurn`, balão da usuária na hora, do Jarvis como "…") e completa com a resposta (`sendTextAsTurn` para VAD/nativo; `sendTextStreamAndPlay` atualiza por frase e fecha no fim; turno cancelado é removido). O modal agora só mostra a lista de turnos (+ linha provisória quando a frase está sendo completada). O fallback não-stream não duplica a troca no histórico.

## Arquivos
app/services/voice/mic_capture.py (novo), app/ui/panel/api/voice_capture.py (novo), app/ui/panel/server.py, app/ui/panel/api/mission_control.py, app/ui/panel/api/settings.py, app/services/voice/wake_word.py, app/storage/runtime_settings.py, app/config.py, pyproject.toml, frontend/src/hooks/useMediaAssistant.ts, components/LiveCallModal.tsx, components/VoiceSettings.tsx, pages/SettingsPage.tsx, pages/WorkspaceOverview.tsx

## Dependências
Já instaladas aqui: SpeechRecognition 3.16.1 e PyAudio. Em outro PC: `pip install SpeechRecognition pyaudio`. Python 3.11 tem `audioop` (removido no 3.13; nesse caso o motor do PC fica "desligado" com motivo). `faster-whisper` só se escolher STT local (`pip install faster-whisper`).

## Verificação feita
Só `tsc --noEmit` e `py_compile`, como pedido. Teste rápido do módulo: abriu o microfone padrão, calibrou (limiar 1100), emitiu níveis e fechou com `stop()`.

## Para testar
1. Reiniciar o Jarvis (backend novo). Ligação por voz: o diagnóstico deve dizer "MICROFONE DO PC (SPEECHRECOGNITION)" com Entrada/Limiar e "Transcrição N ms".
2. Falar várias vezes: cada fala deve criar um novo par Você/Jarvis na ligação sem apagar os anteriores, e o mesmo no chat.
3. Interromper o Jarvis falando alto enquanto ele responde; se cortar sozinho (eco), usar fone ou baixar o volume (ou subir `PLAYBACK_THRESHOLD_FACTOR` em `mic_capture.py`).
4. Configurações > Voz e microfone: escolher o microfone do PC, ajustar sensibilidade, "Testar microfone".
5. Encerrar a ligação e conferir que a palavra de ativação volta a responder e que o microfone liberou.
6. Para forçar o navegador: motor de detecção = Navegador.
