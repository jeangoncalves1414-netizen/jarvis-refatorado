from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

try:
    from mss import mss
    from PIL import Image
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


import os
import time
from pathlib import Path

CAPTURES_DIR = Path("data/captures")
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

# CORREÇÃO REVIEW 2: Cache global para validação de modelos Groq
_GROQ_MODEL_VALIDATION_CACHE: dict[str, bool] = {}


class VisionService:
    """Serviço de visão multimodal com Gemini ou Groq."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-flash-latest",
        provider: str = "gemini",
        groq_api_key: str | None = None,
    ):
        if not VISION_AVAILABLE:
            raise RuntimeError("Dependências não disponíveis: mss, Pillow")
        self.provider = provider.lower() if provider else "gemini"
        self.api_key = api_key or ""
        self.groq_api_key = groq_api_key or self.api_key
        self.model = model
        self.groq_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
        self._groq_client = None
        self._genai_client = None
        self._groq_model_invalid = False  # CORREÇÃO REVIEW 3: Marcador de modelo inválido
        
        # CORREÇÃO REVIEW 3 + 4: Validar que ao menos uma chave está configurada
        if not self.api_key and not self.groq_api_key:
            import logging
            logging.warning("[VisionService] Nenhuma chave de API configurada (Gemini ou Groq). Serviço pode falhar.")
        
        # CORREÇÃO REVIEW 3: Health-check do modelo Groq na inicialização
        if self.groq_api_key and self.provider == "groq":
            self._validate_groq_model()

    def _get_client(self, provider: str, api_key: str):
        if provider == "groq":
            if not self._groq_client:
                from groq import Groq
                self._groq_client = Groq(api_key=api_key)
            return self._groq_client
        else:
            from google import genai
            return genai.Client(api_key=api_key)
    
    def _validate_groq_model(self) -> None:
        """CORREÇÃO REVIEW 2+3: Valida se o modelo Groq configurado existe (com cache global).
        
        LIMITAÇÃO (FINDING 4): Esta validação usa uma chamada de texto simples (max_tokens=1)
        para verificar se o modelo existe, mas NÃO testa o path multimodal completo (image_url).
        Se o modelo existir mas não suportar visão, a validação passará e o primeiro analyze()
        falhará. Tradeoff aceito para evitar latência e custo de validação com imagem na init.
        """
        if not self.groq_api_key:
            return
        
        # CORREÇÃO REVIEW 2: Usar cache global para evitar validação repetida
        cache_key = f"{self.groq_model}:{mask_key(self.groq_api_key) if self.groq_api_key else 'no-key'}"
        if cache_key in _GROQ_MODEL_VALIDATION_CACHE:
            self._groq_model_invalid = not _GROQ_MODEL_VALIDATION_CACHE[cache_key]
            return
        
        try:
            from app.core.secrets_mask import mask_key
            client = self._get_client("groq", self.groq_api_key)
            # Chamada mínima de validação (não testa multimodal completo, ver docstring)
            client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": [{"type": "text", "text": "test"}]}],
                max_tokens=1
            )
            _GROQ_MODEL_VALIDATION_CACHE[cache_key] = True
            self._groq_model_invalid = False
        except Exception as e:
            error_str = str(e).lower()
            is_model_error = any(keyword in error_str for keyword in [
                "not found", "invalid model", "404", "model_not_found", "model not found"
            ])
            if is_model_error:
                import logging
                logging.warning(f"[VisionService] Modelo Groq '{self.groq_model}' inválido. Fallback para Gemini será usado.")
                _GROQ_MODEL_VALIDATION_CACHE[cache_key] = False
                self._groq_model_invalid = True

    def capture_screen(self) -> bytes:
        """Captura tela como bytes RGB."""
        with mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            return screenshot.rgb

    def capture_pil(self) -> Image.Image:
        """Captura tela como PIL Image."""
        with mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            return Image.frombytes("RGB", screenshot.size, screenshot.rgb)

    def capture_camera(self) -> Image.Image | None:
        """Captura um frame da webcam se OpenCV (cv2) estiver disponível."""
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None
            # Converte BGR (OpenCV) para RGB (PIL)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(frame_rgb)
        except Exception:
            return None

    def save_capture(self, image: Image.Image, prefix: str = "screen") -> tuple[str, str]:
        """
        Salva imagem em data/captures/ e retorna (filepath, filename).
        """
        filename = f"{prefix}_{int(time.time())}_{os.urandom(2).hex()}.jpg"
        filepath = CAPTURES_DIR / filename
        if image.width > 1600 or image.height > 900:
            image.thumbnail((1600, 900))
        image.save(filepath, format="JPEG", quality=85)
        return str(filepath), filename

    def analyze(self, prompt: str, image: Image.Image | None = None, api_key: str | None = None, provider: str | None = None) -> dict[str, Any]:
        """
        Analisa a tela ou uma imagem PIL fornecida.
        Retorna dict com {"reply": text, "capture_path": path, "capture_filename": filename}.
        """
        if image is None:
            image = self.capture_pil()

        filepath, filename = self.save_capture(image)

        # Automatic QR Code detection on the captured image
        qr_info = ""
        try:
            from app.services.qr_reader import QRReaderService, QR_AVAILABLE
            if QR_AVAILABLE:
                qr_svc = QRReaderService()
                codes = qr_svc._decode_pil(image)
                if codes:
                    qr_details = [f"#{i+1}: {c['data']} (Tipo: {c['type']})" for i, c in enumerate(codes)]
                    qr_info = "\n\n📌 [QR Code(s) Detectado(s) na Imagem]:\n" + "\n".join(qr_details)
        except Exception:
            pass

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_bytes = buffer.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode()

        active_provider = (provider or self.provider).lower()
        active_key = api_key or (self.groq_api_key if active_provider == "groq" else self.api_key)

        if not active_key:
            return {
                "ok": False,
                "reply": f"Chave de API do {active_provider.capitalize()} necessária para visão computacional.",
                "capture_path": filepath,
                "capture_filename": filename,
            }

        ok = True
        try:
            # CORREÇÃO REVIEW 3: Usar Gemini imediatamente se modelo Groq já foi marcado inválido
            if active_provider == "groq" and self._groq_model_invalid:
                if not self.api_key:
                    return {
                        "ok": False,
                        "reply": f"Modelo Groq '{self.groq_model}' inválido e chave Gemini não configurada.",
                        "capture_path": filepath,
                        "capture_filename": filename,
                    }
                active_provider = "gemini"
                active_key = self.api_key
            
            if active_provider == "groq":
                client = self._get_client("groq", active_key)
                res = client.chat.completions.create(
                    model=self.groq_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                        ]
                    }]
                )
                raw_text = res.choices[0].message.content or ""
                if "<think>" in raw_text and "</think>" in raw_text:
                    raw_text = raw_text.split("</think>")[-1].strip()
                reply = raw_text
            else:
                from google.genai import types
                client = self._get_client("gemini", active_key)
                response = client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/jpeg"
                        ),
                        prompt
                    ]
                )
                reply = response.text or "Nenhum detalhe visual extraído."
        except (ImportError, AttributeError, RuntimeError, KeyError, Exception) as e:
            # CORREÇÃO REVIEW 6: Exception tuple ampliado para capturar erros de rede/API
            # que podem ser lançados pelos clientes Groq/Gemini (httpx, requests, etc.)
            # CORREÇÃO PONTO 2: Verificar se é erro de modelo e tentar fallback para Gemini
            error_str = str(e).lower()
            is_model_error = any(keyword in error_str for keyword in [
                "not found", "invalid model", "404", "model_not_found", "model not found"
            ])
            
            if is_model_error and active_provider == "groq":
                # FALLBACK AUTOMÁTICO para Gemini Vision
                import logging
                logging.info(f"[Vision] Modelo Groq '{self.groq_model}' inválido ou obsoleto. Fallback para Gemini Vision.")
                self._groq_model_invalid = True  # CORREÇÃO REVIEW 3: Marcar para próximas chamadas
                try:
                    from google.genai import types
                    gemini_key = self.api_key  # Chave Gemini
                    if not gemini_key:
                        ok = False
                        reply = f"Fallback Gemini solicitado mas chave de API não configurada. Erro original: {e}"
                    else:
                        client = self._get_client("gemini", gemini_key)
                        response = client.models.generate_content(
                            model=self.model,
                            contents=[
                                types.Part.from_bytes(
                                    data=image_bytes,
                                    mime_type="image/jpeg"
                                ),
                                prompt
                            ]
                        )
                        reply = response.text or "Nenhum detalhe visual extraído."
                        ok = True
                except (ImportError, AttributeError, RuntimeError, Exception) as fallback_error:
                    # CORREÇÃO REVIEW 6: Exception tuple ampliado
                    ok = False
                    reply = f"Fallback para Gemini Vision também falhou: {fallback_error}. Erro Groq original: {e}"
            else:
                # Outro tipo de erro ou já estava usando Gemini
                ok = False
                reply = f"Erro na análise visual ({active_provider}): {e}"

        if qr_info:
            reply += qr_info

        return {
            "ok": ok,
            "reply": reply,
            "capture_path": filepath,
            "capture_filename": filename,
        }

    def analyze_bytes(self, prompt: str, image_bytes: bytes, api_key: str | None = None, provider: str | None = None) -> str:
        """Analisa uma imagem em bytes com prompt."""
        image_b64 = base64.b64encode(image_bytes).decode()
        active_provider = (provider or self.provider).lower()
        active_key = api_key or (self.groq_api_key if active_provider == "groq" else self.api_key)

        if not active_key:
            return f"Chave de API do {active_provider.capitalize()} necessária para visão computacional."

        try:
            # CORREÇÃO REVIEW 3: Usar Gemini imediatamente se modelo Groq já foi marcado inválido
            if active_provider == "groq" and self._groq_model_invalid:
                if not self.api_key:
                    return f"Modelo Groq '{self.groq_model}' inválido e chave Gemini não configurada."
                active_provider = "gemini"
                active_key = self.api_key
            
            if active_provider == "groq":
                client = self._get_client("groq", active_key)
                res = client.chat.completions.create(
                    model=self.groq_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                        ]
                    }]
                )
                raw_text = res.choices[0].message.content or ""
                if "<think>" in raw_text and "</think>" in raw_text:
                    raw_text = raw_text.split("</think>")[-1].strip()
                return raw_text
            else:
                from google.genai import types
                client = self._get_client("gemini", active_key)
                response = client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/png"
                        ),
                        prompt
                    ]
                )
                return response.text or "Sem resposta gerada."
        except (ImportError, AttributeError, RuntimeError, KeyError, Exception) as e:
            # CORREÇÃO REVIEW 6: Exception tuple ampliado para capturar erros de rede/API
            # CORREÇÃO PONTO 2: Fallback para Gemini se erro de modelo Groq
            error_str = str(e).lower()
            is_model_error = any(keyword in error_str for keyword in [
                "not found", "invalid model", "404", "model_not_found", "model not found"
            ])
            
            if is_model_error and active_provider == "groq":
                import logging
                logging.info(f"[Vision] Modelo Groq '{self.groq_model}' inválido. Fallback para Gemini Vision.")
                self._groq_model_invalid = True  # CORREÇÃO REVIEW 3: Marcar para próximas chamadas
                try:
                    gemini_key = self.api_key
                    if not gemini_key:
                        return f"Fallback Gemini solicitado mas chave não configurada. Erro original: {e}"
                    
                    from google.genai import types
                    client = self._get_client("gemini", gemini_key)
                    response = client.models.generate_content(
                        model=self.model,
                        contents=[
                            types.Part.from_bytes(
                                data=image_bytes,
                                mime_type="image/png"
                            ),
                            prompt
                        ]
                    )
                    return response.text or "Sem resposta gerada."
                except (ImportError, AttributeError, RuntimeError, Exception) as fallback_error:
                    # CORREÇÃO REVIEW 6: Exception tuple ampliado
                    return f"Fallback para Gemini falhou: {fallback_error}. Erro Groq: {e}"
            else:
                return f"Erro ao analisar imagem: {e}"


