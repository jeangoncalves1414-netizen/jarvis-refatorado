# Achados de Investigação — PONTO 9: Testes de Integração Automatizados

**Investigador:** Subagente de Análise Estática  
**Data:** 2026-01-11  
**Workspace:** `c:\Users\maria\Desktop\Jarvis`

---

## Status: **CONFIRMADO**

O problema descrito no checkup foi completamente confirmado. Não existe um test suite que rode contra o servidor real em formato de integração end-to-end automatizada.

---

## Evidências — Estrutura Atual de Testes

### Framework Utilizado: **pytest**

A pasta `tests/` contém **150+ arquivos de teste** (excluindo `.pyc`), mas todos são **testes unitários ou de componente isolados**, não testes de integração contra servidor real.

**Confirmação de pytest:**
- `conftest.py` define fixtures globais (autouse) que isolam todos os testes em `tmp_path`
- Uso de `monkeypatch` extensivamente para substituir dependências reais
- Fixtures como `isolated_lote6_data`, `isolated_credentials`, `isolated_sessions` garantem isolamento total

### Arquivo-Alvo: `test_live_integration.py`

**Status:** ❌ **NÃO EXISTE**

```powershell
PS> Test-Path "c:\Users\maria\Desktop\Jarvis\tests\test_live_integration.py"
False
```

### Arquivo Existente Mais Próximo: `test_live_server.py`

**Descrição:** Teste manual que verifica se o servidor está rodando em `http://127.0.0.1:8000`

**Limitações identificadas:**
1. **Não sobe o servidor automaticamente** — apenas tenta conectar; se falhar, faz `pytest.skip()`
2. **Testa apenas APIs HTTP do painel Evolute** (water, habits, summary, frontend)
3. **Não testa o agente conversacional** (orchestrator, tools, LLM integration)
4. **Não valida efeitos colaterais** (arquivo criado, memória salva, checklist persistida)
5. **Marcado com `@pytest.mark.live`, `@pytest.mark.network`, `@pytest.mark.hardware`** no `conftest.py` — excluído da suite padrão (`pytest_collection_modifyitems`)

**Código relevante:**
```python
try:
    urllib.request.urlopen(f"{base}/api/evolute/summary", timeout=1)
except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
    pytest.skip("Live server is not running at http://127.0.0.1:8000 - skipping live server test.")
```

### Padrões de Teste Existentes — Testes de Componentes

Os testes atuais seguem um padrão robusto de isolamento:

**`conftest.py` — Fixtures Globais:**
- `isolated_lote6_data`: Cria ambiente temporário com banco de dados fake (checklist, habits, action_store)
- `isolated_credentials`: Credenciais em dicionário na memória (não toca Windows Credential Manager)
- `isolated_sessions`: Sessões em arquivo temporário
- `isolated_routines`: Banco SQLite de rotinas em `tmp_path`
- `effect_checks_off`: Desabilita verificação de processos/janelas reais

**Testes Representativos:**
1. **`test_synthesis_failure_after_actions.py`**: Mock do LLM que falha após executar ação; valida recovery
2. **`test_orchestrator.py`**: Testes unitários do orchestrator com LLM real (mas sem servidor HTTP)
3. **`test_memory_tool.py`**: Ciclo save/search/forget com `FakeSemantic` (não usa Chroma real)
4. **`test_checklists.py`**: CRUD de checklists com `ChecklistStore` isolado em SQLite temporário
5. **`test_rate_limit_rotation.py`**: Mock de erros 429 com `FakeGroq` para testar rotação de chaves

**Nenhum deles:**
- Sobe o servidor real (`main.py` ou `panel.py`)
- Testa fluxo conversacional completo (user input → LLM → tool execution → response)
- Valida integração real entre orchestrator + LLMService + tools + storage

---

## Gravidade e Impacto

**Gravidade:** 🟡 **MÉDIA-ALTA**

**Impacto:**
1. **Regressões não detectadas:** Mudanças no orchestrator, registry ou LLM integration podem quebrar o sistema sem falhar nos testes unitários
2. **Comportamento end-to-end não validado:** Pontos 1-8 do checkup (tool selection, rate limit recovery, memory cross-session) não têm cobertura de integração
3. **Validação manual repetitiva:** Usuário teve que executar 11 cenários manualmente (mencionados no checkup), processo que deveria ser automatizado
4. **CI incompleto:** Pipeline de CI roda apenas testes unitários, não valida o sistema funcionando como um todo

**Casos não cobertos (relacionados aos 10 pontos do checkup):**
- **Ponto 1:** LLM escolhendo action errada em checklist (`list_all` vs `get_list`) → sem teste end-to-end que valide resposta do LLM real
- **Ponto 3:** Memória cross-session → sem teste que salva em session A e busca em session B
- **Ponto 4:** Rate limit com backoff → `test_rate_limit_rotation.py` testa rotação, mas não recovery de síntese (`_recover_synthesis`)
- **Ponto 6:** Sequência "criar arquivo, esperar 2s, ler" → mencionado no checkup mas sem teste automatizado
- **Ponto 7:** Timer audio confirmado → sem teste que valida callback de `_fire()`
- **Ponto 8:** Web search fallback → sem teste que valida recovery quando síntese trunca

---

## Avaliação da Solução Proposta

**Solução proposta:** Criar `tests/test_live_integration.py` com os 11 cenários, usando fixture que sobe/desce o servidor, para rodar no CI.

### ✅ Viabilidade: **ALTA**

**Fundamentação:**
1. **Infraestrutura pytest já existe:** `conftest.py` com fixtures robustas, pode adicionar nova fixture para servidor
2. **Precedente:** `test_live_server.py` já conecta em servidor HTTP (mas não sobe automaticamente)
3. **Padrão existente de `@pytest.mark.integration`:** `pytest_collection_modifyitems` já separa testes por tipo (integration, network, hardware)
4. **Orchestrator testável:** `test_orchestrator.py` e `test_synthesis_failure_after_actions.py` já instanciam `AgentOrchestrator` diretamente

### 🟡 Desafios Identificados:

1. **Subir servidor em background dentro do teste:**
   - **Opção A:** `subprocess.Popen()` para iniciar `python main.py` ou `python app/ui/panel.py`
   - **Opção B:** Importar `app.ui.panel.create_app()` e rodar em thread separada com `flask.run()` ou `uvicorn.run()`
   - **Recomendação:** Opção B (mais controle, shutdown limpo)

2. **LLM real vs Mock:**
   - **Problema:** Testes com LLM real (Groq/Gemini) são não-determinísticos e custam quota
   - **Solução proposta no checkup:** "simular uma conversa com o usuário" → usar LLM mock que retorna respostas fixas (como `SynthesisFailsLLM` em `test_synthesis_failure_after_actions.py`)
   - **Recomendação:** Criar `FakeAgentLLM` que retorna tool calls pré-programados para cada cenário

3. **Dependências externas (Chroma, SQLite, winsound):**
   - **Solução:** Reutilizar fixtures `isolated_lote6_data` para banco temporário; `monkeypatch` para `winsound.Beep`
   - **Chroma:** Pode usar real em `tmp_path` ou `FakeSemantic` (já existe em `test_memory_tool.py`)

4. **Validação de efeitos colaterais:**
   - Arquivo criado: verificar com `Path.exists()`
   - Memória salva: buscar em `memory_facts.list_facts()`
   - Timer ativo: verificar `timer._active_timers`
   - Checklist persistida: buscar em `checklist_store.list_all()`

5. **Timeout e cleanup:**
   - Servidor precisa de tempo para iniciar (até 5s)
   - Fixture `yield` garante shutdown limpo após teste
   - Usar `atexit` ou `try/finally` para matar processos órfãos

---

## Outline do Test Suite — `test_live_integration.py`

### Estrutura Geral

```python
"""Testes de integração end-to-end do sistema Jarvis com servidor real.

Estes testes cobrem os 11 cenários identificados no checkup do sistema,
validando o fluxo completo: user input → orchestrator → LLM → tools → storage → response.

Marcados com @pytest.mark.integration para rodar separadamente no CI.
"""
import pytest
import time
from pathlib import Path
from types import SimpleNamespace
from threading import Thread
import requests  # ou urllib

# Imports do Jarvis
from app.agent.orchestrator import AgentOrchestrator
from app.storage.checklist_store import checklist_store
from app.storage.memory_facts import memory_facts
from app.agent.tools.registry import registry
from app.services.llm import LLMService

pytestmark = pytest.mark.integration


# ============================================================================
# FIXTURE: Servidor Real em Background
# ============================================================================

@pytest.fixture(scope="module")
def live_server(tmp_path_factory, monkeypatch_module):
    """Sobe o servidor Jarvis em background para testes de integração.
    
    Estratégia:
    1. Cria ambiente isolado em tmp_path (bancos SQLite, chroma, etc.)
    2. Monkeypatch nos caminhos de storage para usar ambiente temporário
    3. Inicia servidor HTTP em thread separada (porta 8001 para não conflitar)
    4. Aguarda servidor estar pronto (health check GET /)
    5. Yield para testes
    6. Shutdown limpo do servidor + cleanup
    
    Returns:
        SimpleNamespace com:
            - base_url (str): http://127.0.0.1:8001
            - data_dir (Path): diretório temporário de dados
            - orchestrator (AgentOrchestrator): instância do orquestrador
    """
    # TODO: Implementar setup
    # - tmp_path com data/ fake
    # - Monkeypatch em storage paths
    # - Thread com servidor Flask/FastAPI
    # - Polling até servidor responder
    pass


@pytest.fixture
def agent_mock_llm(monkeypatch):
    """LLM mock que retorna tool calls pré-programados para cada cenário.
    
    Substitui LLMService.generate() para retornar respostas determinísticas
    sem consumir quota real de Groq/Gemini.
    """
    class FakeAgentLLM:
        def __init__(self):
            self.scenario_responses = {
                "create_checklist": self._checklist_create_response,
                "list_checklist": self._checklist_list_response,
                "save_memory": self._memory_save_response,
                "search_memory": self._memory_search_response,
                "set_timer": self._timer_set_response,
                "web_search": self._web_search_response,
                "create_and_read_file": self._file_sequence_response,
            }
            self.active_scenario = None
        
        def generate(self, **kwargs):
            """Retorna LLMResponse com tool calls baseado no cenário ativo."""
            handler = self.scenario_responses.get(self.active_scenario)
            if handler:
                return handler(kwargs)
            return self._default_response()
        
        def _checklist_create_response(self, kwargs):
            # Retorna tool call para checklist_tool com action=create_list
            pass
        
        # ... outros handlers
    
    llm = FakeAgentLLM()
    monkeypatch.setattr(LLMService, "generate", llm.generate)
    return llm


# ============================================================================
# CENÁRIO 1: Checklist — Criar e Listar (Ponto 1 do checkup)
# ============================================================================

def test_scenario_01_checklist_create_and_get_list(live_server, agent_mock_llm):
    """
    Cenário: Usuário cria checklist "Compras" e depois pede para listar itens.
    
    Objetivo: Validar que LLM escolhe action correta (get_list, não list_all).
    
    Passos:
    1. POST /api/agent/request: "Crie uma checklist Compras com arroz e feijão"
    2. Validar resposta: intent=tool_execution, summary menciona "Compras criada"
    3. Validar storage: checklist existe em checklist_store
    4. POST /api/agent/request: "Liste os itens da checklist Compras"
    5. Validar resposta: menciona "arroz" e "feijão" (não lista resumos)
    
    Relacionado: Ponto 1 do checkup (list_all vs get_list)
    """
    agent_mock_llm.active_scenario = "create_checklist"
    
    # 1. Criar checklist
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Crie uma checklist Compras com arroz e feijão",
            "session_id": "test_session_01"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "tool_execution"
    assert "Compras" in data["summary"]
    
    # 2. Validar storage
    lists = checklist_store.list_all()
    assert any(lst["title"] == "Compras" for lst in lists)
    compras = next(lst for lst in lists if lst["title"] == "Compras")
    items = checklist_store.get_list(compras["id"])["items"]
    assert len(items) == 2
    assert any("arroz" in item["text"] for item in items)
    
    # 3. Listar itens (validar que usa get_list, não list_all)
    agent_mock_llm.active_scenario = "list_checklist"
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Liste os itens da checklist Compras",
            "session_id": "test_session_01"
        }
    )
    data = response.json()
    assert "arroz" in data["summary"] and "feijão" in data["summary"]
    # Não deve mencionar outros títulos de checklists
    assert "list_all" not in str(data.get("tool_calls", []))


# ============================================================================
# CENÁRIO 2: Visão — Fallback automático quando modelo Groq obsoleto (Ponto 2)
# ============================================================================

def test_scenario_02_vision_model_fallback(live_server, monkeypatch):
    """
    Cenário: Groq Vision model retorna erro model_not_found; sistema faz fallback para Gemini.
    
    Objetivo: Validar health-check ou fallback automático (ponto 2 do checkup).
    
    Passos:
    1. Monkeypatch VisionService._get_client para falhar em Groq
    2. POST /api/agent/request: "Analise a tela"
    3. Validar resposta: não contém erro; usou Gemini como fallback
    
    Relacionado: Ponto 2 do checkup (GROQ_VISION_MODEL hardcoded)
    """
    # Mock de falha no Groq Vision
    def fake_groq_create(**kwargs):
        raise RuntimeError("model_not_found: qwen/qwen3.8-27b")
    
    # TODO: Implementar monkeypatch no VisionService
    # Validar que segunda tentativa usa Gemini e funciona
    pass


# ============================================================================
# CENÁRIO 3: Memória — Busca Cross-Session (Ponto 3)
# ============================================================================

def test_scenario_03_memory_cross_session_search(live_server):
    """
    Cenário: Memória salva na session A é encontrada por busca na session B.
    
    Objetivo: Validar que busca semântica é global, não filtrada por session.
    
    Passos:
    1. POST em session_A: "Me lembre que meu nome é Jean"
    2. Validar storage: memória existe em memory_facts
    3. POST em session_B (diferente): "Qual é o meu nome?"
    4. Validar resposta: menciona "Jean" (memória foi encontrada)
    
    Relacionado: Ponto 3 do checkup (memória cross-session)
    """
    # 1. Salvar memória em session A
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Me lembre que meu nome é Jean",
            "session_id": "session_A"
        }
    )
    assert response.status_code == 200
    
    # 2. Validar storage
    facts = memory_facts.list_facts()
    assert any("Jean" in fact["text"] for fact in facts)
    
    # 3. Buscar em session B (diferente)
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Qual é o meu nome?",
            "session_id": "session_B"  # ← SESSION DIFERENTE
        }
    )
    data = response.json()
    assert "Jean" in data["summary"], "Memória cross-session não foi encontrada"


# ============================================================================
# CENÁRIO 4: Rate Limit — Recovery com Exponential Backoff (Ponto 4)
# ============================================================================

def test_scenario_04_rate_limit_recovery_with_backoff(live_server, monkeypatch):
    """
    Cenário: Síntese falha com 429 após ação executada; recovery tenta com backoff.
    
    Objetivo: Validar _recover_synthesis com exponential backoff (ponto 4).
    
    Passos:
    1. Monkeypatch LLM para retornar 429 na síntese (após tool execution)
    2. Mock KeyRotator para retornar nova chave com cooldown < 10s
    3. POST: "Crie uma tarefa de estudar Python"
    4. Validar: recovery tentou 2x com backoff (2s, 4s)
    5. Validar resposta: contém resultado da ação (tarefa criada) mesmo sem síntese
    
    Relacionado: Ponto 4 do checkup (retry com backoff)
    """
    # TODO: Implementar mock que:
    # - Primeira chamada: executa tool (task_tool)
    # - Segunda chamada (síntese): 429 com retry-after: 5s
    # - Terceira e quarta tentativas: validar backoff 2s, 4s
    pass


# ============================================================================
# CENÁRIO 5: Tool Selection — Keyword Matcher com Contexto (Ponto 5)
# ============================================================================

def test_scenario_05_tool_selection_keyword_with_context(live_server):
    """
    Cenário: Usuário diz "liste minhas memórias"; checklist_tool NÃO deve ser ativado.
    
    Objetivo: Validar contexto negativo em keyword matcher (ponto 5).
    
    Passos:
    1. POST: "liste minhas memórias"
    2. Validar tool_calls: contém memory_tool, NÃO contém checklist_tool
    3. POST: "liste as checklists"
    4. Validar tool_calls: contém checklist_tool
    
    Relacionado: Ponto 5 do checkup (keyword matcher frágil)
    """
    # 1. Lista memórias (não deve ativar checklist)
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "liste minhas memórias",
            "session_id": "session_05"
        }
    )
    data = response.json()
    tool_names = [call["tool"] for call in data.get("tool_calls", [])]
    assert "memory_tool" in tool_names or "memory" in tool_names
    assert "checklist_tool" not in tool_names, "checklist_tool foi ativado indevidamente"
    
    # 2. Lista checklists (deve ativar checklist)
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "liste as checklists",
            "session_id": "session_05"
        }
    )
    data = response.json()
    tool_names = [call["tool"] for call in data.get("tool_calls", [])]
    assert "checklist_tool" in tool_names or "checklist" in tool_names


# ============================================================================
# CENÁRIO 6: Sequência de Ações — Criar Arquivo, Esperar 2s, Ler (Ponto 6)
# ============================================================================

def test_scenario_06_action_sequence_with_intermediate_results(live_server, tmp_path):
    """
    Cenário: "Crie arquivo teste.txt, espere 2s, leia o arquivo".
    
    Objetivo: Validar rastreamento de resultados intermediários (ponto 6).
    
    Passos:
    1. POST: "Crie arquivo teste.txt com conteúdo ABC, espere 2 segundos e leia o arquivo"
    2. Validar resposta: contém "Li o arquivo" + conteúdo "ABC"
    3. Validar context.tool_calls: registra file_manager (write), wait, file_manager (read)
    4. Validar arquivo: tmp_path / "teste.txt" existe e contém "ABC"
    
    Relacionado: Ponto 6 do checkup (tools: [] vazio quando deveria registrar)
    """
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": f"Crie arquivo {tmp_path}/teste.txt com conteúdo ABC, espere 2 segundos e leia o arquivo",
            "session_id": "session_06"
        }
    )
    data = response.json()
    
    # 1. Validar resposta
    assert "Li o arquivo" in data["summary"] or "ABC" in data["summary"]
    
    # 2. Validar tool_calls registrados
    tool_calls = data.get("tool_calls", [])
    assert len(tool_calls) == 3, f"Esperado 3 tool calls, obteve {len(tool_calls)}"
    tool_names = [call["tool"] for call in tool_calls]
    assert "file_manager" in tool_names[0]
    assert "wait" in tool_names[1]
    assert "file_manager" in tool_names[2]
    
    # 3. Validar arquivo criado
    file_path = Path(tmp_path) / "teste.txt"
    assert file_path.exists(), "Arquivo não foi criado"
    assert file_path.read_text() == "ABC"


# ============================================================================
# CENÁRIO 7: Timer — Feedback Audível Confirmado (Ponto 7)
# ============================================================================

def test_scenario_07_timer_audio_callback_confirmation(live_server, monkeypatch):
    """
    Cenário: Timer toca alarme; sistema confirma que áudio disparou.
    
    Objetivo: Validar callback de confirmação em _fire() (ponto 7).
    
    Passos:
    1. Monkeypatch winsound.Beep para registrar chamadas
    2. POST: "Me avise em 1 segundo"
    3. Aguardar 2 segundos
    4. Validar: winsound.Beep foi chamado 3x (timer padrão)
    5. Validar: log ou callback registrou disparo do alarme
    
    Relacionado: Ponto 7 do checkup (timer sem feedback audível)
    """
    beep_calls = []
    
    def fake_beep(frequency, duration):
        beep_calls.append((frequency, duration))
    
    monkeypatch.setattr("winsound.Beep", fake_beep)
    
    # 1. Criar timer de 1 segundo
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Me avise em 1 segundo",
            "session_id": "session_07"
        }
    )
    assert response.status_code == 200
    
    # 2. Aguardar disparo
    time.sleep(2)
    
    # 3. Validar beep foi chamado
    assert len(beep_calls) >= 3, f"Esperado 3+ beeps, obteve {len(beep_calls)}"
    
    # TODO: Validar callback/log que confirma disparo
    # (requer implementação do ponto 7 do checkup)


# ============================================================================
# CENÁRIO 8: Web Search — Fallback quando Síntese Trunca (Ponto 8)
# ============================================================================

def test_scenario_08_web_search_fallback_on_truncated_synthesis(live_server, monkeypatch):
    """
    Cenário: Web search executa; síntese é truncada por rate limit; fallback usa snippets.
    
    Objetivo: Validar que _recover_synthesis monta resposta com snippets crus (ponto 8).
    
    Passos:
    1. Mock web_search para retornar snippets no ToolResult.data
    2. Mock LLM para truncar síntese (429 após tool execution)
    3. POST: "Pesquise sobre inteligência artificial"
    4. Validar resposta: contém snippets (mesmo sem síntese do LLM)
    
    Relacionado: Ponto 8 do checkup (web search fallback)
    """
    # TODO: Implementar mock que:
    # - web_search retorna ToolResult(ok=True, data={"snippets": ["IA é...", "Redes neurais..."]})
    # - LLM falha na síntese final com 429
    # - _recover_synthesis extrai snippets de data e monta resposta
    pass


# ============================================================================
# CENÁRIO 9: Memory — Salvar e Buscar (Baseline)
# ============================================================================

def test_scenario_09_memory_save_and_search_baseline(live_server):
    """
    Cenário: Salvar memória e buscá-la na mesma session (baseline).
    
    Objetivo: Validar ciclo básico de memória (complementa cenário 3).
    
    Passos:
    1. POST: "Me lembre que eu gosto de pizza"
    2. Validar storage: memória salva
    3. POST: "O que eu gosto de comer?"
    4. Validar resposta: menciona "pizza"
    """
    # 1. Salvar memória
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Me lembre que eu gosto de pizza",
            "session_id": "session_09"
        }
    )
    assert response.status_code == 200
    
    # 2. Buscar memória
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "O que eu gosto de comer?",
            "session_id": "session_09"
        }
    )
    data = response.json()
    assert "pizza" in data["summary"].lower()


# ============================================================================
# CENÁRIO 10: Checklist Delete — Confirmação Destrutiva (Ponto 10)
# ============================================================================

def test_scenario_10_checklist_delete_requires_confirmation(live_server):
    """
    Cenário: Excluir checklist deve pedir confirmação (risk: destructive).
    
    Objetivo: Validar que delete_list usa CriticalConfirm (ponto 10).
    
    Passos:
    1. POST: "Crie checklist Teste"
    2. POST: "Exclua a checklist Teste"
    3. Validar resposta: status=pending_confirmation (não excluiu imediatamente)
    4. POST: aprovação de confirmação
    5. Validar storage: checklist foi excluída
    
    Relacionado: Ponto 10 do checkup (delete sem confirm)
    """
    # 1. Criar checklist
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Crie uma checklist Teste",
            "session_id": "session_10"
        }
    )
    assert response.status_code == 200
    
    # 2. Tentar excluir
    response = requests.post(
        f"{live_server.base_url}/api/agent/request",
        json={
            "text": "Exclua a checklist Teste",
            "session_id": "session_10"
        }
    )
    data = response.json()
    
    # TODO: Validar que resposta pede confirmação (CriticalConfirm.request)
    # assert data.get("status") == "pending_confirmation"
    # Após implementação do ponto 10, validar que checklist não foi excluída ainda
    
    # 3. Aprovar e validar exclusão
    # (requer endpoint de aprovação ou mock de CriticalConfirm.resolve)


# ============================================================================
# CENÁRIO 11: Rate Limit — Todas as Chaves em Cooldown (Degradação Graceful)
# ============================================================================

def test_scenario_11_rate_limit_all_keys_exhausted(live_server, monkeypatch):
    """
    Cenário: Todas as chaves estão em cooldown; sistema retorna mensagem user-friendly.
    
    Objetivo: Validar ProviderRateLimit exception e wait_message.
    
    Passos:
    1. Mock KeyRotator para marcar todas as chaves em cooldown
    2. POST: "Olá"
    3. Validar resposta: intent=error, summary menciona "sobrecarregado" e tempo de espera
    4. Validar: não crashou; não expôs API keys
    
    Relacionado: Ponto 4 do checkup (degradação de rate limit)
    """
    # TODO: Implementar mock que:
    # - KeyRotator.get_key() retorna "" (todas em cooldown)
    # - wait_message() retorna "4 de 4 chaves em cooldown, aguarde 10m3s"
    # - Validar resposta user-facing não contém "sk-xxx" ou stack trace
    pass


# ============================================================================
# FIXTURE HELPERS
# ============================================================================

def wait_for_server(base_url: str, timeout: int = 10) -> bool:
    """Aguarda servidor estar pronto com polling."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{base_url}/", timeout=1)
            if response.status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


def shutdown_server(thread: Thread, timeout: int = 5):
    """Envia shutdown signal e aguarda thread terminar."""
    # TODO: Implementar shutdown graceful
    # - POST /api/shutdown (se existir endpoint)
    # - Ou thread.join(timeout) + kill forcado
    pass
```

---

## Descrição dos 11 Cenários Mapeados

| # | Nome do Cenário | Relacionado ao Ponto | Objetivo de Validação |
|---|----------------|----------------------|------------------------|
| 1 | **Checklist Create & Get List** | Ponto 1 | LLM escolhe `get_list` (não `list_all`) ao listar itens |
| 2 | **Vision Model Fallback** | Ponto 2 | Fallback para Gemini quando Groq Vision model obsoleto |
| 3 | **Memory Cross-Session Search** | Ponto 3 | Memória salva em session A encontrada na session B |
| 4 | **Rate Limit Recovery Backoff** | Ponto 4 | `_recover_synthesis` tenta com backoff 2s, 4s |
| 5 | **Tool Selection Keyword Context** | Ponto 5 | "lista memórias" não ativa checklist_tool |
| 6 | **Action Sequence File-Wait-Read** | Ponto 6 | Rastreamento de tool_calls intermediários |
| 7 | **Timer Audio Callback** | Ponto 7 | Confirmação que `winsound.Beep` disparou |
| 8 | **Web Search Synthesis Fallback** | Ponto 8 | Recovery monta resposta com snippets quando síntese trunca |
| 9 | **Memory Save & Search Baseline** | Baseline | Ciclo básico de memória (complementa #3) |
| 10 | **Checklist Delete Confirmation** | Ponto 10 | `delete_list` pede confirmação via CriticalConfirm |
| 11 | **Rate Limit All Keys Exhausted** | Ponto 4 (degradação) | Mensagem user-friendly quando todas as chaves em cooldown |

**Nota:** O cenário original mencionado ("criar arquivo, esperar 2s, ler") corresponde ao **Cenário 6** no outline.

---

## Forma do Fixture que Sobe/Desce o Servidor

### Estratégia: Thread com Servidor Flask/FastAPI

**Arquitetura:**
```
┌─────────────────────────────────────────────────────┐
│ pytest test runner (main thread)                    │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Fixture: live_server (scope=module)          │  │
│  │                                              │  │
│  │ 1. Setup:                                    │  │
│  │    - tmp_path_factory.mktemp("jarvis-test") │  │
│  │    - Monkeypatch storage paths               │  │
│  │    - Thread: run_server()                    │  │
│  │    - wait_for_server() com polling           │  │
│  │                                              │  │
│  │ 2. Yield: base_url, data_dir, orchestrator   │  │
│  │                                              │  │
│  │ 3. Teardown:                                 │  │
│  │    - shutdown_server()                       │  │
│  │    - thread.join(timeout=5)                  │  │
│  │    - shutil.rmtree(data_dir)                 │  │
│  └──────────────────────────────────────────────┘  │
│           │                                         │
│           │ HTTP requests (requests.post/get)       │
│           ▼                                         │
│  ┌──────────────────────────────────────────────┐  │
│  │ Background Thread: run_server()              │  │
│  │                                              │  │
│  │  from app.ui.panel import create_app         │  │
│  │  app = create_app()                          │  │
│  │  app.run(host="127.0.0.1", port=8001)        │  │
│  │                                              │  │
│  │  (ou uvicorn.run se FastAPI)                 │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Alternativa: Subprocess com `main.py`**
- **Prós:** Mais próximo de produção; testa inicialização completa
- **Contras:** Menos controle; shutdown mais complexo; pode deixar processos órfãos
- **Recomendação:** Usar apenas se thread não funcionar (conflitos de event loop, etc.)

---

## Imports Esperados

```python
# Pytest e fixtures
import pytest
from pathlib import Path
from types import SimpleNamespace
import time
from threading import Thread
import shutil
import atexit

# HTTP client
import requests  # ou urllib.request

# Jarvis core
from app.agent.orchestrator import AgentOrchestrator
from app.services.llm import LLMService
from app.agent.tools.registry import ToolRegistry, registry
from app.storage.checklist_store import ChecklistStore, checklist_store
from app.storage.memory_facts import MemoryFacts, memory_facts
from app.storage.action_store import ActionStore
from app.agent.tools.timer import timer_tool  # para validar _active_timers
from app.core.critical_confirm import critical_confirm
from app.services.vision import VisionService

# Servidor (escolher uma opção)
from app.ui.panel import create_app  # Flask
# ou
# import uvicorn
# from app.ui.panel import app  # FastAPI

# Mocks e helpers
from app.services.rate_limits import ProviderRateLimit, retry_seconds
```

---

## Próximos Passos Recomendados

1. **Implementar fixture `live_server`** com thread de servidor em background
2. **Criar `FakeAgentLLM`** que retorna tool calls pré-programados (determinístico)
3. **Implementar cenários 1, 3, 6, 9** (baseline — sem depender de fixes dos pontos 1-10)
4. **Após fixes dos pontos 1-10:** implementar cenários 2, 4, 5, 7, 8, 10, 11 (validação das correções)
5. **Adicionar ao CI:** `pytest tests/test_live_integration.py -v -m integration`

**Marcação no CI:** Adicionar no `pytest.ini` ou `pyproject.toml`:
```ini
[pytest]
markers =
    integration: Tests that run against a live server (slow, excluded from default run)
    network: Tests that require network access
    hardware: Tests that require specific hardware (audio, camera, etc.)
```

**Comando CI rápido (sem integration):**
```bash
pytest tests/ -v -m "not integration and not network and not hardware"
```

**Comando CI completo (com integration):**
```bash
pytest tests/ -v  # roda tudo, incluindo integration
```

---

## Conclusão

O **PONTO 9 está CONFIRMADO**: não existe suite de testes de integração automatizada contra o servidor real. O arquivo `test_live_integration.py` não existe, e `test_live_server.py` é manual/limitado.

A solução proposta (criar `test_live_integration.py` com os 11 cenários) é **viável e recomendada**. O outline acima fornece a estrutura completa, incluindo:

✅ Fixture que sobe/desce servidor em background  
✅ Mock de LLM para testes determinísticos  
✅ Validação de storage e efeitos colaterais  
✅ Cobertura dos 10 pontos do checkup + baseline  
✅ Integração com CI via markers do pytest  

**Gravidade reafirmada:** 🟡 **MÉDIA-ALTA** — ausência deste suite permite regressões silenciosas em componentes críticos (orchestrator, LLM integration, tool selection, rate limit recovery).

---

**Fim do Documento de Achados — PONTO 9**
