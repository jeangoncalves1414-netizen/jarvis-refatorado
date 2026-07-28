from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.storage.runtime_settings import get_llm_provider


import time

class KeyRotator:
    """
    Gerencia rotação inteligente de múltiplas chaves de API (Round-Robin / Failover)
    para Groq e Gemini com suporte a tempo de espera (cooldown) em caso de limite 429.
    """
    def __init__(self) -> None:
        self.cooldowns: dict[str, float] = {}
        self.indices: dict[str, int] = {"groq": 0, "gemini": 0}

    def get_key(self, provider: str, settings: Any) -> str:
        if provider == "groq":
            keys = getattr(settings, "groq_api_keys", []) or [getattr(settings, "groq_api_key", "")]
        else:
            keys = getattr(settings, "gemini_api_keys", []) or [getattr(settings, "gemini_api_key", "")]

        cleaned = [k.strip() for k in keys if k and str(k).strip()]
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

        # Se todas estiverem em cooldown, retorna a que vai liberar primeiro
        best_k = min(cleaned, key=lambda k: self.cooldowns.get(k, 0))
        return best_k

    def mark_cooldown(self, key: str, duration_seconds: float = 300.0) -> None:
        if not key:
            return
        self.cooldowns[key] = time.time() + duration_seconds
        print(f"[KeyRotator] Chave {key[:8]}... colocada em cooldown por {int(duration_seconds)}s devido a Rate Limit (429).")

    def rotate_next(self, provider: str, settings: Any) -> str:
        if provider == "groq":
            keys = getattr(settings, "groq_api_keys", []) or [getattr(settings, "groq_api_key", "")]
        else:
            keys = getattr(settings, "gemini_api_keys", []) or [getattr(settings, "gemini_api_key", "")]
        cleaned = [k.strip() for k in keys if k and str(k).strip()]
        if not cleaned:
            return ""
        self.indices[provider] = (self.indices.get(provider, 0) + 1) % len(cleaned)
        return self.get_key(provider, settings)

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
        if override and override.lower() in {"gemini", "groq"}:
            return override.lower()
        env_default = getattr(self.settings, "llm_provider", "gemini") or "gemini"
        provider = get_llm_provider(env_default)
        
        # Fallback: se Gemini não tem API key, usa Groq
        if provider == "gemini" and not self._api_key_for("gemini"):
            if self._api_key_for("groq"):
                print("[LLM] Gemini API key não configurada, usando Groq como fallback")
                return "groq"
        
        return provider

    def _api_key_for(self, provider: str) -> str:
        return _key_rotator.get_key(provider, self.settings)

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

    def generate(
        self,
        contents: Any,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        active = self.get_active_provider(provider)
        api_key = self._api_key_for(active)
        if not api_key:
            key_name = "GROQ_API_KEY" if active == "groq" else "GEMINI_API_KEY"
            raise ValueError(f"{key_name} não configurada.")

        if active == "groq":
            return self._generate_groq(contents, tools, system_instruction, api_key)
        return self._generate_gemini(contents, tools, system_instruction, api_key)

    def generate_stream(
        self,
        contents: Any,
        on_chunk: Any = None,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        active = self.get_active_provider(provider)
        api_key = self._api_key_for(active)
        if not api_key:
            key_name = "GROQ_API_KEY" if active == "groq" else "GEMINI_API_KEY"
            raise ValueError(f"{key_name} não configurada.")

        if active == "groq":
            return self._generate_groq_stream(contents, on_chunk, tools, system_instruction, api_key)
        return self._generate_gemini_stream(contents, on_chunk, tools, system_instruction, api_key)

    def _generate_groq_stream(
        self,
        contents: Any,
        on_chunk: Any,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None,
        api_key: str,
    ) -> LLMResponse:
        from groq import Groq
        client = Groq(api_key=api_key)
        model_name = getattr(self.settings, "groq_model", "llama-3.3-70b-versatile")
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
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    text_delta = chunk.choices[0].delta.content
                    full_chunks.append(text_delta)
                    if on_chunk:
                        try:
                            on_chunk(text_delta)
                        except Exception:
                            pass
            return LLMResponse(text="".join(full_chunks))
        except Exception as e:
            print(f"[LLMStream Groq] Fallback devido a erro: {e}")
            return self._generate_groq(contents, tools, system_instruction, api_key)

    def _generate_gemini_stream(
        self,
        contents: Any,
        on_chunk: Any,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None,
        api_key: str,
    ) -> LLMResponse:
        from google import genai
        client = genai.Client(api_key=api_key)
        model_name = getattr(self.settings, "llm_model", "gemini-flash-latest")
        config_args: dict[str, Any] = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        full_chunks = []
        try:
            response_stream = client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config_args if config_args else None
            )
            for chunk in response_stream:
                if hasattr(chunk, "text") and chunk.text:
                    full_chunks.append(chunk.text)
                    if on_chunk:
                        try:
                            on_chunk(chunk.text)
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
            client = Groq(api_key=api_key)
            model_name = getattr(self.settings, "groq_model", "llama-3.3-70b-versatile")
            
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.4,
            }
            if tools:
                kwargs["tools"] = tools
            
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
                function_calls.append(SimpleNamespace(name=fn.name, args=args, id=tc.id))

            return LLMResponse(
                text=getattr(message, "content", None),
                function_calls=function_calls,
            )
        
        # Para Gemini, precisaria implementar similar
        raise NotImplementedError("generate_with_messages não implementado para Gemini")

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
        model_name = getattr(self.settings, "llm_model", "gemini-flash-latest")

        config_args: dict[str, Any] = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        if tools:
            declarations = []
            for tool in tools:
                decl = types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters_json_schema=tool["parameters"],
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

    def _generate_groq(
        self,
        contents: Any,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None,
        api_key: str,
    ) -> LLMResponse:
        from groq import Groq

        client = Groq(api_key=api_key)
        model_name = getattr(self.settings, "groq_model", "llama-3.3-70b-versatile")
        messages = self._contents_to_openai_messages(contents, system_instruction)

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.4,
        }
        
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

    def chat_with_functions_stream(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        on_function_call: callable | None = None,
        on_chunk: callable | None = None,
        force_tool: bool = False,
    ) -> str | None:
        """Chat com function calling nativo para Gemini e Groq."""
        active_provider = self.get_active_provider()
        if active_provider == "groq":
            return self._chat_groq_stream(
                system_instruction=system_instruction,
                messages=messages,
                tools=tools,
                on_function_call=on_function_call,
                on_chunk=on_chunk,
            )

        api_key = self._api_key_for("gemini")
        if not api_key:
            return None


        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            model_name = getattr(self.settings, "llm_model", "gemini-flash-latest")

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

            if tools:
                declarations = [
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=t.get("description", ""),
                        parameters_json_schema=t["parameters"],
                    )
                    for t in tools
                ]
                config_args["tools"] = [types.Tool(function_declarations=declarations)]
                config_args["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
                mode = "ANY" if force_tool else "AUTO"
                config_args["tool_config"] = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode=mode)
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
                
                # Procura por tools ou pedaços de texto dentro dos candidates
                for candidate in getattr(chunk, "candidates", []):
                    for part in getattr(getattr(candidate, "content", None), "parts", []):
                        fc = getattr(part, "function_call", None)
                        if fc:
                            args = dict(fc.args) if fc.args else {}
                            function_calls.append((fc.name, args, part))
                        # As vezes o chunk.text é None mas o part.text existe
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

            config2 = types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None,
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
                else:
                    for candidate in getattr(chunk, "candidates", []):
                        for part in getattr(getattr(candidate, "content", None), "parts", []):
                            if getattr(part, "text", None):
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

            # Fallback automático para Groq em caso de Rate Limit (429) ou erro na API Gemini
            groq_key = self._api_key_for("groq")
            if groq_key:
                print("[LLM] Fallback automático para Groq...")
                try:
                    return self._chat_groq_stream(
                        system_instruction=system_instruction or "",
                        messages=messages,
                        tools=tools,
                        on_function_call=on_function_call,
                        on_chunk=on_chunk,
                    )
                except Exception as groq_err:
                    print(f"[LLM] Falha no fallback Groq: {groq_err}")

            if "429" in str(e) or "resource_exhausted" in str(e).lower():
                raise ValueError("Limite de taxa da API Gemini excedido. Altere o provedor para 'Groq' nas Configurações do painel.")
            raise



    def _chat_groq_stream(
        self,
        system_instruction: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        on_function_call: callable | None = None,
        on_chunk: callable | None = None,
    ) -> str | None:
        """Function Calling nativo de 2 etapas para Groq (OpenAI format)."""
        from groq import Groq
        api_key = self._api_key_for("groq")
        if not api_key:
            return None

        client = Groq(api_key=api_key)
        model_name = getattr(self.settings, "groq_model", "llama-3.3-70b-versatile")

        formatted_messages: list[dict[str, Any]] = []
        if system_instruction:
            formatted_messages.append({"role": "system", "content": system_instruction})

        for m in messages or []:
            role = m.get("role", "user")
            content = m.get("content") or m.get("text") or ""
            if content:
                formatted_messages.append({"role": role, "content": content})

        groq_tools = None
        if tools:
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["parameters"],
                    },
                }
                for tool in tools
            ]

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": formatted_messages,
            "temperature": 0.4,
        }
        if groq_tools:
            kwargs["tools"] = groq_tools
            kwargs["tool_choice"] = "auto"

        try:
            completion = client.chat.completions.create(**kwargs)
            msg = completion.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None) or []

            if tool_calls:
                formatted_messages.append(msg)
                for tc in tool_calls:
                    fn_name = tc.function.name
                    args_raw = tc.function.arguments or "{}"
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                    except Exception:
                        args = {}

                    tool_result = ""
                    if on_function_call:
                        tool_result = str(on_function_call(fn_name, args))

                    formatted_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result or "Ação concluída com sucesso."
                    })

                final_completion = client.chat.completions.create(
                    model=model_name,
                    messages=formatted_messages,
                    temperature=0.4,
                )
                final_text = final_completion.choices[0].message.content or ""
                if on_chunk and final_text:
                    on_chunk(final_text)
                return final_text

            text = msg.content or ""
            if on_chunk and text:
                on_chunk(text)
            return text
        except Exception as e:
            err_msg = str(e)
            # Tratar caso o Groq retorne erro 400 tool_use_failed com failed_generation
            if "failed_generation" in err_msg and ("<function=" in err_msg or "function=" in err_msg):
                import re
                print(f"[Groq] Resgatando chamada de função do failed_generation: {err_msg}")
                match = re.search(r'<function=([a-zA-Z0-9_]+)(\(\{.*?\}\)|\{.*?\})', err_msg)
                if not match:
                    match = re.search(r'function=([a-zA-Z0-9_]+)(\(\{.*?\}\)|\{.*?\})', err_msg)
                
                if match:
                    fn_name = match.group(1)
                    raw_args = match.group(2).lstrip("(").rstrip(")")
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except Exception:
                        args = {}
                    
                    tool_result = ""
                    if on_function_call:
                        tool_result = str(on_function_call(fn_name, args))

                    # Gerar resposta final em linguagem natural
                    formatted_messages.append({"role": "user", "content": f"O resultado da ação {fn_name} foi: {tool_result}. Responda ao usuário com elegância em 1 frase."})
                    try:
                        kwargs_retry = {"model": model_name, "messages": formatted_messages, "temperature": 0.4}
                        final_res = client.chat.completions.create(**kwargs_retry)
                        txt = final_res.choices[0].message.content or tool_result
                        if on_chunk and txt:
                            on_chunk(txt)
                        return txt
                    except Exception:
                        return tool_result or "Ação processada com sucesso."

            print(f"[Groq Function Calling Stream] Erro: {e}")
            err_str = str(e).lower()
            if "429" in err_str or "rate_limit" in err_str or "limit" in err_str or "tpd" in err_str:
                # Marca a chave atual em cooldown (10 min)
                _key_rotator.mark_cooldown(api_key, duration_seconds=600.0)

                # Tenta a próxima chave do pool Groq
                next_key = _key_rotator.rotate_next("groq", self.settings)
                if next_key and next_key != api_key:
                    print(f"[Groq] Alternando para próxima chave do pool ({next_key[:8]}...)...")
                    try:
                        return self._chat_groq_stream(
                            system_instruction=system_instruction,
                            messages=messages,
                            tools=tools,
                            on_function_call=on_function_call,
                            on_chunk=on_chunk,
                        )
                    except Exception as retry_err:
                        print(f"[Groq] Falha com chave secundária: {retry_err}")

                # Fallback automático para Gemini se todas as chaves Groq falharem
                gemini_key = self._api_key_for("gemini")
                if gemini_key:
                    print("[LLM] Todas as chaves Groq esgotadas. Fallback automático de emergência para Gemini...")
                    try:
                        return self.chat_with_functions_stream(
                            system_instruction=system_instruction,
                            messages=messages,
                            tools=tools,
                            on_function_call=on_function_call,
                            on_chunk=on_chunk,
                        )
                    except Exception as gem_err:
                        print(f"[LLM] Falha no fallback para Gemini: {gem_err}")

                raise ValueError("Todas as chaves da API Groq atingiram o limite de cota (TPD/TPM). Por favor, adicione mais chaves em GROQ_API_KEYS no .env ou altere para 'Gemini' nas Configurações.")
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
