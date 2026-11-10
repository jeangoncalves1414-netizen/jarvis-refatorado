# Relatório de Implementação: Deep Search & Video Routing Intelligence

**Data:** 10 de Novembro de 2026  
**Branch:** `feat/deep-search-video-routing`  
**Worktree:** `C:\Users\maria\Desktop\Jarvis\.worktrees\deep-search-video-routing`  
**Status:** Concluído com Sucesso (66/66 testes passando)

---

## 1. Contexto e Objetivos

O objetivo deste ciclo de engenharia foi resolver três problemas críticos de orquestração e pesquisa inteligente no Jarvis:
1. **Roteamento de Vídeo / YouTube:** Pedidos de análise e links do YouTube (`youtube.com`, `youtu.be`) estavam sendo interceptados incorretamente por `web_search` ou abrindo abas no navegador local em vez de executar o `VideoAnalystTool`.
2. **Deep Search Multi-Hop & Síntese:** Buscas sobre notícias e personalidades muitas vezes retornavam apenas links genéricos (redes sociais, dicionários como Dicio e Priberam) sem fatos substantivos. O sistema agora executa refinamento multi-hop iterativo e síntese limpa sem despejar links brutos.
3. **Desduplicação de Ferramentas e Polimento Llama 3.3 / Groq:** `get_tool_declarations` retornava a ferramenta `browser` duplicada (estourando validações da API do Google/Gemini), e o modelo Llama 3.3 (Groq) frequentemente exibia cabeçalhos robóticos como `"Resultados das ferramentas:"` e listas de URLs brutas na resposta final ao usuário.

---

## 2. Alterações Implementadas

### A. Roteamento Preciso de Vídeos e YouTube
- **`app/agent/tools/registry.py`**:
  - Removido `\byoutube` de `web_search` em `LOOP_KEYWORD_TOOLS`.
  - Implementada função de detecção `is_video_analysis_request(text)` cobrindo URLs do YouTube (`youtube.com`, `youtu.be`), termos de análise ("analise o video", "resumo do video", "transcricao", "topicos do video", "timestamps").
  - Em `allowed_tool_names`: exclusão ativa e forçada de `web_search`, `browser`, `browser_agent`, `browser_tool` e `media_tool` para pedidos de análise de vídeo, garantindo roteamento exclusivo para `video_analyst`.
  - Em `run_by_marker`: se a LLM emitir marcador de `web_search` para um link de vídeo ou pedido de análise, há o redirecionamento automático para `video_analyst`.
- **`app/agent/tools/web_search.py`**:
  - Em `WebSearchTool.execute`: verificação se a query/URL contém link do YouTube; caso positivo, delega a execução diretamente para o `VideoAnalystTool` sem abrir o navegador local.

### B. Multi-Hop Deep Web Search & Refinamento Iterativo
- **`app/agent/tools/web_search.py`**:
  - Criado filtro de fontes genéricas (`GENERIC_DOMAINS` cobrindo dicionários e redes sociais) e heurística `_is_informative_result` para descartar links não-informativos.
  - Criada função `search_with_refinement(query, limit, max_hops)` com estratégia iterativa:
    - Hop 1: busca inicial.
    - Se retornar 0 resultados ou apenas dicionários/redes sociais (`_needs_refinement`), dispara automaticamente o Hop 2 com termos refinados (ex.: `f"{termo} noticias recentes"` ou portais jornalísticos).
    - Mecanismo de *early stopping*: conclui assim que obtém resultados substantivos sem consumo desnecessário de hops.
  - Implementada formatação limpa e concisa `_format_search_response` que resume fatos essenciais sem despejo de URLs brutas no corpo da fala.
- **`app/agent/tools/deep_browser.py`**:
  - Módulo unificador para navegação profunda, síntese com Playwright, snapshots interativos e busca iterativa.
- **`app/services/browser.py`**:
  - Integração de `BrowserService.deep_search` com o novo fluxo de `search_with_refinement`.

### C. Desduplicação de Ferramentas & Filtros STM (Groq/Llama 3.3)
- **`app/agent/tools/registry.py`**:
  - `get_tool_declarations` agora rastreia `seen_names`, garantindo que nenhuma ferramenta (como o `browser`, registrado tanto como `browser` quanto `browser_tool`) seja declarada em duplicidade.
- **`app/services/llm.py`**:
  - Desduplicação defensiva adicionada na montagem de `FunctionDeclaration` para o Google Gemini (`_generate_gemini` e `_generate_gemini_function_calling_stream`), evitando erros 400 da API por ferramentas com mesmo nome.
  - Desduplicação em `_generate_groq_function_calling_stream` (`seen_selected_names`).
  - Reformulação das mensagens de retorno da execução de ferramentas no Groq, instruindo explicitamente a nunca gerar cabeçalhos técnicos como `"Resultados das ferramentas:"` ou links brutos `"Link: https://..."`.
  - Fallback defensivo com `stm_filter.process(tool_summary)` caso o turno de síntese do Groq não gere texto.
- **`app/services/stm_filters.py`**:
  - Expressões regulares aprimoradas para expurgar cabeçalhos robóticos (`"Resultados das ferramentas:"`, `"Resultados da pesquisa:"`, `"Aqui estão os resultados:"`) e linhas soltas com links (`"Link: https://..."`, `"- Link: https://..."`, `"• Link: https://..."`).
- **`app/agent/orchestrator.py` & `app/agent/prompts.py`**:
  - Prompts centrais atualizados com regra de ouro de não usar cabeçalhos técnicos nem despejar links brutos.
  - `orchestrator.py` processa o output final com `stm_filter.process(final_summary)` antes de enviar para fala/UI.

---

## 3. Testes Executados

Executado o conjunto completo de testes direcionados:
```bash
python -m pytest tests/test_video_intelligence.py tests/test_deep_browser.py tests/test_mode_router.py
```

**Resultado:**
- `tests/test_video_intelligence.py`: 14 testes aprovados.
  - Roteamento exclusivo para links do YouTube no Groq e Gemini.
  - Bloqueio de sequestro de vídeo pelo `web_search`.
  - Redirecionamento por marcador de `web_search` para `video_analyst`.
- `tests/test_deep_browser.py`: 15 testes aprovados.
  - Extração limpa de artigos sem ruído publicitário ou de cookies.
  - Snapshots de elementos interativos numerados no DOM.
  - Multi-hop search com refinamento automático em buscas sobre pessoas/notícias.
  - Early stopping na busca iterativa.
  - Ausência de ferramentas duplicadas em `get_tool_declarations`.
  - Desduplicação defensiva na API Gemini.
  - Filtragem STM de cabeçalhos técnicos e links brutos.
- `tests/test_mode_router.py`: 37 testes aprovados.
  - Desambiguação de intenção de notícias, coder, research e vídeo.

**Total: 66 testes aprovados (100% de sucesso).**
