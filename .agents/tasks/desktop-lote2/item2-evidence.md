# Item 2 — Perfil neutro do agente (persona fora do código)

Data: 7/11/2026. Branch `main`, sem worktree.

## O que mudou

- **Perfil do agente nas runtime settings** (`app/storage/runtime_settings.py`): chave `agent_profile` em `data/runtime_settings.json` com `name`, `style` e `wake_phrase`. Funções `get_agent_profile`, `set_agent_profile`, `prepare_agent_profile`, `default_agent_profile`, `normalize_wake_phrase`, `derive_wake_phrase`.
  - Padrão neutro: nome "Assistente", estilo "Neutro, cordial e conciso. Responda em português do Brasil…", frase "ei assistente".
  - `wake_phrase` vazio no arquivo significa "derivar do nome" (`ei <nome>`). A resposta da API traz a frase efetiva e `wake_phrase_custom`.
  - Validação: nome obrigatório com até 40 caracteres; estilo com até 2000 (vazio usa o padrão); frase só com letras e espaços, até 60 caracteres e 4 palavras. Dados salvos inválidos voltam ao perfil padrão.
- **Prompts** (`app/agent/prompts.py`): `AGENT_SYSTEM_CORE_TEMPLATE` e `AGENT_SYSTEM_PROMPT_FUNCTION_CALLING_TEMPLATE` usam `{agent_name}`. Os builders aceitam `agent_profile=` e, sem ele, leem o perfil ativo. A seção "## Perfil do agente" traz nome e estilo e avisa que o perfil não muda permissões, ferramentas nem aprovações. Saíram "JARVIS", "Tony Stark", "Sir", "senhor" e "sotaque britânico". O contexto factual de rota/motor, a lista de ferramentas do modo e as regras de ferramentas ficaram iguais. `AGENT_SYSTEM_CORE`, `AGENT_SYSTEM_PROMPT` e `CHAT_SYSTEM_PROMPT` continuam exportados, agora com o nome padrão.
- **Outros prompts com persona**, achados por grep e trocados para "assistente": `coder_subagent.py`, `reflexion.py`, as descrições das ferramentas `jarvis_mode` e `proactive_agent`, e `GENERAL_SYSTEM_PROMPT` em `modes/tutor.py` (sem uso no runtime, ficou neutro). Nenhum arquivo, módulo, ferramenta ou chave de storage foi renomeado.
- **Chat direto móvel** (`frontend/src/utils/jarvisVaultKeys.ts`): o prompt usa o perfil salvo na nova chave local `jarvis-agent-profile`, com padrão neutro. As chaves existentes ficaram iguais.
- **API**: `GET /api/settings/agent-profile` e `POST /api/settings/agent-profile` (`app/ui/panel/api/settings.py`). O POST valida, confere o vocabulário do Vosk, grava e atualiza a frase do detector em execução (`set_wake_phrase`), sem importar o servidor.
- **Wake word** (`app/services/voice/wake_word.py`): a frase padrão do detector vem do perfil (a constante `WAKE_WORDS` com "jarvis" saiu). O modelo Vosk é carregado uma vez e serve ao detector e à validação. `check_wake_phrase_vocabulary` usa `Model.vosk_model_find_word` e não baixa o modelo. Sem Vosk ou sem modelo local, retorna `checked: false` e o perfil é salvo com esse aviso. O evento `wake_word` **não** foi ligado à UI. O texto do evento WS já existente (`_broadcast_wake_word`) e o log de início agora usam a frase do perfil.
- **UI** (`frontend/src/pages/SettingsPage.tsx`): cartão "Perfil do agente" no topo de Configurações, com campos nome, personalidade e estilo, e frase de ativação (só no desktop). Tem estados de carregando, salvando, salvo e erro (`role="alert"`). O texto do cartão diz que permissões, ferramentas e aprovações não mudam. No APK sem backend, o perfil fica salvo no aparelho.
- **Docs**: atualizei uma linha em `docs/PENDENCIAS_DO_PAINEL.md` (item 2) e outra em `docs/PROJECT_CONTINUITY.md`.

## Achado sobre o Vosk

No modelo local `data/vosk_model_ptbr` (vosk-model-small-pt-0.3), uma consulta somente leitura deu `ei`, `assistente`, `oi`, `olá` e `você` no vocabulário. `jarvis` e `sexta-feira` ficam **fora**. O detector usa reconhecimento livre, então uma palavra fora do vocabulário nunca aparece na transcrição: a frase "ei jarvis" antiga não podia disparar. Agora o POST recusa essa frase com uma mensagem clara. Um perfil com o nome "Jarvis" ainda pode ser salvo com outra frase, por exemplo "ei assistente".

## Decisões conservadoras (sem pausa)

- Uma frase fora do vocabulário é sempre recusada, inclusive quando é derivada do nome. Nesse caso a usuária informa uma frase personalizada.
- Mantive o reconhecimento livre do Vosk, sem trocar para gramática restrita, para não mudar o comportamento do detector neste item.
- O `AgentManager` legado (`app/agent/agent_model/profile.py`, `data/agents.json`, padrão "Jarvis") não alimenta nenhum prompt e não foi alterado. O `SoulService` (`docs/SOUL.md`) também não é usado no runtime.
- Ficaram fora deste item as **mensagens de resultado** com "Sir" em ferramentas e serviços (calendar_tool, system_tray_tool, lifeos_tool, proactive.py, como "Bom dia, Sir", yesterday_recap e lifeos), além de textos de UI como "Falar com Jarvis". Elas não são prompts. Ficam para um lote futuro.
- O perfil ainda não entra na sincronização com a nuvem.

## Testes

- `tests/test_agent_profile.py` (novo, storage em tmp e vocabulário Vosk falso). Cobre: perfil padrão neutro e prompt sem jarvis, Tony Stark, sir ou senhor; perfil custom com nome e estilo e sem "jarvis"; perfil salvo muda o prompt sem mudar a seção de ferramentas; round-trip GET→POST→GET com o arquivo gravado; entradas inválidas recusadas e não gravadas; frase fora do vocabulário recusada; vocabulário não verificado sem modelo; detector segue o perfil e é atualizado ao salvar.
- `pytest tests/test_agent_profile.py tests/test_orchestrator.py tests/test_chat.py tests/test_conversation_runtime.py tests/test_provider_routes.py`: **53 passed**. Nenhum assert desses arquivos fixava a persona Jarvis.
- `pytest tests/test_voice_api.py tests/test_voice_modular.py tests/test_agent_profile.py`: **30 passed**.
- `tests/smoke_test.py` (manual, hardware) passou a usar `WakeWordDetector(wake_words={"ei assistente"})`. Não foi executado.
- Typecheck: `tsc --noEmit -p tsconfig.json` sem erros.
- Smoke Playwright com APIs mockadas: `workspace.smoke.cjs` ganhou o passo "perfil do agente carrega, recusa frase fora do vocabulário e salva". Ele e `runs.smoke.cjs` passaram. Captura: `item2-screens/desktop-agent-profile.png`.

## Observação de ambiente

Já havia um Vite dev server em 127.0.0.1:5173 (PID 12708, iniciado antes deste passo), e o meu falhou com "port in use". Os smokes rodaram contra esse servidor. Ao encerrar, parei esse processo por engano e subi outro no mesmo endereço (`vite --host 127.0.0.1 --port 5173`, PID 17384), que continua rodando. Backend real não foi iniciado.
