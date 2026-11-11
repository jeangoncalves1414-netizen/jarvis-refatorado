# Memória, Hábitos e Entrega de Contexto

Documentação da implementação do plano `memoria-habitos-contexto` (fix/memoria-habitos-contexto).

## Memória

### Fontes de verdade

- **`data/memory_facts.json`**: fonte de verdade das memórias com fonte (VERSION=1). Cada fato guarda texto, slot opcional (`music`, `city`, `app.<categoria>`, `name`), valor, período e a fonte completa (data, conversa, run, origem chat/voz/painel e tipo gatilho/extração/manual). Exclusão é suave (`deleted_at`, lápide local) e `updated_at` acompanha cada mudança.
- **Índice semântico `user_memory`** (Chroma): opcional, mantém cópia para busca vetorial com metadados `fact_id` e `session_id`.

### Perfil essencial

`memory_facts.essential(max_chars=500)` retorna fatos fixados (`pinned=True`), importantes (`importance >= 0.7`) ou de slots essenciais (`name`, `city`), ordenados por `(pinned, importance, updated_at)` desc e limitados a 500 caracteres.

O perfil essencial é injetado em todo turno comum (chat e voz) via `turn_context.build_turn_sections()`, sob o header `## Perfil essencial do usuário`. Pedidos de histórico do chat ("Resuma o início deste chat") não recebem o perfil.

A injeção crua de `USER-PROFILE.md` (que continha o modelo "Nome: Usuário") foi removida de `orchestrator.py:513-516`.

### Ferramenta `memory`

Oferecida ao modelo via function calling nativo. Ações:
- **save**: grava fato duradouro em 3ª pessoa (nome, família, gostos, rotina); `pinned=True` marca fatos centrais (nome, cidade, família).
- **search**: busca fatos por texto (`memory_facts.relevant` + `essential()` quando vazio + busca semântica com `max_distance`).
- **list**: até 30 fatos vivos (id, text, pinned, data).
- **forget**: apaga por id ou por query única (pede aprovação, risco `high`).

Riscos no catálogo (`TOOL_CATALOG["memory"]`):
- `search`/`list`: `observe`
- `save`: `low`
- `forget`: `high` (aguarda aprovação)

Execução via `ActionExecutor` no turno: o recibo é a própria ação `memory` (não há `memory_tool` aninhado). A gravação usa `memory_kernel.save_fact()` que constrói a fonte e escreve `memory_facts` diretamente.

Escopo: `data/memory_facts.json` e o índice local `user_memory`.

### Limite de distância e expiração

- **`USER_MEMORY_MAX_DISTANCE = 0.45`** (distância cosseno com all-MiniLM-L6-v2): resultados além desse limite são descartados na busca semântica.
- **Coleção `user_memory` não expira por idade**: `_NO_EXPIRY_COLLECTIONS = frozenset({"user_memory"})`. As demais coleções (`conversations`, `episodic_memory`) ainda expiram em 90 dias.
- **`access_count`** é incrementado pelo id que o Chroma retorna (`results["ids"][0][i]`), não pelo metadata (que pode estar ausente).

### Recuperação e gatilhos ampliados

`requests_saved_memory()` (`context_policy.py`) retorna True para:
- Pergunta explícita por memória salva ("tem alguma memória", "memória salva")
- "sobre mim" + ("o que", "sabe", "lembra", "conhece")
- "qual/quais (é/são) (o/a/os/as) meu/minha/meus/minhas"
- "você sabe ... (mim|meu|minha|eu)" (até 40 chars)
- Lookup + source: ("busca", "procura", "consulta", "lembra", "qual") + ("memória", "cofre", "outros chats")

Continua False para:
- Negação ("não consulte a memória")
- "Salve isso na memória", "me lembre de abrir o Spotify amanhã" (comandos imperativos, não perguntas)
- Pedidos de histórico deste chat

`_MEMORY_TRIGGERS` (orchestrator.py) inclui: "prefiro", "me lembre", "lembra que", "meu nome e", "me chamo", "eu moro", "salva", "memoriza", "memoria", "sobre mim".

`_MEMORY_TRIGGER_RE`: `\b(gosto|gosta|adoro|odeio)\b`, `tenho N anos`, `meu/minha (filh|mae|pai|espos|marido|namorad|irma|cachorr|gat|avo|tia|tio|prim|chefe|amig)`.

### Falhas registradas

Todas as fontes do contexto do turno (`_situational`, `_profile`, `_memories`) e os salvamentos de memória (`save_trigger_memory`, `save_via_kernel`, `profile_memory`) registram falhas via `record_run_step(..., kind="failure")` em vez de engoli-las silenciosamente.

`_extract()` (extração em segundo plano) trata `ProviderErrorText` como falha e conta `save_via_kernel` com `ok=False` ou exceção, levantando `RuntimeError` no fim para que `in_background` registre `background_failed`.

## Embeddings: decisão pendente

O modelo de embedding de todas as coleções é controlado por um único ponto: `semantic_memory.embedding_function()`.

Atualmente retorna `None`, mantendo o padrão do Chroma (**all-MiniLM-L6-v2**, ONNX local, monolíngue).

Alternativas consideradas:
- **paraphrase-multilingual-MiniLM-L12-v2**: multilíngue, local, melhor para pt-BR.
- **gemini-embedding-001**: API remota do Google, alta qualidade, exige chave e rede.

Trocar o modelo exige **reindexar todas as coleções existentes** (`user_memory`, `conversations`, `episodic_memory`), porque vetores de modelos diferentes não são comparáveis. Também será necessário reajustar `USER_MEMORY_MAX_DISTANCE` com base nas distâncias medidas do novo modelo.

Decisão final pendente.

## Contexto no Groq

### Orçamento de tokens por pedido

`context_budget.py` estima tokens por `ceil(len(text) / 3.2)` (3.2 chars/token, sem tiktoken). A configuração é lida de `runtime_settings.get_groq_budget_settings()`:

```json
{
  "groq_budget": {
    "size_fallback": true,
    "request_budget": 6000,
    "fallback_above": 7000
  }
}
```

Valores padrão em `GROQ_BUDGET_DEFAULTS` (`runtime_settings.py`):
- `request_budget`: 6000 tokens (máximo por pedido)
- `fallback_above`: 7000 tokens (troca para Gemini quando estimativa excede)
- `size_fallback`: `true` (ativa a troca automática)

### Ordem de corte

`context_budget.fit_request()` mantém:
1. Última mensagem do usuário
2. `## Perfil essencial do usuário`
3. Resto do system prompt (regras, modo)

Remove na ordem:
1. Ferramentas não mencionadas pelo último user message (literal ou via keyword), maiores primeiro
2. Mensagens antigas do histórico, mais antigas primeiro
3. Seção `## Situação agora`

Ferramentas mencionadas, o perfil essencial e a última mensagem nunca são cortadas.

`_chat_groq_stream` (llm.py) recusa chamadas a ferramentas que foram aparadas, retornando "A ferramenta X não foi oferecida neste turno; nada foi executado." O executor nunca roda uma ferramenta que o modelo não viu.

### Esforço de raciocínio

Configurado via variáveis de ambiente:
- **`GROQ_REASONING_EFFORT`**: padrão `"low"`, usado em chat simples (mode `general`, `lifeos`, `coder_pro`)
- **`GROQ_REASONING_EFFORT_DEEP`**: padrão `"high"`, usado em modos `planning`, `thinking` ou quando o system prompt contém "MODO DE PLANEJAMENTO"

Valores aceitos: `low`, `medium`, `high`.

### Troca por tamanho (size fallback)

Quando o pedido estimado excede `fallback_above` (padrão 7000 tokens), `size_fallback` está ativado e uma chave Gemini existe, o Groq chama `capability_health.note_route_switch(f"pedido estimado em {tokens} tokens, acima de {limit}")` e repassa o pedido completo (sistema, histórico e ferramentas originais, sem cortes) para `_chat_gemini_stream`.

A troca fica visível na Central como um evento de fallback: "Modelo: gemini (...) respondeu no lugar de groq. Motivo: pedido estimado em X tokens, acima de Y."

O estado de `capability_health.get("chat")["fallback"]["reason"]` também carrega o motivo.

### Até 3 rodadas de ferramentas

`_chat_groq_stream` (llm.py) executa até `MAX_TOOL_ROUNDS = 3`:
1. Primeira rodada: chamada normal com ferramentas
2. Rodadas 2-3: se o modelo retorna `tool_calls` sem texto final, as mensagens de ferramentas (resultado limitado a 2000 chars) são adicionadas ao histórico e o modelo é chamado novamente
3. Quando o modelo retorna texto sem tool calls, ou quando a rodada 3 termina, a síntese final é gerada (possivelmente sem ferramentas)

Orçamento é re-estimado a cada rodada. Se o pedido excede o budget, a síntese final é feita sem oferecer ferramentas de novo.

## Modelo

Mantido em **`openai/gpt-oss-120b`** (Groq).

O relatório consultou modelos gratuitos do Groq disponíveis em novembro de 2024 e concluiu:
- `qwen/qwen3.8-27b`: preview, mesmos limites de taxa do atual (6K TPM, 30 RPM)
- `openai/gpt-oss-20b`: mais fraco que o atual
- Llama 3.3 70B: Enterprise (pago)

Não há modelo Groq gratuito mais inteligente com cota suficiente. A decisão foi manter o modelo atual.

## Próximo passo: histórico no backend

Item 8 do relatório original (`review-study-system.md`), não implementado neste plano.

Proposta: persistir `session_history` (mensagens de cada `session_id`) no backend (Supabase) para:
- Sincronização entre dispositivos (web, mobile)
- Histórico além do cache local
- Fonte para `episodic_memory` e análise de evolução

Pendente decisão e implementação futura.
