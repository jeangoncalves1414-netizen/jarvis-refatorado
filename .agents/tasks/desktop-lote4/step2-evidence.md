# Lote 4, passo 2: C6 (voz, Swarm, Racing e memória em segundo plano na Central, com origem)

## O que mudou
- **Origem no Run** (`app/core/runs.py`): `RunRecord.origin` (padrão `chat`; registros antigos sem o campo continuam legíveis). `RUN_ORIGINS = chat, voice, routine, clap, window, mobile, system` e `run_origin()` para normalizar. Do cliente continuam chegando só `chat` e `voice` (`REQUEST_ORIGINS`); `routine`, `clap` e `mobile` ficam prontos para os gatilhos futuros.
- **Armazenamento** (`app/storage/action_store.py`): `create_run(..., source=, origin=)`; `add_run_event(run_id, kind, summary)` grava etapa interna sem ferramenta (texto passa por `redact`, até 300 caracteres), sem mudar o estado do pedido e mesmo depois do encerramento. Pedido que não é de conversa e termina sem ferramenta diz "Concluído; nenhuma ferramenta registrada.".
- **Turnos** (`app/agent/run_tracking.py`): `track_run` grava a origem do turno (voz ou chat; chamada sem origem herda a do pedido atual). Novos: `record_run_step`, `background_run` (abre pedido para trabalho sem ferramenta) e `in_background` (embrulha alvo de thread; vira evento do pedido de origem, ou pedido próprio se não houver).
- **Swarm** (`app/agent/swarm.py`): cada especialista grava "acionado", "concluiu" ou "não concluiu: motivo". O modo paralelo copia o contexto para cada thread. A rota direta `/api/swarm` abre pedido `mode=swarm`, `source=api:swarm`, origem `window`, e devolve `run_id`.
- **Racing** (`app/services/llm_racing.py`, `orchestrator.py`): `race_prompt` devolve `attempts` (provedor, `winner`/`empty`/`failed`/`discarded`, tempo, nome da exceção), sem o texto das respostas. O orquestrador grava cada tentativa e a falha da corrida no pedido.
- **Memória em segundo plano**: extração de memória da mensagem (chamada ao modelo) e salvamento da conversa na memória semântica (`/api/chat/stream` e WebSocket) viram eventos `background`/`background_failed` do pedido que os disparou. O resumo diário (agendador) vira pedido próprio com origem `system`, `mode=memory`, `source=background:daily_summary`.
- **Rotas diretas** (`action_gateway.run_action`): parâmetro `origin` (padrão `window`); `/api/script/run` usa `chat`. O Run também guarda `source`.
- **Central** (`frontend/src/components/RunHistory.tsx`): linha do pedido mostra a origem ("Voz · data"); detalhe tem "Origem"; eventos internos aparecem como "Etapa interna", "Etapa com falha", "Segundo plano". Novos rótulos de modo (memória, controles, navegador, script, terminal).

## Decisões tomadas sem perguntar
- Acrescentei a origem `system` ("Segundo plano") para trabalho sem pedido da usuária (resumo diário). As seis origens pedidas estão todas lá.
- Memória disparada por um turno não cria pedido novo: vira evento do próprio turno (menos ruído na Central e ligado à conversa). Só o resumo diário, que não tem turno, abre pedido.
- Etapas internas de Swarm e Racing são eventos do pedido, não ações: não executam ferramenta nem pedem aprovação.
- `/api/swarm`, `/api/browser/run` e o terminal ficaram com origem `window` (rotas do painel).
- `tests/test_control_plane_security.py`: o tempo-limite do cliente HTTP do teste subiu de 3 s para 15 s. Esses testes estouravam 3 s também no HEAD anterior (conferido com `git stash` das minhas mudanças), por máquina lenta; nenhuma asserção mudou.

## Testes
- `tests/test_run_origins.py` (novo, 12 testes): origens; voz cria Run com origem `voice`; herança e valor desconhecido; etapas internas; Swarm; falha de `background_run`; Racing sem texto da resposta; memória como evento depois do fim do turno; memória capturada dentro do turno; trabalho sem pedido abre pedido próprio; resumo diário `system`; rotas diretas com `window`/`chat`.
- `test_god_mode_components.py test_llm_racing.py test_runs.py test_conversation_runtime.py test_action_gateway.py test_run_origins.py test_action_history.py test_mission_control.py test_chat.py`: **97 passed**. `test_control_plane_security.py` + `test_run_origins.py`: **24 passed**. Antes, `test_orchestrator.py` no mesmo lote passou.
- `tsc --noEmit`: sem erros.

## Não verificado
- Voz real, provedores reais na corrida, memória semântica real (Chroma) e agendador rodando no backend real.
