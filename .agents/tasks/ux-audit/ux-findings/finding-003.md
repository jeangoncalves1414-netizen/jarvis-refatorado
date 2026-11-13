## Finding 3: Mensagens de Erro Expõem Detalhes Técnicos de Configuração

**Categoria**: DX
**Prioridade**: 🟡 IMPORTANTE

### Problema Atual
O arquivo `app/services/llm.py` expõe mensagens de erro com detalhes de configuração técnica:
- Linha 640: `"Erro de autenticação com a API Gemini. Verifique a GEMINI_API_KEY no .env."`
- Linha 642-643: `"Limite de taxa da API Gemini excedido. Tente novamente em alguns instantes."`
- Linha 644: `"Modelo 'X' não encontrado. Verifique GEMINI_MODEL no .env."`

Similarmente em `app/services/llm.py` linha 196-197:
- `"Chave GROQ_API_KEY não encontrada no .env. Configure-a para conversar com o Jarvis."`

### Impacto no Usuário
- **Confusão para usuários leigos**: Menções a `.env`, `GEMINI_API_KEY`, `GROQ_API_KEY` são incompreensíveis para quem não é desenvolvedor
- **Quebra de experiência**: Usuário final não deveria ver detalhes de configuração de backend
- **Insegurança**: Expor nomes de variáveis de ambiente pode ser uma vulnerabilidade de segurança menor

### Proposta de Solução
Diferenciar mensagens entre **modo desenvolvedor** e **modo usuário**:

1. Para usuários finais: mensagens genéricas e acionáveis
2. Para desenvolvedores: mensagens detalhadas vão para logs/console, não para UI

Implementar um sistema de `user_facing` flag nas mensagens de erro.

### Implementação Estimada
**Média** — 3 horas

### Arquivos Envolvidos
- `app/services/llm.py` (linhas 196-197, 640-644)
- `app/core/capability_health.py` (já tem lógica de mensagens user-facing)
- Todas as ferramentas em `app/agent/tools/` que retornam `ToolResult`

### Exemplo de Código
```python
# Antes (linha 640)
raise ValueError("Erro de autenticação com a API Gemini. Verifique a GEMINI_API_KEY no .env.")

# Depois
# Para log/console (desenvolvedor)
logger.error("Autenticação Gemini falhou: GEMINI_API_KEY inválida ou ausente no .env")
# Para usuário
raise ValueError("Não foi possível conectar ao serviço de IA. Por favor, verifique sua configuração.")

# Antes (linha 196-197)
return ProviderErrorText(f"Chave GROQ_API_KEY não encontrada no .env. Configure-a para conversar com o Jarvis.")

# Depois
logger.warning("GROQ_API_KEY não configurada no .env")
return ProviderErrorText("Serviço de IA não está configurado. Por favor, configure as credenciais.")
```
