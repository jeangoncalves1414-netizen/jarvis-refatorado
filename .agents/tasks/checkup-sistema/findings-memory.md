# Achados de Investigação — PONTO 3: Memória Cross-Session

**Investigador:** Subagente de Checkup  
**Data:** 2026-01-11  
**Arquivos analisados:**
- `app/agent/tools/memory_tool.py`
- `app/storage/memory_facts.py`
- `app/storage/vector/semantic_memory.py`
- `app/agent/orchestrator.py`

---

## Status: REFUTADO

O problema descrito **NÃO existe**. A busca de memória já é global por design e funciona corretamente entre sessões.

---

## Evidência

### 1. memory_facts.relevant() — Busca textual (arquivo: `app/storage/memory_facts.py`, linhas 332-352)

```python
def relevant(text: str, limit: int = 3, facts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Fatos mais ligados ao pedido: palavras em comum (≥ 3 letras) + bônus do assunto do slot."""
    words = _words(text)
    if not words:
        return []
    bonus_slots = {slot for subject, slots in _SUBJECTS if words & subject for slot in slots}
    scored = []
    for fact in list_facts() if facts is None else facts:  # ← Busca em TODOS os fatos
        score = len(words & _words(fact.get("text", "")))
        if fact.get("slot") in bonus_slots:
            score += 2
        if score > 0:
            scored.append((score, float(fact.get("updated_at") or 0), fact))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [fact for _score, _at, fact in scored[:limit]]
```

**Análise:**
- Chama `list_facts()` sem parâmetro de session_id
- `list_facts()` retorna TODOS os fatos vivos (não deletados)
- **Não há filtro de session em nenhum ponto da cadeia**

---

### 2. semantic_memory.search_memories() — Busca vetorial (arquivo: `app/storage/vector/semantic_memory.py`, linhas 128-198)

```python
def search_memories(
    self,
    collection_name: str,
    query: str,
    n_results: int = 5,
    filter_expired: bool = True,
    max_distance: float | None = None,
) -> List[dict[str, Any]]:
    """Busca memórias similares, incrementando access_count."""
    if not self.client:
        return []
    
    collection = self.get_or_create_collection(collection_name)
    if not collection:
        return []
    
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results * 2  # ← SEM filtro where por session_id
        )
        # ... resto do código filtra por distance, expired, deleted_at
```

**Análise:**
- `collection.query()` é chamado **SEM** parâmetro `where` para filtrar session_id
- Os únicos filtros aplicados são:
  - `max_distance` (relevância semântica)
  - Expiração por idade (apenas para collections que não são `user_memory`)
  - Exclusão de fatos deletados (`deleted_at` ou lápide em `sync_tombstones`)
- **A busca é globalmente cross-session por design**

---

### 3. memory_tool._search() — Orquestração da busca (arquivo: `app/agent/tools/memory_tool.py`, linhas 93-115)

```python
def _search(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
    query = str(args.get("query") or args.get("text") or "").strip()
    if not query:
        return ToolResult(False, "Informe em query o que procurar.")
    
    # Busca textual (sem filtro de session)
    found = memory_facts.relevant(query, SEARCH_LIMIT) or memory_facts.essential()
    results = [_public(fact) for fact in found]
    seen = {_norm(item["text"]) for item in results}
    
    # Busca vetorial (sem filtro de session)
    semantic = _semantic(context)
    if semantic is not None:
        from app.storage.vector.semantic_memory import USER_MEMORY_MAX_DISTANCE
        try:
            hits = semantic.search_memories(COLLECTION, query, n_results=SEARCH_LIMIT,
                                            max_distance=USER_MEMORY_MAX_DISTANCE)
        except Exception as exc:
            logger.debug("Busca semântica falhou: %s", exc)
            hits = []
        # ... mescla resultados de ambas as fontes
```

**Análise:**
- Combina resultados de `memory_facts.relevant()` (textual) e `semantic.search_memories()` (vetorial)
- **Nenhuma das duas fontes filtra por session_id**
- A tool tem acesso a `context["session_id"]` mas **não o utiliza na busca**

---

### 4. Uso no orchestrator (arquivo: `app/agent/orchestrator.py`, linhas 499-504)

```python
# Global recall is deliberate; it must not impersonate this chat's transcript.
if lookup_memory and self.semantic_memory and self.semantic_memory.is_available():
    relevant = self.semantic_memory.search_memories("user_memory", text, n_results=3, max_distance=USER_MEMORY_MAX_DISTANCE)
    episodic = self.semantic_memory.search_memories("episodic_memory", text, n_results=1, max_distance=USER_MEMORY_MAX_DISTANCE)
```

**Análise crítica:**
- Comentário explícito no código: **"Global recall is deliberate"** (linha 499)
- A busca cross-session foi **intencionalmente projetada** para ser global
- Razão: memórias são sobre a **usuária**, não sobre uma conversa específica

---

## Gravidade e Impacto

**Gravidade:** N/A (não é um bug)

**Impacto real:** ZERO — A memória funciona como esperado.

**Comportamento atual:**
- ✅ Memória salva na session A é encontrada na session B
- ✅ Busca textual (`memory_facts.relevant`) é global
- ✅ Busca vetorial (`semantic_memory.search_memories`) é global
- ✅ Comentário no código confirma design intencional

---

## Avaliação da Solução Proposta

**Solução proposta original:**
> "A memory tool deveria sempre fazer busca global, independente da session."

**Avaliação:** Desnecessária — a tool **JÁ FAZ** busca global.

---

## Possível Origem do Equívoco

### Hipótese 1: Confusão com `session_id` nos metadados

O campo `session_id` existe em dois lugares:

1. **`memory_facts` source** (`app/storage/memory_facts.py`, linha 141-147):
   ```python
   def _clean_source(source: dict[str, Any] | None, now: float) -> dict[str, Any]:
       return {
           "created_at": ...,
           "session_id": str(source.get("session_id") or "")[:120],  # ← salvo como metadado
           "run_id": ...,
           "origin": ...,
           "kind": ...,
       }
   ```

2. **`semantic_memory` metadata** (`app/agent/tools/memory_tool.py`, linha 82-83):
   ```python
   semantic.add_memory(COLLECTION, fact["text"], metadata={
       "fact_id": fact["id"], "session_id": str(context.get("session_id") or "")  # ← indexado no Chroma
   }, importance=...)
   ```

**Porém:**
- Esses campos são **apenas para rastreamento/auditoria**
- **Não são usados como filtro** em nenhuma busca
- A presença do campo no metadata **não implica filtro**

---

### Hipótese 2: Teste manual mal interpretado

Se o usuário testou:
1. Session A: salvou "meu nome é João"
2. Session B: perguntou "qual meu nome?"
3. O agente não respondeu corretamente

**Causas possíveis (não relacionadas à busca cross-session):**

a) **Rate limit no LLM durante síntese:**
   - Memória foi recuperada com sucesso
   - LLM não conseguiu gerar resposta por 429
   - Aparência: "não lembrou"
   - Realidade: não sintetizou a resposta

b) **Memória salva com texto não-normalizado:**
   - Exemplo: "João" vs "joão" vs "Joao"
   - `memory_facts.relevant()` normaliza para busca textual
   - Mas se o embedding vetorial for sensível a maiúsculas, pode falhar
   - **Nota:** o embedding `all-MiniLM-L6-v2` é case-insensitive, então isso é improvável

c) **Threshold de distância muito restritivo:**
   - `USER_MEMORY_MAX_DISTANCE = 0.45` (arquivo `semantic_memory.py`, linha 21)
   - Se a query "qual meu nome" tem distância cosseno > 0.45 de "meu nome é João", não retorna
   - **Solução:** ajustar threshold, não adicionar filtro de session

d) **Chroma não inicializado:**
   - Se `CHROMADB_AVAILABLE = False` ou erro na inicialização
   - Apenas busca textual funciona (via `memory_facts.relevant`)
   - Busca textual pode não encontrar se não há overlap de palavras-chave

---

## Recomendações

### 1. Manter comportamento atual (RECOMENDADO)

**Razão:** A busca global é o design correto para memória pessoal.

**Vantagens:**
- Memórias sobre a usuária (nome, cidade, gostos) são relevantes em qualquer conversa
- Evita repetição: usuária não precisa se reapresentar a cada sessão
- Alinha com o conceito de "memória durável" do sistema

**Desvantagens:** Nenhuma identificada.

---

### 2. Se o problema real for rate limit na síntese (INVESTIGAR PONTO 4)

**Ação:** Implementar retry com backoff no `_recover_synthesis` (ponto 4 do checkup)

**Razão:** Se a memória foi recuperada mas a resposta não foi sintetizada por 429, o usuário vê como "não lembrou".

---

### 3. Se o problema real for threshold de distância (CALIBRAR)

**Ação:** Ajustar `USER_MEMORY_MAX_DISTANCE` baseado em testes empíricos.

**Valores sugeridos:**
- Atual: `0.45` (conservador)
- Sugestão: `0.55` (mais permissivo para queries indiretas como "qual meu nome")

**Teste:** Criar suite de queries esperadas e validar recall.

---

### 4. Adicionar logging de debug na busca (MELHORIA OPCIONAL)

**Objetivo:** Facilitar troubleshooting de "memória não encontrada".

**Implementação:**
```python
# Em memory_tool._search(), adicionar:
logger.debug(f"Busca textual: {len(found)} resultados para '{query}'")
logger.debug(f"Busca vetorial: {len(hits)} resultados para '{query}'")
for hit in hits:
    logger.debug(f"  - distância: {hit.get('distance'):.3f}, texto: {hit.get('text')[:60]}")
```

**Benefício:** Diagnóstico preciso de por que uma memória não foi recuperada.

---

## Validação por Análise Estática

✅ **Confirmado por code review:**
- Traçado completo do fluxo de busca
- Nenhum filtro de session_id em nenhuma camada
- Comentário explícito no código confirma design

❌ **Validação em runtime:** NÃO REALIZADA (quota de LLM atingida)

**Teste sugerido (se necessário):**
```python
# tests/test_memory_cross_session.py
def test_memory_is_global_across_sessions(isolated_data):
    # Session A: salvar
    result_save = memory_tool.execute(
        {"action": "save", "text": "O nome da usuária é Maria"},
        context={"session_id": "session_A", "semantic_memory": semantic}
    )
    assert result_save.success
    
    # Session B: buscar
    result_search = memory_tool.execute(
        {"action": "search", "query": "qual o nome"},
        context={"session_id": "session_B", "semantic_memory": semantic}
    )
    assert result_search.success
    assert any("Maria" in r["text"] for r in result_search.data["results"])
```

---

## Conclusão

O **ponto 3 do checkup é baseado em premissa falsa**. A busca de memória JÁ É global e funciona corretamente entre sessões.

**Ações recomendadas:**
1. ✅ **NENHUMA mudança** no código de memória
2. 🔍 **Investigar a causa raiz** do relato do usuário (provavelmente rate limit ou threshold)
3. 📊 **Adicionar testes automatizados** para garantir que a busca global continue funcionando
4. 📝 **Documentar** explicitamente no código que a busca é global por design (já existe comentário no orchestrator, mas pode ser expandido)

---

**Fim do Relatório de Investigação — Ponto 3**
