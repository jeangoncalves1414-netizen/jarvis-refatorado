# Relatório do lote 5 (ajustes)
Sem revisão e sem verificação visual, como pedido. Cada step rodou só `tsc --noEmit` (e `py_compile`/build do evolute quando havia backend/evolute). Detalhes por step estão nos arquivos `.md` desta pasta.

## O que mudou e o que testar, por step

### 1. bugs-chat-voz (commits 83a8859, dee430e, 86cc0f3)
- Chat preso em "pensando" após aprovar na Central: `useChat.ts` ganhou vigia de turno (4 s; sem evento por 15 s consulta `/api/runs`). Run terminal vira resposta; aguardando aprovação mostra aviso; limite de 10 min.
- Ligação por voz: cada fala vira turno novo (usuária + Jarvis) no modal e no chat.
- Testar: pedir "abrir os hábitos de hoje", aprovar na Central, voltar ao chat (sai de "pensando" em ~15 s, janela não abre sozinha, só o resumo). Ligação: falar várias vezes e ver pares novos.

### 2. voz-latencia (bdbbdcf)
- O streaming por frases para o TTS já existia. Fish agora usa latency `balanced`; primeira frase corta com 8 caracteres; status mostra "Primeiro áudio em X ms".
- Testar: ligar, falar, ver o tempo; conferir se a voz da Fish soa igual; interromper falando.

### 3. stt-local (f8cd332, 9e95655)
- Provedor STT `local` (faster-whisper, modelo padrão `base`, baixado na primeira transcrição ~145 MB). Mic configurável (`/api/settings/mic`). Referência do Projeto AI: SpeechRecognition com limiar 1100 e pausa 0,8 s.
- Obs.: o step mic-backend depois devolveu o padrão para Groq com Google de reserva; `local` continua escolhível.
- Testar: `pip install faster-whisper`, escolher "STT local", falar e ditar.

### 4. auto-aprovar (215d801)
- Regras de aprovação automática (ferramenta + operação + alvo, durações 10 min / hoje / 30 dias / sempre) e Modo liberado (aprova tudo; selo vermelho no cabeçalho). Botão "Permitir e autorizar" na Central e no histórico.
- Testar: Configurações > Aprovações automáticas; ligar/desligar Modo liberado; aprovar uma ação de risco com "Permitir e autorizar" e repetir; editar duração e revogar.

### 5. fix-groq-voz (b86f6fc)
- Não há arquivo de resumo `fix-groq-voz.md` na pasta. Pelo commit: "turno final do Groq sem falha e histórico atual na ligação por voz".
- Testar: ligação por voz com Groq, conferir que o último turno não falha e o histórico da ligação mostra a conversa atual.

### 6. configuracoes (74d3a30)
- `SettingsPage` redesenhada em duas colunas no tema do workspace: seções, busca, modo Organizar (subir/descer, fixar, ocultar; salvo em `lifeos_settings_layout`). Novo `VoiceSettings`: sensibilidade, silêncio, ganho, dispositivo, medidor ao vivo, STT/TTS e testes (microfone, STT, TTS). `POST /api/settings/tts` aceita `voices`.
- Testar: Configurações > Voz e microfone (medidor, sliders, os três testes), busca, Organizar e "Restaurar ordem padrão".

### 7. mic-backend (0b9b30a)
- Ligação por voz com SpeechRecognition no PC (`mic_capture.py`, rotas `/api/voice/capture/*`, só loopback). Eco/barge-in simples, pausa do wake word durante a captura, parada garantida. STT padrão voltou a Groq. Balões da ligação corrigidos: todo modo cria turno.
- Testar: reiniciar o Jarvis; ligação deve indicar "MICROFONE DO PC (SPEECHRECOGNITION)"; falar várias vezes; interromper o Jarvis; escolher microfone e "Testar microfone"; encerrar e conferir que o wake word volta e o mic é liberado. Forçar navegador: motor = Navegador.

### 8. lifeos (508d00e)
- Tokens `--ws-*` movidos para `styles/ws-tokens.css` (valem em `:root`). App `/evolute/` remapeado para o tema; `EvoluteHubPage` com classes `lo-*`; `styles/lifeos.css` novo. `evolute/dist` reconstruído (ignorado pelo git).
- Testar: janela Evolução/Life OS, hub de resumo, cada tela do app interno (hábitos, água, treino, etc.) e HUD "Life OS · Hoje" no painel inicial.

### 9. calendario (5755336)
- `Calendar.tsx` com classes `cal-*` e `styles/calendar.css`: calendário à esquerda, painel do dia à direita, day-picker e modal de lembrete tematizados.
- Testar: criar, ver e cancelar lembrete; navegar entre meses.

### 10. busca-workspace (commit deste step, `feat: busca do workspace no tema`)
- `styles/command-palette.css` novo, escopo `.ws-command-dialog`. `CommandPalette.tsx` intacto.
- Testar: Ctrl+K, digitar, setas, Enter, Esc, clique fora, tela estreita.

## Dependências (pip)
- `pip install SpeechRecognition pyaudio` (motor do PC; já instalados na máquina de desenvolvimento). Python 3.13 remove `audioop`; nesse caso o motor do PC fica desligado com motivo e cai no navegador.
- `pip install faster-whisper` só se usar STT local (extra `local-stt` em `pyproject.toml`).
- Reiniciar o backend para pegar as rotas novas. Rebuild do `evolute` (`npm run build`) se o dist for regenerado; APK precisa de build próprio.

## Pendente / duvidoso
- Regras de auto-aprovação são locais (sem sync Supabase); "Permitir e autorizar" só funciona enquanto o backend que criou a proposta está no ar.
- Eco: sem fone, o Jarvis pode cortar a si mesmo; ajustar `PLAYBACK_THRESHOLD_FACTOR` em `mic_capture.py`.
- Lista de vozes Gemini/Edge/Oxyy em Configurações é fixa.
- Estilos antigos órfãos em `styles.css` (`calendar-focus*`, blocos `cmd-*` antigos); o estado vazio da busca usa emoji 🔍.
- Evolute: componentes Tailwind remapeados, pode precisar de ajuste fino por tela.
- Falta `fix-groq-voz.md`; o relato desse step vem só do commit.
- Nada foi verificado visualmente nem por testes; revisão ficou para o futuro, conforme combinado.
