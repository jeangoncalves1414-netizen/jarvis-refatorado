# PONTO 5 — Tool Selection: Keyword Matcher Frágil

**Investigador:** Subagente de Checkup  
**Data:** 2026-01-11  
**Arquivo investigado:** `c:\Users\maria\Desktop\Jarvis\app\agent\tools\registry.py`

---

## STATUS: **CONFIRMADO**

O problema descrito no checkup está presente e comprovado por análise estática do código.

---

## EVIDÊNCIA

### 1. Tabela de Regras Atual (GROQ_KEYWORD_TOOLS)

**Localização:** `registry.py`, linhas 107-130

```python
GROQ_KEYWORD_TOOLS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = tuple(
    (re.compile(pattern), tools)
    for pattern, tools in (
        (r"\bclipboard\b|\btransferencia\b|\bcopi\w*\b.*\btexto\b", ("clipboard",)),
        (r"\bhabit", ("personal_records", "habit_tool")),
        (r"\bchecklist|\blista\b|\blistas\b|\bmercado\b|\bcompras\b", ("checklist_tool",)),  # ← PROBLEMA
        (r"\btaref|\bpendencia", ("task_tool",)),
        (r"\bagua\b|\bbebi\b|\bhidrat|\btreino\b", ("lifeos_tool",)),
        (r"\bgastei\b|\bpaguei\b|\bgasto|\bdespesa|\breceita\b|\bfinanc|\blancamento|\bsaldo\b|\bdinheiro\b|\brecebi\b|\bganhei\b", ("finance_tool",)),
        (r"\bnota\b|\bnotas\b|\banota|\bcofre\b", ("vault_save_note", "vault_search")),
        (r"\blembrete|\bagenda|\bcompromisso", ("calendar",)),
        # ... (demais regras)
    )
)
```

**Regex problemático:**  
`r"\bchecklist|\blista\b|\blistas\b|\bmercado\b|\bcompras\b"`

Este padrão matcha a palavra **"lista"** isoladamente (`\blista\b`), sem considerar o contexto ao redor.

---

### 2. Conflitos Identificados

#### Cenário A: "Liste as memórias"
- **Entrada:** `"liste as memórias que você sabe sobre mim"`
- **Normalização:** `normalize_name()` → `"liste as memorias que voce sabe sobre mim"`
- **Match:** regex `\blista\b` **NÃO** matcha diretamente "liste", mas a variação pode confundir
- **Conflito potencial:** se o usuário disser "lista de memórias" ou "minhas listas de memórias", o regex `\blista\b` **MATCHA** e ativa `checklist_tool`
- **Ferramenta correta:** `memory` (action: `list` ou `search`)
- **Ferramenta ativada:** `checklist_tool` (incorreta)

#### Cenário B: "Liste todas as tarefas"
- **Entrada:** `"mostre minha lista de tarefas pendentes"`
- **Normalização:** `"mostre minha lista de tarefas pendentes"`
- **Match:** `\blista\b` → **MATCHA**
- **Conflito:** ativa `checklist_tool`
- **Ferramenta correta:** `task_tool` (action: `list`)
- **Ferramenta ativada:** `checklist_tool` + `task_tool` (ambiguidade)

#### Cenário C: "Lista de compras" (uso correto)
- **Entrada:** `"adicione leite na lista de compras"`
- **Match:** `\blista\b` + `\bcompras\b` → **MATCHA**
- **Ferramenta correta:** `checklist_tool`
- **Resultado:** ✅ **CORRETO** (não há conflito aqui)

---

### 3. Lógica de Aplicação do Matcher

**Localização:** `registry.py`, método `allowed_tool_names()`, linhas ~466-490

```python
def allowed_tool_names(
    self,
    mode: str = "general",
    provider: str | None = None,
    user_text: str = "",
    *,
    narrow: bool = False,
) -> frozenset[str]:
    # ... (código de filtragem de modo e provedor)
    
    # Normalização do texto do usuário
    normalized = normalize_name(user_text)
    
    # Aplicação das regras de keyword matching
    for pattern, tools in GROQ_KEYWORD_TOOLS + LOOP_KEYWORD_TOOLS:
        if pattern.search(normalized):  # ← MATCH SIMPLES, SEM CONTEXTO NEGATIVO
            dynamic_tools.update(tools)
    
    # ... (mais lógica de filtragem)
```

**Problema identificado:**
- O matching é **positivo simples**: se o regex encontra a palavra-chave, adiciona a ferramenta
- **NÃO há lógica de exclusão por contexto negativo** (ex: "lista" + "memória" → remover `checklist_tool`)
- Todas as ferramentas que matcham keywords são **adicionadas cumulativamente** ao conjunto `dynamic_tools`

---

### 4. Análise de Mitigação Parcial Existente

**Localização:** `registry.py`, linhas 500-520

Existe uma lógica de **desambiguação parcial** para conflitos específicos:

```python
# Linha 500-509: Desambiguação personal_records vs. ferramentas redundantes
if 'personal_records' in allowed_set and re.search(
    r'\b(?:conta\b|cartao\b|parcela|estorn|transfer|recorr|etiqueta|treino|serie|repetic|sono|dormi|humor|desfaz|historico|na verdade|relac|vincul)',
    normalize_name(user_text)
):
    redundant = {'finance_tool', 'habit_tool', 'task_tool', 'checklist_tool', 'vault_save_note'}
    if not re.search(r'\b(?:agua|bebi|hidrat)', normalize_name(user_text)):
        redundant.add('lifeos_tool')
    allowed_set.difference_update(name for name in redundant if name not in user_text)

# Linha 511-514: Desambiguação habit vs. routine
if re.search(r'\bhabit', normalize_name(user_text)) and not re.search(r'\brotina', normalize_name(user_text)):
    allowed_set.discard('routine')
```

**Observação:**
- Existe lógica de exclusão **APÓS** o matching
- **MAS:** não cobre o conflito específico "lista" + "memória/tarefas"
- A desambiguação atual é específica para `personal_records`, `habit`, e `routine`

---

## GRAVIDADE E IMPACTO

### Gravidade: **MÉDIA**

- **Frequência:** moderada (usuários podem frequentemente pedir "lista de X")
- **Consequência:** ferramenta errada é oferecida ao LLM, aumentando confusão e escolhas incorretas
- **Mitigação natural:** o LLM pode ignorar `checklist_tool` se o contexto for claro, mas isso consome tokens e aumenta latência

### Impacto:

1. **Experiência do usuário:** frustração quando o agente tenta gerenciar checklist ao invés de listar memórias/tarefas
2. **Custo de tokens:** ferramentas desnecessárias na declaração de tools aumentam o payload enviado ao LLM
3. **Confiabilidade:** reduz a precisão do tool selection, especialmente em provedores com limite estrito (Groq)

---

## AVALIAÇÃO DA SOLUÇÃO PROPOSTA

### Solução Original (do checkup):
> "Adicionar contexto negativo (ex: `lista.*memória` → não ativar checklist)."

### Análise:

**✅ VIÁVEL e CORRETA**, mas requer extensão da arquitetura atual.

#### Opção 1: Patterns Negativos no Matcher (Recomendada)

**Implementação:**

```python
# Estrutura estendida: (positive_pattern, tools, negative_pattern_optional)
GROQ_KEYWORD_TOOLS: tuple[tuple[re.Pattern[str], tuple[str, ...], re.Pattern[str] | None], ...] = tuple(
    (re.compile(pattern), tools, re.compile(neg_pattern) if neg_pattern else None)
    for pattern, tools, neg_pattern in (
        (r"\bchecklist|\blista\b|\blistas\b|\bmercado\b|\bcompras\b", 
         ("checklist_tool",),
         r"\blista.*(?:memori|memoria|tarefa|nota|vault|cofre)"),  # ← CONTEXTO NEGATIVO
        # ... demais regras
    )
)

# Lógica de matching atualizada
for pattern, tools, neg_pattern in GROQ_KEYWORD_TOOLS:
    if pattern.search(normalized):
        if neg_pattern is None or not neg_pattern.search(normalized):
            dynamic_tools.update(tools)
```

**Vantagens:**
- Simples de implementar
- Mantém a estrutura atual (tabela declarativa)
- Fácil de testar e manter

**Desvantagens:**
- Regex negativo pode crescer complexo (múltiplos casos de exclusão)
- Ainda é regex estático (frágil para novos padrões)

---

#### Opção 2: Refatoração para Classificador Semântico (Futura)

**Ideia:** substituir regex por classificação de intenção baseada em embeddings ou LLM lightweight.

**Exemplo:**
```python
def classify_tool_intent(user_text: str) -> frozenset[str]:
    """Usa modelo pequeno (ex: DistilBERT) ou embedding para classificar intenção."""
    # "lista de memórias" → intent: memory_query
    # "lista de compras" → intent: checklist_query
    # "lista de tarefas" → intent: task_query
    return intent_to_tools(intent)
```

**Vantagens:**
- **Robusto:** aprende contexto naturalmente
- Escalável para novos casos sem escrever regex

**Desvantagens:**
- **Complexidade:** requer treinamento/fine-tuning ou chamada a LLM adicional
- **Latência:** adiciona overhead (mitigável com cache)
- **Overkill:** para o problema atual, regex com contexto negativo é suficiente

---

#### Opção 3: Desambiguação Pós-Matching (Complementar)

Estender a lógica existente (linhas 500-520) com regras adicionais:

```python
# Após o matching, descartar checklist_tool se houver conflito de contexto
if 'checklist_tool' in allowed_set:
    if re.search(r'\blista.*(?:memori|memoria|tarefa|nota|vault|cofre)', normalized):
        allowed_set.discard('checklist_tool')
    elif re.search(r'\blista.*tarefas?', normalized):
        allowed_set.discard('checklist_tool')
```

**Vantagens:**
- Não quebra a estrutura atual de `GROQ_KEYWORD_TOOLS`
- Rápido de implementar

**Desvantagens:**
- Duplica lógica (regex espalhado em dois lugares)
- Menos declarativo (desambiguação implícita)

---

## RECOMENDAÇÃO FINAL

### Implementar **Opção 1 (Patterns Negativos)** + **Opção 3 (Desambiguação Pós-Matching)** como solução híbrida:

1. **Curto prazo:** adicionar desambiguação pós-matching (linhas 520+) para resolver o problema imediatamente
2. **Médio prazo:** refatorar `GROQ_KEYWORD_TOOLS` para suportar patterns negativos (melhora a manutenibilidade)
3. **Longo prazo:** avaliar migração para classificador semântico quando o número de conflitos crescer

---

## CASOS DE TESTE PROPOSTOS

### Teste 1: "lista de memórias" → NÃO deve ativar checklist_tool
```python
user_text = "mostre minha lista de memórias"
tools = registry.allowed_tool_names(provider="groq", user_text=user_text)
assert "checklist_tool" not in tools
assert "memory" in tools
```

### Teste 2: "lista de tarefas" → NÃO deve ativar checklist_tool
```python
user_text = "liste todas as minhas tarefas pendentes"
tools = registry.allowed_tool_names(provider="groq", user_text=user_text)
assert "checklist_tool" not in tools
assert "task_tool" in tools
```

### Teste 3: "lista de compras" → DEVE ativar checklist_tool
```python
user_text = "adicione leite na lista de compras"
tools = registry.allowed_tool_names(provider="groq", user_text=user_text)
assert "checklist_tool" in tools
```

### Teste 4: "criar checklist" → DEVE ativar checklist_tool
```python
user_text = "crie uma checklist de viagem"
tools = registry.allowed_tool_names(provider="groq", user_text=user_text)
assert "checklist_tool" in tools
```

---

## ARQUIVOS RELACIONADOS

- **registry.py** (linhas 107-130, 466-520): lógica de keyword matching
- **lifestyle_tools.py**: implementação de `normalize_name()` (linha 50+)
- **checklist_tool.py**: ferramenta que é ativada incorretamente
- **memory_tool.py**: ferramenta que DEVERIA ser ativada em "lista de memórias"
- **task_tool.py** (em lifestyle_tools.py): ferramenta que DEVERIA ser ativada em "lista de tarefas"

---

## NOTAS ADICIONAIS

### Observação 1: LOOP_KEYWORD_TOOLS também tem o mesmo padrão
**Localização:** `registry.py`, linhas 147-165

O problema se repete em `LOOP_KEYWORD_TOOLS` (usado no modo `narrow=True`), mas com menor impacto porque o loop agêntico já filtra mais agressivamente.

### Observação 2: Normalização remove acentos
A função `normalize_name()` (importada de `lifestyle_tools.py`) remove acentos e converte para minúsculas:
```python
def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())
```

Isso significa:
- "memória" → "memoria"
- "tarefá" → "tarefa"
- Regex negativo deve usar formas sem acento

### Observação 3: MCP Tools não são afetados
Ferramentas dinâmicas de servidores MCP (prefixo `mcp_`) usam lógica de matching diferente (linhas 481-485) e não são afetadas por este problema.

---

## CONCLUSÃO

O problema está **CONFIRMADO** por análise estática. O keyword matcher atual é frágil e gera conflitos quando a palavra "lista" aparece em contextos não relacionados a checklist (ex: "lista de memórias", "lista de tarefas"). A solução proposta (contexto negativo) é viável e recomendada, com implementação híbrida (desambiguação pós-matching imediata + refatoração da tabela de keywords a médio prazo).

**Prioridade de correção:** MÉDIA (não é crítico, mas afeta a experiência do usuário e consome recursos desnecessários).

---

**Fim do Documento de Achados — PONTO 5**
