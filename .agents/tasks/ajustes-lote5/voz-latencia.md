# Voz: latência (step 2)

**O streaming já existia?** Sim: a ligação já fatiava a resposta de /api/chat/stream em frases e pedia o TTS de cada uma em paralelo, tocando em fila; o que não existia era a medição e a latência baixa configurada.

Alterado:
- app/services/voice/tts/providers/fish_audio.py: latency "normal" -> "balanced" (menor tempo até o primeiro áudio da Fish).
- frontend/src/hooks/useMediaAssistant.ts: primeira frase corta com 8 caracteres (as demais 12); mede o tempo entre o início do turno e o primeiro áudio tocando, mostra "Primeiro áudio em X ms" no status da ligação e registra o diagnóstico voice_first_audio_ms.

Mantido: barge-in cancela a fila e as requisições TTS (AbortController); fallback para /api/voice/tts e demais provedores pelo pipeline existente.

Testar: ligar, falar e ver o tempo no status; conferir se a voz da Fish soa igual com "balanced"; interromper falando.
