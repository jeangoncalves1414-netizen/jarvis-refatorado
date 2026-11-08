# STT local e sensibilidade do microfone

## O que mudou
- Novo provedor de STT `local` (faster-whisper, offline): `app/services/voice/stt/local_whisper.py`. Modelo configurável (tiny/base/small/medium, padrão `base`), dispositivo auto/cpu/cuda, int8 na CPU. O modelo é baixado na PRIMEIRA transcrição (aviso no log e em Configurações). Nada foi baixado automaticamente.
- `local` é a primeira opção da rota `stt` e o padrão sugerido (`config.py`, `runtime_settings.py`). Sem a biblioteca, a rota cai para Groq/Oxyy/Google e Integrações mostra "Desligado: faster-whisper não instalado (pip install faster-whisper)". O antigo `whisper_local` virou apelido de `local`.
- `engine.py`: o provedor local tenta primeiro; se falhar, segue a cadeia Groq/Google.
- Dependência `faster-whisper>=1.0` em `pyproject.toml`.
- Microfone configurável: `GET/POST /api/settings/mic` com `sensitivity` (1-100, padrão 75), `silence_ms` (padrão 700, antes 750) e `gain` (padrão 1.0). Limiar da ligação: de 0,012 fixo para ~0,0105; multiplicador de ruído de 3 para ~2,4 (um pouco mais sensível).
- Referência do Projeto AI: usava SpeechRecognition (VAD por energia, limiar 1100, pausa 0,8 s, mínimo 0,35 s) + Google/Groq. Não havia Whisper local lá; os valores padrão vêm daí.
- `useMediaAssistant.ts` lê essas configurações ao iniciar a ligação.
- Configurações: opção "STT local" e seletor de modelo em `SettingsPage.tsx`. A tela de ajuste/teste do microfone fica para o passo de redesenho de Configurações (a API já existe).

## Arquivos
pyproject.toml, app/config.py, app/storage/runtime_settings.py, app/ui/panel/api/settings.py, app/services/voice/stt/engine.py, app/services/voice/stt/local_whisper.py (novo), frontend/src/types.ts, App.tsx, pages/SettingsPage.tsx, hooks/useMediaAssistant.ts

## Para testar
1. `pip install faster-whisper`, escolha "STT local" em Configurações. A primeira fala baixa o modelo `base` (~145 MB) e demora.
2. Ligação por voz e ditado devem transcrever localmente (Integrações mostra o provedor efetivo).
3. Sensibilidade: `POST /api/settings/mic {"sensitivity": 85}` até existir a UI de ajuste.
4. Quem já tinha Groq salvo continua em Groq até trocar na lista.
5. O streaming em tempo real (`stt/streaming.py`) não usa o provedor local.
