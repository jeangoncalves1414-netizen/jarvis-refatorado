# Investigação: memória, criação de hábitos e qualidade do modelo (11/11/2026)

Investigação somente leitura em `main` @ 7cab802. Nenhum código ou dado real foi alterado. As reproduções rodaram em um diretório temporário (`%TEMP%\jv_iso`) com cópia do índice vetorial. As chaves de API foram omitidas.

## Resumo

1. **Memória.** O agente quase não grava fatos sobre você, e o que fica gravado raramente chega ao prompt. O modelo não tem ferramenta de memória: `memory_kernel.py:1-5` diz explicitamente que a ferramenta "não está no registro nem é oferecida ao modelo". A busca semântica só roda quando a frase bate num regex estreito (`context_policy.py:18-26`). "O que você sabe sobre mim?" e "tem alguma memória salva?" não batem. A única memória que entra em todo turno é o `USER-PROFILE.md` do cofre, e esse arquivo foi poluído pelos testes: aparece "Nome: Usuário" e a linha "Prefere testes automatizados com unittest" repetida 22 vezes. O agente respondeu exatamente isso quando você perguntou o que ele sabia sobre você. Ele não alucinou: repetiu o contexto sujo que recebeu. As memórias boas que existem (por exemplo "O usuário criou o sistema Jarvis") são descartadas por um filtro de 90 dias.
2. **Hábitos.** As falhas têm quatro causas, todas no código ou no esquema das ferramentas. O modelo só contribuiu escolhendo campos errados porque não recebeu a lista de campos válidos.
   - (a) `print()` com caractere fora do cp1252 derruba a chamada ao modelo com `UnicodeEncodeError` (reproduzido). Os hábitos já tinham sido criados, mas o turno aparece como falha.
   - (b) No loop agêntico, `personal_records.fields` chega ao modelo só como `"object"`, sem os campos aceitos. O modelo então copiou colunas do banco (`color`, `icon`, `frequency_type`, `target_days_per_week`) e a lista `habits`. O resultado foi o erro "Campos não reconhecidos".
   - (c) Não há verificação de duplicata: cada nova tentativa criou os mesmos hábitos de novo (8 hábitos, 3 duplicados).
   - (d) O horário padrão `15:00` foi aplicado a "Acordar às 5:00", e o auto-check marcou esse hábito como feito às 18:12 só porque a mensagem tinha a palavra "acordar".
3. **Modelo.** A rota de chat usa `groq / openai/gpt-oss-120b`. Pelos limites publicados pela Groq hoje, esse já é o modelo mais forte disponível no plano gratuito (30 RPM, 1K RPD, 8K TPM, 200K TPD). O Llama 3.3 70B passou a ser Enterprise. Os erros vistos vêm de contexto e ferramentas mal entregues:
   - um único pedido de hábitos custa cerca de 9–11K tokens na primeira chamada, acima do limite de 8K TPM;
   - as descrições das ferramentas são cortadas em 200 caracteres e perdem as regras de uso;
   - o system prompt cita cerca de 25 ferramentas, mas o modelo recebe só 16;
   - há apenas uma rodada de ferramentas por turno;
   - o perfil injetado está sujo.

   Troque o contexto antes de trocar o modelo.

---

## Problema 1: memória

### Evidência

**Onde as memórias ficam: seis lugares, nenhum é a fonte única.**

| Armazenamento | Arquivo | Conteúdo real | Entra no prompt? |
|---|---|---|---|
| Fatos com fonte (fase contexto 2) | `data/memory_facts.json` | **Não existe** | `turn_context._memories`, sempre (até 3 fatos / 300 caracteres) |
| Chroma `user_memory` | `data/vector_db` | 18 itens, o último de 09/11. Quase todos triviais ("ativou o modo cinema", "vai testar a interrupção") | Só quando `requests_saved_memory()` é verdadeiro |
| Chroma `episodic_memory` | idem | **0 itens** (o resumo diário nunca gravou) | Idem |
| Chroma `conversations` | idem | 91 turnos | **Nunca é lido**: só há escrita em `server.py:1572,2253` |
| `data/memory.json` (MemoryStore) | | 8 "preferências" que na verdade são comandos ("quero que você abra o Roblox") | Filtradas na leitura por `context_preferences` |
| `data/preferences.json` | | "meu nome é Alex", gravado por `tests/smoke_test.py:33` | Não |
| Cofre `02-User-Profile/USER-PROFILE.md` | | "Nome: Usuário" e "Prefere testes automatizados com unittest" ×22, gravados por `tests/test_desktop_modules.py:29` | **Sempre**, os primeiros 600 caracteres (`orchestrator.py:513-516`) |
| Cofre `05-Notas/Fato-sobre-o-usuário.md` | | "Usuário gosta de pizza" (11/11) | Não. Só via `vault_search`, que só é oferecido quando a frase contém "nota" ou "cofre" |
| `data/profile_memories.json` | | Não existe (nenhuma identidade confirmada no chat) | Não |

As notas diárias do cofre também estão cheias de "Testando integração do Memory Vault", gravadas por `tests/test_desktop_modules.py:22`.

**Conversa real 0c2023c6 (11/11, 17:52):**
- Você: "voce tem acesso há alguma mensagem anterior? também tem alguma memória salva?" → Jarvis: "Não... Não tenho acesso a memórias".
- Você: "Consegue salvar um fato sobre mim? ... gosta de pizza" → foi salvo como nota do cofre via `personal_records` (ação #166).
- Você: "Não é no cofre, é na memória" → foi salvo de novo no cofre (#167). O modelo não tem outra ferramenta para isso.

**Conversa 795174dc (17:57):** "O que voce sabe sobre mim?" → "Sei que seu nome é Usuário, prefere comunicação direta... testes automatizados com unittest". Essa resposta é o `USER-PROFILE.md` poluído, repetido literalmente.

**Gatilhos de recuperação** (testados em isolamento):
- `requests_saved_memory('O que voce sabe sobre mim?')` → **False**
- `requests_saved_memory('...também tem alguma memória salva?')` → **False**
- `requests_saved_memory('qual é o meu nome?')` → **False**
- `requests_saved_memory('Você lembra do meu nome?')` → True

O regex exige um verbo de busca (busca/lembra/qual/o que) **e** uma fonte (memória/cofre/outro chat) (`context_policy.py:22-25`).

**Gatilhos de gravação.** `_MEMORY_TRIGGERS` (`orchestrator.py:90-94`) não contém "gosto", "gosta", "salva", "memória" nem "sobre mim". Por isso "usuário gosta de pizza" não disparou a extração. A opção `extract_memory_always` está desligada por padrão (`runtime_settings.py:597`). `memory_slots.parse()` só reconhece música, cidade e apps: `parse('Meu nome é Jean')` → None.

**Recuperação semântica** (testada numa cópia do índice):
- `max_age_days=90` (`semantic_memory.py:43,146`) descarta tudo com mais de 90 dias, sem levar em conta a importância. Para "quem criou o Jarvis?", a melhor resposta ("O usuário criou o sistema Jarvis", distância 0,174, de 02/08) é **filtrada**, e volta "quer uma assistente estilo Jarvis".
- Não existe limite de distância: para "qual comida eu gosto?" volta "vai dar comida apenas de manhã e à noite" (0,569).
- Os embeddings vêm do modelo padrão do Chroma, `all-MiniLM-L6-v2` (384 dimensões, treinado em inglês), apesar de as memórias estarem em português.
- `access_count` nunca é incrementado, porque o código procura `metadata["id"]`, que não existe (`semantic_memory.py:156`). Todos os 18 itens estão com 0.

**Falhas silenciosas:**
- `orchestrator.py:395-398` (`save_via_kernel` dentro de `except Exception: pass`);
- `turn_context.py:40-44`;
- `orchestrator.py:504,517` (perfil e cofre);
- `semantic_memory.search_memories` devolve `[]` em qualquer exceção.

O `memory_facts.json` nunca foi criado, embora o kernel exista desde 09/11 12:49 (4132381) e o `user_memory` tenha recebido 4 itens às 14:56 do mesmo dia. Também não há nenhuma ação `memory_tool` no `action_journal` (190 ações). Em isolamento, `save_via_kernel` funciona. A causa provável é que o processo estava rodando código antigo ou que a falha foi engolida pelo `except: pass`. Não dá para provar qual das duas com os logs atuais.

**Histórico perdido.** As sessões 795174dc e 6e5b5a23 têm 6 e 3 execuções no journal, mas o `sessions.json` guardou só a primeira troca de uma e nenhuma mensagem da outra. O histórico só é salvo pelo frontend (`frontend/src/hooks/useChat.ts:212,462,890`), e turnos com falha não chegam a ser gravados. Isso também afeta o resumo episódico, que lê o `sessions.json`.

### Causa raiz
1. O modelo não tem ferramenta de memória (salvar, buscar, esquecer). Fatos pedidos explicitamente vão para o cofre, que não é reinjetado.
2. A recuperação depende de um regex estreito, e não existe um perfil essencial do usuário injetado em todo turno.
3. A única fonte injetada sempre (`USER-PROFILE.md`) está poluída pelos testes, que gravam no `data/` real.
4. Os gatilhos de extração são estreitos, o parser de slots é limitado e os erros são engolidos.
5. O índice semântico expira memórias após 90 dias, não tem limite de distância e usa embeddings em inglês.
6. Os seis armazenamentos são desconectados. A coleção `conversations` é escrita e nunca lida, e a `episodic_memory` está vazia.

### Plano de correção (em ordem)
1. **Isolar os testes do `data/` real.** Em `tests/test_desktop_modules.py` e `tests/smoke_test.py`, apontar `memory_vault.VAULT_DIR` e `user_preferences.PREFERENCES_FILE` para `tmp_path` (monkeypatch). Verificar com `pytest tests/test_desktop_modules.py tests/smoke_test.py`: o hash de `data/vault/02-User-Profile/USER-PROFILE.md` deve ficar igual antes e depois. Em seguida, **com sua aprovação**, limpar `USER-PROFILE.md` (duplicatas, "Nome: Usuário"), as notas diárias de teste, `memory.json.preferences` e `preferences.json` (fazer backup antes).
2. **Ferramenta `memory`** (nova, `app/agent/tools/memory_tool.py`) com as ações `save`, `search`, `list` e `forget`. Ela grava via `memory_kernel.save_via_kernel` (`memory_facts` vira a fonte da verdade, com recibo na Central) e indexa em paralelo no Chroma `user_memory`. A busca combina `memory_facts.relevant` com a busca semântica. Incluí-la em `GENERAL_TOOL_NAMES`, `core_groq` e `LOOP_DATA_TOOLS` (`registry.py`), e acrescentar ao `prompts.py` a regra: "fato duradouro sobre a usuária → memory save; pergunta sobre ela → memory search; cofre é para anotações". Testes: `tests/test_memory_tool.py` com save → search → forget num `DATA_DIR` temporário, e um teste de registro garantindo que `memory` está em `allowed_tool_names('general','groq','O que você sabe sobre mim?')`.
3. **Perfil essencial em todo turno.** Em `turn_context.py`, injetar até cerca de 500 caracteres com os fatos fixados ou de maior importância de `memory_facts` (nome, cidade, família, preferências), além dos 3 relevantes. Adicionar os campos `pinned` e `importance` em `memory_facts.save`. Remover a injeção crua de `USER-PROFILE.md[:600]` (`orchestrator.py:513-516`), ou passar a gerá-lo a partir de `memory_facts`. Testes: estender `tests/test_memory_facts.py` e `tests/test_context_policy.py`.
4. **Ampliar a recuperação.** Fazer `requests_saved_memory` aceitar "sobre mim", "meu nome", "você sabe", "tem memória" e "lembra". Melhor ainda: rodar sempre a busca barata (`memory_facts.relevant`) e a semântica só com distância ≤ 0,45. Teste: casos de `requests_saved_memory` com as frases reais citadas acima.
5. **Extração.** Adicionar "gosto", "gosta", "adoro", "odeio", "salva", "memoriza", "memória", "meu/minha <relação>", "tenho <n> anos" a `_MEMORY_TRIGGERS`. Adicionar o slot `name` em `memory_slots`. Trocar os `except: pass` por `record_run_step(..., kind="failure")`. Testes em `tests/test_memory_params.py` e `test_memory_facts.py`.
6. **Índice semântico.** Remover a expiração de `user_memory` (manter só para `conversations`), aplicar limite de distância, corrigir `access_count` usando os ids que o Chroma devolve, e trocar o embedding por um multilíngue: `paraphrase-multilingual-MiniLM-L12-v2` local, ou `gemini-embedding-001`, que já está em `oxyy_models.embedding`. A troca exige reindexar.
7. **Decidir sobre `conversations` e `episodic_memory`.** Ou usar `conversations` para a busca "outras conversas" ou parar de gravá-la. Investigar por que `_run_daily_summary` nunca gravou nada (depende de `self.scheduler`).
8. **Persistir o histórico no backend** ao final de cada execução, incluindo as que falharam, em vez de depender só do `useChat.ts`.

---

## Problema 2: erros ao criar hábitos

### Evidência (11/11, 18:09–18:12)

| Execução | Sessão, modo | Chamadas (ação #) | Resultado |
|---|---|---|---|
| run_62b6… | 795174dc, auto→loop | `personal_records preview query="*"` ×2 (#168-169) | Prévia de **exclusão** com 0 registros. O modelo usou `preview` (ação de exclusão em lote) em vez de `list`. A execução terminou como `failed` |
| run_b498… | 795174dc, thinking | nenhuma | `groq falhou: Erro do provedor (APIError)`. O motivo exato não foi gravado, só o tipo da exceção |
| run_8f40… | 795174dc, thinking ("Agora cria os hábitos que pedi") | `habit_tool list` (#172) → "0 hábito(s)" | Parou aí: o modo de function calling só permite **uma rodada** de ferramentas (`llm.py` `_chat_groq_stream`). Não houve como listar e depois criar |
| run_957b… | 6e5b5a23, react | `personal_records list` ✓, `create fields={habits:[…]}` ✗ (#174, "Campos não reconhecidos: habits"), `preview` ✓, 3× `create` ✓ (#176-178) | 3 hábitos criados, mas a execução foi marcada `failed` |
| run_85d6… | 6e5b5a23, react | `routine create reset_habits` com etapa `personal_records` ✗ (#179, "ferramenta desconhecida 'personal_records'"), `list` ✓, 5× `create` com `color, frequency_type, icon, target_days_per_week` ✗ (#181-185) | Terminou em `groq falhou: UnicodeEncodeError` |
| run_41f3… | 6e5b5a23, auto→loop | 5× `create` ✓ (#186-190) | Hábitos criados, depois `groq falhou: UnicodeEncodeError` |

Estado em `lifestyle.db.habits`: 8 hábitos, todos com `start_time='15:00'`. "Acordar às 5:00 da manhã", "Arrumar a cama" e "Beber 1 L de água" estão **duplicados**. O nome "Beber 2\u202fL" contém U+202F (espaço fino que o gpt-oss costuma gerar). Em `habit_logs` aparece `habit_192a78aa` ("Acordar às 5:00") marcado como feito em 11/11 às 18:12, com a nota "Auto-check contextual: saudação matinal".

**Reproduções no diretório temporário:**
- `personal_records.dispatch(create, habit, fields={'habits':[...]})` → `ValueError: Campos não reconhecidos: habits`.
- O mesmo com `color/icon/frequency_type/target_days_per_week` → idem.
- `create` sem horário → "criado ... às 15:00". O segundo `create` igual cria **outro** hábito.
- `HabitTool.create_many` com 2 hábitos → OK. O caminho correto existe, mas o modelo não o usou.
- `routine create` com etapa `personal_records` → "ferramenta desconhecida 'personal_records'".
- `personal_records list kind=habit` devolve ao modelo 30 chaves, entre elas `color`, `icon`, `frequency_type` e `target_days_per_week`. Foi daí que o modelo copiou os campos.
- `python -c "print('2\u202fL')" | Out-String` e `print('→')` → `UnicodeEncodeError: 'charmap'` quando o stdout é um pipe (encoding `cp1252`; ver `sys.stdout.encoding`).

### Causa raiz
1. **UnicodeEncodeError (bug de código).** Há `print()` com caracteres fora do cp1252 em caminhos de erro do modelo. O caso certo é `llm.py:282` (`print(f"[LLM] Failover automático: {active} → {fallback} ...")`, a seta "→" sempre falha). Outros casos possíveis são os prints com texto do modelo ou das ferramentas (`llm.py:677,1277,1359,1393`). Quando o backend roda com stdout redirecionado (processo iniciado por pipe), qualquer falha do Groq, como 429 ou 413 de TPM, vira `UnicodeEncodeError`. Isso esconde o erro real e derruba a síntese depois que as ações já tinham sido executadas. Você vê "falhou", tenta de novo, e os hábitos são duplicados.
2. **Esquema incompleto no loop agêntico (bug de código ou descrição).** `react_loop._compact_schema` (`react_loop.py:110-127`) reduz os parâmetros a `"fields": "object"` e corta a descrição em 160 caracteres (`_DESCRIPTION_CHARS`). O modelo não fica sabendo que, para hábito, só valem `title, target_value, unit, days_of_week, start_time`, e nem que existe `habit_tool create_many`, porque a frase sobre `create_many` fica depois do caractere 200 da descrição.
3. **Duas interfaces para hábitos no mesmo turno.** `habit_tool` (com `name`, `category` e `habits` para criar em lote) e `personal_records` (`fields.title`, sem lote) são oferecidas juntas (`LOOP_DATA_TOOLS`). O modelo misturou os dois esquemas. `personal_records.mutate` (`personal_records.py:188-203`) rejeita tudo que não está em `allowed_fields`, e a mensagem de erro não diz quais campos são aceitos.
4. **Sem verificação de duplicata** em `HabitTool` `create`/`create_many` (`lifestyle_tools.py:262-299`) e em `HabitService.create_habit`.
5. **Padrões errados.** `_norm_time` devolve `"15:00"` quando não há horário (`lifestyle_tools.py:99-101`, `236`), e não extrai "5:00" do nome. `contextual_auto_check` roda em toda mensagem (`orchestrator.py:1220-1223`) e marca "Acordar" sempre que o texto contém "acordar" (`habits.py:369`), mesmo num pedido de cadastro e às 18h.
6. **Seleção de ferramentas por palavra-chave.** O regex de rotina `\bas \d{1,2}:\d{2}` (`registry.py:116` e o equivalente no loop) oferece a ferramenta `routine` porque a frase dizia "às 5:00". O modelo então tentou criar a rotina "reset_habits".
7. **Uma rodada de ferramentas** no modo function calling (`llm.py` `_chat_groq_stream`). Pedidos do tipo "listar e depois criar" param na primeira etapa.

O comportamento do modelo contribuiu (uso de `preview` para listar, invenção da rotina), mas sempre por falta de informação ou por ferramentas oferecidas sem necessidade.

### Plano de correção (em ordem)
1. **Encoding do stdout.** No início de `app/main.py:main()` e de `run_jarvis.pyw`, chamar `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` (e o mesmo para stderr), protegido para quando forem `None` (pythonw). Trocar a seta de `llm.py:282` por "->". Teste: `tests/test_stdout_encoding.py` executando `subprocess.run([sys.executable, "-c", "import app.main; ...print('→\u202f')"], stdout=PIPE)` sem `PYTHONIOENCODING`, esperando código de saída 0.
2. **Erro real visível.** Em `capability_health.failure_reason`, incluir o status HTTP e o código (429/413/400) quando existirem. Teste em `tests/test_capability_health*.py`.
3. **Uma interface de hábitos.** Em `personal_records.mutate`/`_delegate`, aceitar `fields.habits` (lista) para `kind=habit, action=create` e delegar a `HabitTool create_many`. Aceitar `name` e `category`. Ignorar com aviso as chaves somente leitura que `list` devolve (`color`, `icon`, `frequency_type`, `target_days_per_week`, `id`, `created_at`…), em vez de falhar. A mensagem de erro deve listar os campos aceitos. No registro, quando `personal_records` estiver presente, retirar `habit_tool` do turno (a mesma lógica de `redundant` em `registry.py:428-433`, que hoje só vale para algumas palavras), para que o modelo enxergue um único esquema. Testes: `tests/test_personal_records*.py`, cobrindo criação em lote, chaves somente leitura ignoradas e mensagem com os campos aceitos.
4. **Esquema útil no loop.** Em `react_loop._compact_schema`, preservar a `description` de parâmetros do tipo object (por exemplo os primeiros 300 caracteres de `fields`). Aumentar `_DESCRIPTION_CHARS` e reescrever as descrições de `personal_records` e `habit_tool` para que a regra principal ("vários hábitos = UMA chamada create com fields.habits") caiba nos primeiros 150 caracteres. Teste em `tests/test_react_loop*.py` verificando que `_tool_lines` contém "title" e "start_time" para `personal_records`.
5. **Duplicatas.** Em `_prepare_habit`/`HabitService.create_habit`, quando já existir um hábito ativo com o mesmo nome normalizado (`normalize_name`), devolver o existente com a mensagem "já existia". Isso torna as novas tentativas idempotentes. Teste em `tests/test_habits_tasks_finance.py`.
6. **Padrões de horário.** Sem horário informado, gravar `start_time=""` (sem horário), extrair "às 5:00 / 5h" do nome quando houver e definir `routine_block=morning` antes das 12h. Revisar a migração `DEFAULT '15:00'` (`habits.py:80,114`) apenas para registros novos. Teste em `tests/test_modular_habits.py`.
7. **Auto-check.** Em `contextual_auto_check`, ignorar mensagens com verbos de cadastro (registre, crie, adicione, cadastre, "hábito de") e só aceitar "acordar" como relato no passado ("acordei", "bom dia") e antes das 12h. Teste com a frase real: nenhum check-in.
8. **Rotina.** Não oferecer `routine` quando o pedido contém "hábito". O erro "ferramenta desconhecida" deve listar as ferramentas permitidas numa etapa. Teste em `tests/test_routine*.py` e no registro.
9. **Execução com ações concluídas.** Quando a síntese falhar depois de ações bem-sucedidas, devolver o resumo das ações como resposta e marcar a execução como concluída com aviso, não como `failed`. Isso já é feito para 429 (`docs/limites-rotacao-2026-11-11.md`), mas não para outras exceções.
10. **Limpeza de dados (com sua aprovação).** Arquivar os 3 hábitos duplicados e o check-in automático indevido, usando o desfazer da Central ou `personal_records undo`.

---

## Problema 3: modelo, contexto e ferramentas

### Evidência
- **Modelo configurado.** `data/runtime_settings.json` → `routes.chat = groq / openai/gpt-oss-120b`, `llm_provider=groq`. O `.env` tem `GROQ_MODEL=openai/gpt-oss-120b` e `GEMINI_MODEL=gemini-2.5-flash` (fallback). Há 4 chaves Groq em rotação. `reasoning_effort` padrão `medium` (`llm.py:1170-1175`).
- **Limites da Groq** (página oficial [Rate limits](https://console.groq.com/docs/rate-limits) e [Models](https://console.groq.com/docs/models), consultadas em 11/11/2026). No plano gratuito, os modelos de chat listados são `openai/gpt-oss-120b`, `openai/gpt-oss-20b` e `qwen/qwen3.8-27b`, todos com 30 RPM, 1K RPD, 8K TPM e 200K TPD. `llama-3.3-70b-versatile` e `llama-3.1-8b-instant` agora são "Enterprise". O `qwen3.8-27b` está em preview. *Conteúdo reformulado por questões de licenciamento.*
- **Medição de tokens por pedido** (tiktoken `o200k_base`, registro real com 64 ferramentas, modo general, Groq):

| Componente | "Olá" / "O que sabe sobre mim?" | Pedido de hábitos |
|---|---|---|
| System prompt (com perfil de 600 caracteres) | ~1.950 | ~1.950 |
| Contexto situacional e memórias com fonte | ~100–300 | ~100–300 |
| Ferramentas (descrição em 200 caracteres + esquema completo) | **16 ferramentas ≈ 4.050** | **19 ferramentas ≈ 6.280** (entram `habit_tool`, `lifeos_tool` e `routine` por palavra-chave) |
| Histórico (10 mensagens, até 10.000 caracteres, `llm.py:1128`) | até ~2.800 | até ~2.800 |
| **Total da 1ª chamada** | **~6–9K** | **~9–11K** |

Uma rodada com ferramentas faz duas chamadas (decisão e síntese). A síntese reenvia o system prompt, o histórico e os resultados, cerca de 4–6K tokens a mais, e o `reasoning_effort=medium` acrescenta tokens de saída. Ou seja, **um único pedido de hábitos passa sozinho do limite de 8K TPM**. Com 200K TPD, a conta comporta só cerca de 12–18 turnos com ferramentas por dia. O log de 10/11 mostra que o limite diário foi esgotado (198.675 de 200.000; `docs/limites-rotacao-2026-11-11.md`). As 4 chaves só somam cota se forem de organizações diferentes, porque os limites valem por organização.
- **Corte de contexto do lote 7.** A economia corta exatamente o que orienta o modelo e mantém o que pesa:
  - as descrições caem para 250 (`registry.py:465`) e depois para 200 caracteres (`llm.py:1148`). A regra de `create_many` do `habit_tool` e quase toda a descrição de `personal_records` (751 caracteres) se perdem;
  - os esquemas JSON completos, que são o maior volume, continuam;
  - o system prompt manda usar cerca de 25 ferramentas (`realtime`, `clipboard`, `proactive_agent`, `system_tray`, `task_tool`, `finance_tool`, `vault_*`, `places_search`, `show_popup`…), mas o turno "Olá" recebe só 16;
  - o histórico do loop agêntico é de 4 mensagens com 300 caracteres cada (`react_loop.py:34`, `_CONVERSATION_CHARS`), e a lista de hábitos ditada antes pode ser cortada;
  - a memória só entra quando o regex permite (Problema 1).
- **O system prompt se contradiz** (ver o texto montado): "Estilo: Neutro, cordial e conciso" contra "Tom (amigável): Caloroso, empático"; "Voz: sem markdown" no chat de texto.
- **Exemplos de "alucinação" e a causa real de cada um:**
  - "Seu nome é Usuário... unittest": contexto poluído (Problema 1).
  - "Não tenho acesso a memórias": verdade, porque o modelo não tem ferramenta de memória.
  - Salvou no cofre depois de ouvir "não é no cofre": sem ferramenta de memória.
  - Campos inventados: esquema reduzido a `object`.
  - `preview` usado como listagem: descrição cortada.
  - Rotina "reset_habits": ferramenta oferecida por regex de horário.
  - Resumo de vídeo em tabela contra a regra do prompt (run_cc29…): regra fraca, modelo de raciocínio.

  Nenhum dos casos exige um modelo maior.
- **Erro mascarado.** `LLMService.ask` (`llm.py:179-185`) devolve "Erro ao acessar a API do Groq: ..." como **texto** de resposta. No loop agêntico esse texto vira o "plano" do modelo.
- **Segurança.** `data/runtime_settings.json` guarda em texto puro as chaves Groq (4), Gemini, Oxyy e Fish (valores omitidos neste relatório).

### Causa raiz
O modelo recebe muitas ferramentas com descrições mutiladas e um prompt que cita ferramentas ausentes. Ele recebe ainda contexto pessoal sujo, nenhuma memória útil e apenas uma rodada de ferramentas, tudo dentro de 8K TPM, que um único pedido já ultrapassa. A capacidade do gpt-oss-120b não é o gargalo.

### Plano de correção (independe do modelo)
1. **Orçamento por pedido de ≤ 6K tokens no Groq.** Medir com um contador (heurística de caracteres / 3,5, ou `tiktoken` se estiver disponível) e cortar nesta ordem: ferramentas não citadas, histórico antigo, situacional. Nunca cortar a última mensagem, o perfil essencial ou as regras. Implementar em `app/agent/context_budget.py` e aplicar em `_chat_groq_stream` e no `react_loop._build_prompt`. Teste em `tests/test_context_budget.py`: dado o registro real e o pedido de hábitos, o pacote final fica ≤ 6K.
2. **Menos ferramentas, descrições inteiras.** Reduzir `core_groq` (`registry.py:401-405`) a cerca de 8 ferramentas de uso diário (`personal_records`, `memory`, `web_search`, `open_windows_app`, `spotify`, `calendar`, `timer`, `wait`). Adicionar as demais só por palavra-chave. Manter a descrição completa, reescrita para ≤ 250 caracteres com a regra principal no começo. Enxugar os esquemas: tirar `description` redundantes e enums longos. Teste: snapshot dos tokens de ferramentas por frase.
3. **Prompt coerente com o turno.** Em `prompts.build_function_calling_system_prompt`, gerar a "REGRA Nº 2" a partir das ferramentas realmente oferecidas, e remover a contradição de tom e o "sem markdown" do chat de texto. Teste: nenhuma ferramenta citada no prompt fica fora de `allowed_tool_names`.
4. **Mais de uma rodada de ferramentas** no `_chat_groq_stream` (até 3 rodadas com o mesmo orçamento), ou encaminhar ao loop agêntico pedidos que precisam de "listar e depois agir". Teste com um modelo falso que faz `list` e depois `create_many`.
5. **`reasoning_effort=low`** no chat simples (`GROQ_REASONING_EFFORT`) e `medium/high` só em planning/thinking. Isso economiza tokens de saída no TPM.
6. **Fallback por tamanho.** Quando o pacote estimado passar de 7K, mandar direto para Gemini 2.5 Flash, que já está configurado, em vez de tomar um 413/429 no Groq. Isso exige conferir a cota gratuita atual do Gemini na conta.
7. **Chaves fora do `data/`.** Mover para `.env` ou o cofre de credenciais do Windows (Credential Manager). Fazer em etapa separada e com seu acordo.

**Sobre trocar o modelo Groq:** no plano gratuito não há opção mais inteligente que `openai/gpt-oss-120b`. O `qwen/qwen3.8-27b` tem os mesmos limites, está em preview e pode ser descontinuado. O `gpt-oss-20b` é mais rápido e mais fraco. A recomendação é manter o gpt-oss-120b, aplicar as correções acima e usar o Gemini 2.5 Flash para turnos pesados.

---

## Prioridades combinadas
1. **stdout UTF-8 e seta de `llm.py:282`**: elimina o `UnicodeEncodeError` que derruba os turnos e provoca duplicatas (Problema 2, item 1).
2. **Isolar os testes do `data/` real e limpar `USER-PROFILE.md`**: tira o contexto falso de todo prompt (Problema 1, item 1). A limpeza dos dados precisa da sua aprovação.
3. **Ferramenta `memory` e perfil essencial em todo turno** (Problema 1, itens 2–3).
4. **Hábitos**: lote em `personal_records`, uma interface só, esquema útil no loop e idempotência (Problema 2, itens 3–5).
5. **Orçamento de tokens ≤ 6K, menos ferramentas, descrições inteiras e prompt gerado pelas ferramentas oferecidas** (Problema 3, itens 1–3).
6. **Horário padrão, auto-check e regex de rotina** (Problema 2, itens 6–8).
7. **Recuperação semântica**: sem expiração, com limite de distância e embedding multilíngue (Problema 1, itens 4–6).
8. **Várias rodadas de ferramentas, `reasoning_effort` low e fallback por tamanho** (Problema 3, itens 4–6).
9. **Histórico persistido no backend, erros visíveis na Central e chaves fora do `data/`.**

Comando de verificação geral do projeto: `python -m pytest tests -q` (`pyproject.toml`, `[tool.pytest.ini_options] testpaths=["tests"]`).
