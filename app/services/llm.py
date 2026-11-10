from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.core.capability_health import track_model_call
from app.core.runs import RunCancelled
from app.core.secrets_mask import mask_key
from app.storage.runtime_settings import get_llm_provider, resolve_ai_routes
from app.services.stm_filters import stm_filter

import time

try:
    from app.services.llm_router import SmartLLMRouter
    _smart_router = SmartLLMRouter()
    SMART_ROUTER_AVAILABLE = True
except Exception:
    _smart_router = None  # type: ignore[assignment]
    SMART_ROUTER_AVAILABLE = False

class KeyRotator:
    """
    Gerencia rotação inteligente de múltiplas chaves de API (Round-Robin / Failover)
    para Groq, Gemini e Oxyy com suporte a tempo de espera (cooldown) em caso de limite 429.
    """
    def __init__(self) -> None:
        self.cooldowns: dict[str, float] = {}
        self.indices: dict[str, int] = {"groq": 0, "gemini": 0, "oxyy": 0}

    def _cleaned_keys(self, provider: str, settings: Any) -> list[str]:
        if provider == "groq":
            keys = getattr(settings, "groq_api_keys", []) or [getattr(settings, "groq_api_key", "")]
        elif provider == "oxyy":
            keys = getattr(settings, "oxyy_api_keys", []) or [getattr(settings, "oxyy_api_key", "")]
        else:
            keys = getattr(settings, "gemini_api_keys", []) or [getattr(settings, "gemini_api_key", "")]
        return [k.strip() for k in keys if k and str(k).strip()]

    def get_key(self, provider: str, settings: Any) -> str:
        cleaned = self._cleaned_keys(provider, settings)
        if not cleaned:
            return ""

        now = time.time()
        start_idx = self.indices.get(provider, 0) % len(cleaned)

        # Procura a primeira chave que não está em cooldown
        for i in range(len(cleaned)):
            idx = (start_idx + i) % len(cleaned)
            k = cleaned[idx]
            cooldown_until = self.cooldowns.get(k, 0)
            if now >= cooldown_until:
                self.indices[provider] = idx
                return k

        # Se todas estiverem em cooldown, NÃO retorna chave bloqueada para evitar spam e loop infinito 429
        return ""

    def mark_cooldown(self, key: str, duration_seconds: float = 60.0) -> None:
        if not key:
            return
        self.cooldowns[key] = time.time() + duration_seconds
        print(f"[KeyRotator] Chave {mask_key(key)} colocada em cooldown por {int(duration_seconds)}s devido a Rate Limit (429).")

    def rotate_next(self, provider: str, settings: Any) -> str:
        cleaned = self._cleaned_keys(provider, settings)
        if not cleaned:
            return ""
        now = time.time()
        start_idx = (self.indices.get(provider, 0) + 1) % len(cleaned)
        for i in range(len(cleaned)):
            idx = (start_idx + i) % len(cleaned)
            k = cleaned[idx]
            if now >= self.cooldowns.get(k, 0):
                self.indices[provider] = idx
                return k
        # Todas as chaves do provider estão em cooldown
        return ""

_key_rotator = KeyRotator()


@dataclass(slots=True)
class LLMResponse:
    text: str | None = None
    function_calls: list[Any] = field(default_factory=list)
    candidates: list[Any] = field(default_factory=list)


@dataclass(slots=True)
class LLMService:
    settings: Any

    def get_active_provider(self, override: str | None = None) -> str:
        if override and override.lower() in {"gemini", "groq", "oxyy"}:
            return override.lower()
        env_default = getattr(self.settings, "llm_provider", "gemini") or "gemini"
        route = resolve_ai_routes({"llm_provider": env_default}).get("chat", {})
        effective = route.get("effective") or route.get("primary") or {"provider": get_llm_provider(env_default)}
        provider = str(effective.get("provider", env_default)).lower()
        if route.get("fallback_used"):
            print(f"[LLM] Rota chat efetiva: {provider} ({effective.get('model')}); {route.get('reason')}")
        return provider

    def _api_key_for(self, provider: str) -> str:
        return _key_rotator.get_key(provider, self.settings)

    _SAFE_MODEL_FALLBACKS = {
        "oxyy": "gpt-4o-mini",
        "groq": "llama-3.3-70b-versatile",
        "gemini": "gemini-2.5-flash",
    }

    def _sanitize_model(self, model: str, provider: str) -> str:
        """Rejeita IDs de placeholder/corrompidos e retorna um modelo seguro."""
        bad_prefixes = ("official-", "the provider", "unknown", "qwen3-235b")
        if not model or any(model.startswith(p) for p in bad_prefixes):
            safe = self._SAFE_MODEL_FALLBACKS.get(provider, "gpt-4o-mini")
            print(f"[LLM] Modelo invalido '{model}' rejeitado para {provider}, usando fallback: {safe}")
            return safe
        return model

    def _effective_chat_model(self, provider: str | None = None) -> str:
        """Retorna o modelo da rota efetiva, sem deixar cada método escolher outro."""
        active = provider or self.get_active_provider()
        route = resolve_ai_routes().get("chat", {})
        effective = route.get("effective") or {}
        if effective.get("provider") == active and effective.get("model"):
            return self._sanitize_model(str(effective["model"]), active)
        primary = route.get("primary") or {}
        if primary.get("provider") == active and primary.get("model"):
            return self._sanitize_model(str(primary["model"]), active)
        defaults = {
            "groq": getattr(self.settings, "groq_model", "llama-3.3-70b-versatile"),
            "oxyy": getattr(self.settings, "oxyy_chat_model", getattr(self.settings, "oxyy_model", "gemini-2.5-flash")),
            "gemini": getattr(self.settings, "llm_model", "gemini-flash-latest"),
        }
        result = str(defaults.get(active, defaults["gemini"]))
        return self._sanitize_model(result, active)

    @track_model_call()
    def ask(
        self,
        prompt: str,
        system_instruction: str | None = None,
        provider: str | None = None,
    ) -> str:
        active = self.get_active_provider(provider)
        api_key = self._api_key_for(active)
        if not api_key:
            if active == "groq":
                return "Chave GROQ_API_KEY não encontrada no .env. Configure-a ou volte para Gemini."
            return "Chave GEMINI_API_KEY não encontrada no .env. Por favor, configure-a para conversar com o Jarvis."

        try:
            response = self.generate(prompt, system_instruction=system_instruction, provider=active)
            return response.text or "Sem resposta gerada pelo modelo."
        except Exception as e:
            label = "Groq" if active == "groq" else "Gemini"
            return f"Erro ao acessar a API do {label}: {e}"

    @staticmethod
    def build_contents(history: list[dict], user_message: str) -> list[dict[str, str]]:
        contents: list[dict[str, str]] = []
        try:
            from app.agent.tool_markers import parse_tool_markers
        except ImportError:
            parse_tool_markers = None

        for msg in history[-20:]:
            role = msg.get("role", "user")
            text = (msg.get("content") or msg.get("text") or "").strip()
            if not text:
                continue
            gemini_role = "model" if role == "assistant" else "user"
            if gemini_role == "model" and parse_tool_markers and "[" in text and "]" in text:
                text, _ = parse_tool_markers(text)
                if not text:
                    continue
            contents.append({"role": gemini_role, "parts": [{"text": text}]})
        if user_message:
            contents.append({"role": "user", "parts": [{"text": user_message}]})
        return contents

    @staticmethod
    def _contents_to_openai_messages(contents: Any, system_instruction: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        if isinstance(contents, str):
            messages.append({"role": "user", "content": contents})
            return messages

        try:
            from app.agent.tool_markers import parse_tool_markers
        except ImportError:
            parse_tool_markers = None

        for item in contents or []:
            role = item.get("role", "user")
            parts = item.get("parts") or []
            text = ""
            if parts and isinstance(parts[0], dict):
                text = str(parts[0].get("text", "")).strip()
            elif parts:
                text = str(parts[0]).strip()
            if not text:
                continue
            oai_role = "assistant" if role == "model" else "user"
            if oai_role == "assistant" and parse_tool_markers and "[" in text and "]" in text:
                text, _ = parse_tool_markers(text)
                if not text:
                    continue
            messages.append({"role": oai_role, "content": text})
        return messages

    @track_model_call()
    def generate(
        self,
        contents: Any,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        # SmartLLMRouter: auto-seleciona provedor se nenhum foi forçado
        if provider is None and SMART_ROUTER_AVAILABLE and _smart_router is not None:
            prompt_text = contents if isinstance(contents, str) else str(contents)[:300]
            has_image = isinstance(contents, list) and any(
                isinstance(c, dict) and c.get("mime_type", "").startswith("image") for c in contents
            )
            decision = _smart_router.route(prompt_text, has_image=has_image)
            if _smart_router.is_provider_healthy(decision.primary_provider):
                provider = decision.primary_provider

        active = self.get_active_provider(provider)
        api_key = self._api_key_for(active)
        if not api_key:
            key_name = {"groq": "GROQ_API_KEY", "oxyy": "OXYY_API_KEY"}.get(active, "GEMINI_API_KEY")
            raise ValueError(f"{key_name} não configurada.")

        try:
            if active == "groq":
                return self._generate_groq(contents, tools, system_instruction, api_key)
            if active == "oxyy":
                return self._generate_oxyy(contents, tools, system_instruction, api_key)
            return self._generate_gemini(contents, tools, system_instruction, api_key)
        except Exception as exc:
            # Failover automático: marca provedor com erro e tenta o fallback
            if SMART_ROUTER_AVAILABLE and _smart_router is not None:
                _smart_router.mark_provider_error(active)
                fallback = "groq" if active != "groq" else "gemini"
                fallback_key = self._api_key_for(fallback)
                if fallback_key:
                    print(f"[LLM] Failover automático: {active} → {fallback} ({exc})")
                    if fallback == "groq":
                        return self._generate_groq(contents, tools, system_instruction, fallback_key)
                    return self._generate_gemini(contents, tools, system_instruction, fallback_key)
            raise

    @track_model_call()
    def generate_stream(
        self,
        contents: Any,
        on_chunk: Any = None,
        on_reasoning: Any = None,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        provider: str | None = None,
        mode: str | None = None,
    ) -> LLMResponse:
        active = self.get_active_provider(provider)
        api_key = self._api_key_for(active)
        if not api_key:
            key_name = {"groq": "GROQ_API_KEY", "oxyy": "OXYY_API_KEY"}.get(active, "GEMINI_API_KEY")
            raise ValueError(f"{key_name} não configurada.")

        if active == "groq":
            return self._generate_groq_stream(contents, on_chunk, tools, system_instruction, api_key, on_reasoning)
        if active == "oxyy":
            return self._generate_oxyy_stream(contents, on_chunk, tools, system_instruction, api_key, on_reasoning)
        return self._generate_gemini_stream(contents, on_chunk, tools, system_instruction, api_key, on_reasoning, mode=mode)

    def _oxyy_client(self, api_key: str):
        from openai import OpenAI
        return OpenAI(
            api_key=api_key,
            base_url=getattr(self.settings, "oxyy_base_url", "https://api.oxyy.ai/v1"),
        )

    def _oxyy_kwargs(self, contents: Any, tools: list[dict[str, Any]] | None, system_instruction: str | None) -> dict[str, Any]:
        raw_model = self._effective_chat_model("oxyy")
        model = self._sanitize_model(raw_model, "oxyy")
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._contents_to_openai_messages(contents, system_instruction),
            "temperature": 0.4,
        }
        if tools:
            kwargs["tools"] = [{"type": "function", "function": {
                "name": t["name"], "description": t.get("description", ""), "parameters": t["parameters"]
            }} for t in tools]
            kwargs["tool_choice"] = "auto"
        return kwargs

    @track_model_call("oxyy")
    def _generate_oxyy(self, contents: Any, tools: list[dict[str, Any]] | None, system_instruction: str | None, api_key: str) -> LLMResponse:
        completion = self._oxyy_client(api_key).chat.completions.create(**self._oxyy_kwargs(contents, tools, system_instruction))
        message = completion.choices[0].message
        calls: list[Any] = []
        for tc in getattr(message, "tool_calls", None) or []:
            fn = tc.function
            try:
                args = json.loads(fn.arguments or "{}")
            except Exception:
                args = {}
            calls.append(SimpleNamespace(name=fn.name, args=args, id=getattr(tc, "id", None)))
        return LLMResponse(text=getattr(message, "content", None), function_calls=calls)

    @track_model_call("oxyy")
    def _generate_oxyy_stream(self, contents: Any, on_chunk: Any, tools: list[dict[str, Any]] | None, system_instruction: str | None, api_key: str, on_reasoning: Any = None) -> LLMResponse:
        kwargs = self._oxyy_kwargs(contents, tools, system_instruction)
        kwargs["stream"] = True
        text = ""
        for chunk in self._oxyy_client(api_key).chat.completions.create(**kwargs):
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                text += piece
                if on_chunk:
                    on_chunk(piece)
        return LLMResponse(text=text)

    @track_model_call("groq")
    def _generate_groq_stream(
        self,
        contents: Any,
        on_chunk: Any,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None,
        api_key: str,
        on_reasoning: Any = None,
    ) -> LLMResponse:
        from groq import Groq
        client = Groq(api_key=api_key, max_retries=0)
        model_name = self._effective_chat_model("groq")
        messages = self._contents_to_openai_messages(contents, system_instruction)

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.4,
            "stream": True,
        }
        full_chunks = []
        try:
            stream_resp = client.chat.completions.create(**kwargs)
            for chunk in stream_resp:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                reason = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
                if reason and on_reasoning:
                    try:
                        on_reasoning(reason)
                    except Exception:
                        pass
                text_delta = getattr(delta, "content", None)
                if text_delta:
                    full_chunks.append(text_delta)
                    if on_chunk:
                        try:
                            on_chunk(text_delta)
                        except Exception:
                            pass
            return LLMResponse(text="".join(full_chunks))
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate_limit" in err_str or "limit" in err_str:
                _key_rotator.mark_cooldown(api_key, duration_seconds=60.0)
                next_key = _key_rotator.rotate_next("groq", self.settings)
                if next_key and next_key != api_key:
                    print(f"[Groq Stream] 429 detectado. Rotação IMEDIATA para chave ({mask_key(next_key)}).")
                    return self._generate_groq_stream(contents, on_chunk, tools, system_instruction, next_key, on_reasoning)
            print(f"[LLMStream Groq] Fallback devido a erro: {e}")
            return self._generate_groq(contents, tools, system_instruction, api_key)

    @track_model_call("gemini")
    def _generate_gemini_stream(
        self,
        contents: Any,
        on_chunk: Any,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None,
        api_key: str,
        on_reasoning: Any = None,
        mode: str | None = None,
    ) -> LLMResponse:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        model_name = self._effective_chat_model("gemini")
        config_args: dict[str, Any] = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        # Configurar Ultra-Thinking com budget estendido quando em planning/thinking
        if mode in {"planning", "thinking"}:
            config_args["thinking_config"] = types.ThinkingConfig(include_thoughts=True, thinking_budget=4096)
        elif on_reasoning:
            config_args["thinking_config"] = types.ThinkingConfig(include_thoughts=True)

        full_chunks = []
        try:
            response_stream = client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(**config_args) if config_args else None,
            )
            for chunk in response_stream:
                text_piece = getattr(chunk, "text", None)
                for candidate in getattr(chunk, "candidates", []):
                    for part in getattr(getattr(candidate, "content", None), "parts", []):
                        if getattr(part, "thought", False):
                            thought_text = getattr(part, "text", None)
                            if thought_text and on_reasoning:
                                try:
                                    on_reasoning(thought_text)
                                except Exception:
                                    pass
                            continue
                        if not text_piece and getattr(part, "text", None):
                            text_piece = part.text
                if text_piece:
                    full_chunks.append(text_piece)
                    if on_chunk:
                        try:
                            on_chunk(text_piece)
                        except Exception:
                            pass
            return LLMResponse(text="".join(full_chunks))
        except Exception as e:
            print(f"[LLMStream Gemini] Fallback devido a erro: {e}")
            return self._generate_gemini(contents, tools, system_instruction, api_key)

    def generate_with_messages(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        """Gera resposta usando mensagens já formatadas (para loop de function calling)."""
        active = self.get_active_provider(provider)
        api_key = self._api_key_for(active)
        if not api_key:
            key_name = "GROQ_API_KEY" if active == "groq" else "GEMINI_API_KEY"
            raise ValueError(f"{key_name} não configurada.")

        if active == "groq":
            from groq import Groq
            client = Groq(api_key=api_key, max_retries=0)
            model_name = self._effective_chat_model("groq")
            
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.4,
            }
            if tools:
                kwargs["tools"] = tools
            
            try:
                completion = client.chat.completions.create(**kwargs)
            except Exception as request_error:
                if "reasoning_effort" in str(request_error).lower() or "include_reasoning" in str(request_error).lower():
                    kwargs.pop("reasoning_effort", None)
                    kwargs.pop("include_reasoning", None)
                    completion = client.chat.completions.create(**kwargs)
                else:
                    raise
            message = completion.choices[0].message
            function_calls: list[Any] = []

            for tc in getattr(message, "tool_calls", None) or []:
                fn = tc.function
                args_raw = fn.arguments or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                except Exception:
                    args = {}
                function_calls.append(SimpleNamespace(name=fn.name, args=args, id=tc.id))

            return LLMResponse(
                text=getattr(message, "content", None),
                function_calls=function_calls,
            )
        
        # Para Gemini, precisaria implementar similar
        raise NotImplementedError("generate_with_messages não implementado para Gemini")

    @track_model_call("gemini")
    def _generate_gemini(
        self,
        contents: Any,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None,
        api_key: str,
    ) -> LLMResponse:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model_name = self._effective_chat_model("gemini")

        config_args: dict[str, Any] = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        if tools:
            declarations = []
            seen_decl: set[str] = set()
            for tool in tools:
                t_name = tool.get("name", "")
                if not t_name or t_name in seen_decl:
                    continue
                seen_decl.add(t_name)
                decl = types.FunctionDeclaration(
                    name=t_name,
                    description=tool.get("description", ""),
                    parameters_json_schema=tool.get("parameters"),
                )
                declarations.append(decl)
            config_args["tools"] = [types.Tool(function_declarations=declarations)]
            config_args["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)

        config = types.GenerateContentConfig(**config_args)
        
        try:
            raw = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
        except Exception as e:
            print(f"[Gemini] Erro na API: {e}")
            if "API key" in str(e) or "401" in str(e) or "403" in str(e):
                raise ValueError("Erro de autenticação com a API Gemini. Verifique a GEMINI_API_KEY no .env.")
            elif "429" in str(e):
                raise ValueError("Limite de taxa da API Gemini excedido. Tente novamente em alguns instantes.")
            elif "not found" in str(e).lower() or "400" in str(e):
                raise ValueError(f"Modelo '{model_name}' não encontrado. Verifique GEMINI_MODEL no .env.")
            raise

        function_calls: list[Any] = []
        if hasattr(raw, "function_calls") and raw.function_calls:
            function_calls.extend(raw.function_calls)
        candidates = getattr(raw, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", None) or []:
                fc = getattr(part, "function_call", None)
                if fc:
                    function_calls.append(fc)

        return LLMResponse(
            text=getattr(raw, "text", None),
            function_calls=function_calls,
            candidates=list(candidates),
        )

    @track_model_call("groq")
    def _generate_groq(
        self,
        contents: Any,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None,
        api_key: str,
    ) -> LLMResponse:
        from groq import Groq

        client = Groq(api_key=api_key, max_retries=0)
        model_name = self._effective_chat_model("groq")
        messages = self._contents_to_openai_messages(contents, system_instruction)

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.4,
        }
        if model_name.lower().startswith("openai/gpt-oss"):
            default_effort = "high" if "MODO DE PLANEJAMENTO" in (system_instruction or "") else "medium"
            kwargs["reasoning_effort"] = os.getenv("GROQ_REASONING_EFFORT", default_effort).lower()
            kwargs["include_reasoning"] = True
        
        # Tenta com tools, mas se falhar, retry sem tools
        try:
            if tools:
                kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["parameters"],
                        },
                    }
                    for tool in tools
                ]
                kwargs["tool_choice"] = "auto"

            completion = client.chat.completions.create(**kwargs)
            message = completion.choices[0].message
            function_calls: list[Any] = []

            for tc in getattr(message, "tool_calls", None) or []:
                fn = tc.function
                args_raw = fn.arguments or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                except Exception:
                    args = {}
                function_calls.append(SimpleNamespace(name=fn.name, args=args))
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate_limit" in err_str or "limit" in err_str:
                _key_rotator.mark_cooldown(api_key, duration_seconds=60.0)
                next_key = _key_rotator.rotate_next("groq", self.settings)
                if next_key and next_key != api_key:
                    print(f"[Groq Generate] 429 detectado. Rotação IMEDIATA para chave ({mask_key(next_key)}).")
                    return self._generate_groq(contents, tools, system_instruction, next_key)
            # Se erro de validação de tools, retry sem tools
            if "tool" in str(e).lower() or "validation" in str(e).lower():
                print(f"[Groq] Erro de validação de tools: {e}. Retry sem tools.")
                kwargs.pop("tools", None)
                kwargs.pop("tool_choice", None)
                completion = client.chat.completions.create(**kwargs)
                message = completion.choices[0].message
                function_calls: list[Any] = []
            else:
                raise

        return LLMResponse(
            text=getattr(message, "content", None),
            function_calls=function_calls,
        )

    @track_model_call()
    def chat_with_functions_stream(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        on_function_call: callable | None = None,
        on_chunk: callable | None = None,
        force_tool: bool = False,
        on_reasoning: callable | None = None,
        provider: str | None = None,
        mode: str | None = None,
    ) -> str | None:
        """Chat com function calling nativo para Gemini e Groq.

        on_reasoning recebe, em tempo real, os fragmentos de raciocínio do modelo
        (reasoning_content no Groq / thought parts no Gemini) para exibição ao vivo.
        Quando mode for 'planning' ou 'thinking', ativa Ultra-Thinking no Gemini (thinking_budget=4096).
        """
        active_provider = self.get_active_provider(provider)
        if active_provider == "groq":
            return self._chat_groq_stream(
                system_instruction=system_instruction,
                messages=messages,
                tools=tools,
                on_function_call=on_function_call,
                on_chunk=on_chunk,
                on_reasoning=on_reasoning,
            )
        if active_provider == "oxyy":
            return self._chat_oxyy_stream(
                system_instruction=system_instruction,
                messages=messages,
                tools=tools,
                on_function_call=on_function_call,
                on_chunk=on_chunk,
            )

        return self._chat_gemini_stream(
            system_instruction=system_instruction,
            messages=messages,
            tools=tools,
            on_function_call=on_function_call,
            on_chunk=on_chunk,
            force_tool=force_tool,
            on_reasoning=on_reasoning,
            mode=mode,
        )

    @track_model_call("gemini")
    def _chat_gemini_stream(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        on_function_call: callable | None = None,
        on_chunk: callable | None = None,
        force_tool: bool = False,
        on_reasoning: callable | None = None,
        mode: str | None = None,
    ) -> str | None:
        api_key = self._api_key_for("gemini")
        if not api_key:
            return None


        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            model_name = self._effective_chat_model("gemini")

            # Recuperar a última mensagem do usuário (suporta 'content' e 'text')
            last_user_msg = ""
            for m in reversed(messages or []):
                if m.get("role") == "user":
                    text = (m.get("content") or m.get("text") or "").strip()
                    if text:
                        last_user_msg = text
                        break

            # Construir histórico sem a última mensagem do usuário
            history_msgs = []
            matched_last = False
            for m in (messages or []):
                text = (m.get("content") or m.get("text") or "").strip()
                if m.get("role") == "user" and text == last_user_msg and not matched_last:
                    matched_last = True
                    continue
                history_msgs.append(m)

            contents = self.build_contents(history_msgs, last_user_msg)
            if not contents:
                contents = [{"role": "user", "parts": [{"text": last_user_msg or "Olá"}]}]


            # Configurar tools e config
            config_args: dict[str, Any] = {}
            if system_instruction:
                config_args["system_instruction"] = system_instruction
            if mode in {"planning", "thinking"}:
                config_args["thinking_config"] = types.ThinkingConfig(include_thoughts=True, thinking_budget=4096)
            else:
                config_args["thinking_config"] = types.ThinkingConfig(include_thoughts=True)

            if tools:
                declarations = []
                seen_decl_stream: set[str] = set()
                for t in tools:
                    t_name = t.get("name", "")
                    if not t_name or t_name in seen_decl_stream:
                        continue
                    seen_decl_stream.add(t_name)
                    declarations.append(
                        types.FunctionDeclaration(
                            name=t_name,
                            description=t.get("description", ""),
                            parameters_json_schema=t["parameters"],
                        )
                    )
                config_args["tools"] = [types.Tool(function_declarations=declarations)]
                config_args["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
                fc_mode = "ANY" if force_tool else "AUTO"
                config_args["tool_config"] = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode=fc_mode)
                )

            config = types.GenerateContentConfig(**config_args)
            response_stream = client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config,
            )

            function_calls: list[tuple[str, dict, Any]] = []
            full_text = ""

            for chunk in response_stream:
                # O chunk pode ter texto direto ou function_calls
                text_piece = getattr(chunk, "text", None)
                if text_piece:
                    full_text += text_piece
                    if on_chunk:
                        on_chunk(text_piece)

                # Procura por tools, pedacos de texto e raciocinio (thought) dentro dos candidates
                for candidate in getattr(chunk, "candidates", []):
                    for part in getattr(getattr(candidate, "content", None), "parts", []):
                        # Parts de raciocinio (thought=True) -> reasoning ao vivo
                        if getattr(part, "thought", False):
                            thought_text = getattr(part, "text", None)
                            if thought_text and on_reasoning:
                                try:
                                    on_reasoning(thought_text)
                                except Exception:
                                    pass
                            continue
                        fc = getattr(part, "function_call", None)
                        if fc:
                            args = dict(fc.args) if fc.args else {}
                            function_calls.append((fc.name, args, part))
                        # As vezes o chunk.text eh None mas o part.text existe
                        elif not text_piece and getattr(part, "text", None):
                            text_p = part.text
                            full_text += text_p
                            if on_chunk:
                                on_chunk(text_p)

            if not function_calls:
                return full_text if full_text else None

            # Executar function calls e montar segunda rodada
            fn_result_parts = []
            model_fc_parts = []
            for name, args, part in function_calls:
                model_fc_parts.append(part)
                if on_function_call:
                    result = on_function_call(name, args)
                    fn_result_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=name,
                                response={"result": str(result)},
                            )
                        )
                    )

            # Segunda geração com os resultados das ferramentas
            contents2 = list(contents)
            contents2.append(types.Content(role="model", parts=model_fc_parts))
            if fn_result_parts:
                contents2.append(types.Content(role="user", parts=fn_result_parts))

            thinking_cfg2 = (
                types.ThinkingConfig(include_thoughts=True, thinking_budget=4096)
                if mode in {"planning", "thinking"}
                else types.ThinkingConfig(include_thoughts=True)
            )
            config2 = types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None,
                thinking_config=thinking_cfg2,
            )
            final_stream = client.models.generate_content_stream(
                model=model_name,
                contents=contents2,
                config=config2,
            )
            
            final_text = ""
            for chunk in final_stream:
                text_piece = getattr(chunk, "text", None)
                if text_piece:
                    final_text += text_piece
                    if on_chunk:
                        on_chunk(text_piece)
                # Parts de raciocinio (thought=True) -> reasoning ao vivo
                for candidate in getattr(chunk, "candidates", []):
                    for part in getattr(getattr(candidate, "content", None), "parts", []):
                        if getattr(part, "thought", False):
                            thought_text = getattr(part, "text", None)
                            if thought_text and on_reasoning:
                                try:
                                    on_reasoning(thought_text)
                                except Exception:
                                    pass
                        elif not text_piece and getattr(part, "text", None):
                            text_p = part.text
                            final_text += text_p
                            if on_chunk:
                                on_chunk(text_p)

            return final_text if final_text else None

        except Exception as e:
            print(f"[LLM] Erro no function calling Gemini: {e}")
            import traceback
            traceback.print_exc()

            # Tentar extrair chamada de função em caso de erro de failed_generation (Gemini pode devolver isso)
            try:
                err_str = str(e)
                if "failed_generation" in err_str and ("<function=" in err_str or "function=" in err_str):
                    import re, json
                    print(f"[LLM] Detectado failed_generation no erro Gemini; extraindo chamada de função: {err_str}")
                    match = re.search(r'<function=([a-zA-Z0-9_]+)\s*(\{.*?\})', err_str)
                    if not match:
                        match = re.search(r'function=([a-zA-Z0-9_]+)\s*(\{.*?\})', err_str)
                    if match:
                        fn_name = match.group(1)
                        raw_args = match.group(2) or "{}"
                        try:
                            fn_args = json.loads(raw_args)
                        except Exception:
                            fn_args = {}
                        if on_function_call:
                            try:
                                tool_result = on_function_call(fn_name, fn_args)
                                return str(tool_result)
                            except Exception as exfn:
                                print(f"[LLM] Erro ao executar função extraída: {exfn}")
            except Exception:
                pass

            err_str = str(e).lower()
            # Rotação IMEDIATA entre chaves Gemini se houver mais de uma
            if "429" in err_str or "resource_exhausted" in err_str:
                _key_rotator.mark_cooldown(api_key, duration_seconds=60.0)
                next_key = _key_rotator.rotate_next("gemini", self.settings)
                if next_key and next_key != api_key:
                    print(f"[Gemini Stream] 429 detectado. Rotação IMEDIATA para chave Gemini ({mask_key(next_key)}).")
                    return self._chat_gemini_stream(
                        system_instruction=system_instruction,
                        messages=messages,
                        tools=tools,
                        on_function_call=on_function_call,
                        on_chunk=on_chunk,
                        force_tool=force_tool,
                        on_reasoning=on_reasoning,
                    )

            # Fallback automático para Groq em caso de Rate Limit (429) ou erro na API Gemini
            groq_key = self._api_key_for("groq")
            if groq_key:
                print("[LLM] Falha no Gemini. Fallback IMEDIATO para Groq...")
                try:
                    return self._chat_groq_stream(
                        system_instruction=system_instruction or "",
                        messages=messages,
                        tools=tools,
                        on_function_call=on_function_call,
                        on_chunk=on_chunk,
                        on_reasoning=on_reasoning,
                    )
                except Exception as groq_err:
                    print(f"[LLM] Falha no fallback Groq: {groq_err}")

            if "429" in err_str or "resource_exhausted" in err_str:
                raise ValueError("Limite de taxa da API Gemini excedido. Altere o provedor para 'Groq' nas Configurações do painel.")
            raise



    @track_model_call("oxyy")
    def _chat_oxyy_stream(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        on_function_call: callable | None = None,
        on_chunk: callable | None = None,
    ) -> str | None:
        """Chat OpenAI-compatible via Oxyy, com rotação de chaves e tools básicas."""
        api_key = self._api_key_for("oxyy")
        if not api_key:
            return None
        client = self._oxyy_client(api_key)
        payload_messages: list[dict[str, Any]] = []
        if system_instruction:
            payload_messages.append({"role": "system", "content": system_instruction})
        payload_messages.extend(messages or [])
        kwargs = self._oxyy_kwargs([], tools, None)
        kwargs["messages"] = payload_messages
        kwargs["stream"] = True
        text = ""
        tool_calls: dict[int, dict[str, str]] = {}
        try:
            stream = client.chat.completions.create(**kwargs)
            for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None)
                if piece:
                    text += piece
                    if on_chunk:
                        on_chunk(piece)
                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = getattr(tc, "index", 0) or 0
                    entry = tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if getattr(tc, "id", None):
                        entry["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            entry["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            entry["arguments"] += fn.arguments
            if not tool_calls:
                return text or None
            assistant_call = {"role": "assistant", "content": text or None, "tool_calls": []}
            results: list[dict[str, Any]] = []
            for entry in [tool_calls[i] for i in sorted(tool_calls)]:
                assistant_call["tool_calls"].append({"id": entry["id"], "type": "function", "function": {"name": entry["name"], "arguments": entry["arguments"] or "{}"}})
                try:
                    args = json.loads(entry["arguments"] or "{}")
                except Exception:
                    args = {}
                result = on_function_call(entry["name"], args) if on_function_call else "Ação concluída."
                results.append({"role": "tool", "tool_call_id": entry["id"], "content": str(result)})
            final_messages = payload_messages + [assistant_call] + results
            final_kwargs = {"model": self._effective_chat_model("oxyy"), "messages": final_messages, "temperature": 0.4, "stream": True}
            final_text = ""
            for chunk in client.chat.completions.create(**final_kwargs):
                if not getattr(chunk, "choices", None):
                    continue
                piece = getattr(chunk.choices[0].delta, "content", None)
                if piece:
                    final_text += piece
                    if on_chunk:
                        on_chunk(piece)
            return final_text or text or None
        except Exception as exc:
            if "429" in str(exc) or "rate" in str(exc).lower() or "limit" in str(exc).lower():
                _key_rotator.mark_cooldown(api_key, duration_seconds=600.0)
                next_key = _key_rotator.rotate_next("oxyy", self.settings)
                if next_key and next_key != api_key:
                    return self._chat_oxyy_stream(system_instruction, messages, tools, on_function_call, on_chunk)
            raise

    @track_model_call("groq")
    def _chat_groq_stream(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        on_function_call: callable | None = None,
        on_chunk: callable | None = None,
        on_reasoning: callable | None = None,
        tried_keys: set[str] | None = None,
    ) -> str | None:
        """Function calling nativo de 2 etapas para Groq (streaming + reasoning)."""
        from groq import Groq
        if tried_keys is None:
            tried_keys = set()

        api_key = self._api_key_for("groq")
        if not api_key:
            api_key = _key_rotator.rotate_next("groq", self.settings)

        if not api_key or api_key in tried_keys:
            gemini_key = self._api_key_for("gemini")
            if gemini_key:
                print("[LLM] Todas as chaves Groq em cooldown (429). Fallback IMEDIATO para Gemini...")
                return self._chat_gemini_stream(
                    system_instruction=system_instruction,
                    messages=messages,
                    tools=tools,
                    on_function_call=on_function_call,
                    on_chunk=on_chunk,
                    force_tool=False,
                    on_reasoning=on_reasoning,
                )
            oxyy_key = self._api_key_for("oxyy")
            if oxyy_key:
                print("[LLM] Todas as chaves Groq em cooldown (429). Fallback IMEDIATO para Oxyy...")
                return self._chat_oxyy_stream(
                    system_instruction=system_instruction,
                    messages=messages,
                    tools=tools,
                    on_function_call=on_function_call,
                    on_chunk=on_chunk,
                )
            return None

        client = Groq(api_key=api_key, max_retries=0)
        model_name = self._effective_chat_model("groq")

        formatted_messages: list[dict[str, Any]] = []
        if system_instruction:
            formatted_messages.append({"role": "system", "content": system_instruction})

        # Limita histórico recente para não estourar limite de TPM (8000 TPM no gpt-oss-120b na Groq)
        history_msgs = [m for m in (messages or []) if (m.get("content") or m.get("text"))]
        if len(history_msgs) > 10:
            history_msgs = history_msgs[-10:]

        for m in history_msgs:
            role = m.get("role", "user")
            content = str(m.get("content") or m.get("text") or "")
            if content:
                if len(content) > 3000:
                    content = content[:3000] + "... [truncado para caber no contexto]"
                formatted_messages.append({"role": role, "content": content})

        groq_tools = None
        if tools:
            # Proteção contra estouro de TPM na Groq:
            # Enviar 35 ferramentas consome ~6500 tokens só de schemas.
            # Filtramos para as essenciais + quaisquer mencionadas na última fala do usuário:
            core_groq_names = {
                "web_search", "system_control", "open_windows_app", "timer", "wait",
                "spotify", "whatsapp", "calendar", "file_manager", "notes",
                "cinema", "script_runner", "image_generator", "vision"
            }
            last_user_content = ""
            for msg in reversed(messages or []):
                if msg.get("role") == "user":
                    last_user_content = str(msg.get("content") or "").lower()
                    break

            selected_tools = []
            for tool in tools:
                t_name = tool.get("name", "")
                # routine só chega aqui quando o registro já casou horário/repetição no pedido.
                if t_name in core_groq_names or t_name == "routine" or t_name in last_user_content or t_name.replace("_", " ") in last_user_content:
                    selected_tools.append(tool)

            if not selected_tools:
                selected_tools = tools[:8]

            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": (tool.get("description", "") or "")[:200],
                        "parameters": tool["parameters"],
                    },
                }
                for tool in selected_tools
            ]

        def _emit_reasoning(piece: str) -> None:
            if piece and on_reasoning:
                try:
                    on_reasoning(piece)
                except Exception:
                    pass

        def _emit_chunk(piece: str) -> None:
            if piece and on_chunk:
                try:
                    on_chunk(piece)
                except Exception:
                    pass

        def _stream_turn(
            msgs: list[dict[str, Any]], with_tools: bool = True
        ) -> tuple[str, dict[int, dict[str, str]]]:
            """Streams one turn. Emite reasoning (delta.reasoning | delta.reasoning_content)
            e conteudo (delta.content) em tempo real.
            Retorna (texto_acumulado, tool_calls_agrupadas_por_index)."""
            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": msgs,
                "temperature": 0.4,
                "stream": True,
            }
            if model_name.lower().startswith("openai/gpt-oss"):
                # GPT-OSS só emite raciocínio quando este parâmetro é enviado.
                # O valor pode ser ajustado sem alterar código: low|medium|high.
                default_effort = "high" if "MODO DE PLANEJAMENTO" in (system_instruction or "") else "medium"
                kwargs["reasoning_effort"] = os.getenv("GROQ_REASONING_EFFORT", default_effort).lower()
                kwargs["include_reasoning"] = True
            if with_tools and groq_tools:
                kwargs["tools"] = groq_tools
                kwargs["tool_choice"] = "auto"

            text = ""
            tool_calls: dict[int, dict[str, str]] = {}

            try:
                stream = client.chat.completions.create(**kwargs)
            except Exception as request_error:
                if "reasoning_effort" in str(request_error).lower() or "include_reasoning" in str(request_error).lower():
                    kwargs.pop("reasoning_effort", None)
                    kwargs.pop("include_reasoning", None)
                    stream = client.chat.completions.create(**kwargs)
                else:
                    raise
            for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue

                reason = getattr(delta, "reasoning", None)
                if not reason:
                    reason = getattr(delta, "reasoning_content", None)
                if reason:
                    _emit_reasoning(reason)

                content = getattr(delta, "content", None)
                if content:
                    text += content
                    _emit_chunk(content)

                tcs = getattr(delta, "tool_calls", None)
                if tcs:
                    for tc in tcs:
                        idx = getattr(tc, "index", None) or 0
                        entry = tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                        if getattr(tc, "id", None):
                            entry["id"] = tc.id
                        fn = getattr(tc, "function", None)
                        if fn is not None:
                            if getattr(fn, "name", None):
                                entry["name"] = fn.name
                            args = getattr(fn, "arguments", None)
                            if args:
                                entry["arguments"] += args

            return text, tool_calls

        def _ordered_tool_calls(tool_calls: dict[int, dict[str, str]]) -> list[dict[str, str]]:
            return [tool_calls[i] for i in sorted(tool_calls)]

        try:
            first_text, first_tools = _stream_turn(formatted_messages, with_tools=bool(groq_tools))

            if not first_tools:
                return first_text if first_text else None

            # Executar as tools e montar a segunda rodada
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": first_text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"] or "{}"},
                    }
                    for tc in _ordered_tool_calls(first_tools)
                ],
            }
            formatted_messages.append(assistant_msg)

            for tc in _ordered_tool_calls(first_tools):
                fn_name = tc["name"]
                args_raw = tc["arguments"] or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                except Exception:
                    args = {}

                tool_result = ""
                if on_function_call:
                    try:
                        tool_result = str(on_function_call(fn_name, args))
                    except RunCancelled:
                        raise
                    except Exception as exfn:
                        print(f"[Groq] Erro ao executar tool {fn_name}: {exfn}")
                        tool_result = f"A ferramenta {fn_name} falhou; nada foi confirmado."

                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result or f"A ferramenta {fn_name} não devolveu resultado; nada foi confirmado.",
                })

            # Segunda rodada sem o bloco assistant/tool_calls. Alguns modelos
            # GPT-OSS tentam chamar a ferramenta novamente ao enxergar esse
            # bloco mesmo com tools desabilitadas, gerando "Tool choice is none".
            tool_summary = "\n".join(
                f"Resultado de {tc['name']}: {next((m.get('content', '') for m in reversed(formatted_messages) if m.get('role') == 'tool' and m.get('tool_call_id') == tc['id']), '')}"
                for tc in _ordered_tool_calls(first_tools)
            )
            final_messages = formatted_messages[:-(len(first_tools) + 1)]
            final_messages.append({"role": "user", "content": f"As ações solicitadas foram executadas. Resultados:\n{tool_summary}\nResponda ao usuário diretamente, sem chamar ferramentas novamente."})
            final_text = ""
            try:
                final_text, _final_tools = _stream_turn(final_messages, with_tools=False)
            except Exception as final_err:
                if "tool choice is none" not in str(final_err).lower() and "called a tool" not in str(final_err).lower():
                    raise
                # O modelo insistiu em chamar ferramenta no turno de sintese. Os resultados ja
                # existem: tenta uma vez so com o contexto em texto, depois entrega o resumo.
                print(f"[Groq] Turno final tentou chamar ferramenta; tentando de novo sem historico de tools: {final_err}")
                plain_messages = [
                    m for m in final_messages[:-1]
                    if m.get("role") in ("system", "user", "assistant") and not m.get("tool_calls")
                ]
                plain_messages.append({
                    "role": "user",
                    "content": f"Resultados das ferramentas (já executadas, não chame nenhuma ferramenta):\n{tool_summary}\n\nEscreva apenas a resposta final em texto para o usuário.",
                })
                try:
                    final_text, _final_tools = _stream_turn(plain_messages, with_tools=False)
                except Exception as retry_err:
                    print(f"[Groq] Retry do turno final falhou: {retry_err}")
                    final_text = ""
                if not final_text:
                    final_text = f"Resultados das ferramentas:\n{tool_summary}"
                    _emit_chunk(final_text)
            return final_text if final_text else (first_text or None)

        except RunCancelled:
            raise
        except Exception as e:
            err_msg = str(e)
            # Tratar caso o Groq retorne erro 400 tool_use_failed com failed_generation
            if "failed_generation" in err_msg and ("<function=" in err_msg or "function=" in err_msg):
                import re
                print(f"[Groq] Resgatando chamada de funcao do failed_generation: {err_msg}")
                match = re.search(r"<function=([a-zA-Z0-9_]+)(\(\{.*?\}\)|\{.*?\})", err_msg)
                if not match:
                    match = re.search(r"function=([a-zA-Z0-9_]+)(\(\{.*?\}\)|\{.*?\})", err_msg)

                if match:
                    fn_name = match.group(1)
                    raw_args = match.group(2).lstrip("(").rstrip(")")
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except Exception:
                        args = {}

                    tool_result = ""
                    if on_function_call:
                        try:
                            tool_result = str(on_function_call(fn_name, args))
                        except RunCancelled:
                            raise
                        except Exception as exfn:
                            print(f"[Groq] Erro ao executar tool {fn_name}: {exfn}")
                            tool_result = f"A ferramenta {fn_name} falhou; nada foi confirmado."

                    # Gerar resposta final em linguagem natural (streaming, com reasoning)
                    formatted_messages.append({"role": "user", "content": f"O resultado da acao {fn_name} foi: {tool_result}. Responda ao usuario com elegancia em 1 frase."})
                    try:
                        rescued_text, _rescued_tools = _stream_turn(formatted_messages, with_tools=False)
                        txt = rescued_text or tool_result
                        if on_chunk and txt:
                            _emit_chunk(txt)
                        return txt
                    except Exception:
                        return tool_result or f"A ferramenta {fn_name} não devolveu resultado; nada foi confirmado."

            print(f"[Groq Function Calling Stream] Erro: {e}")
            err_str = str(e).lower()
            if "413" in err_str or "too large" in err_str or "message size" in err_str:
                print("[Groq] Contexto excedeu limite de TPM/tamanho (413). Compactando histórico para 3 mensagens...")
                reduced_messages = (messages or [])[-3:]
                try:
                    return self._chat_groq_stream(
                        system_instruction=system_instruction[:1500] if system_instruction else None,
                        messages=reduced_messages,
                        tools=None,
                        on_function_call=on_function_call,
                        on_chunk=on_chunk,
                        on_reasoning=on_reasoning,
                    )
                except RunCancelled:
                    raise
                except Exception as retry_413_err:
                    print(f"[Groq] Falha após compactação: {retry_413_err}")

            if "429" in err_str or "rate_limit" in err_str or "limit" in err_str or "tpd" in err_str:
                # Marca a chave atual em cooldown (60s)
                _key_rotator.mark_cooldown(api_key, duration_seconds=60.0)
                tried_keys.add(api_key)

                # Tenta a próxima chave do pool Groq livre que ainda não foi tentada nesta chamada
                next_key = _key_rotator.rotate_next("groq", self.settings)
                if next_key and next_key not in tried_keys:
                    print(f"[Groq] Rate limit (429)! Alternando IMEDIATAMENTE para próxima chave ({mask_key(next_key)})...")
                    try:
                        return self._chat_groq_stream(
                            system_instruction=system_instruction,
                            messages=messages,
                            tools=tools,
                            on_function_call=on_function_call,
                            on_chunk=on_chunk,
                            on_reasoning=on_reasoning,
                            tried_keys=tried_keys,
                        )
                    except RunCancelled:
                        raise
                    except Exception as retry_err:
                        print(f"[Groq] Falha com chave secundária: {retry_err}")

                # Fallback automático IMEDIATO para Gemini se todas as chaves Groq falharem ou estiverem em cooldown
                gemini_key = self._api_key_for("gemini")
                if gemini_key:
                    print("[LLM] Todas as chaves Groq em cooldown (429). Fallback IMEDIATO para Gemini...")
                    try:
                        return self._chat_gemini_stream(
                            system_instruction=system_instruction,
                            messages=messages,
                            tools=tools,
                            on_function_call=on_function_call,
                            on_chunk=on_chunk,
                            force_tool=False,
                            on_reasoning=on_reasoning,
                        )
                    except Exception as gem_err:
                        print(f"[LLM] Falha no fallback para Gemini: {gem_err}")

                # Se Gemini falhar, tenta Oxyy
                oxyy_key = self._api_key_for("oxyy")
                if oxyy_key:
                    print("[LLM] Fallback IMEDIATO para Oxyy...")
                    try:
                        return self._chat_oxyy_stream(
                            system_instruction=system_instruction,
                            messages=messages,
                            tools=tools,
                            on_function_call=on_function_call,
                            on_chunk=on_chunk,
                        )
                    except Exception as oxyy_err:
                        print(f"[LLM] Falha no fallback para Oxyy: {oxyy_err}")

                raise ValueError("Todas as chaves da API Groq atingiram o limite de cota (429) e nenhum fallback respondeu.")
            raise


    def summarize(self, text: str, provider: str | None = None) -> str:
        normalized = (text or "").strip()
        if not normalized:
            return "Nenhum texto fornecido."
        prompt = f"Resuma o seguinte texto de forma concisa e objetiva:\n\n{normalized}"
        return self.ask(prompt, provider=provider)


    def detect_intent(self, text: str) -> str:
        normalized = (text or "").strip().lower()
        if "arquivo" in normalized or "pasta" in normalized:
            return "file"
        if "tarefa" in normalized or "meta" in normalized:
            return "productivity"
        if "voz" in normalized or "falar" in normalized:
            return "voice"
        return "general"
