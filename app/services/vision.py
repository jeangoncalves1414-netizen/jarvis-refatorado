from __future__ import annotations

import base64
from io import BytesIO

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


class VisionService:
    """Serviço de visão multimodal com Gemini ou Groq (Qwen 3.6 Vision)."""

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
        self._groq_client = None
        self._genai_client = None

    def _get_client(self, provider: str, api_key: str):
        if provider == "groq":
            if not self._groq_client:
                from groq import Groq
                self._groq_client = Groq(api_key=api_key)
            return self._groq_client
        else:
            from google import genai
            return genai.Client(api_key=api_key)

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

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_bytes = buffer.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode()

        active_provider = (provider or self.provider).lower()
        active_key = api_key or (self.groq_api_key if active_provider == "groq" else self.api_key)

        if not active_key:
            return {
                "reply": f"Chave de API do {active_provider.capitalize()} necessária para visão computacional.",
                "capture_path": filepath,
                "capture_filename": filename,
            }

        try:
            if active_provider == "groq":
                client = self._get_client("groq", active_key)
                res = client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
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
        except Exception as e:
            reply = f"Erro na análise visual ({active_provider}): {e}"

        return {
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
            if active_provider == "groq":
                client = self._get_client("groq", active_key)
                res = client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
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
        except Exception as e:
            return f"Erro na análise visual: {e}"


