from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.actions import FileActionService
from app.domain.productivity import ProductivityService
from app.agent.tools.registry import ToolRegistry
from app.agent.modes.tutor import build_tutor_system
from app.agent.tool_markers import parse_tool_markers, ToolStep
from app.agent.prompts import build_marker_agent_system_prompt, build_function_calling_system_prompt, AGENT_SYSTEM_CORE
from app.agent.runtime_modes import AgentMode
from app.agent.mode_resolver import ModeResolver
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.action_executor import ActionExecutor
from app.storage.session_store import get_session_history, save_session_history
from app.storage.enem_store import EnemStore
from app.storage.tutor_store import TutorStore
from app.agent.agent_model import AgentManager
from app.storage.vector import SemanticMemory
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
    ) -> None:
        self.settings = settings
        self.llm_service = llm_service
        self.memory_store = memory_store
        self.file_action_service = file_action_service or FileActionService()
        self.productivity_service = productivity_service or ProductivityService()
        self.tutor_store = tutor_store or TutorStore()
        self.enem_store = enem_store or EnemStore()
        self.agent_manager = agent_manager or AgentManager()
        self.semantic_memory = semantic_memory or SemanticMemory()
        
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
        
        base_folder = getattr(settings, "base_folder", None)
        self.registry = ToolRegistry(
            base_folder=base_folder,
            tutor_store=self.tutor_store,
            enem_store=self.enem_store,
        )
        self.last_plan: AgentPlan | None = None
        
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
            try:
                from app.agent.prompts import EPISODIC_MEMORY_PROMPT
                prompt = f"{EPISODIC_MEMORY_PROMPT}\n\nHistórico do dia:\n{history_text[:30000]}"
                summary = self.llm_service.ask(prompt)
                if summary:
                    self.semantic_memory.add_memory("episodic_memory", f"Resumo Diário (Episódico): {summary}")
                    with open(summary_file, "w") as f:
                        f.write(str(current_time))
            except Exception as e:
                print(f"Erro ao gerar resumo diário: {e}")

    def _remember_preferences(self, text: str, normalized: str) -> None:
        if not self.semantic_memory or not self.llm_service:
            return

        def _extract():
            try:
                from app.agent.prompts import EXTRACT_MEMORY_PROMPT
                prompt = f"{EXTRACT_MEMORY_PROMPT}\n\nMensagem do usuário: '{text}'"
                response = self.llm_service.ask(prompt)
                
                if response and "VAZIO" not in response:
                    for line in response.splitlines():
                        line = line.strip().strip("-* 1234567890.")
                        if line and len(line) > 5 and line.lower() != "vazio":
                            # Salva na memória semântica vetorial
                            self.semantic_memory.add_memory("user_memory", line)
            except Exception as e:
                print(f"Erro ao extrair memória inteligente: {e}")
                
        import threading
        threading.Thread(target=_extract, daemon=True).start()

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

    def _run_llm_with_tools(
        self,
        text: str,
        mode: str,
        session_id: str | None,
        history: list[dict],
        enem_question: dict[str, Any] | None = None,
        on_chunk: callable | None = None,
    ) -> AgentPlan:
        # Reset guardrails for new turn
        self.tool_guardrails.reset_turn()
        
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
            
            # Para Gemini e Groq (function calling nativo) usa prompt sem marcadores de texto
            active_provider = self.llm_service.get_active_provider() if self.llm_service else "gemini"
            if active_provider in {"gemini", "groq"}:
                system = build_function_calling_system_prompt(
                    base_persona="",
                    evolution_notes=evolution_notes,
                    preferences_summary="",
                    critical_confirm_enabled=False,
                )
            else:
                system = build_marker_agent_system_prompt(
                    base_persona="",
                    evolution_notes=evolution_notes,
                    critical_confirm_enabled=False,
                )
        
        # Preparar ferramentas para function calling nativo
        tools_decl = self.registry.get_tool_declarations()
        tool_context = {
            "session_id": session_id,
            "vision": self.vision_service,
            "browser": self.browser_agent,
            "settings": self.settings,
        }
        
        # Garantir que a mensagem atual do usuário está incluída na lista de mensagens
        full_messages = list(history)
        if text and (not full_messages or full_messages[-1].get("content") != text):
            full_messages.append({"role": "user", "content": text})

        # Usar function calling nativo para Gemini e Groq
        active_provider = self.llm_service.get_active_provider() if self.llm_service else "gemini"
        
        if active_provider in {"gemini", "groq"}:
            executed_actions: list[str] = []
            executed_tool_results: dict[str, dict] = {}

            # Function calling nativo
            def on_function_call(name: str, args: dict) -> str:
                # Execute the tool directly so we capture the full ToolResult (message + data)
                try:
                    tr = self.registry.execute_tool(name, args or {}, context=tool_context)
                except Exception as e:
                    tr = None
                # Record pattern and action
                self.pattern_learner.record_action(name, args)
                executed_actions.append(name)

                # Store rich result if available
                try:
                    if tr is not None:
                        executed_tool_results[name] = {
                            'ok': getattr(tr, 'ok', False),
                            'message': getattr(tr, 'message', ''),
                            'data': getattr(tr, 'data', None)
                        }
                        return getattr(tr, 'message', '')
                except Exception:
                    pass

                return ''
            
            result = self.llm_service.chat_with_functions_stream(
                system_instruction=system,
                messages=full_messages,
                tools=tools_decl,
                on_function_call=on_function_call,
                on_chunk=on_chunk,
                force_tool=False
            )
            raw = result or "Sem resposta."
            from app.agent.tool_markers import parse_tool_markers
            summary, _ = parse_tool_markers(raw)
            return AgentPlan(
                intent="tool_execution" if executed_actions else ("tutor" if mode == "tutor" else "general"),
                summary=summary,
                actions=executed_actions,
                context={'tool_results': executed_tool_results} if executed_tool_results else {},
                whiteboard_updated=False,
            )

        else:
            # Fallback para marcadores (Groq, etc)
            tools_decl = None
            contents = self.llm_service.build_contents(history, text)
            if on_chunk and hasattr(self.llm_service, "generate_stream"):
                response = self.llm_service.generate_stream(contents, on_chunk=on_chunk, tools=tools_decl, system_instruction=system)
            else:
                response = self.llm_service.generate(contents, tools=tools_decl, system_instruction=system)
            summary = getattr(response, "text", None) or "Sem resposta."
            
            # Extrair e executar marcadores de ferramentas
            speakable, tool_steps = parse_tool_markers(summary)
            
            actions: list[str] = []
            context_data: dict[str, Any] = {}
            whiteboard_updated = False
            
            if tool_steps:
                # Criar executor com proteções
                executor = ActionExecutor(
                    allowed_tool_names=frozenset(self.registry.tools.keys()),
                    guardrails=self.tool_guardrails,
                    legacy_execute=lambda name, args, user_line: self.registry.run_by_marker(name, args.get("command") if args else None, user_line).message
                )
                
                for step in tool_steps:
                    tool_name = step.kind
                    tool_arg = step.arg
                    
                    try:
                        self.pattern_learner.record_action(tool_name, {"command": tool_arg} if tool_arg else {})
                        res = executor.execute(tool_name, {"command": tool_arg} if tool_arg else {}, text)
                        actions.append(f"executar_{tool_name}")
                        context_data[tool_name] = {"arg": tool_arg, "result": res}
                        try:
                            from app.core.logger import logger
                            logger.record_tool_execution(tool_name)
                            logger.info("ToolExecutor", f"Ferramenta {tool_name} executada com sucesso", {"arg": tool_arg, "result": str(res)[:100]})
                        except Exception:
                            pass
                        if tool_name.startswith("whiteboard_"):
                            whiteboard_updated = True
                        # Para system_control, adicionar o resultado ao speakable
                        if tool_name == "system_control" and res:
                            if speakable and not speakable.endswith("."):
                                speakable += ". "
                            speakable += res
                    except Exception as e:
                        print(f"Erro ao executar ferramenta {tool_name}: {e}")
            
            # Se houver ferramentas executadas, usar o texto limpo (agora com resultados incluídos)
            final_summary = speakable if tool_steps else summary
            
            return AgentPlan(
                intent="tool_execution" if tool_steps else ("tutor" if mode == "tutor" else "general"),
                summary=final_summary,
                actions=actions,
                context=context_data,
                whiteboard_updated=whiteboard_updated,
            )


    def handle_request(
        self,
        text: str,
        session_id: str | None = None,
        mode: str = "general",
        history: list[dict] | None = None,
        enem_context: dict[str, Any] | None = None,
        enem_question_id: str | None = None,
        on_chunk: Any = None,
    ) -> AgentPlan:
        try:
            from app.core.logger import logger
            logger.record_request()
            logger.info("Orchestrator", f"Requisição recebida: {text[:60]}", {"mode": mode, "session_id": session_id})
        except Exception:
            pass

        normalized = (text or "").strip().lower()
        self._remember_preferences(text, normalized)

        if session_id and history is None:
            history = get_session_history(session_id)
        history = history or []

        enem_question = self._resolve_enem_context(enem_context, enem_question_id)
        if enem_question and mode == "tutor":
            subject = enem_question.get("subject") or enem_question.get("area") or "ENEM"
            year = enem_question.get("year")
            year_label = f" ({year})" if year else ""
            prefix = f"[Questão ENEM — {subject}{year_label}]\n{enem_question.get('text', '')}\n\n"
            if not text.strip().startswith("[Questão ENEM"):
                text = prefix + (text or "Vamos resolver esta questão juntos, passo a passo.")

        api_key = ""
        if self.llm_service:
            provider = self.llm_service.get_active_provider()
            api_key = self.llm_service._api_key_for(provider)

        if any(token in normalized for token in ["arquivo", "pasta", "folder", "documento"]) and mode != "tutor":
            action_result = None
            if self.file_action_service is not None:
                try:
                    action_result = self.file_action_service.execute(text)
                except Exception:
                    action_result = None
            if self.llm_service and api_key:
                prompt = f"O usuário solicitou: '{text}'. Resultado: {action_result}. Confirme de forma amigável."
                summary = self.llm_service.ask(prompt)
            else:
                summary = "Listei os arquivos da pasta solicitada."
            plan = AgentPlan(intent="file", summary=summary, actions=["listar arquivos"], context={"action_result": action_result})
            self.last_plan = plan
            return plan

        if any(token in normalized for token in ["tarefa", "meta", "habito", "hábito", "progresso"]) and mode != "tutor":
            task_title = normalized
            for phrase in ("adicione", "crie", "uma tarefa", "um item", "tarefa de", "tarefa"):
                task_title = task_title.replace(phrase, "")
            task_title = task_title.strip()
            if task_title.startswith("de "):
                task_title = task_title[3:].strip()
            if self.productivity_service and task_title:
                self.productivity_service.add_task(task_title)
            if self.llm_service and api_key:
                summary = self.llm_service.ask(f"Tarefa '{task_title}' registrada. Confirme brevemente.")
            else:
                summary = f"Tarefa '{task_title}' registrada."
            plan = AgentPlan(intent="productivity", summary=summary, actions=["criar item"], context={"task_title": task_title})
            self.last_plan = plan
            return plan

        if self.llm_service:
            if not api_key:
                provider = self.llm_service.get_active_provider()
                key_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
                plan = AgentPlan(
                    intent="general",
                    summary=(
                        f"Chave {key_name} não encontrada no .env. "
                        f"Configure-a ou altere o provedor LLM em Configurações."
                    ),
                    actions=["configurar api key"],
                )
                self.last_plan = plan
                return plan
            try:
                plan = self._run_llm_with_tools(
                    text, mode, session_id, history, enem_question=enem_question, on_chunk=on_chunk
                )
                if session_id:
                    updated = list(history)
                    updated.append({"role": "user", "content": text})
                    updated.append({"role": "assistant", "content": plan.summary})
                    save_session_history(session_id, updated[-40:])
                self.last_plan = plan
                return plan
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
    ):
        normalized = (text or "").strip().lower()
        self._remember_preferences(text, normalized)

        if session_id and history is None:
            history = get_session_history(session_id)
        history = history or []

        enem_question = self._resolve_enem_context(enem_context, enem_question_id)
        if enem_question and mode == "tutor":
            subject = enem_question.get("subject") or enem_question.get("area") or "ENEM"
            year = enem_question.get("year")
            year_label = f" ({year})" if year else ""
            prefix = f"[Questão ENEM — {subject}{year_label}]\n{enem_question.get('text', '')}\n\n"
            if not text.strip().startswith("[Questão ENEM"):
                text = prefix + (text or "Vamos resolver esta questão juntos, passo a passo.")

        api_key = ""
        if self.llm_service:
            provider = self.llm_service.get_active_provider()
            api_key = self.llm_service._api_key_for(provider)

        import queue
        import threading
        q = queue.Queue()

        if not api_key and self.llm_service:
            key_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
            summary = (f"Chave {key_name} não encontrada no .env. Configure-a ou altere o provedor LLM em Configurações.")
            plan = AgentPlan(intent="general", summary=summary, actions=["configurar api key"])
            self.last_plan = plan
            yield {"status": "complete", "plan": plan}
            return

        def on_chunk(chunk_text: str):
            q.put({"type": "chunk", "text": chunk_text})

        def run_llm():
            try:
                plan = self._run_llm_with_tools(
                    text, mode, session_id, history, enem_question=enem_question, on_chunk=on_chunk
                )
                if session_id:
                    updated = list(history)
                    updated.append({"role": "user", "content": text})
                    updated.append({"role": "assistant", "content": plan.summary})
                    save_session_history(session_id, updated[-40:])
                self.last_plan = plan
                q.put({"type": "done", "plan": plan})
            except Exception as e:
                import traceback
                print(f"[Orchestrator] Falha LLM Stream: {e}")
                print(f"[Orchestrator] Traceback: {traceback.format_exc()}")
                error_msg = f"Erro ao processar: {str(e)}"
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
