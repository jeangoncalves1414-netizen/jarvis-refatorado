from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.domain.actions import FileActionService
from app.storage import task_store
from app.agent.tools.registry import ToolRegistry
from app.agent.modes.tutor import build_tutor_system
from app.agent.tool_markers import parse_tool_markers, ToolStep
from app.agent.prompts import build_marker_agent_system_prompt, build_function_calling_system_prompt, AGENT_SYSTEM_CORE
from app.storage.runtime_settings import resolve_ai_routes
from app.agent.runtime_modes import AgentMode
from app.agent.mode_resolver import ModeResolver
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.action_executor import ActionExecutor
from app.agent.run_tracking import background_run, in_background, record_run_step, track_run
from app.agent import turn_meta
from app.agent.turn_context import build_turn_sections
from app.core.runs import REQUEST_ORIGINS, RunCancelled, check_run_cancelled, current_origin, current_run
from app.core.actions import ToolMetadata
from app.agent.tools.base import ToolResult
from app.storage.session_store import get_session_history, save_session_history
from app.storage.enem_store import EnemStore
from app.storage.tutor_store import TutorStore
from app.agent.agent_model import AgentManager
from app.storage.vector import SemanticMemory
from app.storage.vector.semantic_memory import is_technical_error_memory
from app.core import RateLimiter, ToolGuardrails, CriticalConfirm, Telemetry, Scheduler, Heartbeat, SettingsManager, UserManager, PatternLearner
from app.services import AppManager, WindowControl, FileProcessor, CalendarService, CalendarEvent

try:
    from app.services import VisionService, BrowserAgent
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

try:
    from app.services import WindowsNotification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

try:
    from app.ui import TrayIcon
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

try:
    from app.services import OllamaLLM
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


@dataclass(slots=True)
class AgentPlan:
    intent: str
    summary: str
    actions: list[str]
    context: dict[str, Any] = field(default_factory=dict)
    whiteboard_updated: bool = False


def _build_search_marker(tool_results: dict[str, dict[str, Any]]) -> str:
    """Converte o resultado estruturado da busca em um bloco renderizável no chat."""
    result = tool_results.get("web_search") or {}
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return ""
    payload = {
        "query": str(data.get("query") or ""),
        "workflow": str(data.get("workflow") or "search"),
        "steps": data.get("steps") or [],
        "results": data.get("results") or [],
    }
    try:
        return "__SEARCH__" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""


# Frases que justificam gastar uma chamada ao modelo para extrair memória (comparadas sem acento).
_MEMORY_TRIGGERS = (
    "prefiro", "prefer", "me lembre", "lembra que", "lembre que", "lembre-se", "quero que voce",
    "meu nome e", "me chamo", "eu moro", "moro em", "eu trabalho", "eu estudo", "eu sou",
    "minha idade", "meu aniversario", "nao esqueca", "anota que", "guarda que", "sempre que",
)

_RACE_STATUS = {"winner": "respondeu primeiro e foi usado", "empty": "devolveu resposta vazia", "failed": "falhou", "discarded": "descartado (outro respondeu antes)"}


def _record_race_attempts(race_res: dict[str, Any]) -> None:
    """Grava na Central o resultado de cada provedor da corrida, sem o texto das respostas (C6)."""
    for attempt in race_res.get("attempts") or []:
        status = attempt.get("status")
        text = f"Corrida: {attempt.get('provider')} {_RACE_STATUS.get(status, status)}"
        if attempt.get("elapsed_ms"):
            text += f" em {attempt['elapsed_ms']} ms"
        if attempt.get("reason"):
            text += f" ({attempt['reason']})"
        record_run_step(text + ".", kind="failure" if status == "failed" else "step")
    if not race_res.get("ok"):
        record_run_step(f"Corrida sem vencedor: {race_res.get('error') or 'motivo desconhecido'}", kind="failure")


def _build_cinema_marker(tool_results: dict[str, dict[str, Any]]) -> str:
    result = tool_results.get("cinema") or {}
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, dict):
        return ""
    if not any(key in data for key in ("catalog_results", "discovery_results", "detect_url", "imdb_id")):
        return ""
    try:
        return "__CINEMA_PLAY__" + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""


class AgentOrchestrator:
    def __init__(
        self,
        settings: Any | None = None,
        llm_service: Any | None = None,
        memory_store: Any | None = None,
        file_action_service: Any | None = None,
        productivity_service: Any | None = None,
        tutor_store: Any | None = None,
        enem_store: Any | None = None,
        agent_manager: Any | None = None,
        semantic_memory: Any | None = None,
        profile_memory: Any | None = None,
    ) -> None:
        self.settings = settings
        self.llm_service = llm_service
        self.memory_store = memory_store
        self.file_action_service = file_action_service or FileActionService(getattr(settings, "base_folder", None))
        self.productivity_service = productivity_service if productivity_service is not None else task_store
        self.tutor_store = tutor_store or TutorStore()
        self.enem_store = enem_store or EnemStore()
        self.agent_manager = agent_manager or AgentManager()
        self.semantic_memory = semantic_memory or SemanticMemory()
        self.profile_memory = profile_memory

        base_folder = getattr(settings, "base_folder", None)
        self.registry = ToolRegistry(
            base_folder=base_folder,
            tutor_store=self.tutor_store,
            enem_store=self.enem_store,
        )

        # Motores God Mode Avançados
        from app.agent.react_loop import ReActLoopEngine
        from app.agent.swarm import AgentSwarmManager
        from app.services.skill_distiller import SkillDistillerEngine
        from app.services.reflexion import ReflexionEngine

        self.react_loop = ReActLoopEngine(llm_service=self.llm_service, registry=self.registry)
        self.swarm = AgentSwarmManager(llm_service=self.llm_service)
        self.skill_distiller = SkillDistillerEngine(llm_service=self.llm_service)
        self.reflexion = ReflexionEngine(llm_service=self.llm_service)

        # Code Quality Pipeline (Snapshot + Review)
        try:
            from app.services.code_snapshots import CodeSnapshotManager
            from app.services.code_reviewer import CodeReviewPipeline
            self.snapshot_manager = CodeSnapshotManager()
            self.code_reviewer = CodeReviewPipeline(max_iterations=2)
        except Exception:
            self.snapshot_manager = None
            self.code_reviewer = None

        self.last_plan: AgentPlan | None = None
        
        # Sistemas de segurança FASE 1
        self.rate_limiter = RateLimiter(max_per_minute=10)
        self.guardrails = ToolGuardrails()
        self.tool_guardrails = ToolCallGuardrailController()
        self.critical_confirm = CriticalConfirm()
        self.telemetry = Telemetry()
        
        # Sistema de resolução de modo
        self.mode_resolver = ModeResolver()
        
        # Serviços de automação Windows FASE 2
        self.app_manager = AppManager()
        self.window_control = WindowControl()
        self.file_processor = FileProcessor()
        
        # Serviços de visão e web FASE 3 (opcionais)
        self.vision_service = None
        self.browser_agent = None
        if VISION_AVAILABLE:
            api_key = getattr(settings, "gemini_api_key", "")
            if api_key:
                try:
                    self.vision_service = VisionService(api_key=api_key)
                except RuntimeError:
                    pass
            try:
                self.browser_agent = BrowserAgent(headless=False)
            except RuntimeError:
                pass
        
        # Serviços de sistema FASE 4
        self.scheduler = Scheduler()
        self.heartbeat = Heartbeat()
        self.settings_manager = SettingsManager()
        self.user_manager = UserManager()
        
        # Sistema de aprendizado de padrões para proatividade
        self.pattern_learner = PatternLearner(min_occurrences=3, time_window_hours=24)
        
        # Integrações Windows
        self.calendar_service = CalendarService()
        self.notification_service = None
        if NOTIFICATIONS_AVAILABLE:
            try:
                self.notification_service = WindowsNotification()
                
                def on_pattern(pattern):
                    action_name = pattern.action
                    if self.notification_service:
                        self.notification_service.show(
                            "Sugestão do Jarvis",
                            f"Sir, notei o padrão '{action_name}' neste horário. Deseja executar?",
                            duration=8
                        )
                self.pattern_learner.add_callback(on_pattern)
            except RuntimeError:
                pass
        
        # Tray Icon
        self.tray_icon = None
        if TRAY_AVAILABLE:
            try:
                self.tray_icon = TrayIcon("Jarvis")
                self.tray_icon.set_menu_items([
                    ("Abrir Painel", lambda: None),
                    ("Parar Jarvis", lambda: None),
                    ("Sair", lambda: None)
                ])
            except RuntimeError:
                pass
        
        # LLM Local (Ollama)
        self.ollama_llm = None
        if OLLAMA_AVAILABLE:
            try:
                ollama_url = getattr(settings, "ollama_url", "http://localhost:11434")
                ollama_model = getattr(settings, "ollama_model", "llama3")
                self.ollama_llm = OllamaLLM(base_url=ollama_url, model=ollama_model)
            except RuntimeError:
                pass
        

        
        # Iniciar rotina de memória episódica
        if self.scheduler:
            self.scheduler.add_job(self._run_daily_summary, 3600)  # Verifica a cada hora

    def _run_daily_summary(self) -> None:
        if not self.llm_service or not self.semantic_memory:
            return
            
        import time, os
        from app.storage.session_store import list_sessions
        
        current_time = time.time()
        summary_file = os.path.join("data", "last_summary.txt")
        if os.path.exists(summary_file):
            try:
                last_run = float(open(summary_file).read().strip() or 0)
                if current_time - last_run < 86400:
                    return  # Já gerou um resumo nas últimas 24h
            except Exception:
                pass
                
        sessions = list_sessions()
        history_text = ""
        for s in sessions:
            updated_at = s.get("updated_at", 0)
            if current_time - updated_at < 86400:
                history_text += f"\nSessão: {s.get('title', 'Chat')}\n"
                for msg in s.get("history", []):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role and content:
                        history_text += f"{role}: {content}\n"
                        
        if len(history_text.strip()) > 100:
            # C6: o resumo diário chama o modelo sem pedido da usuária; vira pedido de origem "system".
            with background_run(mode="memory", source="background:daily_summary", origin="system") as job:
                try:
                    from app.agent.prompts import EPISODIC_MEMORY_PROMPT
                    prompt = f"{EPISODIC_MEMORY_PROMPT}\n\nHistórico do dia:\n{history_text[:30000]}"
                    summary = self.llm_service.ask(prompt)
                    if summary:
                        self.semantic_memory.add_memory("episodic_memory", f"Resumo Diário (Episódico): {summary}")
                        with open(summary_file, "w") as f:
                            f.write(str(current_time))
                        job.step("Resumo diário gravado na memória.")
                    else:
                        job.fail("Resumo diário: o modelo não devolveu texto.")
                except Exception as e:
                    job.fail(f"Resumo diário falhou ({type(e).__name__}).")
                    print(f"Erro ao gerar resumo diário: {e}")

    @staticmethod
    def _should_extract_memory(normalized: str) -> bool:
        """Gatilho da extração de memória em segundo plano (sem acento, minúsculas)."""
        try:
            from app.storage.runtime_settings import get_agent_loop_settings
            if get_agent_loop_settings().get("extract_memory_always"):
                return True
        except Exception:
            pass
        from app.agent.loop_policy import normalize
        value = normalize(normalized)
        return any(trigger in value for trigger in _MEMORY_TRIGGERS)

    def _remember_preferences(self, text: str, normalized: str, session_id: str | None = None) -> None:
        # Detecta preferências explícitas em linguagem natural e salva no memory_store (síncrono)
        _preference_triggers = ("prefiro", "prefer", "me lembre", "lembra que", "quero que voce", "quero que você")
        _style_keywords = {
            "curto": "short", "curta": "short", "curtos": "short", "curtas": "short",
            "breve": "short", "breves": "short", "resumido": "short", "resumida": "short",
            "detalhado": "detailed", "detalhada": "detailed", "detalhados": "detailed", "detalhadas": "detailed",
            "longo": "long", "longa": "long", "longos": "long", "longas": "long",
            "completo": "detailed", "completa": "detailed",
            "formal": "formal", "informal": "informal", "direto": "direct", "direta": "direct",
        }
        if self.memory_store and any(trigger in normalized for trigger in _preference_triggers):
            for kw, style in _style_keywords.items():
                if kw in normalized:
                    self.memory_store.add_preference("preferred_response_style", style)
                    break
            else:
                # Salva a preferência genérica sem categorizar o estilo
                self.memory_store.add_preference("general_preference", text.strip()[:120])

        # Também salva na memória semântica vetorial (assíncrono, quando disponível).
        # A extração custa uma chamada ao modelo: só roda com gatilho na mensagem ou com a opção
        # "Extrair memórias de toda mensagem" ligada em Configurações > Agente.
        should_extract = self._should_extract_memory(normalized)
        if should_extract:
            # Fase contexto 2: preferência com slot vira memória com fonte pelo Kernel (sem modelo).
            from app.services.memory_kernel import save_trigger_memory, save_via_kernel
            save_trigger_memory(text, session_id=session_id)
        if not self.semantic_memory or not self.llm_service:
            return
        if not should_extract:
            return
        turn_origin = current_origin.get()

        def _extract():
            try:
                from app.agent.prompts import EXTRACT_MEMORY_PROMPT
                prompt = f"{EXTRACT_MEMORY_PROMPT}\n\nMensagem do usuário: '{text}'"
                response = self.llm_service.ask(prompt)
                
                if response and "VAZIO" not in response and not is_technical_error_memory(response):
                    for line in response.splitlines():
                        line = line.strip().strip("-* 1234567890.")
                        if line and len(line) > 5 and line.lower() != "vazio":
                            # Salva na memória semântica vetorial
                            self.semantic_memory.add_memory("user_memory", line)
                            try:
                                save_via_kernel(line[:300], kind="extracao", session_id=session_id, origin=turn_origin)
                            except Exception:
                                pass
            except Exception as e:
                print(f"Erro ao extrair memória inteligente: {e}")
                raise
                
        import threading
        # C6: a extração (uma chamada ao modelo) fica registrada no pedido que a disparou.
        threading.Thread(target=in_background(_extract, label="Extração de memória da mensagem"), daemon=True).start()


    def _extract_function_calls(self, response: Any) -> list[Any]:
        calls = []
        if hasattr(response, "function_calls") and response.function_calls:
            calls.extend(response.function_calls)
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", None) or []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    calls.append(fc)
        return calls

    def _resolve_enem_context(
        self,
        enem_context: dict[str, Any] | None,
        enem_question_id: str | None,
    ) -> dict[str, Any] | None:
        if enem_context and enem_context.get("text"):
            return dict(enem_context)
        if enem_question_id:
            question = self.enem_store.get_question(str(enem_question_id))
            if question:
                return question
        return None

    @track_run
    def _run_llm_with_tools(
        self,
        text: str,
        mode: str,
        session_id: str | None,
        history: list[dict],
        enem_question: dict[str, Any] | None = None,
        on_chunk: callable | None = None,
        on_reasoning: callable | None = None,
        on_search: callable | None = None,
        profile_id: str | None = None,
    ) -> AgentPlan:
        # A pending approval retains this turn's limits, even during another chat.
        turn_guardrails = ToolCallGuardrailController()
        
        # Detect mode if not explicitly provided
        if mode == "general":
            mode_resolution = self.mode_resolver.resolve(text)
            mode = mode_resolution.mode.value
        
        if mode == "tutor":
            system = build_tutor_system(
                "tutor",
                self.tutor_store.get_summary_for_llm(),
                text,
                enem_question=enem_question,
            )
        else:
            evolution_notes = []
            
            # Recuperar memórias semânticas relevantes (RAG)
            # Recuperar memórias semânticas relevantes (RAG) apenas se a mensagem tiver substância
            if self.semantic_memory and self.semantic_memory.is_available() and text and len(text.strip().split()) > 2:
                relevant = self.semantic_memory.search_memories("user_memory", text, n_results=3)
                episodic = self.semantic_memory.search_memories("episodic_memory", text, n_results=1)
            else:
                relevant = []
                episodic = []
                
            import datetime
            for mem in relevant + episodic:
                mem_text = mem.get("text", "")
                meta = mem.get("metadata", {})
                timestamp = meta.get("timestamp", 0)
                if timestamp:
                    date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M')
                    evolution_notes.append(f"[{date_str}] {mem_text}")
                else:
                    evolution_notes.append(mem_text)
                    
            # Adicionar preferências (se houver)
            if self.memory_store:
                prefs = self.memory_store.get_preferences()
                if prefs:
                    evolution_notes.extend([f"Pref: {p['value']}" if isinstance(p, dict) else f"Pref: {p}" for p in prefs])

            # Memórias privadas só entram no contexto quando uma identidade
            # foi confirmada. Elas nunca são misturadas com user_memory global.
            if self.profile_memory and profile_id:
                try:
                    private = self.profile_memory.context(profile_id, text, limit=8)
                    for item in private:
                        kind = item.get("kind", "note")
                        evolution_notes.append(f"[Memória privada · {kind}] {item.get('text', '')}")
                except Exception:
                    pass

            # Memory Vault: AI Priming contextual + perfil do usuário (ai-memory-vault)
            try:
                from app.services.memory_vault import memory_vault
                priming_notes = memory_vault.get_priming_context(text)
                if priming_notes:
                    evolution_notes.append(f"[Priming Contextual]\n{priming_notes}")
                user_profile = memory_vault.get_user_profile()
                if user_profile:
                    # Inclui apenas as primeiras 600 chars do perfil para não inflar o contexto
                    evolution_notes.append(f"[Perfil do Usuário]\n{user_profile[:600]}")
            except Exception:
                pass
            
            # Para Gemini e Groq (function calling nativo) usa prompt sem marcadores de texto
            active_provider = self.llm_service.get_active_provider() if self.llm_service else "gemini"
            runtime_chat_route = resolve_ai_routes().get("chat")
            if active_provider in {"gemini", "groq", "oxyy"}:
                system = build_function_calling_system_prompt(
                    base_persona="",
                    evolution_notes=evolution_notes,
                    preferences_summary="",
                    critical_confirm_enabled=False,
                    runtime_route=runtime_chat_route,
                )
            else:
                system = build_marker_agent_system_prompt(
                    base_persona="",
                    evolution_notes=evolution_notes,
                    critical_confirm_enabled=False,
                    runtime_route=runtime_chat_route,
                )
            # Contexto situacional do turno (fase contexto 1): texto pronto, sem chamada ao modelo.
            system += build_turn_sections(text, current_origin.get()).text

            if mode == "planning":
                system += """

MODO DE PLANEJAMENTO: responda com um plano público, conciso e verificável.
Estruture em Objetivo, Plano de ação, Próximos passos e Riscos/decisões quando fizer sentido.
Não exponha raciocínio interno, cadeias de pensamento ou texto de deliberação privada.
Use ferramentas somente se elas ajudarem a validar ou executar uma etapa solicitada.
"""
            elif mode == "research":
                system += """

MODO DE PESQUISA: quando a pergunta depender de dados atuais ou de fontes externas,
use a ferramenta web_search com action='research' antes de concluir. Ela deve pesquisar
mais de uma fonte e retornar os links consultados. Diferencie fatos encontrados de
inferências e forneça URLs ou nomes das fontes usadas. Não invente fontes nem alegue
ter pesquisado se não pesquisou.
"""
        
        # Usar function calling nativo para Gemini e Groq
        active_provider = self.llm_service.get_active_provider() if self.llm_service else "gemini"

        # Preparar ferramentas para function calling nativo
        tools_decl = self.registry.get_tool_declarations(mode=mode, provider=active_provider, user_text=text)
        # C3: o executor do turno aceita só a lista de ferramentas do modo e do turno,
        # a mesma que o modelo enxerga; o catálogo completo não vale mais aqui.
        turn_tool_names = self.registry.allowed_tool_names(mode=mode, provider=active_provider, user_text=text)
        tool_context = {
            "session_id": session_id,
            "vision": self.vision_service,
            "browser": self.browser_agent,
            "settings": self.settings,
        }
        
        # Garantir que a mensagem atual do usuário está incluída na lista de mensagens
        full_messages = [{k: v for k, v in msg.items() if k != "run_id"} for msg in history]
        if text and (not full_messages or full_messages[-1].get("content") != text):
            full_messages.append({"role": "user", "content": text})

        if active_provider in {"gemini", "groq", "oxyy"}:
            executed_actions: list[str] = []
            executed_tool_results: dict[str, dict] = {}
            # Todas as chamadas do turno em ordem; o dicionário acima guarda só a última por nome.
            executed_tool_calls: list[dict[str, Any]] = []
            native_tool_results: dict[str, Any] = {}

            def native_legacy_execute(name: str, args: dict, _user_line: str) -> ToolResult:
                tool_result = self.registry.execute_tool(name, args or {}, context=tool_context)
                native_tool_results[name] = tool_result
                return tool_result

            native_executor = ActionExecutor(
                allowed_tool_names=turn_tool_names,
                guardrails=turn_guardrails,
                legacy_execute=native_legacy_execute,
                metadata_for=self.registry.get_tool_metadata,
                source=f"function:{session_id or 'default'}",
            )

            # Function calling nativo
            def on_function_call(name: str, args: dict) -> str:
                # All native function calls use the same proposal/audit boundary
                # as marker-based calls. The model never receives an ability to
                # elevate risk or fabricate approval state.
                try:
                    message = native_executor.execute(name, args or {}, text)
                    tr = native_tool_results.pop(name, None)
                except RunCancelled:
                    raise
                except Exception:
                    tr = None
                    message = "Não foi possível preparar a ação solicitada."
                # Record pattern and action
                self.pattern_learner.record_action(name, args)
                executed_actions.append(name)

                # Store rich result if available
                try:
                    if tr is not None:
                        executed_tool_results[name] = {
                            'ok': bool(native_executor.last_action and native_executor.last_action.status == 'succeeded'),
                            'message': getattr(tr, 'message', ''),
                            'data': getattr(tr, 'data', None)
                        }
                        executed_tool_calls.append({'name': name, **executed_tool_results[name]})
                        if name == "web_search" and on_search:
                            try:
                                payload = {
                                    "query": (getattr(tr, "data", {}) or {}).get("query", args.get("query", "")),
                                    "workflow": (getattr(tr, "data", {}) or {}).get("workflow", "search"),
                                    "steps": (getattr(tr, "data", {}) or {}).get("steps", []),
                                    "results": (getattr(tr, "data", {}) or {}).get("results", []),
                                }
                                on_search(payload)
                            except Exception:
                                pass
                        return message
                except Exception:
                    pass

                return message
            
            result = self.llm_service.chat_with_functions_stream(
                system_instruction=system,
                messages=full_messages,
                tools=tools_decl,
                on_function_call=on_function_call,
                on_chunk=on_chunk,
                on_reasoning=on_reasoning,
                force_tool=False
            )
            raw = result or "Sem resposta."
            summary, _ = parse_tool_markers(raw)
            # Aplicar filtros STM para remover preâmbulos robóticos e hesitações
            try:
                from app.services.stm_filters import stm_filter
                summary = stm_filter.process(summary)
            except Exception:
                pass
            search_marker = _build_search_marker(executed_tool_results)
            if search_marker:
                summary = f"{summary.rstrip()}\n\n{search_marker}" if summary.strip() else search_marker
            cinema_marker = _build_cinema_marker(executed_tool_results)
            if cinema_marker:
                summary = f"{summary.rstrip()}\n\n{cinema_marker}" if summary.strip() else cinema_marker
            return AgentPlan(
                intent="tool_execution" if executed_actions else ("tutor" if mode == "tutor" else "general"),
                summary=summary,
                actions=executed_actions,
                context={'tool_results': executed_tool_results, 'tool_calls': executed_tool_calls} if executed_tool_results else {},
                whiteboard_updated=False,
            )

        else:
            # Fallback para marcadores (Groq, etc)
            tools_decl = None
            contents = self.llm_service.build_contents(history, text)
            if on_chunk and hasattr(self.llm_service, "generate_stream"):
                response = self.llm_service.generate_stream(contents, on_chunk=on_chunk, tools=tools_decl, system_instruction=system, on_reasoning=on_reasoning)
            else:
                response = self.llm_service.generate(contents, tools=tools_decl, system_instruction=system)
            summary = getattr(response, "text", None) or "Sem resposta."
            
            # Extrair e executar marcadores de ferramentas
            speakable, tool_steps = parse_tool_markers(summary)
            
            actions: list[str] = []
            action_feedback: list[str] = []
            context_data: dict[str, Any] = {}
            whiteboard_updated = False
            
            if tool_steps:
                # Criar executor com proteções
                legacy_tool_results: dict[str, dict[str, Any]] = {}

                def legacy_execute(name: str, args: dict, user_line: str) -> ToolResult:
                    tool_result = self.registry.run_by_marker(name, args.get("command") if args else None, user_line)
                    legacy_tool_results[name] = {
                        "ok": getattr(tool_result, "ok", False),
                        "message": getattr(tool_result, "message", ""),
                        "data": getattr(tool_result, "data", None),
                    }
                    return tool_result

                executor = ActionExecutor(
                    allowed_tool_names=turn_tool_names,
                    guardrails=turn_guardrails,
                    legacy_execute=legacy_execute,
                    metadata_for=self.registry.get_tool_metadata,
                    source=f"marker:{session_id or 'default'}",
                )
                
                for step in tool_steps:
                    tool_name = step.kind
                    tool_arg = step.arg
                    
                    try:
                        self.pattern_learner.record_action(tool_name, {"command": tool_arg} if tool_arg else {})
                        res = executor.execute(tool_name, {"command": tool_arg} if tool_arg else {}, text)
                        actions.append(f"executar_{tool_name}")
                        context_data[tool_name] = {"arg": tool_arg, "result": res}
                        if not executor.last_action or executor.last_action.status != "succeeded":
                            action_feedback.append(f"{tool_name}: {res}")
                        try:
                            from app.core.logger import logger
                            logger.record_tool_execution(tool_name)
                            logger.info("ToolExecutor", f"Ferramenta {tool_name}: {executor.last_action.status if executor.last_action else 'bloqueada'}")
                        except Exception:
                            pass
                        if tool_name.startswith("whiteboard_") and executor.last_action and executor.last_action.status == "succeeded":
                            whiteboard_updated = True
                        # Para system_control, adicionar o resultado ao speakable
                        if tool_name == "system_control" and res:
                            if speakable and not speakable.endswith("."):
                                speakable += ". "
                            speakable += res
                    except RunCancelled:
                        raise
                    except Exception:
                        action_feedback.append(f"{tool_name}: não foi possível confirmar a execução. Consulte a Central.")
            
            # Se houver ferramentas executadas, usar o texto limpo (agora com resultados incluídos)
            # The model's marker preamble precedes execution and is not a receipt.
            final_summary = "\n\n".join(action_feedback) if action_feedback else speakable if tool_steps else summary
            search_marker = _build_search_marker(legacy_tool_results) if tool_steps else ""
            if search_marker:
                final_summary = f"{final_summary.rstrip()}\n\n{search_marker}" if final_summary.strip() else search_marker
            cinema_marker = _build_cinema_marker(legacy_tool_results) if tool_steps else ""
            if cinema_marker:
                final_summary = f"{final_summary.rstrip()}\n\n{cinema_marker}" if final_summary.strip() else cinema_marker
            ui_results = {name: legacy_tool_results[name] for name in ("open_window", "open_screen") if tool_steps and legacy_tool_results.get(name, {}).get("ok")}
            if ui_results:
                # Mesmo formato do caminho nativo: o painel lê context.tool_results.<ferramenta>.data.ui_window / ui_screen.
                context_data["tool_results"] = ui_results
            
            return AgentPlan(
                intent="tool_execution" if tool_steps else ("tutor" if mode == "tutor" else "general"),
                summary=final_summary,
                actions=actions,
                context=context_data,
                whiteboard_updated=whiteboard_updated,
            )


    def _run_local_shortcut(self, text: str, mode: str, session_id: str | None) -> AgentPlan | None:
        if mode not in {"general", "chat", "files"}:
            return None
        task = re.fullmatch(r"(?:adicione|adicionar|crie|criar)\s+(?:uma\s+)?tarefa\s+(?:de\s+)?(.+)", text.strip(), re.I)
        if not task and FileActionService.listing_target(text) is None:
            return None
        name = "create_local_task" if task else "list_local_directory"
        result_data = {}

        def execute(_name: str, args: dict, _user: str) -> ToolResult:
            if task:
                if self.productivity_service is None:
                    return ToolResult(False, "O serviço de tarefas não está disponível.")
                task_record = self.productivity_service.add_task(args["title"])
                if task_record is None:
                    return ToolResult(False, "O serviço de tarefas não confirmou a criação.")
                if isinstance(task_record, dict) and task_record.get("id"):
                    result_data["task_id"] = task_record["id"]
                return ToolResult(True, "Tarefa adicionada à lista.")
            if self.file_action_service is None:
                return ToolResult(False, "O serviço de arquivos não está disponível.")
            try:
                result = self.file_action_service.execute(args["request"])
            except FileNotFoundError:
                return ToolResult(False, "Não foi possível listar os arquivos: a pasta não foi encontrada.")
            except ValueError:
                return ToolResult(False, "Não foi possível listar os arquivos: o caminho está fora da pasta permitida.")
            if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                return ToolResult(False, "O serviço de arquivos não confirmou a listagem.")
            result_data.update(result)
            return ToolResult(True, f"Arquivos listados: {len(result['items'])} itens encontrados.", result)

        executor = ActionExecutor(
            frozenset({name}), ToolCallGuardrailController(), execute,
            metadata_for=lambda _: ToolMetadata(("productivity",) if task else ("files",), "low" if task else "observe"),
            source=f"shortcut:{session_id or 'default'}",
        )
        args = {"title": task[1].strip()} if task else {"request": text}
        try:
            message = executor.execute(name, args, text)
        except RunCancelled:
            raise
        except Exception:
            message = "A ação local falhou; conclusão não confirmada. Consulte a Central."
        succeeded = executor.last_action and executor.last_action.status == "succeeded"
        if succeeded and task:
            destination = " no painel pessoal" if self.productivity_service is task_store else ""
            message = f"Criei a tarefa “{args['title']}”{destination}."
        elif succeeded and result_data.get("items"):
            items = result_data["items"]
            message += "\n" + "\n".join(f"• {item}" for item in items[:40])
            if len(items) > 40:
                message += f"\nMais {len(items) - 40} itens na pasta."
        return AgentPlan(
            intent=("productivity" if task else "file") if succeeded else "error",
            summary=message, actions=[name],
            context={"task_title": args["title"], **result_data} if task else {"action_result": result_data},
        )

    def _run_agent_loop(self, text, mode, session_id, history, max_steps, on_progress, *, allowed_tools) -> AgentPlan:
        """Loop agêntico no pedido atual: progresso no barramento e no Run, retomada após aprovação."""
        from app.core import ui_events
        from app.storage.runtime_settings import get_agent_loop_settings

        settings = get_agent_loop_settings()
        context_run = current_run.get()
        store, run_id = (context_run[0], context_run[1]) if context_run else (None, None)

        def progress(event: dict) -> None:
            payload = {"type": "agent_progress", "session_id": session_id, "run_id": run_id, **event}
            ui_events.publish(payload)
            if store is not None and run_id:
                try:
                    store.update_run_progress(run_id, event)
                except Exception:
                    pass
            if on_progress:
                try:
                    on_progress(payload)
                except Exception:
                    pass

        def save_reply(reply: str, _trajectory: Any) -> None:
            # Resposta da retomada: entra no histórico da conversa e vai ao chat aberto.
            if session_id and reply and not is_technical_error_memory(reply):
                updated = [*get_session_history(session_id), {"role": "assistant", "content": reply, "run_id": run_id}]
                save_session_history(session_id, updated[-40:])
            ui_events.publish({"type": "agent_reply", "session_id": session_id, "run_id": run_id, "reply": reply})

        try:
            trajectory = self.react_loop.run_loop(
                text, max_steps=max_steps if max_steps is not None else settings["max_steps"],
                context={"session_id": session_id, "situational": build_turn_sections(text, current_origin.get()).text.strip()},
                allowed_tools=allowed_tools,
                max_model_calls=settings["max_model_calls"], verify=settings["auto_verify"],
                progress=progress, history=history, save_reply=save_reply,
            )
        except RunCancelled:
            raise
        except Exception:
            return AgentPlan(intent="error", summary="O modo ReAct falhou. Consulte as etapas na Central antes de tentar novamente.", actions=[])
        intent = "react_loop" if mode == "react" else "agent_loop"
        return AgentPlan(
            intent=intent if trajectory.success or trajectory.pending_action_id else "error",
            summary=trajectory.final_output,
            actions=[f"react_step_{s.step_number}" for s in trajectory.steps],
            context={
                "success": trajectory.success, "pending_action_id": trajectory.pending_action_id,
                "steps_count": len(trajectory.steps), "elapsed_sec": trajectory.total_elapsed_sec,
                "model_calls": trajectory.model_calls, "max_steps": trajectory.max_steps,
                "max_model_calls": trajectory.max_model_calls, "stopped_reason": trajectory.stopped_reason,
            },
        )

    @track_run
    def handle_request(
        self,
        text: str,
        session_id: str | None = None,
        mode: str = "general",
        history: list[dict] | None = None,
        enem_context: dict[str, Any] | None = None,
        enem_question_id: str | None = None,
        on_chunk: Any = None,
        on_reasoning: Any = None,
        on_search: Any = None,
        profile_id: str | None = None,
        racing_mode: bool = False,
        react_max_steps: int | None = None,
        origin: str | None = None,
        on_progress: Any = None,
        on_popup: Any = None,
    ) -> AgentPlan:
        from app.core import ui_events

        if history is None:
            history = get_session_history(session_id) if session_id else []
        # Toda ação deste turno registra a origem (voz ou chat) no Action Kernel;
        # sem origem explícita, uma chamada aninhada herda a do pedido que a contém.
        origin_token = current_origin.set(origin) if origin in REQUEST_ORIGINS else None
        # Coletor de popups do turno (lote 6); uma chamada aninhada usa o do pedido que a contém.
        popups = ui_events.current_popups.get()
        popup_tokens = []
        if popups is None:
            popups = []
            popup_tokens = [
                (ui_events.current_popups, ui_events.current_popups.set(popups)),
                (ui_events.current_popup_session, ui_events.current_popup_session.set(session_id)),
                (ui_events.current_popup_listener, ui_events.current_popup_listener.set(on_popup)),
            ]
        meta_token = turn_meta.start()  # contexto usado / memórias citadas do turno
        turn_extra: dict = {}
        try:
            plan = self._dispatch_request(
                text, session_id, mode, history, enem_context, enem_question_id,
                on_chunk, on_reasoning, on_search, profile_id, racing_mode, react_max_steps,
                on_progress,
            )
        finally:
            if meta_token is not None:
                turn_extra = turn_meta.snapshot()
                turn_meta.reset(meta_token)
            for var, token in reversed(popup_tokens):
                var.reset(token)
            if origin_token is not None:
                current_origin.reset(origin_token)
        if popup_tokens and popups:
            plan.context = {**(plan.context or {}), "ui_popups": list(popups)}
        if turn_extra:
            plan.context = {**(plan.context or {}), **turn_extra}
        check_run_cancelled()
        if session_id and plan.intent != "error" and not is_technical_error_memory(plan.summary):
            assistant_message = {"role": "assistant", "content": plan.summary, "run_id": current_run.get()[1]}
            updated = [*history, {"role": "user", "content": text}, assistant_message]
            save_session_history(session_id, updated[-40:])
        return plan

    def _dispatch_request(
        self, text, session_id, mode, history, enem_context, enem_question_id,
        on_chunk, on_reasoning, on_search, profile_id, racing_mode, react_max_steps,
        on_progress=None,
    ) -> AgentPlan:
        try:
            from app.core.logger import logger
            logger.record_request()
            logger.info("Orchestrator", f"Requisição recebida: {text[:60]}", {"mode": mode, "session_id": session_id, "racing": racing_mode})
        except Exception:
            pass

        # Se o modo ReAct estiver ativado ("Execução por etapas": ferramentas do modo, REACT_TOOLS)
        if mode == "react":
            plan = self._run_agent_loop(text, mode, session_id, history, react_max_steps, on_progress, allowed_tools=None)
            self.last_plan = plan
            return plan

        # Se o modo Swarm estiver ativado
        if mode == "swarm":
            try:
                swarm_res = self.swarm.route_and_execute(text)
                plan = AgentPlan(
                    intent="swarm_execution" if swarm_res.get("ok") is True else "error",
                    summary=swarm_res.get("summary", swarm_res.get("synthesis", swarm_res.get("code", str(swarm_res)))),
                    actions=[f"agent_{swarm_res.get('agent', 'swarm')}"],
                    context=swarm_res
                )
                self.last_plan = plan
                return plan
            except RunCancelled:
                raise
            except Exception:
                plan = AgentPlan(intent="error", summary="A execução do especialista falhou.", actions=[])
                self.last_plan = plan
                return plan

        # Se o modo Racing estiver ativado e for uma pergunta geral
        if racing_mode and mode not in {"tutor", "planning", "research"} and self.llm_service:
            try:
                from app.services.llm_racing import MultiLLMRacingService
                racing_svc = MultiLLMRacingService(llm_service=self.llm_service)
                record_run_step("Corrida entre modelos iniciada.")
                race_res = racing_svc.race_prompt(text)
                _record_race_attempts(race_res)
                if race_res.get("ok"):
                    summary = race_res.get("response", "")
                    badge = race_res.get("badge", "")
                    plan = AgentPlan(
                        intent="racing",
                        summary=summary,
                        actions=["multi_llm_race"],
                        context={"racing": True, "badge": badge, "winner": race_res.get("winner_provider"), "elapsed_ms": race_res.get("elapsed_ms")}
                    )
                    self.last_plan = plan
                    return plan
            except RunCancelled:
                raise
            except Exception as exc:
                record_run_step(f"Corrida entre modelos falhou ({type(exc).__name__}); seguindo pelo caminho normal.", kind="failure")
                print(f"[Orchestrator] Falha no modo Racing: {exc}")

        check_run_cancelled()
        normalized = (text or "").strip().lower()
        plan = self._run_local_shortcut(text, mode, session_id)
        if plan is not None:
            self.last_plan = plan
            return plan
        self._remember_preferences(text, normalized, session_id)

        enem_question = self._resolve_enem_context(enem_context, enem_question_id)
        if enem_question and mode == "tutor":
            subject = enem_question.get("subject") or enem_question.get("area") or "ENEM"
            year = enem_question.get("year")
            year_label = f" ({year})" if year else ""
            prefix = f"[Questão ENEM — {subject}{year_label}]\n{enem_question.get('text', '')}\n\n"
            if not text.strip().startswith("[Questão ENEM"):
                text = prefix + (text or "Vamos resolver esta questão juntos, passo a passo.")

        if self.llm_service:
            provider = self.llm_service.get_active_provider()
            api_key = self.llm_service._api_key_for(provider)
            if not api_key:
                key_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
                plan = AgentPlan(
                    intent="general",
                    summary=(
                        f"Chave {key_name} não encontrada no .env. "
                        f"Configure-a ou altere o provedor LLM em Configurações."
                    ),
                    actions=["configurar api key"],
                    context={"success": False},
                )
                self.last_plan = plan
                return plan
            # Loop agêntico (regra, zero modelo): pedido de várias partes planeja, age e confere sozinho.
            if getattr(self, "react_loop", None) is not None and self.registry is not None:
                from app.agent.loop_policy import mentions_alarm, should_use_agent_loop, wait_intent
                from app.storage.runtime_settings import get_agent_loop_settings
                use_loop, reason = should_use_agent_loop(text, mode, get_agent_loop_settings())
                if use_loop:
                    record_run_step(f"Loop agêntico escolhido ({reason}).")
                    allowed = self.registry.allowed_tool_names(mode="general", provider=provider, user_text=text, narrow=True)
                    # Pedido com espera e sem alarme: timer só bipa e não pausa; sem ele o modelo usa wait.
                    if wait_intent(text) is not None and not mentions_alarm(text):
                        allowed = frozenset(allowed) - {"timer"}
                    plan = self._run_agent_loop(text, mode, session_id, history, react_max_steps, on_progress, allowed_tools=allowed)
                    self.last_plan = plan
                    return plan
            try:
                plan = self._run_llm_with_tools(
                    text, mode, session_id, history, enem_question=enem_question, on_chunk=on_chunk, on_reasoning=on_reasoning, on_search=on_search, profile_id=profile_id
                )
                check_run_cancelled()
                if profile_id and self.profile_memory and plan.intent != "error" and not is_technical_error_memory(plan.summary):
                    try:
                        self.profile_memory.add(
                            profile_id,
                            f"Usuário: {text}\nJarvis: {plan.summary}",
                            kind="conversation",
                            importance=0.25,
                            source="chat",
                        )
                    except Exception:
                        pass
                self.last_plan = plan
                return plan
            except RunCancelled:
                raise
            except Exception as e:
                import traceback
                print(f"[Orchestrator] Falha LLM: {e}")
                print(f"[Orchestrator] Traceback: {traceback.format_exc()}")
                # Retorna erro mais detalhado para debug
                error_msg = f"Erro ao processar: {str(e)}"
                if "API key" in str(e).lower() or "401" in str(e) or "403" in str(e):
                    error_msg = "Erro de autenticação com a API. Verifique as chaves no .env."
                elif "429" in str(e):
                    error_msg = "Limite de taxa da API excedido. Tente novamente em alguns instantes."
                elif "timeout" in str(e).lower():
                    error_msg = "Timeout na conexão com a API. Verifique sua internet."
                elif "connection" in str(e).lower():
                    error_msg = "Erro de conexão com a API. Verifique sua internet."
                
                if "tool choice is none" in str(e).lower() or "model called a tool" in str(e).lower():
                    error_msg = "O Groq encontrou uma incompatibilidade ao chamar uma ferramenta. Tente novamente ou altere o provedor para Gemini."
                plan = AgentPlan(
                    intent="error",
                    summary=error_msg,
                    actions=[],
                )
                self.last_plan = plan
                return plan

        plan = AgentPlan(
            intent="general",
            summary="Ocorreu uma instabilidade. Tente novamente.",
            actions=[],  # Sem ações para erros
            context={"success": False},
        )
        self.last_plan = plan
        return plan

    def handle_request_stream(
        self,
        text: str,
        session_id: str | None = None,
        mode: str = "general",
        history: list[dict] | None = None,
        enem_context: dict[str, Any] | None = None,
        enem_question_id: str | None = None,
        profile_id: str | None = None,
        origin: str | None = None,
    ):
        import queue
        import threading
        q = queue.Queue()

        def on_chunk(chunk_text: str):
            q.put({"type": "chunk", "text": chunk_text})

        def on_reasoning(reason_text: str):
            q.put({"type": "reasoning", "text": reason_text})

        def on_progress(event: dict):
            q.put({"type": "progress", "event": event})

        def on_popup(popup: dict):
            q.put({"type": "popup", "popup": popup})

        def run_llm():
            try:
                plan = self.handle_request(
                    text, mode=mode, session_id=session_id, history=history,
                    enem_context=enem_context, enem_question_id=enem_question_id,
                    on_chunk=on_chunk, on_reasoning=on_reasoning, profile_id=profile_id, origin=origin,
                    on_progress=on_progress, on_popup=on_popup,
                )
                self.last_plan = plan
                q.put({"type": "error" if plan.intent == "error" else "done", "plan": plan})
            except Exception as e:
                import traceback
                print(f"[Orchestrator] Falha LLM Stream: {e}")
                print(f"[Orchestrator] Traceback: {traceback.format_exc()}")
                error_msg = f"Erro ao processar: {str(e)}"
                if "tool choice is none" in str(e).lower() or "model called a tool" in str(e).lower():
                    error_msg = "O Groq encontrou uma incompatibilidade ao chamar uma ferramenta. Tente novamente ou altere o provedor para Gemini."
                plan = AgentPlan(intent="error", summary=error_msg, actions=[])
                self.last_plan = plan
                q.put({"type": "error", "plan": plan})

        t = threading.Thread(target=run_llm)
        t.start()

        yield {"status": "thinking"}

        while True:
            msg = q.get()
            if msg["type"] == "done":
                yield {"status": "complete", "plan": msg["plan"]}
                break
            elif msg["type"] == "error":
                yield {"status": "error", "plan": msg["plan"]}
                break
            elif msg["type"] == "chunk":
                yield {"status": "streaming", "chunk": msg["text"]}
            elif msg["type"] == "reasoning":
                yield {"status": "reasoning", "text": msg["text"]}
            elif msg["type"] == "progress":
                event = {key: value for key, value in msg["event"].items() if key != "type"}
                yield {"status": "progress", **event}
            elif msg["type"] == "popup":
                yield {"status": "popup", "popup": msg["popup"]}
