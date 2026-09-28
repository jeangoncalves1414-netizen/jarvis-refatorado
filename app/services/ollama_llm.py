from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests não disponível. Ollama LLM será desabilitado.")


class OllamaLLM:
    """Cliente para Ollama (LLM local)."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests não instalado. Instale com: pip install requests")
        
        self.base_url = base_url
        self.model = model
        self._check_connection()
    
    def _check_connection(self):
        """Verifica se Ollama está rodando."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            if response.status_code == 200:
                logger.info(f"Ollama conectado em {self.base_url}")
            else:
                logger.info(f"Ollama respondeu com status {response.status_code}")
        except Exception:
            logger.info("Ollama não detectado localmente em %s (usando provedor configurado).", self.base_url)
    
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Gera texto usando Ollama."""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Falha ao gerar com Ollama: {e}")
            return None
    
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Chat usando Ollama."""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                logger.error(f"Ollama chat error: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Falha no chat Ollama: {e}")
            return None
    
    def list_models(self) -> list[str]:
        """Lista modelos disponíveis."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
            return []
        except Exception as e:
            logger.error(f"Falha ao listar modelos: {e}")
            return []
    
    def is_available(self) -> bool:
        """Verifica se Ollama está disponível."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
