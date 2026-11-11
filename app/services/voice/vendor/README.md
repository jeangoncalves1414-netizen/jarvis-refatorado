# Fontes incorporadas

`whisper_features.py` foi incorporado sem alterações de Pipecat, revisão
`36d7520eee97028d312739139ca1dac41c5713d2`:
https://github.com/pipecat-ai/pipecat/blob/36d7520eee97028d312739139ca1dac41c5713d2/src/pipecat/audio/turn/smart_turn/_whisper_features.py

Licença BSD-2-Clause (Daily), com partes derivadas de Transformers sob
Apache-2.0. Avisos originais preservados; textos das licenças incluídos.

Os pesos ficam em `data/models/voice`, fora do código versionado. URLs fixas
por revisão e SHA-256 estão em `turn_audio.py`. Instalação reproduzível:

```powershell
python -m app.services.voice.turn_audio --install
```

Smart Turn: https://github.com/pipecat-ai/smart-turn (BSD-2-Clause).
Silero VAD: https://github.com/snakers4/silero-vad (MIT).
As licenças dos modelos também estão nesta pasta.
