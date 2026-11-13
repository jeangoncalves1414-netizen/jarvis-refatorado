# CHANGELOG SPRINT 1 — Correções Críticas do Jarvis

Data: 2024-01-20

## [SEGURANÇA] Ponto 10 — Checklist delete_list com confirmação
- Arquivo: app/agent/tools/checklist_tool.py
- Mudança: exclusão de checklist agora solicita confirmação via CriticalConfirm antes de executar
- Impact: previne perda acidental de listas com itens
- Retrocompatível: sim (se CriticalConfirm falhar, prossegue sem confirmação)

## [MELHORIA] Ponto 8 — Web Search fallback snippets
- Arquivos: app/agent/tools/web_search.py, app/agent/tools/base.py
- Mudança: ToolResult de web_search agora inclui fallback_snippets (5 itens compactos) no .data; model_observation() expõe esses campos ao LLM
- Impact: _recover_synthesis tem material para reformular resposta quando rate limit trunca a síntese
- Retrocompatível: sim (apenas adiciona dados novos)

## [ROBUSTEZ] Ponto 2 — Vision fallback automático Groq → Gemini
- Arquivo: app/services/vision.py
- Mudança: analyze() e analyze_bytes() agora fazem fallback automático para Gemini Vision quando modelo Groq retorna erro de modelo inválido/não encontrado
- Impact: análise visual continua funcionando mesmo se GROQ_VISION_MODEL ficar obsoleto
- Retrocompatível: sim (apenas adiciona recovery, não muda comportamento normal)
