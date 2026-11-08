# Configurações redesenhadas
## O que mudou
- `SettingsPage.tsx`: layout de duas colunas no tema do workspace (tokens `--ws-*`), com lista lateral de seções, busca e modo Organizar. Seções: Geral e perfil (perfil do agente, briefing, módulos), Voz e microfone, Provedores e rotas (rotas, catálogo Oxyy, chaves, config mobile), Aprovações automáticas (`AutoApprovalsManager` com o toggle Modo liberado), Sincronização e conta, Aparência e sons (SFX + organização), Backup e sistema. Os cartões antigos foram só movidos; o cartão antigo de provedor TTS foi substituído pelo da seção de voz.
- Busca: filtra as seções por nome e palavras-chave e mostra as que casam, empilhadas.
- Organizar: subir/descer, fixar no topo (estrela) e ocultar/mostrar seções. Salvo em `localStorage` na chave `lifeos_settings_layout` (`utils/settingsLayout.ts`), que o sync existente já leva em `extraData` (prefixo `lifeos_`). "Restaurar ordem padrão" em Aparência.
- `components/VoiceSettings.tsx` (novo):
  - Sliders de sensibilidade, silêncio para encerrar a fala e ganho, ligados a `/api/settings/mic` (salvam sozinhos, com botão de padrões 75 / 700 ms / 1,0).
  - Dispositivo de entrada (guardado em `jarvis_mic_device`; `utils/micPrefs.ts`; `useMediaAssistant.ts` agora usa esse dispositivo na ligação e no ditado).
  - Medidor de nível ao vivo (liga/desliga), com linha do limiar mínimo da sensibilidade e pico.
  - STT: provedor, modelo local, aviso vermelho com `pip install faster-whisper` quando o local está desligado.
  - TTS: provedor e voz dentro do provedor (Fish: ID de referência; Gemini; Edge; Oxyy).
  - Testes: Testar microfone (grava 4 s, mostra transcrição e tempo), Testar STT (gera frase com TTS e transcreve de volta, mostra tempo), Testar TTS (fala uma frase, mostra tempo até o primeiro áudio e total). Só usam `/api/voice/stt`, `/api/voice/tts` e `/api/voice/tts/stream`; nenhum modelo de chat.
- Backend: `POST /api/settings/tts` aceita `{"voices": {"fish_reference_id", "gemini", "edge"}}` (salvo em `runtime_settings.json` > `tts_voices`, aplicado em env e no objeto Settings, e o pipeline de voz é reconstruído). Voz do Oxyy continua em `/api/settings/oxyy`.
- `styles/settings.css` (novo, importado em `main.tsx`).
## Arquivos
frontend/src/pages/SettingsPage.tsx, components/VoiceSettings.tsx (novo), utils/settingsLayout.ts (novo), utils/micPrefs.ts (novo), styles/settings.css (novo), main.tsx, hooks/useMediaAssistant.ts, app/storage/runtime_settings.py, app/ui/panel/api/settings.py
## Observações
- Sem verificação visual nem testes, conforme pedido; só `tsc --noEmit` e `py_compile`.
- A lista de vozes Gemini/Edge/Oxyy é fixa (as mais comuns); a voz atual aparece mesmo se não estiver na lista.
- O ajuste de microfone vale na próxima ligação por voz.
- Para testar: Configurações > Voz e microfone; ligue o medidor, mexa na sensibilidade e rode os três testes.
